from __future__ import annotations

CAPABILITY_NAME = "Stage-ef93cbc8-d14d-4bb0-8337-0681c4609c63"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
