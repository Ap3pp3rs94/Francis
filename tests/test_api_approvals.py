from __future__ import annotations

import json
from pathlib import Path

_APPROVAL_ACTOR = "test.approvals.decision"
_PLUGIN_ACTOR = "test.plugins.write"


def test_approval_decision_requires_local_client(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.delenv("FRANCIS_APPROVALS_ALLOW_REMOTE_DECISIONS", raising=False)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    app = create_app()
    approval = approvals.request("plugin.run", "integration_test", {"plugin_id": "builtin.echo"})
    approval_id = str(approval["id"])

    remote_client = TestClient(app, client=("198.51.100.5", 4321))
    blocked = remote_client.post(
        "/approvals/decision",
        json={"id": approval_id, "action": "approve", "actor": _APPROVAL_ACTOR},
    )
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "approval decisions require a local caller"

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()

    local_client = TestClient(app)
    missing_actor = local_client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert missing_actor.status_code == 200
    missing_actor_body = missing_actor.json()
    assert missing_actor_body["ok"] is False
    assert missing_actor_body["status"] == "denied"
    assert missing_actor_body["error"] == "api_permission_denied"
    assert missing_actor_body["governance"]["gate"] == "permission_gate"
    assert missing_actor_body["governance"]["reason"] == "missing_actor"
    assert pending_path.exists()

    approved = local_client.post(
        "/approvals/decision",
        json={"id": approval_id, "action": "approve", "actor": _APPROVAL_ACTOR},
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"
    assert approved_body["item"]["decision_actor"] == _APPROVAL_ACTOR


def test_approval_reason_and_decision_comment_redact_secrets(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_reason_secret = "approvalreasonsecret123"
    requested = client.post(
        "/approvals/request",
        json={
            "action": "plugin.run",
            "reason": f"operator note password={raw_reason_secret}",
            "payload": {"plugin_id": "builtin.echo"},
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    approval_id = str(requested_body["id"])
    assert requested_body["reason"] == "operator note password=[REDACTED:secret]"

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    pending_payload = json.loads(pending_path.read_text(encoding="utf-8"))
    assert pending_payload["reason"] == "operator note password=[REDACTED:secret]"
    assert raw_reason_secret not in pending_path.read_text(encoding="utf-8")

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)
    assert listed_item["reason"] == "operator note password=[REDACTED:secret]"

    raw_comment_secret = "approvalcommentsecret456"
    approved = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": _APPROVAL_ACTOR,
            "comment": f"reviewed token={raw_comment_secret}",
        },
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    assert approved_body["item"]["decision_actor"] == _APPROVAL_ACTOR
    assert approved_body["item"]["comment"] == "reviewed token=[REDACTED:secret]"

    approved_path = data_root / "approvals" / "approved" / f"{approval_id}.json"
    approved_payload = json.loads(approved_path.read_text(encoding="utf-8"))
    assert approved_payload["reason"] == "operator note password=[REDACTED:secret]"
    assert approved_payload["decision_actor"] == _APPROVAL_ACTOR
    assert approved_payload["comment"] == "reviewed token=[REDACTED:secret]"
    approved_text = approved_path.read_text(encoding="utf-8")
    assert raw_reason_secret not in approved_text
    assert raw_comment_secret not in approved_text


def test_approval_api_redacts_sealed_payload_digests(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_secret = "approvaldigestsecret123"
    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "approval list digest redaction",
            "input": {"user_command": f"echo password={raw_secret}", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.approvals.digest_redaction"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    persisted_text = (data_root / "approvals" / "pending" / f"{approval_id}.json").read_text(encoding="utf-8")
    assert raw_secret not in persisted_text
    assert "hmac-sha256:" in persisted_text

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)
    listed_text = json.dumps(listed_item, sort_keys=True)
    assert raw_secret not in listed_text
    assert "hmac-sha256:" not in listed_text
    assert listed_item["payload"]["user_command"] == "echo password=[REDACTED:secret]"

    approved = client.post(
        "/approvals/decision",
        json={"id": approval_id, "action": "approve", "actor": _APPROVAL_ACTOR},
    )
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    decision_text = json.dumps(approved_body["item"], sort_keys=True)
    assert raw_secret not in decision_text
    assert "hmac-sha256:" not in decision_text
    assert approved_body["item"]["payload"]["user_command"] == "echo password=[REDACTED:secret]"


def test_approval_list_surfaces_linked_operation_gate_handles(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Approval list should point back to the held mission operation.",
            "summary": "A governed operation should be reviewable from the approval queue.",
            "next_step": "Approve the exact action and rerun the linked operation.",
            "requester_id": "test.approvals.loop_handles",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "approval projection operation linkage",
            "mission_id": mission_id,
            "input": {"user_command": "echo approval projection", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.approvals.loop_handles"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["status"] == "queued"
    approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert approval_id

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)

    assert listed_item["operation_id"] == operation_id
    assert listed_item["operation_name"] == "codex.supervised_exec"
    assert listed_item["operation_plane"] == "P3_GOVERNANCE"
    assert listed_item["mission_id"] == mission_id
    assert listed_item["operation_status"] == "queued"
    assert listed_item["operation_result_status"] == "needs_approval"
    assert listed_item["gate"] == "approvals_gate"
    assert listed_item["next_step"] == "approve_exact_action"
    assert listed_item["run_id"] == approval_id
    artifact_dir = Path(str(listed_item["artifact_dir"]))
    assert artifact_dir.name == approval_id
    assert artifact_dir.parent.name == "supervised_exec"


def test_approval_list_preserves_metadata_only_loop_handles(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    approval = approvals.request("plugin.run", "metadata loop handles", {"plugin_id": "plugin.meta"})
    approval_id = str(approval["id"])
    operation_id = "tsk_approval_metadata_handles"
    mission_id = "mission_approval_metadata_handles"
    trace_id = "trace_approval_metadata_handles"
    run_id = "run_approval_metadata_handles"
    artifact_dir = str(data_root / "artifacts" / "metadata" / run_id)

    task_dir = data_root / "tasks" / operation_id
    task_dir.mkdir(parents=True)
    (task_dir / "record.json").write_text(
        json.dumps(
            {
                "task_id": operation_id,
                "status": "pending",
                "capability": "plugin.run",
                "requester_id": "test.approvals.metadata_handles",
                "created_at": "2024-03-09T16:00:00+00:00",
                "updated_at": "2024-03-09T16:00:01+00:00",
                "inputs": {
                    "meta": {
                        "approval_id": approval_id,
                        "mission_id": mission_id,
                        "run_id": run_id,
                        "artifact_dir": artifact_dir,
                        "advance_action": "run_linked_operation",
                    }
                },
                "meta": {
                    "trace_id": trace_id,
                },
                "result": {
                    "data": {
                        "status": "needs_approval",
                        "governance": {
                            "gate": "approvals_gate",
                            "next_step": "approve_exact_action",
                        },
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    client = TestClient(create_app())

    listed = client.get("/approvals/list?status=pending&limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == approval_id)

    assert listed_item["operation_id"] == operation_id
    assert listed_item["operation_name"] == "plugin.run"
    assert listed_item["operation_plane"] == "P3_GOVERNANCE"
    assert listed_item["advance_action"] == "run_linked_operation"
    assert listed_item["mission_id"] == mission_id
    assert listed_item["operation_status"] == "queued"
    assert listed_item["operation_result_status"] == "needs_approval"
    assert listed_item["gate"] == "approvals_gate"
    assert listed_item["next_step"] == "approve_exact_action"
    assert listed_item["trace_id"] == trace_id
    assert listed_item["run_id"] == run_id
    assert listed_item["artifact_dir"] == artifact_dir


def test_approval_list_surfaces_refresh_lineage_and_payload_summary(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/reviewable",
            "actor": _PLUGIN_ACTOR,
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

    trust = client.post(
        "/trust/set",
        json={"level": 6, "reason": "allow approval-bound approvals-list test", "actor": "test.trust.write"},
    )
    assert trust.status_code == 200
    assert trust.json()["ok"] is True

    pending = client.post("/plugins/run", json={"id": plugin_id, "action": "deploy", "input": {"target": "prod"}})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    first_approval_id = str(pending_body["approval_id"])
    assert first_approval_id

    approved = client.post(
        "/approvals/decision",
        json={"id": first_approval_id, "action": "approve", "actor": _APPROVAL_ACTOR},
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/plugins/run",
        json={"id": plugin_id, "action": "deploy", "approval_id": first_approval_id, "input": {"target": "staging"}},
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    refreshed_approval_id = str(mismatched_body["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != first_approval_id

    approvals_list = client.get("/approvals/list?status=pending&limit=20")
    assert approvals_list.status_code == 200
    approvals_body = approvals_list.json()
    refreshed_item = next(item for item in approvals_body["items"] if item["id"] == refreshed_approval_id)

    assert refreshed_item["action"] == "plugin.run"
    assert refreshed_item["status"] == "pending"
    assert refreshed_item["request_kind"] == "plugin.run.request"
    assert refreshed_item["previous_approval_id"] == first_approval_id
    assert refreshed_item["previous_approval_status"] == "approved"
    assert refreshed_item["replacement_kind"] == "plugin.run.mismatch"
    assert refreshed_item["replacement_reason"] == "approval_payload_mismatch"
    assert refreshed_item["replacement_expected_payload_keys"] == [
        "action",
        "idempotency_key",
        "input",
        "meta",
        "plugin_id",
        "required_trust",
        "risk_tier",
    ]
    assert refreshed_item["replacement_previous_payload_keys"] == [
        "action",
        "idempotency_key",
        "input",
        "meta",
        "plugin_id",
        "required_trust",
        "risk_tier",
    ]
    assert refreshed_item["replacement_changed_keys"] == ["input"]
    assert refreshed_item["payload_summary"]["plugin_id"] == plugin_id
    assert refreshed_item["payload_summary"]["requested_action"] == "deploy"
    assert refreshed_item["payload_summary"]["risk_tier"] == "critical"
    assert refreshed_item["payload_summary"]["required_trust"] == 5
    assert refreshed_item["payload_summary"]["input_keys"] == ["target"]
    assert "plugin_id" in refreshed_item["payload_summary"]["payload_keys"]


def test_approval_list_surfaces_credential_request_and_revoke_context(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    requested = client.post(
        "/credentials/request",
        json={
            "scope_id": "openai_readonly",
            "provider": "openai",
            "type": "api_key",
            "label": "OpenAI Queue Visibility",
            "reason": "integration_test",
            "actor": "test.credentials.write",
            "meta": {"ticket": "FR-901"},
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["ok"] is True
    credential_id = str(requested_body["id"])
    request_approval_id = str(requested_body["approval_id"])

    approvals_list = client.get("/approvals/list?status=pending&limit=20")
    assert approvals_list.status_code == 200
    request_item = next(item for item in approvals_list.json()["items"] if item["id"] == request_approval_id)
    assert request_item["action"] == "credential.request"
    assert request_item["status"] == "pending"
    assert request_item["request_kind"] == "credential.request.request"
    assert request_item["payload_summary"]["scope_id"] == "openai_readonly"
    assert request_item["payload_summary"]["provider"] == "openai"
    assert request_item["payload_summary"]["credential_type"] == "api_key"
    assert request_item["payload_summary"]["label"] == "OpenAI Queue Visibility"
    assert request_item["payload_summary"]["credential_id"] == credential_id

    approved_request = client.post(
        "/approvals/decision",
        json={"id": request_approval_id, "action": "approve", "actor": _APPROVAL_ACTOR},
    )
    assert approved_request.status_code == 200
    assert approved_request.json()["ok"] is True

    listed_active = client.get("/credentials/list?status=active")
    assert listed_active.status_code == 200
    active_items = [item for item in listed_active.json()["items"] if item.get("id") == credential_id]
    assert len(active_items) == 1

    revoked = client.post(
        "/credentials/revoke",
        json={"id": credential_id, "reason": "cleanup", "actor": "test.credentials.write"},
    )
    assert revoked.status_code == 200
    revoked_body = revoked.json()
    assert revoked_body["ok"] is True
    revoke_approval_id = str(revoked_body["approval_id"])

    approvals_list = client.get("/approvals/list?status=pending&limit=20")
    assert approvals_list.status_code == 200
    revoke_item = next(item for item in approvals_list.json()["items"] if item["id"] == revoke_approval_id)
    assert revoke_item["action"] == "credential.revoke"
    assert revoke_item["status"] == "pending"
    assert revoke_item["request_kind"] == "credential.revoke.request"
    assert revoke_item["payload_summary"]["scope_id"] == "openai_readonly"
    assert revoke_item["payload_summary"]["provider"] == "openai"
    assert revoke_item["payload_summary"]["credential_id"] == credential_id


def test_approval_list_surfaces_exact_action_context_for_industrial_request(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    asset_created = client.post(
        "/industrial/assets", json={"name": "Queue Compressor", "asset_type": "compressor", "risk": "high"}
    )
    assert asset_created.status_code == 200
    asset_id = str(asset_created.json()["id"])

    pending = client.post(
        "/industrial/interventions/request",
        json={
            "target_kind": "asset",
            "target_id": asset_id,
            "action": "dispatch_crew",
            "reason": "operator_request",
            "dry_run": False,
            "risk": "high",
            "domain": "operations",
            "actor": "operator:queue",
            "params": {"crew": "alpha"},
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    approval_id = str(pending_body["approval_id"])

    approvals_list = client.get("/approvals/list?status=pending&limit=20")
    assert approvals_list.status_code == 200
    approval_item = next(item for item in approvals_list.json()["items"] if item["id"] == approval_id)

    assert approval_item["action"] == "industrial.intervention.request"
    assert approval_item["status"] == "pending"
    assert approval_item["request_kind"] == "industrial.approval.request"
    assert approval_item["payload_summary"]["requested_action"] == "dispatch_crew"
    assert approval_item["payload_summary"]["target_kind"] == "asset"
    assert approval_item["payload_summary"]["target_id"] == asset_id
    assert approval_item["payload_summary"]["risk"] == "high"
    assert approval_item["payload_summary"]["domain"] == "operations"
    assert approval_item["payload_summary"]["actor"] == "operator:queue"
    assert approval_item["payload_summary"]["dry_run"] is False
    assert approval_item["payload_summary"]["params_keys"] == ["crew"]
    assert "target_id" in approval_item["payload_summary"]["payload_keys"]
