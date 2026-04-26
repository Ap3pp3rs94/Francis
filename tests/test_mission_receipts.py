from __future__ import annotations

from pathlib import Path


def test_mission_operation_receipts_preserve_structured_references(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.chat.continuity.ledger import append
    from francis.memory.mission_receipts import mission_operation_receipts, operation_memory_receipts

    append(
        "system",
        "Mission operation completed: mission=msn_receipt_refs operation=tsk_receipt_refs status=succeeded",
        {
            "domain": "operations",
            "scope": "mission.loop",
            "subsystem": "operations.runtime",
            "mission_id": "msn_receipt_refs",
            "operation_id": "tsk_receipt_refs",
            "trace_id": "trace_receipt_refs",
            "approval_id": "apr_receipt_refs",
            "run_id": "run_receipt_refs",
            "artifact_dir": "D:/francis/data/artifacts/receipt-refs",
            "operation_status": "succeeded",
            "operation_error": "",
            "recovery_next_step": "",
            "approval_status": "approved",
            "capability": "plugin.run",
            "active_stage": "interface",
            "handoff_stage": "interface",
            "handoff_action": "review_result",
            "handoff_operation_id": "tsk_receipt_refs",
            "handoff_trace_id": "trace_receipt_refs",
            "handoff_run_id": "run_receipt_refs",
            "handoff_artifact_dir": "D:/francis/data/artifacts/receipt-refs",
            "handoff_next_step": "review_completed_mission",
            "current_task_source": "terminal_operation_receipt",
            "current_task_operation_id": "tsk_receipt_refs",
            "current_task_trace_id": "trace_receipt_refs",
            "current_task_run_id": "run_receipt_refs",
            "current_task_artifact_dir": "D:/francis/data/artifacts/receipt-refs",
            "current_task_next_step": "review_completed_mission",
            "memory_receipt_count": 1,
        },
    )

    receipts = mission_operation_receipts("msn_receipt_refs")

    assert len(receipts) == 1
    assert receipts[0]["mission_id"] == "msn_receipt_refs"
    assert receipts[0]["operation_id"] == "tsk_receipt_refs"
    assert receipts[0]["approval_id"] == "apr_receipt_refs"
    assert receipts[0]["approval_status"] == "approved"
    assert receipts[0]["active_stage"] == "interface"
    assert receipts[0]["handoff_stage"] == "interface"
    assert receipts[0]["handoff_action"] == "review_result"
    assert receipts[0]["handoff_operation_id"] == "tsk_receipt_refs"
    assert receipts[0]["handoff_trace_id"] == "trace_receipt_refs"
    assert receipts[0]["handoff_run_id"] == "run_receipt_refs"
    assert receipts[0]["handoff_next_step"] == "review_completed_mission"
    assert receipts[0]["current_task_source"] == "terminal_operation_receipt"
    assert receipts[0]["current_task_operation_id"] == "tsk_receipt_refs"
    assert receipts[0]["current_task_trace_id"] == "trace_receipt_refs"
    assert receipts[0]["current_task_run_id"] == "run_receipt_refs"
    assert receipts[0]["current_task_next_step"] == "review_completed_mission"
    assert receipts[0]["memory_receipt_count"] == 1
    assert receipts[0]["references"] == {
        "mission_id": "msn_receipt_refs",
        "operation_id": "tsk_receipt_refs",
        "trace_id": "trace_receipt_refs",
        "approval_id": "apr_receipt_refs",
        "run_id": "run_receipt_refs",
        "artifact_dir": "D:/francis/data/artifacts/receipt-refs",
    }

    operation_receipts = operation_memory_receipts("tsk_receipt_refs", mission_id="msn_receipt_refs")
    assert operation_receipts == receipts
    assert operation_memory_receipts("tsk_receipt_refs", mission_id="other_mission") == []


def test_mission_operation_receipts_preserve_failure_recovery_context(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.chat.continuity.ledger import append
    from francis.memory.mission_receipts import operation_memory_receipts

    append(
        "system",
        "Mission operation failed: mission=msn_failure_refs operation=tsk_failure_refs status=failed",
        {
            "domain": "operations",
            "scope": "mission.loop",
            "subsystem": "operations.runtime",
            "mission_id": "msn_failure_refs",
            "operation_id": "tsk_failure_refs",
            "trace_id": "trace_failure_refs",
            "run_id": "run_failure_refs",
            "operation_status": "failed",
            "operation_error": "plugin_id_required",
            "result_message": "Plugin id is required.",
            "recovery_next_step": "review_operation_detail",
            "capability": "plugin.run",
        },
    )

    receipts = operation_memory_receipts("tsk_failure_refs", mission_id="msn_failure_refs")

    assert len(receipts) == 1
    assert receipts[0]["operation_status"] == "failed"
    assert receipts[0]["operation_error"] == "plugin_id_required"
    assert receipts[0]["result_message"] == "Plugin id is required."
    assert receipts[0]["recovery_next_step"] == "review_operation_detail"
