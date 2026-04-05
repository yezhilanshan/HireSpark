"""
即时报告接口测试：覆盖去重与事件时间标准化。
"""

import json
import unittest
from datetime import datetime
from unittest.mock import patch

try:
    import app as backend_app_module
except Exception:  # pragma: no cover - 兼容从仓库根目录执行
    from backend import app as backend_app_module


class _FakeDBManager:
    def __init__(self, start_time_iso: str):
        self.start_time_iso = start_time_iso
        self._start_epoch = float(datetime.fromisoformat(start_time_iso).timestamp())

    def get_interview_by_id(self, interview_id):
        if interview_id != "i_api_001":
            return None
        return {
            "interview_id": "i_api_001",
            "start_time": self.start_time_iso,
            "end_time": "2026-04-04T10:06:00",
            "duration": 360,
            "max_probability": 66.0,
            "avg_probability": 24.0,
            "risk_level": "MEDIUM",
            "events_count": 2,
            "report_path": "",
        }

    def get_statistics_by_interview(self, interview_id):
        return {
            "interview_id": interview_id,
            "total_deviations": 3,
            "total_mouth_open": 1,
            "total_multi_person": 0,
            "off_screen_ratio": 12.5,
            "frames_processed": 1800,
        }

    def get_interview_dialogues(self, interview_id):
        return [
            {
                "interview_id": interview_id,
                "turn_id": "t1",
                "round_type": "technical",
                "question": "解释一下 HashMap 在高并发下的风险。",
                "answer": "会有并发问题，可能出现链表冲突。",
                "created_at": "2026-04-04T10:01:00",
            },
            {
                "interview_id": interview_id,
                "turn_id": "t2",
                "round_type": "technical",
                "question": "如何优化数据库慢查询？",
                "answer": "先分析执行计划，再做索引和缓存。",
                "created_at": "2026-04-04T10:03:00",
            },
        ]

    def get_events(self, interview_id):
        return [
            {
                "event_type": "gaze_deviation",
                "score": 60,
                "description": "candidate looked away from screen",
                "timestamp": self._start_epoch + 12.5,
            },
            {
                "event_type": "mouth_open",
                "score": 20,
                "description": "possible external communication",
                "timestamp": self._start_epoch + 30,
            },
        ]

    def get_interview_evaluations(self, interview_id, evaluation_version=None):
        layer1 = {
            "key_points": {
                "covered": ["并发风险"],
                "missing": ["扩容代价"],
                "coverage_ratio": 0.5,
            },
            "signals": {
                "hit": ["并发风险"],
                "red_flags": ["缺少性能数据支撑"],
            },
        }
        layer2_v1 = {
            "overall_score_final": 40,
            "final_dimension_scores": {
                "logic": {"score": 40, "reason": "结构不清晰，先后顺序混乱"},
                "technical_accuracy": {"score": 55, "reason": "技术描述不够准确"},
            },
        }
        layer2_v2 = {
            "overall_score_final": 80,
            "final_dimension_scores": {
                "logic": {"score": 82, "reason": "结构更完整"},
                "technical_accuracy": {"score": 78, "reason": "技术点覆盖较好"},
            },
        }
        layer2_t2 = {
            "overall_score_final": 60,
            "final_dimension_scores": {
                "logic": {"score": 58, "reason": "结论先给出但论证偏弱"},
                "clarity": {"score": 62, "reason": "表达尚可但重点不够突出"},
            },
        }

        return [
            {
                "interview_id": interview_id,
                "turn_id": "t1",
                "question": "解释一下 HashMap 在高并发下的风险。",
                "answer": "会有并发问题，可能出现链表冲突。",
                "round_type": "technical",
                "status": "ok",
                "evaluation_version": "v1",
                "layer1_json": json.dumps(layer1, ensure_ascii=False),
                "layer2_json": json.dumps(layer2_v1, ensure_ascii=False),
                "overall_score": 40,
            },
            {
                "interview_id": interview_id,
                "turn_id": "t1",
                "question": "解释一下 HashMap 在高并发下的风险。",
                "answer": "会有并发问题，可能出现链表冲突。",
                "round_type": "technical",
                "status": "ok",
                "evaluation_version": "v2",
                "layer1_json": json.dumps(layer1, ensure_ascii=False),
                "layer2_json": json.dumps(layer2_v2, ensure_ascii=False),
                "overall_score": 80,
            },
            {
                "interview_id": interview_id,
                "turn_id": "t1",
                "question": "解释一下 HashMap 在高并发下的风险。",
                "answer": "会有并发问题，可能出现链表冲突。",
                "round_type": "technical",
                "status": "running",
                "evaluation_version": "v3",
                "layer1_json": json.dumps(layer1, ensure_ascii=False),
                "layer2_json": json.dumps({"overall_score_final": 20}, ensure_ascii=False),
                "overall_score": 20,
            },
            {
                "interview_id": interview_id,
                "turn_id": "t2",
                "question": "如何优化数据库慢查询？",
                "answer": "先分析执行计划，再做索引和缓存。",
                "round_type": "technical",
                "status": "ok",
                "evaluation_version": "v1",
                "layer1_json": json.dumps(layer1, ensure_ascii=False),
                "layer2_json": json.dumps(layer2_t2, ensure_ascii=False),
                "overall_score": 60,
            },
            {
                "interview_id": interview_id,
                "turn_id": "t2",
                "question": "如何优化数据库慢查询？",
                "answer": "先分析执行计划，再做索引和缓存。",
                "round_type": "technical",
                "status": "partial_ok",
                "evaluation_version": "v2",
                "layer1_json": json.dumps(layer1, ensure_ascii=False),
                "layer2_json": json.dumps({"overall_score_final": 30}, ensure_ascii=False),
                "overall_score": 30,
            },
        ]

    def get_speech_evaluations(self, interview_id, start_time=None, end_time=None):
        return []


class ImmediateReportApiTestCase(unittest.TestCase):
    def setUp(self):
        self.client = backend_app_module.app.test_client()
        self.fake_db = _FakeDBManager(start_time_iso="2026-04-04T10:00:00")

    def test_report_api_deduplicates_turn_versions(self):
        with patch.object(backend_app_module, "db_manager", self.fake_db):
            response = self.client.get("/api/report/interview/i_api_001")

        self.assertEqual(response.status_code, 200)
        data = response.get_json() or {}
        self.assertTrue(data.get("success"))
        report = data.get("report") or {}

        structured = report.get("structured_evaluation") or {}
        # t1 仅保留最新评估(v2=80) + t2(60) => 70
        self.assertAlmostEqual(float(structured.get("overall_score") or 0.0), 70.0, places=2)
        self.assertEqual(int(structured.get("evaluated_questions") or 0), 2)

        content = report.get("content_performance") or {}
        self.assertEqual(int((content.get("scoring_basis") or {}).get("sample_size") or 0), 2)
        self.assertEqual(len(content.get("question_evidence") or []), 2)
        # t2 的 partial_ok(30) 不应覆盖 ok(60)
        evidence_scores = [float(item.get("overall_score") or 0.0) for item in (content.get("question_evidence") or [])]
        self.assertIn(60.0, evidence_scores)
        self.assertNotIn(30.0, evidence_scores)

        evaluation_v2 = report.get("evaluation_v2") or {}
        self.assertIn(evaluation_v2.get("status"), {"ready", "partial"})
        self.assertIn("layers", evaluation_v2)
        self.assertIn("fusion", evaluation_v2)
        self.assertIn("text", evaluation_v2.get("layers") or {})
        self.assertIn("speech", evaluation_v2.get("layers") or {})
        self.assertIn("video", evaluation_v2.get("layers") or {})

        weak_dims = content.get("weak_dimensions") or []
        self.assertTrue(any("结构" in (item.get("reason_tags") or []) for item in weak_dims))

        question_evidence = content.get("question_evidence") or []
        self.assertTrue(any("表达" in (item.get("reason_tags") or []) for item in question_evidence))

    def test_report_api_normalizes_event_timestamp(self):
        with patch.object(backend_app_module, "db_manager", self.fake_db):
            response = self.client.get("/api/report/interview/i_api_001")

        self.assertEqual(response.status_code, 200)
        data = response.get_json() or {}
        report = data.get("report") or {}
        anti_cheat = report.get("anti_cheat") or {}
        top_events = anti_cheat.get("top_risk_events") or []
        self.assertGreaterEqual(len(top_events), 1)

        # 第一条高风险事件应被标准化为“会话内偏移秒”
        first_ts = float(top_events[0].get("timestamp") or 0.0)
        self.assertAlmostEqual(first_ts, 12.5, places=1)


if __name__ == "__main__":
    unittest.main()
