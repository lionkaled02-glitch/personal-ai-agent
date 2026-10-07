import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import api
import pytest
from agent_core import Settings, TaskState
from agent_core.providers.gateway import ModelGateway
from agent_core.providers.mock import MockModelProvider
from fastapi import HTTPException
from pydantic import ValidationError


def test_health() -> None:
    assert api.health()["status"] == "ok"


def test_task_request_bounds() -> None:
    assert api.TaskRequest(request="hello").input_channel == "text"
    with pytest.raises(ValidationError):
        api.TaskRequest(request="")
    with pytest.raises(ValidationError):
        api.TaskRequest(request="x" * 20_001)


def test_api_list_bounds() -> None:
    with pytest.raises(HTTPException):
        api.list_tasks(0)
    with pytest.raises(HTTPException):
        api.list_tasks(501)
    with pytest.raises(HTTPException):
        api.get_events("missing", 0)


def test_missing_task_and_approval_are_404() -> None:
    with pytest.raises(HTTPException) as task_exc:
        api.get_task("no-such-task")
    assert task_exc.value.status_code == 404
    with pytest.raises(HTTPException) as events_exc:
        api.get_events("no-such-task", 10)
    assert events_exc.value.status_code == 404
    with pytest.raises(HTTPException) as approval_exc:
        api.decide_approval("no-such-approval", api.ApprovalDecision(approved=True))
    assert approval_exc.value.status_code == 404


# --- End-to-end approval workflow -------------------------------------------


@pytest.fixture(autouse=True)
def _short_approval_wait(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep a stuck worker from blocking test-session exit for minutes."""
    monkeypatch.setattr(api, "APPROVAL_WAIT_TIMEOUT_S", 10.0)


def _scripted_gateway(plan: dict[str, object]) -> ModelGateway:
    return ModelGateway(MockModelProvider(responses=[json.dumps(plan)]))


def _write_file_plan(path: str = "notes.txt", content: str = "hello") -> dict[str, object]:
    return {
        "steps": [
            {
                "tool_name": "write_text_file",
                "description": "Write a file",
                "input": {"path": path, "content": content},
            }
        ]
    }


def _demo_tool_plan() -> dict[str, object]:
    return {
        "steps": [
            {
                "tool_name": "demo_tool",
                "description": "Run the demo tool",
                "input": {"message": "hi from the api test"},
            }
        ]
    }


class _IsolatedApi:
    """Bind the api module to a temporary data/workspace root for one test."""

    def __init__(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, plan: dict[str, object]
    ) -> None:
        from task_store import TaskStore

        self.data_root = tmp_path / "data"
        self.workspace_root = tmp_path / "workspace"
        self.settings = Settings(data_root=self.data_root, workspace_root=self.workspace_root)
        self.store = TaskStore(self.data_root / "tasks.sqlite3")
        monkeypatch.setattr(api, "settings", self.settings)
        monkeypatch.setattr(api, "store", self.store)
        monkeypatch.setattr(api, "build_gateway", lambda _s: _scripted_gateway(plan))

    def submit(self, request: str = "please write a file") -> str:
        result = api.create_task(api.TaskRequest(request=request))
        return result["task_id"]

    def wait_for(self, predicate: Callable[[], Any], timeout_s: float = 10.0) -> Any:
        deadline = time.monotonic() + timeout_s
        outcome = None
        while time.monotonic() < deadline:
            outcome = predicate()
            if outcome:
                return outcome
            time.sleep(0.05)
        return outcome

    def task_state(self, task_id: str) -> TaskState | None:
        task = self.store.get_task(task_id)
        return None if task is None else task.state

    def execution_state(self, task_id: str) -> TaskState | None:
        """The task state once it has left CREATED, else None."""
        state = self.task_state(task_id)
        return None if state is TaskState.CREATED else state

    def wait_terminal(self, task_id: str, timeout_s: float = 10.0) -> TaskState:
        def _state() -> TaskState | None:
            state = self.task_state(task_id)
            return state if state is not None and state_is_terminal(state) else None

        final: TaskState | None = self.wait_for(_state, timeout_s=timeout_s)
        assert final is not None, "task never reached a terminal state"
        return final

    def pending_approval(self, task_id: str) -> dict[str, Any] | None:
        def _approval() -> dict[str, Any] | None:
            approvals = self.store.list_approvals(task_id)
            return approvals[0] if approvals else None

        outcome: dict[str, Any] | None = self.wait_for(_approval)
        return outcome

    def release_pending_approvals(self, task_id: str) -> None:
        """Decide any still-pending approval so no worker thread lingers."""
        for approval in self.store.list_approvals(task_id):
            if approval["status"] == "PENDING":
                self.store.decide_approval(approval["id"], False, datetime.now(UTC).isoformat())
                waiter = None
                with api.approval_lock:
                    waiter = api.approval_waiters.get(approval["id"])
                if waiter is not None:
                    waiter.set()


def state_is_terminal(state: TaskState) -> bool:
    return state in (TaskState.COMPLETED, TaskState.FAILED, TaskState.CANCELLED)


def test_approval_flow_persists_waiting_state_and_resumes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolated = _IsolatedApi(monkeypatch, tmp_path, _write_file_plan())
    task_id = isolated.submit()
    try:
        # The durable task must reflect execution while the worker runs
        # (never stuck at CREATED). PLANNING/RUNNING are transient here
        # because the approval request follows almost immediately.
        state = isolated.wait_for(lambda: isolated.execution_state(task_id))
        assert state in (TaskState.PLANNING, TaskState.RUNNING, TaskState.WAITING_FOR_USER)

        approval = isolated.pending_approval(task_id)
        assert approval is not None
        assert approval["status"] == "PENDING"
        assert approval["tool_name"] == "write_text_file"

        waiting = isolated.wait_for(
            lambda: isolated.task_state(task_id) is TaskState.WAITING_FOR_USER
        )
        assert waiting, "task never became WAITING_FOR_USER while approval was pending"

        decision = api.decide_approval(approval["id"], api.ApprovalDecision(approved=True))
        assert decision == {"approval_id": approval["id"], "status": "APPROVED"}

        final = isolated.wait_terminal(task_id)
        assert final is TaskState.COMPLETED
        assert (isolated.workspace_root / "notes.txt").read_text(encoding="utf-8") == "hello"

        event_types = [event["type"] for event in isolated.store.events(task_id)]
        assert "TASK_CREATED" in event_types
        assert "APPROVAL_REQUIRED" in event_types
        assert "TOOL_COMPLETED" in event_types
        assert "TASK_COMPLETED" in event_types
    finally:
        isolated.release_pending_approvals(task_id)


def test_denied_approval_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    isolated = _IsolatedApi(monkeypatch, tmp_path, _write_file_plan("secret.txt", "nope"))
    task_id = isolated.submit()
    try:
        approval = isolated.pending_approval(task_id)
        assert approval is not None

        decision = api.decide_approval(approval["id"], api.ApprovalDecision(approved=False))
        assert decision["status"] == "DENIED"

        final = isolated.wait_terminal(task_id)
        assert final is TaskState.CANCELLED
        assert not (isolated.workspace_root / "secret.txt").exists()

        record = isolated.store.get_approval(approval["id"])
        assert record is not None and record["status"] == "DENIED"
    finally:
        isolated.release_pending_approvals(task_id)


def test_duplicate_approval_decision_is_rejected(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolated = _IsolatedApi(monkeypatch, tmp_path, _write_file_plan())
    task_id = isolated.submit()
    try:
        approval = isolated.pending_approval(task_id)
        assert approval is not None

        api.decide_approval(approval["id"], api.ApprovalDecision(approved=True))
        with pytest.raises(HTTPException) as exc:
            api.decide_approval(approval["id"], api.ApprovalDecision(approved=False))
        assert exc.value.status_code == 409

        final = isolated.wait_terminal(task_id)
        assert final is TaskState.COMPLETED
    finally:
        isolated.release_pending_approvals(task_id)


def test_approval_wait_timeout_expires_record_and_fails_closed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(api, "APPROVAL_WAIT_TIMEOUT_S", 0.5)
    isolated = _IsolatedApi(monkeypatch, tmp_path, _write_file_plan())
    task_id = isolated.submit()
    try:
        approval = isolated.pending_approval(task_id)
        assert approval is not None

        # No human decision arrives; the bounded wait must elapse by itself.
        final = isolated.wait_terminal(task_id, timeout_s=15.0)
        assert final is TaskState.CANCELLED

        record = isolated.store.get_approval(approval["id"])
        assert record is not None
        assert record["status"] == "EXPIRED"

        # An expired approval can no longer be decided through the API.
        with pytest.raises(HTTPException) as exc:
            api.decide_approval(approval["id"], api.ApprovalDecision(approved=True))
        assert exc.value.status_code == 409
        assert not (isolated.workspace_root / "notes.txt").exists()
    finally:
        isolated.release_pending_approvals(task_id)


def test_task_lifecycle_without_approval_completes(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    isolated = _IsolatedApi(monkeypatch, tmp_path, _demo_tool_plan())
    task_id = isolated.submit()

    final = isolated.wait_terminal(task_id)
    assert final is TaskState.COMPLETED
    task = isolated.store.get_task(task_id)
    assert task is not None
    assert task.result is not None
    assert isolated.store.list_approvals(task_id) == []
