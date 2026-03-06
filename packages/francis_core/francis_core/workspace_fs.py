from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .clock import utc_now_iso
from .journal import append_jsonl


class WorkspaceFS:
    """Workspace-only file IO with audit journaling."""

    def __init__(self, *, roots: Iterable[Path], journal_path: Path) -> None:
        self.roots = [Path(r).resolve() for r in roots]
        if not self.roots:
            raise ValueError("WorkspaceFS requires at least one root")
        self.journal_path = Path(journal_path).resolve()

    def read_text(self, rel_path: str) -> str:
        path = self._resolve(rel_path)
        data = path.read_text(encoding="utf-8")
        self._journal("read_text", rel_path, len(data))
        return data

    def write_text(self, rel_path: str, content: str) -> None:
        path = self._resolve(rel_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        self._journal("write_text", rel_path, len(content))

    def _resolve(self, rel_path: str) -> Path:
        p = (self.roots[0] / rel_path).resolve()
        try:
            p.relative_to(self.roots[0])
        except ValueError as exc:
            raise ValueError(f"Path escapes workspace root: {rel_path}") from exc
        return p

    def _journal(self, op: str, rel_path: str, bytes_count: int) -> None:
        append_jsonl(
            self.journal_path,
            {
                "ts": utc_now_iso(),
                "op": op,
                "path": rel_path,
                "bytes": bytes_count,
            },
        )
