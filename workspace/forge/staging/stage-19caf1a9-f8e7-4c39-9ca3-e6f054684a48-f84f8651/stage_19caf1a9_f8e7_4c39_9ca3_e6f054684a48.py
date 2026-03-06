from __future__ import annotations

CAPABILITY_NAME = "Stage-19caf1a9-f8e7-4c39-9ca3-e6f054684a48"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
