from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS

from .parsing import clamp_int, truncate_text


def _workspace_root(fs: WorkspaceFS) -> Path:
    return fs.roots[0]


def _resolve_within_workspace(fs: WorkspaceFS, rel_path: str) -> Path:
    root = _workspace_root(fs)
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {rel_path}") from exc
    return candidate


def _to_rel_path(fs: WorkspaceFS, path: Path) -> str:
    return str(path.relative_to(_workspace_root(fs))).replace("\\", "/")


def workspace_read(fs: WorkspaceFS, *, path: str, max_chars: int = 20000) -> dict[str, Any]:
    resolved = _resolve_within_workspace(fs, path)
    rel = _to_rel_path(fs, resolved)
    text = fs.read_text(rel)
    clipped = truncate_text(text, clamp_int(max_chars, minimum=1, maximum=200000))
    return {"path": rel, "content": clipped, "bytes": len(text), "truncated": len(clipped) < len(text)}


def workspace_write(fs: WorkspaceFS, *, path: str, content: str, append: bool = False) -> dict[str, Any]:
    resolved = _resolve_within_workspace(fs, path)
    rel = _to_rel_path(fs, resolved)

    final = content
    if append:
        try:
            existing = fs.read_text(rel)
        except Exception:
            existing = ""
        if existing and not existing.endswith("\n") and content and not content.startswith("\n"):
            existing += "\n"
        final = existing + content

    fs.write_text(rel, final)
    return {"path": rel, "bytes": len(final), "append": append}


def workspace_search(
    fs: WorkspaceFS,
    *,
    query: str,
    path: str = ".",
    max_hits: int = 20,
    max_file_bytes: int = 500_000,
) -> dict[str, Any]:
    if not query.strip():
        raise ValueError("query cannot be empty")

    root = _resolve_within_workspace(fs, path)
    hits: list[dict[str, Any]] = []
    query_lower = query.lower()
    max_hits = clamp_int(max_hits, minimum=1, maximum=500)
    max_file_bytes = clamp_int(max_file_bytes, minimum=1_024, maximum=5_000_000)

    candidates: list[Path]
    if root.is_file():
        candidates = [root]
    else:
        candidates = [item for item in root.rglob("*") if item.is_file()]

    for file_path in candidates:
        if len(hits) >= max_hits:
            break
        try:
            if file_path.stat().st_size > max_file_bytes:
                continue
        except Exception:
            continue

        rel = _to_rel_path(fs, file_path)
        try:
            text = fs.read_text(rel)
        except Exception:
            continue

        for line_no, line in enumerate(text.splitlines(), start=1):
            if query_lower not in line.lower():
                continue
            hits.append(
                {
                    "path": rel,
                    "line": line_no,
                    "snippet": truncate_text(line.strip(), 240),
                }
            )
            if len(hits) >= max_hits:
                break

    return {"query": query, "path": _to_rel_path(fs, root), "hits": hits, "count": len(hits)}
