"""
Embedding 模块 - 使用 text2vec 中文嵌入模型
"""

import os
import numpy as np

class TextEmbedder:
    """文本向量化"""

    def __init__(self, model_name=None):
        """
        初始化 Embedding 模型

        Args:
            model_name: 模型名称，可选：
                - shibing624/text2vec-base-chinese: 基础中文模型
                - shibing624/text2vec-large-chinese: 更大模型
                - BAAI/bge-base-zh-v1.5: BGE 中文模型
        """
        self.model_name = (
            model_name
            or str(os.environ.get('EMBEDDING_MODEL', '')).strip()
            or 'shibing624/text2vec-base-chinese'
        )
        self.model = None
        self._load_model()

    def _load_model(self):
        """加载 embedding 模型"""
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[*] 加载 embedding 模型：{self.model_name}")
            self.model = SentenceTransformer(self.model_name)
            print("[OK] 模型加载成功")
        except ImportError:
            print("[!] 未安装 sentence-transformers，使用模拟 embedding")
            print("    安装命令：pip install sentence-transformers")
            self.model = None
        except Exception as e:
            print(f"[!] 模型加载失败：{e}")
            print("    将使用模拟 embedding")
            self.model = None

    def encode(self, text):
        """
        将文本转换为向量

        Args:
            text: 输入文本

        Returns:
            numpy 数组（向量）
        """
        if self.model is not None:
            try:
                embedding = self.model.encode(text, convert_to_numpy=True)
                return embedding.astype(np.float32)
            except Exception as e:
                print(f"[!] 编码失败：{e}")
                return self._mock_encode(text)
        else:
            return self._mock_encode(text)

    def encode_batch(self, texts):
        """批量编码"""
        if self.model is not None:
            try:
                embeddings = self.model.encode(texts, convert_to_numpy=True)
                return embeddings.astype(np.float32)
            except Exception as e:
                print(f"[!] 批量编码失败：{e}")
                return [self._mock_encode(t) for t in texts]
        else:
            return [self._mock_encode(t) for t in texts]

    def _mock_encode(self, text):
        """模拟 embedding（用于测试）- 基于关键词的稀疏向量"""
        # 创建一个基于关键词的稀疏向量，使相似文本有相似的向量
        import re
        import hashlib

        # 提取关键词（简单的中文和英文分词）
        words = set(re.findall(r'[\u4e00-\u9fa5]{2,}|[a-zA-Z]+', text.lower()))

        # 创建稀疏向量表示（使用稳定的 hash 将词映射到向量位置）
        vector = np.zeros(768, dtype=np.float32)
        for word in words:
            # 使用 MD5 hash 确保跨会话一致性
            hash_obj = hashlib.md5(word.encode('utf-8'))
            hash_val = int(hash_obj.hexdigest(), 16) % 768
            # 使用词的长度作为权重的一个因素
            weight = min(len(word) * 0.1, 1.0)
            vector[hash_val] = weight

        # 归一化
        norm = np.linalg.norm(vector)
        if norm > 0:
            vector = vector / norm

        return vector

    def get_dimension(self):
        """获取向量维度"""
        if self.model is not None:
            return self.model.get_sentence_embedding_dimension()
        return 768  # 默认维度
