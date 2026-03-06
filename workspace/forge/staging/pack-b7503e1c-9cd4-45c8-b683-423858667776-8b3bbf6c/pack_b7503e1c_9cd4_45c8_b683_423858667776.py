from __future__ import annotations

CAPABILITY_NAME = "Pack-b7503e1c-9cd4-45c8-b683-423858667776"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
