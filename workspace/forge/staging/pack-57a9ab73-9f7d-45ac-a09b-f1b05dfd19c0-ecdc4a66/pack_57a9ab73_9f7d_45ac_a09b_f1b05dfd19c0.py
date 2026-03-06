from __future__ import annotations

CAPABILITY_NAME = "Pack-57a9ab73-9f7d-45ac-a09b-f1b05dfd19c0"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
