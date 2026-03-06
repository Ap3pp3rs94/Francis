from __future__ import annotations

CAPABILITY_NAME = "Stage-98344533-7585-494e-b8dd-eee959014673"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
