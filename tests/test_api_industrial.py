from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def test_industrial_lifecycle_runs_safety_and_interventions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    health = client.get("/industrial/health")
    assert health.status_code == 200
    health_body = health.json()
    assert health_body["ok"] is True
    assert health_body["status"] == "ready"

    asset_created = client.post(
        "/industrial/assets",
        json={
            "name": "Pump A",
            "asset_type": "pump",
            "risk": "medium",
            "tags": ["plant", "critical"],
            "meta": {"domain": "energy"},
        },
    )
    assert asset_created.status_code == 200
    asset_body = asset_created.json()
    assert asset_body["ok"] is True
    asset_id = str(asset_body["id"])

    asset_get = client.get(f"/industrial/assets/{asset_id}")
    assert asset_get.status_code == 200
    assert asset_get.json()["item"]["name"] == "Pump A"

    asset_list = client.get("/industrial/assets?asset_type=pump&tags=plant")
    assert asset_list.status_code == 200
    assert any(str(item.get("id")) == asset_id for item in asset_list.json()["items"])

    asset_updated = client.patch(f"/industrial/assets/{asset_id}", json={"status": "maintenance", "location": "line-1"})
    assert asset_updated.status_code == 200
    assert asset_updated.json()["item"]["status"] == "maintenance"
    assert asset_updated.json()["item"]["location"] == "line-1"

    process_created = client.post(
        "/industrial/processes",
        json={
            "name": "Cooling Loop",
            "risk": "high",
            "inputs": ["water_in"],
            "outputs": ["water_out"],
            "tags": ["safety"],
        },
    )
    assert process_created.status_code == 200
    process_id = str(process_created.json()["id"])

    sim_created = client.post(
        "/industrial/simulations",
        json={
            "name": "Pump Stress Sim",
            "engine": "numpy",
            "asset_id": asset_id,
            "process_id": process_id,
            "default_params": {"duration_s": 60},
        },
    )
    assert sim_created.status_code == 200
    sim_id = str(sim_created.json()["id"])

    run_started = client.post(
        "/industrial/runs/start",
        json={
            "simulation_id": sim_id,
            "reason": "integration_test",
            "params": {"pressure": 42},
            "dry_run": False,
        },
    )
    assert run_started.status_code == 200
    run_started_body = run_started.json()
    assert run_started_body["ok"] is True
    run_id = str(run_started_body["id"])
    assert run_started_body["run"]["status"] in {"running", "succeeded"}

    run_fetched = client.get(f"/industrial/runs/{run_id}")
    assert run_fetched.status_code == 200
    assert run_fetched.json()["ok"] is True
    assert run_fetched.json()["item"]["simulation_id"] == sim_id

    run_cancelled = client.post(f"/industrial/runs/{run_id}/cancel", json={"reason": "stop_test"})
    assert run_cancelled.status_code == 200
    run_cancelled_body = run_cancelled.json()
    assert run_cancelled_body["ok"] is True
    assert run_cancelled_body["status"] in {"running", "succeeded", "failed", "canceled"}

    safety = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "precheck",
            "dry_run": True,
            "params": {"risk": "medium"},
        },
    )
    assert safety.status_code == 200
    safety_body = safety.json()
    assert safety_body["ok"] is True
    assert safety_body["validation"]["target_id"] == asset_id
    assert safety_body["validation"]["status"] in {"warn", "pass", "fail", "unknown"}

    safety_list = client.get("/industrial/safety/validations?target_kind=asset")
    assert safety_list.status_code == 200
    assert any(str(item.get("target_id")) == asset_id for item in safety_list.json()["items"])

    intervention_request = client.post(
        "/industrial/interventions/request",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "calibrate",
            "reason": "operator_request",
            "dry_run": True,
            "risk": "medium",
        },
    )
    assert intervention_request.status_code == 200
    intervention_request_body = intervention_request.json()
    assert intervention_request_body["ok"] is True
    assert intervention_request_body["status"] == "pending"
    assert intervention_request_body["request_id"]
    assert intervention_request_body["approval_id"]

    intervention_execute = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "set_setpoint",
            "reason": "safe_dry_run",
            "dry_run": True,
            "risk": "low",
            "params": {"setpoint": 7},
        },
    )
    assert intervention_execute.status_code == 200
    intervention_execute_body = intervention_execute.json()
    assert intervention_execute_body["ok"] is True
    assert intervention_execute_body["status"] in {"dry_run", "executed", "pending"}

    telemetry = client.get(f"/industrial/telemetry?source_id={sim_id}&limit=50")
    assert telemetry.status_code == 200
    telemetry_body = telemetry.json()
    assert isinstance(telemetry_body.get("items"), list)
    assert telemetry_body["total"] >= 1

    sim_deleted = client.request("DELETE", f"/industrial/simulations/{sim_id}", json={"reason": "cleanup"})
    process_deleted = client.request("DELETE", f"/industrial/processes/{process_id}", json={"reason": "cleanup"})
    asset_deleted = client.request("DELETE", f"/industrial/assets/{asset_id}", json={"reason": "cleanup"})
    assert sim_deleted.status_code == 200
    assert process_deleted.status_code == 200
    assert asset_deleted.status_code == 200
    assert sim_deleted.json()["ok"] is True
    assert process_deleted.json()["ok"] is True
    assert asset_deleted.json()["ok"] is True

    status = client.get("/industrial/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["counts"]["runs"] >= 1


def test_industrial_digital_twin_aliases_and_run_export(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Twin Asset", "asset_type": "asset", "risk": "low"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    sim_created = client.post("/industrial/simulations", json={"name": "Twin Sim", "asset_id": asset_id})
    assert sim_created.status_code == 200
    sim_id = str(sim_created.json()["id"])

    run_started = client.post("/industrial/runs/start", json={"simulation_id": sim_id, "dry_run": True})
    assert run_started.status_code == 200
    run_id = str(run_started.json()["id"])

    twins = client.get("/industrial/digital_twins/list")
    assert twins.status_code == 200
    twins_body = twins.json()
    assert isinstance(twins_body.get("items"), list)
    assert any(str(item.get("id")) == asset_id for item in twins_body["items"])

    twin_get = client.get(f"/industrial/digital_twins/get?id={asset_id}")
    assert twin_get.status_code == 200
    twin_get_body = twin_get.json()
    assert twin_get_body["ok"] is True
    assert twin_get_body["item"]["id"] == asset_id

    twin_snapshot = client.get(f"/industrial/digital_twins/snapshot?id={asset_id}")
    assert twin_snapshot.status_code == 200
    twin_snapshot_body = twin_snapshot.json()
    assert twin_snapshot_body["ok"] is True
    assert twin_snapshot_body["snapshot"]["id"] == asset_id
    assert "state" in twin_snapshot_body["snapshot"]

    twin_action = client.post(
        "/industrial/digital_twins/action",
        json={"twin_id": asset_id, "action": "validate_safety", "reason": "alias_flow"},
    )
    assert twin_action.status_code == 200
    twin_action_body = twin_action.json()
    assert twin_action_body["ok"] is True
    assert twin_action_body["twin_id"] == asset_id

    export_json = client.get("/industrial/runs/export?format=json")
    assert export_json.status_code == 200
    export_json_body = export_json.json()
    assert isinstance(export_json_body.get("items"), list)
    assert any(str(item.get("id")) == run_id for item in export_json_body["items"])

    export_csv = client.get("/industrial/runs/export?format=csv")
    assert export_csv.status_code == 200
    assert export_csv.headers["content-type"].startswith("text/csv")
    parsed = list(csv.DictReader(io.StringIO(export_csv.text)))
    assert any(str(row.get("id")) == run_id for row in parsed)

    registry_path = data_root / "industrial" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry.get("assets"), dict)
    assert isinstance(registry.get("runs"), dict)
    assert isinstance(registry.get("telemetry"), list)


def test_industrial_execute_refreshes_mismatched_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Critical Pump", "asset_type": "pump", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "shutdown",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:a",
            "params": {"mode": "safe"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    intervention_id = str(pending_body["intervention_id"])
    assert approval_id
    assert intervention_id

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "shutdown",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:b",
            "params": {"mode": "safe"},
            "approval_id": approval_id,
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatched_body["previous_approval_id"] == approval_id
    assert mismatched_body["intervention_id"] == intervention_id
    artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "shutdown",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:b",
            "params": {"mode": "safe"},
            "approval_id": refreshed_approval_id,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "executed"
    assert executed_body["approval_id"] == refreshed_approval_id
    assert executed_body["intervention_id"] == intervention_id
    assert executed_body["result_id"]

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    interventions = [item for item in registry.get("interventions", []) if str(item.get("id")) == intervention_id]
    assert len(interventions) == 1
    assert interventions[0]["status"] == "executed"
    assert interventions[0]["approval_id"] == refreshed_approval_id


def test_industrial_execute_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Valve Bank", "asset_type": "valve", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "vent_pressure",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:a",
            "params": {"psi": 12},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    intervention_id = str(pending_body["intervention_id"])
    assert approval_id
    assert intervention_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    refreshed = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "vent_pressure",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:a",
            "params": {"psi": 12},
            "approval_id": approval_id,
        },
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["ok"] is False
    assert refreshed_body["status"] == "needs_approval"
    assert refreshed_body["error"] == "approval_not_found"
    refreshed_approval_id = str(refreshed_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert refreshed_body["previous_approval_id"] == approval_id
    assert refreshed_body["intervention_id"] == intervention_id
    artifact_dir = Path(str(refreshed_body["artifact_dir"]))
    assert (artifact_dir / "error.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(
        "/industrial/interventions/execute",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "vent_pressure",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "actor": "operator:a",
            "params": {"psi": 12},
            "approval_id": refreshed_approval_id,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "executed"
    assert executed_body["approval_id"] == refreshed_approval_id
    assert executed_body["intervention_id"] == intervention_id
    assert executed_body["result_id"]

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    interventions = [item for item in registry.get("interventions", []) if str(item.get("id")) == intervention_id]
    assert len(interventions) == 1
    assert interventions[0]["status"] == "executed"
    assert interventions[0]["approval_id"] == refreshed_approval_id


def test_industrial_safety_validate_refreshes_mismatched_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Boiler A", "asset_type": "boiler", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high", "window": "short"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "warn"
    approval_id = str(pending_body["approval_id"])
    validation_id = str(pending_body["id"])
    assert approval_id
    assert validation_id

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high", "window": "extended"},
            "approval_id": approval_id,
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatched_body["previous_approval_id"] == approval_id
    assert mismatched_body["id"] == validation_id
    artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    validated = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high", "window": "extended"},
            "approval_id": refreshed_approval_id,
        },
    )
    assert validated.status_code == 200
    validated_body = validated.json()
    assert validated_body["ok"] is True
    assert validated_body["status"] == "pass"
    assert validated_body["approval_id"] == refreshed_approval_id
    assert validated_body["id"] == validation_id

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validation = registry.get("safety_validations", {}).get(validation_id)
    assert isinstance(validation, dict)
    assert validation["status"] == "pass"
    assert validation["meta"]["approval_id"] == refreshed_approval_id
    assert validation["meta"]["previous_approval_id"] == approval_id


def test_industrial_safety_validate_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Boiler B", "asset_type": "boiler", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "warn"
    approval_id = str(pending_body["approval_id"])
    validation_id = str(pending_body["id"])
    assert approval_id
    assert validation_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    refreshed = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high"},
            "approval_id": approval_id,
        },
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["ok"] is False
    assert refreshed_body["status"] == "needs_approval"
    assert refreshed_body["error"] == "approval_not_found"
    refreshed_approval_id = str(refreshed_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert refreshed_body["previous_approval_id"] == approval_id
    assert refreshed_body["id"] == validation_id
    artifact_dir = Path(str(refreshed_body["artifact_dir"]))
    assert (artifact_dir / "request.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    validated = client.post(
        "/industrial/safety/validate",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "reason": "preflight",
            "dry_run": False,
            "params": {"risk": "high"},
            "approval_id": refreshed_approval_id,
        },
    )
    assert validated.status_code == 200
    validated_body = validated.json()
    assert validated_body["ok"] is True
    assert validated_body["status"] == "pass"
    assert validated_body["approval_id"] == refreshed_approval_id
    assert validated_body["id"] == validation_id

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    validation = registry.get("safety_validations", {}).get(validation_id)
    assert isinstance(validation, dict)
    assert validation["status"] == "pass"
    assert validation["meta"]["approval_id"] == refreshed_approval_id
    assert validation["meta"]["previous_approval_id"] == approval_id


def test_industrial_digital_twin_action_refreshes_mismatched_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Twin Controller", "asset_type": "controller", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "manual"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    action_id = str(pending_body["action_id"])
    assert approval_id
    assert action_id

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "override"},
            "approval_id": approval_id,
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatched_body["previous_approval_id"] == approval_id
    assert mismatched_body["action_id"] == action_id
    artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    approved_action = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "override"},
            "approval_id": refreshed_approval_id,
        },
    )
    assert approved_action.status_code == 200
    approved_body = approved_action.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"
    assert approved_body["approval_id"] == refreshed_approval_id
    assert approved_body["action_id"] == action_id

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    actions = [item for item in registry.get("digital_twin_actions", []) if str(item.get("id")) == action_id]
    assert len(actions) == 1
    assert actions[0]["status"] == "approved"
    assert actions[0]["approval_id"] == refreshed_approval_id
    assert actions[0]["previous_approval_id"] == approval_id


def test_industrial_digital_twin_action_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post("/industrial/assets", json={"name": "Twin Controller B", "asset_type": "controller", "risk": "high"})
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "manual"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    action_id = str(pending_body["action_id"])
    assert approval_id
    assert action_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    refreshed = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "manual"},
            "approval_id": approval_id,
        },
    )
    assert refreshed.status_code == 200
    refreshed_body = refreshed.json()
    assert refreshed_body["ok"] is False
    assert refreshed_body["status"] == "needs_approval"
    assert refreshed_body["error"] == "approval_not_found"
    refreshed_approval_id = str(refreshed_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert refreshed_body["previous_approval_id"] == approval_id
    assert refreshed_body["action_id"] == action_id
    artifact_dir = Path(str(refreshed_body["artifact_dir"]))
    assert (artifact_dir / "error.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    approved_action = client.post(
        "/industrial/digital_twins/action",
        json={
            "twin_id": asset_id,
            "action": "request_control",
            "reason": "operator_request",
            "params": {"mode": "manual"},
            "approval_id": refreshed_approval_id,
        },
    )
    assert approved_action.status_code == 200
    approved_body = approved_action.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"
    assert approved_body["approval_id"] == refreshed_approval_id
    assert approved_body["action_id"] == action_id

    registry_path = data_root / "industrial" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    actions = [item for item in registry.get("digital_twin_actions", []) if str(item.get("id")) == action_id]
    assert len(actions) == 1
    assert actions[0]["status"] == "approved"
    assert actions[0]["approval_id"] == refreshed_approval_id
    assert actions[0]["previous_approval_id"] == approval_id
