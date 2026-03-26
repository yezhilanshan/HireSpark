"""
检索器模块 - RAG 核心逻辑（支持双通道 Question/Rubric 检索）
"""

import re
from typing import Any, Dict, List, Optional

from .chroma_db import KnowledgeStore
from .embedding import TextEmbedder


class BaseKnowledgeRetriever:
    """检索器基类，封装共享的召回、词法打分和重排逻辑。"""

    default_view_type: Optional[str] = None

    def __init__(self, knowledge_store: KnowledgeStore, embedder: TextEmbedder = None):
        self.store = knowledge_store
        self.embedder = embedder

    def _merge_metadata_filters(
        self,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> Optional[Dict[str, Any]]:
        combined = dict(metadata_filters or {})
        if self.default_view_type and "view_type" not in combined:
            combined["view_type"] = self.default_view_type
        return combined or None

    @staticmethod
    def _normalize_text(text: str) -> str:
        """归一化文本，便于中英文混合做轻量词法匹配。"""
        return re.sub(r"\s+", "", (text or "").lower())

    @staticmethod
    def _extract_ascii_terms(text: str) -> List[str]:
        """提取英文/符号术语，用于降低语义召回的噪声。"""
        terms = []
        for term in re.findall(r"[a-zA-Z][a-zA-Z0-9_\-./+]*", text or ""):
            normalized = term.lower().strip()
            if len(normalized) >= 2:
                terms.append(normalized)
        return list(dict.fromkeys(terms))

    def _compute_lexical_score(self, query: str, item: Dict[str, Any]) -> Dict[str, Any]:
        """基于问题/关键词/检索文本做轻量词法打分，增强关键词匹配权重。"""
        normalized_query = self._normalize_text(query)
        metadata = item.get("metadata", {}) or {}
        question = item.get("question", "") or ""
        retrieval_text = metadata.get("retrieval_text", "") or item.get("document", "") or ""
        category = metadata.get("category", "") or ""
        subcategory = metadata.get("subcategory", "") or ""
        keywords = metadata.get("keywords", []) or []
        tags = metadata.get("tags", []) or []

        if isinstance(keywords, str):
            keywords = [keywords]
        if isinstance(tags, str):
            tags = [tags]

        normalized_question = self._normalize_text(question)
        normalized_retrieval = self._normalize_text(retrieval_text)
        normalized_category = self._normalize_text(category)
        normalized_subcategory = self._normalize_text(subcategory)

        score = 0.0
        keyword_hits = []
        ascii_hits = []

        if normalized_query and normalized_query in normalized_question:
            score += 0.40
        elif normalized_query and normalized_query in normalized_retrieval:
            score += 0.25

        query_ascii_terms = set(self._extract_ascii_terms(query))
        for keyword in keywords:
            normalized_keyword = self._normalize_text(str(keyword))
            if len(normalized_keyword) < 2:
                continue
            if normalized_keyword in normalized_query:
                keyword_hits.append(str(keyword))
            elif query_ascii_terms and any(
                term in self._normalize_text(str(keyword)) for term in query_ascii_terms
            ):
                keyword_hits.append(str(keyword))

        if keyword_hits:
            score += min(0.20 * len(keyword_hits), 0.50)

        for term in query_ascii_terms:
            if term in normalized_question:
                ascii_hits.append(term)
            elif term in normalized_retrieval:
                ascii_hits.append(term)
            elif any(term in self._normalize_text(str(keyword)) for keyword in keywords):
                ascii_hits.append(term)

        if ascii_hits:
            score += min(0.15 * len(ascii_hits), 0.30)

        tag_hits = []
        for tag in tags:
            normalized_tag = self._normalize_text(str(tag))
            if normalized_tag in normalized_query:
                tag_hits.append(str(tag))
        if tag_hits:
            score += min(0.10 * len(tag_hits), 0.20)

        if normalized_category and normalized_category in normalized_query:
            score += 0.08
        if normalized_subcategory and normalized_subcategory in normalized_query:
            score += 0.08

        query_words = set(normalized_query.split()) if normalized_query else set()
        question_words = set(normalized_question.split()) if normalized_question else set()
        common_words = query_words & question_words
        if query_words and len(common_words) > 0:
            score += min(0.05 * len(common_words), 0.15)

        return {
            "lexical_score": min(score, 1.0),
            "keyword_hits": keyword_hits,
            "ascii_hits": ascii_hits,
            "tag_hits": tag_hits,
        }

    @staticmethod
    def _is_strong_match(
        item: Dict[str, Any],
        top_similarity: float,
        max_similarity_gap: float,
        min_lexical_score: float
    ) -> bool:
        """只保留强相关结果，减少尾部噪声污染 LLM 上下文。"""
        similarity = float(item.get("similarity", 0))
        lexical_score = float(item.get("lexical_score", 0))
        rerank_score = float(item.get("rerank_score", 0))

        if lexical_score >= 0.35:
            return True

        if rerank_score >= top_similarity * 0.85:
            return True

        if similarity >= max(top_similarity - max_similarity_gap / 2, top_similarity * 0.90):
            return True

        return (top_similarity - similarity) <= max_similarity_gap and lexical_score >= min_lexical_score

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        filter_category: str = None,
        filter_difficulty: str = None,
        strong_filter: bool = True,
        max_similarity_gap: float = 0.08,
        min_lexical_score: float = 0.10,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        results = self.store.search(
            query,
            top_k=max(top_k * 2, top_k),
            metadata_filters=self._merge_metadata_filters(metadata_filters)
        )

        filtered = []
        for item in results:
            sim = item.get("similarity", 1 - item.get("distance", 0))
            if sim < min_similarity:
                continue

            item["similarity"] = sim
            metadata = item.get("metadata", {})
            if filter_category and metadata.get("category") != filter_category:
                continue
            if filter_difficulty and metadata.get("difficulty") != filter_difficulty:
                continue

            lexical_info = self._compute_lexical_score(query, item)
            item.update(lexical_info)
            item["rerank_score"] = round(sim * 0.60 + item["lexical_score"] * 0.40, 4)
            filtered.append(item)

        filtered.sort(
            key=lambda candidate: (
                float(candidate.get("rerank_score", 0)),
                float(candidate.get("similarity", 0))
            ),
            reverse=True
        )

        if not strong_filter or not filtered:
            return filtered[:top_k]

        top_similarity = float(filtered[0].get("similarity", 0))
        strong_results = []
        for item in filtered:
            item["is_strong_match"] = self._is_strong_match(
                item=item,
                top_similarity=top_similarity,
                max_similarity_gap=max_similarity_gap,
                min_lexical_score=min_lexical_score
            )
            if item["is_strong_match"]:
                strong_results.append(item)

        if not strong_results:
            strong_results = filtered[:1]
            strong_results[0]["is_strong_match"] = True

        return strong_results[:top_k]


class QuestionRetriever(BaseKnowledgeRetriever):
    """面向出题场景的 Question 视图检索器。"""

    default_view_type = "question"


class RubricRetriever(BaseKnowledgeRetriever):
    """面向判题与追问场景的 Rubric 视图检索器。"""

    default_view_type = "rubric"


class KnowledgeRetriever:
    """兼容层：对外保留统一入口，内部委托给双通道 retriever。"""

    def __init__(self, knowledge_store: KnowledgeStore, embedder: TextEmbedder = None):
        self.store = knowledge_store
        self.embedder = embedder
        self.question_retriever = QuestionRetriever(knowledge_store, embedder)
        self.rubric_retriever = RubricRetriever(knowledge_store, embedder)

    def _select_retriever(
        self,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> BaseKnowledgeRetriever:
        view_type = (metadata_filters or {}).get("view_type")
        if view_type == "rubric":
            return self.rubric_retriever
        return self.question_retriever

    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        min_similarity: float = 0.5,
        filter_category: str = None,
        filter_difficulty: str = None,
        strong_filter: bool = True,
        max_similarity_gap: float = 0.08,
        min_lexical_score: float = 0.10,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        retriever = self._select_retriever(metadata_filters)
        return retriever.retrieve(
            query=query,
            top_k=top_k,
            min_similarity=min_similarity,
            filter_category=filter_category,
            filter_difficulty=filter_difficulty,
            strong_filter=strong_filter,
            max_similarity_gap=max_similarity_gap,
            min_lexical_score=min_lexical_score,
            metadata_filters=metadata_filters,
        )

    def retrieve_questions(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        metadata_filters = dict(kwargs.pop("metadata_filters", {}) or {})
        metadata_filters["view_type"] = "question"
        return self.question_retriever.retrieve(
            query=query,
            metadata_filters=metadata_filters,
            **kwargs,
        )

    def retrieve_rubrics(self, query: str, **kwargs) -> List[Dict[str, Any]]:
        metadata_filters = dict(kwargs.pop("metadata_filters", {}) or {})
        metadata_filters["view_type"] = "rubric"
        return self.rubric_retriever.retrieve(
            query=query,
            metadata_filters=metadata_filters,
            **kwargs,
        )

    def retrieve_with_prompt(
        self,
        query: str,
        top_k: int = 3,
        include_key_points: bool = True,
        include_common_mistakes: bool = True
    ) -> str:
        results = self.retrieve_rubrics(query, top_k=top_k)

        if not results:
            return query

        context_parts = []
        for i, item in enumerate(results, 1):
            question = item.get("question", "")
            metadata = item.get("metadata", {})
            answer_summary = metadata.get("answer_summary", "")
            key_points = metadata.get("key_points", [])
            common_mistakes = metadata.get("common_mistakes", [])
            retrieval_text = metadata.get("retrieval_text", "")
            category = metadata.get("category", "")
            difficulty = metadata.get("difficulty", "")

            parts = [f"【参考 {i}】{question}"]
            if category:
                parts.append(f"分类：{category}")
            if difficulty:
                parts.append(f"难度：{difficulty}")

            answer_content = answer_summary or retrieval_text or metadata.get("answer", "")
            if answer_content:
                parts.append(f"\n核心要点：\n{answer_content}")

            if include_key_points and key_points:
                parts.append("\n关键要点：")
                for j, point in enumerate(key_points[:5], 1):
                    parts.append(f"  {j}. {point}")

            if include_common_mistakes and common_mistakes:
                parts.append("\n常见错误：")
                for j, mistake in enumerate(common_mistakes[:3], 1):
                    parts.append(f"  {j}. {mistake}")

            context_parts.append("\n".join(parts))

        context = "\n\n" + "=" * 50 + "\n\n".join(context_parts) + "\n" + "=" * 50

        return f"""你是一个专业的技术面试官助手。请根据以下背景知识回答问题。

用户问题：{query}

请结合以下背景知识，给出专业、准确、结构化的回答。回答应包含：
1. 核心概念解释
2. 关键要点说明
3. 需要注意的常见误区

背景知识：
{context}

请基于以上背景知识，对用户问题给出专业回答："""

    def get_related_questions(self, query: str, top_k: int = 5) -> List[str]:
        results = self.retrieve_questions(query, top_k=top_k)
        return [item.get("question", "") for item in results if item.get("question")]

    def get_question_details(self, question_id: str) -> Optional[Dict[str, Any]]:
        items = self.store.get_by_metadata(
            {"source_id": question_id, "view_type": "question"},
            limit=1
        )
        if items:
            item = items[0]
            return {
                "id": item.get("metadata", {}).get("source_id", question_id),
                "question": item.get("question", ""),
                **(item.get("metadata", {}) or {})
            }

        if self.store.collection is not None:
            try:
                result = self.store.collection.get(
                    ids=[question_id],
                    include=["documents", "metadatas"]
                )
                if result and result["ids"]:
                    return {
                        "id": result["ids"][0],
                        "question": result["documents"][0] if result["documents"] else "",
                        **(result["metadatas"][0] if result["metadatas"] else {})
                    }
            except Exception as e:
                print(f"[!] 获取问题详情失败：{e}")

        if hasattr(self.store, "_fallback_data"):
            for i, qid in enumerate(self.store._fallback_data.get("ids", [])):
                if qid == question_id:
                    return {
                        "id": question_id,
                        "question": self.store._fallback_data["documents"][i],
                        **self.store._fallback_data["metadatas"][i]
                    }

        return None

    def get_followup_questions(self, query: str, top_k: int = 3) -> List[Dict[str, str]]:
        results = self.retrieve_rubrics(query, top_k=top_k)
        followups = []

        for item in results:
            metadata = item.get("metadata", {})
            item_followups = metadata.get("followups", [])

            for fu in item_followups:
                if isinstance(fu, dict) and "question" in fu:
                    followups.append({
                        "question": fu["question"],
                        "trigger": fu.get("trigger_type", fu.get("trigger", "")),
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
        results = self.retrieve_rubrics(query, top_k=1)
        if results:
            metadata = results[0].get("metadata", {})
            return metadata.get("scoring_rubric")
        return None

    def build_interview_prompt(
        self,
        query: str,
        candidate_answer: str = "",
        top_k: int = 3
    ) -> str:
        results = self.retrieve_rubrics(query, top_k=top_k)

        reference_answers = []
        scoring_rubrics = []

        for i, item in enumerate(results, 1):
            metadata = item.get("metadata", {})
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

            rubric = metadata.get("scoring_rubric", {})
            if rubric:
                scoring_rubrics.append((item.get("question", ""), rubric))

        references_text = "\n".join(reference_answers)

        rubric_text = "\n\n评分标准：\n"
        for question, rubric in scoring_rubrics:
            rubric_text += f"\n问题：{question}\n"
            for level, criteria in rubric.items():
                rubric_text += f"  {level}：\n"
                for criterion in criteria:
                    rubric_text += f"    - {criterion}\n"

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
