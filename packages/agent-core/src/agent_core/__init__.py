"""agent-core — modular foundation for a personal autonomous AI agent.

Phase 0 (IMPLEMENTED): task state model, model-driven planner, executor,
tool system with registry and JSON-Schema validation, permission manager
(LOW/MEDIUM/HIGH, fail-safe approvals), structured event bus, vendor-neutral
ModelProvider interface with a deterministic mock, and one demo tool that
proves the end-to-end flow.

Everything else (real providers, real tools, UI, browser/computer control,
voice, media generation, RAG/memory) is PLANNED — see ARCHITECTURE.md and
ROADMAP.md at the repository root for what exists and what does not.
"""

from .agent import Agent
from .config import Settings
from .demo_tools import DEMO_TOOL_NAME, DemoTool
from .errors import (
    AgentCoreError,
    PlanningError,
    ProviderError,
    TaskStateError,
    ToolExecutionError,
    ToolInputError,
    ToolNotFoundError,
)
from .events import AgentEvent, EventBus, EventType, utc_now
from .executor import BasicVerifier, Executor, Verifier, VerifyResult
from .permissions import (
    ApprovalCallback,
    ApprovalRequest,
    PermissionDecision,
    PermissionLevel,
    PermissionManager,
    PermissionPolicy,
    ToolDescriptor,
)
from .planner import ModelPlanner, Plan, Planner, PlanStep
from .providers import (
    Capability,
    ChatMessage,
    MockModelProvider,
    ModelProvider,
    ModelRequest,
    ModelResponse,
)
from .schema import validate_against_schema
from .tasks import StepStatus, Task, TaskState, TaskStep
from .tools import Tool, ToolRegistry, ToolResult, ToolSpec

__version__ = "0.1.0"

__all__ = [
    "DEMO_TOOL_NAME",
    "Agent",
    "AgentCoreError",
    "AgentEvent",
    "ApprovalCallback",
    "ApprovalRequest",
    "BasicVerifier",
    "Capability",
    "ChatMessage",
    "DemoTool",
    "EventBus",
    "EventType",
    "Executor",
    "MockModelProvider",
    "ModelPlanner",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "PermissionDecision",
    "PermissionLevel",
    "PermissionManager",
    "PermissionPolicy",
    "Plan",
    "PlanStep",
    "Planner",
    "PlanningError",
    "ProviderError",
    "Settings",
    "StepStatus",
    "Task",
    "TaskState",
    "TaskStateError",
    "TaskStep",
    "Tool",
    "ToolDescriptor",
    "ToolExecutionError",
    "ToolInputError",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolResult",
    "ToolSpec",
    "Verifier",
    "VerifyResult",
    "__version__",
    "utc_now",
    "validate_against_schema",
]
