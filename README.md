# personal-ai-agent

A modular foundation for a **personal, autonomous AI agent**. The end goal
(see [ROADMAP.md](ROADMAP.md)) is an agent that can converse, use tools, act
on a computer/browser, and run multi-step workflows — with permissions,
human approval, and verification.

This repository currently contains:

- **Phase 0: the Agent Core foundation** — the abstractions and a working
  end-to-end flow.
- **Phase 1: the Model Gateway & a real provider** — provider selection,
  error normalization, safe retries/timeouts, and an OpenAI adapter. The
  default remains the fully offline mock provider.
- **Phase 2: the Tool Runtime & safe built-in tools** — a permission-gated,
  schema-validated, metadata-carrying tool execution layer plus deterministic
  built-in tools (calculator, date/time, text utils, JSON utils).
- **Phase 3: system & workspace tools** — nine filesystem tools
  (list/read/write/create-dir/copy/move/delete/file-info/search) that work
  **only inside an explicitly configured workspace boundary**
  (`WORKSPACE_ROOT`). No shell, subprocess, or arbitrary code execution.
- **Phase 4: document processing & knowledge foundation** — parses TXT,
  Markdown, PDF, DOCX, PPTX, and XLSX (mature libraries behind a replaceable
  parser interface) into a normalized, deterministic document model;
  deterministic bounded chunking; provider-neutral **lexical** retrieval in
  an in-memory knowledge store; four permission-gated tools
  (`inspect_document`, `extract_document`, `index_document`,
  `search_documents`) that read **only** through the Phase 3 workspace
  boundary. Document content is untrusted data, never instructions.
- **Phase 5: memory & RAG foundation** — a strongly typed,
  provider-neutral **memory model** (types, provenance, TTL, soft-delete)
  behind the `MemoryStore` protocol (`InMemoryMemoryStore`), five
  permission-gated memory tools (`remember` MEDIUM, `update_memory` MEDIUM,
  `forget` HIGH, `recall` LOW, `list_memories` LOW), deterministic **lexical**
  memory retrieval behind the `MemoryRetriever` protocol, and a
  provider-neutral **RAG context builder** that combines retrieved memories +
  document chunks into a structured, bounded, provenance-labeled context.
  Memory creation is explicit (never automatic); memory and document content
  is untrusted data, never instructions. Retrieval is lexical only — no
  embeddings in this phase.

Everything else (tools beyond the workspace boundary, web access, browser,
computer control, voice, media, document/presentation generation, durable
(persisted) memory, vector/semantic retrieval, and a user interface) is
deliberately NOT IMPLEMENTED yet.

> See [ROADMAP.md](ROADMAP.md) and [ARCHITECTURE.md](ARCHITECTURE.md) for
> exactly what exists and what does not.

---

## What is implemented

A single Python package, `agent-core`, that proves the architecture works:

- **Task state model** — 9 states (`CREATED … COMPLETED/FAILED/CANCELLED`)
  with an explicit, enforced transition map.
- **Planner** — turns a request into a strict-JSON plan of tool steps, driven
  through a vendor-neutral `ModelProvider` interface.
- **Executor** — runs a plan step-by-step: permission check → approval →
  tool execution → verification → terminal state.
- **Tool system** — `Tool` abstraction with a declarative `ToolSpec`
  (name, description, JSON-Schema input/output, permission level) and a
  `ToolRegistry` with controlled execution and schema validation.
- **Permission system** — `LOW/MEDIUM/HIGH` levels, policy-driven decisions,
  and a **fail-safe** approval flow (no approval channel ⇒ denied).
- **Event system** — a structured, in-memory `EventBus` emitting concise
  operational events (`TASK_CREATED`, `PLAN_CREATED`, `TOOL_STARTED`, …).
  No chain-of-thought is ever placed in events.
- **Model provider abstraction** — `ModelProvider` ABC + a deterministic
  `MockModelProvider` used by tests and the demo. No API key required.
- **Model Gateway (Phase 1)** — `ModelGateway` decorator that normalizes
  provider errors and retries transient failures (timeout/5xx/429/connection)
  with bounded backoff, plus a configuration-driven provider factory.
- **Real provider (Phase 1)** — `OpenAIProvider` (Chat Completions) behind
  the same interface; optional `openai` extra, lazy SDK import, env-based
  credentials, configurable timeout, sanitized errors, OpenAI-compatible
  `OPENAI_BASE_URL` support.
- **Structured planning (Phase 1)** — explicit JSON contract in the model
  request + strict validation of model output (invalid model output fails as
  a controlled `PlanningError`, never an invalid plan).
- **Tool Runtime (Phase 2)** — the agent's only tool-execution path. It
  requires an explicit ALLOWED permission decision, validates input *and*
  output against the tool's JSON-Schema, contains tool exceptions into
  structured `ToolResult`s (machine-readable `error_code`), attaches
  execution metadata (tool version, determinism, duration), and emits the
  tool lifecycle events. Provider-independent.
- **Safe built-in tools (Phase 2)** — `calculator` (hand-written parser, no
  `eval`), `datetime` (IANA timezones, declared non-deterministic),
  `text_utils`, `json_utils`. All LOW-permission, bounded, side-effect-free.
- **Workspace filesystem tools (Phase 3)** — `list_directory`,
  `read_text_file`, `write_text_file`, `create_directory`, `copy_file`,
  `move_file`, `delete_file`, `file_info`, `search_files`. All paths resolve
  against the configured workspace root; absolute paths, `../` traversal,
  and symlink/junction escapes are rejected; sizes and result counts are
  bounded; writes are atomic; `delete_file` is HIGH-permission and requires
  explicit approval. See SECURITY.md for the safety model.
- **Document processing & knowledge foundation (Phase 4)** — a
  `DocumentParser` interface + registry with built-in parsers for TXT,
  Markdown, PDF (pypdf), DOCX (python-docx), PPTX (python-pptx), and XLSX
  (openpyxl); binary parsers use optional libraries imported lazily (missing
  library ⇒ structured `parser_unavailable`, never a crash). Parsers produce
  a normalized, deterministic, serializable model (`Document` /
  `DocumentSection` / `DocumentChunk`) with page/slide/sheet locations,
  headings, and deterministic table rendering. All extraction is bounded
  (input bytes, extracted chars, pages/slides/sheets, sections, chunks) and
  every cap is **explicitly reported** — truncation is never silent.
  Chunking is deterministic (configurable size + overlap, section-aware,
  count-capped). Retrieval is a provider-neutral, deterministic **lexical**
  `KnowledgeStore` (token-based TF/IDF ranking, no embeddings, no external
  model) behind the `RetrievalIndex` protocol, so a future vector store can
  be swapped in without rewriting the model or the tools. Four tools are
  permission-gated through the Tool Runtime: `inspect_document` (LOW,
  metadata only), `extract_document` (LOW, normalized text + structure),
  `index_document` (MEDIUM — internal knowledge mutation),
  `search_documents` (LOW, grounded, bounded results). All document I/O goes
  through the Phase 3 `Workspace` boundary, and document content is treated
  as untrusted data — it is never executed or interpreted as instructions.
  See SECURITY.md for the full security model.
- **Memory & RAG foundation (Phase 5)** — a strongly typed,
  provider-neutral `Memory` model (Pydantic): stable deterministic ids
  (`mem-…`), lifecycle types (`short_term`/`working`/`long_term`/
  `knowledge`), provenance (`user_explicit`/`task`/`agent`/`document`/
  `system` + optional source ref), confidence, timestamps, optional
  expiration, and a soft-delete `active` flag. Storage is behind the
  `MemoryStore` protocol with the required `InMemoryMemoryStore`
  (no external database, no network): limits and policy are enforced at the
  store layer (allowed types, content length, metadata size, item cap,
  conservative secret heuristic), ordering is deterministic
  (`created_at`, then id), and `forget` is a soft deactivation by default
  (hard delete is an explicit opt-in; a forget never touches other
  memories). Expiration: `short_term`/`working` get an implicit TTL from
  configuration; `long_term`/`knowledge` never expire implicitly and are
  never purged (long-term protection). Creation is explicit — permission-
  gated tools or a clearly defined trusted internal pathway; nothing ever
  auto-persists conversation text. Retrieval is a provider-neutral,
  deterministic **lexical** `MemoryRetriever` (token-based TF/IDF ranking,
  stable tie-breaks; no embeddings, no external model) over the store, so a
  future semantic provider plugs in without touching tools or the context
  builder. Five permission-gated tools: `remember` (MEDIUM — explicit
  creation, validated + bounded), `recall` (LOW — lexical, type filter,
  bounded, provenance + stable ids), `update_memory` (MEDIUM — mutable
  fields only; identity fields are immutable and rejected), `forget`
  (HIGH — approval required; soft deactivation by default, hard delete
  opt-in, single memory only), `list_memories` (LOW — filters, bounded,
  public fields only). The `ContextBuilder` (RAG) combines retrieved
  memories and document chunks into a structured, bounded `Context`:
  memories first (recall order), then document chunks (search order);
  every item carries kind (`memory` vs `document`), source id, source ref,
  provenance category, and location (page/slide/sheet for documents);
  the char/item budget is enforced with **explicit** omission reporting
  (never silent); it assembles data only — it never generates answers and
  never interprets retrieved content. Configuration: `MEMORY_MAX_ITEMS`,
  `MEMORY_MAX_CONTENT_CHARS`, `MEMORY_MAX_METADATA_BYTES`,
  `MEMORY_MAX_RECALL_RESULTS`, `MEMORY_MAX_CONTEXT_CHARS`,
  `MEMORY_MAX_CONTEXT_ITEMS`, `MEMORY_SHORT_TERM_TTL_S`,
  `MEMORY_WORKING_TTL_S`. See SECURITY.md for the trust model and
  ARCHITECTURE.md (D18/D19) for the design decisions.
- **One mock tool** (`demo_tool`) used for the end-to-end tests.

The **first end-to-end flow** is implemented and tested:

```
User Request → Agent → Planner → Tool Registry → Mock Tool → Result → Task Completed
```

---

## Repository layout

```
.
├── apps/
│   └── backend/
│       ├── src/main.py          # demo entry point (provider via MODEL_PROVIDER)
│       └── tests/test_main.py   # smoke test for the entry point
├── packages/
│   └── agent-core/              # the only importable package (src layout)
│       ├── src/agent_core/
│       │   ├── agent.py         # Agent facade (end-to-end orchestration)
│       │   ├── tasks.py         # Task / TaskStep state machines
│       │   ├── planner.py       # Plan, Planner, ModelPlanner, plan contract
│       │   ├── executor.py      # Executor, Verifier, BasicVerifier
│       │   ├── tools.py         # Tool, ToolSpec, ToolResult, ToolRegistry
│       │   ├── schema.py        # minimal JSON-Schema (subset) validator
│       │   ├── permissions.py   # levels, policy, PermissionManager
│       │   ├── events.py        # EventType, AgentEvent, EventBus
│       │   ├── config.py        # Settings (env-based, no secrets)
│       │   ├── demo_tools.py    # DemoTool (the demo tool)
│       │   ├── builtin_tools/   # safe built-in tools (calc, datetime, text, json)
│       │   ├── workspace.py     # workspace boundary + fail-closed path resolution
│       │   ├── workspace_tools/ # nine scoped filesystem tools (Phase 3)
│       │   ├── documents/       # normalized model, parser registry, chunking,
│       │   │                    #   retrieval (Phase 4)
│       │   ├── document_tools/  # inspect/extract/index/search tools (Phase 4)
│       │   ├── memory/          # Memory model, MemoryStore, lexical retrieval,
│       │   │                    #   limits, secret guard (Phase 5)
│       │   ├── memory_tools/    # remember/recall/update/forget/list tools (Phase 5)
│       │   ├── rag/             # ContextBuilder: bounded memory+document context
│       │   ├── tool_runtime.py  # ToolRuntime (permission-gated execution)
│       │   ├── errors.py        # exception hierarchy
│       │   └── providers/
│       │       ├── base.py      # ModelProvider ABC + request/response models
│       │       ├── mock.py      # MockModelProvider (offline default)
│       │       ├── gateway.py   # ModelGateway (normalization + safe retry)
│       │       ├── factory.py   # provider selection from Settings/env
│       │       └── openai_provider.py  # OpenAI adapter (optional extra)
│       └── tests/               # deterministic, offline test suite
├── data/                        # runtime data (git-ignored)
│   └── workspace/               # default workspace root for the file tools
├── .env.example                 # placeholder config (no secrets)
├── AGENTS.md                    # engineering rules
├── ARCHITECTURE.md              # the real, current architecture
├── ROADMAP.md                   # phased plan (IMPLEMENTED/PLANNED/NOT IMPLEMENTED)
├── SECURITY.md                  # permissions, secrets, trust model
└── CONTRIBUTING.md              # how to contribute
```

---

## Quickstart

Python **3.11+** is required.

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Install the core (editable) plus dev tools
#    (add [openai] only if you will use a real OpenAI model)
pip install -e packages/agent-core
pip install pytest ruff mypy

# 3. Run the test suite (offline, deterministic — no API keys needed)
pytest

# 4. Run the end-to-end demo (mock provider by default, no API keys)
python apps/backend/src/main.py "Run the demo tool."
```

### Using a real model (optional)

```bash
pip install -e "packages/agent-core[openai]"   # optional vendor extra

export MODEL_PROVIDER=openai
export OPENAI_API_KEY="sk-..."                 # from your shell / .env — never commit it
# optional: export MODEL_NAME=gpt-4o-mini
# optional: export OPENAI_BASE_URL=...         # OpenAI-compatible endpoints

python apps/backend/src/main.py "Run the demo tool."
```

Configuration is environment-based (see `.env.example`): provider selection
(`MODEL_PROVIDER`), model name (`MODEL_NAME`), timeout (`MODEL_TIMEOUT_S`),
and retry count (`MODEL_MAX_RETRIES`). Copy `.env.example` to `.env` to
override defaults. **The default (`mock`) needs no API key and no network.**

---

## Quality gates

Before a change is complete, all of these must pass (see
[CONTRIBUTING.md](CONTRIBUTING.md)):

```bash
ruff format .     # formatting
ruff check .      # linting
mypy              # type checking (strict)
pytest            # full test suite
```

---

## Documentation

- [AGENTS.md](AGENTS.md) — project-wide engineering rules (read this first).
- [ARCHITECTURE.md](ARCHITECTURE.md) — the layering and what is/ isn't built.
- [ROADMAP.md](ROADMAP.md) — the incremental phase plan.
- [SECURITY.md](SECURITY.md) — permissions, secrets, and the trust model.
- [CONTRIBUTING.md](CONTRIBUTING.md) — setup, workflow, and conventions.

---

## Not implemented yet (by design)

A second real provider adapter (Anthropic, local models), streaming,
semantic/vector retrieval (the Phase 4 document and Phase 5 memory
retrieval are lexical by design and swappable via the `RetrievalIndex` and
`MemoryRetriever` protocols), durable (persisted) memory beyond the
process lifetime, tools that leave the workspace boundary (web fetch/search,
shell/command execution), computer control, browser automation, voice,
image/video generation, presentation/document generation, and a user
interface are all **future phases**. Adding them is explicitly gated in
[ROADMAP.md](ROADMAP.md).
