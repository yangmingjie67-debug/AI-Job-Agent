"""Chroma 持久化向量库封装。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import chromadb


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "knowledge_base" / "chroma_db"
COLLECTION_NAME = "job_agent_knowledge"


class VectorStore:
    """对 Chroma PersistentClient 的最小封装，避免业务层直接依赖 Chroma API。"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, collection_name: str = COLLECTION_NAME):
        path = Path(db_path)
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(name=collection_name)

    def add_documents(self, documents: list[dict[str, Any]]) -> int:
        """使用稳定 ID upsert 文档，重复入库不会无限增加记录。"""
        if not documents:
            return 0
        self.collection.upsert(
            ids=[str(item["chunk_id"]) for item in documents],
            documents=[str(item["text"]) for item in documents],
            embeddings=[item["embedding"] for item in documents],
            metadatas=[item["metadata"] for item in documents],
        )
        return len(documents)

    def similarity_search(self, query_embedding: list[float], top_k: int = 5) -> dict[str, Any]:
        """按向量距离检索最相似内容。"""
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")
        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )

    def count(self) -> int:
        return int(self.collection.count())

    def reset_collection(self) -> None:
        """清空当前集合，供开发调试使用。"""
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(name=name)


_default_store: VectorStore | None = None


def get_default_store() -> VectorStore:
    global _default_store
    if _default_store is None:
        _default_store = VectorStore()
    return _default_store


def add_documents(documents: list[dict[str, Any]]) -> int:
    return get_default_store().add_documents(documents)


def similarity_search(query_embedding: list[float], top_k: int = 5) -> dict[str, Any]:
    return get_default_store().similarity_search(query_embedding, top_k)


def count() -> int:
    return get_default_store().count()


def reset_collection() -> None:
    get_default_store().reset_collection()
