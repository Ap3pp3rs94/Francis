from __future__ import annotations

CAPABILITY_NAME = "Stage-5fba01c1-9c4d-48f6-b641-efa38f9df521"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
