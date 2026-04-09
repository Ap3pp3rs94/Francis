from __future__ import annotations

import json
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS

from services.orchestrator.app.managed_copy_store import build_managed_copy_state


def test_managed_copy_state_read_does_not_rewrite_clean_registry(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace_root], journal_path=workspace_root / "journals" / "fs.jsonl")

    first = build_managed_copy_state(fs)
    registry_path = workspace_root / "managed_copies" / "registry.json"
    before = registry_path.read_text(encoding="utf-8")

    second = build_managed_copy_state(fs)
    after = registry_path.read_text(encoding="utf-8")

    before_doc = json.loads(before)
    after_doc = json.loads(after)
    assert after == before
    assert after_doc["updated_at"] == before_doc["updated_at"]
    assert second["updated_at"] == first["updated_at"]
