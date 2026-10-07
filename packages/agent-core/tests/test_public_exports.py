"""The public ``agent_core`` surface must match its declared exports.

``__all__`` is a contract: every name listed there must be importable from
the package root. A missing import (name declared but never imported) breaks
``from agent_core import X`` at runtime even though mypy and lint pass.
"""

from __future__ import annotations

import agent_core


def test_every_public_export_is_importable() -> None:
    missing = [name for name in agent_core.__all__ if not hasattr(agent_core, name)]
    assert missing == []


def test_patch_runtime_is_exported() -> None:
    # Regression guard: ``CodingPatchRuntime`` was listed in ``__all__``
    # without being imported, so ``from agent_core import CodingPatchRuntime``
    # raised ImportError.
    from agent_core import CodingPatchRuntime

    assert agent_core.CodingPatchRuntime is CodingPatchRuntime
