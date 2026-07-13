"""RAG 入库和检索流程编排。

本阶段只返回检索到的原文，不调用大语言模型生成答案。
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .document_loader import load_directory
from .embedding_service import encode_query, encode_texts
from .text_splitter import split_documents
from .vector_store import VectorStore, get_default_store


logger = logging.getLogger(__name__)
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENT_DIRECTORY = Path(
    os.getenv("KNOWLEDGE_BASE_DIRECTORY", str(PROJECT_ROOT / "knowledge_base" / "documents"))
)


def _log_stats(prefix: str, directory_path: str | Path, stats: dict[str, int | float]) -> None:
    logger.info(
        "%s directory=%s found_files=%s chars/chunks=%s chunks=%s written=%s collection=%s elapsed=%s",
        prefix,
        Path(directory_path).resolve(),
        stats.get("found_files"),
        stats.get("characters"),
        stats.get("chunks"),
        stats.get("written"),
        stats.get("collection_count"),
        stats.get("elapsed_seconds"),
    )


def ingest_directory(directory_path: str | Path, store: VectorStore | None = None) -> dict[str, int | float]:
    """读取目录、切块、生成向量并写入 Chroma，返回入库统计。"""
    import time

    started = time.perf_counter()
    documents, found_files = load_directory(directory_path)
    characters = sum(len(str(document.get("text") or "")) for document in documents)
    logger.info("RAG parse directory=%s files=%d characters=%d", Path(directory_path).resolve(), found_files, characters)
    chunks = split_documents(documents)
    logger.info("RAG split directory=%s chunks=%d", Path(directory_path).resolve(), len(chunks))
    if chunks:
        embeddings = encode_texts([chunk["text"] for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
    target = store or get_default_store()
    written = target.add_documents(chunks)
    stats = {
        "found_files": found_files,
        "chunks": len(chunks),
        "written": written,
        "characters": characters,
        "collection_count": target.count(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    if chunks and written != len(chunks):
        raise RuntimeError(f"Chroma wrote {written} of {len(chunks)} chunks")
    _log_stats("RAG ingest complete", directory_path, stats)
    return stats


def search(query: str, top_k: int = 5, store: VectorStore | None = None) -> list[dict[str, Any]]:
    """检索内容并统一返回页面需要的字段。"""
    if not query or not query.strip():
        raise ValueError("查询问题不能为空")
    target = store or get_default_store()
    if target.count() == 0 and DEFAULT_DOCUMENT_DIRECTORY.is_dir():
        logger.warning(
            "RAG collection is empty before query; rebuilding from %s",
            DEFAULT_DOCUMENT_DIRECTORY.resolve(),
        )
        ingest_directory(DEFAULT_DOCUMENT_DIRECTORY, store=target)
    result = target.similarity_search(encode_query(query), top_k=top_k)
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]
    items = []
    for content, metadata, distance in zip(documents, metadatas, distances):
        page = metadata.get("page")
        if page in ("", None):
            page = None
        items.append({
            "content": content,
            "source": metadata.get("source", ""),
            "page": page,
            "distance": distance,
            "score": round(1 / (1 + distance), 6),
            "metadata": metadata,
        })
    return items


def get_collection_count(store: VectorStore | None = None) -> int:
    return (store or get_default_store()).count()
