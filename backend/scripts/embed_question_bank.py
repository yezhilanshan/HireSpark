#!/usr/bin/env python
"""
Incrementally embed interview question banks into the RAG vector store.

Examples:
  python backend/scripts/embed_question_bank.py --source backend/interview_knowledge/new_questions.json
  python backend/scripts/embed_question_bank.py --source backend/interview_knowledge --dry-run
  python backend/scripts/embed_question_bank.py --source backend/interview_knowledge --rebuild
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.service import rag_service


SUPPORTED_SUFFIXES = {".json", ".jsonl", ".md"}

POSITION_HINTS = {
    "java_backend": (
        "java", "backend", "后端", "spring", "jvm", "redis", "mysql",
    ),
    "frontend": (
        "frontend", "front-end", "前端", "qianduan", "react", "vue", "javascript", "typescript",
    ),
    "algorithm": (
        "algorithm", "算法", "machine_learning", "ml", "deep_learning", "模型",
    ),
    "test_engineer": (
        "test", "qa", "测试", "ceshi", "software_test", "jmeter",
    ),
    "agent_developer": (
        "agent", "智能体", "mcp", "function_calling", "tool_call",
    ),
    "product_manager": (
        "product", "pm", "产品", "chanpin", "prd",
    ),
    "devops": (
        "devops", "运维", "kubernetes", "k8s", "docker", "cicd", "ci_cd",
    ),
}

ROLE_LABELS = {
    "java_backend": "Java后端工程师",
    "frontend": "前端工程师",
    "algorithm": "算法工程师",
    "test_engineer": "软件测试工程师",
    "agent_developer": "Agent开发工程师",
    "product_manager": "产品经理",
    "devops": "DevOps工程师",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Embed JSON/JSONL/Markdown interview question banks into the RAG vector store."
    )
    parser.add_argument(
        "--source",
        required=True,
        help="A JSON/JSONL/Markdown file or a directory containing question-bank files.",
    )
    parser.add_argument(
        "--position",
        default="",
        help="Optional position override, e.g. java_backend/frontend/test_engineer. Defaults to auto-detect.",
    )
    parser.add_argument(
        "--round-type",
        default="",
        help="Optional round_type override, e.g. technical/project/system_design/hr.",
    )
    parser.add_argument(
        "--difficulty",
        default="",
        help="Optional difficulty override, e.g. easy/medium/hard.",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear the existing vector store before embedding this source.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and normalize records without writing embeddings.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum number of normalized questions to embed, useful for smoke tests.",
    )
    return parser.parse_args()


def resolve_source_path(source: str) -> Path:
    raw = Path(source)
    if raw.is_absolute():
        return raw

    candidates = [
        Path.cwd() / raw,
        BACKEND_ROOT / raw,
        PROJECT_ROOT / raw,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()

    return (PROJECT_ROOT / raw).resolve()


def iter_source_files(source: Path) -> list[Path]:
    if source.is_file():
        if source.suffix.lower() not in SUPPORTED_SUFFIXES:
            raise ValueError(f"Unsupported file type: {source}")
        return [source]

    if not source.is_dir():
        raise FileNotFoundError(f"Source path does not exist: {source}")

    return [
        item
        for item in sorted(source.rglob("*"))
        if item.is_file() and item.suffix.lower() in SUPPORTED_SUFFIXES
    ]


def detect_position_from_text(*parts: Any) -> str:
    haystack = " ".join(str(part or "") for part in parts).lower()
    for position, hints in POSITION_HINTS.items():
        if any(str(hint).lower() in haystack for hint in hints):
            return position
    return ""


def infer_record_defaults(record: dict[str, Any], file_path: Path, args: argparse.Namespace) -> dict[str, Any]:
    updated = dict(record)

    detected_position = (
        str(args.position or "").strip()
        or str(updated.get("position") or "").strip()
        or detect_position_from_text(
            updated.get("role"),
            updated.get("category"),
            updated.get("subcategory"),
            updated.get("keywords"),
            updated.get("tags"),
            file_path.stem,
            file_path.parent.name,
        )
    )
    if detected_position:
        updated["position"] = detected_position
        updated.setdefault("role", ROLE_LABELS.get(detected_position, detected_position))
    elif not str(updated.get("role") or "").strip():
        updated["role"] = ROLE_LABELS.get("java_backend", "Java后端工程师")

    if args.round_type:
        updated["round_type"] = args.round_type
    else:
        updated.setdefault("round_type", "technical")

    if args.difficulty:
        updated["difficulty"] = args.difficulty
    else:
        updated.setdefault("difficulty", "medium")

    updated.setdefault("source", str(file_path.name))
    updated.setdefault("source_type", file_path.suffix.lower().lstrip(".") or "question_bank")
    return updated


def existing_vector_ids() -> set[str]:
    store = rag_service.store
    if store is None:
        return set()

    if getattr(store, "collection", None) is not None:
        try:
            data = store.collection.get(include=[])
        except Exception:
            data = store.collection.get()
        return {str(item) for item in (data or {}).get("ids", [])}

    fallback = getattr(store, "_fallback_data", {}) or {}
    return {str(item) for item in fallback.get("ids", []) or []}


def base_id_exists(base_id: str, existing_ids: set[str]) -> bool:
    return (
        base_id in existing_ids
        or f"{base_id}#question" in existing_ids
        or f"{base_id}#rubric" in existing_ids
    )


def summarize_by_position(records: Iterable[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for record in records:
        position = str(record.get("position") or record.get("role") or "unknown").strip() or "unknown"
        summary[position] = summary.get(position, 0) + 1
    return summary


def main() -> int:
    args = parse_args()

    if not rag_service.enabled:
        print("RAG is disabled in backend/config.yaml. Set rag.enabled: true first.")
        return 1

    source = resolve_source_path(args.source)
    files = iter_source_files(source)
    if not files:
        print(f"No supported question-bank files found under: {source}")
        return 1

    rag_service._init_runtime()
    if rag_service.store is None:
        print("RAG store is not available.")
        return 2

    if args.rebuild and not args.dry_run:
        rag_service.store.reset()

    raw_records: list[dict[str, Any]] = []
    for file_path in files:
        try:
            loaded = rag_service._load_records(str(file_path))
        except Exception as exc:
            print(f"[skip] {file_path}: {exc}")
            continue

        for record in loaded:
            if isinstance(record, dict):
                raw_records.append(infer_record_defaults(record, file_path, args))

    normalized = [
        rag_service._normalize_record(record, index)
        for index, record in enumerate(raw_records, start=1)
    ]
    normalized = rag_service._ensure_unique_record_ids(normalized)

    if args.limit and args.limit > 0:
        normalized = normalized[: args.limit]

    existing_ids = existing_vector_ids()
    new_records = [
        record
        for record in normalized
        if not base_id_exists(str(record.get("id") or "").strip(), existing_ids)
    ]

    report = {
        "source": str(source),
        "files": len(files),
        "parsed_records": len(raw_records),
        "normalized_records": len(normalized),
        "new_records": len(new_records),
        "skipped_existing": len(normalized) - len(new_records),
        "by_position": summarize_by_position(new_records),
        "dry_run": bool(args.dry_run),
        "rebuild": bool(args.rebuild),
    }

    if args.dry_run:
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0

    if new_records:
        rag_service.store.add_questions_batch(new_records)
        rag_service.store.save()

    report["vector_documents_after"] = rag_service.store.count()
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
