"""
检索器模块 - RAG 核心逻辑（支持新格式知识库）
"""

from typing import List, Dict, Any, Optional
from .embedding import TextEmbedder
from .chroma_db import KnowledgeStore


class KnowledgeRetriever:
    """知识检索器 - 支持详细格式的面试知识库"""

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
                 min_similarity: float = 0.5,
                 filter_category: str = None,
                 filter_difficulty: str = None) -> List[Dict[str, Any]]:
        """
        检索相关知识

        Args:
            query: 查询问题
            top_k: 返回数量
            min_similarity: 最低相似度阈值
            filter_category: 按分类过滤（可选）
            filter_difficulty: 按难度过滤（可选）

        Returns:
            相关知识列表（新格式）
        """
        results = self.store.search(query, top_k=top_k)

        # 过滤低相似度结果
        filtered = []
        for item in results:
            sim = item.get("similarity", 1 - item.get("distance", 0))
            if sim >= min_similarity:
                item["similarity"] = sim

                # 应用过滤器
                metadata = item.get("metadata", {})
                if filter_category and metadata.get("category") != filter_category:
                    continue
                if filter_difficulty and metadata.get("difficulty") != filter_difficulty:
                    continue

                filtered.append(item)

        return filtered

    def retrieve_with_prompt(self, query: str, top_k: int = 3,
                             include_key_points: bool = True,
                             include_common_mistakes: bool = True) -> str:
        """
        检索并生成 RAG Prompt（新格式增强版）

        Args:
            query: 用户问题
            top_k: 引用知识数量
            include_key_points: 是否包含关键要点
            include_common_mistakes: 是否包含常见错误

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
            metadata = item.get("metadata", {})

            # 优先使用新格式字段
            answer_summary = metadata.get("answer_summary", "")
            key_points = metadata.get("key_points", [])
            common_mistakes = metadata.get("common_mistakes", [])
            retrieval_text = metadata.get("retrieval_text", "")
            category = metadata.get("category", "")
            difficulty = metadata.get("difficulty", "")

            # 构建知识条目
            parts = [f"【参考 {i}】{question}"]

            if category:
                parts.append(f"分类：{category}")
            if difficulty:
                parts.append(f"难度：{difficulty}")

            # 使用 answer_summary 或 retrieval_text 或旧版 answer
            answer_content = answer_summary or retrieval_text or metadata.get("answer", "")
            if answer_content:
                parts.append(f"\n核心要点：\n{answer_content}")

            # 添加关键要点
            if include_key_points and key_points:
                parts.append("\n关键要点：")
                for j, point in enumerate(key_points[:5], 1):  # 最多显示5个要点
                    parts.append(f"  {j}. {point}")

            # 添加常见错误
            if include_common_mistakes and common_mistakes:
                parts.append("\n常见错误：")
                for j, mistake in enumerate(common_mistakes[:3], 1):  # 最多显示3个常见错误
                    parts.append(f"  {j}. {mistake}")

            context_parts.append("\n".join(parts))

        context = "\n\n" + "="*50 + "\n\n".join(context_parts) + "\n" + "="*50

        prompt = f"""你是一个专业的技术面试官助手。请根据以下背景知识回答问题。

用户问题：{query}

请结合以下背景知识，给出专业、准确、结构化的回答。回答应包含：
1. 核心概念解释
2. 关键要点说明
3. 需要注意的常见误区

背景知识：
{context}

请基于以上背景知识，对用户问题给出专业回答："""

        return prompt

    def get_related_questions(self, query: str, top_k: int = 5) -> List[str]:
        """获取相关问题列表"""
        results = self.retrieve(query, top_k=top_k)
        return [item.get("question", "") for item in results if item.get("question")]

    def get_question_details(self, question_id: str) -> Optional[Dict[str, Any]]:
        """
        获取问题的完整详情（新格式）

        Args:
            question_id: 问题ID

        Returns:
            问题详情字典
        """
        # 从 store 中查找
        if self.store.collection is not None:
            try:
                result = self.store.collection.get(
                    ids=[question_id],
                    include=["documents", "metadatas"]
                )
                if result and result['ids']:
                    return {
                        "id": result['ids'][0],
                        "question": result['documents'][0] if result['documents'] else "",
                        **(result['metadatas'][0] if result['metadatas'] else {})
                    }
            except Exception as e:
                print(f"[!] 获取问题详情失败：{e}")

        # 本地存储模式
        if hasattr(self.store, '_fallback_data'):
            for i, qid in enumerate(self.store._fallback_data.get("ids", [])):
                if qid == question_id:
                    return {
                        "id": question_id,
                        "question": self.store._fallback_data["documents"][i],
                        **self.store._fallback_data["metadatas"][i]
                    }

        return None

    def get_followup_questions(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        """
        获取推荐的追问问题（基于新格式 followups 字段）

        Args:
            query: 用户问题
            top_k: 返回数量

        Returns:
            追问问题列表
        """
        results = self.retrieve(query, top_k=top_k)
        followups = []

        for item in results:
            metadata = item.get("metadata", {})
            item_followups = metadata.get("followups", [])

            for fu in item_followups:
                if isinstance(fu, dict) and "question" in fu:
                    followups.append({
                        "question": fu["question"],
                        "trigger": fu.get("trigger", ""),
                        "source_question": item.get("question", "")
                    })
                elif isinstance(fu, str):
                    followups.append({
                        "question": fu,
                        "trigger": "",
                        "source_question": item.get("question", "")
                    })

        return followups

    def get_scoring_rubric(self, query: str) -> Optional[Dict[str, List[str]]]:
        """
        获取评分标准（基于新格式 scoring_rubric 字段）

        Args:
            query: 用户问题

        Returns:
            评分标准字典
        """
        results = self.retrieve(query, top_k=1)
        if results:
            metadata = results[0].get("metadata", {})
            return metadata.get("scoring_rubric")
        return None

    def build_interview_prompt(self, query: str, candidate_answer: str = "",
                               top_k: int = 3) -> str:
        """
        构建面试评估 Prompt（用于评估候选人回答）

        Args:
            query: 面试问题
            candidate_answer: 候选人的回答
            top_k: 参考知识数量

        Returns:
            评估 Prompt
        """
        results = self.retrieve(query, top_k=top_k)

        # 构建参考答案
        reference_answers = []
        scoring_rubrics = []

        for i, item in enumerate(results, 1):
            metadata = item.get("metadata", {})

            # 参考答案
            key_points = metadata.get("key_points", [])
            answer_summary = metadata.get("answer_summary", "")

            ref = f"【参考 {i}】\n"
            ref += f"问题：{item.get('question', '')}\n"
            if answer_summary:
                ref += f"答案概要：{answer_summary}\n"
            if key_points:
                ref += "关键要点：\n"
                for point in key_points:
                    ref += f"  - {point}\n"

            reference_answers.append(ref)

            # 评分标准
            rubric = metadata.get("scoring_rubric", {})
            if rubric:
                scoring_rubrics.append((item.get('question', ''), rubric))

        references_text = "\n".join(reference_answers)

        # 构建评分标准文本
        rubric_text = "\n\n评分标准：\n"
        for question, rubric in scoring_rubrics:
            rubric_text += f"\n问题：{question}\n"
            for level, criteria in rubric.items():
                rubric_text += f"  {level}：\n"
                for c in criteria:
                    rubric_text += f"    - {c}\n"

        prompt = f"""你是一位经验丰富的技术面试官。请根据以下参考答案和评分标准，评估候选人的回答。

面试问题：{query}

{references_text}
{rubric_text}
"""

        if candidate_answer:
            prompt += f"""
候选人回答：
{candidate_answer}

请从以下几个方面进行评估：
1. 准确性：回答是否正确
2. 完整性：是否覆盖了关键要点
3. 深度：是否有深入的理解
4. 评分：根据评分标准给出等级（basic/good/excellent）
5. 建议：如何改进回答

请给出详细的评估结果："""
        else:
            prompt += """
请基于以上参考答案，准备可能的追问问题和评分要点："""

        return prompt
