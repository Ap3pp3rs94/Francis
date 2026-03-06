from __future__ import annotations

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

from .catalog import update_entry


def promote_stage(fs: WorkspaceFS, stage_id: str) -> dict | None:
    return update_entry(
        fs,
        stage_id,
        {
            "status": "active",
            "promoted_at": utc_now_iso(),
        },
    )
