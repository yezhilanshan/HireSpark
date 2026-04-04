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
    from utils.logger import get_logger
except ImportError:  # pragma: no cover
    from backend.utils.config_loader import config
    from backend.utils.logger import get_logger


class EvaluationService:
    STATUS_PENDING = "pending"
    STATUS_RUNNING = "running"
    STATUS_OK = "ok"
    STATUS_PARTIAL_OK = "partial_ok"
    STATUS_SKIPPED = "skipped"
    STATUS_FAILED = "failed"

    ROUND_DIMENSIONS = {
        "technical": ["technical_accuracy", "knowledge_depth", "completeness", "logic", "job_match"],
        "project": ["authenticity", "ownership", "technical_depth", "reflection"],
        "system_design": ["architecture_reasoning", "tradeoff_awareness", "scalability", "logic"],
        "hr": ["clarity", "relevance", "self_awareness", "communication"],
    }
    SPEECH_GATE_MIN_AUDIO_MS = 8000.0
    SPEECH_GATE_MIN_TOKENS = 20
    SPEECH_FUSION_VERSION = "speech_fusion_v1"
    SPEECH_EXPRESSION_WEIGHTS = {
        "clarity_score": 0.30,
        "fluency_score": 0.25,
        "speech_rate_score": 0.20,
        "pause_anomaly_score": 0.15,
        "filler_frequency_score": 0.10,
    }
    SPEECH_DIMENSION_BLEND = {
        "technical": {"logic": 0.20, "completeness": 0.10},
        "project": {"reflection": 0.15},
        "system_design": {"logic": 0.20},
        "hr": {"clarity": 0.30, "communication": 0.30, "relevance": 0.10, "self_awareness": 0.10},
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
            "expression_dimensions": {
                key: self._clamp_score(value)
                for key, value in (expression_dimensions or {}).items()
                if self._safe_float(value) is not None
            },
            "expression_score": expression_score,
            "turn_id": str(payload.get("turn_id", "")).strip(),
        }

    def fuse_speech_with_dimension_scores(
        self,
        round_type: str,
        layer2_result: Dict[str, Any],
        speech_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        layer2_result = dict(layer2_result or {})
        dimensions = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        raw_dimension_scores = layer2_result.get("dimension_scores", {}) or {}

        text_base_dimension_scores = {}
        for dim in dimensions:
            payload = raw_dimension_scores.get(dim, {}) or {}
            text_base_dimension_scores[dim] = {
                "score": self._clamp_score(payload.get("score", 0.0)),
                "reason": str(payload.get("reason", "") or "").strip(),
            }

        blend_weights = self.SPEECH_DIMENSION_BLEND.get(round_type, {})
        speech_used = bool((speech_context or {}).get("speech_used"))
        expression_score = self._safe_float((speech_context or {}).get("expression_score"))
        if expression_score is None:
            speech_used = False

        speech_adjustments = {}
        final_dimension_scores = {}
        for dim in dimensions:
            base_score = float(text_base_dimension_scores[dim]["score"])
            blend_weight = float(blend_weights.get(dim, 0.0)) if speech_used else 0.0
            if blend_weight > 0.0:
                final_score = self._clamp_score(base_score * (1.0 - blend_weight) + float(expression_score) * blend_weight)
            else:
                final_score = round(base_score, 2)

            speech_adjustments[dim] = round(final_score - base_score, 2)
            final_dimension_scores[dim] = {
                "score": final_score,
                "reason": text_base_dimension_scores[dim]["reason"],
            }

        overall_score_base = round(
            sum(item["score"] for item in text_base_dimension_scores.values()) / len(text_base_dimension_scores),
            2,
        ) if text_base_dimension_scores else 0.0
        overall_score_final = round(
            sum(item["score"] for item in final_dimension_scores.values()) / len(final_dimension_scores),
            2,
        ) if final_dimension_scores else overall_score_base

        layer2_result.update({
            "text_base_dimension_scores": text_base_dimension_scores,
            "speech_context": speech_context or {},
            "speech_adjustments": speech_adjustments,
            "final_dimension_scores": final_dimension_scores,
            "overall_score_base": overall_score_base,
            "overall_score_final": overall_score_final,
            "speech_used": speech_used,
            "speech_fusion_version": self.SPEECH_FUSION_VERSION,
            "dimension_scores": final_dimension_scores,
            "overall_score": overall_score_final,
        })
        if expression_score is not None:
            layer2_result["speech_expression_score"] = round(float(expression_score), 2)
        return layer2_result

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
        # 兼容旧第一层结果：若未透出 scoring_rubric，则允许从 payload 透传。
        if not scoring_rubric:
            scoring_rubric = payload.get("scoring_rubric", {})

        speech_context = self.build_speech_context(payload)
        layer2_result = self.llm_manager.evaluate_answer_with_rubric(
            user_answer=payload.get("answer", ""),
            question=payload.get("question", ""),
            position=payload.get("position", ""),
            round_type=payload.get("round_type", "technical"),
            scoring_rubric=scoring_rubric,
            layer1_result=layer1_result,
            prompt_version=payload.get("prompt_version", self.prompt_version),
            speech_context=speech_context,
        )
        if layer2_result.get("error"):
            return layer2_result

        return self.fuse_speech_with_dimension_scores(
            round_type=payload.get("round_type", "technical"),
            layer2_result=layer2_result,
            speech_context=speech_context,
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

    def _extract_dimension_columns(self, round_type: str, layer2_result: Dict[str, Any]) -> Dict[str, Optional[float]]:
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
        }
        used_dims = self.ROUND_DIMENSIONS.get(round_type, self.ROUND_DIMENSIONS["technical"])
        for dim in used_dims:
            payload = dimension_scores.get(dim, {}) or {}
            key = f"{dim}_score"
            if key in columns:
                columns[key] = self._safe_float(payload.get("score"))
        return columns

    def _estimate_fallback_score(self, answer: str) -> float:
        text = str(answer or "").strip()
        if not text:
            return 25.0
        units = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9]+", text))
        punct = len(re.findall(r"[。！？.!?；;，,]", text))
        score = 30.0 + min(45.0, float(units) * 1.1) + min(8.0, float(punct) * 1.2)
        return round(max(20.0, min(85.0, score)), 1)

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
        }
        payload["eval_task_key"] = self._build_task_key(
            payload["interview_id"],
            payload["turn_id"],
            payload["evaluation_version"]
        )

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

        self.executor.submit(self._run_evaluation_task, payload)
        return {
            "success": True,
            "enqueued": True,
            "eval_task_key": payload["eval_task_key"],
        }

    def _run_evaluation_task(self, payload: Dict[str, Any]) -> None:
        retry_count_layer1 = 0
        retry_count_layer2 = 0
        retry_count_persist = int(payload.get("retry_count_persist", 0) or 0)
        final_status = self.STATUS_FAILED
        final_error_code = ""
        final_error_message = ""
        layer1_result: Dict[str, Any] = {}
        layer2_result: Dict[str, Any] = {}

        try:
            running_record = self._default_record(payload, self.STATUS_RUNNING)
            persist_running_result, running_retries, running_error_code, running_error_message = self._retry(
                lambda: self.db_manager.save_or_update_evaluation(running_record),
                max_retries=self.retry_persist,
                error_prefix="PERSIST_RUNNING",
            )
            retry_count_persist += running_retries
            if running_error_code or not persist_running_result or not persist_running_result.get("success"):
                final_status = self.STATUS_FAILED
                final_error_code = running_error_code or "PERSIST_RUNNING_FAILED"
                final_error_message = running_error_message or str((persist_running_result or {}).get("error", ""))
                return

            layer1_result, retry_count_layer1, layer1_error_code, layer1_error_message = self._retry(
                lambda: self.evaluate_layer1(payload),
                max_retries=self.retry_layer1,
                error_prefix="LAYER1",
            )
            if layer1_error_code or layer1_result is None:
                final_status = self.STATUS_FAILED
                final_error_code = layer1_error_code or "LAYER1_FAILED"
                final_error_message = layer1_error_message or "第一层评估失败"
                return

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

        except Exception as e:  # pragma: no cover - runtime resilience
            final_status = self.STATUS_FAILED
            final_error_code = "EVALUATION_TASK_EXCEPTION"
            final_error_message = str(e)
            self.logger.error(f"评估任务异常: {e}", exc_info=True)
        finally:
            rubric_eval = (layer2_result or {}).get("rubric_eval", {}) or {}
            dimension_columns = self._extract_dimension_columns(
                payload.get("round_type", "technical"),
                layer2_result or {}
            )
            final_record = self._default_record(
                {
                    **payload,
                    "rubric_version": payload.get("rubric_version", "unknown"),
                    "status": final_status,
                    "layer1_json": layer1_result or {},
                    "layer2_json": layer2_result or {},
                    "rubric_level": self._derive_rubric_level(layer1_result or {}, layer2_result or {}),
                    "overall_score": (layer2_result or {}).get("overall_score"),
                    "confidence": rubric_eval.get("confidence"),
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
            if persist_error_code or not persist_final_result or not persist_final_result.get("success"):
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

            with self._inflight_lock:
                self._inflight_task_keys.discard(payload.get("eval_task_key", ""))

    def shutdown(self) -> None:
        try:
            self.executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass
