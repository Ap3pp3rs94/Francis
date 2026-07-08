from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from francis.compute_substrate_approvals import ApprovalStore
from francis.compute_substrate_governor import SubstrateGovernor
from francis.compute_substrate_receipts import ComputeReceiptStore
from francis.compute_substrate_registry import WorkerRegistry, default_registry
from francis.compute_substrate_types import (
    _int_or_default,
    _now_ms,
    _safe_text,
    CapabilityReceipt,
    ExecutionContext,
    ExecutionResult,
    TaskEnvelope,
)


class ComputeTaskStatus:
    SUBMITTED = "submitted"
    DENIED = "denied"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    RECEIPT_PERSISTENCE_FAILED = "receipt_persistence_failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class ComputeSubmission:
    envelope: TaskEnvelope
    context: ExecutionContext | None = None
    submitted_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "submitted_at_ms", _int_or_default(self.submitted_at_ms, default=_now_ms()))

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.envelope.task_id,
            "correlation_id": _safe_record_text(self.envelope.trace_id),
            "capability": self.envelope.function_name,
            "approval_required": self.envelope.budget.approval_required,
            "has_execution_context": self.context is not None,
            "submitted_at_ms": self.submitted_at_ms,
            "stores_payload": False,
            "stores_output": False,
        }


@dataclass(frozen=True, slots=True)
class ComputeTaskRecord:
    task_id: str
    correlation_id: str
    capability: str
    worker_id: str
    status: str
    error: str = ""
    denial_reason: str = ""
    approval_required: bool = False
    approval_satisfied: bool = False
    approval_consumed: bool = False
    cancellation_requested: bool = False
    cancellation_reason: str = ""
    timed_out: bool = False
    timeout_stage: str = "not_applicable"
    execution_started: bool = False
    execution_finished: bool = False
    receipt_id: str = ""
    receipt_persisted: bool = False
    receipt_persistence_status: str = "not_available"
    receipt_error: str = ""
    started_at_ms: int = 0
    finished_at_ms: int = 0
    duration_ms: int = 0
    created_at_ms: int = field(default_factory=_now_ms)
    updated_at_ms: int = field(default_factory=_now_ms)

    def __post_init__(self) -> None:
        object.__setattr__(self, "task_id", _safe_record_text(self.task_id))
        object.__setattr__(self, "correlation_id", _safe_record_text(self.correlation_id))
        object.__setattr__(self, "capability", _bounded_text(self.capability, limit=120))
        object.__setattr__(self, "worker_id", _safe_record_text(self.worker_id))
        object.__setattr__(self, "status", _safe_status(self.status))
        object.__setattr__(self, "error", _bounded_text(self.error))
        object.__setattr__(self, "denial_reason", _bounded_text(self.denial_reason))
        object.__setattr__(self, "cancellation_reason", _bounded_text(self.cancellation_reason))
        object.__setattr__(self, "timeout_stage", _bounded_text(self.timeout_stage, limit=80) or "not_applicable")
        object.__setattr__(self, "receipt_id", _safe_record_text(self.receipt_id))
        object.__setattr__(
            self,
            "receipt_persistence_status",
            _bounded_text(self.receipt_persistence_status, limit=120) or "not_available",
        )
        object.__setattr__(self, "receipt_error", _bounded_text(self.receipt_error))
        object.__setattr__(self, "started_at_ms", _int_or_default(self.started_at_ms, default=0))
        object.__setattr__(self, "finished_at_ms", _int_or_default(self.finished_at_ms, default=0))
        object.__setattr__(self, "duration_ms", max(0, _int_or_default(self.duration_ms, default=0)))
        object.__setattr__(self, "created_at_ms", _int_or_default(self.created_at_ms, default=_now_ms()))
        object.__setattr__(self, "updated_at_ms", _int_or_default(self.updated_at_ms, default=_now_ms()))

    @classmethod
    def from_submission(cls, submission: ComputeSubmission) -> ComputeTaskRecord:
        return cls(
            task_id=submission.envelope.task_id,
            correlation_id=submission.envelope.trace_id,
            capability=submission.envelope.function_name,
            worker_id="",
            status=ComputeTaskStatus.SUBMITTED,
            approval_required=submission.envelope.budget.approval_required,
            created_at_ms=submission.submitted_at_ms,
            updated_at_ms=submission.submitted_at_ms,
        )

    @classmethod
    def from_execution_result(
        cls,
        result: ExecutionResult,
        *,
        created_at_ms: int,
    ) -> ComputeTaskRecord:
        governance = dict(result.receipt.governance)
        status = _status_from_execution(result.status)
        error = _bounded_text(result.error)
        denial_reason = error if status == ComputeTaskStatus.DENIED else ""
        return cls(
            task_id=result.task_id,
            correlation_id=result.receipt.trace_id,
            capability=result.function_name,
            worker_id=result.worker_id,
            status=status,
            error=error,
            denial_reason=denial_reason,
            approval_required=bool(governance.get("approval_required", False)),
            approval_satisfied=bool(governance.get("approval_satisfied", False)),
            approval_consumed=bool(governance.get("approval_consumed", False)),
            cancellation_requested=bool(governance.get("cancellation_requested", False)),
            cancellation_reason=_safe_text(governance.get("cancellation_reason")),
            timed_out=bool(governance.get("timed_out", False)),
            timeout_stage=_safe_text(governance.get("timeout_stage")) or "not_applicable",
            execution_started=bool(governance.get("execution_started", False)),
            execution_finished=bool(governance.get("execution_finished", False)),
            receipt_id=result.receipt.receipt_id,
            receipt_persisted=result.receipt.persisted,
            receipt_persistence_status=_safe_text(governance.get("receipt_persistence")) or "not_available",
            receipt_error=result.receipt.receipt_error,
            started_at_ms=result.started_at_ms,
            finished_at_ms=result.ended_at_ms,
            duration_ms=result.elapsed_ms,
            created_at_ms=created_at_ms,
            updated_at_ms=result.ended_at_ms,
        )

    @classmethod
    def unknown(
        cls,
        *,
        task_id: str = "",
        correlation_id: str = "",
    ) -> ComputeTaskRecord:
        now_ms = _now_ms()
        return cls(
            task_id=task_id,
            correlation_id=correlation_id,
            capability="",
            worker_id="",
            status=ComputeTaskStatus.UNKNOWN,
            error="status_not_found",
            created_at_ms=now_ms,
            updated_at_ms=now_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "capability": self.capability,
            "worker_id": self.worker_id,
            "status": self.status,
            "error": self.error,
            "denial_reason": self.denial_reason,
            "approval_required": self.approval_required,
            "approval_satisfied": self.approval_satisfied,
            "approval_consumed": self.approval_consumed,
            "cancellation_requested": self.cancellation_requested,
            "cancellation_reason": self.cancellation_reason,
            "timed_out": self.timed_out,
            "timeout_stage": self.timeout_stage,
            "execution_started": self.execution_started,
            "execution_finished": self.execution_finished,
            "receipt_id": self.receipt_id,
            "receipt_persisted": self.receipt_persisted,
            "receipt_persistence_status": self.receipt_persistence_status,
            "receipt_error": self.receipt_error,
            "started_at_ms": self.started_at_ms,
            "finished_at_ms": self.finished_at_ms,
            "duration_ms": self.duration_ms,
            "created_at_ms": self.created_at_ms,
            "updated_at_ms": self.updated_at_ms,
            "stores_payload": False,
            "stores_output": False,
            "durable_status_persistence": False,
            "background_execution": False,
        }


@dataclass(frozen=True, slots=True)
class ComputeSubmissionResult:
    ok: bool
    status: str
    task_id: str
    correlation_id: str
    record: ComputeTaskRecord
    receipt: CapabilityReceipt
    result_status: str
    result_error: str

    @classmethod
    def from_execution_result(
        cls,
        *,
        record: ComputeTaskRecord,
        result: ExecutionResult,
    ) -> ComputeSubmissionResult:
        return cls(
            ok=result.ok,
            status=record.status,
            task_id=record.task_id,
            correlation_id=record.correlation_id,
            record=record,
            receipt=result.receipt,
            result_status=result.status,
            result_error=_bounded_text(result.error),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "task_id": self.task_id,
            "correlation_id": self.correlation_id,
            "record": self.record.to_dict(),
            "receipt": self.receipt.to_dict(),
            "result_status": self.result_status,
            "result_error": self.result_error,
            "stores_payload": False,
            "stores_output": False,
            "async_execution": False,
        }


class ComputeStatusStore(Protocol):
    def upsert(self, record: ComputeTaskRecord) -> ComputeTaskRecord: ...

    def get_by_task_id(self, task_id: str) -> ComputeTaskRecord | None: ...

    def get_by_correlation_id(self, correlation_id: str) -> ComputeTaskRecord | None: ...

    def describe(self) -> dict[str, Any]: ...


class InMemoryComputeStatusStore:
    """Process-local status readback for internal compute submissions."""

    def __init__(self) -> None:
        self._records_by_task_id: dict[str, ComputeTaskRecord] = {}
        self._task_id_by_correlation_id: dict[str, str] = {}

    def upsert(self, record: ComputeTaskRecord) -> ComputeTaskRecord:
        self._records_by_task_id[record.task_id] = record
        if record.correlation_id:
            self._task_id_by_correlation_id[record.correlation_id] = record.task_id
        return record

    def get_by_task_id(self, task_id: str) -> ComputeTaskRecord | None:
        return self._records_by_task_id.get(_safe_record_text(task_id))

    def get_by_correlation_id(self, correlation_id: str) -> ComputeTaskRecord | None:
        task_id = self._task_id_by_correlation_id.get(_safe_record_text(correlation_id))
        if not task_id:
            return None
        return self._records_by_task_id.get(task_id)

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.in_memory_status_store",
            "stored_record_count": len(self._records_by_task_id),
            "durable": False,
            "stores_payload": False,
            "stores_output": False,
            "stores_approval_notes": False,
            "writes_memory": False,
            "background_execution": False,
        }


class ComputeSubstrateService:
    """Internal submission/status control surface for governed compute tasks."""

    def __init__(
        self,
        *,
        governor: SubstrateGovernor | None = None,
        registry: WorkerRegistry | None = None,
        approval_store: ApprovalStore | None = None,
        receipt_store: ComputeReceiptStore | None = None,
        status_store: ComputeStatusStore | None = None,
    ) -> None:
        self.registry = registry or default_registry()
        self.governor = governor or SubstrateGovernor(
            approval_store=approval_store,
            receipt_store=receipt_store,
        )
        self.status_store = status_store or InMemoryComputeStatusStore()

    def submit(
        self,
        submission: ComputeSubmission | TaskEnvelope,
        *,
        context: ExecutionContext | None = None,
    ) -> ComputeSubmissionResult:
        normalized = _normalize_submission(submission, context=context)
        submitted_record = self.status_store.upsert(ComputeTaskRecord.from_submission(normalized))
        result = self.governor.execute(normalized.envelope, self.registry, context=normalized.context)
        final_record = self.status_store.upsert(
            ComputeTaskRecord.from_execution_result(
                result,
                created_at_ms=submitted_record.created_at_ms,
            )
        )
        return ComputeSubmissionResult.from_execution_result(record=final_record, result=result)

    def status_for_task(self, task_id: str) -> ComputeTaskRecord:
        return self.status_store.get_by_task_id(task_id) or ComputeTaskRecord.unknown(task_id=task_id)

    def status_for_correlation(self, correlation_id: str) -> ComputeTaskRecord:
        return self.status_store.get_by_correlation_id(correlation_id) or ComputeTaskRecord.unknown(
            correlation_id=correlation_id
        )

    def known_capabilities(self) -> tuple[str, ...]:
        capabilities: set[str] = set()
        for descriptor in self.registry.descriptors():
            capabilities.update(descriptor.capabilities)
        return tuple(sorted(capabilities))

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.compute_substrate.service",
            "submission_mode": "synchronous_in_process",
            "uses_governor": True,
            "status_store": self.status_store.describe(),
            "no_api_route": True,
            "no_background_worker": True,
            "stores_payload": False,
            "stores_output": False,
            "writes_memory": False,
            "durable_approval_persistence": False,
            "live_learning_persistence": False,
            "os_level_cpu_memory_enforcement": False,
        }


def _normalize_submission(
    submission: ComputeSubmission | TaskEnvelope,
    *,
    context: ExecutionContext | None,
) -> ComputeSubmission:
    if isinstance(submission, ComputeSubmission):
        if context is None:
            return submission
        return replace(submission, context=context)
    return ComputeSubmission(envelope=submission, context=context)


def _status_from_execution(status: str) -> str:
    normalized = _safe_text(status)
    if normalized == "success":
        return ComputeTaskStatus.SUCCEEDED
    if normalized == "error":
        return ComputeTaskStatus.FAILED
    if normalized == "timeout":
        return ComputeTaskStatus.TIMED_OUT
    if normalized == "cancelled":
        return ComputeTaskStatus.CANCELLED
    if normalized == "denied":
        return ComputeTaskStatus.DENIED
    if normalized == "receipt_persistence_failed":
        return ComputeTaskStatus.RECEIPT_PERSISTENCE_FAILED
    return ComputeTaskStatus.FAILED


def _safe_status(status: str) -> str:
    normalized = _safe_text(status)
    allowed = {
        ComputeTaskStatus.SUBMITTED,
        ComputeTaskStatus.DENIED,
        ComputeTaskStatus.SUCCEEDED,
        ComputeTaskStatus.FAILED,
        ComputeTaskStatus.CANCELLED,
        ComputeTaskStatus.TIMED_OUT,
        ComputeTaskStatus.RECEIPT_PERSISTENCE_FAILED,
        ComputeTaskStatus.UNKNOWN,
    }
    return normalized if normalized in allowed else ComputeTaskStatus.UNKNOWN


def _safe_record_text(value: Any) -> str:
    text = _safe_text(value)
    if not text:
        return ""
    if all(ch.isalnum() or ch in ("-", "_", ".") for ch in text):
        return text[:160]
    return ""


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return _safe_text(value)[:limit]
