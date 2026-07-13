"""知识库文档读取模块。

支持 PDF、DOCX 和 UTF-8 TXT。单个文件读取失败时只记录日志并跳过，
避免一个坏文件中断整批知识库入库。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader


logger = logging.getLogger(__name__)
SUPPORTED_SUFFIXES = {".pdf", ".docx", ".txt"}


def _record(text: str, source: Path, page: int | None, file_type: str) -> dict[str, Any]:
    """统一生成文档记录，保留后续切块和检索需要的元数据。"""
    return {
        "text": text.strip(),
        "source": source.name,
        "page": page,
        "file_type": file_type,
    }


def _load_pdf(path: Path) -> list[dict[str, Any]]:
    reader = PdfReader(str(path))
    records = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        if text:
            records.append(_record(text, path, page_number, "pdf"))
    return records


def _load_docx(path: Path) -> list[dict[str, Any]]:
    document = Document(str(path))
    text = "\n".join(paragraph.text for paragraph in document.paragraphs).strip()
    if not text:
        return []
    return [_record(text, path, None, "docx")]


def _load_txt(path: Path) -> list[dict[str, Any]]:
    text = path.read_text(encoding="utf-8-sig").strip()
    if not text:
        return []
    return [_record(text, path, None, "txt")]


def load_file(file_path: str | Path) -> list[dict[str, Any]]:
    """读取单个支持的文件，失败时记录日志并返回空列表。"""
    path = Path(file_path)
    if not path.is_file():
        logger.warning("忽略不存在的文件: %s", path)
        return []

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_SUFFIXES:
        logger.info("忽略不支持的文件类型: %s", path)
        return []

    try:
        if suffix == ".pdf":
            records = _load_pdf(path)
        elif suffix == ".docx":
            records = _load_docx(path)
        else:
            records = _load_txt(path)
        logger.info("读取文件成功: %s, records=%d", path, len(records))
        return records
    except Exception:
        logger.exception("读取文件失败，跳过该文件: %s", path)
        return []


def load_directory(directory_path: str | Path) -> tuple[list[dict[str, Any]], int]:
    """递归读取目录中的支持文件，返回记录和发现的文件数量。"""
    directory = Path(directory_path)
    if not directory.is_dir():
        raise NotADirectoryError(f"知识库目录不存在: {directory}")

    files = sorted(
        path for path in directory.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )
    records: list[dict[str, Any]] = []
    for path in files:
        records.extend(load_file(path))
    return records, len(files)
