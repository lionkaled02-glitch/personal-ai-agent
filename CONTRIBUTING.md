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

1. Create a class with a `spec: ToolSpec` and a `run(input) -> ToolResult`
   method (see `demo_tools.py` for the pattern).
2. Declare the correct `permission_level`
   (`LOW` / `MEDIUM` / `HIGH`) — see [SECURITY.md](SECURITY.md).
3. Register it in a `ToolRegistry` where the agent is wired up.
4. Add tests (registration, execution, permission path).
5. No core changes should be needed. If they are, stop and reconsider —
   that's a smell.

Do **not** add tools with shell access or broad side effects before the
relevant roadmap phase.

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
