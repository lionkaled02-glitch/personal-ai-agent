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
```

Configuration is environment-based. If you want to override defaults, copy
`.env.example` to `.env` (which is git-ignored). **Phase 0 needs no API keys.**

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

1. Subclass `ModelProvider` and implement `complete()`
   (optionally `stream()` / `embed()`).
2. Set `name` and declare `capabilities`.
3. Read any API key from the **environment** (never hard-code it).
4. Add tests that exercise the new adapter without hitting the network
   (e.g. via injection) plus a gated integration test.
5. No core changes should be needed.

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
