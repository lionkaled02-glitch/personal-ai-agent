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
from .computer import ComputerLimits, ComputerProvider, ComputerRuntime
from .computer_tools import register_computer_tools
from .config import Settings
from .document_tools import register_document_tools
from .documents.limits import DocumentLimits
from .documents.retrieval import KnowledgeStore
from .errors import PlanningError
from .events import Clock, EventBus, EventType, bounded_text, utc_now
from .executor import BasicVerifier, Executor, Verifier
from .memory.limits import MemoryLimits
from .memory.retrieval import LexicalMemoryRetriever
from .memory.store import InMemoryMemoryStore, MemoryStore
from .memory_tools import register_memory_tools
from .permissions import ApprovalCallback, PermissionManager
from .planner import ModelPlanner, Planner
from .providers.factory import build_gateway
from .providers.gateway import ModelGateway
from .providers.mock import MockModelProvider
from .rag.context import ContextBuilder
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
        memory_store: MemoryStore | None = None,
        context_builder: ContextBuilder | None = None,
    ) -> None:
        self._planner = planner
        self._registry = registry
        self._permissions = permissions
        self._events = events
        self._knowledge_store = knowledge_store if knowledge_store is not None else KnowledgeStore()
        self._memory_store = (
            memory_store
            if memory_store is not None
            else InMemoryMemoryStore(MemoryLimits(), clock=clock if clock is not None else utc_now)
        )
        self._context_builder = (
            context_builder
            if context_builder is not None
            else ContextBuilder(
                memory_retriever=LexicalMemoryRetriever(self._memory_store),
                knowledge_store=self._knowledge_store,
                limits=self._memory_store.limits,
                clock=clock if clock is not None else utc_now,
            )
        )
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
        ``data/workspace``), the Phase 4 document tools bound to the same
        boundary and an in-memory knowledge store, and the Phase 5 memory
        tools bound to an in-memory memory store. Filesystem and document
        tools only act inside the workspace boundary; memory is explicit
        (permission-gated creation, never automatic).
        """
        registry = ToolRegistry()
        register_default_tools(registry)
        root = workspace_root if workspace_root is not None else Settings().workspace_root
        workspace = Workspace(root)
        register_workspace_tools(registry, workspace)
        store = KnowledgeStore()
        register_document_tools(registry, workspace, store)
        memory = InMemoryMemoryStore(MemoryLimits(), clock=clock)
        register_memory_tools(registry, memory, clock=clock)
        provider = MockModelProvider()
        return cls(
            planner=ModelPlanner(provider),
            registry=registry,
            permissions=PermissionManager(approval=approval),
            events=EventBus(clock=clock),
            verifier=BasicVerifier(),
            clock=clock,
            knowledge_store=store,
            memory_store=memory,
        )

    @classmethod
    def create_configured(
        cls,
        settings: Settings | None = None,
        approval: ApprovalCallback | None = None,
        clock: Clock | None = None,
        gateway: ModelGateway | None = None,
        computer_provider: ComputerProvider | None = None,
    ) -> Agent:
        """An agent wired from configuration (Phase 1).

        The model provider is selected via ``MODEL_PROVIDER`` and reached
        through the :class:`~agent_core.providers.gateway.ModelGateway`.
        With default settings (``MODEL_PROVIDER=mock``) the agent is fully
        offline — the demo path — and requires no API keys.

        Pass a pre-built ``gateway`` to reuse/inspect one (e.g. to log the
        active provider name); otherwise it is built from ``settings``.
        Registers the default tool set (demo tool + Phase 2 safe built-ins)
        plus the Phase 3 workspace tools bound to ``settings.workspace_root``,
        the Phase 4 document tools bound to the same boundary and an
        in-memory knowledge store whose limits come from the settings, and
        the Phase 5 memory tools bound to an in-memory memory store whose
        limits also come from the settings. Computer tools are registered
        only when an explicit provider is passed; those tools use the same
        permission manager and event bus, with limits from ``COMPUTER_*``.
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
        memory = InMemoryMemoryStore(MemoryLimits.from_settings(resolved), clock=clock)
        register_memory_tools(registry, memory, clock=clock)
        permissions = PermissionManager(approval=approval)
        events = EventBus(clock=clock)
        if computer_provider is not None:
            computer_runtime = ComputerRuntime(
                provider=computer_provider,
                permissions=permissions,
                events=events,
                limits=ComputerLimits.from_settings(resolved),
                clock=clock,
            )
            register_computer_tools(registry, computer_runtime)
        return cls(
            planner=ModelPlanner(gateway),
            registry=registry,
            permissions=permissions,
            events=events,
            verifier=BasicVerifier(),
            clock=clock,
            knowledge_store=store,
            memory_store=memory,
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

    @property
    def memory_store(self) -> MemoryStore:
        return self._memory_store

    @property
    def context_builder(self) -> ContextBuilder:
        return self._context_builder

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
