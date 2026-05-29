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

    release = client.post(
        f"/web_learning/quarantine/{quarantine_id}/decide", json={"action": "release", "reason": "manual_review"}
    )
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


def test_web_learning_request_denies_unscoped_write_before_force_or_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/poison",
            "request_actor": "unscoped.web.learning.writer",
            "actor": "operator:poison",
            "reason": "unscoped_force_attempt",
            "meta": {"force": True},
        },
    )

    assert denied.status_code == 200
    body = denied.json()
    assert body["ok"] is False
    assert body["status"] == "denied"
    assert body["error"] == "api_permission_denied"
    assert body["governance"]["gate"] == "permission_gate"
    assert body["governance"]["reason"] == "missing_scopes"
    assert body["governance"]["next_step"] == "configure_actor_scope_before_mutating_web_learning"
    assert body["governance"]["evidence"]["actor_present"] is True
    assert body["governance"]["evidence"]["required_scope_count"] == 1

    registry_path = data_root / "web_learning" / "_registry.json"
    assert not registry_path.exists()

    records = client.get("/web_learning/records?search=poison")
    assert records.status_code == 200
    assert records.json()["total"] == 0


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

    delete_pending = client.post(
        f"/web_learning/quarantine/{quarantine_id}/decide", json={"action": "delete", "reason": "cleanup"}
    )
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


def test_web_learning_request_refreshes_mismatched_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    pending = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/docs",
            "reason": "approval_path",
            "actor": "operator:a",
            "bytes": 128,
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    record_id = str(pending_body["record_id"])
    assert approval_id
    assert record_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/docs",
            "reason": "approval_path",
            "actor": "operator:b",
            "bytes": 128,
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
    assert mismatched_body["record_id"] == record_id
    artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    applied = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/docs",
            "reason": "approval_path",
            "actor": "operator:b",
            "bytes": 128,
            "approval_id": refreshed_approval_id,
        },
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["status"] == "ingested"
    assert applied_body["approval_id"] == refreshed_approval_id
    assert applied_body["record_id"] == record_id

    records = client.get("/web_learning/records")
    assert records.status_code == 200
    matching_records = [item for item in records.json()["items"] if str(item.get("id")) == record_id]
    assert len(matching_records) == 1
    assert matching_records[0]["status"] == "ingested"
    assert matching_records[0]["approval_id"] == refreshed_approval_id


def test_web_learning_request_redacts_sensitive_approval_metadata(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_key = "sk-" + ("g" * 32)
    raw_token = "ghp_" + ("h" * 36)
    raw_password = "weblearningsecret123"
    pending = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/redaction",
            "reason": "approval_path",
            "actor": "operator:redaction",
            "bytes": 128,
            "meta": {
                "ticket": "FR-WEB",
                "api_key": raw_key,
                "nested": {"refresh_token": raw_token},
                "note": f"operator note password={raw_password}",
                "token_count": 13,
            },
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    approval_id = str(pending_body["approval_id"])

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    artifact_path = data_root / "artifacts" / "web_learning" / "approvals" / approval_id / "request.json"
    registry_path = data_root / "web_learning" / "_registry.json"
    approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
    approval_meta = approval_payload["payload"]["payload"]["meta"]
    assert approval_meta["ticket"] == "FR-WEB"
    assert approval_meta["api_key"] == "[REDACTED:secret]"
    assert approval_meta["nested"]["refresh_token"] == "[REDACTED:secret]"
    assert approval_meta["note"] == "operator note password=[REDACTED:secret]"
    assert approval_meta["token_count"] == 13

    artifact_payload = json.loads(artifact_path.read_text(encoding="utf-8"))
    assert artifact_payload["request"]["payload"]["meta"] == approval_meta

    persisted_text = "\n".join(
        [
            approval_path.read_text(encoding="utf-8"),
            artifact_path.read_text(encoding="utf-8"),
            registry_path.read_text(encoding="utf-8"),
        ]
    )
    assert raw_key not in persisted_text
    assert raw_token not in persisted_text
    assert raw_password not in persisted_text


def test_web_learning_request_seals_sensitive_payload_without_weakening_exact_approval(
    monkeypatch, tmp_path: Path
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    raw_url_token = "learnurlsecret123"
    request_url = f"https://example.org/sealed?token={raw_url_token}"
    redacted_url = "https://example.org/sealed?token=[REDACTED:secret]"
    raw_password = "learnsecret123"
    different_password = "learnsecret456"
    pending = client.post(
        "/web_learning/request",
        json={
            "url": request_url,
            "reason": "approval_path",
            "actor": "operator:sealed",
            "bytes": 128,
            "title": f"Operator note password={raw_password}",
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    approval_id = str(pending_body["approval_id"])

    approval_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    artifact_path = data_root / "artifacts" / "web_learning" / "approvals" / approval_id / "request.json"
    registry_path = data_root / "web_learning" / "_registry.json"
    approval_payload = json.loads(approval_path.read_text(encoding="utf-8"))
    sealed_url = approval_payload["payload"]["payload"]["url"]
    assert sealed_url["kind"] == "sealed_secret"
    assert sealed_url["redacted"] == redacted_url
    assert str(sealed_url["digest"]).startswith("hmac-sha256:")
    sealed_title = approval_payload["payload"]["payload"]["title"]
    assert sealed_title["kind"] == "sealed_secret"
    assert sealed_title["redacted"] == "Operator note password=[REDACTED:secret]"
    assert str(sealed_title["digest"]).startswith("hmac-sha256:")

    artifact_text = artifact_path.read_text(encoding="utf-8")
    artifact_payload = json.loads(artifact_text)
    assert artifact_payload["request"]["payload"]["url"] == redacted_url
    assert artifact_payload["request"]["payload"]["title"] == "Operator note password=[REDACTED:secret]"
    assert artifact_payload["approval"]["payload"]["payload"]["url"] == redacted_url
    assert artifact_payload["approval"]["payload"]["payload"]["title"] == "Operator note password=[REDACTED:secret]"
    assert raw_password not in approval_path.read_text(encoding="utf-8")
    assert raw_password not in artifact_text
    assert raw_url_token not in approval_path.read_text(encoding="utf-8")
    assert raw_url_token not in artifact_text
    assert "hmac-sha256:" not in artifact_text
    assert raw_url_token not in registry_path.read_text(encoding="utf-8")
    assert redacted_url in registry_path.read_text(encoding="utf-8")

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/web_learning/request",
        json={
            "url": request_url,
            "reason": "approval_path",
            "actor": "operator:sealed",
            "bytes": 128,
            "title": f"Operator note password={different_password}",
            "approval_id": approval_id,
        },
    )
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is False
    assert mismatched_body["status"] == "needs_approval"
    assert mismatched_body["error"] == "approval_payload_mismatch"
    assert str(mismatched_body["approval_id"]) != approval_id

    refreshed_id = str(mismatched_body["approval_id"])
    refreshed_artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    refreshed_request_text = (refreshed_artifact_dir / "request.json").read_text(encoding="utf-8")
    refreshed_mismatch_text = (refreshed_artifact_dir / "mismatch.json").read_text(encoding="utf-8")
    original_mismatch_text = (
        data_root / "artifacts" / "web_learning" / "approvals" / approval_id / "mismatch.json"
    ).read_text(encoding="utf-8")
    for artifact_text in (refreshed_request_text, refreshed_mismatch_text, original_mismatch_text):
        assert raw_url_token not in artifact_text
        assert raw_password not in artifact_text
        assert different_password not in artifact_text
        assert "hmac-sha256:" not in artifact_text

    approved_refreshed = client.post(
        "/approvals/decision", json={"id": refreshed_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(
        "/web_learning/request",
        json={
            "url": request_url,
            "reason": "approval_path",
            "actor": "operator:sealed",
            "bytes": 128,
            "title": f"Operator note password={different_password}",
            "approval_id": refreshed_id,
        },
    )
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "ingested"

    registry_payload = json.loads(registry_path.read_text(encoding="utf-8"))
    registry_text = json.dumps(registry_payload, sort_keys=True)
    assert raw_url_token not in registry_text
    assert raw_password not in registry_text
    assert different_password not in registry_text
    assert redacted_url in registry_text

    record = next(item for item in registry_payload["records"] if item["id"] == executed_body["record_id"])
    assert record["url"] == redacted_url
    assert record["title"] == "Operator note password=[REDACTED:secret]"
    assert all(event["url"] == redacted_url for event in registry_payload["events"] if "url" in event)


def test_web_learning_request_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    pending = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/missing",
            "reason": "approval_path",
            "actor": "operator:a",
            "bytes": 64,
        },
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    record_id = str(pending_body["record_id"])
    assert approval_id
    assert record_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    refreshed = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/missing",
            "reason": "approval_path",
            "actor": "operator:a",
            "bytes": 64,
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
    assert refreshed_body["record_id"] == record_id
    artifact_dir = Path(str(refreshed_body["artifact_dir"]))
    assert (artifact_dir / "error.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    applied = client.post(
        "/web_learning/request",
        json={
            "url": "https://example.org/missing",
            "reason": "approval_path",
            "actor": "operator:a",
            "bytes": 64,
            "approval_id": refreshed_approval_id,
        },
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["status"] == "ingested"
    assert applied_body["approval_id"] == refreshed_approval_id
    assert applied_body["record_id"] == record_id

    records = client.get("/web_learning/records")
    assert records.status_code == 200
    matching_records = [item for item in records.json()["items"] if str(item.get("id")) == record_id]
    assert len(matching_records) == 1
    assert matching_records[0]["status"] == "ingested"
    assert matching_records[0]["approval_id"] == refreshed_approval_id


def test_web_learning_enable_refreshes_mismatched_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    disabled = client.post("/web_learning/enabled", json={"enabled": False, "reason": "maintenance"})
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    pending = client.post(
        "/web_learning/enabled",
        json={"enabled": True, "reason": "resume", "actor": "operator:a"},
    )
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "pending"
    approval_id = str(pending_body["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    mismatched = client.post(
        "/web_learning/enabled",
        json={"enabled": True, "reason": "resume", "actor": "operator:b", "approval_id": approval_id},
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
    artifact_dir = Path(str(mismatched_body["artifact_dir"]))
    assert (artifact_dir / "mismatch.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    applied = client.post(
        "/web_learning/enabled",
        json={"enabled": True, "reason": "resume", "actor": "operator:b", "approval_id": refreshed_approval_id},
    )
    assert applied.status_code == 200
    applied_body = applied.json()
    assert applied_body["ok"] is True
    assert applied_body["status"] == "applied"
    assert applied_body["applied"] is True
    assert applied_body["enabled"] is True
    assert applied_body["approval_id"] == refreshed_approval_id


def test_web_learning_quarantine_delete_refreshes_missing_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    blocked = client.post("/web_learning/request", json={"url": "https://127.0.0.1/internal", "reason": "blocked_path"})
    assert blocked.status_code == 200
    assert blocked.json()["ok"] is False

    quarantine = client.get("/web_learning/quarantine")
    assert quarantine.status_code == 200
    quarantine_items = quarantine.json()["items"]
    assert quarantine_items
    quarantine_id = str(quarantine_items[0]["id"])

    pending_delete = client.post(
        f"/web_learning/quarantine/{quarantine_id}/decide",
        json={"action": "delete", "reason": "cleanup", "actor": "operator:a"},
    )
    assert pending_delete.status_code == 200
    pending_delete_body = pending_delete.json()
    assert pending_delete_body["ok"] is True
    assert pending_delete_body["status"] == "pending"
    approval_id = str(pending_delete_body["approval_id"])
    assert approval_id

    pending_path = data_root / "approvals" / "pending" / f"{approval_id}.json"
    assert pending_path.exists()
    pending_path.unlink()

    refreshed = client.post(
        f"/web_learning/quarantine/{quarantine_id}/decide",
        json={"action": "delete", "reason": "cleanup", "actor": "operator:a", "approval_id": approval_id},
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
    artifact_dir = Path(str(refreshed_body["artifact_dir"]))
    assert (artifact_dir / "error.json").exists()

    approved_refreshed = client.post(
        "/approvals/decision",
        json={"id": refreshed_approval_id, "action": "approve", "actor": "test.approvals.decision"},
    )
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    deleted = client.post(
        f"/web_learning/quarantine/{quarantine_id}/decide",
        json={"action": "delete", "reason": "cleanup", "actor": "operator:a", "approval_id": refreshed_approval_id},
    )
    assert deleted.status_code == 200
    deleted_body = deleted.json()
    assert deleted_body["ok"] is True
    assert deleted_body["status"] == "deleted"
    assert deleted_body["applied"] is True
    assert deleted_body["approval_id"] == refreshed_approval_id

    remaining = client.get("/web_learning/quarantine")
    assert remaining.status_code == 200
    remaining_ids = {str(item.get("id")) for item in remaining.json()["items"]}
    assert quarantine_id not in remaining_ids

    records = client.get("/web_learning/records")
    assert records.status_code == 200
    matching_records = [
        item for item in records.json()["items"] if str(item.get("quarantine_id")) in {"", quarantine_id}
    ]
    assert any(
        str(item.get("status")) == "failed" and str(item.get("error")) == "Deleted from quarantine."
        for item in matching_records
    )


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
