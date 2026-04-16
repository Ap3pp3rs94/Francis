from __future__ import annotations

import json
from pathlib import Path

from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest, MissionStatus


def _write_task_record(repo_root: Path, task_id: str, payload: dict[str, object]) -> None:
    task_dir = repo_root / "data" / "tasks" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "record.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")


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
    assert queue_item["last_task_approval_id"] == "apr_exact_123"
    assert queue_item["last_task_previous_approval_id"] == "apr_old_122"
    assert queue_item["last_task_approval_status"] == "pending"
    assert queue_item["operator_hint"] == "Approval apr_exact_123 is pending before the mission can continue."


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
