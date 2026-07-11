import json
import logging
from typing import Any

from services.deepseek_service import chat_completion


logger = logging.getLogger(__name__)

_LIST_FIELDS = (
    "strengths",
    "weaknesses",
    "resume_suggestions",
    "interview_suggestions",
)


def _fallback_analysis(message: str) -> dict[str, Any]:
    return {
        "match_score": 0,
        "summary": message,
        "strengths": [],
        "weaknesses": [],
        "resume_suggestions": [],
        "interview_suggestions": [],
        "greeting_message": "您好，我希望进一步了解该岗位，并与您沟通我的项目经验。",
    }


def _remove_markdown_code_block(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned


def _normalize_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    if value is None or value == "":
        return []
    return [str(value)]


def _normalize_score(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        score = int(float(value))
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _parse_analysis(content: str) -> dict[str, Any]:
    cleaned = _remove_markdown_code_block(content)
    try:
        parsed = json.loads(cleaned)
    except (TypeError, json.JSONDecodeError):
        logger.exception("岗位匹配分析返回的内容不是有效 JSON")
        return _fallback_analysis("岗位匹配分析结果格式异常，请稍后重试。")

    if not isinstance(parsed, dict):
        logger.error("岗位匹配分析 JSON 顶层结构不是对象")
        return _fallback_analysis("岗位匹配分析结果格式异常，请稍后重试。")

    result: dict[str, Any] = {
        "match_score": _normalize_score(parsed.get("match_score")),
        "summary": str(parsed.get("summary") or "暂未生成匹配结论。"),
        "greeting_message": str(
            parsed.get("greeting_message") or "您好，我希望进一步了解该岗位，并与您沟通我的项目经验。"
        ),
    }
    for field in _LIST_FIELDS:
        result[field] = _normalize_list(parsed.get(field))
    return result


def analyze_job_match(resume_text: str, job_description: str) -> dict[str, Any]:
    logger.info("Starting resume and job description matching analysis")

    prompt = f"""请基于以下简历与岗位JD进行匹配分析。

请严格只返回一个合法 JSON 对象，不要添加 Markdown 代码块、解释文字或其他内容。JSON 必须包含以下字段：
{{
  "match_score": 0到100之间的整数,
  "summary": "岗位匹配结论",
  "strengths": ["我的核心优势"],
  "weaknesses": ["当前主要短板"],
  "resume_suggestions": ["简历修改建议"],
  "interview_suggestions": ["面试准备建议"],
  "greeting_message": "一条可以直接在招聘平台发送的打招呼语"
}}

分析时请覆盖：总匹配度评分、匹配技能、缺失核心技能、简历需要优化的内容、针对岗位的项目描述优化建议、是否建议投递和接下来7天的补技能计划，并将这些结论整理到上述 JSON 字段中。

简历内容：
{resume_text}

岗位JD：
{job_description}"""

    try:
        raw_analysis = chat_completion([
            {"role": "system", "content": "你是一个简历与岗位匹配分析专家。"},
            {"role": "user", "content": prompt}
        ])
        analysis = _parse_analysis(raw_analysis)
    except Exception:
        logger.exception("岗位匹配分析失败")
        analysis = _fallback_analysis("岗位匹配分析暂时无法生成，请稍后重试。")

    logger.info("Resume and job description matching analysis completed")
    return analysis
