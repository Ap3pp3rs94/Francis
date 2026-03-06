from __future__ import annotations

CAPABILITY_NAME = "Stage-0673636b-b27b-4a0a-b054-609014d654f6"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
