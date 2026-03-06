from __future__ import annotations

CAPABILITY_NAME = "Pack-bbc8fdbd-0e74-4c91-aca8-23db8160910c"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
