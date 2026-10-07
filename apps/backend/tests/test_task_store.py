from datetime import UTC, datetime
from pathlib import Path

from agent_core.events import AgentEvent, EventType
from agent_core.tasks import Task
from task_store import TaskStore


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


def test_approval_round_trip_and_single_decision(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    now = datetime.now(UTC).isoformat()
    store.create_approval("ap-1", "task-1", "step-1", "demo", 2, "needs approval", now)

    record = store.get_approval("ap-1")
    assert record is not None
    assert record["status"] == "PENDING"
    assert store.decide_approval("ap-1", True, now) is True
    assert store.decide_approval("ap-1", False, now) is False
    record = store.get_approval("ap-1")
    assert record is not None
    assert record["status"] == "APPROVED"


def test_expired_approval_cannot_be_decided(tmp_path: Path) -> None:
    store = TaskStore(tmp_path / "tasks.sqlite3")
    now = datetime.now(UTC).isoformat()
    store.create_approval("ap-2", "task-2", "step-2", "demo", 2, "needs approval", now)

    assert store.expire_approval("missing", now) is False
    assert store.expire_approval("ap-2", now) is True
    assert store.expire_approval("ap-2", now) is False

    record = store.get_approval("ap-2")
    assert record is not None
    assert record["status"] == "EXPIRED"
    # An expired approval is no longer decidable; the flow failed closed.
    assert store.decide_approval("ap-2", True, now) is False
