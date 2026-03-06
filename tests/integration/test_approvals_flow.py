from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def test_approvals_request_list_and_decide() -> None:
    c = TestClient(app)

    requested = c.post(
        "/approvals/request",
        json={
            "action": "forge.promote",
            "reason": f"Need explicit approval for promote {uuid4()}",
            "metadata": {"source": "integration-test"},
        },
    )
    assert requested.status_code == 200
    approval = requested.json()["approval"]
    approval_id = approval["id"]
    assert approval["status"] == "pending"

    pending = c.get("/approvals", params={"status": "pending"})
    assert pending.status_code == 200
    pending_rows = pending.json()["approvals"]
    assert any(row.get("id") == approval_id for row in pending_rows)

    decision = c.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "approved", "note": "integration test approval"},
    )
    assert decision.status_code == 200
    assert decision.json()["decision"]["decision"] == "approved"

    fetched = c.get(f"/approvals/{approval_id}")
    assert fetched.status_code == 200
    fetched_approval = fetched.json()["approval"]
    assert fetched_approval["status"] == "approved"


def test_approvals_decision_rbac_denies_observer() -> None:
    c = TestClient(app)
    requested = c.post(
        "/approvals/request",
        json={"action": "forge.promote", "reason": "rbac test"},
    )
    assert requested.status_code == 200
    approval_id = requested.json()["approval"]["id"]

    denied = c.post(
        f"/approvals/{approval_id}/decision",
        headers={"x-francis-role": "observer"},
        json={"decision": "approved"},
    )
    assert denied.status_code == 403
    assert "RBAC denied" in denied.json().get("detail", "")


def test_lens_pending_approvals_includes_approval_queue() -> None:
    c = TestClient(app)
    before = c.get("/lens/state")
    assert before.status_code == 200
    before_count = int(before.json().get("pending_approvals", 0))

    requested = c.post(
        "/approvals/request",
        json={"action": "forge.promote", "reason": "lens pending count"},
    )
    assert requested.status_code == 200

    after = c.get("/lens/state")
    assert after.status_code == 200
    after_count = int(after.json().get("pending_approvals", 0))
    assert after_count >= before_count + 1
