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

``DATA_ROOT`` is configuration only in Phases 0-1: no tool touches the
filesystem yet.
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
        )

    def configure_logging(self) -> None:
        """Configure the root logger to the configured level."""
        logging.basicConfig(level=self.log_level.upper())
