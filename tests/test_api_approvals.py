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
