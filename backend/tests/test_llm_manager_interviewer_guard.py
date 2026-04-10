import unittest
import types
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

dashscope_stub = types.ModuleType("dashscope")


class _GenerationStub:
    api_key = None


dashscope_stub.Generation = _GenerationStub
dashscope_stub.api_key = None
sys.modules.setdefault("dashscope", dashscope_stub)

config_loader_stub = types.ModuleType("utils.config_loader")
config_loader_stub.config = types.SimpleNamespace(
    get=lambda *args, **kwargs: args[1] if len(args) > 1 else kwargs.get("default")
)
sys.modules.setdefault("utils.config_loader", config_loader_stub)

logger_stub = types.ModuleType("utils.logger")
logger_stub.get_logger = lambda _name: types.SimpleNamespace(
    info=lambda *args, **kwargs: None,
    warning=lambda *args, **kwargs: None,
    error=lambda *args, **kwargs: None,
)
sys.modules.setdefault("utils.logger", logger_stub)

try:
    from backend.utils.llm_manager import LLMManager
except ImportError:  # pragma: no cover
    from utils.llm_manager import LLMManager


class InterviewerGuardTests(unittest.TestCase):
    def test_extracts_candidate_question_from_rag_context(self):
        rag_context = """目标能力：语言特性

1. 候选题：请你解释一下 Java 里的多态，以及重载和重写的区别？
分类：语言基础 / 面向对象
"""
        question = LLMManager._extract_question_from_context(rag_context)
        self.assertEqual(question, "请你解释一下 Java 里的多态，以及重载和重写的区别？")

    def test_rewrites_teaching_style_followup_into_question(self):
        bad_reply = (
            "好的,我们来具体看一下这个例子。假设我们有一个Animal接口,里面有一个makeSound方法。"
            "然后我们创建两个实现了Animal接口的类:Dog和Cat。每个类都重写了makeSound方法。"
            "最后,我们通过Animal类型的引用来调用这些方法。你觉得这个例子清晰吗?"
        )
        repaired = LLMManager._sanitize_interviewer_output(
            bad_reply,
            round_type="technical",
            current_question="请你直接解释一下 Java 里的多态是什么，它在运行时是怎么体现的？",
            user_answer="多态就是父类引用指向子类对象。",
        )
        self.assertEqual(
            repaired,
            "你刚才讲的是概括层面。请继续往下展开一层，具体说明它的底层机制、关键约束，以及实际使用时最容易出错的点？",
        )

    def test_keeps_valid_question(self):
        reply = "你刚才提到了重写，那你再说一下重载和重写在编译期、运行期分别有什么区别？"
        repaired = LLMManager._sanitize_interviewer_output(
            reply,
            round_type="technical",
            current_question="请解释多态。",
        )
        self.assertEqual(repaired, reply)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
