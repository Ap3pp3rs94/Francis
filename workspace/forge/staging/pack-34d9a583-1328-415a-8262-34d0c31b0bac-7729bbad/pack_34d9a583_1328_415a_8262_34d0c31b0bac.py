from __future__ import annotations

CAPABILITY_NAME = "Pack-34d9a583-1328-415a-8262-34d0c31b0bac"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
