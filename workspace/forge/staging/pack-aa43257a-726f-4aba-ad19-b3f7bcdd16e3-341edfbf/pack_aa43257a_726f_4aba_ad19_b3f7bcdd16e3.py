from __future__ import annotations

CAPABILITY_NAME = "Pack-aa43257a-726f-4aba-ad19-b3f7bcdd16e3"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
