"""
三层评价服务：
1) RAG 第一层匹配（原词 + 同义 + 轻量语义）
2) LLM 第二层结构化评估
3) 结果版本化落库 + 异步编排 + 重试 + 幂等
"""
from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

try:
    from utils.config_loader import config
    from utils.evidence_services import TextEvidenceService, SpeechEvidenceService, VideoEvidenceService
    from utils.logger import get_logger
except ImportError:  # pragma: no cover
    from backend.utils.config_loader import config
    from backend.utils.evidence_services import TextEvidenceService, SpeechEvidenceService, VideoEvidenceService
    from backend.utils.logger import get_logger


class EvaluationService:
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_OK = "ok"
    STATUS_PARTIAL_OK = "partial_ok"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    ROUND_DIMENSIONS = {
        "technical": [
            "technical_accuracy",
            "knowledge_depth",
            "completeness",
            "logic",
            "job_match"
        ],
        "project": [
            "authenticity",
            "ownership",
            "technical_depth",
            "reflection",
            "communication"
        ],
        "system_design": [
            "architecture_reasoning",
            "tradeoff_awareness",
            "scalability",
            "logic"
        ],
        "hr": [
            "clarity",
            "relevance",
            "self_awareness",
            "communication",
            "confidence"
        ],
    }
    AXIS_WEIGHTS = {
        "content": 0.70,
        "delivery": 0.20,
        "presence": 0.10,
    }
    LAYER_WEIGHTS = {
        "text": AXIS_WEIGHTS["content"],
        "speech": AXIS_WEIGHTS["delivery"],
        "video": AXIS_WEIGHTS["presence"],
    }
    SHORTBOARD_RULES = {
        "technical": {"dimension": "technical_accuracy", "threshold": 60.0, "slope": 0.012},
        "project": {"dimension": "technical_depth", "threshold": 60.0, "slope": 0.010},
        "system_design": {"dimension": "architecture_reasoning", "threshold": 60.0, "slope": 0.012},
        "hr": {"dimension": "clarity", "threshold": 60.0, "slope": 0.008},
    }
    MIN_SHORTBOARD_COEFFICIENT = 0.45
    EVALUATION_SCHEMA_VERSION = "evaluation_v2.1"
    EVALUATION_ARCHITECTURE = "orthogonal_content_delivery_presence_with_integrity"
    SPEECH_GATE_MIN_AUDIO_MS = 8000.0
    SPEECH_GATE_MIN_TOKENS = 20
    SPEECH_FUSION_VERSION = "speech_decoupled_v3"
    SPEECH_EXPRESSION_WEIGHTS = {
        "clarity_score": 0.30,
        "fluency_score": 0.25,
        "speech_rate_score": 0.20,
        "pause_anomaly_score": 0.15,
        "filler_frequency_score": 0.10,
    }
    VIDEO_DIMENSION_WEIGHTS = {
        "gaze_focus": 0.30,
        "posture_compliance": 0.25,
        "physiology_stability": 0.20,
        "expression_naturalness": 0.15,
        "engagement_level": 0.10,
    }

    def __init__(
        self,
        db_manager,
        rag_service=None,
        llm_manager=None,
        logger=None,
    ):
        self.db_manager = db_manager
        self.rag_service = rag_service
        self.llm_manager = llm_manager
        self.logger = logger or get_logger(__name__)
        self.text_evidence_service = TextEvidenceService()
        self.speech_evidence_service = SpeechEvidenceService()
        self.video_evidence_service = VideoEvidenceService()

        self.evaluation_version = str(config.get("evaluation.version", "v1")).strip() or "v1"
        self.prompt_version = str(config.get("evaluation.prompt_version", "v1")).strip() or "v1"
        self.semantic_threshold = float(config.get("evaluation.semantic_threshold", 0.74))

        self.max_workers = int(config.get("evaluation.max_workers", 2))
        self.retry_layer1 = int(config.get("evaluation.retry.layer1", 1))
        self.retry_layer2 = int(config.get("evaluation.retry.layer2", 2))
        self.retry_persist = int(config.get("evaluation.retry.persist", 2))
        self.retry_backoff = float(config.get("evaluation.retry.backoff_seconds", 0.2))

        self.executor = ThreadPoolExecutor(
            max_workers=max(1, self.max_workers),
            thread_name_prefix="evaluation-worker"
        )
        self._inflight_lock = threading.Lock()
        self._inflight_task_keys = set()
        self._completion_callbacks: list = []

    @staticmethod
    def _json_dumps(value: Any) -> str:
        try:
            return json.dumps(value if value is not None else {}, ensure_ascii=False)
        except Exception:
            return "{}"

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(value)
        except Exception:
            return None

    @staticmethod
    def _clamp_score(value: Any, default: float = 0.0) -> float:
        try:
            return round(max(0.0, min(100.0, float(value))), 2)
        except Exception:
            return round(float(default), 2)

    @staticmethod
    def _safe_json_loads(value: Any, default: Any) -> Any:
        if value in (None, ""):
            return default
        if isinstance(value, (dict, list)):
            return value
        try:
            return json.loads(value)
        except Exception:
            return default

    @staticmethod
    def _clamp_unit(value: Any, default: float = 0.0) -> float:
        try:
            return round(max(0.0, min(1.0, float(value))), 4)
        except Exception:
            return round(float(default), 4)

    @staticmethod
    def _sanitize_text(text: Any) -> str:
        return str(text or "").strip()

    def _build_quote_time_index(self, word_timestamps: list[Dict[str, Any]]) -> Dict[str, Any]:
        merged_chars = []
        char_ranges = []
        for item in word_timestamps or []:
            token = self._sanitize_text((item or {}).get("word") or (item or {}).get("token"))
            if not token:
                continue
            start_ms = self._safe_float((item or {}).get("start_ms"))
            end_ms = self._safe_float((item or {}).get("end_ms"))
            if start_ms is None:
                continue
            if end_ms is None:
                end_ms = start_ms
            for _ch in token:
                merged_chars.append(_ch)
                char_ranges.append((float(start_ms), float(end_ms)))

        return {
            "text": "".join(merged_chars),
            "char_ranges": char_ranges,
        }

    def _infer_quote_time_span(self, quote: str, word_timestamps: list[Dict[str, Any]]) -> Dict[str, Optional[float]]:
        normalized_quote = self._sanitize_text(quote).replace(" ", "")
        if not normalized_quote:
            return {"start_ms": None, "end_ms": None}

        index_data = self._build_quote_time_index(word_timestamps)
        timeline_text = str(index_data.get("text") or "")
        char_ranges = index_data.get("char_ranges") or []
        if not timeline_text or not char_ranges:
            return {"start_ms": None, "end_ms": None}

        start_idx = timeline_text.find(normalized_quote)
        if start_idx < 0:
            return {"start_ms": None, "end_ms": None}

        end_idx = min(len(char_ranges) - 1, start_idx + len(normalized_quote) - 1)
        start_ms = float(char_ranges[start_idx][0])
        end_ms = float(char_ranges[end_idx][1])
        if end_ms < start_ms:
            end_ms = start_ms
        return {
            "start_ms": round(start_ms, 2),
            "end_ms": round(end_ms, 2),
        }

    @staticmethod
    def _count_transcript_tokens(text: str) -> int:
        content = str(text or "").strip()
        if not content:
            return 0
        return len(re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", content))

    def _load_turn_speech_evaluation(self, interview_id: str, turn_id: str) -> Optional[Dict[str, Any]]:
        if not interview_id or not turn_id or not hasattr(self.db_manager, "get_speech_evaluations"):
            return None

        try:
            rows = self.db_manager.get_speech_evaluations(interview_id=interview_id)
        except Exception as e:  # pragma: no cover - runtime resilience
            self.logger.warning("load speech evaluation failed: %s", e)
            return None

        for row in rows or []:
            if str((row or {}).get("turn_id", "")).strip() != str(turn_id).strip():
                continue

            item = dict(row or {})
            item["word_timestamps"] = self._safe_json_loads(item.get("word_timestamps_json"), [])
            item["pause_events"] = self._safe_json_loads(item.get("pause_events_json"), [])
            item["filler_events"] = self._safe_json_loads(item.get("filler_events_json"), [])
            item["speech_metrics_final"] = self._safe_json_loads(item.get("speech_metrics_final_json"), {})
            item["realtime_metrics"] = self._safe_json_loads(item.get("realtime_metrics_json"), {})
            return item
        return None

    def _calculate_speech_expression_score(self, expression_dimensions: Dict[str, Any]) -> Optional[float]:
        weighted_sum = 0.0
        total_weight = 0.0
        for key, weight in self.SPEECH_EXPRESSION_WEIGHTS.items():
            value = self._safe_float((expression_dimensions or {}).get(key))
            if value is None:
                continue
            weighted_sum += self._clamp_score(value) * float(weight)
            total_weight += float(weight)

        if total_weight <= 0:
            return None
        return round(weighted_sum / total_weight, 2)

    def build_speech_context(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        speech_row = self._load_turn_speech_evaluation(
            interview_id=str(payload.get("interview_id", "")).strip(),
            turn_id=str(payload.get("turn_id", "")).strip(),
        )
        metrics = (speech_row or {}).get("speech_metrics_final") or {}
        expression_dimensions = (metrics.get("dimensions") or {}) if isinstance(metrics, dict) else {}
        final_transcript = str((speech_row or {}).get("final_transcript", "") or "").strip()
        audio_duration_ms = self._safe_float((metrics or {}).get("audio_duration_ms")) or 0.0
        token_count = self._count_transcript_tokens(final_transcript)
        gate_reasons = []

        if not speech_row:
            gate_reasons.append("missing_speech_evaluation")
        if not isinstance(metrics, dict) or not metrics:
            gate_reasons.append("missing_speech_metrics_final")
        if not final_transcript:
            gate_reasons.append("missing_final_transcript")
        if audio_duration_ms < self.SPEECH_GATE_MIN_AUDIO_MS:
            gate_reasons.append("audio_duration_below_threshold")
        if token_count < self.SPEECH_GATE_MIN_TOKENS:
            gate_reasons.append("token_count_below_threshold")
        if not expression_dimensions:
            gate_reasons.append("missing_expression_dimensions")

        expression_score = self._calculate_speech_expression_score(expression_dimensions)
        speech_used = not gate_reasons and expression_score is not None

        return {
            "available": bool(speech_row),
            "speech_used": speech_used,
            "quality_gate": {
                "passed": speech_used,
                "reasons": gate_reasons,
                "min_audio_ms": self.SPEECH_GATE_MIN_AUDIO_MS,
                "min_tokens": self.SPEECH_GATE_MIN_TOKENS,
            },
            "audio_duration_ms": round(audio_duration_ms, 2),
            "token_count": token_count,
            "final_transcript_excerpt": final_transcript[:160],
            "word_timestamps": list((speech_row or {}).get("word_timestamps") or []),
            "expression_dimensions": {
                key: self._clamp_score(value)
                for key, value in (expression_dimensions or {}).items()
                if self._safe_float(value) is not None
            },
            "expression_score": expression_score,
            "turn_id": str(payload.get("turn_id", "")).strip(),
        }

    def build_scoring_snapshot(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        round_type = str(payload.get("round_type", "technical") or "technical").strip() or "technical"
        shortboard_rule = dict(self.SHORTBOARD_RULES.get(round_type, self.SHORTBOARD_RULES["technical"]))
        return {
            "evaluation_version": str(payload.get("evaluation_version", self.evaluation_version)).strip() or self.evaluation_version,
            "prompt_version": str(payload.get("prompt_version", self.prompt_version)).strip() or self.prompt_version,
            "schema_version": self.EVALUATION_SCHEMA_VERSION,
            "architecture": self.EVALUATION_ARCHITECTURE,
            "speech_fusion_version": self.SPEECH_FUSION_VERSION,
            "semantic_threshold": round(float(self.semantic_threshold), 4),
            "axis_weights": dict(self.AXIS_WEIGHTS),
            "layer_weights": dict(self.LAYER_WEIGHTS),
            "shortboard_rule": shortboard_rule,
            "rubric_scoring_version": "atomic_rubric_rules_v1",
            "speech_gate": {
                "min_audio_ms": self.SPEECH_GATE_MIN_AUDIO_MS,
                "min_tokens": self.SPEECH_GATE_MIN_TOKENS,
            },
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def _log_trace(self, payload: Dict[str, Any], event_type: str, status: str = "", duration_ms: Optional[float] = None, extra: Optional[Dict[str, Any]] = None) -> None:
        if not hasattr(self.db_manager, "log_evaluation_event"):
            return
        try:
            self.db_manager.log_evaluation_event(
                trace_id=str(payload.get("eval_task_key", "")).strip(),
                interview_id=str(payload.get("interview_id", "")).strip(),
                turn_id=str(payload.get("turn_id", "")).strip(),
                event_type=event_type,
                status=status,
                duration_ms=duration_ms,
                payload=extra or {},
            )
        except Exception:
            pass

    def _normalize_dimension_evidence(self, dimension_scores: Dict[str, Any]) -> Dict[str, Any]:
        normalized = {}
        for dim_key, dim_payload in (dimension_scores or {}).items():
            if not isinstance(dim_payload, dict):
                continue
            reason = str(dim_payload.get("reason", "") or "").strip()
            evidence = dim_payload.get("evidence") if isinstance(dim_payload.get("evidence"), dict) else {}
            normalized[dim_key] = {
                "score": self._clamp_score(dim_payload.get("score", 0.0)),
                "confidence": self._clamp_unit(dim_payload.get("confidence"), default=0.0),
                "reason": reason,
                "evidence": {
                    "hit_rubric_points": list(evidence.get("hit_rubric_points") or []),
                    "missed_rubric_points": list(evidence.get("missed_rubric_points") or []),
                    "source_quotes": list(evidence.get("source_quotes") or []),
                    "deduction_rationale": str(evidence.get("deduction_rationale") or reason),
                },
            }
        return normalized

    def _quote_matches_answer(self, quote: str, answer_text: str) -> bool:
        quote_text = self._sanitize_text(quote)
        answer = self._sanitize_text(answer_text)
        if not quote_text or not answer:
            return False
        if quote_text in answer:
            return True
        compact_quote = re.sub(r"\s+", "", quote_text).lower()
        compact_answer = re.sub(r"\s+", "", answer).lower()
        return bool(compact_quote and compact_quote in compact_answer)

    @staticmethod
    def _slugify_point_id(text: str, fallback: str) -> str:
        raw = str(text or "").strip().lower()
        tokens = re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", raw)
        if not tokens:
            return fallback
        compact = "_".join(tokens)[:48].strip("_")
        return compact or fallback

    def _infer_atomic_dimension(self, text: str, round_type: str, level: str, index: int) -> str:
        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        content = self._sanitize_text(text)
        if not dimensions:
            return "technical_accuracy"

        keyword_map = {
            "technical": [
                ("job_match", ["岗位", "业务", "场景", "工程实践", "落地", "生产", "经验"]),
                ("logic", ["逻辑", "步骤", "链路", "流程", "因果", "推理", "分析路径"]),
                ("completeness", ["完整", "覆盖", "遗漏", "边界", "异常", "兜底", "方案"]),
                ("knowledge_depth", ["原理", "底层", "权衡", "复杂度", "性能", "优化", "源码", "深入"]),
            ],
            "project": [
                ("authenticity", ["真实", "细节", "数据", "背景", "复盘"]),
                ("ownership", ["负责", "主导", "推进", "协作", "决策"]),
                ("technical_depth", ["架构", "技术", "原理", "性能", "难点"]),
                ("reflection", ["反思", "复盘", "改进", "教训"]),
            ],
            "system_design": [
                ("tradeoff_awareness", ["权衡", "取舍", "成本", "一致性", "可用性"]),
                ("scalability", ["扩展", "容量", "高并发", "吞吐", "分片"]),
                ("logic", ["步骤", "链路", "逻辑", "推理"]),
            ],
            "hr": [
                ("self_awareness", ["反思", "不足", "成长", "优势", "劣势"]),
                ("communication", ["沟通", "协作", "冲突", "表达"]),
                ("confidence", ["信心", "判断", "压力", "稳定"]),
                ("relevance", ["岗位", "匹配", "动机", "经历"]),
            ],
        }
        for dim, keywords in keyword_map.get(round_type, []):
            if dim in dimensions and any(keyword in content for keyword in keywords):
                return dim

        if round_type == "technical":
            if level == "excellent" and "knowledge_depth" in dimensions:
                return "knowledge_depth"
            if level == "good" and "completeness" in dimensions:
                return "completeness"
            return "technical_accuracy" if "technical_accuracy" in dimensions else dimensions[index % len(dimensions)]
        return dimensions[index % len(dimensions)]

    @staticmethod
    def _default_atomic_weight(level: str) -> float:
        return {
            "basic": 1.0,
            "good": 1.25,
            "excellent": 1.5,
        }.get(str(level or "").strip().lower(), 1.0)

    def build_atomic_rubric_points(
        self,
        scoring_rubric: Optional[Dict[str, Any]],
        layer1_result: Optional[Dict[str, Any]],
        round_type: str,
    ) -> list[Dict[str, Any]]:
        """Convert legacy rubric buckets into deterministic, weighted scoring points."""
        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        source = scoring_rubric if isinstance(scoring_rubric, dict) else {}
        explicit_points = source.get("atomic_points") or source.get("atomic_rubric_points")
        atomic_points: list[Dict[str, Any]] = []

        def append_point(raw_item: Any, level: str, index: int) -> None:
            if isinstance(raw_item, dict):
                expected = self._sanitize_text(
                    raw_item.get("expected")
                    or raw_item.get("point")
                    or raw_item.get("text")
                    or raw_item.get("label")
                    or raw_item.get("description")
                )
                raw_id = self._sanitize_text(raw_item.get("id") or raw_item.get("point_id"))
                raw_dimension = self._sanitize_text(raw_item.get("dimension"))
                raw_weight = self._safe_float(raw_item.get("weight"))
                core = bool(raw_item.get("core", level == "basic"))
            else:
                expected = self._sanitize_text(raw_item)
                raw_id = ""
                raw_dimension = ""
                raw_weight = None
                core = level == "basic"

            if not expected:
                return
            normalized_level = str(level or "basic").strip().lower()
            if normalized_level not in {"basic", "good", "excellent"}:
                normalized_level = "basic"
            dimension = raw_dimension if raw_dimension in dimensions else self._infer_atomic_dimension(expected, round_type, normalized_level, index)
            point_id = raw_id or self._slugify_point_id(expected, f"{normalized_level}_{index + 1}")
            if any(item.get("id") == point_id for item in atomic_points):
                point_id = f"{point_id}_{index + 1}"
            atomic_points.append({
                "id": point_id,
                "level": normalized_level,
                "dimension": dimension,
                "weight": round(float(raw_weight if raw_weight is not None and raw_weight > 0 else self._default_atomic_weight(normalized_level)), 4),
                "expected": expected,
                "core": bool(core),
                "source": "explicit" if isinstance(raw_item, dict) else "legacy_rubric",
            })

        if isinstance(explicit_points, list):
            for idx, item in enumerate(explicit_points):
                append_point(item, str((item or {}).get("level", "basic")) if isinstance(item, dict) else "basic", idx)

        if not atomic_points:
            idx = 0
            for level in ("basic", "good", "excellent"):
                for item in source.get(level, []) or []:
                    append_point(item, level, idx)
                    idx += 1

        if not atomic_points:
            key_points = (layer1_result or {}).get("key_points") if isinstance((layer1_result or {}).get("key_points"), dict) else {}
            idx = 0
            for item in key_points.get("covered", []) or []:
                point = item.get("point") if isinstance(item, dict) else item
                append_point(point, "basic", idx)
                idx += 1
            for item in key_points.get("missing", []) or []:
                append_point(item, "good", idx)
                idx += 1

        return atomic_points[:30]

    def _normalize_point_judgements(
        self,
        point_judgements: Any,
        atomic_points: list[Dict[str, Any]],
        answer_text: str = "",
    ) -> Dict[str, Dict[str, Any]]:
        if isinstance(point_judgements, dict):
            raw_items = [
                {"point_id": key, **(value if isinstance(value, dict) else {"status": value})}
                for key, value in point_judgements.items()
            ]
        elif isinstance(point_judgements, list):
            raw_items = point_judgements
        else:
            raw_items = []

        valid_ids = {str(item.get("id") or "") for item in atomic_points}
        status_aliases = {
            "hit": "hit",
            "covered": "hit",
            "yes": "hit",
            "true": "hit",
            "partial": "partial",
            "partially_hit": "partial",
            "partially_covered": "partial",
            "miss": "miss",
            "missing": "miss",
            "no": "miss",
            "false": "miss",
            "contradict": "contradict",
            "contradiction": "contradict",
            "wrong": "contradict",
            "incorrect": "contradict",
        }
        normalized: Dict[str, Dict[str, Any]] = {}
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            point_id = self._sanitize_text(raw.get("point_id") or raw.get("id"))
            if point_id not in valid_ids:
                continue
            raw_status = self._sanitize_text(raw.get("status") or raw.get("judgement") or raw.get("result")).lower()
            status = status_aliases.get(raw_status, "miss")
            quote = self._sanitize_text(raw.get("quote") or raw.get("source_quote"))[:160]
            quote_valid = self._quote_matches_answer(quote, answer_text)
            quote_required = status in {"hit", "partial", "contradict"}
            raw_confidence = self._clamp_unit(raw.get("confidence"), default=0.65)
            confidence = raw_confidence
            if quote_required and not quote_valid:
                confidence = self._clamp_unit(confidence * 0.55, default=0.35)
            normalized[point_id] = {
                "point_id": point_id,
                "status": status,
                "confidence": confidence,
                "raw_confidence": raw_confidence,
                "quote": quote,
                "quote_valid": bool(quote_valid),
                "quote_required": bool(quote_required),
                "reason": self._sanitize_text(raw.get("reason") or raw.get("rationale"))[:240],
            }
        return normalized

    def _apply_atomic_rubric_rules(
        self,
        layer2_result: Dict[str, Any],
        atomic_points: list[Dict[str, Any]],
        round_type: str,
        answer_text: str = "",
    ) -> Dict[str, Any]:
        if not atomic_points:
            return layer2_result
        judgement_map = self._normalize_point_judgements(
            layer2_result.get("point_judgements"),
            atomic_points,
            answer_text=answer_text,
        )
        if not judgement_map:
            return layer2_result

        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        fallback_dimensions = layer2_result.get("dimension_scores") if isinstance(layer2_result.get("dimension_scores"), dict) else {}
        ratio_map = {"hit": 1.0, "partial": 0.55, "miss": 0.0, "contradict": 0.0}

        dimension_buckets: Dict[str, list[Tuple[Dict[str, Any], Dict[str, Any]]]] = {dim: [] for dim in dimensions}
        level_buckets: Dict[str, list[Tuple[Dict[str, Any], Dict[str, Any]]]] = {"basic": [], "good": [], "excellent": []}
        normalized_judgements = []
        quote_validation = {
            "checked": 0,
            "valid": 0,
            "invalid": 0,
            "invalid_items": [],
        }
        core_contradictions = []
        for point in atomic_points:
            point_id = str(point.get("id") or "")
            judgement = judgement_map.get(point_id)
            if not judgement:
                continue
            dim = str(point.get("dimension") or "").strip()
            if dim not in dimension_buckets:
                continue
            dimension_buckets[dim].append((point, judgement))
            level = str(point.get("level") or "basic").strip().lower()
            if level in level_buckets:
                level_buckets[level].append((point, judgement))
            if judgement.get("quote_required"):
                quote_validation["checked"] += 1
                if judgement.get("quote_valid"):
                    quote_validation["valid"] += 1
                else:
                    quote_validation["invalid"] += 1
                    quote_validation["invalid_items"].append({
                        "point_id": point_id,
                        "status": judgement.get("status"),
                        "quote": judgement.get("quote", ""),
                    })
            if bool(point.get("core")) and judgement.get("status") == "contradict":
                core_contradictions.append({
                    "point_id": point_id,
                    "dimension": dim,
                    "expected": point.get("expected", ""),
                    "quote": judgement.get("quote", ""),
                    "quote_valid": bool(judgement.get("quote_valid")),
                })
            normalized_judgements.append({
                **judgement,
                "expected": point.get("expected", ""),
                "dimension": dim,
                "level": level,
                "weight": point.get("weight", 1.0),
                "core": bool(point.get("core")),
            })

        if not normalized_judgements:
            return layer2_result
        quote_validation["invalid_items"] = quote_validation["invalid_items"][:10]

        final_dimensions: Dict[str, Dict[str, Any]] = {}
        dimension_caps: Dict[str, float] = {}
        for item in core_contradictions:
            dimension = str(item.get("dimension") or "").strip()
            if dimension:
                dimension_caps[dimension] = min(float(dimension_caps.get(dimension, 100.0)), 55.0)

        for dim in dimensions:
            bucket = dimension_buckets.get(dim) or []
            if not bucket:
                fallback = fallback_dimensions.get(dim) if isinstance(fallback_dimensions.get(dim), dict) else {}
                final_dimensions[dim] = {
                    "score": self._clamp_score(fallback.get("score", 60.0)),
                    "confidence": self._clamp_unit(fallback.get("confidence"), default=0.45),
                    "reason": self._sanitize_text(fallback.get("reason")) or "该维度未覆盖原子评分点，保留语义基线分。",
                    "evidence": fallback.get("evidence") if isinstance(fallback.get("evidence"), dict) else {
                        "scoring_source": "semantic_fallback",
                    },
                }
                continue

            total_weight = sum(float(point.get("weight") or 1.0) for point, _ in bucket)
            earned = sum(
                float(point.get("weight") or 1.0) * ratio_map.get(judgement.get("status"), 0.0)
                for point, judgement in bucket
            )
            score = self._clamp_score((earned / total_weight) * 100.0 if total_weight > 0 else 0.0)
            cap = dimension_caps.get(dim)
            cap_applied = cap is not None
            if cap is not None and score > cap:
                score = self._clamp_score(cap)
            confidence_numerator = sum(
                float(point.get("weight") or 1.0) * float(judgement.get("confidence") or 0.0)
                for point, judgement in bucket
            )
            dimension_confidence = self._clamp_unit(
                confidence_numerator / total_weight if total_weight > 0 else 0.0,
                default=0.0,
            )
            hit_points = [str(point.get("expected") or "") for point, judgement in bucket if judgement.get("status") == "hit"]
            partial_points = [str(point.get("expected") or "") for point, judgement in bucket if judgement.get("status") == "partial"]
            missed_points = [str(point.get("expected") or "") for point, judgement in bucket if judgement.get("status") in {"miss", "contradict"}]
            quotes = [judgement.get("quote", "") for _, judgement in bucket if judgement.get("quote") and judgement.get("quote_valid")]
            final_dimensions[dim] = {
                "score": score,
                "confidence": dimension_confidence,
                "reason": f"由 {len(bucket)} 个原子评分点按权重确定性计算。",
                "evidence": {
                    "scoring_source": "atomic_rubric_rules_v1",
                    "hit_rubric_points": hit_points[:5],
                    "partial_rubric_points": partial_points[:5],
                    "missed_rubric_points": missed_points[:5],
                    "source_quotes": quotes[:3],
                    "quote_validation": {
                        "checked": len([1 for _, judgement in bucket if judgement.get("quote_required")]),
                        "invalid": len([1 for _, judgement in bucket if judgement.get("quote_required") and not judgement.get("quote_valid")]),
                    },
                    "score_cap": {
                        "applied": cap_applied,
                        "max_score": cap,
                        "reason": "core_point_contradiction" if cap_applied else "",
                    },
                    "deduction_rationale": "未命中或答错的原子评分点按权重扣分。",
                },
            }

        def level_match(level: str) -> float:
            bucket = level_buckets.get(level) or []
            if not bucket:
                return 0.0
            total_weight = sum(float(point.get("weight") or 1.0) for point, _ in bucket)
            earned = sum(float(point.get("weight") or 1.0) * ratio_map.get(judgement.get("status"), 0.0) for point, judgement in bucket)
            return self._clamp_score((earned / total_weight) * 100.0 if total_weight > 0 else 0.0)

        basic_match = level_match("basic")
        good_match = level_match("good")
        excellent_match = level_match("excellent")
        if excellent_match >= 70.0 and good_match >= 70.0 and basic_match >= 70.0:
            final_level = "excellent"
        elif good_match >= 60.0 and basic_match >= 70.0:
            final_level = "good"
        else:
            final_level = "basic"

        pre_cap_overall_score = round(sum(item["score"] for item in final_dimensions.values()) / len(final_dimensions), 2) if final_dimensions else 0.0
        overall_cap = 65.0 if core_contradictions else None
        overall_score = pre_cap_overall_score
        if overall_cap is not None and overall_score > overall_cap:
            overall_score = overall_cap
        confidence = self._clamp_unit(
            sum(float(item.get("confidence") or 0.0) for item in final_dimensions.values()) / len(final_dimensions),
            default=0.65,
        ) if final_dimensions else self._clamp_unit(0.0)

        updated = dict(layer2_result or {})
        updated["atomic_rubric_points"] = atomic_points
        updated["point_judgements"] = normalized_judgements
        updated["rubric_scoring"] = {
            "mode": "atomic_rubric_rules_v1",
            "point_count": len(atomic_points),
            "judged_count": len(normalized_judgements),
            "status_weights": ratio_map,
            "pre_cap_overall_score": pre_cap_overall_score,
            "overall_score": overall_score,
            "confidence": confidence,
            "quote_validation": quote_validation,
            "core_error_caps": {
                "applied": bool(core_contradictions),
                "dimension_caps": dimension_caps,
                "overall_cap": overall_cap,
                "core_contradictions": core_contradictions[:10],
            },
        }
        updated["rubric_eval"] = {
            **(updated.get("rubric_eval") if isinstance(updated.get("rubric_eval"), dict) else {}),
            "basic_match": basic_match,
            "good_match": good_match,
            "excellent_match": excellent_match,
            "final_level": final_level,
            "confidence": confidence,
            "reason": "基于原子评分点命中状态确定性计算。",
        }
        updated["dimension_scores"] = final_dimensions
        updated["overall_score"] = overall_score
        return updated

    def _build_video_penalties(self, video_context: Dict[str, Any]) -> list[Dict[str, Any]]:
        penalties = []
        if not isinstance(video_context, dict):
            return penalties
        face_count = int(video_context.get("face_count", 1) or 1)
        has_face = bool(video_context.get("has_face", True))
        raw_off_screen = self._safe_float(video_context.get("off_screen_ratio")) or 0.0
        off_screen_ratio = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen
        flags = [str(flag).strip() for flag in (video_context.get("flags") or []) if str(flag).strip()]

        if face_count > 1:
            penalties.append({"code": "multi_person", "label": "检测到多张人脸", "deduct_score": 40.0, "evidence": {"face_count": face_count}})
        if not has_face:
            penalties.append({"code": "face_missing", "label": "候选人离开镜头", "deduct_score": 25.0, "evidence": {"has_face": has_face}})
        if off_screen_ratio >= 20.0:
            penalties.append({"code": "off_screen", "label": "视线频繁离开屏幕", "deduct_score": round(min(20.0, off_screen_ratio * 0.25), 2), "evidence": {"off_screen_ratio": round(off_screen_ratio, 2)}})
        for flag in flags:
            if flag in {"suspicious_object", "no_face_long"}:
                penalties.append({"code": flag, "label": flag, "deduct_score": 10.0, "evidence": {"flag": flag}})
        return penalties

    def fuse_speech_with_dimension_scores(
        self,
        round_type: str,
        layer2_result: Dict[str, Any],
        speech_context: Optional[Dict[str, Any]] = None,
        video_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        layer2_result = dict(layer2_result or {})
        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        raw_dimension_scores = layer2_result.get("dimension_scores", {}) or {}
        provided_scores = []
        for payload in raw_dimension_scores.values():
            if not isinstance(payload, dict):
                continue
            score_value = self._safe_float(payload.get("score"))
            if score_value is None:
                continue
            provided_scores.append(self._clamp_score(score_value))
        fallback_dimension_score = round(
            sum(provided_scores) / len(provided_scores),
            2,
        ) if provided_scores else 60.0

        text_base_dimension_scores = {}
        for dim in dimensions:
            payload = raw_dimension_scores.get(dim)
            payload_dict = payload if isinstance(payload, dict) else {}
            has_explicit_dimension = dim in raw_dimension_scores and isinstance(payload, dict)
            raw_score = payload_dict.get("score")
            safe_score = self._safe_float(raw_score)
            resolved_score = self._clamp_score(
                safe_score if safe_score is not None else fallback_dimension_score
            )
            reason = str(payload_dict.get("reason", "") or "").strip()
            evidence = payload_dict.get("evidence") if isinstance(payload_dict.get("evidence"), dict) else {}

            if not has_explicit_dimension:
                reason = "该维度未独立产出，按同题文本维度均值估算。"
                evidence = {
                    "estimation": "fallback_mean",
                    "fallback_score": fallback_dimension_score,
                }

            text_base_dimension_scores[dim] = {
                "score": resolved_score,
                "reason": reason,
                "evidence": evidence,
            }

        final_dimension_scores = {
            dim: {
                "score": round(float(text_base_dimension_scores[dim]["score"]), 2),
                "reason": text_base_dimension_scores[dim]["reason"],
                "evidence": text_base_dimension_scores[dim].get("evidence") or {},
            }
            for dim in dimensions
        }

        overall_score_base = round(
            sum(item["score"] for item in text_base_dimension_scores.values()) / len(text_base_dimension_scores),
            2,
        ) if text_base_dimension_scores else 0.0

        overall_score_before_atomic_caps = overall_score_base
        rubric_scoring = layer2_result.get("rubric_scoring") if isinstance(layer2_result.get("rubric_scoring"), dict) else {}
        core_error_caps = rubric_scoring.get("core_error_caps") if isinstance(rubric_scoring.get("core_error_caps"), dict) else {}
        overall_cap = self._safe_float(core_error_caps.get("overall_cap")) if core_error_caps.get("applied") else None
        if overall_cap is not None and overall_score_base > overall_cap:
            overall_score_base = self._clamp_score(overall_cap)

        overall_score_final = overall_score_base

        layer2_result.update({
            "text_base_dimension_scores": text_base_dimension_scores,
            "speech_context": speech_context or {},
            "video_context": video_context or {},
            "speech_adjustments": {dim: 0.0 for dim in dimensions},
            "video_adjustments": {dim: 0.0 for dim in dimensions},
            "final_dimension_scores": final_dimension_scores,
            "overall_score_base": overall_score_base,
            "overall_score_final": overall_score_final,
            "overall_score_before_atomic_caps": overall_score_before_atomic_caps,
            "speech_used": bool(speech_context and speech_context.get("speech_used")),
            "video_used": bool(video_context and video_context.get("status") == "ready"),
            "speech_fusion_version": self.SPEECH_FUSION_VERSION,
            "dimension_scores": final_dimension_scores,
            "overall_score": overall_score_final,
        })
        return layer2_result

    def evaluate_speech_layer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        speech_context = self.build_speech_context(payload)
        expression_dimensions = (speech_context or {}).get("expression_dimensions") or {}
        expression_score = self._safe_float((speech_context or {}).get("expression_score"))
        speech_used = bool((speech_context or {}).get("speech_used")) and expression_score is not None
        audio_duration_ms = float((speech_context or {}).get("audio_duration_ms") or 0.0)
        token_count = int((speech_context or {}).get("token_count") or 0)
        confidence_breakdown = self._compute_speech_axis_confidence(
            speech_context=speech_context,
            expression_dimensions=expression_dimensions,
            speech_used=speech_used,
        )

        if speech_used:
            status = "ready"
        elif (speech_context or {}).get("available"):
            status = "insufficient_data"
        else:
            status = "unavailable"

        evidence_service = self.speech_evidence_service.build(
            speech_context=speech_context,
            confidence=self._clamp_unit(confidence_breakdown.get("overall_confidence"), default=0.0),
        )

        return {
            "status": status,
            "overall_score": round(float(expression_score), 2) if speech_used else None,
            "confidence": self._clamp_unit(confidence_breakdown.get("overall_confidence"), default=0.0),
            "confidence_breakdown": confidence_breakdown,
            "dimension_scores": {
                key: {"score": self._clamp_score(value), "reason": ""}
                for key, value in (expression_dimensions or {}).items()
                if self._safe_float(value) is not None
            },
            "summary": {
                "audio_duration_ms": audio_duration_ms,
                "token_count": token_count,
                "quality_gate": (speech_context or {}).get("quality_gate") or {},
                "axis": "delivery",
            },
            "evidence": {
                "final_transcript_excerpt": str((speech_context or {}).get("final_transcript_excerpt", "") or "").strip(),
                "quality_gate_reasons": list(((speech_context or {}).get("quality_gate") or {}).get("reasons") or []),
            },
            "evidence_service": evidence_service,
            "source": "speech_metrics_final",
        }

    def evaluate_video_layer(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        video_context = dict((payload or {}).get("video_context") or (payload or {}).get("detection_state") or {})
        if not video_context:
            return {
                "status": "unavailable",
                "overall_score": None,
                "confidence": 0.0,
                "dimension_scores": {},
                "summary": {"reason": "missing_video_context"},
                "evidence": {},
                "source": "detection_state",
            }

        has_face = bool(video_context.get("has_face", True))
        face_count = int(video_context.get("face_count", 1) or 1)
        raw_off_screen = self._safe_float(video_context.get("off_screen_ratio")) or 0.0
        off_screen_ratio = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen
        off_screen_ratio = max(0.0, min(100.0, off_screen_ratio))
        hr = self._safe_float(video_context.get("hr"))
        rppg_reliable = bool(video_context.get("rppg_reliable", False))
        risk_score = self._safe_float(video_context.get("risk_score"))
        flags = [str(flag).strip() for flag in (video_context.get("flags") or []) if str(flag).strip()]
        
        video_features = video_context.get("video_features") or {}
        expression_score = self._safe_float(video_features.get("expression_score")) or 70.0
        engagement_signals = video_features.get("engagement_signals") or {}
        head_movement = self._safe_float(engagement_signals.get("head_movement")) or 50.0
        facial_activity = self._safe_float(engagement_signals.get("facial_activity")) or 50.0

        gaze_focus_score = self._clamp_score(100.0 - off_screen_ratio)

        posture_compliance_score = self._clamp_score(
            62.0
            + max(0.0, min(24.0, head_movement * 0.24))
            + max(0.0, min(14.0, facial_activity * 0.14))
            - (8.0 if face_count > 1 else 0.0)
            - (18.0 if not has_face else 0.0)
        )

        physiology_score = 55.0
        if rppg_reliable and hr is not None:
            physiology_score = 85.0 if 50.0 <= hr <= 120.0 else 65.0
        physiology_score = self._clamp_score(physiology_score)

        expression_naturalness_score = self._clamp_score(
            expression_score - (5.0 if not has_face else 0.0)
        )

        engagement_level_score = self._clamp_score(
            (head_movement * 0.4 + facial_activity * 0.4 + (100.0 - off_screen_ratio) * 0.2)
        )

        dimension_scores = {
            "gaze_focus": {
                "score": gaze_focus_score,
                "reason": f"基于离屏比例 ({round(off_screen_ratio, 1)}%) 与在镜状态估计。",
                "evidence": {
                    "off_screen_ratio": round(off_screen_ratio, 2),
                    "has_face": has_face,
                }
            },
            "posture_compliance": {
                "score": posture_compliance_score,
                "reason": f"基于同框人数 ({face_count}) 与镜头在位稳定性估计。",
                "evidence": {
                    "face_count": face_count,
                    "has_face": has_face,
                }
            },
            "physiology_stability": {
                "score": physiology_score,
                "reason": f"基于心率可用性 (HR={hr}) 与异常风险估计。" if rppg_reliable else "基于基础生理指标估计。",
                "evidence": {
                    "hr": hr,
                    "rppg_reliable": rppg_reliable,
                    "risk_score": risk_score,
                }
            },
            "expression_naturalness": {
                "score": expression_naturalness_score,
                "reason": "基于面部表情自然度与微表情分析。",
                "evidence": {
                    "expression_score": round(expression_score, 2),
                    "face_count": face_count,
                }
            },
            "engagement_level": {
                "score": engagement_level_score,
                "reason": "基于头部活动、面部活跃度与眼神专注度。",
                "evidence": {
                    "head_movement": round(head_movement, 2),
                    "facial_activity": round(facial_activity, 2),
                    "gaze_focus": round(gaze_focus_score, 2),
                }
            },
        }
        
        weighted_sum = sum(
            dimension_scores[dim]["score"] * weight
            for dim, weight in self.VIDEO_DIMENSION_WEIGHTS.items()
        )
        overall_score = round(weighted_sum / sum(self.VIDEO_DIMENSION_WEIGHTS.values()), 2)
        confidence_breakdown = self._compute_video_axis_confidence(
            video_context=video_context,
            video_features=video_features if isinstance(video_features, dict) else {},
            engagement_signals=engagement_signals if isinstance(engagement_signals, dict) else {},
        )

        integrity_signals = self._build_video_penalties(video_context)

        evidence_service = self.video_evidence_service.build(
            video_context=video_context,
            dimension_scores=dimension_scores,
            confidence=self._clamp_unit(confidence_breakdown.get("overall_confidence"), default=0.0),
            integrity_signals=integrity_signals,
        )

        return {
            "status": "ready",
            "overall_score": overall_score,
            "confidence": self._clamp_unit(confidence_breakdown.get("overall_confidence"), default=0.0),
            "confidence_breakdown": confidence_breakdown,
            "dimension_scores": dimension_scores,
            "summary": {
                "video_features_snapshot": video_features if isinstance(video_features, dict) else {},
                "engagement_signals": engagement_signals if isinstance(engagement_signals, dict) else {},
                "axis": "presence",
            },
            "evidence": {
                "flags": flags,
                "has_face": has_face,
                "face_count": face_count,
                "off_screen_ratio": round(off_screen_ratio, 2),
                "hr": hr,
                "rppg_reliable": rppg_reliable,
                "risk_score": risk_score,
                "expression_score": round(expression_score, 2),
                "head_movement": round(head_movement, 2),
                "facial_activity": round(facial_activity, 2),
            },
            "integrity_signals": integrity_signals,
            "evidence_service": evidence_service,
            "source": "detection_state",
        }

    def build_text_layer_result(self, layer2_result: Dict[str, Any]) -> Dict[str, Any]:
        result = dict(layer2_result or {})
        dimension_scores = result.get("final_dimension_scores") or result.get("dimension_scores") or {}
        score = self._safe_float(result.get("overall_score_final"))
        if score is None:
            score = self._safe_float(result.get("overall_score"))
        rubric_eval = result.get("rubric_eval") or {}
        confidence_breakdown = result.get("confidence_breakdown") if isinstance(result.get("confidence_breakdown"), dict) else {}
        confidence = self._clamp_unit(
            confidence_breakdown.get("overall_confidence", rubric_eval.get("confidence", 0.55)),
            default=0.55 if dimension_scores else 0.0,
        )
        return {
            "status": "ready" if dimension_scores else "unavailable",
            "overall_score": round(float(score), 2) if score is not None else None,
            "confidence": confidence,
            "confidence_breakdown": confidence_breakdown,
            "dimension_scores": dimension_scores,
            "rubric_eval": rubric_eval,
            "summary": result.get("summary") or {},
            "axis": "content",
            "source": "rubric_llm",
        }

    def _build_dimension_evidence_chain(self, layer2_result: Dict[str, Any], fallback_answer: str = "") -> list[Dict[str, Any]]:
        evidence_chain = []
        dimension_scores = (layer2_result or {}).get("final_dimension_scores") or (layer2_result or {}).get("dimension_scores") or {}
        speech_context = (layer2_result or {}).get("speech_context") if isinstance((layer2_result or {}).get("speech_context"), dict) else {}
        word_timestamps = list((speech_context or {}).get("word_timestamps") or [])
        fallback_quote = self._sanitize_text(fallback_answer)[:80]

        for dim_key, dim_payload in (dimension_scores or {}).items():
            if not isinstance(dim_payload, dict):
                continue
            evidence = dim_payload.get("evidence") if isinstance(dim_payload.get("evidence"), dict) else {}
            quotes = [self._sanitize_text(x) for x in (evidence.get("source_quotes") or []) if self._sanitize_text(x)]
            if not quotes and fallback_quote:
                quotes = [fallback_quote]

            for quote in quotes[:2]:
                span = self._infer_quote_time_span(quote, word_timestamps)
                evidence_chain.append({
                    "dimension": dim_key,
                    "event_type": "support",
                    "quote": quote,
                    "start_ms": span.get("start_ms"),
                    "end_ms": span.get("end_ms"),
                    "reason": self._sanitize_text((dim_payload or {}).get("reason")),
                    "confidence": self._clamp_unit(0.9 if span.get("start_ms") is not None else 0.7, default=0.7),
                    "hit_rubric_points": list(evidence.get("hit_rubric_points") or []),
                })

            for miss in [self._sanitize_text(x) for x in (evidence.get("missed_rubric_points") or []) if self._sanitize_text(x)][:2]:
                evidence_chain.append({
                    "dimension": dim_key,
                    "event_type": "deduction",
                    "quote": "",
                    "start_ms": None,
                    "end_ms": None,
                    "reason": self._sanitize_text(evidence.get("deduction_rationale") or dim_payload.get("reason")),
                    "confidence": 0.75,
                    "missed_rubric_point": miss,
                })

        return evidence_chain

    def _extract_layer1_points(self, layer1_result: Dict[str, Any]) -> Tuple[list[str], list[str], list[str]]:
        key_points = (layer1_result or {}).get("key_points") if isinstance((layer1_result or {}).get("key_points"), dict) else {}
        covered_payload = list((key_points or {}).get("covered") or [])
        missing_points = [self._sanitize_text(x) for x in (key_points or {}).get("missing") or [] if self._sanitize_text(x)]
        red_flags = [self._sanitize_text(x) for x in ((layer1_result or {}).get("signals") or {}).get("red_flags") or [] if self._sanitize_text(x)]

        covered_points = []
        for item in covered_payload:
            if isinstance(item, dict):
                point = self._sanitize_text(item.get("point"))
            else:
                point = self._sanitize_text(item)
            if point:
                covered_points.append(point)
        return covered_points, missing_points, red_flags

    def _compute_content_evidence_correction(
        self,
        llm_score: float,
        coverage_ratio: float,
        rubric_match: Optional[Dict[str, Any]],
        evidence_density: float,
        missing_points: list[str],
        red_flags: list[str],
    ) -> Dict[str, Any]:
        rubric_match = rubric_match if isinstance(rubric_match, dict) else {}
        basic_match = max(0.0, min(1.0, float(rubric_match.get("basic", 0.0) or 0.0)))
        good_match = max(0.0, min(1.0, float(rubric_match.get("good", 0.0) or 0.0)))
        excellent_match = max(0.0, min(1.0, float(rubric_match.get("excellent", 0.0) or 0.0)))

        positive_bonus = round(
            min(4.0, coverage_ratio * 4.0)
            + min(2.5, good_match * 1.5 + excellent_match * 1.0)
            + min(1.5, evidence_density * 1.5)
            + min(0.8, basic_match * 0.8),
            2,
        )

        missing_penalty = round(min(8.0, len(missing_points) * 2.5), 2)
        risk_penalty = round(min(12.0, len(red_flags) * 6.0), 2)
        total_penalty = round(missing_penalty + risk_penalty, 2)

        net_correction = round(max(-18.0, min(8.0, positive_bonus - total_penalty)), 2)
        corrected_score = self._clamp_score(llm_score + net_correction)

        return {
            "strategy": "llm_anchor_plus_evidence_correction_v1",
            "llm_anchor_score": round(float(llm_score), 2),
            "positive_bonus": positive_bonus,
            "missing_penalty": missing_penalty,
            "risk_penalty": risk_penalty,
            "net_correction": net_correction,
            "corrected_score": corrected_score,
            "components": {
                "coverage_ratio": round(float(coverage_ratio), 4),
                "basic_match": round(basic_match, 4),
                "good_match": round(good_match, 4),
                "excellent_match": round(excellent_match, 4),
                "evidence_density": round(float(evidence_density), 4),
                "missing_points_count": len(missing_points),
                "red_flags_count": len(red_flags),
            },
        }

    def _compute_text_axis_confidence(
        self,
        payload: Optional[Dict[str, Any]],
        dimension_scores: Dict[str, Any],
        base_conf: float,
        coverage_ratio: float,
        evidence_density: float,
        rubric_match: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        answer_text = self._sanitize_text((payload or {}).get("answer"))
        token_count = self._count_transcript_tokens(answer_text)
        dimension_count = max(1, len(dimension_scores or {}))
        rubric_match = rubric_match if isinstance(rubric_match, dict) else {}
        rubric_signal = max(
            float(rubric_match.get("basic", 0.0) or 0.0),
            float(rubric_match.get("good", 0.0) or 0.0),
            float(rubric_match.get("excellent", 0.0) or 0.0),
        )

        data_confidence = self._clamp_unit(
            0.25
            + min(0.35, token_count / 120.0 * 0.35)
            + min(0.20, evidence_density * 0.20)
            + min(0.20, dimension_count / 5.0 * 0.20),
            default=0.0,
        )
        model_confidence = self._clamp_unit(base_conf, default=0.0)
        rubric_confidence = self._clamp_unit(
            coverage_ratio * 0.5 + evidence_density * 0.2 + min(1.0, rubric_signal) * 0.3,
            default=0.0,
        )
        overall_confidence = self._clamp_unit(
            data_confidence * 0.4 + model_confidence * 0.3 + rubric_confidence * 0.3,
            default=0.0,
        )
        return {
            "data_confidence": data_confidence,
            "model_confidence": model_confidence,
            "rubric_confidence": rubric_confidence,
            "overall_confidence": overall_confidence,
            "inputs": {
                "token_count": token_count,
                "dimension_count": dimension_count,
                "coverage_ratio": round(float(coverage_ratio), 4),
                "evidence_density": round(float(evidence_density), 4),
            },
        }

    def _compute_speech_axis_confidence(
        self,
        speech_context: Dict[str, Any],
        expression_dimensions: Dict[str, Any],
        speech_used: bool,
    ) -> Dict[str, Any]:
        audio_duration_ms = float((speech_context or {}).get("audio_duration_ms") or 0.0)
        token_count = int((speech_context or {}).get("token_count") or 0)
        quality_gate = (speech_context or {}).get("quality_gate") if isinstance((speech_context or {}).get("quality_gate"), dict) else {}
        gate_passed = bool((quality_gate or {}).get("passed"))
        gate_reasons = list((quality_gate or {}).get("reasons") or [])
        dimension_count = max(1, len(expression_dimensions or {}))
        dimension_coverage = min(1.0, dimension_count / max(1, len(self.SPEECH_EXPRESSION_WEIGHTS)))
        duration_factor = min(1.0, audio_duration_ms / 30000.0)
        token_factor = min(1.0, token_count / 120.0)

        data_confidence = self._clamp_unit(
            0.15 + duration_factor * 0.45 + token_factor * 0.25 + dimension_coverage * 0.15,
            default=0.0,
        )
        model_confidence = self._clamp_unit(
            0.2
            + (0.45 if speech_used else 0.0)
            + dimension_coverage * 0.2
            - min(0.15, len(gate_reasons) * 0.03),
            default=0.0,
        )
        rubric_confidence = self._clamp_unit(
            (0.55 if gate_passed else 0.15) + dimension_coverage * 0.25,
            default=0.0,
        )
        overall_confidence = self._clamp_unit(
            data_confidence * 0.4 + model_confidence * 0.3 + rubric_confidence * 0.3,
            default=0.0,
        )
        return {
            "data_confidence": data_confidence,
            "model_confidence": model_confidence,
            "rubric_confidence": rubric_confidence,
            "overall_confidence": overall_confidence,
            "inputs": {
                "audio_duration_ms": round(audio_duration_ms, 2),
                "token_count": token_count,
                "dimension_count": dimension_count,
                "dimension_coverage": round(dimension_coverage, 4),
                "quality_gate_passed": gate_passed,
                "quality_gate_reason_count": len(gate_reasons),
            },
        }

    def _compute_video_axis_confidence(
        self,
        video_context: Dict[str, Any],
        video_features: Dict[str, Any],
        engagement_signals: Dict[str, Any],
    ) -> Dict[str, Any]:
        has_face = bool(video_context.get("has_face", True))
        face_count = int(video_context.get("face_count", 1) or 1)
        rppg_reliable = bool(video_context.get("rppg_reliable", False))
        raw_off_screen = self._safe_float(video_context.get("off_screen_ratio")) or 0.0
        off_screen_ratio = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen
        off_screen_ratio = max(0.0, min(100.0, off_screen_ratio))

        feature_hits = 0
        if self._safe_float(video_features.get("expression_score")) is not None:
            feature_hits += 1
        if self._safe_float(engagement_signals.get("head_movement")) is not None:
            feature_hits += 1
        if self._safe_float(engagement_signals.get("facial_activity")) is not None:
            feature_hits += 1
        feature_coverage = min(1.0, feature_hits / 3.0)

        data_confidence = self._clamp_unit(
            0.15
            + (0.35 if has_face else 0.0)
            + (0.2 if face_count == 1 else 0.0)
            + feature_coverage * 0.2
            + (0.1 if off_screen_ratio < 35.0 else 0.0),
            default=0.0,
        )
        model_confidence = self._clamp_unit(
            0.2
            + (0.25 if has_face else 0.0)
            + (0.2 if rppg_reliable else 0.0)
            + feature_coverage * 0.25,
            default=0.0,
        )
        rubric_confidence = self._clamp_unit(
            0.2
            + (0.25 if face_count == 1 else 0.0)
            + (0.2 if off_screen_ratio < 35.0 else 0.0)
            + (0.15 if has_face else 0.0)
            + feature_coverage * 0.2,
            default=0.0,
        )
        overall_confidence = self._clamp_unit(
            data_confidence * 0.4 + model_confidence * 0.3 + rubric_confidence * 0.3,
            default=0.0,
        )
        return {
            "data_confidence": data_confidence,
            "model_confidence": model_confidence,
            "rubric_confidence": rubric_confidence,
            "overall_confidence": overall_confidence,
            "inputs": {
                "has_face": has_face,
                "face_count": face_count,
                "rppg_reliable": rppg_reliable,
                "off_screen_ratio": round(off_screen_ratio, 2),
                "feature_hits": feature_hits,
                "feature_coverage": round(feature_coverage, 4),
            },
        }

    def _build_content_layer(
        self,
        layer1_result: Optional[Dict[str, Any]],
        layer2_result: Optional[Dict[str, Any]],
        text_layer: Optional[Dict[str, Any]],
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        layer2_payload = dict(layer2_result or {})
        text_payload = dict(text_layer or {})

        dimension_scores = (
            layer2_payload.get("final_dimension_scores")
            or layer2_payload.get("dimension_scores")
            or text_payload.get("dimension_scores")
            or {}
        )
        if not dimension_scores:
            return {
                "status": "unavailable",
                "overall_score": None,
                "confidence": 0.0,
                "dimension_scores": {},
                "checklist": {"total": 0, "hit": 0, "items": []},
                "deductions": [],
                "evidence_chain": [],
                "summary": {"reason": "missing_content_dimensions"},
                "source": "content_axis",
            }

        llm_score = self._safe_float(layer2_payload.get("overall_score_final"))
        if llm_score is None:
            llm_score = self._safe_float(layer2_payload.get("overall_score"))
        if llm_score is None:
            llm_score = self._safe_float(text_payload.get("overall_score"))
        llm_score = self._clamp_score(llm_score if llm_score is not None else 0.0)

        covered_points, missing_points, red_flags = self._extract_layer1_points(layer1_result or {})
        total_points = len(covered_points) + len(missing_points)
        point_unit = (100.0 / total_points) if total_points > 0 else 0.0
        checklist_score = round(len(covered_points) * point_unit, 2) if total_points > 0 else llm_score

        deduction_items = []
        for item in missing_points:
            deduction_items.append({"type": "missing_key_point", "item": item, "deduct": round(point_unit * 0.35, 2) if point_unit else 8.0})
        for item in red_flags:
            deduction_items.append({"type": "risk_signal", "item": item, "deduct": 8.0})
        total_deduction = round(sum(float(x.get("deduct") or 0.0) for x in deduction_items), 2)

        rubric_eval = layer2_payload.get("rubric_eval") if isinstance(layer2_payload.get("rubric_eval"), dict) else {}
        base_conf = self._clamp_unit((text_payload.get("confidence") if text_payload else None) or rubric_eval.get("confidence", 0.55), default=0.55)
        coverage_ratio = self._safe_float(((layer1_result or {}).get("key_points") or {}).get("coverage_ratio"))
        if coverage_ratio is None:
            coverage_ratio = (len(covered_points) / total_points) if total_points > 0 else 0.5
        evidence_chain = self._build_dimension_evidence_chain(
            layer2_payload,
            fallback_answer=self._sanitize_text((payload or {}).get("answer")),
        )
        evidence_density = min(1.0, (len(evidence_chain) / max(1, len(dimension_scores))))
        evidence_correction = self._compute_content_evidence_correction(
            llm_score=llm_score,
            coverage_ratio=float(coverage_ratio),
            rubric_match=(layer1_result or {}).get("rubric_match"),
            evidence_density=evidence_density,
            missing_points=missing_points,
            red_flags=red_flags,
        )
        blended_score = self._clamp_score(evidence_correction.get("corrected_score", llm_score))
        confidence_breakdown = self._compute_text_axis_confidence(
            payload=payload,
            dimension_scores=dimension_scores,
            base_conf=base_conf,
            coverage_ratio=float(coverage_ratio),
            evidence_density=evidence_density,
            rubric_match=(layer1_result or {}).get("rubric_match"),
        )
        confidence = self._clamp_unit(confidence_breakdown.get("overall_confidence"), default=0.0)
        evidence_service = self.text_evidence_service.build(
            layer1_result=layer1_result or {},
            layer2_result=layer2_payload,
            confidence=confidence,
        )

        checklist_items = []
        for item in covered_points:
            checklist_items.append({"point": item, "status": "hit", "score": round(point_unit, 2) if point_unit else 0.0})
        for item in missing_points:
            checklist_items.append({"point": item, "status": "miss", "score": 0.0})

        return {
            "status": "ready",
            "overall_score": blended_score,
            "confidence": confidence,
            "dimension_scores": dimension_scores,
            "rubric_eval": rubric_eval,
            "checklist": {
                "total": int(total_points),
                "hit": int(len(covered_points)),
                "score": round(checklist_score, 2),
                "items": checklist_items[:16],
            },
            "deductions": deduction_items[:12],
            "evidence_chain": evidence_chain[:28],
            "summary": {
                "llm_text_score": llm_score,
                "checklist_score": round(checklist_score, 2),
                "deduction_score": total_deduction,
                "evidence_correction": evidence_correction,
                "coverage_ratio": round(float(coverage_ratio), 4),
            },
            "confidence_breakdown": confidence_breakdown,
            "evidence_service": evidence_service,
            "axis": "content",
            "source": "content_axis",
        }

    def _build_integrity_layer(self, payload: Dict[str, Any], video_layer: Dict[str, Any]) -> Dict[str, Any]:
        video_context = dict((payload or {}).get("video_context") or (payload or {}).get("detection_state") or {})
        if not video_context:
            return {
                "status": "unavailable",
                "risk_level": "unknown",
                "risk_index": None,
                "signals": [],
                "veto": False,
                "source": "integrity_axis",
            }

        raw_off_screen = self._safe_float(video_context.get("off_screen_ratio")) or 0.0
        off_screen_ratio = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen
        face_count = int(video_context.get("face_count", 1) or 1)
        has_face = bool(video_context.get("has_face", True))
        risk_score_raw = self._safe_float(video_context.get("risk_score"))
        risk_score = None
        if risk_score_raw is not None:
            risk_score = risk_score_raw if risk_score_raw > 1.0 else risk_score_raw * 100.0
            risk_score = max(0.0, min(100.0, risk_score))

        signals = []
        if face_count > 1:
            signals.append({"code": "multi_person", "severity": "critical", "score": 95.0, "evidence": {"face_count": face_count}})
        if not has_face:
            signals.append({"code": "face_missing", "severity": "high", "score": 80.0, "evidence": {"has_face": has_face}})
        if off_screen_ratio >= 35.0:
            severity = "high" if off_screen_ratio >= 50.0 else "medium"
            signals.append({"code": "gaze_off_screen_long", "severity": severity, "score": round(min(90.0, off_screen_ratio), 2), "evidence": {"off_screen_ratio": round(off_screen_ratio, 2)}})
        if risk_score is not None and risk_score >= 65.0:
            severity = "high" if risk_score >= 80.0 else "medium"
            signals.append({"code": "risk_score_alert", "severity": severity, "score": round(risk_score, 2), "evidence": {"risk_score": round(risk_score, 2)}})

        for item in list((video_layer or {}).get("integrity_signals") or []):
            code = self._sanitize_text((item or {}).get("code"))
            if not code:
                continue
            if any(code == x.get("code") for x in signals):
                continue
            signals.append({
                "code": code,
                "severity": "medium",
                "score": float((item or {}).get("deduct_score") or 10.0) * 3.0,
                "evidence": (item or {}).get("evidence") if isinstance((item or {}).get("evidence"), dict) else {},
            })

        risk_index = round(max([float(x.get("score") or 0.0) for x in signals] + [risk_score or 0.0]), 2)
        if risk_index >= 80.0:
            risk_level = "high"
        elif risk_index >= 40.0:
            risk_level = "medium"
        else:
            risk_level = "low"

        veto = any((item.get("code") in {"multi_person"} and float(item.get("score") or 0.0) >= 90.0) for item in signals)
        return {
            "status": "ready",
            "risk_level": risk_level,
            "risk_index": risk_index,
            "signals": signals,
            "veto": bool(veto),
            "source": "integrity_axis",
        }

    def _apply_shortboard_penalty(self, round_type: str, content_layer: Dict[str, Any]) -> Dict[str, Any]:
        rule = dict(self.SHORTBOARD_RULES.get(round_type, self.SHORTBOARD_RULES["technical"]))
        dimension = str(rule.get("dimension") or "technical_accuracy").strip()
        threshold = float(rule.get("threshold", 60.0))
        slope = float(rule.get("slope", 0.01))

        dim_payload = ((content_layer or {}).get("dimension_scores") or {}).get(dimension, {})
        core_score = self._safe_float((dim_payload or {}).get("score"))
        if core_score is None:
            return {
                "applied": False,
                "dimension": dimension,
                "threshold": threshold,
                "slope": slope,
                "core_score": None,
                "coefficient": 1.0,
                "reason": "missing_core_dimension",
            }

        core_score = self._clamp_score(core_score)
        if core_score >= threshold:
            return {
                "applied": False,
                "dimension": dimension,
                "threshold": threshold,
                "slope": slope,
                "core_score": core_score,
                "coefficient": 1.0,
                "reason": "core_dimension_above_threshold",
            }

        coefficient = max(self.MIN_SHORTBOARD_COEFFICIENT, 1.0 - slope * (threshold - core_score))
        coefficient = round(coefficient, 4)
        return {
            "applied": True,
            "dimension": dimension,
            "threshold": threshold,
            "slope": slope,
            "core_score": core_score,
            "coefficient": coefficient,
            "reason": "core_dimension_below_threshold",
        }

    def fuse_layer_scores(
        self,
        content_layer: Dict[str, Any],
        delivery_layer: Dict[str, Any],
        presence_layer: Dict[str, Any],
        integrity_layer: Optional[Dict[str, Any]] = None,
        round_type: str = "technical",
    ) -> Dict[str, Any]:
        axes = {
            "content": content_layer or {},
            "delivery": delivery_layer or {},
            "presence": presence_layer or {},
        }
        base_weights = dict(self.AXIS_WEIGHTS)
        available_scores = {}
        confidence_map = {}
        confidence_breakdown_map = {}
        normalized_weight_numerators = {}
        missing_axes = []
        rejection_reasons: Dict[str, list[str]] = {}

        for name, layer in axes.items():
            score = self._safe_float((layer or {}).get("overall_score"))
            breakdown = (layer or {}).get("confidence_breakdown") if isinstance((layer or {}).get("confidence_breakdown"), dict) else {}
            confidence = self._clamp_unit(
                breakdown.get("overall_confidence", (layer or {}).get("confidence")),
                default=1.0 if score is not None else 0.0,
            )

            if score is None or confidence <= 0.0:
                missing_axes.append(name)
                reasons: list[str] = []
                layer_status = str((layer or {}).get("status", "")).strip()
                if layer_status:
                    reasons.append(f"status={layer_status}")

                summary = (layer or {}).get("summary") if isinstance((layer or {}).get("summary"), dict) else {}
                summary_reason = str((summary or {}).get("reason", "")).strip()
                if summary_reason:
                    reasons.append(summary_reason)

                quality_gate = (summary or {}).get("quality_gate") if isinstance((summary or {}).get("quality_gate"), dict) else {}
                gate_reasons = [
                    str(item).strip()
                    for item in (quality_gate or {}).get("reasons", [])
                    if str(item).strip()
                ]
                reasons.extend(gate_reasons)

                if not reasons:
                    reasons.append("missing_or_low_confidence")
                rejection_reasons[name] = reasons
                continue
            available_scores[name] = self._clamp_score(score)
            confidence_map[name] = confidence
            confidence_breakdown_map[name] = breakdown
            normalized_weight_numerators[name] = round(float(base_weights.get(name, 0.0)) * confidence, 6)

        if not available_scores:
            return {
                "status": "unavailable",
                "overall_score": None,
                "axis_scores": {},
                "axis_confidences": {},
                "axis_confidence_breakdowns": {},
                "base_weights": base_weights,
                "effective_weights": {},
                "missing_layers": ["text", "speech", "video"],
                "missing_axes": missing_axes,
                "rejection_reasons": rejection_reasons,
                "weight_normalization": {
                    "sum_before": 0.0,
                    "sum_after": 0.0,
                },
                "calculation_steps": [],
                "formula": "weighted_mean(available_axes_scores)",
                "integrity": integrity_layer or {},
            }

        weight_sum_before = round(sum(normalized_weight_numerators.values()), 6)
        if weight_sum_before <= 0:
            uniform = round(1.0 / len(available_scores), 4)
            effective_weights = {name: uniform for name in available_scores.keys()}
        else:
            effective_weights = {
                name: round(normalized_weight_numerators.get(name, 0.0) / weight_sum_before, 4)
                for name in available_scores.keys()
            }
        weight_sum_after = round(sum(effective_weights.values()), 4)

        calculation_steps = []
        for name in available_scores.keys():
            component = round(available_scores[name] * effective_weights.get(name, 0.0), 2)
            calculation_steps.append(
                f"{name}: {available_scores[name]:.2f} * {effective_weights.get(name, 0.0):.4f} = {component:.2f}"
            )

        pre_penalty_score = round(
            sum(available_scores[name] * effective_weights.get(name, 0.0) for name in available_scores.keys()),
            2,
        )
        shortboard = self._apply_shortboard_penalty(round_type=round_type, content_layer=content_layer or {})
        overall_score = round(pre_penalty_score * float(shortboard.get("coefficient", 1.0)), 2)

        layer_alias_scores = {
            "text": available_scores.get("content"),
            "speech": available_scores.get("delivery"),
            "video": available_scores.get("presence"),
        }
        layer_alias_weights = {
            "text": effective_weights.get("content", 0.0),
            "speech": effective_weights.get("delivery", 0.0),
            "video": effective_weights.get("presence", 0.0),
        }
        missing_layers = [
            layer_name for layer_name, axis_name in {
                "text": "content",
                "speech": "delivery",
                "video": "presence",
            }.items()
            if axis_name in missing_axes
        ]

        integrity_payload = dict(integrity_layer or {})
        integrity_veto = bool(integrity_payload.get("veto"))
        status = "risk_flagged" if integrity_veto else "ready"

        calculation_steps.append(
            f"shortboard_penalty: {pre_penalty_score:.2f} * {float(shortboard.get('coefficient', 1.0)):.4f} = {overall_score:.2f}"
        )
        overall_confidence = round(
            sum(confidence_map.get(name, 0.0) * effective_weights.get(name, 0.0) for name in available_scores.keys()),
            4,
        )

        return {
            "status": status,
            "overall_score": overall_score,
            "overall_score_before_shortboard": pre_penalty_score,
            "overall_confidence": overall_confidence,
            "axis_scores": available_scores,
            "axis_confidences": confidence_map,
            "axis_confidence_breakdowns": confidence_breakdown_map,
            "layer_scores": layer_alias_scores,
            "base_weights": base_weights,
            "base_weights_layers": dict(self.LAYER_WEIGHTS),
            "effective_weights": effective_weights,
            "effective_weights_layers": layer_alias_weights,
            "missing_layers": missing_layers,
            "missing_axes": missing_axes,
            "rejection_reasons": rejection_reasons,
            "weight_normalization": {
                "sum_before": weight_sum_before,
                "sum_after": weight_sum_after,
            },
            "calculation_steps": calculation_steps,
            "formula": "W_effective_i = (W_base_i * C_i) / sum(W_base_j * C_j)",
            "shortboard_penalty": shortboard,
            "integrity": {
                "risk_level": integrity_payload.get("risk_level"),
                "risk_index": integrity_payload.get("risk_index"),
                "signals": integrity_payload.get("signals") or [],
                "veto": integrity_veto,
            },
        }

    def build_evaluation_v2(
        self,
        text_layer: Dict[str, Any],
        speech_layer: Dict[str, Any],
        video_layer: Dict[str, Any],
        layer1_result: Optional[Dict[str, Any]] = None,
        layer2_result: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        content_axis = self._build_content_layer(
            layer1_result=layer1_result,
            layer2_result=layer2_result,
            text_layer=text_layer,
            payload=payload,
        )
        delivery_axis = dict(speech_layer or {})
        delivery_axis.setdefault("axis", "delivery")
        presence_axis = dict(video_layer or {})
        presence_axis.setdefault("axis", "presence")
        integrity_axis = self._build_integrity_layer(payload or {}, presence_axis)

        round_type = str((payload or {}).get("round_type", "technical") or "technical").strip() or "technical"
        fusion = self.fuse_layer_scores(
            content_layer=content_axis,
            delivery_layer=delivery_axis,
            presence_layer=presence_axis,
            integrity_layer=integrity_axis,
            round_type=round_type,
        )

        return {
            "schema_version": self.EVALUATION_SCHEMA_VERSION,
            "architecture": self.EVALUATION_ARCHITECTURE,
            "layers": {
                "text": text_layer or {},
                "speech": speech_layer or {},
                "video": video_layer or {},
            },
            "axes": {
                "content": content_axis,
                "delivery": delivery_axis,
                "presence": presence_axis,
                "integrity": integrity_axis,
            },
            "fusion": fusion,
        }

    def _build_task_key(self, interview_id: str, turn_id: str, evaluation_version: str) -> str:
        raw = f"{interview_id}|{turn_id}|{evaluation_version}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _get_existing_record(
        self,
        interview_id: str,
        turn_id: str,
        evaluation_version: str
    ) -> Optional[Dict[str, Any]]:
        if hasattr(self.db_manager, "get_evaluation_record"):
            return self.db_manager.get_evaluation_record(
                interview_id=interview_id,
                turn_id=turn_id,
                evaluation_version=evaluation_version,
            )

        # 兼容旧 DB 管理器接口
        rows = self.db_manager.get_interview_evaluations(
            interview_id=interview_id,
            evaluation_version=evaluation_version,
        )
        for row in rows or []:
            if str(row.get("turn_id", "")).strip() == str(turn_id).strip():
                return row
        return None

    def _default_record(self, payload: Dict[str, Any], status: str) -> Dict[str, Any]:
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "interview_id": payload.get("interview_id", ""),
            "turn_id": payload.get("turn_id", ""),
            "question_id": payload.get("question_id", ""),
            "user_id": payload.get("user_id", "default"),
            "round_type": payload.get("round_type", "technical"),
            "position": payload.get("position", ""),
            "question": payload.get("question", ""),
            "answer": payload.get("answer", ""),
            "evaluation_version": payload.get("evaluation_version", self.evaluation_version),
            "rubric_version": payload.get("rubric_version", "unknown"),
            "prompt_version": payload.get("prompt_version", self.prompt_version),
            "llm_model": payload.get("llm_model", ""),
            "eval_task_key": payload.get("eval_task_key", ""),
            "status": status,
            "layer1_json": self._json_dumps(payload.get("layer1_json", {})),
            "layer2_json": self._json_dumps(payload.get("layer2_json", {})),
            "text_layer_json": self._json_dumps(payload.get("text_layer_json", {})),
            "speech_layer_json": self._json_dumps(payload.get("speech_layer_json", {})),
            "video_layer_json": self._json_dumps(payload.get("video_layer_json", {})),
            "fusion_json": self._json_dumps(payload.get("fusion_json", {})),
            "scoring_snapshot_json": self._json_dumps(payload.get("scoring_snapshot_json", {})),
            "rubric_level": payload.get("rubric_level"),
            "overall_score": self._safe_float(payload.get("overall_score")),
            "confidence": self._safe_float(payload.get("confidence")),
            "technical_accuracy_score": self._safe_float(payload.get("technical_accuracy_score")),
            "knowledge_depth_score": self._safe_float(payload.get("knowledge_depth_score")),
            "completeness_score": self._safe_float(payload.get("completeness_score")),
            "logic_score": self._safe_float(payload.get("logic_score")),
            "job_match_score": self._safe_float(payload.get("job_match_score")),
            "authenticity_score": self._safe_float(payload.get("authenticity_score")),
            "ownership_score": self._safe_float(payload.get("ownership_score")),
            "technical_depth_score": self._safe_float(payload.get("technical_depth_score")),
            "reflection_score": self._safe_float(payload.get("reflection_score")),
            "architecture_reasoning_score": self._safe_float(payload.get("architecture_reasoning_score")),
            "tradeoff_awareness_score": self._safe_float(payload.get("tradeoff_awareness_score")),
            "scalability_score": self._safe_float(payload.get("scalability_score")),
            "clarity_score": self._safe_float(payload.get("clarity_score")),
            "relevance_score": self._safe_float(payload.get("relevance_score")),
            "self_awareness_score": self._safe_float(payload.get("self_awareness_score")),
            "communication_score": self._safe_float(payload.get("communication_score")),
            "confidence_score": self._safe_float(payload.get("confidence_score")),
            "gaze_focus_score": self._safe_float(payload.get("gaze_focus_score")),
            "posture_compliance_score": self._safe_float(payload.get("posture_compliance_score")),
            "physiology_stability_score": self._safe_float(payload.get("physiology_stability_score")),
            "expression_naturalness_score": self._safe_float(payload.get("expression_naturalness_score")),
            "engagement_level_score": self._safe_float(payload.get("engagement_level_score")),
            "retry_count_layer1": int(payload.get("retry_count_layer1", 0) or 0),
            "retry_count_layer2": int(payload.get("retry_count_layer2", 0) or 0),
            "retry_count_persist": int(payload.get("retry_count_persist", 0) or 0),
            "error_code": payload.get("error_code", ""),
            "error_message": payload.get("error_message", ""),
            "created_at": payload.get("created_at", now),
            "updated_at": payload.get("updated_at", now),
        }

    def save_or_update_evaluation(self, record: Dict[str, Any]) -> Dict[str, Any]:
        return self.db_manager.save_or_update_evaluation(self._default_record(record, record.get("status", self.STATUS_PENDING)))

    def _retry(
        self,
        fn,
        max_retries: int,
        error_prefix: str,
    ) -> Tuple[Optional[Any], int, Optional[str], Optional[str]]:
        attempt = 0
        last_error = None
        while attempt <= max_retries:
            try:
                result = fn()
                return result, attempt, None, None
            except Exception as e:  # pragma: no cover - runtime resilience
                last_error = e
                attempt += 1
                if attempt <= max_retries:
                    time.sleep(self.retry_backoff * attempt)
        return None, max_retries, f"{error_prefix}_RETRY_EXHAUSTED", str(last_error or "unknown error")

    def evaluate_layer1(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if self.rag_service is None or not getattr(self.rag_service, "enabled", False):
            return {
                "status": self.STATUS_SKIPPED,
                "error_code": "RAG_NOT_READY",
                "message": "RAG 未启用，跳过第一层评估",
            }
        if not hasattr(self.rag_service, "evaluate_layer1"):
            return {
                "status": self.STATUS_SKIPPED,
                "error_code": "RAG_LAYER1_UNSUPPORTED",
                "message": "RAG 不支持 evaluate_layer1",
            }
        return self.rag_service.evaluate_layer1(
            question_id=payload.get("question_id", ""),
            candidate_answer=payload.get("answer", ""),
            current_question=payload.get("question", ""),
            position=payload.get("position", ""),
            round_type=payload.get("round_type", ""),
            semantic_threshold=self.semantic_threshold,
        )

    def evaluate_layer2(self, payload: Dict[str, Any], layer1_result: Dict[str, Any]) -> Dict[str, Any]:
        if self.llm_manager is None or not getattr(self.llm_manager, "enabled", False):
            return {
                "error": "LLM_NOT_READY",
                "message": "LLM 未启用，跳过第二层评估",
            }
        if not hasattr(self.llm_manager, "evaluate_answer_with_rubric"):
            return {
                "error": "LLM_LAYER2_UNSUPPORTED",
                "message": "LLM 不支持 evaluate_answer_with_rubric",
            }

        scoring_rubric = (
            (layer1_result or {}).get("scoring_rubric")
            or (layer1_result or {}).get("rubric_match_source")
            or {}
        )
        if not scoring_rubric:
            scoring_rubric = payload.get("scoring_rubric", {})

        atomic_points = self.build_atomic_rubric_points(
            scoring_rubric=scoring_rubric,
            layer1_result=layer1_result,
            round_type=str(payload.get("round_type", "technical") or "technical").strip() or "technical",
        )
        augmented_rubric = dict(scoring_rubric or {}) if isinstance(scoring_rubric, dict) else {}
        if atomic_points:
            augmented_rubric["atomic_points"] = atomic_points

        speech_context = self.build_speech_context(payload)
        video_context = self.evaluate_video_layer(payload)

        layer2_result = self.llm_manager.evaluate_answer_with_rubric(
            user_answer=payload.get("answer", ""),
            question=payload.get("question", ""),
            position=payload.get("position", ""),
            round_type=payload.get("round_type", "technical"),
            scoring_rubric=augmented_rubric,
            layer1_result=layer1_result,
            prompt_version=payload.get("prompt_version", self.prompt_version),
            speech_context=speech_context if speech_context.get("speech_used") else {},
        )
        if layer2_result.get("error"):
            return layer2_result

        if atomic_points:
            layer2_result.setdefault("atomic_rubric_points", atomic_points)
            layer2_result = self._apply_atomic_rubric_rules(
                layer2_result=layer2_result,
                atomic_points=atomic_points,
                round_type=str(payload.get("round_type", "technical") or "technical").strip() or "technical",
                answer_text=str(payload.get("answer", "") or ""),
            )

        return self.fuse_speech_with_dimension_scores(
            round_type=payload.get("round_type", "technical"),
            layer2_result=layer2_result,
            speech_context=speech_context,
            video_context=video_context,
        )

    def _derive_rubric_level(self, layer1_result: Dict[str, Any], layer2_result: Dict[str, Any]) -> Optional[str]:
        rubric_eval = (layer2_result or {}).get("rubric_eval", {}) or {}
        final_level = str(rubric_eval.get("final_level", "")).strip().lower()
        if final_level in {"basic", "good", "excellent"}:
            return final_level
        rubric_match = (layer1_result or {}).get("rubric_match", {}) or {}
        if not rubric_match:
            return None
        ranked = sorted(rubric_match.items(), key=lambda item: float(item[1] or 0), reverse=True)
        return ranked[0][0] if ranked else None

    def _extract_dimension_columns(
        self,
        round_type: str,
        layer2_result: Dict[str, Any],
        video_layer_result: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Optional[float]]:
        dimension_scores = (
            (layer2_result or {}).get("final_dimension_scores")
            or (layer2_result or {}).get("dimension_scores")
            or {}
        )
        columns = {
            "technical_accuracy_score": None,
            "knowledge_depth_score": None,
            "completeness_score": None,
            "logic_score": None,
            "job_match_score": None,
            "authenticity_score": None,
            "ownership_score": None,
            "technical_depth_score": None,
            "reflection_score": None,
            "architecture_reasoning_score": None,
            "tradeoff_awareness_score": None,
            "scalability_score": None,
            "clarity_score": None,
            "relevance_score": None,
            "self_awareness_score": None,
            "communication_score": None,
            "confidence_score": None,
            "gaze_focus_score": None,
            "posture_compliance_score": None,
            "physiology_stability_score": None,
            "expression_naturalness_score": None,
            "engagement_level_score": None,
        }
        used_dims = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        for dim in used_dims:
            payload = dimension_scores.get(dim, {}) or {}
            key = f"{dim}_score"
            if key in columns:
                columns[key] = self._safe_float(payload.get("score"))

        video_dimension_scores = (video_layer_result or {}).get("dimension_scores") if isinstance((video_layer_result or {}).get("dimension_scores"), dict) else {}
        video_dimensions = [
            "gaze_focus", "posture_compliance", "physiology_stability",
            "expression_naturalness", "engagement_level"
        ]
        for dim in video_dimensions:
            key = f"{dim}_score"
            if key in columns:
                video_payload = video_dimension_scores.get(dim, {}) or {}
                columns[key] = self._safe_float(video_payload.get("score"))

        return columns

    def _estimate_fallback_score(self, answer: str) -> float:
        text = str(answer or "").strip()
        if not text:
            return 25.0
        units = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))
        punct = len(re.findall(r"[。！？.!?；;，,]", text))
        score = 30.0 + min(45.0, float(units) * 1.1) + min(8.0, float(punct) * 1.2)
        # 回退评分只用于 LLM/RAG 异常时保持报告可用，不能给出优秀档语义结论。
        return round(max(20.0, min(70.0, score)), 1)

    def _build_partial_layer2_from_layer1(
        self,
        layer1_result: Dict[str, Any],
        reason: str,
        payload: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        rubric_match = (layer1_result or {}).get("rubric_match", {}) or {}
        best_level = None
        confidence = 0.45
        if rubric_match:
            ranked = sorted(rubric_match.items(), key=lambda item: float(item[1] or 0), reverse=True)
            if ranked:
                best_level = ranked[0][0]
                confidence = min(0.75, max(0.2, float(ranked[0][1] or 0.0)))

        rubric_score = float(rubric_match.get("good", 0.0) or 0.0) * 100.0
        round_type = str((payload or {}).get("round_type") or "technical").strip() or "technical"
        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        heuristic_score = self._estimate_fallback_score((payload or {}).get("answer", ""))
        overall_score = round(rubric_score if rubric_score > 0 else heuristic_score, 1)

        dimension_scores = {
            dim: {
                "score": overall_score,
                "reason": "基于回答文本长度与结构的回退评分。",
            }
            for dim in dimensions
        }

        return {
            "evaluation_mode": "heuristic_text_fallback",
            "fallback_reason": reason,
            "rubric_eval": {
                "basic_match": float(rubric_match.get("basic", 0.0) or 0.0) * 100.0,
                "good_match": float(rubric_match.get("good", 0.0) or 0.0) * 100.0,
                "excellent_match": float(rubric_match.get("excellent", 0.0) or 0.0) * 100.0,
                "final_level": best_level or "basic",
                "confidence": round(confidence, 4),
                "reason": reason,
            },
            "dimension_scores": dimension_scores,
            "text_base_dimension_scores": dimension_scores,
            "speech_context": {},
            "speech_adjustments": {dim: 0.0 for dim in dimensions},
            "final_dimension_scores": dimension_scores,
            "overall_score_base": overall_score,
            "overall_score_final": overall_score,
            "overall_score": overall_score,
            "speech_used": False,
            "speech_fusion_version": self.SPEECH_FUSION_VERSION,
            "summary": {
                "strengths": [],
                "weaknesses": [],
                "next_actions": []
            }
        }

    def enqueue_evaluation(
        self,
        interview_id: str,
        turn_id: str,
        question_id: str,
        user_id: str,
        round_type: str,
        position: str,
        question: str,
        answer: str,
        evaluation_version: Optional[str] = None,
        detection_state: Optional[Dict[str, Any]] = None,
        video_context: Optional[Dict[str, Any]] = None,
        force: bool = False,
    ) -> Dict[str, Any]:
        interview_id = str(interview_id or "").strip()
        turn_id = str(turn_id or "").strip()
        if not interview_id or not turn_id:
            return {"success": False, "error": "MISSING_ID", "message": "interview_id 或 turn_id 为空"}

        current_evaluation_version = str(evaluation_version or self.evaluation_version).strip() or self.evaluation_version
        payload = {
            "interview_id": interview_id,
            "turn_id": turn_id,
            "question_id": str(question_id or "").strip(),
            "user_id": str(user_id or "default").strip() or "default",
            "round_type": str(round_type or "technical").strip() or "technical",
            "position": str(position or "").strip(),
            "question": str(question or "").strip(),
            "answer": str(answer or "").strip(),
            "evaluation_version": current_evaluation_version,
            "prompt_version": self.prompt_version,
            "llm_model": str(getattr(self.llm_manager, "model", "") or "").strip(),
            "rubric_version": "unknown",
            "detection_state": detection_state or {},
            "video_context": video_context or {},
        }
        payload["eval_task_key"] = self._build_task_key(
            payload["interview_id"],
            payload["turn_id"],
            payload["evaluation_version"]
        )
        payload["scoring_snapshot_json"] = self.build_scoring_snapshot(payload)

        with self._inflight_lock:
            if payload["eval_task_key"] in self._inflight_task_keys:
                return {
                    "success": True,
                    "enqueued": False,
                    "reason": "already_inflight",
                    "eval_task_key": payload["eval_task_key"],
                }

            existing = self._get_existing_record(
                interview_id=payload["interview_id"],
                turn_id=payload["turn_id"],
                evaluation_version=payload["evaluation_version"],
            )
            if existing is not None and not force:
                return {
                    "success": True,
                    "enqueued": False,
                    "reason": "already_exists",
                    "status": str(existing.get("status", "")).strip(),
                    "eval_task_key": payload["eval_task_key"],
                }

            self._inflight_task_keys.add(payload["eval_task_key"])

        pending_record = self._default_record(payload, self.STATUS_PENDING)
        persist_pending_result, pending_retries, pending_error_code, pending_error_message = self._retry(
            lambda: self.db_manager.save_or_update_evaluation(pending_record),
            max_retries=self.retry_persist,
            error_prefix="PERSIST_PENDING",
        )
        if pending_error_code or not persist_pending_result or not persist_pending_result.get("success"):
            with self._inflight_lock:
                self._inflight_task_keys.discard(payload["eval_task_key"])
            return {
                "success": False,
                "error": pending_error_code or "PERSIST_PENDING_FAILED",
                "message": pending_error_message or str((persist_pending_result or {}).get("error", "")),
                "retry_count_persist": pending_retries,
            }
        payload["retry_count_persist"] = int(pending_retries or 0)

        self._log_trace(
            payload,
            event_type="task_enqueued",
            status=self.STATUS_PENDING,
            extra={
                "evaluation_version": payload.get("evaluation_version", ""),
                "prompt_version": payload.get("prompt_version", ""),
                "retry_count_persist": payload.get("retry_count_persist", 0),
            },
        )

        self.executor.submit(self._run_evaluation_task, payload)
        return {
            "success": True,
            "enqueued": True,
            "eval_task_key": payload["eval_task_key"],
        }

    def _run_evaluation_task(self, payload: Dict[str, Any]) -> None:
        task_started = time.perf_counter()
        retry_count_layer1 = 0
        retry_count_layer2 = 0
        retry_count_persist = int(payload.get("retry_count_persist", 0) or 0)
        final_status = self.STATUS_FAILED
        final_error_code = ""
        final_error_message = ""
        layer1_result: Dict[str, Any] = {}
        layer2_result: Dict[str, Any] = {}
        text_layer_result: Dict[str, Any] = {}
        speech_layer_result: Dict[str, Any] = {}
        video_layer_result: Dict[str, Any] = {}
        evaluation_v2: Dict[str, Any] = {}

        try:
            self._log_trace(
                payload,
                event_type="task_running",
                status=self.STATUS_RUNNING,
                extra={
                    "evaluation_version": payload.get("evaluation_version", ""),
                },
            )

            running_started = time.perf_counter()
            running_record = self._default_record(payload, self.STATUS_RUNNING)
            persist_running_result, running_retries, running_error_code, running_error_message = self._retry(
                lambda: self.db_manager.save_or_update_evaluation(running_record),
                max_retries=self.retry_persist,
                error_prefix="PERSIST_RUNNING",
            )
            running_duration_ms = round((time.perf_counter() - running_started) * 1000.0, 2)
            retry_count_persist += running_retries
            if running_error_code or not persist_running_result or not persist_running_result.get("success"):
                final_status = self.STATUS_FAILED
                final_error_code = running_error_code or "PERSIST_RUNNING_FAILED"
                final_error_message = running_error_message or str((persist_running_result or {}).get("error", ""))
                self._log_trace(
                    payload,
                    event_type="persist_running_done",
                    status=final_status,
                    duration_ms=running_duration_ms,
                    extra={
                        "retry_count_persist": retry_count_persist,
                        "error_code": final_error_code,
                        "error_message": final_error_message,
                    },
                )
                return

            self._log_trace(
                payload,
                event_type="persist_running_done",
                status=self.STATUS_OK,
                duration_ms=running_duration_ms,
                extra={
                    "retry_count_persist": retry_count_persist,
                },
            )

            layer1_started = time.perf_counter()
            layer1_result, retry_count_layer1, layer1_error_code, layer1_error_message = self._retry(
                lambda: self.evaluate_layer1(payload),
                max_retries=self.retry_layer1,
                error_prefix="LAYER1",
            )
            layer1_duration_ms = round((time.perf_counter() - layer1_started) * 1000.0, 2)
            if layer1_error_code or layer1_result is None:
                final_status = self.STATUS_FAILED
                final_error_code = layer1_error_code or "LAYER1_FAILED"
                final_error_message = layer1_error_message or "第一层评估失败"
                self._log_trace(
                    payload,
                    event_type="layer1_done",
                    status=final_status,
                    duration_ms=layer1_duration_ms,
                    extra={
                        "retry_count_layer1": retry_count_layer1,
                        "error_code": final_error_code,
                        "error_message": final_error_message,
                    },
                )
                return

            self._log_trace(
                payload,
                event_type="layer1_done",
                status=str((layer1_result or {}).get("status", self.STATUS_OK)).strip() or self.STATUS_OK,
                duration_ms=layer1_duration_ms,
                extra={
                    "retry_count_layer1": retry_count_layer1,
                    "error_code": str((layer1_result or {}).get("error_code", "") or ""),
                },
            )

            layer2_started = time.perf_counter()
            if layer1_result.get("status") == self.STATUS_SKIPPED:
                payload["rubric_version"] = str(layer1_result.get("rubric_version", "fallback_unknown") or "fallback_unknown")
                layer2_result, retry_count_layer2, layer2_error_code, layer2_error_message = self._retry(
                    lambda: self.evaluate_layer2(payload, layer1_result),
                    max_retries=self.retry_layer2,
                    error_prefix="LAYER2_FALLBACK",
                )
                if layer2_error_code or layer2_result is None or layer2_result.get("error"):
                    layer2_result = self._build_partial_layer2_from_layer1(
                        layer1_result,
                        "第一层未命中可用 rubric，回退评分失败，已使用启发式文本评分",
                        payload=payload,
                    )
                    final_status = self.STATUS_PARTIAL_OK
                    final_error_code = layer2_error_code or str((layer2_result or {}).get("error", "")) or "LAYER2_FALLBACK_FAILED"
                    final_error_message = layer2_error_message or str((layer2_result or {}).get("message", "")) or "第二层回退评估失败"
                else:
                    fallback_reason = str((layer1_result or {}).get("error_code") or "RUBRIC_NOT_FOUND")
                    layer2_result["evaluation_mode"] = "layer2_without_layer1_rubric"
                    layer2_result["evaluation_note"] = f"layer1 skipped: {fallback_reason}"
                    final_status = self.STATUS_PARTIAL_OK
            else:
                payload["rubric_version"] = str(layer1_result.get("rubric_version", "unknown") or "unknown")
                layer2_result, retry_count_layer2, layer2_error_code, layer2_error_message = self._retry(
                    lambda: self.evaluate_layer2(payload, layer1_result),
                    max_retries=self.retry_layer2,
                    error_prefix="LAYER2",
                )
                if layer2_error_code or layer2_result is None or layer2_result.get("error"):
                    reason = layer2_error_message or str((layer2_result or {}).get("message", "")) or "第二层评估失败"
                    layer2_result = self._build_partial_layer2_from_layer1(layer1_result, reason, payload=payload)
                    final_status = self.STATUS_PARTIAL_OK
                    final_error_code = layer2_error_code or str((layer2_result or {}).get("error", "")) or "LAYER2_FAILED"
                    final_error_message = reason
                else:
                    final_status = self.STATUS_OK

            layer2_duration_ms = round((time.perf_counter() - layer2_started) * 1000.0, 2)
            self._log_trace(
                payload,
                event_type="layer2_done",
                status=final_status,
                duration_ms=layer2_duration_ms,
                extra={
                    "retry_count_layer2": retry_count_layer2,
                    "error_code": final_error_code,
                    "error_message": final_error_message,
                },
            )

        except Exception as e:  # pragma: no cover - runtime resilience
            final_status = self.STATUS_FAILED
            final_error_code = "EVALUATION_TASK_EXCEPTION"
            final_error_message = str(e)
            self.logger.error(f"评估任务异常: {e}", exc_info=True)
        finally:
            dim_source = (
                (layer2_result or {}).get("final_dimension_scores")
                or (layer2_result or {}).get("dimension_scores")
                or {}
            )
            if dim_source:
                layer2_result["dimension_evidence_json"] = self._normalize_dimension_evidence(dim_source)

            speech_started = time.perf_counter()
            text_layer_result = self.build_text_layer_result(layer2_result or {})
            speech_layer_result = self.evaluate_speech_layer(payload)
            speech_duration_ms = round((time.perf_counter() - speech_started) * 1000.0, 2)
            self._log_trace(
                payload,
                event_type="speech_layer_done",
                status=str((speech_layer_result or {}).get("status", "")).strip() or "unknown",
                duration_ms=speech_duration_ms,
                extra={
                    "overall_score": (speech_layer_result or {}).get("overall_score"),
                },
            )

            video_started = time.perf_counter()
            video_layer_result = self.evaluate_video_layer(payload)
            video_duration_ms = round((time.perf_counter() - video_started) * 1000.0, 2)
            self._log_trace(
                payload,
                event_type="video_layer_done",
                status=str((video_layer_result or {}).get("status", "")).strip() or "unknown",
                duration_ms=video_duration_ms,
                extra={
                    "overall_score": (video_layer_result or {}).get("overall_score"),
                },
            )

            fusion_started = time.perf_counter()
            evaluation_v2 = self.build_evaluation_v2(
                text_layer=text_layer_result,
                speech_layer=speech_layer_result,
                video_layer=video_layer_result,
                layer1_result=layer1_result,
                layer2_result=layer2_result,
                payload=payload,
            )
            fusion_duration_ms = round((time.perf_counter() - fusion_started) * 1000.0, 2)
            self._log_trace(
                payload,
                event_type="fusion_done",
                status=str(((evaluation_v2.get("fusion") or {}).get("status", "")).strip() or "unknown"),
                duration_ms=fusion_duration_ms,
                extra={
                    "overall_score": (evaluation_v2.get("fusion") or {}).get("overall_score"),
                    "missing_layers": list((evaluation_v2.get("fusion") or {}).get("missing_layers") or []),
                },
            )

            fusion_score = self._safe_float((evaluation_v2.get("fusion") or {}).get("overall_score"))
            fusion_confidence = self._safe_float((evaluation_v2.get("fusion") or {}).get("overall_confidence"))

            persisted_layer2 = dict(layer2_result or {})
            persisted_speech_context = dict((persisted_layer2.get("speech_context") or {}))
            if "word_timestamps" in persisted_speech_context:
                persisted_speech_context["word_timestamps_count"] = len(persisted_speech_context.get("word_timestamps") or [])
                persisted_speech_context.pop("word_timestamps", None)
            if persisted_speech_context:
                persisted_layer2["speech_context"] = persisted_speech_context

            persisted_fusion = dict(evaluation_v2.get("fusion") or {})
            persisted_fusion["schema_version"] = evaluation_v2.get("schema_version")
            persisted_fusion["architecture"] = evaluation_v2.get("architecture")
            persisted_fusion["axes"] = {
                "content": (evaluation_v2.get("axes") or {}).get("content", {}),
                "delivery": (evaluation_v2.get("axes") or {}).get("delivery", {}),
                "presence": (evaluation_v2.get("axes") or {}).get("presence", {}),
                "integrity": (evaluation_v2.get("axes") or {}).get("integrity", {}),
            }

            rubric_eval = (layer2_result or {}).get("rubric_eval", {}) or {}
            dimension_columns = self._extract_dimension_columns(
                payload.get("round_type", "technical"),
                layer2_result or {},
                video_layer_result=video_layer_result,
            )
            final_record = self._default_record(
                {
                    **payload,
                    "rubric_version": payload.get("rubric_version", "unknown"),
                    "status": final_status,
                    "layer1_json": layer1_result or {},
                    "layer2_json": persisted_layer2,
                    "text_layer_json": text_layer_result or {},
                    "speech_layer_json": speech_layer_result or {},
                    "video_layer_json": video_layer_result or {},
                    "fusion_json": persisted_fusion,
                    "scoring_snapshot_json": payload.get("scoring_snapshot_json") or {},
                    "rubric_level": self._derive_rubric_level(layer1_result or {}, layer2_result or {}),
                    "overall_score": fusion_score if fusion_score is not None else (layer2_result or {}).get("overall_score"),
                    "confidence": fusion_confidence if fusion_confidence is not None else rubric_eval.get("confidence"),
                    "retry_count_layer1": retry_count_layer1,
                    "retry_count_layer2": retry_count_layer2,
                    "retry_count_persist": retry_count_persist,
                    "error_code": final_error_code,
                    "error_message": final_error_message,
                    **dimension_columns,
                },
                final_status
            )

            persist_final_result, final_persist_retries, persist_error_code, persist_error_message = self._retry(
                lambda: self.db_manager.save_or_update_evaluation(final_record),
                max_retries=self.retry_persist,
                error_prefix="PERSIST_FINAL",
            )
            retry_count_persist += final_persist_retries
            persist_final_status = self.STATUS_OK
            if persist_error_code or not persist_final_result or not persist_final_result.get("success"):
                persist_final_status = self.STATUS_FAILED
                self.logger.error(
                    "评估结果最终落库失败: task_key=%s error=%s message=%s",
                    payload.get("eval_task_key", ""),
                    persist_error_code or "PERSIST_FINAL_FAILED",
                    persist_error_message or str((persist_final_result or {}).get("error", "")),
                )
            elif final_persist_retries:
                # 最终落库重试次数在首次写入时未知，成功后补写总重试计数。
                final_record["retry_count_persist"] = retry_count_persist
                try:
                    self.db_manager.save_or_update_evaluation(final_record)
                except Exception:
                    pass

            self._log_trace(
                payload,
                event_type="persist_done",
                status=persist_final_status,
                extra={
                    "retry_count_persist": retry_count_persist,
                    "error_code": persist_error_code or "",
                    "error_message": persist_error_message or "",
                },
            )

            total_duration_ms = round((time.perf_counter() - task_started) * 1000.0, 2)
            self._log_trace(
                payload,
                event_type="task_finished",
                status=final_status,
                duration_ms=total_duration_ms,
                extra={
                    "error_code": final_error_code,
                    "error_message": final_error_message,
                    "retry_count_layer1": retry_count_layer1,
                    "retry_count_layer2": retry_count_layer2,
                    "retry_count_persist": retry_count_persist,
                },
            )

            with self._inflight_lock:
                self._inflight_task_keys.discard(payload.get("eval_task_key", ""))

            self._fire_completion_callbacks(payload, final_status)

    def register_completion_callback(self, callback) -> None:
        """注册评估完成回调，签名: callback(interview_id, turn_id, status)"""
        if callable(callback):
            self._completion_callbacks.append(callback)

    def _fire_completion_callbacks(self, payload: dict, status: str) -> None:
        interview_id = str(payload.get("interview_id") or "").strip()
        turn_id = str(payload.get("turn_id") or "").strip()
        for cb in self._completion_callbacks:
            try:
                cb(interview_id, turn_id, status)
            except Exception as exc:
                self.logger.warning(f"评估完成回调异常: {exc}")

    def shutdown(self) -> None:
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
