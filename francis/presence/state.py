from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from francis.core.run_context import ActorKind, RunContext
from francis.core.workspace_fs import WorkspaceFS
from francis.brain.ledger import RunLedger


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class PresenceState:
    utc_now: str
    workspace_root: str
    inbox_count: int
    inbox_alerts: int
    last_ledger: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "utc_now": self.utc_now,
            "workspace_root": self.workspace_root,
            "inbox_count": self.inbox_count,
            "inbox_alerts": self.inbox_alerts,
            "last_ledger": self.last_ledger,
        }


def _count_inbox(fs: WorkspaceFS, inbox_rel: str = "inbox/messages.jsonl") -> tuple[int, int]:
    """
    Returns (total_count, alert_count).
    Missing file => (0,0)
    """
    ctx = RunContext(
        run_id=__import__("uuid").uuid4(),
        actor_kind=ActorKind.SYSTEM,
        actor_name="francis",
        reason="presence.state.count_inbox",
    )

    try:
        raw = fs.read_text(ctx, inbox_rel)
    except Exception:
        return (0, 0)

    total = 0
    alerts = 0
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        total += 1
        try:
            obj = json.loads(ln)
            if obj.get("severity") == "alert":
                alerts += 1
        except Exception:
            # malformed line still counts as message
            continue
    return (total, alerts)


def compute_state(fs: WorkspaceFS, ledger: RunLedger, workspace_root: Path) -> PresenceState:
    inbox_count, inbox_alerts = _count_inbox(fs)
    last_ledger = ledger.tail(5)
    return PresenceState(
        utc_now=utc_now_iso(),
        workspace_root=str(workspace_root),
        inbox_count=inbox_count,
        inbox_alerts=inbox_alerts,
        last_ledger=last_ledger,
    )

