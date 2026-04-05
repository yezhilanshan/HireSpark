"""
会话运行时与状态编排器
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from utils import DataManager

DETECTION_NOTICE_MIN_INTERVAL_SECONDS = 18.0


@dataclass
class SessionRuntime:
    client_id: str
    session_id: str
    interview_id: str
    user_id: str = "default"
    round_type: str = "technical"
    position: str = "java_backend"
    difficulty: str = "medium"
    mode: str = "idle"
    turn_index: int = 0
    turn_id: str = ""
    active_asr_stream_id: str = ""
    active_llm_job_id: str = ""
    active_tts_job_id: str = ""
    pending_detection_state: Dict[str, Any] = field(default_factory=dict)
    chat_history: List[Dict[str, Any]] = field(default_factory=list)
    interrupt_epoch: int = 0
    started_at: Optional[float] = None
    resume_data: Optional[Dict[str, Any]] = None
    interview_state: Optional[Dict[str, Any]] = None
    last_question_plan: Optional[Dict[str, Any]] = None
    last_answer_analysis: Optional[Dict[str, Any]] = None
    last_committed_hash: str = ""
    last_committed_at: float = 0.0
    current_question: str = ""
    current_question_started_at: Optional[float] = None
    current_question_estimated_end_at: Optional[float] = None
    current_answer_started_at: Optional[float] = None
    data_manager: Optional[DataManager] = None
    pending_asr_partials: List[str] = field(default_factory=list)
    pending_asr_finals: List[str] = field(default_factory=list)
    pending_asr_audio_lock: Any = field(default_factory=threading.RLock)
    pending_asr_audio_chunks: List[bytes] = field(default_factory=list)
    pending_asr_audio_bytes: int = 0
    speech_epoch: int = 0
    client_speech_epoch: int = 0
    active_client_speech_epoch: int = 0
    asr_generation_counter: int = 0
    active_asr_generation: int = 0
    active_asr_speech_epoch: int = 0
    finalizing_asr_generation: int = 0
    last_finalized_asr_generation: int = 0
    last_finalized_asr_speech_epoch: int = 0
    asr_start_lock: Any = field(default_factory=threading.Lock)
    pending_commit_timer: Any = None
    pending_answer_finalize_timer: Any = None
    notice_queue: List[str] = field(default_factory=list)
    last_notice_at: Dict[str, float] = field(default_factory=dict)
    asr_available: bool = True
    asr_error: str = ""
    asr_error_code: str = ""
    asr_locked: bool = False
    asr_lock_reason: str = ""
    ended: bool = False
    current_answer_session: Any = None
    short_pause_threshold_seconds: float = 0.9
    long_pause_threshold_seconds: float = 4.5

    def next_turn(self) -> str:
        self.turn_index += 1
        self.turn_id = f"turn_{self.turn_index}_{uuid.uuid4().hex[:8]}"
        return self.turn_id

    @staticmethod
    def new_job(prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:12]}"


class SessionRegistry:
    def __init__(self):
        self._lock = threading.RLock()
        self._sessions: Dict[str, SessionRuntime] = {}

    def create(
        self,
        client_id: str,
        session_id: str,
        user_id: str,
        round_type: str,
        position: str,
        difficulty: str,
    ) -> SessionRuntime:
        runtime = SessionRuntime(
            client_id=client_id,
            session_id=session_id,
            interview_id=f"interview_{session_id}",
            user_id=user_id,
            round_type=round_type,
            position=position,
            difficulty=difficulty,
            mode="idle",
            data_manager=DataManager() if DataManager is not None else None,
        )
        with self._lock:
            self._sessions[client_id] = runtime
        return runtime

    def get(self, client_id: str) -> Optional[SessionRuntime]:
        with self._lock:
            return self._sessions.get(client_id)

    def remove(self, client_id: str) -> Optional[SessionRuntime]:
        with self._lock:
            return self._sessions.pop(client_id, None)


class StateOrchestrator:
    def __init__(self, registry: SessionRegistry):
        self.registry = registry

    def build_public_state(self, runtime: SessionRuntime) -> Dict[str, Any]:
        answer_session = runtime.current_answer_session
        return {
            "session_id": runtime.session_id,
            "mode": runtime.mode,
            "turn_id": runtime.turn_id,
            "interrupt_epoch": runtime.interrupt_epoch,
            "speech_epoch": runtime.speech_epoch,
            "active_asr_stream_id": runtime.active_asr_stream_id,
            "active_llm_job_id": runtime.active_llm_job_id,
            "active_tts_job_id": runtime.active_tts_job_id,
            "asr_available": runtime.asr_available,
            "asr_error": runtime.asr_error,
            "asr_error_code": runtime.asr_error_code,
            "asr_locked": runtime.asr_locked,
            "asr_lock_reason": runtime.asr_lock_reason,
            "detection_state": runtime.pending_detection_state,
            "answer_session_id": getattr(answer_session, "answer_session_id", ""),
            "answer_session_status": getattr(answer_session, "status", "idle"),
        }

    def begin_listening(self, runtime: SessionRuntime) -> None:
        runtime.mode = "listening"

    def begin_thinking(self, runtime: SessionRuntime, job_id: str) -> None:
        runtime.active_llm_job_id = job_id
        runtime.mode = "thinking"

    def finish_thinking(self, runtime: SessionRuntime, job_id: str) -> bool:
        if runtime.active_llm_job_id != job_id:
            return False
        runtime.active_llm_job_id = ""
        return True

    def begin_speaking(self, runtime: SessionRuntime, job_id: str) -> None:
        runtime.active_tts_job_id = job_id
        runtime.mode = "speaking"

    def finish_speaking(self, runtime: SessionRuntime, job_id: str) -> bool:
        if runtime.active_tts_job_id != job_id:
            return False
        runtime.active_tts_job_id = ""
        runtime.mode = "listening"
        return True

    def interrupt(self, runtime: SessionRuntime) -> Dict[str, Any]:
        interrupted_job_id = runtime.active_tts_job_id
        runtime.interrupt_epoch += 1
        runtime.active_tts_job_id = ""
        runtime.active_llm_job_id = ""
        runtime.mode = "interrupted"
        return {
            "session_id": runtime.session_id,
            "turn_id": runtime.turn_id,
            "job_id": interrupted_job_id,
            "interrupt_epoch": runtime.interrupt_epoch,
        }

    def start_speech(self, runtime: SessionRuntime) -> Dict[str, Any]:
        payload = {}
        if runtime.mode in {"speaking", "thinking"}:
            payload = self.interrupt(runtime)
        runtime.mode = "listening"
        runtime.pending_asr_partials.clear()
        runtime.pending_asr_finals.clear()
        with runtime.pending_asr_audio_lock:
            runtime.pending_asr_audio_chunks.clear()
            runtime.pending_asr_audio_bytes = 0
        runtime.finalizing_asr_generation = 0
        runtime.last_finalized_asr_generation = 0
        runtime.active_asr_stream_id = runtime.active_asr_stream_id or runtime.session_id
        timer = runtime.pending_commit_timer
        if timer:
            timer.cancel()
            runtime.pending_commit_timer = None
        return payload

    def can_commit(self, runtime: SessionRuntime, turn_id: str, text_hash: str, now: float) -> bool:
        if runtime.mode == "thinking":
            return False
        if turn_id and runtime.turn_id and turn_id != runtime.turn_id:
            return False
        if text_hash and runtime.last_committed_hash == text_hash and now - runtime.last_committed_at < 3.0:
            return False
        return True

    def mark_committed(self, runtime: SessionRuntime, text_hash: str, now: float) -> None:
        runtime.last_committed_hash = text_hash
        runtime.last_committed_at = now

    def update_detection_state(self, runtime: SessionRuntime, payload: Dict[str, Any]) -> Optional[str]:
        runtime.pending_detection_state = dict(payload or {})
        flags = set(payload.get("flags") or [])
        has_face = bool(payload.get("has_face", True))
        notice_key = ""
        notice_text = ""

        if "no_face_long" in flags:
            notice_key = "no_face_long"
            notice_text = "我暂时看不到你，请调整一下摄像头位置。"
        elif "device_muted" in flags or "mic_issue" in flags:
            notice_key = "mic_issue"
            notice_text = "我暂时听不到你的声音，请检查麦克风。"

        if not notice_key:
            return None

        now = time.time()
        last_notice_at = runtime.last_notice_at.get(notice_key, 0)
        if now - last_notice_at < DETECTION_NOTICE_MIN_INTERVAL_SECONDS:
            return None

        runtime.last_notice_at[notice_key] = now
        runtime.notice_queue.append(notice_text)
        return notice_text
