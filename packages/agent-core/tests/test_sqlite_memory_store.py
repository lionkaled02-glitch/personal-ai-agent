from datetime import UTC, datetime, timedelta
from pathlib import Path

from agent_core.memory import MemoryType, SourceCategory, SQLiteMemoryStore


def test_sqlite_memory_store_survives_restart(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first = SQLiteMemoryStore(path)
    memory = first.remember(
        memory_type=MemoryType.LONG_TERM,
        content="project uses a modular agent architecture",
        source=SourceCategory.USER_EXPLICIT,
        now=now,
    )

    second = SQLiteMemoryStore(path)
    loaded = second.get(memory.memory_id)

    assert loaded == memory
    assert second.recall("modular agent") == [memory]


def test_sqlite_memory_store_persists_soft_forget(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(path)
    memory = store.remember(
        memory_type="working",
        content="temporary task context",
        source="task",
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    store.forget(memory.memory_id)

    reopened = SQLiteMemoryStore(path)
    assert reopened.get(memory.memory_id) is not None
    assert reopened.list(active_only=True) == []


def test_sqlite_memory_store_persists_updates(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SQLiteMemoryStore(path)
    memory = store.remember(
        memory_type=MemoryType.LONG_TERM,
        content="original content",
        source=SourceCategory.USER_EXPLICIT,
        now=now,
    )

    updated = store.update(
        memory.memory_id,
        content="updated content",
        confidence=0.9,
        now=now + timedelta(minutes=1),
    )

    reopened = SQLiteMemoryStore(path)
    loaded = reopened.get(memory.memory_id)
    assert loaded is not None
    assert loaded.content == "updated content"
    assert loaded == updated
    assert reopened.recall("updated") == [updated]


def test_sqlite_memory_store_hard_forget_removes_row(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    store = SQLiteMemoryStore(path)
    memory = store.remember(
        memory_type=MemoryType.LONG_TERM,
        content="erase me completely",
        source=SourceCategory.USER_EXPLICIT,
        now=datetime(2026, 1, 1, tzinfo=UTC),
    )
    store.forget(memory.memory_id, hard=True)

    reopened = SQLiteMemoryStore(path)
    assert reopened.get(memory.memory_id) is None
    assert reopened.list(active_only=False) == []


def test_sqlite_memory_store_purge_is_durable(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    now = datetime(2026, 1, 1, tzinfo=UTC)
    store = SQLiteMemoryStore(path)
    expired = store.remember(
        memory_type=MemoryType.SHORT_TERM,
        content="temporary context that will expire",
        source=SourceCategory.TASK,
        now=now,
    )
    kept = store.remember(
        memory_type=MemoryType.LONG_TERM,
        content="permanent knowledge",
        source=SourceCategory.USER_EXPLICIT,
        now=now,
    )

    purged = store.purge_expired(now + timedelta(hours=2))
    reopened = SQLiteMemoryStore(path)

    assert purged == 1
    assert reopened.get(expired.memory_id) is None
    assert reopened.get(kept.memory_id) == kept


def test_sqlite_memory_store_accepts_injected_clock(tmp_path: Path) -> None:
    path = tmp_path / "memory.sqlite3"
    fixed = datetime(2026, 5, 1, tzinfo=UTC)
    store = SQLiteMemoryStore(path, clock=lambda: fixed)

    memory = store.remember(
        memory_type=MemoryType.LONG_TERM,
        content="clock-injected creation",
        source=SourceCategory.USER_EXPLICIT,
    )

    assert memory.created_at == fixed
    reopened = SQLiteMemoryStore(path)
    assert reopened.get(memory.memory_id) == memory
