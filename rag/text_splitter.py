"""轻量级字符切块模块，不引入 LangChain。"""

from __future__ import annotations

import hashlib
from typing import Any


def _stable_chunk_id(source: str, page: int | None, index: int, text: str) -> str:
    """使用来源、页码、序号和文本生成稳定 ID，重复入库时可安全 upsert。"""
    raw = f"{source}|{page}|{index}|{text}".encode("utf-8")
    return hashlib.sha1(raw).hexdigest()


def split_documents(
    documents: list[dict[str, Any]],
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> list[dict[str, Any]]:
    """按字符切块，并为每个切块保留原始元数据。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size 必须大于 0")
    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise ValueError("chunk_overlap 必须大于等于 0 且小于 chunk_size")

    chunks: list[dict[str, Any]] = []
    step = chunk_size - chunk_overlap
    for document in documents:
        text = str(document.get("text") or "").strip()
        if not text:
            continue

        source = str(document.get("source") or "")
        page = document.get("page")
        file_type = str(document.get("file_type") or "")
        index = 0
        for start in range(0, len(text), step):
            chunk_text = text[start:start + chunk_size].strip()
            if not chunk_text:
                continue
            metadata = {
                "source": source,
                "page": page if page is not None else "",
                "file_type": file_type,
                "chunk_index": index,
            }
            chunks.append({
                "chunk_id": _stable_chunk_id(source, page, index, chunk_text),
                "text": chunk_text,
                "metadata": metadata,
            })
            index += 1
            if start + chunk_size >= len(text):
                break
    return chunks
