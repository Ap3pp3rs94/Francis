from __future__ import annotations

CAPABILITY_NAME = "Pack-db0f660e-2b80-42de-927a-26ffe86fcfe4"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
