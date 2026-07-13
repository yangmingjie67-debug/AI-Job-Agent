"""DeepSeek client service with backward-compatible tool calling support."""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx
import openai
from dotenv import load_dotenv
from openai import OpenAI


load_dotenv()
logger = logging.getLogger(__name__)

http_client = httpx.Client(trust_env=False)
client = OpenAI(
    api_key=os.environ.get("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    http_client=http_client,
)


def chat_completion(
    messages: list[dict[str, Any]],
    model: str = "deepseek-chat",
    tools: list[dict[str, Any]] | None = None,
    tool_choice: str | dict[str, Any] | None = None,
    return_message: bool = False,
) -> Any:
    """调用现有 DeepSeek 客户端，兼容普通文本和 Function Calling。"""
    try:
        request_kwargs: dict[str, Any] = {"model": model, "messages": messages}
        if tools is not None:
            request_kwargs["tools"] = tools
        if tool_choice is not None:
            request_kwargs["tool_choice"] = tool_choice
        message = client.chat.completions.create(**request_kwargs).choices[0].message
        return message if return_message else (message.content or "")
    except openai.APIConnectionError:
        logger.exception("DeepSeek API connection failed")
        if return_message:
            raise
        return "无法连接 DeepSeek API，请检查网络、VPN、代理或 API 地址。"
