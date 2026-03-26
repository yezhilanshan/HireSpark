#!/usr/bin/env python
"""
Check RAG retrieval quality and print a compact top-k quality report.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.service import rag_service


DEFAULT_CASES = [
    {
        "query": "Attention 为什么要除以 dk",
        "position": "大模型算法工程师",
        "expected_keywords": ["attention", "dk", "softmax"],
    },
    {
        "query": "PPO 和 DPO 有什么区别",
        "position": "大模型算法工程师",
        "expected_keywords": ["ppo", "dpo", "rlhf"],
    },
    {
        "query": "Adam 优化器原理",
        "position": "大模型算法工程师",
        "expected_keywords": ["adam", "优化器", "梯度"],
    },
    {
        "query": "RoPE 的原理是什么",
        "position": "大模型算法工程师",
        "expected_keywords": ["rope", "位置编码", "相对位置"],
    },
    {
        "query": "交叉熵损失函数怎么写",
        "position": "大模型算法工程师",
        "expected_keywords": ["交叉熵", "损失函数", "crossentropy"],
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check RAG retrieval quality.")
    parser.add_argument("--position", help="Override position for all test cases.")
    parser.add_argument("--top-k", type=int, default=3, help="Number of results to print.")
    parser.add_argument(
        "--query",
        action="append",
        help="Custom query. Can be passed multiple times. If omitted, built-in cases are used."
    )
    parser.add_argument(
        "--show-context",
        action="store_true",
        help="Also print the answer context built for each query."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print a machine-readable JSON report instead of formatted text."
    )
    return parser.parse_args()


def match_expected(item: Dict, expected_keywords: List[str]) -> Dict[str, List[str]]:
    metadata = item.get("metadata", {}) or {}
    haystack = " ".join([
        item.get("question", "") or "",
        metadata.get("answer", "") or "",
        metadata.get("answer_summary", "") or "",
        metadata.get("category", "") or "",
        metadata.get("subcategory", "") or "",
        " ".join(str(keyword) for keyword in metadata.get("keywords", []) or []),
        " ".join(str(tag) for tag in metadata.get("tags", []) or []),
    ]).lower()

    hits = [keyword for keyword in expected_keywords if keyword.lower() in haystack]
    misses = [keyword for keyword in expected_keywords if keyword.lower() not in haystack]
    return {"hits": hits, "misses": misses}


def run_cases(
    top_k: int,
    show_context: bool,
    position_override: str | None,
    custom_queries: List[str] | None = None
) -> Dict:
    status = rag_service.status()
    cases = []

    if not rag_service.ensure_ready():
        return {"status": status, "cases": [], "summary": {"error": "RAG not ready"}}

    raw_cases = list(DEFAULT_CASES)
    if custom_queries:
        raw_cases = [
            {
                "query": query,
                "position": position_override or "大模型算法工程师",
                "expected_keywords": [],
            }
            for query in custom_queries
        ]

    for raw_case in raw_cases:
        case = dict(raw_case)
        if position_override:
            case["position"] = position_override

        results = rag_service.retrieve(
            query=case["query"],
            position=case["position"],
            top_k=top_k
        )

        formatted_results = []
        for index, item in enumerate(results, start=1):
            expectation = match_expected(item, case["expected_keywords"])
            formatted_results.append({
                "rank": index,
                "id": item.get("id"),
                "question": item.get("question"),
                "similarity": round(float(item.get("similarity", 0)), 4),
                "lexical_score": round(float(item.get("lexical_score", 0)), 4),
                "rerank_score": round(float(item.get("rerank_score", 0)), 4),
                "is_strong_match": bool(item.get("is_strong_match", False)),
                "keyword_hits": item.get("keyword_hits", []),
                "ascii_hits": item.get("ascii_hits", []),
                "expected_hits": expectation["hits"],
                "expected_misses": expectation["misses"],
            })

        top1_hit = bool(formatted_results and formatted_results[0]["expected_hits"])
        topk_hit = any(result["expected_hits"] for result in formatted_results)

        report_item = {
            "query": case["query"],
            "position": case["position"],
            "expected_keywords": case["expected_keywords"],
            "top1_hit": top1_hit if case["expected_keywords"] else None,
            "topk_hit": topk_hit if case["expected_keywords"] else None,
            "results": formatted_results,
        }
        if show_context:
            report_item["context"] = rag_service.build_answer_context(
                position=case["position"],
                current_question=case["query"]
            )

        cases.append(report_item)

    summary = {
        "case_count": len(cases),
    }
    scored_cases = [case for case in cases if case["top1_hit"] is not None]
    if scored_cases:
        summary["top1_hit_rate"] = round(
            sum(1 for case in scored_cases if case["top1_hit"]) / len(scored_cases),
            4
        )
        summary["topk_hit_rate"] = round(
            sum(1 for case in scored_cases if case["topk_hit"]) / len(scored_cases),
            4
        )

    return {
        "status": rag_service.status(),
        "cases": cases,
        "summary": summary,
    }


def print_report(report: Dict):
    print("RAG Status")
    print(json.dumps(report["status"], ensure_ascii=False, indent=2))
    print()

    for case in report["cases"]:
        print("=" * 72)
        print(f"Query: {case['query']}")
        print(f"Position: {case['position']}")
        if case["expected_keywords"]:
            print(f"Expected: {', '.join(case['expected_keywords'])}")
            print(f"Top-1 Hit: {'YES' if case['top1_hit'] else 'NO'} | Top-K Hit: {'YES' if case['topk_hit'] else 'NO'}")
        else:
            print("Expected: (custom query, no keyword scoring)")
        print("-" * 72)

        if not case["results"]:
            print("No results")
        else:
            for result in case["results"]:
                print(
                    f"[{result['rank']}] {result['question']}\n"
                    f"    id={result['id']} sim={result['similarity']:.4f} "
                    f"lex={result['lexical_score']:.4f} rerank={result['rerank_score']:.4f} "
                    f"strong={result['is_strong_match']}"
                )
                print(
                    f"    expected_hits={result['expected_hits']} "
                    f"keyword_hits={result['keyword_hits']} ascii_hits={result['ascii_hits']}"
                )

        if "context" in case:
            print("-" * 72)
            print("Context Preview:")
            print(case["context"] or "(empty)")
        print()

    print("=" * 72)
    print("Summary")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


def main() -> int:
    args = parse_args()
    report = run_cases(
        top_k=args.top_k,
        show_context=args.show_context,
        position_override=args.position,
        custom_queries=args.query
    )

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print_report(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
