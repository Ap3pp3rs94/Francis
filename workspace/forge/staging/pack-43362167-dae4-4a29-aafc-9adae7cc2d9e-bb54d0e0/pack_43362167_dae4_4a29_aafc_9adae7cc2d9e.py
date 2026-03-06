from __future__ import annotations

CAPABILITY_NAME = "Pack-43362167-dae4-4a29-aafc-9adae7cc2d9e"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
