from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(tags=["capabilities"])


@router.get("/capabilities")
def capabilities() -> dict:
    return {
        "status": "ok",
        "capabilities": [
            "health",
            "capabilities",
            "inbox",
            "presence.briefing",
            "presence.state",
            "runs",
            "missions",
            "approvals",
            "tools",
            "worker",
            "observer",
            "forge",
            "autonomy",
            "autonomy.events",
            "autonomy.events.collect",
            "autonomy.events.dispatch",
            "autonomy.events.recover",
            "autonomy.events.history",
            "autonomy.reactor.tick",
            "autonomy.reactor.last",
            "autonomy.reactor.history",
            "autonomy.reactor.guardrail",
            "autonomy.reactor.guardrail.history",
            "autonomy.reactor.guardrail.reset",
            "control",
            "receipts",
            "lens",
            "telemetry",
        ],
    }
