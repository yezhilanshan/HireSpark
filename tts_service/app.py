from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
import random
import tempfile
import threading
import uuid
from typing import Any, Optional, cast

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from backend.tts_text import prepare_tts_text

app = FastAPI(title="Standalone TTS Service", version="1.0.0")
logger = logging.getLogger("tts_service")


def _as_bool(value: Optional[str], default: bool) -> bool:
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _first_env(*keys: str, default: str = "") -> str:
    for key in keys:
        value = str(os.environ.get(key, "") or "").strip()
        if value:
            return value
    return default


def _canonical_provider_name(name: str) -> str:
    normalized = str(name or "").strip().lower()
    if normalized in {"edge", "edge-tts", "edge_tts", "edgetts"}:
        return "edge"
    if normalized in {"cosyvoice", "cosy", "dashscope", "cosyvoice-v3-flash"}:
        return "cosyvoice"
    if normalized in {"auto", ""}:
        return "auto"
    return normalized


def _load_env_from_repo_root() -> None:
    """Load root .env for standalone service launches that miss shell env vars."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.exists():
        return

    try:
        content = env_path.read_text(encoding="utf-8")
    except Exception:
        return

    loaded_any = False
    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or key in os.environ:
            continue
        normalized_value = value.strip().strip('"').strip("'")
        os.environ[key] = normalized_value
        loaded_any = True

    if loaded_any:
        logger.info("[TTS Service] Loaded missing runtime environment from repository .env")


_load_env_from_repo_root()


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    interview_id: Optional[str] = None
    session_id: Optional[str] = None
    language: Optional[str] = None
    speaker: Optional[str] = None
    speed: Optional[float] = None
    voice: Optional[str] = None
    rate: Optional[str] = None
    volume: Optional[str] = None


class CosyVoiceProvider:
    name = "cosyvoice"

    _MEDIA_TYPE_BY_AUDIO_FORMAT = {
        "mp3": "audio/mpeg",
        "wav": "audio/wav",
        "pcm": "audio/pcm",
        "opus": "audio/ogg",
    }

    def __init__(self):
        import dashscope
        from dashscope.audio.tts_v2 import AudioFormat, SpeechSynthesizer

        self.dashscope = dashscope
        self.audio_format_enum = AudioFormat
        self.speech_synthesizer = SpeechSynthesizer
        self.model = _first_env(
            "TTS_COSYVOICE_MODEL",
            "TTS_MODEL",
            default="cosyvoice-v3-flash",
        )
        self.voice = _first_env(
            "TTS_COSYVOICE_VOICE",
            "TTS_VOICE",
            default="Chinese_dramatic_storyteller_vv1",
        )
        self.timeout = float(os.environ.get("TTS_COSYVOICE_TIMEOUT", "30"))
        self.retry_count = max(int(os.environ.get("TTS_COSYVOICE_RETRIES", "1")), 0)
        self.audio_format_name = (
            os.environ.get("TTS_COSYVOICE_FORMAT", "MP3_22050HZ_MONO_256KBPS").strip()
            or "MP3_22050HZ_MONO_256KBPS"
        )
        self.audio_format = self._resolve_audio_format(self.audio_format_name)
        inferred_media_type = self._infer_media_type(self.audio_format)
        configured_media_type = os.environ.get("TTS_COSYVOICE_MEDIA_TYPE", "").strip()
        self.media_type = configured_media_type or inferred_media_type

        api_key = (
            os.environ.get("DASHSCOPE_API_KEY")
            or os.environ.get("BAILIAN_API_KEY")
            or ""
        ).strip()
        if not api_key:
            raise RuntimeError("Missing DASHSCOPE_API_KEY or BAILIAN_API_KEY for CosyVoice")
        self.dashscope.api_key = api_key

    def _resolve_audio_format(self, format_name: str):
        candidate = format_name.strip().upper()
        resolved = getattr(self.audio_format_enum, candidate, None)
        if resolved is not None:
            return resolved
        logger.warning(
            "[TTS Service] Unknown TTS_COSYVOICE_FORMAT=%s, fallback to MP3_22050HZ_MONO_256KBPS",
            format_name,
        )
        return self.audio_format_enum.MP3_22050HZ_MONO_256KBPS

    def _infer_media_type(self, audio_format) -> str:
        fmt = str(getattr(audio_format, "format", "") or "").strip().lower()
        return self._MEDIA_TYPE_BY_AUDIO_FORMAT.get(fmt, "audio/mpeg")

    def _validate_audio_payload(self, audio_data: Any) -> bytes:
        if isinstance(audio_data, memoryview):
            audio_data = audio_data.tobytes()
        elif isinstance(audio_data, bytearray):
            audio_data = bytes(audio_data)

        if not isinstance(audio_data, bytes) or not audio_data:
            raise RuntimeError("DashScope TTS returned empty audio")

        if self.media_type == "audio/mpeg":
            is_mp3 = audio_data.startswith(b"ID3") or (
                len(audio_data) >= 2 and audio_data[0] == 0xFF and (audio_data[1] & 0xE0) == 0xE0
            )
            if not is_mp3:
                raise RuntimeError("DashScope TTS returned invalid MP3 payload")
        elif self.media_type == "audio/wav":
            is_wav = len(audio_data) >= 12 and audio_data[:4] == b"RIFF" and audio_data[8:12] == b"WAVE"
            if not is_wav:
                raise RuntimeError("DashScope TTS returned invalid WAV payload")

        return audio_data

    async def synthesize(self, req: SynthesizeRequest) -> bytes:
        selected_voice = (req.voice or "").strip() or self.voice
        if not selected_voice:
            raise ValueError("CosyVoice voice is required")

        timeout_millis: Optional[int]
        if self.timeout > 0:
            timeout_millis = int(self.timeout * 1000)
        else:
            timeout_millis = None

        def _invoke_synthesizer() -> Any:
            synthesizer = cast(Any, self.speech_synthesizer)(
                model=self.model,
                voice=selected_voice,
                format=self.audio_format,
            )
            return synthesizer.call(req.text, timeout_millis=timeout_millis)

        last_error: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            try:
                response = await asyncio.wait_for(
                    asyncio.to_thread(_invoke_synthesizer),
                    timeout=max(self.timeout + 5.0, 10.0),
                )
                return self._validate_audio_payload(response)
            except Exception as exc:
                last_error = exc
                if attempt >= self.retry_count:
                    raise
                logger.warning(
                    "[TTS Service] CosyVoice synthesis attempt %s/%s failed, retrying: %s",
                    attempt + 1,
                    self.retry_count + 1,
                    str(exc)[:180],
                )
                await asyncio.sleep(0.2 * (attempt + 1))

        if last_error is not None:
            raise last_error
        raise RuntimeError("CosyVoice synthesis failed")

    def health(self) -> dict:
        return {
            "provider": self.name,
            "model": self.model,
            "voice": self.voice or None,
            "format": self.audio_format.name,
            "timeout": self.timeout,
            "retries": self.retry_count,
            "media_type": self.media_type,
        }


class EdgeTTSProvider:
    name = "edge"
    media_type = "audio/mpeg"

    def __init__(self):
        import edge_tts

        self.edge_tts = edge_tts
        self.voice = os.environ.get("TTS_EDGE_VOICE", "").strip()
        self.female_voice = os.environ.get("TTS_EDGE_FEMALE_VOICE", "zh-CN-XiaoxiaoNeural").strip()
        self.male_voice = os.environ.get("TTS_EDGE_MALE_VOICE", "zh-CN-YunyangNeural").strip()
        self.auto_gender = str(os.environ.get("TTS_EDGE_AUTO_GENDER", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self.random_by_interview = str(os.environ.get("TTS_EDGE_RANDOM_BY_INTERVIEW", "1")).strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._interview_voice_map: dict[str, str] = {}
        self._rng = random.Random()
        self._voice_turn = 0
        self._voice_lock = threading.Lock()
        self.rate = os.environ.get("TTS_EDGE_RATE", "+0%")
        self.volume = os.environ.get("TTS_EDGE_VOLUME", "+0%")
        self.timeout = float(os.environ.get("TTS_EDGE_TIMEOUT", "30"))

    def _random_voice(self) -> str:
        candidates = []
        if self.female_voice:
            candidates.append(self.female_voice)
        if self.male_voice and self.male_voice != self.female_voice:
            candidates.append(self.male_voice)
        if not candidates:
            return "zh-CN-XiaoxiaoNeural"
        return self._rng.choice(candidates)

    def _resolve_voice(
        self,
        request_voice: Optional[str],
        interview_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> str:
        if request_voice and request_voice.strip():
            return request_voice.strip()
        if self.voice:
            return self.voice
        if not self.auto_gender:
            return self.female_voice

        normalized_interview_id = str(interview_id or "").strip()
        normalized_session_id = str(session_id or "").strip()
        bind_key = normalized_interview_id or normalized_session_id

        if self.random_by_interview and bind_key:
            with self._voice_lock:
                if bind_key not in self._interview_voice_map:
                    self._interview_voice_map[bind_key] = self._random_voice()
                return self._interview_voice_map[bind_key]

        with self._voice_lock:
            voice = self.female_voice if self._voice_turn % 2 == 0 else self.male_voice
            self._voice_turn += 1
        return voice

    async def synthesize(self, req: SynthesizeRequest) -> bytes:
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        selected_voice = self._resolve_voice(
            req.voice,
            interview_id=req.interview_id,
            session_id=req.session_id,
        )
        communicate = self.edge_tts.Communicate(
            text=req.text,
            voice=selected_voice,
            rate=req.rate or self.rate,
            volume=req.volume or self.volume,
        )
        try:
            await asyncio.wait_for(communicate.save(file_path), timeout=self.timeout)
            with open(file_path, "rb") as f:
                return f.read()
        finally:
            try:
                os.unlink(file_path)
            except OSError:
                pass

    def health(self) -> dict:
        return {
            "provider": self.name,
            "voice": self.voice or None,
            "female_voice": self.female_voice,
            "male_voice": self.male_voice,
            "auto_gender": self.auto_gender,
            "random_by_interview": self.random_by_interview,
            "bound_interview_voice_count": len(self._interview_voice_map),
            "timeout": self.timeout,
        }


class ProviderRuntime:
    def __init__(self, provider):
        self.provider = provider
        self.error: Optional[str] = None

    @property
    def name(self) -> str:
        return self.provider.name

    @property
    def media_type(self) -> str:
        return self.provider.media_type

    async def synthesize(self, req: SynthesizeRequest) -> bytes:
        return await self.provider.synthesize(req)

    def health(self) -> dict:
        details = self.provider.health()
        details["error"] = self.error
        return details


def _resolve_provider_order() -> list[str]:
    explicit_order_raw = str(os.environ.get("TTS_PROVIDER_ORDER", "") or "").strip()
    if explicit_order_raw:
        explicit_order: list[str] = []
        for token in explicit_order_raw.split(","):
            canonical = _canonical_provider_name(token)
            if canonical in {"cosyvoice", "edge"} and canonical not in explicit_order:
                explicit_order.append(canonical)
        if explicit_order:
            return explicit_order

    requested = _canonical_provider_name(os.environ.get("TTS_PROVIDER", "auto") or "auto")
    strict = _as_bool(os.environ.get("TTS_PROVIDER_STRICT"), False)

    if requested in {"", "auto"}:
        order = ["cosyvoice", "edge"]
    elif requested == "cosyvoice":
        order = ["cosyvoice", "edge"]
    elif requested == "edge":
        order = ["edge"]
    else:
        logger.warning(
            "[TTS Service] Unknown TTS_PROVIDER=%s, fallback to auto(cosyvoice->edge)",
            requested,
        )
        order = ["cosyvoice", "edge"]

    if strict and order:
        return [order[0]]
    return order


def _load_single_provider(name: str) -> ProviderRuntime:
    if name == "cosyvoice":
        return ProviderRuntime(CosyVoiceProvider())
    if name == "edge":
        return ProviderRuntime(EdgeTTSProvider())
    raise RuntimeError(f"Unsupported provider: {name}")


def _load_providers():
    provider_order = _resolve_provider_order()
    loaded_providers: list[ProviderRuntime] = []
    load_errors: dict[str, str] = {}

    for name in provider_order:
        try:
            loaded_providers.append(_load_single_provider(name))
        except Exception as exc:
            load_errors[name] = str(exc)

    return loaded_providers, load_errors, provider_order


def _classify_tts_error(error_message: str) -> str:
    message = (error_message or "").strip().lower()
    if not message:
        return "upstream_error"
    if "timeout" in message:
        return "upstream_timeout"
    if "api key" in message or "unauthorized" in message or "forbidden" in message:
        return "upstream_auth_error"
    if "empty audio" in message or "invalid mp3" in message or "invalid wav" in message:
        return "upstream_invalid_audio"
    return "upstream_error"


providers, provider_errors, provider_order = _load_providers()

loaded_names = [runtime.name for runtime in providers]
logger.info(
    "[TTS Service] provider_order=%s, loaded=%s",
    provider_order,
    loaded_names,
)
if provider_errors:
    logger.warning("[TTS Service] provider load errors: %s", provider_errors)


@app.get("/health")
async def health():
    ready = len(providers) > 0
    return {
        "status": "healthy" if ready else "degraded",
        "ready": ready,
        "provider_strict": _as_bool(os.environ.get("TTS_PROVIDER_STRICT"), False),
        "provider_order": provider_order,
        "active_provider": providers[0].name if providers else None,
        "providers": [runtime.health() for runtime in providers],
        "provider_errors": provider_errors,
    }


@app.post("/synthesize")
async def synthesize(req: SynthesizeRequest):
    if not providers:
        raise HTTPException(
            status_code=503,
            detail=provider_errors or "No TTS provider available",
        )

    prepared_text = prepare_tts_text(req.text)
    if not prepared_text:
        raise HTTPException(status_code=400, detail="Text is empty after sanitization")

    normalized_req = req.model_copy(update={"text": prepared_text})
    synth_errors: list[dict[str, str]] = []
    primary_provider = providers[0].name if providers else ""
    primary_error: str = ""
    primary_error_code: str = "upstream_error"

    for runtime in providers:
        try:
            audio_data = await runtime.synthesize(normalized_req)
            if not audio_data:
                raise RuntimeError("TTS provider returned empty audio")
            runtime.error = None
            headers = {"X-TTS-Provider": runtime.name}
            if primary_provider and runtime.name != primary_provider and primary_error:
                headers["X-TTS-Fallback-From"] = primary_provider
                headers["X-TTS-Fallback-Reason"] = primary_error_code
                logger.warning(
                    "[TTS Service] fallback applied: %s -> %s, reason_code=%s",
                    primary_provider,
                    runtime.name,
                    primary_error_code,
                )
            return Response(
                content=audio_data,
                media_type=runtime.media_type,
                headers=headers,
            )
        except ValueError as exc:
            runtime.error = str(exc)[:300]
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            runtime.error = str(exc)[:300]
            synth_errors.append({"provider": runtime.name, "error": runtime.error})
            if not primary_error:
                primary_error = runtime.error
                primary_error_code = _classify_tts_error(primary_error)

    raise HTTPException(status_code=502, detail=synth_errors)
