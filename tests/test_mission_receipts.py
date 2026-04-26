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
            "approval_status": "approved",
            "capability": "plugin.run",
        },
    )

    receipts = mission_operation_receipts("msn_receipt_refs")

    assert len(receipts) == 1
    assert receipts[0]["mission_id"] == "msn_receipt_refs"
    assert receipts[0]["operation_id"] == "tsk_receipt_refs"
    assert receipts[0]["approval_id"] == "apr_receipt_refs"
    assert receipts[0]["approval_status"] == "approved"
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
