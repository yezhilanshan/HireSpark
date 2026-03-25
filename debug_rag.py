#!/usr/bin/env python
"""
调试 RAG 检索
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from backend.rag.embedding import TextEmbedder
from backend.rag.chroma_db import KnowledgeStore
import json

# 加载问题
questions_path = Path(__file__).parent / "backend" / "knowledge" / "llm_questions_v2.json"
with open(questions_path, 'r', encoding='utf-8') as f:
    data = json.load(f)
questions = data.get("llm_interview_questions", [])

# 初始化 embedder
embedder = TextEmbedder()

# 检查 embedding 生成
print("=" * 60)
print("测试 Embedding 生成")
print("=" * 60)

query = "attention 怎么计算的"
query_emb = embedder.encode(query)
print(f"\n查询：{query}")
print(f"查询向量非零元素数：{sum(query_emb != 0)}")
print(f"查询向量前10个非零位置：{[i for i, v in enumerate(query_emb) if v != 0][:10]}")

# 检查第一个问题的 embedding
q = questions[0]
text_for_embedding = q.get("retrieval_text", "") or q.get("answer_summary", "") or q["question"]
print(f"\n问题：{q['question']}")
print(f"用于 embedding 的文本：{text_for_embedding[:100]}...")

q_emb = embedder.encode(text_for_embedding)
print(f"问题向量非零元素数：{sum(q_emb != 0)}")
print(f"问题向量前10个非零位置：{[i for i, v in enumerate(q_emb) if v != 0][:10]}")

# 计算相似度
import numpy as np
sim = np.dot(query_emb, q_emb) / (np.linalg.norm(query_emb) * np.linalg.norm(q_emb) + 1e-8)
print(f"\n相似度：{sim:.4f}")

# 测试关键词匹配
print("\n" + "=" * 60)
print("测试关键词匹配")
print("=" * 60)

query_keywords = set(query.lower().split())
print(f"查询关键词：{query_keywords}")

for q in questions[:3]:
    doc_keywords = set(q['question'].lower().split())
    common = query_keywords & doc_keywords
    print(f"\n问题：{q['question'][:50]}...")
    print(f"问题关键词：{list(doc_keywords)[:10]}...")
    print(f"共同关键词：{common}")
