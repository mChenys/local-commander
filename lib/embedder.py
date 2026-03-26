"""
Embedding 模块 - 支持 BGE-M3 等向量模型
支持两种后端: Ollama 和 HuggingFace (sentence-transformers)
"""

import subprocess
import json
import numpy as np
from typing import List, Optional, Dict, Any
from pathlib import Path


class Embedder:
    """向量嵌入器，支持多种后端"""

    def __init__(self, backend: str = "auto", model: str = "bge-m3"):
        """
        初始化 Embedder

        Args:
            backend: 后端类型 "ollama", "huggingface", "auto"
            model: 模型名称
        """
        self.model = model
        self.backend = self._detect_backend(backend) if backend == "auto" else backend
        self._hf_model = None

    def _detect_backend(self) -> str:
        """自动检测可用后端"""
        # 优先使用 HuggingFace（无需额外服务）
        try:
            from sentence_transformers import SentenceTransformer
            return "huggingface"
        except ImportError:
            pass

        # 其次检查 Ollama
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True, text=True, timeout=5
            )
            if "bge-m3" in result.stdout:
                return "ollama"
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

        raise RuntimeError("No embedding backend available. Install sentence-transformers or start ollama with bge-m3")

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        将文本转换为向量

        Args:
            texts: 文本列表

        Returns:
            向量数组 shape=(len(texts), embedding_dim)
        """
        if self.backend == "ollama":
            return self._encode_ollama(texts)
        else:
            return self._encode_huggingface(texts)

    def _encode_ollama(self, texts: List[str]) -> np.ndarray:
        """使用 Ollama HTTP API 生成 embedding"""
        import urllib.request
        import urllib.error

        embeddings = []
        ollama_url = "http://localhost:11434/api/embeddings"

        for text in texts:
            data = json.dumps({"model": self.model, "prompt": text}).encode('utf-8')
            req = urllib.request.Request(
                ollama_url,
                data=data,
                headers={"Content-Type": "application/json"}
            )

            try:
                with urllib.request.urlopen(req, timeout=60) as response:
                    result = json.loads(response.read().decode('utf-8'))
                    embeddings.append(result["embedding"])
            except urllib.error.URLError as e:
                raise RuntimeError(f"Ollama API error: {e}")

        return np.array(embeddings)

    def _encode_huggingface(self, texts: List[str]) -> np.ndarray:
        """使用 sentence-transformers 生成 embedding (PyTorch + MPS)"""
        if self._hf_model is None:
            from sentence_transformers import SentenceTransformer
            import torch

            model_name = "BAAI/bge-m3" if self.model == "bge-m3" else self.model

            # 选择设备：优先 MPS (Apple Silicon GPU)，其次 CPU
            if torch.backends.mps.is_available():
                device = "mps"
                print(f"[BGE-M3] 使用 MPS 加速 (Apple Silicon GPU)")
            elif torch.cuda.is_available():
                device = "cuda"
                print(f"[BGE-M3] 使用 CUDA 加速")
            else:
                device = "cpu"
                print(f"[BGE-M3] 使用 CPU")

            self._hf_model = SentenceTransformer(model_name, device=device)
            self._device = device

        embeddings = self._hf_model.encode(texts, normalize_embeddings=True)
        return embeddings

    def similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        return float(np.dot(vec1, vec2) / (np.linalg.norm(vec1) * np.linalg.norm(vec2)))

    def search(self, query: str, corpus: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        语义搜索

        Args:
            query: 查询文本
            corpus: 文档库
            top_k: 返回前 k 个结果

        Returns:
            排序后的结果列表 [{"text": ..., "score": ..., "index": ...}]
        """
        if not corpus:
            return []

        # 编码
        query_vec = self.encode([query])[0]
        corpus_vecs = self.encode(corpus)

        # 计算相似度
        scores = [self.similarity(query_vec, vec) for vec in corpus_vecs]

        # 排序
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            results.append({
                "text": corpus[idx],
                "score": score,
                "index": idx
            })

        return results


class KnowledgeBase:
    """简单的向量知识库"""

    def __init__(self, embedder: Optional[Embedder] = None):
        self.embedder = embedder or Embedder()
        self.documents: List[str] = []
        self.embeddings: Optional[np.ndarray] = None
        self.metadata: List[Dict[str, Any]] = []

    def add(self, documents: List[str], metadata: Optional[List[Dict]] = None):
        """添加文档到知识库"""
        if not documents:
            return

        new_embeddings = self.embedder.encode(documents)

        if self.embeddings is None:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])

        self.documents.extend(documents)

        if metadata:
            self.metadata.extend(metadata)
        else:
            self.metadata.extend([{} for _ in documents])

    def query(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """查询知识库"""
        if not self.documents:
            return []

        query_vec = self.embedder.encode([query])[0]

        # 计算相似度
        scores = [
            self.embedder.similarity(query_vec, vec)
            for vec in self.embeddings
        ]

        # 排序
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in indexed_scores[:top_k]:
            results.append({
                "text": self.documents[idx],
                "score": score,
                "metadata": self.metadata[idx]
            })

        return results

    def save(self, path: str):
        """保存知识库到文件"""
        data = {
            "documents": self.documents,
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else None,
            "metadata": self.metadata
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load(self, path: str):
        """从文件加载知识库"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.documents = data["documents"]
        self.embeddings = np.array(data["embeddings"]) if data["embeddings"] else None
        self.metadata = data["metadata"]

    def clear(self):
        """清空知识库"""
        self.documents = []
        self.embeddings = None
        self.metadata = []


# 单例实例
_embedder_instance = None

def get_embedder(backend: str = "auto", model: str = "bge-m3") -> Embedder:
    """获取 Embedder 单例"""
    global _embedder_instance
    if _embedder_instance is None:
        _embedder_instance = Embedder(backend, model)
    return _embedder_instance
