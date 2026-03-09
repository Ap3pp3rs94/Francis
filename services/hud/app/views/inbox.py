from __future__ import annotations

from services.hud.app.state import build_lens_snapshot


def get_inbox_view() -> dict[str, object]:
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
    return {
        "status": "ok",
        "surface": "inbox",
        "message_count": inbox["count"],
        "alert_count": inbox["alert_count"],
        "messages": messages,
    }
