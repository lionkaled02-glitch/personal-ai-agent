"""Offline tests for safe Phase 10 patch application."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from agent_core import PermissionManager, Workspace
from agent_core.coding import (
    CodeChange,
    CodePatch,
    CodingPatchRuntime,
    CodingPermissionError,
    CodingProject,
    PatchApplicationStatus,
)


def _setup(tmp_path: Path, approval=None):
    root = tmp_path / "workspace"
    root.mkdir()
    project_root = root / "project"
    project_root.mkdir()
    ws = Workspace(root)
    project = CodingProject(project_id="patch-test", root_path="project")
    permissions = PermissionManager(approval=approval)
    return ws, project, permissions, project_root


def _patch(path: str, original: str, replacement: str) -> CodePatch:
    return CodePatch(
        project_id="patch-test",
        summary="test patch",
        changes=(
            CodeChange(
                target_path=path,
                original_sha256=hashlib.sha256(original.encode()).hexdigest(),
                original_size_bytes=len(original.encode()),
                replacement_content=replacement,
            ),
        ),
    )


def test_patch_requires_approval_and_applies_after_approval(tmp_path: Path) -> None:
    ws, project, permissions, root = _setup(tmp_path, approval=lambda _: True)
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8", newline="")

    result = CodingPatchRuntime(ws, permissions).apply(project, _patch("app.py", "value = 1\n", "value = 2\n"))

    assert result.status == PatchApplicationStatus.APPLIED
    assert target.read_text(encoding="utf-8") == "value = 2\n"


def test_denied_patch_does_not_touch_files(tmp_path: Path) -> None:
    ws, project, permissions, root = _setup(tmp_path, approval=lambda _: False)
    target = root / "app.py"
    target.write_text("value = 1\n", encoding="utf-8", newline="")

    with pytest.raises(CodingPermissionError):
        CodingPatchRuntime(ws, permissions).apply(project, _patch("app.py", "value = 1\n", "value = 2\n"))

    assert target.read_text(encoding="utf-8") == "value = 1\n"


def test_stale_patch_is_rejected_before_any_write(tmp_path: Path) -> None:
    ws, project, permissions, root = _setup(tmp_path, approval=lambda _: True)
    target = root / "app.py"
    target.write_text("value = 9\n", encoding="utf-8", newline="")

    result = CodingPatchRuntime(ws, permissions).apply(project, _patch("app.py", "value = 1\n", "value = 2\n"))

    assert result.status == PatchApplicationStatus.CONFLICT
    assert result.files[0].error_code == "source_changed"
    assert target.read_text(encoding="utf-8") == "value = 9\n"


def test_multi_file_preflight_prevents_partial_patch(tmp_path: Path) -> None:
    ws, project, permissions, root = _setup(tmp_path, approval=lambda _: True)
    first = "a = 1\n"
    second = "b = 1\n"
    (root / "a.py").write_text(first, encoding="utf-8", newline="")
    (root / "b.py").write_text("b = 9\n", encoding="utf-8", newline="")
    patch = CodePatch(
        project_id="patch-test",
        summary="multi",
        changes=(
            CodeChange(
                target_path="a.py",
                original_sha256=hashlib.sha256(first.encode()).hexdigest(),
                original_size_bytes=len(first.encode()),
                replacement_content="a = 2\n",
            ),
            CodeChange(
                target_path="b.py",
                original_sha256=hashlib.sha256(second.encode()).hexdigest(),
                original_size_bytes=len(second.encode()),
                replacement_content="b = 2\n",
            ),
        ),
    )

    result = CodingPatchRuntime(ws, permissions).apply(project, patch)

    assert result.status == PatchApplicationStatus.CONFLICT
    assert (root / "a.py").read_text(encoding="utf-8") == first
    assert (root / "b.py").read_text(encoding="utf-8") == "b = 9\n"


def test_patch_target_cannot_escape_project(tmp_path: Path) -> None:
    ws, project, permissions, _ = _setup(tmp_path, approval=lambda _: True)
    patch = _patch("../outside.py", "x\n", "y\n")

    with pytest.raises(Exception):
        CodingPatchRuntime(ws, permissions).apply(project, patch)
