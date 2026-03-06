from __future__ import annotations

CAPABILITY_NAME = "Pack-236ec887-ece6-41da-a1dc-c3cd71d57526"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
