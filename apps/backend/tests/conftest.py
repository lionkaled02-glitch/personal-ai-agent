"""Backend test path setup."""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

FIXED_NOW = datetime(2026, 1, 1, tzinfo=UTC)
