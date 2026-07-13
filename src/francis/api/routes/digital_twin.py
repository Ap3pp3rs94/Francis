from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/status")
def status() -> dict[str, object]:
    return {
        "ok": True,
        "route": "digital_twin",
        "status": "not_implemented",
        "ready": False,
        "implemented_operations": ["status_readback"],
        "blockers": ["digital_twin_api_route_operations_not_implemented"],
        "governance": {
            "read_only": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
