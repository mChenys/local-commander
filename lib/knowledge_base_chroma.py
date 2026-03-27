"""
AI Knowledge Base - ChromaDB 版本
使用 ChromaDB 进行向量存储，支持大规模知识库和高效元数据过滤
"""

import json
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional
import uuid


class KnowledgeBaseChroma:
    """AI 知识库管理器 - ChromaDB 版本"""

    def __init__(self, storage_dir: Optional[Path] = None, collection_name: str = "knowledge"):
        """
        初始化知识库

        Args:
            storage_dir: 存储目录，默认 ~/.claude/knowledge/
            collection_name: 集合名称
        """
        if storage_dir is None:
            storage_dir = Path.home() / ".claude" / "knowledge_chroma"

        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.collection_name = collection_name
        self._client = None
        self._collection = None
        self._embedder = None

        # 元数据文件（用于存储额外信息）
        self.metadata_file = self.storage_dir / "meta.json"

    @property
    def client(self):
        """延迟初始化 ChromaDB 客户端"""
        if self._client is None:
            import chromadb
            self._client = chromadb.PersistentClient(path=str(self.storage_dir))
        return self._client

    @property
    def collection(self):
        """延迟初始化集合"""
        if self._collection is None:
            # 获取或创建集合
            self._collection = self.client.get_or_create_collection(
                name=self.collection_name,
                metadata={"hnsw:space": "cosine"}  # 使用余弦相似度
            )
        return self._collection

    @property
    def embedder(self):
        """延迟加载 embedder"""
        if self._embedder is None:
            from embedder import get_embedder
            self._embedder = get_embedder(backend="huggingface", model="bge-m3")
        return self._embedder

    def _generate_id(self) -> str:
        """生成知识点 ID"""
        return f"kb_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

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
        kb_id = self._generate_id()

        # 自动生成摘要
        if summary is None:
            summary = text[:100] + "..." if len(text) > 100 else text

        now = datetime.now().isoformat()

        # 元数据
        metadata = {
            "category": category,
            "tags": ",".join(tags or []),  # Chroma 不支持列表，转为逗号分隔
            "source": source,
            "importance": importance,
            "created_at": now,
            "updated_at": now,
            "access_count": 0,
            "summary": summary
        }

        # 添加到 Chroma
        self.collection.add(
            ids=[kb_id],
            documents=[text],
            metadatas=[metadata]
        )

        return {
            "id": kb_id,
            "text": text,
            "summary": summary,
            "category": category,
            "tags": tags or [],
            "source": source,
            "created_at": now,
            "updated_at": now,
            "importance": importance,
            "access_count": 0
        }

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
            tags: 限定标签

        Returns:
            匹配的知识点列表
        """
        # 构建 where 过滤条件
        where = None
        if category or tags:
            conditions = []
            if category:
                conditions.append({"category": category})
            if tags:
                # Chroma 的 $contains 用于字符串包含
                for tag in tags:
                    conditions.append({"tags": {"$contains": tag}})

            if len(conditions) == 1:
                where = conditions[0]
            elif len(conditions) > 1:
                where = {"$and": conditions}

        # 查询
        results = self.collection.query(
            query_texts=[query],
            n_results=top_k,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

        # 解析结果
        items = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i]

                # 更新访问计数
                self._increment_access_count(doc_id)

                items.append({
                    "id": doc_id,
                    "text": results["documents"][0][i],
                    "score": 1 - results["distances"][0][i],  # 距离转相似度
                    "summary": metadata.get("summary", ""),
                    "category": metadata.get("category", "general"),
                    "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                    "source": metadata.get("source", ""),
                    "importance": metadata.get("importance", 0.5),
                    "created_at": metadata.get("created_at", ""),
                    "updated_at": metadata.get("updated_at", ""),
                    "access_count": metadata.get("access_count", 0) + 1
                })

        return items

    def _increment_access_count(self, doc_id: str):
        """增加访问计数"""
        try:
            # 获取当前元数据
            result = self.collection.get(ids=[doc_id], include=["metadatas"])
            if result["metadatas"]:
                metadata = result["metadatas"][0].copy()
                metadata["access_count"] = metadata.get("access_count", 0) + 1

                # 更新
                self.collection.update(
                    ids=[doc_id],
                    metadatas=[metadata]
                )
        except Exception:
            pass  # 静默失败

    def get(self, kb_id: str) -> Optional[Dict[str, Any]]:
        """根据 ID 获取知识点"""
        try:
            result = self.collection.get(
                ids=[kb_id],
                include=["documents", "metadatas"]
            )

            if result["ids"]:
                metadata = result["metadatas"][0]
                return {
                    "id": kb_id,
                    "text": result["documents"][0],
                    "summary": metadata.get("summary", ""),
                    "category": metadata.get("category", "general"),
                    "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                    "source": metadata.get("source", ""),
                    "importance": metadata.get("importance", 0.5),
                    "created_at": metadata.get("created_at", ""),
                    "updated_at": metadata.get("updated_at", ""),
                    "access_count": metadata.get("access_count", 0)
                }
        except Exception:
            pass

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
        try:
            result = self.collection.get(
                ids=[kb_id],
                include=["documents", "metadatas"]
            )

            if not result["ids"]:
                return None

            # 更新元数据
            metadata = result["metadatas"][0].copy()
            metadata["updated_at"] = datetime.now().isoformat()

            if category is not None:
                metadata["category"] = category
            if tags is not None:
                metadata["tags"] = ",".join(tags)
            if summary is not None:
                metadata["summary"] = summary
            if importance is not None:
                metadata["importance"] = importance

            # 更新
            if text is not None:
                self.collection.update(
                    ids=[kb_id],
                    documents=[text],
                    metadatas=[metadata]
                )
            else:
                self.collection.update(
                    ids=[kb_id],
                    metadatas=[metadata]
                )

            return self.get(kb_id)

        except Exception:
            return None

    def delete(self, kb_id: str) -> bool:
        """删除知识点"""
        try:
            self.collection.delete(ids=[kb_id])
            return True
        except Exception:
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
        # 构建 where 条件
        where = None
        if category or tags:
            conditions = []
            if category:
                conditions.append({"category": category})
            if tags:
                for tag in tags:
                    conditions.append({"tags": {"$contains": tag}})

            if len(conditions) == 1:
                where = conditions[0]
            elif len(conditions) > 1:
                where = {"$and": conditions}

        # 获取所有匹配的知识点
        result = self.collection.get(
            where=where,
            include=["documents", "metadatas"]
        )

        if not result["ids"]:
            return []

        # 解析并排序
        items = []
        for i, doc_id in enumerate(result["ids"]):
            metadata = result["metadatas"][i]
            items.append({
                "id": doc_id,
                "text": result["documents"][i],
                "summary": metadata.get("summary", ""),
                "category": metadata.get("category", "general"),
                "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                "source": metadata.get("source", ""),
                "importance": metadata.get("importance", 0.5),
                "created_at": metadata.get("created_at", ""),
                "updated_at": metadata.get("updated_at", ""),
                "access_count": metadata.get("access_count", 0)
            })

        # 按重要性排序
        items.sort(key=lambda x: x.get("importance", 0), reverse=True)

        # 分页
        return items[offset:offset + limit]

    def stats(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        count = self.collection.count()

        # 获取所有元数据用于统计
        result = self.collection.get(include=["metadatas"])

        categories = {}
        tags_count = {}

        if result["metadatas"]:
            for metadata in result["metadatas"]:
                cat = metadata.get("category", "general")
                categories[cat] = categories.get(cat, 0) + 1

                for tag in metadata.get("tags", "").split(","):
                    if tag:
                        tags_count[tag] = tags_count.get(tag, 0) + 1

        # 计算存储大小
        storage_size = sum(
            f.stat().st_size for f in self.storage_dir.rglob("*") if f.is_file()
        )

        return {
            "total": count,
            "categories": categories,
            "top_tags": dict(sorted(tags_count.items(), key=lambda x: x[1], reverse=True)[:10]),
            "storage_size_mb": storage_size / (1024 * 1024),
            "backend": "chromadb",
            "collection_name": self.collection_name
        }

    def clear(self):
        """清空知识库"""
        # 删除集合并重新创建
        self.client.delete_collection(self.collection_name)
        self._collection = None  # 重置集合引用

    def export(self, filepath: str):
        """导出知识库到文件"""
        result = self.collection.get(include=["documents", "metadatas"])

        export_data = {
            "version": "2.0",
            "backend": "chromadb",
            "exported_at": datetime.now().isoformat(),
            "items": []
        }

        if result["ids"]:
            for i, doc_id in enumerate(result["ids"]):
                metadata = result["metadatas"][i]
                export_data["items"].append({
                    "id": doc_id,
                    "text": result["documents"][i],
                    "summary": metadata.get("summary", ""),
                    "category": metadata.get("category", "general"),
                    "tags": metadata.get("tags", "").split(",") if metadata.get("tags") else [],
                    "source": metadata.get("source", ""),
                    "importance": metadata.get("importance", 0.5),
                    "created_at": metadata.get("created_at", ""),
                    "updated_at": metadata.get("updated_at", ""),
                    "access_count": metadata.get("access_count", 0)
                })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

    def import_from(self, filepath: str, merge: bool = True):
        """从文件导入知识库"""
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])

        if not merge:
            self.clear()

        # 批量添加
        ids = []
        documents = []
        metadatas = []

        for item in items:
            ids.append(item["id"])
            documents.append(item["text"])
            metadatas.append({
                "category": item.get("category", "general"),
                "tags": ",".join(item.get("tags", [])),
                "source": item.get("source", ""),
                "importance": item.get("importance", 0.5),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "access_count": item.get("access_count", 0),
                "summary": item.get("summary", "")
            })

        if ids:
            self.collection.add(
                ids=ids,
                documents=documents,
                metadatas=metadatas
            )

    def migrate_from_numpy(self, old_storage_dir: str):
        """
        从旧版 NumPy 存储迁移数据

        Args:
            old_storage_dir: 旧版存储目录
        """
        old_dir = Path(old_storage_dir)
        old_json = old_dir / "knowledge.json"

        if not old_json.exists():
            raise FileNotFoundError(f"旧版知识库不存在: {old_json}")

        with open(old_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        items = data.get("items", [])

        if not items:
            return {"migrated": 0}

        # 批量添加
        ids = []
        documents = []
        metadatas = []

        for item in items:
            ids.append(item["id"])
            documents.append(item["text"])
            metadatas.append({
                "category": item.get("category", "general"),
                "tags": ",".join(item.get("tags", [])),
                "source": item.get("source", ""),
                "importance": item.get("importance", 0.5),
                "created_at": item.get("created_at", ""),
                "updated_at": item.get("updated_at", ""),
                "access_count": item.get("access_count", 0),
                "summary": item.get("summary", "")
            })

        self.collection.add(
            ids=ids,
            documents=documents,
            metadatas=metadatas
        )

        return {"migrated": len(items)}


# 单例实例
_kb_instance = None

def get_knowledge_base() -> KnowledgeBaseChroma:
    """获取知识库单例"""
    global _kb_instance
    if _kb_instance is None:
        _kb_instance = KnowledgeBaseChroma()
    return _kb_instance
