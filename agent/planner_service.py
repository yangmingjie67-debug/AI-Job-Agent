"""Model-generated multi-step planner built on the existing tool executor."""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timezone
from typing import Any

from services.deepseek_service import chat_completion

from .execution_context import ReferenceError, resolve_arguments
from .plan_models import ExecutionPlan, PlanStep
from .tool_executor import execute_tool
from .tool_registry import TOOL_DEFINITIONS, TOOL_FUNCTIONS

logger = logging.getLogger(__name__)
MAX_PLAN_STEPS = 5
MAX_TOTAL_SECONDS = 120

PLANNER_PROMPT = """你是 AI Job Agent 的任务规划器，不是最终问答助手。
你的输出只用于后端执行，禁止直接替用户完成岗位分析、匹配、知识库查询或打招呼语。
只要用户要求查询知识库、分析 JD/技能、匹配简历、生成打招呼语，或在一次请求中要求其中两项以上，就必须返回 mode=plan，不能返回 direct。
只有真正的寒暄、闲聊或不需要任何工具的请求，才返回 JSON {\"mode\":\"direct\",\"answer\":\"...\"}。
复合任务返回 JSON {\"mode\":\"plan\",\"goal\":\"...\",\"steps\":[{"step_id":"step_1","tool_name":"...","purpose":"...","arguments":{},"depends_on":[]}]}
每个明确动作都必须有对应步骤，执行完一个动作后不能用另一个工具的回答替代它。
“分析岗位/岗位需要什么技能”必须使用 analyze_job_description，不能用 search_knowledge_base 替代；如果消息中已经包含岗位描述，可以把消息中的岗位描述作为 jd_text。即使只有这一个动作，也必须返回包含一个 analyze_job_description 步骤的 plan，不能返回 direct。
“分析岗位、判断简历匹配、再生成打招呼语”必须依次规划 analyze_job_description、match_resume_to_job、generate_boss_greeting。
“先查 RAG，再分析岗位”必须依次规划 search_knowledge_base、analyze_job_description，即使知识库结果已经包含相关解释，也不能省略第二步。
只允许使用提供的工具，steps 只能有 1 到 5 步，step_id 唯一，depends_on 只能引用前面步骤，不能循环。
arguments 只允许使用真实数据、$context.xxx 或 $steps.step_id.data.xxx，禁止编造字段。只输出 JSON。"""


def _clean_json(text: str) -> str:
    value = (text or "").strip()
    if value.startswith("```"):
        value = value.split("\n", 1)[1] if "\n" in value else value[3:]
        if value.rstrip().endswith("```"):
            value = value.rstrip()[:-3]
    return value.strip()


def _parse(raw: str) -> dict[str, Any]:
    try:
        payload = json.loads(_clean_json(raw))
    except json.JSONDecodeError as exc:
        raise ValueError("Planner 返回的不是合法 JSON") from exc
    if not isinstance(payload, dict) or payload.get("mode") not in {"direct", "plan"}:
        raise ValueError("Planner mode 必须是 direct 或 plan")
    return payload


def _validate(payload: dict[str, Any]) -> ExecutionPlan:
    raw_steps = payload.get("steps")
    if not isinstance(raw_steps, list) or not 1 <= len(raw_steps) <= MAX_PLAN_STEPS:
        raise ValueError(f"steps 数量必须在 1 到 {MAX_PLAN_STEPS} 之间")
    known: set[str] = set()
    steps: list[PlanStep] = []
    for raw in raw_steps:
        if not isinstance(raw, dict):
            raise ValueError("每个步骤必须是对象")
        step_id, tool_name = raw.get("step_id"), raw.get("tool_name")
        depends_on, arguments = raw.get("depends_on", []), raw.get("arguments", {})
        if not isinstance(step_id, str) or not step_id or step_id in known:
            raise ValueError("step_id 必须非空且唯一")
        if not isinstance(tool_name, str) or tool_name not in TOOL_FUNCTIONS:
            raise ValueError(f"未知工具：{tool_name}")
        if not isinstance(arguments, dict):
            raise ValueError(f"步骤 {step_id} 的 arguments 必须是对象")
        if not isinstance(depends_on, list) or any(not isinstance(item, str) for item in depends_on):
            raise ValueError(f"步骤 {step_id} 的 depends_on 必须是字符串数组")
        if step_id in depends_on or any(item not in known for item in depends_on):
            raise ValueError(f"步骤 {step_id} 的依赖必须只引用前面已存在的 step_id")
        known.add(step_id)
        steps.append(PlanStep(step_id, tool_name, str(raw.get("purpose", "")), arguments, depends_on))
    return ExecutionPlan(str(payload.get("goal", "")), steps)


def _needs_repair(user_message: str, plan: ExecutionPlan) -> bool:
    """Reject a structurally valid plan that clearly omits a requested action."""
    text = user_message.lower()
    names = {step.tool_name for step in plan.steps}
    if any(word in text for word in ("分析岗位", "岗位需要什么技能", "分析这个岗位", "jd")) and "analyze_job_description" not in names:
        return True
    if any(word in text for word in ("匹配", "简历和岗位")) and "match_resume_to_job" not in names:
        return True
    if any(word in text for word in ("打招呼", "boss", "greeting")) and "generate_boss_greeting" not in names:
        return True
    if text.count("先") and text.count("再") and len(names) == 1:
        return True
    if len(plan.steps) > 1 and len(names) == 1:
        return True
    return False


def create_plan(user_message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Ask the model for JSON, then reject malformed plans before execution."""
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValueError("message 不能为空")
    if context is not None and not isinstance(context, dict):
        raise ValueError("context 必须是对象")
    request = json.dumps({"message": user_message.strip(), "context": context or {}}, ensure_ascii=False)
    catalog = json.dumps(TOOL_DEFINITIONS, ensure_ascii=False)
    messages = [{"role": "system", "content": PLANNER_PROMPT}, {"role": "user", "content": f"可用工具：{catalog}\n用户任务：{request}"}]
    raw = chat_completion(messages)
    parsed = _parse(raw)
    if parsed["mode"] == "direct":
        return parsed
    plan = _validate(parsed)
    if _needs_repair(user_message, plan):
        messages.append({"role": "assistant", "content": raw})
        messages.append({"role": "user", "content": "计划结构合法但没有覆盖用户的全部动作。请重新生成完整 plan：岗位/技能分析必须包含 analyze_job_description；简历匹配必须包含 match_resume_to_job；打招呼必须包含 generate_boss_greeting；先查知识库再分析必须包含两个按顺序执行的步骤。不要返回 direct。只输出 JSON。"})
        repaired = _parse(chat_completion(messages))
        if repaired["mode"] != "plan":
            raise ValueError("Planner 未能生成覆盖全部动作的计划")
        plan = _validate(repaired)
        if _needs_repair(user_message, plan):
            raise ValueError("Planner 计划未覆盖用户的全部动作")
    return {"mode": "plan", "plan": plan}


def _short(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value)
    return text[:240] + ("..." if len(text) > 240 else "")


def execute_plan(plan: ExecutionPlan, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Execute steps in order and mark dependent steps skipped after failures."""
    total_started = time.perf_counter()
    results: dict[str, dict[str, Any]] = {}
    trace: list[dict[str, Any]] = []
    for step in plan.steps:
        started = time.perf_counter()
        item: dict[str, Any] = {"step_id": step.step_id, "tool_name": step.tool_name, "status": "pending", "started_at": datetime.now(timezone.utc).isoformat(), "elapsed_ms": 0, "result_summary": "", "error": None}
        if time.perf_counter() - total_started >= MAX_TOTAL_SECONDS:
            item.update(status="skipped", error="计划执行超过 120 秒")
            results[step.step_id] = {"success": False, "error": item["error"]}
        elif any(results.get(dep, {}).get("success") is not True for dep in step.depends_on):
            item.update(status="skipped", error="依赖步骤未成功")
            results[step.step_id] = {"success": False, "error": item["error"]}
        else:
            item["status"] = "running"
            try:
                arguments = resolve_arguments(step.arguments, context, results)
                result = execute_tool(step.tool_name, arguments)
                item.update(status="success" if result.get("success") else "failed", data=result.get("data"), error=result.get("error"), result_summary=_short(result.get("data") if result.get("success") else result.get("error", "")))
                results[step.step_id] = result
            except (ReferenceError, ValueError) as exc:
                item.update(status="failed", error=str(exc), result_summary=str(exc))
                results[step.step_id] = {"success": False, "error": str(exc)}
            except Exception:
                logger.exception("Planner step failed: %s", step.step_id)
                item.update(status="failed", error="步骤执行异常", result_summary="步骤执行异常")
                results[step.step_id] = {"success": False, "error": "步骤执行异常"}
        item["elapsed_ms"] = round((time.perf_counter() - started) * 1000, 2)
        trace.append(item)
    completed = sum(item["status"] == "success" for item in trace)
    failed = sum(item["status"] in {"failed", "skipped"} for item in trace)
    return {"execution_trace": trace, "completed_steps": completed, "failed_steps": failed, "step_results": results, "total_elapsed_ms": round((time.perf_counter() - total_started) * 1000, 2)}


def _final_answer(user_message: str, plan: ExecutionPlan, execution: dict[str, Any]) -> tuple[str, int]:
    rows = [{"step_id": row["step_id"], "tool_name": row["tool_name"], "status": row["status"], "data": row.get("data"), "error": row.get("error")} for row in execution["execution_trace"]]
    answer = chat_completion([{"role": "system", "content": "你是 AI Job Agent。只能根据真实工具执行结果回答，不要编造未完成步骤。清晰、简洁、可直接使用。"}, {"role": "user", "content": json.dumps({"goal": user_message, "plan": plan.goal, "execution_results": rows}, ensure_ascii=False)}])
    return answer, 1


def run_planner(user_message: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    created = create_plan(user_message, context)
    if created["mode"] == "direct":
        return {"success": True, "mode": "direct", "answer": str(created.get("answer", "")), "plan": None, "execution_trace": [], "completed_steps": 0, "failed_steps": 0, "llm_calls": 1, "total_elapsed_ms": 0}
    plan: ExecutionPlan = created["plan"]
    execution = execute_plan(plan, context)
    answer, final_calls = _final_answer(user_message, plan, execution)
    execution.pop("step_results", None)
    execution.update({"success": execution["failed_steps"] == 0, "mode": "plan", "goal": plan.goal, "plan": {"steps": [step.__dict__ for step in plan.steps]}, "answer": answer, "llm_calls": 2 + final_calls - 1})
    return execution
