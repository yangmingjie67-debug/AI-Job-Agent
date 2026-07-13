"""Agent HTTP API 路由。"""

from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from agent.agent_service import run_agent
from agent.planner_service import run_planner


logger = logging.getLogger(__name__)
agent_bp = Blueprint("agent", __name__, url_prefix="/api/agent")


@agent_bp.post("/plan")
def agent_plan():
    """执行模型生成的多步骤计划。"""
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "请求体必须是 JSON 对象"}), 400
    message = payload.get("message", "")
    context = payload.get("context")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "message 不能为空"}), 400
    if context is not None and not isinstance(context, dict):
        return jsonify({"success": False, "error": "context 必须是对象"}), 400
    try:
        return jsonify(run_planner(message, context=context))
    except ValueError as exc:
        return jsonify({"success": False, "error": str(exc)}), 400
    except Exception:
        logger.exception("Planner agent failed")
        return jsonify({"success": False, "error": "Planner 服务暂时不可用，请稍后重试"}), 500


@agent_bp.post("/chat")
def agent_chat():
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return jsonify({"success": False, "error": "请求体必须是 JSON 对象"}), 400
    message = payload.get("message", "")
    context = payload.get("context")
    if not isinstance(message, str) or not message.strip():
        return jsonify({"success": False, "error": "message 不能为空"}), 400
    if context is not None and not isinstance(context, dict):
        return jsonify({"success": False, "error": "context 必须是对象"}), 400
    try:
        return jsonify(run_agent(message, context=context))
    except Exception:
        logger.exception("Agent chat failed")
        return jsonify({"success": False, "error": "Agent 服务暂时不可用，请稍后重试"}), 500
