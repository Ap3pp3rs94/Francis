from __future__ import annotations

import csv
import io
import json
from pathlib import Path


def test_explanations_list_get_export_and_filters(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/explanations/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["ok"] is True
    assert status_body["route"] == "explanation"

    first = client.post(
        "/explanations/record",
        json={
            "id": "exp-alpha",
            "ts": 1_700_000_001,
            "kind": "decision",
            "severity": "warning",
            "title": "Policy check",
            "summary": "Checked policy before execution.",
            "domain": "operations",
            "run_id": "run-1",
            "trace_id": "trace-policy",
            "artifact_dir": "runs/run-1/artifacts",
            "conversation_id": "conv-1",
            "approval_id": "appr-1",
            "plugin_id": "plugin-1",
            "tags": ["ops", "policy"],
            "content": {"step": "preflight"},
            "inputs": {"task": "deploy"},
            "outputs": {"result": "pending"},
            "policy": {"decision": "allow"},
            "tools": [{"name": "policy_gate"}],
        },
    )
    assert first.status_code == 200
    assert first.json()["ok"] is True

    second = client.post(
        "/explanations/record",
        json={
            "id": "exp-beta",
            "ts": 1_700_000_002,
            "kind": "audit",
            "severity": "info",
            "title": "Audit note",
            "summary": "General bookkeeping entry.",
            "domain": "security",
            "tags": ["audit"],
        },
    )
    assert second.status_code == 200
    assert second.json()["ok"] is True

    third = client.post(
        "/explanations/record",
        json={
            "id": "exp-gamma",
            "ts": 1_700_000_003,
            "kind": "decision",
            "severity": "error",
            "title": "Rollout guardrail",
            "summary": "Rollout was blocked after risk check.",
            "domain": "operations",
            "run_id": "run-2",
            "trace_id": "trace-rollout",
            "artifact_dir": "runs/run-2/artifacts",
            "tags": ["ops", "risk"],
            "content": {"step": "risk-check", "decision": "block"},
        },
    )
    assert third.status_code == 200
    assert third.json()["ok"] is True

    listed = client.get(
        "/explanations/list?kind=decision&domain=operations&tags=ops&search=rollout"
        "&trace_id=trace-rollout&artifact_dir=runs/run-2/artifacts&limit=10"
    )
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["limit"] == 10
    ids = [str(item.get("id")) for item in listed_body["items"]]
    assert "exp-gamma" in ids
    assert "exp-alpha" not in ids
    assert listed_body["records"] == listed_body["items"]

    fetched = client.get("/explanations/get?id=exp-gamma")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["id"] == "exp-gamma"
    assert fetched_body["item"]["trace_id"] == "trace-rollout"
    assert fetched_body["item"]["artifact_dir"] == "runs/run-2/artifacts"
    assert fetched_body["content"]["decision"] == "block"

    exported_json = client.get("/explanations/export?format=json&kind=decision&trace_id=trace-policy")
    assert exported_json.status_code == 200
    assert exported_json.headers["content-type"].startswith("application/json")
    exported_json_body = json.loads(exported_json.text)
    exported_json_ids = {str(item.get("id")) for item in exported_json_body["items"]}
    assert "exp-alpha" in exported_json_ids
    assert "exp-gamma" not in exported_json_ids
    assert "exp-beta" not in exported_json_ids

    exported_artifact_json = client.get("/explanations/export?format=json&artifact_dir=runs/run-2/artifacts")
    assert exported_artifact_json.status_code == 200
    exported_artifact_body = json.loads(exported_artifact_json.text)
    exported_artifact_ids = {str(item.get("id")) for item in exported_artifact_body["items"]}
    assert exported_artifact_ids == {"exp-gamma"}
    assert exported_artifact_body["items"][0]["artifact_dir"] == "runs/run-2/artifacts"

    exported_csv = client.get("/explanations/export?format=csv&severity=error")
    assert exported_csv.status_code == 200
    assert exported_csv.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    row_ids = {str(row.get("id")) for row in rows}
    assert "exp-gamma" in row_ids
    assert "exp-alpha" not in row_ids
    assert rows[0]["trace_id"] == "trace-rollout"
    assert rows[0]["artifact_dir"] == "runs/run-2/artifacts"


def test_explanation_prefix_compatibility_and_persistence(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    singular_write = client.post(
        "/explanation/record",
        json={
            "id": "exp-singular",
            "kind": "audit",
            "severity": "info",
            "title": "Singular write",
            "summary": "Written through singular prefix.",
            "tags": ["compat"],
        },
    )
    assert singular_write.status_code == 200
    assert singular_write.json()["ok"] is True

    plural_read = client.get("/explanations/get?id=exp-singular")
    assert plural_read.status_code == 200
    plural_read_body = plural_read.json()
    assert plural_read_body["ok"] is True
    assert plural_read_body["item"]["id"] == "exp-singular"

    plural_write = client.post(
        "/explanations/create",
        json={
            "id": "exp-plural",
            "kind": "decision",
            "severity": "warning",
            "title": "Plural write",
            "summary": "Written through plural prefix.",
            "tags": ["compat"],
        },
    )
    assert plural_write.status_code == 200
    assert plural_write.json()["ok"] is True

    singular_list = client.get("/explanation/list?tags=compat")
    assert singular_list.status_code == 200
    list_ids = {str(item.get("id")) for item in singular_list.json()["items"]}
    assert "exp-singular" in list_ids
    assert "exp-plural" in list_ids

    registry_path = data_root / "explanations" / "_registry.json"
    assert registry_path.exists()
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    records = registry.get("records")
    assert isinstance(records, dict)
    assert "exp-singular" in records
    assert "exp-plural" in records

    client2 = TestClient(create_app())
    persisted = client2.get("/explanations/get?id=exp-plural")
    assert persisted.status_code == 200
    assert persisted.json()["ok"] is True
