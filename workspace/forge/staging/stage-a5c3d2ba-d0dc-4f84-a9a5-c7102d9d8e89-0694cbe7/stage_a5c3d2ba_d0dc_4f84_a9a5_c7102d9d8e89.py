from __future__ import annotations

CAPABILITY_NAME = "Stage-a5c3d2ba-d0dc-4f84-a9a5-c7102d9d8e89"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
