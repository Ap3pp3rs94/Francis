from __future__ import annotations

CAPABILITY_NAME = "Pack-fe55688c-ff4c-4c32-af7d-bdacffc6c7bc"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
