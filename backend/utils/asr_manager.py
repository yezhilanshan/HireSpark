"""
阿里 DashScope ASR 语音识别管理器
基于 Paraformer 实时语音转写，支持多会话并发
"""
import os
import json
import queue
import time
import threading
import logging
import re
import wave
from collections import deque
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, Optional, Deque, List

logger = logging.getLogger(__name__)

try:
    import audioop
except Exception:  # Python 3.13+ 可能不可用
    audioop = None


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
        vad_in_speech: bool = False
        vad_speech_run: int = 0
        vad_silence_run: int = 0
        vad_pre_roll: Deque[bytes] = field(default_factory=lambda: deque(maxlen=2))
        vad_last_keepalive_at: float = 0.0
        vad_last_frame_at: float = 0.0
        vad_input_frames: int = 0
        vad_forwarded_frames: int = 0
        vad_dropped_frames: int = 0
        vad_keepalive_frames: int = 0

    class AsrManager:
        """ASR 管理器 - 支持多会话实时语音识别"""

        def __init__(self):
            self.enabled = False
            self.api_key = self._get_api_key()
            self.sample_rate = 16000
            self.format_pcm = "pcm"
            self.model = os.environ.get("ASR_MODEL", "fun-asr-realtime")
            self.final_model = os.environ.get("ASR_FINAL_MODEL", "qwen3-asr-1.7b")
            self.final_language = os.environ.get("ASR_FINAL_LANGUAGE", "").strip()
            self.final_timeout = int(os.environ.get("ASR_FINAL_TIMEOUT", "60") or 60)
            self.final_enable_itn = str(
                os.environ.get("ASR_FINAL_ENABLE_ITN", "true")
            ).strip().lower() not in {"0", "false", "no", "off"}
            self.aligner_model = os.environ.get("ASR_ALIGNER_MODEL", "qwen3-forcedaligner-0.6b").strip()
            self.aligner_timeout = int(os.environ.get("ASR_ALIGNER_TIMEOUT", "90") or 90)
            self.aligner_enabled = str(
                os.environ.get("ASR_ALIGNER_ENABLED", "true")
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
            self.last_align_error = ""
            self.vad_enabled = str(
                os.environ.get("ASR_STREAM_VAD_ENABLED", "true")
            ).strip().lower() not in {"0", "false", "no", "off"}
            self.vad_rms_threshold = self._get_env_int(
                "ASR_STREAM_VAD_RMS_THRESHOLD",
                default=520,
                minimum=120,
            )
            self.vad_enter_frames = self._get_env_int(
                "ASR_STREAM_VAD_ENTER_FRAMES",
                default=2,
                minimum=1,
            )
            self.vad_exit_frames = self._get_env_int(
                "ASR_STREAM_VAD_EXIT_FRAMES",
                default=4,
                minimum=1,
            )
            self.vad_pre_roll_frames = self._get_env_int(
                "ASR_STREAM_VAD_PRE_ROLL_FRAMES",
                default=3,
                minimum=1,
            )
            self.vad_keepalive_interval = self._get_env_float(
                "ASR_STREAM_VAD_KEEPALIVE_SECONDS",
                default=0.6,
                minimum=0.0,
            )
            self.vad_idle_reset_seconds = self._get_env_float(
                "ASR_STREAM_VAD_IDLE_RESET_SECONDS",
                default=1.5,
                minimum=0.4,
            )

            logger.info(
                "[ASR] 流式VAD配置 enabled=%s rms_threshold=%s enter=%s exit=%s pre_roll=%s keepalive=%.2fs idle_reset=%.2fs",
                self.vad_enabled,
                self.vad_rms_threshold,
                self.vad_enter_frames,
                self.vad_exit_frames,
                self.vad_pre_roll_frames,
                self.vad_keepalive_interval,
                self.vad_idle_reset_seconds,
            )
            logger.info(
                "[ASR] 模型配置 realtime=%s final=%s aligner=%s aligner_enabled=%s",
                self.model,
                self.final_model,
                self.aligner_model or "disabled",
                self.aligner_enabled,
            )

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

        @staticmethod
        def _get_env_int(name: str, default: int, minimum: int = 0) -> int:
            raw_value = str(os.environ.get(name, default)).strip()
            try:
                parsed = int(raw_value)
            except Exception:
                parsed = default
            return max(minimum, parsed)

        @staticmethod
        def _get_env_float(name: str, default: float, minimum: float = 0.0) -> float:
            raw_value = str(os.environ.get(name, default)).strip()
            try:
                parsed = float(raw_value)
            except Exception:
                parsed = default
            return max(minimum, parsed)

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
            state.vad_pre_roll = deque(maxlen=self.vad_pre_roll_frames)

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
                        frames_to_send = self._filter_audio_frames_by_vad(state, audio_data)
                        for frame in frames_to_send:
                            state.recognition.send_audio_frame(frame)
                except queue.Empty:
                    self._apply_vad_idle_reset(state)
                    continue
                except Exception as e:
                    logger.error(f"[ASR] 发送音频失败 - stream={stream_id}: {e}")
                    state.is_running = False
                    state.stop_worker = True
                    if state.callback and state.callback.on_error_callback:
                        state.callback.on_error_callback(str(e))
                    break

            logger.info(f"[ASR] 音频工作线程已停止 - stream={stream_id}")

        def _apply_vad_idle_reset(self, state: AsrStreamState) -> None:
            if (
                not self.vad_enabled
                or not state.vad_in_speech
                or state.vad_last_frame_at <= 0
            ):
                return
            idle_seconds = time.monotonic() - state.vad_last_frame_at
            if idle_seconds < self.vad_idle_reset_seconds:
                return
            state.vad_in_speech = False
            state.vad_speech_run = 0
            state.vad_silence_run = 0
            state.vad_pre_roll.clear()
            logger.debug(
                "[ASR] VAD空闲超时回落 stream=%s idle=%.2fs",
                state.stream_id,
                idle_seconds,
            )

        def _frame_rms(self, audio_data: bytes) -> int:
            if not audio_data:
                return 0
            if audioop is not None:
                try:
                    return int(audioop.rms(audio_data, 2))
                except Exception:
                    pass

            sample_count = len(audio_data) // 2
            if sample_count <= 0:
                return 0

            energy = 0.0
            view = memoryview(audio_data)
            for index in range(0, sample_count * 2, 2):
                sample = int.from_bytes(view[index:index + 2], byteorder="little", signed=True)
                energy += float(sample * sample)

            return int((energy / sample_count) ** 0.5)

        def _filter_audio_frames_by_vad(self, state: AsrStreamState, audio_data: bytes) -> List[bytes]:
            if not audio_data:
                return []

            state.vad_input_frames += 1
            state.vad_last_frame_at = time.monotonic()

            if not self.vad_enabled:
                state.vad_forwarded_frames += 1
                return [audio_data]

            rms = self._frame_rms(audio_data)
            now = time.monotonic()
            is_speech_frame = rms >= self.vad_rms_threshold
            frames_to_send: List[bytes] = []
            keepalive_sent = False

            if is_speech_frame:
                state.vad_speech_run += 1
                state.vad_silence_run = 0
                if state.vad_in_speech:
                    frames_to_send.append(audio_data)
                else:
                    state.vad_pre_roll.append(audio_data)
                    if state.vad_speech_run >= self.vad_enter_frames:
                        state.vad_in_speech = True
                        frames_to_send.extend(state.vad_pre_roll)
                        state.vad_pre_roll.clear()
            else:
                state.vad_speech_run = 0
                if state.vad_in_speech:
                    state.vad_silence_run += 1
                    if state.vad_silence_run <= self.vad_exit_frames:
                        frames_to_send.append(audio_data)
                    else:
                        state.vad_in_speech = False
                        state.vad_silence_run = 0
                        state.vad_pre_roll.clear()
                else:
                    state.vad_pre_roll.append(audio_data)

            if (
                not frames_to_send
                and not state.vad_in_speech
                and not is_speech_frame
                and self.vad_keepalive_interval > 0
                and now - state.vad_last_keepalive_at >= self.vad_keepalive_interval
            ):
                frames_to_send.append(b"\x00" * len(audio_data))
                state.vad_last_keepalive_at = now
                state.vad_keepalive_frames += 1
                keepalive_sent = True

            if frames_to_send:
                state.vad_forwarded_frames += len(frames_to_send)
                if keepalive_sent:
                    state.vad_dropped_frames += 1
            else:
                state.vad_dropped_frames += 1
                if state.vad_dropped_frames % 120 == 0:
                    logger.debug(
                        "[ASR] VAD已过滤噪声帧 stream=%s dropped=%s threshold=%s",
                        state.stream_id,
                        state.vad_dropped_frames,
                        self.vad_rms_threshold,
                    )

            return frames_to_send

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

            if self.vad_enabled:
                logger.info(
                    "[ASR] stream=%s VAD统计 input=%s forwarded=%s dropped=%s keepalive=%s",
                    stream_id,
                    state.vad_input_frames,
                    state.vad_forwarded_frames,
                    state.vad_dropped_frames,
                    state.vad_keepalive_frames,
                )

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

        def transcribe_file_with_meta(
            self,
            audio_path: str,
            prompt: str = "",
            language: str = "",
            enable_itn: Optional[bool] = None,
        ) -> Dict[str, Any]:
            self.last_transcribe_error = ""

            if not self.enabled:
                self.last_transcribe_error = "ASR is not enabled"
                logger.warning("[ASR] 高精复写不可用：未启用")
                return {"text": "", "word_timestamps": [], "confidence": None}

            if MultiModalConversation is None:
                self.last_transcribe_error = "dashscope MultiModalConversation is unavailable"
                logger.warning("[ASR] 高精复写不可用：当前 DashScope SDK 不支持 MultiModalConversation")
                return {"text": "", "word_timestamps": [], "confidence": None}

            resolved_audio_path = str(Path(audio_path).expanduser().resolve())
            if not os.path.isfile(resolved_audio_path):
                self.last_transcribe_error = f"audio file not found: {resolved_audio_path}"
                logger.warning(f"[ASR] 高精复写失败：音频文件不存在 - {resolved_audio_path}")
                return {"text": "", "word_timestamps": [], "confidence": None}

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
                    return {"text": "", "word_timestamps": [], "confidence": None}

                payload = self._extract_transcription_payload(response)
                transcript = str(payload.get("text") or "").strip()
                if not transcript:
                    self.last_transcribe_error = "empty transcription result"
                    logger.warning(
                        f"[ASR] 高精复写返回空文本 - model={self.final_model} file={resolved_audio_path}"
                    )
                    return {"text": "", "word_timestamps": [], "confidence": None}

                logger.info(
                    f"[ASR] 高精复写完成 - model={self.final_model} file={resolved_audio_path} "
                    f"text_len={len(transcript)}"
                )
                return payload
            except Exception as exc:
                self.last_transcribe_error = str(exc)
                logger.error(f"[ASR] 高精复写异常：{exc}")
                return {"text": "", "word_timestamps": [], "confidence": None}

        def transcribe_file(
            self,
            audio_path: str,
            prompt: str = "",
            language: str = "",
            enable_itn: Optional[bool] = None,
        ) -> str:
            payload = self.transcribe_file_with_meta(
                audio_path=audio_path,
                prompt=prompt,
                language=language,
                enable_itn=enable_itn,
            )
            return str(payload.get("text") or "").strip()

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

        @staticmethod
        def _extract_json_from_text(text: str) -> Dict[str, Any]:
            payload = str(text or "").strip()
            if not payload:
                return {}
            match = re.search(r"\{[\s\S]*\}", payload)
            candidate = match.group(0) if match else payload
            try:
                parsed = json.loads(candidate)
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

        def _object_to_dict(self, data: Any, depth: int = 0) -> Any:
            if depth > 6:
                return None
            if isinstance(data, (str, int, float, bool)) or data is None:
                return data
            if isinstance(data, list):
                return [self._object_to_dict(item, depth + 1) for item in data]
            if isinstance(data, tuple):
                return [self._object_to_dict(item, depth + 1) for item in data]
            if isinstance(data, dict):
                return {str(k): self._object_to_dict(v, depth + 1) for k, v in data.items()}
            if hasattr(data, "__dict__"):
                return self._object_to_dict(vars(data), depth + 1)
            return str(data)

        def _collect_word_timestamps(self, data: Any) -> List[Dict[str, Any]]:
            candidates: List[Dict[str, Any]] = []

            def walk(node: Any):
                if isinstance(node, dict):
                    text = node.get("text") or node.get("word") or node.get("token")
                    start = node.get("start_ms", node.get("start", node.get("begin", node.get("start_time"))))
                    end = node.get("end_ms", node.get("end", node.get("stop", node.get("end_time"))))
                    if text is not None and start is not None and end is not None:
                        try:
                            start_v = float(start)
                            end_v = float(end)
                            if end_v < start_v:
                                start_v, end_v = end_v, start_v
                            candidates.append({
                                "text": str(text).strip(),
                                "start_ms": round(max(0.0, start_v), 2),
                                "end_ms": round(max(0.0, end_v), 2),
                                "confidence": float(node.get("confidence")) if node.get("confidence") is not None else None,
                            })
                        except Exception:
                            pass
                    for value in node.values():
                        walk(value)
                elif isinstance(node, list):
                    for item in node:
                        walk(item)

            walk(data)
            dedup: List[Dict[str, Any]] = []
            seen = set()
            for item in sorted(candidates, key=lambda x: (x["start_ms"], x["end_ms"])):
                key = (item.get("text"), item.get("start_ms"), item.get("end_ms"))
                if key in seen or not item.get("text"):
                    continue
                seen.add(key)
                dedup.append(item)
            return dedup

        def _extract_transcription_payload(self, response: Any) -> Dict[str, Any]:
            text = self._extract_transcription_text(response)
            response_dict = self._object_to_dict(response)
            word_timestamps = self._collect_word_timestamps(response_dict)
            confidences = [item["confidence"] for item in word_timestamps if item.get("confidence") is not None]
            confidence = (sum(confidences) / len(confidences)) if confidences else None
            return {
                "text": str(text or "").strip(),
                "word_timestamps": word_timestamps,
                "confidence": round(float(confidence), 4) if confidence is not None else None,
                "raw": response_dict,
            }

        @staticmethod
        def _build_char_tokens(text: str) -> List[str]:
            tokens: List[str] = []
            buffer = ""
            for char in str(text or "").strip():
                if re.match(r"[A-Za-z0-9]", char):
                    buffer += char
                else:
                    if buffer:
                        tokens.append(buffer)
                        buffer = ""
                    if not char.isspace():
                        tokens.append(char)
            if buffer:
                tokens.append(buffer)
            return [token for token in tokens if token]

        @staticmethod
        def _get_wav_duration_ms(audio_path: str) -> float:
            try:
                with wave.open(str(audio_path), "rb") as wav_file:
                    frame_count = wav_file.getnframes()
                    frame_rate = wav_file.getframerate() or 16000
                    return max(0.0, (frame_count / float(frame_rate)) * 1000.0)
            except Exception:
                return 0.0

        def _build_naive_alignment(self, transcript: str, audio_path: str = "") -> Dict[str, Any]:
            tokens = self._build_char_tokens(transcript)
            if not tokens:
                return {"word_timestamps": [], "mode": "naive", "confidence": None}

            duration_ms = self._get_wav_duration_ms(audio_path)
            if duration_ms <= 0.0:
                duration_ms = max(600.0, len(tokens) * 220.0)
            per_token = max(80.0, duration_ms / max(1, len(tokens)))

            cursor = 0.0
            timestamps: List[Dict[str, Any]] = []
            for token in tokens:
                start_ms = cursor
                end_ms = min(duration_ms, start_ms + per_token)
                timestamps.append(
                    {
                        "text": token,
                        "start_ms": round(start_ms, 2),
                        "end_ms": round(end_ms, 2),
                        "confidence": 0.5,
                    }
                )
                cursor = end_ms

            return {"word_timestamps": timestamps, "mode": "naive", "confidence": 0.5}

        def align_transcript(
            self,
            audio_path: str,
            transcript: str,
            language: str = "",
        ) -> Dict[str, Any]:
            self.last_align_error = ""
            normalized_transcript = str(transcript or "").strip()
            if not normalized_transcript:
                self.last_align_error = "empty transcript"
                return {"word_timestamps": [], "mode": "empty", "confidence": None}

            resolved_audio_path = str(Path(audio_path or "").expanduser().resolve())
            if not os.path.isfile(resolved_audio_path):
                self.last_align_error = f"audio file not found: {resolved_audio_path}"
                return self._build_naive_alignment(normalized_transcript, audio_path="")

            if (
                not self.enabled
                or not self.aligner_enabled
                or MultiModalConversation is None
                or not self.aligner_model
            ):
                return self._build_naive_alignment(normalized_transcript, resolved_audio_path)

            try:
                dashscope.api_key = self.api_key
                if self.base_http_api_url:
                    dashscope.base_http_api_url = self.base_http_api_url

                align_prompt = (
                    "You are a forced aligner. Return strict JSON only. "
                    "Schema: {\"word_timestamps\":[{\"text\":\"word\",\"start_ms\":0,\"end_ms\":120,\"confidence\":0.95}]}. "
                    "No markdown, no extra keys."
                )
                language_hint = str(language or self.final_language or "").strip()
                user_text = (
                    f"Transcript:\n{normalized_transcript}\n"
                    f"{'Language: ' + language_hint if language_hint else ''}".strip()
                )
                response = MultiModalConversation.call(
                    api_key=self.api_key,
                    model=self.aligner_model,
                    messages=[
                        {"role": "system", "content": [{"text": align_prompt}]},
                        {"role": "user", "content": [{"audio": resolved_audio_path}, {"text": user_text}]},
                    ],
                    result_format="message",
                    timeout=self.aligner_timeout,
                )
                if getattr(response, "status_code", None) != 200:
                    self.last_align_error = str(
                        getattr(response, "message", "")
                        or getattr(response, "code", "")
                        or "unknown aligner error"
                    ).strip()
                    logger.warning(
                        "[ASR] 强制对齐失败，切换到启发式对齐 - model=%s error=%s",
                        self.aligner_model,
                        self.last_align_error,
                    )
                    return self._build_naive_alignment(normalized_transcript, resolved_audio_path)

                response_text = self._extract_transcription_text(response)
                align_json = self._extract_json_from_text(response_text)
                raw_word_timestamps = align_json.get("word_timestamps") if isinstance(align_json, dict) else None
                if not isinstance(raw_word_timestamps, list) or not raw_word_timestamps:
                    self.last_align_error = "aligner returned empty word timestamps"
                    return self._build_naive_alignment(normalized_transcript, resolved_audio_path)

                word_timestamps = self._collect_word_timestamps({"word_timestamps": raw_word_timestamps})
                if not word_timestamps:
                    self.last_align_error = "invalid aligner word timestamps"
                    return self._build_naive_alignment(normalized_transcript, resolved_audio_path)

                confidences = [item["confidence"] for item in word_timestamps if item.get("confidence") is not None]
                confidence = (sum(confidences) / len(confidences)) if confidences else None
                return {
                    "word_timestamps": word_timestamps,
                    "mode": "forced_aligner",
                    "confidence": round(float(confidence), 4) if confidence is not None else None,
                }
            except Exception as exc:
                self.last_align_error = str(exc)
                logger.warning("[ASR] 强制对齐异常，切换到启发式对齐: %s", exc)
                return self._build_naive_alignment(normalized_transcript, resolved_audio_path)

    asr_manager = AsrManager()

except ImportError as e:
    print(f"[ASR] DashScope SDK 未安装：{e}")
    asr_manager = None
