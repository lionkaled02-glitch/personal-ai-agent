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
│  External Providers / Computer / Browser / Files           │  PARTIAL (see below)
└────────────────────────────────────────────────────────────┘
```

**What "PARTIAL" means on the bottom row:** the *interfaces* for external
providers exist (`ModelProvider`) and a deterministic mock is implemented.
Real computer/browser/file providers are NOT IMPLEMENTED.

The implemented portion is the middle band: **Orchestrator → Planner → Tool
Registry → Permission**, plus the events backbone that runs alongside all of
it.

---

## 2. Implemented components

All implemented code lives in the single package
`packages/agent-core/src/agent_core/`.

| Module | Key types | Responsibility | Status |
| --- | --- | --- | --- |
| `tasks.py` | `Task`, `TaskStep`, `TaskState`, `StepStatus` | Task/step state machines with an enforced transition map. Supports multi-step workflows. | IMPLEMENTED |
| `planner.py` | `Plan`, `PlanStep`, `Planner`, `ModelPlanner` | Turns a request into an ordered list of tool steps via strict-JSON, validated against registered tools. | IMPLEMENTED |
| `executor.py` | `Executor`, `Verifier`, `BasicVerifier` | Runs a plan: permission check → approval → execute → verify → terminal state. Emits events. | IMPLEMENTED |
| `tools.py` | `Tool`, `ToolSpec`, `ToolResult`, `ToolRegistry` | Tool abstraction + registry with controlled execution and JSON-Schema validation. | IMPLEMENTED |
| `schema.py` | `validate_against_schema` | Minimal JSON-Schema (subset) validator: `type`, `properties`, `required`, `items`, `enum`. | IMPLEMENTED |
| `permissions.py` | `PermissionLevel`, `PermissionPolicy`, `PermissionManager`, `ApprovalCallback` | Level-based policy decisions and fail-safe approval routing. | IMPLEMENTED |
| `events.py` | `EventType`, `AgentEvent`, `EventBus` | Structured, in-memory event log + subscribers. Operational data only. | IMPLEMENTED |
| `providers/base.py` | `ModelProvider`, `ModelRequest`, `ModelResponse`, `Capability` | Vendor-neutral model interface. `stream`/`embed` are declared but raise until an adapter implements them. | IMPLEMENTED (interface) / PLANNED (real adapters) |
| `providers/mock.py` | `MockModelProvider` | Deterministic in-memory provider (scripted or keyword mode). No network, no key. | IMPLEMENTED |
| `config.py` | `Settings` | Env-based configuration (`AGENT_NAME`, `LOG_LEVEL`, `DATA_ROOT`). No secrets. | IMPLEMENTED |
| `demo_tools.py` | `DemoTool` | The one mock tool (`demo_tool`, LOW permission) used for the end-to-end test. | IMPLEMENTED |
| `errors.py` | `AgentCoreError` + subclasses | Single exception hierarchy so agent failures are catchable. | IMPLEMENTED |
| `agent.py` | `Agent` | Facade that wires planner + registry + permissions + events + executor into `run(request)`. | IMPLEMENTED |

Entry point: `apps/backend/src/main.py` (demo, mock provider, no API key).

---

## 3. End-to-end flow (IMPLEMENTED)

`Agent.run(request)` executes the following and emits a structured event at
each observable transition:

```
1. TASK_CREATED        Task created (state CREATED), event emitted.
2. → PLANNING          Planner plans via ModelProvider → strict-JSON Plan.
   PLAN_CREATED        Plan steps validated (tool names exist, shapes ok).
3. → RUNNING           Executor starts. For each step:
                         a. permission check (PermissionManager)
                         b. if REQUIRES_APPROVAL → APPROVAL_REQUIRED, ask channel
                            (no channel / denied → task CANCELLED, TOOL not run)
                         c. TOOL_STARTED → registry.execute (schema-validated)
                         d. ok → TOOL_COMPLETED   |  fail → TOOL_FAILED → task FAILED
4. → VERIFYING         Verifier checks the executed task (BasicVerifier: all steps done).
5. → COMPLETED         result set (last step output); or FAILED on verification failure.
   TASK_COMPLETED      (or TASK_FAILED / TASK_CANCELLED on the failure paths)
```

The happy path for the request `"Run the demo tool."` emits exactly:

```
TASK_CREATED → PLAN_CREATED → TOOL_STARTED → TOOL_COMPLETED → TASK_COMPLETED
```

Failure paths (invalid plan, unknown tool, failing tool, denied approval) are
all implemented and tested in `packages/agent-core/tests/test_agent_flow.py`.

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

---

## 5. What is NOT implemented (explicit)

These are **NOT IMPLEMENTED** and must not be added prematurely
(AGENTS.md rule 15). They are tracked in [ROADMAP.md](ROADMAP.md):

- Real model-provider adapters (OpenAI / Anthropic / local models).
- Streaming and embeddings (interface declared; behavior raises).
- Real tools with side effects (files, web, shell, computer, browser).
- Computer control and browser automation.
- Voice I/O.
- Image/video generation, presentation generation, document analysis.
- RAG and persistent memory.
- Task Manager layer (task persistence, queueing, multi-task scheduling).
- User interface and API layer (HTTP/WebSocket).
- `WAITING_FOR_USER`, `PAUSED`, `TASK_PAUSED`, `TASK_RESUMED` are **modeled**
  in the state machine but not yet *driven* by any implemented flow (the
  approval flow is synchronous today).

---

## 6. How new capability plugs in

- **New tool:** implement `spec: ToolSpec` + `run(input) -> ToolResult`,
  register it in a `ToolRegistry`, declare the correct `permission_level`.
  No core changes.
- **New model provider:** subclass `ModelProvider`, implement `complete()`
  (and optionally `stream()`/`embed()`), declare `capabilities`. No core
  changes.
- **New planner/verifier:** satisfy the `Planner` / `Verifier` protocols.
  Swap them into `Agent`.

These extension points are the reason the layering stays modular.
