from __future__ import annotations

from pathlib import Path
from typing import Any


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


def _criterion(body: dict[str, Any], criterion_id: str) -> dict[str, Any]:
    readiness = body.get("stage6_readiness") if isinstance(body.get("stage6_readiness"), dict) else {}
    criteria = readiness.get("criteria") if isinstance(readiness.get("criteria"), list) else []
    for item in criteria:
        if isinstance(item, dict) and item.get("id") == criterion_id:
            return item
    raise AssertionError(f"missing Stage 6 criterion: {criterion_id}")


def test_lens_status_projects_readonly_stage6_contract(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    response = client.get("/lens/status?limit=3")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "lens.status"
    assert body["read_only"] is True
    assert body["governance"] == {
        "gate": "lens_readback_only",
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
    }
    assert body["command_palette"]["status"] == "contract_ready"
    assert body["command_palette"]["summon_anywhere"] is False
    assert body["mode_selector"]["status"] == "readback_ready"
    assert body["pilot_indicator"]["status"] == "standby"
    assert body["stage6_readiness"]["claim"] == "backend_readback_contract_only"
    assert _criterion(body, "mode_visibility")["status"] == "readback_ready"
    assert _criterion(body, "approvals_view")["status"] == "readback_ready"
    assert _criterion(body, "incident_view")["status"] == "readback_ready"
    assert _criterion(body, "receipt_visibility")["status"] == "readback_ready"
    assert _criterion(body, "summon_anywhere")["status"] == "not_implemented"

    hud = client.get("/lens/hud")
    assert hud.status_code == 200
    assert hud.json()["kind"] == "lens.status"


def test_lens_status_surfaces_pending_approval_without_decision_authority(monkeypatch, tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    data_root = repo_root / "data"
    _write_dev_environment(repo_root)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    approval = client.post(
        "/approvals/request",
        json={
            "action": "operations.run",
            "reason": "prove Lens pending approval readback",
            "payload": {"mission_id": "mission-lens", "risk_tier": "normal"},
        },
    )
    assert approval.status_code == 200

    response = client.get("/lens/status")

    assert response.status_code == 200
    body = response.json()
    assert body["approvals_view"]["pending_count"] == 1
    assert body["approvals_view"]["status"] == "attention"
    assert body["approvals_view"]["items"][0]["status"] == "pending"
    assert body["approvals_view"]["items"][0]["action"] == "operations.run"
    assert body["approvals_view"]["items"][0]["payload_summary"]["risk_tier"] == "normal"
    assert body["governance"]["approval_decision_authority"] is False
    approval_badge = next(item for item in body["hud"]["badges"] if item["label"] == "approvals")
    assert approval_badge["value"] == 1
    assert approval_badge["severity"] == "attention"
