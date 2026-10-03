"""Planning: turn a user request into an ordered list of tool steps.

The :class:`ModelPlanner` asks a :class:`~agent_core.providers.base.ModelProvider`
for a strict-JSON plan and validates it against the registered tools. This
is the same code path that will run against real providers in Phase 1 —
tests exercise it with the mock provider, so no external API is needed.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .errors import PlanningError
from .providers.base import ChatMessage, ModelProvider, ModelRequest
from .tools import ToolSpec

PLAN_JSON_INSTRUCTIONS = (
    "You are the planning component of a personal AI agent.\n"
    "Decompose the user request into the minimal ordered list of tool calls.\n"
    "Respond with ONLY a JSON object of the form:\n"
    '{{"steps": [{{"tool_name": str, "description": str, "input": object}}]}}\n'
    "Rules:\n"
    "- Use only tools from the available tools list.\n"
    "- Every step must reference a tool by its exact name.\n"
    '- "input" must be an object matching that tool\'s input schema.\n'
    "- Do not include commentary, markdown, or chain of thought.\n\n"
    "Available tools (JSON):\n{tools}\n"
)


class PlanStep(BaseModel):
    model_config = ConfigDict(frozen=True)

    tool_name: str
    description: str
    input: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    model_config = ConfigDict(frozen=True)

    steps: list[PlanStep]
    notes: str | None = None


class Planner(Protocol):
    """Any component that can turn a request into a plan."""

    def plan(self, request: str, available_tools: Sequence[ToolSpec]) -> Plan: ...


class ModelPlanner:
    """Planner that derives a strict-JSON plan from a model provider."""

    def __init__(self, provider: ModelProvider, system_prompt: str | None = None) -> None:
        self._provider = provider
        self._system_prompt = system_prompt or PLAN_JSON_INSTRUCTIONS

    def plan(self, request: str, available_tools: Sequence[ToolSpec]) -> Plan:
        specs = list(available_tools)
        if not specs:
            raise PlanningError("no tools available; nothing to plan with")
        tools_json = json.dumps([spec.model_dump(mode="json") for spec in specs], indent=2)
        model_request = ModelRequest(
            messages=[
                ChatMessage(role="system", content=self._system_prompt.format(tools=tools_json)),
                ChatMessage(role="user", content=request),
            ],
        )
        try:
            response = self._provider.complete(model_request)
        except Exception as exc:
            raise PlanningError(f"model provider failed: {type(exc).__name__}: {exc}") from exc
        return self._parse(response.content, specs)

    def _parse(self, content: str, specs: Sequence[ToolSpec]) -> Plan:
        try:
            data: Any = json.loads(content)
        except json.JSONDecodeError as exc:
            raise PlanningError(f"plan is not valid JSON: {exc.msg} at position {exc.pos}") from exc
        if not isinstance(data, dict):
            raise PlanningError("plan must be a JSON object")
        try:
            plan = Plan.model_validate(data)
        except ValidationError as exc:
            raise PlanningError(f"plan does not match the plan schema: {exc.errors()[:3]}") from exc
        if not plan.steps:
            raise PlanningError("plan contains no steps")
        known = {spec.name for spec in specs}
        unknown = [step.tool_name for step in plan.steps if step.tool_name not in known]
        if unknown:
            raise PlanningError(
                f"plan references unknown tools {unknown}; available: {sorted(known)}"
            )
        return plan
