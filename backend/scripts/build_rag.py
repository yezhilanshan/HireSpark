#!/usr/bin/env python
"""
Build or rebuild the RAG index from a knowledge file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from rag.service import rag_service


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build the interview RAG index.")
    parser.add_argument(
        "--source",
        help="Optional path to a JSON/JSONL knowledge file. Defaults to rag.knowledge_path."
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Clear the persisted index before rebuilding."
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if not rag_service.enabled:
        print("RAG is disabled in config.yaml. Set rag.enabled: true first.")
        return 1

    try:
        count = rag_service.build_index(source_path=args.source, rebuild=args.rebuild)
    except Exception as exc:
        print(f"Failed to build RAG index: {exc}")
        return 2

    print(json.dumps(rag_service.status(), ensure_ascii=False, indent=2))
    print(f"Indexed documents: {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
