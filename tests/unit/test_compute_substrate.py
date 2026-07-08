from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from francis.compute_substrate import (
    COMPUTE_RECEIPT_KIND,
    LIVE_LEARNING_EVENT_KIND,
    ApprovalConsumptionResult,
    ApprovalGrant,
    ApprovalScope,
    CapabilityReceipt,
    CapabilityReceiptAdapter,
    InMemoryApprovalStore,
    LocalJsonComputeReceiptStore,
    ResourceBudget,
    SafeLocalBackend,
    SubstrateGovernor,
    TaskEnvelope,
    WorkerDescriptor,
    WorkerRegistry,
    create_task_envelope,
    execute_registered_function,
)


def test_task_envelope_creation_carries_budget_and_payload() -> None:
    budget = ResourceBudget(
        max_runtime_ms=500,
        max_memory_mb=64,
        cpu_weight=10,
        priority="low",
        max_compute_units=50,
    )

    envelope = create_task_envelope(
        "echo",
        task_id="task-echo-contract",
        payload={"message": "hello"},
        budget=budget,
        actor="codex.local",
        trace_id="trace-compute-substrate",
    )

    assert envelope.task_id == "task-echo-contract"
    assert envelope.function_name == "echo"
    assert envelope.payload == {"message": "hello"}
    assert envelope.actor == "codex.local"
    assert envelope.trace_id == "trace-compute-substrate"
    assert envelope.budget.max_runtime_ms == 500
    assert envelope.budget.filesystem_scope == ("none",)
    assert envelope.to_dict()["budget"]["allow_network"] is False


def test_worker_registry_registers_safe_local_backend() -> None:
    registry = WorkerRegistry()
    backend = SafeLocalBackend(worker_id="safe-local-test")

    registry.register(backend)

    descriptors = registry.descriptors()
    assert len(descriptors) == 1
    assert descriptors[0].worker_id == "safe-local-test"
    assert descriptors[0].backend_name == "safe_local"
    assert descriptors[0].starts_processes is False
    assert descriptors[0].allow_network is False
    assert descriptors[0].filesystem_access == "none"
    assert set(descriptors[0].capabilities) == {
        "compute_test",
        "echo",
        "health_check",
        "summarize_status",
    }
    assert registry.backend_for("echo") is backend


def test_worker_registry_rejects_duplicate_worker_ids() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend(worker_id="safe-local-duplicate"))

    with pytest.raises(ValueError, match="worker_already_registered"):
        registry.register(SafeLocalBackend(worker_id="safe-local-duplicate"))


class _DisabledBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="disabled-worker",
            backend_name="disabled_test",
            capabilities=("echo",),
            enabled=False,
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        raise AssertionError("disabled worker should not execute")


def test_governor_rejects_disabled_workers_before_backend_execution() -> None:
    registry = WorkerRegistry()
    registry.register(_DisabledBackend())
    result = SubstrateGovernor().execute(create_task_envelope("echo"), registry)

    assert result.ok is False
    assert result.status == "denied"
    assert result.error == "worker_enabled"
    assert result.output["decision"]["checks"]["worker_enabled"] is False
    assert result.receipt.governance["worker_enabled"] is False


def test_budget_validation_rejects_over_budget_values() -> None:
    governor = SubstrateGovernor()
    budget = ResourceBudget(
        max_runtime_ms=6000,
        max_memory_mb=64,
        cpu_weight=10,
        priority="normal",
    )

    decision = governor.validate_budget(budget)

    assert decision.allowed is False
    assert decision.reason == "runtime_within_limit"
    assert decision.checks["runtime_within_limit"] is False
    assert decision.governance["resource_enforcement"] == "validated_boundaries_not_os_cgroups"


def test_governor_rejects_unauthorized_scope_gpu_network_and_compute_overrun() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor()

    network_envelope = create_task_envelope(
        "echo",
        payload={"message": "blocked"},
        budget=ResourceBudget(allow_network=True),
    )
    network_result = governor.execute(network_envelope, registry)

    assert network_result.ok is False
    assert network_result.status == "denied"
    assert network_result.error == "network_allowed"
    assert network_result.receipt.kind == COMPUTE_RECEIPT_KIND
    assert network_result.receipt.persisted is False
    assert network_result.receipt.governance["unrestricted_network"] is False
    assert network_result.receipt.governance["network_requested"] is True
    assert network_result.receipt.governance["uses_network"] is False

    gpu_result = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(allow_gpu=True)),
        registry,
    )
    assert gpu_result.ok is False
    assert gpu_result.status == "denied"
    assert gpu_result.error == "gpu_allowed"

    filesystem_result = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(filesystem_scope=("D:/Francis",))),
        registry,
    )
    assert filesystem_result.ok is False
    assert filesystem_result.status == "denied"
    assert filesystem_result.error == "filesystem_scope_allowed"

    compute_envelope = create_task_envelope(
        "compute_test",
        payload={"iterations": 11},
        budget=ResourceBudget(max_compute_units=10),
    )
    compute_result = governor.execute(compute_envelope, registry)

    assert compute_result.ok is False
    assert compute_result.status == "denied"
    assert compute_result.error == "payload_compute_units_within_budget"
    assert compute_result.output["decision"]["checks"]["payload_compute_units_within_budget"] is False


def test_governor_rejects_unknown_capability_and_approval_required_tasks() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor()

    unknown = governor.execute(create_task_envelope("shell"), registry)
    assert unknown.ok is False
    assert unknown.status == "denied"
    assert unknown.error == "unregistered_function"
    assert unknown.receipt.persisted is False

    approval_required = governor.execute(
        create_task_envelope("echo", budget=ResourceBudget(approval_required=True)),
        registry,
    )
    assert approval_required.ok is False
    assert approval_required.status == "denied"
    assert approval_required.error == "missing_approval"
    assert approval_required.output["approval"]["reason"] == "missing_approval"
    assert approval_required.receipt.governance["approval_required"] is True
    assert approval_required.receipt.governance["approval_satisfied"] is False
    assert approval_required.receipt.governance["approval_consumed"] is False


def _approval_grant(
    *,
    approval_id: str = "approval-echo",
    task_id: str = "task-approved",
    capability: str = "echo",
    worker_id: str = "safe-local-1",
    max_risk_level: str = "low",
    max_runtime_ms: int | None = 1000,
    expires_at_ms: int | None = None,
    revoked: bool = False,
    approval_note: str = "",
    single_use: bool = True,
) -> ApprovalGrant:
    return ApprovalGrant(
        approval_id=approval_id,
        scope=ApprovalScope(
            task_id=task_id,
            allowed_capabilities=(capability,),
            allowed_worker_ids=(worker_id,),
            max_risk_level=max_risk_level,
            max_runtime_ms=max_runtime_ms,
            max_memory_mb=128,
            max_cpu_weight=25,
            max_compute_units=1000,
        ),
        approved_by="operator",
        reason="bounded compute approval",
        approval_note=approval_note,
        expires_at_ms=expires_at_ms,
        revoked=revoked,
        single_use=single_use,
    )


def test_approval_required_false_preserves_existing_execution_behavior() -> None:
    result = execute_registered_function(create_task_envelope("echo", payload={"message": "no approval needed"}))

    assert result.ok is True
    assert result.status == "success"
    assert result.output == {"ok": True, "function": "echo", "message": "no approval needed"}
    assert result.receipt.governance["approval_required"] is False
    assert result.receipt.governance["approval_decision"] == "not_required"
    assert result.receipt.governance["approval_consumption"] == "not_required"


def test_approval_required_with_valid_approval_executes_and_links_receipt() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant()])
    governor = SubstrateGovernor(approval_store=approval_store)

    result = governor.execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-echo",
            payload={"message": "approved"},
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.output == {"ok": True, "function": "echo", "message": "approved"}
    assert result.receipt.approval_id == "approval-echo"
    assert result.receipt.governance["approval_required"] is True
    assert result.receipt.governance["approval_satisfied"] is True
    assert result.receipt.governance["approval_consumed"] is True
    assert result.receipt.governance["approval_consumption"] == "consumed"
    assert result.receipt.governance["approval_scope_summary"]["task_id_bound"] is True
    consumed = approval_store.get("approval-echo")
    assert consumed is not None
    assert consumed.consumed_by_task_id == "task-approved"
    assert consumed.consumed_at_ms > 0


def test_single_use_approval_cannot_be_reused() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant()])
    governor = SubstrateGovernor(approval_store=approval_store)
    envelope = create_task_envelope(
        "echo",
        task_id="task-approved",
        approval_id="approval-echo",
        budget=ResourceBudget(approval_required=True),
    )

    first = governor.execute(envelope, registry)
    second = governor.execute(envelope, registry)

    assert first.ok is True
    assert second.ok is False
    assert second.status == "denied"
    assert second.error == "already_consumed_approval"
    assert second.receipt.governance["approval_consumed"] is False


def test_reusable_approval_is_scoped_and_not_marked_consumed() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(single_use=False)])
    governor = SubstrateGovernor(approval_store=approval_store)
    envelope = create_task_envelope(
        "echo",
        task_id="task-approved",
        approval_id="approval-echo",
        budget=ResourceBudget(approval_required=True),
    )

    first = governor.execute(envelope, registry)
    second = governor.execute(envelope, registry)

    assert first.ok is True
    assert second.ok is True
    assert first.receipt.governance["approval_consumption"] == "satisfied_reusable"
    assert first.receipt.governance["approval_consumed"] is False
    reusable = approval_store.get("approval-echo")
    assert reusable is not None
    assert reusable.consumed_at_ms == 0


def test_expired_and_revoked_approvals_fail_closed() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())

    expired = SubstrateGovernor(
        approval_store=InMemoryApprovalStore([_approval_grant(approval_id="approval-expired", expires_at_ms=1)])
    ).execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-expired",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )
    assert expired.ok is False
    assert expired.error == "expired_approval"

    revoked = SubstrateGovernor(
        approval_store=InMemoryApprovalStore([_approval_grant(approval_id="approval-revoked", revoked=True)])
    ).execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-revoked",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )
    assert revoked.ok is False
    assert revoked.error == "revoked_approval"


@pytest.mark.parametrize(
    ("grant", "envelope", "expected_error"),
    [
        (
            ApprovalGrant(
                approval_id="approval-echo",
                scope=ApprovalScope(task_id="task-approved", allowed_worker_ids=("safe-local-1",)),
            ),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                budget=ResourceBudget(approval_required=True),
            ),
            "approval_scope_missing_capability",
        ),
        (
            _approval_grant(task_id="other-task"),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                budget=ResourceBudget(approval_required=True),
            ),
            "task_id_mismatch",
        ),
        (
            _approval_grant(capability="compute_test"),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                budget=ResourceBudget(approval_required=True),
            ),
            "capability_mismatch",
        ),
        (
            _approval_grant(worker_id="other-worker"),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                budget=ResourceBudget(approval_required=True),
            ),
            "worker_mismatch",
        ),
        (
            _approval_grant(max_risk_level="low"),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                payload={"risk_level": "high"},
                budget=ResourceBudget(approval_required=True),
            ),
            "risk_exceeds_approval",
        ),
        (
            _approval_grant(max_runtime_ms=500),
            create_task_envelope(
                "echo",
                task_id="task-approved",
                approval_id="approval-echo",
                budget=ResourceBudget(approval_required=True, max_runtime_ms=1000),
            ),
            "resource_budget_exceeds_approval",
        ),
    ],
)
def test_approval_scope_mismatches_are_denied(
    grant: ApprovalGrant,
    envelope: TaskEnvelope,
    expected_error: str,
) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    result = SubstrateGovernor(approval_store=InMemoryApprovalStore([grant])).execute(envelope, registry)

    assert result.ok is False
    assert result.status == "denied"
    assert result.error == expected_error
    assert result.receipt.governance["approval_satisfied"] is False
    assert result.receipt.governance["approval_denial_reason"] == expected_error


class _ExplodingBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="safe-local-1",
            backend_name="approval_denial_test",
            capabilities=("echo",),
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        raise AssertionError("backend should not execute when approval is denied")


def test_backend_is_not_called_when_approval_is_denied() -> None:
    registry = WorkerRegistry()
    registry.register(_ExplodingBackend())
    result = SubstrateGovernor().execute(
        create_task_envelope(
            "echo",
            task_id="task-denied-before-backend",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    assert result.ok is False
    assert result.error == "missing_approval"


class _FailingAfterApprovalBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="safe-local-1",
            backend_name="approval_failure_test",
            capabilities=("echo",),
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        raise RuntimeError("backend failed after approval")


def test_execution_failure_after_valid_approval_keeps_approval_consumed() -> None:
    registry = WorkerRegistry()
    registry.register(_FailingAfterApprovalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="task-backend-fails")])

    result = SubstrateGovernor(approval_store=approval_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-backend-fails",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    consumed = approval_store.get("approval-echo")
    assert result.ok is False
    assert result.status == "error"
    assert result.error == "RuntimeError: backend failed after approval"
    assert consumed is not None
    assert consumed.consumed_by_task_id == "task-backend-fails"
    assert consumed.consumed_at_ms > 0
    assert result.receipt.governance["approval_satisfied"] is True
    assert result.receipt.governance["approval_consumed"] is True
    assert result.receipt.governance["approval_consumption"] == "consumed"


def test_durable_receipt_records_approval_summary_without_raw_approval_note(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    receipt_store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    approval_store = InMemoryApprovalStore(
        [_approval_grant(approval_note="approval-secret-note", approval_id="approval-durable")]
    )
    governor = SubstrateGovernor(receipt_store=receipt_store, approval_store=approval_store)

    result = governor.execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-durable",
            payload={"message": "approved durable"},
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    assert result.ok is True
    assert result.receipt.persisted is True
    assert result.receipt.governance["approval_required"] is True
    assert result.receipt.governance["approval_satisfied"] is True
    assert result.receipt.governance["approval_consumed"] is True
    assert result.live_learning_event.persisted is False
    receipt_text = Path(result.receipt.receipt_path).read_text(encoding="utf-8")
    assert "approval-durable" in receipt_text
    assert "approval-secret-note" not in receipt_text
    assert "approved durable" not in receipt_text
    assert receipt_store.read_receipt(result.receipt.receipt_id) == result.receipt


class _FailingApprovalStore:
    def consume(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        raise OSError("approval store unavailable")

    def get(self, approval_id: str) -> ApprovalGrant | None:
        return None


def test_failed_approval_consumption_does_not_fake_success() -> None:
    registry = WorkerRegistry()
    registry.register(_ExplodingBackend())
    result = SubstrateGovernor(approval_store=_FailingApprovalStore()).execute(
        create_task_envelope(
            "echo",
            task_id="task-approval-fails",
            approval_id="approval-fails",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    assert result.ok is False
    assert result.status == "denied"
    assert result.error == "approval_cannot_be_consumed"
    assert result.receipt.governance["approval_satisfied"] is False
    assert result.receipt.governance["approval_consumed"] is False


def test_safe_local_backend_executes_registered_function_only() -> None:
    result = execute_registered_function(
        create_task_envelope(
            "compute_test",
            payload={"iterations": 5},
            budget=ResourceBudget(max_runtime_ms=1000, max_compute_units=5),
        )
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.backend_name == "safe_local"
    assert result.function_name == "compute_test"
    assert result.output == {
        "ok": True,
        "function": "compute_test",
        "iterations": 5,
        "checksum": 30,
    }
    assert result.elapsed_ms >= 0
    assert result.receipt.status == "success"


def test_execution_result_contains_receipt_and_live_learning_event() -> None:
    envelope = TaskEnvelope(
        task_id="task-live-learning",
        function_name="echo",
        payload={"message": "event"},
    )

    result = execute_registered_function(envelope)

    assert result.ok is True
    assert result.receipt.kind == COMPUTE_RECEIPT_KIND
    assert result.receipt.receipt_id.startswith("compute_capability_")
    assert result.receipt.task_id == "task-live-learning"
    assert result.receipt.function_name == "echo"
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "in_memory_only"
    assert result.receipt.governance["os_level_cpu_memory_enforcement"] is False
    assert result.receipt.governance["long_term_memory_persistence"] is False

    event = result.live_learning_event
    assert event.kind == LIVE_LEARNING_EVENT_KIND
    assert event.event_id.startswith("compute_learning_")
    assert event.task_id == "task-live-learning"
    assert event.result_status == "success"
    assert event.persistence_requested is False
    assert event.persisted is False
    assert event.persistence_follow_up == "requires_governance_review_before_long_term_memory_write"


def test_receipt_adapter_creates_non_persisted_capability_receipt() -> None:
    envelope = create_task_envelope("echo", task_id="task-receipt")
    descriptor = SafeLocalBackend(worker_id="safe-local-receipt").descriptor

    receipt = CapabilityReceiptAdapter().create(
        envelope=envelope,
        descriptor=descriptor,
        status="success",
        reason="executed_registered_function",
    )

    assert receipt.kind == COMPUTE_RECEIPT_KIND
    assert receipt.receipt_id.startswith("compute_capability_")
    assert receipt.task_id == "task-receipt"
    assert receipt.worker_id == "safe-local-receipt"
    assert receipt.persisted is False
    assert receipt.receipt_path == ""
    assert receipt.receipt_error == ""
    assert receipt.governance["registered_function_only"] is True
    assert receipt.governance["arbitrary_subprocess"] is False
    assert receipt.governance["shell"] is False
    assert receipt.governance["background_daemon"] is False


def test_local_json_compute_receipt_store_writes_and_reads_receipt(tmp_path: Path) -> None:
    receipt_root = tmp_path / "compute-receipts"
    store = LocalJsonComputeReceiptStore(receipt_root)
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope(
            "echo",
            task_id="task-durable-receipt",
            payload={"message": "raw payload should not be persisted"},
            trace_id="trace-durable-receipt",
        ),
        descriptor=SafeLocalBackend(worker_id="safe-local-durable").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    assert receipt.persisted is False
    assert receipt.receipt_path == ""

    persisted = store.write_receipt(receipt)

    assert persisted.persisted is True
    assert persisted.receipt_path
    receipt_path = Path(persisted.receipt_path)
    assert receipt_path.exists()
    assert receipt_path.parent == receipt_root
    assert persisted.governance["receipt_persistence"] == "persisted_local_json"
    assert persisted.governance["durable_compute_receipt"] is True
    assert persisted.governance["approval_consumption"] == "not_required"
    assert persisted.governance["long_term_memory_persistence"] is False

    payload = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert payload["receipt"]["receipt_id"] == persisted.receipt_id
    assert payload["receipt"]["trace_id"] == "trace-durable-receipt"
    assert payload["governance"]["does_not_persist_task_payload"] is True
    assert payload["governance"]["does_not_persist_task_output"] is True
    receipt_text = json.dumps(payload, sort_keys=True)
    assert "raw payload should not be persisted" not in receipt_text
    assert "payload" not in payload["receipt"]

    readback = store.read_receipt(persisted.receipt_id)

    assert readback == persisted

    filesystem_scope_receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope(
            "echo",
            task_id="task-filesystem-scope-summary",
            budget=ResourceBudget(filesystem_scope=("C:/secret/private",)),
        ),
        descriptor=SafeLocalBackend(worker_id="safe-local-filesystem-summary").descriptor,
        status="denied",
        reason="filesystem_scope_allowed",
    )
    filesystem_scope_persisted = store.write_receipt(filesystem_scope_receipt)
    assert filesystem_scope_persisted.budget["filesystem_scope"] == ["non_default_scope_requested"]
    assert "C:/secret/private" not in Path(filesystem_scope_persisted.receipt_path).read_text(encoding="utf-8")


def test_local_json_compute_receipt_store_rejects_unsafe_receipt_ids(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-unsafe-receipt"),
        descriptor=SafeLocalBackend(worker_id="safe-local-unsafe").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.write_receipt(replace(receipt, receipt_id="../escape"))

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.read_receipt("..\\escape")


@pytest.mark.parametrize(
    "receipt_id",
    [
        "../escape",
        "..\\escape",
        "nested/escape",
        "nested\\escape",
        "/absolute/path",
        "\\absolute\\path",
        "C:/absolute/path",
        "C:\\absolute\\path",
        "receipt.with.dot",
        "receipt:with:colon",
        "receipt\u2215with\u2215unicode-separator",
        "",
    ],
)
def test_local_json_compute_receipt_store_rejects_path_like_receipt_ids(
    tmp_path: Path,
    receipt_id: str,
) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-path-like-receipt"),
        descriptor=SafeLocalBackend(worker_id="safe-local-path-like").descriptor,
        status="success",
        reason="executed_registered_function",
    )

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.write_receipt(replace(receipt, receipt_id=receipt_id))

    with pytest.raises(ValueError, match="unsafe_receipt_id"):
        store.read_receipt(receipt_id)


def test_local_json_compute_receipt_store_accepts_safe_receipt_id(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    receipt = CapabilityReceiptAdapter().create(
        envelope=create_task_envelope("echo", task_id="task-safe-receipt-id"),
        descriptor=SafeLocalBackend(worker_id="safe-local-safe-id").descriptor,
        status="success",
        reason="executed_registered_function",
    )
    safe_receipt = replace(receipt, receipt_id="compute_capability-safe_ID_123")

    persisted = store.write_receipt(safe_receipt)

    assert persisted.receipt_id == "compute_capability-safe_ID_123"
    assert Path(persisted.receipt_path).parent == store.receipt_root
    assert store.read_receipt("compute_capability-safe_ID_123") == persisted


class _FailingReceiptStore:
    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        raise OSError("receipt store unavailable")

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None:
        return None

    def describe(self) -> dict[str, object]:
        return {"kind": "test.failing_compute_receipt_store"}


def test_failed_receipt_persistence_does_not_fake_success() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    governor = SubstrateGovernor(receipt_store=_FailingReceiptStore())

    result = governor.execute(create_task_envelope("echo", payload={"message": "persist me"}), registry)

    assert result.ok is False
    assert result.status == "receipt_persistence_failed"
    assert result.error.startswith("OSError: receipt store unavailable")
    assert result.output == {"ok": True, "function": "echo", "message": "persist me"}
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.receipt_error.startswith("OSError: receipt store unavailable")
    assert result.receipt.governance["receipt_persistence"] == "persistence_failed"
    assert result.receipt.governance["receipt_store_configured"] is True
    assert result.live_learning_event.persisted is False
    assert result.live_learning_event.result_status == "receipt_persistence_failed"


def test_governor_without_receipt_store_preserves_in_memory_behavior() -> None:
    result = execute_registered_function(create_task_envelope("echo", payload={"message": "memory only"}))

    assert result.ok is True
    assert result.status == "success"
    assert result.receipt.persisted is False
    assert result.receipt.receipt_path == ""
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "in_memory_only"
    assert result.receipt.governance["receipt_store_configured"] is False


def test_governor_with_receipt_store_persists_compute_receipt_and_not_learning(
    tmp_path: Path,
) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    governor = SubstrateGovernor(receipt_store=store)

    result = governor.execute(
        create_task_envelope(
            "compute_test",
            payload={"iterations": 4, "secret": "secret-token-should-not-persist"},
            budget=ResourceBudget(max_compute_units=4),
        ),
        registry,
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.receipt.persisted is True
    assert result.receipt.receipt_path
    assert result.receipt.receipt_error == ""
    assert result.receipt.governance["receipt_persistence"] == "persisted_local_json"
    assert result.receipt.governance["arbitrary_subprocess"] is False
    assert result.receipt.governance["shell"] is False
    assert result.receipt.governance["background_daemon"] is False
    assert result.receipt.governance["unrestricted_filesystem_write"] is False
    assert result.receipt.governance["unrestricted_network"] is False
    assert result.receipt.governance["uses_network"] is False
    assert result.receipt.governance["uses_gpu"] is False
    assert result.receipt.governance["writes_memory"] is False
    assert result.receipt.governance["long_term_memory_persistence"] is False
    assert result.receipt.governance["approval_consumption"] == "not_required"
    assert result.receipt.governance["os_level_cpu_memory_enforcement"] is False
    assert result.live_learning_event.persistence_requested is False
    assert result.live_learning_event.persisted is False

    receipt_text = Path(result.receipt.receipt_path).read_text(encoding="utf-8")
    assert "secret-token-should-not-persist" not in receipt_text
    assert "iterations" not in receipt_text
    assert "checksum" not in receipt_text
    assert store.read_receipt(result.receipt.receipt_id) == result.receipt
