# personal-ai-agent

A modular foundation for a **personal, autonomous AI agent**. The end goal
(see [ROADMAP.md](ROADMAP.md)) is an agent that can converse, use tools, act
on a computer/browser, and run multi-step workflows — with permissions,
human approval, and verification.

This repository currently contains **Phase 0: the Agent Core foundation** —
the abstractions and a working end-to-end flow, deliberately *without* real
external integrations (no live model API, no real tools, no browser, no
computer control, no voice).

> **Status: FOUNDATION ONLY.** Everything beyond the core is NOT IMPLEMENTED
> on purpose. See [ROADMAP.md](ROADMAP.md) and [ARCHITECTURE.md](ARCHITECTURE.md).

---

## What is implemented (Phase 0)

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
- **One mock tool** (`demo_tool`) used for the first end-to-end test.

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
│       ├── src/main.py          # demo entry point (mock provider, no API key)
│       └── tests/test_main.py   # smoke test for the entry point
├── packages/
│   └── agent-core/              # the only importable package (src layout)
│       ├── src/agent_core/
│       │   ├── agent.py         # Agent facade (end-to-end orchestration)
│       │   ├── tasks.py         # Task / TaskStep state machines
│       │   ├── planner.py       # Plan, Planner, ModelPlanner
│       │   ├── executor.py      # Executor, Verifier, BasicVerifier
│       │   ├── tools.py         # Tool, ToolSpec, ToolResult, ToolRegistry
│       │   ├── schema.py        # minimal JSON-Schema (subset) validator
│       │   ├── permissions.py   # levels, policy, PermissionManager
│       │   ├── events.py        # EventType, AgentEvent, EventBus
│       │   ├── config.py        # Settings (env-based)
│       │   ├── demo_tools.py    # DemoTool (the one mock tool)
│       │   ├── errors.py        # exception hierarchy
│       │   └── providers/       # base.ModelProvider + mock.MockModelProvider
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
pip install -e packages/agent-core
pip install pytest ruff mypy

# 3. Run the test suite (offline, deterministic — no API keys)
pytest

# 4. Run the end-to-end demo (mock provider, no API keys)
python apps/backend/src/main.py "Run the demo tool."
```

Configuration is environment-based. Copy `.env.example` to `.env` if you want
to override defaults — but **no API keys are needed for Phase 0**.

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

Real model-provider adapters, real tools, computer control, browser
automation, voice, image/video generation, RAG, memory, presentation
generation, and a user interface are all **future phases**. They are NOT in
this foundation. Adding them is explicitly gated in
[ROADMAP.md](ROADMAP.md).
