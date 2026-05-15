import unittest

from rag.service import RAGService
from rag.state import InterviewState


class FollowupStyleInferenceTestCase(unittest.TestCase):
    def test_low_basic_coverage_prefers_detail_probe(self):
        service = object.__new__(RAGService)
        state = InterviewState(target_round_type="project")
        analysis_result = {
            "depth": 0.72,
            "correctness": 0.66,
            "coverage": {
                "basic": 0.2,
                "good": 0.15,
                "excellent": 0.0,
            },
            "suggested_followup_type": "",
        }
        style = service._infer_followup_style(state, analysis_result, "")
        self.assertEqual(style, "detail_probe")


if __name__ == "__main__":
    unittest.main()
