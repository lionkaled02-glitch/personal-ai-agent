# ARCHITECTURE

This document describes the architecture **as actually implemented** in the
repository. It explicitly distinguishes:

- **IMPLEMENTED** — code exists, is wired in, and is tested.
- **PLANNED** — designed and on the roadmap, not yet built.
- **NOT IMPLEMENTED** — desired, no design or code yet.

The target is a modular personal autonomous AI agent. It is built
**incrementally**, so most layers are intentionally not present yet.

---

## 1. Layering (target)

The long-term system is layered top-down. Arrows point *down* in the
dependency direction (a layer may depend only on layers below it).

```
┌────────────────────────────────────────────────────────────┐
│  User Interface          (CLI today; desktop/web later)    │  NOT IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  API                    (HTTP/WebSocket)                   │  NOT IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Task Manager           (task store, queue, persistence)   │  NOT IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Agent Orchestrator     (Agent + Executor)                 │  IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Planner                (request → plan of tool steps)     │  IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Tool Registry          (register / find / list / execute) │  IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Permission System      (LOW/MED/HIGH + approvals)         │  IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Specialized Agents     (browser/file/media/… agents)      │  NOT IMPLEMENTED
├────────────────────────────────────────────────────────────┤
│  Model Gateway (Phase 1)                                  │  IMPLEMENTED
│  provider selection, error normalization, safe retry      │
├────────────────────────────────────────────────────────────┤
│  External Providers / Computer / Browser / Files           │  PARTIAL (see below)
└────────────────────────────────────────────────────────────┘
```

**What "PARTIAL" means on the bottom row:** provider *interfaces* exist
(`ModelProvider`, `ComputerProvider`), the deterministic mock model provider
is implemented, and the OpenAI adapter (optional extra) is implemented. A
provider-neutral computer foundation and an optional Windows UI Automation
adapter are implemented; browser automation and unrestricted computer
control are not.

The implemented portion is the middle band: **Orchestrator → Planner →
Model Gateway → Provider → Tool Registry → Permission**, plus the opt-in
Phase 6 computer runtime and the events backbone that runs alongside all of
it.

---

## 2. Implemented components

All implemented code lives in the single package
`packages/agent-core/src/agent_core/`.

| Module | Key types | Responsibility | Status |
| --- | --- | --- | --- |
| `tasks.py` | `Task`, `TaskStep`, `TaskState`, `StepStatus` | Task/step state machines with an enforced transition map. Supports multi-step workflows. | IMPLEMENTED |
| `planner.py` | `Plan`, `PlanStep`, `Planner`, `ModelPlanner`, `plan_json_schema` | Turns a request into an ordered list of tool steps. Sends an explicit structured-output contract (`response_format`), tolerates one markdown code fence, and validates output (JSON → `Plan` schema → known tool names) before anything runs. | IMPLEMENTED |
| `executor.py` | `Executor`, `Verifier`, `BasicVerifier` | Runs a plan: TOOL_REQUESTED → permission check → approval → execute via the Tool Runtime → verify → terminal state. Emits task/step events incl. `TOOL_DENIED`. | IMPLEMENTED |
| `tools.py` | `Tool`, `ToolSpec`, `ToolResult`, `ToolRegistry` | Tool abstraction (incl. `version`, `deterministic` metadata) + registry with controlled execution and JSON-Schema validation. Structured `ToolResult` (`error_code`, `metadata`). | IMPLEMENTED |
| `tool_runtime.py` | `ToolRuntime`, `ToolInvocation` | The agent's only tool-execution path: requires an explicit ALLOWED permission decision (backstop), runs the registry's validate→run→validate pipeline, attaches execution metadata, emits tool lifecycle events, and redacts sensitive computer tool inputs/outputs from events. Provider-independent. | IMPLEMENTED |
| `schema.py` | `validate_against_schema` | Minimal JSON-Schema (subset) validator: `type`, `properties`, `required`, `items`, `enum`. | IMPLEMENTED |
| `permissions.py` | `PermissionLevel`, `PermissionPolicy`, `PermissionManager`, `ApprovalCallback` | Level-based policy decisions and fail-safe approval routing; a private, exact-tool authorization scope lets explicitly registered computer tools reuse the executor's existing approval without widening privileges. | IMPLEMENTED |
| `events.py` | `EventType`, `AgentEvent`, `EventBus`, `bounded_text`, `bounded_value` | Structured, in-memory event log + subscribers. Operational data only; `bounded_value` caps large tool I/O, computer outputs and typed-text inputs are redacted, and computer lifecycle events carry bounded status/metadata. | IMPLEMENTED |
| `providers/base.py` | `ModelProvider`, `ModelRequest`, `ModelResponse`, `Capability` | Vendor-neutral model interface. `stream`/`embed` are declared but raise until an adapter implements them. | IMPLEMENTED |
| `providers/mock.py` | `MockModelProvider` | Deterministic in-memory provider (scripted or keyword mode). No network, no key. Default provider. | IMPLEMENTED |
| `providers/gateway.py` | `ModelGateway` | `ModelProvider` decorator: normalizes provider errors, retries transient failures with bounded exponential backoff, passes structured responses through unchanged. Vendor-agnostic. | IMPLEMENTED |
| `providers/factory.py` | `create_provider`, `build_gateway`, `SUPPORTED_PROVIDERS` | Configuration-driven provider selection (`MODEL_PROVIDER`) + gateway construction. The only place that knows provider names. | IMPLEMENTED |
| `providers/openai_provider.py` | `OpenAIProvider` | Real Chat Completions adapter (optional `openai` extra, lazy SDK import). Env credentials, timeouts, sanitized error mapping. | IMPLEMENTED |
| `config.py` | `Settings` | Env-based configuration (`AGENT_NAME`, `LOG_LEVEL`, `DATA_ROOT`, `MODEL_PROVIDER`, `MODEL_NAME`, `MODEL_TIMEOUT_S`, `MODEL_MAX_RETRIES`, `WORKSPACE_ROOT`, `WORKSPACE_MAX_*` limits, `DOCUMENT_MAX_*` / `DOCUMENT_CHUNK_*` limits, `MEMORY_*` limits/TTLs, `COMPUTER_*` limits). No secrets. | IMPLEMENTED |
| `demo_tools.py` | `DemoTool` | The demo tool (`demo_tool`, LOW permission) used to prove the end-to-end flow. | IMPLEMENTED |
| `builtin_tools/` | `CalculatorTool`, `DateTimeTool`, `TextUtilsTool`, `JsonUtilsTool`, `register_default_tools` | Safe, deterministic, side-effect-free built-in tools (all LOW permission, bounded input). Date/time is declared non-deterministic. No shell/network. | IMPLEMENTED |
| `workspace.py` | `Workspace`, `WorkspaceError`, `WorkspaceLimits` | The workspace boundary: turns model-supplied (workspace-relative) paths into real filesystem paths with fail-closed resolution (no absolute paths, no `../` escape, no symlink/junction escape, no host-path leakage). | IMPLEMENTED |
| `workspace_tools/` | `ListDirectoryTool`, `ReadTextFileTool`, `WriteTextFileTool`, `CreateDirectoryTool`, `CopyFileTool`, `MoveFileTool`, `DeleteFileTool`, `FileInfoTool`, `SearchFilesTool`, `register_workspace_tools` | Nine filesystem tools scoped to the workspace boundary (LOW/MEDIUM/HIGH permission, bounded sizes/results, structured error codes, atomic writes, no shell/subprocess). See SECURITY.md for the safety model. | IMPLEMENTED |
| `documents/models.py` | `Document`, `DocumentSection`, `DocumentChunk`, `SearchResult` + deterministic id helpers | The normalized document model: Pydantic, deterministic, serializable. Workspace-relative `source_path` only; stable ids derived from inputs; page/slide/sheet locations; extraction warnings + stats + truncation flag. | IMPLEMENTED |
| `documents/errors.py` | `DocumentError` + stable codes | Structured document-domain failures: `unsupported_document_type`, `document_not_found`, `document_too_large`, `document_corrupt`, `extraction_failed`, `decode_failed`, `parser_limit_exceeded`, `invalid_document`, `security_violation` (+ `parser_unavailable`, `invalid_query`, `invalid_input`, `document_not_indexed`, `chunk_not_found`). | IMPLEMENTED |
| `documents/limits.py` | `DocumentLimits` | Frozen, validated safety limits (input bytes, extracted chars, pages/slides/sheets, sections, chunks, chunk size/overlap, search results, query chars). Fail-safe: limits either reject (structured error) or produce an **explicitly reported** truncation. | IMPLEMENTED |
| `documents/parsers/` | `DocumentParser`, `ParserRegistry`, `RawSection`, `ExtractedContent`, `default_registry`, built-in parsers (text, markdown, pdf, docx, pptx, xlsx) | The parser seam: `_extract` (library-specific) → shared `normalize` (limits, truncation reporting, stats, ids). Binary parsers lazy-import their optional library (pypdf / python-docx / python-pptx / openpyxl) and fail with `parser_unavailable` when it is missing. Content is data only — nothing is ever executed. | IMPLEMENTED |
| `documents/chunking.py` | `split_text`, `chunk_document`, `ChunkingResult` | Deterministic bounded chunking: paragraph-aware, hard-splits oversized paragraphs with overlap carry, count-capped with an explicit truncation report. Preserves document/section ids and location metadata on every chunk. No embeddings. | IMPLEMENTED |
| `documents/retrieval.py` | `KnowledgeStore`, `RetrievalIndex` (protocol) | Provider-neutral in-memory lexical index: add/replace/remove documents + chunks, `search` with deterministic TF/IDF token ranking, document filtering, and result caps. The protocol is the seam a future vector store implements without touching the model or tools. | IMPLEMENTED |
| `document_tools/` | `InspectDocumentTool`, `ExtractDocumentTool`, `IndexDocumentTool`, `SearchDocumentsTool`, `register_document_tools` | Four permission-gated tools over the document layer (inspect/extract/search LOW, index MEDIUM). All paths resolve through the Phase 3 `Workspace`; inputs/outputs schema-validated; failures are structured `ToolResult`s, never crashes. | IMPLEMENTED |
| `memory/models.py` | `Memory`, `MemoryType`, `SourceCategory`, `make_memory_id`, `metadata_size_bytes` | The memory model: Pydantic, provider-neutral, deterministic. Stable ids derived from (type, source, content, created_at); lifecycle types (`short_term`/`working`/`long_term`/`knowledge`); provenance (`user_explicit`/`task`/`agent`/`document`/`system` + optional source ref); confidence; timestamps; optional expiration; soft-delete `active` flag. | IMPLEMENTED |
| `memory/limits.py` | `MemoryLimits` | Frozen, validated limits + policy (allowed types, content chars, metadata bytes, item cap, recall cap, context chars/items, short-term/working TTLs). From `Settings` (`MEMORY_*`). | IMPLEMENTED |
| `memory/guards.py` | `contains_secret_like_content` | Conservative secret-content heuristic (credential shapes, token prefixes, key blocks, URL credentials). A heuristic, not a guarantee — the real guarantees are structural (explicit creation, data-only content). | IMPLEMENTED |
| `memory/store.py` | `MemoryStore` (protocol), `InMemoryMemoryStore` | Provider-neutral storage + recall: `remember`/`get`/`update`/`forget`/`list`/`recall`/`purge_expired`. Policy enforced at the store layer (defense in depth); deterministic ordering; `forget` = soft deactivation by default (hard delete opt-in, single memory, never recursive); expiration with long-term protection (only `short_term`/`working` auto-expire/purge). No external DB, no network. | IMPLEMENTED |
| `memory/retrieval.py` | `MemoryRetriever` (protocol), `LexicalMemoryRetriever` | The retrieval seam: deterministic lexical recall over the store (reuses the Phase 4 tokenizer; TF/IDF ranking, stable id tie-breaks; active + non-expired scope; type filter; bounded). A future semantic retriever implements the same protocol. | IMPLEMENTED |
| `memory/errors.py` | `MemoryStoreError` + stable codes | Structured memory-domain failures: `memory_not_found`, `memory_invalid_input`, `memory_type_not_allowed`, `memory_limit_exceeded`, `memory_field_immutable`, `secret_like_content`. (Named `MemoryStoreError` so it never shadows the Python builtin `MemoryError`.) | IMPLEMENTED |
| `memory_tools/` | `RememberTool`, `RecallTool`, `UpdateMemoryTool`, `ForgetTool`, `ListMemoriesTool`, `register_memory_tools` | Five permission-gated tools (remember/update MEDIUM, forget HIGH, recall/list LOW) over an explicit `MemoryStore`. Validation + limits at tool and store layer; immutable identity fields on update; forget soft by default; read outputs carry stable public fields only. | IMPLEMENTED |
| `rag/context.py` | `ContextBuilder`, `Context`, `ContextItem`, `ContextRequest` | Provider-neutral RAG assembly: retrieved memories (via `MemoryRetriever`) + document chunks (via `RetrievalIndex`) into a structured, bounded, deterministically ordered context. Memories first, then documents; every item carries kind (`memory`/`document`), source id/ref, provenance, location; char/item budget with explicit omission reporting; assembly only — no answer generation, no interpretation of content. | IMPLEMENTED |
| `errors.py` | `AgentCoreError` + subclasses | Single exception hierarchy so agent failures are catchable (incl. `PermissionDeniedError`, `ToolAlreadyRegisteredError`, `WorkspaceError`, `DocumentError`). Computer provider errors use stable, sanitized codes in `computer/errors.py`. | IMPLEMENTED |
| `computer/models.py`, `computer/interfaces.py`, `computer/limits.py` | `ComputerProvider`, bounded models, `ComputerLimits` | Provider-neutral screen/window/UI/screenshot observations and explicit mouse/keyboard action models; strict validation and finite hard/configured limits. UI labels are untrusted data. | IMPLEMENTED |
| `computer/runtime.py`, `computer/verification.py`, `computer/recovery.py` | `ComputerRuntime`, `VerificationCondition`, `RecoveryPolicy` | Existing permission-system integration around observation → authorization → action → fresh observation → deterministic verification; structured results/events, bounded safe retries and cooperative timeouts. No action is assumed successful without verification. | IMPLEMENTED |
| `computer/windows.py` | `WindowsComputerProvider` | Optional Windows UI Automation adapter; `pywinauto`, `pywin32`, and Pillow load only when explicitly constructed on Windows. Non-Windows use raises `UnsupportedPlatformError`; missing extras raise `ProviderUnavailableError`. | IMPLEMENTED |
| `computer_tools/` | 6 observation + 8 explicit action tools | Opt-in tools with declared schemas and LOW observation / MEDIUM interaction levels. No generic arbitrary-action tool. | IMPLEMENTED |
| `agent.py` | `Agent` | Facade that wires planner + registry + permissions + events + executor (+ knowledge store + memory store + context builder) into `run(request)`. `create_demo`/`create_configured` register the default tool set plus Phases 3–5 tools. Phase 6 tools are registered only when `create_configured(computer_provider=...)` receives an explicit provider; limits come from `COMPUTER_*`. No provider is auto-created. | IMPLEMENTED |

Entry point: `apps/backend/src/main.py` (demo, mock provider by default, no API key).

---

## 3. End-to-end flow (IMPLEMENTED)

`Agent.run(request)` executes the following and emits a structured event at
each observable transition:

```
1. TASK_CREATED        Task created (state CREATED), event emitted.
2. → PLANNING          Planner → Model Gateway → ModelProvider (mock or real).
                       Provider response is parsed as strict JSON (one markdown
                       fence tolerated) and validated against the Plan schema
                       and the registered tool names → invalid output becomes
                       a controlled PlanningError, never an invalid plan.
   PLAN_CREATED        Plan validated (tool names exist, shapes ok).
3. → RUNNING           Executor starts. For each step:
                         a. TOOL_REQUESTED (step picked up, permission level noted)
                         b. permission check (PermissionManager)
                         c. if REQUIRES_APPROVAL → APPROVAL_REQUIRED, ask channel
                            (no channel / denied → TOOL_DENIED → task CANCELLED,
                            TOOL not run)
                         d. if DENIED by policy → TOOL_DENIED → task CANCELLED
                         e. Tool Runtime (requires ALLOWED) → TOOL_STARTED →
                            registry: input validation → run → output validation
                            (input invalid → TOOL_INPUT_INVALID → TOOL_FAILED)
                            (output invalid → TOOL_OUTPUT_INVALID → TOOL_FAILED)
                         f. ok → TOOL_COMPLETED (metadata attached)
                            | fail → TOOL_FAILED (error_code) → task FAILED
4. → VERIFYING         Verifier checks the executed task (BasicVerifier: all steps done).
5. → COMPLETED         result set (last step output); or FAILED on verification failure.
   TASK_COMPLETED      (or TASK_FAILED / TASK_CANCELLED on the failure paths)
```

Gateway behavior on the planning call (Phase 1): transient provider failures
(timeout / 5xx / 429 / connection) are retried with bounded exponential
backoff (`MODEL_MAX_RETRIES`); any non-project exception is normalized to a
`ProviderError`; planning failures end the task as FAILED with a controlled
error.

Tool Runtime behavior (Phase 2): a tool cannot execute without an explicit
ALLOWED permission decision — the runtime raises `PermissionDeniedError` for
anything else (the executor only ever passes ALLOWED, so this is a
defense-in-depth backstop). Input and output are schema-validated; tool
exceptions are contained into a structured `ToolResult` (never a crash).

Tool Runtime payload bounding (Phase 3): `TOOL_STARTED`/`TOOL_COMPLETED`
carry the tool input/output through `bounded_value` — large values (e.g. a
file's content) are truncated to an excerpt in the *event* so the model still
receives the full result via the step output, but events/logs stay concise
and never carry bulk file content or secrets.

The happy path for the request `"Run the demo tool."` emits exactly:

```
TASK_CREATED → PLAN_CREATED → TOOL_REQUESTED → TOOL_STARTED
  → TOOL_COMPLETED → TASK_COMPLETED
```

Failure paths (invalid plan, unknown tool, failing tool, invalid input/output,
denied policy/approval) are all implemented and tested in
`packages/agent-core/tests/test_agent_flow.py`.

---

## 4. Key design decisions

Each decision lists the *why*, per the AGENTS.md rule to document decisions.

- **D1 — Single importable package (`agent-core`).** The core is a library;
  apps are thin scripts that import it. This keeps the core reusable by any
  future UI/API and enforces one-way dependencies.
- **D2 — Vendor-neutral `ModelProvider`.** The core depends on an interface,
  not a vendor SDK. `complete()` is the only required method; `stream()` and
  `embed()` are declared on the ABC and raise until a real adapter implements
  them. This keeps the core free of vendor lock-in (AGENTS.md rule 5).
- **D3 — Tools declared as JSON-Schema.** `ToolSpec` carries JSON-Schema for
  input/output, which (a) is portable to function-calling APIs later and
  (b) is testable without a provider. The registry validates both directions
  and *contains* tool exceptions into `ToolResult(ok=False)`.
- **D4 — Separation of registry and permissions.** The registry validates and
  executes; the *executor* checks permissions first. This keeps the registry
  reusable outside the agent loop and makes the permission boundary explicit
  and auditable.
- **D5 — Fail-safe permissions.** Defaults are `LOW=allowed`,
  `MEDIUM/HIGH=approval required`. If a step requires approval but no approval
  channel is configured, it is **denied**, never silently allowed. An explicit
  deny-list always wins. No tool has shell access today.
- **D6 — Events are operational only.** `AgentEvent.data` carries concise
  operational facts (task id, tool name, bounded input/output, error). Model
  chain-of-thought, raw prompts, and secrets are never placed in events (see
  SECURITY.md).
- **D7 — Synchronous by design (for now).** `Agent.run` is blocking. This is
  deliberate for the foundation; async execution is a later-phase concern and
  is NOT implemented.
- **D8 — Deterministic tests.** A mock provider + an injectable clock keep the
  entire suite offline, reproducible, and free of API keys.
- **D9 — Gateway as a decorator, not a new interface.** `ModelGateway`
  implements the *existing* `ModelProvider` ABC, so the planner/agent are
  unchanged and no second provider concept was introduced. Retry + error
  normalization live in exactly one place (the gateway); adapters stay thin.
  Streaming/embedding are delegated without retry (a half-consumed stream
  cannot be replayed).
- **D10 — Vendor SDKs are optional extras with lazy import.**
  `agent-core[openai]` adds the OpenAI SDK; `import agent_core` works without
  it (the SDK is imported only when the adapter actually builds a client or
  runs a request). Selecting a provider whose extra is not installed is a
  controlled `ProviderConfigurationError`.
- **D11 — Structured output: contract + validation, not faith.** The planner
  sends an explicit JSON contract in `ModelRequest.response_format`; adapters
  with native JSON mode map it (OpenAI → `json_object`). Reliability comes
  from post-validation (JSON parse → `Plan` schema → tool allow-list), so a
  poorly-behaved model can never produce an invalid plan. One markdown code
  fence is tolerated (real models emit it despite instructions).
- **D12 — Timeouts at the transport, retries at the gateway.** The adapter
  sets the HTTP timeout (`MODEL_TIMEOUT_S`) and disables the SDK's own
  retries (`max_retries=0`) so retry policy exists in one place: the gateway,
  with deterministic, testable backoff.
- **D13 — The Tool Runtime is the agent's only execution path; the registry
  stays permission-free.** The registry keeps the validate→run→validate
  pipeline and exception containment (reusable outside the agent loop); the
  runtime adds the permission precondition (explicit ALLOWED decision or
  `PermissionDeniedError`), execution metadata, and tool lifecycle events.
  No tool can be executed by the agent without passing both the permission
  system and schema validation. Phase 2 built-ins are all LOW-permission,
  deterministic (or declared non-deterministic), side-effect-free, and
  bounded; forbidden capabilities (shell/subprocess/eval/network) are
  verified absent by static + behavioral tests.
- **D14 — Filesystem access is confined to an explicit workspace boundary.**
  Phase 3 adds nine filesystem tools, but *no* unrestricted shell,
  subprocess, or arbitrary code execution. Every path is resolved by
  `Workspace.resolve()` against a configured root (`WORKSPACE_ROOT`) and the
  **fully resolved** path must be the root or under it — so absolute paths,
  `../` traversal, and symlinks/junctions/reparse-points that point outside
  are all rejected (`path_outside_workspace`). There are no string-prefix
  checks; containment is decided on the canonical path, and any case that
  cannot be proven safe fails closed with a structured security error.
  Permission levels (LOW read/list/info/search; MEDIUM write/create/copy/
  move; HIGH delete) reuse the Phase 2 fail-safe approval mechanism, so a
  denied operation never touches the filesystem. Writes are atomic and
  bounded; events carry only relative paths + metadata, never host paths or
  file contents. See SECURITY.md for the full model.
- **D15 — Parsers are a replaceable seam; the core model is library-free.**
  Phase 4's document layer depends on the `DocumentParser` interface and the
  normalized Pydantic models — never on a specific parser library. Each
  built-in parser implements `_extract` (library-specific) and inherits the
  shared `normalize` (limits, truncation reporting, stats, ids). The four
  binary parsers (PDF/DOCX/PPTX/XLSX) live behind an optional `docs` extra
  and import their library **lazily at parse time**; a missing library is a
  structured `parser_unavailable` error, so the package stays importable and
  the registry shape stays stable. TXT/Markdown need no dependency. All
  parser libraries are used for *parsing only* — macros, embedded scripts,
  formulas, links, and any other executable content are never run (XLSX is
  opened `read_only` + `data_only`, i.e. cached values, no formula
  evaluation), and document text is never interpreted as instructions.
- **D16 — Retrieval is lexical and deterministic, behind a swappable
  protocol.** `KnowledgeStore` implements `RetrievalIndex` (add/replace/
  remove/get/search) with token-based TF/IDF ranking: no embeddings, no
  external model, no network — the same query over the same index always
  yields the same ranked results (ties break on chunk id). The protocol is
  the deliberate seam: a future vector/embedding store can implement the same
  interface without changing the document model or the tools.
- **D17 — Document I/O rides the Phase 3 workspace boundary; indexing is a
  MEDIUM mutation.** All four document tools resolve paths through
  `Workspace.resolve()` — document tools inherit the entire Phase 3 safety
  model (no absolute paths, no escape, fail-closed). `inspect/extract/
  search` are LOW (read-only); `index_document` is MEDIUM because it mutates
  internal knowledge state (analogous to workspace file mutations), so a
  denied index never touches the store. Limits are configuration-driven
  (`DOCUMENT_*` env vars) and fail-safe: size violations are structured
  errors, capacity violations produce **explicitly reported** truncation —
  never silent.
- **D18 — Memory is explicit, typed, provider-neutral, and policy-enforced
  at the store layer.** Phase 5 adds a `Memory` model + `MemoryStore`
  protocol with the required `InMemoryMemoryStore` (no external DB, no
  network). Key choices: (a) **creation is explicit** — a MEDIUM-permission
  `remember` tool (or a clearly defined trusted internal pathway); nothing
  auto-saves conversation text, so there is no implicit privacy loss and no
  unbounded growth; (b) **identity is deterministic** — ids are pure
  functions of (type, source, content, created_at), `remember` is
  idempotent for identical inputs at the same instant, and ordering is
  always `(created_at, memory_id)`; (c) **policy lives in one place** —
  `MemoryLimits` (allowed types, content chars, metadata bytes, item cap,
  recall cap, TTLs) is enforced by the *store itself* (defense in depth),
  so no code path can bypass the caps; (d) **deletion is safe by default** —
  `forget` is a soft deactivation (hidden from recall/active listings, kept
  for audit, reversible via `update`), hard delete is an explicit `hard:
  true` opt-in, both behind HIGH-permission approval, and a forget never
  touches other memories; (e) **long-term protection is structural** —
  `long_term`/`knowledge` get no implicit TTL and `purge_expired` only ever
  touches `short_term`/`working`, so durable memory cannot silently
  disappear (and, by (a), cannot silently appear); (f) **secrets are
  rejected conservatively** — a heuristic guard blocks obvious credential
  shapes, documented as a heuristic (never a guarantee); the real guarantee
  is structural: memory is data, created explicitly, never auto-captured.
  Identity fields (type, source, source_ref, created_at) are immutable by
  construction — `update_memory` cannot change them, and attempting to is a
  structured `memory_field_immutable` failure.
- **D19 — RAG assembly is a bounded, provenance-preserving projection — not
  an answer generator.** The `ContextBuilder` combines retrieved memories
  (via the `MemoryRetriever` protocol) and retrieved document chunks (via
  the Phase 4 `RetrievalIndex` protocol) into a structured `Context`. Key
  choices: (a) **memory vs knowledge stay distinct but composable** — items
  are explicitly typed `memory` or `document` with their own provenance
  (memory source category / document path + page/slide/sheet location), so
  downstream consumers can reason about trust and origin; a `knowledge`-type
  memory is still a *memory* (a deliberately stored fact), never an implicit
  document load; (b) **deterministic order** — memories in recall rank
  order, then document chunks in search rank order, both deterministic
  (stable id tie-breaks); (c) **bounded with explicit omission** — the char
  budget (`MEMORY_MAX_CONTEXT_CHARS`) and item cap
  (`MEMORY_MAX_CONTEXT_ITEMS`) are enforced by dropping whole items in
  order, and every drop is reported in `omitted_items`/`truncated` —
  provenance is never silently lost; (d) **assembly only** — the builder
  retrieves, orders, and bounds; it never generates answers and never
  interprets content. Retrieved memory and document content is untrusted
  DATA: it is labeled as such in the context and is never executed,
  converted into tool calls, or allowed to change permissions or bypass
  approval (verified by security tests). The two retrieval protocols are
  the seams: a future embedding/vector provider can replace
  `LexicalMemoryRetriever`/`KnowledgeStore` without touching the builder,
  the memory model, or the tools. No embeddings in this phase.
- **D20 — Computer interaction is provider-neutral, explicit, permissioned,
  and postcondition-verified.** Phase 6 adds a `ComputerProvider` protocol,
  bounded typed models/runtime, an opt-in Windows UI Automation adapter,
  and 14 named tools (six observations, eight interactions). No provider is
  created automatically and there is no generic action/command tool. The
  lifecycle is observation → intent validation → existing `PermissionManager`
  check/approval → one bounded action → fresh observation → deterministic
  verification. Observation is LOW; every interaction (including mouse
  movement, focus, selection, and keyboard input) is MEDIUM; destructive,
  externally consequential, and unknown operation names classify as HIGH.
  Executor approval is reused only for the exact registered tool invocation
  through a private scope; it cannot lower a HIGH requirement or bypass the
  deny-list. A provider returning without a verified postcondition is
  `unverified`, never success. Only idempotent operations with safe
  conditions may retry, under a small configured budget; clicks, typing,
  and other non-idempotent input do not auto-retry. Timeouts are cooperative:
  the synchronous runtime detects an overrun but cannot forcibly interrupt a
  blocked OS API call. UI/window data is untrusted; screenshot bytes are
  sensitive, capped, returned only by explicit screenshot requests, kept
  in-memory, and omitted from action history and events. The Windows extra
  is optional and lazily imported; non-Windows behavior is a structured
  `unsupported_platform` result, not a failed import.

---

## 5. What is NOT implemented (explicit)

These are **NOT IMPLEMENTED** and must not be added prematurely
(AGENTS.md rule 15). They are tracked in [ROADMAP.md](ROADMAP.md):

- Second real provider adapter (Anthropic, local models, ...). Only OpenAI
  exists today (plus the mock).
- Streaming and embeddings (interface declared; all adapters raise until
  implemented).
- Native strict `json_schema` output mode (the openai adapter uses
  `json_object` mode; see decision D11).
- Side-effecting tools *beyond the workspace boundary*: web fetch/search,
  browser automation, and unrestricted computer control remain
  NOT IMPLEMENTED. Phase 3's filesystem tools are scoped to `WORKSPACE_ROOT`;
  Phase 6 adds only the explicit, bounded Windows computer foundation
  described in D20. There is no shell, process launch, arbitrary code
  execution, remote desktop, or generic computer action tool.
- Output verification beyond "all steps completed" (a richer `Verifier`).
- Human-facing approval channel (CLI prompt / UI); a synchronous approval
  callback protocol exists and is fail-safe.
- Browser automation and voice I/O.
- Image/video generation and presentation/document *generation*. (Reading &
  analyzing existing documents — TXT/MD/PDF/DOCX/PPTX/XLSX — is IMPLEMENTED
  in Phase 4; producing new documents is not.)
- **Semantic/vector** retrieval (embeddings) for documents *or* memory.
  Phase 4 document retrieval and Phase 5 memory retrieval are deliberately
  *lexical* and deterministic (in-memory `KnowledgeStore` behind the
  `RetrievalIndex` protocol; `InMemoryMemoryStore`/`LexicalMemoryRetriever`
  behind the `MemoryStore`/`MemoryRetriever` protocols); a vector/embedding
  backend is a future phase that plugs into those same protocols.
- **Persistent (durable) memory** across process restarts. Phase 5 memory
  is in-process only (`InMemoryMemoryStore`); a durable backend (e.g.
  SQLite) is a future phase that implements the `MemoryStore` protocol.
- Task Manager layer (task persistence, queueing, multi-task scheduling).
- User interface and API layer (HTTP/WebSocket).
- `WAITING_FOR_USER`, `PAUSED`, `TASK_PAUSED`, `TASK_RESUMED` are **modeled**
  in the state machine but not yet *driven* by any implemented flow (the
  approval flow is synchronous today).

---

## 6. How new capability plugs in

- **New tool:** implement `spec: ToolSpec` (name, description, input/output
  JSON-Schema, `permission_level`, `version`, `deterministic`) +
  `run(input) -> ToolResult`; register it in a `ToolRegistry` (or use
  `register_default_tools` for the built-in set). The Tool Runtime then
  handles permission gating, validation, metadata, and events — no core
  changes. Tools must be safe by construction (bounded inputs, structured
  failures via `error_code`); see CONTRIBUTING.md for the checklist.
- **New model provider:** subclass `ModelProvider`, implement `complete()`
  (and optionally `stream()`/`embed()`), declare `capabilities`. Add an
  optional extra in `packages/agent-core/pyproject.toml`, import the vendor
  SDK **lazily** (keep the package importable without it), and register the
  provider name in `providers/factory.py`. Everything upstream (gateway,
  planner, agent) then works unchanged. See CONTRIBUTING.md for the pattern.
- **New computer provider (Phase 6):** implement `ComputerProvider` using
  only the explicit observation and input primitives. Keep the provider
  optional and platform-isolated; enforce the same bounds and existing
  `PermissionManager`, treat UI data as untrusted, and never add command,
  process, network, or generic arbitrary-action methods. Pass the provider
  explicitly to `Agent.create_configured(computer_provider=...)`.
- **New document parser (Phase 4):** subclass `DocumentParser`, declare
  `supported_extensions` / `supported_media_types`, implement `_extract`
  (return `ExtractedContent`), and register the instance in a
  `ParserRegistry` (or `default_registry()` for the built-in set). The
  shared `normalize` applies limits, truncation reporting, stats, and
  deterministic ids; the document tools and the knowledge store then work
  with the new format unchanged. Keep any third-party library import lazy
  and behind the optional `docs` extra, and use it for parsing only — never
  for executing anything the document contains.
- **New retrieval backend (Phase 4 seam):** implement the `RetrievalIndex`
  protocol (`add_document`, `add_chunks`, `remove_document`,
  `get_document`, `get_chunk`, `list_documents`, `search`) — e.g. a
  vector/embedding store — and pass it wherever a `KnowledgeStore` is
  injected. The document model and the four document tools stay unchanged.
- **New memory backend (Phase 5 seam):** implement the `MemoryStore`
  protocol (`limits`, `remember`, `get`, `update`, `forget`, `list`,
  `recall`, `purge_expired`) — e.g. a durable SQLite or vector store — and
  inject it via `Agent(memory_store=...)` / `register_memory_tools`. The
  memory model, the five memory tools, and the context builder stay
  unchanged; enforce the same policy at the store layer.
- **New memory retriever (Phase 5 seam):** implement the `MemoryRetriever`
  protocol (`recall`) — e.g. a semantic/embedding retriever over the same
  or a different store — and pass it to the `ContextBuilder`. Ranking must
  stay deterministic and bounded; the tool and builder contracts are
  unchanged.
- **New planner/verifier:** satisfy the `Planner` / `Verifier` protocols.
  Swap them into `Agent`.

These extension points are the reason the layering stays modular.
