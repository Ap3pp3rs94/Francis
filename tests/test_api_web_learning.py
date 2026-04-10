from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def test_web_learning_lifecycle_and_quarantine(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/web_learning/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["route"] == "web_learning"

    policy = client.get("/web_learning/policy")
    assert policy.status_code == 200
    policy_body = policy.json()
    assert policy_body["ok"] is True
    assert "policy" in policy_body

    disabled = client.post("/web_learning/enabled", json={"enabled": False, "reason": "maintenance"})
    assert disabled.status_code == 200
    disabled_body = disabled.json()
    assert disabled_body["ok"] is True
    assert disabled_body["enabled"] is False

    while_disabled = client.post("/web_learning/request", json={"url": "https://example.com/path"})
    assert while_disabled.status_code == 200
    while_disabled_body = while_disabled.json()
    assert while_disabled_body["ok"] is False
    assert while_disabled_body["status"] == "disabled"

    enabled = client.post("/web_learning/enabled", json={"enabled": True, "reason": "resume", "meta": {"force": True}})
    assert enabled.status_code == 200
    enabled_body = enabled.json()
    assert enabled_body["ok"] is True
    assert enabled_body["enabled"] is True

    blocked = client.post("/web_learning/request", json={"url": "https://localhost/private", "reason": "blocked_test"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is False
    assert blocked_body["status"] in {"blocked", "quarantined"}

    quarantine = client.get("/web_learning/quarantine")
    assert quarantine.status_code == 200
    quarantine_items = quarantine.json()["items"]
    assert isinstance(quarantine_items, list)
    assert quarantine_items
    quarantine_id = str(quarantine_items[0]["id"])

    release = client.post(f"/web_learning/quarantine/{quarantine_id}/decide", json={"action": "release", "reason": "manual_review"})
    assert release.status_code == 200
    release_body = release.json()
    assert release_body["ok"] is True
    assert release_body["applied"] is True

    learned = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.com/docs",
            "reason": "integration_test",
            "bytes": 1234,
            "meta": {"force": True},
        },
    )
    assert learned.status_code == 200
    learned_body = learned.json()
    assert learned_body["ok"] is True
    assert learned_body["status"] == "ingested"
    record_id = str(learned_body["record_id"])

    records = client.get("/web_learning/records?status=ingested")
    assert records.status_code == 200
    record_items = records.json()["items"]
    assert any(str(item.get("id")) == record_id for item in record_items)

    events = client.get("/web_learning/events")
    assert events.status_code == 200
    event_items = events.json()["items"]
    assert isinstance(event_items, list)
    assert any(str(item.get("kind")) in {"ingest", "fetch_end", "fetch_start"} for item in event_items)



def test_web_learning_exports_aliases_and_registry(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    pending = client.post("/web_learning/request", json={"url": "https://example.org", "reason": "approval_path"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    assert pending_body.get("approval_id")

    blocked = client.post("/web_learning/request", json={"url": "https://127.0.0.1/internal", "reason": "blocked_path"})
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False

    export_post = client.post("/web_learning/export", json={"kind": "events", "format": "csv"})
    assert export_post.status_code == 200
    assert export_post.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(export_post.text)))
    assert isinstance(rows, list)

    export_records = client.get("/web_learning/records/export?format=json")
    assert export_records.status_code == 200
    export_records_body = json.loads(export_records.text)
    assert isinstance(export_records_body.get("items"), list)

    export_quarantine = client.get("/web_learning/export/quarantine?format=jsonl")
    assert export_quarantine.status_code == 200
    assert export_quarantine.headers["content-type"].startswith("application/jsonl")

    quarantine = client.get("/web_learning/quarantine")
    assert quarantine.status_code == 200
    quarantine_items = quarantine.json()["items"]
    assert quarantine_items
    quarantine_id = str(quarantine_items[0]["id"])

    delete_pending = client.post(f"/web_learning/quarantine/{quarantine_id}/decide", json={"action": "delete", "reason": "cleanup"})
    assert delete_pending.status_code == 200
    delete_pending_body = delete_pending.json()
    assert delete_pending_body["ok"] is True
    assert delete_pending_body["status"] == "pending"
    assert delete_pending_body["applied"] is False
    assert delete_pending_body.get("approval_id")

    registry_path = data_root / "web_learning" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry.get("policy"), dict)
    assert isinstance(registry.get("records"), list)
    assert isinstance(registry.get("events"), list)
    assert isinstance(registry.get("quarantine"), list)


def test_web_learning_dash_and_system_prefix_aliases(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    dash_status = client.get("/web-learning/status")
    assert dash_status.status_code == 200
    dash_status_body = dash_status.json()
    assert dash_status_body["ok"] is True
    assert dash_status_body["route"] == "web_learning"

    system_policy = client.get("/system/web_learning/policy")
    assert system_policy.status_code == 200
    system_policy_body = system_policy.json()
    assert system_policy_body["ok"] is True
    assert isinstance(system_policy_body["policy"], dict)

    requested = client.post(
        "/system/web-learning/request",
        json={
            "url": "https://example.net/alias-test",
            "reason": "alias_request",
            "meta": {"force": True},
            "bytes": 256,
        },
    )
    assert requested.status_code == 200
    requested_body = requested.json()
    assert requested_body["ok"] is True
    assert requested_body["status"] == "ingested"
    record_id = str(requested_body["record_id"])

    dash_records = client.get("/web-learning/records?status=ingested")
    assert dash_records.status_code == 200
    dash_records_body = dash_records.json()
    assert any(str(item.get("id")) == record_id for item in dash_records_body["items"])

    system_export = client.get("/system/web-learning/records/export?format=json")
    assert system_export.status_code == 200
    system_export_body = json.loads(system_export.text)
    assert isinstance(system_export_body.get("items"), list)
    assert any(str(item.get("id")) == record_id for item in system_export_body["items"])
