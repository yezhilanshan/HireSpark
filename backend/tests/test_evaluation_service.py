"""
三层评价服务测试
"""
import json
import os
import tempfile
import time
import unittest
from datetime import datetime

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


class _StubLLMScored:
    enabled = True
    model = "mock-scored"

    def evaluate_answer_with_rubric(self, **kwargs):
        round_type = kwargs.get("round_type", "technical")
        dimensions = {
            "technical": {
                "technical_accuracy": {"score": 92, "reason": "solid fundamentals"},
                "knowledge_depth": {"score": 80, "reason": "good depth"},
                "completeness": {"score": 70, "reason": "mostly complete"},
                "logic": {"score": 60, "reason": "structure can improve"},
                "job_match": {"score": 75, "reason": "relevant experience"},
            },
            "hr": {
                "clarity": {"score": 68, "reason": "clear enough"},
                "relevance": {"score": 72, "reason": "mostly relevant"},
                "self_awareness": {"score": 66, "reason": "some reflection"},
                "communication": {"score": 64, "reason": "can be tighter"},
            },
        }
        dimension_scores = dimensions.get(round_type, dimensions["technical"])
        overall_score = sum(item["score"] for item in dimension_scores.values()) / len(dimension_scores)
        return {
            "rubric_eval": {
                "basic_match": 88,
                "good_match": 76,
                "excellent_match": 32,
                "final_level": "good",
                "confidence": 0.82,
                "reason": "overall aligned",
            },
            "dimension_scores": dimension_scores,
            "overall_score": overall_score,
            "summary": {
                "strengths": ["structured answer"],
                "weaknesses": ["logic pacing"],
                "next_actions": ["tighten examples"],
            },
        }


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

    def _ensure_interview(self, interview_id: str):
        now = datetime.now().isoformat()
        result = self.db.save_interview({
            "interview_id": interview_id,
            "start_time": now,
            "end_time": now,
            "duration": 60,
            "max_probability": 0.0,
            "avg_probability": 0.0,
            "risk_level": "LOW",
            "events_count": 0,
            "report_path": "",
        })
        if not result.get("success") and result.get("error") != "Interview ID already exists":
            self.fail(f"failed to create interview fixture: {result}")

    def test_database_upsert_with_evaluation_version(self):
        self._ensure_interview("i_001")
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
        self._ensure_interview("i_async_001")
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
        self._ensure_interview("i_idem_001")
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
        self._ensure_interview("i_skip_001")
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

            self.assertEqual(final_status, "partial_ok")
        finally:
            eval_service.shutdown()

    def test_layer2_keeps_text_scores_even_when_speech_is_available(self):
        self._ensure_interview("i_speech_001")
        self.db.save_or_update_speech_evaluation({
            "interview_id": "i_speech_001",
            "turn_id": "turn_1",
            "answer_session_id": "answer_1",
            "round_type": "technical",
            "final_transcript": "one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty one twenty two",
            "word_timestamps_json": "[]",
            "pause_events_json": "[]",
            "filler_events_json": "[]",
            "speech_metrics_final_json": '{"audio_duration_ms": 12000, "dimensions": {"clarity_score": 90, "fluency_score": 80, "speech_rate_score": 70, "pause_anomaly_score": 60, "filler_frequency_score": 50}}',
            "realtime_metrics_json": "{}",
        })
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            payload = {
                "interview_id": "i_speech_001",
                "turn_id": "turn_1",
                "question_id": "q_1",
                "round_type": "technical",
                "position": "java_backend",
                "question": "Explain a design choice",
                "answer": "Candidate answer",
                "prompt_version": "v1",
                "detection_state": {
                    "has_face": True,
                    "face_count": 1,
                    "off_screen_ratio": 0.1,
                    "rppg_reliable": True,
                    "hr": 78,
                    "risk_score": 18,
                    "flags": [],
                },
            }
            layer2 = eval_service.evaluate_layer2(payload, _StubRAG().evaluate_layer1(question_id="q_1"))
            self.assertAlmostEqual(layer2["text_base_dimension_scores"]["logic"]["score"], 60.0, places=2)
            self.assertAlmostEqual(layer2["final_dimension_scores"]["logic"]["score"], 60.0, places=2)
            self.assertAlmostEqual(layer2["speech_adjustments"]["logic"], 0.0, places=2)
            self.assertAlmostEqual(layer2["final_dimension_scores"]["completeness"]["score"], 70.0, places=2)
            self.assertAlmostEqual(layer2["final_dimension_scores"]["technical_accuracy"]["score"], 92.0, places=2)
            self.assertAlmostEqual(layer2["overall_score_final"], 75.4, places=2)
            self.assertTrue(layer2.get("speech_used"))

            speech_layer = eval_service.evaluate_speech_layer(payload)
            self.assertEqual(speech_layer.get("status"), "ready")
            self.assertAlmostEqual(float(speech_layer.get("overall_score") or 0.0), 75.0, places=2)

            video_layer = eval_service.evaluate_video_layer(payload)
            self.assertEqual(video_layer.get("status"), "ready")
            self.assertTrue(isinstance(video_layer.get("overall_score"), (int, float)))

            evaluation_v2 = eval_service.build_evaluation_v2(
                text_layer=eval_service.build_text_layer_result(layer2),
                speech_layer=speech_layer,
                video_layer=video_layer,
            )
            self.assertEqual(evaluation_v2.get("schema_version"), "evaluation_v2.1")
            self.assertIn("fusion", evaluation_v2)
            self.assertIsNotNone((evaluation_v2.get("fusion") or {}).get("overall_score"))
        finally:
            eval_service.shutdown()

    def test_layer2_keeps_text_scores_when_speech_gate_fails(self):
        self._ensure_interview("i_speech_002")
        self.db.save_or_update_speech_evaluation({
            "interview_id": "i_speech_002",
            "turn_id": "turn_1",
            "answer_session_id": "answer_2",
            "round_type": "technical",
            "final_transcript": "too short",
            "word_timestamps_json": "[]",
            "pause_events_json": "[]",
            "filler_events_json": "[]",
            "speech_metrics_final_json": '{"audio_duration_ms": 3000, "dimensions": {"clarity_score": 95, "fluency_score": 92, "speech_rate_score": 88, "pause_anomaly_score": 85, "filler_frequency_score": 90}}',
            "realtime_metrics_json": "{}",
        })
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            payload = {
                "interview_id": "i_speech_002",
                "turn_id": "turn_1",
                "question_id": "q_2",
                "round_type": "technical",
                "position": "java_backend",
                "question": "Explain a design choice",
                "answer": "Candidate answer",
                "prompt_version": "v1",
            }
            layer2 = eval_service.evaluate_layer2(payload, _StubRAG().evaluate_layer1(question_id="q_2"))

            self.assertFalse(layer2.get("speech_used"))
            self.assertAlmostEqual(layer2["final_dimension_scores"]["logic"]["score"], 60.0, places=2)
            self.assertAlmostEqual(layer2["speech_adjustments"]["logic"], 0.0, places=2)
            self.assertAlmostEqual(layer2["overall_score_final"], layer2["overall_score_base"], places=2)

            speech_layer = eval_service.evaluate_speech_layer(payload)
            self.assertEqual(speech_layer.get("status"), "insufficient_data")
            reasons = ((speech_layer.get("summary") or {}).get("quality_gate") or {}).get("reasons") or []
            self.assertIn("audio_duration_below_threshold", reasons)
            self.assertIn("token_count_below_threshold", reasons)
        finally:
            eval_service.shutdown()

    def test_fusion_contains_explainable_fields_and_rejections(self):
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            text_layer = {
                "status": "ready",
                "overall_score": 80.0,
            }
            speech_layer = {
                "status": "insufficient_data",
                "overall_score": None,
                "summary": {
                    "quality_gate": {
                        "reasons": ["audio_duration_below_threshold"],
                    }
                },
            }
            video_layer = {
                "status": "unavailable",
                "overall_score": None,
                "summary": {
                    "reason": "missing_video_context",
                },
            }

            fusion = eval_service.fuse_layer_scores(text_layer, speech_layer, video_layer)
            self.assertEqual(fusion.get("status"), "ready")
            self.assertIn("layer_scores", fusion)
            self.assertIn("rejection_reasons", fusion)
            self.assertIn("weight_normalization", fusion)
            self.assertIn("calculation_steps", fusion)
            self.assertEqual(float((fusion.get("layer_scores") or {}).get("text", 0.0)), 80.0)
            self.assertIn("delivery", (fusion.get("rejection_reasons") or {}))
            self.assertIn("presence", (fusion.get("rejection_reasons") or {}))
            self.assertGreaterEqual(len(fusion.get("calculation_steps") or []), 1)
            self.assertIn("shortboard_penalty", fusion)
        finally:
            eval_service.shutdown()

    def test_shortboard_penalty_applies_for_low_core_dimension(self):
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            content_layer = {
                "status": "ready",
                "overall_score": 86.0,
                "confidence": 0.95,
                "dimension_scores": {
                    "technical_accuracy": {"score": 42.0, "reason": "核心准确性明显不足"},
                },
            }
            delivery_layer = {
                "status": "ready",
                "overall_score": 88.0,
                "confidence": 0.7,
            }
            presence_layer = {
                "status": "ready",
                "overall_score": 90.0,
                "confidence": 0.6,
            }

            fusion = eval_service.fuse_layer_scores(
                content_layer,
                delivery_layer,
                presence_layer,
                integrity_layer={"status": "ready", "signals": [], "veto": False, "risk_level": "low", "risk_index": 5.0},
                round_type="technical",
            )
            shortboard = fusion.get("shortboard_penalty") or {}

            self.assertTrue(shortboard.get("applied"))
            self.assertLess(float(shortboard.get("coefficient") or 1.0), 1.0)
            self.assertGreater(
                float(fusion.get("overall_score_before_shortboard") or 0.0),
                float(fusion.get("overall_score") or 0.0),
            )
        finally:
            eval_service.shutdown()

    def test_integrity_veto_flags_result_without_zeroing_score(self):
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            fusion = eval_service.fuse_layer_scores(
                {"status": "ready", "overall_score": 80.0, "confidence": 0.9, "dimension_scores": {"technical_accuracy": {"score": 80}}},
                {"status": "ready", "overall_score": 75.0, "confidence": 0.8},
                {"status": "ready", "overall_score": 70.0, "confidence": 0.7},
                integrity_layer={
                    "status": "ready",
                    "risk_level": "high",
                    "risk_index": 92.0,
                    "signals": [{"code": "multi_person", "severity": "critical", "score": 95.0}],
                    "veto": True,
                },
                round_type="technical",
            )
            self.assertEqual(fusion.get("status"), "risk_flagged")
            self.assertTrue(((fusion.get("integrity") or {}).get("veto")))
            self.assertIsNotNone(fusion.get("overall_score"))
        finally:
            eval_service.shutdown()

    def test_async_enqueue_persists_snapshot_and_traces(self):
        self._ensure_interview("i_trace_001")
        eval_service = EvaluationService(
            db_manager=self.db,
            rag_service=_StubRAG(),
            llm_manager=_StubLLMScored(),
        )
        try:
            enqueue = eval_service.enqueue_evaluation(
                interview_id="i_trace_001",
                turn_id="turn_1",
                question_id="q_trace_1",
                user_id="default",
                round_type="technical",
                position="java_backend",
                question="HashMap 原理？",
                answer="底层是数组+链表+红黑树。扩容时会重哈希。",
            )
            self.assertTrue(enqueue.get("success"))

            deadline = time.time() + 10
            final_record = None
            while time.time() < deadline:
                final_record = self.db.get_evaluation_record("i_trace_001", "turn_1", "v1")
                if final_record and str(final_record.get("status", "")).strip() not in {"pending", "running"}:
                    break
                time.sleep(0.2)

            self.assertIsNotNone(final_record)
            self.assertIn(str(final_record.get("status", "")).strip(), {"ok", "partial_ok", "skipped"})

            snapshot_json = str(final_record.get("scoring_snapshot_json") or "{}").strip() or "{}"
            snapshot = json.loads(snapshot_json)
            self.assertIn("evaluation_version", snapshot)
            self.assertIn("layer_weights", snapshot)
            self.assertIn("speech_gate", snapshot)

            layer2_json = str(final_record.get("layer2_json") or "{}").strip() or "{}"
            layer2 = json.loads(layer2_json)
            self.assertIn("dimension_evidence_json", layer2)

            traces = self.db.get_evaluation_traces("i_trace_001", "turn_1")
            self.assertGreaterEqual(len(traces), 6)
            event_types = [str(item.get("event_type") or "") for item in traces]
            for expected in [
                "task_enqueued",
                "task_running",
                "layer1_done",
                "layer2_done",
                "fusion_done",
                "persist_done",
                "task_finished",
            ]:
                self.assertIn(expected, event_types)
        finally:
            eval_service.shutdown()


if __name__ == "__main__":
    unittest.main()
