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
