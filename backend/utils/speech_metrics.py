"""
Speech metrics utilities for realtime feedback and final expression scoring.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, List, Tuple


_CJK_RE = re.compile(r"[\u4e00-\u9fff]")
_EN_WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_DIGIT_RE = re.compile(r"\d+")
_FILLERS = {
    "啊",
    "嗯",
    "呃",
    "额",
    "哦",
    "哎",
    "唉",
    "就是",
    "那个",
    "这个",
    "然后",
    "然后呢",
    "你知道",
    "怎么说呢",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return float(default)


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, float(value)))


def normalize_token(token: str) -> str:
    return re.sub(r"\s+", "", str(token or "").strip().lower())


def count_spoken_tokens(text: str) -> int:
    content = str(text or "").strip()
    if not content:
        return 0
    cjk_count = len(_CJK_RE.findall(content))
    en_count = len(_EN_WORD_RE.findall(content))
    digit_count = len(_DIGIT_RE.findall(content))
    return max(0, cjk_count + en_count + digit_count)


def normalize_word_timestamps(word_timestamps: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for raw in word_timestamps or []:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or raw.get("word") or raw.get("token") or "").strip()
        if not text:
            continue
        start_ms = _safe_float(
            raw.get("start_ms", raw.get("start", raw.get("begin", raw.get("start_time", 0.0))))
        )
        end_ms = _safe_float(
            raw.get("end_ms", raw.get("end", raw.get("stop", raw.get("end_time", 0.0))))
        )
        if end_ms < start_ms:
            start_ms, end_ms = end_ms, start_ms
        confidence = raw.get("confidence")
        normalized.append(
            {
                "text": text,
                "start_ms": round(max(0.0, start_ms), 2),
                "end_ms": round(max(0.0, end_ms), 2),
                "confidence": _safe_float(confidence, 0.0) if confidence is not None else None,
            }
        )
    normalized.sort(key=lambda item: (item["start_ms"], item["end_ms"]))
    return normalized


def derive_pause_events(word_timestamps: List[Dict[str, Any]], min_pause_ms: float = 120.0) -> List[Dict[str, Any]]:
    pauses: List[Dict[str, Any]] = []
    if len(word_timestamps) < 2:
        return pauses

    for prev, nxt in zip(word_timestamps, word_timestamps[1:]):
        gap_ms = _safe_float(nxt.get("start_ms")) - _safe_float(prev.get("end_ms"))
        if gap_ms < min_pause_ms:
            continue
        if gap_ms < 600:
            pause_type = "short"
        elif gap_ms < 1500:
            pause_type = "medium"
        else:
            pause_type = "long"
        pauses.append(
            {
                "start_ms": round(_safe_float(prev.get("end_ms")), 2),
                "end_ms": round(_safe_float(nxt.get("start_ms")), 2),
                "duration_ms": round(gap_ms, 2),
                "type": pause_type,
            }
        )
    return pauses


def derive_filler_events(transcript: str, word_timestamps: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    filler_events: List[Dict[str, Any]] = []
    if word_timestamps:
        for word in word_timestamps:
            normalized = normalize_token(word.get("text", ""))
            if normalized in _FILLERS:
                filler_events.append(
                    {
                        "text": word.get("text", ""),
                        "start_ms": _safe_float(word.get("start_ms")),
                        "end_ms": _safe_float(word.get("end_ms")),
                    }
                )
        if filler_events:
            return filler_events

    content = str(transcript or "")
    for filler in sorted(_FILLERS, key=len, reverse=True):
        for match in re.finditer(re.escape(filler), content):
            filler_events.append(
                {
                    "text": filler,
                    "char_start": int(match.start()),
                    "char_end": int(match.end()),
                }
            )
    return filler_events


def _calc_repetition_ratio(words: List[Dict[str, Any]]) -> float:
    if not words:
        return 0.0
    normalized_words = [normalize_token(item.get("text", "")) for item in words if item.get("text")]
    normalized_words = [token for token in normalized_words if token]
    if len(normalized_words) < 2:
        return 0.0
    repeat_hits = sum(
        1 for idx in range(1, len(normalized_words)) if normalized_words[idx] == normalized_words[idx - 1]
    )
    return repeat_hits / max(1, len(normalized_words) - 1)


def compute_final_speech_metrics(
    transcript: str,
    draft_text: str,
    word_timestamps: List[Dict[str, Any]],
    audio_duration_ms: float,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], List[Dict[str, Any]]]:
    words = normalize_word_timestamps(word_timestamps)
    pauses = derive_pause_events(words)
    fillers = derive_filler_events(transcript, words)

    audio_duration_ms = max(0.0, _safe_float(audio_duration_ms))
    if audio_duration_ms <= 0.0 and words:
        audio_duration_ms = max(0.0, _safe_float(words[-1].get("end_ms")) - _safe_float(words[0].get("start_ms")))

    speech_ms = sum(max(0.0, _safe_float(word.get("end_ms")) - _safe_float(word.get("start_ms"))) for word in words)
    pause_ms = sum(max(0.0, _safe_float(item.get("duration_ms"))) for item in pauses)
    if speech_ms <= 0.0 and audio_duration_ms > 0.0:
        speech_ms = max(0.0, audio_duration_ms - pause_ms)

    token_count = count_spoken_tokens(transcript)
    speech_minutes = max(speech_ms / 60000.0, 1e-6)
    audio_minutes = max(audio_duration_ms / 60000.0, 1e-6)
    speech_rate_wpm = token_count / speech_minutes if token_count > 0 else 0.0

    pause_counter = Counter(item.get("type", "short") for item in pauses)
    long_pause_ratio = pause_counter.get("long", 0) / max(1, len(pauses))
    pause_anomaly_ratio = (
        (pause_counter.get("medium", 0) + pause_counter.get("long", 0)) / max(1, len(pauses))
        if pauses else 0.0
    )

    filler_count = len(fillers)
    fillers_per_min = filler_count / audio_minutes if filler_count else 0.0
    fillers_per_100_words = (filler_count / token_count) * 100 if token_count else 0.0
    repetition_ratio = _calc_repetition_ratio(words)

    avg_confidence = None
    confidences = [_safe_float(item.get("confidence")) for item in words if item.get("confidence") is not None]
    if confidences:
        avg_confidence = sum(confidences) / len(confidences)
    low_confidence_ratio = (
        (sum(1 for score in confidences if score < 0.75) / len(confidences))
        if confidences else 0.0
    )

    draft = str(draft_text or "").strip()
    final = str(transcript or "").strip()
    stability_ratio = SequenceMatcher(None, draft, final).ratio() if draft and final else (1.0 if final else 0.0)

    # 维度分数（启发式）
    # 语速：默认目标区间 120-210 token/min，偏离越大扣分。
    if speech_rate_wpm <= 0:
        speech_rate_score = 45.0
    elif speech_rate_wpm < 120:
        speech_rate_score = _clamp(88 - (120 - speech_rate_wpm) * 0.6)
    elif speech_rate_wpm > 210:
        speech_rate_score = _clamp(88 - (speech_rate_wpm - 210) * 0.5)
    else:
        speech_rate_score = _clamp(90 - abs(speech_rate_wpm - 165) * 0.08)

    pause_anomaly_score = _clamp(92 - pause_anomaly_ratio * 42 - long_pause_ratio * 24 - max(0.0, pause_ms - 5000) / 260)
    filler_frequency_score = _clamp(94 - fillers_per_100_words * 5.0 - max(0.0, fillers_per_min - 3.0) * 2.2)
    fluency_score = _clamp(90 - pause_anomaly_ratio * 35 - repetition_ratio * 45 - fillers_per_100_words * 2.4)
    clarity_score = _clamp(
        62
        + stability_ratio * 28
        + (avg_confidence * 18 if avg_confidence is not None else 0)
        - low_confidence_ratio * 20
        - fillers_per_100_words * 1.6
    )

    metrics = {
        "analysis_version": "speech_v1",
        "audio_duration_ms": round(audio_duration_ms, 2),
        "effective_speech_ms": round(max(0.0, speech_ms), 2),
        "silence_ms": round(max(0.0, audio_duration_ms - speech_ms), 2) if audio_duration_ms else round(max(0.0, pause_ms), 2),
        "token_count": int(token_count),
        "speech_rate_wpm": round(speech_rate_wpm, 2),
        "pause": {
            "count": len(pauses),
            "short_count": int(pause_counter.get("short", 0)),
            "medium_count": int(pause_counter.get("medium", 0)),
            "long_count": int(pause_counter.get("long", 0)),
            "total_pause_ms": round(pause_ms, 2),
            "anomaly_ratio": round(pause_anomaly_ratio, 4),
        },
        "fillers": {
            "count": filler_count,
            "per_minute": round(fillers_per_min, 3),
            "per_100_words": round(fillers_per_100_words, 3),
        },
        "fluency": {
            "repetition_ratio": round(repetition_ratio, 4),
            "score": round(fluency_score, 2),
        },
        "clarity_proxy": {
            "stability_ratio": round(stability_ratio, 4),
            "avg_confidence": round(avg_confidence, 4) if avg_confidence is not None else None,
            "low_confidence_ratio": round(low_confidence_ratio, 4),
            "score": round(clarity_score, 2),
        },
        "dimensions": {
            "speech_rate_score": round(speech_rate_score, 2),
            "pause_anomaly_score": round(pause_anomaly_score, 2),
            "filler_frequency_score": round(filler_frequency_score, 2),
            "fluency_score": round(fluency_score, 2),
            "clarity_score": round(clarity_score, 2),
        },
    }

    return metrics, pauses, fillers


def aggregate_expression_metrics(speech_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not speech_rows:
        return {
            "available": False,
            "dimensions": {},
            "summary": {},
        }

    dimension_keys = (
        "speech_rate_score",
        "pause_anomaly_score",
        "filler_frequency_score",
        "fluency_score",
        "clarity_score",
    )
    accum = {key: [] for key in dimension_keys}
    summary_accum = {
        "speech_rate_wpm": [],
        "fillers_per_100_words": [],
        "pause_anomaly_ratio": [],
        "long_pause_count": [],
    }

    for row in speech_rows:
        metrics = row.get("speech_metrics_final") or {}
        dimensions = (metrics or {}).get("dimensions") or {}
        for key in dimension_keys:
            if key in dimensions:
                accum[key].append(_safe_float(dimensions.get(key)))
        summary_accum["speech_rate_wpm"].append(_safe_float((metrics or {}).get("speech_rate_wpm")))
        summary_accum["fillers_per_100_words"].append(_safe_float(((metrics or {}).get("fillers") or {}).get("per_100_words")))
        summary_accum["pause_anomaly_ratio"].append(_safe_float(((metrics or {}).get("pause") or {}).get("anomaly_ratio")))
        summary_accum["long_pause_count"].append(_safe_float(((metrics or {}).get("pause") or {}).get("long_count")))

    def _avg(values: List[float]) -> float:
        valid = [item for item in values if isinstance(item, (int, float)) and not math.isnan(item)]
        return (sum(valid) / len(valid)) if valid else 0.0

    dimensions = {key: round(_avg(values), 2) for key, values in accum.items() if values}
    summary = {
        "avg_speech_rate_wpm": round(_avg(summary_accum["speech_rate_wpm"]), 2),
        "avg_fillers_per_100_words": round(_avg(summary_accum["fillers_per_100_words"]), 3),
        "avg_pause_anomaly_ratio": round(_avg(summary_accum["pause_anomaly_ratio"]), 4),
        "avg_long_pause_count": round(_avg(summary_accum["long_pause_count"]), 2),
        "samples": len(speech_rows),
    }

    return {
        "available": bool(dimensions),
        "dimensions": dimensions,
        "summary": summary,
    }
