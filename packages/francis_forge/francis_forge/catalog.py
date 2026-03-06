from __future__ import annotations

import json
from typing import Any

from francis_core.workspace_fs import WorkspaceFS


def _load(fs: WorkspaceFS, rel_path: str) -> dict[str, Any]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return {"entries": []}
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            entries = parsed.get("entries")
            if isinstance(entries, list):
                return parsed
    except Exception:
        pass
    return {"entries": []}


def _save(fs: WorkspaceFS, rel_path: str, doc: dict[str, Any]) -> None:
    fs.write_text(rel_path, json.dumps(doc, ensure_ascii=False, indent=2))


def list_entries(fs: WorkspaceFS, rel_path: str = "forge/catalog.json") -> list[dict[str, Any]]:
    doc = _load(fs, rel_path)
    return [e for e in doc.get("entries", []) if isinstance(e, dict)]


def add_entry(fs: WorkspaceFS, entry: dict[str, Any], rel_path: str = "forge/catalog.json") -> dict[str, Any]:
    doc = _load(fs, rel_path)
    entries = [e for e in doc.get("entries", []) if isinstance(e, dict)]
    entries = [e for e in entries if e.get("id") != entry.get("id")]
    entries.append(entry)
    doc["entries"] = entries
    _save(fs, rel_path, doc)
    return entry


def update_entry(fs: WorkspaceFS, entry_id: str, patch: dict[str, Any], rel_path: str = "forge/catalog.json") -> dict[str, Any] | None:
    doc = _load(fs, rel_path)
    entries = [e for e in doc.get("entries", []) if isinstance(e, dict)]
    updated: dict[str, Any] | None = None
    for i, entry in enumerate(entries):
        if entry.get("id") == entry_id:
            merged = {**entry, **patch}
            entries[i] = merged
            updated = merged
            break
    if updated is None:
        return None
    doc["entries"] = entries
    _save(fs, rel_path, doc)
    return updated
