from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable

from francis.telemetry import audit
from francis.telemetry.tracing import start_span

from .limits import SandboxLimits

logger = logging.getLogger(__name__)

__all__ = ["SandboxRunResult", "SandboxRunner"]


@dataclass(frozen=True)
class SandboxRunResult:
    ok: bool
    status: str
    output: Any = None
    error: str = ""
    elapsed_ms: int = 0
    limits: dict[str, Any] | None = None
    run_id: str = ""
    trace_id: str = ""
    audit_event: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "elapsed_ms": self.elapsed_ms,
            "limits": self.limits or {},
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "audit_event": self.audit_event or {},
        }


class SandboxRunner:
    def __init__(self, limits: SandboxLimits | None = None) -> None:
        self.limits = limits or SandboxLimits()

    def run(self, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        result = self.run_with_receipt(handler, *args, **kwargs)
        return result.output if result.ok else None

    def run_with_receipt(
        self,
        handler: Callable[..., Any],
        *args: Any,
        payload: Any | None = None,
        dry_run: bool = False,
        **kwargs: Any,
    ) -> SandboxRunResult:
        if not callable(handler):
            logger.warning("run expected callable handler")
            event = audit.record(
                "plugin.sandbox.run",
                status="error",
                reason="invalid_handler",
                dry_run=dry_run,
                limits=self.limits.to_dict(),
            )
            return SandboxRunResult(
                ok=False,
                status="error",
                error="invalid_handler",
                limits=self.limits.to_dict(),
                audit_event=event,
            )

        payload_size = self._estimate_payload_bytes(
            payload if payload is not None else {"args": args, "kwargs": kwargs}
        )
        if payload_size > self.limits.max_payload_bytes:
            event = audit.record(
                "plugin.sandbox.run",
                status="blocked",
                reason="payload_too_large",
                payload_size=payload_size,
                dry_run=dry_run,
                limits=self.limits.to_dict(),
            )
            return SandboxRunResult(
                ok=False,
                status="blocked",
                error="payload_too_large",
                limits=self.limits.to_dict(),
                audit_event=event,
            )

        started = time.perf_counter()
        with start_span("plugin.sandbox.run") as trace:
            if dry_run:
                preview = {
                    "args_count": len(args),
                    "kwargs_keys": sorted(kwargs.keys()),
                    "payload_size": payload_size,
                }
                event = audit.record(
                    "plugin.sandbox.run",
                    status="dry_run",
                    payload_size=payload_size,
                    dry_run=True,
                    limits=self.limits.to_dict(),
                    preview=preview,
                )
                return SandboxRunResult(
                    ok=True,
                    status="dry_run",
                    output=preview,
                    elapsed_ms=int((time.perf_counter() - started) * 1000),
                    limits=self.limits.to_dict(),
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    audit_event=event,
                )

            try:
                output = handler(*args, **kwargs)
            except Exception as exc:
                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.error("Sandbox run failed: %s", exc)
                event = audit.record(
                    "plugin.sandbox.run",
                    status="error",
                    reason="handler_failed",
                    error=str(exc),
                    payload_size=payload_size,
                    dry_run=False,
                    limits=self.limits.to_dict(),
                )
                return SandboxRunResult(
                    ok=False,
                    status="error",
                    error=str(exc),
                    elapsed_ms=elapsed_ms,
                    limits=self.limits.to_dict(),
                    run_id=trace.run_id,
                    trace_id=trace.trace_id,
                    audit_event=event,
                )

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            event = audit.record(
                "plugin.sandbox.run",
                status="ok",
                payload_size=payload_size,
                dry_run=False,
                limits=self.limits.to_dict(),
                output_type=type(output).__name__,
            )
            return SandboxRunResult(
                ok=True,
                status="ok",
                output=output,
                elapsed_ms=elapsed_ms,
                limits=self.limits.to_dict(),
                run_id=trace.run_id,
                trace_id=trace.trace_id,
                audit_event=event,
            )

    def _estimate_payload_bytes(self, payload: Any) -> int:
        try:
            raw = json.dumps(payload, ensure_ascii=False, default=str)
        except Exception:
            raw = repr(payload)
        return len(raw.encode("utf-8", errors="replace"))
