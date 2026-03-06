from __future__ import annotations

CAPABILITY_NAME = "Pack-2f05b481-3664-4934-b10c-c923244a1704"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
