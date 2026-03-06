from __future__ import annotations

CAPABILITY_NAME = "Stage-e4f77e5c-2018-469f-9acf-a623bfde40af"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
