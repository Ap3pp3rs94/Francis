from __future__ import annotations

from pathlib import Path


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
    blocked = remote_client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert blocked.status_code == 403
    assert blocked.json()["detail"] == "approval decisions require a local caller"

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()

    local_client = TestClient(app)
    approved = local_client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    approved_body = approved.json()
    assert approved_body["ok"] is True
    assert approved_body["status"] == "approved"


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

    trust = client.post("/trust/set", json={"level": 6, "reason": "allow approval-bound approvals-list test"})
    assert trust.status_code == 200
    assert trust.json()["ok"] is True

    pending = client.post("/plugins/run", json={"id": plugin_id, "action": "deploy", "input": {"target": "prod"}})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    first_approval_id = str(pending_body["approval_id"])
    assert first_approval_id

    approved = client.post("/approvals/decision", json={"id": first_approval_id, "action": "approve"})
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

    approved_request = client.post("/approvals/decision", json={"id": request_approval_id, "action": "approve"})
    assert approved_request.status_code == 200
    assert approved_request.json()["ok"] is True

    listed_active = client.get("/credentials/list?status=active")
    assert listed_active.status_code == 200
    active_items = [item for item in listed_active.json()["items"] if item.get("id") == credential_id]
    assert len(active_items) == 1

    revoked = client.post("/credentials/revoke", json={"id": credential_id, "reason": "cleanup"})
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

    asset_created = client.post("/industrial/assets", json={"name": "Queue Compressor", "asset_type": "compressor", "risk": "high"})
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
