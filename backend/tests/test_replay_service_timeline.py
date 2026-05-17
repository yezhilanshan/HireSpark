import json
import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

try:
    from backend.utils.replay_service import ReplayService
except Exception:  # pragma: no cover
    from utils.replay_service import ReplayService


class _ReplayPayloadDB:
    def get_interview_dialogues(self, interview_id):
        return [
            {
                "interview_id": interview_id,
                "turn_id": "turn_2",
                "question": "项目里什么时候会在 Java 和其他语言之间做选择？",
                "answer": "我会根据生态和团队维护成本选择。",
                "created_at": "2026-05-17 10:00:02",
            },
            {
                "interview_id": interview_id,
                "turn_id": "turn_3",
                "question": "如何防止重复支付？",
                "answer": "用幂等键、状态机和锁控制。",
                "created_at": "2026-05-17 10:00:03",
            },
        ]

    def get_interview_evaluations(self, interview_id=None, **kwargs):
        return []

    def get_speech_evaluations(self, interview_id):
        return []

    def get_interview_turn_timelines(self, interview_id):
        return [
            {"interview_id": interview_id, "turn_id": "turn_1", "question_start_ms": 17000, "question_end_ms": 18000, "answer_start_ms": 0, "answer_end_ms": 0, "latency_ms": 0, "source": "runtime"},
            {"interview_id": interview_id, "turn_id": "turn_2", "question_start_ms": 95000, "question_end_ms": 97000, "answer_start_ms": 101000, "answer_end_ms": 118000, "latency_ms": 4000, "source": "runtime"},
            {"interview_id": interview_id, "turn_id": "turn_3", "question_start_ms": 123000, "question_end_ms": 126000, "answer_start_ms": 132000, "answer_end_ms": 158000, "latency_ms": 6000, "source": "runtime"},
            {"interview_id": interview_id, "turn_id": "turn_4", "question_start_ms": 196000, "question_end_ms": 197000, "answer_start_ms": 0, "answer_end_ms": 0, "latency_ms": 0, "source": "runtime"},
        ]

    def get_timeline_tags(self, interview_id):
        return []

    def get_deep_audit(self, interview_id):
        return None

    def get_shadow_answers(self, interview_id, version=None):
        return []

    def get_visual_metrics(self, interview_id):
        return {
            "latency_matrix_json": json.dumps({"items": [{"turn_id": f"turn_{idx}", "latency_ms": 0} for idx in range(1, 5)]}),
            "keyword_coverage_json": "{}",
            "speech_tone_json": "{}",
            "radar_json": "[]",
            "heatmap_json": "[]",
        }


class ReplayServiceTimelineTestCase(unittest.TestCase):
    def test_build_turn_timeline_uses_actual_dialogue_turns_not_orphan_runtime_rows(self):
        service = ReplayService(db_manager=object())

        rows = service._build_turn_timeline(
            "i_replay",
            dialogues=_ReplayPayloadDB().get_interview_dialogues("i_replay"),
            speech_rows=[],
            existing=_ReplayPayloadDB().get_interview_turn_timelines("i_replay"),
        )

        self.assertEqual([item["turn_id"] for item in rows], ["turn_2", "turn_3"])
        self.assertEqual(rows[0]["question_start_ms"], 95000)
        self.assertEqual(rows[1]["answer_end_ms"], 158000)

    def test_build_turn_timeline_backfills_missing_dialogue_turn(self):
        service = ReplayService(db_manager=object())

        rows = service._build_turn_timeline(
            "i_replay",
            dialogues=[
                {"interview_id": "i_replay", "turn_id": "turn_1", "question": "第一题", "answer": "回答一", "created_at": "1"},
                {"interview_id": "i_replay", "turn_id": "turn_2", "question": "第二题", "answer": "回答二", "created_at": "2"},
            ],
            speech_rows=[
                {
                    "turn_id": "turn_2",
                    "word_timestamps": [{"start_ms": 0, "end_ms": 500}, {"start_ms": 600, "end_ms": 1800}],
                    "speech_metrics_final": {},
                }
            ],
            existing=[
                {"interview_id": "i_replay", "turn_id": "turn_1", "question_start_ms": 0, "question_end_ms": 1200, "answer_start_ms": 1600, "answer_end_ms": 4600, "latency_ms": 400, "source": "runtime"},
            ],
        )

        self.assertEqual([item["turn_id"] for item in rows], ["turn_1", "turn_2"])
        self.assertEqual(rows[1]["source"], "heuristic_backfill")
        self.assertAlmostEqual(rows[1]["answer_end_ms"] - rows[1]["answer_start_ms"], 1800.0)

    def test_build_replay_payload_filters_orphan_anchors_and_refreshes_visual_metrics(self):
        service = ReplayService(db_manager=_ReplayPayloadDB())

        payload = service.build_replay_payload("i_replay")

        anchors = payload["transcript_anchor_list"]
        self.assertEqual([item["turn_id"] for item in anchors], ["turn_2", "turn_3"])
        self.assertTrue(all(item["question"] for item in anchors))
        self.assertEqual(len(payload["visual_metrics"]["latency_matrix"]["items"]), 2)


if __name__ == "__main__":
    unittest.main()
