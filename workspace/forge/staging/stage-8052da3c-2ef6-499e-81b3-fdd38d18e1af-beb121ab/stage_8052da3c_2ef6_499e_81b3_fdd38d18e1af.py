from __future__ import annotations

CAPABILITY_NAME = "Stage-8052da3c-2ef6-499e-81b3-fdd38d18e1af"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
