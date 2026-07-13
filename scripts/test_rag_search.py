"""命令行 RAG 检索测试脚本。"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from rag.rag_service import search  # noqa: E402


logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def main() -> int:
    parser = argparse.ArgumentParser(description="测试 AI Job Agent 知识库相似度检索")
    parser.add_argument("query", nargs="*", help="检索问题；不传时进入交互输入")
    parser.add_argument("--top-k", type=int, default=3, help="返回结果数量，默认 3")
    args = parser.parse_args()
    query = " ".join(args.query).strip() or input("请输入检索问题: ").strip()

    try:
        results = search(query, top_k=args.top_k)
    except Exception:
        logging.exception("RAG 检索失败")
        return 1

    if not results:
        print("没有检索到结果。")
        return 0

    for rank, item in enumerate(results, start=1):
        print(f"\n===== 排名 {rank} =====")
        print(f"文本内容: {item['content']}")
        print(f"来源文件: {item['source']}")
        print(f"页码: {item['page'] if item['page'] is not None else '未知'}")
        print(f"distance: {item['distance']}")
        print(f"score: {item['score']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
