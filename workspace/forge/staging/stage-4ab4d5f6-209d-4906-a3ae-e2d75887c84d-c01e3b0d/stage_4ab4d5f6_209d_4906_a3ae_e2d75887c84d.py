from __future__ import annotations

CAPABILITY_NAME = "Stage-4ab4d5f6-209d-4906-a3ae-e2d75887c84d"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
