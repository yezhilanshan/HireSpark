#!/usr/bin/env python
"""
Scenario-oriented RAG test script for interview_knowledge.

It evaluates question retrieval with multiple query styles:
1. exact: use the original question text
2. keyword: use role + round + category + keywords
3. paraphrase: use a rewritten natural query
4. resume_skill: simulate next-question planning from resume hints

It also evaluates rubric retrieval separately with an answer-evaluation query.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.service import rag_service


QUESTION_MODES = ("exact", "keyword", "paraphrase", "resume_skill")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Scenario-oriented RAG matching test for interview_knowledge."
    )
    parser.add_argument(
        "--source",
        default="backend/interview_knowledge",
        help="Knowledge source path. Supports directory, Markdown, JSON, or JSONL.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="How many retrieval results to inspect for each case.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Limit number of records to test. Use 0 for all records.",
    )
    parser.add_argument(
        "--position",
        help="Only test records for a specific role/position.",
    )
    parser.add_argument(
        "--modes",
        default="all",
        help="Comma-separated question query modes: exact,keyword,paraphrase,resume_skill. Default: all",
    )
    parser.add_argument(
        "--rebuild-first",
        action="store_true",
        help="Rebuild the index from --source before running tests.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of formatted text.",
    )
    return parser.parse_args()


def resolve_source_path(source: str | None) -> str | None:
    if not source:
        return None

    raw = Path(source)
    if raw.is_absolute():
        return str(raw)

    candidates = [
        Path.cwd() / raw,
        BACKEND_ROOT / raw,
        PROJECT_ROOT / raw,
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate.resolve())

    return str((PROJECT_ROOT / raw).resolve())


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "").strip())


def shorten_text(text: str, limit: int = 90) -> str:
    text = normalize_text(text)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def base_id(document_id: str) -> str:
    return str(document_id or "").split("#")[0]


def find_expected_rank(items: List[Dict[str, Any]], expected_id: str) -> Optional[int]:
    for index, item in enumerate(items, start=1):
        if base_id(item.get("id", "")) == expected_id:
            return index
    return None


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def extract_topic_hint(question: str) -> str:
    text = normalize_text(question)
    prefixes = [
        "请做一个",
        "请用1分钟",
        "请用一分钟",
        "请你",
        "请",
        "介绍一个",
        "介绍你",
        "介绍",
        "聊聊一个",
        "聊聊",
        "说说",
        "为什么",
        "如果让候选人",
    ]
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix):].strip()
            break

    stop_phrases = ["怎么", "如何", "一下", "一下子", "可以", "应该", "并", "一下你", "吗"]
    for phrase in stop_phrases:
        text = text.replace(phrase, " ")

    text = re.sub(r"[？?！!，,。；;：:、/]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def build_exact_query(record: Dict[str, Any]) -> str:
    return str(record.get("question", "")).strip()


def build_keyword_query(record: Dict[str, Any]) -> str:
    topic_hint = extract_topic_hint(str(record.get("question", "")))
    parts = [
        record.get("position", ""),
        record.get("round_type", ""),
        first_non_empty(record.get("subcategory"), record.get("category")),
    ]
    keywords = [str(item).strip() for item in record.get("keywords", []) or [] if str(item).strip()]
    competencies = [str(item).strip() for item in record.get("competency", []) or [] if str(item).strip()]
    if topic_hint:
        parts.append(topic_hint)
    parts.extend(keywords[:3] or competencies[:2])
    return " ".join(part for part in parts if str(part).strip())


def build_paraphrase_query(record: Dict[str, Any]) -> str:
    question = normalize_text(record.get("question", ""))
    replacements = [
        ("请做一个自我介绍并突出", "如果让候选人自我介绍并重点突出"),
        ("请用1分钟介绍", "如果面试中要求候选人在1分钟内说明"),
        ("介绍一个", "聊聊一个"),
        ("介绍你", "聊聊你"),
        ("介绍", "说说"),
        ("为什么", "你会怎么解释为什么"),
        ("请", ""),
    ]
    rewritten = question
    for old, new in replacements:
        if old in rewritten:
            rewritten = rewritten.replace(old, new, 1)
            break

    if rewritten == question:
        anchor = first_non_empty(record.get("subcategory"), record.get("category"))
        keywords = [str(item).strip() for item in record.get("keywords", []) or [] if str(item).strip()]
        if keywords:
            rewritten = f"围绕{'、'.join(keywords[:2])}的{anchor or '面试'}追问怎么问"
        else:
            rewritten = f"{record.get('position', '')}岗位里，{question}"

    return rewritten.strip()


def build_resume_skill_query(record: Dict[str, Any]) -> str:
    position = str(record.get("position", "")).strip()
    subcategory = first_non_empty(record.get("subcategory"), record.get("category"))
    topic_hint = extract_topic_hint(str(record.get("question", "")))
    keywords = [str(item).strip() for item in record.get("keywords", []) or [] if str(item).strip()]
    competencies = [str(item).strip() for item in record.get("competency", []) or [] if str(item).strip()]
    hints = [topic_hint] if topic_hint else []
    if not hints:
        hints = keywords[:2] or competencies[:2] or ([subcategory] if subcategory else [])

    parts = [f"候选人应聘{position}"]
    if hints:
        parts.append(f"简历里提到{'、'.join(hints)}")
    if subcategory:
        parts.append(f"希望考察{subcategory}")
    parts.append("下一题应该怎么追问")
    return "，".join(part for part in parts if str(part).strip())


def build_rubric_query(record: Dict[str, Any]) -> str:
    parts = [str(record.get("question", "")).strip()]
    answer_summary = normalize_text(record.get("answer_summary", ""))
    if answer_summary:
        parts.append(shorten_text(answer_summary, 120))
    expected_signals = [str(item).strip() for item in record.get("expected_answer_signals", []) or [] if str(item).strip()]
    if expected_signals:
        parts.append(" ".join(expected_signals[:3]))
    common_mistakes = [str(item).strip() for item in record.get("common_mistakes", []) or [] if str(item).strip()]
    if common_mistakes:
        parts.append("避免：" + " ".join(common_mistakes[:2]))
    return " ".join(part for part in parts if part).strip()


QUESTION_QUERY_BUILDERS: Dict[str, Callable[[Dict[str, Any]], str]] = {
    "exact": build_exact_query,
    "keyword": build_keyword_query,
    "paraphrase": build_paraphrase_query,
    "resume_skill": build_resume_skill_query,
}


def parse_modes(raw_modes: str) -> List[str]:
    if not raw_modes or raw_modes.strip().lower() == "all":
        return list(QUESTION_MODES)

    modes = []
    for item in raw_modes.split(","):
        mode = item.strip().lower()
        if not mode:
            continue
        if mode not in QUESTION_QUERY_BUILDERS:
            raise ValueError(f"Unsupported mode: {mode}")
        modes.append(mode)

    if not modes:
        raise ValueError("No valid modes provided.")
    return modes


def load_normalized_records(source_path: str, position_filter: str | None) -> List[Dict[str, Any]]:
    raw_records = rag_service._load_records(source_path=source_path)
    normalized = [
        rag_service._normalize_record(record, index)
        for index, record in enumerate(raw_records, start=1)
    ]
    if position_filter:
        normalized = [
            record for record in normalized
            if str(record.get("position", "")).strip() == position_filter.strip()
        ]
    return normalized


def format_result_snapshot(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": item.get("id"),
        "question": item.get("question"),
        "similarity": round(float(item.get("similarity", 0.0)), 4),
        "lexical_score": round(float(item.get("lexical_score", 0.0)), 4),
        "rerank_score": round(float(item.get("rerank_score", 0.0)), 4),
    }


def retrieve_question_results(
    query: str,
    position: str,
    round_type: str,
    top_k: int,
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    metadata_filters = {"round_type": round_type} if round_type else None
    strict_results = rag_service.retrieve_questions(
        query=query,
        position=position,
        top_k=top_k,
        metadata_filters=metadata_filters,
    )

    retriever = getattr(rag_service, "question_retriever", None)
    if retriever is None:
        return strict_results, []

    diagnostic_results = retriever.retrieve(
        query=query,
        top_k=max(top_k, 10),
        min_similarity=0.0,
        strong_filter=False,
        metadata_filters=metadata_filters,
    )

    if position:
        normalized_position = rag_service._normalize_position(position)
        diagnostic_results = [
            item for item in diagnostic_results
            if not rag_service._normalize_position(
                str((item.get("metadata", {}) or {}).get("position", ""))
            ) or rag_service._normalize_position(
                str((item.get("metadata", {}) or {}).get("position", ""))
            ) == normalized_position
        ]

    return strict_results, diagnostic_results


def run_test(
    source_path: str,
    top_k: int,
    limit: int,
    position_filter: str | None,
    rebuild_first: bool,
    modes: List[str],
) -> Dict[str, Any]:
    if rebuild_first:
        rag_service.build_index(source_path=source_path, rebuild=True)

    if not rag_service.ensure_ready():
        return {"error": "RAG not ready"}

    records = load_normalized_records(source_path, position_filter)
    if limit > 0:
        records = records[:limit]

    mode_stats = {
        mode: {
            "top1_hits": 0,
            "topk_hits": 0,
            "top1_similarity_sum": 0.0,
            "cases": 0,
        }
        for mode in modes
    }
    rubric_stats = {
        "top1_hits": 0,
        "topk_hits": 0,
        "top1_similarity_sum": 0.0,
        "cases": 0,
    }

    cases = []
    for record in records:
        position = record.get("position", "")
        round_type = record.get("round_type", "technical")
        expected_id = record["id"]
        mode_results = {}

        for mode in modes:
            query = QUESTION_QUERY_BUILDERS[mode](record)
            retrieved, diagnostic_retrieved = retrieve_question_results(
                query=query,
                position=position,
                round_type=round_type,
                top_k=top_k,
            )
            expected_rank = find_expected_rank(retrieved, expected_id)
            diagnostic_rank = find_expected_rank(diagnostic_retrieved, expected_id)
            top_result = retrieved[0] if retrieved else {}
            diagnostic_top = diagnostic_retrieved[0] if diagnostic_retrieved else {}
            top1_hit = expected_rank == 1
            topk_hit = expected_rank is not None

            mode_stats[mode]["cases"] += 1
            mode_stats[mode]["top1_hits"] += int(top1_hit)
            mode_stats[mode]["topk_hits"] += int(topk_hit)
            mode_stats[mode]["top1_similarity_sum"] += float(top_result.get("similarity", 0.0))

            mode_results[mode] = {
                "query": query,
                "expected_rank": expected_rank,
                "diagnostic_rank": diagnostic_rank,
                "top1_hit": top1_hit,
                "topk_hit": topk_hit,
                "top_result": format_result_snapshot(top_result) if top_result else None,
                "diagnostic_top_result": format_result_snapshot(diagnostic_top) if diagnostic_top else None,
            }

        rubric_query = build_rubric_query(record)
        rubric_retrieved = rag_service.retrieve_rubrics(
            query=rubric_query,
            position=position,
            top_k=top_k,
            metadata_filters={"round_type": round_type} if round_type else None,
        )
        rubric_rank = find_expected_rank(rubric_retrieved, expected_id)
        rubric_top_result = rubric_retrieved[0] if rubric_retrieved else {}
        rubric_top1_hit = rubric_rank == 1
        rubric_topk_hit = rubric_rank is not None

        rubric_stats["cases"] += 1
        rubric_stats["top1_hits"] += int(rubric_top1_hit)
        rubric_stats["topk_hits"] += int(rubric_topk_hit)
        rubric_stats["top1_similarity_sum"] += float(rubric_top_result.get("similarity", 0.0))

        cases.append({
            "id": expected_id,
            "position": position,
            "round_type": round_type,
            "question": record["question"],
            "question_view": mode_results,
            "rubric_view": {
                "query": rubric_query,
                "expected_rank": rubric_rank,
                "top1_hit": rubric_top1_hit,
                "topk_hit": rubric_topk_hit,
                "top_result": format_result_snapshot(rubric_top_result) if rubric_top_result else None,
            },
        })

    summary_modes = {}
    for mode in modes:
        cases_count = mode_stats[mode]["cases"]
        summary_modes[mode] = {
            "top1_hit_rate": round(mode_stats[mode]["top1_hits"] / cases_count, 4) if cases_count else 0.0,
            "topk_hit_rate": round(mode_stats[mode]["topk_hits"] / cases_count, 4) if cases_count else 0.0,
            "avg_top1_similarity": round(mode_stats[mode]["top1_similarity_sum"] / cases_count, 4) if cases_count else 0.0,
        }

    rubric_cases = rubric_stats["cases"]
    summary = {
        "source_path": source_path,
        "tested_records": len(cases),
        "question_view": summary_modes,
        "rubric_view": {
            "top1_hit_rate": round(rubric_stats["top1_hits"] / rubric_cases, 4) if rubric_cases else 0.0,
            "topk_hit_rate": round(rubric_stats["topk_hits"] / rubric_cases, 4) if rubric_cases else 0.0,
            "avg_top1_similarity": round(rubric_stats["top1_similarity_sum"] / rubric_cases, 4) if rubric_cases else 0.0,
        },
    }

    return {
        "status": rag_service.status(),
        "summary": summary,
        "cases": cases,
    }


def print_report(report: Dict[str, Any], modes: List[str]) -> None:
    if report.get("error"):
        print(report["error"])
        return

    print("RAG Status")
    print(json.dumps(report["status"], ensure_ascii=False, indent=2))
    print()
    print("Summary")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print()

    for case in report["cases"]:
        print("=" * 90)
        print(f"[{case['id']}] {case['question']}")
        print(f"Position: {case['position']} | Round: {case['round_type']}")

        for mode in modes:
            result = case["question_view"][mode]
            top = result.get("top_result") or {}
            diagnostic_top = result.get("diagnostic_top_result") or {}
            print(
                f"Question View [{mode}]: "
                f"rank={result['expected_rank']} "
                f"diag_rank={result['diagnostic_rank']} "
                f"top1={result['top1_hit']} "
                f"topk={result['topk_hit']} "
                f"sim={top.get('similarity', 0.0)} "
                f"lex={top.get('lexical_score', 0.0)} "
                f"rerank={top.get('rerank_score', 0.0)}"
            )
            print(f"  query: {result['query']}")
            print(f"  top: {top.get('id')} | {top.get('question')}")
            if not result["topk_hit"] and diagnostic_top:
                print(
                    f"  diagnostic_top: {diagnostic_top.get('id')} | "
                    f"{diagnostic_top.get('question')} | "
                    f"sim={diagnostic_top.get('similarity', 0.0)} "
                    f"lex={diagnostic_top.get('lexical_score', 0.0)} "
                    f"rerank={diagnostic_top.get('rerank_score', 0.0)}"
                )

        rubric = case["rubric_view"]
        rubric_top = rubric.get("top_result") or {}
        print(
            "Rubric View: "
            f"rank={rubric['expected_rank']} "
            f"top1={rubric['top1_hit']} "
            f"topk={rubric['topk_hit']} "
            f"sim={rubric_top.get('similarity', 0.0)} "
            f"lex={rubric_top.get('lexical_score', 0.0)} "
            f"rerank={rubric_top.get('rerank_score', 0.0)}"
        )
        print(f"  query: {rubric['query']}")
        print(f"  top: {rubric_top.get('id')} | {rubric_top.get('question')}")


def main() -> int:
    args = parse_args()
    modes = parse_modes(args.modes)
    source_path = resolve_source_path(args.source)
    report = run_test(
        source_path=source_path,
        top_k=args.top_k,
        limit=args.limit,
        position_filter=args.position,
        rebuild_first=args.rebuild_first,
        modes=modes,
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report, modes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
