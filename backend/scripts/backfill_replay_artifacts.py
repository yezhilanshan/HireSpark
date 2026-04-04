#!/usr/bin/env python
"""
Backfill replay artifacts (A/B/C/D) for historical interviews.

Usage:
  python backend/scripts/backfill_replay_artifacts.py --limit 100
  python backend/scripts/backfill_replay_artifacts.py --interview-id interview_xxx --force
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

from database import DatabaseManager
from utils.logger import get_logger
from utils.replay_service import ReplayService

try:
    from utils.llm_manager import llm_manager
except Exception:
    llm_manager = None

try:
    from rag.service import rag_service
except Exception:
    rag_service = None


logger = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill replay artifacts for historical interviews.")
    parser.add_argument("--db", default="backend/interview_system.db", help="SQLite DB path")
    parser.add_argument("--interview-id", action="append", default=[], help="Specific interview_id(s)")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of interviews")
    parser.add_argument("--force", action="store_true", help="Force regeneration")
    parser.add_argument("--json", action="store_true", help="Print JSON summary")
    return parser.parse_args()


def resolve_db_path(raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return str(candidate)
    for item in (Path.cwd() / candidate, BACKEND_ROOT / candidate, PROJECT_ROOT / candidate):
        if item.exists():
            return str(item.resolve())
    return str((PROJECT_ROOT / candidate).resolve())


def load_interview_ids(db_manager: DatabaseManager, explicit_ids: List[str], limit: int) -> List[str]:
    normalized = [str(item).strip() for item in explicit_ids if str(item).strip()]
    if normalized:
        return normalized

    sql = """
        SELECT interview_id
        FROM interview_dialogues
        GROUP BY interview_id
        ORDER BY MAX(datetime(created_at)) DESC
    """
    params = []
    if limit and limit > 0:
        sql += " LIMIT ?"
        params.append(int(limit))

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [str(row["interview_id"]).strip() for row in cursor.fetchall() if str(row["interview_id"]).strip()]


def main() -> int:
    args = parse_args()
    db_path = resolve_db_path(args.db)
    db_manager = DatabaseManager(db_path=db_path)
    service = ReplayService(
        db_manager=db_manager,
        llm_manager=llm_manager,
        rag_service=rag_service,
        logger=logger,
    )

    interview_ids = load_interview_ids(db_manager, args.interview_id, args.limit)
    if not interview_ids:
        summary = {"success": True, "processed": 0, "ok": 0, "failed": 0, "errors": []}
        print(json.dumps(summary, ensure_ascii=False, indent=2) if args.json else "No interviews to process.")
        return 0

    ok = 0
    failed = 0
    errors: List[Dict[str, str]] = []

    for interview_id in interview_ids:
        result = service.generate_replay(interview_id, force=bool(args.force))
        if result.get("success"):
            ok += 1
            print(f"[OK] {interview_id} tags={result.get('tag_count', 0)} shadow={result.get('shadow_answer_count', 0)}")
        else:
            failed += 1
            err = str(result.get("error") or "unknown_error")
            errors.append({"interview_id": interview_id, "error": err})
            print(f"[FAILED] {interview_id} error={err}")

    summary = {
        "success": failed == 0,
        "processed": len(interview_ids),
        "ok": ok,
        "failed": failed,
        "errors": errors[:20],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"Processed={summary['processed']} ok={ok} failed={failed}")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
