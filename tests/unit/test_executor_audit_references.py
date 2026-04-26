from __future__ import annotations

from pathlib import Path


def test_executor_status_audit_preserves_receipt_approval_reference(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import executor
    from francis.agent.delegation import DelegationRequest, create_delegation, read_audit

    def capability_with_nested_receipt(inputs: dict[str, object], objective: str) -> dict[str, object]:
        return {
            "kind": "test.approval.audit.result",
            "objective": objective,
            "receipt": {
                "approval_id": "apr_executor_receipt",
                "trace_id": "trace_executor_receipt",
                "run_id": "run_executor_receipt",
                "artifact_dir": str(data_root / "artifacts" / "executor_receipt"),
            },
            "inputs_seen": sorted(inputs.keys()),
        }

    monkeypatch.setitem(executor.CAPABILITY_ALLOWLIST, "test.approval.audit", capability_with_nested_receipt)

    record, err = create_delegation(
        DelegationRequest(
            requester_id="test.executor.audit",
            capability="test.approval.audit",
            objective="Preserve approval handles in execution audit receipts",
            inputs={"ticket": "EXEC-AUDIT-1"},
            priority=5,
            ttl_sec=900,
        )
    )

    assert err is None
    assert record is not None

    executed = executor.execute_task(record.task_id, worker_id="test.executor.audit")
    assert executed["status"] == "complete"

    audit = read_audit(record.task_id)
    finished = [
        item
        for item in audit
        if item.get("event") == "status_updated" and item.get("details", {}).get("to") == "complete"
    ][-1]
    details = finished["details"]
    assert details["approval_id"] == "apr_executor_receipt"
    assert details["trace_id"] == "trace_executor_receipt"
    assert details["run_id"] == "run_executor_receipt"
    assert details["artifact_dir"] == str(data_root / "artifacts" / "executor_receipt")
