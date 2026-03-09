from __future__ import annotations

MODE_OPENERS = {
    "observe": "Observe mode. Reporting only what is grounded in current state.",
    "assist": "Assist mode. I can stage the next move and show the diff before execution.",
    "pilot": "Pilot mode. Control transfer is explicit and receipts stay visible throughout execution.",
    "away": "Away mode. Progress stays bounded by approved scope, queued approvals, and shift reports.",
}


def normalize_mode(mode: str) -> str:
    normalized = str(mode).strip().lower()
    if normalized not in MODE_OPENERS:
        raise ValueError(f"Unsupported mode: {mode}")
    return normalized


def compose_mode_briefing(*, objective: str, mode: str, include_receipts: bool = True) -> str:
    normalized_mode = normalize_mode(mode)
    normalized_objective = " ".join(str(objective).strip().split())

    parts = [MODE_OPENERS[normalized_mode]]
    if normalized_objective:
        parts.append(f"Objective: {normalized_objective}.")
    if include_receipts:
        parts.append("Claims remain tied to visible receipts and current scope.")
    return " ".join(parts)
