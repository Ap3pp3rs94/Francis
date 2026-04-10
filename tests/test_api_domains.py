from __future__ import annotations

import json
from pathlib import Path


def test_domains_lifecycle_and_summary(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/domains/create",
        json={
            "name": "Alpha Ops",
            "description": "Operations domain",
            "tags": ["ops", "critical"],
            "reason": "integration_test",
            "meta": {"trust_level": 4, "memory_items": 12, "plugin_count": 3},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    domain_id = str(created_body["id"])

    fetched = client.get(f"/domains/get?domain_id={domain_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["id"] == domain_id
    assert fetched_body["item"]["name"] == "Alpha Ops"

    listed = client.get("/domains/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    assert any(str(item.get("id")) == domain_id for item in listed_body["items"])

    summary = client.get(f"/domains/summary?domain_id={domain_id}")
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["ok"] is True
    assert summary_body["summary"]["domain_id"] == domain_id
    assert summary_body["summary"]["trust_level"] == 4
    assert summary_body["summary"]["memory_items"] == 12
    assert summary_body["summary"]["plugin_count"] == 3

    updated = client.patch(
        "/domains/update",
        json={
            "domain_id": domain_id,
            "updates": {"status": "archived", "tags": ["ops"], "meta": {"trust_level": 8}},
            "reason": "test_archive",
        },
    )
    assert updated.status_code == 200
    updated_body = updated.json()
    assert updated_body["ok"] is True
    assert updated_body["status"] == "archived"

    archived = client.get("/domains/list?status=archived")
    assert archived.status_code == 200
    archived_body = archived.json()
    assert any(str(item.get("id")) == domain_id for item in archived_body["items"])

    deleted = client.post("/domains/delete", json={"domain_id": domain_id, "reason": "cleanup"})
    assert deleted.status_code == 200
    deleted_body = deleted.json()
    assert deleted_body["ok"] is True
    assert deleted_body["status"] == "deleted"

    fetched_after_delete = client.get(f"/domains/get?domain_id={domain_id}")
    assert fetched_after_delete.status_code == 200
    assert fetched_after_delete.json()["ok"] is False


def test_domains_filters_and_registry_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    first = client.post("/domains/create", json={"name": "Core Systems", "tags": ["core", "ops"]})
    second = client.post("/domains/create", json={"name": "Billing", "tags": ["finance", "ops"]})
    assert first.status_code == 200
    assert second.status_code == 200
    first_id = str(first.json()["id"])
    second_id = str(second.json()["id"])

    disabled = client.patch("/domains/update", json={"domain_id": second_id, "updates": {"status": "disabled"}})
    assert disabled.status_code == 200
    assert disabled.json()["ok"] is True

    by_status = client.get("/domains/list?status=disabled")
    assert by_status.status_code == 200
    status_ids = {str(item.get("id")) for item in by_status.json()["items"]}
    assert second_id in status_ids
    assert first_id not in status_ids

    by_tags = client.get("/domains/list?tags=core,ops")
    assert by_tags.status_code == 200
    tag_ids = {str(item.get("id")) for item in by_tags.json()["items"]}
    assert first_id in tag_ids
    assert second_id not in tag_ids

    paged = client.get("/domains/list?limit=1&offset=0")
    assert paged.status_code == 200
    paged_body = paged.json()
    assert paged_body["limit"] == 1
    assert paged_body["offset"] == 0
    assert paged_body["total"] >= 2
    assert len(paged_body["items"]) == 1

    registry_path = data_root / "domains" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry.get("version"), int)
    assert isinstance(registry.get("updated_at"), int)
    assert isinstance(registry.get("domains"), dict)
    assert first_id in registry["domains"]
    assert second_id in registry["domains"]
