from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, Protocol

from francis.compute_substrate_types import (
    SAFE_LOCAL_BACKEND_NAME,
    _int_or_default,
    _now_ms,
    _safe_text,
    ExecutionContext,
    TaskEnvelope,
    WorkerDescriptor,
)
from francis.kernel.health import health_report
from francis.telemetry.status import telemetry_status_snapshot


class ExecutionBackend(Protocol):
    @property
    def descriptor(self) -> WorkerDescriptor: ...

    def execute(self, envelope: TaskEnvelope, context: ExecutionContext | None = None) -> dict[str, Any]: ...


RegisteredFunction = Callable[[TaskEnvelope, ExecutionContext], dict[str, Any]]


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

    def execute(self, envelope: TaskEnvelope, context: ExecutionContext | None = None) -> dict[str, Any]:
        fn = self._functions.get(envelope.function_name)
        if fn is None:
            raise KeyError("registered_function_not_found")
        execution_context = context or ExecutionContext.for_envelope(envelope, started_at_ms=_now_ms())
        return fn(envelope, execution_context)


def default_registered_functions() -> dict[str, RegisteredFunction]:
    return {
        "echo": _echo,
        "health_check": _health_check,
        "compute_test": _compute_test,
        "cooperative_delay_test": _cooperative_delay_test,
        "summarize_status": _summarize_status,
    }


def _echo(envelope: TaskEnvelope, context: ExecutionContext) -> dict[str, Any]:
    context.raise_if_interrupted(stage="during_execution")
    return {
        "ok": True,
        "function": "echo",
        "message": _safe_text(envelope.payload.get("message", envelope.payload.get("text", ""))),
    }


def _health_check(_: TaskEnvelope, context: ExecutionContext) -> dict[str, Any]:
    context.raise_if_interrupted(stage="during_execution")
    return {
        "ok": True,
        "function": "health_check",
        "source": "francis.kernel.health.health_report",
        "health": health_report(),
    }


def _compute_test(envelope: TaskEnvelope, context: ExecutionContext) -> dict[str, Any]:
    iterations = _int_or_default(
        envelope.payload.get("iterations", envelope.payload.get("units", 100)),
        default=100,
    )
    total = 0
    for index in range(iterations):
        context.raise_if_interrupted(stage="during_execution")
        total = (total + (index * index)) % 1_000_003
    return {
        "ok": True,
        "function": "compute_test",
        "iterations": iterations,
        "checksum": total,
    }


def _cooperative_delay_test(envelope: TaskEnvelope, context: ExecutionContext) -> dict[str, Any]:
    steps = max(
        1,
        min(
            _int_or_default(envelope.payload.get("steps", envelope.payload.get("units", 1)), default=1),
            envelope.budget.max_compute_units,
            50,
        ),
    )
    delay_ms = max(0, min(_int_or_default(envelope.payload.get("delay_ms", 1), default=1), 25))
    completed_steps = 0
    for _ in range(steps):
        context.raise_if_interrupted(stage="during_execution")
        if delay_ms:
            time.sleep(delay_ms / 1000)
        completed_steps += 1
    context.raise_if_interrupted(stage="during_execution")
    return {
        "ok": True,
        "function": "cooperative_delay_test",
        "steps": steps,
        "delay_ms": delay_ms,
        "completed_steps": completed_steps,
    }


def _summarize_status(_: TaskEnvelope, context: ExecutionContext) -> dict[str, Any]:
    context.raise_if_interrupted(stage="during_execution")
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
