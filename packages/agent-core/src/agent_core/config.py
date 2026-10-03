"""Environment-based configuration.

The core reads plain environment variables via :meth:`Settings.from_env`.
Settings holds **non-secret** values only. Provider *credentials*
(``OPENAI_API_KEY``) are read from the environment by the provider factory
at construction time — never stored in Settings and never logged
(see SECURITY.md).

Variables:

- ``AGENT_NAME`` (str, default ``personal-agent``)
- ``LOG_LEVEL`` (str, default ``INFO``)
- ``DATA_ROOT`` (path, default ``data``)
- ``MODEL_PROVIDER`` (str, default ``mock`` — provider selection, Phase 1)
- ``MODEL_NAME`` (str, default ``""`` — model for the selected provider)
- ``MODEL_TIMEOUT_S`` (float, default ``60`` — provider request timeout)
- ``MODEL_MAX_RETRIES`` (int, default ``2`` — gateway retries after the
  first attempt for transient failures)
- ``WORKSPACE_ROOT`` (path, default ``data/workspace`` — root of the
  workspace boundary for the filesystem tools, Phase 3)
- ``WORKSPACE_MAX_READ_BYTES`` (int, default ``1048576`` — largest file the
  read/copy tools will process)
- ``WORKSPACE_MAX_WRITE_BYTES`` (int, default ``1048576`` — largest
  content the write tool will accept)
- ``WORKSPACE_MAX_LIST_ENTRIES`` (int, default ``500`` — listing cap)
- ``WORKSPACE_MAX_SEARCH_RESULTS`` (int, default ``200`` — search cap)
- ``WORKSPACE_MAX_PATH_LENGTH`` (int, default ``512`` — max resolved
  workspace-relative path length)
- ``DOCUMENT_MAX_INPUT_BYTES`` (int, default ``10485760`` — max raw document
  size, Phase 4)
- ``DOCUMENT_MAX_EXTRACTED_CHARS`` (int, default ``500000`` — total
  extracted text budget)
- ``DOCUMENT_MAX_PAGES`` / ``DOCUMENT_MAX_SLIDES`` /
  ``DOCUMENT_MAX_SHEETS`` (int, defaults ``200`` / ``100`` / ``20`` —
  container caps for PDF / PPTX / XLSX)
- ``DOCUMENT_MAX_SECTIONS`` (int, default ``500`` — section cap)
- ``DOCUMENT_MAX_CHUNKS`` (int, default ``500`` — chunk count cap)
- ``DOCUMENT_CHUNK_SIZE`` (int, default ``800`` — max chunk characters)
- ``DOCUMENT_CHUNK_OVERLAP`` (int, default ``100`` — chunk overlap)
- ``DOCUMENT_MAX_SEARCH_RESULTS`` (int, default ``10`` — retrieval cap)
- ``DOCUMENT_MAX_QUERY_CHARS`` (int, default ``500`` — max query length)

``DATA_ROOT`` holds logs and task artifacts; it is independent of the
workspace boundary, which the Phase 3 filesystem tools enforce strictly.
Document tools (Phase 4) read only through that same boundary.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from pathlib import Path

from pydantic import BaseModel


class Settings(BaseModel):
    agent_name: str = "personal-agent"
    log_level: str = "INFO"
    data_root: Path = Path("data")
    # Model gateway (Phase 1) — non-secret provider configuration.
    model_provider: str = "mock"
    model_name: str = ""
    model_timeout_s: float = 60.0
    model_max_retries: int = 2
    # Workspace filesystem tools (Phase 3) — boundary + limits.
    workspace_root: Path = Path("data/workspace")
    workspace_max_read_bytes: int = 1_048_576
    workspace_max_write_bytes: int = 1_048_576
    workspace_max_list_entries: int = 500
    workspace_max_search_results: int = 200
    workspace_max_path_length: int = 512
    # Document processing & knowledge foundation (Phase 4) — limits.
    document_max_input_bytes: int = 10_485_760
    document_max_extracted_chars: int = 500_000
    document_max_pages: int = 200
    document_max_slides: int = 100
    document_max_sheets: int = 20
    document_max_sections: int = 500
    document_max_chunks: int = 500
    document_chunk_size: int = 800
    document_chunk_overlap: int = 100
    document_max_search_results: int = 10
    document_max_query_chars: int = 500

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from an environment mapping (defaults: os.environ)."""
        source: Mapping[str, str] = os.environ if env is None else env
        defaults = cls()
        return cls(
            agent_name=source.get("AGENT_NAME", defaults.agent_name),
            log_level=source.get("LOG_LEVEL", defaults.log_level),
            data_root=Path(source.get("DATA_ROOT", str(defaults.data_root))),
            model_provider=source.get("MODEL_PROVIDER", defaults.model_provider),
            model_name=source.get("MODEL_NAME", defaults.model_name),
            model_timeout_s=float(source.get("MODEL_TIMEOUT_S", defaults.model_timeout_s)),
            model_max_retries=int(source.get("MODEL_MAX_RETRIES", defaults.model_max_retries)),
            workspace_root=Path(source.get("WORKSPACE_ROOT", str(defaults.workspace_root))),
            workspace_max_read_bytes=int(
                source.get("WORKSPACE_MAX_READ_BYTES", defaults.workspace_max_read_bytes)
            ),
            workspace_max_write_bytes=int(
                source.get("WORKSPACE_MAX_WRITE_BYTES", defaults.workspace_max_write_bytes)
            ),
            workspace_max_list_entries=int(
                source.get("WORKSPACE_MAX_LIST_ENTRIES", defaults.workspace_max_list_entries)
            ),
            workspace_max_search_results=int(
                source.get("WORKSPACE_MAX_SEARCH_RESULTS", defaults.workspace_max_search_results)
            ),
            workspace_max_path_length=int(
                source.get("WORKSPACE_MAX_PATH_LENGTH", defaults.workspace_max_path_length)
            ),
            document_max_input_bytes=int(
                source.get("DOCUMENT_MAX_INPUT_BYTES", defaults.document_max_input_bytes)
            ),
            document_max_extracted_chars=int(
                source.get("DOCUMENT_MAX_EXTRACTED_CHARS", defaults.document_max_extracted_chars)
            ),
            document_max_pages=int(source.get("DOCUMENT_MAX_PAGES", defaults.document_max_pages)),
            document_max_slides=int(
                source.get("DOCUMENT_MAX_SLIDES", defaults.document_max_slides)
            ),
            document_max_sheets=int(
                source.get("DOCUMENT_MAX_SHEETS", defaults.document_max_sheets)
            ),
            document_max_sections=int(
                source.get("DOCUMENT_MAX_SECTIONS", defaults.document_max_sections)
            ),
            document_max_chunks=int(
                source.get("DOCUMENT_MAX_CHUNKS", defaults.document_max_chunks)
            ),
            document_chunk_size=int(
                source.get("DOCUMENT_CHUNK_SIZE", defaults.document_chunk_size)
            ),
            document_chunk_overlap=int(
                source.get("DOCUMENT_CHUNK_OVERLAP", defaults.document_chunk_overlap)
            ),
            document_max_search_results=int(
                source.get("DOCUMENT_MAX_SEARCH_RESULTS", defaults.document_max_search_results)
            ),
            document_max_query_chars=int(
                source.get("DOCUMENT_MAX_QUERY_CHARS", defaults.document_max_query_chars)
            ),
        )

    def configure_logging(self) -> None:
        """Configure the root logger to the configured level."""
        logging.basicConfig(level=self.log_level.upper())
