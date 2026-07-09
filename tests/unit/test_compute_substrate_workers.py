from __future__ import annotations

import inspect
import json

import francis.compute_substrate_workers as worker_module
from francis.compute_substrate import (
    ComputeSubstrateService,
    ComputeTaskStatus,
    ExecutionContext,
    ExecutionDeadline,
    ExecutionResult,
    InMemoryManagedWorkerRegistry,
    ManagedWorkerBackendContract,
    ManagedWorkerBinding,
    ManagedWorkerCapabilitySummary,
    ManagedWorkerCapabilities,
    ManagedWorkerDescriptor,
    ManagedWorkerExecutionPlan,
    ManagedWorkerKind,
    ManagedWorkerPolicy,
    ManagedWorkerReadiness,
    ManagedWorkerRegistry,
    ManagedWorkerRegistryResult,
    ManagedWorkerResourceEnvelope,
    ManagedWorkerSandboxProfile,
    ResourceBudget,
    SafeLocalBackend,
    SubstrateGovernor,
    TaskEnvelope,
    WorkerRegistry,
    create_task_envelope,
    create_managed_worker_execution_plan,
    validate_managed_worker_descriptor,
    validate_managed_worker_policy,
)


def _capabilities(
    *,
    capabilities: tuple[str, ...] = ("echo",),
    supports_cancellation: bool = True,
    supports_deadline: bool = True,
    supports_receipts: bool = True,
    supports_status: bool = True,
    supports_network: bool = False,
    supports_gpu: bool = False,
    supports_persistent_storage: bool = False,
    supports_remote: bool = False,
) -> ManagedWorkerCapabilities:
    return ManagedWorkerCapabilities(
        declared_capabilities=capabilities,
        supports_cancellation=supports_cancellation,
        supports_deadline=supports_deadline,
        supports_receipts=supports_receipts,
        supports_status=supports_status,
        supports_network=supports_network,
        supports_gpu=supports_gpu,
        supports_persistent_storage=supports_persistent_storage,
        supports_remote=supports_remote,
    )


def _descriptor(
    *,
    worker_id: str = "managed-worker-1",
    kind: str = ManagedWorkerKind.LOCAL_SAFE,
    enabled: bool = True,
    capabilities: tuple[str, ...] = ("echo",),
    requires_approval: bool = False,
    supports_receipts: bool = True,
    supports_status: bool = True,
    supports_network: bool = False,
    supports_gpu: bool = False,
    supports_persistent_storage: bool = False,
    supports_remote: bool = False,
    max_budget: ResourceBudget | None = None,
    filesystem_scope: tuple[str, ...] = ("none",),
    metadata_summary: dict[str, object] | None = None,
) -> ManagedWorkerDescriptor:
    return ManagedWorkerDescriptor(
        worker_id=worker_id,
        name="Managed worker contract",
        kind=kind,
        enabled=enabled,
        capabilities=_capabilities(
            capabilities=capabilities,
            supports_receipts=supports_receipts,
            supports_status=supports_status,
            supports_network=supports_network,
            supports_gpu=supports_gpu,
            supports_persistent_storage=supports_persistent_storage,
            supports_remote=supports_remote,
        ),
        default_resource_budget=ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
        max_resource_budget=max_budget or ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
        requires_approval_by_default=requires_approval,
        filesystem_scope=filesystem_scope,
        metadata_summary=metadata_summary or {"owner": "compute-substrate-tests"},
    )


def _policy(
    *,
    capabilities: tuple[str, ...] = ("echo",),
    worker_kinds: tuple[str, ...] = (ManagedWorkerKind.LOCAL_SAFE,),
    budget: ResourceBudget | None = None,
    require_approval: bool = False,
    require_deadline: bool = False,
    require_cancellation_context: bool = False,
    require_receipt: bool = True,
    require_status: bool = True,
    allow_network: bool = False,
    allow_gpu: bool = False,
    filesystem_scope: tuple[str, ...] = ("none",),
    allow_persistent_storage: bool = False,
    allow_remote: bool = False,
) -> ManagedWorkerPolicy:
    return ManagedWorkerPolicy(
        allowed_capabilities=capabilities,
        allowed_worker_kinds=worker_kinds,
        max_resource_budget=budget or ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
        require_approval=require_approval,
        require_deadline=require_deadline,
        require_cancellation_context=require_cancellation_context,
        require_receipt=require_receipt,
        require_status=require_status,
        allow_network=allow_network,
        allow_gpu=allow_gpu,
        filesystem_scope=filesystem_scope,
        allow_persistent_storage=allow_persistent_storage,
        allow_remote=allow_remote,
    )


def _resource(
    *,
    task_id: str = "managed-task-1",
    capability: str = "echo",
    budget: ResourceBudget | None = None,
    approval_required: bool = False,
    persistent_storage_requested: bool = False,
    remote_execution_requested: bool = False,
    shell_requested: bool = False,
) -> ManagedWorkerResourceEnvelope:
    return ManagedWorkerResourceEnvelope(
        task_id=task_id,
        requested_capability=capability,
        resource_budget=budget or ResourceBudget(),
        approval_required=approval_required,
        persistent_storage_requested=persistent_storage_requested,
        remote_execution_requested=remote_execution_requested,
        shell_requested=shell_requested,
    )


def _plan(
    *,
    descriptor: ManagedWorkerDescriptor | None = None,
    policy: ManagedWorkerPolicy | None = None,
    resource: ManagedWorkerResourceEnvelope | TaskEnvelope | None = None,
    context: ExecutionContext | None = None,
    plan_id: str | None = "managed-plan-1",
) -> ManagedWorkerExecutionPlan:
    return create_managed_worker_execution_plan(
        descriptor or _descriptor(),
        policy or _policy(),
        resource or _resource(),
        context=context,
        plan_id=plan_id,
    )


class _CountingSafeLocalBackend(SafeLocalBackend):
    def __init__(self) -> None:
        super().__init__()
        self.execute_calls = 0

    def execute(self, envelope: TaskEnvelope, context: ExecutionContext | None = None) -> dict[str, object]:
        self.execute_calls += 1
        return super().execute(envelope, context=context)


class _CountingGovernor(SubstrateGovernor):
    def __init__(self) -> None:
        super().__init__()
        self.execute_calls = 0

    def execute(
        self,
        envelope: TaskEnvelope,
        registry: WorkerRegistry,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        self.execute_calls += 1
        return super().execute(envelope, registry, context=context)


def test_valid_managed_worker_descriptor_can_be_created() -> None:
    descriptor = _descriptor()

    readiness = validate_managed_worker_descriptor(descriptor)
    payload = descriptor.to_dict()

    assert readiness.ready is True
    assert descriptor.worker_id == "managed-worker-1"
    assert descriptor.kind == ManagedWorkerKind.LOCAL_SAFE
    assert descriptor.declared_capabilities == ("echo",)
    assert payload["real_worker_implementation"] is False
    assert payload["stores_secrets"] is False


def test_unsafe_worker_ids_are_rejected_by_contract_validation() -> None:
    descriptor = _descriptor(worker_id="../escape")

    readiness = validate_managed_worker_descriptor(descriptor)

    assert readiness.ready is False
    assert readiness.reason == "safe_worker_id"


def test_empty_whitespace_and_dot_path_ids_are_rejected() -> None:
    invalid_descriptors = [
        _descriptor(worker_id=""),
        _descriptor(worker_id="   "),
        _descriptor(worker_id="."),
        _descriptor(worker_id=".."),
        _descriptor(worker_id="worker..escape"),
        _descriptor(worker_id="C:drive"),
        _descriptor(worker_id="worker\\escape"),
    ]

    reasons = [validate_managed_worker_descriptor(descriptor).reason for descriptor in invalid_descriptors]

    assert reasons == ["safe_worker_id"] * len(invalid_descriptors)


def test_managed_worker_registry_registers_valid_descriptor() -> None:
    registry = InMemoryManagedWorkerRegistry()
    descriptor = _descriptor(worker_id="managed-worker-registry")

    result = registry.register_descriptor(descriptor)
    summaries = registry.list_descriptors()
    capability_summaries = registry.list_capability_summaries()

    assert result.ok is True
    assert result.status == "registered"
    assert result.worker_id == "managed-worker-registry"
    assert result.descriptor == descriptor
    assert registry.get_descriptor("managed-worker-registry") == descriptor
    assert summaries == [
        {
            **summaries[0],
            "worker_id": "managed-worker-registry",
            "status": "registered_contract_only",
            "contract_only": True,
            "metadata_only": True,
            "non_executable": True,
            "executable_substrate_capability": False,
            "registered_execution_backend": False,
        }
    ]
    assert len(capability_summaries) == 1
    assert capability_summaries[0].worker_id == "managed-worker-registry"
    assert capability_summaries[0].capability_id == "echo"
    assert capability_summaries[0].to_dict()["non_executable"] is True
    assert registry.describe()["process_local"] is True
    assert registry.describe()["durable"] is False


def test_managed_worker_registry_rejects_duplicate_worker_id() -> None:
    registry = InMemoryManagedWorkerRegistry()
    descriptor = _descriptor(worker_id="managed-worker-duplicate")

    first = registry.register_descriptor(descriptor)
    duplicate = registry.register_descriptor(descriptor)

    assert first.ok is True
    assert duplicate.ok is False
    assert duplicate.reason == "worker_already_registered"
    assert len(registry.list_descriptors()) == 1


def test_managed_worker_registry_rejects_unsafe_worker_id() -> None:
    registry = InMemoryManagedWorkerRegistry()

    result = registry.register_descriptor(_descriptor(worker_id="../managed-worker"))

    assert result.ok is False
    assert result.reason == "safe_worker_id"
    assert registry.list_descriptors() == []


def test_managed_worker_registry_unknown_lookup_is_truthful_none() -> None:
    registry = InMemoryManagedWorkerRegistry()

    assert registry.get_descriptor("unknown-worker") is None
    assert registry.get_descriptor("../bad-worker") is None
    assert registry.binding_for("unknown-worker") is None


def test_managed_worker_registry_stores_disabled_worker_as_non_executable_metadata() -> None:
    registry = InMemoryManagedWorkerRegistry()

    result = registry.register_descriptor(_descriptor(worker_id="managed-worker-disabled", enabled=False))
    summary = registry.list_descriptors()[0]
    capability_summary = registry.list_capability_summaries()[0].to_dict()
    binding = registry.binding_for("managed-worker-disabled")

    assert result.ok is True
    assert summary["enabled"] is False
    assert summary["status"] == "disabled"
    assert summary["non_executable"] is True
    assert capability_summary["worker_enabled"] is False
    assert capability_summary["executable_substrate_capability"] is False
    assert binding is not None
    assert binding.descriptor.enabled is False


def test_managed_worker_registry_summaries_redact_paths_secrets_env_and_user_metadata() -> None:
    registry = InMemoryManagedWorkerRegistry()
    descriptor = _descriptor(
        worker_id="managed-worker-redacted",
        metadata_summary={
            "host_path": "D:\\Francis\\private",
            "secret": "SECRET_SHOULD_NOT_APPEAR",
            "raw_env": "API_KEY=SHOULD_NOT_APPEAR",
            "container_image_credentials": "credential=SHOULD_NOT_APPEAR",
            "host_username": "Austin",
            "owner": "compute-substrate-tests",
        },
    )

    result = registry.register_descriptor(descriptor)
    serialized = json.dumps(
        {
            "result": result.to_dict(),
            "descriptors": registry.list_descriptors(),
            "capabilities": [item.to_dict() for item in registry.list_capability_summaries()],
        },
        sort_keys=True,
    )

    assert result.ok is True
    assert "D:\\Francis\\private" not in serialized
    assert "SHOULD_NOT_APPEAR" not in serialized
    assert "Austin" not in serialized
    assert "non_default_summary_declared" in serialized
    assert "redacted_summary" in serialized


def test_managed_worker_registry_exposes_no_execution_run_spawn_or_backend_lookup() -> None:
    registry = InMemoryManagedWorkerRegistry()
    protocol_methods = set(ManagedWorkerRegistry.__dict__)
    concrete_methods = set(dir(registry))

    assert "register_descriptor" in protocol_methods
    assert "list_capability_summaries" in protocol_methods
    for forbidden in ("execute", "run", "spawn", "backend_for", "launch", "start"):
        assert forbidden not in protocol_methods
        assert forbidden not in concrete_methods


def test_managed_worker_registry_does_not_call_backend_governor_service_or_mutate_worker_registry() -> None:
    backend = _CountingSafeLocalBackend()
    worker_registry = WorkerRegistry()
    worker_registry.register(backend)
    governor = _CountingGovernor()
    service = ComputeSubstrateService(governor=governor, registry=worker_registry)
    executable_capabilities = service.known_capabilities()
    managed_registry = InMemoryManagedWorkerRegistry()

    result = managed_registry.register_descriptor(
        _descriptor(worker_id="future-managed-worker", kind=ManagedWorkerKind.CONTAINER, capabilities=("echo",))
    )
    binding = managed_registry.binding_for(
        "future-managed-worker",
        policy=_policy(worker_kinds=(ManagedWorkerKind.CONTAINER,)),
    )

    assert result.ok is True
    assert binding is not None
    assert binding.create_execution_plan(_resource(), plan_id="managed-registry-plan").ok is True
    assert backend.execute_calls == 0
    assert governor.execute_calls == 0
    assert service.known_capabilities() == executable_capabilities
    assert [worker.worker_id for worker in worker_registry.descriptors()] == ["safe-local-1"]
    assert service.status_store.describe()["stored_record_count"] == 0
    assert managed_registry.describe()["mutates_worker_registry"] is False


def test_managed_worker_registry_does_not_create_executable_substrate_capabilities() -> None:
    worker_registry = WorkerRegistry()
    worker_registry.register(SafeLocalBackend())
    service = ComputeSubstrateService(registry=worker_registry)
    managed_registry = InMemoryManagedWorkerRegistry()

    managed_registry.register_descriptor(
        _descriptor(
            worker_id="future-vm-worker",
            kind=ManagedWorkerKind.VM,
            capabilities=("future_vm_echo",),
        )
    )
    summaries = [item.to_dict() for item in managed_registry.list_capability_summaries()]

    assert summaries == [
        {
            **summaries[0],
            "capability_id": "future_vm_echo",
            "contract_only": True,
            "non_executable": True,
            "future_worker": True,
            "executable_substrate_capability": False,
            "registered_execution_backend": False,
        }
    ]
    assert "future_vm_echo" not in service.known_capabilities()
    assert worker_registry.backend_for("future_vm_echo") is None
    assert managed_registry.get_descriptor("future-vm-worker") is not None


def test_disabled_worker_is_denied() -> None:
    plan = _plan(descriptor=_descriptor(enabled=False))

    assert plan.ok is False
    assert plan.denial_reason == "worker_disabled"


def test_unknown_worker_kind_denied_unless_explicitly_allowed() -> None:
    descriptor = _descriptor(kind="future-runtime")

    denied = _plan(descriptor=descriptor)
    allowed = _plan(
        descriptor=descriptor,
        policy=_policy(worker_kinds=(ManagedWorkerKind.UNKNOWN,)),
        plan_id="managed-plan-unknown-kind",
    )

    assert descriptor.kind == ManagedWorkerKind.UNKNOWN
    assert denied.denial_reason == "worker_kind_not_allowed"
    assert allowed.ok is True
    assert allowed.status == "planned_contract_only"


def test_policy_worker_kind_does_not_silently_normalize_unknown_labels() -> None:
    policy = _policy(worker_kinds=("future-runtime",))

    readiness = validate_managed_worker_policy(policy)

    assert readiness.ready is False
    assert readiness.reason == "allowed_worker_kinds_present"
    assert policy.allowed_worker_kinds == ()


def test_undeclared_capability_denied() -> None:
    plan = _plan(resource=_resource(capability="compute_test"))

    assert plan.denial_reason == "capability_not_declared"


def test_capability_outside_policy_denied() -> None:
    plan = _plan(
        descriptor=_descriptor(capabilities=("echo", "health_check")),
        policy=_policy(capabilities=("health_check",)),
    )

    assert plan.denial_reason == "capability_not_allowed"


def test_requested_runtime_memory_cpu_or_units_above_policy_denied() -> None:
    policy = _policy(budget=ResourceBudget(max_runtime_ms=100, max_memory_mb=64, cpu_weight=10, max_compute_units=10))

    denied = [
        _plan(policy=policy, resource=_resource(budget=ResourceBudget(max_runtime_ms=101))),
        _plan(policy=policy, resource=_resource(budget=ResourceBudget(max_memory_mb=65))),
        _plan(policy=policy, resource=_resource(budget=ResourceBudget(cpu_weight=11))),
        _plan(policy=policy, resource=_resource(budget=ResourceBudget(max_compute_units=11))),
    ]

    assert {plan.denial_reason for plan in denied} == {"resource_budget_exceeds_worker_policy"}


def test_descriptor_resource_ceiling_still_applies_when_policy_allows_more() -> None:
    descriptor = _descriptor(max_budget=ResourceBudget(max_runtime_ms=50, max_memory_mb=64, cpu_weight=10))
    policy = _policy(budget=ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25))

    plan = _plan(descriptor=descriptor, policy=policy, resource=_resource(budget=ResourceBudget(max_runtime_ms=51)))

    assert plan.denial_reason == "resource_budget_exceeds_worker_descriptor"


def test_network_denied_by_default() -> None:
    plan = _plan(resource=_resource(budget=ResourceBudget(allow_network=True)))

    assert plan.denial_reason == "network_not_allowed"


def test_network_policy_allow_still_requires_worker_support() -> None:
    plan = _plan(
        descriptor=_descriptor(supports_network=False),
        policy=_policy(allow_network=True),
        resource=_resource(budget=ResourceBudget(allow_network=True)),
    )

    assert plan.denial_reason == "network_support_required"


def test_gpu_denied_by_default() -> None:
    plan = _plan(resource=_resource(budget=ResourceBudget(allow_gpu=True)))

    assert plan.denial_reason == "gpu_not_allowed"


def test_gpu_policy_allow_still_requires_worker_support() -> None:
    plan = _plan(
        descriptor=_descriptor(supports_gpu=False),
        policy=_policy(allow_gpu=True),
        resource=_resource(budget=ResourceBudget(allow_gpu=True)),
    )

    assert plan.denial_reason == "gpu_support_required"


def test_filesystem_scope_outside_none_denied_by_default() -> None:
    plan = _plan(resource=_resource(budget=ResourceBudget(filesystem_scope=("D:/Francis/private",))))

    assert plan.denial_reason == "filesystem_scope_not_allowed"
    assert "D:/Francis/private" not in json.dumps(plan.to_dict(), sort_keys=True)


def test_filesystem_policy_allow_still_requires_worker_scope_support() -> None:
    plan = _plan(
        descriptor=_descriptor(filesystem_scope=("none",)),
        policy=_policy(filesystem_scope=("workspace",)),
        resource=_resource(budget=ResourceBudget(filesystem_scope=("workspace",))),
    )

    assert plan.denial_reason == "filesystem_scope_not_supported"
    assert "workspace" not in json.dumps(plan.to_dict(), sort_keys=True)


def test_persistent_storage_denied_by_default() -> None:
    plan = _plan(resource=_resource(persistent_storage_requested=True))

    assert plan.denial_reason == "persistent_storage_not_allowed"


def test_persistent_storage_policy_allow_still_requires_worker_support() -> None:
    plan = _plan(
        descriptor=_descriptor(supports_persistent_storage=False),
        policy=_policy(allow_persistent_storage=True),
        resource=_resource(persistent_storage_requested=True),
    )

    assert plan.denial_reason == "persistent_storage_support_required"


def test_remote_execution_denied_by_default() -> None:
    plan = _plan(resource=_resource(remote_execution_requested=True))

    assert plan.denial_reason == "remote_execution_not_allowed"


def test_remote_policy_allow_still_requires_worker_support() -> None:
    plan = _plan(
        descriptor=_descriptor(supports_remote=False),
        policy=_policy(allow_remote=True),
        resource=_resource(remote_execution_requested=True),
    )

    assert plan.denial_reason == "remote_execution_support_required"


def test_shell_request_denied_even_if_constructed_in_contract() -> None:
    plan = _plan(resource=_resource(shell_requested=True))

    assert plan.denial_reason == "shell_not_allowed"


def test_approval_required_downgrade_denied() -> None:
    plan = _plan(
        descriptor=_descriptor(requires_approval=True),
        policy=_policy(require_approval=True),
        resource=_resource(approval_required=False),
    )

    assert plan.denial_reason == "approval_required_downgrade"


def test_missing_deadline_denied_if_policy_requires_deadline() -> None:
    plan = _plan(policy=_policy(require_deadline=True))

    assert plan.denial_reason == "deadline_required"


def test_missing_cancellation_context_denied_if_policy_requires_cancellation() -> None:
    plan = _plan(policy=_policy(require_cancellation_context=True))

    assert plan.denial_reason == "cancellation_context_required"


def test_missing_receipt_or_status_support_denied_when_required() -> None:
    receipt_denied = _plan(descriptor=_descriptor(supports_receipts=False), policy=_policy(require_receipt=True))
    status_denied = _plan(
        descriptor=_descriptor(supports_status=False),
        policy=_policy(require_status=True),
        plan_id="managed-plan-status-denied",
    )

    assert receipt_denied.denial_reason == "receipt_support_required"
    assert status_denied.denial_reason == "status_support_required"


def test_unsafe_plan_ids_and_capability_ids_are_denied() -> None:
    bad_plan = _plan(plan_id="../bad-plan")
    bad_capability = _plan(resource=_resource(capability="../bad-capability"), plan_id="managed-plan-bad-capability")

    assert bad_plan.denial_reason == "unsafe_plan_id"
    assert bad_capability.denial_reason == "unsafe_capability_id"


def test_valid_request_produces_contract_only_execution_plan() -> None:
    context = ExecutionContext(deadline=ExecutionDeadline(deadline_at_ms=9999999999999, source="test"))
    plan = _plan(policy=_policy(require_deadline=True), context=context)

    assert plan.ok is True
    assert plan.status == "planned_contract_only"
    assert plan.contract_only is True
    assert plan.dry_run is True
    assert plan.launch_plan is not None
    assert plan.readiness.ready is True
    assert plan.to_dict()["starts_processes"] is False
    assert plan.to_dict()["real_container_execution"] is False
    assert plan.to_dict()["real_vm_execution"] is False


def test_managed_worker_contracts_compose_with_substrate_without_execution() -> None:
    backend = _CountingSafeLocalBackend()
    registry = WorkerRegistry()
    registry.register(backend)
    governor = _CountingGovernor()
    service = ComputeSubstrateService(governor=governor, registry=registry)
    safe_capabilities = service.known_capabilities()
    descriptor = _descriptor(
        worker_id="future-managed-container",
        kind=ManagedWorkerKind.CONTAINER,
        capabilities=("echo",),
        metadata_summary={
            "owner": "compute-substrate-tests",
            "host_path": "D:\\Francis\\private",
            "api_token": "token=SHOULD_NOT_APPEAR",
        },
    )
    policy = _policy(
        capabilities=("echo",),
        worker_kinds=(ManagedWorkerKind.CONTAINER,),
        require_deadline=True,
        require_cancellation_context=True,
    )
    context = ExecutionContext(
        deadline=ExecutionDeadline(deadline_at_ms=9999999999999, source="managed-worker-checkpoint")
    )
    plan_envelope = create_task_envelope(
        "echo",
        task_id="managed-worker-composition-plan",
        payload={
            "message": "RAW_MANAGED_WORKER_PAYLOAD_SHOULD_NOT_APPEAR",
            "model_prompt": "MODEL_PROMPT_SHOULD_NOT_APPEAR",
        },
        budget=ResourceBudget(max_runtime_ms=1000, max_memory_mb=128, cpu_weight=25),
    )

    plan = create_managed_worker_execution_plan(
        descriptor,
        policy,
        plan_envelope,
        context=context,
        plan_id="managed-worker-composition-checkpoint",
    )
    plan_payload = plan.to_dict()
    serialized_contract = json.dumps(
        {
            "descriptor": descriptor.to_dict(),
            "plan": plan_payload,
            "service": service.describe(),
        },
        sort_keys=True,
    )

    assert plan.ok is True
    assert plan.status == "planned_contract_only"
    assert plan.contract_only is True
    assert plan.dry_run is True
    assert plan.launch_plan is not None
    assert plan.launch_plan.contract_only is True
    assert plan.launch_plan.dry_run is True
    assert plan.worker_kind == ManagedWorkerKind.CONTAINER
    assert plan_payload["starts_processes"] is False
    assert plan_payload["uses_network"] is False
    assert plan_payload["uses_gpu"] is False
    assert plan_payload["runs_shell"] is False
    assert plan_payload["starts_daemon"] is False
    assert plan_payload["real_container_execution"] is False
    assert plan_payload["real_vm_execution"] is False
    assert plan_payload["real_worker_implementation"] is False
    assert plan_payload["durable_worker_persistence"] is False
    assert plan.readiness.evidence["requires_substrate_governor_for_execution"] is True
    assert plan.readiness.evidence["requires_worker_registry_for_execution"] is True
    assert backend.execute_calls == 0
    assert governor.execute_calls == 0
    assert [worker.worker_id for worker in registry.descriptors()] == ["safe-local-1"]
    assert service.known_capabilities() == safe_capabilities
    assert ManagedWorkerKind.CONTAINER not in service.known_capabilities()
    assert ManagedWorkerKind.VM not in service.known_capabilities()
    assert service.status_for_task("managed-worker-composition-plan").status == ComputeTaskStatus.UNKNOWN
    assert service.status_store.describe()["stored_record_count"] == 0
    assert "future-managed-container" not in [worker.worker_id for worker in registry.descriptors()]
    assert "RAW_MANAGED_WORKER_PAYLOAD_SHOULD_NOT_APPEAR" not in serialized_contract
    assert "MODEL_PROMPT_SHOULD_NOT_APPEAR" not in serialized_contract
    assert "D:\\Francis\\private" not in serialized_contract
    assert "SHOULD_NOT_APPEAR" not in serialized_contract
    assert descriptor.to_dict()["metadata_summary"]["host_path"] == "non_default_summary_declared"
    assert descriptor.to_dict()["metadata_summary"]["api_token"] == "redacted_summary"

    execution = service.submit(
        create_task_envelope(
            "echo",
            task_id="managed-worker-composition-exec",
            trace_id="managed-worker-composition-trace",
            payload={"message": "service execution remains governed"},
        )
    )

    assert execution.status == ComputeTaskStatus.SUCCEEDED
    assert execution.record.worker_id == "safe-local-1"
    assert execution.receipt.worker_id == "safe-local-1"
    assert execution.receipt.function_name == "echo"
    assert execution.record.receipt_id == execution.receipt.receipt_id
    assert execution.record.status_write_attempted is True
    assert execution.record.status_write_succeeded is True
    assert service.status_for_task("managed-worker-composition-exec") == execution.record
    assert backend.execute_calls == 1
    assert governor.execute_calls == 1
    assert service.known_capabilities() == safe_capabilities
    assert [worker.worker_id for worker in registry.descriptors()] == ["safe-local-1"]


def test_binding_creates_contract_only_plan_without_changing_execution_path() -> None:
    binding = ManagedWorkerBinding(
        descriptor=_descriptor(),
        policy=_policy(),
        sandbox_profile=ManagedWorkerSandboxProfile(isolation_kind="future_container_boundary"),
    )

    plan = binding.create_execution_plan(_resource(), plan_id="managed-plan-binding")

    assert plan.ok is True
    assert binding.to_dict()["real_worker_implementation"] is False
    assert plan.sandbox_profile_summary["isolation_kind"] == "future_container_boundary"


def test_task_envelope_is_summarized_without_raw_payload_storage() -> None:
    envelope = TaskEnvelope(
        task_id="managed-task-payload",
        function_name="echo",
        payload={
            "message": "RAW_PAYLOAD_SHOULD_NOT_APPEAR",
            "model_prompt": "MODEL_PROMPT_SHOULD_NOT_APPEAR",
            "risk_level": "low",
        },
    )

    plan = _plan(resource=envelope, plan_id="managed-plan-payload")
    text = json.dumps(plan.to_dict(), sort_keys=True)

    assert plan.ok is True
    assert "RAW_PAYLOAD_SHOULD_NOT_APPEAR" not in text
    assert "MODEL_PROMPT_SHOULD_NOT_APPEAR" not in text
    assert plan.to_dict()["stores_payload"] is False
    assert plan.to_dict()["stores_output"] is False


def test_metadata_and_sandbox_summaries_do_not_store_paths_or_secrets() -> None:
    descriptor = _descriptor(
        metadata_summary={
            "host_path": "D:\\Francis\\private",
            "api_token": "token=SHOULD_NOT_APPEAR",
            "owner": "compute-substrate-tests",
        }
    )
    binding = ManagedWorkerBinding(
        descriptor=descriptor,
        policy=_policy(),
        sandbox_profile=ManagedWorkerSandboxProfile(filesystem_policy="D:\\Francis\\private"),
    )

    plan = binding.create_execution_plan(_resource(), plan_id="managed-plan-redaction")
    text = json.dumps({"descriptor": descriptor.to_dict(), "plan": plan.to_dict()}, sort_keys=True)

    assert "D:\\Francis\\private" not in text
    assert "SHOULD_NOT_APPEAR" not in text
    assert "token=SHOULD_NOT_APPEAR" not in text
    assert descriptor.to_dict()["metadata_summary"]["host_path"] == "non_default_summary_declared"
    assert descriptor.to_dict()["metadata_summary"]["api_token"] == "redacted_summary"
    assert plan.sandbox_profile_summary["filesystem_policy"] == "non_default_policy_declared"


def test_execution_plan_does_not_execute_backend_or_live_runtime_calls() -> None:
    source = inspect.getsource(worker_module)
    plan = _plan(plan_id="managed-plan-no-runtime")

    assert plan.ok is True
    assert "def execute(" not in source
    for forbidden in (
        "import subprocess",
        "os.system",
        "shell=True",
        "socket",
        "requests",
        "urllib",
        "create_task",
        "Popen",
        "docker",
        "podman",
        "qemu",
        "firecracker",
    ):
        assert forbidden not in source


def test_public_facade_exports_managed_worker_contracts() -> None:
    registry = InMemoryManagedWorkerRegistry()
    descriptor = _descriptor()
    policy = _policy()
    readiness = validate_managed_worker_policy(policy)
    registry_result = registry.register_descriptor(descriptor)
    capability_summary = registry.list_capability_summaries()[0]

    assert ManagedWorkerKind.CONTAINER == "container"
    assert ManagedWorkerBackendContract is not None
    assert ManagedWorkerRegistry is not None
    assert isinstance(registry, InMemoryManagedWorkerRegistry)
    assert isinstance(registry_result, ManagedWorkerRegistryResult)
    assert isinstance(capability_summary, ManagedWorkerCapabilitySummary)
    assert isinstance(descriptor.capabilities, ManagedWorkerCapabilities)
    assert isinstance(readiness, ManagedWorkerReadiness)
    assert create_managed_worker_execution_plan(descriptor, policy, _resource()).ok is True


def test_backend_contract_exposes_no_live_execute_run_or_spawn_method() -> None:
    contract_methods = set(ManagedWorkerBackendContract.__dict__)

    assert {"describe_contract", "validate_plan", "dry_run_plan"}.issubset(contract_methods)
    assert "execute" not in contract_methods
    assert "run" not in contract_methods
    assert "spawn" not in contract_methods
