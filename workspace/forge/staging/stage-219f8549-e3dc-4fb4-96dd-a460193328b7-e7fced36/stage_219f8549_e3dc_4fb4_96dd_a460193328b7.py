from __future__ import annotations

CAPABILITY_NAME = "Stage-219f8549-e3dc-4fb4-96dd-a460193328b7"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
