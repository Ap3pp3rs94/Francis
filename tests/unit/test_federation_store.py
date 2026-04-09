from __future__ import annotations

import json
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS

from services.orchestrator.app.federation_store import load_or_init_topology


def test_federation_topology_read_does_not_rewrite_clean_file(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    workspace_root = tmp_path / "workspace"
    fs = WorkspaceFS(roots=[workspace_root], journal_path=workspace_root / "journals" / "fs.jsonl")

    first = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    topology_path = workspace_root / "federation" / "topology.json"
    before = topology_path.read_text(encoding="utf-8")

    second = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    after = topology_path.read_text(encoding="utf-8")

    before_doc = json.loads(before)
    after_doc = json.loads(after)
    assert after == before
    assert after_doc["updated_at"] == before_doc["updated_at"]
    assert second["updated_at"] == first["updated_at"]

