"""Production-oriented HTTP/WebSocket application shell for Personal AI Agent."""

from __future__ import annotations

import asyncio
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from threading import Event, Lock
from typing import Any, cast

from agent_core import Agent, Settings, Task, TaskState, build_gateway
from agent_core.permissions import ApprovalCallback, ApprovalRequest
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from task_store import TaskStore

settings = Settings.from_env()
store = TaskStore(settings.data_root / "tasks.sqlite3")
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-task")
approval_waiters: dict[str, Event] = {}
approval_lock = Lock()
# Bounded wait for a human decision; on timeout the approval expires and the
# step fails closed (denied). Fail-safe: no decision => no mutation.
APPROVAL_WAIT_TIMEOUT_S = 300.0

app = FastAPI(
    title="Personal AI Agent",
    version="1.0.0",
    description="Bounded API for task submission, durable task state, and operational events.",
)


class TaskRequest(BaseModel):
    request: str = Field(min_length=1, max_length=20_000)
    input_channel: str = Field(default="text", pattern="^(text|voice)$")


def _transition_stored_task(task_id: str, expected: TaskState, target: TaskState) -> None:
    """Persist one durable task-state transition for a live worker task.

    The guard makes this a no-op when the stored task is missing, already
    terminal, or not in the expected state, so a late or raced transition can
    never corrupt the durable shell.
    """
    task = store.get_task(task_id)
    if task is None or task.state is not expected:
        return
    task.transition(target, now=datetime.now(UTC))
    store.save_task(task)


def _mark_task_failed(task_id: str) -> None:
    """Force the durable shell to FAILED through legal transitions only."""
    task = store.get_task(task_id)
    if task is None or task.is_terminal():
        return
    now = datetime.now(UTC)
    if task.state is TaskState.CREATED:
        task.transition(TaskState.PLANNING, now=now)
    if task.state is TaskState.WAITING_FOR_USER:
        task.transition(TaskState.RUNNING, now=now)
    if task.state is TaskState.PLANNING:
        task.transition(TaskState.RUNNING, now=now)
    task.error = "task execution failed"
    task.transition(TaskState.FAILED, now=now)
    store.save_task(task)


def _run_task(task_id: str, request: TaskRequest) -> str:
    def approval_callback(approval: ApprovalRequest) -> bool:
        approval_id = str(uuid.uuid4())
        waiter = Event()
        with approval_lock:
            approval_waiters[approval_id] = waiter
        store.create_approval(
            approval_id,
            approval.task_id,
            approval.step_id,
            approval.tool_name,
            int(approval.permission_level),
            approval.reason,
            datetime.now(UTC).isoformat(),
        )
        _transition_stored_task(task_id, TaskState.RUNNING, TaskState.WAITING_FOR_USER)
        waiter.wait(timeout=APPROVAL_WAIT_TIMEOUT_S)
        record = store.get_approval(approval_id)
        if record is not None and record["status"] == "PENDING":
            # The bounded wait elapsed with no human decision. Expire the
            # record so the API/UI never offer a decision that can no longer
            # take effect, and so the flow fails closed.
            store.expire_approval(approval_id, datetime.now(UTC).isoformat())
            record = store.get_approval(approval_id)
        with approval_lock:
            approval_waiters.pop(approval_id, None)
        _transition_stored_task(task_id, TaskState.WAITING_FOR_USER, TaskState.RUNNING)
        return bool(record and record["status"] == "APPROVED")

    # Each task receives a fresh in-process agent so event history is isolated.
    # The workspace tools resolve against the configured boundary; ensure it
    # exists so a fresh deployment does not fail every workspace write with
    # "parent directory does not exist".
    settings.workspace_root.mkdir(parents=True, exist_ok=True)
    gateway = build_gateway(settings)
    agent = Agent.create_configured(
        settings=settings, gateway=gateway, approval=cast(ApprovalCallback, approval_callback)
    )
    agent.events.subscribe(store.add_event)
    # Reflect that the durable task is now executing, so status is truthful
    # while it runs and WAITING_FOR_USER/FAILED transitions stay legal.
    _transition_stored_task(task_id, TaskState.CREATED, TaskState.PLANNING)
    _transition_stored_task(task_id, TaskState.PLANNING, TaskState.RUNNING)
    try:
        completed_task = agent.run(
            request.request,
            input_channel=request.input_channel,  # type: ignore[arg-type]
            task_id=task_id,
        )
    except Exception:
        # Keep the durable shell truthful if a worker fails outside Agent.run's
        # controlled error handling.
        _mark_task_failed(task_id)
        raise
    store.save_task(completed_task)
    return completed_task.id


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": settings.agent_name}


@app.post("/tasks", status_code=202)
def create_task(request: TaskRequest) -> dict[str, str]:
    task_id = str(uuid.uuid4())
    # Persist a durable shell before handing work to the executor.
    store.save_task(
        Task(
            id=task_id,
            request=request.request,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
    )
    executor.submit(_run_task, task_id, request)
    return {"status": "accepted", "task_id": task_id}


@app.get("/tasks")
def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return cast(
        list[dict[str, Any]], [task.model_dump(mode="json") for task in store.list_tasks(limit)]
    )


@app.get("/approvals")
def list_approvals(task_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    return store.list_approvals(task_id, limit)


class ApprovalDecision(BaseModel):
    approved: bool


@app.post("/approvals/{approval_id}", status_code=200)
def decide_approval(approval_id: str, decision: ApprovalDecision) -> dict[str, Any]:
    record = store.get_approval(approval_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval not found")
    changed = store.decide_approval(approval_id, decision.approved, datetime.now(UTC).isoformat())
    if not changed:
        raise HTTPException(status_code=409, detail="approval already decided")
    with approval_lock:
        waiter = approval_waiters.get(approval_id)
    if waiter is not None:
        waiter.set()
    return {"approval_id": approval_id, "status": "APPROVED" if decision.approved else "DENIED"}


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task.model_dump(mode="json")


@app.get("/tasks/{task_id}/events")
def get_events(task_id: str, limit: int = 200) -> list[dict[str, Any]]:
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    if store.get_task(task_id) is None:
        raise HTTPException(status_code=404, detail="task not found")
    return store.events(task_id, limit)


@app.websocket("/tasks/{task_id}/events/stream")
async def event_stream(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    if store.get_task(task_id) is None:
        await websocket.send_json({"error": "task not found"})
        await websocket.close(code=1008)
        return
    seen: set[str] = set()
    try:
        while True:
            for event in store.events(task_id):
                if event["event_id"] not in seen:
                    seen.add(event["event_id"])
                    await websocket.send_json(event)
            task = store.get_task(task_id)
            if task is not None and task.is_terminal() and len(seen) >= len(store.events(task_id)):
                await websocket.send_json({"type": "STREAM_COMPLETE"})
                return
            await asyncio.sleep(0.25)
    except WebSocketDisconnect:
        return


# The bundled UI is intentionally static and contains no credentials or privileged logic.
app.mount(
    "/",
    StaticFiles(directory=Path(__file__).resolve().parent / "static", html=True),
    name="ui",
)
