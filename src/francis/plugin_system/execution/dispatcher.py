from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Callable

from francis.telemetry import audit
from francis.telemetry.tracing import start_span

from ..sandbox.runner import SandboxRunResult, SandboxRunner

logger = logging.getLogger(__name__)

__all__ = ["DispatchResult", "PluginDispatcher"]


@dataclass(frozen=True)
class DispatchResult:
    ok: bool
    status: str
    output: Any = None
    error: str = ""
    plugin_id: str = ""
    tool_name: str = ""
    run_id: str = ""
    trace_id: str = ""
    sandbox: dict[str, Any] | None = None
    audit_event: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "output": self.output,
            "error": self.error,
            "plugin_id": self.plugin_id,
            "tool_name": self.tool_name,
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "sandbox": self.sandbox or {},
            "audit_event": self.audit_event or {},
        }


class PluginDispatcher:
    def __init__(self, *, sandbox: SandboxRunner | None = None) -> None:
        self.sandbox = sandbox or SandboxRunner()

    def dispatch(self, handler: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        result = self.dispatch_with_receipt(handler, *args, **kwargs)
        return result.output if result.ok else None

    def dispatch_with_receipt(
        self,
        handler: Callable[..., Any],
        *args: Any,
        plugin_id: str = "",
        tool_name: str = "",
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        if not callable(handler):
            logger.warning("dispatch expected callable handler")
            event = audit.record(
                "plugin.dispatch",
                status="error",
                plugin_id=plugin_id,
                tool_name=tool_name,
                reason="invalid_handler",
            )
            return DispatchResult(
                ok=False,
                status="error",
                error="invalid_handler",
                plugin_id=plugin_id,
                tool_name=tool_name,
                audit_event=event,
            )

        with start_span("plugin.dispatch") as trace:
            sandbox_result: SandboxRunResult = self.sandbox.run_with_receipt(
                handler,
                *args,
                payload={"args": args, "kwargs": kwargs, "plugin_id": plugin_id, "tool_name": tool_name},
                dry_run=dry_run,
                **kwargs,
            )
            status = sandbox_result.status if sandbox_result.ok else "error"
            event = audit.record(
                "plugin.dispatch",
                status=status,
                plugin_id=plugin_id,
                tool_name=tool_name,
                sandbox_status=sandbox_result.status,
                dry_run=dry_run,
            )
            return DispatchResult(
                ok=sandbox_result.ok,
                status=sandbox_result.status,
                output=sandbox_result.output,
                error=sandbox_result.error,
                plugin_id=plugin_id,
                tool_name=tool_name,
                run_id=trace.run_id,
                trace_id=trace.trace_id,
                sandbox=sandbox_result.to_dict(),
                audit_event=event,
            )
