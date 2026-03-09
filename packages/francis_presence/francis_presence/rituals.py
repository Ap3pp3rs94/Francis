from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from francis_brain.calibration import summarize_fabric_posture

from .tone import normalize_mode


def build_handback_ritual(
    *,
    mode: str,
    run_id: str,
    summary: str,
    pending_approvals: int = 0,
    verification: Mapping[str, Any] | None = None,
    fabric_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_mode = normalize_mode(mode)
    clean_summary = " ".join(str(summary).strip().split()) or "No summary was recorded."
    clean_run_id = str(run_id).strip() or "unknown"

    if normalized_mode == "pilot":
        title = "Pilot handback ready."
    elif normalized_mode == "away":
        title = "Away shift report ready."
    else:
        title = "Operator handback ready."

    lines = [
        f"Mode: {normalized_mode}",
        f"Run ID: {clean_run_id}",
        f"Summary: {clean_summary}",
        f"Pending approvals: {max(0, int(pending_approvals))}",
    ]
    if verification:
        checks = ", ".join(f"{key}={value}" for key, value in verification.items())
        if checks:
            lines.append(f"Verification: {checks}")
    posture: dict[str, Any] | None = None
    if fabric_summary:
        posture = summarize_fabric_posture(fabric_summary)
        lines.append(
            "Fabric trust: "
            f"{posture['trust']} "
            f"({posture['confirmed_count']} confirmed, "
            f"{posture['likely_count']} likely, "
            f"{posture['uncertain_count']} uncertain, "
            f"{posture['citation_ready_count']} citation-ready)."
        )
        if posture["warning"]:
            lines.append(f"Trust note: {posture['warning']}")

    body = "\n".join([title, "", *[f"- {line}" for line in lines]])
    return {"title": title, "body": body, "lines": lines, "fabric": posture}


def build_shift_report(
    *,
    completed_actions: int,
    staged_actions: int,
    pending_approvals: int,
    top_deltas: Sequence[str],
    next_action: str,
    fabric_summary: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    deltas = [str(delta).strip() for delta in top_deltas if str(delta).strip()]
    lines = [
        f"Completed actions: {max(0, int(completed_actions))}",
        f"Staged actions: {max(0, int(staged_actions))}",
        f"Pending approvals: {max(0, int(pending_approvals))}",
    ]
    if deltas:
        lines.append(f"Top deltas: {', '.join(deltas[:3])}")
    clean_next_action = " ".join(str(next_action).strip().split())
    if clean_next_action:
        lines.append(f"Recommended next action: {clean_next_action}")
    posture: dict[str, Any] | None = None
    if fabric_summary:
        posture = summarize_fabric_posture(fabric_summary)
        lines.append(
            "Fabric trust: "
            f"{posture['trust']} "
            f"({posture['confirmed_count']} confirmed, "
            f"{posture['likely_count']} likely, "
            f"{posture['uncertain_count']} uncertain)."
        )
        if posture["warning"]:
            lines.append(f"Trust note: {posture['warning']}")

    body = "\n".join(["Shift complete.", "", *[f"- {line}" for line in lines]])
    return {"title": "Shift complete.", "body": body, "lines": lines, "fabric": posture}
