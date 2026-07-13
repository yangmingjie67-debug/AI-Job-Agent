"""命令行知识库入库脚本。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.rag_service import ingest_directory  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="将知识库文档切块并写入 Chroma")
    parser.add_argument(
        "--directory",
        type=Path,
        default=PROJECT_ROOT / "knowledge_base" / "documents",
        help="知识库文档目录，默认使用项目内 knowledge_base/documents",
    )
    args = parser.parse_args()

    try:
        stats = ingest_directory(args.directory.resolve())
    except Exception:
        logging.exception("文档入库失败")
        return 1

    print(f"找到文件数: {stats['found_files']}")
    print(f"生成 chunks: {stats['chunks']}")
    print(f"成功写入条数: {stats['written']}")
    print(f"Chroma 集合当前总记录数: {stats['collection_count']}")
    print(f"入库耗时: {stats['elapsed_seconds']} 秒")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
