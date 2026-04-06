"""
评分审计与评分卡接口测试。
"""

import json
import unittest
from unittest.mock import patch

backend_app_module = None
_IMPORT_ERROR = None

try:
    import app as backend_app_module
except Exception as exc_direct:  # pragma: no cover
    try:
        from backend import app as backend_app_module
    except Exception as exc_pkg:  # pragma: no cover
        _IMPORT_ERROR = (exc_direct, exc_pkg)


class _FakeScorecardDB:
    def get_turn_scorecard(self, interview_id: str, turn_id: str):
        if interview_id != "i_trace_api" or turn_id != "turn_1":
            return {
                "interview_id": interview_id,
                "turn_id": turn_id,
                "evaluation": None,
                "speech_evaluation": None,
                "traces": [],
            }

        return {
            "interview_id": interview_id,
            "turn_id": turn_id,
            "evaluation": {
                "interview_id": interview_id,
                "turn_id": turn_id,
                "status": "ok",
                "layer1_json": json.dumps({"status": "ok"}, ensure_ascii=False),
                "layer2_json": json.dumps({"overall_score_final": 78.5}, ensure_ascii=False),
                "text_layer_json": json.dumps({"overall_score": 78.5}, ensure_ascii=False),
                "speech_layer_json": json.dumps({"status": "insufficient_data", "overall_score": None}, ensure_ascii=False),
                "video_layer_json": json.dumps({"overall_score": 82.0}, ensure_ascii=False),
                "fusion_json": json.dumps({"overall_score": 80.2}, ensure_ascii=False),
                "scoring_snapshot_json": json.dumps(
                    {
                        "evaluation_version": "v1",
                        "prompt_version": "v1",
                        "layer_weights": {"text": 0.5, "speech": 0.25, "video": 0.25},
                    },
                    ensure_ascii=False,
                ),
            },
            "speech_evaluation": {
                "interview_id": interview_id,
                "turn_id": turn_id,
                "final_transcript": "候选人回答示例",
                "word_timestamps_json": "[]",
                "pause_events_json": "[]",
                "filler_events_json": "[]",
                "speech_metrics_final_json": json.dumps({"token_count": 32}, ensure_ascii=False),
                "realtime_metrics_json": "{}",
            },
            "traces": [
                {
                    "event_type": "task_enqueued",
                    "status": "pending",
                    "payload_json": json.dumps({"retry_count": 0}, ensure_ascii=False),
                },
                {
                    "event_type": "task_finished",
                    "status": "ok",
                    "payload_json": json.dumps({"retry_count": 0}, ensure_ascii=False),
                },
            ],
        }


class EvaluationTraceApiTestCase(unittest.TestCase):
    def setUp(self):
        if backend_app_module is None:
            self.skipTest(f"flask app unavailable: {_IMPORT_ERROR}")
        self.client = backend_app_module.app.test_client()
        self.fake_db = _FakeScorecardDB()

    def test_trace_endpoint_returns_decoded_snapshot_and_traces(self):
        with patch.object(backend_app_module, "db_manager", self.fake_db):
            response = self.client.get("/api/evaluation/trace/i_trace_api/turn_1")

        self.assertEqual(response.status_code, 200)
        data = response.get_json() or {}
        self.assertTrue(data.get("success"))

        snapshot = data.get("snapshot") or {}
        self.assertEqual(snapshot.get("evaluation_version"), "v1")
        self.assertIn("layer_weights", snapshot)

        trace = data.get("trace") or []
        self.assertGreaterEqual(len(trace), 2)
        self.assertIsInstance((trace[0] or {}).get("payload"), dict)

    def test_scorecard_endpoint_returns_404_when_missing(self):
        with patch.object(backend_app_module, "db_manager", self.fake_db):
            response = self.client.get("/api/evaluation/scorecard/not_found/turn_x")

        self.assertEqual(response.status_code, 404)
        data = response.get_json() or {}
        self.assertFalse(data.get("success"))
        self.assertEqual(data.get("error"), "scorecard not found")


if __name__ == "__main__":
    unittest.main()
