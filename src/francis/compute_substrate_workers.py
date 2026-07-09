from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any, Protocol

from francis.compute_substrate_types import (
    _NO_FILESYSTEM_SCOPE,
    _now_ms,
    _risk_level,
    _risk_rank,
    _safe_text,
    _scope_tuple,
    ExecutionContext,
    ResourceBudget,
    TaskEnvelope,
)


class ManagedWorkerKind:
    LOCAL_SAFE = "local_safe"
    CONTAINER = "container"
    VM = "vm"
    MICROVM = "microvm"
    REMOTE = "remote"
    SIMULATION = "simulation"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

    @classmethod
    def allowed(cls) -> set[str]:
        return {
            cls.LOCAL_SAFE,
            cls.CONTAINER,
            cls.VM,
            cls.MICROVM,
            cls.REMOTE,
            cls.SIMULATION,
            cls.CUSTOM,
            cls.UNKNOWN,
        }


class ManagedWorkerContractViolation(ValueError):
    """Raised by callers that choose exception-style contract validation."""


@dataclass(frozen=True, slots=True)
class ManagedWorkerCapabilitySummary:
    worker_id: str
    capability_id: str
    worker_kind: str
    worker_enabled: bool
    worker_name: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", _contract_id(self.worker_id))
        object.__setattr__(self, "capability_id", _contract_id(self.capability_id))
        object.__setattr__(self, "worker_kind", _worker_kind(self.worker_kind))
        object.__setattr__(self, "worker_name", _bounded_text(self.worker_name, limit=120))

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "worker_name": self.worker_name,
            "worker_kind": self.worker_kind,
            "capability_id": self.capability_id,
            "worker_enabled": self.worker_enabled,
            "contract_only": True,
            "non_executable": True,
            "future_worker": True,
            "executable_substrate_capability": False,
            "registered_execution_backend": False,
            "real_worker_implementation": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerRegistryResult:
    ok: bool
    status: str
    worker_id: str = ""
    reason: str = ""
    descriptor: ManagedWorkerDescriptor | None = None

    @classmethod
    def registered(cls, descriptor: ManagedWorkerDescriptor) -> ManagedWorkerRegistryResult:
        return cls(
            ok=True,
            status="registered",
            worker_id=descriptor.worker_id,
            descriptor=descriptor,
        )

    @classmethod
    def denied(cls, reason: str, *, worker_id: str = "") -> ManagedWorkerRegistryResult:
        return cls(
            ok=False,
            status="denied",
            worker_id=_contract_id(worker_id),
            reason=_bounded_text(reason, limit=160) or "managed_worker_registry_denied",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "worker_id": self.worker_id,
            "reason": self.reason,
            "descriptor": _descriptor_summary(self.descriptor) if self.descriptor is not None else {},
            "contract_only": True,
            "non_executable": True,
            "durable": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
            "mutates_worker_registry": False,
            "registers_execution_backend": False,
            "real_worker_implementation": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerCapabilities:
    declared_capabilities: tuple[str, ...] = ()
    supports_cancellation: bool = True
    supports_deadline: bool = True
    supports_receipts: bool = True
    supports_status: bool = True
    supports_network: bool = False
    supports_gpu: bool = False
    supports_persistent_storage: bool = False
    supports_remote: bool = False
    supports_shell: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "declared_capabilities", _capability_tuple(self.declared_capabilities))
        object.__setattr__(self, "supports_shell", False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "declared_capabilities": list(self.declared_capabilities),
            "supports_cancellation": self.supports_cancellation,
            "supports_deadline": self.supports_deadline,
            "supports_receipts": self.supports_receipts,
            "supports_status": self.supports_status,
            "supports_network": self.supports_network,
            "supports_gpu": self.supports_gpu,
            "supports_persistent_storage": self.supports_persistent_storage,
            "supports_remote": self.supports_remote,
            "supports_shell": False,
            "real_worker_implementation": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerSandboxProfile:
    isolation_kind: str = "contract_only"
    filesystem_policy: str = "none"
    network_policy: str = "deny"
    gpu_policy: str = "deny"
    process_policy: str = "not_implemented"
    memory_policy: str = "validation_only"
    cpu_policy: str = "validation_only"
    timeout_policy: str = "cooperative_deadline"
    log_policy: str = "bounded_summary"
    secret_policy: str = "no_secret_storage"
    cleanup_policy: str = "not_applicable"
    receipt_policy: str = "required_through_substrate"
    status_policy: str = "required_through_substrate"

    def __post_init__(self) -> None:
        for field_name in (
            "isolation_kind",
            "filesystem_policy",
            "network_policy",
            "gpu_policy",
            "process_policy",
            "memory_policy",
            "cpu_policy",
            "timeout_policy",
            "log_policy",
            "secret_policy",
            "cleanup_policy",
            "receipt_policy",
            "status_policy",
        ):
            object.__setattr__(self, field_name, _policy_label(getattr(self, field_name)))

    def to_summary(self) -> dict[str, Any]:
        return {
            "isolation_kind": self.isolation_kind,
            "filesystem_policy": self.filesystem_policy,
            "network_policy": self.network_policy,
            "gpu_policy": self.gpu_policy,
            "process_policy": self.process_policy,
            "memory_policy": self.memory_policy,
            "cpu_policy": self.cpu_policy,
            "timeout_policy": self.timeout_policy,
            "log_policy": self.log_policy,
            "secret_policy": self.secret_policy,
            "cleanup_policy": self.cleanup_policy,
            "receipt_policy": self.receipt_policy,
            "status_policy": self.status_policy,
            "contract_only": True,
            "os_level_enforcement_implemented": False,
            "real_sandbox_implementation": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerDescriptor:
    worker_id: str
    name: str
    kind: str = ManagedWorkerKind.LOCAL_SAFE
    capabilities: ManagedWorkerCapabilities = field(default_factory=ManagedWorkerCapabilities)
    enabled: bool = True
    trust_tier: str = "local_internal"
    default_resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    max_resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    requires_approval_by_default: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    registered_at_ms: int = field(default_factory=_now_ms)
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", _contract_id(self.worker_id))
        object.__setattr__(self, "name", _bounded_text(self.name, limit=120))
        object.__setattr__(self, "kind", _worker_kind(self.kind))
        object.__setattr__(self, "trust_tier", _bounded_text(self.trust_tier, limit=80) or "local_internal")
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        object.__setattr__(self, "registered_at_ms", max(0, _int_ms(self.registered_at_ms)))
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    @property
    def declared_capabilities(self) -> tuple[str, ...]:
        return self.capabilities.declared_capabilities

    @property
    def supports_cancellation(self) -> bool:
        return self.capabilities.supports_cancellation

    @property
    def supports_deadline(self) -> bool:
        return self.capabilities.supports_deadline

    @property
    def supports_receipts(self) -> bool:
        return self.capabilities.supports_receipts

    @property
    def supports_status(self) -> bool:
        return self.capabilities.supports_status

    @property
    def supports_network(self) -> bool:
        return self.capabilities.supports_network

    @property
    def supports_gpu(self) -> bool:
        return self.capabilities.supports_gpu

    @property
    def supports_persistent_storage(self) -> bool:
        return self.capabilities.supports_persistent_storage

    @property
    def supports_remote(self) -> bool:
        return self.capabilities.supports_remote

    @property
    def supports_shell(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "name": self.name,
            "kind": self.kind,
            "enabled": self.enabled,
            "trust_tier": self.trust_tier,
            "declared_capabilities": list(self.declared_capabilities),
            "capabilities": self.capabilities.to_dict(),
            "default_resource_budget": _budget_summary(self.default_resource_budget),
            "max_resource_budget": _budget_summary(self.max_resource_budget),
            "requires_approval_by_default": self.requires_approval_by_default,
            "filesystem_scope": _scope_summary(self.filesystem_scope),
            "registered_at_ms": self.registered_at_ms,
            "metadata_summary": dict(self.metadata_summary),
            "real_worker_implementation": False,
            "stores_secrets": False,
            "stores_runtime_config": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerPolicy:
    allowed_capabilities: tuple[str, ...] = ()
    max_resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    allowed_worker_kinds: tuple[str, ...] = (ManagedWorkerKind.LOCAL_SAFE,)
    max_risk_level: str = "low"
    require_approval: bool = False
    allow_network: bool = False
    allow_gpu: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    require_receipt: bool = True
    require_status: bool = True
    require_deadline: bool = False
    require_cancellation_context: bool = False
    allow_persistent_storage: bool = False
    allow_remote: bool = False
    allow_shell: bool = False
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_capabilities", _capability_tuple(self.allowed_capabilities))
        object.__setattr__(self, "allowed_worker_kinds", _worker_kind_tuple(self.allowed_worker_kinds))
        object.__setattr__(self, "max_risk_level", _risk_level(self.max_risk_level))
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        object.__setattr__(self, "allow_shell", False)
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_capabilities": list(self.allowed_capabilities),
            "max_resource_budget": _budget_summary(self.max_resource_budget),
            "allowed_worker_kinds": list(self.allowed_worker_kinds),
            "max_risk_level": self.max_risk_level,
            "require_approval": self.require_approval,
            "allow_network": self.allow_network,
            "allow_gpu": self.allow_gpu,
            "filesystem_scope": _scope_summary(self.filesystem_scope),
            "require_receipt": self.require_receipt,
            "require_status": self.require_status,
            "require_deadline": self.require_deadline,
            "require_cancellation_context": self.require_cancellation_context,
            "allow_persistent_storage": self.allow_persistent_storage,
            "allow_remote": self.allow_remote,
            "allow_shell": False,
            "metadata_summary": dict(self.metadata_summary),
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerResourceEnvelope:
    task_id: str
    requested_capability: str
    resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    risk_level: str = "low"
    approval_required: bool = False
    approval_id: str = ""
    persistent_storage_requested: bool = False
    remote_execution_requested: bool = False
    shell_requested: bool = False
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _contract_id(self.task_id))
        object.__setattr__(self, "requested_capability", _contract_id(self.requested_capability))
        object.__setattr__(self, "risk_level", _risk_level(self.risk_level))
        object.__setattr__(self, "approval_id", _contract_id(self.approval_id) if self.approval_id else "")
        object.__setattr__(self, "created_at_ms", max(0, _int_ms(self.created_at_ms)))

    @classmethod
    def from_task_envelope(cls, envelope: TaskEnvelope) -> ManagedWorkerResourceEnvelope:
        return cls(
            task_id=envelope.task_id,
            requested_capability=envelope.function_name,
            resource_budget=envelope.budget,
            risk_level=_safe_text(envelope.payload.get("risk_level")) or "low",
            approval_required=envelope.budget.approval_required,
            approval_id=envelope.approval_id,
            created_at_ms=envelope.created_at_ms,
        )

    def to_summary(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "requested_capability": self.requested_capability,
            "resource_budget": _budget_summary(self.resource_budget),
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "approval_id_present": bool(self.approval_id),
            "persistent_storage_requested": self.persistent_storage_requested,
            "remote_execution_requested": self.remote_execution_requested,
            "shell_requested": self.shell_requested,
            "created_at_ms": self.created_at_ms,
            "stores_payload": False,
            "stores_output": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerReadiness:
    ready: bool
    reason: str
    checks: dict[str, bool] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def allowed(
        cls,
        *,
        reason: str = "managed_worker_contract_ready",
        checks: dict[str, bool] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> ManagedWorkerReadiness:
        return cls(ready=True, reason=reason, checks=checks or {}, evidence=evidence or {})

    @classmethod
    def denied(
        cls,
        reason: str,
        *,
        checks: dict[str, bool] | None = None,
        evidence: dict[str, Any] | None = None,
    ) -> ManagedWorkerReadiness:
        return cls(ready=False, reason=reason, checks=checks or {}, evidence=evidence or {})

    def raise_for_violation(self) -> None:
        if not self.ready:
            raise ManagedWorkerContractViolation(self.reason)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "reason": self.reason,
            "checks": dict(self.checks),
            "evidence": dict(self.evidence),
            "contract_only": True,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerLaunchPlan:
    """Contract-only launch description; it never starts a process or runtime."""

    plan_id: str
    worker_id: str
    worker_kind: str
    sandbox_profile_summary: dict[str, Any]
    execution_mode: str = "contract_only"
    dry_run: bool = True
    contract_only: bool = True
    created_at_ms: int = field(default_factory=_now_ms)
    denial_reason: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "plan_id", _contract_id(self.plan_id))
        object.__setattr__(self, "worker_id", _contract_id(self.worker_id))
        object.__setattr__(self, "worker_kind", _worker_kind(self.worker_kind))
        object.__setattr__(self, "sandbox_profile_summary", _summary_dict(self.sandbox_profile_summary))
        object.__setattr__(self, "execution_mode", _bounded_text(self.execution_mode, limit=80) or "contract_only")
        object.__setattr__(self, "created_at_ms", max(0, _int_ms(self.created_at_ms)))
        object.__setattr__(self, "denial_reason", _bounded_text(self.denial_reason, limit=160))

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind,
            "sandbox_profile_summary": dict(self.sandbox_profile_summary),
            "execution_mode": self.execution_mode,
            "dry_run": True,
            "contract_only": True,
            "created_at_ms": self.created_at_ms,
            "denial_reason": self.denial_reason,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
            "real_worker_implementation": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerExecutionPlan:
    """Contract-only execution description; it never executes backend work."""

    ok: bool
    status: str
    plan_id: str
    worker_id: str
    worker_kind: str
    task_id: str
    requested_capability: str
    approval_required: bool
    approval_id: str = ""
    denial_reason: str = ""
    resource_envelope: dict[str, Any] = field(default_factory=dict)
    sandbox_profile_summary: dict[str, Any] = field(default_factory=dict)
    execution_mode: str = "contract_only"
    dry_run: bool = True
    contract_only: bool = True
    readiness: ManagedWorkerReadiness = field(default_factory=ManagedWorkerReadiness.allowed)
    launch_plan: ManagedWorkerLaunchPlan | None = None
    created_at_ms: int = field(default_factory=_now_ms)

    @classmethod
    def denied(
        cls,
        *,
        reason: str,
        plan_id: str,
        descriptor: ManagedWorkerDescriptor | None = None,
        resource_envelope: ManagedWorkerResourceEnvelope | None = None,
        sandbox_profile: ManagedWorkerSandboxProfile | None = None,
    ) -> ManagedWorkerExecutionPlan:
        clean_plan_id = _contract_id(plan_id)
        worker_id = descriptor.worker_id if descriptor is not None else ""
        worker_kind = descriptor.kind if descriptor is not None else ManagedWorkerKind.UNKNOWN
        task_id = resource_envelope.task_id if resource_envelope is not None else ""
        capability = resource_envelope.requested_capability if resource_envelope is not None else ""
        approval_required = resource_envelope.approval_required if resource_envelope is not None else False
        readiness = ManagedWorkerReadiness.denied(reason)
        sandbox_summary = (sandbox_profile or ManagedWorkerSandboxProfile()).to_summary()
        launch_plan = ManagedWorkerLaunchPlan(
            plan_id=clean_plan_id,
            worker_id=worker_id,
            worker_kind=worker_kind,
            sandbox_profile_summary=sandbox_summary,
            denial_reason=reason,
        )
        return cls(
            ok=False,
            status="denied",
            plan_id=clean_plan_id,
            worker_id=worker_id,
            worker_kind=worker_kind,
            task_id=task_id,
            requested_capability=capability,
            approval_required=approval_required,
            approval_id=resource_envelope.approval_id if resource_envelope is not None else "",
            denial_reason=reason,
            resource_envelope=resource_envelope.to_summary() if resource_envelope is not None else {},
            sandbox_profile_summary=sandbox_summary,
            readiness=readiness,
            launch_plan=launch_plan,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "plan_id": self.plan_id,
            "worker_id": self.worker_id,
            "worker_kind": self.worker_kind,
            "task_id": self.task_id,
            "requested_capability": self.requested_capability,
            "approval_required": self.approval_required,
            "approval_id_present": bool(self.approval_id),
            "denial_reason": self.denial_reason,
            "resource_envelope": dict(self.resource_envelope),
            "sandbox_profile_summary": dict(self.sandbox_profile_summary),
            "execution_mode": self.execution_mode,
            "dry_run": True,
            "contract_only": True,
            "readiness": self.readiness.to_dict(),
            "launch_plan": self.launch_plan.to_dict() if self.launch_plan is not None else {},
            "created_at_ms": self.created_at_ms,
            "stores_payload": False,
            "stores_output": False,
            "stores_secrets": False,
            "stores_raw_model_prompt": False,
            "stores_broad_filesystem_paths": False,
            "writes_memory": False,
            "live_learning_persistence": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
            "os_level_cpu_memory_enforcement": False,
            "real_container_execution": False,
            "real_vm_execution": False,
            "real_worker_implementation": False,
            "durable_worker_persistence": False,
        }


@dataclass(frozen=True, slots=True)
class ManagedWorkerBinding:
    descriptor: ManagedWorkerDescriptor
    policy: ManagedWorkerPolicy = field(default_factory=ManagedWorkerPolicy)
    sandbox_profile: ManagedWorkerSandboxProfile = field(default_factory=ManagedWorkerSandboxProfile)

    def create_execution_plan(
        self,
        resource_envelope: ManagedWorkerResourceEnvelope | TaskEnvelope,
        *,
        context: ExecutionContext | None = None,
        plan_id: str | None = None,
    ) -> ManagedWorkerExecutionPlan:
        """Create a dry-run contract plan without executing or launching anything."""

        return create_managed_worker_execution_plan(
            self.descriptor,
            self.policy,
            resource_envelope,
            context=context,
            plan_id=plan_id,
            sandbox_profile=self.sandbox_profile,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "descriptor": self.descriptor.to_dict(),
            "policy": self.policy.to_dict(),
            "sandbox_profile": self.sandbox_profile.to_summary(),
            "contract_only": True,
            "real_worker_implementation": False,
        }


class ManagedWorkerBackendContract(Protocol):
    @property
    def descriptor(self) -> ManagedWorkerDescriptor: ...

    def describe_contract(self) -> dict[str, Any]: ...

    def validate_plan(self, plan: ManagedWorkerExecutionPlan) -> ManagedWorkerReadiness: ...

    def dry_run_plan(
        self,
        resource_envelope: ManagedWorkerResourceEnvelope | TaskEnvelope,
        *,
        context: ExecutionContext | None = None,
    ) -> ManagedWorkerExecutionPlan: ...


class ManagedWorkerRegistry(Protocol):
    def register_descriptor(self, descriptor: ManagedWorkerDescriptor) -> ManagedWorkerRegistryResult: ...

    def get_descriptor(self, worker_id: str) -> ManagedWorkerDescriptor | None: ...

    def list_descriptors(self) -> list[dict[str, Any]]: ...

    def list_capability_summaries(self) -> list[ManagedWorkerCapabilitySummary]: ...

    def validate_descriptor(self, descriptor: ManagedWorkerDescriptor) -> ManagedWorkerReadiness: ...

    def binding_for(
        self,
        worker_id: str,
        *,
        policy: ManagedWorkerPolicy | None = None,
        sandbox_profile: ManagedWorkerSandboxProfile | None = None,
    ) -> ManagedWorkerBinding | None: ...

    def describe(self) -> dict[str, Any]: ...


class InMemoryManagedWorkerRegistry:
    """Process-local registry for contract-only managed worker metadata."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ManagedWorkerDescriptor] = {}

    def register_descriptor(self, descriptor: ManagedWorkerDescriptor) -> ManagedWorkerRegistryResult:
        readiness = self.validate_descriptor(descriptor)
        if not readiness.ready:
            return ManagedWorkerRegistryResult.denied(readiness.reason, worker_id=descriptor.worker_id)
        if descriptor.worker_id in self._descriptors:
            return ManagedWorkerRegistryResult.denied("worker_already_registered", worker_id=descriptor.worker_id)
        self._descriptors[descriptor.worker_id] = descriptor
        return ManagedWorkerRegistryResult.registered(descriptor)

    def get_descriptor(self, worker_id: str) -> ManagedWorkerDescriptor | None:
        clean_id = _contract_id(worker_id)
        if not clean_id:
            return None
        return self._descriptors.get(clean_id)

    def list_descriptors(self) -> list[dict[str, Any]]:
        return [_descriptor_summary(descriptor) for descriptor in _sorted_descriptors(self._descriptors)]

    def list_capability_summaries(self) -> list[ManagedWorkerCapabilitySummary]:
        summaries: list[ManagedWorkerCapabilitySummary] = []
        for descriptor in _sorted_descriptors(self._descriptors):
            for capability in descriptor.declared_capabilities:
                summaries.append(
                    ManagedWorkerCapabilitySummary(
                        worker_id=descriptor.worker_id,
                        worker_name=descriptor.name,
                        worker_kind=descriptor.kind,
                        capability_id=capability,
                        worker_enabled=descriptor.enabled,
                    )
                )
        return sorted(summaries, key=lambda item: (item.worker_id, item.capability_id))

    def validate_descriptor(self, descriptor: ManagedWorkerDescriptor) -> ManagedWorkerReadiness:
        return validate_managed_worker_descriptor(descriptor)

    def binding_for(
        self,
        worker_id: str,
        *,
        policy: ManagedWorkerPolicy | None = None,
        sandbox_profile: ManagedWorkerSandboxProfile | None = None,
    ) -> ManagedWorkerBinding | None:
        descriptor = self.get_descriptor(worker_id)
        if descriptor is None:
            return None
        return ManagedWorkerBinding(
            descriptor=descriptor,
            policy=policy or _policy_from_descriptor(descriptor),
            sandbox_profile=sandbox_profile or ManagedWorkerSandboxProfile(),
        )

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.in_memory_managed_worker_registry",
            "registered_worker_count": len(self._descriptors),
            "registered_capability_count": sum(len(item.declared_capabilities) for item in self._descriptors.values()),
            "process_local": True,
            "durable": False,
            "contract_only": True,
            "non_executable": True,
            "metadata_only": True,
            "registers_execution_backends": False,
            "mutates_worker_registry": False,
            "submits_tasks": False,
            "mutates_approvals": False,
            "mutates_receipts": False,
            "mutates_status": False,
            "writes_memory": False,
            "live_learning_persistence": False,
            "real_worker_implementation": False,
            "real_container_execution": False,
            "real_vm_execution": False,
            "real_remote_execution": False,
            "real_simulation_execution": False,
            "starts_processes": False,
            "uses_network": False,
            "uses_gpu": False,
            "runs_shell": False,
            "starts_daemon": False,
            "os_level_cpu_memory_enforcement": False,
        }


def validate_managed_worker_descriptor(descriptor: ManagedWorkerDescriptor) -> ManagedWorkerReadiness:
    checks = {
        "safe_worker_id": bool(descriptor.worker_id),
        "name_present": bool(descriptor.name),
        "known_worker_kind": descriptor.kind in ManagedWorkerKind.allowed(),
        "declared_capabilities_present": bool(descriptor.declared_capabilities),
        "safe_declared_capabilities": all(_contract_id(item) == item for item in descriptor.declared_capabilities),
        "shell_not_supported": not descriptor.supports_shell,
        "metadata_bounded": len(descriptor.metadata_summary) <= 20,
    }
    if all(checks.values()):
        return ManagedWorkerReadiness.allowed(
            reason="managed_worker_descriptor_ready",
            checks=checks,
            evidence={
                "worker_id": descriptor.worker_id,
                "worker_kind": descriptor.kind,
                "capability_count": len(descriptor.declared_capabilities),
                "real_worker_implementation": False,
            },
        )
    return ManagedWorkerReadiness.denied(_first_failed(checks), checks=checks)


def validate_managed_worker_policy(policy: ManagedWorkerPolicy) -> ManagedWorkerReadiness:
    checks = {
        "allowed_capabilities_present": bool(policy.allowed_capabilities),
        "safe_allowed_capabilities": all(_contract_id(item) == item for item in policy.allowed_capabilities),
        "allowed_worker_kinds_present": bool(policy.allowed_worker_kinds),
        "safe_worker_kinds": all(kind in ManagedWorkerKind.allowed() for kind in policy.allowed_worker_kinds),
        "shell_not_allowed": not policy.allow_shell,
    }
    if all(checks.values()):
        return ManagedWorkerReadiness.allowed(
            reason="managed_worker_policy_ready",
            checks=checks,
            evidence={
                "allowed_worker_kinds": list(policy.allowed_worker_kinds),
                "allowed_capability_count": len(policy.allowed_capabilities),
                "os_level_enforcement_implemented": False,
            },
        )
    return ManagedWorkerReadiness.denied(_first_failed(checks), checks=checks)


def create_managed_worker_execution_plan(
    descriptor: ManagedWorkerDescriptor,
    policy: ManagedWorkerPolicy,
    resource_envelope: ManagedWorkerResourceEnvelope | TaskEnvelope,
    *,
    context: ExecutionContext | None = None,
    plan_id: str | None = None,
    sandbox_profile: ManagedWorkerSandboxProfile | None = None,
) -> ManagedWorkerExecutionPlan:
    """Build a contract-only plan; this function never executes worker code."""

    profile = sandbox_profile or ManagedWorkerSandboxProfile()
    resolved_plan_id = plan_id or f"managed_worker_plan_{uuid.uuid4().hex[:12]}"
    if not _contract_id(resolved_plan_id):
        return ManagedWorkerExecutionPlan.denied(
            reason="unsafe_plan_id",
            plan_id="",
            descriptor=descriptor,
            resource_envelope=_resource_envelope(resource_envelope),
            sandbox_profile=profile,
        )

    resource = _resource_envelope(resource_envelope)
    descriptor_ready = validate_managed_worker_descriptor(descriptor)
    if not descriptor_ready.ready:
        return ManagedWorkerExecutionPlan.denied(
            reason=descriptor_ready.reason,
            plan_id=resolved_plan_id,
            descriptor=descriptor,
            resource_envelope=resource,
            sandbox_profile=profile,
        )
    policy_ready = validate_managed_worker_policy(policy)
    if not policy_ready.ready:
        return ManagedWorkerExecutionPlan.denied(
            reason=policy_ready.reason,
            plan_id=resolved_plan_id,
            descriptor=descriptor,
            resource_envelope=resource,
            sandbox_profile=profile,
        )

    denial = _plan_denial(descriptor, policy, resource, context)
    if denial:
        return ManagedWorkerExecutionPlan.denied(
            reason=denial,
            plan_id=resolved_plan_id,
            descriptor=descriptor,
            resource_envelope=resource,
            sandbox_profile=profile,
        )

    sandbox_summary = profile.to_summary()
    launch_plan = ManagedWorkerLaunchPlan(
        plan_id=resolved_plan_id,
        worker_id=descriptor.worker_id,
        worker_kind=descriptor.kind,
        sandbox_profile_summary=sandbox_summary,
    )
    readiness = ManagedWorkerReadiness.allowed(
        reason="managed_worker_execution_plan_ready",
        checks={
            "descriptor_ready": True,
            "policy_ready": True,
            "budget_within_policy": True,
            "approval_requirement_preserved": True,
            "contract_only": True,
        },
        evidence={
            "uses_task_envelope": True,
            "uses_resource_budget": True,
            "requires_substrate_governor_for_execution": True,
            "requires_worker_registry_for_execution": True,
            "requires_receipts_for_execution": policy.require_receipt,
            "requires_status_for_execution": policy.require_status,
            "real_worker_implementation": False,
        },
    )
    return ManagedWorkerExecutionPlan(
        ok=True,
        status="planned_contract_only",
        plan_id=resolved_plan_id,
        worker_id=descriptor.worker_id,
        worker_kind=descriptor.kind,
        task_id=resource.task_id,
        requested_capability=resource.requested_capability,
        approval_required=resource.approval_required,
        approval_id=resource.approval_id,
        resource_envelope=resource.to_summary(),
        sandbox_profile_summary=sandbox_summary,
        readiness=readiness,
        launch_plan=launch_plan,
        created_at_ms=_now_ms(),
    )


def _plan_denial(
    descriptor: ManagedWorkerDescriptor,
    policy: ManagedWorkerPolicy,
    resource: ManagedWorkerResourceEnvelope,
    context: ExecutionContext | None,
) -> str:
    if not resource.task_id:
        return "unsafe_task_id"
    if not resource.requested_capability:
        return "unsafe_capability_id"
    if not descriptor.enabled:
        return "worker_disabled"
    if descriptor.kind not in policy.allowed_worker_kinds:
        return "worker_kind_not_allowed"
    if resource.requested_capability not in descriptor.declared_capabilities:
        return "capability_not_declared"
    if resource.requested_capability not in policy.allowed_capabilities:
        return "capability_not_allowed"
    if _risk_rank(resource.risk_level) > _risk_rank(policy.max_risk_level):
        return "risk_exceeds_worker_policy"

    descriptor_budget_denial = _budget_denial(resource.resource_budget, descriptor.max_resource_budget)
    if descriptor_budget_denial:
        return "resource_budget_exceeds_worker_descriptor"

    budget_denial = _budget_denial(resource.resource_budget, policy.max_resource_budget)
    if budget_denial:
        return "resource_budget_exceeds_worker_policy"

    if resource.resource_budget.allow_network and not policy.allow_network:
        return "network_not_allowed"
    if resource.resource_budget.allow_network and not descriptor.supports_network:
        return "network_support_required"
    if resource.resource_budget.allow_gpu and not policy.allow_gpu:
        return "gpu_not_allowed"
    if resource.resource_budget.allow_gpu and not descriptor.supports_gpu:
        return "gpu_support_required"
    if any(scope not in policy.filesystem_scope for scope in resource.resource_budget.filesystem_scope):
        return "filesystem_scope_not_allowed"
    if any(scope not in descriptor.filesystem_scope for scope in resource.resource_budget.filesystem_scope):
        return "filesystem_scope_not_supported"

    if resource.persistent_storage_requested and not policy.allow_persistent_storage:
        return "persistent_storage_not_allowed"
    if resource.persistent_storage_requested and not descriptor.supports_persistent_storage:
        return "persistent_storage_support_required"
    if resource.remote_execution_requested and not policy.allow_remote:
        return "remote_execution_not_allowed"
    if resource.remote_execution_requested and not descriptor.supports_remote:
        return "remote_execution_support_required"
    if resource.shell_requested or descriptor.supports_shell or policy.allow_shell:
        return "shell_not_allowed"

    approval_required = descriptor.requires_approval_by_default or policy.require_approval
    if approval_required and not resource.approval_required:
        return "approval_required_downgrade"
    if policy.require_deadline and (context is None or not context.deadline.is_configured()):
        return "deadline_required"
    if policy.require_cancellation_context and context is None:
        return "cancellation_context_required"
    if policy.require_receipt and not descriptor.supports_receipts:
        return "receipt_support_required"
    if policy.require_status and not descriptor.supports_status:
        return "status_support_required"
    return ""


def _resource_envelope(value: ManagedWorkerResourceEnvelope | TaskEnvelope) -> ManagedWorkerResourceEnvelope:
    if isinstance(value, ManagedWorkerResourceEnvelope):
        return value
    return ManagedWorkerResourceEnvelope.from_task_envelope(value)


def _policy_from_descriptor(descriptor: ManagedWorkerDescriptor) -> ManagedWorkerPolicy:
    return ManagedWorkerPolicy(
        allowed_capabilities=descriptor.declared_capabilities,
        max_resource_budget=descriptor.max_resource_budget,
        allowed_worker_kinds=(descriptor.kind,),
        require_approval=descriptor.requires_approval_by_default,
        allow_network=descriptor.supports_network,
        allow_gpu=descriptor.supports_gpu,
        filesystem_scope=descriptor.filesystem_scope,
        allow_persistent_storage=descriptor.supports_persistent_storage,
        allow_remote=descriptor.supports_remote,
        allow_shell=False,
    )


def _sorted_descriptors(descriptors: dict[str, ManagedWorkerDescriptor]) -> list[ManagedWorkerDescriptor]:
    return sorted(descriptors.values(), key=lambda item: item.worker_id)


def _descriptor_summary(descriptor: ManagedWorkerDescriptor | None) -> dict[str, Any]:
    if descriptor is None:
        return {}
    return {
        "worker_id": descriptor.worker_id,
        "name": descriptor.name,
        "kind": descriptor.kind,
        "enabled": descriptor.enabled,
        "status": "disabled" if not descriptor.enabled else "registered_contract_only",
        "declared_capabilities": list(descriptor.declared_capabilities),
        "declared_capability_count": len(descriptor.declared_capabilities),
        "trust_tier": descriptor.trust_tier,
        "default_resource_budget": _budget_summary(descriptor.default_resource_budget),
        "max_resource_budget": _budget_summary(descriptor.max_resource_budget),
        "requires_approval_by_default": descriptor.requires_approval_by_default,
        "filesystem_scope": _scope_summary(descriptor.filesystem_scope),
        "registered_at_ms": descriptor.registered_at_ms,
        "metadata_summary": dict(descriptor.metadata_summary),
        "contract_only": True,
        "metadata_only": True,
        "non_executable": True,
        "future_worker": True,
        "executable_substrate_worker": False,
        "executable_substrate_capability": False,
        "registered_execution_backend": False,
        "real_worker_implementation": False,
        "durable_worker_persistence": False,
        "starts_processes": False,
        "uses_network": False,
        "uses_gpu": False,
        "runs_shell": False,
        "starts_daemon": False,
        "stores_payload": False,
        "stores_output": False,
        "stores_secrets": False,
        "stores_runtime_config": False,
        "writes_memory": False,
    }


def _budget_denial(budget: ResourceBudget, maximum: ResourceBudget) -> str:
    if budget.max_runtime_ms > maximum.max_runtime_ms:
        return "max_runtime_ms"
    if budget.max_memory_mb > maximum.max_memory_mb:
        return "max_memory_mb"
    if budget.cpu_weight > maximum.cpu_weight:
        return "cpu_weight"
    if budget.max_compute_units > maximum.max_compute_units:
        return "max_compute_units"
    return ""


def _budget_summary(budget: ResourceBudget) -> dict[str, Any]:
    payload = budget.to_dict()
    payload["filesystem_scope"] = _scope_summary(payload.get("filesystem_scope"))
    return payload


def _scope_summary(value: Any) -> list[str]:
    scopes = _scope_tuple(value)
    return ["none"] if scopes == _NO_FILESYSTEM_SCOPE else ["non_default_scope_requested"]


def _worker_kind(value: Any) -> str:
    text = _safe_text(value).lower()
    return text if text in ManagedWorkerKind.allowed() else ManagedWorkerKind.UNKNOWN


def _worker_kind_tuple(value: Any) -> tuple[str, ...]:
    try:
        items = list(value)
    except TypeError:
        return ()
    allowed = ManagedWorkerKind.allowed()
    return tuple(sorted({text for item in items if (text := _safe_text(item).lower()) in allowed}))


def _capability_tuple(value: Any) -> tuple[str, ...]:
    try:
        items = list(value)
    except TypeError:
        return ()
    return tuple(sorted({_contract_id(item) for item in items if _contract_id(item)}))


def _contract_id(value: Any) -> str:
    text = _safe_text(value)
    if not text or len(text) > 160 or text in {".", ".."} or ".." in text:
        return ""
    if all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text
    return ""


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return _safe_text(value)[:limit]


def _policy_label(value: Any) -> str:
    text = _safe_text(value).lower()
    if not text:
        return "not_specified"
    if len(text) <= 80 and all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text
    return "non_default_policy_declared"


def _metadata_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for raw_key, raw_value in list(value.items())[:20]:
        key = _bounded_text(raw_key, limit=80)
        if not key:
            continue
        if _summary_key_sensitive(key):
            summary[key] = "redacted_summary"
        elif isinstance(raw_value, bool | int | float):
            summary[key] = raw_value
        else:
            summary[key] = _summary_text(raw_value)
    return summary


def _summary_dict(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for raw_key, raw_value in list(value.items())[:40]:
        key = _bounded_text(raw_key, limit=80)
        if not key:
            continue
        if isinstance(raw_value, bool | int | float):
            summary[key] = raw_value
        elif isinstance(raw_value, list | tuple):
            summary[key] = [_summary_text(item, limit=120) for item in raw_value[:20]]
        else:
            summary[key] = _summary_text(raw_value)
    return summary


def _summary_key_sensitive(key: str) -> bool:
    normalized = key.lower()
    return any(
        marker in normalized
        for marker in (
            "secret",
            "token",
            "credential",
            "password",
            "api_key",
            "apikey",
            "environment",
            "env",
            "username",
            "user_name",
            "user",
        )
    )


def _summary_text(value: Any, *, limit: int = 160) -> str:
    text = _safe_text(value)
    normalized = text.lower()
    if any(marker in normalized for marker in ("secret", "token=", "credential", "password", "api_key", "apikey")):
        return "redacted_summary"
    if _looks_like_host_path(text):
        return "non_default_summary_declared"
    return text[:limit]


def _looks_like_host_path(text: str) -> bool:
    if "\\" in text or "/" in text:
        return True
    if len(text) >= 2 and text[1] == ":" and text[0].isalpha():
        return True
    return False


def _int_ms(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return _now_ms()


def _first_failed(checks: dict[str, bool]) -> str:
    return next((name for name, passed in checks.items() if not passed), "managed_worker_contract_not_ready")
