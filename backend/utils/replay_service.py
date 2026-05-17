"""
面试复盘的回放分析服务。
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Any, Dict, List, Optional

from utils.config_loader import config
from utils.speech_metrics import aggregate_expression_metrics


def _safe_float(value: Any, default: float = 0.0) -> float:
    """安全地将值转换为浮点数，转换失败时返回默认值。"""
    try:
        return float(value)
    except Exception:
        return float(default)


def _safe_json_loads(value: Any, default: Any):
    """安全地解析 JSON 字符串，解析失败时返回默认值。"""
    if value in (None, ""):
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def _avg(values: List[float]) -> float:
    """计算数值列表的平均值，忽略无效值。"""
    valid = [float(item) for item in values if isinstance(item, (int, float)) and not math.isnan(float(item))]
    return (sum(valid) / len(valid)) if valid else 0.0


def _clamp(value: float, min_value: float, max_value: float) -> float:
    """将值限制在指定范围内。"""
    return max(min_value, min(max_value, float(value)))


def _count_tokens(text: str) -> int:
    """估算文本的 token 数量，中文字符和单词分别计数。"""
    content = str(text or "").strip()
    if not content:
        return 0
    count = 0
    for ch in content:
        if "\u4e00" <= ch <= "\u9fff":
            count += 1
    words = [w for w in content.replace("\n", " ").split(" ") if w.strip()]
    count += len(words)
    return max(1, count)


def _filter_content_dimensions_by_round(round_type: str, dimension_map: Dict[str, Any]) -> Dict[str, Any]:
    normalized_round = str(round_type or "").strip().lower()
    if not isinstance(dimension_map, dict):
        return {}

    filtered: Dict[str, Any] = {}
    for dim_key, dim_payload in dimension_map.items():
        if not isinstance(dim_payload, dict):
            continue
        normalized_key = str(dim_key or "").strip().lower()
        if normalized_round == "system_design" and normalized_key == "clarity":
            continue
        filtered[dim_key] = dim_payload
    return filtered


class ReplayService:
    """生成回放产物（A/B/C/D）并持久化。"""

    def __init__(self, db_manager, llm_manager=None, rag_service=None, logger=None):
        """初始化回放服务，配置 LLM 和数据库管理器。"""
        self.db_manager = db_manager
        self.llm_manager = llm_manager
        self.rag_service = rag_service
        self.logger = logger
        self.review_llm_enabled = bool(config.get("replay.llm.enabled", True))
        self.review_model = (
            str(os.environ.get("REPLAY_LLM_MODEL", "")).strip()
            or str(config.get("replay.llm.model", "gemma-4-27b-it") or "").strip()
            or "gemma-4-27b-it"
        )
        self.review_timeout = float(config.get("replay.llm.timeout", 45))
        self.review_max_turns = max(4, int(config.get("replay.llm.max_turns", 14)))
        self.review_version = str(config.get("replay.version", "v2_gemma_fallback") or "v2_gemma_fallback")

    def _decode_evaluations(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解码评估数据行，解析 JSON 字段。"""
        decoded = []
        for row in rows or []:
            item = dict(row)
            item["layer1"] = _safe_json_loads(item.get("layer1_json"), {})
            item["layer2"] = _safe_json_loads(item.get("layer2_json"), {})
            decoded.append(item)
        return decoded

    def _decode_speech_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解码语音评估数据行，解析各类 JSON 字段。"""
        decoded = []
        for row in rows or []:
            item = dict(row)
            item["word_timestamps"] = _safe_json_loads(item.get("word_timestamps_json"), [])
            item["pause_events"] = _safe_json_loads(item.get("pause_events_json"), [])
            item["filler_events"] = _safe_json_loads(item.get("filler_events_json"), [])
            item["speech_metrics_final"] = _safe_json_loads(item.get("speech_metrics_final_json"), {})
            item["realtime_metrics"] = _safe_json_loads(item.get("realtime_metrics_json"), {})
            decoded.append(item)
        return decoded

    def _build_turn_timeline(
        self,
        interview_id: str,
        dialogues: List[Dict[str, Any]],
        speech_rows: List[Dict[str, Any]],
        existing: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构建回合时间线，包含问答时间戳和延迟信息。"""
        def normalize_existing(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "interview_id": interview_id,
                "turn_id": str(row.get("turn_id") or "").strip(),
                "question_start_ms": _safe_float(row.get("question_start_ms"), 0.0),
                "question_end_ms": _safe_float(row.get("question_end_ms"), 0.0),
                "answer_start_ms": _safe_float(row.get("answer_start_ms"), 0.0),
                "answer_end_ms": _safe_float(row.get("answer_end_ms"), 0.0),
                "latency_ms": _safe_float(row.get("latency_ms"), 0.0),
                "source": row.get("source") or "runtime",
            }

        def speech_answer_duration_ms(speech_item: Optional[Dict[str, Any]]) -> float:
            if not speech_item:
                return 2200.0
            words = speech_item.get("word_timestamps") or []
            if words:
                try:
                    return max(
                        300.0,
                        _safe_float(words[-1].get("end_ms"), 0.0) - _safe_float(words[0].get("start_ms"), 0.0),
                    )
                except Exception:
                    return 2200.0
            metrics = speech_item.get("speech_metrics_final") or {}
            return max(600.0, _safe_float((metrics or {}).get("audio_duration_ms"), 2200.0))

        def merge_existing_with_estimate(existing_row: Optional[Dict[str, Any]], estimated: Dict[str, Any]) -> Dict[str, Any]:
            if not existing_row:
                return estimated

            question_start_ms = (
                _safe_float(existing_row.get("question_start_ms"), 0.0)
                if _safe_float(existing_row.get("question_end_ms"), 0.0) > 0
                else _safe_float(estimated.get("question_start_ms"), 0.0)
            )
            question_end_ms = _safe_float(existing_row.get("question_end_ms"), 0.0)
            if question_end_ms <= question_start_ms:
                question_end_ms = _safe_float(estimated.get("question_end_ms"), question_start_ms)

            answer_start_ms = _safe_float(existing_row.get("answer_start_ms"), 0.0)
            if answer_start_ms <= 0:
                latency_ms = _safe_float(existing_row.get("latency_ms"), 0.0)
                answer_start_ms = question_end_ms + latency_ms if latency_ms > 0 else _safe_float(estimated.get("answer_start_ms"), question_end_ms)

            answer_end_ms = _safe_float(existing_row.get("answer_end_ms"), 0.0)
            if answer_end_ms <= answer_start_ms:
                answer_end_ms = _safe_float(estimated.get("answer_end_ms"), answer_start_ms)
                if answer_end_ms <= answer_start_ms:
                    answer_end_ms = answer_start_ms + 600.0

            latency_ms = _safe_float(existing_row.get("latency_ms"), -1.0)
            if latency_ms <= 0 and answer_start_ms > question_end_ms:
                latency_ms = max(0.0, answer_start_ms - question_end_ms)

            return {
                "interview_id": interview_id,
                "turn_id": str(estimated.get("turn_id") or existing_row.get("turn_id") or "").strip(),
                "question_start_ms": round(question_start_ms, 2),
                "question_end_ms": round(question_end_ms, 2),
                "answer_start_ms": round(answer_start_ms, 2),
                "answer_end_ms": round(answer_end_ms, 2),
                "latency_ms": round(max(0.0, latency_ms), 2),
                "source": existing_row.get("source") or "runtime",
            }

        existing_rows = [normalize_existing(row) for row in (existing or [])]
        existing_by_turn = {
            str(row.get("turn_id") or "").strip(): row
            for row in existing_rows
            if str(row.get("turn_id") or "").strip()
        }

        if existing:
            if not dialogues:
                return existing_rows

        timeline: List[Dict[str, Any]] = []
        cursor_ms = 0.0

        speech_by_turn = {
            str(item.get("turn_id") or "").strip(): item
            for item in speech_rows
            if str(item.get("turn_id") or "").strip()
        }

        sorted_dialogues = sorted(dialogues or [], key=lambda x: str(x.get("created_at") or ""))
        fallback_turn_idx = 0

        for row in sorted_dialogues:
            fallback_turn_idx += 1
            turn_id = str(row.get("turn_id") or "").strip() or f"turn_legacy_{fallback_turn_idx}"
            question = str(row.get("question") or "").strip()

            question_start_ms = cursor_ms
            question_duration_ms = max(1200.0, _count_tokens(question) * 280.0)
            question_end_ms = question_start_ms + question_duration_ms

            speech_item = speech_by_turn.get(turn_id)
            answer_start_ms = question_end_ms + 450.0
            answer_end_ms = answer_start_ms + speech_answer_duration_ms(speech_item)

            latency_ms = max(0.0, answer_start_ms - question_end_ms)
            estimated = {
                "interview_id": interview_id,
                "turn_id": turn_id,
                "question_start_ms": round(question_start_ms, 2),
                "question_end_ms": round(question_end_ms, 2),
                "answer_start_ms": round(answer_start_ms, 2),
                "answer_end_ms": round(answer_end_ms, 2),
                "latency_ms": round(latency_ms, 2),
                "source": "heuristic_backfill",
            }
            merged = merge_existing_with_estimate(existing_by_turn.get(turn_id), estimated)
            cursor_ms = max(answer_end_ms, _safe_float(merged.get("answer_end_ms"), 0.0)) + 900.0
            timeline.append(merged)

        return sorted(timeline, key=lambda item: (_safe_float(item.get("question_start_ms"), 0.0), _safe_float(item.get("answer_start_ms"), 0.0)))

    def _build_highlight_tags(
        self,
        interview_id: str,
        evaluations: List[Dict[str, Any]],
        timeline_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构建高亮标签，标记高分、低分和转折点。"""
        score_by_turn: Dict[str, float] = {}
        coverage_by_turn: Dict[str, float] = {}
        for row in evaluations:
            turn_id = str(row.get("turn_id") or "").strip()
            if not turn_id:
                continue
            layer2 = row.get("layer2") or {}
            layer1 = row.get("layer1") or {}
            score = _safe_float(layer2.get("overall_score_final") or row.get("overall_score"), 0.0)
            score_by_turn[turn_id] = score
            coverage_by_turn[turn_id] = _safe_float(((layer1.get("key_points") or {}).get("coverage_ratio")), 0.0)

        merged = []
        for item in timeline_rows:
            turn_id = str(item.get("turn_id") or "").strip()
            merged.append({
                "turn_id": turn_id,
                "start_ms": _safe_float(item.get("answer_start_ms"), 0.0),
                "end_ms": _safe_float(item.get("answer_end_ms"), 0.0),
                "score": score_by_turn.get(turn_id, 0.0),
                "coverage": coverage_by_turn.get(turn_id, 0.0),
            })

        merged = [x for x in merged if x["turn_id"]]
        if not merged:
            return []

        ordered_high = sorted(merged, key=lambda x: (x["score"], x["coverage"]), reverse=True)
        ordered_low = sorted(merged, key=lambda x: (x["score"], x["coverage"]))

        tags = []
        top_n = min(2, len(merged))
        for item in ordered_high[:top_n]:
            tags.append({
                "turn_id": item["turn_id"],
                "tag_type": "high",
                "start_ms": round(item["start_ms"], 2),
                "end_ms": round(item["end_ms"], 2),
                "reason": "本题得分与关键点覆盖较高，表达完整度较好。",
                "confidence": round(min(0.95, 0.55 + item["score"] / 200.0), 4),
                "evidence_json": json.dumps({"score": item["score"], "coverage": item["coverage"]}, ensure_ascii=False),
                "source": "review_service",
            })
        for item in ordered_low[:top_n]:
            tags.append({
                "turn_id": item["turn_id"],
                "tag_type": "low",
                "start_ms": round(item["start_ms"], 2),
                "end_ms": round(item["end_ms"], 2),
                "reason": "本题得分或关键点覆盖偏低，建议重点复盘。",
                "confidence": round(min(0.95, 0.55 + (100.0 - item["score"]) / 220.0), 4),
                "evidence_json": json.dumps({"score": item["score"], "coverage": item["coverage"]}, ensure_ascii=False),
                "source": "review_service",
            })

        for prev, curr in zip(merged, merged[1:]):
            diff = curr["score"] - prev["score"]
            if abs(diff) < 12:
                continue
            tag_start = min(prev["end_ms"], curr["start_ms"])
            tag_end = max(prev["end_ms"], curr["start_ms"])
            tags.append({
                "turn_id": curr["turn_id"],
                "tag_type": "turning",
                "start_ms": round(tag_start, 2),
                "end_ms": round(tag_end if tag_end > tag_start else curr["start_ms"], 2),
                "reason": "该处回答质量出现明显跃迁，属于关键转折节点。",
                "confidence": round(min(0.93, 0.5 + abs(diff) / 100.0), 4),
                "evidence_json": json.dumps({"delta_score": round(diff, 2), "from_turn": prev["turn_id"], "to_turn": curr["turn_id"]}, ensure_ascii=False),
                "source": "review_service",
            })

        return tags

    def _build_deep_audit(self, evaluations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """构建深度审核报告，包含事实检查、维度差距和轮次诊断。"""
        fact_checks = []
        dimension_gaps = []
        round_diag = defaultdict(lambda: {"count": 0, "avg_score": 0.0, "coverage": 0.0})

        for row in evaluations:
            turn_id = str(row.get("turn_id") or "").strip()
            question = str(row.get("question") or "").strip()
            layer1 = row.get("layer1") or {}
            layer2 = row.get("layer2") or {}
            key_points = layer1.get("key_points") or {}
            missing = [str(item).strip() for item in (key_points.get("missing") or []) if str(item).strip()]
            red_flags = [str(item).strip() for item in ((layer1.get("signals") or {}).get("red_flags") or []) if str(item).strip()]

            if missing:
                fact_checks.append({
                    "turn_id": turn_id,
                    "question": question,
                    "type": "coverage_missing",
                    "finding": f"回答遗漏关键点：{missing[0]}",
                    "evidence": {"missing_key_points": missing[:4]},
                    "severity": "medium",
                })
            if red_flags:
                fact_checks.append({
                    "turn_id": turn_id,
                    "question": question,
                    "type": "risk_signal",
                    "finding": f"出现潜在风险信号：{red_flags[0]}",
                    "evidence": {"red_flags": red_flags[:4]},
                    "severity": "high",
                })

            round_type = str(row.get("round_type") or "technical")
            dims = _filter_content_dimensions_by_round(
                round_type,
                layer2.get("final_dimension_scores") or layer2.get("dimension_scores") or {},
            )
            weakest = sorted(
                [{"key": key, "score": _safe_float((value or {}).get("score"), 0.0)} for key, value in dims.items()],
                key=lambda item: item["score"]
            )[:2]
            for item in weakest:
                if item["score"] < 72:
                    dimension_gaps.append({
                        "turn_id": turn_id,
                        "question": question,
                        "dimension": item["key"],
                        "score": round(item["score"], 2),
                        "suggestion": f"建议补充 {item['key']} 维度的底层原理、权衡与边界条件说明。",
                    })

            score = _safe_float(layer2.get("overall_score_final") or row.get("overall_score"), 0.0)
            coverage = _safe_float(key_points.get("coverage_ratio"), 0.0)
            round_diag[round_type]["count"] += 1
            round_diag[round_type]["avg_score"] += score
            round_diag[round_type]["coverage"] += coverage

        normalized_round_diag = {}
        for key, payload in round_diag.items():
            count = max(1, int(payload["count"]))
            normalized_round_diag[key] = {
                "count": int(payload["count"]),
                "avg_score": round(payload["avg_score"] / count, 2),
                "avg_coverage": round(payload["coverage"] / count, 4),
            }

        return {
            "fact_checks": fact_checks[:24],
            "dimension_gaps": dimension_gaps[:24],
            "round_diagnosis": normalized_round_diag,
        }

    def _build_shadow_answers(
        self,
        evaluations: List[Dict[str, Any]],
        dialogues: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]] = None,
        version: str = "v1",
    ) -> List[Dict[str, Any]]:
        """构建影子回答，为低分题目生成优化后的参考回答。"""
        dialogue_by_turn = {str(item.get("turn_id") or "").strip(): item for item in dialogues if str(item.get("turn_id") or "").strip()}
        resume_skills = [str(item).strip() for item in ((resume_data or {}).get("skills") or []) if str(item).strip()]

        candidates = []
        for row in evaluations:
            turn_id = str(row.get("turn_id") or "").strip()
            if not turn_id:
                continue
            layer2 = row.get("layer2") or {}
            score = _safe_float(layer2.get("overall_score_final") or row.get("overall_score"), 0.0)
            if score >= 78:
                continue
            candidates.append((score, row))

        candidates.sort(key=lambda x: x[0])
        records = []
        for _, row in candidates[:4]:
            turn_id = str(row.get("turn_id") or "").strip()
            question = str(row.get("question") or "").strip()
            original_answer = str(row.get("answer") or "").strip()
            layer1 = row.get("layer1") or {}
            missing_points = [str(item).strip() for item in (((layer1.get("key_points") or {}).get("missing") or [])) if str(item).strip()]

            if missing_points:
                key_point_text = "；".join(missing_points[:3])
                focus = f"先补齐这几个关键点：{key_point_text}。"
            else:
                focus = "先给结论，再补原理、方案权衡和落地细节。"

            if resume_skills:
                skill_hint = f"可结合你的技术栈（{', '.join(resume_skills[:4])}）给出项目化例子。"
            else:
                skill_hint = "可结合你最熟悉的真实项目案例增强说服力。"

            shadow_answer = (
                f"我的结论是：针对这个问题我会先明确目标与约束，再给出可落地方案。"
                f"{focus}"
                f"在实现层面我会说明关键数据流、异常场景和性能权衡，最后补充验证方案与监控指标。"
                f"{skill_hint}"
            )
            why_better = "该版本结构更完整、关键点覆盖更高，并明确了取舍依据与工程落地路径。"
            records.append({
                "turn_id": turn_id,
                "question": question,
                "original_answer": original_answer,
                "shadow_answer": shadow_answer,
                "why_better": why_better,
                "resume_alignment_json": json.dumps({"skills": resume_skills[:6]}, ensure_ascii=False),
                "version": version,
            })

        return records

    def _build_visual_metrics(
        self,
        timeline_rows: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]],
        speech_rows: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """构建可视化指标，包含延迟、覆盖率、语音语调等数据。"""
        latencies = []
        for row in timeline_rows:
            latencies.append({
                "turn_id": str(row.get("turn_id") or "").strip(),
                "latency_ms": round(_safe_float(row.get("latency_ms"), 0.0), 2),
            })

        keyword_cov = []
        radar_bucket = defaultdict(list)
        for row in evaluations:
            turn_id = str(row.get("turn_id") or "").strip()
            layer1 = row.get("layer1") or {}
            layer2 = row.get("layer2") or {}
            coverage_ratio = _safe_float(((layer1.get("key_points") or {}).get("coverage_ratio")), 0.0)
            keyword_cov.append({
                "turn_id": turn_id,
                "coverage_ratio": round(coverage_ratio, 4),
            })
            round_type = str(row.get("round_type") or "technical")
            dims = _filter_content_dimensions_by_round(
                round_type,
                layer2.get("final_dimension_scores") or layer2.get("dimension_scores") or {},
            )
            for key, payload in dims.items():
                radar_bucket[key].append(_safe_float((payload or {}).get("score"), 0.0))

        radar = [
            {"key": key, "score": round(_avg(values), 2)}
            for key, values in sorted(radar_bucket.items())
        ]

        speech_summary = aggregate_expression_metrics(speech_rows)
        heatmap = [
            {
                "turn_id": item.get("turn_id"),
                "latency_ms": round(_safe_float(item.get("latency_ms"), 0.0), 2),
                "coverage_ratio": next((row.get("coverage_ratio") for row in keyword_cov if row.get("turn_id") == item.get("turn_id")), 0.0),
            }
            for item in timeline_rows
        ]

        return {
            "latency_matrix": {
                "avg_latency_ms": round(_avg([_safe_float(item.get("latency_ms"), 0.0) for item in latencies]), 2),
                "items": latencies,
            },
            "keyword_coverage": {
                "avg_coverage_ratio": round(_avg([_safe_float(item.get("coverage_ratio"), 0.0) for item in keyword_cov]), 4),
                "items": keyword_cov,
            },
            "speech_tone": speech_summary,
            "radar": radar,
            "heatmap": heatmap,
        }

    def _build_turn_evidence(
        self,
        dialogues: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]],
        timeline_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """构建回合证据，整合对话、评估和时间线数据。"""
        dialogue_by_turn = {
            str(item.get("turn_id") or "").strip(): item
            for item in (dialogues or [])
            if str(item.get("turn_id") or "").strip()
        }
        evaluation_by_turn = {
            str(item.get("turn_id") or "").strip(): item
            for item in (evaluations or [])
            if str(item.get("turn_id") or "").strip()
        }
        evidences = []
        for row in timeline_rows or []:
            turn_id = str(row.get("turn_id") or "").strip()
            if not turn_id:
                continue
            dialogue = dialogue_by_turn.get(turn_id, {})
            ev = evaluation_by_turn.get(turn_id, {})
            layer1 = ev.get("layer1") or {}
            layer2 = ev.get("layer2") or {}
            round_type = str(ev.get("round_type") or "technical")
            dims = _filter_content_dimensions_by_round(
                round_type,
                layer2.get("final_dimension_scores") or layer2.get("dimension_scores") or {},
            )
            weakest = sorted(
                [
                    {"dimension": key, "score": round(_safe_float((value or {}).get("score"), 0.0), 2)}
                    for key, value in dims.items()
                ],
                key=lambda item: item["score"],
            )[:2]
            evidences.append({
                "turn_id": turn_id,
                "question": str(dialogue.get("question") or ev.get("question") or ""),
                "answer": str(dialogue.get("answer") or ev.get("answer") or ""),
                "question_start_ms": round(_safe_float(row.get("question_start_ms"), 0.0), 2),
                "question_end_ms": round(_safe_float(row.get("question_end_ms"), 0.0), 2),
                "answer_start_ms": round(_safe_float(row.get("answer_start_ms"), 0.0), 2),
                "answer_end_ms": round(_safe_float(row.get("answer_end_ms"), 0.0), 2),
                "latency_ms": round(_safe_float(row.get("latency_ms"), 0.0), 2),
                "overall_score": round(_safe_float(layer2.get("overall_score_final") or ev.get("overall_score"), 0.0), 2),
                "coverage_ratio": round(_safe_float(((layer1.get("key_points") or {}).get("coverage_ratio")), 0.0), 4),
                "missing_key_points": [str(x).strip() for x in (((layer1.get("key_points") or {}).get("missing") or [])) if str(x).strip()][:4],
                "red_flags": [str(x).strip() for x in (((layer1.get("signals") or {}).get("red_flags") or [])) if str(x).strip()][:4],
                "weak_dimensions": weakest,
            })
        evidences.sort(key=lambda item: _safe_float(item.get("answer_start_ms"), 0.0))
        return evidences[: self.review_max_turns]

    def _normalize_llm_tags(self, tags: Any, timeline_by_turn: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """标准化 LLM 生成的标签数据。"""
        if not isinstance(tags, list):
            return []
        normalized = []
        for item in tags:
            if not isinstance(item, dict):
                continue
            turn_id = str(item.get("turn_id") or "").strip()
            if not turn_id or turn_id not in timeline_by_turn:
                continue
            timeline = timeline_by_turn.get(turn_id) or {}
            default_start = _safe_float(timeline.get("answer_start_ms"), 0.0)
            default_end = _safe_float(timeline.get("answer_end_ms"), default_start)
            start_ms = _safe_float(item.get("start_ms"), default_start)
            end_ms = _safe_float(item.get("end_ms"), default_end)
            if end_ms < start_ms:
                end_ms = start_ms
            tag_type = str(item.get("tag_type") or "").strip().lower()
            if tag_type not in {"high", "low", "turning", "emotion", "posture", "gaze"}:
                continue
            normalized.append({
                "turn_id": turn_id,
                "tag_type": tag_type,
                "start_ms": round(start_ms, 2),
                "end_ms": round(end_ms, 2),
                "reason": str(item.get("reason") or "").strip()[:220] or "关键片段",
                "confidence": round(_clamp(_safe_float(item.get("confidence"), 0.72), 0.0, 1.0), 4),
                "evidence_json": json.dumps({"source": "gemma4"}, ensure_ascii=False),
                "source": "gemma4",
            })
        return normalized[:18]

    @staticmethod
    def _normalize_llm_deep_audit(payload: Any) -> Dict[str, Any]:
        """标准化 LLM 生成的深度审核数据。"""
        if not isinstance(payload, dict):
            return {}

        fact_checks = []
        for item in payload.get("fact_checks") or []:
            if not isinstance(item, dict):
                continue
            finding = str(item.get("finding") or "").strip()
            if not finding:
                continue
            fact_checks.append({
                "turn_id": str(item.get("turn_id") or "").strip(),
                "question": str(item.get("question") or "").strip(),
                "type": str(item.get("type") or "fact_check").strip(),
                "finding": finding[:320],
                "evidence": item.get("evidence") if isinstance(item.get("evidence"), dict) else {},
                "severity": str(item.get("severity") or "medium").strip().lower(),
            })

        dimension_gaps = []
        for item in payload.get("dimension_gaps") or []:
            if not isinstance(item, dict):
                continue
            dimension = str(item.get("dimension") or "").strip()
            suggestion = str(item.get("suggestion") or "").strip()
            if not (dimension and suggestion):
                continue
            dimension_gaps.append({
                "turn_id": str(item.get("turn_id") or "").strip(),
                "question": str(item.get("question") or "").strip(),
                "dimension": dimension,
                "score": round(_safe_float(item.get("score"), 0.0), 2),
                "suggestion": suggestion[:320],
            })

        round_diagnosis = payload.get("round_diagnosis")
        if not isinstance(round_diagnosis, dict):
            round_diagnosis = {}

        return {
            "fact_checks": fact_checks[:24],
            "dimension_gaps": dimension_gaps[:24],
            "round_diagnosis": round_diagnosis,
        }

    def _normalize_llm_shadow_answers(
        self,
        records: Any,
        evaluations: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """标准化 LLM 生成的影子回答数据。"""
        if not isinstance(records, list):
            return []
        valid_turns = {str(item.get("turn_id") or "").strip() for item in evaluations}
        resume_skills = [str(x).strip() for x in ((resume_data or {}).get("skills") or []) if str(x).strip()]
        normalized = []
        for item in records:
            if not isinstance(item, dict):
                continue
            turn_id = str(item.get("turn_id") or "").strip()
            if not turn_id or turn_id not in valid_turns:
                continue
            shadow_answer = str(item.get("shadow_answer") or "").strip()
            if not shadow_answer:
                continue
            normalized.append({
                "turn_id": turn_id,
                "question": str(item.get("question") or "").strip(),
                "original_answer": str(item.get("original_answer") or "").strip(),
                "shadow_answer": shadow_answer[:1200],
                "why_better": str(item.get("why_better") or "").strip()[:320],
                "resume_alignment_json": json.dumps({"skills": resume_skills[:6]}, ensure_ascii=False),
                "version": self.review_version,
            })
        return normalized[:6]

    def _try_generate_llm_bundle(
        self,
        interview_id: str,
        dialogues: List[Dict[str, Any]],
        evaluations: List[Dict[str, Any]],
        timeline_rows: List[Dict[str, Any]],
        resume_data: Optional[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        """尝试使用 LLM 生成标签、深度审核和影子回答。"""
        if not self.review_llm_enabled:
            return None
        if self.llm_manager is None or not hasattr(self.llm_manager, "generate_structured_json"):
            return None

        turn_evidence = self._build_turn_evidence(dialogues, evaluations, timeline_rows)
        if not turn_evidence:
            return None

        resume_skills = [str(x).strip() for x in ((resume_data or {}).get("skills") or []) if str(x).strip()]
        timeline_by_turn = {str(item.get("turn_id") or "").strip(): item for item in timeline_rows}
        system_prompt = (
            "你是高级技术面试复盘教练。"
            "基于输入证据，输出结构化 JSON，不能输出 Markdown。"
            "结论要可执行、可定位到 turn。"
        )
        user_prompt = (
            "请根据输入证据产出以下内容：\n"
            "1) tags: highlight 标签列表，仅允许 high/low/turning。\n"
            "2) deep_audit: fact_checks + dimension_gaps + round_diagnosis。\n"
            "3) shadow_answers: 针对回答不完美题目的优化话术。\n"
            "必须返回 JSON：\n"
            "{\n"
            '  "tags":[{"turn_id":"...","tag_type":"high|low|turning","start_ms":0,"end_ms":0,"reason":"...","confidence":0.0}],\n'
            '  "deep_audit":{"fact_checks":[...],"dimension_gaps":[...],"round_diagnosis":{...}},\n'
            '  "shadow_answers":[{"turn_id":"...","question":"...","shadow_answer":"...","why_better":"..."}]\n'
            "}\n\n"
            f"interview_id: {interview_id}\n"
            f"resume_skills: {json.dumps(resume_skills[:8], ensure_ascii=False)}\n"
            f"turn_evidence_json: {json.dumps(turn_evidence, ensure_ascii=False)}\n"
        )
        result = self.llm_manager.generate_structured_json(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=self.review_model,
            temperature=0.15,
            top_p=0.35,
            top_k=40,
            max_tokens=2200,
            timeout=self.review_timeout,
        )
        if not result.get("success"):
            if self.logger:
                self.logger.warning(f"[Replay] Gemma4 复盘生成失败，回退启发式: {result.get('error')}")
            return None

        data = result.get("data")
        if not isinstance(data, dict):
            return None

        normalized_tags = self._normalize_llm_tags(data.get("tags"), timeline_by_turn)
        normalized_audit = self._normalize_llm_deep_audit(data.get("deep_audit"))
        normalized_shadow = self._normalize_llm_shadow_answers(data.get("shadow_answers"), evaluations, resume_data)
        return {
            "tags": normalized_tags,
            "deep_audit": normalized_audit,
            "shadow_answers": normalized_shadow,
            "model": str(result.get("model") or self.review_model),
        }

    def generate_replay(self, interview_id: str, force: bool = False) -> Dict[str, Any]:
        """生成完整的面试回放数据，包含时间线、标签、审核和影子回答。"""
        interview_id = str(interview_id or "").strip()
        if not interview_id:
            return {"success": False, "error": "invalid_interview_id"}

        dialogues = self.db_manager.get_interview_dialogues(interview_id) if hasattr(self.db_manager, "get_interview_dialogues") else []
        evaluations = self._decode_evaluations(
            self.db_manager.get_interview_evaluations(interview_id) if hasattr(self.db_manager, "get_interview_evaluations") else []
        )
        speech_rows = self._decode_speech_rows(
            self.db_manager.get_speech_evaluations(interview_id) if hasattr(self.db_manager, "get_speech_evaluations") else []
        )
        existing_timeline = self.db_manager.get_interview_turn_timelines(interview_id) if hasattr(self.db_manager, "get_interview_turn_timelines") else []

        timeline_rows = self._build_turn_timeline(interview_id, dialogues, speech_rows, existing_timeline if not force else [])
        if hasattr(self.db_manager, "save_or_update_turn_timeline"):
            for row in timeline_rows:
                self.db_manager.save_or_update_turn_timeline(row)

        resume_data = None
        if self.llm_manager is not None and hasattr(self.llm_manager, "load_resume_data"):
            try:
                resume_data = self.llm_manager.load_resume_data("default")
            except Exception:
                resume_data = None

        heuristic_tags = self._build_highlight_tags(interview_id, evaluations, timeline_rows)
        heuristic_audit = self._build_deep_audit(evaluations)
        heuristic_shadow = self._build_shadow_answers(
            evaluations,
            dialogues,
            resume_data=resume_data,
            version=self.review_version,
        )

        llm_bundle = self._try_generate_llm_bundle(
            interview_id=interview_id,
            dialogues=dialogues,
            evaluations=evaluations,
            timeline_rows=timeline_rows,
            resume_data=resume_data,
        )
        tags = (llm_bundle or {}).get("tags") or heuristic_tags
        deep_audit = (llm_bundle or {}).get("deep_audit") or heuristic_audit
        shadow_answers = (llm_bundle or {}).get("shadow_answers") or heuristic_shadow
        generated_version = self.review_version if llm_bundle else "v1_heuristic"

        if hasattr(self.db_manager, "replace_timeline_tags"):
            existing_tags = self.db_manager.get_timeline_tags(interview_id) if hasattr(self.db_manager, "get_timeline_tags") else []
            behavior_tags = [
                item for item in (existing_tags or [])
                if str(item.get("tag_type") or "").strip().lower() in {"emotion", "posture", "gaze"}
            ]
            self.db_manager.replace_timeline_tags(interview_id, list(tags or []) + behavior_tags)

        if hasattr(self.db_manager, "save_or_update_deep_audit"):
            round_diagnosis = deep_audit.get("round_diagnosis", {}) if isinstance(deep_audit, dict) else {}
            if llm_bundle:
                round_diagnosis = {
                    **(round_diagnosis if isinstance(round_diagnosis, dict) else {}),
                    "_meta": {
                        "model": llm_bundle.get("model", self.review_model),
                        "version": generated_version,
                    }
                }
            self.db_manager.save_or_update_deep_audit({
                "interview_id": interview_id,
                "fact_checks_json": json.dumps((deep_audit or {}).get("fact_checks", []), ensure_ascii=False),
                "dimension_gaps_json": json.dumps((deep_audit or {}).get("dimension_gaps", []), ensure_ascii=False),
                "round_diagnosis_json": json.dumps(round_diagnosis, ensure_ascii=False),
                "version": generated_version,
            })

        if hasattr(self.db_manager, "replace_shadow_answers"):
            self.db_manager.replace_shadow_answers(interview_id, shadow_answers, version=generated_version)

        visual_metrics = self._build_visual_metrics(timeline_rows, evaluations, speech_rows)
        if hasattr(self.db_manager, "save_or_update_visual_metrics"):
            self.db_manager.save_or_update_visual_metrics({
                "interview_id": interview_id,
                "latency_matrix_json": json.dumps(visual_metrics.get("latency_matrix", {}), ensure_ascii=False),
                "keyword_coverage_json": json.dumps(visual_metrics.get("keyword_coverage", {}), ensure_ascii=False),
                "speech_tone_json": json.dumps(visual_metrics.get("speech_tone", {}), ensure_ascii=False),
                "radar_json": json.dumps(visual_metrics.get("radar", []), ensure_ascii=False),
                "heatmap_json": json.dumps(visual_metrics.get("heatmap", []), ensure_ascii=False),
                "version": generated_version,
            })

        return {
            "success": True,
            "interview_id": interview_id,
            "timeline_count": len(timeline_rows),
            "tag_count": len(tags),
            "shadow_answer_count": len(shadow_answers),
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }

    def build_replay_payload(self, interview_id: str) -> Dict[str, Any]:
        """构建回放数据的前端展示载荷。"""
        interview_id = str(interview_id or "").strip()
        if not interview_id:
            return {"success": False, "error": "invalid_interview_id"}

        dialogues = self.db_manager.get_interview_dialogues(interview_id) if hasattr(self.db_manager, "get_interview_dialogues") else []
        evaluation_rows = self.db_manager.get_interview_evaluations(interview_id=interview_id) if hasattr(self.db_manager, "get_interview_evaluations") else []
        timeline_rows = self.db_manager.get_interview_turn_timelines(interview_id) if hasattr(self.db_manager, "get_interview_turn_timelines") else []
        speech_rows = self._decode_speech_rows(
            self.db_manager.get_speech_evaluations(interview_id) if hasattr(self.db_manager, "get_speech_evaluations") else []
        )
        timeline_rows = self._build_turn_timeline(interview_id, dialogues, speech_rows, timeline_rows)
        tags = self.db_manager.get_timeline_tags(interview_id) if hasattr(self.db_manager, "get_timeline_tags") else []
        deep_audit = self.db_manager.get_deep_audit(interview_id) if hasattr(self.db_manager, "get_deep_audit") else None
        latest_version = str((deep_audit or {}).get("version") or "").strip()
        if hasattr(self.db_manager, "get_shadow_answers"):
            shadow_answers = self.db_manager.get_shadow_answers(interview_id, version=latest_version or None)
        else:
            shadow_answers = []
        visual_metrics = self.db_manager.get_visual_metrics(interview_id) if hasattr(self.db_manager, "get_visual_metrics") else None

        dialogue_by_turn: Dict[str, Dict[str, Any]] = {}
        for idx, item in enumerate(sorted(dialogues or [], key=lambda x: str(x.get("created_at") or "")), start=1):
            turn_id = str(item.get("turn_id") or "").strip() or f"turn_legacy_{idx}"
            dialogue_by_turn[turn_id] = item
        evaluation_by_turn: Dict[str, Dict[str, Any]] = {}
        decoded_evaluations = self._decode_evaluations(evaluation_rows)
        for row in decoded_evaluations:
            turn_id = str(row.get("turn_id") or "").strip()
            if not turn_id:
                continue
            status = str(row.get("status") or "").strip().lower()
            if turn_id in evaluation_by_turn:
                existing_status = str((evaluation_by_turn.get(turn_id) or {}).get("status") or "").strip().lower()
                if existing_status in {"ok", "partial_ok"}:
                    continue
                if status not in {"ok", "partial_ok"}:
                    continue
            evaluation_by_turn[turn_id] = row

        transcript_anchors = []
        for row in timeline_rows:
            turn_id = str(row.get("turn_id") or "").strip()
            dialogue = dialogue_by_turn.get(turn_id, {})
            evaluation = evaluation_by_turn.get(turn_id, {})
            layer2 = evaluation.get("layer2") or {}
            score = layer2.get("overall_score_final")
            if score is None:
                score = evaluation.get("overall_score")
            if score is None:
                score = layer2.get("overall_score")
            transcript_anchors.append({
                "turn_id": turn_id,
                "question": str(dialogue.get("question") or ""),
                "answer": str(dialogue.get("answer") or ""),
                "question_start_ms": round(_safe_float(row.get("question_start_ms"), 0.0), 2),
                "question_end_ms": round(_safe_float(row.get("question_end_ms"), 0.0), 2),
                "answer_start_ms": round(_safe_float(row.get("answer_start_ms"), 0.0), 2),
                "answer_end_ms": round(_safe_float(row.get("answer_end_ms"), 0.0), 2),
                "latency_ms": round(_safe_float(row.get("latency_ms"), 0.0), 2),
                "score": round(_safe_float(score), 1) if score is not None else None,
            })

        parsed_visual_metrics = {
            "latency_matrix": _safe_json_loads((visual_metrics or {}).get("latency_matrix_json"), {}),
            "keyword_coverage": _safe_json_loads((visual_metrics or {}).get("keyword_coverage_json"), {}),
            "speech_tone": _safe_json_loads((visual_metrics or {}).get("speech_tone_json"), {}),
            "radar": _safe_json_loads((visual_metrics or {}).get("radar_json"), []),
            "heatmap": _safe_json_loads((visual_metrics or {}).get("heatmap_json"), []),
        }
        latency_items = ((parsed_visual_metrics.get("latency_matrix") or {}).get("items") or [])
        if timeline_rows and len(latency_items) != len(timeline_rows):
            parsed_visual_metrics = self._build_visual_metrics(timeline_rows, decoded_evaluations, speech_rows)

        payload = {
            "success": True,
            "interview_id": interview_id,
            "transcript_anchor_list": transcript_anchors,
            "tags": [
                {
                    **dict(item),
                    "evidence": _safe_json_loads(item.get("evidence_json"), {}),
                }
                for item in (tags or [])
            ],
            "audits": {
                "fact_checks": _safe_json_loads((deep_audit or {}).get("fact_checks_json"), []),
                "dimension_gaps": _safe_json_loads((deep_audit or {}).get("dimension_gaps_json"), []),
                "round_diagnosis": _safe_json_loads((deep_audit or {}).get("round_diagnosis_json"), {}),
            },
            "shadow_answers": [
                {
                    **dict(item),
                    "resume_alignment": _safe_json_loads(item.get("resume_alignment_json"), {}),
                }
                for item in (shadow_answers or [])
            ],
            "visual_metrics": parsed_visual_metrics,
            "meta": {
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "has_timeline": bool(transcript_anchors),
            },
        }
        return payload


class ReplayTaskManager:
    """用于回放生成的异步任务管理器。"""

    def __init__(self, replay_service: ReplayService, max_workers: int = 2, logger=None):
        """初始化任务管理器，配置线程池和锁。"""
        self.replay_service = replay_service
        self.max_workers = max(1, int(max_workers or 1))
        self.logger = logger
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="replay-worker")
        self._lock = threading.RLock()
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._inflight: Dict[str, str] = {}

    def enqueue(self, interview_id: str, force: bool = False) -> Dict[str, Any]:
        """将回放生成任务加入队列，支持去重。"""
        interview_id = str(interview_id or "").strip()
        if not interview_id:
            return {"success": False, "error": "invalid_interview_id"}

        with self._lock:
            inflight_task_id = self._inflight.get(interview_id)
            if inflight_task_id:
                task = self._tasks.get(inflight_task_id) or {}
                return {
                    "success": True,
                    "task_id": inflight_task_id,
                    "status": task.get("status", "running"),
                    "interview_id": interview_id,
                    "deduplicated": True,
                }

            task_id = f"review_{int(time.time() * 1000)}_{interview_id[-8:]}"
            self._tasks[task_id] = {
                "task_id": task_id,
                "interview_id": interview_id,
                "status": "pending",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "result": None,
                "error": "",
            }
            self._inflight[interview_id] = task_id

        def _runner():
            self._set_status(task_id, "running")
            try:
                result = self.replay_service.generate_replay(interview_id, force=force)
                if not result.get("success"):
                    self._set_status(task_id, "failed", error=result.get("error", "generate_failed"), result=result)
                else:
                    self._set_status(task_id, "ok", result=result)
            except Exception as exc:
                self._set_status(task_id, "failed", error=str(exc)[:240], result=None)
            finally:
                with self._lock:
                    current = self._inflight.get(interview_id)
                    if current == task_id:
                        self._inflight.pop(interview_id, None)

        self.executor.submit(_runner)
        return {"success": True, "task_id": task_id, "status": "pending", "interview_id": interview_id}

    def _set_status(self, task_id: str, status: str, error: str = "", result: Optional[Dict[str, Any]] = None) -> None:
        """设置任务状态，更新任务信息。"""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return
            task["status"] = status
            task["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            task["error"] = error
            if result is not None:
                task["result"] = result

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务状态和信息。"""
        with self._lock:
            task = self._tasks.get(str(task_id or "").strip())
            return dict(task) if task else None
