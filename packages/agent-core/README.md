# agent-core

The only importable package in this repository. It contains the Phase 0
foundation and the Phase 1 model layer of the personal AI agent: task state
model, planner, executor, tool system with registry, permission manager,
structured event bus, and the model layer — vendor-neutral
`ModelProvider` interface, `ModelGateway` (error normalization + safe
retry), a configuration-driven provider factory, a deterministic mock
provider (offline default), and an OpenAI provider adapter (optional
`openai` extra, lazy SDK import).

- Architecture: see [`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- Engineering rules: see [`AGENTS.md`](../../AGENTS.md)
- Security model: see [`SECURITY.md`](../../SECURITY.md)

No API keys or network access are required to use or test this package; a
real provider is opt-in via `MODEL_PROVIDER=openai` + `OPENAI_API_KEY`.
