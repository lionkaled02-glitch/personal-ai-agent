"""Production-oriented HTTP/WebSocket application shell for Personal AI Agent."""
from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from agent_core import Agent, Settings, Task
from .task_store import TaskStore

settings = Settings.from_env()
store = TaskStore(settings.data_root / "tasks.sqlite3")
executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="agent-task")

app = FastAPI(
    title="Personal AI Agent",
    version="1.0.0",
    description="Bounded API for task submission, durable task state, and operational events.",
)


class TaskRequest(BaseModel):
    request: str = Field(min_length=1, max_length=20_000)
    input_channel: str = Field(default="text", pattern="^(text|voice)$")


def _run_task(task_id: str, request: TaskRequest) -> str:
    # Each task receives a fresh in-process agent so event history is isolated.
    gateway = build_gateway(settings)
    agent = Agent.create_configured(settings=settings, gateway=gateway)
    agent.events.subscribe(store.add_event)
    task = agent.run(request.request, input_channel=request.input_channel, task_id=task_id)  # type: ignore[arg-type]
    store.save_task(task)
    return task.id


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "agent": settings.agent_name}


@app.post("/tasks", status_code=202)
def create_task(request: TaskRequest) -> dict[str, str]:
    task_id = str(uuid.uuid4())
    # Persist a durable shell before handing work to the executor.
    now = settings
    from datetime import UTC, datetime
    store.save_task(Task(id=task_id, request=request.request, created_at=datetime.now(UTC), updated_at=datetime.now(UTC)))
    future = executor.submit(_run_task, task_id, request)
    try:
        task_id = future.result(timeout=0.05)
    except TimeoutError:
        # The task id is created inside Agent.run, so the asynchronous API
        # returns a job acknowledgement when it is still starting.
        return {"status": "accepted", "task_id": task_id}
    except Exception as exc:
        raise HTTPException(status_code=500, detail="task execution failed") from exc
    return {"status": "completed", "task_id": task_id}


@app.get("/tasks")
def list_tasks(limit: int = 50) -> list[dict[str, Any]]:
    return [task.model_dump(mode="json") for task in store.list_tasks(limit)]


@app.get("/tasks/{task_id}")
def get_task(task_id: str) -> dict[str, Any]:
    task = store.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return task.model_dump(mode="json")


@app.get("/tasks/{task_id}/events")
def get_events(task_id: str, limit: int = 200) -> list[dict[str, Any]]:
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
