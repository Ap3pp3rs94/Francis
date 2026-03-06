from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

from apps.api.main import app


def _read_catalog() -> dict:
    path = Path(__file__).resolve().parents[2] / "workspace" / "forge" / "catalog.json"
    if not path.exists():
        return {"entries": []}
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"entries": []}
    if not isinstance(parsed, dict):
        return {"entries": []}
    return parsed


def test_forge_proposals_stage_and_promote() -> None:
    c = TestClient(app)

    p = c.get("/forge/proposals")
    assert p.status_code == 200
    p_payload = p.json()
    assert p_payload["status"] == "ok"
    assert isinstance(p_payload.get("proposals"), list)
    assert len(p_payload["proposals"]) >= 1

    name = f"Stage-{uuid4()}"
    stage = c.post(
        "/forge/stage",
        json={
            "name": name,
            "description": "Capability staged by integration test.",
            "rationale": "Validate forge flow.",
            "tags": ["test", "forge"],
            "risk_tier": "low",
        },
    )
    assert stage.status_code == 200
    stage_payload = stage.json()
    assert stage_payload["status"] == "ok"
    stage_id = stage_payload["stage_id"]
    assert stage_payload["entry"]["status"] == "staged"
    assert len(stage_payload["written_files"]) >= 2

    catalog = _read_catalog()
    entries = [e for e in catalog.get("entries", []) if isinstance(e, dict)]
    assert any(entry.get("id") == stage_id for entry in entries)

    promote_blocked = c.post(f"/forge/promote/{stage_id}")
    assert promote_blocked.status_code == 403
    detail = promote_blocked.json().get("detail", {})
    assert isinstance(detail, dict)
    approval_id = str(detail.get("approval_request_id", ""))
    assert approval_id

    approve = c.post(
        f"/approvals/{approval_id}/decision",
        json={"decision": "approved", "note": "Integration test approval for promote"},
    )
    assert approve.status_code == 200

    promote = c.post(f"/forge/promote/{stage_id}", headers={"x-approval-id": approval_id})
    assert promote.status_code == 200
    promoted = promote.json()["entry"]
    assert promoted["status"] == "active"


def test_forge_rbac_blocks_stage_for_observer() -> None:
    c = TestClient(app)
    response = c.post(
        "/forge/stage",
        headers={"x-francis-role": "observer"},
        json={"name": f"Denied-{uuid4()}", "description": "Should be denied."},
    )
    assert response.status_code == 403
    assert "RBAC denied" in response.json().get("detail", "")
