"""Structured events for observable agent activity.

Events carry concise, *operational* information: what happened, for which
task/step, which tool, and a bounded result or error. They must NEVER carry
model chain-of-thought, raw model prompts, or secrets (see SECURITY.md).

The bus is in-process and in-memory. Persistent audit logging is a future
phase; the ``AgentEvent.to_dict()`` shape is the intended on-disk format.
"""

from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger("agent_core.events")


class EventType(StrEnum):
    """Structured event types for important agent activity."""

    TASK_CREATED = "TASK_CREATED"
    PLAN_CREATED = "PLAN_CREATED"
    TOOL_REQUESTED = "TOOL_REQUESTED"  # step picked up, before permission check (Phase 2)
    TOOL_STARTED = "TOOL_STARTED"
    TOOL_COMPLETED = "TOOL_COMPLETED"
    TOOL_FAILED = "TOOL_FAILED"
    TOOL_DENIED = "TOOL_DENIED"  # permission policy or approval refused the tool (Phase 2)
    TOOL_INPUT_INVALID = "TOOL_INPUT_INVALID"  # input failed the tool's input schema (Phase 2)
    TOOL_OUTPUT_INVALID = "TOOL_OUTPUT_INVALID"  # output failed the tool's output schema (Phase 2)
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    TASK_PAUSED = "TASK_PAUSED"
    TASK_RESUMED = "TASK_RESUMED"
    TASK_COMPLETED = "TASK_COMPLETED"
    TASK_FAILED = "TASK_FAILED"
    TASK_CANCELLED = "TASK_CANCELLED"


#: Default maximum length for text values copied into event payloads
#: (event data must stay concise and operational — see SECURITY.md).
EVENT_TEXT_LIMIT = 200


def bounded_text(text: str, limit: int = EVENT_TEXT_LIMIT) -> str:
    """Truncate text for event payloads without altering short values."""
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


@dataclass(frozen=True)
class AgentEvent:
    """One structured, operational observation of agent activity."""

    type: EventType
    task_id: str | None
    event_id: str
    timestamp: datetime
    step_id: str | None = None
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Stable serializable form (future audit-log / API payload)."""
        return {
            "event_id": self.event_id,
            "type": self.type.value,
            "task_id": self.task_id,
            "step_id": self.step_id,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
        }


Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)


class EventBus:
    """In-process event log with subscriber support.

    Thread-safe: ``emit``/``subscribe`` are guarded by a lock. Handlers are
    invoked outside the lock. Determinism in tests comes from injecting a
    fixed ``clock``.
    """

    def __init__(self, clock: Clock | None = None) -> None:
        self._handlers: list[Callable[[AgentEvent], None]] = []
        self._lock = threading.Lock()
        self._clock: Clock = clock or utc_now
        self.history: list[AgentEvent] = []

    def subscribe(self, handler: Callable[[AgentEvent], None]) -> None:
        """Register a handler invoked synchronously for every new event."""
        with self._lock:
            self._handlers.append(handler)

    def emit(
        self,
        event_type: EventType,
        *,
        task_id: str | None = None,
        step_id: str | None = None,
        data: dict[str, Any] | None = None,
    ) -> AgentEvent:
        """Record and dispatch one event. Returns the recorded event."""
        event = AgentEvent(
            type=event_type,
            task_id=task_id,
            step_id=step_id,
            event_id=str(uuid.uuid4()),
            timestamp=self._clock(),
            data=dict(data or {}),
        )
        with self._lock:
            self.history.append(event)
            handlers = list(self._handlers)
        # Log the event *type* and task id only — never event payloads, which
        # may contain user content.
        logger.debug("event=%s task_id=%s", event.type.value, event.task_id)
        for handler in handlers:
            handler(event)
        return event

    def events_of_type(self, event_type: EventType) -> list[AgentEvent]:
        return [event for event in self.history if event.type == event_type]

    def __len__(self) -> int:
        return len(self.history)
