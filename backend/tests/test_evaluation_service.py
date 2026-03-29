"""
三层评价服务测试
"""
import os
import tempfile
import time
import unittest

from database import DatabaseManager
from rag.service import RAGService
from utils.evaluation_service import EvaluationService


class _FakeEmbedder:
    def encode(self, text):
        content = str(text or "")
        if "扩容机制" in content:
            return [1.0, 0.0, 0.0]
        if "容量翻倍" in content:
            return [0.99, 0.01, 0.0]
        if "哈希冲突" in content:
            return [0.0, 1.0, 0.0]
        return [0.0, 0.0, 1.0]


class _StubRAG:
    enabled = True

    def evaluate_layer1(self, **kwargs):
        return {
            "status": "ok",
            "error_code": "",
            "question_id": kwargs.get("question_id", ""),
            "matched_rubric_id": "rubric_001",
            "rubric_version": "unknown",
            "scoring_rubric": {
                "basic": ["基础点"],
                "good": ["进阶点"],
                "excellent": ["高阶点"],
            },
            "key_points": {
                "covered": [{"point": "基础点", "strategies": ["exact"]}],
                "missing": ["进阶点"],
                "coverage_ratio": 0.5,
            },
            "rubric_match": {"basic": 1.0, "good": 0.5, "excellent": 0.0},
            "signals": {"hit": ["基础点"], "red_flags": []},
        }


class _StubLLMDisabled:
    enabled = False
    model = "mock-disabled"


class _StubRAGSkipped:
    enabled = True

    def evaluate_layer1(self, **kwargs):
        return {
            "status": "skipped",
            "error_code": "RUBRIC_NOT_FOUND",
            "question_id": kwargs.get("question_id", ""),
            "matched_rubric_id": "",
            "rubric_version": "unknown",
            "key_points": {"covered": [], "missing": [], "coverage_ratio": 0.0},
            "rubric_match": {"basic": 0.0, "good": 0.0, "excellent": 0.0},
            "signals": {"hit": [], "red_flags": []},
        }


class EvaluationServiceTestCase(unittest.TestCase):
    def setUp(self):
        fd, self.db_path = tempfile.mkstemp(prefix="eval_service_", suffix=".db")
        os.close(fd)
        self.db = DatabaseManager(self.db_path)

    def tearDown(self):
        try:
            os.remove(self.db_path)
        except Exception:
            pass

    def test_database_upsert_with_evaluation_version(self):
        base_payload = {
            "interview_id": "i_001",
            "turn_id": "t_001",
            "question_id": "q_001",
            "user_id": "u_001",
            "round_type": "technical",
            "position": "java_backend",
            "question": "Q",
            "answer": "A",
            "evaluation_version": "v1",
            "rubric_version": "rv1",
            "prompt_version": "pv1",
            "llm_model": "qwen-max",
            "eval_task_key": "k_1",
            "status": "pending",
            "layer1_json": "{}",
            "layer2_json": "{}",
            "overall_score": 50,
            "confidence": 0.5,
        }

        result = self.db.save_or_update_evaluation(base_payload)
        self.assertTrue(result.get("success"))
        result = self.db.save_or_update_evaluation({**base_payload, "status": "ok", "overall_score": 88})
        self.assertTrue(result.get("success"))

        records_v1 = self.db.get_interview_evaluations("i_001", evaluation_version="v1")
        self.assertEqual(len(records_v1), 1)
        self.assertEqual(records_v1[0]["status"], "ok")
        self.assertEqual(float(records_v1[0]["overall_score"]), 88.0)

        result = self.db.save_or_update_evaluation({
            **base_payload,
            "evaluation_version": "v2",
            "eval_task_key": "k_2",
            "status": "ok",
            "overall_score": 92,
        })
        self.assertTrue(result.get("success"))
        records_all = self.db.get_interview_evaluations("i_001")
        self.assertEqual(len(records_all), 2)

    def test_layer1_alias_and_semantic_match(self):
        service = RAGService()
        service.get_rubric = lambda question_id: {
            "id": "r_001",
            "source_id": question_id,
            "rubric_version": "rv_test",
            "key_points": ["扩容机制"],
            "expected_answer_signals": [],
            "common_mistakes": [],
            "scoring_rubric": {"basic": ["扩容机制"], "good": [], "excellent": []},
            "aliases": {"扩容机制": ["容量翻倍"]},
        }
        service.embedder = _FakeEmbedder()

        result_alias = service.evaluate_layer1(
            question_id="q_100",
            candidate_answer="一般会在容量翻倍时进行重分配。",
            current_question="请解释HashMap扩容机制",
            position="java_backend",
            round_type="technical",
            semantic_threshold=0.7,
        )
        self.assertEqual(result_alias.get("status"), "ok")
        covered = result_alias.get("key_points", {}).get("covered", [])
        self.assertTrue(covered)
        self.assertIn("alias", covered[0].get("strategies", []))

        # 只保留语义匹配，不给 aliases
        service.get_rubric = lambda question_id: {
            "id": "r_002",
            "source_id": question_id,
            "rubric_version": "rv_test",
            "key_points": ["扩容机制"],
            "expected_answer_signals": [],
            "common_mistakes": [],
            "scoring_rubric": {"basic": ["扩容机制"], "good": [], "excellent": []},
            "aliases": {},
        }
        result_semantic = service.evaluate_layer1(
            question_id="q_101",
            candidate_answer="一般会在容量翻倍时进行重分配。",
            current_question="请解释HashMap扩容机制",
            position="java_backend",
            round_type="technical",
            semantic_threshold=0.7,
        )
        covered_semantic = result_semantic.get("key_points", {}).get("covered", [])
        self.assertTrue(covered_semantic)
        self.assertIn("semantic", covered_semantic[0].get("strategies", []))

    def test_async_enqueue_partial_ok_when_llm_unavailable(self):
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMDisabled(),
        )
        try:
            enqueue = eval_service.enqueue_evaluation(
                interview_id="i_async_001",
                turn_id="turn_1",
                question_id="q_async_1",
                user_id="default",
                round_type="technical",
                position="java_backend",
                question="HashMap 原理？",
                answer="底层是数组加链表和红黑树。",
            )
            self.assertTrue(enqueue.get("success"))

            deadline = time.time() + 8
            final_status = None
            while time.time() < deadline:
                records = self.db.get_interview_evaluations("i_async_001")
                if records:
                    final_status = records[-1].get("status")
                    if final_status not in {"pending", "running"}:
                        break
                time.sleep(0.15)

            self.assertEqual(final_status, "partial_ok")
        finally:
            eval_service.shutdown()

    def test_enqueue_idempotent_when_record_exists(self):
        self.db.save_or_update_evaluation({
            "interview_id": "i_idem_001",
            "turn_id": "turn_1",
            "question_id": "q_1",
            "user_id": "default",
            "round_type": "technical",
            "position": "java_backend",
            "question": "Q",
            "answer": "A",
            "evaluation_version": "v1",
            "rubric_version": "unknown",
            "prompt_version": "v1",
            "llm_model": "qwen-max",
            "eval_task_key": "k_idem_001",
            "status": "ok",
            "layer1_json": "{}",
            "layer2_json": "{}",
        })
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMDisabled(),
        )
        try:
            result = eval_service.enqueue_evaluation(
                interview_id="i_idem_001",
                turn_id="turn_1",
                question_id="q_1",
                user_id="default",
                round_type="technical",
                position="java_backend",
                question="Q",
                answer="A",
                evaluation_version="v1",
            )
            self.assertTrue(result.get("success"))
            self.assertFalse(result.get("enqueued"))
            self.assertEqual(result.get("reason"), "already_exists")
        finally:
            eval_service.shutdown()

    def test_async_enqueue_skipped_when_rubric_missing(self):
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAGSkipped(),
            llm_manager=_StubLLMDisabled(),
        )
        try:
            enqueue = eval_service.enqueue_evaluation(
                interview_id="i_skip_001",
                turn_id="turn_1",
                question_id="q_skip_1",
                user_id="default",
                round_type="technical",
                position="java_backend",
                question="不存在的题目",
                answer="我不确定",
            )
            self.assertTrue(enqueue.get("success"))

            deadline = time.time() + 8
            final_status = None
            while time.time() < deadline:
                records = self.db.get_interview_evaluations("i_skip_001")
                if records:
                    final_status = records[-1].get("status")
                    if final_status not in {"pending", "running"}:
                        break
                time.sleep(0.15)

            self.assertEqual(final_status, "skipped")
        finally:
            eval_service.shutdown()


if __name__ == "__main__":
    unittest.main()
