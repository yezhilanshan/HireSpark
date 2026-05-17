import types
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


class _FakeRAGForSwitchFallback:
    enabled = True

    @staticmethod
    def update_interview_state_from_analysis(session_state, analysis_result):
        return dict(session_state or {})

    @staticmethod
    def decide_followup(question_id, analysis_result, session_state):
        return {
            "next_action": "switch_question",
            "followup_type": "switch_topic",
            "followup_question": "",
            "difficulty_target": "hard",
            "followup_style": "detail_probe",
        }

    @staticmethod
    def get_next_question(session_state, top_k=2):
        return {"candidate_questions": []}

    @staticmethod
    def format_question_plan(question_plan):
        return ""

    @staticmethod
    def format_followup_decision(decision):
        return "策略决策：ask_followup"


class _FakeLLMForSwitchFallback:
    @staticmethod
    def process_answer_with_round(**kwargs):
        return "你刚才的回答还比较概括，请补充一个具体实现细节？"


class _FakeRAGForQuestionTextAnalysis:
    enabled = True

    def __init__(self):
        self.analyze_kwargs = None

    def analyze_answer(self, **kwargs):
        self.analyze_kwargs = kwargs
        return {
            "question_id": "",
            "matched_rubric_id": "q_by_text",
            "coverage": {"basic": 0.5, "good": 0.0, "excellent": 0.0},
            "correctness": 0.4,
            "depth": 0.3,
            "confidence": 0.6,
            "followups": [],
            "recommended_followup_ids": [],
        }

    @staticmethod
    def format_analysis_result(analysis_result):
        return "analysis-context"

    @staticmethod
    def build_answer_context(**kwargs):
        return "reference-context"


class InterviewQuestionPolicyTestCase(unittest.TestCase):
    def setUp(self):
        if backend_app_module is None:
            self.skipTest(f"flask app unavailable: {_IMPORT_ERROR}")

    def test_switch_failure_downgrades_to_followup_and_keeps_plan(self):
        current_plan = {
            "candidate_questions": [{"id": "q_current", "question": "请解释一下线程池参数怎么配置？"}]
        }
        analysis_result = {
            "question_id": "q_current",
            "coverage": {"basic": 0.1, "good": 0.0, "excellent": 0.0},
            "correctness": 0.2,
            "depth": 0.2,
            "followups": [],
            "recommended_followup_ids": [],
        }

        with (
            patch.object(backend_app_module, "rag_service", _FakeRAGForSwitchFallback()),
            patch.object(backend_app_module, "llm_manager", _FakeLLMForSwitchFallback()),
            patch.object(
                backend_app_module,
                "_build_answer_rag_context",
                return_value=("analysis-context", analysis_result),
            ),
        ):
            feedback, _analysis, decision, _next_state, next_plan = backend_app_module._generate_policy_response(
                user_answer="我知道线程池可以限制并发。",
                current_question="请解释一下线程池参数怎么配置？",
                position="java_backend",
                round_type="technical",
                chat_history=[],
                difficulty="medium",
                interview_state={"target_round_type": "technical"},
                question_plan=current_plan,
            )

        self.assertTrue(str(feedback).strip())
        self.assertEqual(str((decision or {}).get("next_action")), "ask_followup")
        self.assertTrue(bool((decision or {}).get("switch_fallback")))
        self.assertEqual(next_plan, current_plan)

    def test_auto_end_uses_topic_question_count_not_interaction_count(self):
        runtime = types.SimpleNamespace(
            topic_question_count=1,
            formal_question_count=9,
            auto_end_min_questions=3,
            auto_end_max_questions=8,
        )
        should_end, decision = backend_app_module._should_auto_end_interview(runtime, "turn_9")
        self.assertFalse(should_end)
        self.assertEqual(decision.get("reason"), "below_min_questions")
        self.assertEqual(decision.get("question_count"), 1)
        self.assertEqual(decision.get("topic_question_count"), 1)
        self.assertEqual(decision.get("interaction_question_count"), 9)

    def test_extract_runtime_question_core_strips_transition_prefix(self):
        text = "这个点先到这里，我们换一个方向。\n\n请你讲讲线程池的拒绝策略有哪些？"
        extracted = backend_app_module._extract_runtime_question_core(text)
        self.assertEqual(extracted, "请你讲讲线程池的拒绝策略有哪些？")

    def test_extract_runtime_question_core_prefers_last_question_clause(self):
        text = "你刚才对线程池参数说得比较概括，可以补充一下阻塞队列如何影响拒绝策略吗？"
        extracted = backend_app_module._extract_runtime_question_core(text)
        self.assertEqual(extracted, "可以补充一下阻塞队列如何影响拒绝策略吗？")

    def test_answer_rag_context_analyzes_by_question_text_without_plan_id(self):
        fake_rag = _FakeRAGForQuestionTextAnalysis()

        with patch.object(backend_app_module, "rag_service", fake_rag):
            context, analysis = backend_app_module._build_answer_rag_context(
                position="java_backend",
                round_type="technical",
                current_question="请解释一下线程池参数怎么配置？",
                user_answer="核心线程数和队列会影响并发与拒绝策略。",
                interview_state={"target_round_type": "technical"},
                question_plan=None,
            )

        self.assertIn("analysis-context", context)
        self.assertIn("reference-context", context)
        self.assertEqual(analysis.get("matched_rubric_id"), "q_by_text")
        self.assertIsNone(fake_rag.analyze_kwargs.get("question_id"))
        self.assertEqual(fake_rag.analyze_kwargs.get("current_question"), "请解释一下线程池参数怎么配置？")


if __name__ == "__main__":
    unittest.main()
