"""Environment-based configuration.

The core reads plain environment variables (``AGENT_NAME``, ``LOG_LEVEL``,
``DATA_ROOT``) via :meth:`Settings.from_env`. Secrets are never read here —
provider API keys are not needed for the foundation (mock provider), and
future key handling belongs in provider adapters (see SECURITY.md).

``DATA_ROOT`` is configuration only in Phase 0: no tool touches the
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

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> Settings:
        """Build settings from an environment mapping (defaults: os.environ)."""
        source: Mapping[str, str] = os.environ if env is None else env
        defaults = cls()
        return cls(
            agent_name=source.get("AGENT_NAME", defaults.agent_name),
            log_level=source.get("LOG_LEVEL", defaults.log_level),
            data_root=Path(source.get("DATA_ROOT", str(defaults.data_root))),
        )

    def configure_logging(self) -> None:
        """Configure the root logger to the configured level."""
        logging.basicConfig(level=self.log_level.upper())
