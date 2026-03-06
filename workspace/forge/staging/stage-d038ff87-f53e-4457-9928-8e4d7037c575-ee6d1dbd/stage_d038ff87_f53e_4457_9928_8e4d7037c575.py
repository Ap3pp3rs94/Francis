from __future__ import annotations

CAPABILITY_NAME = "Stage-d038ff87-f53e-4457-9928-8e4d7037c575"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
