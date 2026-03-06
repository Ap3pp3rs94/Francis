from __future__ import annotations

CAPABILITY_NAME = "Stage-e9c0c629-8f49-49a7-bea7-f3ecc43c61a2"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
