from __future__ import annotations

CAPABILITY_NAME = "Stage-6746b8fc-0f7c-44a5-a0d0-0ea9f13ab25b"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
