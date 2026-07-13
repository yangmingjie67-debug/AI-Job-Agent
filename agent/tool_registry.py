"""Agent 可调用工具的声明和实现注册表。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from rag.rag_service import search
from services.deepseek_service import chat_completion
from services.job_analysis_service import analyze_job_match


def search_knowledge_base(query: str, top_k: int = 3) -> dict[str, Any]:
    """搜索现有 RAG 知识库。"""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query 不能为空")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 10:
        raise ValueError("top_k 必须是 1 到 10 之间的整数")
    results = search(query.strip(), top_k=top_k)
    safe_results = []
    for result in results:
        item = dict(result)
        source = str(item.get("source", ""))
        item["source"] = Path(source).name if source else ""
        metadata = dict(item.get("metadata") or {})
        if metadata.get("source"):
            metadata["source"] = Path(str(metadata["source"])).name
        item["metadata"] = metadata
        safe_results.append(item)
    return {"results": safe_results}


def analyze_job_description(jd_text: str) -> dict[str, Any]:
    """复用当前 JD 分析调用能力。"""
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise ValueError("jd_text 不能为空")
    prompt = f"""请根据以下岗位JD，给出：
- 岗位核心要求
- 必备技能
- 加分技能
- 当前项目可以匹配哪些要求
- 还缺哪些技能
- 接下来7天学习建议

岗位描述：
{jd_text.strip()}"""
    answer = chat_completion([
        {"role": "system", "content": "你是一个岗位JD分析助手。"},
        {"role": "user", "content": prompt},
    ])
    return {"analysis": answer}


def match_resume_to_job(resume_text: str, jd_text: str) -> dict[str, Any]:
    """复用现有结构化简历岗位匹配服务。"""
    if not isinstance(resume_text, str) or not resume_text.strip():
        raise ValueError("resume_text 不能为空")
    if not isinstance(jd_text, str) or not jd_text.strip():
        raise ValueError("jd_text 不能为空")
    return analyze_job_match(resume_text.strip(), jd_text.strip())


def generate_boss_greeting(resume_text: str, jd_text: str) -> dict[str, Any]:
    """复用匹配服务生成的招聘平台打招呼语。"""
    analysis = match_resume_to_job(resume_text, jd_text)
    return {"greeting_message": analysis.get("greeting_message", "")}


TOOL_FUNCTIONS: dict[str, Callable[..., Any]] = {
    "search_knowledge_base": search_knowledge_base,
    "analyze_job_description": analyze_job_description,
    "match_resume_to_job": match_resume_to_job,
    "generate_boss_greeting": generate_boss_greeting,
}

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "查询 AI Job Agent 的 RAG 知识库。",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "要查询的问题"},
                    "top_k": {"type": "integer", "minimum": 1, "maximum": 10, "default": 3},
                },
                "required": ["query"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_job_description",
            "description": "分析岗位 JD 的职责、技能、经验要求和关键词。",
            "parameters": {
                "type": "object",
                "properties": {"jd_text": {"type": "string", "description": "完整岗位 JD"}},
                "required": ["jd_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "match_resume_to_job",
            "description": "分析简历与岗位 JD 的匹配度、优势、短板和建议。",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "jd_text": {"type": "string", "description": "完整岗位 JD"},
                },
                "required": ["resume_text", "jd_text"],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_boss_greeting",
            "description": "根据简历和 JD 生成简洁自然的 BOSS 直聘打招呼语。",
            "parameters": {
                "type": "object",
                "properties": {
                    "resume_text": {"type": "string", "description": "简历文本"},
                    "jd_text": {"type": "string", "description": "完整岗位 JD"},
                },
                "required": ["resume_text", "jd_text"],
                "additionalProperties": False,
            },
        },
    },
]
