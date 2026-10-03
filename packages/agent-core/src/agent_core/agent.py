"""The agent core facade.

:func:`Agent.run` wires together the complete end-to-end flow:

    user request -> Task (CREATED) -> Planner (PLANNING) ->
    Executor (RUNNING: per-step permission check + tool call) ->
    Verifier (VERIFYING) -> Task (COMPLETED / FAILED / CANCELLED)

Every observable transition emits a structured event on the bus. The agent
is synchronous by design for Phase 0 (see ARCHITECTURE.md, decision D7).
"""

from __future__ import annotations

import uuid

from .config import Settings
from .demo_tools import DemoTool
from .errors import PlanningError
from .events import Clock, EventBus, EventType, utc_now
from .executor import BasicVerifier, Executor, Verifier
from .permissions import ApprovalCallback, PermissionManager
from .planner import ModelPlanner, Planner
from .providers.factory import build_gateway
from .providers.gateway import ModelGateway
from .providers.mock import MockModelProvider
from .tasks import Task, TaskState, TaskStep
from .tools import ToolRegistry

# Bounded length for model-generated text that ends up in event data
# (event payloads must stay concise and operational — SECURITY.md).
_EVENT_TEXT_LIMIT = 200


def _bounded(text: str) -> str:
    return text if len(text) <= _EVENT_TEXT_LIMIT else text[: _EVENT_TEXT_LIMIT - 1] + "…"


class Agent:
    """Minimal agent core: request in, task out, events along the way."""

    def __init__(
        self,
        *,
        planner: Planner,
        registry: ToolRegistry,
        permissions: PermissionManager,
        events: EventBus,
        verifier: Verifier | None = None,
        clock: Clock | None = None,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._permissions = permissions
        self._events = events
        self._executor = Executor(
            registry=registry,
            permissions=permissions,
            events=events,
            verifier=verifier,
            clock=clock,
        )
        self._clock: Clock = clock or utc_now

    @classmethod
    def create_demo(
        cls,
        approval: ApprovalCallback | None = None,
        clock: Clock | None = None,
    ) -> Agent:
        """A fully wired agent using only in-process fakes.

        No API keys, no network, no external state — used by the demo entry
        point (apps/backend/src/main.py) and by integration tests.
        """
        registry = ToolRegistry()
        registry.register(DemoTool())
        provider = MockModelProvider()
        return cls(
            planner=ModelPlanner(provider),
            registry=registry,
            permissions=PermissionManager(approval=approval),
            events=EventBus(clock=clock),
            verifier=BasicVerifier(),
            clock=clock,
        )

    @classmethod
    def create_configured(
        cls,
        settings: Settings | None = None,
        approval: ApprovalCallback | None = None,
        clock: Clock | None = None,
        gateway: ModelGateway | None = None,
    ) -> Agent:
        """An agent wired from configuration (Phase 1).

        The model provider is selected via ``MODEL_PROVIDER`` and reached
        through the :class:`~agent_core.providers.gateway.ModelGateway`.
        With default settings (``MODEL_PROVIDER=mock``) the agent is fully
        offline — the demo path — and requires no API keys.

        Pass a pre-built ``gateway`` to reuse/inspect one (e.g. to log the
        active provider name); otherwise it is built from ``settings``.
        """
        resolved = settings if settings is not None else Settings.from_env()
        if gateway is None:
            gateway = build_gateway(resolved)
        registry = ToolRegistry()
        registry.register(DemoTool())
        return cls(
            planner=ModelPlanner(gateway),
            registry=registry,
            permissions=PermissionManager(approval=approval),
            events=EventBus(clock=clock),
            verifier=BasicVerifier(),
            clock=clock,
        )

    @property
    def events(self) -> EventBus:
        return self._events

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def run(self, request: str) -> Task:
        """Run one user request to a terminal task state."""
        now = self._clock()
        task = Task.create(request, now=now)
        self._events.emit(EventType.TASK_CREATED, task_id=task.id, data={"request": request})

        task.transition(TaskState.PLANNING, now=now)
        try:
            plan = self._planner.plan(request, self._registry.list_tools())
        except PlanningError as exc:
            task.error = f"planning failed: {exc}"
            task.transition(TaskState.FAILED, now=self._clock())
            self._events.emit(EventType.TASK_FAILED, task_id=task.id, data={"error": task.error})
            return task

        task.steps = [
            TaskStep(
                id=str(uuid.uuid4()),
                tool_name=step.tool_name,
                description=step.description,
                input=dict(step.input),
            )
            for step in plan.steps
        ]
        self._events.emit(
            EventType.PLAN_CREATED,
            task_id=task.id,
            data={
                "steps": [
                    {
                        "tool_name": step.tool_name,
                        "description": _bounded(step.description),
                    }
                    for step in plan.steps
                ],
            },
        )
        return self._executor.execute(task)
