"""
Embedding 模块 - 使用 text2vec 中文嵌入模型
"""

import numpy as np

class TextEmbedder:
    """文本向量化"""

    def __init__(self, model_name='shibing624/text2vec-base-chinese'):
        """
        初始化 Embedding 模型

        Args:
            model_name: 模型名称，可选：
                - shibing624/text2vec-base-chinese: 基础中文模型
                - shibing624/text2vec-large-chinese: 更大模型
                - BAAI/bge-base-zh-v1.5: BGE 中文模型
        """
        self.model_name = model_name
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
        """模拟 embedding（用于测试）"""
        # 使用简单的 hash 模拟，相同文本返回相同向量
        np.random.seed(hash(text) % (2**32))
        return np.random.randn(768).astype(np.float32)

    def get_dimension(self):
        """获取向量维度"""
        if self.model is not None:
            return self.model.get_sentence_embedding_dimension()
        return 768  # 默认维度
