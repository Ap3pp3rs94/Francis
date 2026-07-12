from __future__ import annotations

import json
import os
import time
from pathlib import Path


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app()), data_root


def _write_supervisor_state(data_root: Path) -> None:
    path = data_root / "runtime" / "lens-host-supervisor" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "lens.host.supervisor_state",
                "status": "resident_supervising",
                "supervisor_pid": os.getpid(),
                "supervisor_process_alive": True,
            }
        ),
        encoding="utf-8",
    )


def _write_perception_state(data_root: Path, *, receipt_id: str) -> None:
    path = data_root / "runtime" / "lens-perception" / "status.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "kind": "lens.perception.runtime_state",
                "version": 1,
                "owner": "lens_supervisor",
                "state": "running",
                "updated_at": time.time(),
                "situation_model": {"status": "ready", "revision": "authority-integration"},
                "capture": {
                    "desktop": {
                        "authority_granted": True,
                        "active": True,
                        "receipt_id": receipt_id,
                        "source": "desktop_ring_buffer",
                    }
                },
            }
        ),
        encoding="utf-8",
    )


def test_perception_authority_grant_requires_an_approved_matching_request(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    requested = client.post(
        "/lens/perception/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request bounded desktop capture authority",
        },
    )
    assert requested.status_code == 200
    approval_id = requested.json()["approval_id"]

    blocked = client.post(
        "/lens/perception/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "attempt grant before approval",
        },
    )
    assert blocked.status_code == 200
    body = blocked.json()
    assert body["status"] == "blocked"
    assert body["authority_granted"] is False
    assert body["receipt_written"] is False
    assert body["executed"] is False
    assert "desktop_capture_authority_approval_not_approved" in body["blockers"]
    assert not (data_root / "runtime" / "lens-perception").exists()


def test_perception_authority_receipt_is_required_for_ready_runtime_readback(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)

    requested = client.post(
        "/lens/perception/authority/request",
        json={
            "actor": "test.system.write",
            "reason": "request bounded desktop capture authority",
        },
    )
    approval_id = requested.json()["approval_id"]
    decision = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": "test.approvals.decision",
            "comment": "approve desktop-only capture authority",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["status"] == "approved"

    granted = client.post(
        "/lens/perception/authority",
        json={
            "actor": "test.system.write",
            "approval_id": approval_id,
            "reason": "grant desktop-only capture authority lease",
            "lease_seconds": 120,
        },
    )
    assert granted.status_code == 200
    grant = granted.json()
    assert grant["status"] == "authority_granted"
    assert grant["authority_granted"] is True
    assert grant["capture_authority"] is True
    assert grant["new_sensing_authority"] is True
    assert grant["receipt_written"] is True
    assert grant["applied"] is True
    assert grant["executed"] is False
    assert grant["starts_capture"] is False
    assert grant["launches_process"] is False
    receipt = grant["receipt"]
    assert receipt["plane"] == "desktop"
    assert receipt["authorities"]["desktop_capture_authority"] is True
    assert receipt["authorities"]["camera_capture_authority"] is False
    assert receipt["authorities"]["keyboard_capture_authority"] is False
    assert receipt["authorities"]["user_mouse_capture_authority"] is False
    assert receipt["authorities"]["execution_authority"] is False
    assert receipt["authorities"]["memory_write"] is False
    assert not (data_root / "runtime" / "lens-perception").exists()

    authority_readback = client.get("/lens/perception/authority?limit=10").json()
    assert authority_readback["status"] == "authority_granted"
    assert authority_readback["active_authority_grant"]["receipt_id"] == receipt["receipt_id"]

    _write_supervisor_state(data_root)
    _write_perception_state(data_root, receipt_id=receipt["receipt_id"])
    ready = client.get("/lens/perception").json()
    assert ready["status"] == "ready"
    assert ready["ready"] is True
    assert ready["capture"]["desktop"]["authority_receipt"]["active"] is True
    assert ready["capture"]["desktop"]["authority_receipt"]["approval_id"] == approval_id

    receipt_path = data_root / "lens" / "perception_desktop_capture_authority_grants" / f"{receipt['receipt_id']}.json"
    tampered_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    tampered_receipt["authorities"]["camera_capture_authority"] = True
    receipt_path.write_text(json.dumps(tampered_receipt), encoding="utf-8")
    overbroad = client.get("/lens/perception").json()
    assert overbroad["ready"] is False
    assert "desktop_capture_authority_receipt_overbroad" in overbroad["blockers"]

    _write_perception_state(data_root, receipt_id="receipt-shaped-but-unresolved")
    blocked = client.get("/lens/perception").json()
    assert blocked["status"] == "blocked"
    assert blocked["ready"] is False
    assert blocked["capture"]["desktop"]["authority_receipt"]["active"] is False
    assert "desktop_capture_authority_receipt_not_found" in blocked["blockers"]
