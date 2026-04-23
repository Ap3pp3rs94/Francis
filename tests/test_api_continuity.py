from __future__ import annotations

from pathlib import Path
from typing import Any


def _without_dynamic_observed_at(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _without_dynamic_observed_at(item) for key, item in value.items() if key != "observed_at"}
    if isinstance(value, list):
        return [_without_dynamic_observed_at(item) for item in value]
    return value


def _write_dev_environment(repo_root: Path) -> None:
    env_root = repo_root / "config" / "environments"
    env_root.mkdir(parents=True, exist_ok=True)
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


def _write_orb_meta(repo_root: Path) -> None:
    meta_root = repo_root / "meta"
    meta_root.mkdir(parents=True, exist_ok=True)
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
    side_effects_allowed: false
    default_risk_class: medium
  - id: P8_MEMORY
    name: Memory
    category: memory
    purpose: Preserve continuity
    side_effects_allowed: false
    default_risk_class: medium
transitions:
  - from: P1_INTERFACE
    to: P4_COGNITION
    reason: Operator intent enters planning
    conditions:
      - input_received
  - from: P4_COGNITION
    to: P3_GOVERNANCE
    reason: Planned work enters policy evaluation
    conditions:
      - plan_ready
forbidden_transitions:
  - from: P1_INTERFACE
    to: P7_EXECUTION
    reason: Execution must not bypass cognition and governance
    conditions:
      - governance_missing
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


def _write_repo_scaffold(repo_root: Path) -> None:
    (repo_root / "data").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "api").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "daemon").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "workers").mkdir(parents=True, exist_ok=True)
    (repo_root / "apps" / "chat_ui").mkdir(parents=True, exist_ok=True)
    (repo_root / "plugins").mkdir(parents=True, exist_ok=True)
    (repo_root / "src" / "francis" / "api" / "app.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "daemon" / "runner.py").write_text("", encoding="utf-8")
    (repo_root / "src" / "francis" / "workers" / "runner.py").write_text("", encoding="utf-8")
    (repo_root / "pyproject.toml").write_text("[project]\nname='francis-test'\nversion='0.0.0'\n", encoding="utf-8")
    _write_dev_environment(repo_root)
    _write_orb_meta(repo_root)


def test_continuity_briefing_reports_idle_operator_start_state(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    response = client.get("/continuity/briefing")
    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["subsystem"] == "continuity_briefing"
    assert body["briefing"]["headline"] == "No mission backlog is currently active."
    assert body["briefing"]["focus"] == []
    assert body["briefing"]["readiness"]["stage"] == "Stage 3 - Missions"
    assert body["briefing"]["readiness"]["status"] == "review"
    assert body["briefing"]["readiness"]["satisfied"] == 1
    assert body["briefing"]["readiness"]["total"] == 5
    mission_readiness_by_id = {item["id"]: item for item in body["briefing"]["readiness"]["criteria"]}
    assert mission_readiness_by_id["visible_status"]["status"] == "satisfied"
    assert mission_readiness_by_id["idempotent_ticks"]["status"] == "not_yet_observed"
    assert mission_readiness_by_id["deadletter_cleanly"]["status"] == "not_yet_observed"
    assert body["briefing"]["observer"]["headline"] == "Observer reports no active incidents."
    assert body["briefing"]["observer"]["observed_at"] > 0
    assert body["briefing"]["observer"]["readiness"]["stage"] == "Stage 2 - Observer"
    assert body["briefing"]["observer"]["readiness"]["status"] == "review"
    assert body["briefing"]["observer"]["readiness"]["satisfied"] == 4
    assert body["briefing"]["observer"]["readiness"]["total"] == 5
    readiness_by_id = {item["id"]: item for item in body["briefing"]["observer"]["readiness"]["criteria"]}
    assert readiness_by_id["traceable_scans"]["status"] == "not_yet_observed"
    assert readiness_by_id["observer_findings_receipted"]["status"] == "satisfied"
    assert body["briefing"]["observer"]["counts"]["active"] == 0
    assert body["briefing"]["observer"]["anomaly"]["score"] == 0
    assert body["briefing"]["observer"]["anomaly"]["level"] == "clear"
    assert {item["id"] for item in body["briefing"]["observer"]["probes"]} == {
        "stack_status",
        "services_status",
        "approval_queue",
        "task_runtime",
    }
    assert all(item["observed_at"] > 0 for item in body["briefing"]["observer"]["probes"])
    assert body["briefing"]["observer"]["focus"] == []
    assert body["recent_missions"] == []
    assert body["operator"]["available"] is True
    assert body["operator"]["control_mode"]["id"] == "assist"
    assert body["operator"]["focus"]["plane_id"] == "P1_INTERFACE"
    assert body["orb"]["available"] is True
    assert body["orb"]["state"]["mode"]["id"] == "assist"
    assert body["orb"]["state"]["render_state"] == "ambient_rest"
    assert body["orb"]["state"]["handback_state"]["state"] == "none"


def test_continuity_briefing_aliases_match_primary_route(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    primary = client.get("/continuity/briefing")
    underscore_alias = client.get("/continuity/shift_briefing")
    hyphen_alias = client.get("/continuity/shift-briefing")

    assert primary.status_code == 200
    assert underscore_alias.status_code == 200
    assert hyphen_alias.status_code == 200

    primary_body = primary.json()
    for body in (underscore_alias.json(), hyphen_alias.json()):
        assert body["ok"] == primary_body["ok"]
        assert body["subsystem"] == primary_body["subsystem"]
        assert _without_dynamic_observed_at(body["briefing"]) == _without_dynamic_observed_at(primary_body["briefing"])
        assert body["mission_status_counts"] == primary_body["mission_status_counts"]
        assert body["recent_missions"] == primary_body["recent_missions"]
        assert body["operator"] == primary_body["operator"]
        assert _without_dynamic_observed_at(body["orb"]) == _without_dynamic_observed_at(primary_body["orb"])


def test_continuity_ledger_tail_returns_recent_entries(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.chat.continuity.ledger import append

    append(
        "user", "Carry forward the 8 AM continuity pass.", {"session_id": "chat_alpha", "mission_id": "mission_alpha"}
    )
    append("system", "daemon started", {"subsystem": "daemon", "profile": "dev", "run_mode": "api"})

    client = TestClient(create_app())

    response = client.get("/continuity/ledger?limit=1")
    assert response.status_code == 200

    body = response.json()
    assert "error" not in body
    assert len(body["entries"]) == 1
    latest = body["entries"][0]
    assert latest["role"] == "system"
    assert latest["content"] == "daemon started"
    assert latest["meta"]["subsystem"] == "daemon"
    assert latest["meta"]["profile"] == "dev"
    assert latest["meta"]["run_mode"] == "api"


def test_continuity_briefing_surfaces_handoff_and_recent_completion(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission for shift briefing",
            "summary": "This mission should lead the continuity focus.",
            "priority": 9,
            "requester_id": "test.continuity.briefing",
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
            "reason": "continuity briefing blocker",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert blocked_operation.status_code == 200
    blocked_operation_id = str(blocked_operation.json()["operation_id"])

    blocked_run = client.post(
        f"/operations/{blocked_operation_id}/run",
        json={"worker_id": "test.continuity.briefing"},
    )
    assert blocked_run.status_code == 200
    assert blocked_run.json()["status"] == "blocked"

    observer_scan = client.post(
        "/system/observer/scan",
        json={"reason": "continuity handoff check", "actor": "test.continuity.briefing"},
    )
    assert observer_scan.status_code == 200
    observer_scan_body = observer_scan.json()
    assert observer_scan_body["ok"] is True
    receipt_id = str(observer_scan_body["receipt"]["receipt_id"])
    assert receipt_id

    completed = client.post(
        "/missions/create",
        json={
            "objective": "Completed mission for shift briefing",
            "summary": "This mission should show up as recently completed.",
            "requester_id": "test.continuity.briefing",
        },
    )
    assert completed.status_code == 200
    completed_id = str(completed.json()["mission_id"])

    first_advance = client.post(
        f"/missions/{completed_id}/advance",
        json={"actor": "test.continuity.briefing"},
    )
    assert first_advance.status_code == 200
    assert first_advance.json()["ok"] is True
    assert first_advance.json()["applied"] is True

    second_advance = client.post(
        f"/missions/{completed_id}/advance",
        json={"actor": "test.continuity.briefing", "worker_id": "test.continuity.briefing"},
    )
    assert second_advance.status_code == 200
    assert second_advance.json()["ok"] is True
    assert second_advance.json()["applied"] is True

    response = client.get("/continuity/briefing")
    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert body["briefing"]["counts"]["blocked"] == 1
    assert body["briefing"]["counts"]["completed"] == 1
    assert "blocked mission" in body["briefing"]["headline"].lower()
    assert body["briefing"]["focus"][0]["id"] == blocked_id
    assert body["briefing"]["focus"][0]["recommended_action"] == "raise_trust_or_reduce_risk"
    assert body["briefing"]["focus"][0]["latest_activity"]["name"] == "governance_hold"
    assert body["briefing"]["focus"][0]["latest_activity"]["status"] == "blocked"
    assert body["briefing"]["observer"]["counts"]["active"] >= 1
    assert body["briefing"]["observer"]["readiness"]["status"] == "ready"
    assert body["briefing"]["observer"]["readiness"]["satisfied"] == 5
    assert body["briefing"]["observer"]["readiness"]["total"] == 5
    assert body["briefing"]["readiness"]["stage"] == "Stage 3 - Missions"
    assert body["briefing"]["readiness"]["status"] == "review"
    assert body["briefing"]["readiness"]["satisfied"] == 4
    assert body["briefing"]["readiness"]["total"] == 5
    mission_readiness_by_id = {item["id"]: item for item in body["briefing"]["readiness"]["criteria"]}
    assert mission_readiness_by_id["idempotent_ticks"]["status"] == "satisfied"
    assert mission_readiness_by_id["deadletter_cleanly"]["status"] == "not_yet_observed"
    assert mission_readiness_by_id["visible_status"]["status"] == "satisfied"
    assert mission_readiness_by_id["session_continuity"]["status"] == "satisfied"
    assert mission_readiness_by_id["reconstruction_reduced"]["status"] == "satisfied"
    assert body["briefing"]["observer"]["anomaly"]["score"] >= 50
    assert body["briefing"]["observer"]["anomaly"]["level"] == "error"
    observer_probes = body["briefing"]["observer"]["probes"]
    assert observer_probes
    assert next(item for item in observer_probes if item["id"] == "task_runtime")["status"] == "attention"
    assert next(item for item in observer_probes if item["id"] == "approval_queue")["incident_count"] == 0
    observer_focus = body["briefing"]["observer"]["focus"]
    assert observer_focus
    blocked_incident = next(item for item in observer_focus if item["id"] == "governance.blocked_tasks")
    assert blocked_incident["probe"] == "task_runtime"
    assert blocked_incident["task_id"] == blocked_operation_id
    assert blocked_incident["observed_at"] > 0
    assert blocked_incident["evidence"][0]["kind"] == "task"
    assert blocked_incident["evidence"][0]["id"] == blocked_operation_id
    observer_recent_scans = body["briefing"]["observer"]["recent_scans"]
    assert observer_recent_scans
    assert observer_recent_scans[0]["receipt_id"] == receipt_id
    assert observer_recent_scans[0]["decision"] == "urgent_review"
    assert observer_recent_scans[0]["anomaly"]["level"] == "error"
    assert observer_recent_scans[0]["trace_id"] == observer_scan_body["receipt"]["trace_id"]
    assert observer_recent_scans[0]["run_id"] == observer_scan_body["receipt"]["run_id"]
    recent_blocked_focus = next(
        item for item in observer_recent_scans[0]["focus"] if item["id"] == "governance.blocked_tasks"
    )
    assert recent_blocked_focus["observed_at"] > 0
    assert (
        next(item for item in observer_recent_scans[0]["probe_statuses"] if item["id"] == "task_runtime")["status"]
        == "attention"
    )
    assert "task_runtime" in observer_recent_scans[0]["probes"]
    assert body["mission_status_counts"]["completed"] == 1
    assert body["recent_missions"][0]["id"] in {blocked_id, completed_id}
    assert body["operator"]["available"] is True
    assert body["operator"]["focus"]["plane_id"] == "P3_GOVERNANCE"
    assert body["orb"]["available"] is True
    assert body["orb"]["state"]["render_state"] == "handback"
    assert body["orb"]["state"]["handback_state"]["focus"]["id"] == blocked_id
    recent_completed = body["briefing"]["recently_completed"]
    assert recent_completed
    assert recent_completed[0]["id"] == completed_id


def test_continuity_briefing_surfaces_dependency_blocker_context(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    dependency = client.post(
        "/missions/create",
        json={
            "objective": "Complete prerequisite research",
            "summary": "The dependent mission must wait for this work.",
            "requester_id": "test.continuity.dependencies",
            "status": "active",
            "priority": 1,
        },
    )
    assert dependency.status_code == 200
    dependency_id = str(dependency.json()["mission_id"])

    dependent = client.post(
        "/missions/create",
        json={
            "objective": "Proceed only after research completes",
            "summary": "Briefing should expose the declared blocker.",
            "requester_id": "test.continuity.dependencies",
            "dependency_ids": [dependency_id],
            "escalation_path": "Ask the operator whether to replace or deadletter the dependency.",
            "priority": 9,
        },
    )
    assert dependent.status_code == 200
    dependent_id = str(dependent.json()["mission_id"])

    response = client.get("/continuity/briefing")
    assert response.status_code == 200

    body = response.json()
    assert body["ok"] is True
    assert "dependencies" in body["briefing"]["headline"].lower()
    assert body["briefing"]["counts"]["dependency_waiting"] == 1

    focus = body["briefing"]["focus"][0]
    assert focus["id"] == dependent_id
    assert focus["recommended_action"] == "wait_for_dependency"
    assert focus["action_target_id"] == dependency_id
    assert focus["advance"]["eligible"] is False
    assert focus["advance"]["action"] == "wait_for_dependency"
    assert focus["advance"]["target_id"] == dependency_id
    assert focus["dependency_ids"] == [dependency_id]
    assert focus["dependency_count"] == 1
    assert focus["dependency_state"]["status"] == "waiting"
    assert focus["dependency_state"]["first_unresolved"]["id"] == dependency_id
    assert focus["escalation_path"] == "Ask the operator whether to replace or deadletter the dependency."

    mission_readiness_by_id = {item["id"]: item for item in body["briefing"]["readiness"]["criteria"]}
    reconstruction = mission_readiness_by_id["reconstruction_reduced"]
    assert reconstruction["status"] == "satisfied"
    assert dependent_id in reconstruction["evidence"]["dependency_context_ids"]


def test_continuity_briefing_marks_clean_deadletter_readiness(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Deadletter mission for readiness",
            "summary": "Deadletter state should remain inspectable in continuity.",
            "requester_id": "test.continuity.deadletter",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

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

    operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "deadletter readiness blocker",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert operation.status_code == 200
    operation_id = str(operation.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.continuity.deadletter"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={
            "reason": "operator_abandoned_after_governance_hold",
            "actor": "test.continuity.deadletter",
            "note": "deadletter readiness verification",
        },
    )
    assert deadlettered.status_code == 200
    assert deadlettered.json()["ok"] is True

    response = client.get("/continuity/briefing")
    assert response.status_code == 200

    body = response.json()
    assert body["briefing"]["counts"]["deadlettered"] == 1
    assert body["briefing"]["deadletter_preview"][0]["id"] == mission_id
    assert body["briefing"]["deadletter_preview"][0]["recommended_action"] == "review_deadletter"
    assert body["briefing"]["deadletter_preview"][0]["last_task_id"] == operation_id
    assert body["briefing"]["deadletter_preview"][0]["last_task_status"] == "accepted"
    assert body["briefing"]["deadletter_preview"][0]["last_task_result_status"] == "blocked"
    assert body["briefing"]["deadletter_preview"][0]["last_task_gate"] == "trust_gate"
    assert body["briefing"]["deadletter_preview"][0]["history_count"] >= 1
    assert body["briefing"]["deadletter_preview"][0]["latest_history_event"] in {"status_changed", "continuity_updated"}
    assert body["briefing"]["deadletter_preview"][0]["latest_history_ts"]
    assert body["briefing"]["deadletter_preview"][0]["latest_activity"]["name"] == "governance_hold"
    assert body["briefing"]["deadletter_preview"][0]["latest_activity"]["status"] == "blocked"
    mission_readiness_by_id = {item["id"]: item for item in body["briefing"]["readiness"]["criteria"]}
    assert mission_readiness_by_id["deadletter_cleanly"]["status"] == "satisfied"
    assert mission_readiness_by_id["deadletter_cleanly"]["evidence"]["sampled_deadletter_ids"] == [mission_id]
    assert mission_readiness_by_id["deadletter_cleanly"]["evidence"]["missing_reason_ids"] == []
    assert mission_readiness_by_id["deadletter_cleanly"]["evidence"]["missing_history_ids"] == []


def test_continuity_briefing_surfaces_exact_pending_approval_context(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_repo_scaffold(repo_root)

    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/reviewable",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Approval-bound deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    trust = client.post("/trust/set", json={"level": 6, "reason": "allow approval-bound continuity test"})
    assert trust.status_code == 200
    assert trust.json()["ok"] is True

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Continuity briefing should carry exact approval context.",
            "summary": "Blocked mission should name the pending approval.",
            "priority": 9,
            "requester_id": "test.continuity.approval_projection",
        },
    )
    assert blocked.status_code == 200
    blocked_id = str(blocked.json()["mission_id"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "continuity approval projection",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert operation.status_code == 200
    operation_id = str(operation.json()["operation_id"])

    pending = client.post(
        f"/operations/{operation_id}/run",
        json={"worker_id": "test.continuity.approval_projection"},
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    response = client.get("/continuity/briefing")
    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True

    focus_item = next(item for item in body["briefing"]["focus"] if item["id"] == blocked_id)
    assert focus_item["recommended_action"] == "review_pending_approval"
    assert focus_item["advance"]["eligible"] is False
    assert focus_item["advance"]["action"] == "review_pending_approval"
    assert focus_item["advance"]["target_id"] == operation_id
    assert focus_item["last_task_approval_id"] == approval_id
    assert focus_item["last_task_approval_status"] == "pending"
    assert focus_item["operator_hint"] == f"Approval {approval_id} is pending before the mission can continue."

    recent_item = next(item for item in body["recent_missions"] if item["id"] == blocked_id)
    assert recent_item["last_task_id"] == operation_id
    assert recent_item["last_task_gate"] == "approvals_gate"
    assert recent_item["last_task_approval_id"] == approval_id
    assert recent_item["last_task_approval_status"] == "pending"
