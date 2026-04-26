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
            "operation_status": "succeeded",
            "domain": "operations",
            "actor": "francis",
            "scope": "chat.session",
            "correlation_id": "corr-1",
            "trace_id": "trace-memory-a",
            "mission_id": "mission-memory-a",
            "operation_id": "tsk-memory-a",
            "approval_id": "apr-memory-a",
            "run_id": "run-memory-a",
            "artifact_dir": "D:/francis/data/artifacts/memory-a",
            "title": "Session write",
            "message": "Stored summary memory block.",
            "tags": ["session-a", "write"],
            "payload": {"token_count": 320},
            "artifacts": [{"id": "art-1", "kind": "summary", "path": "data/memory/summary-1.json"}],
            "meta": {
                "source": "unit_test",
                "retention_policy": "mission_trace",
                "retention_until": "2026-05-01T00:00:00Z",
                "ttl_seconds": 86400,
            },
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
    assert first_item["operation_status"] == "succeeded"
    assert first_item["provenance"] == {
        "source": "unit_test",
        "domain": "operations",
        "actor": "francis",
        "scope": "chat.session",
        "correlation_id": "corr-1",
    }
    assert first_item["references"] == {
        "mission_id": "mission-memory-a",
        "operation_id": "tsk-memory-a",
        "trace_id": "trace-memory-a",
        "approval_id": "apr-memory-a",
        "run_id": "run-memory-a",
        "artifact_dir": "D:/francis/data/artifacts/memory-a",
    }
    assert first_item["retention"] == {
        "policy": "mission_trace",
        "until": "2026-05-01T00:00:00Z",
        "ttl_seconds": 86400,
    }
    assert listed_body["events"] == listed_body["items"]
    assert listed_body["entries"] == listed_body["items"]
    assert listed_body["timeline"] == listed_body["items"]

    trace_listed = client.get("/memory/timeline/list?trace_id=trace-memory-a&mission_id=mission-memory-a")
    assert trace_listed.status_code == 200
    assert [item["id"] for item in trace_listed.json()["items"]] == ["evt-a"]

    operation_listed = client.get("/memory/timeline/list?operation_id=tsk-memory-a")
    assert operation_listed.status_code == 200
    assert [item["id"] for item in operation_listed.json()["items"]] == ["evt-a"]

    run_listed = client.get("/memory/timeline/list?run_id=run-memory-a")
    assert run_listed.status_code == 200
    assert [item["id"] for item in run_listed.json()["items"]] == ["evt-a"]

    status_listed = client.get("/memory/timeline/list?operation_status=succeeded")
    assert status_listed.status_code == 200
    assert [item["id"] for item in status_listed.json()["items"]] == ["evt-a"]

    artifact_listed = client.get("/memory/timeline/list", params={"artifact_dir": "D:/francis/data/artifacts/memory-a"})
    assert artifact_listed.status_code == 200
    assert [item["id"] for item in artifact_listed.json()["items"]] == ["evt-a"]

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

    export_status_csv = client.get("/memory/timeline/export?format=csv&operation_status=succeeded")
    assert export_status_csv.status_code == 200
    status_rows = list(csv.DictReader(io.StringIO(export_status_csv.text)))
    status_csv_ids = {str(row.get("id")) for row in status_rows}
    assert "evt-a" in status_csv_ids
    assert status_rows[0]["operation_status"] == "succeeded"
    assert "evt-b" not in status_csv_ids

    export_json = client.get(
        "/memory/timeline/export", params={"format": "json", "artifact_dir": "D:/francis/data/artifacts/memory-a"}
    )
    assert export_json.status_code == 200
    json_ids = {str(item.get("id")) for item in export_json.json()["items"]}
    assert "evt-a" in json_ids
    assert "evt-b" not in json_ids


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


def test_memory_timeline_filters_continuity_ledger_by_references(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.chat.continuity.ledger import append

    append(
        "assistant",
        "Mission continuity receipt for memory evidence.",
        {
            "domain": "operations",
            "scope": "mission.loop",
            "mission_id": "msn-ledger-memory",
            "operation_id": "tsk-ledger-memory",
            "trace_id": "trace-ledger-memory",
            "approval_id": "apr-ledger-memory",
            "run_id": "run-ledger-memory",
            "artifact_dir": "D:/francis/data/artifacts/ledger-memory",
            "handoff_approval_id": "apr-ledger-memory",
            "handoff_approval_status": "pending",
            "current_task_approval_id": "apr-ledger-memory",
            "current_task_approval_status": "pending",
            "operation_status": "failed",
        },
    )

    client = TestClient(create_app())

    listed = client.get(
        "/memory/timeline/list?mission_id=msn-ledger-memory&operation_id=tsk-ledger-memory&trace_id=trace-ledger-memory"
    )
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["kind"] == "ledger_append"
    assert item["operation_status"] == "failed"
    assert item["provenance"] == {
        "source": "continuity.ledger",
        "domain": "operations",
        "actor": "assistant",
        "scope": "mission.loop",
        "correlation_id": "trace-ledger-memory",
    }
    assert item["references"] == {
        "mission_id": "msn-ledger-memory",
        "operation_id": "tsk-ledger-memory",
        "trace_id": "trace-ledger-memory",
        "approval_id": "apr-ledger-memory",
        "run_id": "run-ledger-memory",
        "artifact_dir": "D:/francis/data/artifacts/ledger-memory",
    }
    assert item["loop"] == {
        "handoff_approval_id": "apr-ledger-memory",
        "handoff_approval_status": "pending",
        "current_task_approval_id": "apr-ledger-memory",
        "current_task_approval_status": "pending",
        "run_id": "run-ledger-memory",
        "artifact_dir": "D:/francis/data/artifacts/ledger-memory",
    }

    operation_listed = client.get("/memory/timeline/list?operation_id=tsk-ledger-memory")
    assert operation_listed.status_code == 200
    assert [event["id"] for event in operation_listed.json()["items"]] == [item["id"]]

    run_listed = client.get("/memory/timeline/list?run_id=run-ledger-memory")
    assert run_listed.status_code == 200
    assert [event["id"] for event in run_listed.json()["items"]] == [item["id"]]

    status_listed = client.get("/memory/timeline/list?operation_status=failed")
    assert status_listed.status_code == 200
    assert [event["id"] for event in status_listed.json()["items"]] == [item["id"]]


def test_memory_timeline_projects_chat_mission_ingress_loop_metadata(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    sent = client.post(
        "/chat/send",
        json={"message": "/mission Preserve memory loop projection token=memoryloopsecret123", "use_llm": False},
    )
    assert sent.status_code == 200
    sent_body = sent.json()
    mission_id = str(sent_body["mission_id"])
    operation_id = str(sent_body["operation_id"])

    listed = client.get("/memory/timeline/list", params={"mission_id": mission_id})
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["kind"] == "ledger_append"
    assert item["provenance"]["source"] == "continuity.ledger"
    assert item["references"]["mission_id"] == mission_id
    assert item["loop"] == {
        "ingress_plane": "P1_INTERFACE",
        "active_stage": "execute",
        "handoff_stage": "execute",
        "handoff_action": "run_linked_operation",
        "handoff_operation_id": operation_id,
        "handoff_next_step": sent_body["loop_state"]["handoff"]["next_step"],
        "current_task_source": "mission_meta",
        "current_task_operation_id": operation_id,
        "current_task_next_step": sent_body["current_task"]["next_step"],
        "linked_operation_count": 1,
        "run_ledger_count": 1,
        "memory_receipt_count": 0,
    }
    item_text = json.dumps(item, sort_keys=True)
    assert "memoryloopsecret123" not in item_text


def test_memory_timeline_finds_completed_mission_operation_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry completed operation receipt into memory timeline",
            "summary": "Completed mission-linked operation should create ledger-backed memory evidence.",
            "requester_id": "test.memory.timeline.mission_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "memory evidence completion receipt",
            "mission_id": mission_id,
            "input": {"goal": "Create receipt-backed memory evidence"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.memory.timeline.mission_receipt", "worker_id": "test.memory.timeline.mission_receipt"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["status"] == "succeeded"
    trace_id = str(advanced_body.get("trace_id") or "")
    run_id = str(advanced_body.get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")
    receipt_handoff = advanced_body["memory_receipt"]
    assert receipt_handoff["plan_status"] == "in_progress"
    assert receipt_handoff["plan_current_step_id"] == "understand"
    assert receipt_handoff["plan_current_step_title"] == "Understand goal + constraints"
    assert receipt_handoff["plan_step_count"] == 4
    assert receipt_handoff["plan_checkpoint_count"] == 3

    listed = client.get(
        f"/memory/timeline/list?mission_id={mission_id}&operation_id={operation_id}&trace_id={trace_id}&include_payload=1"
    )
    assert listed.status_code == 200
    body = listed.json()
    receipts = [
        item
        for item in body["items"]
        if item.get("kind") == "ledger_append"
        and item.get("references", {}).get("mission_id") == mission_id
        and item.get("references", {}).get("operation_id") == operation_id
        and item.get("operation_status") == "succeeded"
    ]
    assert receipts
    receipt = receipts[0]
    assert "Mission operation completed" in receipt["message"]
    assert receipt["provenance"]["source"] == "continuity.ledger"
    assert receipt["provenance"]["domain"] == "operations"
    assert receipt["provenance"]["scope"] == "mission.loop"
    assert receipt["references"]["trace_id"] == trace_id
    assert receipt["references"]["run_id"] == run_id
    assert receipt["loop"]["active_stage"] == "interface"
    assert receipt["loop"]["handoff_stage"] == "interface"
    assert receipt["loop"]["handoff_action"] == "review_result"
    assert receipt["loop"]["handoff_operation_id"] == operation_id
    assert receipt["loop"]["handoff_trace_id"] == trace_id
    assert receipt["loop"]["handoff_run_id"] == run_id
    assert receipt["loop"]["handoff_next_step"] == "review_completed_mission"
    assert receipt["loop"]["current_task_source"] == "terminal_operation_receipt"
    assert receipt["loop"]["current_task_operation_id"] == operation_id
    assert receipt["loop"]["current_task_run_id"] == run_id
    assert receipt["loop"]["current_task_next_step"] == "review_completed_mission"
    assert receipt["loop"]["run_id"] == run_id
    assert receipt["loop"]["memory_receipt_count"] == 1
    assert receipt["loop"]["plan_status"] == "in_progress"
    assert receipt["loop"]["plan_current_step_id"] == "understand"
    assert receipt["loop"]["plan_current_step_title"] == "Understand goal + constraints"
    assert receipt["loop"]["plan_step_count"] == 4
    assert receipt["loop"]["plan_checkpoint_count"] == 3
    assert receipt["payload"]["meta"]["subsystem"] == "operations.runtime"
    assert receipt["payload"]["meta"]["operation_status"] == "succeeded"
    assert receipt["payload"]["meta"]["plan_status"] == "in_progress"
    assert receipt["payload"]["meta"]["plan_current_step_id"] == "understand"
    assert receipt["payload"]["meta"]["plan_current_step_title"] == "Understand goal + constraints"
    assert receipt["payload"]["meta"]["plan_step_count"] == 4
    assert receipt["payload"]["meta"]["plan_checkpoint_count"] == 3

    status_listed = client.get("/memory/timeline/list", params={"operation_status": "succeeded"})
    assert status_listed.status_code == 200
    assert any(item.get("references", {}).get("operation_id") == operation_id for item in status_listed.json()["items"])

    run_listed = client.get(f"/memory/timeline/list?run_id={run_id}")
    assert run_listed.status_code == 200
    assert any(item.get("references", {}).get("operation_id") == operation_id for item in run_listed.json()["items"])


def test_memory_timeline_preserves_approved_operation_receipt_posture(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry approved operation posture into memory timeline",
            "summary": "Approved mission-linked execution should retain approval posture in terminal receipts.",
            "requester_id": "test.memory.timeline.approval_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "approved memory receipt posture",
            "mission_id": mission_id,
            "input": {"user_command": "echo approved-memory-receipt", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.memory.timeline.approval"})
    assert pending.status_code == 200
    approval_id = str(pending.json()["operation"]["meta"]["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.memory.timeline.approval"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    assert executed_body["memory_receipt"]["references"]["approval_id"] == approval_id
    assert executed_body["memory_receipt"]["approval_status"] == "approved"

    listed = client.get(
        "/memory/timeline/list",
        params={
            "mission_id": mission_id,
            "operation_id": operation_id,
            "run_id": approval_id,
            "include_payload": "1",
        },
    )
    assert listed.status_code == 200
    receipts = [
        item
        for item in listed.json()["items"]
        if item.get("kind") == "ledger_append"
        and item.get("references", {}).get("operation_id") == operation_id
        and item.get("operation_status") == "succeeded"
    ]
    assert receipts
    receipt = receipts[0]
    assert receipt["references"]["approval_id"] == approval_id
    assert receipt["loop"]["handoff_approval_id"] == approval_id
    assert receipt["loop"]["handoff_approval_status"] == "approved"
    assert receipt["loop"]["current_task_approval_id"] == approval_id
    assert receipt["loop"]["current_task_approval_status"] == "approved"
    assert receipt["payload"]["meta"]["approval_status"] == "approved"


def test_memory_timeline_redacts_secrets_from_persistence_and_api(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance.redaction import REDACTED_SECRET

    client = TestClient(create_app())

    raw_openai_key = "sk-proj-" + ("a" * 48)
    raw_github_pat = "github_pat_" + ("B" * 64)
    raw_remote = "https://token-secret-123456@github.com/owner/repo.git"

    created = client.post(
        "/memory/timeline/record",
        json={
            "id": "evt-redaction",
            "kind": "memory_write",
            "severity": "info",
            "domain": "operations",
            "actor": "francis",
            "scope": "mission.loop",
            "correlation_id": "trace-redaction",
            "title": f"Captured {raw_openai_key}",
            "message": f"Operator note api_key={raw_openai_key} remote {raw_remote}",
            "tags": ["mission", raw_github_pat],
            "payload": {
                "api_key": raw_openai_key,
                "remote": raw_remote,
                "nested": {"note": f"token={raw_github_pat}", "ticket": "FR-123"},
            },
            "artifacts": [
                {
                    "id": "art-redaction",
                    "kind": "trace",
                    "url": raw_remote,
                    "meta": {"token": raw_github_pat, "ticket": "FR-123"},
                }
            ],
            "meta": {"password": "correcthorsebattery", "ticket": "FR-123"},
        },
    )
    assert created.status_code == 200
    assert created.json()["ok"] is True

    registry_path = data_root / "memory" / "timeline" / "_events.json"
    stored_text = registry_path.read_text(encoding="utf-8")
    assert raw_openai_key not in stored_text
    assert raw_github_pat not in stored_text
    assert raw_remote not in stored_text
    assert REDACTED_SECRET in stored_text
    assert "FR-123" in stored_text

    fetched = client.get("/memory/timeline/get?id=evt-redaction")
    assert fetched.status_code == 200
    fetched_text = json.dumps(fetched.json(), sort_keys=True)
    assert raw_openai_key not in fetched_text
    assert raw_github_pat not in fetched_text
    assert raw_remote not in fetched_text
    assert REDACTED_SECRET in fetched_text

    listed = client.get("/memory/timeline/list?include_payload=1&search=FR-123")
    assert listed.status_code == 200
    listed_text = json.dumps(listed.json(), sort_keys=True)
    assert raw_openai_key not in listed_text
    assert raw_github_pat not in listed_text
    assert raw_remote not in listed_text
    assert "FR-123" in listed_text

    exported = client.get("/memory/timeline/export?format=json&include_payload=1&search=FR-123")
    assert exported.status_code == 200
    assert raw_openai_key not in exported.text
    assert raw_github_pat not in exported.text
    assert raw_remote not in exported.text
    assert REDACTED_SECRET in exported.text
