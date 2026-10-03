"""Step executor: run a planned task through the registry and permissions.

Responsibilities — and only these:

- enforce the task/step state machine,
- check permissions before every tool call (and route approvals),
- execute tools through the registry's controlled interface,
- emit a structured event for every observable transition.

Verification is delegated to a pluggable :class:`Verifier`. The default
(:class:`BasicVerifier`) only confirms that every step completed; real
output verification is a later phase.

Approval-denied steps end the task as CANCELLED (a user-initiated stop),
while tool failures end it as FAILED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from .errors import TaskStateError, ToolExecutionError, ToolInputError, ToolNotFoundError
from .events import Clock, EventBus, EventType, utc_now
from .permissions import ApprovalRequest, PermissionDecision, PermissionManager
from .tasks import StepStatus, Task, TaskState, TaskStep
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
    ) -> None:
        self._registry = registry
        self._permissions = permissions
        self._events = events
        self._verifier: Verifier = verifier or BasicVerifier()
        self._clock: Clock = clock or utc_now

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

        decision = self._permissions.check(tool.spec)
        if decision is PermissionDecision.DENIED:
            step.transition(StepStatus.CANCELLED)
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
                return self._cancel_task(
                    task,
                    step,
                    f"approval denied for tool {step.tool_name!r}",
                )

        step.transition(StepStatus.RUNNING)
        self._events.emit(
            EventType.TOOL_STARTED,
            task_id=task.id,
            step_id=step.id,
            data={"tool_name": step.tool_name, "input": step.input},
        )
        try:
            result = self._registry.execute(step.tool_name, step.input)
        except (ToolInputError, ToolExecutionError) as exc:
            step.transition(StepStatus.FAILED)
            step.error = str(exc)
            self._events.emit(
                EventType.TOOL_FAILED,
                task_id=task.id,
                step_id=step.id,
                data={"tool_name": step.tool_name, "error": str(exc)},
            )
            self._fail_task(task, str(exc))
            return False

        if result.ok:
            step.transition(StepStatus.COMPLETED)
            step.output = result.output
            self._events.emit(
                EventType.TOOL_COMPLETED,
                task_id=task.id,
                step_id=step.id,
                data={"tool_name": step.tool_name, "output": result.output},
            )
            return True

        step.transition(StepStatus.FAILED)
        step.error = result.error
        self._events.emit(
            EventType.TOOL_FAILED,
            task_id=task.id,
            step_id=step.id,
            data={"tool_name": step.tool_name, "error": result.error},
        )
        self._fail_task(task, result.error or "tool failed without an error message")
        return False

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
