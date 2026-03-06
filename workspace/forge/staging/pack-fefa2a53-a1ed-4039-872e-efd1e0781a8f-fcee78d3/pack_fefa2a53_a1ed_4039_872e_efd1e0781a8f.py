from __future__ import annotations

CAPABILITY_NAME = "Pack-fefa2a53-a1ed-4039-872e-efd1e0781a8f"
CAPABILITY_DESCRIPTION = "Tool-pack auto registration integration test."

def run(payload: dict | None = None) -> dict:
    data = payload or {}
    return {"status": "ok", "capability": CAPABILITY_NAME, "input": data}
