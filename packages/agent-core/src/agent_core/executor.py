"""Step executor: run a planned task through the tool runtime and permissions.

Responsibilities — and only these:

- enforce the task/step state machine,
- check permissions before every tool call (and route approvals),
- execute tools through the :class:`~agent_core.tool_runtime.ToolRuntime`,
  which requires the executor's ALLOWED decision and owns the tool
  lifecycle events (started/completed/failed + validation events),
- emit a structured event for every task/step transition.

Verification is delegated to a pluggable :class:`Verifier`. The default
(:class:`BasicVerifier`) only confirms that every step completed; real
output verification is a later phase.

Approval-denied steps end the task as CANCELLED (a user-initiated stop),
while tool failures end it as FAILED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .errors import (
    PermissionDeniedError,
    TaskStateError,
    ToolNotFoundError,
)
from .events import Clock, EventBus, EventType, utc_now
from .permissions import ApprovalRequest, PermissionDecision, PermissionManager
from .tasks import StepStatus, Task, TaskState, TaskStep
from .tool_runtime import ToolInvocation, ToolRuntime
from .tools import ToolRegistry


@dataclass(frozen=True)
class VerifyResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


class Verifier(Protocol):
    """Checks a fully-executed task before it can be marked COMPLETED."""

    def verify(self, task: Task) -> VerifyResult: ...


class BasicVerifier:
    """Default verifier: the task is verified iff every step completed."""

    def verify(self, task: Task) -> VerifyResult:
        pending = [step.tool_name for step in task.steps if step.status is not StepStatus.COMPLETED]
        if pending:
            return VerifyResult(ok=False, errors=[f"steps not completed: {pending}"])
        return VerifyResult(ok=True)


class Executor:
    """Executes the steps of a PLANNING-state task to a terminal state."""

    def __init__(
        self,
        registry: ToolRegistry,
        permissions: PermissionManager,
        events: EventBus,
        verifier: Verifier | None = None,
        clock: Clock | None = None,
        runtime: ToolRuntime | None = None,
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._events = events
        self._verifier: Verifier = verifier or BasicVerifier()
        self._clock: Clock = clock or utc_now
        # Phase 2: the runtime is the only execution path for tool calls.
        # Auto-built from the same registry/events/clock when not supplied.
        self._runtime = runtime or ToolRuntime(registry=registry, events=events, clock=self._clock)

    @property
    def runtime(self) -> ToolRuntime:
        return self._runtime

    def execute(self, task: Task) -> Task:
        if task.state is not TaskState.PLANNING:
            raise TaskStateError(f"executor requires a task in PLANNING, got {task.state.value}")
        task.transition(TaskState.RUNNING, now=self._clock())

        for step in task.steps:
            if not self._run_step(task, step):
                return task  # task reached a terminal state

        task.transition(TaskState.VERIFYING, now=self._clock())
        verdict = self._verifier.verify(task)
        if verdict.ok:
            task.result = task.steps[-1].output if task.steps else None
            task.transition(TaskState.COMPLETED, now=self._clock())
            self._events.emit(
                EventType.TASK_COMPLETED,
                task_id=task.id,
                data={"result": task.result, "steps_completed": len(task.steps)},
            )
        else:
            task.error = "verification failed: " + "; ".join(verdict.errors)
            task.transition(TaskState.FAILED, now=self._clock())
            self._events.emit(EventType.TASK_FAILED, task_id=task.id, data={"error": task.error})
        return task

    def _run_step(self, task: Task, step: TaskStep) -> bool:
        """Execute one step. Returns False when the task reached a terminal state."""
        try:
            tool = self._registry.require(step.tool_name)
        except ToolNotFoundError as exc:
            self._fail_task(task, str(exc))
            return False

        # Phase 2: the step is picked up (observable before any permission work).
        self._events.emit(
            EventType.TOOL_REQUESTED,
            task_id=task.id,
            step_id=step.id,
            data={
                "tool_name": step.tool_name,
                "permission_level": tool.spec.permission_level.name,
            },
        )

        decision = self._permissions.check(tool.spec)
        if decision is PermissionDecision.DENIED:
            step.transition(StepStatus.CANCELLED)
            self._emit_tool_denied(task, step, "denied_by_policy")
            return self._cancel_task(
                task,
                step,
                f"tool {step.tool_name!r} denied by permission policy",
            )
        if decision is PermissionDecision.REQUIRES_APPROVAL:
            self._events.emit(
                EventType.APPROVAL_REQUIRED,
                task_id=task.id,
                step_id=step.id,
                data={
                    "tool_name": step.tool_name,
                    "permission_level": tool.spec.permission_level.name,
                    "reason": tool.spec.description,
                },
            )
            approved = self._permissions.request_approval(
                ApprovalRequest(
                    task_id=task.id,
                    step_id=step.id,
                    tool_name=step.tool_name,
                    permission_level=tool.spec.permission_level,
                    reason=tool.spec.description,
                )
            )
            if not approved:
                step.transition(StepStatus.CANCELLED)
                self._emit_tool_denied(task, step, "approval_denied")
                return self._cancel_task(
                    task,
                    step,
                    f"approval denied for tool {step.tool_name!r}",
                )

        step.transition(StepStatus.RUNNING)
        invocation = ToolInvocation(
            task_id=task.id,
            step_id=step.id,
            tool_name=step.tool_name,
            input=dict(step.input),
        )
        try:
            # The runtime re-checks the decision (backstop) and emits the
            # tool lifecycle events (started / completed / failed / invalid).
            result = self._runtime.execute(invocation, decision=PermissionDecision.ALLOWED)
        except PermissionDeniedError as exc:
            # Unreachable via this path (we only pass ALLOWED); treated as a
            # denial so no code path can execute an unapproved tool.
            step.transition(StepStatus.CANCELLED)
            self._emit_tool_denied(task, step, "permission_backstop")
            return self._cancel_task(task, step, str(exc))

        if result.ok:
            step.transition(StepStatus.COMPLETED)
            step.output = result.output
            return True

        step.transition(StepStatus.FAILED)
        step.error = result.error
        self._fail_task(task, result.error or "tool failed without an error message")
        return False

    def _emit_tool_denied(self, task: Task, step: TaskStep, reason: str) -> None:
        """Structured observation of a permission refusal (Phase 2)."""
        self._events.emit(
            EventType.TOOL_DENIED,
            task_id=task.id,
            step_id=step.id,
            data={"tool_name": step.tool_name, "reason": reason},
        )

    def _cancel_task(self, task: Task, step: TaskStep, reason: str) -> bool:
        task.error = reason
        task.transition(TaskState.CANCELLED, now=self._clock())
        self._events.emit(
            EventType.TASK_CANCELLED,
            task_id=task.id,
            data={"error": reason, "tool_name": step.tool_name},
        )
        return False

    def _fail_task(self, task: Task, error: str) -> None:
        task.error = error
        task.transition(TaskState.FAILED, now=self._clock())
        self._events.emit(EventType.TASK_FAILED, task_id=task.id, data={"error": error})
