# agent-core

The only importable package in this repository. It contains the Phase 0
foundation, the Phase 1 model layer, the Phase 2 tool layer, the Phase 3
workspace layer, and the Phase 4 document layer of the personal AI agent:
task state model, planner, executor, tool system with registry, permission
manager, structured event bus, a vendor-neutral `ModelProvider` interface
with a `ModelGateway` (error normalization + safe retry), a
configuration-driven provider factory, a deterministic mock provider
(offline default), an OpenAI provider adapter (optional `openai` extra, lazy
SDK import), the **Tool Runtime** — permission-gated, schema-validated,
metadata-carrying tool execution — safe, deterministic built-in tools
(calculator, date/time, text utils, JSON utils), the **workspace filesystem
layer** (a fail-closed `Workspace` boundary plus nine scoped,
permission-gated file tools; no shell or subprocess), and the **document
processing & knowledge foundation**:

- **Parsers** — a `DocumentParser` interface + registry with built-ins for
  TXT, Markdown, PDF (pypdf), DOCX (python-docx), PPTX (python-pptx), and
  XLSX (openpyxl). The four binary parsers use an optional `docs` extra and
  import their library lazily (missing library ⇒ structured
  `parser_unavailable`). Parsers extract text/structure only — they never
  execute anything a document contains, and document text is never treated
  as instructions.
- **Normalized model** — `Document` / `DocumentSection` / `DocumentChunk`
  (Pydantic, deterministic ids, serializable) with page/slide/sheet
  locations, headings, deterministic table rendering, extraction warnings,
  stats, and an explicit truncation flag.
- **Chunking** — deterministic, bounded (configurable size + overlap,
  count-capped, metadata-preserving). No embeddings.
- **Retrieval** — a provider-neutral, deterministic **lexical**
  `KnowledgeStore` behind the `RetrievalIndex` protocol (a future vector
  store implements the same protocol). No external model.
- **Tools** — `inspect_document` (LOW), `extract_document` (LOW),
  `index_document` (MEDIUM), `search_documents` (LOW), all run through the
  Tool Runtime and read only through the Phase 3 `Workspace` boundary.

## Extras

- `agent-core[openai]` — the OpenAI provider SDK.
- `agent-core[docs]` — the four document parser libraries (pypdf,
  python-docx, python-pptx, openpyxl). Without it, the binary parsers fail
  with a structured `parser_unavailable` error at parse time; TXT and
  Markdown always work.

- Architecture: see [`ARCHITECTURE.md`](../../ARCHITECTURE.md)
- Engineering rules: see [`AGENTS.md`](../../AGENTS.md)
- Security model: see [`SECURITY.md`](../../SECURITY.md)

No API keys or network access are required to use or test this package; a
real provider is opt-in via `MODEL_PROVIDER=openai` + `OPENAI_API_KEY`.
