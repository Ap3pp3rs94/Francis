from __future__ import annotations

CAPABILITY_NAME = "Stage-a44c902a-660a-4f65-8954-c9dbbb5e750a"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
