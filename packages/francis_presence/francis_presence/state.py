from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS


@dataclass(frozen=True)
class PresenceState:
    utc_now: str
    workspace_root: str
    inbox_count: int
    inbox_alerts: int
    last_ledger: list[dict]

    def to_dict(self) -> dict:
        return {
            "utc_now": self.utc_now,
            "workspace_root": self.workspace_root,
            "inbox_count": self.inbox_count,
            "inbox_alerts": self.inbox_alerts,
            "last_ledger": self.last_ledger,
        }


def _count_inbox(fs: WorkspaceFS, inbox_rel: str = "inbox/messages.jsonl") -> tuple[int, int]:
    try:
        raw = fs.read_text(inbox_rel)
    except Exception:
        return (0, 0)
    total = 0
    alerts = 0
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        total += 1
        try:
            item = json.loads(line)
            if item.get("severity") == "alert":
                alerts += 1
        except Exception:
            continue
    return (total, alerts)


def compute_state(fs: WorkspaceFS, ledger: RunLedger, workspace_root: Path) -> PresenceState:
    inbox_count, inbox_alerts = _count_inbox(fs)
    return PresenceState(
        utc_now=utc_now_iso(),
        workspace_root=str(workspace_root),
        inbox_count=inbox_count,
        inbox_alerts=inbox_alerts,
        last_ledger=ledger.tail(5),
    )
