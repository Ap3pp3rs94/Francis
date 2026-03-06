from __future__ import annotations

from pathlib import Path


def ensure_local_first(*, repo_root: Path, workspace_root: Path) -> None:
    repo = repo_root.resolve()
    workspace = workspace_root.resolve()
    try:
        workspace.relative_to(repo)
    except ValueError as exc:
        raise ValueError(f"Workspace root must be inside repo root: {workspace}") from exc
