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
vector retrieval remains a future phase that plugs into the same interfaces;
durable storage is provided by the SQLite-backed `SQLiteMemoryStore` behind
the unchanged `MemoryStore` protocol. See [SECURITY.md](SECURITY.md) for the security model
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
| Persistent, durable SQLite memory store (survives process restarts) as a `MemoryStore` implementation | IMPLEMENTED — bounded local SQLite persistence |

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
- `InMemoryMemoryStore` remains in-process; durable local persistence is provided
  separately by `SQLiteMemoryStore`, which uses the same `MemoryStore` seam and
  persists memory lifecycle changes across process restarts.
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
| Unrestricted autonomous browser use, CAPTCHA/anti-bot bypass, arbitrary browser actions, semantic vision/OCR, remote vision APIs/cloud upload, real microphone capture/external STT-TTS, remote desktop, shell/PowerShell, arbitrary code/actions, clipboard, and surveillance | NOT IMPLEMENTED (out of scope) |

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

## Phase 7 — Vision & Visual Verification ✅ IMPLEMENTED

A provider-neutral layer over the Phase 6 screenshot path. It analyzes and
compares only fresh, bounded screenshots already acquired by
`ComputerRuntime`; it does not add another capture mechanism or infer
semantic meaning from pixels.

| Item | Status |
| --- | --- |
| Strict `ImageSize`, `BoundingBox`, ephemeral `ImageFrame`, `VisualObservation`, `VisualMatch`, and `VisualVerification*` Pydantic models | IMPLEMENTED |
| Existing Phase 6 `ComputerRuntime.screenshot()` acquisition reused; no screen recording, history, or automatic storage | IMPLEMENTED |
| Offline deterministic provider: metadata-only observation plus bounded exact RGB/pixel comparison; no object recognition or OCR | IMPLEMENTED |
| Optional local `vision-image` extra for Pillow; lazy import and no external vision SDK/API | IMPLEMENTED |
| Explicit `VERIFIED` / `FAILED` / `UNCERTAIN` visual verdicts; stable sanitized error codes and provider-output revalidation | IMPLEMENTED |
| `vision_analyze_screenshot` (LOW, only registered with an explicit computer provider); raw screenshot bytes are never returned by this tool | IMPLEMENTED |
| Optional schema-validated visual conditions on named Phase 6 action tools; uses the same permission manager and before/after action lifecycle | IMPLEMENTED |
| Pixel changes never establish semantic action success by themselves; a non-screenshot Phase 6 postcondition is still required for action success | IMPLEMENTED |
| Uncertainty permits only a bounded screenshot/verification refresh; it never replays the action, and HIGH-risk operations remain non-retryable | IMPLEMENTED |
| `VISION_*` bounds for image bytes/dimensions/pixels, regions, labels, summaries, comparison work, cooperative elapsed-time checks, and refresh retries | IMPLEMENTED |
| Visual events contain operational metadata only; labels and summaries are marked untrusted; screenshot bytes never enter events/results/history | IMPLEMENTED |
| Platform-independent synthetic PNG tests, permission/recovery integration tests, and static dependency-boundary tests | IMPLEMENTED |
| Semantic vision models, OCR (including credential discovery), remote APIs/cloud upload, persistent screenshot storage, and surveillance | NOT IMPLEMENTED (out of scope) |

**Acceptance (met):** screenshot acquisition remains in Phase 6; the default
provider is offline and deterministic; malformed or over-limit images fail
closed; comparisons are pixel evidence only; uncertainty is never success;
a visual condition without a separate deterministic action postcondition
cannot mark a computer action successful; uncertainty refreshes are bounded
and do not repeat mouse/keyboard input; no screenshot bytes enter events or
persistent models.

---

## Phase 8 — Voice Agent Foundation ✅ IMPLEMENTED

Voice is a transport over the existing agent loop, not a second planner,
executor, or permission path. The phase is a provider-neutral foundation
only: no real microphone hardware, external STT/TTS provider, API key,
network upload, or persistent audio storage is included.

| Item | Status |
| --- | --- |
| Strict bounded PCM format, audio metadata, ephemeral input/output buffers, transcription/synthesis, observation, and response models | IMPLEMENTED |
| Provider-neutral `STTProvider` / `TTSProvider` protocols plus deterministic local mocks | IMPLEMENTED |
| Deterministic Unicode NFC and whitespace normalization; punctuation retained; empty/oversized/invalid text rejected | IMPLEMENTED |
| One canonical `Agent.run(..., input_channel="voice")` handoff; existing intent/planning/permission/execution/verification remains authoritative | IMPLEMENTED |
| Explicit `CONFIDENT` / `UNCERTAIN` transcription state; uncertain output does not reach Agent or TTS | IMPLEMENTED |
| Safe audio/text/language/voice/duration/time/retry limits from `VOICE_*` configuration | IMPLEMENTED |
| Cooperative provider timeouts, bounded retry only for explicitly retryable provider failures, no command replay | IMPLEMENTED |
| Metadata-only voice events; input and synthesized payloads excluded from repr/serialization/events | IMPLEMENTED |
| Optional LOW-permission `voice_normalize` text-only tool with sensitive event redaction | IMPLEMENTED |
| No network, credentials, persistent microphone recording, or optional audio/ML dependency required | IMPLEMENTED |
| Real microphone capture, Windows audio hardware, external/cloud STT/TTS adapters | NOT IMPLEMENTED (future phase) |

**Acceptance (met):** valid bounded PCM metadata is validated; malformed,
oversized, and over-duration data fails deterministically; normalization is
local and content-preserving beyond canonical Unicode/whitespace; uncertain
provider results never become success; the existing Agent loop is called once
and its HIGH/MEDIUM permissions and approvals are unchanged. Provider errors
are sanitized, retries are finite, events carry metadata only, and audio
buffers are never persisted or uploaded.

---

## Phase 9 — Browser Agent Foundation ✅ IMPLEMENTED

A deliberately bounded browser surface—not an unrestricted autonomous web
agent. Browser tools are opt-in, provider-neutral, and use the existing Tool
Runtime, permission manager, event bus, structured errors, and confirmation
callback. Tests use an in-memory mock and do not require the internet,
Playwright, browser binaries, or a GUI.

| Item | Status |
| --- | --- |
| Required `browser/` package modules: models, limits, provider interface, runtime, serialization, verification, recovery, mock, and explicit tools | IMPLEMENTED |
| Optional `PlaywrightBrowserProvider`, lazily imports the optional extra only at launch; no binary install in core/CI | IMPLEMENTED |
| Strict bounded models; HTTP(S)-only URL validation; reject malformed URLs, userinfo, unsupported schemes, and filesystem paths | IMPLEMENTED |
| Explicit isolated sessions/pages; every operation supplies IDs; no implicit active-tab selection or persistent profile | IMPLEMENTED |
| Fixed observation, element lookup/wait, navigation/history, click, fill, select, and key operations; no generic action/script tool | IMPLEMENTED |
| LOW read/observe/wait operations; ordinary navigation and interactions MEDIUM; externally consequential controls and Enter require HIGH confirmation | IMPLEMENTED |
| Observe → permission/confirmation → action → fresh observe → verify → bounded safe recovery | IMPLEMENTED |
| Explicit `VERIFIED` / `FAILED` / `UNCERTAIN`; uncertain/failed actions never become successful browser Tool Runtime steps | IMPLEMENTED |
| Bounded page text/elements/attributes/timeouts/screenshots/retries; event payloads omit page contents, form values, raw HTML, and screenshot bytes | IMPLEMENTED |
| Sensitive-form detection/redaction; filling/selecting sensitive controls is blocked; no automatic high-risk retries | IMPLEMENTED |
| Offline tests: URL security, limits, permissions, confirmation, navigation/element/form behavior, redaction, prompt-injection data, verification/recovery, serialization, boundaries, Tool Runtime/Agent integration | IMPLEMENTED |
| Root/package READMEs, architecture, security, roadmap, BROWSER_* configuration documentation, and `.env.example` | IMPLEMENTED |
| Host/domain allowlist, DNS-rebinding/SSRF protection, authenticated profile reuse, CAPTCHA/anti-bot bypass, unrestricted autonomous browsing | NOT IMPLEMENTED (explicit limitation/out of scope) |

**Acceptance:** deterministic mock tests prove that unsafe schemes/paths are
rejected; page text remains marked untrusted and cannot authorize or trigger a
privileged operation; sensitive values do not enter events; approval/denial
uses the existing policy; high-risk operations are not replayed; action
uncertainty is never success; all outputs/retries are bounded; browser tools
run through the existing Tool Runtime and Agent orchestration. Ordinary
installation and CI do not import Playwright or require browser binaries.

**Known limitations:**
- URL validation checks bounded HTTP(S) syntax, host syntax, and credentials;
  it is not a domain allowlist or SSRF/DNS-rebinding defense. Deployments that
  require private-network isolation must provide network-level egress rules.
- Sensitive-content redaction is heuristic. Sensitive form controls are
  blocked and values are not read, but visible page text/title content can
  still contain secrets that heuristic redaction cannot recognize. Do not
  browse pages containing secrets unless the deployment accepts that risk.
- Playwright calls are synchronous; configured library timeouts are used, but
  a blocked launch/provider call cannot be forcibly interrupted by the core.
  The optional Python extra does not install Chromium; manual Playwright
  hardware/browser smoke testing is not part of offline CI.
- No user-facing approval UI is included. The existing callback must be wired
  by the application, and absent/denied approval fails closed.
- No CAPTCHA/anti-bot handling, credential collection, authenticated-profile
  persistence, download handling, raw HTML access, arbitrary JavaScript,
  shell/process/filesystem access, or unrestricted browsing is provided.

---

## Phase 10 — Coding Agent Foundation (Steps 1–3) ✅ IMPLEMENTED

Step 1 establishes bounded provider-neutral contracts; Step 2 adds a local,
read-only analyzer; Step 3 adds deterministic diagnostics for Python,
JavaScript, and TypeScript snapshots. Code and repository text are untrusted
data, paths use the existing `Workspace` containment/symlink boundary, and the
mock, analyzer, and diagnostics engine make no network requests.

| Item | Status |
| --- | --- |
| `coding/` project/file/region, analysis/edit, structural patch, test-plan, and observation models | IMPLEMENTED |
| `CodingProvider`, hard-clamped `CodingLimits`, safe errors, and deterministic mock | IMPLEMENTED |
| Workspace-backed path resolution, project containment, original-hash patch preconditions | IMPLEMENTED |
| `CODING_*` environment configuration and bounded output/result validation | IMPLEMENTED |
| Read-only `CodingAnalysisRuntime`; bounded discovery, UTF-8 snapshots, Python AST, shallow JS/TS scan, metadata-only formats | IMPLEMENTED |
| Explicit analyzed/skipped file metadata, truncation reasons, and file/entry/output bounds | IMPLEMENTED |
| `CodeDiagnosticsEngine`; bounded Python syntax, JavaScript/TypeScript delimiter, and shared style diagnostics | IMPLEMENTED |
| Coding analysis tools and source observation | IMPLEMENTED — bounded, workspace-scoped |
| Source patch application | IMPLEMENTED — separate MEDIUM permission-gated, hash/size-checked, all-or-nothing preflight |
| Test/build execution | NOT IMPLEMENTED — deliberately excluded from host runtime |
| Shell/process/command use, arbitrary execution, compilers, package installation, real model providers | NOT IMPLEMENTED (explicitly excluded) |

**Acceptance:** proposed replacements remain structured data and are checked
against the supplied source hash/size; the mock never accesses or modifies
workspace paths; analysis reads only validated project files and reports
bounded symbols, categorized diagnostics, skipped files, and truncation;
diagnostics include severity, stable code, path, and a source region when
available; test plans cannot report execution; configured input, diagnostic,
region, and output limits remain enforced. No phase grants command or
arbitrary-code access.

**Known limitation:** analysis uses cooperative wall-clock checks around
synchronous reads/parsers; a single bounded operation cannot be forcibly
interrupted. JavaScript/TypeScript diagnostics use a shallow lexical scan, not
full language parsers or compilers; regex literals and template interpolation
are not fully parsed. The runtime never writes files, applies patches, launches
commands, installs packages, executes builds/tests, or connects a real model.
Any future write path must be a separate operation, use the existing
permission system, and revalidate the patch against the live workspace.

---

## Future — Extended Computer Workflows (phase unassigned)

Phase 6 and Phase 7 provide a conservative desktop foundation and pixel-level
verification only. Any future extension requires separate approval, explicit
named tools, least privilege, semantic postconditions, and privacy review; it
is not permission to add generic control.

| Item | Status |
| --- | --- |
| Manual Windows compatibility/accessibility validation matrix | PLANNED |
| Additional narrowly scoped, named workflows with risk review and deterministic postconditions | NOT IMPLEMENTED |
| Any destructive or externally consequential computer operation (HIGH + explicit approval) | NOT IMPLEMENTED |
| Persistent, redaction-aware task/event trail (Phase 12) | IMPLEMENTED — bounded operational event persistence |
| Remote desktop/network control, shell/PowerShell, arbitrary code/actions | NOT IMPLEMENTED (excluded by current safety scope) |

The Phase 6 adapter never launches processes and exposes no generic arbitrary-action tool.

---

## Phase 11 — Media generation

Media generation is intentionally provider-neutral. Generated artifacts are
stored under the configured data boundary and are never treated as trusted
instructions.

| Item | Status |
| --- | --- |
| Image generation provider | IMPLEMENTED — provider protocol, bounded request/result models, deterministic mock, and artifact writer |
| Video generation provider | IMPLEMENTED — provider protocol, bounded request/result models, deterministic mock, and artifact writer |
| Outputs under `data/generated` | IMPLEMENTED |
| Credential/network access | OPTIONAL and disabled by default; no secret is stored in task history |

---

## Phase 12 — UI, API, and the Task Manager layer

The user-facing shell and durable task management.

| Item | Status |
| --- | --- |
| Durable SQLite task/event persistence and bounded task listing | IMPLEMENTED |
| Background task queue with stable task IDs | IMPLEMENTED |
| FastAPI HTTP task API and WebSocket event streaming | IMPLEMENTED |
| Backend smoke tests and repository CI quality gates | IMPLEMENTED |
| User interface (bundled web UI) | IMPLEMENTED — static task submission, task state/events, and approval controls |
| Drive `WAITING_FOR_USER` / `PAUSED` / resume (async approvals) | IMPLEMENTED — durable approval records, HTTP approve/deny endpoints, bounded waiter, state transitions, and wake-up are wired |

**Known limitations:**

- Approvals wait for a human decision for a bounded time (default 300s,
  `APPROVAL_WAIT_TIMEOUT_S` in `apps/backend/src/api.py`). On timeout the
  record is marked `EXPIRED`, the step fails closed, and the task ends in a
  terminal state; an expired approval can no longer be decided.
- `PAUSED` remains modeled in the task state machine but is not driven by
  any current flow; only `WAITING_FOR_USER` is exercised end-to-end.
- The bundled UI is a deliberately minimal static console (no build step);
  it is not a full-featured client. Event history is bounded per request.
- Background execution uses a bounded in-process thread pool, not a
  distributed queue; task state and events are durable (SQLite) but a task
  lost mid-process is not automatically resumed after a restart.

---

## Ordering rationale

The core is proven first (Phase 0) so every later capability is a *pluggable
extension* (new tool, new provider, new agent) rather than a rewrite. The
bounded Phase 6 computer foundation follows the exercised permission, approval,
and verification layers; Phase 7 reuses its ephemeral screenshot path for
local pixel-level observation. Semantic vision and broader browser/computer
workflows remain separate and are not enabled by this phase.
