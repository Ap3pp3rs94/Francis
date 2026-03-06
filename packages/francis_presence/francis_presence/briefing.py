from __future__ import annotations

from typing import Iterable


def compose_briefing(*, headline: str, bullets: Iterable[str]) -> dict:
    lines = [headline, "", *[f"- {line}" for line in bullets]]
    return {"headline": headline, "body": "\n".join(lines)}
