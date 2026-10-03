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
from pathlib import Path

from .builtin_tools import register_default_tools
from .config import Settings
from .document_tools import register_document_tools
from .documents.limits import DocumentLimits
from .documents.retrieval import KnowledgeStore
from .errors import PlanningError
from .events import Clock, EventBus, EventType, bounded_text, utc_now
from .executor import BasicVerifier, Executor, Verifier
from .permissions import ApprovalCallback, PermissionManager
from .planner import ModelPlanner, Planner
from .providers.factory import build_gateway
from .providers.gateway import ModelGateway
from .providers.mock import MockModelProvider
from .tasks import Task, TaskState, TaskStep
from .tools import ToolRegistry
from .workspace import Workspace
from .workspace_tools import register_workspace_tools


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
        knowledge_store: KnowledgeStore | None = None,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._permissions = permissions
        self._events = events
        self._knowledge_store = knowledge_store if knowledge_store is not None else KnowledgeStore()
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
        workspace_root: Path | None = None,
    ) -> Agent:
        """A fully wired agent using only in-process fakes.

        No API keys, no network — used by the demo entry point
        (apps/backend/src/main.py) and by integration tests. Registers the
        default tool set (demo tool + Phase 2 safe built-ins) plus the Phase 3
        workspace tools bound to the workspace root (default
        ``data/workspace``) and the Phase 4 document tools bound to the same
        boundary and an in-memory knowledge store. Filesystem and document
        tools only act inside that boundary.
        """
        registry = ToolRegistry()
        register_default_tools(registry)
        root = workspace_root if workspace_root is not None else Settings().workspace_root
        workspace = Workspace(root)
        register_workspace_tools(registry, workspace)
        store = KnowledgeStore()
        register_document_tools(registry, workspace, store)
        provider = MockModelProvider()
        return cls(
            planner=ModelPlanner(provider),
            registry=registry,
            permissions=PermissionManager(approval=approval),
            events=EventBus(clock=clock),
            verifier=BasicVerifier(),
            clock=clock,
            knowledge_store=store,
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
        Registers the default tool set (demo tool + Phase 2 safe built-ins)
        plus the Phase 3 workspace tools bound to ``settings.workspace_root``
        and the Phase 4 document tools bound to the same boundary and an
        in-memory knowledge store whose limits come from the settings.
        """
        resolved = settings if settings is not None else Settings.from_env()
        if gateway is None:
            gateway = build_gateway(resolved)
        registry = ToolRegistry()
        register_default_tools(registry)
        workspace = Workspace.from_settings(resolved)
        register_workspace_tools(registry, workspace)
        store = KnowledgeStore(DocumentLimits.from_settings(resolved))
        register_document_tools(registry, workspace, store)
        return cls(
            planner=ModelPlanner(gateway),
            registry=registry,
            permissions=PermissionManager(approval=approval),
            events=EventBus(clock=clock),
            verifier=BasicVerifier(),
            clock=clock,
            knowledge_store=store,
        )

    @property
    def events(self) -> EventBus:
        return self._events

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    @property
    def knowledge_store(self) -> KnowledgeStore:
        return self._knowledge_store

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
                        "description": bounded_text(step.description),
                    }
                    for step in plan.steps
                ],
            },
        )
        return self._executor.execute(task)
