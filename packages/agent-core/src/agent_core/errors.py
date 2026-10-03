"""Exception hierarchy for the agent core.

All agent failures derive from :class:`AgentCoreError` so callers can catch
agent-level problems without accidentally swallowing unrelated errors.
"""

from __future__ import annotations


class AgentCoreError(Exception):
    """Base class for all agent core errors."""


class TaskStateError(AgentCoreError):
    """An illegal task or step state transition was attempted."""


class PlanningError(AgentCoreError):
    """The planner produced an invalid or unusable plan (or failed)."""


class ToolNotFoundError(AgentCoreError):
    """A tool was requested that is not registered."""


class ToolInputError(AgentCoreError):
    """Tool input did not match the tool's declared input schema."""


class ToolExecutionError(AgentCoreError):
    """A registry-level tool execution failure.

    Faulty tool *results* normally surface as ``ToolResult(ok=False)``; this
    is reserved for unrecoverable failures at the registry boundary.
    """


class ProviderError(AgentCoreError):
    """A model provider could not service a request."""
