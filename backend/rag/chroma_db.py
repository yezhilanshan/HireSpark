"""
ChromaDB 向量存储模块
"""

import json
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

        if self.collection is not None:
            # ChromaDB 模式
            self.collection.add(
                ids=[question_id],
                embeddings=[embedding.tolist() if embedding is not None else None],
                documents=[question],
                metadatas=[meta]
            )
        else:
            # 本地存储模式
            self._fallback_data["ids"].append(question_id)
            self._fallback_data["embeddings"].append(embedding.tolist() if embedding is not None else [])
            self._fallback_data["documents"].append(question)
            self._fallback_data["metadatas"].append(meta)

    def add_questions_batch(self, questions: List[Dict[str, Any]]):
        """
        批量添加问题

        Args:
            questions: 问题列表，每项包含 id, question, answer, metadata
        """
        ids = []
        embeddings = []
        documents = []
        metadatas = []

        for q in questions:
            ids.append(q["id"])
            documents.append(q["question"])
            metadatas.append(q.get("metadata", {}))
            if q.get("answer"):
                metadatas[-1]["answer"] = q["answer"]

            embedding = self.embedder.encode(q["question"]) if self.embedder else None
            embeddings.append(embedding.tolist() if embedding is not None else None)

        if self.collection is not None:
            self.collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=documents,
                metadatas=metadatas
            )
        else:
            self._fallback_data["ids"].extend(ids)
            self._fallback_data["embeddings"].extend(embeddings)
            self._fallback_data["documents"].extend(documents)
            self._fallback_data["metadatas"].extend(metadatas)

        print(f"[OK] 批量添加 {len(questions)} 条问题")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
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
                include=["documents", "metadatas", "distances"]
            )

            # 格式化结果
            items = []
            if results and results['ids'] and len(results['ids'][0]) > 0:
                for i, doc_id in enumerate(results['ids'][0]):
                    items.append({
                        "id": doc_id,
                        "question": results['documents'][0][i] if results['documents'] else "",
                        "metadata": results['metadatas'][0][i] if results['metadatas'] else {},
                        "distance": results['distances'][0][i] if results['distances'] else 0
                    })
            return items
        else:
            # 本地存储模式 - 余弦相似度
            return self._fallback_search(query, query_embedding, top_k)

    def _fallback_search(self, query: str, query_embedding, top_k: int) -> List[Dict[str, Any]]:
        """本地存储的搜索实现"""
        import numpy as np

        if not self._fallback_data["ids"]:
            return []

        if query_embedding is None:
            # 没有 embedding，返回空
            return []

        # 计算余弦相似度
        similarities = []
        for i, emb in enumerate(self._fallback_data["embeddings"]):
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
            items.append({
                "id": self._fallback_data["ids"][i],
                "question": self._fallback_data["documents"][i],
                "metadata": self._fallback_data["metadatas"][i],
                "similarity": float(sim)
            })

        return items

    def save(self):
        """保存本地知识库"""
        if self._fallback_path and self._fallback_data["ids"]:
            with open(self._fallback_path, 'w', encoding='utf-8') as f:
                json.dump(self._fallback_data, f, ensure_ascii=False, indent=2)
            print(f"[OK] 知识库已保存：{self._fallback_path}")

    def count(self) -> int:
        """获取知识库问题数量"""
        if self.collection is not None:
            return self.collection.count()
        return len(self._fallback_data["ids"])
