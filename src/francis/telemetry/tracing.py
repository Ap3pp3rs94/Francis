from __future__ import annotations

import secrets
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from typing import Iterator

_RUN_ID: ContextVar[str] = ContextVar("francis_run_id", default="")
_TRACE_ID: ContextVar[str] = ContextVar("francis_trace_id", default="")
_SPAN_ID: ContextVar[str] = ContextVar("francis_span_id", default="")
_PARENT_SPAN_ID: ContextVar[str] = ContextVar("francis_parent_span_id", default="")
_SPAN_NAME: ContextVar[str] = ContextVar("francis_span_name", default="")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def new_run_id() -> str:
    return f"run_{int(time.time())}_{secrets.token_hex(4)}"


def new_trace_id() -> str:
    return _new_id("trace")


def new_span_id() -> str:
    return _new_id("span")


@dataclass(frozen=True, slots=True)
class TraceContext:
    run_id: str = ""
    trace_id: str = ""
    span_id: str = ""
    parent_span_id: str = ""
    span_name: str = ""

    def as_dict(self) -> dict[str, str]:
        out = {
            "run_id": self.run_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "span_name": self.span_name,
        }
        return {key: value for key, value in out.items() if value}


def current_context() -> TraceContext:
    return TraceContext(
        run_id=_RUN_ID.get(),
        trace_id=_TRACE_ID.get(),
        span_id=_SPAN_ID.get(),
        parent_span_id=_PARENT_SPAN_ID.get(),
        span_name=_SPAN_NAME.get(),
    )


def bind(
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    span_name: str | None = None,
) -> TraceContext:
    current = current_context()
    effective_run_id = run_id if run_id is not None else current.run_id or new_run_id()
    effective_trace_id = trace_id if trace_id is not None else current.trace_id or new_trace_id()
    effective_span_id = span_id if span_id is not None else current.span_id
    effective_parent = parent_span_id if parent_span_id is not None else current.parent_span_id
    effective_name = span_name if span_name is not None else current.span_name

    _RUN_ID.set(effective_run_id)
    _TRACE_ID.set(effective_trace_id)
    _SPAN_ID.set(effective_span_id)
    _PARENT_SPAN_ID.set(effective_parent)
    _SPAN_NAME.set(effective_name)
    return current_context()


def clear() -> None:
    _RUN_ID.set("")
    _TRACE_ID.set("")
    _SPAN_ID.set("")
    _PARENT_SPAN_ID.set("")
    _SPAN_NAME.set("")


@contextmanager
def start_span(
    name: str,
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    span_id: str | None = None,
) -> Iterator[TraceContext]:
    previous = current_context()
    next_run_id = run_id or previous.run_id or new_run_id()
    next_trace_id = trace_id or previous.trace_id or new_trace_id()
    next_parent_span_id = previous.span_id
    next_span_id = span_id or new_span_id()

    run_token: Token[str] = _RUN_ID.set(next_run_id)
    trace_token: Token[str] = _TRACE_ID.set(next_trace_id)
    span_token: Token[str] = _SPAN_ID.set(next_span_id)
    parent_token: Token[str] = _PARENT_SPAN_ID.set(next_parent_span_id)
    name_token: Token[str] = _SPAN_NAME.set(name.strip())
    try:
        yield current_context()
    finally:
        _RUN_ID.reset(run_token)
        _TRACE_ID.reset(trace_token)
        _SPAN_ID.reset(span_token)
        _PARENT_SPAN_ID.reset(parent_token)
        _SPAN_NAME.reset(name_token)
