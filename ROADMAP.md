# ROADMAP

The agent is built **incrementally**. Each phase adds capability on top of the
previous one and keeps the architecture modular. Every item is labeled:

- **IMPLEMENTED** — code exists, is wired in, and is tested.
- **PLANNED** — designed and scheduled, not yet built.
- **NOT IMPLEMENTED** — desired, no design or code yet.

A phase is "done" only when its acceptance criteria pass the quality gates
(format, lint, type-check, tests — see [CONTRIBUTING.md](CONTRIBUTING.md)).

---

## Phase 0 — Agent Core foundation ✅ IMPLEMENTED

The modular foundation and the first working end-to-end flow.

| Item | Status |
| --- | --- |
| Task state model (9 states) + enforced transitions | IMPLEMENTED |
| Planner (strict-JSON, tool-validated) | IMPLEMENTED |
| Executor (permission → approval → execute → verify) | IMPLEMENTED |
| Tool abstraction + Tool Registry + JSON-Schema validation | IMPLEMENTED |
| Permission system (LOW/MED/HIGH, fail-safe approvals) | IMPLEMENTED |
| Structured event system (EventBus, operational data only) | IMPLEMENTED |
| `ModelProvider` interface + deterministic mock provider | IMPLEMENTED |
| One mock tool (`demo_tool`) + end-to-end flow + tests | IMPLEMENTED |
| Env-based config (`Settings`), `.env.example`, no secrets | IMPLEMENTED |
| Tooling: ruff, mypy (strict), pytest — all green | IMPLEMENTED |
| Docs: AGENTS / ARCHITECTURE / ROADMAP / SECURITY / CONTRIBUTING | IMPLEMENTED |

**Not done in Phase 0 (by design):** real providers, real tools, UI, API,
browser, computer control, voice, media, RAG, memory.

---

## Phase 1 — Model Gateway & real provider integration ✅ IMPLEMENTED

A production-oriented gateway in front of the (unchanged) provider
abstraction, plus one real provider adapter. The Mock provider remains the
offline default; all tests run without credentials by default.

| Item | Status |
| --- | --- |
| Model Gateway: provider selection, stable interface, error normalization | IMPLEMENTED |
| Safe retry for transient failures (timeout/5xx/429/connection), bounded exponential backoff | IMPLEMENTED |
| Request timeouts (transport-level, configurable) | IMPLEMENTED |
| One real provider adapter (OpenAI Chat Completions, optional `openai` extra, lazy SDK import) | IMPLEMENTED |
| Keys via environment variables only (never in Settings, logs, or source) | IMPLEMENTED |
| Structured planning: explicit JSON contract + strict validation of model output | IMPLEMENTED |
| OpenAI-compatible endpoints via `OPENAI_BASE_URL` (local servers, proxies) | IMPLEMENTED |
| Opt-in live-provider test (skipped by default; runs only with `OPENAI_API_KEY`) | IMPLEMENTED |
| Real `stream()` / `embed()` on the adapter | NOT IMPLEMENTED (deferred — not needed for planning) |
| Second provider adapter (Anthropic, local models, ...) | NOT IMPLEMENTED (follow-up) |

**Acceptance (met):** `Agent.run` reaches a real model through the gateway
with no core changes; the default offline suite (mock provider) passes with
no credentials; malformed model output fails as a controlled `PlanningError`.

---

## Phase 2 — Tool Runtime & safe built-in tools ✅ IMPLEMENTED

A provider-independent Tool Runtime around the existing tool abstraction,
plus a small set of deterministic, side-effect-free built-in tools. The
runtime makes it architecturally difficult to bypass permissions and
validation: the agent's only execution path requires an explicit ALLOWED
permission decision and schema-valid input.

| Item | Status |
| --- | --- |
| Tool Runtime: registration, discovery, lookup, controlled execution | IMPLEMENTED |
| Permission enforcement as a hard precondition of execution (backstop) | IMPLEMENTED |
| Input validation (JSON-Schema subset) before execution | IMPLEMENTED |
| Output validation (JSON-Schema subset) before results reach the Agent | IMPLEMENTED |
| Structured results: machine-readable `error_code` + execution `metadata` | IMPLEMENTED |
| Tool lifecycle events (requested/started/completed/failed/denied/invalid) | IMPLEMENTED |
| Built-in tools: calculator, date/time, text utils, JSON utils (LOW, bounded) | IMPLEMENTED |
| Tool spec compatibility metadata (`version`, `deterministic`) | IMPLEMENTED |
| Safety-boundary tests (no shell/subprocess/eval/network in core source) | IMPLEMENTED |
| Side-effecting file tools | IMPLEMENTED in Phase 3 (workspace-scoped); web fetch/search still NOT IMPLEMENTED |
| Approval channel wired to a human (CLI prompt, then UI) | NOT IMPLEMENTED (synchronous callback exists) |
| Output verification beyond "all steps done" | NOT IMPLEMENTED (later phase) |

**Acceptance (met):** tools are permission-gated, schema-validated, bounded,
and deterministic (or declared non-deterministic); the default test suite
runs offline with no external services; forbidden capabilities are verified
absent by tests.

---

## Phase 3 — System & Workspace Tools ✅ IMPLEMENTED

A safe, provider-agnostic filesystem/workspace tool layer. The agent can
work with files and directories, but **only inside an explicitly configured
workspace boundary** (`WORKSPACE_ROOT`). There is **no** unrestricted shell,
subprocess, PowerShell/cmd.exe, or arbitrary Python/DLL execution. See
[SECURITY.md](SECURITY.md) §4 for the full safety model.

| Item | Status |
| --- | --- |
| Workspace boundary (`Workspace.resolve`): resolved-path containment, no absolute/`../`/symlink/junction escape, fail-closed | IMPLEMENTED |
| `list_directory` (LOW) — sorted, capped entries | IMPLEMENTED |
| `read_text_file` (LOW) — explicit encoding, size cap, structured decode errors | IMPLEMENTED |
| `write_text_file` (MEDIUM) — explicit overwrite, size cap, atomic write, no implicit mkdir | IMPLEMENTED |
| `create_directory` (MEDIUM) — nested, idempotent, never the root | IMPLEMENTED |
| `copy_file` (MEDIUM) — explicit overwrite, source size cap, atomic destination | IMPLEMENTED |
| `move_file` (MEDIUM) — explicit overwrite, `os.replace` | IMPLEMENTED |
| `delete_file` (HIGH) — files only, explicit approval, no recursive dir deletion | IMPLEMENTED |
| `file_info` (LOW) — missing path is a structured `exists:false` | IMPLEMENTED |
| `search_files` (LOW) — glob-style (no regex), result cap, no symlink following | IMPLEMENTED |
| Configurable limits (read/write bytes, list/search counts, path length) via env | IMPLEMENTED |
| Structured, stable error codes; no host-path or content leakage in errors/events | IMPLEMENTED |
| Event payload bounding (`bounded_value`) so file content never floods events | IMPLEMENTED |
| Comprehensive tests (normal ops, traversal, symlink escape, denial, limits, integration) | IMPLEMENTED |
| **Not present (intentionally out of scope):** subprocess/shell, arbitrary code execution, any access outside the workspace, recursive directory deletion | NOT IMPLEMENTED (by design) |

**Acceptance (met):** every filesystem action stays inside `WORKSPACE_ROOT`;
escape attempts (absolute, `../`, symlink/junction) are rejected with a
structured error; a denied operation never touches the filesystem; delete is
HIGH + fail-safe approval; the default suite stays offline and deterministic.

---

## Phase 4 — Document processing & knowledge foundation ✅ IMPLEMENTED

A safe, modular layer on top of the Phase 3 workspace boundary: the agent
can **read and understand** common document types. Six formats (TXT,
Markdown, PDF, DOCX, PPTX, XLSX) are parsed — mature libraries isolated
behind a replaceable parser interface — into a normalized, deterministic,
serializable document model, chunked deterministically, and indexed for
**provider-neutral, deterministic lexical retrieval**. All document content
is untrusted **data**, never instructions. See [SECURITY.md](SECURITY.md)
for the security model and [ARCHITECTURE.md](ARCHITECTURE.md) §4 (D15–D17)
for the design decisions.

| Item | Status |
| --- | --- |
| Supported formats: TXT, Markdown, PDF (pypdf), DOCX (python-docx), PPTX (python-pptx), XLSX (openpyxl) | IMPLEMENTED |
| `DocumentParser` interface + registry/factory; core model coupled to no parser library; optional `docs` extra, lazy imports, structured `parser_unavailable` | IMPLEMENTED |
| Normalized model: `Document` / `DocumentSection` / `DocumentChunk` (Pydantic, deterministic ids, serializable) | IMPLEMENTED |
| Stable document error codes (`unsupported_document_type`, `document_not_found`, `document_too_large`, `document_corrupt`, `extraction_failed`, `decode_failed`, `parser_limit_exceeded`, `invalid_document`, `security_violation`, …) | IMPLEMENTED |
| Configurable limits (`DOCUMENT_*`) with fail-safe behavior; every truncation explicitly reported, never silent | IMPLEMENTED |
| Normalization: document order, page/slide/sheet locations, headings, deterministic table rendering, newline/encoding handling, extraction warnings | IMPLEMENTED |
| Deterministic chunking (configurable size + overlap, section-aware, count-capped, metadata-preserving) | IMPLEMENTED |
| `KnowledgeStore` behind the `RetrievalIndex` protocol: add/replace/remove, grounded `search` with deterministic TF/IDF ranking, document filter, bounded results — **lexical only, no embeddings, no external model** | IMPLEMENTED |
| Tools via the Tool Runtime: `inspect_document` (LOW), `extract_document` (LOW), `index_document` (MEDIUM), `search_documents` (LOW) | IMPLEMENTED |
| All document paths through the Phase 3 `Workspace` boundary; content is data — nothing executed, no new subprocess/shell/network capability (static + behavioral tests) | IMPLEMENTED |
| Observability: events carry ids/relative paths/counts/status, never document content; bounded payloads | IMPLEMENTED |
| Vector/semantic retrieval (embeddings) — future, swappable via `RetrievalIndex` | NOT IMPLEMENTED (future) |
| Persistent long-term memory | NOT IMPLEMENTED (future, Phase 5) |
| Document/presentation *generation* (writing new documents) | NOT IMPLEMENTED (deferred; no phase scheduled) |

**Acceptance (met):** all six formats parse to the normalized model from
deterministic fixtures; malformed/corrupt/unsupported/oversized inputs fail
with structured errors (no crashes); limits produce explicitly reported
truncation; chunking and retrieval are deterministic; document content is
never interpreted as instructions and the document layer introduces no
subprocess/shell/network capability; denied `index_document` performs no
mutation; the full Phase 0–3 suite still passes.

**Known limitations (by design or documented):**
- No parser timeout: a pathologically encoded file can make pypdf slow.
  A Python-level timeout would need threads/subprocesses — both forbidden
  here — so input size limits bound the work instead.
- PDF: text layer only — scanned/image-only PDFs extract as empty sections
  (no OCR). `/Title` metadata is best-effort.
- DOCX: main body only (headers/footers/footnotes are separate parts);
  heading detection relies on Word heading styles.
- PPTX: top-level shape text frames only — text inside grouped shapes is
  not recursed into.
- XLSX: cached values only — formulas are deliberately never evaluated
  (safety), so cells without a cached value are empty; images/charts are
  not extracted. Row/column caps per sheet (10,000 × 200) with reported
  truncation.
- Retrieval is lexical (token-based) by design — no semantic matching;
  ranking quality is commensurate.
- The `KnowledgeStore` is in-memory: the index does not survive a process
  restart (a durable backend is a future phase via the `RetrievalIndex`
  protocol).
- Chunk overlap is best-effort: carried tails are trimmed to fit the chunk
  size, so the *effective* overlap can be smaller than configured for
  large units.

---

## Phase 5 — Memory & RAG foundation ✅ IMPLEMENTED

An explicit, permission-gated, **provider-neutral memory layer** plus a
bounded, provenance-preserving **RAG context builder** that combines
memories and Phase 4 document chunks. Memory creation is explicit (never
automatic); all retrieved memory and document content is untrusted **data**,
never instructions. Retrieval in this phase is **lexical** (deterministic,
no embeddings, no external model) behind swappable protocols, so semantic/
vector retrieval and durable storage remain future phases that plug into
the same interfaces. See [SECURITY.md](SECURITY.md) for the security model
and [ARCHITECTURE.md](ARCHITECTURE.md) §4 (D18–D19) for the design
decisions.

| Item | Status |
| --- | --- |
| `Memory` model: deterministic ids, types (short_term/working/long_term/knowledge), provenance (user_explicit/task/agent/document/system + source ref), confidence, timestamps, expiration, soft-delete flag | IMPLEMENTED |
| `MemoryStore` protocol + required `InMemoryMemoryStore` (remember/get/update/forget/list/recall/purge_expired; deterministic ordering; no external DB, no network) | IMPLEMENTED |
| Limits & policy (`MemoryLimits` from `MEMORY_*` settings): allowed types, content chars, metadata bytes, item cap, recall cap, context chars/items, TTLs — enforced at the store layer | IMPLEMENTED |
| Expiration: implicit TTL only for short_term/working; long_term/knowledge never implicitly expire and are never purged (long-term protection) | IMPLEMENTED |
| `forget`: soft deactivation by default (auditable, reversible), hard delete explicit opt-in, HIGH permission, single memory, never recursive | IMPLEMENTED |
| `MemoryRetriever` protocol + `LexicalMemoryRetriever` (deterministic TF/IDF ranking, stable tie-breaks, type filter, active/non-expired scope, bounded) — **lexical only, no embeddings** | IMPLEMENTED |
| Tools via the Tool Runtime: `remember` (MEDIUM), `update_memory` (MEDIUM, identity fields immutable), `forget` (HIGH), `recall` (LOW), `list_memories` (LOW) | IMPLEMENTED |
| `ContextBuilder` (RAG): memories + document chunks → structured, bounded, deterministic `Context`; MEMORY vs DOCUMENT items with full provenance/location; explicit omission reporting; assembly only (no answer generation) | IMPLEMENTED |
| Secret guard: conservative heuristic rejects obvious credential shapes (`secret_like_content`); documented as heuristic, structural guarantees are explicit creation + data-only content | IMPLEMENTED |
| Agent integration: `memory_store` + `context_builder` exposed on `Agent`; default tool set is now 23 tools; no auto-injection of memories into model calls (retrieval is explicit & bounded) | IMPLEMENTED |
| Security: injection in memory/document content never triggers tools, permissions, or approval bypass; no auto-persistence of conversation; no new subprocess/shell/network/DB capability (static + behavioral tests) | IMPLEMENTED |
| Configuration: `MEMORY_MAX_ITEMS`, `MEMORY_MAX_CONTENT_CHARS`, `MEMORY_MAX_METADATA_BYTES`, `MEMORY_MAX_RECALL_RESULTS`, `MEMORY_MAX_CONTEXT_CHARS`, `MEMORY_MAX_CONTEXT_ITEMS`, `MEMORY_SHORT_TERM_TTL_S`, `MEMORY_WORKING_TTL_S` (defaults in `.env.example`) | IMPLEMENTED |
| Vector store + embeddings (via `ModelProvider.embed`) as `MemoryRetriever`/`RetrievalIndex` implementations | NOT IMPLEMENTED (future — the protocols are the seam) |
| Persistent, durable memory store (survives process restarts) as a `MemoryStore` implementation | NOT IMPLEMENTED (future) |

**Acceptance (met):** memory CRUD/list/recall are deterministic (stable
ids, `(created_at, memory_id)` ordering, id tie-breaks) and covered by
tests for creation, retrieval, update, forget (soft/hard), listing, type
filters, provenance, expiration, limits, and ordering; permission tests
prove remember/update/forget require approval and that denial performs no
mutation; security tests prove injection content (memory or document) is
never executed, triggers no tools, and changes no permissions, that
oversized/secret content is rejected atomically, that expired memories are
excluded, that no conversation text is auto-persisted, and that the
memory/RAG layers import only stdlib + pydantic; RAG context tests prove
memory + document combination, provenance preservation (ids, refs,
categories, locations), deterministic ordering, char/item budgets with
explicit omission, and the MEMORY vs DOCUMENT distinction; the full
Phase 0–4 suite still passes (regression).

**Known limitations (by design or documented):**
- Retrieval is lexical (token-based) by design — no semantic matching for
  either documents (Phase 4) or memory (Phase 5); ranking quality is
  commensurate. Embeddings/vector backends are a future phase.
- The `InMemoryMemoryStore` is in-process: memories do not survive a
  process restart (durability is a future `MemoryStore` implementation).
- The secret-content guard is a heuristic (conservative patterns), not a
  guarantee — credentials must never be stored in memory at all.
- Naive datetimes are assumed UTC (documented contract); expiry is
  evaluated against an injectable clock.
- The context builder drops whole items (never truncates mid-item) to fit
  the budget; omitted items are reported but not fetched further (bounded
  retrieval at each layer).

---

## Phase 6 — Safe Windows Computer Agent foundation ✅ IMPLEMENTED

A provider-neutral, opt-in foundation for bounded desktop observation and
explicit UI interaction. It is deliberately **not** unrestricted autonomous
computer control. UI/window contents are untrusted data, all interactions
use the existing fail-safe permission system, and there is no generic
arbitrary-action interface.

| Item | Status |
| --- | --- |
| Provider-neutral `ComputerProvider` protocol and strict bounded models for display, cursor, windows, UI elements, screenshots, intents, verification, and results | IMPLEMENTED |
| Bounded observation tools: `computer_screen_info`, `computer_cursor_position`, `computer_active_window`, `computer_list_windows`, `computer_inspect_ui`, `computer_screenshot` (LOW) | IMPLEMENTED |
| Explicit interaction tools: `computer_move_mouse`, `computer_click`, `computer_double_click`, `computer_focus_window`, `computer_select_ui_element`, `computer_press_key`, `computer_hotkey`, `computer_type_text` (MEDIUM) | IMPLEMENTED |
| Risk classification: observations LOW, every interaction MEDIUM, destructive/external/unknown operations HIGH; existing `PermissionManager`, deny-list, and fail-safe approvals are reused | IMPLEMENTED |
| Lifecycle: observe → validate intent → authorize → act → re-observe → verify; provider completion without a passed postcondition is not success | IMPLEMENTED |
| Deterministic verification, structured results/events, sensitive I/O redaction, ephemeral screenshots, and bounded idempotent retries | IMPLEMENTED |
| `COMPUTER_*` limits for action counts, timeouts, text, screenshot bytes, windows, UI elements, retries, movement duration, and cursor tolerance, all under hard caps | IMPLEMENTED |
| Optional `computer-windows` extra: lazily loaded Windows UI Automation provider; import-safe elsewhere and explicit `unsupported_platform` behavior | IMPLEMENTED |
| Agent integration is opt-in: tools are registered only when an explicit provider is passed to `Agent.create_configured(computer_provider=...)` | IMPLEMENTED |
| Deterministic fake-provider tests cover tools, permission/approval, bounds, verification, redaction, retry/timeouts, settings, and unsupported platforms | IMPLEMENTED |
| Browser/Playwright, vision-LLM, voice, remote desktop, shell/PowerShell, arbitrary code/actions, clipboard, destructive actions, and automatic actions | NOT IMPLEMENTED (out of scope) |

**Acceptance:** deterministic tests use an in-memory fake provider (no Windows
desktop required); the shared permission manager is enforced even for direct
runtime/registry calls; the default configured agent does not register
computer tools; only named tools are exposed; provider errors are sanitized;
observation/action/event payloads stay bounded; non-idempotent input is never
retried; the Windows adapter imports no platform dependency until explicitly
constructed on Windows. Hardware behavior on Windows remains unverified.

**Known limitations:**
- The Windows adapter targets one primary display and pywinauto UI Automation;
  desktop scaling and application-specific accessibility behavior vary.
- Timeouts are cooperative elapsed-time checks around synchronous provider
  calls. A blocked Windows API call cannot be forcibly interrupted by the
  core; the result is marked timed out only after it returns.
- Screenshots are returned only by the explicit screenshot tool, and remain
  sensitive caller output. The core keeps no screenshot history or event
  payload, but callers are responsible for handling returned bytes safely.
- There has been no manual Windows hardware verification in this phase.

Document and presentation *generation* (writing new files) remains deferred
and unscheduled; document *analysis* is implemented in Phase 4.

---

## Phase 7 — Browser automation

| Item | Status |
| --- | --- |
| Browser provider (e.g. Playwright) behind a tool/agent boundary | NOT IMPLEMENTED |
| HIGH-permission + approval for navigations/actions | NOT IMPLEMENTED |
| Screenshots/DOM as tool outputs | NOT IMPLEMENTED |

---

## Phase 8 — Voice

| Item | Status |
| --- | --- |
| Speech-to-text / text-to-speech providers | NOT IMPLEMENTED |
| Voice as an input/output channel for the UI | NOT IMPLEMENTED |

---

## Phase 9 — Extended Computer Workflows (future)

Phase 6 provides only a conservative desktop foundation with named,
bounded operations. Future work, if separately approved, must extend that
surface with explicit tools and retain the same least-privilege, verification,
and privacy guarantees; Phase 9 is not permission to add generic control.

| Item | Status |
| --- | --- |
| Manual Windows compatibility/accessibility validation matrix | PLANNED |
| Additional narrowly scoped, named workflows with risk review and deterministic postconditions | NOT IMPLEMENTED |
| Any destructive or externally consequential computer operation (HIGH + explicit approval) | NOT IMPLEMENTED |
| Persistent, redaction-aware audit trail (Phase 11 task/event persistence) | NOT IMPLEMENTED |
| Browser automation, remote desktop/network control, shell/PowerShell, arbitrary code/actions | NOT IMPLEMENTED (excluded by current safety scope) |

No earlier phase grants shell access or unrestricted OS control. The Phase 6
adapter never launches processes and exposes no generic arbitrary-action tool.

---

## Phase 10 — Media generation

| Item | Status |
| --- | --- |
| Image generation provider | NOT IMPLEMENTED |
| Video generation provider | NOT IMPLEMENTED |
| Outputs under `data/generated` | NOT IMPLEMENTED |

---

## Phase 11 — UI, API, and the Task Manager layer

The user-facing shell and durable task management.

| Item | Status |
| --- | --- |
| Task Manager: persistence, queue, multi-task scheduling | NOT IMPLEMENTED |
| API layer (HTTP/WebSocket) streaming events to clients | NOT IMPLEMENTED |
| User interface (CLI → desktop/web) | NOT IMPLEMENTED |
| Drive `WAITING_FOR_USER` / `PAUSED` / resume (async approvals) | NOT IMPLEMENTED |

---

## Ordering rationale

The core is proven first (Phase 0) so every later capability is a *pluggable
extension* (new tool, new provider, new agent) rather than a rewrite. The
bounded Phase 6 computer foundation follows the exercised permission,
approval, and verification layers; broader browser/computer workflows remain
separate, higher-risk work and are not enabled by this phase.
