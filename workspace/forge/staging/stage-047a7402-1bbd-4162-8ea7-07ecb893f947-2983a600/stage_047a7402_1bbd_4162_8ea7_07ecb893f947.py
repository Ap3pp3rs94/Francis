from __future__ import annotations

CAPABILITY_NAME = "Stage-047a7402-1bbd-4162-8ea7-07ecb893f947"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
