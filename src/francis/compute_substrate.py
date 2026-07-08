from __future__ import annotations

import time
import uuid
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from francis.kernel.health import health_report
from francis.telemetry.status import telemetry_status_snapshot

SAFE_LOCAL_BACKEND_NAME = "safe_local"
COMPUTE_RECEIPT_KIND = "francis.compute_substrate.capability_receipt"
LIVE_LEARNING_EVENT_KIND = "francis.compute_substrate.live_learning_event"

_ALLOWED_PRIORITIES = {"low", "normal", "high"}
_NO_FILESYSTEM_SCOPE = ("none",)


def _now_ms() -> int:
    return int(time.time() * 1000)


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _safe_id(value: Any, *, fallback_prefix: str) -> str:
    text = _safe_text(value)
    if text and all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text[:160]
    return f"{fallback_prefix}_{uuid.uuid4().hex[:12]}"


def _scope_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return _NO_FILESYSTEM_SCOPE
    if isinstance(value, str):
        items = [value]
    else:
        try:
            items = list(value)
        except TypeError:
            return _NO_FILESYSTEM_SCOPE
    normalized = tuple(_safe_text(item) for item in items if _safe_text(item))
    return normalized or _NO_FILESYSTEM_SCOPE


def _int_or_default(value: Any, *, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    return parsed


@dataclass(frozen=True, slots=True)
class ResourceBudget:
    max_runtime_ms: int = 1000
    max_memory_mb: int = 128
    cpu_weight: int = 25
    priority: str = "normal"
    allow_network: bool = False
    filesystem_scope: tuple[str, ...] = _NO_FILESYSTEM_SCOPE
    allow_gpu: bool = False
    cancel_requested: bool = False
    approval_required: bool = False
    max_compute_units: int = 1000

    def __post_init__(self) -> None:
        object.__setattr__(self, "max_runtime_ms", _int_or_default(self.max_runtime_ms, default=1000))
        object.__setattr__(self, "max_memory_mb", _int_or_default(self.max_memory_mb, default=128))
        object.__setattr__(self, "cpu_weight", _int_or_default(self.cpu_weight, default=25))
        object.__setattr__(self, "priority", _safe_text(self.priority).lower() or "normal")
        object.__setattr__(self, "filesystem_scope", _scope_tuple(self.filesystem_scope))
        object.__setattr__(self, "max_compute_units", _int_or_default(self.max_compute_units, default=1000))

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["filesystem_scope"] = list(self.filesystem_scope)
        return payload


@dataclass(frozen=True, slots=True)
class TaskEnvelope:
    task_id: str
    function_name: str
    payload: dict[str, Any] = field(default_factory=dict)
    budget: ResourceBudget = field(default_factory=ResourceBudget)
    actor: str = "local.operator"
    trace_id: str = ""
    approval_id: str = ""
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _safe_id(self.task_id, fallback_prefix="task"))
        object.__setattr__(self, "function_name", _safe_text(self.function_name))
        object.__setattr__(self, "payload", dict(self.payload or {}))
        object.__setattr__(self, "actor", _safe_text(self.actor) or "local.operator")
        object.__setattr__(self, "trace_id", _safe_text(self.trace_id))
        object.__setattr__(self, "approval_id", _safe_text(self.approval_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "function_name": self.function_name,
            "payload": dict(self.payload),
            "budget": self.budget.to_dict(),
            "actor": self.actor,
            "trace_id": self.trace_id,
            "approval_id": self.approval_id,
            "created_at_ms": self.created_at_ms,
        }


@dataclass(frozen=True, slots=True)
class WorkerDescriptor:
    worker_id: str
    backend_name: str
    capabilities: tuple[str, ...]
    enabled: bool = True
    local_only: bool = True
    starts_processes: bool = False
    allow_network: bool = False
    filesystem_access: str = "none"
    allow_gpu: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "worker_id", _safe_id(self.worker_id, fallback_prefix="worker"))
        object.__setattr__(self, "backend_name", _safe_text(self.backend_name))
        object.__setattr__(
            self, "capabilities", tuple(sorted({_safe_text(item) for item in self.capabilities if _safe_text(item)}))
        )
        object.__setattr__(self, "filesystem_access", _safe_text(self.filesystem_access).lower() or "none")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["capabilities"] = list(self.capabilities)
        return payload


@dataclass(frozen=True, slots=True)
class SubstratePolicy:
    max_runtime_ms: int = 5000
    max_memory_mb: int = 512
    max_cpu_weight: int = 50
    max_compute_units: int = 10000
    allow_network: bool = False
    allow_gpu: bool = False
    allowed_filesystem_scopes: tuple[str, ...] = _NO_FILESYSTEM_SCOPE


@dataclass(frozen=True, slots=True)
class SubstrateDecision:
    allowed: bool
    reason: str
    checks: dict[str, bool]
    governance: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class CapabilityReceipt:
    kind: str
    receipt_id: str
    task_id: str
    worker_id: str
    backend_name: str
    function_name: str
    status: str
    reason: str
    budget: dict[str, Any]
    persisted: bool
    receipt_path: str
    governance: dict[str, Any]
    created_at_ms: int = field(default_factory=_now_ms)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class LiveLearningEvent:
    kind: str
    event_id: str
    task_id: str
    worker_id: str
    backend_name: str
    function_name: str
    result_status: str
    observations: tuple[str, ...]
    persistence_requested: bool
    persisted: bool
    persistence_follow_up: str
    created_at_ms: int = field(default_factory=_now_ms)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["observations"] = list(self.observations)
        return payload


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    ok: bool
    status: str
    task_id: str
    worker_id: str
    backend_name: str
    function_name: str
    output: dict[str, Any]
    error: str
    started_at_ms: int
    ended_at_ms: int
    elapsed_ms: int
    receipt: CapabilityReceipt
    live_learning_event: LiveLearningEvent

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "task_id": self.task_id,
            "worker_id": self.worker_id,
            "backend_name": self.backend_name,
            "function_name": self.function_name,
            "output": dict(self.output),
            "error": self.error,
            "started_at_ms": self.started_at_ms,
            "ended_at_ms": self.ended_at_ms,
            "elapsed_ms": self.elapsed_ms,
            "receipt": self.receipt.to_dict(),
            "live_learning_event": self.live_learning_event.to_dict(),
        }


class ExecutionBackend(Protocol):
    @property
    def descriptor(self) -> WorkerDescriptor: ...

    def execute(self, envelope: TaskEnvelope) -> dict[str, Any]: ...


RegisteredFunction = Callable[[TaskEnvelope], dict[str, Any]]


class WorkerRegistry:
    def __init__(self) -> None:
        self._backends_by_worker: dict[str, ExecutionBackend] = {}
        self._worker_by_capability: dict[str, str] = {}

    def register(self, backend: ExecutionBackend) -> None:
        descriptor = backend.descriptor
        if descriptor.worker_id in self._backends_by_worker:
            raise ValueError("worker_already_registered")
        if not descriptor.capabilities:
            raise ValueError("worker_requires_capabilities")
        for capability in descriptor.capabilities:
            if capability in self._worker_by_capability:
                raise ValueError(f"capability_already_registered:{capability}")
        self._backends_by_worker[descriptor.worker_id] = backend
        for capability in descriptor.capabilities:
            self._worker_by_capability[capability] = descriptor.worker_id

    def backend_for(self, function_name: str) -> ExecutionBackend | None:
        worker_id = self._worker_by_capability.get(_safe_text(function_name))
        if not worker_id:
            return None
        return self._backends_by_worker.get(worker_id)

    def descriptors(self) -> list[WorkerDescriptor]:
        return [backend.descriptor for backend in self._backends_by_worker.values()]


class CapabilityReceiptAdapter:
    """First-slice receipt boundary.

    This returns a typed receipt object without pretending durable compute-receipt
    persistence exists. A future adapter can bind this contract to Francis's
    governed receipt writer after policy review.
    """

    def create(
        self,
        *,
        envelope: TaskEnvelope,
        descriptor: WorkerDescriptor,
        status: str,
        reason: str,
    ) -> CapabilityReceipt:
        return CapabilityReceipt(
            kind=COMPUTE_RECEIPT_KIND,
            receipt_id=f"compute_capability_{uuid.uuid4().hex[:16]}",
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            status=status,
            reason=reason,
            budget=envelope.budget.to_dict(),
            persisted=False,
            receipt_path="",
            governance={
                "local_first": True,
                "registered_function_only": True,
                "arbitrary_subprocess": False,
                "shell": False,
                "unrestricted_filesystem_write": False,
                "unrestricted_network": False,
                "background_daemon": False,
                "network_requested": envelope.budget.allow_network,
                "gpu_requested": envelope.budget.allow_gpu,
                "uses_network": False,
                "uses_gpu": False,
                "starts_processes": descriptor.starts_processes,
                "worker_enabled": descriptor.enabled,
                "writes_memory": False,
                "long_term_memory_persistence": False,
                "receipt_persistence": "not_persisted_first_slice",
                "os_level_cpu_memory_enforcement": False,
                "timeout_enforcement": "budget_validation_elapsed_check_and_registered_function_caps",
            },
        )


class SubstrateGovernor:
    def __init__(
        self,
        *,
        policy: SubstratePolicy | None = None,
        receipt_adapter: CapabilityReceiptAdapter | None = None,
    ) -> None:
        self.policy = policy or SubstratePolicy()
        self.receipt_adapter = receipt_adapter or CapabilityReceiptAdapter()

    def validate_budget(self, budget: ResourceBudget) -> SubstrateDecision:
        checks = {
            "runtime_within_limit": 0 < budget.max_runtime_ms <= self.policy.max_runtime_ms,
            "memory_within_limit": 0 < budget.max_memory_mb <= self.policy.max_memory_mb,
            "cpu_weight_within_limit": 0 < budget.cpu_weight <= self.policy.max_cpu_weight,
            "priority_allowed": budget.priority in _ALLOWED_PRIORITIES,
            "network_allowed": budget.allow_network is False or self.policy.allow_network,
            "gpu_allowed": budget.allow_gpu is False or self.policy.allow_gpu,
            "filesystem_scope_allowed": all(
                scope in self.policy.allowed_filesystem_scopes for scope in budget.filesystem_scope
            ),
            "not_cancelled": not budget.cancel_requested,
            "approval_not_required_first_slice": not budget.approval_required,
            "compute_units_within_limit": 0 < budget.max_compute_units <= self.policy.max_compute_units,
        }
        if all(checks.values()):
            reason = "budget_allowed"
        else:
            reason = next(name for name, passed in checks.items() if not passed)
        return SubstrateDecision(
            allowed=all(checks.values()),
            reason=reason,
            checks=checks,
            governance={
                "policy": "francis.compute_substrate.first_slice",
                "network_default_deny": not self.policy.allow_network,
                "gpu_default_deny": not self.policy.allow_gpu,
                "filesystem_default_scope": list(_NO_FILESYSTEM_SCOPE),
                "approval_consumption": "not_implemented_first_slice",
                "resource_enforcement": "validated_boundaries_not_os_cgroups",
            },
        )

    def authorize(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> SubstrateDecision:
        budget_decision = self.validate_budget(envelope.budget)
        checks = dict(budget_decision.checks)
        checks.update(
            {
                "registered_capability": envelope.function_name in descriptor.capabilities,
                "worker_enabled": descriptor.enabled,
                "worker_local_only": descriptor.local_only,
                "worker_no_processes": not descriptor.starts_processes,
                "worker_no_network": not descriptor.allow_network,
                "worker_no_filesystem": descriptor.filesystem_access == "none",
                "worker_no_gpu": not descriptor.allow_gpu,
                "payload_compute_units_within_budget": self._payload_compute_units_within_budget(envelope),
            }
        )
        if all(checks.values()):
            reason = "authorized"
        else:
            reason = next(name for name, passed in checks.items() if not passed)
        return SubstrateDecision(
            allowed=all(checks.values()),
            reason=reason,
            checks=checks,
            governance={
                **budget_decision.governance,
                "worker_id": descriptor.worker_id,
                "backend_name": descriptor.backend_name,
                "capability": envelope.function_name,
                "registered_function_only": True,
                "worker_enabled": descriptor.enabled,
            },
        )

    def execute(self, envelope: TaskEnvelope, registry: WorkerRegistry) -> ExecutionResult:
        backend = registry.backend_for(envelope.function_name)
        if backend is None:
            descriptor = WorkerDescriptor(
                worker_id="unregistered",
                backend_name="none",
                capabilities=(),
            )
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status="denied",
                output={},
                error="unregistered_function",
                reason="unregistered_function",
                started_at_ms=_now_ms(),
                ended_at_ms=_now_ms(),
            )

        descriptor = backend.descriptor
        decision = self.authorize(envelope, descriptor)
        started_at_ms = _now_ms()
        if not decision.allowed:
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status="denied",
                output={"decision": decision.to_dict()},
                error=decision.reason,
                reason=decision.reason,
                started_at_ms=started_at_ms,
                ended_at_ms=_now_ms(),
            )

        try:
            output = backend.execute(envelope)
            ended_at_ms = _now_ms()
            elapsed_ms = ended_at_ms - started_at_ms
            if elapsed_ms > envelope.budget.max_runtime_ms:
                return self._result(
                    envelope=envelope,
                    descriptor=descriptor,
                    ok=False,
                    status="timeout",
                    output=output,
                    error="runtime_budget_elapsed_after_registered_function",
                    reason="runtime_budget_elapsed_after_registered_function",
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                )
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=True,
                status="success",
                output=output,
                error="",
                reason="executed_registered_function",
                started_at_ms=started_at_ms,
                ended_at_ms=ended_at_ms,
            )
        except Exception as exc:
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status="error",
                output={},
                error=f"{type(exc).__name__}: {exc}",
                reason="registered_function_error",
                started_at_ms=started_at_ms,
                ended_at_ms=_now_ms(),
            )

    def _result(
        self,
        *,
        envelope: TaskEnvelope,
        descriptor: WorkerDescriptor,
        ok: bool,
        status: str,
        output: dict[str, Any],
        error: str,
        reason: str,
        started_at_ms: int,
        ended_at_ms: int,
    ) -> ExecutionResult:
        receipt = self.receipt_adapter.create(
            envelope=envelope,
            descriptor=descriptor,
            status=status,
            reason=reason,
        )
        event = LiveLearningEvent(
            kind=LIVE_LEARNING_EVENT_KIND,
            event_id=f"compute_learning_{uuid.uuid4().hex[:16]}",
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            result_status=status,
            observations=(
                f"task_status:{status}",
                f"registered_function:{envelope.function_name}",
                "persistence:not_requested",
            ),
            persistence_requested=False,
            persisted=False,
            persistence_follow_up="requires_governance_review_before_long_term_memory_write",
        )
        return ExecutionResult(
            ok=ok,
            status=status,
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            output=dict(output),
            error=error,
            started_at_ms=started_at_ms,
            ended_at_ms=ended_at_ms,
            elapsed_ms=max(0, ended_at_ms - started_at_ms),
            receipt=receipt,
            live_learning_event=event,
        )

    @staticmethod
    def _payload_compute_units_within_budget(envelope: TaskEnvelope) -> bool:
        if envelope.function_name != "compute_test":
            return True
        requested = _int_or_default(
            envelope.payload.get("iterations", envelope.payload.get("units", 100)),
            default=100,
        )
        return 0 < requested <= envelope.budget.max_compute_units


class SafeLocalBackend:
    def __init__(
        self,
        *,
        worker_id: str = "safe-local-1",
    ) -> None:
        functions = default_registered_functions()
        self._functions = {_safe_text(name): fn for name, fn in functions.items() if _safe_text(name)}
        self._descriptor = WorkerDescriptor(
            worker_id=worker_id,
            backend_name=SAFE_LOCAL_BACKEND_NAME,
            capabilities=tuple(self._functions),
            enabled=True,
            local_only=True,
            starts_processes=False,
            allow_network=False,
            filesystem_access="none",
            allow_gpu=False,
        )

    @property
    def descriptor(self) -> WorkerDescriptor:
        return self._descriptor

    def execute(self, envelope: TaskEnvelope) -> dict[str, Any]:
        fn = self._functions.get(envelope.function_name)
        if fn is None:
            raise KeyError("registered_function_not_found")
        return fn(envelope)


def default_registered_functions() -> dict[str, RegisteredFunction]:
    return {
        "echo": _echo,
        "health_check": _health_check,
        "compute_test": _compute_test,
        "summarize_status": _summarize_status,
    }


def default_registry() -> WorkerRegistry:
    registry = WorkerRegistry()
    registry.register(SafeLocalBackend())
    return registry


def create_task_envelope(
    function_name: str,
    *,
    task_id: str | None = None,
    payload: Mapping[str, Any] | None = None,
    budget: ResourceBudget | None = None,
    actor: str = "local.operator",
    trace_id: str = "",
    approval_id: str = "",
) -> TaskEnvelope:
    return TaskEnvelope(
        task_id=task_id or f"task_{uuid.uuid4().hex[:12]}",
        function_name=function_name,
        payload=dict(payload or {}),
        budget=budget or ResourceBudget(),
        actor=actor,
        trace_id=trace_id,
        approval_id=approval_id,
    )


def execute_registered_function(
    envelope: TaskEnvelope,
    *,
    registry: WorkerRegistry | None = None,
    governor: SubstrateGovernor | None = None,
) -> ExecutionResult:
    return (governor or SubstrateGovernor()).execute(envelope, registry or default_registry())


def _echo(envelope: TaskEnvelope) -> dict[str, Any]:
    return {
        "ok": True,
        "function": "echo",
        "message": _safe_text(envelope.payload.get("message", envelope.payload.get("text", ""))),
    }


def _health_check(_: TaskEnvelope) -> dict[str, Any]:
    return {
        "ok": True,
        "function": "health_check",
        "source": "francis.kernel.health.health_report",
        "health": health_report(),
    }


def _compute_test(envelope: TaskEnvelope) -> dict[str, Any]:
    iterations = _int_or_default(
        envelope.payload.get("iterations", envelope.payload.get("units", 100)),
        default=100,
    )
    total = 0
    for index in range(iterations):
        total = (total + (index * index)) % 1_000_003
    return {
        "ok": True,
        "function": "compute_test",
        "iterations": iterations,
        "checksum": total,
    }


def _summarize_status(_: TaskEnvelope) -> dict[str, Any]:
    status = telemetry_status_snapshot()
    return {
        "ok": True,
        "function": "summarize_status",
        "source": "francis.telemetry.status.telemetry_status_snapshot",
        "status": _safe_text(status.get("status")),
        "stage": _safe_text(status.get("stage")),
        "active": bool(status.get("active")),
        "next_smallest_truthful_gap": _safe_text(status.get("next_smallest_truthful_gap")),
    }
