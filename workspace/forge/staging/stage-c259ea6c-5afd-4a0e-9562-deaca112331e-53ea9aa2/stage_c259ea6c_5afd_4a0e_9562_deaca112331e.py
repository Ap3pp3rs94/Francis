from __future__ import annotations

CAPABILITY_NAME = "Stage-c259ea6c-5afd-4a0e-9562-deaca112331e"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
