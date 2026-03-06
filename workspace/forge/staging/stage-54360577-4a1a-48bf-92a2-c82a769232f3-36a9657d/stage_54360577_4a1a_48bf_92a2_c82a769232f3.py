from __future__ import annotations

CAPABILITY_NAME = "Stage-54360577-4a1a-48bf-92a2-c82a769232f3"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
