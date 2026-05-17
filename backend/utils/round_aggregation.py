from __future__ import annotations

from collections import Counter
from datetime import datetime
from statistics import median
from typing import Any


STATUS_WEIGHTS = {
    "full_ok": 1.0,
    "partial_ok": 0.75,
    "fallback_only": 0.35,
    "excluded": 0.0,
}

STABILIZER_VERSION = "round_stabilizer_v1"
CALIBRATION_VERSION = "cross_turn_calibrator_v1"


def _safe_float(value: Any) -> float | None:
    try:
        result = float(value)
    except Exception:
        return None
    return result if result == result else None


def _clamp_score(value: Any) -> float | None:
    score = _safe_float(value)
    if score is None:
        return None
    return round(max(0.0, min(100.0, score)), 2)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return int(default)


def _row_updated_epoch(row: dict[str, Any]) -> int:
    value = str((row or {}).get("updated_at") or (row or {}).get("created_at") or "").strip()
    if not value:
        return 0
    normalized = value.replace("T", " ").replace("Z", "").split(".")[0]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return int(datetime.strptime(normalized[:19] if fmt.endswith("%S") else normalized[:10], fmt).timestamp())
        except Exception:
            continue
    try:
        return int(datetime.fromisoformat(normalized).timestamp())
    except Exception:
        return 0


def _row_priority(row: dict[str, Any]) -> tuple[int, int, int, int]:
    status_priority = {
        "ok": 5,
        "partial_ok": 4,
        "running": 3,
        "pending": 2,
        "queued": 1,
        "skipped": 0,
        "failed": 0,
        "unknown": 0,
    }
    status = str((row or {}).get("status") or "unknown").strip().lower() or "unknown"
    return (
        int(status_priority.get(status, 0)),
        int(_extract_fusion_score(row) is not None),
        _row_updated_epoch(row),
        _safe_int((row or {}).get("id"), 0),
    )


def _weighted_mean(pairs: list[tuple[float, float]]) -> float | None:
    weighted_pairs = [(float(value), float(weight)) for value, weight in pairs if weight > 0]
    if not weighted_pairs:
        return None
    weight_sum = sum(weight for _, weight in weighted_pairs)
    if weight_sum <= 0:
        return None
    return round(sum(value * weight for value, weight in weighted_pairs) / weight_sum, 2)


def _question_excerpt(question_lookup: dict[str, str], row: dict[str, Any]) -> str:
    turn_id = str(row.get("turn_id") or "").strip()
    question = question_lookup.get(turn_id) or row.get("question") or ""
    return str(question).strip()[:80]


def _extract_fusion_score(row: dict[str, Any]) -> float | None:
    fusion = row.get("fusion") if isinstance(row.get("fusion"), dict) else {}
    layer2 = row.get("layer2") if isinstance(row.get("layer2"), dict) else {}
    return _clamp_score(
        fusion.get("overall_score")
        or row.get("overall_score")
        or layer2.get("overall_score_final")
        or layer2.get("overall_score")
    )


def _extract_axis_score(row: dict[str, Any], axis_name: str) -> float | None:
    fusion = row.get("fusion") if isinstance(row.get("fusion"), dict) else {}
    axis_scores = fusion.get("axis_scores") if isinstance(fusion.get("axis_scores"), dict) else {}
    if axis_name in axis_scores:
        return _clamp_score(axis_scores.get(axis_name))

    layer_map = {
        "content": row.get("text_layer") if isinstance(row.get("text_layer"), dict) else {},
        "delivery": row.get("speech_layer") if isinstance(row.get("speech_layer"), dict) else {},
        "presence": row.get("video_layer") if isinstance(row.get("video_layer"), dict) else {},
    }
    return _clamp_score((layer_map.get(axis_name) or {}).get("overall_score"))


def _normalize_turn_status(row: dict[str, Any]) -> tuple[str, str]:
    raw_status = str(row.get("status") or "unknown").strip().lower() or "unknown"
    fusion = row.get("fusion") if isinstance(row.get("fusion"), dict) else {}
    integrity = fusion.get("integrity") if isinstance(fusion.get("integrity"), dict) else {}
    layer2 = row.get("layer2") if isinstance(row.get("layer2"), dict) else {}

    if bool(integrity.get("veto")) or raw_status in {"failed", "skipped", "review_required", "veto"}:
        if bool(integrity.get("veto")):
            return "excluded", "integrity_veto"
        return "excluded", f"status={raw_status}"

    if raw_status == "ok":
        return "full_ok", "status=ok"

    if raw_status == "partial_ok":
        evaluation_mode = str(layer2.get("evaluation_mode") or "").strip()
        error_code = str(row.get("error_code") or layer2.get("error") or "").strip()
        evaluation_note = str(layer2.get("evaluation_note") or "").strip().lower()
        if evaluation_mode == "layer2_without_layer1_rubric":
            return "partial_ok", "layer2_without_layer1_rubric"
        if error_code or "fallback" in evaluation_note or "layer2 failed" in evaluation_note:
            return "fallback_only", error_code or evaluation_note or "partial_fallback"
        return "partial_ok", "status=partial_ok"

    return "excluded", f"status={raw_status}"


def _dedupe_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows):
        interview_id = str(row.get("interview_id") or "").strip()
        turn_id = str(row.get("turn_id") or "").strip()
        eval_task_key = str(row.get("eval_task_key") or "").strip()
        dedupe_key = "::".join(part for part in [interview_id, turn_id or eval_task_key or f"row_{index}"] if part)
        existing = deduped.get(dedupe_key)
        if not existing:
            deduped[dedupe_key] = row
            continue
        if _row_priority(row) > _row_priority(existing):
            deduped[dedupe_key] = row
    return list(deduped.values())


def _build_round_profile(
    round_type: str,
    rows: list[dict[str, Any]],
    question_lookup: dict[str, str],
    baseline_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    deduped_rows = _dedupe_rows(rows)
    status_mix = Counter()
    included_turns: list[dict[str, Any]] = []
    excluded_turns: list[dict[str, Any]] = []

    for row in deduped_rows:
        normalized_status, normalized_reason = _normalize_turn_status(row)
        status_mix[normalized_status] += 1
        fusion_score = _extract_fusion_score(row)
        confidence = max(0.0, min(1.0, _safe_float(row.get("confidence")) or 0.0))
        base_weight = STATUS_WEIGHTS.get(normalized_status, 0.0) * confidence

        turn_payload = {
            "turn_id": str(row.get("turn_id") or "").strip(),
            "question_excerpt": _question_excerpt(question_lookup, row),
            "raw_score": fusion_score,
            "confidence": round(confidence, 4),
            "normalized_status": normalized_status,
            "normalized_reason": normalized_reason,
            "base_turn_weight": round(base_weight, 4),
            "content_score": _extract_axis_score(row, "content"),
            "delivery_score": _extract_axis_score(row, "delivery"),
            "presence_score": _extract_axis_score(row, "presence"),
        }

        if normalized_status == "excluded":
            excluded_turns.append({
                "turn_id": turn_payload["turn_id"],
                "status": normalized_status,
                "reason": normalized_reason,
            })
            continue

        if fusion_score is None:
            excluded_turns.append({
                "turn_id": turn_payload["turn_id"],
                "status": normalized_status,
                "reason": "missing_fusion_score",
            })
            continue

        if base_weight <= 0:
            excluded_turns.append({
                "turn_id": turn_payload["turn_id"],
                "status": normalized_status,
                "reason": "missing_or_zero_confidence",
            })
            continue

        included_turns.append(turn_payload)

    raw_scores = [float(item["raw_score"]) for item in included_turns if item.get("raw_score") is not None]
    round_median = median(raw_scores) if raw_scores else None

    for item in included_turns:
        deviation = abs(float(item["raw_score"]) - float(round_median)) if round_median is not None else 0.0
        suppression_factor = 0.4 if deviation > 25 else 0.7 if deviation > 18 else 1.0
        item["deviation_from_median"] = round(deviation, 2)
        item["suppression_factor"] = suppression_factor

    round_score_raw = _weighted_mean([
        (float(item["raw_score"]), float(item["base_turn_weight"]))
        for item in included_turns
    ])
    round_score_stable = _weighted_mean([
        (float(item["raw_score"]), float(item["base_turn_weight"]) * float(item["suppression_factor"]))
        for item in included_turns
    ])

    axis_payload = {}
    for axis_key in ("content", "delivery", "presence"):
        pairs = [
            (float(item[f"{axis_key}_score"]), float(item["base_turn_weight"]) * float(item["suppression_factor"]))
            for item in included_turns
            if item.get(f"{axis_key}_score") is not None
        ]
        axis_payload[axis_key] = _weighted_mean(pairs)

    confidence_avg = _weighted_mean([
        (float(item["confidence"]), STATUS_WEIGHTS.get(str(item["normalized_status"]), 0.0))
        for item in included_turns
    ])

    if len(included_turns) <= 1:
        round_consistency_score = 100.0 if included_turns else None
    else:
        round_consistency_score = _clamp_score(
            100.0 - (
                _weighted_mean([
                    (float(item["deviation_from_median"]), float(item["base_turn_weight"]))
                    for item in included_turns
                ]) or 0.0
            ) * 3.0
        )

    outlier_turns = [
        {
            "turn_id": str(item["turn_id"]),
            "question_excerpt": str(item["question_excerpt"]),
            "raw_score": float(item["raw_score"]),
            "deviation_from_median": float(item["deviation_from_median"]),
            "suppression_factor": float(item["suppression_factor"]),
            "reason": "deviation_gt_25" if float(item["deviation_from_median"]) > 25 else "deviation_gt_18",
        }
        for item in included_turns
        if float(item.get("suppression_factor") or 1.0) < 1.0
    ]

    baseline_deduped = _dedupe_rows(baseline_rows)
    baseline_scores = [
        score for row in baseline_deduped
        if str(row.get("status") or "").strip().lower() in {"ok", "partial_ok"}
        for score in [_extract_fusion_score(row)]
        if score is not None
    ][:300]
    baseline_avg_score = round(sum(baseline_scores) / len(baseline_scores), 2) if baseline_scores else None
    relative_position = (
        round(float(round_score_raw) - float(baseline_avg_score), 2)
        if round_score_raw is not None and baseline_avg_score is not None
        else None
    )
    if relative_position is None:
        relative_band = None
    elif relative_position >= 8:
        relative_band = "above_baseline"
    elif relative_position <= -8:
        relative_band = "below_baseline"
    else:
        relative_band = "near_baseline"

    return {
        "round_type": round_type,
        "turn_count_total": len(deduped_rows),
        "turn_count_used": len(included_turns),
        "turn_count_excluded": len(excluded_turns),
        "round_score_raw": round_score_raw,
        "round_score_stable": round_score_stable,
        "round_content_score": axis_payload["content"],
        "round_delivery_score": axis_payload["delivery"],
        "round_presence_score": axis_payload["presence"],
        "round_consistency_score": round_consistency_score,
        "confidence_avg": confidence_avg,
        "relative_position": relative_position,
        "relative_band": relative_band,
        "baseline_avg_score": baseline_avg_score,
        "baseline_sample_size": len(baseline_scores),
        "difficulty_adjustment": 0.0,
        "outlier_turns": outlier_turns,
        "excluded_turns": excluded_turns,
        "status_mix": dict(status_mix),
    }


def build_round_aggregation(
    current_rows: list[dict[str, Any]],
    baseline_rows_by_round: dict[str, list[dict[str, Any]]] | None = None,
    question_lookup: dict[str, str] | None = None,
) -> dict[str, Any]:
    baseline_rows_by_round = baseline_rows_by_round or {}
    question_lookup = question_lookup or {}
    deduped_rows = _dedupe_rows(current_rows)

    rows_by_round: dict[str, list[dict[str, Any]]] = {}
    for row in deduped_rows:
        round_type = str(row.get("round_type") or "unknown").strip() or "unknown"
        rows_by_round.setdefault(round_type, []).append(row)

    round_profiles = [
        _build_round_profile(
            round_type=round_type,
            rows=rows,
            question_lookup=question_lookup,
            baseline_rows=baseline_rows_by_round.get(round_type, []),
        )
        for round_type, rows in sorted(rows_by_round.items())
    ]

    valid_profiles = [item for item in round_profiles if item.get("turn_count_used", 0) > 0]
    stability_pairs_raw = [
        (float(item["round_score_raw"]), float(item["turn_count_used"]))
        for item in valid_profiles
        if item.get("round_score_raw") is not None
    ]
    stability_pairs_stable = [
        (float(item["round_score_stable"]), float(item["turn_count_used"]))
        for item in valid_profiles
        if item.get("round_score_stable") is not None
    ]
    consistency_pairs = [
        (float(item["round_consistency_score"]), float(item["turn_count_used"]))
        for item in valid_profiles
        if item.get("round_consistency_score") is not None
    ]

    dominant_round_type = (
        max(round_profiles, key=lambda item: int(item.get("turn_count_total") or 0)).get("round_type")
        if round_profiles else None
    )

    round_summary = {
        "total_rounds": len(round_profiles),
        "ready_rounds": len(valid_profiles),
        "total_turns_used": sum(int(item.get("turn_count_used") or 0) for item in round_profiles),
        "total_turns_excluded": sum(int(item.get("turn_count_excluded") or 0) for item in round_profiles),
        "dominant_round_type": dominant_round_type,
        "status_mix": dict(
            Counter(
                status_key
                for item in round_profiles
                for status_key, count in (item.get("status_mix") or {}).items()
                for _ in range(int(count or 0))
            )
        ),
    }

    interview_stability = {
        "overall_score_raw": _weighted_mean(stability_pairs_raw),
        "overall_score_stable": _weighted_mean(stability_pairs_stable),
        "round_count": len(round_profiles),
        "avg_consistency_score": _weighted_mean(consistency_pairs),
        "outlier_turn_count": sum(len(item.get("outlier_turns") or []) for item in round_profiles),
        "dominant_round_type": dominant_round_type,
    }

    if round_profiles:
        status = "ready" if valid_profiles else "partial"
        status_message = "round aggregation ready" if valid_profiles else "round aggregation has no usable turns"
    else:
        status = "empty"
        status_message = "no round aggregation data"

    return {
        "status": status,
        "status_message": status_message,
        "round_profiles": round_profiles,
        "round_summary": round_summary,
        "interview_stability": interview_stability,
        "calibration_version": CALIBRATION_VERSION,
        "stabilizer_version": STABILIZER_VERSION,
    }
