"""
Interview state model for stateful RAG question planning.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class InterviewState:
    """最小可序列化的面试状态。"""

    session_id: str = ""
    role: str = ""
    target_round_type: str = "technical"
    target_difficulty: str = "medium"
    asked_question_ids: List[str] = field(default_factory=list)
    covered_competencies: List[str] = field(default_factory=list)
    weak_competencies: List[str] = field(default_factory=list)
    resume_skills: List[str] = field(default_factory=list)
    resume_projects: List[str] = field(default_factory=list)
    resume_keywords: List[str] = field(default_factory=list)
    current_topic: Optional[str] = None
    followup_depth: int = 0
    round_goal_progress: float = 0.0

    @classmethod
    def from_dict(
        cls,
        value: Optional[Dict[str, Any]],
        **overrides: Any,
    ) -> "InterviewState":
        payload = dict(value or {})
        payload.update({key: item for key, item in overrides.items() if item is not None})
        return cls(
            session_id=str(payload.get("session_id", "") or ""),
            role=str(payload.get("role", "") or ""),
            target_round_type=str(payload.get("target_round_type", "technical") or "technical"),
            target_difficulty=str(payload.get("target_difficulty", "medium") or "medium"),
            asked_question_ids=[
                str(item).strip()
                for item in payload.get("asked_question_ids", []) or []
                if str(item).strip()
            ],
            covered_competencies=[
                str(item).strip()
                for item in payload.get("covered_competencies", []) or []
                if str(item).strip()
            ],
            weak_competencies=[
                str(item).strip()
                for item in payload.get("weak_competencies", []) or []
                if str(item).strip()
            ],
            resume_skills=[
                str(item).strip()
                for item in payload.get("resume_skills", []) or []
                if str(item).strip()
            ],
            resume_projects=[
                str(item).strip()
                for item in payload.get("resume_projects", []) or []
                if str(item).strip()
            ],
            resume_keywords=[
                str(item).strip()
                for item in payload.get("resume_keywords", []) or []
                if str(item).strip()
            ],
            current_topic=str(payload.get("current_topic")).strip()
            if payload.get("current_topic")
            else None,
            followup_depth=int(payload.get("followup_depth", 0) or 0),
            round_goal_progress=float(payload.get("round_goal_progress", 0.0) or 0.0),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
