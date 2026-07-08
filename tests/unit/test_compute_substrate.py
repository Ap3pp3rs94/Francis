from __future__ import annotations

import inspect
import json
import time
from dataclasses import replace
from pathlib import Path

import pytest

import francis.compute_substrate_approvals as approval_module
from francis.compute_substrate import (
    COMPUTE_RECEIPT_KIND,
    LIVE_LEARNING_EVENT_KIND,
    ApprovalConsumptionResult,
    ApprovalGrant,
    ApprovalScope,
    CancellationToken,
    CapabilityReceipt,
    CapabilityReceiptAdapter,
    ComputeSubmission,
    ComputeSubmissionResult,
    ComputeSubstrateService,
    ComputeTaskStatus,
    ExecutionContext,
    ExecutionDeadline,
    ExecutionResult,
    InMemoryApprovalStore,
    InMemoryComputeStatusStore,
    LocalJsonComputeApprovalStore,
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
        "cooperative_delay_test",
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


def test_local_json_compute_approval_store_writes_and_reads_approval(tmp_path: Path) -> None:
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    grant = _approval_grant(
        approval_id="approval_SAFE-123",
        approval_note="bounded approval note",
        single_use=False,
    )

    stored = store.add(grant)
    readback = store.get("approval_SAFE-123")

    assert stored == grant
    assert readback == grant
    assert store.describe()["durable"] is True
    assert store.describe()["cross_process_atomic_reservation"] is False
    assert (tmp_path / "compute-approvals" / "approval_SAFE-123.json").exists()


@pytest.mark.parametrize(
    "approval_id",
    [
        "../escape",
        "..\\escape",
        "nested/escape",
        "nested\\escape",
        "/absolute/path",
        "\\absolute\\path",
        "C:/absolute/path",
        "C:\\absolute\\path",
        "approval.with.dot",
        "approval:with:colon",
        "approval\u2215with\u2215unicode-separator",
        "",
        "   ",
    ],
)
def test_local_json_compute_approval_store_rejects_unsafe_approval_ids(
    tmp_path: Path,
    approval_id: str,
) -> None:
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")

    with pytest.raises(ValueError, match="unsafe_approval_id"):
        store.get(approval_id)

    with pytest.raises(ValueError, match="unsafe_approval_id"):
        store.add(_approval_grant(approval_id=approval_id))

    assert not (tmp_path / "compute-approvals").exists()


def test_unsafe_approval_ids_are_not_silently_normalized_into_persisted_aliases(tmp_path: Path) -> None:
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")

    for approval_id in ("../escape", "..\\escape", "C:/absolute/path", "approval:with:colon"):
        with pytest.raises(ValueError, match="unsafe_approval_id"):
            store.add(_approval_grant(approval_id=approval_id))

    assert not (tmp_path / "compute-approvals").exists()
    assert store.get("approval_escape") is None
    assert store.get("approval-with-colon") is None


def test_unsafe_envelope_approval_id_denies_without_persisted_receipt_alias(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    receipt_store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")

    result = SubstrateGovernor(approval_store=approval_store, receipt_store=receipt_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-unsafe-approval-id",
            approval_id="../escape",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    receipt_text = Path(result.receipt.receipt_path).read_text(encoding="utf-8")
    assert result.ok is False
    assert result.status == "denied"
    assert result.error == "unsafe_approval_id"
    assert result.receipt.approval_id == ""
    assert result.receipt.governance["approval_id"] == ""
    assert result.receipt.governance["approval_decision"] == "unsafe_approval_id"
    assert result.receipt.governance["approval_persistence"] == "approval_id_rejected_before_read"
    assert result.receipt.governance["approval_consumed"] is False
    assert "../escape" not in receipt_text
    assert "..\\escape" not in receipt_text
    assert "approval_escape" not in receipt_text


def test_local_json_compute_approval_store_consumes_single_use_once_and_persists_readback(
    tmp_path: Path,
) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    store.add(_approval_grant(approval_id="approval-durable-once"))
    envelope = create_task_envelope(
        "echo",
        task_id="task-approved",
        approval_id="approval-durable-once",
        budget=ResourceBudget(approval_required=True),
    )
    backend = registry.backend_for("echo")
    assert backend is not None

    first = store.consume(envelope, backend.descriptor)
    second = store.consume(envelope, backend.descriptor)
    consumed = store.get("approval-durable-once")

    assert first.allowed is True
    assert first.consumed is True
    assert first.evidence["durable_approval_persistence"] is True
    assert second.allowed is False
    assert second.reason == "already_consumed_approval"
    assert consumed is not None
    assert consumed.consumed_at_ms > 0
    assert consumed.consumed_by_task_id == "task-approved"


def test_local_json_compute_approval_store_redacts_raw_notes_and_does_not_store_task_content(
    tmp_path: Path,
) -> None:
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    store.add(
        _approval_grant(
            approval_id="approval-redacted",
            approval_note="token=approval-secret-token-123456",
        )
    )

    approval_text = (tmp_path / "compute-approvals" / "approval-redacted.json").read_text(encoding="utf-8")

    assert "approval-secret-token-123456" not in approval_text
    assert "[REDACTED:secret]" in approval_text
    assert "raw task payload" not in approval_text
    assert "raw execution output" not in approval_text
    assert "raw model prompt" not in approval_text
    assert "C:/secret/private" not in approval_text
    assert '"does_not_persist_raw_approval_note": true' in approval_text


def test_failed_local_json_compute_approval_persistence_does_not_fake_stored_success(
    tmp_path: Path,
) -> None:
    blocked_root = tmp_path / "approval-root-is-file"
    blocked_root.write_text("not a directory", encoding="utf-8")
    store = LocalJsonComputeApprovalStore(blocked_root)

    with pytest.raises(OSError):
        store.add(_approval_grant(approval_id="approval-store-fails"))

    assert store.get("approval-store-fails") is None


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


def test_valid_durable_approval_executes_through_governor_and_service(tmp_path: Path) -> None:
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    store.add(_approval_grant(approval_id="approval-governor", task_id="task-durable-governor"))
    service_store = LocalJsonComputeApprovalStore(tmp_path / "service-approvals")
    service_store.add(_approval_grant(approval_id="approval-service", task_id="task-durable-service"))
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())

    governor_result = SubstrateGovernor(approval_store=store).execute(
        create_task_envelope(
            "echo",
            task_id="task-durable-governor",
            approval_id="approval-governor",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )
    service_result = ComputeSubstrateService(approval_store=service_store).submit(
        create_task_envelope(
            "echo",
            task_id="task-durable-service",
            approval_id="approval-service",
            budget=ResourceBudget(approval_required=True),
        )
    )

    governor_grant = store.get("approval-governor")
    service_grant = service_store.get("approval-service")
    assert governor_result.ok is True
    assert governor_result.receipt.governance["approval_persistence"] == "persisted_local_json"
    assert governor_result.receipt.governance["durable_approval_persistence"] is True
    assert governor_grant is not None
    assert governor_grant.consumed_by_task_id == "task-durable-governor"
    assert service_result.ok is True
    assert service_result.status == ComputeTaskStatus.SUCCEEDED
    assert service_result.record.approval_consumed is True
    assert service_grant is not None
    assert service_grant.consumed_by_task_id == "task-durable-service"


def test_durable_approval_denials_match_existing_scope_rules(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    expired_store = LocalJsonComputeApprovalStore(tmp_path / "expired-approvals")
    expired_store.add(_approval_grant(approval_id="approval-expired", expires_at_ms=1))
    revoked_store = LocalJsonComputeApprovalStore(tmp_path / "revoked-approvals")
    revoked_store.add(_approval_grant(approval_id="approval-revoked", revoked=True))
    wrong_scope_store = LocalJsonComputeApprovalStore(tmp_path / "scope-approvals")
    wrong_scope_store.add(_approval_grant(approval_id="approval-scope", capability="compute_test"))

    expired = SubstrateGovernor(approval_store=expired_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-expired",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )
    revoked = SubstrateGovernor(approval_store=revoked_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-revoked",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )
    wrong_scope = SubstrateGovernor(approval_store=wrong_scope_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-approved",
            approval_id="approval-scope",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    assert expired.error == "expired_approval"
    assert revoked.error == "revoked_approval"
    assert wrong_scope.error == "capability_mismatch"
    assert expired.receipt.governance["durable_approval_persistence"] is True
    assert revoked.receipt.governance["approval_consumed"] is False
    assert wrong_scope.receipt.governance["approval_consumed"] is False


class _FailingConsumeApprovalStore(LocalJsonComputeApprovalStore):
    def __init__(self, approval_root: Path) -> None:
        super().__init__(approval_root)
        self.fail_writes = False

    def _write_grant(self, grant: ApprovalGrant) -> None:
        if self.fail_writes:
            raise OSError("approval write unavailable")
        super()._write_grant(grant)


def test_failed_durable_approval_consumption_does_not_call_backend(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(_ExplodingBackend())
    store = _FailingConsumeApprovalStore(tmp_path / "compute-approvals")
    store.add(_approval_grant(approval_id="approval-consume-fails", task_id="task-consume-fails"))
    store.fail_writes = True

    result = SubstrateGovernor(approval_store=store).execute(
        create_task_envelope(
            "echo",
            task_id="task-consume-fails",
            approval_id="approval-consume-fails",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    grant = store.get("approval-consume-fails")
    assert result.ok is False
    assert result.status == "denied"
    assert result.error == "approval_persistence_failed"
    assert result.receipt.governance["approval_consumed"] is False
    assert grant is not None
    assert grant.consumed_at_ms == 0


def test_durable_approval_not_consumed_on_pre_execution_cancel_or_deadline(tmp_path: Path) -> None:
    cancel_store = LocalJsonComputeApprovalStore(tmp_path / "cancel-approvals")
    cancel_store.add(_approval_grant(approval_id="approval-cancel", task_id="task-cancel-durable"))
    deadline_store = LocalJsonComputeApprovalStore(tmp_path / "deadline-approvals")
    deadline_store.add(_approval_grant(approval_id="approval-deadline", task_id="task-deadline-durable"))

    cancelled = ComputeSubstrateService(approval_store=cancel_store).submit(
        create_task_envelope(
            "echo",
            task_id="task-cancel-durable",
            approval_id="approval-cancel",
            budget=ResourceBudget(approval_required=True),
        ),
        context=ExecutionContext(
            cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
        ),
    )
    timed_out = ComputeSubstrateService(approval_store=deadline_store).submit(
        create_task_envelope(
            "echo",
            task_id="task-deadline-durable",
            approval_id="approval-deadline",
            budget=ResourceBudget(approval_required=True),
        ),
        context=ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired")),
    )

    cancel_grant = cancel_store.get("approval-cancel")
    deadline_grant = deadline_store.get("approval-deadline")
    assert cancelled.status == ComputeTaskStatus.CANCELLED
    assert timed_out.status == ComputeTaskStatus.TIMED_OUT
    assert cancel_grant is not None
    assert deadline_grant is not None
    assert cancel_grant.consumed_at_ms == 0
    assert deadline_grant.consumed_at_ms == 0


def test_durable_approval_remains_consumed_when_execution_starts_then_fails(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(_FailingAfterApprovalBackend())
    store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    store.add(_approval_grant(approval_id="approval-started-fails", task_id="task-started-fails"))

    result = SubstrateGovernor(approval_store=store).execute(
        create_task_envelope(
            "echo",
            task_id="task-started-fails",
            approval_id="approval-started-fails",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    grant = store.get("approval-started-fails")
    assert result.status == "error"
    assert result.receipt.governance["execution_started"] is True
    assert result.receipt.governance["approval_consumed"] is True
    assert grant is not None
    assert grant.consumed_at_ms > 0
    assert grant.consumed_by_task_id == "task-started-fails"


def test_durable_compute_receipt_records_durable_approval_summary(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = LocalJsonComputeApprovalStore(tmp_path / "compute-approvals")
    approval_store.add(_approval_grant(approval_id="approval-receipt", task_id="task-approval-receipt"))
    receipt_store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")

    result = SubstrateGovernor(approval_store=approval_store, receipt_store=receipt_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-approval-receipt",
            approval_id="approval-receipt",
            payload={"message": "raw payload must not persist"},
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
    )

    receipt_text = Path(result.receipt.receipt_path).read_text(encoding="utf-8")
    assert result.ok is True
    assert result.receipt.persisted is True
    assert result.receipt.governance["approval_persistence"] == "persisted_local_json"
    assert result.receipt.governance["approval_store_type"] == "local_json_compute_approval_store"
    assert result.receipt.governance["approval_cross_process_atomic_reservation"] is False
    assert "raw payload must not persist" not in receipt_text
    assert receipt_store.read_receipt(result.receipt.receipt_id) == result.receipt


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
    def authorize(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        return ApprovalConsumptionResult(
            allowed=True,
            reason="approval_scope_valid",
            approval_id=envelope.approval_id,
            consumed=False,
            scope_summary={"allowed_capabilities": [envelope.function_name]},
        )

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


class _CountingBackend:
    def __init__(self) -> None:
        self.called = False

    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="counting-worker",
            backend_name="counting_test",
            capabilities=("echo",),
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        self.called = True
        return {"ok": True, "task_id": envelope.task_id}


def test_already_cancelled_context_denies_before_backend_execution() -> None:
    backend = _CountingBackend()
    registry = WorkerRegistry()
    registry.register(backend)
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = SubstrateGovernor().execute(create_task_envelope("echo"), registry, context=context)

    assert result.ok is False
    assert result.status == "cancelled"
    assert result.error == "operator_cancelled"
    assert backend.called is False
    assert result.receipt.governance["cancellation_requested"] is True
    assert result.receipt.governance["cancellation_reason"] == "operator_cancelled"
    assert result.receipt.governance["execution_started"] is False
    assert result.receipt.governance["execution_finished"] is False


def test_expired_deadline_denies_before_backend_execution() -> None:
    backend = _CountingBackend()
    registry = WorkerRegistry()
    registry.register(backend)
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = SubstrateGovernor().execute(create_task_envelope("echo"), registry, context=context)

    assert result.ok is False
    assert result.status == "timeout"
    assert result.error == "deadline_exceeded_pre_execution"
    assert backend.called is False
    assert result.receipt.governance["timed_out"] is True
    assert result.receipt.governance["timeout_stage"] == "pre_execution"
    assert result.receipt.governance["deadline_source"] == "test_expired"
    assert result.receipt.governance["execution_started"] is False


def test_approval_denial_precedes_cancelled_context() -> None:
    registry = WorkerRegistry()
    registry.register(_ExplodingBackend())
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = SubstrateGovernor().execute(
        create_task_envelope("echo", budget=ResourceBudget(approval_required=True)),
        registry,
        context=context,
    )

    assert result.status == "denied"
    assert result.error == "missing_approval"
    assert result.receipt.governance["approval_satisfied"] is False
    assert result.receipt.governance["approval_consumed"] is False
    assert result.receipt.governance["timeout_stage"] == "not_applicable"
    assert result.receipt.governance["execution_started"] is False


def test_approval_is_not_consumed_when_cancellation_blocks_before_execution() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="task-cancel-approved")])
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = SubstrateGovernor(approval_store=approval_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-cancel-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
        context=context,
    )

    grant = approval_store.get("approval-echo")
    assert result.status == "cancelled"
    assert grant is not None
    assert grant.consumed_at_ms == 0
    assert result.receipt.governance["approval_satisfied"] is True
    assert result.receipt.governance["approval_consumed"] is False
    assert result.receipt.governance["approval_consumption"] == "validated_not_consumed"
    assert result.receipt.governance["execution_started"] is False


def test_approval_is_not_consumed_when_expired_deadline_blocks_before_execution() -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="task-deadline-approved")])
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = SubstrateGovernor(approval_store=approval_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-deadline-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True),
        ),
        registry,
        context=context,
    )

    grant = approval_store.get("approval-echo")
    assert result.status == "timeout"
    assert result.error == "deadline_exceeded_pre_execution"
    assert grant is not None
    assert grant.consumed_at_ms == 0
    assert result.receipt.governance["approval_satisfied"] is True
    assert result.receipt.governance["approval_consumed"] is False
    assert result.receipt.governance["approval_consumption"] == "validated_not_consumed"
    assert result.receipt.governance["timeout_stage"] == "pre_execution"
    assert result.receipt.governance["execution_started"] is False


def test_cooperative_safe_local_backend_observes_deadline_during_execution() -> None:
    context = ExecutionContext(
        deadline=ExecutionDeadline(
            deadline_at_ms=int(time.time() * 1000) + 75,
            source="test_during_execution",
        )
    )

    result = execute_registered_function(
        create_task_envelope(
            "cooperative_delay_test",
            payload={"steps": 6, "delay_ms": 25},
            budget=ResourceBudget(max_runtime_ms=1000, max_compute_units=6),
        ),
        context=context,
    )

    assert result.ok is False
    assert result.status == "timeout"
    assert result.error == "deadline_exceeded_during_execution"
    assert result.output["interruption"]["os_level_preemption"] is False
    assert result.receipt.governance["timed_out"] is True
    assert result.receipt.governance["timeout_stage"] == "during_execution"
    assert result.receipt.governance["execution_started"] is True
    assert result.receipt.governance["execution_finished"] is True
    assert result.receipt.governance["os_level_preemption"] is False


class _SlowNonCooperativeBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="slow-worker",
            backend_name="slow_non_cooperative_test",
            capabilities=("echo",),
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        time.sleep(0.08)
        return {"ok": True, "function": envelope.function_name, "completed_late": True}


def test_post_execution_timeout_reports_overrun_without_claiming_preemption() -> None:
    registry = WorkerRegistry()
    registry.register(_SlowNonCooperativeBackend())

    result = SubstrateGovernor().execute(
        create_task_envelope("echo", budget=ResourceBudget(max_runtime_ms=50)),
        registry,
    )

    assert result.ok is False
    assert result.status == "timeout"
    assert result.output == {"ok": True, "function": "echo", "completed_late": True}
    assert result.error == "runtime_budget_elapsed_after_registered_function"
    assert result.receipt.governance["timed_out"] is True
    assert result.receipt.governance["timeout_stage"] == "post_execution"
    assert result.receipt.governance["execution_started"] is True
    assert result.receipt.governance["execution_finished"] is True
    assert result.receipt.governance["over_budget_runtime"] is True
    assert result.receipt.governance["os_level_preemption"] is False


def test_post_execution_expired_deadline_reports_timeout_without_budget_overrun() -> None:
    registry = WorkerRegistry()
    registry.register(_SlowNonCooperativeBackend())
    context = ExecutionContext(
        deadline=ExecutionDeadline(
            deadline_at_ms=int(time.time() * 1000) + 20,
            source="shorter_than_budget",
        )
    )

    result = SubstrateGovernor().execute(
        create_task_envelope("echo", budget=ResourceBudget(max_runtime_ms=1000)),
        registry,
        context=context,
    )

    assert result.ok is False
    assert result.status == "timeout"
    assert result.output == {"ok": True, "function": "echo", "completed_late": True}
    assert result.error == "deadline_elapsed_after_registered_function"
    assert result.receipt.governance["timed_out"] is True
    assert result.receipt.governance["timeout_stage"] == "post_execution"
    assert result.receipt.governance["deadline_expired"] is True
    assert result.receipt.governance["over_budget_runtime"] is False
    assert result.receipt.governance["os_level_preemption"] is False


def test_approval_remains_consumed_when_execution_starts_then_times_out() -> None:
    registry = WorkerRegistry()
    registry.register(_SlowNonCooperativeBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="task-timeout-approved", worker_id="slow-worker")])

    result = SubstrateGovernor(approval_store=approval_store).execute(
        create_task_envelope(
            "echo",
            task_id="task-timeout-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True, max_runtime_ms=50),
        ),
        registry,
    )

    grant = approval_store.get("approval-echo")
    assert result.status == "timeout"
    assert grant is not None
    assert grant.consumed_at_ms > 0
    assert result.receipt.governance["approval_consumed"] is True
    assert result.receipt.governance["timed_out"] is True
    assert result.receipt.governance["timeout_stage"] == "post_execution"


def test_durable_receipt_records_cancellation_timeout_summary(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = SubstrateGovernor(receipt_store=store).execute(
        create_task_envelope("echo", task_id="task-cancel-receipt"),
        registry,
        context=context,
    )

    assert result.status == "cancelled"
    assert result.receipt.persisted is True
    payload = json.loads(Path(result.receipt.receipt_path).read_text(encoding="utf-8"))
    governance = payload["receipt"]["governance"]
    assert governance["cancellation_requested"] is True
    assert governance["cancellation_reason"] == "operator_cancelled"
    assert governance["timed_out"] is False
    assert governance["timeout_stage"] == "not_applicable"
    assert governance["execution_started"] is False
    assert governance["os_level_preemption"] is False
    assert store.read_receipt(result.receipt.receipt_id) == result.receipt
    assert result.live_learning_event.persisted is False


def test_durable_receipt_records_expired_deadline_timeout_summary(tmp_path: Path) -> None:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = SubstrateGovernor(receipt_store=store).execute(
        create_task_envelope("echo", task_id="task-deadline-receipt"),
        registry,
        context=context,
    )

    assert result.status == "timeout"
    assert result.receipt.persisted is True
    payload = json.loads(Path(result.receipt.receipt_path).read_text(encoding="utf-8"))
    governance = payload["receipt"]["governance"]
    assert governance["cancellation_requested"] is False
    assert governance["deadline_source"] == "test_expired"
    assert governance["deadline_expired"] is True
    assert governance["timed_out"] is True
    assert governance["timeout_stage"] == "pre_execution"
    assert governance["execution_started"] is False
    assert governance["os_level_preemption"] is False
    assert store.read_receipt(result.receipt.receipt_id) == result.receipt
    assert result.live_learning_event.persisted is False


def test_public_facade_exports_cancellation_deadline_contracts() -> None:
    token = CancellationToken()
    deadline = ExecutionDeadline()
    context = ExecutionContext(cancellation_token=token, deadline=deadline)

    assert context.cancellation_token is token
    assert context.deadline is deadline
    assert context.to_summary()["cooperative_cancellation"] is True
    assert context.to_summary()["os_level_preemption"] is False


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


class _RecordingGovernor(SubstrateGovernor):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.execute_calls = 0

    def execute(
        self,
        envelope: TaskEnvelope,
        registry: WorkerRegistry,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        self.execute_calls += 1
        return super().execute(envelope, registry, context=context)


def test_compute_substrate_service_submits_task_through_governor() -> None:
    governor = _RecordingGovernor()
    service = ComputeSubstrateService(governor=governor)

    result = service.submit(
        ComputeSubmission(
            create_task_envelope(
                "echo",
                task_id="service-echo",
                trace_id="trace-service-echo",
                payload={"message": "service hello"},
            )
        )
    )

    assert isinstance(result, ComputeSubmissionResult)
    assert governor.execute_calls == 1
    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.task_id == "service-echo"
    assert result.correlation_id == "trace-service-echo"
    assert result.record.receipt_id == result.receipt.receipt_id
    assert result.record.receipt_persisted is False
    assert result.record.receipt_persistence_status == "in_memory_only"
    assert service.status_for_task("service-echo") == result.record
    assert service.status_for_correlation("trace-service-echo") == result.record


def test_compute_substrate_service_denies_approval_required_without_approval() -> None:
    service = ComputeSubstrateService()

    result = service.submit(
        create_task_envelope(
            "echo",
            task_id="service-approval-missing",
            budget=ResourceBudget(approval_required=True),
        )
    )

    assert result.ok is False
    assert result.status == ComputeTaskStatus.DENIED
    assert result.record.denial_reason == "missing_approval"
    assert result.record.approval_required is True
    assert result.record.approval_satisfied is False
    assert result.record.approval_consumed is False
    assert result.receipt.governance["approval_required"] is True
    assert result.receipt.governance["approval_consumed"] is False


def test_compute_substrate_service_executes_with_valid_scoped_approval() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="service-approved")])
    service = ComputeSubstrateService(approval_store=approval_store)

    result = service.submit(
        create_task_envelope(
            "echo",
            task_id="service-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True),
        )
    )

    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.record.approval_required is True
    assert result.record.approval_satisfied is True
    assert result.record.approval_consumed is True
    consumed = approval_store.get("approval-echo")
    assert consumed is not None
    assert consumed.consumed_by_task_id == "service-approved"


def test_compute_substrate_service_preserves_single_use_approval_behavior() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="service-single-use")])
    service = ComputeSubstrateService(approval_store=approval_store)
    envelope = create_task_envelope(
        "echo",
        task_id="service-single-use",
        approval_id="approval-echo",
        budget=ResourceBudget(approval_required=True),
    )

    first = service.submit(envelope)
    second = service.submit(envelope)

    assert first.status == ComputeTaskStatus.SUCCEEDED
    assert second.ok is False
    assert second.status == ComputeTaskStatus.DENIED
    assert second.record.denial_reason == "already_consumed_approval"
    assert second.record.approval_consumed is False


def test_compute_substrate_service_respects_pre_execution_cancellation() -> None:
    service = ComputeSubstrateService()
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = service.submit(
        create_task_envelope("echo", task_id="service-cancelled"),
        context=context,
    )

    assert result.ok is False
    assert result.status == ComputeTaskStatus.CANCELLED
    assert result.record.cancellation_requested is True
    assert result.record.cancellation_reason == "operator_cancelled"
    assert result.record.execution_started is False


def test_compute_substrate_service_respects_expired_deadline() -> None:
    service = ComputeSubstrateService()
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = service.submit(
        create_task_envelope("echo", task_id="service-timeout"),
        context=context,
    )

    assert result.ok is False
    assert result.status == ComputeTaskStatus.TIMED_OUT
    assert result.record.timed_out is True
    assert result.record.timeout_stage == "pre_execution"
    assert result.record.execution_started is False


def test_compute_substrate_service_preserves_approval_not_consumed_on_pre_execution_cancel() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="service-cancel-approved")])
    service = ComputeSubstrateService(approval_store=approval_store)
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = service.submit(
        create_task_envelope(
            "echo",
            task_id="service-cancel-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True),
        ),
        context=context,
    )

    grant = approval_store.get("approval-echo")
    assert result.status == ComputeTaskStatus.CANCELLED
    assert grant is not None
    assert grant.consumed_at_ms == 0
    assert result.record.approval_required is True
    assert result.record.approval_satisfied is True
    assert result.record.approval_consumed is False
    assert result.record.execution_started is False


def test_compute_substrate_service_preserves_approval_consumed_after_execution_timeout() -> None:
    registry = WorkerRegistry()
    registry.register(_SlowNonCooperativeBackend())
    approval_store = InMemoryApprovalStore(
        [_approval_grant(task_id="service-timeout-approved", worker_id="slow-worker")]
    )
    service = ComputeSubstrateService(registry=registry, approval_store=approval_store)

    result = service.submit(
        create_task_envelope(
            "echo",
            task_id="service-timeout-approved",
            approval_id="approval-echo",
            budget=ResourceBudget(approval_required=True, max_runtime_ms=50),
        )
    )

    grant = approval_store.get("approval-echo")
    assert result.status == ComputeTaskStatus.TIMED_OUT
    assert grant is not None
    assert grant.consumed_at_ms > 0
    assert result.record.approval_consumed is True
    assert result.record.timed_out is True
    assert result.record.timeout_stage == "post_execution"
    assert result.record.execution_started is True


def test_compute_substrate_service_reports_durable_receipt_truth(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    service = ComputeSubstrateService(receipt_store=store)

    result = service.submit(create_task_envelope("echo", task_id="service-receipt-persisted"))

    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.record.receipt_persisted is True
    assert result.record.receipt_persistence_status == "persisted_local_json"
    assert result.receipt.persisted is True
    assert Path(result.receipt.receipt_path).exists()
    assert store.read_receipt(result.receipt.receipt_id) == result.receipt


def test_compute_substrate_service_reports_failed_receipt_persistence_truthfully() -> None:
    service = ComputeSubstrateService(receipt_store=_FailingReceiptStore())

    result = service.submit(create_task_envelope("echo", task_id="service-receipt-fails"))

    assert result.ok is False
    assert result.status == ComputeTaskStatus.RECEIPT_PERSISTENCE_FAILED
    assert result.result_status == "receipt_persistence_failed"
    assert result.record.receipt_persisted is False
    assert result.record.receipt_persistence_status == "persistence_failed"
    assert result.record.receipt_error.startswith("OSError: receipt store unavailable")
    assert result.receipt.persisted is False
    assert result.receipt.receipt_error.startswith("OSError: receipt store unavailable")
    assert service.status_for_task("service-receipt-fails") == result.record


def test_compute_substrate_service_preserves_worker_registry_denials() -> None:
    disabled_registry = WorkerRegistry()
    disabled_registry.register(_DisabledBackend())
    disabled = ComputeSubstrateService(registry=disabled_registry).submit(create_task_envelope("echo"))

    unknown = ComputeSubstrateService().submit(create_task_envelope("shell", task_id="service-unknown"))

    assert disabled.status == ComputeTaskStatus.DENIED
    assert disabled.record.worker_id == "disabled-worker"
    assert disabled.record.denial_reason == "worker_enabled"
    assert unknown.status == ComputeTaskStatus.DENIED
    assert unknown.record.worker_id == "unregistered"
    assert unknown.record.denial_reason == "unregistered_function"


def test_compute_substrate_service_unknown_status_readback_is_truthful() -> None:
    service = ComputeSubstrateService()

    task_status = service.status_for_task("missing-task")
    correlation_status = service.status_for_correlation("missing-trace")

    assert task_status.status == ComputeTaskStatus.UNKNOWN
    assert task_status.task_id == "missing-task"
    assert task_status.error == "status_not_found"
    assert correlation_status.status == ComputeTaskStatus.UNKNOWN
    assert correlation_status.correlation_id == "missing-trace"


def test_compute_substrate_service_records_do_not_store_raw_payload_or_output() -> None:
    service = ComputeSubstrateService()

    result = service.submit(
        create_task_envelope(
            "echo",
            task_id="service-no-raw-storage",
            payload={"message": "secret-service-payload"},
        )
    )

    record_text = json.dumps(result.record.to_dict(), sort_keys=True)
    result_text = json.dumps(result.to_dict(), sort_keys=True)
    assert "secret-service-payload" not in record_text
    assert "secret-service-payload" not in result_text
    assert result.record.to_dict()["stores_payload"] is False
    assert result.record.to_dict()["stores_output"] is False
    assert result.to_dict()["stores_payload"] is False
    assert result.to_dict()["stores_output"] is False


def test_compute_substrate_service_describes_internal_non_api_boundary() -> None:
    service = ComputeSubstrateService()
    status_store = InMemoryComputeStatusStore()

    description = service.describe()
    store_description = status_store.describe()

    assert description["submission_mode"] == "synchronous_in_process"
    assert description["uses_governor"] is True
    assert description["no_api_route"] is True
    assert description["no_background_worker"] is True
    assert description["stores_payload"] is False
    assert description["stores_output"] is False
    assert description["writes_memory"] is False
    assert description["approval_store"]["kind"] == "none"
    assert description["durable_approval_persistence"] is False
    assert description["live_learning_persistence"] is False
    assert description["os_level_cpu_memory_enforcement"] is False
    assert store_description["durable"] is False
    assert store_description["background_execution"] is False


def test_compute_substrate_service_describes_configured_durable_approval_store(tmp_path: Path) -> None:
    service = ComputeSubstrateService(approval_store=LocalJsonComputeApprovalStore(tmp_path / "compute-approvals"))

    description = service.describe()

    assert description["approval_store"]["kind"] == "francis.compute_substrate.local_json_approval_store"
    assert description["approval_store"]["durable"] is True
    assert description["approval_store"]["cross_process_atomic_reservation"] is False
    assert description["durable_approval_persistence"] is True
    assert description["no_api_route"] is True
    assert description["no_background_worker"] is True


def test_public_facade_exports_compute_submission_status_contracts() -> None:
    submission = ComputeSubmission(create_task_envelope("echo", task_id="service-facade"))
    service = ComputeSubstrateService()
    approval_store = LocalJsonComputeApprovalStore

    assert submission.to_dict()["stores_payload"] is False
    assert service.status_for_task("service-facade").status == ComputeTaskStatus.UNKNOWN
    assert ComputeTaskStatus.RECEIPT_PERSISTENCE_FAILED == "receipt_persistence_failed"
    assert approval_store.__name__ == "LocalJsonComputeApprovalStore"


def test_compute_substrate_approval_module_does_not_add_execution_authority() -> None:
    source = inspect.getsource(approval_module)

    for forbidden in (
        "subprocess",
        "os.system",
        "shell=True",
        "socket",
        "requests",
        "urllib",
        "multiprocessing",
        "asyncio.create_task",
        "daemon=True",
    ):
        assert forbidden not in source
