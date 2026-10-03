"""agent-core — modular foundation for a personal autonomous AI agent.

Phase 0 (IMPLEMENTED): task state model, model-driven planner, executor,
tool system with registry and JSON-Schema validation, permission manager
(LOW/MEDIUM/HIGH, fail-safe approvals), structured event bus, vendor-neutral
ModelProvider interface with a deterministic mock, and one demo tool that
proves the end-to-end flow.

Phase 1 (IMPLEMENTED): model gateway (error normalization + safe retry),
configuration-driven provider selection, and a real OpenAI provider adapter
(optional ``openai`` extra, lazy SDK import).

Everything else (real tools, UI, browser/computer control, voice, media
generation, RAG/memory) is PLANNED — see ARCHITECTURE.md and ROADMAP.md at
the repository root for what exists and what does not.
"""

from .agent import Agent
from .config import Settings
from .demo_tools import DEMO_TOOL_NAME, DemoTool
from .errors import (
    AgentCoreError,
    PlanningError,
    ProviderConfigurationError,
    ProviderError,
    TaskStateError,
    ToolExecutionError,
    ToolInputError,
    ToolNotFoundError,
    TransientProviderError,
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
from .planner import ModelPlanner, Plan, Planner, PlanStep, plan_json_schema
from .providers import (
    SUPPORTED_PROVIDERS,
    Capability,
    ChatMessage,
    MockModelProvider,
    ModelGateway,
    ModelProvider,
    ModelRequest,
    ModelResponse,
    OpenAIProvider,
    build_gateway,
    create_provider,
)
from .schema import validate_against_schema
from .tasks import StepStatus, Task, TaskState, TaskStep
from .tools import Tool, ToolRegistry, ToolResult, ToolSpec

__version__ = "0.2.0"

__all__ = [
    "DEMO_TOOL_NAME",
    "SUPPORTED_PROVIDERS",
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
    "ModelGateway",
    "ModelPlanner",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "OpenAIProvider",
    "PermissionDecision",
    "PermissionLevel",
    "PermissionManager",
    "PermissionPolicy",
    "Plan",
    "PlanStep",
    "Planner",
    "PlanningError",
    "ProviderConfigurationError",
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
    "TransientProviderError",
    "Verifier",
    "VerifyResult",
    "build_gateway",
    "create_provider",
    "plan_json_schema",
    "utc_now",
    "validate_against_schema",
]
