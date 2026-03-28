"""
阿里 DashScope ASR 语音识别管理器
基于 Paraformer 实时语音转写，支持多会话并发
"""
import os
import queue
import threading
import logging
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Dict, Optional

logger = logging.getLogger(__name__)


def _load_local_dotenv() -> None:
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    backend_root = Path(__file__).resolve().parents[1]
    project_root = Path(__file__).resolve().parents[2]
    for dotenv_path in (project_root / ".env", backend_root / ".env"):
        if dotenv_path.exists():
            load_dotenv(dotenv_path=dotenv_path, override=False)


_load_local_dotenv()

try:
    import dashscope
    try:
        from dashscope import MultiModalConversation
    except Exception:
        MultiModalConversation = None
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    class AsrCallbackHandler(RecognitionCallback):
        """ASR 回调处理器"""

        def __init__(
            self,
            on_final: Callable[[str], None],
            on_partial: Optional[Callable[[str], None]] = None,
            on_error: Optional[Callable[[str], None]] = None,
        ):
            self.on_final_callback = on_final
            self.on_partial_callback = on_partial
            self.on_error_callback = on_error
            self.is_open = False
            self.wait_open_event = threading.Event()

        def on_open(self) -> None:
            self.is_open = True
            logger.info(f"[ASR] 识别服务已打开 - {datetime.now().strftime('%H:%M:%S')}")
            self.wait_open_event.set()

        def on_close(self) -> None:
            self.is_open = False
            logger.info(f"[ASR] 识别服务已关闭 - {datetime.now().strftime('%H:%M:%S')}")

        def on_complete(self) -> None:
            logger.info(f"[ASR] 识别完成 - {datetime.now().strftime('%H:%M:%S')}")

        def on_error(self, message) -> None:
            error_msg = f"{message.message} (RequestID: {message.request_id})"
            logger.error(f"[ASR] 错误：{error_msg}")
            if self.on_error_callback:
                self.on_error_callback(error_msg)
            self.wait_open_event.set()

        def on_event(self, result: RecognitionResult) -> None:
            sentence = result.get_sentence()
            if not sentence or "text" not in sentence:
                return

            text = str(sentence.get("text") or "").strip()
            if not text:
                return

            is_end = RecognitionResult.is_sentence_end(sentence)
            logger.info(f"[ASR] 识别文本：'{text}' | is_end={is_end}")

            if is_end:
                if self.on_final_callback:
                    self.on_final_callback(text)
            elif self.on_partial_callback:
                self.on_partial_callback(text)

    @dataclass
    class AsrStreamState:
        stream_id: str
        recognition: Optional[Recognition] = None
        callback: Optional[AsrCallbackHandler] = None
        is_running: bool = False
        audio_queue: queue.Queue = field(default_factory=queue.Queue)
        worker_thread: Optional[threading.Thread] = None
        stop_worker: bool = False

    class AsrManager:
        """ASR 管理器 - 支持多会话实时语音识别"""

        def __init__(self):
            self.enabled = False
            self.api_key = self._get_api_key()
            self.sample_rate = 16000
            self.format_pcm = "pcm"
            self.model = os.environ.get("ASR_MODEL", "fun-asr-realtime")
            self.final_model = os.environ.get("ASR_FINAL_MODEL", "qwen3-asr-flash")
            self.final_language = os.environ.get("ASR_FINAL_LANGUAGE", "").strip()
            self.final_timeout = int(os.environ.get("ASR_FINAL_TIMEOUT", "60") or 60)
            self.final_enable_itn = str(
                os.environ.get("ASR_FINAL_ENABLE_ITN", "true")
            ).strip().lower() not in {"0", "false", "no", "off"}
            self.base_http_api_url = str(
                os.environ.get("DASHSCOPE_BASE_HTTP_API_URL")
                or os.environ.get("ASR_FINAL_BASE_HTTP_API_URL")
                or ""
            ).strip()
            self._default_stream_id = "__default__"
            self._lock = threading.RLock()
            self._streams: Dict[str, AsrStreamState] = {}
            self.last_transcribe_error = ""

            if self.api_key:
                dashscope.api_key = self.api_key
                if self.base_http_api_url:
                    dashscope.base_http_api_url = self.base_http_api_url
                self.enabled = True
                logger.info("[ASR] DashScope ASR 已初始化")
            else:
                logger.warning("[ASR] 未配置 API Key，ASR 功能不可用")

        @staticmethod
        def _get_api_key() -> Optional[str]:
            return os.environ.get("DASHSCOPE_API_KEY") or os.environ.get("BAILIAN_API_KEY")

        def start_session(
            self,
            stream_id: str,
            on_result: Callable[[str], None],
            on_partial: Optional[Callable[[str], None]] = None,
            on_error: Optional[Callable[[str], None]] = None,
        ) -> bool:
            if not self.enabled:
                logger.warning("[ASR] ASR 未启用")
                return False

            self.stop_session(stream_id)

            state = AsrStreamState(stream_id=stream_id)

            def handle_error(error: str):
                logger.error(f"[ASR] stream={stream_id} 错误：{error}")
                state.is_running = False
                state.stop_worker = True
                with self._lock:
                    current = self._streams.get(stream_id)
                if current:
                    current.is_running = False
                    current.stop_worker = True
                if on_error:
                    on_error(error)

            try:
                state.callback = AsrCallbackHandler(on_result, on_partial, handle_error)
                state.recognition = Recognition(
                    model=self.model,
                    format=self.format_pcm,
                    sample_rate=self.sample_rate,
                    callback=state.callback,
                )
                with self._lock:
                    self._streams[stream_id] = state
                state.recognition.start()
                state.is_running = True
                state.stop_worker = False

                logger.info(f"[ASR] 等待识别服务打开 - stream={stream_id}")
                opened = state.callback.wait_open_event.wait(timeout=5)
                if not opened:
                    logger.warning(f"[ASR] 等待服务打开超时 - stream={stream_id}")
                    self.stop_session(stream_id)
                    return False
                if not state.callback.is_open or not state.is_running:
                    logger.error(f"[ASR] 服务未成功打开 - stream={stream_id}")
                    self.stop_session(stream_id)
                    return False

                state.worker_thread = threading.Thread(
                    target=self._audio_worker,
                    args=(stream_id,),
                    daemon=True,
                )
                state.worker_thread.start()
                logger.info(f"[ASR] 识别服务已启动 - stream={stream_id}")
                return True
            except Exception as e:
                with self._lock:
                    self._streams.pop(stream_id, None)
                if state.recognition:
                    try:
                        state.recognition.stop()
                    except Exception:
                        pass
                logger.error(f"[ASR] 启动失败 - stream={stream_id}: {e}")
                return False

        def send_audio(self, stream_id: str, audio_data: Optional[bytes] = None):
            if audio_data is None:
                audio_data = stream_id  # 兼容旧签名 send_audio(audio_data)
                stream_id = self._default_stream_id

            with self._lock:
                state = self._streams.get(stream_id)

            if not state or not state.is_running or not state.recognition:
                logger.warning(f"[ASR] stream={stream_id} 未运行")
                return

            state.audio_queue.put(audio_data)

        def _audio_worker(self, stream_id: str):
            logger.info(f"[ASR] 音频工作线程已启动 - stream={stream_id}")
            while True:
                with self._lock:
                    state = self._streams.get(stream_id)

                if not state or not state.is_running or state.stop_worker:
                    break

                try:
                    audio_data = state.audio_queue.get(timeout=0.1)
                    if state.callback and state.callback.is_open and state.recognition:
                        state.recognition.send_audio_frame(audio_data)
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"[ASR] 发送音频失败 - stream={stream_id}: {e}")
                    state.is_running = False
                    state.stop_worker = True
                    if state.callback and state.callback.on_error_callback:
                        state.callback.on_error_callback(str(e))
                    break

            logger.info(f"[ASR] 音频工作线程已停止 - stream={stream_id}")

        def stop_session(self, stream_id: str):
            with self._lock:
                state = self._streams.pop(stream_id, None)

            if not state:
                return

            state.stop_worker = True
            state.is_running = False

            while not state.audio_queue.empty():
                try:
                    state.audio_queue.get_nowait()
                except queue.Empty:
                    break

            if (
                state.worker_thread
                and state.worker_thread.is_alive()
                and state.worker_thread is not threading.current_thread()
            ):
                state.worker_thread.join(timeout=1)

            if state.recognition:
                try:
                    state.recognition.stop()
                except Exception as e:
                    logger.error(f"[ASR] 停止失败 - stream={stream_id}: {e}")

            logger.info(f"[ASR] 识别服务已停止 - stream={stream_id}")

        def is_available(self, stream_id: Optional[str] = None) -> bool:
            if stream_id is None:
                stream_id = self._default_stream_id
            with self._lock:
                state = self._streams.get(stream_id)
            return bool(self.enabled and state and state.is_running)

        # 兼容旧接口
        def start(
            self,
            on_result: Optional[Callable[[str], None]] = None,
            on_partial: Optional[Callable[[str], None]] = None,
            on_error: Optional[Callable[[str], None]] = None,
        ) -> bool:
            return self.start_session(
                self._default_stream_id,
                on_result or (lambda _text: None),
                on_partial=on_partial,
                on_error=on_error,
            )

        def stop(self):
            self.stop_session(self._default_stream_id)

        def transcribe_file(
            self,
            audio_path: str,
            prompt: str = "",
            language: str = "",
            enable_itn: Optional[bool] = None,
        ) -> str:
            self.last_transcribe_error = ""

            if not self.enabled:
                self.last_transcribe_error = "ASR is not enabled"
                logger.warning("[ASR] 高精复写不可用：未启用")
                return ""

            if MultiModalConversation is None:
                self.last_transcribe_error = "dashscope MultiModalConversation is unavailable"
                logger.warning("[ASR] 高精复写不可用：当前 DashScope SDK 不支持 MultiModalConversation")
                return ""

            resolved_audio_path = str(Path(audio_path).expanduser().resolve())
            if not os.path.isfile(resolved_audio_path):
                self.last_transcribe_error = f"audio file not found: {resolved_audio_path}"
                logger.warning(f"[ASR] 高精复写失败：音频文件不存在 - {resolved_audio_path}")
                return ""

            try:
                dashscope.api_key = self.api_key
                if self.base_http_api_url:
                    dashscope.base_http_api_url = self.base_http_api_url

                messages = []
                context_prompt = str(prompt or "").strip()
                if context_prompt:
                    messages.append({
                        "role": "system",
                        "content": [{"text": context_prompt}],
                    })
                messages.append({
                    "role": "user",
                    "content": [{"audio": resolved_audio_path}],
                })

                asr_options = {
                    "enable_itn": self.final_enable_itn if enable_itn is None else bool(enable_itn),
                }
                language_value = str(language or self.final_language or "").strip()
                if language_value:
                    asr_options["language"] = language_value

                response = MultiModalConversation.call(
                    api_key=self.api_key,
                    model=self.final_model,
                    messages=messages,
                    result_format="message",
                    asr_options=asr_options,
                    timeout=self.final_timeout,
                )

                if getattr(response, "status_code", None) != 200:
                    self.last_transcribe_error = str(
                        getattr(response, "message", "")
                        or getattr(response, "code", "")
                        or "unknown transcription error"
                    ).strip()
                    logger.error(
                        f"[ASR] 高精复写失败 - model={self.final_model} file={resolved_audio_path} "
                        f"error={self.last_transcribe_error}"
                    )
                    return ""

                transcript = self._extract_transcription_text(response)
                if not transcript:
                    self.last_transcribe_error = "empty transcription result"
                    logger.warning(
                        f"[ASR] 高精复写返回空文本 - model={self.final_model} file={resolved_audio_path}"
                    )
                    return ""

                logger.info(
                    f"[ASR] 高精复写完成 - model={self.final_model} file={resolved_audio_path} "
                    f"text_len={len(transcript)}"
                )
                return transcript.strip()
            except Exception as exc:
                self.last_transcribe_error = str(exc)
                logger.error(f"[ASR] 高精复写异常：{exc}")
                return ""

        @staticmethod
        def _extract_transcription_text(response) -> str:
            output_text = getattr(getattr(response, "output", None), "text", None)
            if output_text:
                return str(output_text).strip()

            output = getattr(response, "output", None)
            choices = getattr(output, "choices", None) if output else None
            if choices and isinstance(choices, list):
                first = choices[0]
                message = first.get("message", {}) if isinstance(first, dict) else {}
                content = message.get("content", []) if isinstance(message, dict) else []
                if isinstance(content, list):
                    parts = []
                    for item in content:
                        if isinstance(item, dict):
                            text = str(item.get("text") or "").strip()
                            if text:
                                parts.append(text)
                        elif isinstance(item, str):
                            text = item.strip()
                            if text:
                                parts.append(text)
                    if parts:
                        return "\n".join(parts).strip()

            return ""

    asr_manager = AsrManager()

except ImportError as e:
    print(f"[ASR] DashScope SDK 未安装：{e}")
    asr_manager = None
