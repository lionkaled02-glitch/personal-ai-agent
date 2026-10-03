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
| `MEDIUM` | Some side effects, scoped (e.g. file ops inside `DATA_ROOT`) | `REQUIRES_APPROVAL` |
| `HIGH` | Broad or irreversible (computer control, destructive ops) | `REQUIRES_APPROVAL` (stricter by policy) |

Decisions are produced by `PermissionManager` from a data-driven
`PermissionPolicy` (per-level decision + an explicit **deny-list** of tool
names that always wins). The *executor* enforces the decision **before** a
tool is ever run.

### Fail-safe defaults

- If a step is `REQUIRES_APPROVAL` but **no approval channel is configured**,
  the step is **denied** — never silently allowed.
- The deny-list overrides any level policy.
- There is **no tool with shell access today**, and none may be added without
  a HIGH level + approval + an explicit allow/deny policy (Phase 7).

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
- A future persistent audit log (Phase 9) will serialize
  `AgentEvent.to_dict()` — the on-disk format is fixed now so it can be made
  append-only and redaction-aware later.

---

## 4. Trust boundary & current attack surface

**Default path (mock provider):** the agent runs **entirely in-process**
with the deterministic mock provider and one harmless mock tool
(`demo_tool`). It makes **no network calls** and performs **no filesystem
writes** outside the git-ignored `data/` directory (which is itself not
written to yet).

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
  exist, every tool is permission-gated (fail-safe), and no HIGH-permission
  tool is registered today. There is no shell, no browser, no filesystem
  tool.
- **Provider errors are sanitized.** Error messages carry status codes and
  bounded detail only; credentials never appear in them, in logs, or in
  events.
- **Retries are bounded and safe.** Only idempotent completion requests are
  retried, at most `MODEL_MAX_RETRIES` times with capped backoff; the SDK's
  own retry layer is disabled.

**Future surface (NOT IMPLEMENTED, must be handled when built):**
- Real tools need per-tool scoping (e.g. files confined to `DATA_ROOT`).
- Browser / computer control needs sandboxing, command allow/deny policies,
  and mandatory approval (Phases 5 & 7).
- Any UI/API needs authn/authz and input validation (Phase 9).

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
| Controlled tool execution (schema validation, exception containment) | IMPLEMENTED |
| Credentials via environment variables only; `Settings` secret-free; `.env` ignored; `.env.example` placeholders | IMPLEMENTED |
| Missing-credential and unknown-provider failures are clean, no network | IMPLEMENTED |
| Provider error sanitization (no key material, bounded detail) | IMPLEMENTED |
| Bounded, idempotent retry for transient provider failures | IMPLEMENTED |
| Untrusted model output: strict JSON + plan schema + tool allow-list | IMPLEMENTED |
| Operational-only events/logs, bounded payloads | IMPLEMENTED |
| Synchronous human approval channel | PLANNED (wire-up in Phase 2) |
| Persistent, redaction-aware audit log | PLANNED (Phase 9) |
| Sandboxing / command policies for real tools | NOT IMPLEMENTED (Phases 2/5/7) |
| UI/API authentication | NOT IMPLEMENTED (Phase 9) |
