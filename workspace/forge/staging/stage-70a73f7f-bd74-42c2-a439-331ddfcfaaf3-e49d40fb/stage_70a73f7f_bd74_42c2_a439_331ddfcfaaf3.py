from __future__ import annotations

CAPABILITY_NAME = "Stage-70a73f7f-bd74-42c2-a439-331ddfcfaaf3"
CAPABILITY_DESCRIPTION = "Capability staged by integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
