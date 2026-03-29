"""
ChromaDB 向量存储模块
"""

import json
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional


class KnowledgeStore:
    """知识库存储 - 使用 ChromaDB"""

    def __init__(self, collection_name: str = "interview_questions",
                 persist_dir: str = None, embedder=None):
        """
        初始化知识库存储

        Args:
            collection_name: 集合名称
            persist_dir: 持久化目录，None 则使用内存
            embedder: TextEmbedder 实例
        """
        self.collection_name = collection_name
        self.persist_dir = persist_dir
        self.embedder = embedder
        self.client = None
        self.collection = None
        self._fallback_path = None
        self._fallback_data = {
            "ids": [],
            "embeddings": [],
            "documents": [],
            "metadatas": []
        }
        self._init_chroma()

    def _init_chroma(self):
        """初始化 ChromaDB"""
        try:
            import chromadb
            from chromadb.config import Settings

            if self.persist_dir:
                # 持久化模式
                persist_path = Path(self.persist_dir)
                persist_path.mkdir(parents=True, exist_ok=True)
                print(f"[*] 初始化 ChromaDB（持久化）：{persist_path}")
                self.client = chromadb.PersistentClient(
                    path=str(persist_path),
                    settings=Settings(anonymized_telemetry=False)
                )
            else:
                # 内存模式
                print("[*] 初始化 ChromaDB（内存模式）")
                self.client = chromadb.Client(
                    settings=Settings(anonymized_telemetry=False)
                )

            # 获取或创建集合
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
            print(f"[OK] 集合 '{self.collection_name}' 已就绪")

        except ImportError:
            print("[!] 未安装 chromadb，使用本地存储替代")
            print("    安装命令：pip install chromadb")
            self._init_fallback()
        except Exception as e:
            print(f"[!] ChromaDB 初始化失败：{e}")
            print("    使用本地存储替代")
            self._init_fallback()

    def _init_fallback(self):
        """本地存储备选方案"""
        self._fallback_data = {
            "ids": [],
            "embeddings": [],
            "documents": [],
            "metadatas": []
        }
        self._fallback_path = Path(self.persist_dir) / "knowledge_fallback.json" if self.persist_dir else None
        if self._fallback_path and self._fallback_path.exists():
            try:
                with open(self._fallback_path, 'r', encoding='utf-8') as f:
                    self._fallback_data = json.load(f)
                print(f"[OK] 加载本地知识库：{len(self._fallback_data['ids'])} 条")
            except:
                pass

    def _normalize_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """将 metadata 转为 Chroma 可接受的标量类型。"""
        normalized = {}
        for key, value in (metadata or {}).items():
            if value is None:
                continue
            if isinstance(value, (str, int, float, bool)):
                normalized[key] = value
            else:
                normalized[key] = json.dumps(value, ensure_ascii=False)
        return normalized

    def _restore_metadata(self, metadata: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """尽可能恢复 JSON 字符串形式的 metadata。"""
        restored = {}
        for key, value in (metadata or {}).items():
            if not isinstance(value, str):
                restored[key] = value
                continue
            try:
                restored[key] = json.loads(value)
            except (TypeError, ValueError):
                restored[key] = value
        return restored

    @staticmethod
    def _build_chroma_where(
        metadata_filters: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        将简单的 metadata 字典转成 Chroma 兼容的 where 结构。

        新版 Chroma 在多字段过滤时要求显式逻辑操作符，如:
        {"$and": [{"round_type": "technical"}, {"view_type": "question"}]}
        """
        if not metadata_filters:
            return None

        clauses = []
        for key, value in metadata_filters.items():
            if value is None:
                continue
            clauses.append({key: value})

        if not clauses:
            return None
        if len(clauses) == 1:
            return clauses[0]
        return {"$and": clauses}

    @staticmethod
    def _metadata_matches(
        metadata: Optional[Dict[str, Any]],
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        if not filters:
            return True

        current = metadata or {}
        for key, expected in filters.items():
            if expected is None:
                continue
            if current.get(key) != expected:
                return False
        return True

    @staticmethod
    def _build_question_dense_text(question: Dict[str, Any]) -> str:
        competency = ", ".join(str(item) for item in question.get("competency", []) if item)
        keywords = ", ".join(str(item) for item in question.get("keywords", []) if item)
        tags = ", ".join(str(item) for item in question.get("tags", []) if item)
        parts = [
            f"岗位：{question.get('role', '')}",
            f"题目：{question.get('question', '')}",
            f"类别：{question.get('category', '')} / {question.get('subcategory', '')}",
            f"能力点：{competency}",
            f"难度：{question.get('difficulty', '')}",
            f"题型：{question.get('question_type', '')}",
            f"轮次：{question.get('round_type', 'technical')}",
            f"意图：{question.get('question_intent', 'screening')}",
            f"关键词：{keywords}",
            f"标签：{tags}",
        ]
        return "。".join(part for part in parts if part and not part.endswith("："))

    @staticmethod
    def _build_rubric_dense_text(question: Dict[str, Any]) -> str:
        key_points = "；".join(str(item) for item in question.get("key_points", []) if item)
        optional_points = "；".join(
            str(item) for item in question.get("optional_points", []) if item
        )
        expected_signals = "；".join(
            str(item) for item in question.get("expected_answer_signals", []) if item
        )
        common_mistakes = "；".join(
            str(item) for item in question.get("common_mistakes", []) if item
        )
        followup_questions = "；".join(
            str(item.get("question", "")).strip()
            for item in question.get("followups", [])
            if isinstance(item, dict) and str(item.get("question", "")).strip()
        )
        parts = [
            f"题目：{question.get('question', '')}",
            f"标准答案：{question.get('answer_summary', '')}",
            f"关键点：{key_points}",
            f"加分点：{optional_points}",
            f"期望信号：{expected_signals}",
            f"常见错误：{common_mistakes}",
            f"候选追问：{followup_questions}",
        ]
        return "。".join(part for part in parts if part and not part.endswith("："))

    def _expand_question_views(self, questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        documents = []

        for q in questions:
            question_meta = {
                "source_id": q["id"],
                "view_type": "question",
                "role": q.get("role", ""),
                "position": q.get("position", q.get("role", "")),
                "question": q.get("question", ""),
                "category": q.get("category", ""),
                "subcategory": q.get("subcategory", ""),
                "competency": q.get("competency", []),
                "difficulty": q.get("difficulty", ""),
                "question_type": q.get("question_type", ""),
                "round_type": q.get("round_type", "technical"),
                "question_intent": q.get("question_intent", "screening"),
                "keywords": q.get("keywords", []),
                "tags": q.get("tags", []),
                "retrieval_text": self._build_question_dense_text(q),
                "source": q.get("source", ""),
                "source_type": q.get("source_type", ""),
            }
            documents.append({
                "id": f"{q['id']}#question",
                "document": question_meta["retrieval_text"],
                "metadata": question_meta,
            })

            rubric_meta = {
                "source_id": q["id"],
                "view_type": "rubric",
                "role": q.get("role", ""),
                "position": q.get("position", q.get("role", "")),
                "question": q.get("question", ""),
                "category": q.get("category", ""),
                "subcategory": q.get("subcategory", ""),
                "competency": q.get("competency", []),
                "difficulty": q.get("difficulty", ""),
                "question_type": q.get("question_type", ""),
                "round_type": q.get("round_type", "technical"),
                "question_intent": q.get("question_intent", "screening"),
                "keywords": q.get("keywords", []),
                "expected_answer_signals": q.get("expected_answer_signals", []),
                "answer_summary": q.get("answer_summary", ""),
                "key_points": q.get("key_points", []),
                "optional_points": q.get("optional_points", []),
                "common_mistakes": q.get("common_mistakes", []),
                "scoring_rubric": q.get("scoring_rubric", {}),
                "aliases": q.get("aliases", {}),
                "rubric_version": q.get("rubric_version", "unknown"),
                "followups": q.get("followups", []),
                "retrieval_text": self._build_rubric_dense_text(q),
                "source": q.get("source", ""),
                "source_type": q.get("source_type", ""),
                "tags": q.get("tags", []),
            }
            if q.get("answer"):
                rubric_meta["answer"] = q["answer"]
            documents.append({
                "id": f"{q['id']}#rubric",
                "document": rubric_meta["retrieval_text"],
                "metadata": rubric_meta,
            })

        return documents

    def add_question(self, question_id: str, question: str, answer: str = "",
                     metadata: Dict[str, Any] = None):
        """
        添加问题到知识库

        Args:
            question_id: 唯一 ID
            question: 问题文本
            answer: 答案文本（可选）
            metadata: 额外元数据
        """
        # 生成向量
        embedding = self.embedder.encode(question) if self.embedder else None

        # 准备元数据
        meta = metadata or {}
        if answer:
            meta["answer"] = answer
        normalized_meta = self._normalize_metadata(meta)

        if self.collection is not None:
            # ChromaDB 模式
            self.collection.add(
                ids=[question_id],
                embeddings=[embedding.tolist() if embedding is not None else None],
                documents=[question],
                metadatas=[normalized_meta]
            )
        else:
            # 本地存储模式
            self._fallback_data["ids"].append(question_id)
            self._fallback_data["embeddings"].append(embedding.tolist() if embedding is not None else [])
            self._fallback_data["documents"].append(question)
            self._fallback_data["metadatas"].append(meta)

    def add_questions_batch(self, questions: List[Dict[str, Any]]):
        """
        批量添加问题（支持新格式）

        Args:
            questions: 问题列表，每项包含 id, role, question, category, subcategory,
                      difficulty, question_type, keywords, answer_summary, key_points,
                      optional_points, common_mistakes, scoring_rubric, followups,
                      retrieval_text, source_type, tags 等字段
        """
        view_documents = self._expand_question_views(questions)
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for item in view_documents:
            ids.append(item["id"])
            documents.append(item["document"])
            metadatas.append(item["metadata"])
            embedding = self.embedder.encode(item["document"]) if self.embedder else None
            embeddings.append(embedding.tolist() if embedding is not None else None)

        if self.collection is not None:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=[self._normalize_metadata(meta) for meta in metadatas]
            )
        else:
            self._fallback_data["ids"].extend(ids)
            self._fallback_data["embeddings"].extend(embeddings)
            self._fallback_data["documents"].extend(documents)
            self._fallback_data["metadatas"].extend(metadatas)

        print(f"[OK] 批量添加 {len(view_documents)} 条索引文档（来自 {len(questions)} 道题）")

    def search(
        self,
        query: str,
        top_k: int = 5,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        语义搜索最相似的问题

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            相关问题列表
        """
        query_embedding = self.embedder.encode(query) if self.embedder else None

        if self.collection is not None:
            # ChromaDB 模式
            results = self.collection.query(
                query_embeddings=[query_embedding.tolist() if query_embedding is not None else None],
                n_results=top_k,
                include=["documents", "metadatas", "distances"],
                where=self._build_chroma_where(metadata_filters)
            )

            # 格式化结果
            items = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    metadata = self._restore_metadata(
                        results['metadatas'][0][i] if results['metadatas'] else {}
                    )
                    document = results['documents'][0][i] if results['documents'] else ""
                    items.append({
                        "id": doc_id,
                        "document": document,
                        "question": metadata.get("question", "") or document,
                        "metadata": metadata,
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            return items
        else:
            # 本地存储模式 - 余弦相似度
            return self._fallback_search(query, query_embedding, top_k, metadata_filters)

    def _fallback_search(
        self,
        query: str,
        query_embedding,
        top_k: int,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """本地存储的搜索实现（支持关键词匹配作为备选）"""
        import numpy as np

        if not self._fallback_data["ids"]:
            return []

        # 如果没有 embedding，使用关键词匹配
        if query_embedding is None:
            return self._keyword_search(query, top_k, metadata_filters)

        # 计算余弦相似度
        similarities = []
        for i, emb in enumerate(self._fallback_data["embeddings"]):
            metadata = self._fallback_data["metadatas"][i]
            if not self._metadata_matches(metadata, metadata_filters):
                continue
            if emb:
                emb_array = np.array(emb)
                sim = np.dot(query_embedding, emb_array) / (
                    np.linalg.norm(query_embedding) * np.linalg.norm(emb_array) + 1e-8
                )
                similarities.append((i, sim))

        # 按相似度排序
        similarities.sort(key=lambda x: x[1], reverse=True)

        # 返回 top_k
        items = []
        for i, sim in similarities[:top_k]:
            document = self._fallback_data["documents"][i]
            metadata = self._fallback_data["metadatas"][i]
            items.append({
                "id": self._fallback_data["ids"][i],
                "document": document,
                "question": metadata.get("question", "") or document,
                "metadata": metadata,
                "similarity": float(sim)
            })

        return items

    def _keyword_search(
        self,
        query: str,
        top_k: int,
        metadata_filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        基于关键词的搜索（当没有 embedding 模型时的备选方案）

        Args:
            query: 查询文本
            top_k: 返回结果数量

        Returns:
            匹配的问题列表
        """
        query_lower = query.lower()
        query_keywords = set(query_lower.split())

        scored_items = []

        for i, doc in enumerate(self._fallback_data["documents"]):
            doc_lower = doc.lower()
            metadata = self._fallback_data["metadatas"][i]
            if not self._metadata_matches(metadata, metadata_filters):
                continue

            score = 0.0

            # 1. 完全匹配得分最高
            if query_lower in doc_lower:
                score += 10.0

            # 2. 关键词匹配
            doc_words = set(doc_lower.split())
            common_words = query_keywords & doc_words
            if query_keywords:
                score += len(common_words) / len(query_keywords) * 5.0

            # 3. 元数据关键词匹配
            keywords = metadata.get("keywords", [])
            for kw in keywords:
                if kw.lower() in query_lower or query_lower in kw.lower():
                    score += 3.0

            # 4. 标签匹配
            tags = metadata.get("tags", [])
            for tag in tags:
                if tag.lower() in query_lower or query_lower in tag.lower():
                    score += 2.0

            # 5. 分类匹配
            category = metadata.get("category", "").lower()
            subcategory = metadata.get("subcategory", "").lower()
            if category in query_lower or query_lower in category:
                score += 2.0
            if subcategory in query_lower or query_lower in subcategory:
                score += 1.5

            if score > 0:
                scored_items.append((i, score))

        # 按得分排序
        scored_items.sort(key=lambda x: x[1], reverse=True)

        # 返回 top_k
        items = []
        for i, score in scored_items[:top_k]:
            # 归一化相似度到 0-1 范围
            normalized_sim = min(score / 10.0, 1.0)
            document = self._fallback_data["documents"][i]
            metadata = self._fallback_data["metadatas"][i]
            items.append({
                "id": self._fallback_data["ids"][i],
                "document": document,
                "question": metadata.get("question", "") or document,
                "metadata": metadata,
                "similarity": normalized_sim
            })

        return items

    def get_by_metadata(
        self,
        metadata_filters: Dict[str, Any],
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        if self.collection is not None:
            result = self.collection.get(
                where=self._build_chroma_where(metadata_filters),
                limit=limit,
                include=["documents", "metadatas"]
            )
            items = []
            if result and result.get("ids"):
                for i, doc_id in enumerate(result["ids"]):
                    metadata = self._restore_metadata(
                        result["metadatas"][i] if result.get("metadatas") else {}
                    )
                    document = result["documents"][i] if result.get("documents") else ""
                    items.append({
                        "id": doc_id,
                        "document": document,
                        "question": metadata.get("question", "") or document,
                        "metadata": metadata,
                    })
            return items

        items = []
        for i, doc_id in enumerate(self._fallback_data["ids"]):
            metadata = self._fallback_data["metadatas"][i]
            if not self._metadata_matches(metadata, metadata_filters):
                continue
            document = self._fallback_data["documents"][i]
            items.append({
                "id": doc_id,
                "document": document,
                "question": metadata.get("question", "") or document,
                "metadata": metadata,
            })
            if len(items) >= limit:
                break
        return items

    def save(self):
        """保存本地知识库"""
        if self.collection is not None:
            return

        if self._fallback_path and self._fallback_data["ids"]:
            with open(self._fallback_path, 'w', encoding='utf-8') as f:
                json.dump(self._fallback_data, f, ensure_ascii=False, indent=2)
            print(f"[OK] 知识库已保存：{self._fallback_path}")

    def count(self, metadata_filters: Optional[Dict[str, Any]] = None) -> int:
        """获取知识库问题数量"""
        if metadata_filters:
            return len(self.get_by_metadata(metadata_filters, limit=10000))
        if self.collection is not None:
            return self.collection.count()
        return len(self._fallback_data["ids"])

    def reset(self):
        """清空并重建当前集合/本地存储。"""
        if self.collection is not None and self.client is not None:
            try:
                self.client.delete_collection(self.collection_name)
            except Exception:
                pass
            self.collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}
            )
            return

        self._fallback_data = {
            "ids": [],
            "embeddings": [],
            "documents": [],
            "metadatas": []
        }
        if self._fallback_path and self._fallback_path.exists():
            try:
                self._fallback_path.unlink()
            except OSError:
                pass

    def clear_persist_dir(self):
        """彻底清理持久化目录，仅用于重建索引。"""
        if not self.persist_dir:
            self.reset()
            return

        persist_path = Path(self.persist_dir)
        if persist_path.exists():
            shutil.rmtree(persist_path, ignore_errors=True)

        self.client = None
        self.collection = None
        self._init_chroma()
