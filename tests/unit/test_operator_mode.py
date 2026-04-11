from __future__ import annotations

from pathlib import Path


def test_operator_mode_snapshot_summarizes_profile_and_governance_backlog(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    env_root = repo_root / "config" / "environments"
    tasks_root = data_root / "tasks"
    approvals_root = data_root / "approvals" / "pending"
    trust_root = data_root / "trust" / "levels"

    env_root.mkdir(parents=True, exist_ok=True)
    tasks_root.mkdir(parents=True, exist_ok=True)
    approvals_root.mkdir(parents=True, exist_ok=True)
    trust_root.mkdir(parents=True, exist_ok=True)

    (env_root / "production.yaml").write_text(
        """
version: 1
profile:
  id: production
  name: Production
  description: Production test profile
  operator_notes:
    - "Use authenticated access only."
runtime:
  mode: production
governance:
  approvals:
    enabled: true
    mode: strict
  trust:
    minimum_operational_trust: 2
network:
  egress:
    enabled: false
features:
  web_learning:
    enabled: false
    allow_search: false
    allow_fetch: false
    allow_ingest: false
ui:
  label: "PROD"
  banner:
    text: "PRODUCTION - STRICT GOVERNANCE / REQUIRED AUDIT"
""".strip(),
        encoding="utf-8",
    )

    (approvals_root / "appr-1.json").write_text(
        '{"id":"appr-1","action":"plugin.run","reason":"deploy","status":"pending","ts":1}',
        encoding="utf-8",
    )
    blocked_task_dir = tasks_root / "tsk_blocked"
    blocked_task_dir.mkdir(parents=True, exist_ok=True)
    (blocked_task_dir / "record.json").write_text(
        """
{
  "task_id": "tsk_blocked",
  "status": "accepted",
  "capability": "plugin.run",
  "objective": "Deploy change",
  "result": {
    "kind": "task.result",
    "data": {
      "status": "blocked",
      "error": "insufficient_trust"
    }
  }
}
""".strip(),
        encoding="utf-8",
    )
    (trust_root / "current_state.json").write_text(
        '{"global_level": 1, "domain_levels": {}, "last_updated": 10}',
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "production")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from francis.world_state.operator_mode import snapshot

    state = snapshot()
    assert state["ok"] is True
    assert state["subsystem"] == "operator_mode"
    assert state["environment"]["id"] == "production"
    assert state["environment"]["label"] == "PROD"
    assert state["posture"]["governance_mode"] == "strict"
    assert state["posture"]["trust_posture"] == "strict"
    assert state["posture"]["trust_level"] == 1
    assert state["posture"]["minimum_operational_trust"] == 2
    assert state["posture"]["web_access"] == "disabled"
    assert state["posture"]["writes"] == "restricted"
    assert state["backlog"]["pending_approvals"] == 1
    assert state["backlog"]["blocked_tasks"] == 1
    assert state["focus"]["plane_id"] == "P3_GOVERNANCE"
    assert "approval" in state["focus"]["reason"].lower()
    assert state["notes"] == ["Use authenticated access only."]
