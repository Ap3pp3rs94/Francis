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
            "mission_id": "msn-alpha",
            "operation_id": "tsk-alpha",
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
            "trace_id": "trace-rollout",
            "artifact_dir": "runs/run-2/artifacts",
            "tags": ["ops", "risk"],
            "meta": {
                "run_id": "run-2",
                "mission_id": "msn-gamma",
                "operation_id": "tsk-gamma",
                "approval_id": "appr-2",
            },
            "content": {"step": "risk-check", "decision": "block"},
        },
    )
    assert third.status_code == 200
    assert third.json()["ok"] is True

    listed = client.get(
        "/explanations/list?kind=decision&domain=operations&tags=ops&search=rollout"
        "&run_id=run-2&trace_id=trace-rollout&artifact_dir=runs/run-2/artifacts"
        "&mission_id=msn-gamma&operation_id=tsk-gamma&approval_id=appr-2&limit=10"
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
    assert fetched_body["item"]["run_id"] == "run-2"
    assert fetched_body["item"]["trace_id"] == "trace-rollout"
    assert fetched_body["item"]["artifact_dir"] == "runs/run-2/artifacts"
    assert fetched_body["item"]["mission_id"] == "msn-gamma"
    assert fetched_body["item"]["operation_id"] == "tsk-gamma"
    assert fetched_body["item"]["approval_id"] == "appr-2"
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

    exported_approval_json = client.get("/explanations/export?format=json&approval_id=appr-2")
    assert exported_approval_json.status_code == 200
    exported_approval_body = json.loads(exported_approval_json.text)
    assert {str(item.get("id")) for item in exported_approval_body["items"]} == {"exp-gamma"}
    assert exported_approval_body["items"][0]["approval_id"] == "appr-2"

    exported_mission_json = client.get("/explanations/export?format=json&mission_id=msn-gamma&operation_id=tsk-gamma")
    assert exported_mission_json.status_code == 200
    exported_mission_body = json.loads(exported_mission_json.text)
    assert {str(item.get("id")) for item in exported_mission_body["items"]} == {"exp-gamma"}
    assert exported_mission_body["items"][0]["mission_id"] == "msn-gamma"
    assert exported_mission_body["items"][0]["operation_id"] == "tsk-gamma"

    exported_csv = client.get("/explanations/export?format=csv&severity=error")
    assert exported_csv.status_code == 200
    assert exported_csv.headers["content-type"].startswith("text/csv")
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    row_ids = {str(row.get("id")) for row in rows}
    assert "exp-gamma" in row_ids
    assert "exp-alpha" not in row_ids
    assert rows[0]["trace_id"] == "trace-rollout"
    assert rows[0]["artifact_dir"] == "runs/run-2/artifacts"
    assert rows[0]["mission_id"] == "msn-gamma"
    assert rows[0]["operation_id"] == "tsk-gamma"


def test_explanations_promote_structured_receipt_references(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    written = client.post(
        "/explanations/record",
        json={
            "id": "exp-references",
            "ts": 1_700_000_010,
            "kind": "audit",
            "severity": "info",
            "title": "Referenced receipt",
            "summary": "Receipt handles arrived in the structured references block.",
            "domain": "operations",
            "references": {
                "mission_id": "msn-ref",
                "task_id": "tsk-ref",
                "traceId": "trace-ref",
                "approvalId": "appr-ref",
                "run_id": "run-ref",
                "artifact_path": "runs/ref/artifacts",
            },
        },
    )
    assert written.status_code == 200
    written_body = written.json()
    assert written_body["ok"] is True
    assert written_body["item"]["mission_id"] == "msn-ref"
    assert written_body["item"]["operation_id"] == "tsk-ref"
    assert written_body["item"]["trace_id"] == "trace-ref"
    assert written_body["item"]["approval_id"] == "appr-ref"
    assert written_body["item"]["run_id"] == "run-ref"
    assert written_body["item"]["artifact_dir"] == "runs/ref/artifacts"
    assert written_body["item"]["references"] == {
        "mission_id": "msn-ref",
        "operation_id": "tsk-ref",
        "trace_id": "trace-ref",
        "approval_id": "appr-ref",
        "run_id": "run-ref",
        "artifact_dir": "runs/ref/artifacts",
    }

    listed = client.get(
        "/explanations/list",
        params={
            "mission_id": "msn-ref",
            "operation_id": "tsk-ref",
            "trace_id": "trace-ref",
            "approval_id": "appr-ref",
            "run_id": "run-ref",
            "artifact_dir": "runs/ref/artifacts",
        },
    )
    assert listed.status_code == 200
    listed_items = listed.json()["items"]
    assert [item["id"] for item in listed_items] == ["exp-references"]
    assert listed_items[0]["references"]["operation_id"] == "tsk-ref"

    fetched = client.get("/explanations/get?id=exp-references")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["mission_id"] == "msn-ref"
    assert fetched_item["references"]["trace_id"] == "trace-ref"

    exported_json = client.get("/explanations/export", params={"format": "json", "approval_id": "appr-ref"})
    assert exported_json.status_code == 200
    exported_json_body = json.loads(exported_json.text)
    assert [item["id"] for item in exported_json_body["items"]] == ["exp-references"]
    assert exported_json_body["items"][0]["references"]["artifact_dir"] == "runs/ref/artifacts"

    exported_csv = client.get("/explanations/export?format=csv&run_id=run-ref")
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert [row["id"] for row in rows] == ["exp-references"]
    assert rows[0]["operation_id"] == "tsk-ref"
    assert rows[0]["artifact_dir"] == "runs/ref/artifacts"

    registry_path = data_root / "explanations" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["records"]["exp-references"]["references"]["approval_id"] == "appr-ref"

    client2 = TestClient(create_app())
    persisted = client2.get("/explanations/list?trace_id=trace-ref")
    assert persisted.status_code == 200
    assert [item["id"] for item in persisted.json()["items"]] == ["exp-references"]


def test_explanations_preserve_current_task_receipt_identity(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    written = client.post(
        "/explanations/record",
        json={
            "id": "exp-current-task",
            "ts": 1_700_000_020,
            "kind": "audit",
            "severity": "info",
            "title": "Current task receipt",
            "summary": "Receipt-backed current task identity reached explanation evidence.",
            "domain": "operations",
            "references": {
                "mission_id": "msn-loop",
                "current_task_operation_id": "tsk-loop",
                "current_task_approval_id": "appr-loop",
                "current_task_trace_id": "trace-loop",
                "current_task_run_id": "run-loop",
                "current_task_artifact_dir": "runs/loop/artifacts",
            },
            "loop": {
                "operation_status": "succeeded",
                "operation_error": "plugin_id_required",
                "result_message": "Plugin id is required. password=loopsecret123",
                "recovery_next_step": "review_operation_detail token=looprecovery123",
                "current_task_source": "terminal_operation_receipt",
                "current_task_operation_name": "plan.create",
                "current_task_operation_plane": "P9_OBSERVABILITY",
                "current_task_advance_action": "run_linked_operation",
                "current_task_gate": "operator_review",
                "current_task_next_step": "review_completed_mission",
            },
        },
    )
    assert written.status_code == 200
    written_item = written.json()["item"]
    assert written_item["mission_id"] == "msn-loop"
    assert written_item["operation_id"] == "tsk-loop"
    assert written_item["approval_id"] == "appr-loop"
    assert written_item["trace_id"] == "trace-loop"
    assert written_item["run_id"] == "run-loop"
    assert written_item["artifact_dir"] == "runs/loop/artifacts"
    assert written_item["operation_status"] == "succeeded"
    assert written_item["operation_error"] == "plugin_id_required"
    assert written_item["result_message"] == "Plugin id is required. password=[REDACTED:secret]"
    assert written_item["recovery_next_step"] == "review_operation_detail token=[REDACTED:secret]"
    assert written_item["current_task_operation_id"] == "tsk-loop"
    assert written_item["current_task_operation_name"] == "plan.create"
    assert written_item["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert written_item["current_task_advance_action"] == "run_linked_operation"
    assert written_item["current_task_gate"] == "operator_review"
    assert written_item["current_task_next_step"] == "review_completed_mission"
    assert written_item["references"] == {
        "mission_id": "msn-loop",
        "operation_id": "tsk-loop",
        "trace_id": "trace-loop",
        "approval_id": "appr-loop",
        "run_id": "run-loop",
        "artifact_dir": "runs/loop/artifacts",
    }

    listed = client.get(
        "/explanations/list",
        params={
            "operation_id": "tsk-loop",
            "approval_id": "appr-loop",
            "trace_id": "trace-loop",
            "run_id": "run-loop",
            "artifact_dir": "runs/loop/artifacts",
        },
    )
    assert listed.status_code == 200
    listed_items = listed.json()["items"]
    assert [item["id"] for item in listed_items] == ["exp-current-task"]
    assert listed_items[0]["current_task_source"] == "terminal_operation_receipt"
    assert listed_items[0]["operation_error"] == "plugin_id_required"
    assert listed_items[0]["result_message"] == "Plugin id is required. password=[REDACTED:secret]"
    assert listed_items[0]["recovery_next_step"] == "review_operation_detail token=[REDACTED:secret]"

    fetched = client.get("/explanations/get?id=exp-current-task")
    assert fetched.status_code == 200
    fetched_item = fetched.json()["item"]
    assert fetched_item["current_task_operation_name"] == "plan.create"
    assert fetched_item["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert fetched_item["operation_error"] == "plugin_id_required"
    assert fetched_item["recovery_next_step"] == "review_operation_detail token=[REDACTED:secret]"

    exported_json = client.get("/explanations/export", params={"format": "json", "operation_id": "tsk-loop"})
    assert exported_json.status_code == 200
    exported_json_body = json.loads(exported_json.text)
    assert exported_json_body["items"][0]["current_task_advance_action"] == "run_linked_operation"
    assert exported_json_body["items"][0]["operation_error"] == "plugin_id_required"
    assert exported_json_body["items"][0]["result_message"] == "Plugin id is required. password=[REDACTED:secret]"

    exported_csv = client.get("/explanations/export?format=csv&operation_id=tsk-loop")
    assert exported_csv.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported_csv.text)))
    assert rows[0]["current_task_operation_name"] == "plan.create"
    assert rows[0]["current_task_operation_plane"] == "P9_OBSERVABILITY"
    assert rows[0]["operation_error"] == "plugin_id_required"
    assert rows[0]["result_message"] == "Plugin id is required. password=[REDACTED:secret]"
    assert rows[0]["recovery_next_step"] == "review_operation_detail token=[REDACTED:secret]"

    registry_path = data_root / "explanations" / "_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    assert registry["records"]["exp-current-task"]["current_task_advance_action"] == "run_linked_operation"
    assert registry["records"]["exp-current-task"]["operation_error"] == "plugin_id_required"
    assert (
        registry["records"]["exp-current-task"]["result_message"] == "Plugin id is required. password=[REDACTED:secret]"
    )


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
