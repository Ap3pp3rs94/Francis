from __future__ import annotations

import json
from pathlib import Path

_PLUGIN_ACTOR = "test.plugins.write"


def test_missions_create_list_get_update(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Carry Stage 3 continuity work",
            "summary": "Mission declared for the first real Stage 3 slice.",
            "next_step": "Link an operation and advance the mission state.",
            "requester_id": "test.missions",
            "owner_id": "stage3.owner",
            "dependency_ids": ["approval_policy", "workspace_ready", "approval_policy"],
            "escalation_path": "Escalate to operator review if the linked operation blocks.",
            "risk_tier": "high",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])
    assert created_body["history"][0]["event"] == "created"
    assert created_body["history"][0]["details"]["owner_id"] == "stage3.owner"
    assert created_body["history"][0]["details"]["dependency_count"] == 2
    assert created_body["loop_state"]["active_stage"] == "plan"
    assert created_body["loop_state"]["handoff"]["action"] == "link_operation"
    assert created_body["loop_state"]["interface"]["status"] == "available"
    assert created_body["loop_state"]["interface"]["next_step"] == "Link an operation and advance the mission state."
    assert created_body["mission"]["owner_id"] == "stage3.owner"
    assert created_body["mission"]["dependency_ids"] == ["approval_policy", "workspace_ready"]
    assert created_body["mission"]["dependency_count"] == 2
    assert created_body["mission"]["escalation_path"] == "Escalate to operator review if the linked operation blocks."

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert any(str(item.get("id")) == mission_id for item in listed_body["items"])

    operation = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linkage test",
            "input": {"goal": "Create a linked run-ledger entry"},
        },
    )
    assert operation.status_code == 200
    operation_body = operation.json()
    assert operation_body["ok"] is True
    operation_id = str(operation_body["operation_id"])

    patched = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "active",
            "next_step": "Review the linked operation and capture follow-up work.",
            "owner_id": "stage3.reviewer",
            "dependency_ids": ["approval_policy"],
            "escalation_path": "Deadletter if the operation cannot produce a receipt.",
            "add_task_ids": [operation_id],
            "actor": "test.missions",
            "note": "Mission picked up for execution.",
            "meta": {"source": "integration_test"},
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True
    assert patched_body["mission"]["status"] == "active"
    assert patched_body["mission"]["linked_task_ids"] == [operation_id]
    assert patched_body["mission"]["linked_task_count"] == 1
    assert patched_body["mission"]["owner_id"] == "stage3.reviewer"
    assert patched_body["mission"]["dependency_ids"] == ["approval_policy"]
    assert patched_body["mission"]["dependency_count"] == 1
    assert patched_body["mission"]["escalation_path"] == "Deadletter if the operation cannot produce a receipt."
    assert patched_body["mission"]["meta"]["source"] == "integration_test"
    assert patched_body["linked_operations"][0]["operation"]["id"] == operation_id
    assert patched_body["loop_state"]["active_stage"] == "execute"
    assert patched_body["loop_state"]["handoff"]["action"] == "run_linked_operation"
    assert patched_body["loop_state"]["handoff"]["operation_id"] == operation_id
    history_events = [str(item.get("event")) for item in patched_body["history"]]
    assert "status_changed" in history_events
    assert "task_links_updated" in history_events
    assert "continuity_updated" in history_events
    continuity_event = [item for item in patched_body["history"] if item.get("event") == "continuity_updated"][-1]
    assert continuity_event["details"]["owner_id"] == "stage3.reviewer"
    assert continuity_event["details"]["dependency_ids"] == ["approval_policy"]
    assert continuity_event["details"]["escalation_path"] == "Deadletter if the operation cannot produce a receipt."

    deadlettered = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "deadlettered",
            "deadletter_reason": "approval_timeout",
            "actor": "test.missions",
            "note": "Operator did not clear the required gate in time.",
        },
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is True
    assert deadlettered_body["mission"]["status"] == "deadlettered"
    assert deadlettered_body["mission"]["deadletter_reason"] == "approval_timeout"
    assert deadlettered_body["loop_state"]["active_stage"] == "deadletter"
    assert deadlettered_body["loop_state"]["handoff"]["action"] == "review_deadletter"
    assert deadlettered_body["loop_state"]["handoff"]["operation_id"] == operation_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["id"] == mission_id
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["mission"]["owner_id"] == "stage3.reviewer"
    assert fetched_body["mission"]["dependency_ids"] == ["approval_policy"]
    assert fetched_body["mission"]["escalation_path"] == "Deadletter if the operation cannot produce a receipt."
    assert fetched_body["mission"]["deadletter_reason"] == "approval_timeout"
    fetched_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert fetched_events.count("status_changed") >= 2


def test_mission_record_projection_refreshes_decided_approval_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    approval_id = "apr_projection_approved"
    approval_dir = data_root / "approvals" / "approved"
    approval_dir.mkdir(parents=True, exist_ok=True)
    (approval_dir / f"{approval_id}.json").write_text(
        json.dumps(
            {
                "id": approval_id,
                "action": "plugin.run",
                "reason": "projection approved",
                "status": "approved",
                "payload": {"plugin_id": "builtin.echo", "action": "deploy"},
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    created = client.post(
        "/missions/create",
        json={
            "objective": "Approved approval status should project on the mission record.",
            "summary": "Mission record projection should not depend on stale pending meta.",
            "status": "blocked",
            "linked_task_ids": ["tsk_projection_approved"],
            "requester_id": "test.missions.approval_projection",
            "meta": {
                "last_task_id": "tsk_projection_approved",
                "last_task_status": "accepted",
                "last_task_result_status": "needs_approval",
                "last_task_gate": "approvals_gate",
                "last_task_approval_id": approval_id,
                "last_task_approval_status": "pending",
                "last_task_next_step": "approve_exact_action",
            },
        },
    )
    assert created.status_code == 200
    mission_id = str(created.json()["mission_id"])

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["last_task_approval_id"] == approval_id
    assert fetched_body["mission"]["last_task_approval_status"] == "approved"
    assert fetched_body["queue_item"]["last_task_approval_status"] == "approved"
    assert fetched_body["queue_item"]["recommended_action"] == "run_linked_operation"
    assert fetched_body["queue_item"]["advance"]["eligible"] is True
    assert fetched_body["loop_state"]["active_stage"] == "execute"
    assert fetched_body["loop_state"]["handoff"]["action"] == "run_linked_operation"
    assert fetched_body["loop_state"]["handoff"]["approval_id"] == approval_id
    assert fetched_body["loop_state"]["handoff"]["approval_status"] == "approved"
    assert fetched_body["loop_state"]["handoff"]["operation_id"] == "tsk_projection_approved"
    assert fetched_body["loop_state"]["gate"]["status"] == "clear"
    assert fetched_body["loop_state"]["gate"]["approval_id"] == approval_id
    assert fetched_body["loop_state"]["gate"]["approval_status"] == "approved"
    assert fetched_body["loop_state"]["execute"]["approval_status"] == "approved"
    assert fetched_body["current_task"]["approval_status"] == "approved"
    assert fetched_body["current_task"]["handoff_action"] == "run_linked_operation"

    listed = client.get("/missions/list?limit=20")
    assert listed.status_code == 200
    listed_item = next(item for item in listed.json()["items"] if item["id"] == mission_id)
    assert listed_item["last_task_approval_id"] == approval_id
    assert listed_item["last_task_approval_status"] == "approved"


def test_mission_deadletter_reason_and_notes_redact_secret_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Redact mission recovery context",
            "summary": "Mission exists to verify governed recovery text.",
            "next_step": "Deadletter with operator context.",
            "requester_id": "test.missions.redaction",
        },
    )
    assert created.status_code == 200
    mission_id = str(created.json()["mission_id"])

    raw_reason = "operator note password=missiondeadlettersecret123"
    raw_note = "review note token=missionnotesecret456"
    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={"reason": raw_reason, "actor": "test.missions.redaction", "note": raw_note},
    )

    assert deadlettered.status_code == 200
    body = deadlettered.json()
    assert body["ok"] is True
    assert body["mission"]["deadletter_reason"] == "operator note password=[REDACTED:secret]"
    assert body["queue_item"]["recovery"]["reason"] == "operator note password=[REDACTED:secret]"
    history_text = (data_root / "missions" / mission_id / "history.jsonl").read_text(encoding="utf-8")
    record_text = (data_root / "missions" / mission_id / "record.json").read_text(encoding="utf-8")
    assert "missiondeadlettersecret123" not in history_text
    assert "missionnotesecret456" not in history_text
    assert "missiondeadlettersecret123" not in record_text
    assert "password=[REDACTED:secret]" in history_text
    assert "token=[REDACTED:secret]" in history_text

    queue = client.get("/missions/queue")
    assert queue.status_code == 200
    deadletter_item = next(item for item in queue.json()["deadletter"] if item.get("id") == mission_id)
    assert deadletter_item["deadletter_reason"] == "operator note password=[REDACTED:secret]"
    assert deadletter_item["history_tail"][-1]["details"]["note"] == "review note token=[REDACTED:secret]"


def test_mission_create_and_update_redact_continuity_text(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    create_secrets = {
        "objective": "missioncreateobjectivesecret123",
        "summary": "missioncreatesummarysecret123",
        "next_step": "missioncreatenextstepsecret123",
        "escalation_path": "missioncreateescalationsecret123",
    }

    created = client.post(
        "/missions/create",
        json={
            "objective": f"Carry direct mission password={create_secrets['objective']}",
            "summary": f"Create summary token={create_secrets['summary']}",
            "next_step": f"Create next step secret={create_secrets['next_step']}",
            "escalation_path": f"Create escalation api_key={create_secrets['escalation_path']}",
            "requester_id": "test.missions.redaction",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])
    assert created_body["mission"]["objective"] == "Carry direct mission password=[REDACTED:secret]"
    assert created_body["mission"]["summary"] == "Create summary token=[REDACTED:secret]"
    assert created_body["mission"]["next_step"] == "Create next step secret=[REDACTED:secret]"
    assert created_body["mission"]["escalation_path"] == "Create escalation api_key=[REDACTED:secret]"
    assert created_body["loop_state"]["interface"]["next_step"] == "Create next step secret=[REDACTED:secret]"
    assert created_body["history"][0]["details"]["objective"] == "Carry direct mission password=[REDACTED:secret]"
    assert created_body["history"][0]["details"]["next_step"] == "Create next step secret=[REDACTED:secret]"

    mission_dir = data_root / "missions" / mission_id
    record_text = (mission_dir / "record.json").read_text(encoding="utf-8")
    history_text = (mission_dir / "history.jsonl").read_text(encoding="utf-8")
    for raw_secret in create_secrets.values():
        assert raw_secret not in record_text
        assert raw_secret not in history_text

    update_secrets = {
        "summary": "missionupdatesummarysecret123",
        "next_step": "missionupdatenextstepsecret123",
        "escalation_path": "missionupdateescalationsecret123",
        "note": "missionupdatenotesecret123",
    }
    patched = client.patch(
        f"/missions/{mission_id}",
        json={
            "summary": f"Updated summary password={update_secrets['summary']}",
            "next_step": f"Updated next token={update_secrets['next_step']}",
            "escalation_path": f"Updated escalation secret={update_secrets['escalation_path']}",
            "actor": "test.missions.redaction",
            "note": f"Updated note api_key={update_secrets['note']}",
        },
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is True
    assert patched_body["mission"]["summary"] == "Updated summary password=[REDACTED:secret]"
    assert patched_body["mission"]["next_step"] == "Updated next token=[REDACTED:secret]"
    assert patched_body["mission"]["escalation_path"] == "Updated escalation secret=[REDACTED:secret]"
    assert patched_body["loop_state"]["interface"]["next_step"] == "Updated next token=[REDACTED:secret]"
    continuity_event = [item for item in patched_body["history"] if item.get("event") == "continuity_updated"][-1]
    assert continuity_event["details"]["summary"] == "Updated summary password=[REDACTED:secret]"
    assert continuity_event["details"]["next_step"] == "Updated next token=[REDACTED:secret]"
    assert continuity_event["details"]["escalation_path"] == "Updated escalation secret=[REDACTED:secret]"
    assert continuity_event["details"]["note"] == "Updated note api_key=[REDACTED:secret]"

    record_text = (mission_dir / "record.json").read_text(encoding="utf-8")
    history_text = (mission_dir / "history.jsonl").read_text(encoding="utf-8")
    persisted_text = record_text + history_text
    for raw_secret in (*create_secrets.values(), *update_secrets.values()):
        assert raw_secret not in persisted_text
    assert "password=[REDACTED:secret]" in persisted_text
    assert "token=[REDACTED:secret]" in persisted_text
    assert "api_key=[REDACTED:secret]" in persisted_text


def test_missions_create_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    set_control_mode("observe", reason="test_missions_create_block", actor="tests")

    created = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission declaration",
            "summary": "Observe mode should reject mission writes.",
            "requester_id": "test.missions.observe",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is False
    assert created_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in created_body["error"]

    listed = client.get("/missions/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["items"] == []


def test_mission_mutation_routes_are_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    created = client.post(
        "/missions/create",
        json={
            "objective": "Observe-mode mutation guard",
            "summary": "Mission should remain unchanged while posture is read-only.",
            "next_step": "Wait for operator posture change.",
            "requester_id": "test.missions.observe",
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    mission_id = str(created_body["mission_id"])

    set_control_mode("observe", reason="test_mission_mutation_block", actor="tests")

    patched = client.patch(
        f"/missions/{mission_id}",
        json={"status": "active", "summary": "should not apply", "actor": "tests"},
    )
    assert patched.status_code == 200
    patched_body = patched.json()
    assert patched_body["ok"] is False
    assert patched_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in patched_body["error"]

    ticked = client.post(f"/missions/{mission_id}/tick", json={"actor": "tests"})
    assert ticked.status_code == 200
    ticked_body = ticked.json()
    assert ticked_body["ok"] is False
    assert ticked_body["applied"] is False
    assert ticked_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in ticked_body["error"]

    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={"reason": "should_not_apply", "actor": "tests"},
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is False
    assert deadlettered_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in deadlettered_body["error"]

    advanced = client.post(f"/missions/{mission_id}/advance", json={"actor": "tests"})
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is False
    assert advanced_body["applied"] is False
    assert advanced_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in advanced_body["error"]

    replaced = client.post(f"/missions/{mission_id}/replace", json={"actor": "tests"})
    assert replaced.status_code == 200
    replaced_body = replaced.json()
    assert replaced_body["ok"] is False
    assert replaced_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in replaced_body["error"]

    tick_all = client.post("/missions/tick", json={"actor": "tests", "limit": 10})
    assert tick_all.status_code == 200
    tick_all_body = tick_all.json()
    assert tick_all_body["ok"] is False
    assert tick_all_body["status"] == "blocked"
    assert tick_all_body["items"] == []
    assert tick_all_body["applied"] == 0
    assert "Observe mode keeps Francis read-only." in tick_all_body["errors"][0]["error"]

    run_once = client.post(
        "/missions/run_once", json={"actor": "tests", "note": "observe token=missionreadonlysecret123", "limit": 10}
    )
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is False
    assert run_once_body["status"] == "blocked"
    assert "Observe mode keeps Francis read-only." in run_once_body["error"]
    assert run_once_body["request"]["actor"] == "tests"
    assert run_once_body["request"]["limit"] == 10
    assert run_once_body["request"]["note"] == "observe token=[REDACTED:secret]"
    assert "missionreadonlysecret123" not in str(run_once_body["request"])
    assert run_once_body["items"] == []
    assert run_once_body["advanced"] == 0
    assert run_once_body["processed"] == 0
    assert "Observe mode keeps Francis read-only." in run_once_body["errors"][0]["error"]

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "queued"
    assert fetched_body["mission"]["summary"] == "Mission should remain unchanged while posture is read-only."
    assert fetched_body["mission"]["next_step"] == "Wait for operator posture change."
    assert fetched_body["mission"]["deadletter_reason"] is None
    history_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert history_events == ["created"]


def test_mission_run_once_reports_failed_status_for_runtime_errors(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.api.routes import missions as mission_routes

    def boom(**_: object) -> dict[str, object]:
        raise RuntimeError("queue run exploded")

    monkeypatch.setattr(mission_routes.mission_runtime, "run_queue_once", boom)

    client = TestClient(create_app())
    run_once = client.post(
        "/missions/run_once", json={"actor": "tests", "note": "runtime token=missionfailuresecret123", "limit": 10}
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["status"] == "failed"
    assert body["error"] == "queue run exploded"
    assert body["errors"][0]["error"] == "queue run exploded"
    assert body["request"]["actor"] == "tests"
    assert body["request"]["limit"] == 10
    assert body["request"]["note"] == "runtime token=[REDACTED:secret]"
    assert "missionfailuresecret123" not in str(body["request"])
    assert body["results"] == []
    assert body["processed"] == 0


def test_mission_run_once_error_records_preserve_advance_context(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import runtime as mission_runtime

    client = TestClient(create_app())
    mission = client.post(
        "/missions/create",
        json={
            "objective": "Failed queue advance should keep actionable context",
            "summary": "Queue-run errors should preserve bounded handoff fields for the UI.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    def fail_advance(target_mission_id: str, **_: object) -> dict[str, object]:
        assert target_mission_id == mission_id
        return {
            "ok": False,
            "applied": False,
            "action": "create_first_operation",
            "status": "blocked",
            "operation_id": "tsk_failed_context",
            "approval_id": "apr_failed_context",
            "gate": "approvals_gate",
            "next_step": "review_pending_approval",
            "trace_id": "trace_failed_context",
            "operation_error": "operation_failed_context",
            "result_message": "Operation failed with recoverable context.",
            "recovery_next_step": "review_operation_detail",
            "message": "Approval review is required before execution can continue.",
            "error": "advance_failed_context",
        }

    monkeypatch.setattr(mission_runtime, "advance_mission", fail_advance)

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["status"] == "failed"
    assert body["error"] == "advance_failed_context"
    error = body["errors"][0]
    assert error["mission_id"] == mission_id
    assert error["error"] == "advance_failed_context"
    assert error["action"] == "create_first_operation"
    assert error["status"] == "blocked"
    assert error["operation_id"] == "tsk_failed_context"
    assert error["approval_id"] == "apr_failed_context"
    assert error["gate"] == "approvals_gate"
    assert error["next_step"] == "review_pending_approval"
    assert error["trace_id"] == "trace_failed_context"
    assert error["operation_error"] == "operation_failed_context"
    assert error["result_message"] == "Operation failed with recoverable context."
    assert error["recovery_next_step"] == "review_operation_detail"
    assert error["message"] == "Approval review is required before execution can continue."


def test_mission_run_once_results_preserve_advance_trace(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import runtime as mission_runtime

    client = TestClient(create_app())
    mission = client.post(
        "/missions/create",
        json={
            "objective": "Successful queue advance should keep trace context",
            "summary": "Queue-run results should preserve bounded trace fields for the UI.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    def traced_advance(target_mission_id: str, **_: object) -> dict[str, object]:
        assert target_mission_id == mission_id
        return {
            "ok": True,
            "applied": True,
            "action": "create_first_operation",
            "status": "queued",
            "operation_id": "tsk_traced_context",
            "trace_id": "trace_result_context",
            "message": "Trace-bearing operation created.",
        }

    monkeypatch.setattr(mission_runtime, "advance_mission", traced_advance)

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is True
    assert body["status"] == "succeeded"
    result = body["results"][0]
    assert result["mission_id"] == mission_id
    assert result["applied"] is True
    assert result["operation_id"] == "tsk_traced_context"
    assert result["trace_id"] == "trace_result_context"


def test_mission_linked_operation_run_updates_history_and_status(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry a linked operation to completion",
            "summary": "Mission should reflect the linked run lifecycle.",
            "next_step": "Queue the first linked operation.",
            "requester_id": "test.missions.linked",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "mission linked operation",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked plan"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    assert created_body["mission_id"] == mission_id
    assert created_body["mission_linked"] is True
    assert created_body["operation"]["meta"]["mission_id"] == mission_id
    operation_id = str(created_body["operation_id"])

    queued_mission = client.get(f"/missions/{mission_id}")
    assert queued_mission.status_code == 200
    queued_body = queued_mission.json()
    assert queued_body["mission"]["linked_task_ids"] == [operation_id]
    assert queued_body["mission"]["status"] == "queued"

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.linked"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    assert executed_body["memory_receipt"]["source"] == "continuity.ledger"
    assert executed_body["memory_receipt"]["references"]["mission_id"] == mission_id
    assert executed_body["memory_receipt"]["references"]["operation_id"] == operation_id
    assert executed_body["memory_receipt"]["handoff_gate"] == "operator_review"
    assert executed_body["memory_receipt"]["current_task_gate"] == "operator_review"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["last_task_status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "completed"
    linked_operations = fetched_body["linked_operations"]
    assert len(linked_operations) == 1
    assert linked_operations[0]["ok"] is True
    assert linked_operations[0]["operation"]["id"] == operation_id
    linked_logs = linked_operations[0]["logs"]
    assert any(item["status"] == "running" for item in linked_logs)
    assert any(item["status"] == "succeeded" for item in linked_logs)
    run_ledger = fetched_body["run_ledger"]
    assert any(item["operation_id"] == operation_id and item["status"] == "running" for item in run_ledger)
    assert any(item["operation_id"] == operation_id and item["status"] == "succeeded" for item in run_ledger)
    receipt_summary = fetched_body["receipt_summary"]
    assert receipt_summary["linked_operation_count"] == 1
    assert receipt_summary["run_ledger_count"] >= 2
    assert receipt_summary["history_count"] >= 2
    assert receipt_summary["memory_receipt_count"] >= 1
    assert receipt_summary["latest_memory_receipt"]["source"] == "continuity.ledger"
    assert receipt_summary["latest_memory_receipt"]["mission_id"] == mission_id
    assert receipt_summary["latest_memory_receipt"]["operation_id"] == operation_id
    assert receipt_summary["latest_memory_receipt"]["handoff_gate"] == "operator_review"
    assert receipt_summary["latest_memory_receipt"]["current_task_gate"] == "operator_review"
    assert receipt_summary["current_operation_id"] == operation_id
    assert receipt_summary["current_operation_status"] == "succeeded"
    assert receipt_summary["latest_run_event"] == run_ledger[0]["name"]
    assert receipt_summary["latest_run_status"] == run_ledger[0]["status"]
    assert receipt_summary["latest_history_event"] == fetched_body["history"][-1]["event"]
    assert fetched_body["memory_receipt_count"] >= 1
    assert fetched_body["latest_memory_receipt"]["source"] == "continuity.ledger"
    assert fetched_body["latest_memory_receipt"]["mission_id"] == mission_id
    assert fetched_body["latest_memory_receipt"]["operation_id"] == operation_id
    assert fetched_body["latest_memory_receipt"]["handoff_gate"] == "operator_review"
    assert fetched_body["latest_memory_receipt"]["current_task_gate"] == "operator_review"
    assert fetched_body["memory_receipts"][0]["operation_id"] == operation_id
    assert fetched_body["current_task"]["gate"] == "operator_review"
    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "interface"
    assert loop_state["handoff"]["stage"] == "interface"
    assert loop_state["handoff"]["action"] == "review_result"
    assert loop_state["handoff"]["gate"] == "operator_review"
    assert loop_state["handoff"]["operation_id"] == operation_id
    assert loop_state["handoff"]["latest_event"] == fetched_body["history"][-1]["event"]
    assert loop_state["handoff"]["latest_ts"] == fetched_body["history"][-1]["ts"]
    assert loop_state["handoff"]["next_step"] == "review_completed_mission"
    assert loop_state["interface"]["status"] == "available"
    assert loop_state["interface"]["operation_id"] == operation_id
    assert loop_state["interface"]["latest_event"] == receipt_summary["latest_run_event"]
    assert loop_state["interface"]["latest_receipt_status"] == receipt_summary["latest_run_status"]
    assert loop_state["memory"]["memory_receipt_count"] >= 1
    assert loop_state["memory"]["gate"] == "operator_review"
    assert loop_state["memory"]["latest_memory_receipt"]["mission_id"] == mission_id
    assert loop_state["memory"]["latest_memory_receipt"]["operation_id"] == operation_id
    history_events = [str(item.get("event")) for item in fetched_body["history"]]
    assert "linked_task_transition" in history_events
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert any(item.get("details", {}).get("task_status") == "running" for item in transition_events)
    assert any(item.get("details", {}).get("task_status") == "completed" for item in transition_events)


def test_mission_detail_surfaces_failed_operation_memory_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Expose failed linked operation memory",
            "summary": "Mission detail should retain failed terminal operation receipts.",
            "next_step": "Review failed operation receipts before retrying.",
            "requester_id": "test.missions.failed_memory_receipt",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "mission detail failed operation memory receipt",
            "mission_id": mission_id,
            "input": {"action": "run", "input": "missing plugin id"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.failed_memory_receipt"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is False
    assert executed_body["status"] == "failed"
    assert executed_body["memory_receipt"]["operation_status"] == "failed"
    receipt_refs = executed_body["memory_receipt"]["references"]
    assert receipt_refs["mission_id"] == mission_id
    assert receipt_refs["operation_id"] == operation_id
    assert str(receipt_refs["trace_id"]).startswith("trace_")
    assert str(receipt_refs["run_id"]).startswith("run_")

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "failed"
    assert fetched_body["mission"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["last_task_status"] == "failed"
    assert fetched_body["memory_receipt_count"] >= 1
    assert fetched_body["memory_receipts"][0]["operation_id"] == operation_id
    assert fetched_body["memory_receipts"][0]["operation_status"] == "failed"

    receipt_summary = fetched_body["receipt_summary"]
    assert receipt_summary["current_operation_id"] == operation_id
    assert receipt_summary["current_operation_status"] == "failed"
    assert receipt_summary["memory_receipt_count"] >= 1
    assert receipt_summary["latest_memory_receipt"]["mission_id"] == mission_id
    assert receipt_summary["latest_memory_receipt"]["operation_id"] == operation_id
    assert receipt_summary["latest_memory_receipt"]["operation_status"] == "failed"

    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "deadletter"
    assert loop_state["handoff"]["action"] == "retry_or_deadletter"
    assert loop_state["memory"]["status"] == "recorded"
    assert "terminal-operation memory receipt" in loop_state["memory"]["detail"]
    assert loop_state["memory"]["latest_memory_receipt"]["mission_id"] == mission_id
    assert loop_state["memory"]["latest_memory_receipt"]["operation_id"] == operation_id
    assert loop_state["memory"]["latest_memory_receipt"]["operation_status"] == "failed"


def test_mission_linked_plugin_run_surfaces_operation_trace(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry trace-bearing plugin continuity",
            "summary": "Mission should surface traces from linked operation execution.",
            "requester_id": "test.missions.trace",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    built = client.post(
        "/plugins/build",
        json={"name": "Mission Trace Plugin", "description": "mission trace", "actor": _PLUGIN_ACTOR},
    )
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "mission trace projection",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "run", "input": "hello from mission trace"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.trace"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    trace_id = str(executed_body["operation"].get("trace_id") or "")
    run_id = str(executed_body["operation"].get("run_id") or "")
    assert trace_id.startswith("trace_")
    assert run_id.startswith("run_")

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    linked_operation = fetched_body["linked_operations"][0]["operation"]
    assert linked_operation["id"] == operation_id
    assert linked_operation["trace_id"] == trace_id
    assert linked_operation["meta"]["trace_id"] == trace_id
    assert linked_operation["run_id"] == run_id
    assert linked_operation["meta"]["run_id"] == run_id
    assert fetched_body["receipt_summary"]["current_trace_id"] == trace_id
    assert fetched_body["receipt_summary"]["current_run_id"] == run_id
    assert fetched_body["current_task"]["trace_id"] == trace_id
    assert fetched_body["current_task"]["run_id"] == run_id
    assert fetched_body["loop_state"]["trace"]["trace_id"] == trace_id
    assert fetched_body["loop_state"]["trace"]["run_id"] == run_id
    assert fetched_body["loop_state"]["memory"]["run_id"] == run_id
    assert fetched_body["loop_state"]["interface"]["run_id"] == run_id


def test_mission_linked_supervised_exec_surfaces_artifact_handle(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry artifact-backed operation continuity",
            "summary": "Mission should surface supervised execution artifact handles.",
            "requester_id": "test.missions.artifact",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "mission artifact projection",
            "mission_id": mission_id,
            "input": {"user_command": "echo mission-artifact", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.artifact"})
    assert pending.status_code == 200
    approval_id = str(pending.json()["operation"]["meta"]["approval_id"])
    assert approval_id

    approved = client.post(
        "/approvals/decision", json={"id": approval_id, "action": "approve", "actor": "test.approvals.decision"}
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.artifact"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    artifact_dir = str(executed_body["operation"].get("artifact_dir") or "")
    run_id = str(executed_body["operation"].get("run_id") or "")
    assert artifact_dir
    assert Path(artifact_dir).exists()
    assert run_id == approval_id

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    linked_operation = fetched_body["linked_operations"][0]["operation"]
    assert linked_operation["id"] == operation_id
    assert linked_operation["artifact_dir"] == artifact_dir
    assert linked_operation["meta"]["artifact_dir"] == artifact_dir
    assert linked_operation["run_id"] == run_id
    assert fetched_body["receipt_summary"]["current_artifact_dir"] == artifact_dir
    assert fetched_body["receipt_summary"]["current_run_id"] == run_id
    assert fetched_body["latest_memory_receipt"]["approval_id"] == approval_id
    assert fetched_body["latest_memory_receipt"]["approval_status"] == "approved"
    assert fetched_body["current_task"]["artifact_dir"] == artifact_dir
    assert fetched_body["current_task"]["run_id"] == run_id
    assert fetched_body["loop_state"]["trace"]["artifact_dir"] == artifact_dir
    assert fetched_body["loop_state"]["trace"]["run_id"] == run_id
    assert fetched_body["loop_state"]["memory"]["approval_id"] == approval_id
    assert fetched_body["loop_state"]["memory"]["approval_status"] == "approved"
    assert fetched_body["loop_state"]["active_stage"] == "interface"
    assert fetched_body["loop_state"]["handoff"]["stage"] == "interface"
    assert fetched_body["loop_state"]["handoff"]["action"] == "review_result"
    assert fetched_body["loop_state"]["handoff"]["approval_id"] == approval_id
    assert fetched_body["loop_state"]["handoff"]["approval_status"] == "approved"
    assert fetched_body["loop_state"]["interface"]["artifact_dir"] == artifact_dir
    assert fetched_body["loop_state"]["interface"]["run_id"] == run_id


def test_mission_linked_governance_hold_updates_blocked_state(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Carry governed deploy continuity",
            "summary": "Mission should surface governance holds from linked operations.",
            "requester_id": "test.missions.governance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["mission"]["status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_task_status"] == "accepted"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "trust_gate"
    assert fetched_body["mission"]["meta"]["last_task_next_step"] == "raise_trust_or_reduce_risk"
    linked_operations = fetched_body["linked_operations"]
    assert len(linked_operations) == 1
    assert linked_operations[0]["operation"]["id"] == operation_id
    assert any(item["name"] == "governance_hold" for item in linked_operations[0]["logs"])
    run_ledger = fetched_body["run_ledger"]
    assert any(item["operation_id"] == operation_id and item["name"] == "governance_hold" for item in run_ledger)
    assert any(item["operation_id"] == operation_id and item["status"] == "blocked" for item in run_ledger)
    receipt_summary = fetched_body["receipt_summary"]
    assert receipt_summary["linked_operation_count"] == 1
    assert receipt_summary["run_ledger_count"] >= 1
    assert receipt_summary["history_count"] >= 1
    assert receipt_summary["current_operation_id"] == operation_id
    assert receipt_summary["current_operation_status"] == "blocked"
    assert receipt_summary["current_gate"] == "trust_gate"
    assert receipt_summary["latest_run_event"] == run_ledger[0]["name"]
    assert receipt_summary["latest_history_event"] == fetched_body["history"][-1]["event"]
    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "gate"
    assert loop_state["handoff"]["stage"] == "gate"
    assert loop_state["handoff"]["action"] == "raise_trust_or_reduce_risk"
    assert loop_state["handoff"]["operation_id"] == operation_id
    assert loop_state["handoff"]["gate"] == "trust_gate"
    assert loop_state["gate"]["gate"] == "trust_gate"
    assert loop_state["gate"]["next_step"] == "raise_trust_or_reduce_risk"
    assert loop_state["execute"]["next_step"] == "raise_trust_or_reduce_risk"
    assert loop_state["trace"]["latest_event"] == run_ledger[0]["name"]
    assert loop_state["trace"]["latest_receipt_status"] == run_ledger[0]["status"]
    assert loop_state["trace"]["latest_ts"]
    assert loop_state["interface"]["status"] == "available"
    assert loop_state["interface"]["operation_id"] == operation_id
    assert loop_state["interface"]["gate"] == "trust_gate"
    assert loop_state["interface"]["next_step"] == "raise_trust_or_reduce_risk"
    assert loop_state["interface"]["latest_receipt_status"] == run_ledger[0]["status"]
    assert fetched_body["current_task"]["latest_receipt_status"] == run_ledger[0]["status"]
    assert loop_state["memory"]["latest_event"] == fetched_body["history"][-1]["event"]
    assert loop_state["memory"]["latest_ts"] == fetched_body["history"][-1]["ts"]
    transition_events = [item for item in fetched_body["history"] if item.get("event") == "linked_task_transition"]
    assert transition_events
    assert transition_events[-1]["details"]["gate"] == "trust_gate"
    assert transition_events[-1]["details"]["mission_status_after"] == "blocked"


def test_mission_loop_state_uses_current_task_when_multiple_operations_are_linked(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Keep loop state pinned to the current blocked operation",
            "summary": "Older queued work must not hide the latest governance hold.",
            "requester_id": "test.missions.current_task",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    first = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "older queued operation",
            "mission_id": mission_id,
            "input": {"goal": "Older queued work should remain visible but not current."},
        },
    )
    assert first.status_code == 200
    first_operation_id = str(first.json()["operation_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    second = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "newer blocked operation",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert second.status_code == 200
    second_operation_id = str(second.json()["operation_id"])

    blocked = client.post(f"/operations/{second_operation_id}/run", json={"worker_id": "test.missions.current_task"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["linked_task_ids"] == [first_operation_id, second_operation_id]
    assert fetched_body["mission"]["last_task_id"] == second_operation_id
    assert fetched_body["mission"]["last_task_result_status"] == "blocked"
    assert fetched_body["mission"]["last_task_gate"] == "trust_gate"
    assert fetched_body["mission"]["last_task_next_step"] == "raise_trust_or_reduce_risk"
    assert fetched_body["mission"]["meta"]["last_task_id"] == second_operation_id

    loop_state = fetched_body["loop_state"]
    assert loop_state["active_stage"] == "gate"
    assert loop_state["handoff"]["action"] == "raise_trust_or_reduce_risk"
    assert loop_state["handoff"]["operation_id"] == second_operation_id
    assert loop_state["gate"]["operation_id"] == second_operation_id
    assert loop_state["execute"]["operation_id"] == second_operation_id
    assert loop_state["plan"]["operation_id"] == second_operation_id
    assert loop_state["plan"]["count"] == 2


def test_mission_tick_reconciles_pending_link_and_is_idempotent(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Reconcile mission from linked queued work",
            "summary": "Tick should project the latest linked task into mission continuity.",
            "requester_id": "test.missions.tick",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "queued mission tick",
            "mission_id": mission_id,
            "input": {"goal": "Create a queued linked operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    first_tick = client.post(
        f"/missions/{mission_id}/tick",
        json={"actor": "test.missions.tick", "note": "reconcile queued task"},
    )
    assert first_tick.status_code == 200
    first_tick_body = first_tick.json()
    assert first_tick_body["ok"] is True
    assert first_tick_body["applied"] is True
    assert first_tick_body["mission"]["status"] == "queued"
    assert first_tick_body["mission"]["meta"]["last_task_id"] == operation_id
    assert first_tick_body["mission"]["meta"]["last_task_status"] == "pending"
    assert first_tick_body["loop_state"]["active_stage"] == "execute"
    assert first_tick_body["loop_state"]["handoff"]["action"] == "run_linked_operation"
    assert first_tick_body["loop_state"]["handoff"]["operation_id"] == operation_id
    tick_events = [item for item in first_tick_body["history"] if item.get("event") == "mission_ticked"]
    assert tick_events
    assert tick_events[-1]["details"]["latest_task_status"] == "pending"

    second_tick = client.post(
        f"/missions/{mission_id}/tick",
        json={"actor": "test.missions.tick", "note": "repeat reconcile"},
    )
    assert second_tick.status_code == 200
    second_tick_body = second_tick.json()
    assert second_tick_body["ok"] is True
    assert second_tick_body["applied"] is False
    second_tick_events = [item for item in second_tick_body["history"] if item.get("event") == "mission_ticked"]
    assert len(second_tick_events) == len(tick_events)


def test_mission_deadletter_endpoint_moves_blocked_mission_cleanly(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Deadletter a blocked mission",
            "summary": "Governed mission should move cleanly into deadletter.",
            "requester_id": "test.missions.deadletter",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "blocked for deadletter",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.deadletter"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    deadlettered = client.post(
        f"/missions/{mission_id}/deadletter",
        json={
            "reason": "operator_abandoned_after_governance_hold",
            "actor": "test.missions.deadletter",
            "note": "Mission will not be retried.",
        },
    )
    assert deadlettered.status_code == 200
    deadlettered_body = deadlettered.json()
    assert deadlettered_body["ok"] is True
    assert deadlettered_body["mission"]["status"] == "deadlettered"
    assert deadlettered_body["mission"]["deadletter_reason"] == "operator_abandoned_after_governance_hold"
    assert deadlettered_body["loop_state"]["active_stage"] == "deadletter"
    assert deadlettered_body["loop_state"]["handoff"]["action"] == "review_deadletter"
    assert deadlettered_body["loop_state"]["handoff"]["operation_id"] == operation_id
    recovery = deadlettered_body["queue_item"]["recovery"]
    assert recovery["source_status"] == "deadlettered"
    assert recovery["action"] == "review_deadletter"
    assert recovery["target_id"] == operation_id
    assert recovery["reason"] == "operator_abandoned_after_governance_hold"
    assert "not reopened automatically" in recovery["next_step"]
    assert recovery["operator_required"] is True
    assert recovery["automatic_retry"] is False
    assert recovery["read_only"] is True

    history_events = [str(item.get("event")) for item in deadlettered_body["history"]]
    assert "status_changed" in history_events
    assert "continuity_updated" in history_events

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "deadlettered"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] == "blocked"
    assert fetched_body["queue_item"]["recovery"]["action"] == "review_deadletter"

    ticked = client.post(f"/missions/{mission_id}/tick", json={"actor": "test.missions.deadletter"})
    assert ticked.status_code == 200
    ticked_body = ticked.json()
    assert ticked_body["ok"] is True
    assert ticked_body["applied"] is False
    assert ticked_body["mission"]["status"] == "deadlettered"
    assert ticked_body["loop_state"]["active_stage"] == "deadletter"
    assert ticked_body["loop_state"]["handoff"]["action"] == "review_deadletter"

    replacement = client.post(
        f"/missions/{mission_id}/replace",
        json={
            "actor": "test.missions.deadletter",
            "note": "declare replacement after deadletter receipts",
        },
    )
    assert replacement.status_code == 200
    replacement_body = replacement.json()
    assert replacement_body["ok"] is True
    replacement_id = str(replacement_body["replacement_mission_id"])
    assert replacement_body["source_mission"]["status"] == "deadlettered"
    assert replacement_body["source_queue_item"]["recovery"]["last_review_outcome"] == "replacement_declared"
    assert replacement_body["source_queue_item"]["recovery"]["last_review_target_id"] == replacement_id
    assert replacement_body["source_queue_item"]["recovery"]["replacement_mission_id"] == replacement_id
    assert replacement_body["source_queue_item"]["recovery"]["replacement_status"] == "queued"
    assert replacement_body["mission"]["status"] == "queued"
    assert replacement_body["mission"]["linked_task_ids"] == []
    assert replacement_body["mission"]["meta"]["replacement_for_status"] == "deadlettered"
    assert replacement_body["mission"]["meta"]["replacement_source_action"] == "review_deadletter"
    assert replacement_body["linked_operations"] == []


def test_mission_replace_declares_bounded_replacement_from_failed_source(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Recover failed mission with replacement",
            "summary": "Source work failed and should not be reopened automatically.",
            "next_step": "Review failed task receipts before replacing.",
            "requester_id": "test.missions.replace",
            "owner_id": "stage3.owner",
            "priority": 7,
            "risk_tier": "high",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    failed = client.patch(
        f"/missions/{mission_id}",
        json={
            "status": "failed",
            "actor": "test.missions.replace",
            "note": "simulate terminal failed source",
            "meta": {
                "last_task_id": "tsk_failed_replacement",
                "last_task_status": "failed",
                "last_task_result_status": "failed",
                "last_task_reason": "source operation failed with bounded receipts",
                "last_task_next_step": "retry or replace explicitly",
            },
        },
    )
    assert failed.status_code == 200
    assert failed.json()["mission"]["status"] == "failed"

    replaced = client.post(
        f"/missions/{mission_id}/replace",
        json={
            "objective": "Replacement mission after failed source",
            "actor": "test.missions.replace",
            "note": "declare replacement after failed receipts",
            "meta": {"operator_decision": "replace_source"},
        },
    )
    assert replaced.status_code == 200
    body = replaced.json()
    assert body["ok"] is True
    assert body["status"] == "queued"
    replacement_id = str(body["replacement_mission_id"])
    assert replacement_id.startswith("msn_")
    assert body["message"] == "replacement_declared"

    assert body["source_mission"]["id"] == mission_id
    assert body["source_mission"]["status"] == "failed"
    assert body["source_mission"]["meta"]["last_recovery_action"] == "retry_or_deadletter"
    assert body["source_mission"]["meta"]["last_recovery_outcome"] == "replacement_declared"
    assert body["source_mission"]["meta"]["last_recovery_target_id"] == replacement_id
    assert body["source_queue_item"]["recovery"]["last_review_outcome"] == "replacement_declared"
    assert body["source_queue_item"]["recovery"]["last_review_target_id"] == replacement_id
    assert body["source_queue_item"]["recovery"]["replacement_mission_id"] == replacement_id
    assert body["source_queue_item"]["recovery"]["replacement_status"] == "queued"
    assert body["source_queue_item"]["recovery"]["automatic_retry"] is False

    replacement = body["mission"]
    assert replacement["id"] == replacement_id
    assert replacement["status"] == "queued"
    assert replacement["linked_task_ids"] == []
    assert replacement["meta"]["operator_decision"] == "replace_source"
    assert replacement["meta"]["replacement_for_mission_id"] == mission_id
    assert replacement["meta"]["replacement_for_status"] == "failed"
    assert replacement["meta"]["replacement_source_action"] == "retry_or_deadletter"
    assert replacement["meta"]["replacement_source_target_id"] == "tsk_failed_replacement"
    assert replacement["meta"]["replacement_declared_by"] == "test.missions.replace"
    assert replacement["replacement_for_mission_id"] == mission_id
    assert replacement["replacement_for_status"] == "failed"
    assert replacement["replacement_source_action"] == "retry_or_deadletter"
    assert replacement["replacement_source_target_id"] == "tsk_failed_replacement"
    assert replacement["replacement_declared_by"] == "test.missions.replace"
    assert body["linked_operations"] == []
    assert body["run_ledger"] == []

    history_events = [str(item.get("event")) for item in body["history"]]
    assert history_events[-1] == "replacement_declared"
    assert body["history"][-1]["details"]["source_mission_id"] == mission_id
    assert body["history"][-1]["details"]["automatic_retry"] is False
    assert body["history"][-1]["details"]["source_reopened"] is False

    source = client.get(f"/missions/{mission_id}")
    assert source.status_code == 200
    source_body = source.json()
    assert source_body["mission"]["status"] == "failed"
    assert source_body["queue_item"]["recovery"]["last_review_target_id"] == replacement_id
    assert source_body["queue_item"]["recovery"]["replacement_mission_id"] == replacement_id
    assert source_body["queue_item"]["recovery"]["replacement_status"] == "queued"
    assert source_body["history"][-1]["event"] == "recovery_review"

    completed_replacement = client.patch(
        f"/missions/{replacement_id}",
        json={
            "status": "completed",
            "actor": "test.missions.replace",
            "note": "replacement completed",
            "meta": {
                "last_task_id": "tsk_replacement_followthrough",
                "last_task_status": "completed",
            },
        },
    )
    assert completed_replacement.status_code == 200

    source_after_replacement = client.get(f"/missions/{mission_id}")
    assert source_after_replacement.status_code == 200
    followthrough = source_after_replacement.json()["queue_item"]["recovery"]
    assert followthrough["replacement_mission_id"] == replacement_id
    assert followthrough["replacement_status"] == "completed"
    assert followthrough["replacement_last_task_id"] == "tsk_replacement_followthrough"
    assert followthrough["replacement_last_task_status"] == "completed"
    assert followthrough["replacement_terminal"] is True


def test_mission_run_once_advances_safe_queue_actions(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    ready = client.post(
        "/missions/create",
        json={
            "objective": "Create the first linked operation",
            "summary": "Mission has no linked task yet.",
            "priority": 8,
            "requester_id": "test.missions.queue",
        },
    )
    assert ready.status_code == 200
    ready_id = str(ready.json()["mission_id"])

    blocked = client.post(
        "/missions/create",
        json={
            "objective": "Resolve governed blocker",
            "summary": "Mission should surface a trust blocker.",
            "priority": 9,
            "requester_id": "test.missions.queue",
        },
    )
    assert blocked.status_code == 200
    blocked_id = str(blocked.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    blocked_operation = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue blocker",
            "mission_id": blocked_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert blocked_operation.status_code == 200
    blocked_operation_id = str(blocked_operation.json()["operation_id"])

    blocked_run = client.post(f"/operations/{blocked_operation_id}/run", json={"worker_id": "test.missions.queue"})
    assert blocked_run.status_code == 200
    assert blocked_run.json()["status"] == "blocked"

    run_once = client.post(
        "/missions/run_once", json={"actor": "test.missions.queue", "note": "queue reconcile", "limit": 10}
    )
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    assert run_once_body["status"] == "succeeded"
    assert run_once_body["request"] == {
        "actor": "test.missions.queue",
        "note": "queue reconcile",
        "limit": 10,
    }
    assert run_once_body["processed"] >= 2
    assert run_once_body["advanced"] == 1
    assert run_once_body["counts"]["blocked"] >= 1
    assert run_once_body["counts"]["queued"] >= 1
    results = run_once_body["results"]
    blocked_result = next(item for item in results if item["mission_id"] == blocked_id)
    assert blocked_result["applied"] is False
    assert blocked_result["action"] == "raise_trust_or_reduce_risk"
    assert blocked_result["mission"]["id"] == blocked_id
    assert blocked_result["loop_state"]["active_stage"] == "gate"
    assert blocked_result["handoff"]["action"] == "raise_trust_or_reduce_risk"
    assert blocked_result["handoff"]["operation_id"] == blocked_operation_id
    assert blocked_result["linked_operation_count"] == 1
    assert blocked_result["run_ledger_count"] >= 1
    ready_result = next(item for item in results if item["mission_id"] == ready_id)
    assert ready_result["applied"] is True
    assert ready_result["action"] == "create_first_operation"
    assert ready_result["operation_id"]
    assert ready_result["operation"]["id"] == ready_result["operation_id"]
    assert ready_result["mission"]["id"] == ready_id
    assert ready_result["loop_state"]["active_stage"] == "execute"
    assert ready_result["handoff"]["action"] == "run_linked_operation"
    assert ready_result["linked_operation_count"] == 1
    assert ready_result["history_count"] >= 2
    queue_items = run_once_body["items"]
    assert queue_items[0]["id"] == blocked_id
    assert queue_items[0]["recommended_action"] == "raise_trust_or_reduce_risk"
    assert queue_items[0]["action_target_id"] == blocked_operation_id
    assert queue_items[0]["advance"]["eligible"] is False
    assert queue_items[0]["advance"]["action"] == "raise_trust_or_reduce_risk"
    assert queue_items[0]["advance"]["target_id"] == blocked_operation_id
    assert queue_items[0]["history_count"] >= 1
    assert queue_items[0]["latest_history_event"]
    assert len(queue_items[0]["history_tail"]) >= 1
    ready_item = next(item for item in queue_items if item["id"] == ready_id)
    assert ready_item["recommended_action"] == "run_linked_operation"
    assert ready_item["advance"]["eligible"] is True
    assert ready_item["advance"]["action"] == "run_linked_operation"
    assert ready_item["linked_task_count"] == 1
    assert ready_item["last_advance_action"] == "create_first_operation"
    assert ready_item["history_count"] >= 2
    assert ready_item["latest_history_event"]
    assert len(ready_item["history_tail"]) >= 1


def test_mission_run_once_waits_for_unresolved_dependencies(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    dependency = client.post(
        "/missions/create",
        json={
            "objective": "Finish prerequisite evidence",
            "summary": "The dependent mission should not move before this is complete.",
            "requester_id": "test.missions.dependencies",
            "status": "active",
            "priority": 1,
        },
    )
    assert dependency.status_code == 200
    dependency_id = str(dependency.json()["mission_id"])

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Only advance after the dependency is complete",
            "summary": "Queue runner must not fake progress while the dependency is waiting.",
            "requester_id": "test.missions.dependencies",
            "dependency_ids": [dependency_id],
            "escalation_path": "Ask the operator whether to deadletter or replace the dependency.",
            "priority": 9,
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    first_run = client.post("/missions/run_once", json={"actor": "test.missions.dependencies", "limit": 10})
    assert first_run.status_code == 200
    first_body = first_run.json()
    assert first_body["ok"] is True
    assert first_body["advanced"] == 0
    dependent_result = next(item for item in first_body["results"] if item["mission_id"] == mission_id)
    assert dependent_result["applied"] is False
    assert dependent_result["action"] == "wait_for_dependency"
    assert dependent_result["operation_id"] == dependency_id
    assert "Dependency" in dependent_result["message"]
    dependent_queue_item = next(item for item in first_body["items"] if item["id"] == mission_id)
    assert dependent_queue_item["recommended_action"] == "wait_for_dependency"
    assert dependent_queue_item["advance"]["eligible"] is False
    assert dependent_queue_item["advance"]["action"] == "wait_for_dependency"
    assert dependent_queue_item["advance"]["target_id"] == dependency_id
    assert dependent_queue_item["dependency_state"]["status"] == "waiting"
    assert dependent_queue_item["dependency_state"]["first_unresolved"]["id"] == dependency_id
    detail = client.get(f"/missions/{mission_id}")
    assert detail.status_code == 200
    detail_body = detail.json()
    assert detail_body["queue_item"]["recommended_action"] == "wait_for_dependency"
    assert detail_body["queue_item"]["advance"]["eligible"] is False
    assert detail_body["queue_item"]["advance"]["action"] == "wait_for_dependency"
    assert detail_body["queue_item"]["advance"]["target_id"] == dependency_id

    completed = client.patch(
        f"/missions/{dependency_id}",
        json={"status": "completed", "actor": "test.missions.dependencies", "note": "dependency satisfied"},
    )
    assert completed.status_code == 200
    assert completed.json()["mission"]["status"] == "completed"

    second_run = client.post("/missions/run_once", json={"actor": "test.missions.dependencies", "limit": 10})
    assert second_run.status_code == 200
    second_body = second_run.json()
    assert second_body["ok"] is True
    assert second_body["advanced"] == 1
    advanced_result = next(item for item in second_body["results"] if item["mission_id"] == mission_id)
    assert advanced_result["applied"] is True
    assert advanced_result["action"] == "create_first_operation"
    assert advanced_result["operation_id"]


def test_mission_run_once_executes_linked_queued_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Run the linked queued operation",
            "summary": "Queue runner should execute the linked task in one bounded pass.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "run_once linked operation",
            "mission_id": mission_id,
            "input": {"goal": "Create a queued plan for the queue runner"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    assert run_once_body["status"] == "succeeded"
    assert run_once_body["advanced"] == 1
    results = run_once_body["results"]
    mission_result = next(item for item in results if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "run_linked_operation"
    assert mission_result["operation_id"] == operation_id
    assert mission_result["operation"]["id"] == operation_id
    assert mission_result["memory_receipt"]["source"] == "continuity.ledger"
    assert mission_result["memory_receipt"]["references"]["mission_id"] == mission_id
    assert mission_result["memory_receipt"]["references"]["operation_id"] == operation_id
    assert mission_result["mission"]["id"] == mission_id
    assert mission_result["loop_state"]["active_stage"] == "interface"
    assert mission_result["handoff"]["stage"] == "interface"
    assert mission_result["handoff"]["action"] == "review_result"
    assert mission_result["handoff"]["operation_id"] == operation_id
    assert mission_result["run_ledger_count"] >= 2

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "run_linked_operation"
    assert fetched_body["mission"]["meta"]["last_advance_outcome"] == "succeeded"
    assert fetched_body["queue_item"]["recommended_action"] == "review_completion"
    assert fetched_body["queue_item"]["advance"]["eligible"] is False
    assert fetched_body["queue_item"]["advance"]["action"] == "review_completion"


def test_mission_store_run_once_uses_bounded_runtime_path(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.missions import run_queue_once as mission_run_queue_once

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Store queue runner should create bounded progress",
            "summary": "Top-level mission runner should use the same safe queue behavior as the API route.",
            "requester_id": "test.missions.store",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    result = mission_run_queue_once(limit=10, actor="test.missions.store", note="store queue run")
    assert result["ok"] is True
    assert result["status"] == "succeeded"
    assert result["request"] == {
        "actor": "test.missions.store",
        "note": "store queue run",
        "limit": 10,
    }
    assert result["advanced"] == 1
    mission_result = next(item for item in result["results"] if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "create_first_operation"
    assert mission_result["operation_id"]
    assert mission_result["operation"]["id"] == mission_result["operation_id"]

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "create_first_operation"


def test_mission_advance_creates_first_operation_with_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Build the first mission plan",
            "summary": "Mission needs its first linked operation.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "note": "spawn first linked run"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "create_first_operation"
    operation_id = str(advanced_body["operation_id"])
    assert operation_id
    assert advanced_body["operation"]["name"] == "plan.create"
    assert advanced_body["operation"]["meta"]["orb_plane"] == "P7_EXECUTION"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["linked_task_ids"] == [operation_id]
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "create_first_operation"
    assert fetched_body["mission"]["meta"]["last_advance_operation_id"] == operation_id
    assert fetched_body["mission"]["meta"]["last_advance_operation_name"] == "plan.create"
    assert fetched_body["mission"]["meta"]["last_advance_operation_plane"] == "P7_EXECUTION"
    assert fetched_body["queue_item"]["last_advance_operation_name"] == "plan.create"
    assert fetched_body["queue_item"]["last_advance_operation_plane"] == "P7_EXECUTION"
    assert fetched_body["queue_item"]["current_task"]["operation_name"] == "plan.create"
    assert fetched_body["queue_item"]["current_task"]["operation_plane"] == "P7_EXECUTION"
    assert fetched_body["queue_item"]["current_task"]["advance_action"] == "create_first_operation"
    history_events = [item for item in fetched_body["history"] if item.get("event") == "advance_receipt"]
    assert history_events
    assert history_events[-1]["details"]["operation_name"] == "plan.create"
    assert history_events[-1]["details"]["operation_plane"] == "P7_EXECUTION"
    assert history_events[-1]["details"]["applied"] is True


def test_mission_advance_runs_linked_queued_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Advance a queued linked operation",
            "summary": "Mission runner should execute the queued linked task.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "advance linked run",
            "mission_id": mission_id,
            "input": {"goal": "Create a linked queued plan"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["operation_id"] == operation_id
    assert advanced_body["memory_receipt"]["source"] == "continuity.ledger"
    assert advanced_body["memory_receipt"]["references"]["mission_id"] == mission_id
    assert advanced_body["memory_receipt"]["references"]["operation_id"] == operation_id
    operation_output = advanced_body["operation"]["output"]
    assert operation_output["plan_status"] == "in_progress"
    assert operation_output["plan_current_step_id"] == "understand"
    assert operation_output["plan_current_step_title"] == "Understand goal + constraints"
    assert operation_output["plan_step_count"] == 4
    assert operation_output["plan_checkpoint_count"] == 3

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "completed"
    assert fetched_body["mission"]["meta"]["last_advance_action"] == "run_linked_operation"
    plan_stage = fetched_body["loop_state"]["plan"]
    assert plan_stage["operation_id"] == operation_id
    assert plan_stage["plan_status"] == "in_progress"
    assert plan_stage["plan_current_step_id"] == "understand"
    assert plan_stage["plan_current_step_title"] == "Understand goal + constraints"
    assert plan_stage["plan_step_count"] == 4
    assert plan_stage["plan_checkpoint_count"] == 3
    advance_events = [item for item in fetched_body["history"] if item.get("event") == "advance_receipt"]
    assert advance_events
    assert advance_events[-1]["details"]["operation_id"] == operation_id


def test_mission_advance_surfaces_failed_operation_recovery_handoff(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Advance should expose failed operation recovery context",
            "summary": "A failed linked operation should return receipt-backed recovery fields.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "advance failed linked run",
            "mission_id": mission_id,
            "input": {"action": "run", "input": "missing plugin id"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is False
    assert advanced_body["applied"] is False
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["operation_id"] == operation_id
    assert advanced_body["status"] == "failed"
    assert advanced_body["operation_error"] == "plugin_id_required"
    assert advanced_body["recovery_next_step"] == "review_operation_detail"
    assert advanced_body["memory_receipt"]["operation_status"] == "failed"
    assert advanced_body["memory_receipt"]["operation_error"] == "plugin_id_required"
    assert advanced_body["memory_receipt"]["recovery_next_step"] == "review_operation_detail"
    assert advanced_body["latest_memory_receipt"]["operation_id"] == operation_id
    assert advanced_body["latest_memory_receipt"]["operation_error"] == "plugin_id_required"
    assert advanced_body["loop_state"]["active_stage"] == "deadletter"
    assert advanced_body["loop_state"]["handoff"]["action"] == "retry_or_deadletter"


def test_mission_advance_respects_governance_blockers(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Blocked mission should not auto-advance",
            "summary": "Mission runner must not bypass governance.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "blocked advance",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.missions.advance"})
    assert blocked.status_code == 200
    assert blocked.json()["status"] == "blocked"

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is False
    assert advanced_body["action"] == "raise_trust_or_reduce_risk"
    assert advanced_body["operation_id"] == operation_id
    assert advanced_body["loop_state"]["active_stage"] == "gate"
    assert advanced_body["loop_state"]["handoff"]["action"] == "raise_trust_or_reduce_risk"
    assert advanced_body["loop_state"]["handoff"]["operation_id"] == operation_id
    assert advanced_body["run_ledger"]

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["status"] == "blocked"
    assert fetched_body["mission"]["meta"]["last_advance_outcome"] == "requires_operator"


def test_mission_advance_surfaces_approval_handoff_for_governed_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Approval-bound mission should surface exact handoff",
            "summary": "Mission advance should return the approval needed for the next step.",
            "requester_id": "test.missions.advance",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "mission-advance-approval-handoff", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approval-bound advance",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    advanced = client.post(
        f"/missions/{mission_id}/advance",
        json={"actor": "test.missions.advance", "worker_id": "test.missions.advance"},
    )
    assert advanced.status_code == 200
    advanced_body = advanced.json()
    assert advanced_body["ok"] is True
    assert advanced_body["applied"] is True
    assert advanced_body["action"] == "run_linked_operation"
    assert advanced_body["operation_id"] == operation_id
    assert advanced_body["status"] == "queued"
    assert advanced_body["approval_id"]
    assert advanced_body["gate"] == "approvals_gate"
    assert advanced_body["next_step"] == "review_pending_approval"
    assert advanced_body["loop_state"]["active_stage"] == "gate"
    assert advanced_body["loop_state"]["handoff"]["action"] == "review_pending_approval"
    assert advanced_body["loop_state"]["handoff"]["approval_id"] == advanced_body["approval_id"]
    assert advanced_body["loop_state"]["handoff"]["operation_id"] == operation_id
    assert advanced_body["queue_item"]["recommended_action"] == "review_pending_approval"
    assert advanced_body["queue_item"]["action_target_id"] == operation_id
    assert advanced_body["queue_item"]["last_task_approval_id"] == advanced_body["approval_id"]
    assert advanced_body["queue_item"]["last_task_approval_status"] == "pending"
    assert advanced_body["queue_item"]["advance"]["eligible"] is False
    assert advanced_body["queue_item"]["advance"]["action"] == "review_pending_approval"
    assert advanced_body["queue_item"]["current_task"]["source"] == "mission_meta"
    assert advanced_body["queue_item"]["current_task"]["operation_id"] == operation_id
    assert advanced_body["queue_item"]["current_task"]["gate"] == "approvals_gate"
    assert advanced_body["queue_item"]["current_task"]["approval_id"] == advanced_body["approval_id"]
    assert advanced_body["current_task"]["source"] == "mission_meta"
    assert advanced_body["current_task"]["operation_id"] == operation_id
    assert advanced_body["current_task"]["task_status"] == "accepted"
    assert advanced_body["current_task"]["operation_status"] == "queued"
    assert advanced_body["current_task"]["result_status"] in {"pending", "needs_approval"}
    assert advanced_body["current_task"]["gate"] == "approvals_gate"
    assert advanced_body["current_task"]["approval_id"] == advanced_body["approval_id"]
    assert advanced_body["current_task"]["approval_status"] == "pending"
    assert advanced_body["current_task"]["handoff_action"] == "review_pending_approval"
    assert advanced_body["current_task"]["latest_receipt_event"] == "governance_hold"
    assert advanced_body["history"][-1]["event"] == "advance_receipt"

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "approvals_gate"
    assert fetched_body["mission"]["meta"]["last_task_result_status"] in {"pending", "needs_approval"}
    assert fetched_body["current_task"]["operation_id"] == operation_id
    assert fetched_body["current_task"]["approval_id"] == advanced_body["approval_id"]
    assert fetched_body["queue_item"]["last_task_approval_id"] == advanced_body["approval_id"]
    assert fetched_body["queue_item"]["last_advance_operation_id"] == operation_id
    assert fetched_body["queue_item"]["last_advance_outcome"] == "queued"


def test_mission_run_once_surfaces_approval_handoff_for_governed_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    mission = client.post(
        "/missions/create",
        json={
            "objective": "Queue runner should surface approval handoff",
            "summary": "Bounded queue run should return approval ids for governed next steps.",
            "requester_id": "test.missions.queue",
        },
    )
    assert mission.status_code == 200
    mission_id = str(mission.json()["mission_id"])

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "actor": _PLUGIN_ACTOR,
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    plugin_id = str(installed.json()["plugin_id"])

    raised = client.post(
        "/trust/set", json={"level": 6, "reason": "mission-run-once-approval-handoff", "actor": "test.trust.write"}
    )
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "approval-bound queue runner",
            "mission_id": mission_id,
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_once = client.post("/missions/run_once", json={"actor": "test.missions.queue", "limit": 10})
    assert run_once.status_code == 200
    run_once_body = run_once.json()
    assert run_once_body["ok"] is True
    mission_result = next(item for item in run_once_body["results"] if item["mission_id"] == mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "run_linked_operation"
    assert mission_result["operation_id"] == operation_id
    assert mission_result["status"] == "queued"
    assert mission_result["approval_id"]
    assert mission_result["gate"] == "approvals_gate"
    assert mission_result["next_step"] == "review_pending_approval"
    assert mission_result["mission"]["id"] == mission_id
    assert mission_result["loop_state"]["active_stage"] == "gate"
    assert mission_result["handoff"]["action"] == "review_pending_approval"
    assert mission_result["handoff"]["approval_id"] == mission_result["approval_id"]
    assert mission_result["handoff"]["operation_id"] == operation_id
    assert mission_result["queue_item"]["recommended_action"] == "review_pending_approval"
    assert mission_result["queue_item"]["action_target_id"] == operation_id
    assert mission_result["queue_item"]["last_task_approval_id"] == mission_result["approval_id"]
    assert mission_result["queue_item"]["last_task_approval_status"] == "pending"
    assert mission_result["queue_item"]["advance"]["eligible"] is False
    assert mission_result["queue_item"]["advance"]["action"] == "review_pending_approval"
    assert mission_result["queue_item"]["current_task"]["source"] == "mission_meta"
    assert mission_result["queue_item"]["current_task"]["operation_id"] == operation_id
    assert mission_result["queue_item"]["current_task"]["gate"] == "approvals_gate"
    assert mission_result["queue_item"]["current_task"]["approval_id"] == mission_result["approval_id"]
    assert mission_result["current_task"]["source"] == "mission_meta"
    assert mission_result["current_task"]["operation_id"] == operation_id
    assert mission_result["current_task"]["task_status"] == "accepted"
    assert mission_result["current_task"]["gate"] == "approvals_gate"
    assert mission_result["current_task"]["approval_id"] == mission_result["approval_id"]
    assert mission_result["current_task"]["approval_status"] == "pending"
    assert mission_result["current_task"]["handoff_action"] == "review_pending_approval"
    assert mission_result["linked_operation_count"] == 1

    fetched = client.get(f"/missions/{mission_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["mission"]["meta"]["last_task_gate"] == "approvals_gate"
