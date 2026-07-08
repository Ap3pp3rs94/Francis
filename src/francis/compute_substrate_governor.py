from __future__ import annotations

import inspect
import uuid
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from francis.compute_substrate_approvals import ApprovalStore
from francis.compute_substrate_receipts import CapabilityReceiptAdapter, ComputeReceiptStore
from francis.compute_substrate_registry import WorkerRegistry, default_registry
from francis.compute_substrate_types import (
    LIVE_LEARNING_EVENT_KIND,
    _ALLOWED_PRIORITIES,
    _NO_FILESYSTEM_SCOPE,
    _int_or_default,
    _now_ms,
    _safe_text,
    ApprovalConsumptionResult,
    CapabilityReceipt,
    ExecutionContext,
    ExecutionInterrupted,
    ExecutionResult,
    LiveLearningEvent,
    ResourceBudget,
    SubstrateDecision,
    SubstratePolicy,
    TaskEnvelope,
    WorkerDescriptor,
)


class SubstrateGovernor:
    def __init__(
        self,
        *,
        policy: SubstratePolicy | None = None,
        receipt_adapter: CapabilityReceiptAdapter | None = None,
        receipt_store: ComputeReceiptStore | None = None,
        approval_store: ApprovalStore | None = None,
    ) -> None:
        self.policy = policy or SubstratePolicy()
        self.receipt_adapter = receipt_adapter or CapabilityReceiptAdapter()
        self.receipt_store = receipt_store
        self.approval_store = approval_store

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
                "approval_consumption": "internal_compute_approval_store_when_required",
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

    def execute(
        self,
        envelope: TaskEnvelope,
        registry: WorkerRegistry,
        context: ExecutionContext | None = None,
    ) -> ExecutionResult:
        started_at_ms = _now_ms()
        execution_context = ExecutionContext.for_envelope(
            envelope,
            started_at_ms=started_at_ms,
            context=context,
        )
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
                started_at_ms=started_at_ms,
                ended_at_ms=_now_ms(),
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=_now_ms(),
                    execution_started=False,
                    execution_finished=False,
                ),
            )

        descriptor = backend.descriptor
        decision = self.authorize(envelope, descriptor)
        if not decision.allowed:
            ended_at_ms = _now_ms()
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status="denied",
                output={"decision": decision.to_dict()},
                error=decision.reason,
                reason=decision.reason,
                started_at_ms=started_at_ms,
                ended_at_ms=ended_at_ms,
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    execution_started=False,
                    execution_finished=False,
                ),
            )

        approval_result: ApprovalConsumptionResult | None = None
        if envelope.budget.approval_required:
            approval_result = self._authorize_approval(envelope, descriptor)
            if not approval_result.allowed:
                ended_at_ms = _now_ms()
                return self._result(
                    envelope=envelope,
                    descriptor=descriptor,
                    ok=False,
                    status="denied",
                    output={"approval": approval_result.to_dict()},
                    error=approval_result.reason,
                    reason=approval_result.reason,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    approval_result=approval_result,
                    execution_summary=self._execution_summary(
                        envelope=envelope,
                        context=execution_context,
                        started_at_ms=started_at_ms,
                        ended_at_ms=ended_at_ms,
                        execution_started=False,
                        execution_finished=False,
                    ),
                )

        try:
            execution_context.raise_if_interrupted(stage="pre_execution")
        except ExecutionInterrupted as interruption:
            ended_at_ms = _now_ms()
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status=interruption.status,
                output={"interruption": self._interruption_output(interruption)},
                error=interruption.reason,
                reason=interruption.reason,
                started_at_ms=started_at_ms,
                ended_at_ms=ended_at_ms,
                approval_result=approval_result,
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    execution_started=False,
                    execution_finished=False,
                    interruption=interruption,
                ),
            )

        if envelope.budget.approval_required:
            approval_result = self._consume_approval(envelope, descriptor)
            if not approval_result.allowed:
                ended_at_ms = _now_ms()
                return self._result(
                    envelope=envelope,
                    descriptor=descriptor,
                    ok=False,
                    status="denied",
                    output={"approval": approval_result.to_dict()},
                    error=approval_result.reason,
                    reason=approval_result.reason,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    approval_result=approval_result,
                    execution_summary=self._execution_summary(
                        envelope=envelope,
                        context=execution_context,
                        started_at_ms=started_at_ms,
                        ended_at_ms=ended_at_ms,
                        execution_started=False,
                        execution_finished=False,
                    ),
                )

        try:
            output = self._execute_backend(backend, envelope, execution_context)
            ended_at_ms = _now_ms()
            elapsed_ms = ended_at_ms - started_at_ms
            runtime_over_budget = elapsed_ms > envelope.budget.max_runtime_ms
            deadline_elapsed = execution_context.deadline.is_expired(ended_at_ms)
            if runtime_over_budget or deadline_elapsed:
                timeout_reason = (
                    "runtime_budget_elapsed_after_registered_function"
                    if runtime_over_budget
                    else "deadline_elapsed_after_registered_function"
                )
                return self._result(
                    envelope=envelope,
                    descriptor=descriptor,
                    ok=False,
                    status="timeout",
                    output=output,
                    error=timeout_reason,
                    reason=timeout_reason,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    approval_result=approval_result,
                    execution_summary=self._execution_summary(
                        envelope=envelope,
                        context=execution_context,
                        started_at_ms=started_at_ms,
                        ended_at_ms=ended_at_ms,
                        execution_started=True,
                        execution_finished=True,
                        timeout_stage="post_execution",
                        over_budget_runtime=runtime_over_budget,
                    ),
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
                approval_result=approval_result,
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    execution_started=True,
                    execution_finished=True,
                ),
            )
        except ExecutionInterrupted as interruption:
            ended_at_ms = _now_ms()
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status=interruption.status,
                output={"interruption": self._interruption_output(interruption)},
                error=interruption.reason,
                reason=interruption.reason,
                started_at_ms=started_at_ms,
                ended_at_ms=ended_at_ms,
                approval_result=approval_result,
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    execution_started=True,
                    execution_finished=True,
                    interruption=interruption,
                ),
            )
        except Exception as exc:
            ended_at_ms = _now_ms()
            return self._result(
                envelope=envelope,
                descriptor=descriptor,
                ok=False,
                status="error",
                output={},
                error=f"{type(exc).__name__}: {exc}",
                reason="registered_function_error",
                started_at_ms=started_at_ms,
                ended_at_ms=ended_at_ms,
                approval_result=approval_result,
                execution_summary=self._execution_summary(
                    envelope=envelope,
                    context=execution_context,
                    started_at_ms=started_at_ms,
                    ended_at_ms=ended_at_ms,
                    execution_started=True,
                    execution_finished=True,
                ),
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
        approval_result: ApprovalConsumptionResult | None = None,
        execution_summary: Mapping[str, Any] | None = None,
    ) -> ExecutionResult:
        receipt = self.receipt_adapter.create(
            envelope=envelope,
            descriptor=descriptor,
            status=status,
            reason=reason,
            approval_result=approval_result,
            execution_summary=execution_summary,
        )
        receipt = self._persist_receipt(receipt)
        result_ok = ok
        result_status = status
        result_error = error
        if ok and receipt.receipt_error:
            result_ok = False
            result_status = "receipt_persistence_failed"
            result_error = receipt.receipt_error
            receipt = replace(
                receipt,
                status=result_status,
                reason="receipt_persistence_failed_after_execution",
            )
        event = LiveLearningEvent(
            kind=LIVE_LEARNING_EVENT_KIND,
            event_id=f"compute_learning_{uuid.uuid4().hex[:16]}",
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            result_status=result_status,
            observations=(
                f"task_status:{result_status}",
                f"registered_function:{envelope.function_name}",
                f"timeout_stage:{_safe_text((execution_summary or {}).get('timeout_stage')) or 'not_applicable'}",
                f"cancellation_requested:{bool((execution_summary or {}).get('cancellation_requested', False))}",
                "persistence:not_requested",
            ),
            persistence_requested=False,
            persisted=False,
            persistence_follow_up="requires_governance_review_before_long_term_memory_write",
        )
        return ExecutionResult(
            ok=result_ok,
            status=result_status,
            task_id=envelope.task_id,
            worker_id=descriptor.worker_id,
            backend_name=descriptor.backend_name,
            function_name=envelope.function_name,
            output=dict(output),
            error=result_error,
            started_at_ms=started_at_ms,
            ended_at_ms=ended_at_ms,
            elapsed_ms=max(0, ended_at_ms - started_at_ms),
            receipt=receipt,
            live_learning_event=event,
        )

    def _persist_receipt(self, receipt: CapabilityReceipt) -> CapabilityReceipt:
        if self.receipt_store is None:
            return receipt
        try:
            return self.receipt_store.write_receipt(receipt)
        except Exception as exc:
            receipt_error = f"{type(exc).__name__}: {_safe_text(exc)}"[:240]
            return replace(
                receipt,
                persisted=False,
                receipt_path="",
                receipt_error=receipt_error,
                governance={
                    **receipt.governance,
                    "receipt_persistence": "persistence_failed",
                    "receipt_store_configured": True,
                    "receipt_store_error_recorded": True,
                    "writes_memory": False,
                    "long_term_memory_persistence": False,
                    "approval_consumption": receipt.governance.get("approval_consumption", "not_required"),
                    "os_level_cpu_memory_enforcement": False,
                },
            )

    def _authorize_approval(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        if self.approval_store is None:
            return ApprovalConsumptionResult(
                allowed=False,
                reason="missing_approval",
                approval_id=_safe_text(envelope.approval_id),
                consumed=False,
                evidence={"approval_store_configured": False},
            )
        try:
            return self.approval_store.authorize(envelope, descriptor)
        except Exception as exc:
            return ApprovalConsumptionResult(
                allowed=False,
                reason="approval_cannot_be_authorized",
                approval_id=_safe_text(envelope.approval_id),
                consumed=False,
                evidence={
                    "approval_store_configured": True,
                    "error_type": type(exc).__name__,
                    "error": _safe_text(exc)[:160],
                },
            )

    def _consume_approval(self, envelope: TaskEnvelope, descriptor: WorkerDescriptor) -> ApprovalConsumptionResult:
        if self.approval_store is None:
            return ApprovalConsumptionResult(
                allowed=False,
                reason="missing_approval",
                approval_id=_safe_text(envelope.approval_id),
                consumed=False,
                evidence={"approval_store_configured": False},
            )
        try:
            return self.approval_store.consume(envelope, descriptor)
        except Exception as exc:
            return ApprovalConsumptionResult(
                allowed=False,
                reason="approval_cannot_be_consumed",
                approval_id=_safe_text(envelope.approval_id),
                consumed=False,
                evidence={
                    "approval_store_configured": True,
                    "error_type": type(exc).__name__,
                    "error": _safe_text(exc)[:160],
                },
            )

    @staticmethod
    def _execute_backend(
        backend: object,
        envelope: TaskEnvelope,
        context: ExecutionContext,
    ) -> dict[str, Any]:
        execute = getattr(backend, "execute")
        try:
            parameters = inspect.signature(execute).parameters
        except (TypeError, ValueError):
            return execute(envelope, context)
        accepts_context = len(parameters) >= 2 or any(
            parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
        )
        if accepts_context:
            return execute(envelope, context)
        return execute(envelope)

    @staticmethod
    def _interruption_output(interruption: ExecutionInterrupted) -> dict[str, Any]:
        return {
            "status": interruption.status,
            "reason": interruption.reason,
            "stage": interruption.stage,
            "timed_out": interruption.timed_out,
            "cancellation_requested": interruption.cancellation_requested,
            "os_level_preemption": False,
        }

    @staticmethod
    def _execution_summary(
        *,
        envelope: TaskEnvelope,
        context: ExecutionContext,
        started_at_ms: int,
        ended_at_ms: int,
        execution_started: bool,
        execution_finished: bool,
        interruption: ExecutionInterrupted | None = None,
        timeout_stage: str = "not_applicable",
        over_budget_runtime: bool = False,
    ) -> dict[str, Any]:
        duration_ms = max(0, ended_at_ms - started_at_ms)
        deadline_elapsed = context.deadline.is_expired(ended_at_ms)
        timed_out = bool(
            (interruption and interruption.timed_out)
            or over_budget_runtime
            or (deadline_elapsed and timeout_stage != "not_applicable")
        )
        resolved_timeout_stage = timeout_stage
        if interruption and interruption.timed_out:
            resolved_timeout_stage = interruption.stage
        elif not timed_out:
            resolved_timeout_stage = "not_applicable"
        return {
            **context.to_summary(),
            "cancellation_requested": bool(
                context.cancellation_token.cancel_requested or (interruption and interruption.cancellation_requested)
            ),
            "cancellation_reason": (
                interruption.reason
                if interruption and interruption.cancellation_requested
                else context.cancellation_token.reason
            ),
            "deadline_expired": deadline_elapsed,
            "timed_out": timed_out,
            "timeout_stage": resolved_timeout_stage,
            "execution_started": execution_started,
            "execution_finished": execution_finished,
            "duration_ms": duration_ms,
            "over_budget_runtime": over_budget_runtime or duration_ms > envelope.budget.max_runtime_ms,
            "cooperative_cancellation": True,
            "os_level_preemption": False,
        }

    @staticmethod
    def _payload_compute_units_within_budget(envelope: TaskEnvelope) -> bool:
        if envelope.function_name not in {"compute_test", "cooperative_delay_test"}:
            return True
        requested = _int_or_default(
            envelope.payload.get("iterations", envelope.payload.get("steps", envelope.payload.get("units", 100))),
            default=100,
        )
        return 0 < requested <= envelope.budget.max_compute_units


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
    context: ExecutionContext | None = None,
) -> ExecutionResult:
    return (governor or SubstrateGovernor()).execute(envelope, registry or default_registry(), context=context)
