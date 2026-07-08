from __future__ import annotations

import inspect
import json
from pathlib import Path

import francis.compute_substrate_adapters as adapter_module
from francis.compute_substrate import (
    ApprovalGrant,
    ApprovalScope,
    CapabilityReceipt,
    CancellationToken,
    ComputeAdapterDescriptor,
    ComputeAdapterGateway,
    ComputeAdapterKind,
    ComputeAdapterPolicy,
    ComputeAdapterRequest,
    ComputeAdapterSubmissionResult,
    ComputeSubstrateService,
    ComputeTaskStatus,
    ExecutionContext,
    ExecutionDeadline,
    InMemoryApprovalStore,
    InMemoryComputeAdapterRegistry,
    LocalJsonComputeApprovalStore,
    LocalJsonComputeReceiptStore,
    ResourceBudget,
    TaskEnvelope,
    WorkerDescriptor,
    WorkerRegistry,
)


class _RecordingService(ComputeSubstrateService):
    def __init__(self, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self.submit_calls = 0

    def submit(  # type: ignore[override]
        self,
        submission: object,
        *,
        context: ExecutionContext | None = None,
    ) -> object:
        self.submit_calls += 1
        return super().submit(submission, context=context)  # type: ignore[arg-type]


def _descriptor(
    *,
    adapter_id: str = "adapter-internal",
    enabled: bool = True,
    capabilities: tuple[str, ...] = ("echo",),
    requires_approval: bool = False,
) -> ComputeAdapterDescriptor:
    return ComputeAdapterDescriptor(
        adapter_id=adapter_id,
        adapter_kind=ComputeAdapterKind.INTERNAL,
        name="Internal contract adapter",
        enabled=enabled,
        declared_capabilities=capabilities,
        default_resource_budget=ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
        requires_approval_by_default=requires_approval,
        metadata_summary={"owner": "compute-substrate-tests"},
    )


def _policy(
    *,
    capabilities: tuple[str, ...] = ("echo",),
    budget: ResourceBudget | None = None,
    require_approval: bool = False,
    max_risk_level: str = "low",
    allow_network: bool = False,
    allow_gpu: bool = False,
    filesystem_scope: tuple[str, ...] = ("none",),
) -> ComputeAdapterPolicy:
    return ComputeAdapterPolicy(
        allowed_capabilities=capabilities,
        max_resource_budget=budget or ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
        require_approval=require_approval,
        max_risk_level=max_risk_level,
        allow_network=allow_network,
        allow_gpu=allow_gpu,
        filesystem_scope=filesystem_scope,
    )


def _registry(
    *,
    descriptor: ComputeAdapterDescriptor | None = None,
    policy: ComputeAdapterPolicy | None = None,
) -> InMemoryComputeAdapterRegistry:
    registry = InMemoryComputeAdapterRegistry()
    registry.register(descriptor or _descriptor(), policy)
    return registry


def _request(
    *,
    request_id: str = "adapter-request",
    adapter_id: str = "adapter-internal",
    capability: str = "echo",
    payload: dict[str, object] | None = None,
    budget: ResourceBudget | None = None,
    approval_required: bool = False,
    approval_id: str = "",
    context: ExecutionContext | None = None,
    risk_level: str = "low",
) -> ComputeAdapterRequest:
    return ComputeAdapterRequest(
        request_id=request_id,
        adapter_id=adapter_id,
        requested_capability=capability,
        task_type="unit_test_adapter_request",
        intent_summary="bounded adapter request",
        payload=payload or {"message": "hello from adapter"},
        payload_summary="adapter echo request",
        resource_budget=budget or ResourceBudget(),
        risk_level=risk_level,
        approval_required=approval_required,
        approval_id=approval_id,
        context=context,
        correlation_id=f"trace-{request_id}",
        actor="adapter.unit-test",
    )


def _gateway(
    *,
    service: _RecordingService | None = None,
    registry: InMemoryComputeAdapterRegistry | None = None,
) -> tuple[ComputeAdapterGateway, _RecordingService]:
    resolved_service = service or _RecordingService()
    return (
        ComputeAdapterGateway(
            service=resolved_service,
            adapter_registry=registry or _registry(),
        ),
        resolved_service,
    )


def _approval_grant(
    *,
    task_id: str = "adapter-approved",
    capability: str = "echo",
    approval_id: str = "approval-adapter",
    max_runtime_ms: int | None = 1000,
) -> ApprovalGrant:
    return ApprovalGrant(
        approval_id=approval_id,
        scope=ApprovalScope(
            task_id=task_id,
            allowed_capabilities=(capability,),
            allowed_worker_ids=("safe-local-1",),
            max_risk_level="low",
            max_runtime_ms=max_runtime_ms,
            max_memory_mb=128,
            max_cpu_weight=25,
            max_compute_units=1000,
        ),
        approved_by="operator",
        reason="bounded adapter compute approval",
        approval_note="raw note must not be persisted",
    )


class _FailingReceiptStore:
    def write_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        raise OSError("adapter receipt store unavailable")

    def read_receipt(self, receipt_id: str) -> CapabilityReceipt | None:
        return None

    def describe(self) -> dict[str, object]:
        return {"kind": "test.failing_adapter_receipt_store"}


class _FailingAfterApprovalBackend:
    @property
    def descriptor(self) -> WorkerDescriptor:
        return WorkerDescriptor(
            worker_id="safe-local-1",
            backend_name="adapter_failure_after_approval_test",
            capabilities=("echo",),
        )

    def execute(self, envelope: TaskEnvelope) -> dict[str, object]:
        raise RuntimeError("adapter backend failed after approval")


def test_adapter_registry_registers_descriptor() -> None:
    registry = _registry()

    descriptors = registry.descriptors()

    assert len(descriptors) == 1
    assert descriptors[0].adapter_id == "adapter-internal"
    assert descriptors[0].adapter_kind == ComputeAdapterKind.INTERNAL
    assert descriptors[0].declared_capabilities == ("echo",)
    assert registry.policy_for("adapter-internal") is not None
    assert registry.describe()["real_adapter_implementation"] is False


def test_adapter_registry_rejects_duplicate_adapter_ids() -> None:
    registry = _registry()

    try:
        registry.register(_descriptor())
    except ValueError as exc:
        assert str(exc) == "adapter_already_registered"
    else:
        raise AssertionError("duplicate adapter ids must be rejected")


def test_disabled_adapter_denied_before_service_submission() -> None:
    gateway, service = _gateway(registry=_registry(descriptor=_descriptor(enabled=False)))

    result = gateway.submit(_request())

    assert result.ok is False
    assert result.accepted is False
    assert result.denial_reason == "adapter_disabled"
    assert service.submit_calls == 0


def test_unknown_adapter_denied() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(adapter_id="missing-adapter"))

    assert result.denial_reason == "unknown_adapter"
    assert service.submit_calls == 0


def test_invalid_adapter_id_denied() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(adapter_id="../bad-adapter"))

    assert result.denial_reason == "invalid_adapter_id"
    assert service.submit_calls == 0


def test_invalid_request_id_denied() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(request_id="../bad-request"))

    assert result.denial_reason == "invalid_request_id"
    assert service.submit_calls == 0


def test_unknown_capability_denied_before_service_submission() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(capability="shell"))

    assert result.denial_reason == "unknown_capability"
    assert service.submit_calls == 0


def test_capability_not_declared_by_adapter_denied() -> None:
    gateway, service = _gateway(registry=_registry(descriptor=_descriptor(capabilities=("echo",))))

    result = gateway.submit(_request(capability="compute_test"))

    assert result.denial_reason == "capability_not_declared"
    assert service.submit_calls == 0


def test_capability_not_allowed_by_adapter_policy_denied() -> None:
    registry = _registry(
        descriptor=_descriptor(capabilities=("echo", "health_check")),
        policy=_policy(capabilities=("health_check",)),
    )
    gateway, service = _gateway(registry=registry)

    result = gateway.submit(_request(capability="echo"))

    assert result.denial_reason == "capability_not_allowed"
    assert service.submit_calls == 0


def test_requested_budget_above_adapter_policy_denied() -> None:
    registry = _registry(policy=_policy(budget=ResourceBudget(max_runtime_ms=100, max_memory_mb=128, cpu_weight=25)))
    gateway, service = _gateway(registry=registry)

    result = gateway.submit(_request(budget=ResourceBudget(max_runtime_ms=101)))

    assert result.denial_reason == "resource_budget_exceeds_adapter_policy"
    assert service.submit_calls == 0


def test_network_request_denied_by_default() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(budget=ResourceBudget(allow_network=True)))

    assert result.denial_reason == "network_not_allowed"
    assert service.submit_calls == 0


def test_gpu_request_denied_by_default() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(budget=ResourceBudget(allow_gpu=True)))

    assert result.denial_reason == "gpu_not_allowed"
    assert service.submit_calls == 0


def test_filesystem_scope_outside_none_denied_by_default() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(budget=ResourceBudget(filesystem_scope=("D:/Francis",))))

    assert result.denial_reason == "filesystem_scope_not_allowed"
    assert service.submit_calls == 0


def test_risk_above_adapter_policy_denied() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(request_id="adapter-risk-denied", risk_level="high"))

    assert result.denial_reason == "risk_exceeds_adapter_policy"
    assert service.submit_calls == 0


def test_approval_required_downgrade_denied() -> None:
    registry = _registry(descriptor=_descriptor(requires_approval=True), policy=_policy(require_approval=True))
    gateway, service = _gateway(registry=registry)

    result = gateway.submit(_request(approval_required=False))

    assert result.denial_reason == "approval_required_downgrade"
    assert service.submit_calls == 0


def test_adapter_validation_denial_does_not_consume_approval() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-risk-denied")])
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))

    result = gateway.submit(
        _request(
            request_id="adapter-risk-denied",
            approval_required=True,
            approval_id="approval-adapter",
            risk_level="high",
        )
    )

    grant = approval_store.get("approval-adapter")
    assert result.denial_reason == "risk_exceeds_adapter_policy"
    assert service.submit_calls == 0
    assert grant is not None
    assert grant.consumed_at_ms == 0


def test_valid_adapter_request_submits_through_compute_substrate_service() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(request_id="adapter-valid", payload={"message": "service path"}))

    assert isinstance(result, ComputeAdapterSubmissionResult)
    assert service.submit_calls == 1
    assert "echo" in service.known_capabilities()
    assert result.accepted is True
    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.task_id == "adapter-valid"
    assert result.receipt_id
    assert result.submission_result is not None
    assert service.status_for_task("adapter-valid").status == ComputeTaskStatus.SUCCEEDED


def test_adapter_gateway_does_not_import_governor_or_backend_directly() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(request_id="adapter-service-spy"))
    source = inspect.getsource(adapter_module)

    assert result.ok is True
    assert service.submit_calls == 1
    assert "SubstrateGovernor" not in source
    assert "SafeLocalBackend" not in source
    assert gateway.describe()["uses_compute_substrate_service"] is True


def test_approval_required_without_valid_approval_is_denied_through_governed_path() -> None:
    gateway, service = _gateway()

    result = gateway.submit(_request(request_id="adapter-missing-approval", approval_required=True))

    assert service.submit_calls == 1
    assert result.accepted is True
    assert result.ok is False
    assert result.status == ComputeTaskStatus.DENIED
    assert result.submission_result is not None
    assert result.submission_result.record.denial_reason == "missing_approval"
    assert result.approval_required is True
    assert result.approval_satisfied is False


def test_approval_required_with_valid_scoped_approval_executes_through_governed_path() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-approved")])
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))

    result = gateway.submit(
        _request(
            request_id="adapter-approved",
            approval_required=True,
            approval_id="approval-adapter",
        )
    )

    consumed = approval_store.get("approval-adapter")
    assert service.submit_calls == 1
    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.approval_required is True
    assert result.approval_satisfied is True
    assert result.approval_consumed is True
    assert consumed is not None
    assert consumed.consumed_by_task_id == "adapter-approved"


def test_approval_required_with_valid_durable_approval_executes_through_adapter_gateway(tmp_path: Path) -> None:
    approval_store = LocalJsonComputeApprovalStore(tmp_path / "adapter-approvals")
    approval_store.add(_approval_grant(task_id="adapter-durable-approved", approval_id="approval-durable-adapter"))
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))

    result = gateway.submit(
        _request(
            request_id="adapter-durable-approved",
            approval_required=True,
            approval_id="approval-durable-adapter",
        )
    )

    consumed = approval_store.get("approval-durable-adapter")
    assert service.submit_calls == 1
    assert result.ok is True
    assert result.status == ComputeTaskStatus.SUCCEEDED
    assert result.approval_required is True
    assert result.approval_satisfied is True
    assert result.approval_consumed is True
    assert result.submission_result is not None
    assert result.submission_result.receipt.governance["approval_persistence"] == "persisted_local_json"
    assert consumed is not None
    assert consumed.consumed_by_task_id == "adapter-durable-approved"


def test_adapter_validation_denial_does_not_consume_durable_approval(tmp_path: Path) -> None:
    approval_store = LocalJsonComputeApprovalStore(tmp_path / "adapter-approvals")
    approval_store.add(_approval_grant(task_id="adapter-durable-risk-denied", approval_id="approval-durable-adapter"))
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))

    result = gateway.submit(
        _request(
            request_id="adapter-durable-risk-denied",
            approval_required=True,
            approval_id="approval-durable-adapter",
            risk_level="high",
        )
    )

    grant = approval_store.get("approval-durable-adapter")
    assert result.denial_reason == "risk_exceeds_adapter_policy"
    assert service.submit_calls == 0
    assert grant is not None
    assert grant.consumed_at_ms == 0


def test_single_use_approval_cannot_be_reused_through_adapter_gateway() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-single-use")])
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))
    request = _request(
        request_id="adapter-single-use",
        approval_required=True,
        approval_id="approval-adapter",
    )

    first = gateway.submit(request)
    second = gateway.submit(request)

    assert service.submit_calls == 2
    assert first.status == ComputeTaskStatus.SUCCEEDED
    assert second.ok is False
    assert second.status == ComputeTaskStatus.DENIED
    assert second.submission_result is not None
    assert second.submission_result.record.denial_reason == "already_consumed_approval"


def test_pre_execution_cancellation_is_respected_through_adapter_path() -> None:
    gateway, service = _gateway()
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = gateway.submit(_request(request_id="adapter-cancelled", context=context))

    assert service.submit_calls == 1
    assert result.accepted is True
    assert result.status == ComputeTaskStatus.CANCELLED
    assert result.cancellation_requested is True
    assert result.submission_result is not None
    assert result.submission_result.record.execution_started is False


def test_pre_execution_cancellation_with_approval_does_not_consume_approval() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-cancel-approved")])
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))
    context = ExecutionContext(
        cancellation_token=CancellationToken(cancel_requested=True, reason="operator_cancelled"),
    )

    result = gateway.submit(
        _request(
            request_id="adapter-cancel-approved",
            approval_required=True,
            approval_id="approval-adapter",
            context=context,
        )
    )

    grant = approval_store.get("approval-adapter")
    assert service.submit_calls == 1, result.to_dict()
    assert result.status == ComputeTaskStatus.CANCELLED
    assert result.approval_required is True
    assert result.approval_satisfied is True
    assert result.approval_consumed is False
    assert grant is not None
    assert grant.consumed_at_ms == 0


def test_expired_deadline_is_respected_through_adapter_path() -> None:
    gateway, service = _gateway()
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = gateway.submit(_request(request_id="adapter-expired-deadline", context=context))

    assert service.submit_calls == 1
    assert result.accepted is True
    assert result.status == ComputeTaskStatus.TIMED_OUT
    assert result.timed_out is True
    assert result.submission_result is not None
    assert result.submission_result.record.timeout_stage == "pre_execution"


def test_expired_deadline_with_approval_does_not_consume_approval() -> None:
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-deadline-approved")])
    gateway, service = _gateway(service=_RecordingService(approval_store=approval_store))
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=1, source="test_expired"))

    result = gateway.submit(
        _request(
            request_id="adapter-deadline-approved",
            approval_required=True,
            approval_id="approval-adapter",
            context=context,
        )
    )

    grant = approval_store.get("approval-adapter")
    assert service.submit_calls == 1
    assert result.status == ComputeTaskStatus.TIMED_OUT
    assert result.approval_required is True
    assert result.approval_satisfied is True
    assert result.approval_consumed is False
    assert grant is not None
    assert grant.consumed_at_ms == 0


def test_approval_consumed_when_adapter_execution_starts_then_fails() -> None:
    worker_registry = WorkerRegistry()
    worker_registry.register(_FailingAfterApprovalBackend())
    approval_store = InMemoryApprovalStore([_approval_grant(task_id="adapter-started-failure")])
    gateway, service = _gateway(
        service=_RecordingService(registry=worker_registry, approval_store=approval_store),
    )

    result = gateway.submit(
        _request(
            request_id="adapter-started-failure",
            approval_required=True,
            approval_id="approval-adapter",
        )
    )

    grant = approval_store.get("approval-adapter")
    assert service.submit_calls == 1
    assert result.status == ComputeTaskStatus.FAILED
    assert result.approval_consumed is True
    assert result.submission_result is not None
    assert result.submission_result.record.execution_started is True
    assert result.submission_result.result_error == "RuntimeError: adapter backend failed after approval"
    assert grant is not None
    assert grant.consumed_at_ms > 0


def test_durable_compute_receipt_persistence_works_through_adapter_path(tmp_path: Path) -> None:
    store = LocalJsonComputeReceiptStore(tmp_path / "compute-receipts")
    gateway, service = _gateway(service=_RecordingService(receipt_store=store))

    result = gateway.submit(_request(request_id="adapter-durable-receipt"))

    assert service.submit_calls == 1
    assert result.ok is True
    assert result.receipt_persisted is True
    assert result.submission_result is not None
    assert result.submission_result.receipt.persisted is True
    assert store.read_receipt(result.receipt_id) == result.submission_result.receipt


def test_failed_receipt_persistence_reports_truth_through_adapter_path() -> None:
    gateway, service = _gateway(service=_RecordingService(receipt_store=_FailingReceiptStore()))

    result = gateway.submit(_request(request_id="adapter-receipt-fails"))

    assert service.submit_calls == 1
    assert result.ok is False
    assert result.status == ComputeTaskStatus.RECEIPT_PERSISTENCE_FAILED
    assert result.receipt_persisted is False
    assert result.submission_result is not None
    assert result.submission_result.receipt.persisted is False
    assert result.submission_result.receipt.receipt_error.startswith("OSError: adapter receipt store unavailable")


def test_adapter_submission_result_contains_bounded_summary_fields() -> None:
    gateway, _service = _gateway()

    result = gateway.submit(_request(request_id="adapter-summary", payload={"message": "bounded"}))
    summary = result.to_dict()

    assert summary["request_id"] == "adapter-summary"
    assert summary["adapter_id"] == "adapter-internal"
    assert summary["adapter_kind"] == ComputeAdapterKind.INTERNAL
    assert summary["task_id"] == "adapter-summary"
    assert summary["compute_status"] == ComputeTaskStatus.SUCCEEDED
    assert summary["receipt_id"]
    assert summary["stores_payload"] is False
    assert summary["stores_output"] is False
    assert summary["durable_adapter_persistence"] is False
    assert "receipt" not in summary


def test_adapter_status_result_does_not_store_raw_payload_or_output() -> None:
    gateway, _service = _gateway()
    request = _request(
        request_id="adapter-no-raw-storage",
        payload={"message": "secret-adapter-payload"},
    )

    result = gateway.submit(request)

    request_text = json.dumps(request.to_dict(), sort_keys=True)
    result_text = json.dumps(result.to_dict(), sort_keys=True)
    assert "secret-adapter-payload" not in request_text
    assert "secret-adapter-payload" not in result_text
    assert request.to_dict()["stores_payload"] is False
    assert result.to_dict()["stores_payload"] is False
    assert result.to_dict()["stores_output"] is False


def test_adapter_request_summary_redacts_non_default_filesystem_scope() -> None:
    request = _request(
        request_id="adapter-filesystem-summary",
        budget=ResourceBudget(filesystem_scope=("C:/secret/private",)),
    )
    descriptor = _descriptor(
        adapter_id="adapter-filesystem-summary",
        capabilities=("echo",),
    )
    policy = _policy(filesystem_scope=("C:/secret/private",))

    request_text = json.dumps(request.to_dict(), sort_keys=True)
    descriptor_text = json.dumps(descriptor.to_dict(), sort_keys=True)
    policy_text = json.dumps(policy.to_dict(), sort_keys=True)

    assert "C:/secret/private" not in request_text
    assert "C:/secret/private" not in descriptor_text
    assert "C:/secret/private" not in policy_text
    assert request.to_dict()["resource_budget"]["filesystem_scope"] == ["non_default_scope_requested"]
    assert policy.to_dict()["filesystem_scope"] == ["non_default_scope_requested"]


def test_public_facade_exports_adapter_contracts() -> None:
    registry = InMemoryComputeAdapterRegistry()
    descriptor = _descriptor(adapter_id="facade-adapter")
    registry.register(descriptor)
    gateway = ComputeAdapterGateway(adapter_registry=registry)

    result = gateway.submit(_request(adapter_id="facade-adapter", request_id="facade-request"))

    assert result.ok is True
    assert ComputeAdapterKind.INTERNAL == "internal"
    assert descriptor.to_dict()["real_adapter_implementation"] is False


def test_adapter_layer_describes_contract_only_no_live_or_durable_expansion() -> None:
    gateway, _service = _gateway()
    gateway_description = gateway.describe()
    registry_description = InMemoryComputeAdapterRegistry().describe()

    assert gateway_description["no_api_route"] is True
    assert gateway_description["no_background_worker"] is True
    assert gateway_description["real_adapter_implementation"] is False
    assert gateway_description["durable_adapter_persistence"] is False
    assert gateway_description["writes_memory"] is False
    assert registry_description["durable"] is False
    assert registry_description["real_adapter_implementation"] is False

    source = inspect.getsource(adapter_module)
    for forbidden in ("subprocess", "socket", "requests", "urllib", "create_task", "shell=True"):
        assert forbidden not in source
