from __future__ import annotations

CAPABILITY_NAME = "Stage-3d021bde-af5f-4afe-a289-db9dc6638732"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
