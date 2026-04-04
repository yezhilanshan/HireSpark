"""
Offline behavior analysis service for replay phase-2 tags (emotion/posture/gaze).
"""
from __future__ import annotations

import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config_loader import config


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _safe_json_loads(value: Any, default: Any):
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _parse_datetime_to_ts(value: Any) -> Optional[float]:
    text = str(value or "").strip()
    if not text:
        return None
    patterns = (
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
    )
    for pattern in patterns:
        try:
            return datetime.strptime(text, pattern).timestamp()
        except Exception:
            continue
    try:
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return None


class BehaviorAnalysisService:
    def __init__(self, db_manager, logger=None):
        self.db_manager = db_manager
        self.logger = logger
        self.enabled = bool(config.get("replay.behavior.enabled", True))
        self.gaze_ratio_threshold = float(config.get("replay.behavior.min_gaze_offscreen_ratio", 20.0))
        self.long_latency_ms = float(config.get("replay.behavior.long_latency_ms", 3500.0))
        self.filler_per_100_threshold = float(config.get("replay.behavior.filler_per_100_words_threshold", 6.0))
        self.long_pause_threshold = int(config.get("replay.behavior.long_pause_count_threshold", 2))
        self.version = str(config.get("replay.behavior.version", "v2_behavior_heuristic") or "v2_behavior_heuristic")

    @staticmethod
    def _to_session_ms(ts: float, base_ts: Optional[float], fallback_ms: float) -> float:
        value = _safe_float(ts, 0.0)
        if value <= 0:
            return max(0.0, fallback_ms)
        if base_ts and value > 1_000_000_000:
            return max(0.0, (value - base_ts) * 1000.0)
        return max(0.0, value * 1000.0 if value < 100_000 else value)

    def _resolve_base_timestamp(self, interview_id: str) -> Optional[float]:
        interview = self.db_manager.get_interview_by_id(interview_id) if hasattr(self.db_manager, "get_interview_by_id") else None
        if not interview:
            return None
        return _parse_datetime_to_ts(interview.get("start_time")) or _parse_datetime_to_ts(interview.get("created_at"))

    def _decode_speech_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        decoded = []
        for row in rows or []:
            item = dict(row)
            item["speech_metrics_final"] = _safe_json_loads(item.get("speech_metrics_final_json"), {})
            decoded.append(item)
        return decoded

    def _build_gaze_tags(
        self,
        events: List[Dict[str, Any]],
        base_ts: Optional[float],
        duration_ms: float,
    ) -> List[Dict[str, Any]]:
        tags: List[Dict[str, Any]] = []
        fallback_index = 0
        for event in events:
            event_type = str(event.get("event_type") or event.get("type") or "").strip().lower()
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else _safe_json_loads(event.get("metadata"), {})
            off_ratio = _safe_float((metadata or {}).get("off_screen_ratio"), 0.0)
            has_face = bool((metadata or {}).get("has_face", True))
            flags = [str(item).strip().lower() for item in ((metadata or {}).get("flags") or []) if str(item).strip()]
            is_gaze_like = (
                event_type == "gaze_deviation"
                or off_ratio >= self.gaze_ratio_threshold
                or ("no_face_long" in flags)
                or (not has_face)
            )
            if not is_gaze_like:
                continue
            fallback_index += 1
            timestamp = _safe_float(event.get("timestamp"), 0.0)
            start_ms = self._to_session_ms(timestamp, base_ts, fallback_index * 1500.0)
            end_ms = start_ms + 2400.0
            if duration_ms > 0:
                end_ms = min(duration_ms, end_ms)
            reason = "视线偏离镜头或出现长时间离屏迹象。"
            if off_ratio > 0:
                reason = f"离屏占比偏高（{off_ratio:.1f}%），建议回看该段视线状态。"
            tags.append({
                "turn_id": None,
                "tag_type": "gaze",
                "start_ms": round(start_ms, 2),
                "end_ms": round(max(start_ms, end_ms), 2),
                "reason": reason,
                "confidence": round(_clamp(0.58 + off_ratio / 120.0, 0.45, 0.92), 4),
                "evidence_json": json.dumps({"event_type": event_type, "off_screen_ratio": off_ratio}, ensure_ascii=False),
                "source": self.version,
            })
        return tags[:24]

    def _build_posture_tags(
        self,
        events: List[Dict[str, Any]],
        base_ts: Optional[float],
        duration_ms: float,
    ) -> List[Dict[str, Any]]:
        tags: List[Dict[str, Any]] = []
        fallback_index = 0
        for event in events:
            event_type = str(event.get("event_type") or event.get("type") or "").strip().lower()
            metadata = event.get("metadata") if isinstance(event.get("metadata"), dict) else _safe_json_loads(event.get("metadata"), {})
            flags = [str(item).strip().lower() for item in ((metadata or {}).get("flags") or []) if str(item).strip()]
            face_count = _safe_int((metadata or {}).get("face_count"), 1)
            if event_type not in {"multi_person", "posture_shift"} and "no_face_long" not in flags and face_count <= 1:
                continue
            fallback_index += 1
            timestamp = _safe_float(event.get("timestamp"), 0.0)
            start_ms = self._to_session_ms(timestamp, base_ts, fallback_index * 2200.0)
            end_ms = start_ms + 2800.0
            if duration_ms > 0:
                end_ms = min(duration_ms, end_ms)
            if face_count > 1 or event_type == "multi_person":
                reason = "画面内人脸数量异常，姿态/环境稳定性不足。"
            else:
                reason = "出现长时间离开镜头或姿态偏离，建议复看肢体状态。"
            tags.append({
                "turn_id": None,
                "tag_type": "posture",
                "start_ms": round(start_ms, 2),
                "end_ms": round(max(start_ms, end_ms), 2),
                "reason": reason,
                "confidence": round(_clamp(0.6 + (0.18 if face_count > 1 else 0.0), 0.48, 0.9), 4),
                "evidence_json": json.dumps({"event_type": event_type, "face_count": face_count, "flags": flags[:4]}, ensure_ascii=False),
                "source": self.version,
            })
        return tags[:16]

    def _build_emotion_tags(
        self,
        turn_timeline: List[Dict[str, Any]],
        speech_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        tags: List[Dict[str, Any]] = []
        speech_by_turn = {
            str(item.get("turn_id") or "").strip(): item
            for item in speech_rows
            if str(item.get("turn_id") or "").strip()
        }
        for row in turn_timeline or []:
            turn_id = str(row.get("turn_id") or "").strip()
            if not turn_id:
                continue
            latency_ms = _safe_float(row.get("latency_ms"), 0.0)
            metrics = (speech_by_turn.get(turn_id) or {}).get("speech_metrics_final") or {}
            fillers = (metrics.get("fillers") or {})
            pause = (metrics.get("pause") or {})
            filler_per_100 = _safe_float(fillers.get("per_100_words"), 0.0)
            long_pause_count = _safe_int(pause.get("long_count"), 0)
            if latency_ms < self.long_latency_ms and filler_per_100 < self.filler_per_100_threshold and long_pause_count < self.long_pause_threshold:
                continue
            start_ms = _safe_float(row.get("answer_start_ms"), 0.0)
            end_ms = max(start_ms, _safe_float(row.get("answer_end_ms"), start_ms + 1200.0))
            reason_parts = []
            if latency_ms >= self.long_latency_ms:
                reason_parts.append(f"响应时延较高（{latency_ms:.0f}ms）")
            if filler_per_100 >= self.filler_per_100_threshold:
                reason_parts.append(f"口头填充词偏多（{filler_per_100:.1f}/100词）")
            if long_pause_count >= self.long_pause_threshold:
                reason_parts.append(f"长停顿较多（{long_pause_count}次）")
            reason = "；".join(reason_parts) + "，可能存在压力反应。"
            tags.append({
                "turn_id": turn_id,
                "tag_type": "emotion",
                "start_ms": round(start_ms, 2),
                "end_ms": round(end_ms, 2),
                "reason": reason,
                "confidence": round(_clamp(0.52 + latency_ms / 12000.0 + filler_per_100 / 30.0, 0.45, 0.9), 4),
                "evidence_json": json.dumps({
                    "latency_ms": round(latency_ms, 2),
                    "fillers_per_100_words": round(filler_per_100, 3),
                    "long_pause_count": long_pause_count,
                }, ensure_ascii=False),
                "source": self.version,
            })
        return tags[:20]

    def _merge_behavior_tags(self, interview_id: str, behavior_tags: List[Dict[str, Any]]) -> Dict[str, Any]:
        existing_tags = self.db_manager.get_timeline_tags(interview_id) if hasattr(self.db_manager, "get_timeline_tags") else []
        preserved = [
            item for item in (existing_tags or [])
            if str(item.get("tag_type") or "").strip().lower() not in {"emotion", "posture", "gaze"}
        ]
        merged = preserved + list(behavior_tags or [])
        if hasattr(self.db_manager, "replace_timeline_tags"):
            return self.db_manager.replace_timeline_tags(interview_id, merged)
        return {"success": False, "error": "replace_timeline_tags_not_supported"}

    def analyze_interview(self, interview_id: str, force: bool = False) -> Dict[str, Any]:
        normalized_id = str(interview_id or "").strip()
        if not normalized_id:
            return {"success": False, "error": "invalid_interview_id"}
        if not self.enabled:
            return {"success": False, "error": "behavior_analysis_disabled"}

        existing_tags = self.db_manager.get_timeline_tags(normalized_id) if hasattr(self.db_manager, "get_timeline_tags") else []
        has_behavior = any(
            str(item.get("tag_type") or "").strip().lower() in {"emotion", "posture", "gaze"}
            for item in (existing_tags or [])
        )
        if has_behavior and not force:
            return {"success": True, "interview_id": normalized_id, "status": "skipped_existing_behavior_tags"}

        events = self.db_manager.get_events(normalized_id) if hasattr(self.db_manager, "get_events") else []
        turn_timeline = self.db_manager.get_interview_turn_timelines(normalized_id) if hasattr(self.db_manager, "get_interview_turn_timelines") else []
        speech_rows = self._decode_speech_rows(
            self.db_manager.get_speech_evaluations(normalized_id) if hasattr(self.db_manager, "get_speech_evaluations") else []
        )
        asset = self.db_manager.get_interview_asset(normalized_id) if hasattr(self.db_manager, "get_interview_asset") else None
        duration_ms = _safe_float((asset or {}).get("duration_ms"), 0.0)
        base_ts = self._resolve_base_timestamp(normalized_id)

        gaze_tags = self._build_gaze_tags(events, base_ts=base_ts, duration_ms=duration_ms)
        posture_tags = self._build_posture_tags(events, base_ts=base_ts, duration_ms=duration_ms)
        emotion_tags = self._build_emotion_tags(turn_timeline=turn_timeline, speech_rows=speech_rows)
        behavior_tags = gaze_tags + posture_tags + emotion_tags

        write_result = self._merge_behavior_tags(normalized_id, behavior_tags)
        return {
            "success": bool(write_result.get("success")),
            "interview_id": normalized_id,
            "status": "ok" if write_result.get("success") else "failed",
            "error": write_result.get("error", ""),
            "counts": {
                "gaze": len(gaze_tags),
                "posture": len(posture_tags),
                "emotion": len(emotion_tags),
                "total": len(behavior_tags),
            },
            "version": self.version,
        }


class BehaviorAnalysisTaskManager:
    """Async task manager for offline behavior analysis."""

    def __init__(self, service: BehaviorAnalysisService, max_workers: int = 1, logger=None):
        self.service = service
        self.max_workers = max(1, int(max_workers or 1))
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="behavior-worker")
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._inflight: Dict[str, str] = {}

    def enqueue(self, interview_id: str, force: bool = False) -> Dict[str, Any]:
        normalized_id = str(interview_id or "").strip()
        if not normalized_id:
            return {"success": False, "error": "invalid_interview_id"}

        with self._lock:
            current_task_id = self._inflight.get(normalized_id)
            if current_task_id:
                task = self._tasks.get(current_task_id) or {}
                return {
                    "success": True,
                    "task_id": current_task_id,
                    "interview_id": normalized_id,
                    "status": task.get("status", "running"),
                    "deduplicated": True,
                }
            task_id = f"behavior_{int(time.time() * 1000)}_{normalized_id[-8:]}"
            self._tasks[task_id] = {
                "task_id": task_id,
                "interview_id": normalized_id,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "result": None,
                "error": "",
            }
            self._inflight[normalized_id] = task_id

        def _runner():
            self._set_status(task_id, "running")
            try:
                result = self.service.analyze_interview(normalized_id, force=force)
                if result.get("success"):
                    self._set_status(task_id, "ok", result=result)
                else:
                    self._set_status(task_id, "failed", error=str(result.get("error", "analyze_failed")), result=result)
            except Exception as exc:
                self._set_status(task_id, "failed", error=str(exc)[:240], result=None)
            finally:
                with self._lock:
                    if self._inflight.get(normalized_id) == task_id:
                        self._inflight.pop(normalized_id, None)

        self.executor.submit(_runner)
        return {"success": True, "task_id": task_id, "interview_id": normalized_id, "status": "pending"}

    def _set_status(self, task_id: str, status: str, error: str = "", result: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = status
            task["error"] = error
            task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if result is not None:
                task["result"] = result

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            task = self._tasks.get(str(task_id or "").strip())
            return dict(task) if task else None

