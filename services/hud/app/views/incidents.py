from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _severity_rank(value: object) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "severe"}:
        return 4
    if normalized == "high":
        return 3
    if normalized == "medium":
        return 2
    if normalized in {"low", "nominal"}:
        return 1
    return 0


def _security_summary(security: dict[str, Any]) -> str:
    quarantine_count = int(security.get("quarantine_count", 0))
    highest = str(security.get("highest_severity", "nominal")).strip().lower() or "nominal"
    if quarantine_count:
        return f"{quarantine_count} quarantine event(s) are on record. Highest security severity is {highest}."
    return f"No quarantine pressure is active. Security posture is {highest}."


def _detail_summary(row: dict[str, Any]) -> str:
    summary = str(row.get("summary", "Incident")).strip() or "Incident"
    severity = str(row.get("severity", "low")).strip().lower() or "low"
    state = str(row.get("state", "open")).strip().lower() or "open"
    source = str(row.get("source", "unknown source")).strip() or "unknown source"
    return f"{summary} | {severity} severity | {state} | {source}"


def _detail_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    severity = str(row.get("severity", "low")).strip().lower() or "low"
    state = str(row.get("state", "open")).strip().lower() or "open"
    return [
        {"label": "Incident", "value": str(row.get("summary", "Incident")).strip() or "Incident", "tone": severity},
        {"label": "Severity", "value": severity, "tone": severity},
        {"label": "State", "value": state, "tone": "medium"},
        {"label": "Source", "value": str(row.get("source", "unknown")).strip() or "unknown", "tone": "low"},
    ]


def get_incidents_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    incidents = snapshot["incidents"]
    security = snapshot.get("security", {}) if isinstance(snapshot.get("security"), dict) else {}
    items: list[dict[str, Any]] = []
    for row in incidents["items"] if isinstance(incidents.get("items"), list) else []:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["detail_summary"] = _detail_summary(item)
        item["detail_cards"] = _detail_cards(item)
        items.append(item)
    top_incident = items[0] if items else None
    summary = (
        str(top_incident.get("detail_summary", "")).strip()
        if top_incident
        else "No open incidents are active in the current workspace."
    )
    severity = str(incidents["highest_severity"]).strip().lower() or "nominal"
    security_text = _security_summary(security)
    return {
        "status": "ok",
        "surface": "incidents",
        "summary": summary,
        "severity": severity,
        "cards": [
            {"label": "Open", "value": str(int(incidents["open_count"])), "tone": "high" if int(incidents["open_count"]) else "low"},
            {"label": "Severity", "value": severity, "tone": severity},
            {
                "label": "Quarantines",
                "value": str(int(security.get("quarantine_count", 0))),
                "tone": str(security.get("highest_severity", "low")).strip().lower() or "low",
            },
            {
                "label": "Top Source",
                "value": str(top_incident.get("source", "none")).strip() if top_incident else "none",
                "tone": severity,
            },
        ],
        "open_count": incidents["open_count"],
        "items": items,
        "security": security,
        "detail": {
            "top_incident": top_incident,
            "security_summary": security_text,
            "items": items,
            "security": security,
        },
    }
