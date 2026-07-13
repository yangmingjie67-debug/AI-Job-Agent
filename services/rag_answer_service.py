"""RAG 检索增强问答服务。"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from rag.rag_service import search
from services.deepseek_service import chat_completion


logger = logging.getLogger(__name__)
NO_KNOWLEDGE_MESSAGE = "知识库暂无相关内容。"
# Chroma 会始终返回 top_k，使用距离阈值识别确实不相关的问题。
MAX_RELEVANCE_DISTANCE = 1.65


def _safe_source(source: Any) -> str:
    """只保留文件名，避免返回本地绝对路径。"""
    source_text = str(source or "")
    return Path(source_text).name if source_text else ""


def _build_context(results: list[dict[str, Any]]) -> str:
    """将检索片段拼接成模型可读的上下文。"""
    return "\n\n".join(
        f"[知识片段 {index}]\n{result.get('content', '')}"
        for index, result in enumerate(results, start=1)
    )


def _collect_sources(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """按文件去重来源，保留该文件首次出现的页码。"""
    sources: list[dict[str, Any]] = []
    seen_files: set[str] = set()
    for result in results:
        file_name = _safe_source(result.get("source"))
        if file_name in seen_files:
            continue
        seen_files.add(file_name)
        sources.append({"file": file_name, "page": result.get("page")})
    return sources


def answer_query(query: str, top_k: int = 3) -> dict[str, Any]:
    """基于知识库回答问题，并返回回答和去重后的来源。"""
    started = time.perf_counter()
    normalized_query = query.strip() if isinstance(query, str) else ""
    if not normalized_query:
        raise ValueError("query 不能为空")

    try:
        retrieved_results = search(normalized_query, top_k=top_k)
        results = [
            result for result in retrieved_results
            if float(result.get("distance", float("inf"))) <= MAX_RELEVANCE_DISTANCE
        ]
        retrieval_count = len(results)
        if not results:
            logger.info(
                "RAG answer query=%r retrieval_count=0 llm_elapsed=0 total_elapsed=%.3f",
                normalized_query,
                time.perf_counter() - started,
            )
            return {"answer": NO_KNOWLEDGE_MESSAGE, "sources": []}

        messages = [
            {
                "role": "system",
                "content": (
                    "你是AI Job Agent知识助手。\n"
                    "只能依据提供的知识回答。\n"
                    "不知道就明确说不知道。\n"
                    "不要编造。"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"用户问题：\n{normalized_query}\n\n"
                    f"Context：\n{_build_context(results)}"
                ),
            },
        ]

        llm_started = time.perf_counter()
        answer = chat_completion(messages)
        llm_elapsed = time.perf_counter() - llm_started
        logger.info(
            "RAG answer query=%r retrieval_count=%d llm_elapsed=%.3f total_elapsed=%.3f",
            normalized_query,
            retrieval_count,
            llm_elapsed,
            time.perf_counter() - started,
        )
        return {"answer": str(answer), "sources": _collect_sources(results)}
    except Exception:
        logger.exception(
            "RAG answer failed query=%r total_elapsed=%.3f",
            normalized_query,
            time.perf_counter() - started,
        )
        raise
