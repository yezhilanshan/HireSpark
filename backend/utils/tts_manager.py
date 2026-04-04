"""
TTS 管理器 - 通过独立 HTTP TTS 服务进行语音合成
"""

from __future__ import annotations

import json
import os
from typing import Callable, Optional
from urllib import error, request

try:
    from tts_text import prepare_tts_text
except ImportError:
    from backend.tts_text import prepare_tts_text
from utils.config_loader import config
from utils.logger import get_logger

logger = get_logger(__name__)


def _as_bool(value, default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


class TTSManager:
    """远程 TTS 客户端，保持与旧接口兼容。"""

    def __init__(self):
        self.last_error: str = ""
        self.last_content_type: str = "audio/mpeg"
        self.last_provider: str = ""
        self.expected_provider: str = str(os.environ.get("TTS_PROVIDER", "")).strip().lower()
        self.mode = str(
            os.environ.get("TTS_MODE") or config.get("tts.mode", "remote")
        ).strip().lower()
        self.service_url = str(
            os.environ.get("TTS_SERVICE_URL")
            or config.get("tts.service_url", "http://127.0.0.1:5001")
        ).strip().rstrip("/")
        self.timeout = float(
            os.environ.get("TTS_TIMEOUT") or config.get("tts.timeout", 45)
        )
        self.enabled = _as_bool(
            os.environ.get("TTS_ENABLED"),
            config.get("tts.enabled", True),
        ) and self.mode == "remote" and bool(self.service_url)

        if self.enabled:
            logger.info(
                f"[TTS] 远程 TTS 已初始化 - Mode: {self.mode}, URL: {self.service_url}"
            )
            self._log_remote_provider_state()
        else:
            logger.warning(
                f"[TTS] TTS 当前未启用 - Mode: {self.mode}, URL: {self.service_url or 'N/A'}"
            )

    @staticmethod
    def prepare_text(text: str) -> str:
        return prepare_tts_text(text)

    def _synthesize_remote(
        self,
        text: str,
        interview_id: str = "",
        session_id: str = "",
    ) -> Optional[bytes]:
        payload_dict = {"text": text}
        normalized_interview_id = str(interview_id or "").strip()
        normalized_session_id = str(session_id or "").strip()
        if normalized_interview_id:
            payload_dict["interview_id"] = normalized_interview_id
        if normalized_session_id:
            payload_dict["session_id"] = normalized_session_id
        payload = json.dumps(payload_dict).encode("utf-8")
        req = request.Request(
            f"{self.service_url}/synthesize",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with request.urlopen(req, timeout=self.timeout) as resp:
                self.last_content_type = (
                    resp.headers.get("Content-Type", "audio/mpeg").split(";")[0].strip()
                    or "audio/mpeg"
                )
                self.last_provider = str(resp.headers.get("X-TTS-Provider", "")).strip().lower()
                audio_data = resp.read()
                if not audio_data:
                    self.last_error = "Remote TTS returned empty audio"
                    return None
                return audio_data
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            self.last_error = f"HTTP {exc.code}: {body[:200] or exc.reason}"
            return None
        except error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            self.last_error = f"TTS service unavailable: {reason}"
            return None
        except Exception as exc:
            self.last_error = str(exc)[:200]
            return None

    def _log_remote_provider_state(self) -> None:
        req = request.Request(f"{self.service_url}/health", method="GET")
        try:
            with request.urlopen(req, timeout=min(self.timeout, 3.0)) as resp:
                health = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            logger.warning(f"[TTS] 拉取远程健康状态失败：{str(exc)[:200]}")
            return

        active_provider = str(health.get("active_provider") or "").strip().lower()
        provider_order = health.get("provider_order") or []
        provider_errors = health.get("provider_errors") or {}
        logger.info(
            f"[TTS] 远程健康状态 - active_provider: {active_provider or 'unknown'}, "
            f"provider_order: {provider_order}"
        )
        if provider_errors:
            logger.warning(f"[TTS] Provider 加载错误：{provider_errors}")
        if (
            self.expected_provider
            and self.expected_provider != "auto"
            and active_provider
            and self.expected_provider != active_provider
        ):
            logger.warning(
                f"[TTS] Provider 与期望不一致：expected={self.expected_provider}, "
                f"active={active_provider}，可能已回退。"
            )

    def synthesize(
        self,
        text: str,
        callback: Optional[Callable[[bytes], None]] = None,
        interview_id: str = "",
        session_id: str = "",
    ) -> bool:
        if not self.enabled:
            self.last_error = "TTS not enabled"
            logger.warning("[TTS] TTS 未启用")
            return False

        if not text or not text.strip():
            self.last_error = "Empty text"
            logger.warning("[TTS] 文本为空")
            return False

        prepared_text = self.prepare_text(text)
        if not prepared_text:
            self.last_error = "Empty text after sanitization"
            logger.warning("[TTS] 文本清洗后为空")
            return False

        if prepared_text != text.strip():
            logger.info(
                f"[TTS] 文本已清洗 - 原始长度：{len(text)}, 清洗后长度：{len(prepared_text)}"
            )

        logger.info(f"[TTS] 开始远程合成：'{prepared_text[:30]}...'")
        self.last_error = ""
        self.last_content_type = "audio/mpeg"
        self.last_provider = ""
        audio_data = self._synthesize_remote(
            prepared_text,
            interview_id=interview_id,
            session_id=session_id,
        )
        if not audio_data:
            logger.error(f"[TTS] 远程合成失败：{self.last_error}")
            return False

        if callback:
            callback(audio_data)
        logger.info(f"[TTS] 远程合成完成 - 音频大小：{len(audio_data)} bytes")
        return True

    def synthesize_to_file(self, text: str, output_path: str) -> bool:
        try:
            def save_callback(audio_bytes):
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
                logger.info(f"[TTS] 已保存到：{output_path}")

            return self.synthesize(text, callback=save_callback)
        except Exception as exc:
            self.last_error = str(exc)[:200]
            logger.error(f"[TTS] 保存失败：{exc}", exc_info=True)
            return False

    def get_status(self) -> dict:
        status = {
            "enabled": self.enabled,
            "mode": self.mode,
            "service_url": self.service_url,
            "expected_provider": (
                self.expected_provider
                if self.expected_provider and self.expected_provider != "auto"
                else None
            ),
        }
        if not self.enabled:
            return status

        req = request.Request(f"{self.service_url}/health", method="GET")
        try:
            with request.urlopen(req, timeout=min(self.timeout, 3.0)) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                status["remote"] = body
        except Exception as exc:
            status["remote_error"] = str(exc)[:200]
        return status


tts_manager = TTSManager()
