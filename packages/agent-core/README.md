# agent-core

The only importable package in this repository. It contains the Phase 0
foundation of the personal AI agent: task state model, planner, executor,
tool system with registry, permission manager, structured event bus, and a
vendor-neutral model provider interface with a deterministic mock.

- Architecture: see [`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- Engineering rules: see [`AGENTS.md`](../../AGENTS.md)
- Security model: see [`SECURITY.md`](../../SECURITY.md)

No API keys or network access are required to use or test this package.
