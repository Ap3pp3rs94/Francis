from __future__ import annotations

import json
from pathlib import Path


def test_executor_lock_writes_lease_acquire_deny_and_release_receipts(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import executor

    assert executor._try_acquire_lock("tsk_lease_receipt", "worker-1", stale_seconds=3600) is True
    assert executor._try_acquire_lock("tsk_lease_receipt", "worker-2", stale_seconds=3600) is False
    executor._release_lock("tsk_lease_receipt")

    receipt_dir = data_root / "artifacts" / "executor_lease_receipts"
    receipts = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(receipt_dir.glob("*.json"), key=lambda item: item.stat().st_mtime)
    ]

    assert [item["kind"] for item in receipts] == [
        "executor.lease.receipt",
        "executor.lease.receipt",
        "executor.lease.receipt",
    ]
    assert [item["decision"] for item in receipts] == ["acquired", "denied", "released"]
    assert [item["reason"] for item in receipts] == ["lock_acquired", "active_lock_exists", "lock_released"]
    assert receipts[0]["worker_id"] == "worker-1"
    assert receipts[1]["worker_id"] == "worker-2"
    assert receipts[2]["worker_id"] == "worker-1"
    assert all(item["task_id"] == "tsk_lease_receipt" for item in receipts)
    assert all(item["governance"]["lease_receipt"] is True for item in receipts)
    assert all(item["governance"]["execution_authority"] is False for item in receipts)
    assert not executor.lock_path("tsk_lease_receipt").exists()


def test_executor_failure_writes_retry_budget_exhaustion_receipt(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import executor
    from francis.agent.delegation import DelegationRequest, create_delegation

    def failing_capability(_inputs: dict[str, object], _objective: str) -> dict[str, object]:
        return {"kind": "test.retry.failure", "ok": False, "status": "failed", "error": "planned_failure"}

    monkeypatch.setitem(executor.CAPABILITY_ALLOWLIST, "test.retry.failure", failing_capability)

    record, err = create_delegation(
        DelegationRequest(
            requester_id="test.executor.retry",
            capability="test.retry.failure",
            objective="Write retry budget exhaustion receipt",
            inputs={"max_attempts": 1},
            priority=5,
            ttl_sec=900,
        )
    )
    assert err is None
    assert record is not None

    executed = executor.execute_task(record.task_id, worker_id="test.executor.retry")

    assert executed["status"] == "failed"
    assert executed["attempts"] == 1
    retry_budget = executed["result"]["data"]["retry_budget"]
    assert retry_budget["attempts"] == 1
    assert retry_budget["max_attempts"] == 1
    assert retry_budget["retry_exhausted"] is True
    assert retry_budget["retry_started"] is False
    receipt_path = Path(str(retry_budget["receipt_path"]))
    assert receipt_path == data_root / "artifacts" / "executor_retry_receipts" / f"{retry_budget['receipt_id']}.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "executor.retry_budget.receipt"
    assert receipt["task_id"] == record.task_id
    assert receipt["worker_id"] == "test.executor.retry"
    assert receipt["attempts"] == 1
    assert receipt["max_attempts"] == 1
    assert receipt["retry_exhausted"] is True
    assert receipt["retry_started"] is False
    assert receipt["status"] == "exhausted"
    assert receipt["governance"]["bounded_retry_contract"] is True
    assert receipt["governance"]["hidden_retry"] is False
    assert receipt["governance"]["retry_authority"] is False


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


def test_executor_capability_exceptions_are_publicly_sanitized(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from francis.agent import executor
    from francis.agent.delegation import DelegationRequest, create_delegation, read_audit

    def failing_capability(_inputs: dict[str, object], _objective: str) -> dict[str, object]:
        raise RuntimeError("executor traceback token=executor-secret")

    monkeypatch.setitem(executor.CAPABILITY_ALLOWLIST, "test.executor.failure", failing_capability)

    record, err = create_delegation(
        DelegationRequest(
            requester_id="test.executor.failure",
            capability="test.executor.failure",
            objective="Sanitize executor capability failures",
            inputs={"ticket": "EXEC-FAIL-1"},
            priority=5,
            ttl_sec=900,
        )
    )
    assert err is None
    assert record is not None

    executed = executor.execute_task(record.task_id, worker_id="test.executor.failure")

    assert executed["status"] == "failed"
    assert executed["status_reason"] == "capability_internal_error"
    assert executed["result"]["ok"] is False
    assert executed["result"]["data"]["error"] == "capability_internal_error"
    public_text = json.dumps(executed, sort_keys=True)
    assert "executor-secret" not in public_text
    assert "RuntimeError" not in public_text
    assert "traceback" not in public_text.lower()

    finished = [
        item
        for item in read_audit(record.task_id)
        if item.get("event") == "status_updated" and item.get("details", {}).get("to") == "failed"
    ][-1]
    assert finished["details"]["reason"] == "capability_internal_error"
    assert "executor-secret" not in json.dumps(finished, sort_keys=True)


def test_executor_plugin_wrappers_return_stable_error_codes(monkeypatch) -> None:
    from francis.agent import executor
    from francis.api.routes import plugins as plugin_routes

    def fail_list_plugins(*_args, **_kwargs):
        raise RuntimeError("plugin route traceback token=plugin-secret")

    monkeypatch.setattr(plugin_routes, "list_plugins", fail_list_plugins)

    result = executor._cap_plugin_list({}, "Sanitize plugin wrapper failure")

    assert result["ok"] is False
    assert result["error"] == "plugin_runtime_error"
    result_text = json.dumps(result, sort_keys=True)
    assert "plugin-secret" not in result_text
    assert "RuntimeError" not in result_text
    assert "traceback" not in result_text.lower()
