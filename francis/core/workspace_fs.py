from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from francis.core.run_context import RunContext


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class WorkspaceFS:
    """Workspace-only file IO with append-only journaling."""

    def __init__(self, *, roots: Iterable[Path], journal_path: Path) -> None:
        resolved_roots = [Path(r).resolve() for r in roots]
        if not resolved_roots:
            raise ValueError("WorkspaceFS requires at least one root")
        self.roots = resolved_roots
        self.journal_path = Path(journal_path).resolve()
        self.journal_path.parent.mkdir(parents=True, exist_ok=True)

    def read_text(self, ctx: RunContext, rel_path: str) -> str:
        path = self._resolve(rel_path)
        content = path.read_text(encoding="utf-8")
        self._append_journal(ctx=ctx, op="read_text", rel_path=rel_path, bytes_count=len(content))
        return content

    def write_text(self, ctx: RunContext, rel_path: str, content: str) -> None:
        path = self._resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._append_journal(ctx=ctx, op="write_text", rel_path=rel_path, bytes_count=len(content))

    def _resolve(self, rel_path: str) -> Path:
        if not rel_path or Path(rel_path).is_absolute():
            raise ValueError("Path must be non-empty and relative to workspace root")
        normalized = Path(rel_path)
        candidate = (self.roots[0] / normalized).resolve()
        if not self._is_under_root(candidate):
            raise ValueError(f"Path escapes workspace root: {rel_path}")
        return candidate

    def _is_under_root(self, candidate: Path) -> bool:
        for root in self.roots:
            try:
                candidate.relative_to(root)
                return True
            except ValueError:
                continue
        return False

    def _append_journal(self, *, ctx: RunContext, op: str, rel_path: str, bytes_count: int) -> None:
        entry = {
            "ts": _utc_now_iso(),
            "run_id": str(ctx.run_id),
            "actor_kind": ctx.actor_kind.value,
            "actor_name": ctx.actor_name,
            "reason": ctx.reason,
            "op": op,
            "path": rel_path,
            "bytes": bytes_count,
        }
        with self.journal_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

