from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
from francis_forge.library import (
    build_capability_library,
    build_capability_provenance,
    build_promotion_rules,
    build_quality_standard,
)

from services.orchestrator.app.approvals_store import ApprovalSnapshot, list_requests, load_approval_snapshot


def build_workspace_fs(workspace_root: Path) -> WorkspaceFS:
    resolved_workspace = workspace_root.resolve()
    return WorkspaceFS(
        roots=[resolved_workspace],
        journal_path=(resolved_workspace / "journals" / "fs.jsonl").resolve(),
    )


def _normalize_packs(value: object) -> list[dict[str, Any]]:
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _first_failed_rule_detail(rules: dict[str, Any]) -> str:
    for row in rules.get("rules", []) if isinstance(rules.get("rules"), list) else []:
        if not isinstance(row, dict):
            continue
        if bool(row.get("ok")):
            continue
        detail = str(row.get("detail", "")).strip()
        if detail:
            return detail
    return ""


def build_focus_pack(
    packs: list[dict[str, Any]],
    *,
    focus_pack_id: str = "",
) -> dict[str, Any] | None:
    if focus_pack_id:
        explicit = next(
            (pack for pack in packs if str(pack.get("pack_id", "")).strip() == focus_pack_id),
            None,
        )
        if explicit is not None:
            return explicit
    for pack in packs:
        if int(pack.get("staged_count", 0) or 0) > 0:
            return pack
    for pack in packs:
        focus_version = pack.get("focus_version", {}) if isinstance(pack.get("focus_version"), dict) else {}
        if str(focus_version.get("status", "")).strip().lower() == "quarantined":
            return pack
    for pack in packs:
        if int(pack.get("active_count", 0) or 0) > 0:
            return pack
    return packs[0] if packs else None


def _approval_index(
    fs: WorkspaceFS,
    *,
    action: str,
    metadata_keys: Iterable[str],
    snapshot: ApprovalSnapshot | None = None,
) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in list_requests(fs, action=action, limit=200, snapshot=snapshot):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        target_id = ""
        for key in metadata_keys:
            target_id = str(metadata.get(str(key).strip(), "")).strip()
            if target_id:
                break
        if target_id:
            indexed[target_id] = row
    return indexed


def build_capability_state(
    workspace_root: Path,
    *,
    approval_snapshot: ApprovalSnapshot | None = None,
) -> dict[str, Any]:
    fs = build_workspace_fs(workspace_root)
    approvals = approval_snapshot if isinstance(approval_snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    entries = [row for row in list_entries(fs) if isinstance(row, dict)]
    library = build_capability_library(entries)
    packs = _normalize_packs(library.get("packs"))
    focus_pack = build_focus_pack(packs)
    focus_entry = (
        focus_pack.get("focus_version", {})
        if isinstance(focus_pack, dict) and isinstance(focus_pack.get("focus_version"), dict)
        else {}
    )
    return {
        "catalog_count": len(entries),
        "library": library,
        "packs": packs,
        "focus_pack": dict(focus_pack) if isinstance(focus_pack, dict) else {},
        "focus_entry": dict(focus_entry) if isinstance(focus_entry, dict) else {},
        "promote_approvals": _approval_index(
            fs,
            action="forge.promote",
            metadata_keys=("entry_id", "stage_id"),
            snapshot=approvals,
        ),
        "revoke_approvals": _approval_index(
            fs,
            action="forge.revoke",
            metadata_keys=("entry_id", "stage_id"),
            snapshot=approvals,
        ),
    }


def build_capability_focus(capability_state: dict[str, Any]) -> dict[str, Any]:
    library = capability_state.get("library", {}) if isinstance(capability_state.get("library"), dict) else {}
    focus_pack = capability_state.get("focus_pack", {}) if isinstance(capability_state.get("focus_pack"), dict) else {}
    focus_entry = (
        capability_state.get("focus_entry", {})
        if isinstance(capability_state.get("focus_entry"), dict)
        else {}
    )
    promote_approvals = (
        capability_state.get("promote_approvals", {})
        if isinstance(capability_state.get("promote_approvals"), dict)
        else {}
    )
    revoke_approvals = (
        capability_state.get("revoke_approvals", {})
        if isinstance(capability_state.get("revoke_approvals"), dict)
        else {}
    )
    staged_count = int(library.get("staged_pack_count", 0) or 0)
    active_count = int(library.get("active_pack_count", 0) or 0)

    if not focus_entry:
        return {
            "catalog_count": int(capability_state.get("catalog_count", 0) or 0),
            "pack_count": int(library.get("pack_count", 0) or 0),
            "staged_count": staged_count,
            "active_count": active_count,
            "summary": "No governed capability packs are cataloged yet.",
            "focus_entry": None,
        }

    entry_id = str(focus_entry.get("id", "")).strip()
    status = str(focus_entry.get("status", "")).strip().lower() or "staged"
    promote_approval = promote_approvals.get(entry_id) if entry_id else None
    promote_approval_id = str((promote_approval or {}).get("id", "")).strip()
    promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
    revoke_approval = revoke_approvals.get(entry_id) if entry_id else None
    revoke_approval_id = str((revoke_approval or {}).get("id", "")).strip()
    revoke_approval_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    version = str(focus_entry.get("version", "")).strip() or "0.1.0"
    name = str(focus_entry.get("name", "Capability pack")).strip() or "Capability pack"
    risk_tier = str(focus_entry.get("risk_tier", "low")).strip().lower() or "low"
    tool_pack = focus_entry.get("tool_pack", {}) if isinstance(focus_entry.get("tool_pack"), dict) else {}
    diff_summary = focus_entry.get("diff_summary", {}) if isinstance(focus_entry.get("diff_summary"), dict) else {}
    quality_standard = build_quality_standard(focus_entry)
    promotion_rules = build_promotion_rules(focus_entry, approval_status=promote_approval_status)
    provenance = build_capability_provenance(focus_entry, approval_status=promote_approval_status)
    pack_id = str(focus_pack.get("pack_id", "")).strip() or str(focus_entry.get("slug", "")).strip()
    version_count = int(focus_pack.get("version_count", 0) or 0)
    first_failed_rule = _first_failed_rule_detail(promotion_rules)
    approval_action = ""
    approval_id = ""
    approval_status = ""

    if status == "quarantined":
        summary = (
            f"{name} {version} in pack {pack_id} is quarantined and blocked from further use. "
            "Revoke it to keep only audit continuity."
        )
        recommended_action = "forge.revoke"
        approval_action = "forge.revoke"
        approval_id = revoke_approval_id
        approval_status = revoke_approval_status
    elif status == "staged" and (
        str(provenance.get("review_state", "")).strip() in {"rejected", "quarantined", "revoked"}
        or (bool(provenance.get("external")) and not bool(provenance.get("traceable")))
    ):
        summary = (
            f"{name} {version} in pack {pack_id} should be quarantined before any promotion path continues. "
            f"{str(provenance.get('summary', '')).strip()}"
        ).strip()
        recommended_action = "forge.quarantine"
    elif status == "staged":
        if promote_approval_status == "approved" and promote_approval_id and bool(promotion_rules.get("ready")):
            summary = f"{name} {version} in pack {pack_id} is staged and already approved for promotion."
        elif promote_approval_status == "approved" and promote_approval_id:
            summary = (
                f"{name} {version} in pack {pack_id} has approval recorded but still needs policy review before promotion. "
                f"{first_failed_rule or str(provenance.get('summary', '')).strip()}"
            ).strip()
        elif promote_approval_status == "pending" and promote_approval_id:
            summary = f"{name} {version} in pack {pack_id} is staged and waiting on promotion approval {promote_approval_id}."
        elif promote_approval_status == "rejected":
            summary = f"{name} {version} in pack {pack_id} is staged after a rejected promotion request and needs a fresh operator decision."
        else:
            summary = f"{name} {version} in pack {pack_id} is staged and ready for governed promotion into the active library."
        recommended_action = "forge.promote"
        approval_action = "forge.promote"
        approval_id = promote_approval_id
        approval_status = promote_approval_status
    elif status in {"active", "superseded"} and str(provenance.get("review_state", "")).strip() in {
        "rejected",
        "quarantined",
        "revoked",
    }:
        summary = (
            f"{name} {version} in pack {pack_id} has review posture {str(provenance.get('review_label', 'revoked')).strip()} "
            "and should be revoked from governed use."
        )
        recommended_action = "forge.revoke"
        approval_action = "forge.revoke"
        approval_id = revoke_approval_id
        approval_status = revoke_approval_status
    elif status == "active":
        summary = f"{name} {version} is active in pack {pack_id} inside the internal capability library."
        recommended_action = ""
    else:
        summary = f"{name} {version} is cataloged in pack {pack_id} with status {status}."
        recommended_action = ""

    provenance_summary = str(provenance.get("summary", "")).strip()
    if provenance_summary and provenance.get("kind") != "internal" and provenance_summary not in summary:
        summary = f"{summary} {provenance_summary}".strip()

    return {
        "catalog_count": int(capability_state.get("catalog_count", 0) or 0),
        "pack_count": int(library.get("pack_count", 0) or 0),
        "staged_count": staged_count,
        "active_count": active_count,
        "summary": summary,
        "focus_entry": {
            "id": entry_id,
            "pack_id": pack_id,
            "name": name,
            "slug": str(focus_entry.get("slug", "")).strip(),
            "version": version,
            "status": status,
            "risk_tier": risk_tier,
            "path": str(focus_entry.get("path", "")).strip(),
            "approval_id": approval_id,
            "approval_status": approval_status,
            "approval_action": approval_action,
            "summary": summary,
            "recommended_action": recommended_action,
            "actionable": bool(
                (
                    recommended_action == "forge.promote"
                    and entry_id
                    and bool(promotion_rules.get("ready"))
                    and approval_status == "approved"
                )
                or (recommended_action == "forge.quarantine" and entry_id)
                or (recommended_action == "forge.revoke" and entry_id and approval_status == "approved")
            ),
            "validation_ok": bool(quality_standard.get("ok")),
            "quality_standard": quality_standard,
            "promotion_rules": promotion_rules,
            "provenance": provenance,
            "version_count": version_count,
            "active_version": str(focus_pack.get("active_version", "")).strip(),
            "file_count": int(diff_summary.get("file_count", 0) or 0),
            "tool_pack_skill": str(tool_pack.get("skill_name", "")).strip(),
        },
    }
