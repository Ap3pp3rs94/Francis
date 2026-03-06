from __future__ import annotations

CAPABILITY_NAME = "Pack-777a9d13-420c-4715-a082-628f932c822d"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
