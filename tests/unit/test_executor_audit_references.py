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


def test_executor_syncs_mission_transition_from_loop_mission_alias(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import executor
    from francis.agent.delegation import DelegationRequest, create_delegation, read_audit
    from francis.missions import store as mission_store
    from francis.missions.store import MissionCreateRequest

    mission, mission_err = mission_store.create_mission(
        MissionCreateRequest(
            objective="Carry sparse mission alias through executor sync.",
            requester_id="test.executor.alias",
        )
    )
    assert mission_err is None
    assert mission is not None

    def capability_with_status(inputs: dict[str, object], objective: str) -> dict[str, object]:
        return {
            "kind": "test.loop.alias.result",
            "objective": objective,
            "status": "succeeded",
            "inputs_seen": sorted(inputs.keys()),
        }

    monkeypatch.setitem(executor.CAPABILITY_ALLOWLIST, "test.loop.alias", capability_with_status)

    record, err = create_delegation(
        DelegationRequest(
            requester_id="test.executor.alias",
            capability="test.loop.alias",
            objective="Preserve mission transition from alias-only loop metadata",
            inputs={
                "ticket": "EXEC-ALIAS-1",
                "meta": {"handoff_mission_id": mission.mission_id},
            },
            priority=5,
            ttl_sec=900,
        )
    )
    assert err is None
    assert record is not None

    created_audit = next(item for item in read_audit(record.task_id) if item.get("event") == "created")
    assert created_audit["details"]["mission_id"] == mission.mission_id

    executed = executor.execute_task(record.task_id, worker_id="test.executor.alias")
    assert executed["status"] == "complete"

    updated, read_err = mission_store.read_mission(mission.mission_id)
    assert read_err is None
    assert updated is not None
    assert updated.meta["last_task_id"] == record.task_id
    assert updated.meta["last_task_status"] == "completed"
    assert updated.meta["last_task_result_status"] == "succeeded"

    history = mission_store.read_history(mission.mission_id)
    transitions = [item for item in history if item.get("event") == "linked_task_transition"]
    assert [item["details"]["note"] for item in transitions] == ["task_started", "task_finished"]
    assert transitions[-1]["details"]["task_id"] == record.task_id
