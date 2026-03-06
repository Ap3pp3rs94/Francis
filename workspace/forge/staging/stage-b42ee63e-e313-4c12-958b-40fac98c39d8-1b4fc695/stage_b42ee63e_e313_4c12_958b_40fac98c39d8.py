from __future__ import annotations

CAPABILITY_NAME = "Stage-b42ee63e-e313-4c12-958b-40fac98c39d8"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
