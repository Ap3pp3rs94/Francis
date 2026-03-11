from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _severity_rank(value: object) -> int:
    normalized = str(value or "").strip().lower()
    if normalized in {"critical", "high", "alert"}:
        return 3
    if normalized in {"medium", "warn", "warning"}:
        return 2
    if normalized in {"low", "nominal", "info"}:
        return 1
    return 0


def _max_severity(messages: list[dict[str, Any]]) -> str:
    current = "low"
    for row in messages:
        severity = str(row.get("severity", "low")).strip().lower() or "low"
        if _severity_rank(severity) > _severity_rank(current):
            current = severity
    return current


def _detail_summary(row: dict[str, Any]) -> str:
    title = str(row.get("title", "Inbox message")).strip() or "Inbox message"
    summary = str(row.get("summary", "")).strip()
    severity = str(row.get("severity", "nominal")).strip().lower() or "nominal"
    return f"{title} | {severity} | {summary}".strip(" |")


def _detail_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    severity = str(row.get("severity", "nominal")).strip().lower() or "nominal"
    return [
        {"label": "Message", "value": str(row.get("title", "Inbox message")).strip() or "Inbox message", "tone": severity},
        {"label": "Severity", "value": severity, "tone": severity},
        {"label": "Source", "value": str(row.get("source", "workspace")).strip() or "workspace", "tone": "low"},
    ]


def get_inbox_view(*, snapshot: dict[str, object] | None = None) -> dict[str, object]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    inbox = snapshot["inbox"]
    if inbox["items"]:
        messages = inbox["items"]
    else:
        messages = [
            {
                "id": "msg-inbox-empty",
                "title": "Inbox clear",
                "severity": "nominal",
                "summary": "No inbox messages are present in the current workspace.",
            }
        ]
    normalized: list[dict[str, Any]] = []
    for row in messages:
        if not isinstance(row, dict):
            continue
        item = dict(row)
        item["detail_summary"] = _detail_summary(item)
        item["detail_cards"] = _detail_cards(item)
        normalized.append(item)
    top = normalized[0] if normalized else None
    return {
        "status": "ok",
        "surface": "inbox",
        "message_count": inbox["count"],
        "alert_count": inbox["alert_count"],
        "summary": str(top.get("detail_summary", "")).strip() if top else "Inbox is clear.",
        "severity": _max_severity(normalized) if normalized else "low",
        "cards": [
            {"label": "Messages", "value": str(int(inbox["count"])), "tone": "medium" if int(inbox["count"]) else "low"},
            {"label": "Alerts", "value": str(int(inbox["alert_count"])), "tone": "high" if int(inbox["alert_count"]) else "low"},
            {
                "label": "Top Message",
                "value": str(top.get("title", "Inbox clear")).strip() if top else "Inbox clear",
                "tone": str(top.get("severity", "low")).strip().lower() if top else "low",
            },
        ],
        "messages": normalized,
        "detail": {
            "top_message": top,
            "messages": normalized,
        },
    }
