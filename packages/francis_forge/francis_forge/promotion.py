from __future__ import annotations

from typing import Any

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


def _merge_provenance(entry: dict[str, Any], *, review_state: str, actor: str, note: str, reviewed_at: str) -> dict[str, Any]:
    provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    merged = {
        **provenance,
        "review_state": review_state,
        "reviewed_at": reviewed_at,
        "reviewed_by": actor,
    }
    if note:
        merged["review_note"] = note
    return merged


def quarantine_entry(
    fs: WorkspaceFS,
    entry_id: str,
    *,
    reason: str,
    actor: str,
) -> dict | None:
    entries = list_entries(fs)
    target = next(
        (entry for entry in entries if isinstance(entry, dict) and str(entry.get("id", "")).strip() == str(entry_id).strip()),
        None,
    )
    if target is None:
        return None

    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Capability quarantined from Lens."
    normalized_actor = str(actor or "").strip() or "unknown"
    previous_status = str(target.get("status", "")).strip().lower() or "staged"

    return update_entry(
        fs,
        entry_id,
        {
            "status": "quarantined",
            "previous_status": previous_status,
            "quarantined_at": now,
            "quarantine_reason": normalized_reason,
            "quarantined_by": normalized_actor,
            "provenance": _merge_provenance(
                target,
                review_state="quarantined",
                actor=normalized_actor,
                note=normalized_reason,
                reviewed_at=now,
            ),
        },
    )


def revoke_entry(
    fs: WorkspaceFS,
    entry_id: str,
    *,
    reason: str,
    actor: str,
) -> dict | None:
    entries = list_entries(fs)
    target = next(
        (entry for entry in entries if isinstance(entry, dict) and str(entry.get("id", "")).strip() == str(entry_id).strip()),
        None,
    )
    if target is None:
        return None

    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Capability revoked from Lens."
    normalized_actor = str(actor or "").strip() or "unknown"
    previous_status = str(target.get("status", "")).strip().lower() or "active"
    patch: dict[str, Any] = {
        "status": "revoked",
        "previous_status": previous_status,
        "revoked_at": now,
        "revocation_reason": normalized_reason,
        "revoked_by": normalized_actor,
        "provenance": _merge_provenance(
            target,
            review_state="revoked",
            actor=normalized_actor,
            note=normalized_reason,
            reviewed_at=now,
        ),
    }
    if not target.get("quarantined_at"):
        patch["quarantined_at"] = None
    return update_entry(fs, entry_id, patch)
