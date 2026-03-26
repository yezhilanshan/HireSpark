#!/usr/bin/env python
"""
RAG 检索测试 - 新格式知识库
测试新格式字段的检索效果
"""

import sys
import json
from pathlib import Path

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from backend.rag.embedding import TextEmbedder
from backend.rag.chroma_db import KnowledgeStore
from backend.rag.retriever import KnowledgeRetriever


def load_questions(filepath):
    """加载知识库问题（新格式）"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("llm_interview_questions", [])


def build_knowledge_base(questions, embedder):
    """构建知识库（新格式）"""
    print("\n" + "=" * 60)
    print("构建知识库（新格式）...")
    print("=" * 60)

    store = KnowledgeStore(
        collection_name="interview_v2",
        persist_dir=str(Path(__file__).parent / "rag_data_v2"),
        embedder=embedder
    )

    # 直接使用问题列表（已经是新格式）
    store.add_questions_batch(questions)
    print(f"[OK] 知识库构建完成，共 {store.count()} 条问题")

    return store


def display_question_details(item, is_raw=False):
    """显示问题详情（新格式）

    Args:
        item: 问题数据（从JSON加载的原始数据或从store检索的数据）
        is_raw: 是否为原始JSON数据（True）或store检索数据（False）
    """
    if is_raw:
        # 直接从JSON加载的数据
        print(f"\n[{item.get('id', 'N/A')}] {item.get('question', '')}")
        print(f"   角色：{item.get('role', 'N/A')}")
        print(f"   分类：{item.get('category', 'N/A')} / {item.get('subcategory', 'N/A')}")
        print(f"   难度：{item.get('difficulty', 'N/A')} | 类型：{item.get('question_type', 'N/A')}")
        print(f"   关键词：{item.get('keywords', [])}")
        print(f"   标签：{item.get('tags', [])}")

        # 答案概要
        answer_summary = item.get('answer_summary', '')
        if answer_summary:
            print(f"\n   答案概要：{answer_summary[:150]}...")

        # 关键要点
        key_points = item.get('key_points', [])
        if key_points:
            print(f"\n   关键要点（{len(key_points)}条）：")
            for i, point in enumerate(key_points[:3], 1):
                print(f"      {i}. {point[:80]}...")

        # 常见错误
        common_mistakes = item.get('common_mistakes', [])
        if common_mistakes:
            print(f"\n   常见错误（{len(common_mistakes)}条）：")
            for i, mistake in enumerate(common_mistakes[:2], 1):
                print(f"      {i}. {mistake[:80]}...")

        # 评分标准
        scoring_rubric = item.get('scoring_rubric', {})
        if scoring_rubric:
            print(f"\n   评分标准：")
            for level in ['basic', 'good', 'excellent']:
                criteria = scoring_rubric.get(level, [])
                if criteria:
                    print(f"      {level}: {len(criteria)} 条标准")

        # 追问
        followups = item.get('followups', [])
        if followups:
            print(f"\n   追问问题（{len(followups)}个）：")
            for i, fu in enumerate(followups[:2], 1):
                if isinstance(fu, dict):
                    print(f"      {i}. {fu.get('question', '')[:60]}...")
                else:
                    print(f"      {i}. {fu[:60]}...")
    else:
        # 从store检索的数据，metadata在metadata字段中
        metadata = item.get("metadata", {})

        print(f"\n[{item.get('id', 'N/A')}] {item.get('question', '')}")
        print(f"   角色：{metadata.get('role', 'N/A')}")
        print(f"   分类：{metadata.get('category', 'N/A')} / {metadata.get('subcategory', 'N/A')}")
        print(f"   难度：{metadata.get('difficulty', 'N/A')} | 类型：{metadata.get('question_type', 'N/A')}")
        print(f"   关键词：{metadata.get('keywords', [])}")
        print(f"   标签：{metadata.get('tags', [])}")

        # 答案概要
        answer_summary = metadata.get('answer_summary', '')
        if answer_summary:
            print(f"\n   答案概要：{answer_summary[:150]}...")

        # 关键要点
        key_points = metadata.get('key_points', [])
        if key_points:
            print(f"\n   关键要点（{len(key_points)}条）：")
            for i, point in enumerate(key_points[:3], 1):
                print(f"      {i}. {point[:80]}...")

        # 常见错误
        common_mistakes = metadata.get('common_mistakes', [])
        if common_mistakes:
            print(f"\n   常见错误（{len(common_mistakes)}条）：")
            for i, mistake in enumerate(common_mistakes[:2], 1):
                print(f"      {i}. {mistake[:80]}...")

        # 评分标准
        scoring_rubric = metadata.get('scoring_rubric', {})
        if scoring_rubric:
            print(f"\n   评分标准：")
            for level in ['basic', 'good', 'excellent']:
                criteria = scoring_rubric.get(level, [])
                if criteria:
                    print(f"      {level}: {len(criteria)} 条标准")

        # 追问
        followups = metadata.get('followups', [])
        if followups:
            print(f"\n   追问问题（{len(followups)}个）：")
            for i, fu in enumerate(followups[:2], 1):
                if isinstance(fu, dict):
                    print(f"      {i}. {fu.get('question', '')[:60]}...")
                else:
                    print(f"      {i}. {fu[:60]}...")


def test_retrieval(retriever, test_cases):
    """测试检索效果（新格式）"""
    print("\n" + "=" * 60)
    print("检索测试（新格式）")
    print("=" * 60)

    for i, (query, expected_keywords) in enumerate(test_cases, 1):
        print(f"\n[测试 {i}] 查询：{query}")
        print(f"  期望关键词：{expected_keywords}")
        print("-" * 60)

        results = retriever.retrieve(query, top_k=3, min_similarity=0.2)

        if not results:
            print("  [!] 未检索到任何结果")
            continue

        for j, item in enumerate(results, 1):
            question = item.get("question", "")
            sim = item.get("similarity", 0)
            metadata = item.get("metadata", {})
            category = metadata.get("category", "")
            difficulty = metadata.get("difficulty", "")
            question_type = metadata.get("question_type", "")

            # 检查是否包含期望关键词
            matched = any(kw.lower() in question.lower() for kw in expected_keywords)
            marker = "[OK]" if matched else "[?]"

            print(f"  {marker} 结果{j}: {question}")
            print(f"      相似度：{sim:.4f} | 分类：{category} | 难度：{difficulty} | 类型：{question_type}")

        # 测试追问获取
        followups = retriever.get_followup_questions(query, top_k=1)
        if followups:
            print(f"\n  推荐追问：{followups[0].get('question', '')[:50]}...")

        print()


def test_scoring_rubric(retriever):
    """测试评分标准获取"""
    print("\n" + "=" * 60)
    print("评分标准测试")
    print("=" * 60)

    test_query = "Attention 机制的计算公式是什么？为什么要除以 dk？"
    rubric = retriever.get_scoring_rubric(test_query)

    if rubric:
        print(f"\n查询：{test_query}")
        print("评分标准：")
        for level, criteria in rubric.items():
            print(f"\n  {level}:")
            for c in criteria:
                print(f"    - {c}")
    else:
        print("[!] 未找到评分标准")


def test_interview_prompt(retriever):
    """测试面试评估 Prompt 生成"""
    print("\n" + "=" * 60)
    print("面试评估 Prompt 测试")
    print("=" * 60)

    query = "Attention 机制的计算公式是什么？"
    candidate_answer = "Attention(Q,K,V) = softmax(QK^T)V，除以 dk 是为了防止数值过大。"

    prompt = retriever.build_interview_prompt(query, candidate_answer, top_k=2)

    print(f"\n面试问题：{query}")
    print(f"候选人回答：{candidate_answer}")
    print("\n生成的评估 Prompt（前800字符）：")
    print("-" * 60)
    print(prompt[:800])
    print("...")


def main():
    print("=" * 60)
    print("RAG 检索系统测试 - 新格式知识库")
    print("=" * 60)

    # 初始化 Embedding
    embedder = TextEmbedder(model_name='shibing624/text2vec-base-chinese')

    # 加载新格式问题
    questions_path = Path(__file__).parent / "backend" / "knowledge" / "llm_questions_v2.json"
    if not questions_path.exists():
        print(f"[!] 知识库文件不存在：{questions_path}")
        return

    questions = load_questions(questions_path)
    print(f"加载了 {len(questions)} 条问题（新格式）")

    # 显示知识库内容预览
    print("\n" + "=" * 60)
    print("知识库内容预览（新格式）")
    print("=" * 60)

    for q in questions[:3]:  # 只显示前3条
        display_question_details(q, is_raw=True)
        print("\n" + "-" * 60)

    print(f"\n... 共 {len(questions)} 条问题")
    input("\n按 Enter 继续测试检索功能...")

    # 构建知识库
    store = build_knowledge_base(questions, embedder)

    # 显示向量库内容
    print("\n" + "=" * 60)
    print("ChromaDB 向量库内容")
    print("=" * 60)
    print(f"问题数量：{store.count()}")

    # 初始化检索器
    retriever = KnowledgeRetriever(store, embedder)

    # 测试用例：(查询，期望包含的关键词)
    test_cases = [
        # 测试 1：Attention 相关
        ("attention 怎么计算的", ["Attention", "softmax", "dk"]),

        # 测试 2：PPO 相关
        ("ppo 的损失函数", ["PPO", "loss", "ratio"]),

        # 测试 3：位置编码
        ("位置编码有哪些", ["位置编码", "RoPE", "Transformer"]),

        # 测试 4：力扣算法题
        ("最长括号子串", ["括号", "栈", "动态规划"]),

        # 测试 5：大模型对齐
        ("dpo 和 ppo 有什么区别", ["DPO", "PPO", "强化学习"]),

        # 测试 6：优化器
        ("adam 优化器原理", ["Adam", "优化器", "梯度"]),

        # 测试 7：注意力变体
        ("gqa 和 mqa 是什么", ["GQA", "MQA", "Attention"]),

        # 测试 8：手撕代码
        ("交叉熵损失怎么写", ["交叉熵", "损失函数", "代码"]),

        # 测试 9：语义相似但字面不同
        ("transformer 为什么要缩放点积", ["Attention", "dk", "softmax"]),

        # 测试 10：RLHF 相关
        ("大模型训练中的 returns 是什么", ["returns", "PPO", "reward"]),

        # 测试 11：ViT 位置编码
        ("vit 位置编码", ["ViT", "位置编码", "二维"]),

        # 测试 12：多模态
        ("多模态位置编码", ["多模态", "位置编码", "对齐"]),
    ]

    # 执行检索测试
    test_retrieval(retriever, test_cases)

    # 测试评分标准
    test_scoring_rubric(retriever)

    # 测试面试评估 Prompt
    test_interview_prompt(retriever)

    # 总结
    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

    print("\n新格式知识库特性：")
    print("  ✓ 支持 role、category、subcategory 等元数据")
    print("  ✓ 支持 answer_summary、key_points、common_mistakes")
    print("  ✓ 支持 scoring_rubric 评分标准")
    print("  ✓ 支持 followups 追问问题")
    print("  ✓ 支持 retrieval_text 优化检索")
    print("  ✓ 支持 tags 标签系统")

    print("\n[提示] 安装依赖后获得更好的语义检索效果：")
    print("  pip install sentence-transformers chromadb")


if __name__ == "__main__":
    main()
