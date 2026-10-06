from datetime import UTC, datetime
from pathlib import Path

from agent_core.events import AgentEvent, EventType
from agent_core.tasks import Task

from src.task_store import TaskStore


def test_task_and_event_round_trip(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    now = datetime.now(UTC)
    task = Task.create("hello", now)
    store.save_task(task)

    event = AgentEvent(
        type=EventType.TASK_CREATED,
        task_id=task.id,
        event_id="evt-1",
        timestamp=now,
        data={"request_chars": 5},
    )
    store.add_event(event)

    loaded = store.get_task(task.id)
    assert loaded is not None
    assert loaded.id == task.id
    assert loaded.request == "hello"
    assert store.events(task.id)[0]["event_id"] == "evt-1"


def test_task_store_survives_reopen(tmp_path: Path) -> None:
    path = tmp_path / "tasks.sqlite3"
    now = datetime.now(UTC)
    task = Task.create("persist me", now)

    TaskStore(path).save_task(task)
    reopened = TaskStore(path)

    assert reopened.get_task(task.id) is not None
    assert reopened.list_tasks(10)[0].request == "persist me"
