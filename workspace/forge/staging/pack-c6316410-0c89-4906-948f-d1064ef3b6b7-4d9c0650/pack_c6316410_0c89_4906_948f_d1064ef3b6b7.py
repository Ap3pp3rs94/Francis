from __future__ import annotations

CAPABILITY_NAME = "Pack-c6316410-0c89-4906-948f-d1064ef3b6b7"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
