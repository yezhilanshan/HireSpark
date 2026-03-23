"""
语音合成管理器 - 使用 Microsoft Edge TTS（稳定可靠）
替代阿里 DashScope TTS，避免 SDK 版本/权限问题
"""
import os
import asyncio
import tempfile
import uuid
from typing import Optional, Callable
from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)

# 检查 edge_tts 是否可用
try:
    import edge_tts
    HAS_EDGE_TTS = True
except ImportError:
    HAS_EDGE_TTS = False
    logger.warning("[TTS] edge_tts 未安装，请运行：pip install edge-tts")


class TTSManager:
    """TTS 管理器 - 使用 Microsoft Edge TTS"""

    def __init__(self):
        self.enabled = HAS_EDGE_TTS
        self.last_error: str = ""
        # Edge TTS 配置
        self.voice = 'zh-CN-XiaoxiaoNeural'  # 中文女声
        self.rate = '+0%'  # 语速
        self.volume = '+0%'  # 音量

        if self.enabled:
            logger.info(f"[TTS] Edge TTS 已初始化 - 音色：{self.voice}")
        else:
            logger.warning("[TTS] Edge TTS 不可用（未安装 edge-tts），TTS 功能不可用")

    def synthesize(self, text: str, callback: Optional[Callable[[bytes], None]] = None) -> bool:
        """
        合成语音并返回音频数据

        Args:
            text: 要合成的文本
            callback: 音频数据回调函数

        Returns:
            bool: 是否成功
        """
        if not self.enabled:
            logger.warning("[TTS] TTS 未启用（edge-tts 未安装）")
            self.last_error = "TTS not enabled - edge_tts not installed"
            return False

        if not text or not text.strip():
            logger.warning("[TTS] 文本为空")
            self.last_error = "Empty text"
            return False

        try:
            self.last_error = ""
            logger.info(f"[TTS] 开始合成：'{text[:30]}...'")

            # 在线程中运行异步合成
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                audio_data = loop.run_until_complete(
                    self._synthesize_async(text)
                )
            finally:
                loop.close()

            if audio_data:
                if callback:
                    callback(audio_data)
                logger.info(f"[TTS] 合成完成 - 音频大小：{len(audio_data)} bytes")
                return True

            self.last_error = "Synthesis returned empty audio"
            logger.error("[TTS] 合成失败：返回空音频")
            return False

        except Exception as e:
            error_msg = str(e)[:200]
            self.last_error = error_msg
            logger.error(f"[TTS] 合成失败：{error_msg}", exc_info=True)
            return False

    async def _synthesize_async(self, text: str) -> Optional[bytes]:
        """异步合成语音"""
        import edge_tts
        
        try:
            # 创建临时文件
            filename = f"tts_{uuid.uuid4().hex}.mp3"
            file_path = os.path.join(tempfile.gettempdir(), filename)

            # Edge TTS 异步合成
            communicate = edge_tts.Communicate(
                text=text,
                voice=self.voice,
                rate=self.rate,
                volume=self.volume,
            )
            await asyncio.wait_for(communicate.save(file_path), timeout=30)

            # 读取生成的文件
            with open(file_path, 'rb') as f:
                audio_data = f.read()

            # 删除临时文件
            try:
                os.unlink(file_path)
            except:
                pass

            return audio_data if audio_data else None

        except asyncio.TimeoutError:
            self.last_error = "TTS synthesis timeout"
            logger.error("[TTS] 合成超时")
            return None
        except Exception as e:
            self.last_error = str(e)[:200]
            logger.error(f"[TTS] 异步合成失败：{e}")
            return None

    def synthesize_to_file(self, text: str, output_path: str) -> bool:
        """
        合成语音并保存为文件

        Args:
            text: 要合成的文本
            output_path: 输出文件路径

        Returns:
            bool: 是否成功
        """
        if not self.enabled:
            return False

        try:
            def save_callback(audio_bytes):
                with open(output_path, 'wb') as f:
                    f.write(audio_bytes)
                logger.info(f"[TTS] 已保存到：{output_path}")

            ok = self.synthesize(text, callback=save_callback)
            return ok

        except Exception as e:
            logger.error(f"[TTS] 保存失败：{e}", exc_info=True)
            return False


# 创建全局 TTS 管理器实例
tts_manager = TTSManager()


# 创建全局 TTS 管理器实例
tts_manager = TTSManager()
