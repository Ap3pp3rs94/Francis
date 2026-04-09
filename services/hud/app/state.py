from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.approvals_store import ApprovalSnapshot, load_approval_snapshot as load_shared_approval_snapshot
from services.orchestrator.app import lens_snapshot as shared_snapshot

DEFAULT_WORKSPACE_ROOT = shared_snapshot.DEFAULT_WORKSPACE_ROOT


def get_workspace_root() -> Path:
    return DEFAULT_WORKSPACE_ROOT


def load_approval_snapshot(workspace_root: Path | None = None) -> ApprovalSnapshot:
    resolved_workspace = (workspace_root or get_workspace_root()).resolve()
    fs = WorkspaceFS(
        roots=[resolved_workspace],
        journal_path=(resolved_workspace / "journals" / "fs.jsonl").resolve(),
    )
    return load_shared_approval_snapshot(fs)


def build_lens_snapshot(
    workspace_root: Path | None = None,
    *,
    approval_snapshot: ApprovalSnapshot | None = None,
    capability_state: dict[str, Any] | None = None,
    profile: bool = False,
) -> dict[str, Any]:
    return shared_snapshot.build_lens_snapshot(
        (workspace_root or get_workspace_root()).resolve(),
        approval_snapshot=approval_snapshot,
        capability_state=capability_state,
        profile=profile,
    )
