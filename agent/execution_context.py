"""Resolve safe references used by planner steps."""

import re
from typing import Any

_CONTEXT = re.compile(r"^\$context\.([A-Za-z_][A-Za-z0-9_]*)$")
_STEP = re.compile(r"^\$steps\.([A-Za-z_][A-Za-z0-9_]*)\.data\.([A-Za-z_][A-Za-z0-9_]*)$")


class ReferenceError(ValueError):
    pass


def _resolve(value: Any, context: dict[str, Any], results: dict[str, dict[str, Any]]) -> Any:
    if isinstance(value, str):
        match = _CONTEXT.fullmatch(value)
        if match:
            key = match.group(1)
            if key not in context or context[key] in (None, ""):
                raise ReferenceError(f"context 缺少字段：{key}")
            return context[key]
        match = _STEP.fullmatch(value)
        if match:
            step_id, key = match.groups()
            result = results.get(step_id)
            if not result or not result.get("success"):
                raise ReferenceError(f"步骤 {step_id} 没有可用结果")
            data = result.get("data")
            if not isinstance(data, dict) or key not in data or data[key] in (None, ""):
                raise ReferenceError(f"步骤 {step_id} 的结果缺少字段：{key}")
            return data[key]
        if value.startswith("$context.") or value.startswith("$steps."):
            raise ReferenceError(f"不支持的引用：{value}")
        return value
    if isinstance(value, dict):
        return {key: _resolve(item, context, results) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve(item, context, results) for item in value]
    return value


def resolve_arguments(arguments: dict[str, Any], context: dict[str, Any] | None, results: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return _resolve(arguments, context or {}, results)

