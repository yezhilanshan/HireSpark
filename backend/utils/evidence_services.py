from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _clamp_unit(value: Any, default: float = 0.0) -> float:
    num = _safe_float(value)
    if num is None:
        num = default
    return max(0.0, min(1.0, float(num)))


def _clamp_score(value: Any, default: float = 0.0) -> float:
    num = _safe_float(value)
    if num is None:
        num = default
    return round(max(0.0, min(100.0, float(num))), 2)


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip()
    return " ".join(text.split())


def _normalize_text_list(values: Any, limit: int = 6) -> List[str]:
    normalized: List[str] = []
    for item in list(values or []):
        if isinstance(item, dict):
            text = _normalize_text(item.get("point") or item.get("label") or item.get("text") or item.get("value"))
        else:
            text = _normalize_text(item)
        if text:
            normalized.append(text)
    deduped = list(dict.fromkeys(normalized))
    return deduped[:limit]


def _severity_from_score(score: float) -> str:
    if score >= 85:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 35:
        return "medium"
    return "low"


class TextEvidenceService:
    def build(
        self,
        *,
        layer1_result: Dict[str, Any],
        layer2_result: Dict[str, Any],
        confidence: float,
    ) -> Dict[str, Any]:
        key_points = (layer1_result or {}).get("key_points") if isinstance((layer1_result or {}).get("key_points"), dict) else {}
        signals = (layer1_result or {}).get("signals") if isinstance((layer1_result or {}).get("signals"), dict) else {}
        covered_points = _normalize_text_list(key_points.get("covered"), limit=6)
        missing_points = _normalize_text_list(key_points.get("missing"), limit=6)
        red_flags = _normalize_text_list(signals.get("red_flags"), limit=4)
        hit_signals = _normalize_text_list(signals.get("hit"), limit=6)

        coverage_ratio = _safe_float(key_points.get("coverage_ratio"))
        if coverage_ratio is None:
            total = len(covered_points) + len(missing_points)
            coverage_ratio = (len(covered_points) / total) if total > 0 else 0.0

        dimension_scores = (layer2_result or {}).get("final_dimension_scores") or (layer2_result or {}).get("dimension_scores") or {}
        quotes: List[str] = []
        for payload in dimension_scores.values():
            if not isinstance(payload, dict):
                continue
            evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
            quotes.extend(_normalize_text_list(evidence.get("source_quotes"), limit=4))
        quotes = list(dict.fromkeys(quotes))[:4]

        signal_items = (
            [{"code": "hit_signal", "severity": "info", "label": item} for item in hit_signals]
            + [{"code": "red_flag", "severity": "high", "label": item} for item in red_flags]
        )[:8]
        status = "ready" if (covered_points or missing_points or red_flags or quotes) else "unavailable"
        return {
            "status": status,
            "source": "text",
            "confidence": round(_clamp_unit(confidence), 4),
            "features": {
                "coverage_ratio": round(float(coverage_ratio or 0.0), 4),
                "covered_points": covered_points,
                "missing_points": missing_points,
                "red_flags": red_flags,
            },
            "quotes": quotes,
            "signals": signal_items,
        }


class SpeechEvidenceService:
    FEATURE_KEYS = (
        "speech_rate_score",
        "pause_anomaly_score",
        "filler_frequency_score",
        "fluency_score",
        "clarity_score",
    )

    def build(self, *, speech_context: Dict[str, Any], confidence: float) -> Dict[str, Any]:
        speech_context = dict(speech_context or {})
        quality_gate = speech_context.get("quality_gate") if isinstance(speech_context.get("quality_gate"), dict) else {}
        expression_dimensions = speech_context.get("expression_dimensions") if isinstance(speech_context.get("expression_dimensions"), dict) else {}
        features = {
            "audio_duration_ms": round(float(_safe_float(speech_context.get("audio_duration_ms")) or 0.0), 2),
            "token_count": int(speech_context.get("token_count") or 0),
        }
        for key in self.FEATURE_KEYS:
            value = _safe_float(expression_dimensions.get(key))
            if value is not None:
                features[key] = _clamp_score(value)

        gate_reasons = [_normalize_text(item) for item in (quality_gate.get("reasons") or []) if _normalize_text(item)]
        signals = [
            {
                "code": reason,
                "severity": "medium" if str(reason).startswith("missing_") else "high",
                "label": reason,
            }
            for reason in gate_reasons[:6]
        ]

        status = "ready" if bool(quality_gate.get("passed")) else ("insufficient_data" if speech_context.get("available") else "unavailable")
        return {
            "status": status,
            "source": "speech",
            "confidence": round(_clamp_unit(confidence), 4),
            "quality_gate": {
                "passed": bool(quality_gate.get("passed")),
                "reasons": gate_reasons,
            },
            "features": features,
            "quotes": [_normalize_text(speech_context.get("final_transcript_excerpt"))] if _normalize_text(speech_context.get("final_transcript_excerpt")) else [],
            "signals": signals,
        }


class VideoEvidenceService:
    def build(
        self,
        *,
        video_context: Dict[str, Any],
        dimension_scores: Dict[str, Any],
        confidence: float,
        integrity_signals: List[Dict[str, Any]] | None = None,
    ) -> Dict[str, Any]:
        video_context = dict(video_context or {})
        dimension_scores = dict(dimension_scores or {})
        integrity_signals = list(integrity_signals or [])

        def _dimension_value(key: str) -> float | None:
            payload = dimension_scores.get(key) if isinstance(dimension_scores.get(key), dict) else {}
            return _safe_float(payload.get("score"))

        raw_off_screen = _safe_float(video_context.get("off_screen_ratio")) or 0.0
        off_screen_ratio = raw_off_screen * 100.0 if raw_off_screen <= 1.0 else raw_off_screen
        has_face = bool(video_context.get("has_face", True))
        face_count = int(video_context.get("face_count", 1) or 1)
        face_stability = _clamp_score(
            100.0
            - min(60.0, off_screen_ratio * 0.7)
            - (15.0 if not has_face else 0.0)
            - (18.0 if face_count > 1 else 0.0)
        )
        physiology_reliability = 85.0 if bool(video_context.get("rppg_reliable", False)) else 45.0

        features = {
            "gaze_focus": _clamp_score(_dimension_value("gaze_focus")),
            "posture_compliance": _clamp_score(_dimension_value("posture_compliance")),
            "face_stability": face_stability,
            "expression_naturalness": _clamp_score(_dimension_value("expression_naturalness")),
            "physiology_stability": _clamp_score(_dimension_value("physiology_stability")),
            "physiology_reliability": _clamp_score(physiology_reliability),
        }

        suspicious_signals = []
        for item in integrity_signals[:8]:
            if not isinstance(item, dict):
                continue
            code = _normalize_text(item.get("code"))
            if not code:
                continue
            score = _clamp_score(item.get("score"))
            suspicious_signals.append(
                {
                    "code": code,
                    "severity": _normalize_text(item.get("severity")) or _severity_from_score(score),
                    "score": score,
                }
            )

        status = "ready" if video_context else "unavailable"
        return {
            "status": status,
            "source": "video",
            "confidence": round(_clamp_unit(confidence), 4),
            "features": features,
            "quotes": [],
            "signals": suspicious_signals,
        }
