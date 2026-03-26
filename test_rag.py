#!/usr/bin/env python
"""
RAG 检索测试
测试关键词能否检索到相似内容
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
    """加载知识库问题"""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data.get("llm_interview_questions", [])


def build_knowledge_base(questions, embedder):
    """构建知识库"""
    print("\n" + "=" * 60)
    print("构建知识库...")
    print("=" * 60)

    store = KnowledgeStore(
        collection_name="interview_test",
        persist_dir=str(Path(__file__).parent / "rag_data"),
        embedder=embedder
    )

    # 清空重建
    questions_data = []
    for q in questions:
        questions_data.append({
            "id": q["id"],
            "question": q["question"],
            "answer": q.get("answer", ""),
            "metadata": {
                "category": q.get("category", ""),
                "difficulty": q.get("difficulty", ""),
                "keywords": q.get("keywords", [])
            }
        })

    store.add_questions_batch(questions_data)
    print(f"[OK] 知识库构建完成，共 {store.count()} 条问题")

    return store


def test_retrieval(retriever, test_cases):
    """测试检索效果"""
    print("\n" + "=" * 60)
    print("检索测试")
    print("=" * 60)

    for i, (query, expected_keywords) in enumerate(test_cases, 1):
        print(f"\n[测试 {i}] 查询：{query}")
        print(f"  期望关键词：{expected_keywords}")
        print("-" * 60)

        results = retriever.retrieve(query, top_k=3, min_similarity=0.3)

        if not results:
            print("  [!] 未检索到任何结果")
            continue

        for j, item in enumerate(results, 1):
            question = item.get("question", "")
            sim = item.get("similarity", 0)
            category = item.get("metadata", {}).get("category", "")

            # 检查是否包含期望关键词
            matched = any(kw.lower() in question.lower() for kw in expected_keywords)
            marker = "[OK]" if matched else "[?]"

            print(f"  {marker} 结果{j}: {question}")
            print(f"      相似度：{sim:.4f} | 分类：{category}")

        print()


def main():
    print("=" * 60)
    print("RAG 检索系统测试")
    print("=" * 60)

    # 初始化 Embedding
    embedder = TextEmbedder(model_name='shibing624/text2vec-base-chinese')

    # 加载问题
    questions_path = Path(__file__).parent / "backend" / "knowledge" / "llm_questions.json"
    if not questions_path.exists():
        print(f"[!] 知识库文件不存在：{questions_path}")
        return

    questions = load_questions(questions_path)
    print(f"加载了 {len(questions)} 条问题")

    # 显示知识库内容
    print("\n" + "=" * 60)
    print("知识库内容预览")
    print("=" * 60)
    for q in questions:
        print(f"\n[{q['id']}] {q['question']}")
        print(f"   分类：{q.get('category', 'N/A')} | 难度：{q.get('difficulty', 'N/A')}")
        print(f"   关键词：{q.get('keywords', [])}")
        answer = q.get('answer', '')
        if answer:
            # 截断并清理答案，避免编码问题
            answer_preview = answer[:100].replace('\n', ' ').replace('\r', '')
            try:
                print(f"   答案：{answer_preview}...")
            except:
                print(f"   答案：[长度{len(answer)}字符]")

    print("\n" + "=" * 60)
    input("按 Enter 继续测试检索功能...")

    # 构建知识库
    store = build_knowledge_base(questions, embedder)

    # 显示向量库内容
    print("\n" + "=" * 60)
    print("ChromaDB 向量库内容")
    print("=" * 60)
    print(f"问题数量：{store.count()}")

    # 直接查询所有数据
    if store.collection:
        all_data = store.collection.get(include=["documents", "metadatas"])
        for i, doc_id in enumerate(all_data['ids']):
            print(f"\n[{doc_id}] {all_data['documents'][i]}")
            meta = all_data['metadatas'][i]
            if meta.get('answer'):
                ans = meta['answer'][:80].replace('\n', ' ')
                print(f"   答案：{ans}...")
    else:
        # 本地存储模式
        print("(使用本地存储模式)")

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
    ]

    # 执行测试
    test_retrieval(retriever, test_cases)

    # 总结
    print("=" * 60)
    print("测试完成!")
    print("=" * 60)

    print("\n[提示] 安装依赖后获得更好的语义检索效果：")
    print("  pip install sentence-transformers chromadb")


if __name__ == "__main__":
    main()
