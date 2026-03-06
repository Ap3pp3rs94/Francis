from __future__ import annotations

CAPABILITY_NAME = "Pack-7a3ce7f1-35a5-471c-b10c-8a29676dc5ef"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
