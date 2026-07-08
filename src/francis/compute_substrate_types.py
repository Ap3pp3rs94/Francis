from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

SAFE_LOCAL_BACKEND_NAME = "safe_local"
COMPUTE_RECEIPT_KIND = "francis.compute_substrate.capability_receipt"
LIVE_LEARNING_EVENT_KIND = "francis.compute_substrate.live_learning_event"

_ALLOWED_PRIORITIES = {"low", "normal", "high"}
_NO_FILESYSTEM_SCOPE = ("none",)
_RISK_LEVELS = {"low": 1, "medium": 2, "high": 3}


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


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    parsed = _int_or_default(value, default=0)
    return parsed if parsed > 0 else None


def _risk_rank(value: Any) -> int:
    return _RISK_LEVELS.get(_safe_text(value).lower(), _RISK_LEVELS["high"])


def _risk_level(value: Any) -> str:
    text = _safe_text(value).lower()
    return text if text in _RISK_LEVELS else "low"


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
class ApprovalScope:
    task_id: str = ""
    correlation_id: str = ""
    allowed_capabilities: tuple[str, ...] = ()
    allowed_worker_ids: tuple[str, ...] = ()
    max_risk_level: str = "low"
    max_runtime_ms: int | None = None
    max_memory_mb: int | None = None
    max_cpu_weight: int | None = None
    max_compute_units: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _safe_text(self.task_id))
        object.__setattr__(self, "correlation_id", _safe_text(self.correlation_id))
        object.__setattr__(
            self,
            "allowed_capabilities",
            tuple(sorted({_safe_text(item) for item in self.allowed_capabilities if _safe_text(item)})),
        )
        object.__setattr__(
            self,
            "allowed_worker_ids",
            tuple(sorted({_safe_text(item) for item in self.allowed_worker_ids if _safe_text(item)})),
        )
        object.__setattr__(self, "max_risk_level", _risk_level(self.max_risk_level))
        object.__setattr__(self, "max_runtime_ms", _optional_positive_int(self.max_runtime_ms))
        object.__setattr__(self, "max_memory_mb", _optional_positive_int(self.max_memory_mb))
        object.__setattr__(self, "max_cpu_weight", _optional_positive_int(self.max_cpu_weight))
        object.__setattr__(self, "max_compute_units", _optional_positive_int(self.max_compute_units))

    def to_summary(self) -> dict[str, Any]:
        return {
            "task_id_bound": bool(self.task_id),
            "correlation_id_bound": bool(self.correlation_id),
            "allowed_capabilities": list(self.allowed_capabilities),
            "allowed_worker_ids": list(self.allowed_worker_ids),
            "max_risk_level": self.max_risk_level,
            "resource_budget_ceiling": {
                "max_runtime_ms": self.max_runtime_ms,
                "max_memory_mb": self.max_memory_mb,
                "max_cpu_weight": self.max_cpu_weight,
                "max_compute_units": self.max_compute_units,
            },
        }


@dataclass(frozen=True, slots=True)
class ApprovalGrant:
    approval_id: str
    scope: ApprovalScope = field(default_factory=ApprovalScope)
    subject: str = "compute_substrate_task"
    approved_by: str = "local.operator"
    source: str = "in_memory_compute_approval"
    reason: str = ""
    approval_note: str = ""
    correlation_id: str = ""
    trace_id: str = ""
    expires_at_ms: int | None = None
    single_use: bool = True
    consumed_at_ms: int = 0
    consumed_by_task_id: str = ""
    revoked: bool = False
    created_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "approval_id", _safe_id(self.approval_id, fallback_prefix="approval"))
        object.__setattr__(self, "subject", _safe_text(self.subject) or "compute_substrate_task")
        object.__setattr__(self, "approved_by", _safe_text(self.approved_by) or "local.operator")
        object.__setattr__(self, "source", _safe_text(self.source) or "in_memory_compute_approval")
        object.__setattr__(self, "reason", _safe_text(self.reason))
        object.__setattr__(self, "approval_note", _safe_text(self.approval_note))
        object.__setattr__(self, "correlation_id", _safe_text(self.correlation_id))
        object.__setattr__(self, "trace_id", _safe_text(self.trace_id))
        object.__setattr__(self, "expires_at_ms", _optional_positive_int(self.expires_at_ms))
        object.__setattr__(self, "consumed_at_ms", _int_or_default(self.consumed_at_ms, default=0))
        object.__setattr__(self, "consumed_by_task_id", _safe_text(self.consumed_by_task_id))

    def to_summary(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "subject": self.subject,
            "source": self.source,
            "approved_by": self.approved_by,
            "single_use": self.single_use,
            "expires_at_ms": self.expires_at_ms,
            "revoked": self.revoked,
            "consumed": self.consumed_at_ms > 0,
            "consumed_at_ms": self.consumed_at_ms,
            "consumed_by_task_id": self.consumed_by_task_id,
            "approval_note_present": bool(self.approval_note),
            "scope": self.scope.to_summary(),
        }


@dataclass(frozen=True, slots=True)
class ApprovalConsumptionResult:
    allowed: bool
    reason: str
    approval_id: str = ""
    consumed: bool = False
    approval_required: bool = True
    scope_summary: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "approval_id": self.approval_id,
            "consumed": self.consumed,
            "approval_required": self.approval_required,
            "scope_summary": dict(self.scope_summary),
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class CapabilityReceipt:
    kind: str
    receipt_id: str
    task_id: str
    worker_id: str
    backend_name: str
    function_name: str
    trace_id: str
    approval_id: str
    status: str
    reason: str
    budget: dict[str, Any]
    persisted: bool
    receipt_path: str
    receipt_error: str
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
