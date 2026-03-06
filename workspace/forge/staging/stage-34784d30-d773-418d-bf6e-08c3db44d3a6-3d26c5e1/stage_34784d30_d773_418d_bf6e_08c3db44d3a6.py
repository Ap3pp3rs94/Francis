from __future__ import annotations

CAPABILITY_NAME = "Stage-34784d30-d773-418d-bf6e-08c3db44d3a6"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
