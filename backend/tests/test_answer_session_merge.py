import unittest

from backend.utils.answer_session import (
    build_live_answer_text,
    dedupe_answer_text,
    merge_answer_text,
    stabilize_realtime_asr_text,
)


class AnswerSessionMergeTestCase(unittest.TestCase):
    def test_merge_prefers_single_revision_for_high_overlap_text(self):
        draft = (
            "在我的个人开源项目里，主要用到了 Spring Boot starter 组件，"
            "spring boot starter web 构建 web 接口，spring boot starter data redis 操作 redis 做缓存，"
            "mybatis spring boot starter 操作数据库，spring boot starter aop 统一日志，接口耗时统计。"
        )
        rewritten = (
            "在我的个人开源项目里，主要用到了 Spring Boot starter 组件，"
            "spring boot starter web 构建 web 接口，spring boot starter data redis 操作 redis 做缓存，"
            "mybatis spring boot starter 操作数据库，spring boot starter aop 做统一日志，接口耗时统计。"
        )

        merged = merge_answer_text(draft, rewritten)

        self.assertIn(merged, {draft, rewritten})
        self.assertEqual(merged.count("在我的个人开源项目里"), 1)

    def test_merge_keeps_true_continuation(self):
        first = "我在项目里主要用了 Spring Boot 和 Redis。"
        second = "然后我再用 MyBatis 处理数据库访问。"

        merged = merge_answer_text(first, second)

        self.assertIn(first, merged)
        self.assertIn(second, merged)
        self.assertEqual(merged.count("Redis"), 1)

    def test_dedupe_collapses_adjacent_near_duplicate_sentences(self):
        text = (
            "少量配置，自动配置提供了默认值，不只需要覆盖相关配置，如地址、端口、账号密码，其余全部使用默认配置，极大减少了配置量。"
            "少量配置，自动配置提供了默认值，不只需要覆盖相关配置，如地址、端口、账号密码，其余全部使用默认配置，极大减少了配置质量。"
        )

        deduped = dedupe_answer_text(text)

        self.assertIn("少量配置，自动配置提供了默认值", deduped)
        self.assertEqual(deduped.count("少量配置，自动配置提供了默认值"), 1)

    def test_stabilize_realtime_asr_text_collapses_long_single_char_runs(self):
        self.assertEqual(stabilize_realtime_asr_text("我我我我再再试试"), "我再再试试")
        self.assertEqual(stabilize_realtime_asr_text("轻轻试试"), "轻轻试试")

    def test_build_live_answer_text_ignores_tiny_partial_after_final(self):
        draft = "我已经说完这句话。"
        merged = build_live_answer_text(draft, "其")

        self.assertEqual(merged, draft)

    def test_build_live_answer_text_keeps_meaningful_continuation(self):
        draft = "我已经说完这句话。"
        merged = build_live_answer_text(draft, "然后我继续补充")

        self.assertIn("然后我继续补充", merged)


if __name__ == "__main__":
    unittest.main()
