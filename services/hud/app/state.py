from __future__ import annotations

from pathlib import Path
from typing import Any

from services.orchestrator.app import lens_snapshot as shared_snapshot

DEFAULT_WORKSPACE_ROOT = shared_snapshot.DEFAULT_WORKSPACE_ROOT


def get_workspace_root() -> Path:
    return DEFAULT_WORKSPACE_ROOT


def build_lens_snapshot(workspace_root: Path | None = None) -> dict[str, Any]:
    return shared_snapshot.build_lens_snapshot((workspace_root or get_workspace_root()).resolve())
