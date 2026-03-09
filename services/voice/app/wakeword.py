from __future__ import annotations


def capability_status() -> dict[str, object]:
    return {
        "status": "user_armed_only",
        "keyword": "francis",
        "hot_mic": False,
        "activation": "push_to_talk",
        "visible_indicator_required": True,
    }
