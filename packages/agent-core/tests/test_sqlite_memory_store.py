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
