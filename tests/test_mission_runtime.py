from __future__ import annotations

from typing import Any


def test_run_queue_once_promotes_nested_approval_receipt_lineage(monkeypatch, tmp_path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.missions import runtime as mission_runtime
    from francis.missions.store import MissionCreateRequest, create_mission

    operation_id = "tsk_nested_receipt_lineage"
    mission, err = create_mission(
        MissionCreateRequest(
            objective="Queue runtime should preserve approval receipt lineage",
            summary="Nested receipt approval handles should survive queue-run handoff readback.",
            requester_id="test.missions.runtime",
            linked_task_ids=[operation_id],
        )
    )
    assert err is None
    assert mission is not None

    def run_operation(
        operation_id: str,
        *,
        worker_id: str = "missions.runner",
        advance_action: str = "run_linked_operation",
    ) -> dict[str, Any]:
        return {
            "ok": True,
            "status": "queued",
            "message": "waiting on approval",
            "operation": {
                "id": operation_id,
                "name": "plugin.run",
                "status": "queued",
                "meta": {
                    "orb_plane": "P3_GOVERNANCE",
                    "governance": {
                        "gate": "approvals_gate",
                        "next_step": "review_pending_approval",
                    },
                },
                "output": {
                    "receipt": {
                        "approval_id": "apr_nested_lineage",
                        "previous_approval_id": "apr_previous_lineage",
                        "governance": {"approval_status": "pending"},
                    }
                },
            },
        }

    monkeypatch.setattr(mission_runtime.operations_runtime, "run_operation", run_operation)

    result = mission_runtime.run_queue_once(
        limit=10,
        actor="test.missions.runtime",
        note="queue nested receipt approval lineage",
    )

    assert result["ok"] is True
    mission_result = next(item for item in result["results"] if item["mission_id"] == mission.mission_id)
    assert mission_result["applied"] is True
    assert mission_result["action"] == "run_linked_operation"
    assert mission_result["operation_id"] == operation_id
    assert mission_result["approval_id"] == "apr_nested_lineage"
    assert mission_result["previous_approval_id"] == "apr_previous_lineage"
    assert mission_result["approval_status"] == "pending"
