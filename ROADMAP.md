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

## Phase 4 — Memory & RAG

Persistent memory and retrieval over documents. (Originally the planned
Phase 3; rescheduled after the workspace tools phase.)

| Item | Status |
| --- | --- |
| Document ingestion + chunking | NOT IMPLEMENTED |
| Vector store + embeddings (via `ModelProvider.embed`) | NOT IMPLEMENTED |
| Retrieval tool + long/short-term memory | NOT IMPLEMENTED |

---

## Phase 5 — Document & presentation generation

| Item | Status |
| --- | --- |
| Document analysis (PDF/DOCX/…) | NOT IMPLEMENTED |
| Presentation generation (slides) | NOT IMPLEMENTED |
| Output written under `data/generated` | NOT IMPLEMENTED |

---

## Phase 5 — Browser automation

| Item | Status |
| --- | --- |
| Browser provider (e.g. Playwright) behind a tool/agent boundary | NOT IMPLEMENTED |
| HIGH-permission + approval for navigations/actions | NOT IMPLEMENTED |
| Screenshots/DOM as tool outputs | NOT IMPLEMENTED |

---

## Phase 7 — Voice

| Item | Status |
| --- | --- |
| Speech-to-text / text-to-speech providers | NOT IMPLEMENTED |
| Voice as an input/output channel for the UI | NOT IMPLEMENTED |

---

## Phase 7 — Computer control

| Item | Status |
| --- | --- |
| Desktop/OS control behind HIGH permission + mandatory approval | NOT IMPLEMENTED |
| Allow/deny command policies, sandboxing | NOT IMPLEMENTED |
| Full audit trail of actions | NOT IMPLEMENTED |

> Computer control is explicitly the **last** capability to add. Nothing in
> earlier phases grants shell access.

---

## Phase 9 — Media generation

| Item | Status |
| --- | --- |
| Image generation provider | NOT IMPLEMENTED |
| Video generation provider | NOT IMPLEMENTED |
| Outputs under `data/generated` | NOT IMPLEMENTED |

---

## Phase 10 — UI, API, and the Task Manager layer

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
extension* (new tool, new provider, new agent) rather than a rewrite. Risky,
high-privilege capabilities (browser, computer control) come late, after the
permission/approval/verification foundation is exercised by real tools.
