"""
题目级回答会话与草稿文本聚合。
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


SHORT_PAUSE_SECONDS = 0.9
LONG_PAUSE_SECONDS = 4.5

_SPACE_RE = re.compile(r"\s+")
_DUPLICATE_PUNCT_RE = re.compile(r"([，。！？；,.!?])\1+")
_PUNCT_ENDINGS = "。！？!?；;"
_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_DIGIT_RE = re.compile(r"\d+")
_CONTINUATION_PREFIXES = (
    "然后",
    "接着",
    "之后",
    "后来",
    "另外",
    "还有",
    "并且",
    "而且",
    "以及",
    "同时",
    "所以",
    "因为",
    "但是",
    "不过",
    "比如",
    "例如",
    "包括",
    "就是",
    "再",
    "再者",
)


def normalize_answer_text(text: str) -> str:
    normalized = _SPACE_RE.sub(" ", str(text or "").strip())
    normalized = normalized.replace(" ,", ",").replace(" .", ".")
    normalized = _DUPLICATE_PUNCT_RE.sub(r"\1", normalized)
    return normalized.strip()


def build_live_answer_text(draft_text: str, partial_text: str) -> str:
    draft = normalize_answer_text(draft_text)
    partial = normalize_answer_text(partial_text)
    if not partial:
        return draft
    return merge_answer_text(draft, partial)


def merge_answer_text(existing_text: str, incoming_text: str) -> str:
    existing = normalize_answer_text(existing_text)
    incoming = normalize_answer_text(incoming_text)

    if not existing:
        return incoming
    if not incoming:
        return existing
    if existing.endswith(incoming):
        return existing
    if incoming.startswith(existing):
        return incoming

    overlap = _find_overlap(existing, incoming)
    if overlap:
        return _cleanup_merged_text(existing + incoming[overlap:])

    separator = "" if _looks_like_continuation(existing, incoming) else ("。" if len(incoming) > 12 else "，")
    return _cleanup_merged_text(f"{existing}{separator}{incoming}")


def _find_overlap(existing: str, incoming: str) -> int:
    max_len = min(len(existing), len(incoming), 24)
    for length in range(max_len, 1, -1):
        if existing[-length:] == incoming[:length]:
            return length
    return 0


def _looks_like_continuation(existing: str, incoming: str) -> bool:
    if not existing or not incoming:
        return True
    if existing[-1] in _PUNCT_ENDINGS or incoming[0] in "，。！？；,.!?、:：)]}":
        return True
    if incoming.startswith(_CONTINUATION_PREFIXES):
        return True
    return incoming[0].islower() or incoming[0].isdigit()


def _cleanup_merged_text(text: str) -> str:
    cleaned = normalize_answer_text(text)
    cleaned = cleaned.replace("，。", "。").replace("。。", "。")
    cleaned = cleaned.replace("，，", "，")
    return cleaned.strip()


def _count_spoken_tokens(text: str) -> int:
    content = str(text or "").strip()
    if not content:
        return 0
    cjk_count = len(_CJK_RE.findall(content))
    en_count = len(_EN_WORD_RE.findall(content))
    digit_count = len(_DIGIT_RE.findall(content))
    return max(0, cjk_count + en_count + digit_count)


@dataclass
class AnswerSession:
    question_id: str
    turn_id: str
    answer_session_id: str = field(default_factory=lambda: f"answer_{uuid.uuid4().hex[:12]}")
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    status: str = "recording"
    segments: List[Dict[str, Any]] = field(default_factory=list)
    merged_text_draft: str = ""
    final_text: str = ""
    current_partial: str = ""
    audio_chunks: List[bytes] = field(default_factory=list)
    audio_bytes: int = 0
    committed: bool = False
    finalized_reason: str = ""
    exported_audio_path: str = ""
    last_speech_epoch: int = 0
    last_asr_generation: int = 0
    final_transcript: str = ""
    word_timestamps: List[Dict[str, Any]] = field(default_factory=list)
    pause_events: List[Dict[str, Any]] = field(default_factory=list)
    filler_events: List[Dict[str, Any]] = field(default_factory=list)
    speech_metrics_final: Dict[str, Any] = field(default_factory=dict)
    final_metrics_ready: bool = False
    realtime_started_at: float = field(default_factory=time.time)
    last_realtime_event_at: float = 0.0
    active_speaking_ms: float = 0.0
    realtime_speech_metrics: Dict[str, Any] = field(default_factory=lambda: {
        "is_speaking": False,
        "rough_wpm": 0.0,
        "silence_ms": 0,
        "segment_index": 0,
        "updated_at": 0.0,
    })

    def add_audio_chunk(self, audio_data: bytes) -> None:
        if not audio_data:
            return
        self.audio_chunks.append(audio_data)
        self.audio_bytes += len(audio_data)
        self.updated_at = time.time()

    def update_partial(self, text: str) -> str:
        self.current_partial = normalize_answer_text(text)
        self.updated_at = time.time()
        return self.live_text

    def finalize_segment(self, text: str) -> str:
        normalized = normalize_answer_text(text)
        self.current_partial = ""
        self.updated_at = time.time()
        if not normalized:
            return self.merged_text_draft

        self.segments.append({
            "segment_id": f"segment_{len(self.segments) + 1}",
            "text": normalized,
            "timestamp": self.updated_at,
        })
        self.merged_text_draft = merge_answer_text(self.merged_text_draft, normalized)
        return self.merged_text_draft

    def mark_status(self, status: str) -> None:
        self.status = status
        self.updated_at = time.time()
        if status in {"finalizing", "finalized"}:
            self.ended_at = self.updated_at

    def mark_final(self, text: str, reason: str = "", exported_audio_path: str = "") -> str:
        final_text = normalize_answer_text(text) or self.merged_text_draft
        self.final_text = final_text
        self.final_transcript = final_text
        self.finalized_reason = reason
        if exported_audio_path:
            self.exported_audio_path = exported_audio_path
        self.mark_status("finalized")
        return self.final_text

    def update_realtime_speech_metrics(
        self,
        *,
        is_speaking: bool,
        text_snapshot: str = "",
        segment_index: Optional[int] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        current_ts = float(now if now is not None else time.time())
        metrics = dict(self.realtime_speech_metrics or {})

        last_event = float(self.last_realtime_event_at or 0.0)
        if last_event > 0 and metrics.get("is_speaking"):
            self.active_speaking_ms += max(0.0, (current_ts - last_event) * 1000.0)

        if self.realtime_started_at <= 0:
            self.realtime_started_at = current_ts

        if is_speaking:
            metrics["silence_ms"] = 0
            metrics["last_speech_at"] = current_ts
        else:
            last_speech_at = float(metrics.get("last_speech_at") or 0.0)
            if last_speech_at > 0:
                metrics["silence_ms"] = int(max(0.0, (current_ts - last_speech_at) * 1000.0))
            else:
                metrics["silence_ms"] = int(max(0.0, (current_ts - self.realtime_started_at) * 1000.0))

        spoken_text = normalize_answer_text(text_snapshot) or self.live_text or self.merged_text_draft or self.final_text
        token_count = _count_spoken_tokens(spoken_text)
        speaking_minutes = max(self.active_speaking_ms / 60000.0, 0.025)
        rough_wpm = float(token_count / speaking_minutes) if token_count > 0 else 0.0

        metrics.update({
            "is_speaking": bool(is_speaking),
            "rough_wpm": round(rough_wpm, 2),
            "segment_index": int(segment_index or len(self.segments)),
            "updated_at": current_ts,
        })
        if is_speaking and "last_speech_at" not in metrics:
            metrics["last_speech_at"] = current_ts

        self.realtime_speech_metrics = metrics
        self.last_realtime_event_at = current_ts
        self.updated_at = current_ts
        return dict(metrics)

    def mark_final_metrics(
        self,
        *,
        final_transcript: str,
        word_timestamps: List[Dict[str, Any]],
        pause_events: List[Dict[str, Any]],
        filler_events: List[Dict[str, Any]],
        speech_metrics_final: Dict[str, Any],
    ) -> Dict[str, Any]:
        self.final_transcript = normalize_answer_text(final_transcript) or self.final_text or self.merged_text_draft
        self.word_timestamps = list(word_timestamps or [])
        self.pause_events = list(pause_events or [])
        self.filler_events = list(filler_events or [])
        self.speech_metrics_final = dict(speech_metrics_final or {})
        self.final_metrics_ready = bool(self.speech_metrics_final)
        self.updated_at = time.time()
        return self.speech_metrics_final

    @property
    def live_text(self) -> str:
        return build_live_answer_text(self.merged_text_draft, self.current_partial)

    def to_payload(self) -> Dict[str, Any]:
        display_text = self.final_text or self.live_text or self.merged_text_draft
        return {
            "answer_session_id": self.answer_session_id,
            "question_id": self.question_id,
            "turn_id": self.turn_id,
            "status": self.status,
            "segment_count": len(self.segments),
            "merged_text_draft": self.merged_text_draft,
            "live_text": self.live_text,
            "final_text": self.final_text,
            "final_transcript": self.final_transcript or self.final_text,
            "display_text": display_text,
            "audio_bytes": self.audio_bytes,
            "committed": self.committed,
            "finalized_reason": self.finalized_reason,
            "exported_audio_path": self.exported_audio_path,
            "final_metrics_ready": self.final_metrics_ready,
            "speech_metrics_realtime": dict(self.realtime_speech_metrics or {}),
            "speech_metrics_final": dict(self.speech_metrics_final or {}) if self.final_metrics_ready else {},
            "word_timestamps": list(self.word_timestamps or []) if self.final_metrics_ready else [],
            "pause_events": list(self.pause_events or []) if self.final_metrics_ready else [],
            "filler_events": list(self.filler_events or []) if self.final_metrics_ready else [],
            "last_speech_epoch": self.last_speech_epoch,
            "last_asr_generation": self.last_asr_generation,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "ended_at": self.ended_at,
        }
