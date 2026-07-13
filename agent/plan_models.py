"""Planner data models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlanStep:
    step_id: str
    tool_name: str
    purpose: str
    arguments: dict[str, Any]
    depends_on: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ExecutionPlan:
    goal: str
    steps: list[PlanStep]

