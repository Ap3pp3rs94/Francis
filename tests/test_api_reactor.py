from __future__ import annotations

import json
from pathlib import Path

from francis.missions import store as mission_store
from francis.operations import runtime as operations_runtime
from francis.reactor import dispatch as reactor_dispatch

_REACTOR_ACTOR = "test.reactor.write"
_APPROVAL_ACTOR = "test.reactor.approvals.decide"


def test_reactor_event_routes_enqueue_and_readback(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    empty_status = client.get("/reactor/status")
    assert empty_status.status_code == 200
    assert empty_status.json()["ok"] is True
    assert empty_status.json()["total"] == 0
    assert empty_status.json()["dispatch_engine"] == "partial"
    assert empty_status.json()["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "trigger_type": "mission_tick",
            "summary": "Mission queue has a ready item",
            "actor": _REACTOR_ACTOR,
            "mode": "pilot",
            "mission_id": "msn_reactor_ready",
            "operation_id": "tsk_reactor_ready",
            "risk_tier": "normal",
            "action_class": "classify",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "stop_conditions": ["advanced_once", "approval_required", "budget_exhausted"],
            "metadata": {"queue": "mission"},
        },
    )
    assert queued.status_code == 200
    queued_body = queued.json()
    assert queued_body["ok"] is True
    assert queued_body["applied"] is True
    event = queued_body["event"]
    event_id = str(queued_body["event_id"])
    assert event["trigger"]["source"] == "mission_queue"
    assert event["classification"]["mode"] == "pilot"
    assert event["classification"]["stable_state"] == "awaiting_dispatch"
    assert event["bounds"]["max_actions"] == 2
    assert event["dispatch"]["applied"] is False
    assert event["governance"]["dispatch_authority"] is False

    listed = client.get("/reactor/events/list", params={"trigger_source": "mission_queue"})
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["event_id"] == event_id

    fetched = client.get("/reactor/events/get", params={"id": event_id})
    assert fetched.status_code == 200
    assert fetched.json()["ok"] is True
    assert fetched.json()["item"]["event_id"] == event_id

    dispatch_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record a bounded dispatch attempt before execution exists",
        },
    )
    assert dispatch_attempt.status_code == 200
    attempt_body = dispatch_attempt.json()
    assert attempt_body["ok"] is True
    assert attempt_body["applied"] is True
    assert attempt_body["receipt"]["kind"] == "reactor.dispatch_attempt.receipt"
    assert attempt_body["receipt"]["execution_started"] is False
    assert attempt_body["event"]["status"] == "dispatch_deferred"
    assert attempt_body["event"]["dispatch"]["engine"] == "not_implemented"
    assert attempt_body["event"]["governance"]["execution_authority"] is False
    verification = attempt_body["event"]["latest_verification_receipt"]
    assert verification["kind"] == "reactor.verification.receipt"
    assert verification["verification_status"] == "not_available"
    assert verification["verification_outcome"] == "dispatch_engine_not_implemented"
    assert verification["source_receipt_kind"] == "reactor.dispatch_attempt.receipt"
    assert verification["verified"] is False
    assert verification["completion_claimed"] is False
    assert verification["completion_claim_allowed"] is False
    assert verification["governance"]["execution_authority"] is False
    stable_return = attempt_body["event"]["latest_stable_return"]
    assert stable_return["kind"] == "reactor.stable_return.receipt"
    assert stable_return["status"] == "settled"
    assert stable_return["route"] == "dispatch_engine"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch_attempt.receipt"
    assert stable_return["returned_to_stable_state"] is True
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is False
    assert stable_return["governance"]["execution_authority"] is False
    assert stable_return["verification_receipt_id"] == verification["receipt_id"]
    assert stable_return["verification_status"] == "not_available"
    assert stable_return["verification_outcome"] == "dispatch_engine_not_implemented"
    assert attempt_body["event"]["latest_receipt"]["receipt_id"] == stable_return["receipt_id"]

    verification_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.verification.receipt"},
    )
    assert verification_list.status_code == 200
    assert {item["event_id"] for item in verification_list.json()["items"]} == {event_id}

    stable_return_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.stable_return.receipt"},
    )
    assert stable_return_list.status_code == 200
    assert {item["event_id"] for item in stable_return_list.json()["items"]} == {event_id}

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["total"] == 1
    assert status.json()["trigger_source_counts"] == {"mission_queue": 1}
    assert status.json()["status_counts"] == {"dispatch_deferred": 1}
    assert status.json()["verification_counts"] == {"not_available": 1}
    assert status.json()["verification_outcome_counts"] == {"dispatch_engine_not_implemented": 1}
    assert status.json()["stable_return_counts"] == {"settled": 1}


def test_reactor_classification_dispatch_records_read_only_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "observer_anomaly",
            "trigger_type": "watcher_stale",
            "summary": "Observer watcher stale event needs bounded classification",
            "actor": _REACTOR_ACTOR,
            "mode": "assist",
            "risk_tier": "normal",
            "max_actions": 2,
            "max_runtime_seconds": 90,
            "metadata": {"surface": "observer", "token": "ghp_" + ("r" * 36)},
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])
    assert queued.json()["event"]["classification"]["action_class"] == "classify"

    dispatched = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "classify observer anomaly without execution",
        },
    )
    assert dispatched.status_code == 200
    body = dispatched.json()
    assert body["ok"] is True
    event = body["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "classification_recorded"
    assert event["dispatch"]["engine"] == "classification"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is False
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["route"] == "classification"
    assert execution["outcome"] == "observer_anomaly_classified"
    assert execution["trigger_source"] == "observer_anomaly"
    assert execution["trigger_type"] == "watcher_stale"
    assert execution["metadata_keys"] == ["surface", "token"]
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is True
    assert execution["readback_only"] is True
    assert execution["memory_write"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["classification_authority"] is True

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "observer_anomaly_classified"
    assert verification["route"] == "classification"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is True
    assert verification["governance"]["execution_authority"] is False

    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "classification"
    assert stable_return["stable_state"] == "classification_recorded"
    assert stable_return["execution_started"] is False
    assert stable_return["dispatch_applied"] is True
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["memory_write"] is False

    listed = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.dispatch.execution.receipt"},
    )
    assert listed.status_code == 200
    assert {item["event_id"] for item in listed.json()["items"]} == {event_id}

    status = client.get("/reactor/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status_body["status_counts"] == {"dispatch_completed": 1}
    assert status_body["dispatch_execution_counts"] == {"completed": 1}
    assert status_body["verification_counts"] == {"passed": 1}
    assert status_body["verification_outcome_counts"] == {"observer_anomaly_classified": 1}


def test_reactor_proposal_review_dispatch_reads_forge_quality_without_authority(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))
    proposal_id = "plugin_proposal_reactor_quality"
    proposal_path = data_root / "artifacts" / "plugins" / "proposals" / f"{proposal_id}.json"
    proposal_path.parent.mkdir(parents=True, exist_ok=True)
    proposal_path.write_text(
        json.dumps(
            {
                "kind": "plugin.proposal",
                "proposal_id": proposal_id,
                "plugin_id": "generated.reactor_quality",
                "status": "staged",
                "friction": {
                    "summary": "Repeated Reactor quality review needs a bounded readback pass.",
                    "evidence": ["mission.reactor.quality.repeat"],
                },
                "quality_requirements": {
                    "tests": ["tests/test_api_reactor.py::proposal_review"],
                    "docs": ["README.md"],
                    "risk_tier": "normal",
                    "validation_path": ["tests/test_api_reactor.py"],
                    "known_limits": ["readback only"],
                },
                "validation": {
                    "validation_receipt_id": "validation_reactor_quality",
                    "validation_receipt_path": "data/artifacts/plugins/validations/validation_reactor_quality.json",
                },
            }
        ),
        encoding="utf-8",
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    enqueued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "forge_proposal",
            "summary": "Inspect the staged Forge proposal through Reactor.",
            "mode": "pilot",
            "actor": _REACTOR_ACTOR,
            "max_actions": 1,
            "metadata": {"proposal_id": proposal_id},
        },
    )
    assert enqueued.status_code == 200
    enqueued_body = enqueued.json()
    assert enqueued_body["event"]["classification"]["action_class"] == "proposal_review"
    event_id = str(enqueued_body["event_id"])

    dispatched = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "read proposal quality without deciding or promoting it",
        },
    )

    assert dispatched.status_code == 200
    body = dispatched.json()
    assert body["ok"] is True
    assert body["applied"] is True
    event = body["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "proposal_review_inspected"
    assert event["dispatch"]["engine"] == "proposal_review"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is False
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["route"] == "proposal_review"
    assert execution["status"] == "completed"
    assert execution["outcome"] == "proposal_review_ready"
    assert execution["proposal_id"] == proposal_id
    assert execution["plugin_id"] == "generated.reactor_quality"
    assert execution["quality_ready"] is True
    assert execution["missing_requirements"] == []
    assert execution["readback_only"] is True
    assert execution["proposal_decision_applied"] is False
    assert execution["promotion_applied"] is False
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is True
    assert execution["memory_write"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["approval_authority"] is False
    assert execution["governance"]["promotion_authority"] is False
    assert execution["governance"]["memory_write"] is False
    assert execution["governance"]["authority_source"] == "reactor.write"
    verification = event["latest_verification_receipt"]
    assert verification["route"] == "proposal_review"
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "proposal_review_ready"
    assert verification["verified"] is True
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is True
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "proposal_review"
    assert stable_return["dispatch_applied"] is True
    assert stable_return["execution_started"] is False
    assert stable_return["governance"]["execution_authority"] is False
    assert stable_return["governance"]["dispatch_authority"] is True

    status = client.get("/reactor/status")
    assert status.status_code == 200
    status_body = status.json()
    assert status_body["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status_body["status_counts"] == {"dispatch_completed": 1}
    assert status_body["dispatch_execution_counts"] == {"completed": 1}
    assert status_body["verification_counts"] == {"passed": 1}
    assert status_body["verification_outcome_counts"] == {"proposal_review_ready": 1}
    history = client.get(
        "/reactor/proposal_reviews/history/list",
        params={"proposal_id": proposal_id, "quality_ready": "true"},
    )
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["ok"] is True
    assert history_body["total"] == 1
    assert history_body["ready_total"] == 1
    assert history_body["blocked_total"] == 0
    assert history_body["governance"]["execution_authority"] is False
    assert history_body["governance"]["dispatch_authority"] is False
    history_item = history_body["items"][0]
    assert history_item["kind"] == "reactor.proposal_review.history.readback"
    assert history_item["event_id"] == event_id
    assert history_item["proposal_id"] == proposal_id
    assert history_item["plugin_id"] == "generated.reactor_quality"
    assert history_item["route"] == "proposal_review"
    assert history_item["quality_ready"] is True
    assert history_item["readback_only"] is True
    assert history_item["proposal_decision_applied"] is False
    assert history_item["promotion_applied"] is False
    assert history_item["execution_started"] is False
    assert history_item["memory_write"] is False
    assert history_item["source_governance"]["dispatch_authority"] is True
    assert history_item["governance"]["proposal_decision_authority"] is False
    assert history_item["governance"]["promotion_authority"] is False
    plugin_history = client.get(
        "/reactor/proposal_reviews/history/list",
        params={"plugin_id": "generated.reactor_quality"},
    )
    assert plugin_history.status_code == 200
    assert [item["event_id"] for item in plugin_history.json()["items"]] == [event_id]


def test_reactor_operation_dispatch_route_runs_existing_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write", "operations.run"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor route dispatch should run an existing operation",
        input={"goal": "prove reactor API operation dispatch"},
        actor=_REACTOR_ACTOR,
    )
    assert operation["ok"] is True
    operation_id = str(operation["operation_id"])

    client = TestClient(create_app())
    enqueued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Dispatch this existing operation through Reactor.",
            "mode": "pilot",
            "action_class": "operation_run",
            "operation_id": operation_id,
            "actor": _REACTOR_ACTOR,
            "max_actions": 1,
        },
    )
    assert enqueued.status_code == 200
    event_id = str(enqueued.json()["event_id"])

    dispatched = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "run existing operation through reactor dispatch",
        },
    )

    assert dispatched.status_code == 200
    body = dispatched.json()
    assert body["ok"] is True
    assert body["applied"] is True
    event = body["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "dispatch_succeeded"
    assert event["dispatch"]["engine"] == "operation_run"
    assert event["dispatch"]["applied"] is True
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["operation_id"] == operation_id
    assert execution["status"] == "completed"
    assert execution["outcome"] == "operation_succeeded"
    assert execution["governance"]["authority_source"] == "operations.run"
    assert execution["governance"]["approval_authority"] is False
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verified"] is True
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "operation_run"
    assert stable_return["dispatch_applied"] is True

    execution_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.dispatch.execution.receipt"},
    )
    assert execution_list.status_code == 200
    assert {item["event_id"] for item in execution_list.json()["items"]} == {event_id}
    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_completed": 1}
    assert status.json()["dispatch_execution_counts"] == {"completed": 1}
    assert status.json()["verification_counts"] == {"passed": 1}


def test_reactor_mission_tick_dispatch_route_runs_bounded_queue(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write", "missions.write"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    mission, error = mission_store.create_mission(
        mission_store.MissionCreateRequest(
            objective="advance one mission through the reactor API mission tick",
            requester_id=_REACTOR_ACTOR,
            summary="API mission tick dispatch proof",
        )
    )
    assert error is None
    assert mission is not None

    client = TestClient(create_app())
    enqueued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Dispatch one mission queue tick through Reactor.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "actor": _REACTOR_ACTOR,
            "max_actions": 1,
        },
    )
    assert enqueued.status_code == 200
    event_id = str(enqueued.json()["event_id"])

    dispatched = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "run one mission queue tick through reactor dispatch",
        },
    )

    assert dispatched.status_code == 200
    body = dispatched.json()
    assert body["ok"] is True
    assert body["applied"] is True
    event = body["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "dispatch_succeeded"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["applied"] is True
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["route"] == "mission_tick"
    assert execution["status"] == "completed"
    assert execution["outcome"] == "mission_tick_succeeded"
    assert execution["mission_queue_limit"] == 1
    assert execution["mission_queue_processed"] >= 1
    assert execution["mission_queue_applied"] >= 1
    assert execution["mission_queue_advanced"] >= 1
    assert execution["mission_queue_error_count"] == 0
    assert mission.mission_id in execution["mission_ids"]
    assert execution["operation_ids"]
    assert execution["governance"]["authority_source"] == "missions.write"
    assert execution["governance"]["approval_authority"] is False
    assert execution["memory_write"] is False
    verification = event["latest_verification_receipt"]
    assert verification["route"] == "mission_tick"
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "mission_tick_succeeded"
    assert verification["verified"] is True
    assert verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "mission_tick"
    assert stable_return["dispatch_applied"] is True

    execution_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.dispatch.execution.receipt"},
    )
    assert execution_list.status_code == 200
    assert {item["event_id"] for item in execution_list.json()["items"]} == {event_id}
    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status.json()["status_counts"] == {"dispatch_completed": 1}
    assert status.json()["dispatch_execution_counts"] == {"completed": 1}
    assert status.json()["verification_counts"] == {"passed": 1}


def test_reactor_mission_tick_dispatch_route_blocks_without_missions_scope(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    mission, error = mission_store.create_mission(
        mission_store.MissionCreateRequest(
            objective="stay queued when Reactor lacks mission write authority",
            requester_id=_REACTOR_ACTOR,
            summary="API mission tick permission boundary proof",
        )
    )
    assert error is None
    assert mission is not None

    client = TestClient(create_app())
    enqueued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Mission tick dispatch must require mission write authority.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "actor": _REACTOR_ACTOR,
            "max_actions": 1,
        },
    )
    assert enqueued.status_code == 200
    event_id = str(enqueued.json()["event_id"])

    dispatched = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "attempt mission tick without missions.write",
        },
    )

    assert dispatched.status_code == 200
    body = dispatched.json()
    assert body["ok"] is True
    assert body["applied"] is True
    event = body["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "mission_tick_permission_denied"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert event["dispatch"]["allowed"] is False
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["blocked_route"] == "operator_review"
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["kind"] == "reactor.dispatch.execution.receipt"
    assert execution["status"] == "blocked"
    assert execution["outcome"] == "mission_tick_permission_denied"
    assert execution["route"] == "mission_tick"
    assert execution["gate"] == "missions_write_permission_gate"
    assert execution["execution_started"] is False
    assert execution["dispatch_applied"] is False
    assert execution["governance"]["execution_authority"] is False
    assert execution["governance"]["approval_authority"] is False
    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "not_run"
    assert verification["verification_outcome"] == "mission_tick_permission_denied"
    assert verification["route"] == "operator_review"
    assert verification["verified"] is False
    assert verification["completion_claim_allowed"] is False
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "operator_review"
    assert stable_return["stable_state"] == "mission_tick_permission_denied"
    assert stable_return["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert stable_return["dispatch_applied"] is False
    assert stable_return["execution_started"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["memory_write"] is False

    review_queue = client.get("/reactor/review_queue", params={"route": "operator_review"})
    assert review_queue.status_code == 200
    assert review_queue.json()["available_total"] == 1
    assert review_queue.json()["items"][0]["review"]["gate"] == "mission_tick_permission_denied"

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_blocked": 1}
    assert status.json()["stable_state_counts"] == {"mission_tick_permission_denied": 1}
    assert status.json()["dispatch_execution_counts"] == {"blocked": 1}
    assert status.json()["verification_counts"] == {"not_run": 1}
    assert status.json()["verification_outcome_counts"] == {"mission_tick_permission_denied": 1}

    stored_mission, read_error = mission_store.read_mission(mission.mission_id)
    assert read_error is None
    assert stored_mission is not None
    assert stored_mission.status == mission_store.MissionStatus.QUEUED


def test_reactor_mission_tick_retry_exhaustion_route_queues_deadletter(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write", "missions.write"]}),
    )
    run_calls: list[int] = []

    def fail_mission_tick(*, limit: int, actor: str, note: str) -> dict[str, object]:
        run_calls.append(limit)
        return {
            "ok": False,
            "status": "failed",
            "processed": 1,
            "total": 1,
            "applied": 0,
            "advanced": 0,
            "counts": {"queued": 1, "active": 0, "blocked": 0, "failed": 0, "deadlettered": 0},
            "errors": [{"mission_id": "msn_failed_tick_api", "error": "synthetic mission tick failure"}],
            "request": {"actor": actor, "note": note, "limit": limit},
        }

    monkeypatch.setattr(reactor_dispatch.mission_runtime, "run_queue_once", fail_mission_tick)

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())
    enqueued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Failed mission tick should exhaust into deadletter through API.",
            "mode": "pilot",
            "action_class": "mission_tick",
            "actor": _REACTOR_ACTOR,
            "max_actions": 2,
            "max_retries": 1,
            "backoff_seconds": 0,
        },
    )
    assert enqueued.status_code == 200
    event_id = str(enqueued.json()["event_id"])

    first_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "run failed mission tick and schedule retry",
        },
    )
    assert first_attempt.status_code == 200
    first_event = first_attempt.json()["event"]
    assert first_event["status"] == "dispatch_failed"
    assert first_event["stable_state"] == "awaiting_retry"
    retry_schedule_id = str(first_event["latest_retry_schedule"]["retry_schedule_id"])

    due = client.post(
        "/reactor/retries/mark_due",
        json={
            "retry_schedule_id": retry_schedule_id,
            "actor": _REACTOR_ACTOR,
            "reason": "make failed mission tick retry due",
        },
    )
    assert due.status_code == 200
    assert due.json()["status"] == "retry_due"

    retry_attempt = client.post(
        "/reactor/retries/dispatch_attempt",
        json={
            "retry_schedule_id": retry_schedule_id,
            "actor": _REACTOR_ACTOR,
            "reason": "retry failed mission tick and exhaust budget",
        },
    )
    assert retry_attempt.status_code == 200
    body = retry_attempt.json()
    assert body["ok"] is True
    assert body["status"] == "retry_dispatch_attempted"
    event = body["event"]
    assert event["status"] == "dispatch_failed"
    assert event["stable_state"] == "retry_budget_exhausted"
    assert event["dispatch"]["engine"] == "mission_tick"
    assert run_calls == [2, 2]
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["route"] == "mission_tick"
    assert execution["status"] == "failed"
    assert execution["outcome"] == "mission_tick_failed"
    assert execution["attempt_count"] == 2
    retry_exhausted = event["latest_retry_exhausted"]
    assert retry_exhausted["outcome"] == "mission_tick_failed"
    assert retry_exhausted["deadletter_enqueued"] is True
    deadletter_item = event["latest_deadletter_item"]
    assert deadletter_item["status"] == "queued"
    assert deadletter_item["source_receipt_kind"] == "reactor.retry_exhausted.receipt"
    assert event["latest_stable_return"]["route"] == "deadletter_queue"
    assert event["latest_verification_receipt"]["route"] == "deadletter_queue"
    assert event["latest_verification_receipt"]["verification_outcome"] == "mission_tick_failed"

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_failed": 1}
    assert status.json()["stable_state_counts"] == {"retry_budget_exhausted": 1}
    assert status.json()["retry_schedule_counts"] == {"attempted": 1}
    assert status.json()["retry_dispatch_attempt_counts"] == {"attempted": 1}
    assert status.json()["retry_exhausted_counts"] == {"exhausted": 1}
    assert status.json()["deadletter_queue_counts"] == {"queued": 1}


def test_reactor_event_routes_filter_review_readbacks(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    approval = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs review",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_filter",
        },
    ).json()
    approval_id = str(approval["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": approval_id, "actor": _REACTOR_ACTOR},
    )

    budget = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted event needs deadletter review",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 0,
        },
    ).json()
    budget_id = str(budget["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": budget_id, "actor": _REACTOR_ACTOR},
    )

    retry = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Retry-exhausted event needs review",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 1,
            "max_retries": 1,
        },
    ).json()
    retry_id = str(retry["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )

    approval_list = client.get("/reactor/events/list", params={"review_route": "approval_queue"})
    assert approval_list.status_code == 200
    assert {item["event_id"] for item in approval_list.json()["items"]} == {approval_id}

    deadletter_blockers = client.get("/reactor/events/list", params={"blocker_route": "deadletter_candidate"})
    assert deadletter_blockers.status_code == 200
    assert {item["event_id"] for item in deadletter_blockers.json()["items"]} == {budget_id}

    deadletter_review = client.get("/reactor/events/list", params={"review_route": "deadletter_candidate"})
    assert deadletter_review.status_code == 200
    assert {item["event_id"] for item in deadletter_review.json()["items"]} == {budget_id, retry_id}

    exhausted_state = client.get("/reactor/events/list", params={"stable_state": "retry_budget_exhausted"})
    assert exhausted_state.status_code == 200
    assert {item["event_id"] for item in exhausted_state.json()["items"]} == {retry_id}

    exhausted_receipt = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.retry_exhausted.receipt"},
    )
    assert exhausted_receipt.status_code == 200
    assert {item["event_id"] for item in exhausted_receipt.json()["items"]} == {retry_id}


def test_reactor_review_queue_route_projects_readonly_items(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    approval = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval-gated mutation needs review",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "approval_id": "appr_reactor_review_queue",
        },
    ).json()
    approval_id = str(approval["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": approval_id, "actor": _REACTOR_ACTOR},
    )

    retry = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Retry candidate needs scheduler review",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 1,
            "max_retries": 2,
        },
    ).json()
    retry_id = str(retry["event_id"])
    client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": retry_id, "actor": _REACTOR_ACTOR},
    )

    queue = client.get("/reactor/review_queue")

    assert queue.status_code == 200
    body = queue.json()
    assert body["ok"] is True
    assert body["available_total"] == 2
    assert body["route_counts"] == {"approval_queue": 1, "retry_backoff": 1}
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["approval_authority"] is False
    assert body["governance"]["dispatch_authority"] is False

    by_id = {item["event_id"]: item for item in body["items"]}
    assert by_id[approval_id]["review"]["route"] == "approval_queue"
    assert by_id[approval_id]["review"]["gate"] == "approval_required"
    assert by_id[approval_id]["trigger"]["approval_id"] == "appr_reactor_review_queue"
    assert by_id[retry_id]["review"]["route"] == "retry_backoff"
    assert by_id[retry_id]["review"]["receipt_kind"] == "reactor.retry.schedule.receipt"

    retry_only = client.get("/reactor/review_queue", params={"route": "retry_backoff"})
    assert retry_only.status_code == 200
    assert retry_only.json()["available_total"] == 1
    assert retry_only.json()["items"][0]["event_id"] == retry_id


def test_reactor_retry_schedule_readback_routes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Deferred Reactor dispatch needs a durable retry schedule",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 1,
            "max_retries": 2,
            "backoff_seconds": 45,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "schedule retry without starting retry execution",
        },
    )
    assert attempted.status_code == 200
    event = attempted.json()["event"]
    retry_candidate = event["dispatch"]["retry_candidate"]
    retry_schedule = event["dispatch"]["retry_schedule"]
    retry_schedule_receipt = event["dispatch"]["retry_schedule_receipt"]
    retry_schedule_id = retry_schedule["retry_schedule_id"]
    assert retry_candidate["retry_scheduled"] is True
    assert retry_schedule["kind"] == "reactor.retry_schedule.item"
    assert retry_schedule["candidate_id"] == retry_candidate["candidate_id"]
    assert retry_schedule["status"] == "scheduled"
    assert retry_schedule["due_after_ts"] == retry_candidate["next_retry_after_ts"]
    assert retry_schedule["retry_started"] is False
    assert retry_schedule["execution_started"] is False
    assert retry_schedule["governance"]["retry_execution_authority"] is False
    assert retry_schedule_receipt["kind"] == "reactor.retry.schedule.receipt"
    assert retry_schedule_receipt["retry_schedule_id"] == retry_schedule_id
    assert retry_schedule_receipt["retry_scheduled"] is True
    assert event["latest_verification_receipt"]["verification_outcome"] == "retry_scheduled"
    assert event["latest_stable_return"]["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert event["latest_stable_return"]["retry_scheduled"] is True

    listed = client.get("/reactor/retries/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["ok"] is True
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["retry_schedule_id"] == retry_schedule_id
    assert listed_body["items"][0]["event_id"] == event_id
    assert listed_body["governance"]["retry_execution_authority"] is False

    scheduled_only = client.get("/reactor/retries/list", params={"status": "scheduled"})
    assert scheduled_only.status_code == 200
    assert {item["retry_schedule_id"] for item in scheduled_only.json()["items"]} == {retry_schedule_id}

    fetched = client.get("/reactor/retries/get", params={"id": retry_schedule_id})
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["retry_schedule_id"] == retry_schedule_id
    assert fetched_body["item"]["retry_started"] is False
    assert fetched_body["item"]["execution_started"] is False

    schedule_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.retry.schedule.receipt"},
    )
    assert schedule_receipts.status_code == 200
    assert {item["event_id"] for item in schedule_receipts.json()["items"]} == {event_id}

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["retry_schedule_counts"] == {"scheduled": 1}
    assert status.json()["retry_schedule_total"] == 1


def test_reactor_retry_due_handoff_route_records_readback_without_execution(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Deferred Reactor dispatch retry can become due",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 1,
            "max_retries": 2,
            "backoff_seconds": 0,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    retry_schedule_id = str(attempted.json()["event"]["dispatch"]["retry_schedule"]["retry_schedule_id"])

    due = client.post(
        "/reactor/retries/mark_due",
        json={
            "retry_schedule_id": retry_schedule_id,
            "actor": _REACTOR_ACTOR,
            "reason": "mark retry due without automatic dispatch",
        },
    )
    assert due.status_code == 200
    due_body = due.json()
    assert due_body["ok"] is True
    assert due_body["applied"] is True
    assert due_body["status"] == "retry_due"
    event = due_body["event"]
    due_receipt = due_body["receipt"]
    assert event["stable_state"] == "retry_due"
    assert event["status"] == "dispatch_deferred"
    assert due_receipt["kind"] == "reactor.retry.due.receipt"
    assert due_receipt["retry_schedule_id"] == retry_schedule_id
    assert due_receipt["retry_started"] is False
    assert due_receipt["execution_started"] is False
    assert due_receipt["dispatch_applied"] is False
    assert due_receipt["governance"]["retry_execution_authority"] is False
    assert event["dispatch"]["retry_schedule"]["status"] == "due"
    assert event["dispatch"]["retry_due"] is True
    assert event["latest_retry_due_receipt"]["retry_schedule_id"] == retry_schedule_id
    assert event["latest_receipt"]["kind"] == "reactor.retry.due.receipt"

    due_list = client.get("/reactor/retries/list", params={"status": "due"})
    assert due_list.status_code == 200
    assert {item["retry_schedule_id"] for item in due_list.json()["items"]} == {retry_schedule_id}

    fetched = client.get("/reactor/retries/get", params={"id": retry_schedule_id})
    assert fetched.status_code == 200
    assert fetched.json()["item"]["status"] == "due"

    due_events = client.get("/reactor/events/list", params={"receipt_kind": "reactor.retry.due.receipt"})
    assert due_events.status_code == 200
    assert {item["event_id"] for item in due_events.json()["items"]} == {event_id}

    retry_due_review = client.get("/reactor/review_queue", params={"route": "retry_due"})
    assert retry_due_review.status_code == 200
    review_body = retry_due_review.json()
    assert review_body["available_total"] == 1
    assert review_body["items"][0]["review"]["receipt_kind"] == "reactor.retry.due.receipt"
    assert review_body["items"][0]["governance"]["retry_authority"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["stable_state_counts"] == {"retry_due": 1}
    assert status.json()["retry_schedule_counts"] == {"due": 1}
    assert status.json()["retry_due_counts"] == {"due": 1}


def test_reactor_due_retry_dispatch_attempt_route_records_source_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Deferred Reactor dispatch due retry can attempt again",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 1,
            "max_retries": 2,
            "backoff_seconds": 0,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    retry_schedule_id = str(attempted.json()["event"]["dispatch"]["retry_schedule"]["retry_schedule_id"])

    due = client.post(
        "/reactor/retries/mark_due",
        json={"retry_schedule_id": retry_schedule_id, "actor": _REACTOR_ACTOR},
    )
    assert due.status_code == 200
    assert due.json()["status"] == "retry_due"

    retry_attempt = client.post(
        "/reactor/retries/dispatch_attempt",
        json={
            "retry_schedule_id": retry_schedule_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record due retry dispatch attempt without execution",
        },
    )

    assert retry_attempt.status_code == 200
    retry_attempt_body = retry_attempt.json()
    assert retry_attempt_body["ok"] is True
    assert retry_attempt_body["applied"] is True
    assert retry_attempt_body["status"] == "retry_dispatch_attempted"
    retry_dispatch_receipt = retry_attempt_body["retry_dispatch_attempt_receipt"]
    assert retry_dispatch_receipt["kind"] == "reactor.retry.dispatch_attempt.receipt"
    assert retry_dispatch_receipt["retry_schedule_id"] == retry_schedule_id
    assert retry_dispatch_receipt["status"] == "attempted"
    assert retry_dispatch_receipt["retry_dispatch_attempted"] is True
    assert retry_dispatch_receipt["retry_started"] is False
    assert retry_dispatch_receipt["execution_started"] is False
    assert retry_dispatch_receipt["dispatch_applied"] is False
    assert retry_dispatch_receipt["governance"]["retry_execution_authority"] is False
    event = retry_attempt_body["event"]
    assert event["stable_state"] == "awaiting_dispatch_engine"
    assert event["dispatch"]["retry_dispatch_source_schedule_id"] == retry_schedule_id
    assert event["dispatch"]["retry_attempted_schedule"]["status"] == "attempted"
    assert event["latest_retry_dispatch_attempt_receipt"]["retry_schedule_id"] == retry_schedule_id
    assert event["latest_verification_receipt"]["verification_outcome"] == "retry_scheduled"
    assert event["latest_stable_return"]["source_receipt_kind"] == "reactor.retry.schedule.receipt"
    assert event["latest_stable_return"]["retry_scheduled"] is True
    assert event["governance"]["retry_dispatch_attempted"] is True
    assert event["governance"]["retry_execution_authority"] is False

    attempted_schedule = client.get("/reactor/retries/get", params={"id": retry_schedule_id})
    assert attempted_schedule.status_code == 200
    assert attempted_schedule.json()["item"]["status"] == "attempted"
    attempted_list = client.get("/reactor/retries/list", params={"status": "attempted"})
    assert attempted_list.status_code == 200
    assert {item["retry_schedule_id"] for item in attempted_list.json()["items"]} == {retry_schedule_id}
    scheduled_list = client.get("/reactor/retries/list", params={"status": "scheduled"})
    assert scheduled_list.status_code == 200
    assert event["latest_retry_schedule"]["retry_schedule_id"] in {
        item["retry_schedule_id"] for item in scheduled_list.json()["items"]
    }

    receipt_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.retry.dispatch_attempt.receipt"},
    )
    assert receipt_list.status_code == 200
    assert {item["event_id"] for item in receipt_list.json()["items"]} == {event_id}
    retry_due_review = client.get("/reactor/review_queue", params={"route": "retry_due"})
    assert retry_due_review.status_code == 200
    assert retry_due_review.json()["available_total"] == 0
    retry_backoff_review = client.get("/reactor/review_queue", params={"route": "retry_backoff"})
    assert retry_backoff_review.status_code == 200
    assert retry_backoff_review.json()["available_total"] == 1

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["retry_schedule_counts"] == {"attempted": 1, "scheduled": 1}
    assert status.json()["retry_dispatch_attempt_counts"] == {"attempted": 1}
    assert status.json()["verification_outcome_counts"] == {"retry_scheduled": 1}

    second_attempt = client.post(
        "/reactor/retries/dispatch_attempt",
        json={"retry_schedule_id": retry_schedule_id, "actor": _REACTOR_ACTOR},
    )
    assert second_attempt.status_code == 200
    assert second_attempt.json()["applied"] is False
    assert second_attempt.json()["status"] == "already_attempted"


def test_reactor_deadletter_queue_readback_routes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted Reactor event needs real deadletter queueing",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    event = attempted.json()["event"]
    deadletter_item = event["dispatch"]["deadletter_item"]
    deadletter_id = deadletter_item["deadletter_id"]
    assert deadletter_item["kind"] == "reactor.deadletter.item"
    assert deadletter_item["event_id"] == event_id
    assert event["dispatch"]["deadletter_enqueue"]["status"] == "queued"
    assert event["dispatch"]["deadletter_candidate"]["deadletter_enqueued"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False

    listed = client.get("/reactor/deadletters/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert listed_body["ok"] is True
    assert listed_body["total"] == 1
    assert listed_body["items"][0]["deadletter_id"] == deadletter_id
    assert listed_body["items"][0]["source_receipt_kind"] == "reactor.deadletter_candidate.receipt"
    assert listed_body["governance"]["deadletter_resolution_authority"] is False

    fetched = client.get("/reactor/deadletters/get", params={"id": deadletter_id})
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["ok"] is True
    assert fetched_body["item"]["deadletter_id"] == deadletter_id
    assert fetched_body["item"]["execution_started"] is False
    assert fetched_body["item"]["retry_started"] is False
    assert fetched_body["item"]["escalation_started"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["deadletter_queue_counts"] == {"queued": 1}
    assert status.json()["deadletter_total"] == 1


def test_reactor_deadletter_review_route_records_receipt_without_resolution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted Reactor item can be reviewed",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    deadletter_id = str(attempted.json()["event"]["dispatch"]["deadletter_item"]["deadletter_id"])

    reviewed = client.post(
        "/reactor/deadletters/review",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "decision": "escalate_later",
            "reason": "operator reviewed failed Reactor item",
        },
    )

    assert reviewed.status_code == 200
    reviewed_body = reviewed.json()
    assert reviewed_body["ok"] is True
    assert reviewed_body["applied"] is True
    assert reviewed_body["status"] == "deadletter_reviewed"
    receipt = reviewed_body["receipt"]
    assert receipt["kind"] == "reactor.deadletter.review.receipt"
    assert receipt["deadletter_id"] == deadletter_id
    assert receipt["status"] == "reviewed"
    assert receipt["route"] == "deadletter_review"
    assert receipt["review_decision"] == "escalate_later"
    assert receipt["deadletter_resolved"] is False
    assert receipt["execution_started"] is False
    assert receipt["retry_started"] is False
    assert receipt["escalation_started"] is False
    assert receipt["governance"]["deadletter_resolution_authority"] is False
    assert receipt["governance"]["escalation_authority"] is False
    event = reviewed_body["event"]
    assert event["stable_state"] == "deadletter_reviewed"
    assert event["dispatch"]["deadletter_reviewed"] is True
    assert event["latest_deadletter_review_receipt"]["deadletter_id"] == deadletter_id
    assert event["latest_receipt"]["kind"] == "reactor.deadletter.review.receipt"
    assert event["governance"]["deadletter_reviewed"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False

    reviewed_list = client.get("/reactor/deadletters/list", params={"status": "reviewed"})
    assert reviewed_list.status_code == 200
    assert {item["deadletter_id"] for item in reviewed_list.json()["items"]} == {deadletter_id}
    fetched = client.get("/reactor/deadletters/get", params={"id": deadletter_id})
    assert fetched.status_code == 200
    assert fetched.json()["item"]["latest_review_receipt"]["review_decision"] == "escalate_later"

    receipt_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.review.receipt"},
    )
    assert receipt_list.status_code == 200
    assert {item["event_id"] for item in receipt_list.json()["items"]} == {event_id}
    review_route = client.get("/reactor/events/list", params={"review_route": "deadletter_review"})
    assert review_route.status_code == 200
    assert {item["event_id"] for item in review_route.json()["items"]} == {event_id}
    review_queue = client.get("/reactor/review_queue", params={"route": "deadletter_review"})
    assert review_queue.status_code == 200
    assert review_queue.json()["available_total"] == 1

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["stable_state_counts"] == {"deadletter_reviewed": 1}
    assert status.json()["deadletter_queue_counts"] == {"reviewed": 1}
    assert status.json()["deadletter_review_counts"] == {"reviewed": 1}

    second_review = client.post(
        "/reactor/deadletters/review",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR, "decision": "escalate_later"},
    )
    assert second_review.status_code == 200
    assert second_review.json()["applied"] is False
    assert second_review.json()["status"] == "already_reviewed"


def test_reactor_deadletter_resolve_route_records_escalation_pending_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))
    operation = operations_runtime.create_operation(
        action="plan.create",
        reason="reactor API recovery request should target an existing operation",
        input={"goal": "prove API recovery request handoff"},
        actor=_REACTOR_ACTOR,
    )
    operation_id = str(operation["operation_id"])

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "Budget-exhausted Reactor item can be escalated",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "operation_id": operation_id,
            "max_actions": 0,
            "max_retries": 1,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    deadletter_id = str(attempted.json()["event"]["dispatch"]["deadletter_item"]["deadletter_id"])

    reviewed = client.post(
        "/reactor/deadletters/review",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "decision": "escalate_later",
            "reason": "operator reviewed failed Reactor item",
        },
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "deadletter_reviewed"

    resolved = client.post(
        "/reactor/deadletters/resolve",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "decision": "escalate",
            "reason": "operator wants escalation tracked without recovery execution",
        },
    )

    assert resolved.status_code == 200
    resolved_body = resolved.json()
    assert resolved_body["ok"] is True
    assert resolved_body["applied"] is True
    assert resolved_body["status"] == "deadletter_escalation_pending"
    receipt = resolved_body["receipt"]
    assert receipt["kind"] == "reactor.deadletter.resolution.receipt"
    assert receipt["deadletter_id"] == deadletter_id
    assert receipt["status"] == "escalation_pending"
    assert receipt["route"] == "deadletter_escalation"
    assert receipt["resolution_decision"] == "escalation_pending"
    assert receipt["deadletter_resolved"] is False
    assert receipt["escalation_recorded"] is True
    assert receipt["execution_started"] is False
    assert receipt["retry_started"] is False
    assert receipt["escalation_started"] is False
    assert receipt["memory_write"] is False
    assert receipt["governance"]["deadletter_disposition_authority"] is True
    assert receipt["governance"]["deadletter_resolution_authority"] is False
    assert receipt["governance"]["escalation_authority"] is False
    event = resolved_body["event"]
    assert event["stable_state"] == "deadletter_escalation_pending"
    assert event["dispatch"]["deadletter_escalation_recorded"] is True
    assert event["latest_deadletter_resolution_receipt"]["deadletter_id"] == deadletter_id
    assert event["latest_receipt"]["kind"] == "reactor.deadletter.resolution.receipt"
    assert event["governance"]["deadletter_disposition_authority"] is True
    assert event["governance"]["deadletter_resolution_authority"] is False
    assert event["governance"]["escalation_authority"] is False
    assert event["governance"]["execution_authority"] is False

    escalated_list = client.get("/reactor/deadletters/list", params={"status": "escalation_pending"})
    assert escalated_list.status_code == 200
    assert {item["deadletter_id"] for item in escalated_list.json()["items"]} == {deadletter_id}
    fetched = client.get("/reactor/deadletters/get", params={"id": deadletter_id})
    assert fetched.status_code == 200
    assert fetched.json()["item"]["latest_resolution_receipt"]["resolution_decision"] == "escalation_pending"
    history = client.get("/reactor/deadletters/history/get", params={"id": deadletter_id})
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["ok"] is True
    assert history_body["history"]["deadletter_id"] == deadletter_id
    assert history_body["history"]["status"] == "escalation_pending"
    assert history_body["history"]["latest_receipt_kind"] == "reactor.deadletter.resolution.receipt"
    history_kinds = [entry["receipt_kind"] for entry in history_body["history"]["history"]]
    assert "reactor.deadletter.item" in history_kinds
    assert "reactor.deadletter.review.receipt" in history_kinds
    assert "reactor.deadletter.resolution.receipt" in history_kinds
    assert history_body["governance"]["execution_authority"] is False
    assert history_body["governance"]["deadletter_resolution_authority"] is False
    filtered_history = client.get(
        "/reactor/deadletters/history/get",
        params={"id": deadletter_id, "route": "deadletter_escalation"},
    )
    assert filtered_history.status_code == 200
    assert filtered_history.json()["history"]["total"] == 1
    assert filtered_history.json()["history"]["history"][0]["receipt_kind"] == ("reactor.deadletter.resolution.receipt")
    missing_history = client.get("/reactor/deadletters/history/get", params={"id": "rdl_missing"})
    assert missing_history.status_code == 200
    assert missing_history.json() == {"ok": False, "error": "not_found", "history": []}

    receipt_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.resolution.receipt"},
    )
    assert receipt_list.status_code == 200
    assert {item["event_id"] for item in receipt_list.json()["items"]} == {event_id}
    review_route = client.get("/reactor/events/list", params={"review_route": "deadletter_escalation"})
    assert review_route.status_code == 200
    assert {item["event_id"] for item in review_route.json()["items"]} == {event_id}
    review_queue = client.get("/reactor/review_queue", params={"route": "deadletter_escalation"})
    assert review_queue.status_code == 200
    assert review_queue.json()["available_total"] == 1
    assert (
        review_queue.json()["items"][0]["review"]["action"] == "track_escalation_pending_external_or_operator_followup"
    )

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["stable_state_counts"] == {"deadletter_escalation_pending": 1}
    assert status.json()["deadletter_queue_counts"] == {"escalation_pending": 1}
    assert status.json()["deadletter_review_counts"] == {"reviewed": 1}
    assert status.json()["deadletter_resolution_counts"] == {"escalation_pending": 1}

    second_resolution = client.post(
        "/reactor/deadletters/resolve",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR, "decision": "escalate"},
    )
    assert second_resolution.status_code == 200
    assert second_resolution.json()["applied"] is False
    assert second_resolution.json()["status"] == "already_escalation_pending"

    premature_acknowledgement = client.post(
        "/reactor/deadletters/escalation_acknowledgement",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "acknowledgement should require handoff first",
        },
    )
    assert premature_acknowledgement.status_code == 200
    assert premature_acknowledgement.json()["ok"] is False
    assert premature_acknowledgement.json()["applied"] is False
    assert premature_acknowledgement.json()["error"] == "deadletter_escalation_handoff_required"

    handoff = client.post(
        "/reactor/deadletters/escalation_handoff",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record escalation handoff without external execution",
        },
    )

    assert handoff.status_code == 200
    handoff_body = handoff.json()
    assert handoff_body["ok"] is True
    assert handoff_body["applied"] is True
    assert handoff_body["status"] == "deadletter_escalation_handoff_recorded"
    handoff_receipt = handoff_body["receipt"]
    assert handoff_receipt["kind"] == "reactor.deadletter.escalation_handoff.receipt"
    assert handoff_receipt["deadletter_id"] == deadletter_id
    assert handoff_receipt["route"] == "deadletter_escalation_handoff"
    assert handoff_receipt["execution_started"] is False
    assert handoff_receipt["retry_started"] is False
    assert handoff_receipt["escalation_started"] is False
    assert handoff_receipt["external_escalation_started"] is False
    assert handoff_receipt["memory_write"] is False
    assert handoff_receipt["governance"]["execution_authority"] is False
    assert handoff_receipt["governance"]["escalation_authority"] is False
    handoff_event = handoff_body["event"]
    assert handoff_event["stable_state"] == "deadletter_escalation_handoff_recorded"
    assert handoff_event["dispatch"]["deadletter_escalation_handoff_recorded"] is True
    assert handoff_event["governance"]["execution_authority"] is False
    assert handoff_event["governance"]["escalation_authority"] is False

    handoff_list = client.get("/reactor/deadletters/list", params={"status": "escalation_handoff_recorded"})
    assert handoff_list.status_code == 200
    assert {item["deadletter_id"] for item in handoff_list.json()["items"]} == {deadletter_id}
    handoff_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.escalation_handoff.receipt"},
    )
    assert handoff_receipts.status_code == 200
    assert {item["event_id"] for item in handoff_receipts.json()["items"]} == {event_id}
    handoff_review = client.get("/reactor/review_queue", params={"route": "deadletter_escalation_handoff"})
    assert handoff_review.status_code == 200
    assert handoff_review.json()["available_total"] == 1
    assert handoff_review.json()["items"][0]["review"]["action"] == "track_escalation_handoff_until_acknowledged"
    handoff_status = client.get("/reactor/status")
    assert handoff_status.status_code == 200
    assert handoff_status.json()["stable_state_counts"] == {"deadletter_escalation_handoff_recorded": 1}
    assert handoff_status.json()["deadletter_queue_counts"] == {"escalation_handoff_recorded": 1}
    assert handoff_status.json()["deadletter_escalation_handoff_counts"] == {"handoff_recorded": 1}

    second_handoff = client.post(
        "/reactor/deadletters/escalation_handoff",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert second_handoff.status_code == 200
    assert second_handoff.json()["applied"] is False
    assert second_handoff.json()["status"] == "already_escalation_handoff_recorded"

    acknowledgement = client.post(
        "/reactor/deadletters/escalation_acknowledgement",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "acknowledge escalation handoff without starting recovery",
        },
    )

    assert acknowledgement.status_code == 200
    acknowledgement_body = acknowledgement.json()
    assert acknowledgement_body["ok"] is True
    assert acknowledgement_body["applied"] is True
    assert acknowledgement_body["status"] == "deadletter_escalation_acknowledged"
    acknowledgement_receipt = acknowledgement_body["receipt"]
    assert acknowledgement_receipt["kind"] == "reactor.deadletter.escalation_acknowledgement.receipt"
    assert acknowledgement_receipt["deadletter_id"] == deadletter_id
    assert acknowledgement_receipt["route"] == "deadletter_escalation_acknowledgement"
    assert acknowledgement_receipt["source_receipt_kind"] == "reactor.deadletter.escalation_handoff.receipt"
    assert acknowledgement_receipt["execution_started"] is False
    assert acknowledgement_receipt["retry_started"] is False
    assert acknowledgement_receipt["escalation_started"] is False
    assert acknowledgement_receipt["external_escalation_started"] is False
    assert acknowledgement_receipt["recovery_started"] is False
    assert acknowledgement_receipt["memory_write"] is False
    assert acknowledgement_receipt["governance"]["execution_authority"] is False
    assert acknowledgement_receipt["governance"]["escalation_authority"] is False
    acknowledgement_event = acknowledgement_body["event"]
    assert acknowledgement_event["stable_state"] == "deadletter_escalation_acknowledged"
    assert acknowledgement_event["dispatch"]["deadletter_escalation_acknowledged"] is True
    assert acknowledgement_event["governance"]["execution_authority"] is False
    assert acknowledgement_event["governance"]["escalation_authority"] is False

    acknowledgement_list = client.get("/reactor/deadletters/list", params={"status": "escalation_acknowledged"})
    assert acknowledgement_list.status_code == 200
    assert {item["deadletter_id"] for item in acknowledgement_list.json()["items"]} == {deadletter_id}
    acknowledgement_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.escalation_acknowledgement.receipt"},
    )
    assert acknowledgement_receipts.status_code == 200
    assert {item["event_id"] for item in acknowledgement_receipts.json()["items"]} == {event_id}
    acknowledgement_review = client.get(
        "/reactor/review_queue",
        params={"route": "deadletter_escalation_acknowledgement"},
    )
    assert acknowledgement_review.status_code == 200
    assert acknowledgement_review.json()["available_total"] == 1
    assert (
        acknowledgement_review.json()["items"][0]["review"]["action"]
        == "wait_for_explicit_recovery_execution_boundary_after_acknowledgement"
    )
    acknowledgement_status = client.get("/reactor/status")
    assert acknowledgement_status.status_code == 200
    assert acknowledgement_status.json()["stable_state_counts"] == {"deadletter_escalation_acknowledged": 1}
    assert acknowledgement_status.json()["deadletter_queue_counts"] == {"escalation_acknowledged": 1}
    assert acknowledgement_status.json()["deadletter_escalation_handoff_counts"] == {"handoff_recorded": 1}
    assert acknowledgement_status.json()["deadletter_escalation_acknowledgement_counts"] == {"acknowledged": 1}

    second_acknowledgement = client.post(
        "/reactor/deadletters/escalation_acknowledgement",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert second_acknowledgement.status_code == 200
    assert second_acknowledgement.json()["applied"] is False
    assert second_acknowledgement.json()["status"] == "already_escalation_acknowledged"

    external_attempt = client.post(
        "/reactor/deadletters/external_escalation_attempt",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record external attempt without sending anything",
            "external_channel": "ops_bridge",
            "external_target": "on_call",
            "external_adapter": "pager_stub",
        },
    )

    assert external_attempt.status_code == 200
    external_body = external_attempt.json()
    assert external_body["ok"] is True
    assert external_body["applied"] is True
    assert external_body["status"] == "deadletter_external_escalation_attempt_recorded"
    external_receipt = external_body["receipt"]
    assert external_receipt["kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert external_receipt["deadletter_id"] == deadletter_id
    assert external_receipt["status"] == "attempt_recorded"
    assert external_receipt["route"] == "deadletter_external_escalation_attempt"
    assert external_receipt["source_receipt_kind"] == "reactor.deadletter.escalation_acknowledgement.receipt"
    assert external_receipt["external_channel"] == "ops_bridge"
    assert external_receipt["external_target"] == "on_call"
    assert external_receipt["external_adapter"] == "pager_stub"
    assert external_receipt["external_adapter_known"] is False
    assert external_receipt["external_adapter_configured"] is False
    assert external_receipt["external_adapter_status"] == "not_configured"
    assert external_receipt["external_delivery_mode"] == "unsupported"
    assert external_receipt["external_delivery_ready"] is False
    assert external_receipt["external_delivery_queued"] is False
    assert external_receipt["external_delivery_blocker"] == "unsupported_external_adapter"
    assert external_receipt["external_escalation_started"] is False
    assert external_receipt["external_delivery_started"] is False
    assert external_receipt["execution_started"] is False
    assert external_receipt["dispatch_applied"] is False
    assert external_receipt["completion_claim_allowed"] is False
    assert external_receipt["memory_write"] is False
    assert external_receipt["governance"]["execution_authority"] is False
    assert external_receipt["governance"]["external_escalation_authority"] is False
    assert external_receipt["governance"]["escalation_authority"] is False
    external_event = external_body["event"]
    assert external_event["stable_state"] == "deadletter_external_escalation_attempt_recorded"
    assert external_event["dispatch"]["deadletter_external_escalation_attempt_recorded"] is True
    assert external_event["dispatch"]["external_adapter_configured"] is False
    assert external_event["dispatch"]["external_delivery_ready"] is False
    assert external_event["dispatch"]["external_delivery_started"] is False
    assert external_event["governance"]["external_escalation_authority"] is False
    assert external_event["governance"]["external_delivery_authority"] is False

    external_list = client.get(
        "/reactor/deadletters/list",
        params={"status": "external_escalation_attempt_recorded"},
    )
    assert external_list.status_code == 200
    assert {item["deadletter_id"] for item in external_list.json()["items"]} == {deadletter_id}
    external_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.external_escalation_attempt.receipt"},
    )
    assert external_receipts.status_code == 200
    assert {item["event_id"] for item in external_receipts.json()["items"]} == {event_id}
    external_review = client.get("/reactor/review_queue", params={"route": "deadletter_external_escalation_attempt"})
    assert external_review.status_code == 200
    assert external_review.json()["available_total"] == 1
    assert (
        external_review.json()["items"][0]["review"]["action"]
        == "queue_recovery_request_or_configure_external_escalation_adapter_before_delivery"
    )
    external_status = client.get("/reactor/status")
    assert external_status.status_code == 200
    assert external_status.json()["stable_state_counts"] == {"deadletter_external_escalation_attempt_recorded": 1}
    assert external_status.json()["deadletter_queue_counts"] == {"external_escalation_attempt_recorded": 1}
    assert external_status.json()["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}

    blocked_delivery = client.post(
        "/reactor/deadletters/external_escalation_delivery",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "unsupported adapter must not queue local outbox delivery",
        },
    )
    assert blocked_delivery.status_code == 200
    assert blocked_delivery.json()["ok"] is False
    assert blocked_delivery.json()["applied"] is False
    assert blocked_delivery.json()["error"] == "local_outbox_external_escalation_adapter_required"

    second_external_attempt = client.post(
        "/reactor/deadletters/external_escalation_attempt",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert second_external_attempt.status_code == 200
    assert second_external_attempt.json()["applied"] is False
    assert second_external_attempt.json()["status"] == "already_external_escalation_attempt_recorded"

    recovery_request = client.post(
        "/reactor/deadletters/recovery_request",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue recovery through existing operation dispatch gate",
        },
    )
    assert recovery_request.status_code == 200
    recovery_body = recovery_request.json()
    assert recovery_body["ok"] is True
    assert recovery_body["applied"] is True
    assert recovery_body["status"] == "deadletter_recovery_requested"
    recovery_receipt = recovery_body["receipt"]
    recovery_event_id = recovery_receipt["recovery_event_id"]
    assert recovery_receipt["kind"] == "reactor.deadletter.recovery_request.receipt"
    assert recovery_receipt["deadletter_id"] == deadletter_id
    assert recovery_receipt["route"] == "deadletter_recovery_request"
    assert recovery_receipt["source_receipt_kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert recovery_receipt["external_escalation_attempt_receipt_id"] == external_receipt["receipt_id"]
    assert recovery_receipt["operation_id"] == operation_id
    assert recovery_receipt["recovery_event_enqueued"] is True
    assert recovery_receipt["execution_started"] is False
    assert recovery_receipt["retry_started"] is False
    assert recovery_receipt["escalation_started"] is False
    assert recovery_receipt["recovery_started"] is False
    assert recovery_receipt["memory_write"] is False
    assert recovery_receipt["governance"]["execution_authority"] is False
    assert recovery_receipt["governance"]["dispatch_authority"] is False
    assert recovery_receipt["governance"]["recovery_request_authority"] is True
    recovery_source_event = recovery_body["event"]
    assert recovery_source_event["stable_state"] == "deadletter_recovery_requested"
    assert recovery_source_event["dispatch"]["deadletter_recovery_requested"] is True
    assert recovery_source_event["dispatch"]["recovery_event_id"] == recovery_event_id
    assert recovery_source_event["governance"]["execution_authority"] is False
    assert recovery_source_event["governance"]["dispatch_authority"] is False
    recovery_event = recovery_body["recovery_event"]
    assert recovery_event["event_id"] == recovery_event_id
    assert recovery_event["status"] == "queued"
    assert recovery_event["stable_state"] == "awaiting_dispatch"
    assert recovery_event["trigger"]["source"] == "deadletter_recovery"
    assert recovery_event["trigger"]["operation_id"] == operation_id
    assert recovery_event["classification"]["action_class"] == "operation_run"
    assert recovery_event["governance"]["execution_authority"] is False

    recovery_list = client.get("/reactor/deadletters/list", params={"status": "recovery_requested"})
    assert recovery_list.status_code == 200
    assert {item["deadletter_id"] for item in recovery_list.json()["items"]} == {deadletter_id}
    recovery_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.recovery_request.receipt"},
    )
    assert recovery_receipts.status_code == 200
    assert {item["event_id"] for item in recovery_receipts.json()["items"]} == {event_id}
    recovery_trigger = client.get("/reactor/events/list", params={"trigger_source": "deadletter_recovery"})
    assert recovery_trigger.status_code == 200
    assert {item["event_id"] for item in recovery_trigger.json()["items"]} == {recovery_event_id}
    recovery_review = client.get("/reactor/review_queue", params={"route": "deadletter_recovery_request"})
    assert recovery_review.status_code == 200
    assert recovery_review.json()["available_total"] == 1
    assert (
        recovery_review.json()["items"][0]["review"]["action"]
        == "record_dispatch_attempt_for_deadletter_recovery_event"
    )
    recovery_status = client.get("/reactor/status")
    assert recovery_status.status_code == 200
    assert recovery_status.json()["deadletter_queue_counts"] == {"recovery_requested": 1}
    assert recovery_status.json()["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}
    assert recovery_status.json()["deadletter_recovery_request_counts"] == {"recovery_requested": 1}

    second_recovery_request = client.post(
        "/reactor/deadletters/recovery_request",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert second_recovery_request.status_code == 200
    assert second_recovery_request.json()["applied"] is False
    assert second_recovery_request.json()["status"] == "already_recovery_requested"

    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write", "operations.run"]}),
    )
    recovery_dispatch = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": recovery_event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "dispatch queued deadletter recovery through existing operation gate",
        },
    )
    assert recovery_dispatch.status_code == 200
    recovery_dispatch_body = recovery_dispatch.json()
    assert recovery_dispatch_body["ok"] is True
    assert recovery_dispatch_body["applied"] is True
    dispatched_recovery = recovery_dispatch_body["event"]
    assert dispatched_recovery["event_id"] == recovery_event_id
    assert dispatched_recovery["trigger"]["source"] == "deadletter_recovery"
    assert dispatched_recovery["trigger"]["operation_id"] == operation_id
    assert dispatched_recovery["trigger"]["metadata"]["deadletter_id"] == deadletter_id
    assert dispatched_recovery["trigger"]["metadata"]["source_event_id"] == event_id
    assert dispatched_recovery["status"] == "dispatch_completed"
    assert dispatched_recovery["stable_state"] == "dispatch_succeeded"
    assert dispatched_recovery["dispatch"]["engine"] == "operation_run"
    assert dispatched_recovery["dispatch"]["applied"] is True
    assert dispatched_recovery["dispatch"]["execution_started"] is True
    recovery_execution = dispatched_recovery["latest_dispatch_execution_receipt"]
    assert recovery_execution["kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_execution["operation_id"] == operation_id
    assert recovery_execution["status"] == "completed"
    assert recovery_execution["outcome"] == "operation_succeeded"
    assert recovery_execution["execution_started"] is True
    assert recovery_execution["dispatch_applied"] is True
    assert recovery_execution["verified"] is True
    assert recovery_execution["governance"]["authority_source"] == "operations.run"
    assert recovery_execution["governance"]["approval_authority"] is False
    recovery_verification = dispatched_recovery["latest_verification_receipt"]
    assert recovery_verification["verification_status"] == "passed"
    assert recovery_verification["verification_outcome"] == "operation_succeeded"
    assert recovery_verification["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_verification["operation_id"] == operation_id
    assert recovery_verification["verified"] is True
    recovery_stable_return = dispatched_recovery["latest_stable_return"]
    assert recovery_stable_return["route"] == "operation_run"
    assert recovery_stable_return["stable_state"] == "dispatch_succeeded"
    assert recovery_stable_return["operation_id"] == operation_id
    assert recovery_stable_return["dispatch_applied"] is True
    recovery_settlement = recovery_dispatch_body["deadletter_recovery_dispatch"]
    recovery_settlement_receipt = recovery_settlement["receipt"]
    assert recovery_settlement_receipt["kind"] == "reactor.deadletter.recovery_dispatch.receipt"
    assert recovery_settlement_receipt["deadletter_id"] == deadletter_id
    assert recovery_settlement_receipt["status"] == "recovery_dispatched"
    assert recovery_settlement_receipt["route"] == "deadletter_recovery_dispatch"
    assert recovery_settlement_receipt["stable_state"] == "deadletter_recovery_dispatched"
    assert recovery_settlement_receipt["recovery_event_id"] == recovery_event_id
    assert recovery_settlement_receipt["operation_id"] == operation_id
    assert recovery_settlement_receipt["operation_status"] == "succeeded"
    assert recovery_settlement_receipt["source_receipt_kind"] == "reactor.dispatch.execution.receipt"
    assert recovery_settlement_receipt["recovery_dispatched"] is True
    assert recovery_settlement_receipt["deadletter_settled"] is True
    assert recovery_settlement_receipt["execution_started"] is True
    assert recovery_settlement_receipt["dispatch_applied"] is True
    assert recovery_settlement_receipt["governance"]["authority_source"] == "operations.run"
    assert recovery_settlement_receipt["governance"]["deadletter_settlement_authority"] is True
    assert recovery_settlement_receipt["governance"]["approval_authority"] is False
    assert recovery_settlement["item"]["status"] == "recovery_dispatched"
    assert recovery_settlement["source_event"]["stable_state"] == "deadletter_recovery_dispatched"

    recovery_execution_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.dispatch.execution.receipt"},
    )
    assert recovery_execution_list.status_code == 200
    assert {item["event_id"] for item in recovery_execution_list.json()["items"]} == {recovery_event_id}
    recovery_settlement_list = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.recovery_dispatch.receipt"},
    )
    assert recovery_settlement_list.status_code == 200
    assert {item["event_id"] for item in recovery_settlement_list.json()["items"]} == {event_id}
    recovery_settlement_route = client.get(
        "/reactor/events/list",
        params={"review_route": "deadletter_recovery_dispatch"},
    )
    assert recovery_settlement_route.status_code == 200
    assert {item["event_id"] for item in recovery_settlement_route.json()["items"]} == {event_id}
    direct_recovery_receipts = client.get(
        "/reactor/deadletters/recovery_receipts/list",
        params={"deadletter_id": deadletter_id},
    )
    assert direct_recovery_receipts.status_code == 200
    direct_recovery_body = direct_recovery_receipts.json()
    assert direct_recovery_body["ok"] is True
    assert direct_recovery_body["total"] == 2
    assert [item["receipt_kind"] for item in direct_recovery_body["items"]] == [
        "reactor.deadletter.recovery_dispatch.receipt",
        "reactor.deadletter.recovery_request.receipt",
    ]
    assert {item["recovery_event_id"] for item in direct_recovery_body["items"]} == {recovery_event_id}
    assert direct_recovery_body["governance"]["execution_authority"] is False
    direct_dispatch_receipts = client.get(
        "/reactor/deadletters/recovery_receipts/list",
        params={"route": "deadletter_recovery_dispatch"},
    )
    assert direct_dispatch_receipts.status_code == 200
    assert [item["receipt_id"] for item in direct_dispatch_receipts.json()["items"]] == [
        recovery_settlement_receipt["receipt_id"]
    ]
    fetched_recovery_receipt = client.get(
        "/reactor/deadletters/recovery_receipts/get",
        params={"id": recovery_settlement_receipt["receipt_id"]},
    )
    assert fetched_recovery_receipt.status_code == 200
    assert fetched_recovery_receipt.json()["ok"] is True
    assert fetched_recovery_receipt.json()["item"]["deadletter_id"] == deadletter_id
    assert fetched_recovery_receipt.json()["item"]["source_governance"]["execution_authority"] is True
    assert fetched_recovery_receipt.json()["item"]["governance"]["execution_authority"] is False
    missing_recovery_receipt = client.get(
        "/reactor/deadletters/recovery_receipts/get",
        params={"id": "missing_recovery_receipt"},
    )
    assert missing_recovery_receipt.status_code == 200
    assert missing_recovery_receipt.json() == {"ok": False, "error": "not_found", "item": None}
    recovery_request_review_after_dispatch = client.get(
        "/reactor/review_queue",
        params={"route": "deadletter_recovery_request"},
    )
    assert recovery_request_review_after_dispatch.status_code == 200
    assert recovery_request_review_after_dispatch.json()["available_total"] == 0
    recovered_deadletters = client.get("/reactor/deadletters/list", params={"status": "recovery_requested"})
    assert recovered_deadletters.status_code == 200
    assert recovered_deadletters.json()["items"] == []
    recovery_dispatched_deadletters = client.get(
        "/reactor/deadletters/list",
        params={"status": "recovery_dispatched"},
    )
    assert recovery_dispatched_deadletters.status_code == 200
    assert {item["deadletter_id"] for item in recovery_dispatched_deadletters.json()["items"]} == {deadletter_id}
    recovery_dispatch_status = client.get("/reactor/status")
    assert recovery_dispatch_status.status_code == 200
    assert recovery_dispatch_status.json()["stable_state_counts"] == {
        "deadletter_recovery_dispatched": 1,
        "dispatch_succeeded": 1,
    }
    assert recovery_dispatch_status.json()["dispatch_execution_counts"] == {"completed": 1}
    assert recovery_dispatch_status.json()["verification_counts"] == {"not_run": 1, "passed": 1}
    assert recovery_dispatch_status.json()["verification_outcome_counts"] == {
        "deadletter_queued_for_review": 1,
        "operation_succeeded": 1,
    }
    assert recovery_dispatch_status.json()["deadletter_queue_counts"] == {"recovery_dispatched": 1}
    assert recovery_dispatch_status.json()["deadletter_recovery_request_counts"] == {"recovery_requested": 1}
    assert recovery_dispatch_status.json()["deadletter_recovery_dispatch_counts"] == {"recovery_dispatched": 1}

    operation_detail = operations_runtime.get_operation_detail(operation_id)
    assert operation_detail["operation"]["status"] == "succeeded"


def test_reactor_deadletter_external_delivery_route_queues_local_outbox_without_send(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "mission_queue",
            "summary": "External escalation delivery should use local outbox only",
            "actor": _REACTOR_ACTOR,
            "action_class": "classify",
            "max_actions": 0,
            "max_retries": 1,
            "backoff_seconds": 15,
        },
    )
    assert created.status_code == 200
    event_id = str(created.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": event_id, "actor": _REACTOR_ACTOR},
    )
    assert attempted.status_code == 200
    deadletter_id = str(attempted.json()["event"]["dispatch"]["deadletter_item"]["deadletter_id"])

    review = client.post(
        "/reactor/deadletters/review",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "decision": "escalate_later",
        },
    )
    assert review.status_code == 200
    resolution = client.post(
        "/reactor/deadletters/resolve",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "decision": "escalate",
        },
    )
    assert resolution.status_code == 200
    handoff = client.post(
        "/reactor/deadletters/escalation_handoff",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert handoff.status_code == 200
    acknowledgement = client.post(
        "/reactor/deadletters/escalation_acknowledgement",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert acknowledgement.status_code == 200

    external_attempt = client.post(
        "/reactor/deadletters/external_escalation_attempt",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "preflight local outbox delivery metadata",
            "external_channel": "ops_bridge",
            "external_target": "on_call",
            "external_adapter": "local-outbox",
        },
    )
    assert external_attempt.status_code == 200
    attempt_receipt = external_attempt.json()["receipt"]
    assert attempt_receipt["external_adapter"] == "local_outbox"
    assert attempt_receipt["external_delivery_ready"] is True
    assert attempt_receipt["external_delivery_queued"] is False
    assert attempt_receipt["external_delivery_started"] is False

    delivery = client.post(
        "/reactor/deadletters/external_escalation_delivery",
        json={
            "deadletter_id": deadletter_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue local outbox item without sending externally",
        },
    )
    assert delivery.status_code == 200
    delivery_body = delivery.json()
    assert delivery_body["ok"] is True
    assert delivery_body["applied"] is True
    assert delivery_body["status"] == "deadletter_external_escalation_delivery_queued"
    delivery_receipt = delivery_body["receipt"]
    delivery_id = delivery_receipt["delivery_id"]
    assert delivery_receipt["kind"] == "reactor.deadletter.external_escalation_delivery.receipt"
    assert delivery_receipt["status"] == "delivery_queued"
    assert delivery_receipt["route"] == "deadletter_external_escalation_delivery"
    assert delivery_receipt["stable_state"] == "deadletter_external_escalation_delivery_queued"
    assert delivery_receipt["source_receipt_kind"] == "reactor.deadletter.external_escalation_attempt.receipt"
    assert delivery_receipt["external_escalation_attempt_receipt_id"] == attempt_receipt["receipt_id"]
    assert delivery_receipt["external_adapter"] == "local_outbox"
    assert delivery_receipt["external_delivery_mode"] == "local_outbox"
    assert delivery_receipt["external_delivery_ready"] is True
    assert delivery_receipt["external_delivery_queued"] is True
    assert delivery_receipt["external_delivery_started"] is False
    assert delivery_receipt["external_message_sent"] is False
    assert delivery_receipt["external_network_send"] is False
    assert delivery_receipt["external_escalation_started"] is False
    assert delivery_receipt["execution_started"] is False
    assert delivery_receipt["dispatch_applied"] is False
    assert delivery_receipt["completion_claim_allowed"] is False
    assert delivery_receipt["memory_write"] is False
    assert delivery_receipt["governance"]["external_delivery_queue_authority"] is True
    assert delivery_receipt["governance"]["external_delivery_authority"] is False
    assert delivery_receipt["governance"]["external_escalation_authority"] is False

    outbox_item = delivery_body["delivery_item"]
    assert outbox_item["kind"] == "reactor.deadletter.external_escalation.local_outbox.item"
    assert outbox_item["delivery_id"] == delivery_id
    assert outbox_item["status"] == "queued"
    assert outbox_item["external_delivery_started"] is False
    assert outbox_item["external_message_sent"] is False
    assert outbox_item["external_network_send"] is False
    assert (data_root / "reactor" / "external_escalation_outbox" / f"{delivery_id}.json").exists()

    delivery_items = client.get("/reactor/deadletters/external_escalation_deliveries/list")
    assert delivery_items.status_code == 200
    delivery_items_body = delivery_items.json()
    assert delivery_items_body["ok"] is True
    assert delivery_items_body["total"] == 1
    assert delivery_items_body["items"][0]["delivery_id"] == delivery_id
    assert delivery_items_body["items"][0]["external_delivery_started"] is False
    assert delivery_items_body["governance"]["external_delivery_authority"] is False
    filtered_delivery_items = client.get(
        "/reactor/deadletters/external_escalation_deliveries/list",
        params={"status": "queued", "deadletter_id": deadletter_id, "event_id": event_id},
    )
    assert filtered_delivery_items.status_code == 200
    assert [item["delivery_id"] for item in filtered_delivery_items.json()["items"]] == [delivery_id]
    empty_delivery_items = client.get(
        "/reactor/deadletters/external_escalation_deliveries/list",
        params={"status": "sent"},
    )
    assert empty_delivery_items.status_code == 200
    assert empty_delivery_items.json()["items"] == []
    fetched_delivery = client.get(
        "/reactor/deadletters/external_escalation_deliveries/get",
        params={"id": delivery_id},
    )
    assert fetched_delivery.status_code == 200
    assert fetched_delivery.json()["ok"] is True
    assert fetched_delivery.json()["item"]["delivery_id"] == delivery_id
    assert fetched_delivery.json()["item"]["external_network_send"] is False
    assert fetched_delivery.json()["governance"]["external_escalation_authority"] is False
    processor_readiness = client.get(
        "/reactor/deadletters/external_escalation_deliveries/processor_readiness/list",
        params={"status": "queued", "processor_status": "ready"},
    )
    assert processor_readiness.status_code == 200
    processor_readiness_body = processor_readiness.json()
    assert processor_readiness_body["ok"] is True
    assert processor_readiness_body["total"] == 1
    assert processor_readiness_body["ready_total"] == 1
    assert processor_readiness_body["blocked_total"] == 0
    assert processor_readiness_body["items"][0]["delivery_id"] == delivery_id
    assert processor_readiness_body["items"][0]["delivery_processor_ready"] is True
    assert processor_readiness_body["items"][0]["delivery_processor_blockers"] == []
    assert processor_readiness_body["items"][0]["external_delivery_started"] is False
    assert processor_readiness_body["governance"]["external_delivery_authority"] is False
    assert processor_readiness_body["governance"]["delivery_processor_claim_authority"] is False
    filtered_processor_readiness = client.get(
        "/reactor/deadletters/external_escalation_deliveries/processor_readiness/list",
        params={"processor_status": "blocked"},
    )
    assert filtered_processor_readiness.status_code == 200
    assert filtered_processor_readiness.json()["items"] == []
    fetched_processor_readiness = client.get(
        "/reactor/deadletters/external_escalation_deliveries/processor_readiness/get",
        params={"id": delivery_id},
    )
    assert fetched_processor_readiness.status_code == 200
    assert fetched_processor_readiness.json()["ok"] is True
    assert fetched_processor_readiness.json()["item"]["delivery_id"] == delivery_id
    assert fetched_processor_readiness.json()["item"]["delivery_processor_status"] == "ready"
    assert fetched_processor_readiness.json()["item"]["governance"]["external_escalation_authority"] is False
    missing_processor_readiness = client.get(
        "/reactor/deadletters/external_escalation_deliveries/processor_readiness/get",
        params={"id": "red_missing"},
    )
    assert missing_processor_readiness.status_code == 200
    assert missing_processor_readiness.json() == {"ok": False, "error": "not_found", "item": None}
    missing_delivery = client.get(
        "/reactor/deadletters/external_escalation_deliveries/get",
        params={"id": "red_missing"},
    )
    assert missing_delivery.status_code == 200
    assert missing_delivery.json() == {"ok": False, "error": "not_found", "item": None}

    delivered_event = delivery_body["event"]
    assert delivered_event["stable_state"] == "deadletter_external_escalation_delivery_queued"
    assert delivered_event["dispatch"]["deadletter_external_escalation_delivery_queued"] is True
    assert delivered_event["dispatch"]["external_delivery_id"] == delivery_id
    assert delivered_event["dispatch"]["external_delivery_queued"] is True
    assert delivered_event["dispatch"]["external_delivery_started"] is False
    assert delivered_event["dispatch"]["external_message_sent"] is False
    assert delivered_event["dispatch"]["execution_started"] is False
    assert delivered_event["governance"]["external_delivery_queue_authority"] is True
    assert delivered_event["governance"]["external_delivery_authority"] is False
    assert delivered_event["governance"]["external_escalation_authority"] is False

    delivered_list = client.get(
        "/reactor/deadletters/list",
        params={"status": "external_escalation_delivery_queued"},
    )
    assert delivered_list.status_code == 200
    assert {item["deadletter_id"] for item in delivered_list.json()["items"]} == {deadletter_id}
    delivery_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.external_escalation_delivery.receipt"},
    )
    assert delivery_receipts.status_code == 200
    assert {item["event_id"] for item in delivery_receipts.json()["items"]} == {event_id}
    delivery_review = client.get(
        "/reactor/review_queue",
        params={"route": "deadletter_external_escalation_delivery"},
    )
    assert delivery_review.status_code == 200
    assert delivery_review.json()["available_total"] == 1
    assert (
        delivery_review.json()["items"][0]["review"]["action"]
        == "await_local_outbox_external_delivery_processor_or_operator_review"
    )
    delivery_status = client.get("/reactor/status")
    assert delivery_status.status_code == 200
    assert delivery_status.json()["stable_state_counts"] == {"deadletter_external_escalation_delivery_queued": 1}
    assert delivery_status.json()["deadletter_queue_counts"] == {"external_escalation_delivery_queued": 1}
    assert delivery_status.json()["deadletter_external_escalation_attempt_counts"] == {"attempt_recorded": 1}
    assert delivery_status.json()["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}

    second_delivery = client.post(
        "/reactor/deadletters/external_escalation_delivery",
        json={"deadletter_id": deadletter_id, "actor": _REACTOR_ACTOR},
    )
    assert second_delivery.status_code == 200
    assert second_delivery.json()["applied"] is False
    assert second_delivery.json()["status"] == "already_external_escalation_delivery_queued"

    handoff = client.post(
        "/reactor/deadletters/external_escalation_delivery_processor_handoff",
        json={
            "delivery_id": delivery_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record local processor handoff without sending externally",
        },
    )
    assert handoff.status_code == 200
    handoff_body = handoff.json()
    assert handoff_body["ok"] is True
    assert handoff_body["applied"] is True
    assert handoff_body["status"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    handoff_receipt = handoff_body["receipt"]
    assert handoff_receipt["kind"] == "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"
    assert handoff_receipt["status"] == "processor_handoff_recorded"
    assert handoff_receipt["route"] == "deadletter_external_escalation_delivery_processor_handoff"
    assert handoff_receipt["stable_state"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    assert handoff_receipt["external_delivery_queued"] is True
    assert handoff_receipt["external_delivery_started"] is False
    assert handoff_receipt["external_message_sent"] is False
    assert handoff_receipt["external_network_send"] is False
    assert handoff_receipt["delivery_processor_handoff_recorded"] is True
    assert handoff_receipt["delivery_processor_completed"] is False
    assert handoff_receipt["execution_started"] is False
    assert handoff_receipt["memory_write"] is False
    assert handoff_receipt["completion_claim_allowed"] is False
    assert handoff_receipt["governance"]["delivery_processor_handoff_authority"] is True
    assert handoff_receipt["governance"]["external_delivery_authority"] is False
    assert handoff_receipt["governance"]["external_escalation_authority"] is False

    handoff_delivery = client.get(
        "/reactor/deadletters/external_escalation_deliveries/get",
        params={"id": delivery_id},
    )
    assert handoff_delivery.status_code == 200
    assert handoff_delivery.json()["item"]["status"] == "processor_handoff_recorded"
    assert handoff_delivery.json()["item"]["delivery_processor_handoff_recorded"] is True
    assert handoff_delivery.json()["item"]["external_network_send"] is False
    blocked_processor_readiness = client.get(
        "/reactor/deadletters/external_escalation_deliveries/processor_readiness/get",
        params={"id": delivery_id},
    )
    assert blocked_processor_readiness.status_code == 200
    assert blocked_processor_readiness.json()["item"]["delivery_processor_status"] == "blocked"
    assert blocked_processor_readiness.json()["item"]["delivery_processor_blockers"] == ["delivery_not_queued"]

    handoff_event = handoff_body["event"]
    assert handoff_event["stable_state"] == "deadletter_external_escalation_delivery_processor_handoff_recorded"
    assert handoff_event["dispatch"]["deadletter_external_escalation_delivery_processor_handoff_recorded"] is True
    assert handoff_event["dispatch"]["delivery_processor_handoff_recorded"] is True
    assert handoff_event["dispatch"]["external_delivery_started"] is False
    assert handoff_event["dispatch"]["external_network_send"] is False
    assert handoff_event["governance"]["delivery_processor_handoff_authority"] is True
    assert handoff_event["governance"]["external_delivery_authority"] is False

    handoff_list = client.get(
        "/reactor/deadletters/list",
        params={"status": "external_escalation_delivery_processor_handoff_recorded"},
    )
    assert handoff_list.status_code == 200
    assert {item["deadletter_id"] for item in handoff_list.json()["items"]} == {deadletter_id}
    handoff_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt"},
    )
    assert handoff_receipts.status_code == 200
    assert {item["event_id"] for item in handoff_receipts.json()["items"]} == {event_id}
    handoff_history = client.get(
        "/reactor/deadletters/history/get",
        params={
            "id": deadletter_id,
            "receipt_kind": "reactor.deadletter.external_escalation_delivery_processor_handoff.receipt",
        },
    )
    assert handoff_history.status_code == 200
    assert handoff_history.json()["history"]["total"] == 1
    assert (
        handoff_history.json()["history"]["history"][0]["route"]
        == "deadletter_external_escalation_delivery_processor_handoff"
    )
    assert handoff_history.json()["history"]["governance"]["external_delivery_authority"] is False
    handoff_review = client.get(
        "/reactor/review_queue",
        params={"route": "deadletter_external_escalation_delivery_processor_handoff"},
    )
    assert handoff_review.status_code == 200
    assert handoff_review.json()["available_total"] == 1
    assert (
        handoff_review.json()["items"][0]["review"]["action"]
        == "await_explicit_external_delivery_sender_before_marking_sent"
    )
    handoff_status = client.get("/reactor/status")
    assert handoff_status.status_code == 200
    assert handoff_status.json()["stable_state_counts"] == {
        "deadletter_external_escalation_delivery_processor_handoff_recorded": 1
    }
    assert handoff_status.json()["deadletter_queue_counts"] == {
        "external_escalation_delivery_processor_handoff_recorded": 1
    }
    assert handoff_status.json()["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}
    assert handoff_status.json()["deadletter_external_escalation_delivery_processor_handoff_counts"] == {
        "processor_handoff_recorded": 1
    }

    second_handoff = client.post(
        "/reactor/deadletters/external_escalation_delivery_processor_handoff",
        json={"delivery_id": delivery_id, "actor": _REACTOR_ACTOR},
    )
    assert second_handoff.status_code == 200
    assert second_handoff.json()["applied"] is False
    assert second_handoff.json()["status"] == "already_external_escalation_delivery_processor_handoff_recorded"

    completion = client.post(
        "/reactor/deadletters/external_escalation_delivery_processor_completion",
        json={
            "delivery_id": delivery_id,
            "actor": _REACTOR_ACTOR,
            "reason": "complete local processor without sending externally",
        },
    )
    assert completion.status_code == 200
    completion_body = completion.json()
    assert completion_body["ok"] is True
    assert completion_body["applied"] is True
    assert completion_body["status"] == "deadletter_external_escalation_delivery_processor_completed"
    completion_receipt = completion_body["receipt"]
    assert completion_receipt["kind"] == "reactor.deadletter.external_escalation_delivery_processor_completion.receipt"
    assert completion_receipt["status"] == "processor_completed"
    assert completion_receipt["route"] == "deadletter_external_escalation_delivery_processor_completion"
    assert completion_receipt["stable_state"] == "deadletter_external_escalation_delivery_processor_completed"
    assert completion_receipt["external_delivery_queued"] is True
    assert completion_receipt["delivery_processor_handoff_recorded"] is True
    assert completion_receipt["delivery_processor_started"] is True
    assert completion_receipt["delivery_processor_completed"] is True
    assert completion_receipt["local_outbox_processor_completed"] is True
    assert completion_receipt["external_delivery_started"] is False
    assert completion_receipt["external_message_sent"] is False
    assert completion_receipt["external_network_send"] is False
    assert completion_receipt["execution_started"] is False
    assert completion_receipt["memory_write"] is False
    assert completion_receipt["completion_claim_allowed"] is False
    assert completion_receipt["governance"]["delivery_processor_completion_authority"] is True
    assert completion_receipt["governance"]["external_delivery_authority"] is False
    assert completion_receipt["governance"]["external_escalation_authority"] is False

    completion_output = completion_body["processor_output"]
    assert completion_output["kind"] == "reactor.deadletter.external_escalation.local_outbox.processor_output"
    assert completion_output["status"] == "processor_completed"
    assert completion_output["delivery_id"] == delivery_id
    assert completion_output["external_network_send"] is False
    completion_delivery = client.get(
        "/reactor/deadletters/external_escalation_deliveries/get",
        params={"id": delivery_id},
    )
    assert completion_delivery.status_code == 200
    assert completion_delivery.json()["item"]["status"] == "processor_completed"
    assert completion_delivery.json()["item"]["delivery_processor_completed"] is True
    assert completion_delivery.json()["item"]["external_network_send"] is False

    completion_event = completion_body["event"]
    assert completion_event["stable_state"] == "deadletter_external_escalation_delivery_processor_completed"
    assert completion_event["dispatch"]["deadletter_external_escalation_delivery_processor_completed"] is True
    assert completion_event["dispatch"]["delivery_processor_completed"] is True
    assert completion_event["dispatch"]["local_outbox_processor_completed"] is True
    assert completion_event["dispatch"]["external_delivery_started"] is False
    assert completion_event["dispatch"]["external_network_send"] is False
    assert completion_event["governance"]["delivery_processor_completion_authority"] is True
    assert completion_event["governance"]["external_delivery_authority"] is False

    completion_list = client.get(
        "/reactor/deadletters/list",
        params={"status": "external_escalation_delivery_processor_completed"},
    )
    assert completion_list.status_code == 200
    assert {item["deadletter_id"] for item in completion_list.json()["items"]} == {deadletter_id}
    completion_receipts = client.get(
        "/reactor/events/list",
        params={"receipt_kind": "reactor.deadletter.external_escalation_delivery_processor_completion.receipt"},
    )
    assert completion_receipts.status_code == 200
    assert {item["event_id"] for item in completion_receipts.json()["items"]} == {event_id}
    completion_history = client.get(
        "/reactor/deadletters/history/get",
        params={
            "id": deadletter_id,
            "receipt_kind": "reactor.deadletter.external_escalation_delivery_processor_completion.receipt",
        },
    )
    assert completion_history.status_code == 200
    assert completion_history.json()["history"]["total"] == 1
    assert (
        completion_history.json()["history"]["history"][0]["route"]
        == "deadletter_external_escalation_delivery_processor_completion"
    )
    completion_review = client.get(
        "/reactor/review_queue",
        params={"route": "deadletter_external_escalation_delivery_processor_completion"},
    )
    assert completion_review.status_code == 200
    assert completion_review.json()["available_total"] == 1
    assert (
        completion_review.json()["items"][0]["review"]["action"]
        == "await_explicit_external_delivery_sender_before_marking_sent"
    )
    completion_status = client.get("/reactor/status")
    assert completion_status.status_code == 200
    assert completion_status.json()["stable_state_counts"] == {
        "deadletter_external_escalation_delivery_processor_completed": 1
    }
    assert completion_status.json()["deadletter_queue_counts"] == {
        "external_escalation_delivery_processor_completed": 1
    }
    assert completion_status.json()["deadletter_external_escalation_delivery_counts"] == {"delivery_queued": 1}
    assert completion_status.json()["deadletter_external_escalation_delivery_processor_handoff_counts"] == {
        "processor_handoff_recorded": 1
    }
    assert completion_status.json()["deadletter_external_escalation_delivery_processor_completion_counts"] == {
        "processor_completed": 1
    }

    second_completion = client.post(
        "/reactor/deadletters/external_escalation_delivery_processor_completion",
        json={"delivery_id": delivery_id, "actor": _REACTOR_ACTOR},
    )
    assert second_completion.status_code == 200
    assert second_completion.json()["applied"] is False
    assert second_completion.json()["status"] == "already_external_escalation_delivery_processor_completed"


def test_reactor_dispatch_attempt_routes_missing_approval_into_pending_queue(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval-required Reactor work needs a real queue item",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "mission_id": "msn_reactor_api_approval",
            "operation_id": "tsk_reactor_api_approval",
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    attempted = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue missing approval for Reactor dispatch",
        },
    )

    assert attempted.status_code == 200
    body = attempted.json()
    assert body["ok"] is True
    event = body["event"]
    approval_id = event["trigger"]["approval_id"]
    assert approval_id
    assert event["dispatch"]["approval_request"]["approval_id"] == approval_id
    assert event["dispatch"]["approval_request"]["approval_queued"] is True
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["approval_request_queued"] is True

    approvals = client.get("/approvals/list", params={"status": "pending", "limit": 20})
    assert approvals.status_code == 200
    pending = next(item for item in approvals.json()["items"] if item["id"] == approval_id)
    assert pending["action"] == "reactor.dispatch"
    assert pending["status"] == "pending"
    assert pending["payload"]["event_id"] == event_id
    assert pending["payload"]["route"] == "approval_queue"
    assert pending["payload"]["gate"] == "approval_required"
    assert pending["payload"]["execution_started"] is False
    assert pending["payload"]["dispatch_applied"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["approval_request_counts"] == {"pending": 1}

    review_queue = client.get("/reactor/review_queue", params={"route": "approval_queue"})
    assert review_queue.status_code == 200
    review_item = review_queue.json()["items"][0]
    assert review_item["trigger"]["approval_id"] == approval_id
    assert review_item["review"]["receipt_kind"] == "reactor.approval_request.receipt"
    assert review_item["review"]["receipt_ref"] == approval_id


def test_reactor_dispatch_attempt_reconciles_approved_decision(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write"], _APPROVAL_ACTOR: ["approvals.decide"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approved Reactor work should resume only to deferred dispatch",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    first_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue missing approval for Reactor dispatch",
        },
    )
    assert first_attempt.status_code == 200
    approval_id = first_attempt.json()["event"]["trigger"]["approval_id"]
    assert approval_id

    approved = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": _APPROVAL_ACTOR,
            "comment": "approved for Reactor resume proof",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["ok"] is True
    assert approved.json()["status"] == "approved"

    resumed = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "resume after approval decision",
        },
    )

    assert resumed.status_code == 200
    body = resumed.json()
    assert body["ok"] is True
    event = body["event"]
    assert event["status"] == "dispatch_deferred"
    assert event["stable_state"] == "awaiting_dispatch_engine"
    assert event["dispatch"]["allowed"] is True
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "not_implemented"
    assert "blocker" not in event["dispatch"]
    approval_decision = event["dispatch"]["approval_decision"]
    assert approval_decision["kind"] == "reactor.approval_decision.receipt"
    assert approval_decision["approval_id"] == approval_id
    assert approval_decision["status"] == "approved"
    assert approval_decision["approval_allows_dispatch"] is True
    assert approval_decision["execution_started"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_deferred": 1}
    assert status.json()["approval_decision_counts"] == {"approved": 1}

    review_queue = client.get("/reactor/review_queue", params={"route": "approval_queue"})
    assert review_queue.status_code == 200
    assert review_queue.json()["available_total"] == 0


def test_reactor_dispatch_attempt_keeps_rejected_decision_in_operator_review(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write"], _APPROVAL_ACTOR: ["approvals.decide"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Rejected Reactor work must remain blocked",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
        },
    )
    assert queued.status_code == 200
    event_id = str(queued.json()["event_id"])

    first_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "queue missing approval for rejected Reactor proof",
        },
    )
    assert first_attempt.status_code == 200
    approval_id = first_attempt.json()["event"]["trigger"]["approval_id"]
    assert approval_id

    rejected = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "reject",
            "actor": _APPROVAL_ACTOR,
            "comment": "rejected for Reactor denial proof",
        },
    )
    assert rejected.status_code == 200
    assert rejected.json()["ok"] is True
    assert rejected.json()["status"] == "rejected"

    resumed = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "honor rejected approval decision",
        },
    )
    assert resumed.status_code == 200
    body = resumed.json()
    assert body["ok"] is True
    event = body["event"]
    assert event["status"] == "dispatch_blocked"
    assert event["stable_state"] == "approval_rejected"
    assert event["dispatch"]["allowed"] is False
    assert event["dispatch"]["applied"] is False
    assert event["dispatch"]["engine"] == "not_implemented"
    assert event["dispatch"]["blocked_route"] == "operator_review"
    assert event["dispatch"]["blocker"]["gate"] == "approval_rejected"
    assert event["dispatch"]["blocker"]["route"] == "operator_review"
    assert "dispatch_execution_receipt" not in event["dispatch"]

    approval_decision = event["dispatch"]["approval_decision"]
    assert approval_decision["kind"] == "reactor.approval_decision.receipt"
    assert approval_decision["approval_id"] == approval_id
    assert approval_decision["status"] == "rejected"
    assert approval_decision["approval_allows_dispatch"] is False
    assert approval_decision["execution_started"] is False
    assert approval_decision["applied"] is False
    assert event["governance"]["approval_authority"] is False
    assert event["governance"]["dispatch_authority"] is False
    assert event["governance"]["execution_authority"] is False
    assert event["governance"]["approval_status"] == "rejected"

    verification = event["latest_verification_receipt"]
    assert verification["route"] == "operator_review"
    assert verification["verification_status"] == "not_run"
    assert verification["verification_outcome"] == "approval_denied"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is False
    stable_return = event["latest_stable_return"]
    assert stable_return["route"] == "operator_review"
    assert stable_return["stable_state"] == "approval_rejected"
    assert stable_return["approval_status"] == "rejected"

    operator_review = client.get("/reactor/review_queue", params={"route": "operator_review"})
    assert operator_review.status_code == 200
    assert operator_review.json()["available_total"] == 1
    assert operator_review.json()["items"][0]["review"]["gate"] == "approval_rejected"
    approval_review = client.get("/reactor/review_queue", params={"route": "approval_queue"})
    assert approval_review.status_code == 200
    assert approval_review.json()["available_total"] == 0

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["status_counts"] == {"dispatch_blocked": 1}
    assert status.json()["blocker_route_counts"] == {"operator_review": 1}
    assert status.json()["approval_decision_counts"] == {"rejected": 1}
    assert status.json()["verification_outcome_counts"] == {"approval_denied": 1}


def test_reactor_approval_decision_event_records_resume_receipt_without_execution(
    monkeypatch,
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv(
        "FRANCIS_API_ACTOR_SCOPES",
        json.dumps({_REACTOR_ACTOR: ["reactor.write"], _APPROVAL_ACTOR: ["approvals.decide"]}),
    )

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    queued = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "Approval decision event should only record resume readiness",
            "actor": _REACTOR_ACTOR,
            "risk_tier": "critical",
            "action_class": "mutate",
            "approval_required": True,
            "operation_id": "op_resume_api",
        },
    )
    assert queued.status_code == 200
    target_event_id = str(queued.json()["event_id"])
    first_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={"event_id": target_event_id, "actor": _REACTOR_ACTOR, "reason": "queue approval"},
    )
    assert first_attempt.status_code == 200
    approval_id = first_attempt.json()["event"]["trigger"]["approval_id"]

    approved = client.post(
        "/approvals/decision",
        json={
            "id": approval_id,
            "action": "approve",
            "actor": _APPROVAL_ACTOR,
            "comment": "approved for explicit approval-decision event resume",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    resume_event = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "approval_decision",
            "trigger_type": "approved",
            "summary": "Approved event can be resumed through explicit dispatch",
            "actor": _REACTOR_ACTOR,
            "approval_id": approval_id,
            "metadata": {
                "reactor_event_id": target_event_id,
                "operation_id": "op_resume_api",
            },
        },
    )
    assert resume_event.status_code == 200
    resume_event_id = str(resume_event.json()["event_id"])
    assert resume_event.json()["event"]["classification"]["action_class"] == "resume"

    resumed = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": resume_event_id,
            "actor": _REACTOR_ACTOR,
            "reason": "record resume readiness without dispatching target event",
        },
    )
    assert resumed.status_code == 200
    body = resumed.json()
    event = body["event"]
    assert event["status"] == "dispatch_completed"
    assert event["stable_state"] == "approval_resume_recorded"
    assert event["dispatch"]["engine"] == "approval_resume"
    assert event["dispatch"]["applied"] is True
    assert event["dispatch"]["execution_started"] is False
    execution = event["latest_dispatch_execution_receipt"]
    assert execution["route"] == "approval_resume"
    assert execution["outcome"] == "approval_resume_approved"
    assert execution["approval_id"] == approval_id
    assert execution["approval_status"] == "approved"
    assert execution["approval_allows_dispatch"] is True
    assert execution["target_event_id"] == target_event_id
    assert execution["operation_id"] == "op_resume_api"
    assert execution["approval_decision_applied"] is False
    assert execution["execution_started"] is False
    assert execution["readback_only"] is True
    assert execution["memory_write"] is False
    assert execution["governance"]["approval_decision_authority"] is False
    assert execution["governance"]["execution_authority"] is False

    verification = event["latest_verification_receipt"]
    assert verification["verification_status"] == "passed"
    assert verification["verification_outcome"] == "approval_resume_approved"
    assert verification["route"] == "approval_resume"
    assert verification["execution_started"] is False
    assert verification["dispatch_applied"] is True

    target = client.get("/reactor/events/get", params={"id": target_event_id})
    assert target.status_code == 200
    assert target.json()["item"]["dispatch"]["applied"] is False
    assert "dispatch_execution_receipt" not in target.json()["item"]["dispatch"]

    status = client.get("/reactor/status")
    assert status.status_code == 200
    assert status.json()["dispatch_engine_supported_actions"] == [
        "classify",
        "mission_tick",
        "operation_run",
        "proposal_review",
        "resume",
    ]
    assert status.json()["status_counts"] == {"dispatch_blocked": 1, "dispatch_completed": 1}
    assert status.json()["dispatch_execution_counts"] == {"completed": 1}
    assert status.json()["verification_outcome_counts"] == {
        "approval_resume_approved": 1,
        "awaiting_approval": 1,
    }

    history = client.get(
        "/reactor/approval_resumes/history/list",
        params={"approval_id": approval_id, "approval_status": "approved"},
    )
    assert history.status_code == 200
    history_body = history.json()
    assert history_body["total"] == 1
    assert history_body["allowed_total"] == 1
    assert history_body["blocked_total"] == 0
    assert history_body["governance"]["approval_decision_authority"] is False
    assert history_body["governance"]["execution_authority"] is False
    history_item = history_body["items"][0]
    assert history_item["kind"] == "reactor.approval_resume.history.readback"
    assert history_item["event_id"] == resume_event_id
    assert history_item["route"] == "approval_resume"
    assert history_item["outcome"] == "approval_resume_approved"
    assert history_item["approval_id"] == approval_id
    assert history_item["approval_status"] == "approved"
    assert history_item["approval_allows_dispatch"] is True
    assert history_item["target_event_id"] == target_event_id
    assert history_item["operation_id"] == "op_resume_api"
    assert history_item["execution_started"] is False
    assert history_item["approval_decision_applied"] is False
    assert history_item["governance"]["approval_decision_authority"] is False
    assert history_item["governance"]["execution_authority"] is False

    filtered_history = client.get(
        "/reactor/approval_resumes/history/list",
        params={"target_event_id": target_event_id, "operation_id": "op_resume_api", "approval_allows_dispatch": True},
    )
    assert filtered_history.status_code == 200
    assert filtered_history.json()["items"][0]["event_id"] == resume_event_id

    empty_history = client.get(
        "/reactor/approval_resumes/history/list",
        params={"approval_id": "missing_approval"},
    )
    assert empty_history.status_code == 200
    assert empty_history.json()["items"] == []


def test_reactor_event_routes_require_scope_and_valid_trigger(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", "{}")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    denied = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "user_request",
            "summary": "operator asked to continue",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert denied.status_code == 200
    assert denied.json()["ok"] is False
    assert denied.json()["error"] == "api_permission_denied"
    assert denied.json()["governance"]["scope"] == "reactor.write"

    denied_attempt = client.post(
        "/reactor/events/dispatch_attempt",
        json={
            "event_id": "reactor_evt_missing",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert denied_attempt.status_code == 200
    assert denied_attempt.json()["ok"] is False
    assert denied_attempt.json()["error"] == "api_permission_denied"

    monkeypatch.setenv("FRANCIS_API_ACTOR_SCOPES", json.dumps({_REACTOR_ACTOR: ["reactor.write"]}))
    client = TestClient(create_app())
    invalid = client.post(
        "/reactor/events/enqueue",
        json={
            "trigger_source": "self_loop",
            "summary": "keep doing things without a trigger",
            "actor": _REACTOR_ACTOR,
        },
    )
    assert invalid.status_code == 200
    assert invalid.json()["ok"] is False
    assert invalid.json()["error"] == "invalid_trigger_source"
    assert not (data_root / "reactor" / "events").exists()
