from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS


@dataclass(frozen=True)
class LedgerEvent:
    ts: str
    kind: str
    run_id: str
    summary: dict[str, Any]


class RunLedger:
    def __init__(self, fs: WorkspaceFS, rel_path: str = "runs/run_ledger.jsonl") -> None:
        self.fs = fs
        self.rel_path = rel_path

    def append(self, *, run_id: str, kind: str, summary: dict[str, Any]) -> LedgerEvent:
        event = LedgerEvent(ts=utc_now_iso(), kind=kind, run_id=run_id, summary=summary)
        self.fs.append_jsonl(self.rel_path, event.__dict__)
        return event

    def tail(self, n: int = 10) -> list[dict[str, Any]]:
        try:
            raw = self.fs.read_text(self.rel_path)
        except Exception:
            return []
        items: list[dict[str, Any]] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except Exception:
                continue
        return items[-max(0, n) :] if n > 0 else []
