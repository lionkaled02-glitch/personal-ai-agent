# SECURITY

This document defines the security model for the personal AI agent: how
permissions work, how secrets are handled, what the trust boundary is, and
what is explicitly out of scope for the current phase.

---

## 1. Permission model

Every tool declares a `permission_level` on its `ToolSpec`:

| Level | Meaning (intended) | Default handling |
| --- | --- | --- |
| `LOW` | Read-only / harmless, no side effects | `ALLOWED` automatically |
| `MEDIUM` | Some side effects, scoped (workspace file writes/creates/copies/moves) | `REQUIRES_APPROVAL` |
| `HIGH` | Broad or irreversible (e.g. `delete_file`; future computer control) | `REQUIRES_APPROVAL` (stricter by policy) |

Decisions are produced by `PermissionManager` from a data-driven
`PermissionPolicy` (per-level decision + an explicit **deny-list** of tool
names that always wins). The *executor* enforces the decision **before** a
tool is ever run.

### Fail-safe defaults

- If a step is `REQUIRES_APPROVAL` but **no approval channel is configured**,
  the step is **denied** — never silently allowed.
- The deny-list overrides any level policy.
- There is **no tool with shell access today**, and none may be added without
  a HIGH level + approval + an explicit allow/deny policy (Phase 8).

### Approval flow

`REQUIRES_APPROVAL` ⇒ an `APPROVAL_REQUIRED` event is emitted and the
configured `ApprovalCallback` is asked. Approval is **synchronous** in the
current phase. `WAITING_FOR_USER` / async approvals (a UI a human acts on
later) are modeled in the state machine but **NOT IMPLEMENTED** yet.

---

## 2. Secrets handling

- **Environment-based config only.** Non-secret tunables flow through
  `agent_core.config.Settings`, which reads plain environment variables
  (`AGENT_NAME`, `LOG_LEVEL`, `DATA_ROOT`, `MODEL_PROVIDER`, `MODEL_NAME`,
  `MODEL_TIMEOUT_S`, `MODEL_MAX_RETRIES`).
- **`Settings` is secret-free by design.** Provider *credentials*
  (`OPENAI_API_KEY`) are read from the environment by the provider factory
  at construction time, passed straight to the vendor SDK, and never stored
  on `Settings`, on the provider object, in logs, or in error messages.
- **Default is keyless.** `MODEL_PROVIDER=mock` (the default) needs **no API
  key** and no network; the entire default test suite runs without
  credentials.
- **Never commit credentials.** `.env` (and any real config) is git-ignored.
  Only `.env.example`, with **placeholder values**, is committed.
- **Missing credentials fail cleanly.** Selecting `openai` without
  `OPENAI_API_KEY` raises a controlled `ProviderConfigurationError` naming
  the variable (never a value) — no crash, no network call, no invented key.
- **Never expose secrets in logs or events.** See §3.

Rules for contributors (mirrored in [AGENTS.md](AGENTS.md)):
no hard-coded secrets, no committed credentials, no secrets in logs/events.

---

## 3. Logging & events

- The **event bus** carries concise **operational** data only: task id, step
  id, tool name, bounded input/output, and error messages.
- **No chain-of-thought, no raw model prompts, no credentials** are ever
  placed in event payloads or logs. The event logger logs only the event type
  and task id, not payloads.
- Model-generated text that does reach an event (e.g. a plan step
  description) is **bounded in length** to keep payloads concise.
- **File contents are not logged by default.** `TOOL_STARTED`/`TOOL_COMPLETED`
  payloads pass through `bounded_value`: long strings are truncated to an
  excerpt and long lists capped, so a file read/write is observed as
  operation + relative path + size + status, not as bulk content. The full
  result is still returned to the model through the step output (events and
  results are deliberately different channels).
- **Workspace tool events carry only relative workspace paths** (POSIX
  style) and metadata (size, count, error code) — never the absolute host
  path and never directory listings of the host.
- A future persistent audit log (Phase 11) will serialize
  `AgentEvent.to_dict()` — the on-disk format is fixed now so it can be made
  append-only and redaction-aware later.

---

## 4. Trust boundary & current attack surface

**Default path (mock provider):** the agent runs **entirely in-process**
with the deterministic mock provider and the default tool set (Phase 2
built-ins `demo_tool`, `calculator`, `datetime`, `text_utils`, `json_utils`,
all side-effect-free, plus the Phase 3 workspace file tools and the Phase 4
document tools). It makes **no network calls**. Filesystem access is
confined to the configured workspace root (`WORKSPACE_ROOT`, default
`data/workspace` — git-ignored); nothing outside that root can be read,
written, or deleted through any tool. Document tools read only through that
same boundary, and documents are untrusted *data* — their content is never
executed or treated as instructions (see the Phase 4 subsection below).

### Tool runtime security (Phase 2)

- **Permission is a hard precondition of execution.** The Tool Runtime
  refuses to run any tool unless the caller passes an explicit ALLOWED
  decision (otherwise `PermissionDeniedError`). The executor obtains that
  decision from the permission manager; a tool cannot bypass the permission
  system by calling the registry directly through the agent path.
- **Model-generated tool arguments are untrusted input.** They are validated
  against the tool's declared input JSON-Schema *before* execution; invalid
  input is a structured failure (`TOOL_INPUT_INVALID`), never a coercion.
- **Tool outputs are validated too.** A tool that lies about its output
  shape is a structured failure (`TOOL_OUTPUT_INVALID`), not a value handed
  to the Agent.
- **Tool faults cannot crash the agent.** Exceptions are contained into a
  structured `ToolResult` with a machine-readable `error_code`.
- **Built-in tools are safe by construction.** No shell, subprocess,
  `eval`/`exec`, dynamic imports, sockets, or HTTP clients anywhere in the
  core source (verified by `tests/test_security_boundaries.py`). The
  calculator uses a hand-written parser over an explicit operator allow-list
  (no exponentiation, no identifiers); all built-in inputs are length-bounded.
  The Phase 2 built-ins do not touch the filesystem at all; the only
  filesystem access in the core is the Phase 3 workspace layer (below).
- **Built-in tool inventory (all LOW permission):**

  | Tool | Purpose | Deterministic | Bounds |
  | --- | --- | --- | --- |
  | `calculator` | `+ - * / // %`, parens, exponent literals | yes | expression ≤ 200 chars |
  | `datetime` | current date/time in an IANA timezone | **no** (reads the clock; injectable for tests) | n/a |
  | `text_utils` | length / word_count / line_count | yes | text ≤ 10,000 chars |
  | `json_utils` | validate/parse JSON, report shape | yes | text ≤ 100,000 chars |

- **Explicitly NOT present** (forbidden, and test-verified absent):
  unrestricted subprocess/PowerShell/cmd.exe, arbitrary Python execution,
  arbitrary (unscoped) filesystem modification, arbitrary network requests,
  browser/GUI automation, mouse/keyboard control, email, purchases,
  account/security changes.

### Workspace filesystem security (Phase 3)

The nine workspace tools are the **only** filesystem surface in the core.
Their security model:

- **Model-supplied paths are untrusted input.** Every tool receives
  *workspace-relative* paths; absolute paths (POSIX or Windows drive/UNC
  forms) are rejected even when they would land inside the root.
- **Containment is decided on the fully resolved path, never by string
  prefix.** `Workspace.resolve()` canonicalizes the candidate with
  `Path.resolve()` — which follows the whole chain of symlinks, Windows
  junctions, and reparse points — and requires the result to equal the root
  or be under it. `../` segments, `a/..` tricks, and a symlink inside the
  workspace that points outside all fail the same check
  (`path_outside_workspace`).
- **Fail closed.** NUL bytes, over-long paths, non-string inputs, and any
  resolution/OS failure that prevents proving containment are rejected with
  a structured error (e.g. `security_violation`) — the operation is never
  attempted when safety cannot be guaranteed.
- **No protected-location list is needed** because containment, not an
  allow-list, is the control: the workspace root is explicitly configured
  (`WORKSPACE_ROOT`), and pointing it at a sensitive location is a
  deployment decision documented in `.env.example` (with a warning not to do
  so).
- **Symlinks are never followed when walking.** `search_files` and
  directory listing use `followlinks=False` / non-following stat, so a
  symlinked directory cannot smuggle outside files into results.
- **Permissions gate every mutation.** LOW (list/read/info/search) runs
  automatically; MEDIUM (create/write/copy/move) and HIGH (delete) require
  explicit approval through the fail-safe mechanism — a denied operation
  never performs the filesystem action (test-verified).
- **Bounded and atomic.** File reads/copies are capped
  (`WORKSPACE_MAX_READ_BYTES`), writes capped (`WORKSPACE_MAX_WRITE_BYTES`)
  and written atomically (temp file + rename), listings and search capped
  (`WORKSPACE_MAX_LIST_ENTRIES`, `WORKSPACE_MAX_SEARCH_RESULTS`) with a
  `truncated` flag. Writes/copy/move never create parent directories
  implicitly; `delete_file` is files-only (no recursive directory deletion,
  never the root).
- **Structured, non-leaking errors.** Stable codes (`path_outside_workspace`,
  `path_not_found`, `source_not_found`, `target_exists`, `not_a_file`,
  `not_a_directory`, `file_too_large`, `content_too_large`, `decode_error`,
  `invalid_encoding`, `invalid_path`, `invalid_content`,
  `unsupported_operation`, `permission_denied`, `filesystem_error`,
  `security_violation`, ...) plus a message that contains only the
  workspace-relative path the caller supplied — never the absolute host
  path.

**Workspace tool inventory (Phase 3):**

  | Tool | Permission | Key bounds / notes |
  | --- | --- | --- |
  | `list_directory` | LOW | sorted, capped entries, symlink entries reported as `symlink` |
  | `read_text_file` | LOW | explicit encoding (default UTF-8), size cap, decode errors structured |
  | `write_text_file` | MEDIUM | explicit `overwrite`, size cap, atomic, no implicit mkdir |
  | `create_directory` | MEDIUM | nested creation, idempotent, never the root |
  | `copy_file` | MEDIUM | explicit `overwrite`, source size cap, atomic destination write |
  | `move_file` | MEDIUM | explicit `overwrite`, `os.replace` (same filesystem) |
  | `delete_file` | **HIGH** | files only; directories and the root are `unsupported_operation` |
  | `file_info` | LOW | missing path is a successful `exists:false` answer |
  | `search_files` | LOW | glob-style `*`/`?`/`[seq]` on the relative POSIX path (no regex), result cap, no symlink following |

**Opt-in path (real provider, Phase 1):** when `MODEL_PROVIDER=openai` is
set, the agent makes HTTPS calls to the configured provider endpoint.
Security properties of this path:

- The **only** network egress is the provider's Chat Completions API
  (or an explicitly configured `OPENAI_BASE_URL`). No shell, no filesystem
  access, no other egress exists in the codebase.
- **Model output is untrusted data.** It is parsed as strict JSON (one
  markdown fence tolerated), validated against the plan schema, and checked
  against the registered tool allow-list. An invalid or hostile model
  response becomes a controlled `PlanningError` — it cannot name a tool that
  is not registered, and tool inputs are schema-validated by the registry
  before execution.
- **Prompt injection cannot escalate privileges.** Even if a model (or data
  it processed) tries to plan a dangerous action, only registered tools
  exist and every tool is permission-gated (fail-safe). The only
  HIGH-permission tool is `delete_file` (single file, inside the workspace,
  explicit approval required); the MEDIUM workspace tools stay inside the
  boundary by construction. There is no shell and no browser.
- **Provider errors are sanitized.** Error messages carry status codes and
  bounded detail only; credentials never appear in them, in logs, or in
  events.
- **Retries are bounded and safe.** Only idempotent completion requests are
  retried, at most `MODEL_MAX_RETRIES` times with capped backoff; the SDK's
  own retry layer is disabled.

### Document processing security (Phase 4)

Phase 4 adds document parsing and lexical knowledge retrieval. The security
model:

- **Document content is untrusted data, never instructions.** Parsers extract
  text and structure only. Nothing found in a document is executed — no VBA
  macros, no embedded scripts (PDF JavaScript, Office embedded objects), no
  shell/PowerShell/Python, no external programs. Text that *looks like*
  commands ("run this", "ignore previous instructions", `__import__`, …) is
  stored and returned **verbatim as data** and is never interpreted by the
  agent core. Behavioral tests feed injection-style documents through the
  tools and assert nothing executes.
- **Parser libraries are parsing-only and optional.** The four binary
  parsers (pypdf, python-docx, python-pptx, openpyxl) are used strictly to
  read structure/text. XLSX is opened `read_only=True, data_only=True,
  keep_links=False` — cached cell values only, **formulas are never
  evaluated**, external links are dropped. PDF extraction is text-only;
  links/URIs are never followed. The libraries are an optional `docs` extra,
  imported lazily inside `_extract`; a missing library yields a structured
  `parser_unavailable` error. A static test whitelists every third-party
  import in the document layer (stdlib + the four parser libraries +
  pydantic) so no new capability can sneak in.
- **No new execution or network capability.** The Phase 4 modules introduce
  no subprocess, shell, `eval`/`exec`, `ctypes`, sockets, or HTTP clients —
  the existing static source-boundary tests cover them, and the document
  layer passes.
- **All document paths go through the Phase 3 `Workspace` boundary.**
  `inspect/extract/index` resolve every path via `Workspace.resolve()`
  before any read: absolute paths, `../` escapes, and symlink/junction
  escapes are rejected with the same structured codes; containment is
  fail-closed. Document tools never receive or return host paths.
- **Bounded processing, explicit truncation.** `DocumentLimits` (from
  `DOCUMENT_*` settings) cap raw input bytes (otherwise
  `document_too_large`), total extracted characters, pages/slides/sheets,
  sections, chunk count, query length, and result count. Exceeding a
  capacity cap produces `Document.truncated=True` + a recorded warning —
  truncation is never silent; exceeding a hard per-unit cap is
  `parser_limit_exceeded`. No unbounded memory growth on malformed or huge
  documents.
- **Permission-gated tools.** `inspect_document`, `extract_document`, and
  `search_documents` are LOW; `index_document` is MEDIUM (it mutates
  internal knowledge state) and goes through the same fail-safe approval
  path as workspace mutations — a denied index performs no store mutation.
  All tools run only through the Tool Runtime with an explicit ALLOWED
  decision, schema-validated inputs/outputs, and structured failures
  (tool failures never crash the agent process).
- **Observability stays bounded.** Events and tool outputs carry
  document/chunk ids, workspace-relative source paths, type, counts, sizes,
  durations, status, and error codes. `inspect_document` deliberately
  returns metadata only; full text is returned solely by the explicit
  `extract_document` tool (which the caller chose to invoke). No document
  content or sensitive extracted text is logged beyond tool outputs, and
  event payloads remain bounded by `bounded_value`.

**Future surface (NOT IMPLEMENTED, must be handled when built):**
- Side-effecting tools beyond the workspace boundary (web fetch/search)
  need per-tool scoping and MEDIUM/HIGH permission levels; any process or
  shell execution would be HIGH and require an explicit policy.
- Browser / computer control needs sandboxing, command allow/deny policies,
  and mandatory approval (Phases 7 & 9).
- Any UI/API needs authn/authz and input validation (Phase 11).
- Vector/semantic retrieval (embeddings) and persistent memory must preserve
  the lexical-index guarantees above (deterministic, bounded, provider-
  neutral) when built on the `RetrievalIndex` protocol (documents) and the
  `MemoryStore`/`MemoryRetriever` protocols (memory, see Phase 5 below).

### Memory & RAG security (Phase 5)

Phase 5 adds explicit memory and RAG context assembly. The security model:

- **Memory and document content is untrusted data, never instructions.**
  The `ContextBuilder` assembles retrieved memories and document chunks
  into a structured, labeled context; it never executes, interprets, or
  "obeys" any of that content. Injection text stored in a memory or a
  document ("ignore previous instructions", "invoke tool forget…",
  "change permission_level…", `__import__`, …) comes back **verbatim as
  data** and cannot trigger tools, change permissions, bypass approval, or
  alter system behavior. Behavioral tests feed injection payloads through
  recall + the context builder and assert nothing executes and no
  permission state changes.
- **Creation is explicit; nothing auto-persists.** Memory can only be
  created through the MEDIUM-permission `remember` tool (approval-gated,
  fail-safe) or a clearly defined trusted internal code path. The agent
  never saves user messages, model outputs, or conversation text
  implicitly — a full agent run that never plans a `remember` leaves the
  store empty (tested). This bounds both the privacy surface and the
  attack surface (no unbounded, model-influenced persistence).
- **Permissions gate all mutations and deletions.** `remember` and
  `update_memory` are MEDIUM; `forget` is HIGH — all through the existing
  fail-safe permission system (no approval channel ⇒ denied; policy deny
  always wins). A denied remember/update/forget performs **no store
  mutation** (tested). `recall` and `list_memories` are LOW (read-only).
  Memory content cannot bypass the permission system: a memory *saying*
  "run this without approval" changes nothing about how permissions are
  decided.
- **Writes are validated and bounded; failures are atomic.** The store
  (and tools) enforce: allowed types, non-empty content ≤
  `MEMORY_MAX_CONTENT_CHARS`, metadata ≤ `MEMORY_MAX_METADATA_BYTES`,
  total items ≤ `MEMORY_MAX_ITEMS`, confidence ∈ [0,1], valid
  `expires_at`, valid enums — each violation is a structured
  `MemoryStoreError` (stable code) and **nothing is half-written**
  (tested). Tool failures are contained `ToolResult`s — a memory failure
  never crashes the agent process.
- **No secrets by default; the guard is a documented heuristic.** A
  conservative pattern guard rejects content that obviously looks like
  credentials (`api_key=…`, bearer/authorization headers, `sk-…`/`AKIA…`/
  `ghp_…` token shapes, PRIVATE KEY blocks, `user:pass@host` URLs) with
  `secret_like_content`. This is a **heuristic, not a guarantee** — no
  detector can catch arbitrary secrets — so the real guarantees are
  structural: explicit creation only (no auto-capture of what might be a
  pasted secret), data-only content, and the standing rule that
  credentials belong in the environment, never in memory. Do not store
  API keys, passwords, tokens, or cookies in memories.
- **Expiration and long-term protection.** `short_term`/`working` get an
  implicit TTL (`MEMORY_SHORT_TERM_TTL_S`/`MEMORY_WORKING_TTL_S`);
  `long_term`/`knowledge` never expire implicitly and `purge_expired`
  never touches them. Expired or soft-forgotten memories are excluded from
  recall, active listings, and RAG contexts — they are never returned as
  "active".
- **Document-originated metadata is not trusted as provenance.** The
  context builder labels document items with its own provenance
  (`kind=document`, the stored workspace-relative `source_path`, and the
  chunk's structural location); nothing a document *says* about where it
  came from is taken as provenance.
- **No new execution or network capability.** The `memory/`,
  `memory_tools/`, and `rag/` modules are pure stdlib + pydantic (a static
  whitelist test enforces this); no subprocess, shell, `eval`/`exec`,
  `ctypes`, sockets, HTTP clients, or external database. Retrieval is
  lexical (reusing the Phase 4 tokenizer) — no embeddings, no external
  model, fully offline.
- **Privacy in events/logs.** `remember` returns and emits
  **metadata only** (memory id, type, source category, timestamps,
  active flag — no content). All tool I/O in events passes through
  `bounded_value` (200-char string cap, 10-item cap), so a 4,000-char
  memory is never fully logged by default; recall/list outputs carry the
  same bound in event payloads (the model still receives the full
  structured result via the step output — events and results are
  different channels).
- **Determinism and boundedness.** Recall ranking is deterministic
  (TF/IDF, stable id tie-breaks); listings order by
  `(created_at, memory_id)`; all recall/list/context outputs are bounded
  (`MEMORY_MAX_RECALL_RESULTS`, `MEMORY_MAX_CONTEXT_ITEMS`,
  `MEMORY_MAX_CONTEXT_CHARS`) and context omission is always reported
  (`truncated`/`omitted_items`), never silent.

---

## 5. Reporting

Report suspected vulnerabilities or unsafe behavior by opening a private
issue (do not post secrets or proof-of-concept exploit details publicly).

---

## 6. Status summary

| Area | Status |
| --- | --- |
| Permission levels + policy + fail-safe approvals | IMPLEMENTED |
| Deny-list of tools | IMPLEMENTED |
| Tool Runtime permission precondition (ALLOWED or `PermissionDeniedError`) | IMPLEMENTED |
| Controlled tool execution (schema validation, exception containment) | IMPLEMENTED |
| Tool input + output schema validation with structured failures | IMPLEMENTED |
| Structured tool results (`error_code` + execution `metadata`) | IMPLEMENTED |
| Safe built-in tools (LOW, bounded, no side effects) | IMPLEMENTED |
| Workspace boundary: resolved-path containment, no symlink/junction escape, fail-closed | IMPLEMENTED |
| Workspace file tools (9, scoped, LOW/MEDIUM/HIGH, bounded, atomic writes) | IMPLEMENTED |
| Delete is HIGH + fail-safe approval; denial never executes the filesystem action | IMPLEMENTED |
| Event payload bounding (`bounded_value`); no file contents / host paths in events | IMPLEMENTED |
| Document content treated as untrusted data — never executed or interpreted as instructions | IMPLEMENTED |
| Document layer third-party import whitelist (parsing-only libs, no new exec/network capability) | IMPLEMENTED |
| Document tools resolve every path through the Phase 3 workspace boundary (fail-closed) | IMPLEMENTED |
| Document limits (input bytes, extraction, containers, sections, chunks, query, results) with explicit truncation reporting | IMPLEMENTED |
| Document tool permissions (inspect/extract/search LOW, index MEDIUM); denied index performs no mutation | IMPLEMENTED |
| No document content in logs/events beyond explicit tool outputs; bounded payloads | IMPLEMENTED |
| Memory creation explicit only (permission-gated tool / trusted path); no auto-persistence of conversation | IMPLEMENTED |
| Memory tool permissions (remember/update MEDIUM, forget HIGH, recall/list LOW); denial performs no mutation | IMPLEMENTED |
| Memory write validation + limits enforced at the store layer, atomic failures (content, metadata, items, confidence, types) | IMPLEMENTED |
| Secret-like content guard (documented heuristic) + structural no-auto-capture guarantee | IMPLEMENTED |
| Expiration semantics: TTL only for short_term/working; long_term/knowledge protected; expired/forgotten never returned as active | IMPLEMENTED |
| Memory + document content as untrusted data: injection never triggers tools, permissions, or approval bypass | IMPLEMENTED |
| RAG context: bounded (chars/items), deterministic order, provenance-labeled, explicit omission reporting; no answer generation | IMPLEMENTED |
| Document-originated metadata not trusted as memory provenance | IMPLEMENTED |
| Memory layer third-party import whitelist (stdlib + pydantic; no new exec/network/DB capability) | IMPLEMENTED |
| remember events/confirmations carry metadata only (no content); all memory I/O in events bounded | IMPLEMENTED |
| Static + behavioral verification that forbidden capabilities are absent | IMPLEMENTED |
| Credentials via environment variables only; `Settings` secret-free; `.env` ignored; `.env.example` placeholders | IMPLEMENTED |
| Missing-credential and unknown-provider failures are clean, no network | IMPLEMENTED |
| Provider error sanitization (no key material, bounded detail) | IMPLEMENTED |
| Bounded, idempotent retry for transient provider failures | IMPLEMENTED |
| Untrusted model output: strict JSON + plan schema + tool allow-list | IMPLEMENTED |
| Operational-only events/logs, bounded payloads | IMPLEMENTED |
| Synchronous human approval channel | PLANNED (wire-up in Phase 2) |
| Persistent, redaction-aware audit log | PLANNED (Phase 11) |
| Sandboxing / command policies for real tools | NOT IMPLEMENTED (Phases 2/7/9) |
| UI/API authentication | NOT IMPLEMENTED (Phase 11) |
