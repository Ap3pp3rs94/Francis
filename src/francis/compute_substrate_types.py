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
