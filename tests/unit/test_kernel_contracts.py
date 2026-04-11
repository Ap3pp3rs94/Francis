from __future__ import annotations

from pathlib import Path


def test_trust_tracker_adjust_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.trust import tracker

    first = tracker.adjust_level(
        op="set",
        value=4,
        reason="bootstrap",
        actor="test",
        domain="platform",
        idempotency_key="corr-1",
        risk_tier="medium",
    )
    assert first["ok"] is True
    assert first["applied"] is True
    assert first["level"] == 4
    assert first["decision"]["risk_tier"] == "medium"

    second = tracker.adjust_level(
        op="set",
        value=9,
        reason="should_not_reapply",
        actor="test",
        domain="platform",
        idempotency_key="corr-1",
        risk_tier="medium",
    )
    assert second["ok"] is True
    assert second["applied"] is False
    assert second["level"] == 4

    history = tracker.list_history(limit=10, actor="test")
    assert len(history) == 1
    assert history[0]["idempotency_key"] == "corr-1"


def test_authority_boundaries_block_scope_escape() -> None:
    from francis.trust.boundaries import evaluate_request

    result = evaluate_request(
        {
            "action": "plugin.run",
            "risk_tier": "critical",
            "scope": {"path": "C:/forbidden/project"},
        },
        {
            "allowed_paths": ["C:/allowed/project"],
            "allowed_actions": ["plugin.run"],
            "max_risk_tier": "medium",
            "approvals_required": True,
        },
        trust_level=6,
    )

    assert result["ok"] is False
    assert "path_outside_boundary" in result["issues"]
    assert "risk_tier_outside_boundary" in result["issues"]


def test_world_state_snapshot_reports_repo_and_data(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    task_dir = data_root / "tasks" / "tsk_example"
    second_task_dir = data_root / "tasks" / "tsk_running"
    (repo_root / "plugins" / "generated").mkdir(parents=True, exist_ok=True)
    (data_root / "approvals" / "pending").mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    second_task_dir.mkdir(parents=True, exist_ok=True)
    (data_root / "logs").mkdir(parents=True, exist_ok=True)
    (
        data_root / "approvals" / "pending" / "a.json"
    ).write_text('{"id":"a","action":"plugin.run","reason":"test","status":"pending","ts":1}', encoding="utf-8")
    (
        task_dir / "record.json"
    ).write_text(
        '{"task_id":"tsk_example","status":"pending","capability":"plugin.run","objective":"First","created_at":"2026-04-11T10:00:00+00:00","updated_at":"2026-04-11T10:00:00+00:00"}',
        encoding="utf-8",
    )
    (
        second_task_dir / "record.json"
    ).write_text(
        '{"task_id":"tsk_running","status":"running","capability":"codex.supervised_exec","objective":"Second","created_at":"2026-04-11T11:00:00+00:00","updated_at":"2026-04-11T12:00:00+00:00","assigned_to":"worker-1"}',
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.world_state.snapshot import snapshot

    state = snapshot()
    assert state["ok"] is True
    assert state["repo_root"] == str(repo_root.resolve())
    assert state["data_dir"] == str(data_root.resolve())
    assert state["counts"]["pending_approvals"] == 1
    assert state["counts"]["tasks"] == 2
    assert state["overview"]["task_status_counts"]["pending"] == 1
    assert state["overview"]["task_status_counts"]["running"] == 1
    assert state["overview"]["pending_approvals"][0]["action"] == "plugin.run"
    assert state["overview"]["recent_tasks"][0]["id"] == "tsk_running"
    assert state["overview"]["recent_tasks"][0]["assigned_to"] == "worker-1"


def test_stack_and_services_report_known_surfaces(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    config_root = repo_root / "config"

    (repo_root / "src" / "francis" / "api").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "daemon").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "workers").mkdir(parents=True, exist_ok=True)
    (repo_root / "apps" / "chat_ui").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins").mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    config_root.mkdir(parents=True, exist_ok=True)

    (repo_root / "src" / "francis" / "api" / "app.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "daemon" / "runner.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "workers" / "runner.py").write_text("", encoding="utf-8")

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_CONFIG_DIR", str(config_root))

    from francis.kernel.services import services_action, services_status
    from francis.kernel.stack import stack_status

    stack = stack_status(probe_runtime=True)
    assert stack["probe_runtime"] is True
    assert stack["counts"]["total"] >= 5
    assert stack["status"] == "ok"

    services = services_status()
    by_name = {item["name"]: item for item in services["services"]}
    assert services["status"] == "ready"
    assert by_name["api"]["status"] == "ready"
    assert by_name["daemon"]["status"] == "ready"
    assert by_name["workers"]["status"] == "ready"

    action = services_action("restart", ["api", "workers"])
    assert action["ok"] is True
    assert action["simulated"] is True
    assert len(action["services"]) == 2
    assert {item["name"] for item in action["services"]} == {"api", "workers"}
