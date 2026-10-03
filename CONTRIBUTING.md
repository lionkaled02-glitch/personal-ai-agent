# CONTRIBUTING

Thanks for helping build the personal AI agent. This is a deliberately
**incremental** project: small, well-tested, modular changes on top of the
existing foundation. Read [AGENTS.md](AGENTS.md) (engineering rules) and
[ARCHITECTURE.md](ARCHITECTURE.md) before writing code.

---

## Setup

Python **3.11+**.

```bash
git clone <repo>
cd personal-ai-agent

python3 -m venv .venv
source .venv/bin/activate

pip install -e packages/agent-core   # the core library (editable)
pip install pytest ruff mypy          # dev tools

# only if you will develop/test against a real OpenAI model:
pip install -e "packages/agent-core[openai]"
```

Configuration is environment-based. If you want to override defaults, copy
`.env.example` to `.env` (which is git-ignored). **The default (mock) needs
no API keys.** Real-provider settings: `MODEL_PROVIDER`, `MODEL_NAME`,
`MODEL_TIMEOUT_S`, `MODEL_MAX_RETRIES`, and `OPENAI_API_KEY` (env only,
never committed).

---

## Run the quality gates

All four must pass before a change is considered complete:

```bash
ruff format .     # format
ruff check .      # lint
mypy              # type-check (strict)
pytest            # tests (offline, deterministic)
```

Run the end-to-end demo to sanity-check behavior:

```bash
python apps/backend/src/main.py "Run the demo tool."
```

---

## Testing conventions

- **Deterministic and offline.** Tests must not require real external AI APIs
  or network access. Use `MockModelProvider` and the injectable clock
  (see `packages/agent-core/tests/conftest.py`).
- **Test important behavior:** state transitions, permission decisions, tool
  validation, the planner, and the end-to-end flow are all covered. If you add
  behavior, add a test.
- Place core tests in `packages/agent-core/tests/` and app-level tests in
  `apps/backend/tests/`.

---

## Adding a tool

The Tool Runtime (Phase 2) handles permission gating, input/output
validation, metadata, and events — a well-behaved tool is just a spec plus a
pure `run`.

1. Create a class with a `spec: ToolSpec` and a `run(input) -> ToolResult`
   method (see `demo_tools.py` and `builtin_tools/` for patterns).
2. Fill in the **full** spec: `name`, `description`, `input_schema`,
   `output_schema`, `permission_level`, `version`, and `deterministic`
   (declare `False` if the tool reads the clock or any external state).
3. Declare the correct `permission_level` (`LOW` / `MEDIUM` / `HIGH`) —
   see [SECURITY.md](SECURITY.md).
4. **Validate & bound input yourself too.** The runtime checks the input
   against `input_schema`, but also enforce sensible bounds (e.g. max
   lengths) and return a *structured* failure — `ToolResult(ok=False,
   error=..., error_code="...")` — rather than raising. Never `eval`/`exec`,
   never call `subprocess`, never touch the filesystem/network unless that is
   the tool's explicit, permissioned purpose.
5. **Return output that matches `output_schema`.** A mismatch is a structured
   `TOOL_OUTPUT_INVALID` failure, not a value handed to the Agent.
6. Register it in a `ToolRegistry` (or extend `register_default_tools` for a
   built-in).
7. Add tests: registration, valid input, invalid input, permission path,
   and the failure/`error_code` behavior.
8. No core changes should be needed. If they are, stop and reconsider —
   that's a smell.

Do **not** add tools with shell access, unrestricted filesystem or network
access, or broad side effects before the relevant roadmap phase.

### Adding a workspace tool (Phase 3)

Workspace filesystem tools follow the same spec+`run` contract, plus
workspace-specific rules:

1. **Construct the tool with the `Workspace`** it operates on (see
   `workspace_tools/`) — never with a raw path and never without one.
2. **Resolve every path through `Workspace.resolve`** (or the `require_file`
   / `require_directory` / `require_source` helpers in
   `workspace_tools/_common.py`). Never build host paths yourself, and never
   rely on string-prefix checks for containment.
3. **Never coerce input.** Use `require_str_field` for required string
   inputs; malformed types fail closed with a structured error.
4. **Bound the operation** with the configured limits
   (`WorkspaceLimits`): file sizes for read/copy/write, entry counts for
   listing/search, path length. Report truncation with a `truncated` flag.
5. **Return the documented stable error codes** (`path_outside_workspace`,
   `path_not_found`, `source_not_found`, `target_exists`, `not_a_file`,
   `not_a_directory`, `file_too_large`, `content_too_large`, `decode_error`,
   `invalid_encoding`, `invalid_path`, `invalid_content`,
   `unsupported_operation`, `filesystem_error`, `security_violation`, …).
   Messages must contain only the workspace-relative path — never the
   absolute host path, never file contents.
6. **Keep it inside the boundary:** no `subprocess`, no `shutil`-style
   helpers that could follow links out, no directory deletion, no implicit
   `mkdir` on write/copy/move, atomic writes where practical.
7. **Register via `register_workspace_tools`** (keeps the workspace tool
   set auditable as one unit) and add tests for the happy path, every
   error code you can trigger, and at least one escape attempt.

## Adding a model provider

Follow the `OpenAIProvider` pattern (Phase 1) so the core stays
vendor-agnostic:

1. Subclass `ModelProvider` in `providers/<name>_provider.py`; implement
   `complete()` (optionally `stream()` / `embed()`); set `name` and declare
   `capabilities`.
2. **Lazy vendor import** — import the SDK inside methods (client
   construction / request time), never at module top level, so
   `import agent_core` works without the SDK installed.
3. Add an **optional extra** in `packages/agent-core/pyproject.toml`
   (e.g. `[project.optional-dependencies] <name> = [...]`) and a mypy
   `ignore_missing_imports` override for the SDK in the root `pyproject.toml`.
4. **Credentials from the environment only.** Read the key inside
   `__init__`; raise `ProviderConfigurationError` (naming the variable, never
   a value) when it is missing. Never store the key on the instance beyond
   what the SDK client needs, and never put it in logs/errors.
5. **Normalize errors** to the project hierarchy: timeouts/5xx/429/connection
   → `TransientProviderError` (the gateway retries these); auth/config
   problems → `ProviderConfigurationError`; everything else → `ProviderError`
   with bounded, secret-free messages. Disable the SDK's own retry layer so
   the `ModelGateway` owns retry policy.
6. **Register the provider** in `providers/factory.py`
   (`create_provider` + `SUPPORTED_PROVIDERS`). Nothing upstream (gateway,
   planner, agent) changes.
7. **Tests:** offline unit tests with a stub client (inject it via the
   provider's `client`/constructor hook) covering request mapping, the error
   map, and key-leakage; plus an opt-in live test gated on the env key
   (skipped by default).
8. Update `.env.example` (placeholders only) and the docs
   (ARCHITECTURE.md, ROADMAP.md, SECURITY.md, README.md).

## Changing the core

Prefer additive changes. If a public signature must change, note it in the PR
and update the docs. Keep dependencies one-way:
`apps/ → agent_core → (stdlib + pydantic)`.

---

## Documentation

Docs must stay **truthful**. Use exactly these labels:

- **IMPLEMENTED** / **PLANNED** / **NOT IMPLEMENTED**

When you change code, update [ARCHITECTURE.md](ARCHITECTURE.md) and
[ROADMAP.md](ROADMAP.md) so the labels match reality.

---

## Commit & PR guidelines

- Small, focused changes. One concern per change.
- Conventional-commit style subject (`feat:`, `fix:`, `docs:`, `test:`,
  `chore:`, `refactor:`).
- In the PR description: what changed, why, which quality gates you ran, and
  any doc updates.
- Never commit `.env`, credentials, or secrets.
- Do not force-push to shared branches.

---

## Definition of done

A change is done when:

- [ ] `ruff format .`, `ruff check .`, `mypy`, and `pytest` all pass.
- [ ] No secrets/credentials introduced.
- [ ] No scratch or unnecessary files.
- [ ] Docs (labels + descriptions) match the implementation.
- [ ] No unrelated changes included.
