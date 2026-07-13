"""安全执行 Agent 工具并统一处理参数、日志和 JSON 结果。"""

from __future__ import annotations

import json
import logging
import time
from decimal import Decimal
from pathlib import Path
from typing import Any

from .tool_registry import TOOL_FUNCTIONS


logger = logging.getLogger(__name__)


def _json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    try:
        return value.item()
    except AttributeError:
        return str(value)


def execute_tool(tool_name: str, arguments: dict[str, Any] | str) -> dict[str, Any]:
    """执行单个工具；任何单工具异常都转换为可继续处理的 JSON 结果。"""
    started = time.perf_counter()
    parameter_names: list[str] = []
    try:
        if tool_name not in TOOL_FUNCTIONS:
            raise ValueError(f"未知工具：{tool_name}")
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError as exc:
                raise ValueError("工具参数不是合法 JSON") from exc
        if not isinstance(arguments, dict):
            raise ValueError("工具参数必须是对象或 JSON 字符串")
        parameter_names = sorted(str(key) for key in arguments)
        result = TOOL_FUNCTIONS[tool_name](**arguments)
        safe_result = _json_safe(result)
        json.dumps(safe_result, ensure_ascii=False)
        logger.info(
            "tool=%s parameters=%s elapsed=%.3f success=true",
            tool_name,
            parameter_names,
            time.perf_counter() - started,
        )
        return {"success": True, "data": safe_result}
    except Exception as exc:
        logger.exception(
            "tool=%s parameters=%s elapsed=%.3f success=false",
            tool_name,
            parameter_names,
            time.perf_counter() - started,
        )
        return {"success": False, "error": str(exc)}
