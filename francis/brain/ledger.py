from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List

from francis.core.run_context import ActorKind, RunContext
from francis.core.workspace_fs import WorkspaceFS


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class LedgerEvent:
    ts: str
    kind: str
    run_id: str
    summary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "kind": self.kind,
            "run_id": self.run_id,
            "summary": self.summary,
        }


class RunLedger:
    """
    Minimal durable memory lane.
    Append-only JSONL under workspace/brain/run_ledger.jsonl.

    NOTE:
    - We keep it simple: append is implemented by read+write for now (single-user).
    - Later: true append with locks or a DB adapter.
    """

    def __init__(self, fs: WorkspaceFS, rel_path: str = "brain/run_ledger.jsonl") -> None:
        self.fs = fs
        self.rel_path = rel_path

    def append(
        self,
        *,
        run_id: str,
        kind: str,
        summary: Dict[str, Any],
        actor_name: str = "francis",
        reason: str = "ledger.append",
    ) -> LedgerEvent:
        event = LedgerEvent(ts=utc_now_iso(), kind=kind, run_id=run_id, summary=summary)
        ctx = RunContext(
            run_id=__import__("uuid").uuid4(),
            actor_kind=ActorKind.AGENT,
            actor_name=actor_name,
            reason=reason,
        )

        # Read existing -> append one line -> write back through WorkspaceFS (journals included).
        existing = ""
        try:
            existing = self.fs.read_text(ctx, self.rel_path)
        except Exception:
            existing = ""

        if existing and not existing.endswith("\n"):
            existing += "\n"

        new_content = existing + json.dumps(event.to_dict(), ensure_ascii=False) + "\n"
        self.fs.write_text(ctx, self.rel_path, new_content)
        return event

    def tail(self, n: int = 10) -> List[Dict[str, Any]]:
        # Safe tail by reading whole file (tiny for now).
        ctx = RunContext(
            run_id=__import__("uuid").uuid4(),
            actor_kind=ActorKind.SYSTEM,
            actor_name="francis",
            reason="ledger.tail",
        )
        try:
            raw = self.fs.read_text(ctx, self.rel_path)
        except Exception:
            return []

        lines = [ln for ln in raw.splitlines() if ln.strip()]
        tail_lines = lines[-max(0, n) :] if n > 0 else []
        out: List[Dict[str, Any]] = []
        for ln in tail_lines:
            try:
                out.append(json.loads(ln))
            except Exception:
                # Ignore malformed lines rather than failing presence.
                continue
        return out
