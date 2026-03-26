from __future__ import annotations

import json
from pathlib import Path

from francis_core.workspace_fs import WorkspaceFS
from services.orchestrator.app.swarm_store import load_or_init_units


def _make_fs(root: Path) -> WorkspaceFS:
    return WorkspaceFS(
        roots=[root],
        journal_path=root / "journals" / "fs.jsonl",
    )


def test_load_or_init_units_restores_missing_canonical_units(tmp_path: Path) -> None:
    fs = _make_fs(tmp_path)
    swarm_path = tmp_path / "swarm" / "units.json"
    swarm_path.parent.mkdir(parents=True, exist_ok=True)
    swarm_path.write_text(
        json.dumps(
            {
                "version": 1,
                "updated_at": "2026-03-12T10:00:00+00:00",
                "units": [
                    {
                        "unit_id": "planner",
                        "label": "Planner",
                        "role": "planner",
                        "summary": "Portable planner",
                        "capabilities": ["mission.plan"],
                        "scope_defaults": {
                            "repos": [str(tmp_path)],
                            "workspaces": [str(tmp_path / "workspace")],
                            "apps": ["control", "approvals", "lens"],
                        },
                        "delegatable": True,
                        "local": True,
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    units = load_or_init_units(fs, repo_root=tmp_path, workspace_root=tmp_path / "workspace")
    unit_ids = {str(row.get("unit_id", "")).strip() for row in units}

    assert {"coordinator", "planner", "repo_operator", "verifier", "memory_curator", "incident_guard"} <= unit_ids
    planner = next(row for row in units if str(row.get("unit_id", "")).strip() == "planner")
    assert planner["summary"] == "Portable planner"

    persisted = json.loads(swarm_path.read_text(encoding="utf-8"))
    persisted_ids = {str(row.get("unit_id", "")).strip() for row in persisted.get("units", [])}
    assert {"coordinator", "planner", "repo_operator", "verifier", "memory_curator", "incident_guard"} <= persisted_ids
