"""
Chunked interview video upload + storage service.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import shutil
import subprocess
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from utils.config_loader import config


class VideoUploadService:
    def __init__(self, logger=None):
        self.logger = logger
        self._lock = threading.RLock()
        self._sessions: Dict[str, Dict[str, Any]] = {}

        self.upload_root = Path(config.get("video_upload.tmp_dir", "backend/uploads/video_uploads"))
        self.final_root = Path(config.get("video_upload.final_dir", "backend/uploads/interview_videos"))
        self.chunk_size_hint = int(config.get("video_upload.chunk_size_hint", 2 * 1024 * 1024))
        self.default_expires_seconds = int(config.get("video_upload.upload_expires_seconds", 3600))
        self.enable_transcode = bool(config.get("video_upload.enable_transcode", True))
        self.keep_raw = bool(config.get("video_upload.keep_raw", True))

        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.final_root.mkdir(parents=True, exist_ok=True)

        self.signing_secret = str(
            config.get("video_upload.playback_signing_secret", "")
            or config.get("server.secret_key", "")
            or "interview-replay-secret"
        )

    @staticmethod
    def _sanitize_filename(value: str) -> str:
        raw = str(value or "").strip().replace(" ", "_")
        safe = "".join(ch for ch in raw if ch.isalnum() or ch in {"_", "-", "."})
        return safe[:120] if safe else "video"

    def _build_session_dir(self, upload_id: str) -> Path:
        return self.upload_root / upload_id

    def init_upload(self, session_id: str, interview_id: str, mime_type: str = "video/webm", codec: str = "") -> Dict[str, Any]:
        upload_id = f"upload_{uuid.uuid4().hex}"
        now = int(time.time())
        expires_at = now + self.default_expires_seconds

        with self._lock:
            session_dir = self._build_session_dir(upload_id)
            session_dir.mkdir(parents=True, exist_ok=True)
            self._sessions[upload_id] = {
                "upload_id": upload_id,
                "session_id": str(session_id or "").strip(),
                "interview_id": str(interview_id or "").strip(),
                "mime_type": str(mime_type or "video/webm").strip(),
                "codec": str(codec or "").strip(),
                "created_at": now,
                "expires_at": expires_at,
                "parts": {},
                "session_dir": str(session_dir),
            }

        return {
            "upload_id": upload_id,
            "chunk_size_hint": self.chunk_size_hint,
            "expires_at": expires_at,
        }

    def save_chunk(self, upload_id: str, part_no: int, chunk_data: bytes) -> Dict[str, Any]:
        if not upload_id:
            return {"success": False, "error": "missing_upload_id"}
        if part_no <= 0:
            return {"success": False, "error": "invalid_part_no"}
        if not chunk_data:
            return {"success": False, "error": "empty_chunk"}

        with self._lock:
            session = self._sessions.get(upload_id)
            if not session:
                return {"success": False, "error": "upload_not_found"}
            if int(session.get("expires_at", 0)) < int(time.time()):
                return {"success": False, "error": "upload_expired"}

            session_dir = Path(session["session_dir"])
            part_path = session_dir / f"part_{int(part_no):06d}.bin"
            with open(part_path, "wb") as f:
                f.write(chunk_data)

            sha = hashlib.sha1(chunk_data).hexdigest()
            session["parts"][int(part_no)] = {
                "path": str(part_path),
                "etag": sha,
                "size": len(chunk_data),
            }

            return {
                "success": True,
                "upload_id": upload_id,
                "part_no": int(part_no),
                "etag": sha,
                "size": len(chunk_data),
            }

    def _merge_parts(self, session: Dict[str, Any], output_path: Path) -> None:
        parts = session.get("parts") or {}
        if not parts:
            raise ValueError("no_uploaded_parts")

        ordered = sorted(parts.items(), key=lambda item: int(item[0]))
        with open(output_path, "wb") as writer:
            for _, payload in ordered:
                part_path = Path(payload["path"])
                with open(part_path, "rb") as reader:
                    shutil.copyfileobj(reader, writer)

    @staticmethod
    def _detect_duration_ms(video_path: Path) -> float:
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return 0.0

        try:
            proc = subprocess.run(
                [
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1",
                    str(video_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=20,
            )
            if proc.returncode != 0:
                return 0.0
            duration = float((proc.stdout or "0").strip() or 0)
            return max(0.0, duration * 1000.0)
        except Exception:
            return 0.0

    def _transcode_to_mp4(self, input_path: Path, output_path: Path) -> bool:
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            return False

        try:
            proc = subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-i", str(input_path),
                    "-c:v", "libx264",
                    "-preset", "veryfast",
                    "-movflags", "+faststart",
                    "-c:a", "aac",
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
            )
            return proc.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0
        except Exception:
            return False

    def finalize_upload(self, upload_id: str, interview_id: str = "") -> Dict[str, Any]:
        with self._lock:
            session = self._sessions.get(upload_id)
            if not session:
                return {"success": False, "error": "upload_not_found"}

        interview_id = str(interview_id or session.get("interview_id") or "").strip()
        if not interview_id:
            return {"success": False, "error": "missing_interview_id"}

        ext = ".webm"
        mime_type = str(session.get("mime_type") or "video/webm").lower()
        if "mp4" in mime_type:
            ext = ".mp4"

        merged_name = self._sanitize_filename(f"{interview_id}_{upload_id}_raw{ext}")
        merged_path = self.final_root / merged_name

        try:
            self._merge_parts(session, merged_path)
        except Exception as exc:
            return {"success": False, "error": f"merge_failed:{exc}"}

        final_path = merged_path
        codec = str(session.get("codec") or "")
        status = "uploaded"

        if self.enable_transcode and merged_path.suffix.lower() != ".mp4":
            transcoded_path = self.final_root / self._sanitize_filename(f"{interview_id}_{upload_id}.mp4")
            ok = self._transcode_to_mp4(merged_path, transcoded_path)
            if ok:
                final_path = transcoded_path
                codec = "mp4"
                status = "transcoded"
                if not self.keep_raw:
                    try:
                        merged_path.unlink(missing_ok=True)
                    except Exception:
                        pass

        duration_ms = self._detect_duration_ms(final_path)

        with self._lock:
            self._sessions.pop(upload_id, None)

        return {
            "success": True,
            "upload_id": upload_id,
            "interview_id": interview_id,
            "final_path": str(final_path),
            "raw_path": str(merged_path),
            "duration_ms": round(duration_ms, 2),
            "codec": codec or final_path.suffix.lstrip("."),
            "status": status,
        }

    def sign_local_playback(self, interview_id: str, expires_in: int = 3600) -> Dict[str, Any]:
        expires = int(time.time()) + max(60, int(expires_in or 3600))
        payload = f"{interview_id}:{expires}".encode("utf-8")
        sig = hmac.new(self.signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return {"expires": expires, "sig": sig}

    def verify_local_playback(self, interview_id: str, expires: int, sig: str) -> bool:
        try:
            expires_val = int(expires)
        except Exception:
            return False
        if expires_val < int(time.time()):
            return False
        payload = f"{interview_id}:{expires_val}".encode("utf-8")
        expected = hmac.new(self.signing_secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, str(sig or ""))
