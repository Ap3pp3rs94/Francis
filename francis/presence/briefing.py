from __future__ import annotations

from typing import Iterable


def compose_briefing(*, headline: str, bullets: Iterable[str]) -> dict:
    bullet_lines = [f"- {b}" for b in bullets]
    body = "\n".join([headline, "", *bullet_lines]).strip()
    return {"headline": headline, "body": body}

