"""RAG API 路由。"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from flask import Blueprint, jsonify, request

from rag.document_loader import SUPPORTED_SUFFIXES, load_file
from rag.rag_service import get_collection_count, ingest_directory, search
from rag.vector_store import reset_collection
from services.rag_answer_service import answer_query


logger = logging.getLogger(__name__)
rag_bp = Blueprint("rag", __name__, url_prefix="/api/rag")
PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DOCUMENT_DIRECTORY = PROJECT_ROOT / "knowledge_base" / "documents"
WINDOWS_INVALID_FILENAME_CHARS = set('<>:"|?*')


def _validate_upload_filename(raw_filename: str | None) -> tuple[str, str]:
    """校验上传文件名；乱码或 Windows 不安全名称改用唯一存储名。"""
    original_filename = str(raw_filename or "")
    filename = original_filename.strip()
    if not filename or filename in {".", ".."}:
        raise ValueError("文件名不能为空")
    if any(char in filename for char in ("/", "\\", "\x00")):
        raise ValueError("文件名不能包含路径字符")
    if any(ord(char) < 32 for char in filename):
        raise ValueError("文件名包含非法字符")

    suffix = Path(filename).suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 PDF、DOCX、TXT 文件")

    unsafe = (
        any(char in WINDOWS_INVALID_FILENAME_CHARS for char in filename)
        or "�" in filename
        or not filename.isprintable()
    )
    stored_filename = f"upload_{uuid4().hex[:12]}{suffix}" if unsafe else filename
    target = (DEFAULT_DOCUMENT_DIRECTORY / stored_filename).resolve()
    try:
        target.relative_to(DEFAULT_DOCUMENT_DIRECTORY.resolve())
    except ValueError as exc:
        raise ValueError("非法文件路径") from exc
    return original_filename, stored_filename


def _validate_stored_filename(raw_filename: str | None) -> str:
    """校验删除接口中的已存储文件名，禁止目录跳转和非法字符。"""
    filename = str(raw_filename or "").strip()
    if not filename or filename in {".", ".."}:
        raise ValueError("文件名不能为空")
    if any(char in filename for char in ("/", "\\", "\x00")):
        raise ValueError("文件名不能包含路径字符")
    if any(char in WINDOWS_INVALID_FILENAME_CHARS for char in filename):
        raise ValueError("文件名包含非法字符")
    if any(ord(char) < 32 for char in filename):
        raise ValueError("文件名包含非法字符")
    if Path(filename).suffix.lower() not in SUPPORTED_SUFFIXES:
        raise ValueError("仅支持 PDF、DOCX、TXT 文件")
    target = (DEFAULT_DOCUMENT_DIRECTORY / filename).resolve()
    try:
        target.relative_to(DEFAULT_DOCUMENT_DIRECTORY.resolve())
    except ValueError as exc:
        raise ValueError("非法文件路径") from exc
    return filename


def _list_knowledge_files() -> list[dict[str, Any]]:
    """列出文件安全信息，不暴露绝对路径。"""
    DEFAULT_DOCUMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    files = []
    for path in DEFAULT_DOCUMENT_DIRECTORY.iterdir():
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        stat = path.stat()
        files.append({
            "stored_filename": path.name,
            "file_type": path.suffix.lower().lstrip("."),
            "size_bytes": int(stat.st_size),
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
            "_mtime": stat.st_mtime,
        })
    files.sort(key=lambda item: item["_mtime"], reverse=True)
    for item in files:
        item.pop("_mtime", None)
    return files


def _rebuild_knowledge_base() -> dict[str, int | float]:
    """重建集合，确保删除或覆盖后没有旧向量残留。"""
    reset_collection()
    return ingest_directory(DEFAULT_DOCUMENT_DIRECTORY)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    try:
        return value.item()
    except AttributeError:
        return str(value)


def _safe_result(result: dict[str, Any]) -> dict[str, Any]:
    safe = dict(result)
    source = str(safe.get("source", ""))
    safe["source"] = Path(source).name if source else ""
    return _json_safe(safe)


@rag_bp.post("/search")
def rag_search():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "请求体必须是 JSON 对象"}), 400
    query = payload.get("query", "")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"success": False, "error": "query 不能为空"}), 400
    top_k = payload.get("top_k", 3)
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        return jsonify({"success": False, "error": "top_k 必须是 1 到 10 之间的整数"}), 400
    try:
        results = search(query.strip(), top_k=top_k)
        safe_results = [_safe_result(result) for result in results]
        return jsonify({"success": True, "query": query.strip(), "count": len(safe_results), "results": safe_results})
    except Exception:
        logger.exception("RAG 检索失败")
        return jsonify({"success": False, "error": "RAG 检索失败，请检查 Chroma 数据和 Embedding 配置"}), 500


@rag_bp.post("/ingest")
def rag_ingest():
    try:
        stats = ingest_directory(DEFAULT_DOCUMENT_DIRECTORY)
        return jsonify({
            "success": True,
            "files_processed": int(stats.get("found_files", 0)),
            "chunks_generated": int(stats.get("chunks", 0)),
            "records_written": int(stats.get("written", 0)),
            "collection_count": int(stats.get("collection_count", 0)),
            "elapsed_seconds": float(stats.get("elapsed_seconds", 0.0)),
        })
    except Exception:
        logger.exception("RAG 入库失败")
        return jsonify({"success": False, "error": "RAG 入库失败，请检查文档目录和 Chroma 数据目录"}), 500


@rag_bp.post("/answer")
def rag_answer():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "请求体必须是 JSON 对象"}), 400
    query = payload.get("query", "")
    if not isinstance(query, str) or not query.strip():
        return jsonify({"success": False, "error": "query 不能为空"}), 400
    try:
        result = answer_query(query)
        return jsonify({"success": True, "answer": result["answer"], "sources": result["sources"]})
    except Exception:
        logger.exception("RAG answer 接口失败")
        return jsonify({"success": False, "error": "RAG 知识问答失败，请稍后重试"}), 500


@rag_bp.post("/upload")
def rag_upload():
    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return jsonify({"success": False, "error": "请选择要上传的文件"}), 400
    try:
        original_filename, stored_filename = _validate_upload_filename(uploaded.filename)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400

    DEFAULT_DOCUMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    target = DEFAULT_DOCUMENT_DIRECTORY / stored_filename
    try:
        uploaded.save(target)
        if target.stat().st_size == 0:
            target.unlink(missing_ok=True)
            return jsonify({"success": False, "error": "文件不能为空"}), 400
        if not load_file(target):
            target.unlink(missing_ok=True)
            return jsonify({"success": False, "error": "文件解析失败或内容为空"}), 400
        stats = _rebuild_knowledge_base()
        return jsonify({
            "success": True,
            "original_filename": original_filename,
            "stored_filename": stored_filename,
            "filename": stored_filename,
            "files_processed": int(stats.get("found_files", 0)),
            "chunks_generated": int(stats.get("chunks", 0)),
            "records_written": int(stats.get("written", 0)),
            "collection_count": int(stats.get("collection_count", 0)),
        })
    except Exception:
        logger.exception("知识库文件上传或入库失败: %s", original_filename)
        return jsonify({"success": False, "error": "文件解析或入库失败，请检查文件内容"}), 400


@rag_bp.get("/files")
def rag_files():
    try:
        return jsonify({"success": True, "files": _list_knowledge_files()})
    except Exception:
        logger.exception("知识库文件列表读取失败")
        return jsonify({"success": False, "error": "无法读取知识库文件列表"}), 500


@rag_bp.delete("/files/<filename>")
def rag_delete_file(filename: str):
    try:
        safe_filename = _validate_stored_filename(filename)
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    target = (DEFAULT_DOCUMENT_DIRECTORY / safe_filename).resolve()
    if not target.is_file():
        return jsonify({"success": False, "error": "文件不存在"}), 404
    try:
        target.unlink()
        stats = _rebuild_knowledge_base()
        return jsonify({"success": True, "deleted": safe_filename, "collection_count": int(stats.get("collection_count", 0))})
    except Exception:
        logger.exception("知识库文件删除或重建失败: %s", safe_filename)
        return jsonify({"success": False, "error": "文件删除后知识库重建失败"}), 500
