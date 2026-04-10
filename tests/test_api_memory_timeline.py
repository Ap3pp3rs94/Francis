from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def test_memory_timeline_list_get_export_filters_and_cursor(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/memory/timeline/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["route"] == "memory_timeline"

    one = client.post(
        "/memory/timeline/record",
        json={
            "id": "evt-a",
            "ts": 1_700_000_001,
            "kind": "memory_write",
            "severity": "info",
            "domain": "operations",
            "actor": "francis",
            "scope": "chat.session",
            "correlation_id": "corr-1",
            "title": "Session write",
            "message": "Stored summary memory block.",
            "tags": ["session-a", "write"],
            "payload": {"token_count": 320},
            "artifacts": [{"id": "art-1", "kind": "summary", "path": "data/memory/summary-1.json"}],
            "meta": {"source": "unit_test"},
        },
    )
    assert one.status_code == 200
    assert one.json()["ok"] is True

    two = client.post(
        "/memory/timeline/record",
        json={
            "id": "evt-b",
            "ts": 1_700_000_002,
            "kind": "retrieval_query",
            "severity": "warning",
            "domain": "operations",
            "actor": "user",
            "scope": "chat.session",
            "correlation_id": "corr-1",
            "title": "Retrieval query",
            "message": "Queried memory for latest deployment outcome.",
            "tags": ["session-a", "query"],
            "data": {"query": "latest deployment"},
        },
    )
    assert two.status_code == 200
    assert two.json()["ok"] is True

    three = client.post(
        "/memory/timeline/record",
        json={
            "id": "evt-c",
            "ts": 1_700_000_003,
            "kind": "governance_decision",
            "severity": "error",
            "domain": "security",
            "actor": "daemon",
            "scope": "approval.memory",
            "correlation_id": "corr-2",
            "title": "Write denied",
            "message": "Memory write denied by policy.",
            "tags": ["session-b", "approval"],
            "payload": {"decision": "deny"},
        },
    )
    assert three.status_code == 200
    assert three.json()["ok"] is True

    listed = client.get("/memory/timeline/list?kinds=memory_write&tags=session-a&tags=write&include_payload=1")
    assert listed.status_code == 200
    listed_body = listed.json()
    ids = {str(item.get("id")) for item in listed_body["items"]}
    assert "evt-a" in ids
    assert "evt-b" not in ids
    first_item = next(item for item in listed_body["items"] if str(item.get("id")) == "evt-a")
    assert first_item["payload"]["token_count"] == 320
    assert listed_body["events"] == listed_body["items"]
    assert listed_body["entries"] == listed_body["items"]
    assert listed_body["timeline"] == listed_body["items"]

    listed_no_payload = client.get("/memory/timeline/list?kinds=memory_write")
    assert listed_no_payload.status_code == 200
    no_payload_item = next(item for item in listed_no_payload.json()["items"] if str(item.get("id")) == "evt-a")
    assert "payload" not in no_payload_item

    fetched = client.get("/memory/timeline/get?id=evt-b")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["id"] == "evt-b"
    assert fetched_body["item"]["payload"]["query"] == "latest deployment"
    assert fetched_body["event"]["id"] == "evt-b"

    page1 = client.get("/memory/timeline/list?limit=1&offset=0")
    assert page1.status_code == 200
    page1_body = page1.json()
    assert page1_body["limit"] == 1
    assert page1_body["next_cursor"] is not None
    first_page_id = str(page1_body["items"][0]["id"])

    page2 = client.get(f"/memory/timeline/list?limit=1&cursor={page1_body['next_cursor']}")
    assert page2.status_code == 200
    page2_body = page2.json()
    assert page2_body["items"]
    second_page_id = str(page2_body["items"][0]["id"])
    assert second_page_id != first_page_id

    export_jsonl = client.get("/memory/timeline/export?format=jsonl&severity=warning")
    assert export_jsonl.status_code == 200
    assert export_jsonl.headers["content-type"].startswith("application/jsonl")
    lines = [line for line in export_jsonl.text.splitlines() if line.strip()]
    parsed = [json.loads(line) for line in lines]
    jsonl_ids = {str(item.get("id")) for item in parsed}
    assert "evt-b" in jsonl_ids
    assert "evt-a" not in jsonl_ids

    export_csv = client.get("/memory/timeline/export?format=csv&domain=security")
    assert export_csv.status_code == 200
    assert export_csv.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(export_csv.text)))
    csv_ids = {str(row.get("id")) for row in rows}
    assert "evt-c" in csv_ids
    assert "evt-a" not in csv_ids


def test_memory_timeline_create_alias_and_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/memory/timeline/create",
        json={
            "id": "evt-persist",
            "kind": "checkpoint",
            "severity": "info",
            "title": "Checkpoint saved",
            "message": "Saved memory checkpoint.",
            "tags": ["persist"],
            "payload": {"checkpoint": "cp-1"},
        },
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True

    read_back = client.get("/memory/timeline/get?id=evt-persist")
    assert read_back.status_code == 200
    assert read_back.json()["ok"] is True
    assert read_back.json()["item"]["payload"]["checkpoint"] == "cp-1"

    registry_path = data_root / "memory" / "timeline" / "_events.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert isinstance(registry.get("events"), list)
    assert any(str(item.get("id")) == "evt-persist" for item in registry["events"])

    client2 = TestClient(create_app())
    persisted = client2.get("/memory/timeline/get?id=evt-persist")
    assert persisted.status_code == 200
    assert persisted.json()["ok"] is True
