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
- ``MEMORY_MAX_ITEMS`` (int, default ``1000`` — max stored memories, Phase 5)
- ``MEMORY_MAX_CONTENT_CHARS`` (int, default ``4000`` — max memory content
  length; also bounds recall/context queries)
- ``MEMORY_MAX_METADATA_BYTES`` (int, default ``4096`` — max serialized
  metadata size per memory)
- ``MEMORY_MAX_RECALL_RESULTS`` (int, default ``10`` — recall/list cap)
- ``MEMORY_MAX_CONTEXT_CHARS`` (int, default ``8000`` — RAG context budget)
- ``MEMORY_MAX_CONTEXT_ITEMS`` (int, default ``20`` — RAG context item cap)
- ``MEMORY_SHORT_TERM_TTL_S`` (int, default ``3600`` — short_term TTL)
- ``MEMORY_WORKING_TTL_S`` (int, default ``86400`` — working TTL)
- ``COMPUTER_MAX_ACTIONS_PER_TASK`` (int, default ``20``)
- ``COMPUTER_ACTION_TIMEOUT_S`` (float, default ``5``)
- ``COMPUTER_MAX_TEXT_INPUT_CHARS`` (int, default ``256``)
- ``COMPUTER_MAX_SCREENSHOT_BYTES`` (int, default ``1048576``)
- ``COMPUTER_MAX_WINDOWS`` (int, default ``50``)
- ``COMPUTER_MAX_UI_ELEMENTS`` (int, default ``100``)
- ``COMPUTER_MAX_RETRIES`` (int, default ``1``)
- ``COMPUTER_MOUSE_MOVE_DURATION_S`` (float, default ``0.5``)
- ``COMPUTER_CURSOR_TOLERANCE_PX`` (int, default ``2``)

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
    # Memory layer (Phase 5) — limits + policy.
    memory_max_items: int = 1_000
    memory_max_content_chars: int = 4_000
    memory_max_metadata_bytes: int = 4_096
    memory_max_recall_results: int = 10
    memory_max_context_chars: int = 8_000
    memory_max_context_items: int = 20
    memory_short_term_ttl_s: int = 3_600
    memory_working_ttl_s: int = 86_400
    # Computer Agent Foundation (Phase 6) — conservative runtime bounds.
    computer_max_actions_per_task: int = 20
    computer_action_timeout_s: float = 5.0
    computer_max_text_input_chars: int = 256
    computer_max_screenshot_bytes: int = 1_048_576
    computer_max_windows: int = 50
    computer_max_ui_elements: int = 100
    computer_max_retries: int = 1
    computer_mouse_move_duration_s: float = 0.5
    computer_cursor_tolerance_px: int = 2

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
            memory_max_items=int(source.get("MEMORY_MAX_ITEMS", defaults.memory_max_items)),
            memory_max_content_chars=int(
                source.get("MEMORY_MAX_CONTENT_CHARS", defaults.memory_max_content_chars)
            ),
            memory_max_metadata_bytes=int(
                source.get("MEMORY_MAX_METADATA_BYTES", defaults.memory_max_metadata_bytes)
            ),
            memory_max_recall_results=int(
                source.get("MEMORY_MAX_RECALL_RESULTS", defaults.memory_max_recall_results)
            ),
            memory_max_context_chars=int(
                source.get("MEMORY_MAX_CONTEXT_CHARS", defaults.memory_max_context_chars)
            ),
            memory_max_context_items=int(
                source.get("MEMORY_MAX_CONTEXT_ITEMS", defaults.memory_max_context_items)
            ),
            memory_short_term_ttl_s=int(
                source.get("MEMORY_SHORT_TERM_TTL_S", defaults.memory_short_term_ttl_s)
            ),
            memory_working_ttl_s=int(
                source.get("MEMORY_WORKING_TTL_S", defaults.memory_working_ttl_s)
            ),
            computer_max_actions_per_task=int(
                source.get("COMPUTER_MAX_ACTIONS_PER_TASK", defaults.computer_max_actions_per_task)
            ),
            computer_action_timeout_s=float(
                source.get("COMPUTER_ACTION_TIMEOUT_S", defaults.computer_action_timeout_s)
            ),
            computer_max_text_input_chars=int(
                source.get("COMPUTER_MAX_TEXT_INPUT_CHARS", defaults.computer_max_text_input_chars)
            ),
            computer_max_screenshot_bytes=int(
                source.get("COMPUTER_MAX_SCREENSHOT_BYTES", defaults.computer_max_screenshot_bytes)
            ),
            computer_max_windows=int(
                source.get("COMPUTER_MAX_WINDOWS", defaults.computer_max_windows)
            ),
            computer_max_ui_elements=int(
                source.get("COMPUTER_MAX_UI_ELEMENTS", defaults.computer_max_ui_elements)
            ),
            computer_max_retries=int(
                source.get("COMPUTER_MAX_RETRIES", defaults.computer_max_retries)
            ),
            computer_mouse_move_duration_s=float(
                source.get(
                    "COMPUTER_MOUSE_MOVE_DURATION_S", defaults.computer_mouse_move_duration_s
                )
            ),
            computer_cursor_tolerance_px=int(
                source.get("COMPUTER_CURSOR_TOLERANCE_PX", defaults.computer_cursor_tolerance_px)
            ),
        )

    def configure_logging(self) -> None:
        """Configure the root logger to the configured level."""
        logging.basicConfig(level=self.log_level.upper())
