from __future__ import annotations

CAPABILITY_NAME = "Stage-2d358dd4-86d2-4818-88bf-795e15c3001d"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
