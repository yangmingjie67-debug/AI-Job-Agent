"""AI Job Agent 的独立 RAG 基础模块。"""

from .rag_service import get_collection_count, ingest_directory, search

__all__ = ["get_collection_count", "ingest_directory", "search"]
