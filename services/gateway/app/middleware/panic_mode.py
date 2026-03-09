from __future__ import annotations

import os

from fastapi import Request
from starlette.responses import JSONResponse

PANIC_MODE_ENV = "FRANCIS_GATEWAY_PANIC_MODE"
PANIC_MODE_HEADER = "x-francis-panic-mode"
MUTATING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_panic_mode_enabled(request: Request) -> bool:
    existing = getattr(request.state, "panic_mode", None)
    if isinstance(existing, bool):
        return existing
    env_enabled = _is_truthy(os.getenv(PANIC_MODE_ENV, ""))
    header_enabled = _is_truthy(request.headers.get(PANIC_MODE_HEADER, ""))
    return env_enabled or header_enabled


async def enforce_panic_mode(request: Request, call_next):
    enabled = is_panic_mode_enabled(request)
    request.state.panic_mode = enabled
    if enabled and request.method.upper() in MUTATING_METHODS and request.url.path != "/health":
        return JSONResponse(
            status_code=423,
            content={
                "status": "blocked",
                "reason": "panic_mode_enabled",
                "path": request.url.path,
                "method": request.method.upper(),
            },
        )
    return await call_next(request)
