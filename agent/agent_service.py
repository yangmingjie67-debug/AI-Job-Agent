"""基于 DeepSeek Function Calling 的最小 Agent 循环。"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

from services.deepseek_service import chat_completion

from .tool_executor import execute_tool
from .tool_registry import TOOL_DEFINITIONS


logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 3


SYSTEM_PROMPT = """你是 AI Job Agent。
你可以根据用户需求调用工具完成任务。
工具选择要求：
- 用户查询知识库、RAG、项目知识时，必须调用 search_knowledge_base。
- 用户要求分析岗位、JD、职责、技能或关键词时，必须调用 analyze_job_description。
- 用户同时提供 resume_text 和 jd_text，并要求匹配、判断是否适合或评估简历时，必须调用 match_resume_to_job。
- 用户同时提供 resume_text 和 jd_text，并要求生成 BOSS、招聘平台或打招呼语时，必须调用 generate_boss_greeting。
只要对应工具所需字段已经提供，就立即调用工具，不要先询问澄清问题。
只有实际调用过工具，才能声称已经执行工具。
工具结果不足时必须明确说明，不要编造简历、岗位或知识库中不存在的信息。
普通聊天不需要调用工具。
回答保持简洁、自然、实用。"""


def _message_content(message: Any) -> str:
    return str(getattr(message, "content", None) or "")


def _tool_calls(message: Any) -> list[Any]:
    return list(getattr(message, "tool_calls", None) or [])


def _assistant_message(message: Any, calls: list[Any]) -> dict[str, Any]:
    result: dict[str, Any] = {"role": "assistant", "content": _message_content(message)}
    if calls:
        result["tool_calls"] = [
            {
                "id": str(getattr(call, "id", "")),
                "type": "function",
                "function": {
                    "name": str(getattr(getattr(call, "function", None), "name", "")),
                    "arguments": str(getattr(getattr(call, "function", None), "arguments", "{}")),
                },
            }
            for call in calls
        ]
    return result


def _call_fingerprint(name: str, arguments: str) -> str:
    return hashlib.sha256(f"{name}\n{arguments}".encode("utf-8")).hexdigest()


def run_agent(user_message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """运行最多三轮工具调用的 Agent。"""
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("message 不能为空")
    if context is not None and not isinstance(context, dict):
        raise ValueError("context 必须是对象")

    content = user_message.strip()
    if context:
        content += "\n\n可用上下文：\n" + json.dumps(context, ensure_ascii=False)
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": content},
    ]
    summaries: list[dict[str, Any]] = []
    fingerprints: set[str] = set()
    llm_calls = 0

    for round_number in range(1, MAX_TOOL_ROUNDS + 1):
        message = chat_completion(
            messages,
            tools=TOOL_DEFINITIONS,
            tool_choice="auto",
            return_message=True,
        )
        llm_calls += 1
        calls = _tool_calls(message)
        if not calls:
            return {
                "success": True,
                "answer": _message_content(message),
                "tool_calls": summaries,
                "rounds": round_number - 1,
                "llm_calls": llm_calls,
            }

        messages.append(_assistant_message(message, calls))
        for call in calls:
            function = getattr(call, "function", None)
            name = str(getattr(function, "name", ""))
            arguments = str(getattr(function, "arguments", "{}"))
            fingerprint = _call_fingerprint(name, arguments)
            if fingerprint in fingerprints:
                return {
                    "success": False,
                    "error": "检测到重复工具调用，已停止以避免无限循环。",
                    "tool_calls": summaries,
                    "rounds": round_number,
                    "llm_calls": llm_calls,
                }
            fingerprints.add(fingerprint)
            result = execute_tool(name, arguments)
            summaries.append({"name": name, "success": result.get("success", False), "round": round_number})
            messages.append({
                "role": "tool",
                "tool_call_id": str(getattr(call, "id", "")),
                "content": json.dumps(result, ensure_ascii=False),
            })

        if round_number == MAX_TOOL_ROUNDS:
            return {
                "success": False,
                "error": "工具调用已达到最多 3 轮，已停止继续调用。",
                "tool_calls": summaries,
                "rounds": round_number,
                "llm_calls": llm_calls,
            }

    return {"success": False, "error": "Agent 未能完成请求。", "tool_calls": summaries, "rounds": MAX_TOOL_ROUNDS, "llm_calls": llm_calls}
