"""基于 Chroma 默认 Embedding Function 的向量服务。"""

from __future__ import annotations

import logging
from threading import Lock

from chromadb.utils.embedding_functions import DefaultEmbeddingFunction


logger = logging.getLogger(__name__)
_embedding_function: DefaultEmbeddingFunction | None = None
_model_lock = Lock()


def get_embedding_function() -> DefaultEmbeddingFunction:
    """只初始化一次 Chroma 默认 Embedding Function。"""
    global _embedding_function
    if _embedding_function is None:
        with _model_lock:
            if _embedding_function is None:
                logger.info("加载 Chroma 默认 Embedding Function")
                _embedding_function = DefaultEmbeddingFunction()
    return _embedding_function


def encode_texts(texts: list[str]) -> list[list[float]]:
    """批量生成向量；空文本直接报错，避免写入无意义记录。"""
    if not texts or any(not str(text).strip() for text in texts):
        raise ValueError("Embedding 输入不能为空")
    # Chroma 默认实现可能返回 numpy.float32，持久化前统一转换为 Python float。
    return [[float(value) for value in vector] for vector in get_embedding_function()(texts)]


def encode_query(query: str) -> list[float]:
    """使用与文档完全相同的 Embedding Function 生成查询向量。"""
    if not query or not query.strip():
        raise ValueError("查询文本不能为空")
    return encode_texts([query])[0]
