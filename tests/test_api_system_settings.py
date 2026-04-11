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
    incident_ids = {item["id"] for item in body["overview"]["incidents"]}
    assert "governance.pending_approvals" in incident_ids


def test_system_world_state_reports_governance_backlog_states(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    blocked_task_dir = data_root / "tasks" / "tsk_blocked"
    approval_task_dir = data_root / "tasks" / "tsk_approval"
    blocked_task_dir.mkdir(parents=True, exist_ok=True)
    approval_task_dir.mkdir(parents=True, exist_ok=True)

    (
        blocked_task_dir / "record.json"
    ).write_text(
        """
{
  "task_id": "tsk_blocked",
  "status": "accepted",
  "capability": "plugin.run",
  "objective": "Blocked deploy",
  "updated_at": "2026-04-11T12:05:00+00:00",
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
    (
        approval_task_dir / "record.json"
    ).write_text(
        """
{
  "task_id": "tsk_approval",
  "status": "accepted",
  "capability": "plugin.run",
  "objective": "Awaiting approval",
  "updated_at": "2026-04-11T12:10:00+00:00",
  "result": {
    "kind": "task.result",
    "data": {
      "status": "needs_approval",
      "message": "Approval required before rerun."
    }
  }
}
""".strip(),
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
    assert body["counts"]["tasks"] == 2
    assert body["counts"]["queued_tasks"] == 0
    assert body["counts"]["blocked_tasks"] == 1
    assert body["counts"]["approval_pending_tasks"] == 1
    assert body["counts"]["running_tasks"] == 0
    assert body["counts"]["active_incidents"] >= 2
    assert body["overview"]["task_status_counts"]["blocked"] == 1
    assert body["overview"]["task_status_counts"]["needs_approval"] == 1
    assert body["overview"]["recent_tasks"][0]["status"] == "needs_approval"
    assert body["overview"]["recent_tasks"][1]["status"] == "blocked"
    incident_ids = {item["id"] for item in body["overview"]["incidents"]}
    assert "governance.awaiting_approval" in incident_ids
    assert "governance.blocked_tasks" in incident_ids


def test_system_world_state_reports_mission_counts_and_continuity(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Carry mission continuity across sessions",
            "summary": "Stage 3 mission projection test.",
            "next_step": "Link a task and mark the mission blocked.",
            "requester_id": "test.system.world_state",
            "risk_tier": "medium",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "world_state mission linkage",
            "mission_id": mission_id,
            "input": {"goal": "Linked operation for world-state mission summary"},
        },
    )
    assert operation.status_code == 200
    operation_id = str(operation.json()["operation_id"])

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.system.world_state"})
    assert executed.status_code == 200
    assert executed.json()["ok"] is True

    response = client.get("/system/world_state")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["paths"]["missions"]["path"] == str(data_root / "missions")
    assert body["counts"]["missions"] == 1
    assert body["counts"]["blocked_missions"] == 0
    assert body["counts"]["queued_missions"] == 0
    assert body["counts"]["active_missions"] == 0
    assert body["counts"]["deadlettered_missions"] == 0
    assert body["overview"]["mission_status_counts"]["completed"] == 1
    assert body["overview"]["recent_missions"][0]["id"] == mission_id
    assert body["overview"]["recent_missions"][0]["linked_task_ids"] == [operation_id]
    assert body["overview"]["recent_missions"][0]["linked_task_count"] == 1
    assert body["overview"]["recent_missions"][0]["last_task_id"] == operation_id
    assert body["overview"]["recent_missions"][0]["last_task_status"] == "completed"
    assert body["overview"]["recent_missions"][0]["last_task_result_status"] == ""


def test_system_world_state_projects_mission_queue_and_deadletter_preview(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    ready = client.post(
        "/missions/create",
        json={
            "objective": "Queue first mission action",
            "summary": "Mission has no linked work yet.",
            "priority": 7,
            "requester_id": "test.system.queue",
        },
    )
    assert ready.status_code == 200
    ready_id = str(ready.json()["mission_id"])

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission for queue preview",
            "summary": "Mission should surface a governed blocker.",
            "priority": 9,
            "requester_id": "test.system.queue",
        },
    )
    assert blocked.status_code == 200
    blocked_id = str(blocked.json()["mission_id"])

    dead = client.post(
        "/missions/create",
        json={
            "objective": "Deadletter preview mission",
            "summary": "Mission should appear in deadletter preview.",
            "requester_id": "test.system.queue",
        },
    )
    assert dead.status_code == 200
    dead_id = str(dead.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    blocked_operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue preview blocker",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert blocked_operation.status_code == 200
    blocked_operation_id = str(blocked_operation.json()["operation_id"])

    blocked_run = client.post(f"/operations/{blocked_operation_id}/run", json={"worker_id": "test.system.queue"})
    assert blocked_run.status_code == 200
    assert blocked_run.json()["status"] == "blocked"

    deadlettered = client.post(
        f"/missions/{dead_id}/deadletter",
        json={"reason": "manual_cleanup", "actor": "test.system.queue"},
    )
    assert deadlettered.status_code == 200
    assert deadlettered.json()["ok"] is True

    response = client.get("/system/world_state")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    queue_items = body["overview"]["mission_queue"]
    assert queue_items
    assert queue_items[0]["id"] == blocked_id
    assert queue_items[0]["recommended_action"] == "raise_trust_or_reduce_risk"
    ready_item = next(item for item in queue_items if item["id"] == ready_id)
    assert ready_item["recommended_action"] == "create_first_operation"
    deadletter_items = body["overview"]["deadletter_missions"]
    assert deadletter_items
    assert deadletter_items[0]["id"] == dead_id
    assert deadletter_items[0]["recommended_action"] == "review_deadletter"


def test_system_world_state_projects_mission_briefing_and_advance_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/missions/create",
        json={
            "objective": "Queued mission with recorded advance",
            "summary": "This mission should show the first advance receipt in the queue briefing.",
            "priority": 8,
            "requester_id": "test.system.briefing",
        },
    )
    assert queued.status_code == 200
    queued_id = str(queued.json()["mission_id"])

    queued_advance = client.post(
        f"/missions/{queued_id}/advance",
        json={"actor": "test.system.briefing", "note": "create initial linked operation"},
    )
    assert queued_advance.status_code == 200
    assert queued_advance.json()["ok"] is True
    assert queued_advance.json()["applied"] is True

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission for operator handback",
            "summary": "This mission should lead the briefing focus.",
            "priority": 9,
            "requester_id": "test.system.briefing",
        },
    )
    assert blocked.status_code == 200
    blocked_id = str(blocked.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    blocked_operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "blocked mission for briefing",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert blocked_operation.status_code == 200
    blocked_operation_id = str(blocked_operation.json()["operation_id"])

    blocked_run = client.post(f"/operations/{blocked_operation_id}/run", json={"worker_id": "test.system.briefing"})
    assert blocked_run.status_code == 200
    assert blocked_run.json()["status"] == "blocked"

    blocked_advance = client.post(
        f"/missions/{blocked_id}/advance",
        json={"actor": "test.system.briefing", "note": "respect governance blocker"},
    )
    assert blocked_advance.status_code == 200
    assert blocked_advance.json()["ok"] is True
    assert blocked_advance.json()["applied"] is False

    completed = client.post(
        "/missions/create",
        json={
            "objective": "Completed mission for continuity briefing",
            "summary": "This mission should appear in recently completed continuity.",
            "requester_id": "test.system.briefing",
        },
    )
    assert completed.status_code == 200
    completed_id = str(completed.json()["mission_id"])

    first_advance = client.post(
        f"/missions/{completed_id}/advance",
        json={"actor": "test.system.briefing"},
    )
    assert first_advance.status_code == 200
    assert first_advance.json()["ok"] is True
    assert first_advance.json()["applied"] is True

    second_advance = client.post(
        f"/missions/{completed_id}/advance",
        json={"actor": "test.system.briefing", "worker_id": "test.system.briefing"},
    )
    assert second_advance.status_code == 200
    assert second_advance.json()["ok"] is True
    assert second_advance.json()["applied"] is True

    response = client.get("/system/world_state")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True

    briefing = body["overview"]["mission_briefing"]
    assert briefing["counts"]["blocked"] == 1
    assert briefing["counts"]["queued"] == 1
    assert briefing["counts"]["completed"] == 1
    assert "blocked mission" in briefing["headline"].lower()

    focus = briefing["focus"]
    assert focus
    assert focus[0]["id"] == blocked_id
    assert focus[0]["recommended_action"] == "raise_trust_or_reduce_risk"
    assert focus[0]["last_advance_outcome"] == "requires_operator"
    queued_focus = next(item for item in focus if item["id"] == queued_id)
    assert queued_focus["recommended_action"] == "run_linked_operation"
    assert queued_focus["last_advance_action"] == "create_first_operation"
    assert queued_focus["last_advance_applied"] is True

    recent_completed = briefing["recently_completed"]
    assert recent_completed
    assert recent_completed[0]["id"] == completed_id
    assert recent_completed[0]["last_advance_action"] == "run_linked_operation"
    assert recent_completed[0]["last_advance_outcome"] == "succeeded"

    completed_recent = next(item for item in body["overview"]["recent_missions"] if item["id"] == completed_id)
    assert completed_recent["last_advance_action"] == "run_linked_operation"
    assert completed_recent["last_advance_outcome"] == "succeeded"


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
    assert body["control_mode"]["id"] == "assist"
    assert body["available_modes"][1]["id"] == "assist"
    assert body["available_modes"][1]["active"] is True
    assert body["backlog"]["pending_approvals"] == 1
    assert body["backlog"]["blocked_tasks"] == 1
    assert body["focus"]["plane_id"] == "P3_GOVERNANCE"
    assert "approval" in body["focus"]["reason"].lower()


def test_system_operator_mode_update_persists_control_mode(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    env_root = repo_root / "config" / "environments"

    env_root.mkdir(parents=True, exist_ok=True)
    (data_root / "runtime").mkdir(parents=True, exist_ok=True)

    (env_root / "dev.yaml").write_text(
        """
version: 1
profile:
  id: dev
  name: Development
runtime:
  mode: dev
governance:
  approvals:
    enabled: true
    mode: policy
  trust:
    minimum_operational_trust: 0
network:
  egress:
    enabled: true
features:
  web_learning:
    enabled: true
    allow_search: true
    allow_fetch: true
    allow_ingest: false
ui:
  label: "DEV"
  banner:
    text: "DEV MODE"
""".strip(),
        encoding="utf-8",
    )

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    update = client.post(
        "/system/operator_mode",
        json={
            "mode": "away",
            "reason": "night shift coverage",
            "actor": "chat_ui",
        },
    )
    assert update.status_code == 200
    update_body = update.json()
    assert update_body["ok"] is True
    assert update_body["applied"] is True
    assert update_body["control_mode"]["id"] == "away"
    assert update_body["control_mode"]["reason"] == "night shift coverage"
    assert update_body["control_mode"]["changed_by"] == "chat_ui"

    follow_up = client.get("/system/operator_mode")
    assert follow_up.status_code == 200
    body = follow_up.json()
    assert body["control_mode"]["id"] == "away"
    assert body["available_modes"][3]["active"] is True


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
