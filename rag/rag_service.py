"""RAG 入库和检索流程编排。

本阶段只返回检索到的原文，不调用大语言模型生成答案。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .document_loader import load_directory
from .embedding_service import encode_query, encode_texts
from .text_splitter import split_documents
from .vector_store import VectorStore, get_default_store


logger = logging.getLogger(__name__)


def ingest_directory(directory_path: str | Path, store: VectorStore | None = None) -> dict[str, int | float]:
    """读取目录、切块、生成向量并写入 Chroma，返回入库统计。"""
    import time

    started = time.perf_counter()
    documents, found_files = load_directory(directory_path)
    chunks = split_documents(documents)
    if chunks:
        embeddings = encode_texts([chunk["text"] for chunk in chunks])
        for chunk, embedding in zip(chunks, embeddings):
            chunk["embedding"] = embedding
    target = store or get_default_store()
    written = target.add_documents(chunks)
    return {
        "found_files": found_files,
        "chunks": len(chunks),
        "written": written,
        "collection_count": target.count(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }


def search(query: str, top_k: int = 5, store: VectorStore | None = None) -> list[dict[str, Any]]:
    """检索内容并统一返回页面需要的字段。"""
    if not query or not query.strip():
        raise ValueError("查询问题不能为空")
    target = store or get_default_store()
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
