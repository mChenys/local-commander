"""
AI Knowledge Base - Claude Code 知识库系统
使用 BGE-M3 (PyTorch + MPS) 进行向量嵌入
"""

import json
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid


class KnowledgeBase:
    """AI 知识库管理器"""

    def __init__(self, storage_dir: Optional[Path] = None):
        """
        初始化知识库

        Args:
            storage_dir: 存储目录，默认 ~/.claude/knowledge/
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".claude" / "knowledge"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.metadata_file = self.storage_dir / "knowledge.json"
        self.embeddings_file = self.storage_dir / "embeddings.npy"
        self.config_file = self.storage_dir / "config.json"

        # 加载数据
        self.knowledge: List[Dict[str, Any]] = []
        self.embeddings: Optional[np.ndarray] = None
        self._embedder = None

        self._load()

    @property
    def embedder(self):
        """延迟加载 embedder"""
        if self._embedder is None:
            from .embedder import get_embedder
            self._embedder = get_embedder(backend="huggingface", model="bge-m3")
        return self._embedder

    def _load(self):
        """加载知识库数据"""
        # 加载元数据
        if self.metadata_file.exists():
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.knowledge = data.get("items", [])

        # 加载向量
        if self.embeddings_file.exists():
            self.embeddings = np.load(str(self.embeddings_file))

    def _save(self):
        """保存知识库数据"""
        # 保存元数据
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump({
                "version": "1.0",
                "items": self.knowledge,
                "updated_at": datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)

        # 保存向量
        if self.embeddings is not None:
            np.save(str(self.embeddings_file), self.embeddings)

    def add(
        self,
        text: str,
        category: str = "general",
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        source: str = "claude-code",
        importance: float = 0.5
    ) -> Dict[str, Any]:
        """
        添加知识点到知识库

        Args:
            text: 知识点内容
            category: 分类 (coding, architecture, debugging, tools, concepts, general)
            tags: 标签列表
            summary: 简短摘要
            source: 来源
            importance: 重要程度 0-1

        Returns:
            添加的知识点对象
        """
        # 生成 ID
        kb_id = f"kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        # 自动生成摘要
        if summary is None:
            summary = text[:100] + "..." if len(text) > 100 else text

        # 创建知识点
        item = {
            "id": kb_id,
            "text": text,
            "summary": summary,
            "category": category,
            "tags": tags or [],
            "source": source,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "importance": importance,
            "access_count": 0
        }

        # 生成向量
        embedding = self.embedder.encode([text])[0]

        # 添加到存储
        self.knowledge.append(item)
        if self.embeddings is None:
            self.embeddings = embedding.reshape(1, -1)
        else:
            self.embeddings = np.vstack([self.embeddings, embedding])

        self._save()

        return item

    def search(
        self,
        query: str,
        top_k: int = 5,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        搜索知识库

        Args:
            query: 查询文本
            top_k: 返回前 k 个结果
            category: 限定分类
            tags: 限定标签（需全部匹配）

        Returns:
            匹配的知识点列表
        """
        if not self.knowledge:
            return []

        # 生成查询向量
        query_vec = self.embedder.encode([query])[0]

        # 计算相似度
        scores = [
            self.embedder.similarity(query_vec, vec)
            for vec in self.embeddings
        ]

        # 过滤
        filtered_indices = []
        for i, item in enumerate(self.knowledge):
            # 分类过滤
            if category and item["category"] != category:
                continue
            # 标签过滤
            if tags:
                item_tags = set(item.get("tags", []))
                if not all(t in item_tags for t in tags):
                    continue
            filtered_indices.append(i)

        # 排序
        indexed_scores = [(i, scores[i]) for i in filtered_indices]
        indexed_scores.sort(key=lambda x: x[1], reverse=True)

        # 返回结果
        results = []
        for idx, score in indexed_scores[:top_k]:
            item = self.knowledge[idx].copy()
            item["score"] = score
            item["_index"] = idx
            results.append(item)

        # 更新访问计数
        for item in results:
            self.knowledge[item["_index"]]["access_count"] += 1
            del item["_index"]

        self._save()

        return results

    def get(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取知识点"""
        for item in self.knowledge:
            if item["id"] == kb_id:
                return item.copy()
        return None

    def update(
        self,
        kb_id: str,
        text: Optional[str] = None,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        summary: Optional[str] = None,
        importance: Optional[float] = None
    ) -> Optional[Dict[str, Any]]:
        """更新知识点"""
        for i, item in enumerate(self.knowledge):
            if item["id"] == kb_id:
                # 更新字段
                if text is not None:
                    item["text"] = text
                    # 重新生成向量
                    self.embeddings[i] = self.embedder.encode([text])[0]
                if category is not None:
                    item["category"] = category
                if tags is not None:
                    item["tags"] = tags
                if summary is not None:
                    item["summary"] = summary
                if importance is not None:
                    item["importance"] = importance

                item["updated_at"] = datetime.now().isoformat()
                self._save()
                return item.copy()

        return None

    def delete(self, kb_id: str) -> bool:
        """删除知识点"""
        for i, item in enumerate(self.knowledge):
            if item["id"] == kb_id:
                self.knowledge.pop(i)
                if self.embeddings is not None:
                    self.embeddings = np.delete(self.embeddings, i, axis=0)
                self._save()
                return True
        return False

    def list(
        self,
        category: Optional[str] = None,
        tags: Optional[List[str]] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        列出知识点

        Args:
            category: 限定分类
            tags: 限定标签
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            知识点列表
        """
        items = self.knowledge

        # 过滤
        if category:
            items = [i for i in items if i["category"] == category]
        if tags:
            items = [
                i for i in items
                if all(t in i.get("tags", []) for t in tags)
            ]

        # 按重要性排序
        items = sorted(items, key=lambda x: x.get("importance", 0), reverse=True)

        # 分页
        return items[offset:offset + limit]

    def stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        categories = {}
        tags_count = {}

        for item in self.knowledge:
            cat = item.get("category", "general")
            categories[cat] = categories.get(cat, 0) + 1

            for tag in item.get("tags", []):
                tags_count[tag] = tags_count.get(tag, 0) + 1

        return {
            "total": len(self.knowledge),
            "categories": categories,
            "top_tags": dict(sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:10]),
            "storage_size_mb": (
                self.metadata_file.stat().st_size +
                (self.embeddings_file.stat().st_size if self.embeddings_file.exists() else 0)
            ) / (1024 * 1024) if self.knowledge else 0
        }

    def clear(self):
        """清空知识库"""
        self.knowledge = []
        self.embeddings = None
        self._save()

    def export(self, filepath: str):
        """导出知识库到文件"""
        export_data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "items": self.knowledge,
            "embeddings": self.embeddings.tolist() if self.embeddings is not None else None
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def import_from(self, filepath: str, merge: bool = True):
        """从文件导入知识库"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])
        embeddings = data.get("embeddings")

        if merge:
            # 合并模式
            existing_ids = {i["id"] for i in self.knowledge}
            new_items = [i for i in items if i["id"] not in existing_ids]

            if new_items:
                self.knowledge.extend(new_items)
                if embeddings:
                    new_embeddings = np.array([embeddings[items.index(i)] for i in new_items])
                    if self.embeddings is None:
                        self.embeddings = new_embeddings
                    else:
                        self.embeddings = np.vstack([self.embeddings, new_embeddings])
                else:
                    # 重新生成向量
                    texts = [i["text"] for i in new_items]
                    new_embeddings = self.embedder.encode(texts)
                    if self.embeddings is None:
                        self.embeddings = new_embeddings
                    else:
                        self.embeddings = np.vstack([self.embeddings, new_embeddings])
        else:
            # 替换模式
            self.knowledge = items
            if embeddings:
                self.embeddings = np.array(embeddings)
            else:
                texts = [i["text"] for i in items]
                self.embeddings = self.embedder.encode(texts)

        self._save()


# 单例实例
_kb_instance = None

def get_knowledge_base() -> KnowledgeBase:
    """获取知识库单例"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBase()
    return _kb_instance
