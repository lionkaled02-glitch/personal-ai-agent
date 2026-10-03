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

Everything else (side-effecting tools, browser, computer control, voice,
media, memory/RAG) is deliberately NOT IMPLEMENTED yet.

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
│       │   ├── tool_runtime.py  # ToolRuntime (permission-gated execution)
│       │   ├── errors.py        # exception hierarchy
│       │   └── providers/
│       │       ├── base.py      # ModelProvider ABC + request/response models
│       │       ├── mock.py      # MockModelProvider (offline default)
│       │       ├── gateway.py   # ModelGateway (normalization + safe retry)
│       │       ├── factory.py   # provider selection from Settings/env
│       │       └── openai_provider.py  # OpenAI adapter (optional extra)
│       └── tests/               # deterministic, offline test suite
├── data/                        # runtime data (git-ignored, .gitkeep only)
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

A second real provider adapter (Anthropic, local models), streaming/
embeddings, real tools with side effects, computer control, browser
automation, voice, image/video generation, RAG, memory, presentation
generation, and a user interface are all **future phases**. Adding them is
explicitly gated in [ROADMAP.md](ROADMAP.md).
