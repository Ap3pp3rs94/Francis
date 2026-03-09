from __future__ import annotations

from uuid import uuid4

from fastapi import Request

REQUEST_ID_HEADER = "x-request-id"


def get_request_id(request: Request) -> str:
    existing = getattr(request.state, "request_id", None)
    if isinstance(existing, str) and existing.strip():
        return existing.strip()
    header_value = request.headers.get(REQUEST_ID_HEADER, "").strip()
    return header_value or "unknown"


async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER, "").strip() or str(uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers[REQUEST_ID_HEADER] = request_id
    return response
