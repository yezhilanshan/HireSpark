#!/usr/bin/env python
"""
Backfill historical structured evaluations from interview_dialogues.

Usage examples:
1) Dry run all dialogues:
   python backend/scripts/backfill_historical_evaluations.py --dry-run

2) Backfill one interview and wait for completion:
    python backend/scripts/backfill_historical_evaluations.py --interview-id interview_xxx

3) Backfill recent 200 dialogues:
    python backend/scripts/backfill_historical_evaluations.py --limit 200
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = Path(__file__).resolve().parents[1]

for path in (str(BACKEND_ROOT), str(PROJECT_ROOT)):
    if path not in sys.path:
        sys.path.insert(0, path)

from database import DatabaseManager
from utils.evaluation_service import EvaluationService
from utils.logger import get_logger

try:
    from rag.service import rag_service
except Exception:
    rag_service = None

try:
    from utils.llm_manager import llm_manager
except Exception:
    llm_manager = None


FINAL_STATUSES = {"ok", "partial_ok", "skipped", "failed"}
RUNNING_STATUSES = {"pending", "running"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill historical structured evaluations.")
    parser.add_argument(
        "--db",
        default="backend/interview_system.db",
        help="Path to sqlite db file (default: backend/interview_system.db)",
    )
    parser.add_argument(
        "--interview-id",
        action="append",
        default=[],
        help="Only backfill the given interview_id (can be passed multiple times).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Max number of dialogue rows to process (0 means no limit).",
    )
    parser.add_argument(
        "--position",
        default="",
        help="Optional position to write into evaluation records.",
    )
    parser.add_argument(
        "--round-type-override",
        default="",
        help="Optional round_type override for all rows.",
    )
    parser.add_argument(
        "--include-empty-answer",
        action="store_true",
        help="Include dialogues whose answer is empty. Default is skip empty answers.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-evaluation by overwriting existing record for the generated turn_id.",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Deprecated. Kept for compatibility. Waiting is enabled by default.",
    )
    parser.add_argument(
        "--no-wait",
        action="store_true",
        help="Do not wait for async evaluation tasks to finish (not recommended for backfill).",
    )
    parser.add_argument(
        "--wait-timeout",
        type=int,
        default=600,
        help="Max seconds to wait when --wait is enabled (default: 600).",
    )
    parser.add_argument(
        "--poll-interval",
        type=float,
        default=1.0,
        help="Polling interval seconds when waiting (default: 1.0).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned operations, do not enqueue.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary in JSON format.",
    )
    return parser.parse_args()


def resolve_db_path(raw_path: str) -> str:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        return str(candidate)

    candidates = [
        Path.cwd() / candidate,
        BACKEND_ROOT / candidate,
        PROJECT_ROOT / candidate,
    ]
    for item in candidates:
        if item.exists():
            return str(item.resolve())
    return str((PROJECT_ROOT / candidate).resolve())


def load_dialogues(
    db_manager: DatabaseManager,
    interview_ids: Sequence[str],
    limit: int,
) -> List[Dict]:
    normalized_ids = [str(item).strip() for item in (interview_ids or []) if str(item).strip()]

    sql = """
        SELECT id, interview_id, round_type, question, answer, created_at
        FROM interview_dialogues
    """
    params: List = []
    if normalized_ids:
        placeholders = ",".join(["?"] * len(normalized_ids))
        sql += f" WHERE interview_id IN ({placeholders})"
        params.extend(normalized_ids)

    sql += " ORDER BY datetime(created_at) ASC, id ASC"
    if limit > 0:
        sql += " LIMIT ?"
        params.append(limit)

    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, params)
        return [dict(row) for row in cursor.fetchall()]


def ensure_parent_interviews(db_manager: DatabaseManager, interview_ids: Sequence[str], dry_run: bool) -> Tuple[int, int, List[str]]:
    normalized_ids = [str(item).strip() for item in interview_ids if str(item).strip()]
    if not normalized_ids:
        return 0, 0, []

    placeholders = ",".join(["?"] * len(normalized_ids))
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            f"SELECT interview_id FROM interviews WHERE interview_id IN ({placeholders})",
            normalized_ids,
        )
        existing = {str(row["interview_id"]).strip() for row in cursor.fetchall()}

    missing = [item for item in normalized_ids if item not in existing]
    if not missing:
        return 0, 0, []

    written = 0
    failed: List[str] = []
    for interview_id in missing:
        if dry_run:
            continue
        result = db_manager.save_interview(
            {
                "interview_id": interview_id,
                "start_time": None,
                "end_time": None,
                "duration": None,
                "max_probability": None,
                "avg_probability": None,
                "risk_level": None,
                "events_count": None,
                "report_path": None,
            }
        )
        if result.get("success"):
            written += 1
        else:
            failed.append(interview_id)
    return len(missing), written, failed


def chunked(items: Sequence, size: int) -> List[Sequence]:
    if size <= 0:
        return [items]
    return [items[idx : idx + size] for idx in range(0, len(items), size)]


def fetch_status_map(
    db_manager: DatabaseManager,
    keys: Sequence[Tuple[str, str]],
    evaluation_version: str,
) -> Dict[Tuple[str, str], Dict]:
    grouped: Dict[str, List[str]] = defaultdict(list)
    for interview_id, turn_id in keys:
        grouped[str(interview_id).strip()].append(str(turn_id).strip())

    result: Dict[Tuple[str, str], Dict] = {}
    with db_manager.get_connection() as conn:
        cursor = conn.cursor()
        for interview_id, turn_ids in grouped.items():
            for turn_batch in chunked(turn_ids, 300):
                placeholders = ",".join(["?"] * len(turn_batch))
                sql = f"""
                    SELECT interview_id, turn_id, status, error_code, error_message, overall_score
                    FROM interview_evaluations
                    WHERE interview_id = ?
                      AND evaluation_version = ?
                      AND turn_id IN ({placeholders})
                """
                params = [interview_id, evaluation_version, *turn_batch]
                cursor.execute(sql, params)
                for row in cursor.fetchall():
                    key = (str(row["interview_id"]).strip(), str(row["turn_id"]).strip())
                    result[key] = dict(row)
    return result


def wait_until_done(
    db_manager: DatabaseManager,
    keys: Sequence[Tuple[str, str]],
    evaluation_version: str,
    timeout_seconds: int,
    poll_interval: float,
) -> Dict:
    start = time.time()
    total = len(keys)
    last_done = -1

    while True:
        status_map = fetch_status_map(db_manager, keys, evaluation_version)
        done = 0
        pending = 0
        missing = 0

        for key in keys:
            row = status_map.get(key)
            if row is None:
                missing += 1
                continue
            status = str(row.get("status") or "").strip()
            if status in FINAL_STATUSES:
                done += 1
            elif status in RUNNING_STATUSES:
                pending += 1
            else:
                pending += 1

        if done != last_done:
            print(f"[wait] done={done}/{total}, pending={pending}, missing={missing}")
            last_done = done

        if done >= total:
            failed = [
                {
                    "interview_id": key[0],
                    "turn_id": key[1],
                    "status": status_map[key].get("status"),
                    "error_code": status_map[key].get("error_code"),
                    "error_message": status_map[key].get("error_message"),
                }
                for key in keys
                if key in status_map and str(status_map[key].get("status") or "").strip() == "failed"
            ]
            return {
                "completed": True,
                "timeout": False,
                "done": done,
                "total": total,
                "failed": failed,
                "elapsed_seconds": round(time.time() - start, 2),
            }

        if (time.time() - start) >= max(1, timeout_seconds):
            unresolved = []
            for key in keys:
                row = status_map.get(key)
                if row is None or str(row.get("status") or "").strip() in RUNNING_STATUSES:
                    unresolved.append(
                        {
                            "interview_id": key[0],
                            "turn_id": key[1],
                            "status": None if row is None else row.get("status"),
                        }
                    )
                elif str(row.get("status") or "").strip() not in FINAL_STATUSES:
                    unresolved.append(
                        {
                            "interview_id": key[0],
                            "turn_id": key[1],
                            "status": row.get("status"),
                        }
                    )
            return {
                "completed": False,
                "timeout": True,
                "done": done,
                "total": total,
                "unresolved": unresolved[:30],
                "elapsed_seconds": round(time.time() - start, 2),
            }

        time.sleep(max(0.2, poll_interval))


def main() -> int:
    args = parse_args()
    should_wait = not args.no_wait
    logger = get_logger("backfill_historical_evaluations")

    db_path = resolve_db_path(args.db)
    db_manager = DatabaseManager(db_path=db_path)

    evaluation_service = EvaluationService(
        db_manager=db_manager,
        rag_service=rag_service,
        llm_manager=llm_manager,
        logger=logger,
    )
    evaluation_version = str(evaluation_service.evaluation_version or "v1").strip() or "v1"

    dialogues = load_dialogues(db_manager, args.interview_id, args.limit)
    if not dialogues:
        print("No interview dialogues found for backfill.")
        return 0

    distinct_interview_ids = sorted({str(item.get("interview_id") or "").strip() for item in dialogues if str(item.get("interview_id") or "").strip()})
    missing_parent_count, parent_rows_written, parent_write_failed_ids = ensure_parent_interviews(
        db_manager,
        distinct_interview_ids,
        dry_run=args.dry_run,
    )

    planned = 0
    skipped_empty_answer = 0
    skipped_existing = 0
    enqueue_failed = 0
    enqueued = 0
    already_inflight = 0
    failed_items: List[Dict] = []
    waiting_keys: List[Tuple[str, str]] = []

    for row in dialogues:
        dialogue_id = int(row.get("id") or 0)
        interview_id = str(row.get("interview_id") or "").strip()
        round_type = str(args.round_type_override or row.get("round_type") or "technical").strip() or "technical"
        question = str(row.get("question") or "").strip()
        answer = str(row.get("answer") or "").strip()

        if not interview_id:
            continue
        if not args.include_empty_answer and not answer:
            skipped_empty_answer += 1
            continue

        turn_id = f"legacy_dialogue_{dialogue_id}"
        planned += 1

        if not args.force:
            existing = db_manager.get_evaluation_record(
                interview_id=interview_id,
                turn_id=turn_id,
                evaluation_version=evaluation_version,
            )
            if existing is not None:
                skipped_existing += 1
                continue

        if args.dry_run:
            continue

        result = evaluation_service.enqueue_evaluation(
            interview_id=interview_id,
            turn_id=turn_id,
            question_id="",
            user_id="default",
            round_type=round_type,
            position=str(args.position or "").strip(),
            question=question,
            answer=answer,
            evaluation_version=evaluation_version,
            force=bool(args.force),
        )

        if not result.get("success"):
            enqueue_failed += 1
            failed_items.append(
                {
                    "interview_id": interview_id,
                    "turn_id": turn_id,
                    "error": result.get("error"),
                    "message": result.get("message"),
                }
            )
            continue

        if result.get("enqueued"):
            enqueued += 1
            waiting_keys.append((interview_id, turn_id))
        else:
            reason = str(result.get("reason") or "")
            if reason == "already_inflight":
                already_inflight += 1
                waiting_keys.append((interview_id, turn_id))
            elif reason == "already_exists":
                skipped_existing += 1

    wait_result = None
    if should_wait and not args.dry_run and waiting_keys:
        wait_result = wait_until_done(
            db_manager=db_manager,
            keys=waiting_keys,
            evaluation_version=evaluation_version,
            timeout_seconds=args.wait_timeout,
            poll_interval=args.poll_interval,
        )

    summary = {
        "db_path": db_path,
        "evaluation_version": evaluation_version,
        "dialogues_loaded": len(dialogues),
        "interviews_in_scope": len(distinct_interview_ids),
        "missing_parent_interview_rows": missing_parent_count,
        "parent_interview_rows_written": parent_rows_written,
        "parent_interview_rows_write_failed": len(parent_write_failed_ids),
        "parent_interview_write_failed_ids": parent_write_failed_ids[:20],
        "planned": planned,
        "dry_run": bool(args.dry_run),
        "force": bool(args.force),
        "wait": bool(should_wait),
        "skipped_empty_answer": skipped_empty_answer,
        "skipped_existing": skipped_existing,
        "already_inflight": already_inflight,
        "enqueued": enqueued,
        "enqueue_failed": enqueue_failed,
        "failed_samples": failed_items[:20],
    }
    if wait_result is not None:
        summary["wait"] = wait_result

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print("===== Backfill Summary =====")
        print(f"db_path: {summary['db_path']}")
        print(f"evaluation_version: {summary['evaluation_version']}")
        print(f"dialogues_loaded: {summary['dialogues_loaded']}")
        print(f"interviews_in_scope: {summary['interviews_in_scope']}")
        print(f"missing_parent_interview_rows: {summary['missing_parent_interview_rows']}")
        print(f"parent_interview_rows_written: {summary['parent_interview_rows_written']}")
        print(f"parent_interview_rows_write_failed: {summary['parent_interview_rows_write_failed']}")
        print(f"planned: {summary['planned']}")
        print(f"dry_run: {summary['dry_run']}")
        print(f"force: {summary['force']}")
        print(f"wait: {summary['wait']}")
        print(f"skipped_empty_answer: {summary['skipped_empty_answer']}")
        print(f"skipped_existing: {summary['skipped_existing']}")
        print(f"already_inflight: {summary['already_inflight']}")
        print(f"enqueued: {summary['enqueued']}")
        print(f"enqueue_failed: {summary['enqueue_failed']}")
        if failed_items:
            print("failed_samples:")
            for item in failed_items[:10]:
                print(
                    f"- interview_id={item.get('interview_id')} turn_id={item.get('turn_id')} "
                    f"error={item.get('error')} message={item.get('message')}"
                )
        if wait_result is not None:
            print("wait_result:")
            print(json.dumps(wait_result, ensure_ascii=False, indent=2))

    if enqueue_failed > 0:
        return 2
    if summary.get("parent_interview_rows_write_failed", 0) > 0:
        return 5
    if wait_result and wait_result.get("timeout"):
        return 3
    if wait_result and wait_result.get("failed"):
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
