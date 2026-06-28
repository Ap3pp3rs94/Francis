from __future__ import annotations

import json
from pathlib import Path


def _fake_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "src" / "francis").mkdir(parents=True)
    (root / "docs" / "operations").mkdir(parents=True)
    (root / "docs" / "canonical").mkdir(parents=True)
    (root / "tests").mkdir(parents=True)
    (root / "scripts").mkdir(parents=True)
    (root / "pyproject.toml").write_text("[project]\nname='francis'\n", encoding="utf-8")
    (root / "src" / "francis" / "example.py").write_text("# TODO: tighten this path\nVALUE = 1\n", encoding="utf-8")
    (root / "docs" / "operations" / "COMPLETION_LEDGER.md").write_text(
        "Francis is in `Phase 2`.\nThe strongest current posture is still observability.\n",
        encoding="utf-8",
    )
    (root / "docs" / "BUILD_ORDER.md").write_text("## 5. Current priority\nobservability before autonomy\n", encoding="utf-8")
    (root / "docs" / "canonical" / "BUILD_MANIFEST.md").write_text(
        "# Francis 2.0 - ORB Build Manifest (Phase 2)\n## 2. Current Build Posture\n",
        encoding="utf-8",
    )
    (root / "config" / "runtime" / "lens").mkdir(parents=True)
    (root / "config" / "runtime" / "lens" / "overlay.json").write_text(
        '{"visible": true, "status": "idle"}',
        encoding="utf-8",
    )
    return root


def test_overnight_explorer_run_once_is_read_only_and_writes_receipt(tmp_path: Path) -> None:
    from francis.exploration.overnight import make_config, run_once

    data_root = tmp_path / "data"
    config = make_config(
        repo_root=_fake_repo(tmp_path),
        data_root=data_root,
        session_id="test-session",
        max_findings=8,
        max_scan_files=50,
    )

    receipt = run_once(config)

    assert receipt["ok"] is True
    assert receipt["kind"] == "francis.exploration.overnight.receipt"
    assert receipt["session_id"] == "test-session"
    assert receipt["governance"]["read_only"] is True
    assert receipt["governance"]["desktop_input"] is False
    assert receipt["governance"]["network_access"] is False
    assert receipt["governance"]["repository_mutation"] is False
    assert receipt["governance"]["mutation_authority_granted"] is False
    assert receipt["policy_decision"]["decision"] == "allowed"
    assert receipt["policy_decision"]["grants_execution_authority"] is False
    assert receipt["policy_decision"]["grants_mutation_authority"] is False

    receipt_path = Path(receipt["receipt_path"])
    assert receipt_path.exists()
    assert receipt_path.parent == data_root / "runtime" / "overnight_explorer" / "receipts"
    stored = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert stored["receipt_id"] == receipt["receipt_id"]

    findings = receipt["observations"]["findings"]
    assert any(item["marker"] == "todo" for item in findings)
    assert receipt["learning_notes"]["learned"]["scanned_files"] >= 4
    assert (data_root / "runtime" / "overnight_explorer" / "latest.json").exists()
    assert Path(receipt["governance"]["policy_receipt_path"]).exists()


def test_overnight_explorer_loop_respects_existing_stop_flag(tmp_path: Path) -> None:
    from francis.exploration.overnight import make_config, run_loop, stop_flag_path, write_stop_flag

    data_root = tmp_path / "data"
    write_stop_flag(data_root, reason="test")
    config = make_config(repo_root=_fake_repo(tmp_path), data_root=data_root, duration_hours=0.01, interval_minutes=0.01)

    summary = run_loop(config)

    assert summary["ok"] is True
    assert summary["status"] == "stopped"
    assert summary["cycles_completed"] == 0
    assert Path(summary["summary_path"]).exists()
    assert Path(stop_flag_path(data_root)).exists()


def test_overnight_explorer_status_reports_latest(tmp_path: Path) -> None:
    from francis.exploration.overnight import make_config, read_status, run_once

    data_root = tmp_path / "data"
    run_once(make_config(repo_root=_fake_repo(tmp_path), data_root=data_root, session_id="status-session"))

    status = read_status(data_root)

    assert status["ok"] is True
    assert status["status"] == "ready"
    assert status["receipt_count"] == 1
    assert status["latest"]["session_id"] == "status-session"
