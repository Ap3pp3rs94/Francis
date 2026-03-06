from __future__ import annotations

CAPABILITY_NAME = "Stage-92787836-b4d1-4a22-89c7-f43168a510b2"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
