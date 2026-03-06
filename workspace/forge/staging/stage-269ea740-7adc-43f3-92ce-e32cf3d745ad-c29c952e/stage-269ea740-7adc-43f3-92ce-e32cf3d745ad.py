from __future__ import annotations

CAPABILITY_NAME = "Stage-269ea740-7adc-43f3-92ce-e32cf3d745ad"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
