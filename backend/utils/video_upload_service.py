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
        self.transcode_preset = str(config.get("video_upload.transcode_preset", "veryfast") or "veryfast").strip()
        self.transcode_crf = int(config.get("video_upload.transcode_crf", 23))
        self.transcode_target_fps = max(1, int(config.get("video_upload.transcode_target_fps", 30)))
        self.transcode_gop_seconds = max(0.25, float(config.get("video_upload.transcode_gop_seconds", 1.0)))
        self.transcode_audio_bitrate = str(config.get("video_upload.transcode_audio_bitrate", "128k") or "128k").strip()
        self.transcode_timeout_seconds = max(120, int(config.get("video_upload.transcode_timeout_seconds", 7200)))
        self._ffmpeg_path = ""
        self._ffprobe_path = ""
        self._refresh_transcode_tools(force=True)

        self.upload_root.mkdir(parents=True, exist_ok=True)
        self.final_root.mkdir(parents=True, exist_ok=True)

        if self.enable_transcode and not self._ffmpeg_path and self.logger:
            self.logger.warning("[Replay] ffmpeg 未安装，视频将保留原始容器，拖动体验可能受限")
        if not self._ffprobe_path and self.logger:
            self.logger.info("[Replay] ffprobe 未安装，无法精确探测视频时长")

        self.signing_secret = str(
            config.get("video_upload.playback_signing_secret", "")
            or config.get("server.secret_key", "")
            or "interview-replay-secret"
        )

    def _resolve_binary(self, binary_name: str) -> str:
        direct = shutil.which(binary_name)
        if direct:
            return direct

        env_key = "FFMPEG_BINARY" if binary_name == "ffmpeg" else "FFPROBE_BINARY"
        env_path = str(os.getenv(env_key, "")).strip()
        if env_path and Path(env_path).exists():
            return env_path

        exe_name = f"{binary_name}.exe"
        candidates = []
        local_app_data = str(os.getenv("LOCALAPPDATA", "")).strip()
        program_files = str(os.getenv("ProgramFiles", "")).strip()
        chocolatey = str(os.getenv("ChocolateyInstall", "")).strip()

        if local_app_data:
            candidates.append(Path(local_app_data) / "Microsoft" / "WinGet" / "Links" / exe_name)
            winget_pkg_root = Path(local_app_data) / "Microsoft" / "WinGet" / "Packages"
            if winget_pkg_root.exists():
                for package_dir in winget_pkg_root.glob("Gyan.FFmpeg*"):
                    candidates.extend(package_dir.glob(f"**/bin/{exe_name}"))

        if program_files:
            candidates.append(Path(program_files) / "ffmpeg" / "bin" / exe_name)
        if chocolatey:
            candidates.append(Path(chocolatey) / "bin" / exe_name)

        for candidate in candidates:
            if candidate.exists():
                return str(candidate)
        return ""

    def _refresh_transcode_tools(self, force: bool = False) -> None:
        if force or not self._ffmpeg_path:
            self._ffmpeg_path = self._resolve_binary("ffmpeg")
        if force or not self._ffprobe_path:
            self._ffprobe_path = self._resolve_binary("ffprobe")

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

    def _detect_duration_ms(self, video_path: Path) -> float:
        self._refresh_transcode_tools(force=False)
        if not self._ffprobe_path:
            return 0.0

        try:
            proc = subprocess.run(
                [
                    self._ffprobe_path,
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
        self._refresh_transcode_tools(force=False)
        if not self._ffmpeg_path:
            return False

        gop_size = max(1, int(round(self.transcode_gop_seconds * self.transcode_target_fps)))

        try:
            proc = subprocess.run(
                [
                    self._ffmpeg_path,
                    "-y",
                    "-i", str(input_path),
                    "-map", "0:v:0",
                    "-map", "0:a:0?",
                    "-c:v", "libx264",
                    "-preset", self.transcode_preset,
                    "-crf", str(self.transcode_crf),
                    "-pix_fmt", "yuv420p",
                    "-r", str(self.transcode_target_fps),
                    "-g", str(gop_size),
                    "-keyint_min", str(gop_size),
                    "-sc_threshold", "0",
                    "-force_key_frames", f"expr:gte(t,n_forced*{self.transcode_gop_seconds})",
                    "-movflags", "+faststart",
                    "-c:a", "aac",
                    "-b:a", self.transcode_audio_bitrate,
                    str(output_path),
                ],
                capture_output=True,
                text=True,
                check=False,
                timeout=self.transcode_timeout_seconds,
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
        self._refresh_transcode_tools(force=False)

        if self.enable_transcode and merged_path.suffix.lower() != ".mp4":
            if not self._ffmpeg_path:
                status = "uploaded_no_transcode"
            else:
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
                else:
                    status = "transcode_failed_raw"
                    if self.logger:
                        self.logger.warning("[Replay] 转码失败，回退原始文件: %s", merged_path)

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
