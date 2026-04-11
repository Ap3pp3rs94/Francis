from __future__ import annotations

from pathlib import Path


def test_system_info_and_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "test")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api-test")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    info = client.get("/system/info")
    assert info.status_code == 200
    info_body = info.json()
    assert info_body["ok"] is True
    assert info_body["info"]["service"] == "francis-api"
    assert info_body["info"]["env_profile"] == "test"
    assert info_body["info"]["run_mode"] == "api-test"

    status = client.get("/system/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["status"] == "ready"


def test_system_world_state_reports_nested_task_records(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    task_dir = data_root / "tasks" / "tsk_nested"
    (data_root / "approvals" / "pending").mkdir(parents=True, exist_ok=True)
    task_dir.mkdir(parents=True, exist_ok=True)
    (
        data_root / "approvals" / "pending" / "appr.json"
    ).write_text(
        '{"id":"appr","action":"plugin.run","reason":"integration_test","status":"pending","ts":10}',
        encoding="utf-8",
    )
    (
        task_dir / "record.json"
    ).write_text(
        '{"task_id":"tsk_nested","status":"running","capability":"plugin.run","objective":"Test nested task","created_at":"2026-04-11T10:00:00+00:00","updated_at":"2026-04-11T10:05:00+00:00"}',
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/system/world_state")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["subsystem"] == "world_state"
    assert body["counts"]["tasks"] == 1
    assert body["paths"]["tasks"]["path"] == str(data_root / "tasks")
    assert body["overview"]["task_status_counts"]["running"] == 1
    assert body["overview"]["recent_tasks"][0]["id"] == "tsk_nested"
    assert body["overview"]["pending_approvals"][0]["id"] == "appr"


def test_system_orb_status_reports_core_loop_and_gates(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    meta_root = repo_root / "meta"
    (repo_root / "src" / "francis").mkdir(parents=True, exist_ok=True)
    data_root.mkdir(parents=True, exist_ok=True)
    meta_root.mkdir(parents=True, exist_ok=True)
    (repo_root / "pyproject.toml").write_text("[project]\nname='francis-test'\nversion='0.0.0'\n", encoding="utf-8")
    (meta_root / "plane_map.yaml").write_text(
        """
meta:
  model_id: francis.plane_map
  version: 1
planes:
  - id: P1_INTERFACE
    name: Interface
    category: interface
    purpose: Capture operator intent
    side_effects_allowed: false
    default_risk_class: low
  - id: P4_COGNITION
    name: Cognition
    category: cognition
    purpose: Produce plans
    side_effects_allowed: false
    default_risk_class: medium
  - id: P3_GOVERNANCE
    name: Governance
    category: governance
    purpose: Evaluate policy gates
    side_effects_allowed: true
    default_risk_class: high
  - id: P2_IDENTITY
    name: Identity
    category: security
    purpose: Validate scopes
    side_effects_allowed: true
    default_risk_class: high
  - id: P7_EXECUTION
    name: Execution
    category: execution
    purpose: Perform side effects
    side_effects_allowed: true
    default_risk_class: critical
  - id: P9_OBSERVABILITY
    name: Observability
    category: observability
    purpose: Emit audit traces
    side_effects_allowed: true
    default_risk_class: medium
  - id: P8_MEMORY
    name: Memory
    category: data
    purpose: Persist continuity
    side_effects_allowed: true
    default_risk_class: high
transitions:
  - from: P1_INTERFACE
    to: P4_COGNITION
    conditions: [session_valid, request_parsed]
forbidden_transitions:
  - from: P1_INTERFACE
    to: P7_EXECUTION
    reason: direct execution is forbidden
""".strip(),
        encoding="utf-8",
    )
    (meta_root / "action_taxonomy.yaml").write_text(
        """
meta:
  taxonomy_id: francis.action_taxonomy
  version: 1
controls:
  - id: permission_gate
    description: Validate identity and scopes
  - id: trust_gate
    description: Check trust thresholds
  - id: approvals_gate
    description: Require approval when policy demands it
  - id: audit_log
    description: Emit an auditable trail
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/system/orb_status")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["subsystem"] == "orb_status"
    assert body["model"]["plane_map_id"] == "francis.plane_map"
    assert body["model"]["action_taxonomy_id"] == "francis.action_taxonomy"
    assert body["core_loop"][0]["id"] == "P1_INTERFACE"
    assert body["core_loop"][-1]["id"] == "P8_MEMORY"
    assert body["gates"][0]["id"] == "permission_gate"
    assert body["transitions"]["allowed"][0]["to"] == "P4_COGNITION"
    assert body["transitions"]["forbidden"][0]["to"] == "P7_EXECUTION"


def test_system_operator_mode_reports_environment_posture_and_focus(monkeypatch, tmp_path: Path) -> None:
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

    (env_root / "edge.yaml").write_text(
        """
version: 1
profile:
  id: edge
  name: Edge
  operator_notes:
    - "Edge profile note."
runtime:
  mode: edge
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
  label: "EDGE"
  banner:
    text: "EDGE MODE - LOCAL-FIRST / STRICT GOVERNANCE"
""".strip(),
        encoding="utf-8",
    )
    (approvals_root / "appr-1.json").write_text(
        '{"id":"appr-1","action":"plugin.run","reason":"deploy","status":"pending","ts":10}',
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
  "objective": "Blocked task",
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
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "edge")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/system/operator_mode")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["subsystem"] == "operator_mode"
    assert body["environment"]["id"] == "edge"
    assert body["environment"]["label"] == "EDGE"
    assert body["posture"]["governance_mode"] == "strict"
    assert body["posture"]["trust_posture"] == "strict"
    assert body["posture"]["web_access"] == "disabled"
    assert body["posture"]["writes"] == "restricted"
    assert body["backlog"]["pending_approvals"] == 1
    assert body["backlog"]["blocked_tasks"] == 1
    assert body["focus"]["plane_id"] == "P3_GOVERNANCE"
    assert "approval" in body["focus"]["reason"].lower()


def test_system_flags_set_and_list(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    set_res = client.post(
        "/system/flags/set",
        json={
            "key": "ui.experimental_mode",
            "enabled": True,
            "reason": "integration_test",
            "description": "Enable UI experiment",
        },
    )
    assert set_res.status_code == 200
    set_body = set_res.json()
    assert set_body["ok"] is True
    assert set_body["item"]["key"] == "ui.experimental_mode"
    assert set_body["item"]["enabled"] is True

    by_key = client.post(
        "/system/flags/ui.experimental_mode",
        json={"enabled": False, "reason": "turn_off"},
    )
    assert by_key.status_code == 200
    by_key_body = by_key.json()
    assert by_key_body["ok"] is True
    assert by_key_body["item"]["enabled"] is False

    listed = client.get("/system/flags")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    target = [item for item in listed_body["items"] if item.get("key") == "ui.experimental_mode"]
    assert target
    assert target[0]["enabled"] is False


def test_system_config_mutate_reflects_in_effective_snapshot(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    set_mutation = client.post(
        "/system/config/mutate",
        json={
            "op": "set",
            "path": "ui.preferences.theme",
            "value": "light",
            "reason": "test_set",
        },
    )
    assert set_mutation.status_code == 200
    set_body = set_mutation.json()
    assert set_body["ok"] is True
    assert set_body["applied"] is True
    assert set_body["resulting_value"] == "light"

    merge_mutation = client.post(
        "/system/config/mutate",
        json={
            "op": "merge",
            "path": "ui.preferences",
            "value": {"density": "compact"},
            "reason": "test_merge",
        },
    )
    assert merge_mutation.status_code == 200
    merge_body = merge_mutation.json()
    assert merge_body["ok"] is True
    assert merge_body["resulting_value"]["density"] == "compact"

    effective = client.get("/system/config/effective")
    assert effective.status_code == 200
    effective_body = effective.json()
    cfg = effective_body["config"]
    assert cfg["ui"]["preferences"]["theme"] == "light"
    assert cfg["ui"]["preferences"]["density"] == "compact"
