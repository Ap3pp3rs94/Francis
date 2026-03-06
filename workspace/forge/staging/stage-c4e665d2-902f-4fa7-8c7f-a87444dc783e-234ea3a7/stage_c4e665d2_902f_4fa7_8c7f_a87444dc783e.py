from __future__ import annotations

CAPABILITY_NAME = "Stage-c4e665d2-902f-4fa7-8c7f-a87444dc783e"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
