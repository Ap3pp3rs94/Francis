from __future__ import annotations

from pathlib import Path
from typing import Any

from .journal import append_jsonl, read_jsonl


class LocalEventBus:
    def __init__(self, path: Path) -> None:
        self.path = path

    def emit(self, event: dict[str, Any]) -> None:
        append_jsonl(self.path, event)

    def tail(self, n: int = 20) -> list[dict[str, Any]]:
        events = read_jsonl(self.path)
        return events[-n:]
