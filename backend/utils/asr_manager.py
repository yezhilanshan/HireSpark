"""
阿里 DashScope ASR 语音识别管理器
基于 Paraformer 实时语音转写，带 VAD 语音活动检测
"""
import os
import time
import threading
import queue
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    import dashscope
    from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult

    class AsrCallbackHandler(RecognitionCallback):
        """ASR 回调处理器"""

        def __init__(self, on_result: Callable[[str, bool], None], on_error: Callable[[str], None] = None):
            self.on_result_callback = on_result
            self.on_error_callback = on_error
            self.is_open = False
            self.wait_open_event = threading.Event()  # 用于通知主线程服务已打开

        def on_open(self) -> None:
            self.is_open = True
            logger.info(f"[ASR] 识别服务已打开 - {datetime.now().strftime('%H:%M:%S')}")
            # 通知等待的线程
            self.wait_open_event.set()  # type: ignore

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

        def on_event(self, result: RecognitionResult) -> None:
            # 详细调试日志
            logger.info(f"[ASR] on_event 被调用 - result={result}")

            sentence = result.get_sentence()
            logger.info(f"[ASR] get_sentence() 返回：{sentence}")

            if sentence and 'text' in sentence:
                text = sentence['text']
                is_end = RecognitionResult.is_sentence_end(sentence)

                # 关键调试：输出 is_end 状态
                logger.info(f"[ASR] 识别文本：'{text}' | is_end={is_end} | type={type(is_end)}")

                if is_end:
                    logger.info(f"[ASR] ★★★ 完整识别，准备调用回调 ★★★")
                    logger.info(f"[ASR] on_result_callback={self.on_result_callback}")
                    if self.on_result_callback:
                        logger.info(f"[ASR] 调用回调函数 handle_result('{text}', True)")
                        self.on_result_callback(text, True)
                        logger.info(f"[ASR] 回调函数执行完毕")
                    else:
                        logger.warning(f"[ASR] on_result_callback 为空，无法调用")
                else:
                    logger.info(f"[ASR] --- 中间结果，跳过 ---")
            else:
                logger.warning(f"[ASR] sentence 为空或没有 text 字段")

    class AsrManager:
        """ASR 管理器 - 处理实时语音识别"""

        def __init__(self):
            self.enabled = False
            self.api_key = self._get_api_key()
            self.recognition: Optional[Recognition] = None
            self.callback: Optional[AsrCallbackHandler] = None
            self.is_running = False
            self.audio_queue = queue.Queue()
            self.worker_thread: Optional[threading.Thread] = None
            self.stop_worker = False
            self.on_recognition_result: Optional[Callable[[str], None]] = None

            # ASR 参数
            self.sample_rate = 16000
            self.format_pcm = 'pcm'
            self.block_size = 3200

            # 初始化
            if self.api_key:
                dashscope.api_key = self.api_key
                self.enabled = True
                logger.info("[ASR] DashScope ASR 已初始化")
            else:
                logger.warning("[ASR] 未配置 API Key，ASR 功能不可用")

        def _get_api_key(self) -> Optional[str]:
            """获取 API Key"""
            return os.environ.get('DASHSCOPE_API_KEY') or os.environ.get('BAILIAN_API_KEY')

        def start(self, on_result: Callable[[str], None] = None) -> bool:
            """启动 ASR 识别"""
            if not self.enabled:
                logger.warning("[ASR] ASR 未启用")
                return False

            try:
                self.on_recognition_result = on_result

                def handle_result(text: str, is_end: bool):
                    if is_end and self.on_recognition_result:
                        self.on_recognition_result(text)

                def handle_error(error: str):
                    logger.error(f"[ASR] 错误：{error}")
                    self.is_running = False
                    self.callback.wait_open_event.set()  # 出错时也设置事件，避免阻塞

                self.callback = AsrCallbackHandler(handle_result, handle_error)

                # 创建识别对象，使用带 VAD 的实时模型
                self.recognition = Recognition(
                    model='fun-asr-realtime',  # 带 VAD 的实时识别
                    format=self.format_pcm,
                    sample_rate=self.sample_rate,
                    callback=self.callback
                )

                self.recognition.start()
                self.is_running = True
                self.stop_worker = False

                # 等待 on_open 回调（最多 5 秒）
                logger.info("[ASR] 等待识别服务打开...")
                if not self.callback.wait_open_event.wait(timeout=5):
                    logger.warning("[ASR] 等待服务打开超时，但仍将继续尝试")
                else:
                    logger.info("[ASR] 识别服务已打开")

                # 启动音频处理线程
                self.worker_thread = threading.Thread(target=self._audio_worker, daemon=True)
                self.worker_thread.start()

                logger.info("[ASR] 识别服务已启动")
                return True

            except Exception as e:
                logger.error(f"[ASR] 启动失败：{e}")
                return False

        def send_audio(self, audio_data: bytes):
            """发送音频数据"""
            logger.debug(f"[ASR] 请求发送音频：{len(audio_data)} 字节")
            if self.is_running and self.recognition:
                self.audio_queue.put(audio_data)
                logger.debug(f"[ASR] 音频已加入队列")
            else:
                logger.warning(f"[ASR] ASR 未运行：is_running={self.is_running}, recognition={self.recognition is not None}")

        def _audio_worker(self):
            """音频处理工作线程"""
            logger.info("[ASR] 音频工作线程已启动")
            while self.is_running and not self.stop_worker:
                try:
                    # 从队列获取音频数据
                    audio_data = self.audio_queue.get(timeout=0.1)
                    logger.info(f"[ASR] 从队列获取音频：{len(audio_data)} 字节，is_open={self.callback.is_open if self.callback else 'N/A'}")
                    # 等待 ASR 服务打开后再发送数据
                    if self.callback and self.callback.is_open and self.recognition:
                        self.recognition.send_audio_frame(audio_data)
                        logger.info("[ASR] 已发送音频帧到 DashScope")
                    else:
                        logger.warning(f"[ASR] 服务未打开，跳过音频数据")
                except queue.Empty:
                    continue
                except Exception as e:
                    logger.error(f"[ASR] 发送音频失败：{e}")
                    break
            logger.info("[ASR] 音频工作线程已停止")

        def stop(self):
            """停止 ASR 识别"""
            self.stop_worker = True
            self.is_running = False

            # 清空队列
            while not self.audio_queue.empty():
                try:
                    self.audio_queue.get_nowait()
                except queue.Empty:
                    break

            # 等待线程结束
            if self.worker_thread and self.worker_thread.is_alive():
                self.worker_thread.join(timeout=1)

            # 停止识别服务
            if self.recognition:
                try:
                    self.recognition.stop()
                except Exception as e:
                    logger.error(f"[ASR] 停止失败：{e}")
                self.recognition = None

            logger.info("[ASR] 识别服务已停止")

        def is_available(self) -> bool:
            """检查 ASR 是否可用"""
            return self.enabled and self.is_running


    # 创建全局 ASR 管理器实例
    asr_manager = AsrManager()

except ImportError as e:
    print(f"[ASR] DashScope SDK 未安装：{e}")
    asr_manager = None
