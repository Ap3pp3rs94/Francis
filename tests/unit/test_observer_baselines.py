from __future__ import annotations

import json
from pathlib import Path

import pytest

from francis_core.workspace_fs import WorkspaceFS
from services.observer.app.anomaly import baselines
from services.observer.app import main as observer_main


def _workspace_fs(workspace: Path) -> WorkspaceFS:
    return WorkspaceFS(
        roots=[workspace],
        journal_path=(workspace / "journals" / "fs.jsonl").resolve(),
    )


def test_load_or_init_normalizes_pathological_thresholds(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    fs = _workspace_fs(workspace)
    fs.write_text(
        "observer/baselines.json",
        json.dumps(
            {
                "disk_free_percent_min": 100.0,
                "memory_available_percent_min": 100.0,
                "repo_dirty_files_warn": 0,
                "cpu_normalized_load_warn": 101.0,
                "custom_flag": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    loaded = baselines.load_or_init(fs)

    assert loaded["disk_free_percent_min"] == baselines.DEFAULT_BASELINE["disk_free_percent_min"]
    assert loaded["memory_available_percent_min"] == baselines.DEFAULT_BASELINE["memory_available_percent_min"]
    assert loaded["repo_dirty_files_warn"] == baselines.DEFAULT_BASELINE["repo_dirty_files_warn"]
    assert loaded["cpu_normalized_load_warn"] == baselines.DEFAULT_BASELINE["cpu_normalized_load_warn"]
    assert loaded["custom_flag"] is True

    persisted = json.loads(fs.read_text("observer/baselines.json"))
    assert persisted == loaded


def test_run_cycle_uses_normalized_baseline_for_false_positive_threshold_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir(parents=True, exist_ok=True)
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    fs = _workspace_fs(workspace)
    fs.write_text(
        "observer/baselines.json",
        json.dumps(
            {
                "disk_free_percent_min": 100.0,
                "memory_available_percent_min": 100.0,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    monkeypatch.setattr(
        observer_main,
        "collect_snapshot",
        lambda **_: {
            "ts": "2026-03-26T00:00:00+00:00",
            "disk": {"free_percent": 95.84},
            "cpu": {"normalized_load_percent": 5.0},
            "memory": {"available_percent": 39.24},
            "network": {},
            "processes": {},
            "repo": {"dirty_files": 0},
            "services": {},
        },
    )

    result = observer_main.run_cycle(
        run_id="observer-baseline-normalize",
        repo_root=repo_root,
        workspace_root=workspace,
    )

    assert result["baseline"]["disk_free_percent_min"] == baselines.DEFAULT_BASELINE["disk_free_percent_min"]
    assert result["baseline"]["memory_available_percent_min"] == baselines.DEFAULT_BASELINE["memory_available_percent_min"]
    anomaly_kinds = {str(row.get("kind", "")).strip().lower() for row in result["anomalies"]}
    assert "disk.low_free_space" not in anomaly_kinds
    assert "memory.low_available" not in anomaly_kinds

    persisted = json.loads(fs.read_text("observer/baselines.json"))
    assert persisted["disk_free_percent_min"] == baselines.DEFAULT_BASELINE["disk_free_percent_min"]
    assert persisted["memory_available_percent_min"] == baselines.DEFAULT_BASELINE["memory_available_percent_min"]
