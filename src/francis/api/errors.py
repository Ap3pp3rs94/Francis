from __future__ import annotations

import logging
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

_ERROR_CODE = "internal_api_error"
_LOG = logging.getLogger("francis.api.errors")


def api_error_code(*, code: str = _ERROR_CODE) -> str:
    return code


def _public_api_error_code(exc: BaseException) -> str:
    code = getattr(exc, "api_error_code", "")
    if not isinstance(code, str):
        return ""
    clean = code.strip()
    if not clean or len(clean) > 80:
        return ""
    if not all(ch.isalnum() or ch in {"_", "-", ".", ":"} for ch in clean):
        return ""
    return clean


def log_api_exception(exc: BaseException, *, route: str = "") -> None:
    route_text = f" route={route}" if route else ""
    _LOG.exception("API boundary exception%s", route_text, exc_info=True)


def api_error_message(exc: BaseException, *, code: str = _ERROR_CODE, route: str = "") -> str:
    public_code = _public_api_error_code(exc)
    if public_code:
        route_text = f" route={route}" if route else ""
        _LOG.info("API boundary rejected%s code=%s", route_text, public_code)
        return public_code
    log_api_exception(exc, route=route)
    return api_error_code(code=code)


async def sanitized_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    _LOG.exception("Unhandled API exception route=%s", request.url.path, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "ok": False,
            "error": _ERROR_CODE,
            "error_code": _ERROR_CODE,
        },
    )


def sanitized_error_payload(exc: BaseException, *, code: str = _ERROR_CODE, **extra: Any) -> dict[str, Any]:
    message = api_error_message(exc, code=code)
    return {"ok": False, "error": message, "error_code": code, **extra}
