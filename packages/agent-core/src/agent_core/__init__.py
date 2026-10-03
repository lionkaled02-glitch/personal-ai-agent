"""agent-core — modular foundation for a personal autonomous AI agent.

Phase 0 (IMPLEMENTED): task state model, model-driven planner, executor,
tool system with registry and JSON-Schema validation, permission manager
(LOW/MEDIUM/HIGH, fail-safe approvals), structured event bus, vendor-neutral
ModelProvider interface with a deterministic mock, and one demo tool that
proves the end-to-end flow.

Phase 1 (IMPLEMENTED): model gateway (error normalization + safe retry),
configuration-driven provider selection, and a real OpenAI provider adapter
(optional ``openai`` extra, lazy SDK import).

Phase 2 (IMPLEMENTED): the tool runtime (permission-gated, schema-validated,
metadata-carrying tool execution with structured lifecycle events) and a set
of safe, deterministic built-in tools (calculator, date/time, text utils,
JSON utils).

Phase 3 (IMPLEMENTED): a safe, provider-agnostic filesystem/workspace tool
layer. Nine tools (list_directory, read_text_file, write_text_file,
create_directory, copy_file, move_file, delete_file, file_info,
search_files) operate strictly inside an explicitly configured workspace
boundary enforced by :class:`agent_core.workspace.Workspace`. There is still
NO unrestricted shell/subprocess or arbitrary code execution.

Phase 4 (IMPLEMENTED): document processing & knowledge foundation. Six
formats (TXT, Markdown, PDF, DOCX, PPTX, XLSX) parse — via mature libraries
isolated behind the ``DocumentParser`` interface — into a normalized,
deterministic document model; documents chunk deterministically; and a
provider-neutral :class:`agent_core.documents.KnowledgeStore` performs
lexical retrieval. Four tools (inspect_document, extract_document,
index_document, search_documents) are permission-gated and read only through
the Phase 3 workspace boundary. Document content is untrusted DATA, never
instructions.

Everything else (UI, browser/computer control, voice, media generation,
full long-term memory, vector retrieval) is PLANNED — see ARCHITECTURE.md
and ROADMAP.md at the repository root for what exists and what does not.
"""

from .agent import Agent
from .builtin_tools import (
    CalculatorTool,
    DateTimeTool,
    JsonUtilsTool,
    TextUtilsTool,
    register_default_tools,
)
from .config import Settings
from .demo_tools import DEMO_TOOL_NAME, DemoTool
from .document_tools import (
    DOCUMENT_TOOL_NAMES,
    ExtractDocumentTool,
    IndexDocumentTool,
    InspectDocumentTool,
    SearchDocumentsTool,
    register_document_tools,
)
from .documents import (
    Document,
    DocumentChunk,
    DocumentError,
    DocumentLimits,
    DocumentSection,
    KnowledgeStore,
    RetrievalIndex,
)
from .errors import (
    AgentCoreError,
    PermissionDeniedError,
    PlanningError,
    ProviderConfigurationError,
    ProviderError,
    TaskStateError,
    ToolAlreadyRegisteredError,
    ToolExecutionError,
    ToolInputError,
    ToolNotFoundError,
    TransientProviderError,
)
from .events import AgentEvent, EventBus, EventType, bounded_text, bounded_value, utc_now
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
from .tool_runtime import ToolInvocation, ToolRuntime
from .tools import Tool, ToolRegistry, ToolResult, ToolSpec
from .workspace import Workspace, WorkspaceError, WorkspaceLimits
from .workspace_tools import (
    CopyFileTool,
    CreateDirectoryTool,
    DeleteFileTool,
    FileInfoTool,
    ListDirectoryTool,
    MoveFileTool,
    ReadTextFileTool,
    SearchFilesTool,
    WriteTextFileTool,
    register_workspace_tools,
)

__version__ = "0.5.0"

__all__ = [
    "DEMO_TOOL_NAME",
    "DOCUMENT_TOOL_NAMES",
    "SUPPORTED_PROVIDERS",
    "Agent",
    "AgentCoreError",
    "AgentEvent",
    "ApprovalCallback",
    "ApprovalRequest",
    "BasicVerifier",
    "CalculatorTool",
    "Capability",
    "ChatMessage",
    "CopyFileTool",
    "CreateDirectoryTool",
    "DateTimeTool",
    "DeleteFileTool",
    "DemoTool",
    "Document",
    "DocumentChunk",
    "DocumentError",
    "DocumentLimits",
    "DocumentSection",
    "EventBus",
    "EventType",
    "Executor",
    "ExtractDocumentTool",
    "FileInfoTool",
    "IndexDocumentTool",
    "InspectDocumentTool",
    "JsonUtilsTool",
    "KnowledgeStore",
    "ListDirectoryTool",
    "MockModelProvider",
    "ModelGateway",
    "ModelPlanner",
    "ModelProvider",
    "ModelRequest",
    "ModelResponse",
    "MoveFileTool",
    "OpenAIProvider",
    "PermissionDecision",
    "PermissionDeniedError",
    "PermissionLevel",
    "PermissionManager",
    "PermissionPolicy",
    "Plan",
    "PlanStep",
    "Planner",
    "PlanningError",
    "ProviderConfigurationError",
    "ProviderError",
    "ReadTextFileTool",
    "RetrievalIndex",
    "SearchDocumentsTool",
    "SearchFilesTool",
    "Settings",
    "StepStatus",
    "Task",
    "TaskState",
    "TaskStateError",
    "TaskStep",
    "TextUtilsTool",
    "Tool",
    "ToolAlreadyRegisteredError",
    "ToolDescriptor",
    "ToolExecutionError",
    "ToolInputError",
    "ToolInvocation",
    "ToolNotFoundError",
    "ToolRegistry",
    "ToolResult",
    "ToolRuntime",
    "ToolSpec",
    "TransientProviderError",
    "Verifier",
    "VerifyResult",
    "Workspace",
    "WorkspaceError",
    "WorkspaceLimits",
    "WriteTextFileTool",
    "bounded_text",
    "bounded_value",
    "build_gateway",
    "create_provider",
    "plan_json_schema",
    "register_default_tools",
    "register_document_tools",
    "register_workspace_tools",
    "utc_now",
    "validate_against_schema",
]
