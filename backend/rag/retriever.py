"""
检索器模块 - RAG 核心逻辑
"""

from typing import List, Dict, Any, Optional
from .embedding import TextEmbedder
from .chroma_db import KnowledgeStore


class KnowledgeRetriever:
    """知识检索器"""

    def __init__(self, knowledge_store: KnowledgeStore, embedder: TextEmbedder = None):
        """
        初始化检索器

        Args:
            knowledge_store: 知识库存储实例
            embedder: Embedding 实例（可选，如果已传入 store 可省略）
        """
        self.store = knowledge_store
        self.embedder = embedder

    def retrieve(self, query: str, top_k: int = 5,
                 min_similarity: float = 0.5) -> List[Dict[str, Any]]:
        """
        检索相关知识

        Args:
            query: 查询问题
            top_k: 返回数量
            min_similarity: 最低相似度阈值

        Returns:
            相关知识列表
        """
        results = self.store.search(query, top_k=top_k)

        # 过滤低相似度结果
        filtered = []
        for item in results:
            sim = item.get("similarity", 1 - item.get("distance", 0))
            if sim >= min_similarity:
                item["similarity"] = sim
                filtered.append(item)

        return filtered

    def retrieve_with_prompt(self, query: str, top_k: int = 3) -> str:
        """
        检索并生成 RAG Prompt

        Args:
            query: 用户问题
            top_k: 引用知识数量

        Returns:
            包含背景知识的 Prompt
        """
        results = self.retrieve(query, top_k=top_k)

        if not results:
            return query

        # 构建背景知识
        context_parts = []
        for i, item in enumerate(results, 1):
            question = item.get("question", "")
            answer = item.get("metadata", {}).get("answer", "")
            if question and answer:
                context_parts.append(f"{i}. {question}\n   参考答案：{answer}")

        context = "\n\n".join(context_parts)

        prompt = f"""请根据以下背景知识回答问题：

问题：{query}

---
背景知识：
{context}
---

请结合上述知识，给出专业、准确的回答。"""

        return prompt

    def get_related_questions(self, query: str, top_k: int = 5) -> List[str]:
        """获取相关问题列表"""
        results = self.retrieve(query, top_k=top_k)
        return [item.get("question", "") for item in results if item.get("question")]
