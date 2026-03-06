from __future__ import annotations

CAPABILITY_NAME = "Stage-c9c464af-2581-4a45-a312-4f81aaf4d2bc"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
