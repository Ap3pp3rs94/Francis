from __future__ import annotations

from francis_forge.catalog import list_entries, update_entry
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

from .library import build_quality_standard, normalize_version


def promote_stage(fs: WorkspaceFS, stage_id: str) -> dict | None:
    entries = list_entries(fs)
    target = next(
        (entry for entry in entries if isinstance(entry, dict) and str(entry.get("id", "")).strip() == str(stage_id).strip()),
        None,
    )
    if target is None:
        return None

    quality = build_quality_standard(target)
    if not bool(quality.get("ok")):
        raise ValueError(str(quality.get("summary", "")).strip() or "Capability does not meet promotion quality standards.")

    slug = str(target.get("slug", "")).strip()
    now = utc_now_iso()
    if slug:
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            if str(entry.get("id", "")).strip() == str(stage_id).strip():
                continue
            if str(entry.get("slug", "")).strip() != slug:
                continue
            if str(entry.get("status", "")).strip().lower() != "active":
                continue
            update_entry(
                fs,
                str(entry.get("id", "")).strip(),
                {
                    "status": "superseded",
                    "superseded_at": now,
                    "superseded_by": str(stage_id).strip(),
                },
            )

    return update_entry(
        fs,
        stage_id,
        {
            "status": "active",
            "promoted_at": now,
            "pack_id": slug or str(target.get("pack_id", "")).strip() or str(target.get("id", "")).strip(),
            "version": normalize_version(target.get("version")),
            "quality_standard": quality,
        },
    )
