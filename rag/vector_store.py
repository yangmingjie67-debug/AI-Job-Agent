"""Chroma 持久化向量库封装。"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import chromadb
from dotenv import load_dotenv


load_dotenv()
logger = logging.getLogger(__name__)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = Path(os.getenv("CHROMA_PERSIST_DIRECTORY", str(PROJECT_ROOT / "knowledge_base" / "chroma_db")))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION_NAME", "job_agent_knowledge")
EMBEDDING_MODEL_NAME = "chroma-default"


class VectorStore:
    """对 Chroma PersistentClient 的最小封装，避免业务层直接依赖 Chroma API。"""

    def __init__(self, db_path: str | Path = DEFAULT_DB_PATH, collection_name: str = COLLECTION_NAME):
        path = Path(db_path)
        path.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(path))
        self.collection = self.client.get_or_create_collection(name=collection_name)
        logger.info(
            "Chroma initialized path=%s collection=%s count=%d embedding_model=%s",
            path.resolve(), collection_name, self.collection.count(), EMBEDDING_MODEL_NAME,
        )

    def add_documents(self, documents: list[dict[str, Any]]) -> int:
        """使用稳定 ID upsert 文档，重复入库不会无限增加记录。"""
        if not documents:
            return 0
        before = self.collection.count()
        self.collection.upsert(
            ids=[str(item["chunk_id"]) for item in documents],
            documents=[str(item["text"]) for item in documents],
            embeddings=[item["embedding"] for item in documents],
            metadatas=[item["metadata"] for item in documents],
        )
        after = self.collection.count()
        logger.info(
            "Chroma upsert collection=%s before_count=%d chunks=%d after_count=%d",
            self.collection.name, before, len(documents), after,
        )
        if after < 1:
            raise RuntimeError("Chroma upsert completed but collection is empty")
        return len(documents)

    def similarity_search(self, query_embedding: list[float], top_k: int = 5) -> dict[str, Any]:
        """按向量距离检索最相似内容。"""
        if top_k <= 0:
            raise ValueError("top_k 必须大于 0")
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        logger.info(
            "Chroma query collection=%s count=%d result_count=%d distances=%s metadatas=%s",
            self.collection.name,
            self.collection.count(),
            len((result.get("documents") or [[]])[0]),
            (result.get("distances") or [[]])[0],
            (result.get("metadatas") or [[]])[0],
        )
        return result

    def count(self) -> int:
        return int(self.collection.count())

    def source_count(self, source: str) -> int:
        matches = self.collection.get(where={"source": source}, include=[])
        return len(matches.get("ids") or [])

    def reset_collection(self) -> None:
        """清空当前集合，供开发调试使用。"""
        name = self.collection.name
        self.client.delete_collection(name)
        self.collection = self.client.get_or_create_collection(name=name)

    def delete_by_source(self, source: str) -> int:
        """Delete all chunks belonging to one source file."""
        matches = self.collection.get(where={"source": source}, include=[])
        ids = matches.get("ids") or []
        if ids:
            self.collection.delete(ids=ids)
        logger.info("Chroma delete source=%s deleted=%d after_count=%d", source, len(ids), self.collection.count())
        return len(ids)


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
