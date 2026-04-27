from __future__ import annotations

import json
from pathlib import Path

from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest, MissionStatus


def _write_task_record(repo_root: Path, task_id: str, payload: dict[str, object]) -> None:
    task_dir = repo_root / "data" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "record.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_approval_record(repo_root: Path, status: str, approval_id: str, payload: dict[str, object]) -> None:
    approval_dir = repo_root / "data" / "approvals" / status
    approval_dir.mkdir(parents=True, exist_ok=True)
    (approval_dir / f"{approval_id}.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_mission_context_fields_are_typed_and_legacy_records_remain_readable(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Carry explicit mission context.",
            requester_id="test.mission.store",
            owner_id="owner.alpha",
            dependency_ids=["dep_one", "dep_two", "dep_one"],
            escalation_path="Review with the operator before retrying.",
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None
    assert mission.owner_id == "owner.alpha"
    assert mission.dependency_ids == ["dep_one", "dep_two"]
    assert mission.escalation_path == "Review with the operator before retrying."

    updated, err = mission_store.update_mission(
        mission.mission_id,
        repo_root=tmp_path,
        owner_id="owner.beta",
        dependency_ids=["dep_two"],
        escalation_path="Deadletter if dependency dep_two remains blocked.",
        actor="test.mission.store",
        note="tighten explicit context",
    )
    assert err is None
    assert updated is not None
    assert updated.owner_id == "owner.beta"
    assert updated.dependency_ids == ["dep_two"]
    assert updated.escalation_path == "Deadletter if dependency dep_two remains blocked."

    history = mission_store.read_history(mission.mission_id, repo_root=tmp_path)
    continuity_event = [item for item in history if item.get("event") == "continuity_updated"][-1]
    assert continuity_event["details"]["owner_id"] == "owner.beta"
    assert continuity_event["details"]["dependency_ids"] == ["dep_two"]
    assert continuity_event["details"]["escalation_path"] == "Deadletter if dependency dep_two remains blocked."

    legacy_id = "msn_legacy_context"
    legacy_dir = tmp_path / "data" / "missions" / legacy_id
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "record.json").write_text(
        json.dumps(
            {
                "mission_id": legacy_id,
                "created_at": "2026-04-21T00:00:00+00:00",
                "updated_at": "2026-04-21T00:00:00+00:00",
                "status": "queued",
                "objective": "Legacy record without context fields",
                "requester_id": "legacy.requester",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    legacy, err = mission_store.read_mission(legacy_id, repo_root=tmp_path)
    assert err is None
    assert legacy is not None
    assert legacy.owner_id == "legacy.requester"
    assert legacy.dependency_ids == []
    assert legacy.escalation_path == ""


def test_mission_queue_waits_for_unresolved_dependency_before_first_operation(tmp_path: Path) -> None:
    dependency, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Prepare the prerequisite evidence.",
            requester_id="test.mission.store",
            status=MissionStatus.ACTIVE,
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert dependency is not None

    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Advance only after prerequisite evidence exists.",
            requester_id="test.mission.store",
            dependency_ids=[dependency.mission_id],
            escalation_path="Ask the operator whether to deadletter or replace the dependency.",
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    _, queue_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert queue_item is not None
    assert queue_item["recommended_action"] == "wait_for_dependency"
    assert queue_item["action_target_id"] == dependency.mission_id
    assert queue_item["advance"]["eligible"] is False
    assert queue_item["advance"]["action"] == "wait_for_dependency"
    assert queue_item["advance"]["target_id"] == dependency.mission_id
    assert queue_item["dependency_state"]["status"] == "waiting"
    assert queue_item["dependency_state"]["unresolved"] == 1
    assert queue_item["dependency_state"]["first_unresolved"]["id"] == dependency.mission_id
    assert "Escalation:" in queue_item["operator_hint"]

    completed_dependency, err = mission_store.update_mission(
        dependency.mission_id,
        repo_root=tmp_path,
        status=MissionStatus.COMPLETED,
        actor="test.mission.store",
        note="dependency satisfied",
    )
    assert err is None
    assert completed_dependency is not None

    _, ready_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert ready_item is not None
    assert ready_item["recommended_action"] == "create_first_operation"
    assert ready_item["advance"]["eligible"] is True
    assert ready_item["advance"]["action"] == "create_first_operation"
    assert ready_item["dependency_state"]["status"] == "clear"
    assert ready_item["dependency_state"]["resolved"] == 1


def test_record_linked_task_transition_surfaces_exact_pending_approval(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Keep approval context visible at the mission layer.",
            requester_id="test.mission.store",
            summary="Mission should name the exact pending approval.",
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    updated, err = mission_store.record_linked_task_transition(
        mission.mission_id,
        "tsk_pending_approval",
        repo_root=tmp_path,
        task_status="accepted",
        result_status="needs_approval",
        governance={"gate": "approvals_gate", "next_step": "approve_exact_action", "approval_status": "pending"},
        approval_id="apr_exact_123",
        previous_approval_id="apr_old_122",
        actor="test.mission.store",
        note="persist governance hold context",
    )
    assert err is None
    assert updated is not None
    assert updated.status == MissionStatus.BLOCKED
    assert updated.meta["last_task_approval_id"] == "apr_exact_123"
    assert updated.meta["last_task_previous_approval_id"] == "apr_old_122"
    assert updated.meta["last_task_approval_status"] == "pending"

    _, queue_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert queue_item is not None
    assert queue_item["recommended_action"] == "review_pending_approval"
    assert queue_item["advance"]["eligible"] is False
    assert queue_item["advance"]["action"] == "review_pending_approval"
    assert queue_item["last_task_approval_id"] == "apr_exact_123"
    assert queue_item["last_task_previous_approval_id"] == "apr_old_122"
    assert queue_item["last_task_approval_status"] == "pending"
    assert queue_item["operator_hint"] == "Approval apr_exact_123 is pending before the mission can continue."


def test_record_linked_task_transition_preserves_task_timestamp_for_idempotent_tick(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Keep blocked mission ticks idempotent.",
            requester_id="test.mission.store",
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    task_id = "tsk_blocked_timestamp"
    task_updated_at = "2026-04-26T06:30:27+00:00"
    _write_task_record(
        tmp_path,
        task_id,
        {
            "task_id": task_id,
            "status": "accepted",
            "created_at": "2026-04-26T06:30:26+00:00",
            "updated_at": task_updated_at,
            "status_reason": "insufficient_trust",
            "result": {
                "data": {
                    "status": "blocked",
                    "governance": {
                        "gate": "trust_gate",
                        "next_step": "raise_trust_or_reduce_risk",
                    },
                }
            },
        },
    )

    updated, err = mission_store.record_linked_task_transition(
        mission.mission_id,
        task_id,
        repo_root=tmp_path,
        task_status="accepted",
        result_status="blocked",
        status_reason="insufficient_trust",
        governance={"gate": "trust_gate", "next_step": "raise_trust_or_reduce_risk"},
        task_updated_at=task_updated_at,
        actor="test.mission.store",
        note="sync blocked task",
    )
    assert err is None
    assert updated is not None
    assert updated.status == MissionStatus.BLOCKED
    assert updated.meta["last_task_updated_at"] == task_updated_at

    ticked, applied, err = mission_store.tick_mission(
        mission.mission_id,
        repo_root=tmp_path,
        actor="test.mission.store",
        note="repeat blocked task sync",
    )
    assert err is None
    assert ticked is not None
    assert applied is False

    history_events = [item.get("event") for item in mission_store.read_history(mission.mission_id, repo_root=tmp_path)]
    assert history_events.count("mission_ticked") == 0


def test_mission_queue_refreshes_approved_gate_into_rerun_action(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Approved mission should become runnable again.",
            requester_id="test.mission.store",
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    updated, err = mission_store.record_linked_task_transition(
        mission.mission_id,
        "tsk_approved_gate",
        repo_root=tmp_path,
        task_status="accepted",
        result_status="needs_approval",
        governance={"gate": "approvals_gate", "next_step": "approve_exact_action", "approval_status": "pending"},
        approval_id="apr_exact_approved",
        actor="test.mission.store",
        note="persist pending gate before approval decision",
    )
    assert err is None
    assert updated is not None

    _write_approval_record(
        tmp_path,
        "approved",
        "apr_exact_approved",
        {
            "id": "apr_exact_approved",
            "action": "plugin.run",
            "reason": "approved exact action",
            "status": "approved",
            "payload": {"plugin_id": "builtin.echo", "action": "deploy"},
        },
    )

    _, queue_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert queue_item is not None
    assert queue_item["last_task_approval_id"] == "apr_exact_approved"
    assert queue_item["last_task_approval_status"] == "approved"
    assert queue_item["recommended_action"] == "run_linked_operation"
    assert queue_item["action_target_id"] == "tsk_approved_gate"
    assert queue_item["advance"]["eligible"] is True
    assert queue_item["advance"]["action"] == "run_linked_operation"
    assert queue_item["current_task"]["approval_status"] == "approved"
    assert (
        queue_item["operator_hint"]
        == "Approval apr_exact_approved is approved; rerun the linked operation through the governed runtime."
    )


def test_tick_mission_derives_approval_context_from_linked_task_record(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Rebuild approval hold context from linked task truth.",
            requester_id="test.mission.store",
            linked_task_ids=["tsk_refresh_hold"],
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    _write_task_record(
        tmp_path,
        "tsk_refresh_hold",
        {
            "task_id": "tsk_refresh_hold",
            "status": "accepted",
            "created_at": "2026-04-15T22:00:00+00:00",
            "updated_at": "2026-04-15T22:01:00+00:00",
            "result": {
                "data": {
                    "status": "needs_approval",
                    "approval_id": "apr_refresh_200",
                    "previous_approval_id": "apr_refresh_199",
                    "message": "approval refreshed after payload drift",
                    "governance": {
                        "gate": "approvals_gate",
                        "approval_status": "pending",
                        "next_step": "approve_exact_action",
                    },
                }
            },
        },
    )

    ticked, applied, err = mission_store.tick_mission(
        mission.mission_id,
        repo_root=tmp_path,
        actor="test.mission.store",
        note="derive latest approval context from linked task",
    )
    assert err is None
    assert applied is True
    assert ticked is not None
    assert ticked.status == MissionStatus.BLOCKED
    assert ticked.meta["last_task_approval_id"] == "apr_refresh_200"
    assert ticked.meta["last_task_previous_approval_id"] == "apr_refresh_199"
    assert ticked.meta["last_task_approval_status"] == "pending"
    assert ticked.meta["last_task_gate"] == "approvals_gate"

    _, queue_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert queue_item is not None
    assert queue_item["last_task_approval_id"] == "apr_refresh_200"
    assert queue_item["operator_hint"] == "Approval apr_refresh_200 is pending before the mission can continue."

    history = mission_store.read_history(mission.mission_id, repo_root=tmp_path)
    latest = history[-1]
    assert latest["event"] == "mission_ticked"
    assert latest["details"]["latest_task_approval_id"] == "apr_refresh_200"
    assert latest["details"]["latest_task_previous_approval_id"] == "apr_refresh_199"
    assert latest["details"]["latest_task_approval_status"] == "pending"


def test_tick_mission_promotes_nested_receipt_approval_context(tmp_path: Path) -> None:
    mission, err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Rebuild approval hold context from nested receipt truth.",
            requester_id="test.mission.store",
            linked_task_ids=["tsk_nested_receipt_hold"],
        ),
        repo_root=tmp_path,
    )
    assert err is None
    assert mission is not None

    _write_task_record(
        tmp_path,
        "tsk_nested_receipt_hold",
        {
            "task_id": "tsk_nested_receipt_hold",
            "status": "accepted",
            "created_at": "2026-04-15T22:00:00+00:00",
            "updated_at": "2026-04-15T22:01:00+00:00",
            "result": {
                "data": {
                    "status": "needs_approval",
                    "message": "approval is carried by execution receipt",
                    "receipt": {
                        "approval_id": "apr_nested_receipt_200",
                        "previous_approval_id": "apr_nested_receipt_199",
                    },
                    "governance": {
                        "gate": "approvals_gate",
                        "approval_status": "pending",
                        "next_step": "approve_exact_action",
                    },
                }
            },
        },
    )

    ticked, applied, err = mission_store.tick_mission(
        mission.mission_id,
        repo_root=tmp_path,
        actor="test.mission.store",
        note="derive latest approval context from nested receipt",
    )
    assert err is None
    assert applied is True
    assert ticked is not None
    assert ticked.status == MissionStatus.BLOCKED
    assert ticked.meta["last_task_approval_id"] == "apr_nested_receipt_200"
    assert ticked.meta["last_task_previous_approval_id"] == "apr_nested_receipt_199"
    assert ticked.meta["last_task_approval_status"] == "pending"

    _, queue_item, err = mission_store.mission_queue_item(mission.mission_id, repo_root=tmp_path)
    assert err is None
    assert queue_item is not None
    assert queue_item["last_task_approval_id"] == "apr_nested_receipt_200"
    assert queue_item["last_task_previous_approval_id"] == "apr_nested_receipt_199"
    assert queue_item["current_task"]["approval_id"] == "apr_nested_receipt_200"
    assert queue_item["operator_hint"] == (
        "Approval apr_nested_receipt_200 is pending before the mission can continue."
    )
