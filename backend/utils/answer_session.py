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
        self.finalized_reason = reason
        if exported_audio_path:
            self.exported_audio_path = exported_audio_path
        self.mark_status("finalized")
        return self.final_text

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
            "display_text": display_text,
            "audio_bytes": self.audio_bytes,
            "committed": self.committed,
            "finalized_reason": self.finalized_reason,
            "exported_audio_path": self.exported_audio_path,
            "last_speech_epoch": self.last_speech_epoch,
            "last_asr_generation": self.last_asr_generation,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "ended_at": self.ended_at,
        }
