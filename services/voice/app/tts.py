from __future__ import annotations

from francis_presence.tone import MODE_OPENERS, compose_mode_briefing


def capability_status() -> dict[str, object]:
    return {
        "status": "briefing_ready",
        "engine": "template_charter",
        "supported_modes": list(MODE_OPENERS),
        "voice_contract": "calm, grounded, non-dramatic",
    }


def build_briefing(*, objective: str, mode: str, include_receipts: bool = True) -> str:
    return compose_mode_briefing(objective=objective, mode=mode, include_receipts=include_receipts)
