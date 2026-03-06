from __future__ import annotations

CAPABILITY_NAME = "Stage-ce3e4fad-e04d-4909-8c27-8f1b3d461e6c"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
