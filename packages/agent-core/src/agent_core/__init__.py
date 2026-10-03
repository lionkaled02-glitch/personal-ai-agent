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

Phase 5 (IMPLEMENTED): memory & RAG foundation. A strongly typed,
provider-neutral ``Memory`` model (types, provenance, TTL, soft-delete)
behind the ``MemoryStore`` protocol (``InMemoryMemoryStore``), five
permission-gated memory tools (remember MEDIUM, update_memory MEDIUM,
forget HIGH, recall LOW, list_memories LOW), deterministic lexical memory
retrieval behind the ``MemoryRetriever`` protocol, and a provider-neutral
``ContextBuilder`` (RAG) that combines memories + document chunks into a
structured, bounded, provenance-labeled context. Memory creation is
explicit (never automatic); retrieved memory and document content are
untrusted DATA. Retrieval is lexical only — no embeddings in this phase.

Everything else (document/presentation generation, browser/computer
control, voice, media generation, semantic/vector retrieval, durable
memory, UI) is PLANNED — see ARCHITECTURE.md and ROADMAP.md at the
repository root for what exists and what does not.
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
from .memory import (
    InMemoryMemoryStore,
    LexicalMemoryRetriever,
    Memory,
    MemoryLimits,
    MemoryRetriever,
    MemoryStore,
    MemoryStoreError,
    MemoryType,
    SourceCategory,
    make_memory_id,
    metadata_size_bytes,
)
from .memory_tools import (
    MEMORY_TOOL_NAMES,
    ForgetTool,
    ListMemoriesTool,
    RecallTool,
    RememberTool,
    UpdateMemoryTool,
    register_memory_tools,
)
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
from .rag.context import Context, ContextBuilder, ContextItem, ContextRequest
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

__version__ = "0.6.0"

__all__ = [
    "DEMO_TOOL_NAME",
    "DOCUMENT_TOOL_NAMES",
    "FORGET_TOOL_NAME",
    "LIST_MEMORIES_TOOL_NAME",
    "MEMORY_TOOL_NAMES",
    "RECALL_TOOL_NAME",
    "REMEMBER_TOOL_NAME",
    "SUPPORTED_PROVIDERS",
    "UPDATE_MEMORY_TOOL_NAME",
    "Agent",
    "AgentCoreError",
    "AgentEvent",
    "ApprovalCallback",
    "ApprovalRequest",
    "BasicVerifier",
    "CalculatorTool",
    "Capability",
    "ChatMessage",
    "Context",
    "ContextBuilder",
    "ContextItem",
    "ContextRequest",
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
    "ForgetTool",
    "InMemoryMemoryStore",
    "IndexDocumentTool",
    "InspectDocumentTool",
    "JsonUtilsTool",
    "KnowledgeStore",
    "LexicalMemoryRetriever",
    "ListDirectoryTool",
    "ListMemoriesTool",
    "Memory",
    "MemoryLimits",
    "MemoryRetriever",
    "MemoryStore",
    "MemoryStoreError",
    "MemoryType",
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
    "RecallTool",
    "RememberTool",
    "RetrievalIndex",
    "SearchDocumentsTool",
    "SearchFilesTool",
    "Settings",
    "SourceCategory",
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
    "UpdateMemoryTool",
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
    "make_memory_id",
    "metadata_size_bytes",
    "plan_json_schema",
    "register_default_tools",
    "register_document_tools",
    "register_memory_tools",
    "register_workspace_tools",
    "utc_now",
    "validate_against_schema",
]
