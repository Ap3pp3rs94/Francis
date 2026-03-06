from __future__ import annotations

CAPABILITY_NAME = "Stage-2ed84080-a6e8-4e18-bb03-6cb188ce2d04"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
