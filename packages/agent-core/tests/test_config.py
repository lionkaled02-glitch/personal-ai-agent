"""Settings tests: environment-based configuration with safe defaults."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
from agent_core import Settings


class TestFromEnv:
    def test_defaults_when_env_empty(self) -> None:
        settings = Settings.from_env(env={})
        assert settings.agent_name == "personal-agent"
        assert settings.log_level == "INFO"
        assert settings.data_root == Path("data")

    def test_overrides(self) -> None:
        settings = Settings.from_env(
            env={
                "AGENT_NAME": "my-agent",
                "LOG_LEVEL": "debug",
                "DATA_ROOT": "/tmp/agent-data",
            }
        )
        assert settings.agent_name == "my-agent"
        assert settings.log_level == "debug"
        assert settings.data_root == Path("/tmp/agent-data")

    def test_partial_env_falls_back_to_defaults(self) -> None:
        settings = Settings.from_env(env={"AGENT_NAME": "only-name"})
        assert settings.agent_name == "only-name"
        assert settings.log_level == "INFO"
        assert settings.data_root == Path("data")

    def test_reads_os_environ_when_no_mapping_given(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("AGENT_NAME", "from-os")
        settings = Settings.from_env()
        assert settings.agent_name == "from-os"

    def test_configure_logging_sets_level(self) -> None:
        settings = Settings(log_level="WARNING")
        settings.configure_logging()
        assert logging.getLogger().level == logging.WARNING
