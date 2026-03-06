from __future__ import annotations

CAPABILITY_NAME = "Stage-ee7d3f3b-c754-4b1b-8196-12ad13130dba"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
