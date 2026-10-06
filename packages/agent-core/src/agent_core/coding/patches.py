"""Safe, permission-gated application of structured coding patches.

A patch is a set of full-file replacements produced as data. Applying one is a
separate mutation step: every target is resolved through the existing
Workspace boundary, every live file is checked against the patch's original
SHA-256 and byte size, and no file is changed until all preconditions pass.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..permissions import (
    ApprovalRequest,
    PermissionDecision,
    PermissionLevel,
    PermissionManager,
    _active_permission_authorization,
)
from ..workspace import Workspace, WorkspaceError
from ..workspace_tools._common import atomic_write_bytes
from .errors import CodingPermissionError, CodingWorkspaceError
from .limits import CodingLimits
from .models import CodePatch

PATCH_OPERATION = "coding_apply_patch"


class PatchApplicationStatus(str):
    APPLIED = "applied"
    CONFLICT = "conflict"
    DENIED = "denied"
    FAILED = "failed"


@dataclass(frozen=True)
class PatchFileResult:
    path: str
    status: str
    original_sha256: str
    current_sha256: str | None = None
    bytes_written: int = 0
    error_code: str | None = None


@dataclass(frozen=True)
class PatchApplicationResult:
    patch_id: str
    status: str
    files: tuple[PatchFileResult, ...]
    message: str

    @property
    def applied_count(self) -> int:
        return sum(item.status == PatchApplicationStatus.APPLIED for item in self.files)


class _PatchPermissionDescriptor:
    name = PATCH_OPERATION
    permission_level = PermissionLevel.MEDIUM


class CodingPatchRuntime:
    """Apply an already validated patch with all-or-nothing preflight."""

    name = PATCH_OPERATION
    permission_level = PermissionLevel.MEDIUM

    def __init__(
        self,
        workspace: Workspace,
        permissions: PermissionManager,
        limits: CodingLimits | None = None,
    ) -> None:
        self._workspace = workspace
        self._permissions = permissions
        self._limits = limits or CodingLimits()

    def apply(
        self,
        project,
        patch: CodePatch,
        *,
        task_id: str = "coding",
        step_id: str = "coding-apply",
        approval_reason: str = "Apply the proposed coding patch to the workspace.",
    ) -> PatchApplicationResult:
        if patch.project_id != project.project_id:
            raise CodingWorkspaceError()

        self._limits.validate_patch(patch)
        self._authorize(task_id, step_id, approval_reason)

        try:
            targets = project.resolve_project_paths(
                self._workspace,
                (change.target_path for change in patch.changes),
            )
        except Exception as exc:
            if isinstance(exc, CodingWorkspaceError):
                raise
            raise CodingWorkspaceError() from exc

        # Preflight every target before mutating any file. This prevents a
        # stale second file from leaving the patch half-applied.
        preflight: list[tuple[object, Path, str, int]] = []
        results: list[PatchFileResult] = []
        for change, rel in zip(patch.changes, targets, strict=True):
            resolved = self._workspace.resolve(rel)
            try:
                if not resolved.exists() or not resolved.is_file():
                    results.append(
                        PatchFileResult(
                            path=rel,
                            status=PatchApplicationStatus.CONFLICT,
                            original_sha256=change.original_sha256,
                            error_code="target_missing",
                        )
                    )
                    continue
                data = resolved.read_bytes()
            except (OSError, WorkspaceError):
                results.append(
                    PatchFileResult(
                        path=rel,
                        status=PatchApplicationStatus.FAILED,
                        original_sha256=change.original_sha256,
                        error_code="read_failed",
                    )
                )
                continue

            current_hash = hashlib.sha256(data).hexdigest()
            if len(data) != change.original_size_bytes or current_hash != change.original_sha256:
                results.append(
                    PatchFileResult(
                        path=rel,
                        status=PatchApplicationStatus.CONFLICT,
                        original_sha256=change.original_sha256,
                        current_sha256=current_hash,
                        error_code="source_changed",
                    )
                )
                continue
            replacement = change.replacement_content.encode("utf-8")
            if len(replacement) > self._workspace.limits.max_write_bytes:
                results.append(
                    PatchFileResult(
                        path=rel,
                        status=PatchApplicationStatus.FAILED,
                        original_sha256=change.original_sha256,
                        current_sha256=current_hash,
                        error_code="content_too_large",
                    )
                )
                continue
            preflight.append((change, resolved, rel, len(replacement)))

        if len(preflight) != len(patch.changes):
            return PatchApplicationResult(
                patch_id=patch.patch_id,
                status=PatchApplicationStatus.CONFLICT
                if any(item.status == PatchApplicationStatus.CONFLICT for item in results)
                else PatchApplicationStatus.FAILED,
                files=tuple(results),
                message="Patch preflight failed; no files were changed.",
            )

        applied: list[PatchFileResult] = []
        try:
            for change, resolved, rel, size in preflight:
                atomic_write_bytes(resolved, change.replacement_content.encode("utf-8"))
                applied.append(
                    PatchFileResult(
                        path=rel,
                        status=PatchApplicationStatus.APPLIED,
                        original_sha256=change.original_sha256,
                        current_sha256=change.replacement_sha256,
                        bytes_written=size,
                    )
                )
        except OSError:
            return PatchApplicationResult(
                patch_id=patch.patch_id,
                status=PatchApplicationStatus.FAILED,
                files=tuple(applied),
                message="Patch application failed during the write phase.",
            )

        return PatchApplicationResult(
            patch_id=patch.patch_id,
            status=PatchApplicationStatus.APPLIED,
            files=tuple(applied),
            message="Patch applied successfully.",
        )

    def _authorize(self, task_id: str, step_id: str, reason: str) -> None:
        decision = self._permissions.check(_PatchPermissionDescriptor())
        if decision is PermissionDecision.ALLOWED:
            return
        if decision is PermissionDecision.DENIED:
            raise CodingPermissionError()
        active = _active_permission_authorization()
        if (
            active is not None
            and active.tool_name == self.name
            and active.permission_level is self.permission_level
        ):
            return
        approved = self._permissions.request_approval(
            ApprovalRequest(
                task_id=task_id,
                step_id=step_id,
                tool_name=self.name,
                permission_level=self.permission_level,
                reason=reason,
            )
        )
        if not approved:
            raise CodingPermissionError()
