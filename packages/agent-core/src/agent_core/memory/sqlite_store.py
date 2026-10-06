"""Durable SQLite implementation of the provider-neutral MemoryStore."""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from datetime import datetime
from typing import Any

from agent_core.memory.limits import MemoryLimits
from agent_core.memory.models import Memory, MemoryType
from agent_core.memory.store import InMemoryMemoryStore


class SQLiteMemoryStore(InMemoryMemoryStore):
    """Persistent MemoryStore with SQLite durability and in-memory indexing.

    The lexical retrieval contract remains identical to InMemoryMemoryStore.
    SQLite is only the durable backing store; no network or vector database is
    introduced.
    """

    def __init__(self, path: Path, limits: MemoryLimits | None = None) -> None:
        self._db_path = path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db_lock = threading.RLock()
        super().__init__(limits)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS memories "
                "(memory_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
            )
            for row in db.execute("SELECT payload FROM memories"):
                self._items[row[0]] = Memory.model_validate_json(row[1])

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self._db_path, timeout=10)

    def _persist(self, memory: Memory) -> None:
        with self._db_lock, self._connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO memories(memory_id,payload) VALUES(?,?)",
                (memory.memory_id, memory.model_dump_json()),
            )

    def remember(self, **kwargs: Any) -> Memory:
        memory = super().remember(**kwargs)
        self._persist(memory)
        return memory

    def update(self, memory_id: str, **kwargs: Any) -> Memory:
        memory = super().update(memory_id, **kwargs)
        self._persist(memory)
        return memory

    def forget(self, memory_id: str, *, hard: bool = False, now: datetime | None = None) -> Memory:
        memory = super().forget(memory_id, hard=hard, now=now)
        with self._db_lock, self._connect() as db:
            if hard:
                db.execute("DELETE FROM memories WHERE memory_id=?", (memory_id,))
            else:
                db.execute(
                    "INSERT OR REPLACE INTO memories(memory_id,payload) VALUES(?,?)",
                    (memory.memory_id, memory.model_dump_json()),
                )
        return memory

    def purge_expired(self, now: datetime | None = None) -> int:
        removed_ids = [
            memory.memory_id
            for memory in self._items.values()
            if memory.memory_type in (MemoryType.SHORT_TERM, MemoryType.WORKING)
            and memory.is_expired(now or self._clock())
        ]
        count = super().purge_expired(now)
        if removed_ids:
            with self._db_lock, self._connect() as db:
                db.executemany(
                    "DELETE FROM memories WHERE memory_id=?", [(mid,) for mid in removed_ids]
                )
        return count
