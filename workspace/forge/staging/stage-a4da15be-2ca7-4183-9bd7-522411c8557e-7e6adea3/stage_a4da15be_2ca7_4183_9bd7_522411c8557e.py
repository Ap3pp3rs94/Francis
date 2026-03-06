from __future__ import annotations

CAPABILITY_NAME = "Stage-a4da15be-2ca7-4183-9bd7-522411c8557e"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
