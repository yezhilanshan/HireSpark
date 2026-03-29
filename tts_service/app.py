from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import threading
import uuid
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from backend.tts_text import prepare_tts_text

app = FastAPI(title="Standalone TTS Service", version="1.0.0")
logger = logging.getLogger("tts_service")


class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    language: Optional[str] = None
    speaker: Optional[str] = None
    speed: Optional[float] = None
    voice: Optional[str] = None
    rate: Optional[str] = None
    volume: Optional[str] = None


class EdgeTTSProvider:
    name = "edge"
    media_type = "audio/mpeg"

    def __init__(self):
        import edge_tts

        self.edge_tts = edge_tts
        self.voice = os.environ.get("TTS_EDGE_VOICE", "zh-CN-XiaoxiaoNeural")
        self.rate = os.environ.get("TTS_EDGE_RATE", "+0%")
        self.volume = os.environ.get("TTS_EDGE_VOLUME", "+0%")
        self.timeout = float(os.environ.get("TTS_EDGE_TIMEOUT", "30"))

    async def synthesize(self, req: SynthesizeRequest) -> bytes:
        filename = f"tts_{uuid.uuid4().hex}.mp3"
        file_path = os.path.join(tempfile.gettempdir(), filename)
        communicate = self.edge_tts.Communicate(
            text=req.text,
            voice=req.voice or self.voice,
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
            "voice": self.voice,
            "timeout": self.timeout,
        }


class MeloTTSProvider:
    name = "melo"
    media_type = "audio/wav"

    def __init__(self):
        from melo.api import TTS

        self.tts_cls = TTS
        self.device = os.environ.get("TTS_MELO_DEVICE", "auto")
        self.default_language = os.environ.get("TTS_MELO_LANGUAGE", "ZH").upper()
        self.default_speaker = os.environ.get("TTS_MELO_SPEAKER", "").strip()
        self.default_speed = float(os.environ.get("TTS_MELO_SPEED", "1.0"))
        self._models = {}
        self._lock = threading.Lock()

    def _get_model(self, language: str):
        language = (language or self.default_language).upper()
        if language not in self._models:
            self._models[language] = self.tts_cls(language=language, device=self.device)
        return self._models[language]

    def _synthesize_sync(self, req: SynthesizeRequest) -> bytes:
        language = (req.language or self.default_language).upper()
        model = self._get_model(language)
        speakers = dict(model.hps.data.spk2id or {})
        if not speakers:
            raise ValueError("Melo model has no available speakers")

        raw_speaker = req.speaker if req.speaker not in (None, "") else self.default_speaker
        speaker_key = next(iter(speakers.keys()))
        if raw_speaker not in (None, ""):
            candidate = raw_speaker.strip() if isinstance(raw_speaker, str) else raw_speaker
            if candidate in speakers:
                speaker_key = candidate
            elif isinstance(candidate, str) and candidate.isdigit() and int(candidate) in speakers:
                speaker_key = int(candidate)
            else:
                available = ", ".join(map(str, speakers.keys()))
                raise ValueError(
                    f"Unknown Melo speaker '{raw_speaker}'. Available speakers: {available}"
                )

        speaker_id = speakers[speaker_key]
        if not isinstance(speaker_id, int):
            try:
                speaker_id = int(speaker_id)
            except Exception as exc:
                raise ValueError(
                    f"Invalid Melo speaker id '{speaker_id}' for key '{speaker_key}'"
                ) from exc

        speed = req.speed or self.default_speed
        if not isinstance(speed, (float, int)):
            raise ValueError("Melo speed must be a number")

        tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
        tmp_path = tmp_file.name
        tmp_file.close()
        try:
            with self._lock:
                model.tts_to_file(
                    req.text,
                    speaker_id,
                    output_path=tmp_path,
                    speed=float(speed),
                    format="wav",
                    quiet=True,
                )
            with open(tmp_path, "rb") as f:
                audio_data = f.read()
            if not audio_data:
                raise RuntimeError("Melo returned empty wav")
            return audio_data
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def synthesize(self, req: SynthesizeRequest) -> bytes:
        return await asyncio.to_thread(self._synthesize_sync, req)

    def health(self) -> dict:
        return {
            "provider": self.name,
            "device": self.device,
            "default_language": self.default_language,
            "default_speaker": self.default_speaker or None,
            "loaded_languages": sorted(self._models.keys()),
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
    provider_name = os.environ.get("TTS_PROVIDER", "auto").strip().lower()
    strict_mode = str(os.environ.get("TTS_PROVIDER_STRICT", "")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if provider_name == "auto":
        return ["edge"] if strict_mode else ["edge", "melo"]
    if provider_name == "melo":
        return ["melo"] if strict_mode else ["melo", "edge"]
    if provider_name == "edge":
        return ["edge"] if strict_mode else ["edge", "melo"]
    raise RuntimeError(f"Unsupported TTS_PROVIDER: {provider_name}")


def _load_single_provider(name: str) -> ProviderRuntime:
    if name == "melo":
        return ProviderRuntime(MeloTTSProvider())
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
        "provider_strict": str(os.environ.get("TTS_PROVIDER_STRICT", "")).strip().lower() in {"1", "true", "yes", "on"},
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

    for runtime in providers:
        try:
            audio_data = await runtime.synthesize(normalized_req)
            if not audio_data:
                raise RuntimeError("TTS provider returned empty audio")
            runtime.error = None
            return Response(
                content=audio_data,
                media_type=runtime.media_type,
                headers={"X-TTS-Provider": runtime.name},
            )
        except ValueError as exc:
            runtime.error = str(exc)[:300]
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        except Exception as exc:
            runtime.error = str(exc)[:300]
            synth_errors.append({"provider": runtime.name, "error": runtime.error})

    raise HTTPException(status_code=502, detail=synth_errors)
