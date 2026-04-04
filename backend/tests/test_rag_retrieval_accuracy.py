"""
RAG 检索准确率测试。

运行方式：
- python backend/run_tests.py tests.test_rag_retrieval_accuracy
- 或：python -m unittest backend.tests.test_rag_retrieval_accuracy

可选环境变量：
- RAG_ACCURACY_SAMPLE: 抽样题目数，默认 30（0 表示全量）
- RAG_FORCE_REBUILD: 是否强制重建索引（1/0），默认 0
- RAG_MIN_TOP1_HIT_RATE: Top1 命中率阈值，默认 0.8
- RAG_MIN_TOPK_HIT_RATE: TopK 命中率阈值，默认 0.95
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path
from typing import Any, Dict, List

from rag.service import rag_service


class TestRAGRetrievalAccuracy(unittest.TestCase):
    """验证 interview_knowledge 的检索准确率。"""

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()

        if not rag_service.enabled:
            raise unittest.SkipTest("RAG 未启用，跳过检索准确率测试")

        cls.source_path = cls._resolve_source_path("backend/interview_knowledge")

        force_rebuild = os.getenv("RAG_FORCE_REBUILD", "0").strip() in {"1", "true", "True"}
        if force_rebuild:
            rag_service.build_index(source_path=cls.source_path, rebuild=True)

        if not rag_service.ensure_ready():
            raise unittest.SkipTest("RAG 未就绪，无法执行检索准确率测试")

        records = cls._load_records(cls.source_path)
        cls.cases = cls._select_cases(records)

        if not cls.cases:
            raise unittest.SkipTest("没有可用于测试的题目样本")

    @staticmethod
    def _resolve_source_path(source: str) -> str:
        raw = Path(source)
        if raw.is_absolute():
            return str(raw)

        project_root = Path(__file__).resolve().parents[2]
        backend_root = Path(__file__).resolve().parents[1]
        candidates = [Path.cwd() / raw, backend_root / raw, project_root / raw]

        for candidate in candidates:
            if candidate.exists():
                return str(candidate.resolve())

        return str((project_root / raw).resolve())

    @staticmethod
    def _load_records(source_path: str) -> List[Dict[str, Any]]:
        raw_records = rag_service._load_records(source_path=source_path)
        normalized = [
            rag_service._normalize_record(record, idx)
            for idx, record in enumerate(raw_records, start=1)
        ]
        return normalized

    @staticmethod
    def _select_cases(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        # 避免重复 ID 导致评估偏差：同一 ID 只保留首条记录。
        unique_by_id: Dict[str, Dict[str, Any]] = {}
        for item in records:
            item_id = str(item.get("id", "")).strip()
            question = str(item.get("question", "")).strip()
            if not item_id or not question:
                continue
            if item_id not in unique_by_id:
                unique_by_id[item_id] = item

        selected = list(unique_by_id.values())
        sample = int(os.getenv("RAG_ACCURACY_SAMPLE", "30"))
        if sample > 0:
            selected = selected[:sample]
        return selected

    @staticmethod
    def _is_expected_id(retrieved_id: str, expected_id: str) -> bool:
        base_id = str(retrieved_id or "").split("#")[0]
        return base_id == expected_id or base_id.startswith(f"{expected_id}__dup")

    def test_question_retrieval_accuracy(self) -> None:
        top_k = 5
        total = 0
        top1_hits = 0
        topk_hits = 0
        misses: List[str] = []

        for case in self.cases:
            expected_id = str(case.get("id", "")).strip()
            query = str(case.get("question", "")).strip()
            position = str(case.get("position", "")).strip() or None
            round_type = str(case.get("round_type", "")).strip() or None

            metadata_filters = {"round_type": round_type} if round_type else None
            results = rag_service.retrieve_questions(
                query=query,
                position=position,
                top_k=top_k,
                metadata_filters=metadata_filters,
            )

            total += 1
            if not results:
                misses.append(f"[NO_RESULT] {expected_id} | {query}")
                continue

            rank = None
            for idx, item in enumerate(results, start=1):
                if self._is_expected_id(item.get("id", ""), expected_id):
                    rank = idx
                    break

            if rank == 1:
                top1_hits += 1
            if rank is not None:
                topk_hits += 1
            else:
                top = results[0]
                misses.append(
                    f"[MISS] {expected_id} | top={top.get('id')} | q={query[:60]}"
                )

        self.assertGreater(total, 0, "没有统计到任何测试样本")

        top1_rate = top1_hits / total
        topk_rate = topk_hits / total

        min_top1 = float(os.getenv("RAG_MIN_TOP1_HIT_RATE", "0.8"))
        min_topk = float(os.getenv("RAG_MIN_TOPK_HIT_RATE", "0.95"))

        self.assertGreaterEqual(
            top1_rate,
            min_top1,
            msg=(
                f"Top1 命中率不达标: {top1_rate:.4f} < {min_top1:.4f}; "
                f"TopK={topk_rate:.4f}; 样本={total}; 失败示例={misses[:5]}"
            ),
        )
        self.assertGreaterEqual(
            topk_rate,
            min_topk,
            msg=(
                f"TopK 命中率不达标: {topk_rate:.4f} < {min_topk:.4f}; "
                f"Top1={top1_rate:.4f}; 样本={total}; 失败示例={misses[:5]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
