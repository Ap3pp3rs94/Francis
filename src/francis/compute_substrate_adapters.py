from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from francis.compute_substrate_service import ComputeSubstrateService, ComputeSubmission, ComputeSubmissionResult
from francis.compute_substrate_types import (
    _NO_FILESYSTEM_SCOPE,
    _now_ms,
    _risk_level,
    _risk_rank,
    _safe_text,
    _scope_tuple,
    ApprovalGrant,
    ExecutionContext,
    ResourceBudget,
    TaskEnvelope,
)


class ComputeAdapterKind:
    UNREAL = "unreal"
    VSC1 = "vsc1"
    DESKTOP_LENS = "desktop_lens"
    AVATAR = "avatar"
    VOICE = "voice"
    VM_CONTAINER = "vm_container"
    REMOTE_WORKER = "remote_worker"
    SIMULATION = "simulation"
    INTERNAL = "internal"
    CUSTOM = "custom"
    UNKNOWN = "unknown"

    @classmethod
    def allowed(cls) -> set[str]:
        return {
            cls.UNREAL,
            cls.VSC1,
            cls.DESKTOP_LENS,
            cls.AVATAR,
            cls.VOICE,
            cls.VM_CONTAINER,
            cls.REMOTE_WORKER,
            cls.SIMULATION,
            cls.INTERNAL,
            cls.CUSTOM,
            cls.UNKNOWN,
        }


@dataclass(frozen=True, slots=True)
class ComputeAdapterDescriptor:
    adapter_id: str
    adapter_kind: str
    name: str
    declared_capabilities: tuple[str, ...]
    enabled: bool = True
    trust_tier: str = "local_internal"
    default_resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    requires_approval_by_default: bool = False
    allow_network: bool = False
    allow_gpu: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    registered_at_ms: int = field(default_factory=_now_ms)
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "adapter_id", _contract_id(self.adapter_id))
        object.__setattr__(self, "adapter_kind", _adapter_kind(self.adapter_kind))
        object.__setattr__(self, "name", _bounded_text(self.name, limit=120))
        object.__setattr__(self, "declared_capabilities", _capability_tuple(self.declared_capabilities))
        object.__setattr__(self, "trust_tier", _bounded_text(self.trust_tier, limit=80) or "local_internal")
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        object.__setattr__(self, "registered_at_ms", max(0, int(self.registered_at_ms)))
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_kind": self.adapter_kind,
            "name": self.name,
            "enabled": self.enabled,
            "declared_capabilities": list(self.declared_capabilities),
            "trust_tier": self.trust_tier,
            "default_resource_budget": _budget_summary(self.default_resource_budget),
            "requires_approval_by_default": self.requires_approval_by_default,
            "allow_network": self.allow_network,
            "allow_gpu": self.allow_gpu,
            "filesystem_scope": _scope_summary(self.filesystem_scope),
            "registered_at_ms": self.registered_at_ms,
            "metadata_summary": dict(self.metadata_summary),
            "real_adapter_implementation": False,
            "stores_secrets": False,
        }


@dataclass(frozen=True, slots=True)
class ComputeAdapterPolicy:
    allowed_capabilities: tuple[str, ...]
    max_resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    allowed_worker_ids: tuple[str, ...] = ()
    max_risk_level: str = "low"
    require_approval: bool = False
    allow_network: bool = False
    allow_gpu: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    allow_cancellation_context: bool = True
    allow_deadline_context: bool = True
    status_visibility: str = "bounded_summary"
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_capabilities", _capability_tuple(self.allowed_capabilities))
        object.__setattr__(self, "allowed_worker_ids", _id_tuple(self.allowed_worker_ids))
        object.__setattr__(self, "max_risk_level", _risk_level(self.max_risk_level))
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        object.__setattr__(self, "status_visibility", _bounded_text(self.status_visibility, limit=80))
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed_capabilities": list(self.allowed_capabilities),
            "max_resource_budget": _budget_summary(self.max_resource_budget),
            "allowed_worker_ids": list(self.allowed_worker_ids),
            "max_risk_level": self.max_risk_level,
            "require_approval": self.require_approval,
            "allow_network": self.allow_network,
            "allow_gpu": self.allow_gpu,
            "filesystem_scope": _scope_summary(self.filesystem_scope),
            "allow_cancellation_context": self.allow_cancellation_context,
            "allow_deadline_context": self.allow_deadline_context,
            "status_visibility": self.status_visibility,
            "metadata_summary": dict(self.metadata_summary),
        }


@dataclass(frozen=True, slots=True)
class ComputeAdapterRequest:
    request_id: str
    adapter_id: str
    requested_capability: str
    task_type: str = "generic_compute_request"
    intent_summary: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    payload_summary: str = ""
    resource_budget: ResourceBudget = field(default_factory=ResourceBudget)
    risk_level: str = "low"
    approval_required: bool = False
    approval_id: str = ""
    approval_grant: ApprovalGrant | None = None
    context: ExecutionContext | None = None
    correlation_id: str = ""
    trace_id: str = ""
    actor: str = "local.operator"
    created_at_ms: int = field(default_factory=_now_ms)
    metadata_summary: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _contract_id(self.request_id))
        object.__setattr__(self, "adapter_id", _contract_id(self.adapter_id))
        object.__setattr__(self, "requested_capability", _safe_text(self.requested_capability))
        object.__setattr__(self, "task_type", _bounded_text(self.task_type, limit=120))
        object.__setattr__(self, "intent_summary", _bounded_text(self.intent_summary))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "payload_summary", _bounded_text(self.payload_summary))
        object.__setattr__(self, "risk_level", _risk_level(self.risk_level))
        object.__setattr__(self, "approval_id", _contract_id(self.approval_id) if self.approval_id else "")
        object.__setattr__(self, "correlation_id", _contract_id(self.correlation_id) if self.correlation_id else "")
        object.__setattr__(self, "trace_id", _contract_id(self.trace_id) if self.trace_id else "")
        object.__setattr__(self, "actor", _bounded_text(self.actor, limit=120) or "local.operator")
        object.__setattr__(self, "created_at_ms", max(0, int(self.created_at_ms)))
        object.__setattr__(self, "metadata_summary", _metadata_summary(self.metadata_summary))

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "adapter_id": self.adapter_id,
            "requested_capability": self.requested_capability,
            "task_type": self.task_type,
            "intent_summary": self.intent_summary,
            "payload_summary": self.payload_summary,
            "payload_present": bool(self.payload),
            "resource_budget": _budget_summary(self.resource_budget),
            "risk_level": self.risk_level,
            "approval_required": self.approval_required,
            "approval_id": self.approval_id,
            "approval_grant_present": self.approval_grant is not None,
            "has_execution_context": self.context is not None,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "actor": self.actor,
            "created_at_ms": self.created_at_ms,
            "metadata_summary": dict(self.metadata_summary),
            "stores_payload": False,
            "durable_adapter_persistence": False,
        }


@dataclass(frozen=True, slots=True)
class ComputeAdapterSubmissionResult:
    ok: bool
    accepted: bool
    status: str
    request_id: str
    adapter_id: str
    adapter_kind: str
    denial_reason: str = ""
    task_id: str = ""
    correlation_id: str = ""
    compute_status: str = ""
    receipt_id: str = ""
    receipt_persisted: bool = False
    approval_required: bool = False
    approval_satisfied: bool = False
    approval_consumed: bool = False
    cancellation_requested: bool = False
    timed_out: bool = False
    created_at_ms: int = field(default_factory=_now_ms)
    submitted_at_ms: int = 0
    completed_at_ms: int = 0
    submission_result: ComputeSubmissionResult | None = None

    @classmethod
    def denied(
        cls,
        request: ComputeAdapterRequest,
        *,
        reason: str,
        adapter_kind: str = ComputeAdapterKind.UNKNOWN,
    ) -> ComputeAdapterSubmissionResult:
        now_ms = _now_ms()
        return cls(
            ok=False,
            accepted=False,
            status="denied",
            request_id=request.request_id,
            adapter_id=request.adapter_id,
            adapter_kind=adapter_kind,
            denial_reason=reason,
            created_at_ms=request.created_at_ms,
            completed_at_ms=now_ms,
        )

    @classmethod
    def from_submission(
        cls,
        request: ComputeAdapterRequest,
        descriptor: ComputeAdapterDescriptor,
        submission_result: ComputeSubmissionResult,
    ) -> ComputeAdapterSubmissionResult:
        record = submission_result.record
        return cls(
            ok=submission_result.ok,
            accepted=True,
            status=submission_result.status,
            request_id=request.request_id,
            adapter_id=descriptor.adapter_id,
            adapter_kind=descriptor.adapter_kind,
            task_id=submission_result.task_id,
            correlation_id=submission_result.correlation_id,
            compute_status=submission_result.status,
            receipt_id=submission_result.receipt.receipt_id,
            receipt_persisted=submission_result.receipt.persisted,
            approval_required=record.approval_required,
            approval_satisfied=record.approval_satisfied,
            approval_consumed=record.approval_consumed,
            cancellation_requested=record.cancellation_requested,
            timed_out=record.timed_out,
            created_at_ms=request.created_at_ms,
            submitted_at_ms=record.created_at_ms,
            completed_at_ms=record.updated_at_ms,
            submission_result=submission_result,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "accepted": self.accepted,
            "status": self.status,
            "request_id": self.request_id,
            "adapter_id": self.adapter_id,
            "adapter_kind": self.adapter_kind,
            "denial_reason": self.denial_reason,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "compute_status": self.compute_status,
            "receipt_id": self.receipt_id,
            "receipt_persisted": self.receipt_persisted,
            "approval_required": self.approval_required,
            "approval_satisfied": self.approval_satisfied,
            "approval_consumed": self.approval_consumed,
            "cancellation_requested": self.cancellation_requested,
            "timed_out": self.timed_out,
            "created_at_ms": self.created_at_ms,
            "submitted_at_ms": self.submitted_at_ms,
            "completed_at_ms": self.completed_at_ms,
            "stores_payload": False,
            "stores_output": False,
            "durable_adapter_persistence": False,
            "background_execution": False,
            "real_adapter_implementation": False,
        }


class ComputeAdapterRegistry(Protocol):
    def register(
        self,
        descriptor: ComputeAdapterDescriptor,
        policy: ComputeAdapterPolicy | None = None,
    ) -> ComputeAdapterDescriptor: ...

    def get(self, adapter_id: str) -> ComputeAdapterDescriptor | None: ...

    def policy_for(self, adapter_id: str) -> ComputeAdapterPolicy | None: ...

    def descriptors(self) -> list[ComputeAdapterDescriptor]: ...

    def describe(self) -> dict[str, Any]: ...


class InMemoryComputeAdapterRegistry:
    """Process-local adapter contract registry; it does not implement adapters."""

    def __init__(self) -> None:
        self._descriptors: dict[str, ComputeAdapterDescriptor] = {}
        self._policies: dict[str, ComputeAdapterPolicy] = {}

    def register(
        self,
        descriptor: ComputeAdapterDescriptor,
        policy: ComputeAdapterPolicy | None = None,
    ) -> ComputeAdapterDescriptor:
        if not descriptor.adapter_id:
            raise ValueError("adapter_id_invalid")
        if descriptor.adapter_id in self._descriptors:
            raise ValueError("adapter_already_registered")
        if not descriptor.declared_capabilities:
            raise ValueError("adapter_requires_declared_capabilities")
        self._descriptors[descriptor.adapter_id] = descriptor
        self._policies[descriptor.adapter_id] = policy or _policy_from_descriptor(descriptor)
        return descriptor

    def get(self, adapter_id: str) -> ComputeAdapterDescriptor | None:
        return self._descriptors.get(_contract_id(adapter_id))

    def policy_for(self, adapter_id: str) -> ComputeAdapterPolicy | None:
        return self._policies.get(_contract_id(adapter_id))

    def descriptors(self) -> list[ComputeAdapterDescriptor]:
        return list(self._descriptors.values())

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.in_memory_adapter_registry",
            "registered_adapter_count": len(self._descriptors),
            "durable": False,
            "real_adapter_implementation": False,
            "stores_payload": False,
            "stores_output": False,
            "writes_memory": False,
            "background_execution": False,
        }


class ComputeAdapterGateway:
    """Validates adapter obligations before submitting through ComputeSubstrateService."""

    def __init__(
        self,
        *,
        service: ComputeSubstrateService | None = None,
        adapter_registry: ComputeAdapterRegistry | None = None,
    ) -> None:
        self.service = service or ComputeSubstrateService()
        self.adapter_registry = adapter_registry or InMemoryComputeAdapterRegistry()

    def submit(self, request: ComputeAdapterRequest) -> ComputeAdapterSubmissionResult:
        descriptor, policy, denial = self._validate(request)
        if denial:
            adapter_kind = descriptor.adapter_kind if descriptor is not None else ComputeAdapterKind.UNKNOWN
            return ComputeAdapterSubmissionResult.denied(request, reason=denial, adapter_kind=adapter_kind)
        if descriptor is None or policy is None:
            return ComputeAdapterSubmissionResult.denied(request, reason="unknown_adapter")

        envelope = _request_to_envelope(request, descriptor=descriptor, policy=policy)
        submission_result = self.service.submit(ComputeSubmission(envelope=envelope, context=request.context))
        return ComputeAdapterSubmissionResult.from_submission(request, descriptor, submission_result)

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.adapter_gateway",
            "submission_mode": "synchronous_in_process",
            "uses_compute_substrate_service": True,
            "no_api_route": True,
            "no_background_worker": True,
            "real_adapter_implementation": False,
            "durable_adapter_persistence": False,
            "stores_payload": False,
            "stores_output": False,
            "writes_memory": False,
        }

    def _validate(
        self,
        request: ComputeAdapterRequest,
    ) -> tuple[ComputeAdapterDescriptor | None, ComputeAdapterPolicy | None, str]:
        if not request.request_id:
            return None, None, "invalid_request_id"
        if not request.adapter_id:
            return None, None, "invalid_adapter_id"

        descriptor = self.adapter_registry.get(request.adapter_id)
        if descriptor is None:
            return None, None, "unknown_adapter"
        if not descriptor.enabled:
            return descriptor, None, "adapter_disabled"

        capability = _safe_text(request.requested_capability)
        if not capability or capability not in self._known_compute_capabilities():
            return descriptor, None, "unknown_capability"
        if capability not in descriptor.declared_capabilities:
            return descriptor, None, "capability_not_declared"

        policy = self.adapter_registry.policy_for(request.adapter_id)
        if policy is None:
            return descriptor, None, "adapter_policy_missing"
        if policy.allowed_capabilities and capability not in policy.allowed_capabilities:
            return descriptor, policy, "capability_not_allowed"

        if _risk_rank(request.risk_level) > _risk_rank(policy.max_risk_level):
            return descriptor, policy, "risk_exceeds_adapter_policy"

        budget_denial = _budget_denial(request.resource_budget, policy)
        if budget_denial:
            return descriptor, policy, budget_denial

        approval_required_by_contract = descriptor.requires_approval_by_default or policy.require_approval
        if approval_required_by_contract and not request.approval_required:
            return descriptor, policy, "approval_required_downgrade"

        if request.context is not None:
            if request.context.cancellation_token.cancel_requested and not policy.allow_cancellation_context:
                return descriptor, policy, "cancellation_context_not_allowed"
            if request.context.deadline.is_configured() and not policy.allow_deadline_context:
                return descriptor, policy, "deadline_context_not_allowed"

        return descriptor, policy, ""

    def _known_compute_capabilities(self) -> set[str]:
        return set(self.service.known_capabilities())


def _policy_from_descriptor(descriptor: ComputeAdapterDescriptor) -> ComputeAdapterPolicy:
    return ComputeAdapterPolicy(
        allowed_capabilities=descriptor.declared_capabilities,
        max_resource_budget=descriptor.default_resource_budget,
        max_risk_level="low",
        require_approval=descriptor.requires_approval_by_default,
        allow_network=descriptor.allow_network,
        allow_gpu=descriptor.allow_gpu,
        filesystem_scope=descriptor.filesystem_scope,
    )


def _request_to_envelope(
    request: ComputeAdapterRequest,
    *,
    descriptor: ComputeAdapterDescriptor,
    policy: ComputeAdapterPolicy,
) -> TaskEnvelope:
    approval_required = request.approval_required or descriptor.requires_approval_by_default or policy.require_approval
    budget = replace(request.resource_budget, approval_required=approval_required)
    payload = dict(request.payload)
    payload["risk_level"] = request.risk_level
    trace_id = request.trace_id or request.correlation_id or request.request_id
    approval_id = request.approval_id
    if not approval_id and request.approval_grant is not None:
        approval_id = request.approval_grant.approval_id
    return TaskEnvelope(
        task_id=request.request_id,
        function_name=request.requested_capability,
        payload=payload,
        budget=budget,
        actor=request.actor or f"adapter:{descriptor.adapter_id}",
        trace_id=trace_id,
        approval_id=approval_id,
    )


def _budget_denial(budget: ResourceBudget, policy: ComputeAdapterPolicy) -> str:
    maximum = policy.max_resource_budget
    if budget.max_runtime_ms > maximum.max_runtime_ms:
        return "resource_budget_exceeds_adapter_policy"
    if budget.max_memory_mb > maximum.max_memory_mb:
        return "resource_budget_exceeds_adapter_policy"
    if budget.cpu_weight > maximum.cpu_weight:
        return "resource_budget_exceeds_adapter_policy"
    if budget.max_compute_units > maximum.max_compute_units:
        return "resource_budget_exceeds_adapter_policy"
    if budget.allow_network and not policy.allow_network:
        return "network_not_allowed"
    if budget.allow_gpu and not policy.allow_gpu:
        return "gpu_not_allowed"
    if any(scope not in policy.filesystem_scope for scope in budget.filesystem_scope):
        return "filesystem_scope_not_allowed"
    return ""


def _budget_summary(budget: ResourceBudget) -> dict[str, Any]:
    payload = budget.to_dict()
    payload["filesystem_scope"] = _scope_summary(payload.get("filesystem_scope"))
    return payload


def _scope_summary(value: Any) -> list[str]:
    scopes = _scope_tuple(value)
    return ["none"] if scopes == _NO_FILESYSTEM_SCOPE else ["non_default_scope_requested"]


def _adapter_kind(value: Any) -> str:
    text = _safe_text(value).lower()
    return text if text in ComputeAdapterKind.allowed() else ComputeAdapterKind.UNKNOWN


def _capability_tuple(value: Any) -> tuple[str, ...]:
    try:
        items = list(value)
    except TypeError:
        return ()
    return tuple(sorted({_safe_text(item) for item in items if _safe_text(item)}))


def _id_tuple(value: Any) -> tuple[str, ...]:
    try:
        items = list(value)
    except TypeError:
        return ()
    return tuple(sorted({_contract_id(item) for item in items if _contract_id(item)}))


def _contract_id(value: Any) -> str:
    text = _safe_text(value)
    if not text or len(text) > 160:
        return ""
    if all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text
    return ""


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return _safe_text(value)[:limit]


def _metadata_summary(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    summary: dict[str, Any] = {}
    for raw_key, raw_value in list(value.items())[:20]:
        key = _bounded_text(raw_key, limit=80)
        if not key:
            continue
        if isinstance(raw_value, bool | int | float):
            summary[key] = raw_value
        else:
            summary[key] = _bounded_text(raw_value, limit=160)
    return summary
