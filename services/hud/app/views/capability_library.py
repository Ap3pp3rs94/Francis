from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
from francis_forge.library import (
    build_capability_library,
    build_capability_provenance,
    build_promotion_rules,
    build_quality_standard,
)
from services.hud.app.state import build_lens_snapshot, get_workspace_root
from services.orchestrator.app.approvals_store import list_requests
from services.orchestrator.app.control_state import check_action_allowed


def _workspace_context(workspace_root: Path | None = None) -> tuple[Path, Path, WorkspaceFS]:
    root = (workspace_root or get_workspace_root()).resolve()
    repo_root = root.parent.resolve()
    fs = WorkspaceFS(
        roots=[root],
        journal_path=(root / "journals" / "fs.jsonl").resolve(),
    )
    return root, repo_root, fs


def _action_allowed(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    app: str,
    action: str,
    mutating: bool,
) -> tuple[bool, str]:
    allowed, reason, _state = check_action_allowed(
        fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app=app,
        action=action,
        mutating=mutating,
    )
    return allowed, reason


def _entry_version(entry: dict[str, Any]) -> str:
    version = str(entry.get("version", "")).strip()
    return version or "0.1.0"


def _entry_status(entry: dict[str, Any]) -> str:
    return str(entry.get("status", "")).strip().lower() or "staged"


def _pack_id(entry: dict[str, Any]) -> str:
    return str(entry.get("pack_id", "")).strip() or str(entry.get("slug", "")).strip() or str(entry.get("id", "")).strip()


def _approval_for_entry(fs: WorkspaceFS, entry_id: str, *, action: str) -> dict[str, Any] | None:
    requests = list_requests(fs, action=action, limit=50)
    for row in reversed(requests):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        target_id = str(metadata.get("entry_id", "")).strip() or str(metadata.get("stage_id", "")).strip()
        if target_id != entry_id:
            continue
        return row
    return None


def _focus_pack(
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


def _detail_state(pack_id: str, focus_pack_id: str) -> str:
    if not pack_id:
        return "historical"
    return "current" if pack_id == focus_pack_id else "historical"


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


def _detail_cards(
    entry: dict[str, Any],
    promote_approval: dict[str, Any] | None,
    revoke_approval: dict[str, Any] | None,
    pack: dict[str, Any],
) -> list[dict[str, str]]:
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
    revoke_approval_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    quality = build_quality_standard(entry)
    provenance = build_capability_provenance(entry, approval_status=promote_approval_status)
    status = _entry_status(entry)
    lifecycle_value = (
        "quarantined"
        if status == "quarantined"
        else "revoked"
        if status == "revoked"
        else "governed"
    )
    return [
        {
            "label": "Status",
            "value": status,
            "tone": (
                "high"
                if status in {"quarantined", "revoked"}
                else "medium" if status == "staged" else "low" if status == "active" else "medium"
            ),
        },
        {
            "label": "Version",
            "value": _entry_version(entry),
            "tone": "low",
        },
        {
            "label": "Risk",
            "value": str(entry.get("risk_tier", "low")).strip().lower() or "low",
            "tone": "medium" if str(entry.get("risk_tier", "low")).strip().lower() in {"medium", "high"} else "low",
        },
        {
            "label": "Validation",
            "value": "passed" if bool(validation.get("ok")) else "needs review",
            "tone": "low" if bool(validation.get("ok")) else "high",
        },
        {
            "label": "Quality",
            "value": str(quality.get("score", "")).strip() or "0/0",
            "tone": "low" if bool(quality.get("ok")) else "high",
        },
        {
            "label": "Files",
            "value": str(int(diff_summary.get("file_count", 0) or 0)),
            "tone": "low" if int(diff_summary.get("file_count", 0) or 0) > 0 else "medium",
        },
        {
            "label": "Pack Versions",
            "value": str(int(pack.get("version_count", 0) or 0)),
            "tone": "low" if int(pack.get("version_count", 0) or 0) > 1 else "medium",
        },
        {
            "label": "Provenance",
            "value": str(provenance.get("label", "Internal")).strip() or "Internal",
            "tone": str(provenance.get("tone", "low")).strip() or "low",
        },
        {
            "label": "Review",
            "value": str(provenance.get("review_label", "self-governed")).strip() or "self-governed",
            "tone": (
                "low"
                if str(provenance.get("review_state", "")).strip() in {"approved", "internal"}
                else "high"
                if str(provenance.get("review_state", "")).strip() in {"quarantined", "revoked", "rejected"}
                else "medium"
            ),
        },
        {
            "label": "Source",
            "value": str(provenance.get("source_label", "generated inside Francis")).strip() or "generated inside Francis",
            "tone": "low" if bool(provenance.get("traceable")) else "high",
        },
        {
            "label": "Lifecycle",
            "value": lifecycle_value,
            "tone": "high" if lifecycle_value in {"quarantined", "revoked"} else "low",
        },
        {
            "label": "Promotion",
            "value": promote_approval_status or ("active" if status == "active" else "not requested"),
            "tone": "medium" if promote_approval_status == "pending" else "low",
        },
        {
            "label": "Revocation",
            "value": revoke_approval_status or ("complete" if status == "revoked" else "not requested"),
            "tone": "medium" if revoke_approval_status == "pending" else "high" if status == "revoked" else "low",
        },
        {
            "label": "Tool Pack",
            "value": str(tool_pack.get("skill_name", "")).strip() or "not registered",
            "tone": "low" if str(tool_pack.get("skill_name", "")).strip() else "medium",
        },
    ]


def _audit(
    entry: dict[str, Any],
    promote_approval: dict[str, Any] | None,
    revoke_approval: dict[str, Any] | None,
    detail_state: str,
    pack: dict[str, Any],
) -> dict[str, Any]:
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    quality_standard = build_quality_standard(entry)
    promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
    revoke_approval_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    status = _entry_status(entry)
    promotion_rules = build_promotion_rules(entry, approval_status=promote_approval_status)
    provenance = build_capability_provenance(entry, approval_status=promote_approval_status)
    approval_action = "forge.promote" if status == "staged" else "forge.revoke" if status in {"active", "quarantined", "superseded"} else ""
    active_approval = promote_approval if approval_action == "forge.promote" else revoke_approval if approval_action == "forge.revoke" else None
    return {
        "id": str(entry.get("id", "")).strip(),
        "pack_id": _pack_id(entry),
        "status": status,
        "version": _entry_version(entry),
        "name": str(entry.get("name", "")).strip(),
        "slug": str(entry.get("slug", "")).strip(),
        "risk_tier": str(entry.get("risk_tier", "low")).strip().lower() or "low",
        "detail_state": detail_state,
        "path": str(entry.get("path", "")).strip(),
        "validation_ok": bool(validation.get("ok")),
        "file_count": int(diff_summary.get("file_count", 0) or 0),
        "approval_action": approval_action,
        "approval_id": str((active_approval or {}).get("id", "")).strip(),
        "approval_status": str((active_approval or {}).get("status", "")).strip().lower(),
        "promote_approval_id": str((promote_approval or {}).get("id", "")).strip(),
        "promote_approval_status": promote_approval_status,
        "revoke_approval_id": str((revoke_approval or {}).get("id", "")).strip(),
        "revoke_approval_status": revoke_approval_status,
        "tool_pack_skill": str(tool_pack.get("skill_name", "")).strip(),
        "promoted_at": str(entry.get("promoted_at", "")).strip(),
        "quarantined_at": entry.get("quarantined_at"),
        "quarantine_reason": str(entry.get("quarantine_reason", "")).strip(),
        "quarantined_by": str(entry.get("quarantined_by", "")).strip(),
        "revoked_at": entry.get("revoked_at"),
        "revocation_reason": str(entry.get("revocation_reason", "")).strip(),
        "revoked_by": str(entry.get("revoked_by", "")).strip(),
        "previous_status": str(entry.get("previous_status", "")).strip().lower(),
        "quality_standard": quality_standard,
        "promotion_rules": promotion_rules,
        "provenance": provenance,
        "pack": {
            "pack_id": str(pack.get("pack_id", "")).strip(),
            "version_count": int(pack.get("version_count", 0) or 0),
            "active_version": str(pack.get("active_version", "")).strip() or None,
            "latest_version": str(pack.get("latest_version", "")).strip() or None,
            "staged_count": int(pack.get("staged_count", 0) or 0),
            "active_count": int(pack.get("active_count", 0) or 0),
            "superseded_count": int(pack.get("superseded_count", 0) or 0),
            "versions": pack.get("versions", []) if isinstance(pack.get("versions"), list) else [],
        },
    }


def _row_controls(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    entry: dict[str, Any],
    promote_approval: dict[str, Any] | None,
    revoke_approval: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    entry_id = str(entry.get("id", "")).strip()
    status = _entry_status(entry)
    promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
    promote_approval_id = str((promote_approval or {}).get("id", "")).strip()
    revoke_approval_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    revoke_approval_id = str((revoke_approval or {}).get("id", "")).strip()
    provenance = build_capability_provenance(entry, approval_status=promote_approval_status)
    promotion_rules = build_promotion_rules(entry, approval_status=promote_approval_status)
    promotion_ready = bool(promotion_rules.get("ready"))
    promotion_blocker = _first_failed_rule_detail(promotion_rules) or str(provenance.get("promotion_rule_detail", "")).strip()
    promote_allowed, promote_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="forge",
        action="forge.promote",
        mutating=True,
    )
    quarantine_allowed, quarantine_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="forge",
        action="forge.quarantine",
        mutating=True,
    )
    revoke_allowed, revoke_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="forge",
        action="forge.revoke",
        mutating=True,
    )
    request_allowed, request_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="approvals",
        action="approvals.request",
        mutating=False,
    )
    return {
        "request_approval": {
            "kind": "forge.promote.request_approval",
            "label": "Request Promotion Approval",
            "enabled": status == "staged" and promote_approval_status not in {"pending", "approved"} and request_allowed,
            "summary": (
                f"Request approval to promote {str(entry.get('name', 'staged capability')).strip() or 'the staged capability'}."
                if status == "staged" and promote_approval_status not in {"pending", "approved"} and request_allowed
                else f"Promotion approval is waiting as {promote_approval_status}."
                if promote_approval_status in {"pending", "approved"}
                else f"Promotion approval is blocked: {request_reason}."
            ),
            "control_type": "execute",
            "execute_kind": "forge.promote.request_approval",
            "args": {"stage_id": entry_id},
        },
        "promote": {
            "kind": "forge.promote",
            "label": "Promote Capability",
            "enabled": status == "staged" and promote_approval_status == "approved" and promote_allowed and promotion_ready,
            "summary": (
                f"Promote {str(entry.get('name', 'staged capability')).strip() or 'the staged capability'} into the active library."
                if status == "staged" and promote_approval_status == "approved" and promote_allowed and promotion_ready
                else "Capability is already active."
                if status == "active"
                else promotion_blocker
                if status == "staged" and promote_approval_status == "approved" and not promotion_ready
                else f"Promotion is waiting on approval {promote_approval_id}."
                if promote_approval_status == "pending"
                else f"Promotion is blocked: {promote_reason}."
                if not promote_allowed
                else "Promotion requires approval before execution."
            ),
            "control_type": "execute",
            "execute_kind": "forge.promote",
            "args": {"stage_id": entry_id, "approval_id": promote_approval_id},
        },
        "quarantine": {
            "kind": "forge.quarantine",
            "label": "Quarantine Capability",
            "enabled": bool(entry_id) and status in {"staged", "active"} and quarantine_allowed,
            "summary": (
                "Quarantine this capability and remove it from governed promotion/use."
                if bool(entry_id) and status in {"staged", "active"} and quarantine_allowed
                else "Only staged or active capability entries can be quarantined."
                if status not in {"staged", "active"}
                else f"Capability quarantine is blocked: {quarantine_reason}."
            ),
            "control_type": "execute",
            "execute_kind": "forge.quarantine",
            "args": {"entry_id": entry_id},
        },
        "request_revoke": {
            "kind": "forge.revoke.request_approval",
            "label": "Request Revocation Approval",
            "enabled": status in {"active", "quarantined", "superseded"} and revoke_approval_status not in {"pending", "approved"} and request_allowed,
            "summary": (
                f"Request approval to revoke {str(entry.get('name', 'capability')).strip() or 'the capability'}."
                if status in {"active", "quarantined", "superseded"} and revoke_approval_status not in {"pending", "approved"} and request_allowed
                else f"Revocation approval is waiting as {revoke_approval_status}."
                if revoke_approval_status in {"pending", "approved"}
                else "Only active, quarantined, or superseded capability entries can be revoked."
                if status not in {"active", "quarantined", "superseded"}
                else f"Revocation approval is blocked: {request_reason}."
            ),
            "control_type": "execute",
            "execute_kind": "forge.revoke.request_approval",
            "args": {"entry_id": entry_id},
        },
        "revoke": {
            "kind": "forge.revoke",
            "label": "Revoke Capability",
            "enabled": status in {"active", "quarantined", "superseded"} and revoke_approval_status == "approved" and revoke_allowed,
            "summary": (
                f"Revoke {str(entry.get('name', 'capability')).strip() or 'the capability'} and keep only audit continuity."
                if status in {"active", "quarantined", "superseded"} and revoke_approval_status == "approved" and revoke_allowed
                else "Capability is already revoked."
                if status == "revoked"
                else f"Revocation is waiting on approval {revoke_approval_id}."
                if revoke_approval_status == "pending"
                else f"Revocation is blocked: {revoke_reason}."
                if not revoke_allowed
                else "Revocation requires approval before execution."
            ),
            "control_type": "execute",
            "execute_kind": "forge.revoke",
            "args": {"entry_id": entry_id, "approval_id": revoke_approval_id},
        },
    }


def _entry_summary(
    entry: dict[str, Any],
    promote_approval: dict[str, Any] | None,
    revoke_approval: dict[str, Any] | None,
    pack: dict[str, Any],
) -> str:
    status = _entry_status(entry)
    version = _entry_version(entry)
    name = str(entry.get("name", "Capability pack")).strip() or "Capability pack"
    promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
    revoke_approval_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    provenance = build_capability_provenance(entry, approval_status=promote_approval_status)
    promotion_rules = build_promotion_rules(entry, approval_status=promote_approval_status)
    promotion_blocker = _first_failed_rule_detail(promotion_rules)
    if status == "staged":
        suffix = (
            f" Approval is {promote_approval_status}."
            if promote_approval_status
            else " Promotion approval has not been requested yet."
        )
        summary = (
            f"{name} {version} is staged in pack {str(pack.get('pack_id', '')).strip() or 'capability'} "
            f"with {int(pack.get('version_count', 0) or 0)} version(s).{suffix}"
        )
        if not bool(promotion_rules.get("ready")):
            summary = f"{summary} {promotion_blocker or str(provenance.get('promotion_rule_detail', '')).strip()}".strip()
        elif provenance.get("kind") != "internal":
            summary = f"{summary} {str(provenance.get('summary', '')).strip()}".strip()
        return summary
    if status == "quarantined":
        summary = (
            f"{name} {version} is quarantined in pack {str(pack.get('pack_id', '')).strip() or 'capability'} "
            "and blocked from governed use."
        )
        if revoke_approval_status:
            summary = f"{summary} Revocation approval is {revoke_approval_status}.".strip()
        quarantine_reason = str(entry.get("quarantine_reason", "")).strip()
        if quarantine_reason:
            summary = f"{summary} {quarantine_reason}".strip()
        return summary
    if status == "active":
        summary = (
            f"{name} {version} is active in pack {str(pack.get('pack_id', '')).strip() or 'capability'} "
            f"with {int(pack.get('version_count', 0) or 0)} tracked version(s)."
        )
        if revoke_approval_status:
            summary = f"{summary} Revocation approval is {revoke_approval_status}.".strip()
        if provenance.get("kind") != "internal":
            summary = f"{summary} {str(provenance.get('summary', '')).strip()}".strip()
        return summary
    if status == "revoked":
        summary = (
            f"{name} {version} is revoked in pack {str(pack.get('pack_id', '')).strip() or 'capability'} "
            "and remains cataloged only for audit continuity."
        )
        revocation_reason = str(entry.get("revocation_reason", "")).strip()
        if revocation_reason:
            summary = f"{summary} {revocation_reason}".strip()
        return summary
    summary = f"{name} {version} is cataloged in pack {str(pack.get('pack_id', '')).strip() or 'capability'} with status {status}."
    if provenance.get("kind") != "internal":
        summary = f"{summary} {str(provenance.get('summary', '')).strip()}".strip()
    return summary


def get_capability_library_view(
    *,
    snapshot: dict[str, object] | None = None,
) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    workspace_root, repo_root, fs = _workspace_context()
    entries = [row for row in list_entries(fs) if isinstance(row, dict)]
    library = build_capability_library(entries)
    packs = [row for row in library.get("packs", []) if isinstance(row, dict)]
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    capabilities = current_work.get("capabilities", {}) if isinstance(current_work.get("capabilities"), dict) else {}
    capability_focus = (
        capabilities.get("focus_entry", {}) if isinstance(capabilities.get("focus_entry"), dict) else {}
    )
    requested_focus_pack_id = str(capability_focus.get("pack_id", "")).strip() or str(capability_focus.get("slug", "")).strip()
    focus_pack = _focus_pack(packs, focus_pack_id=requested_focus_pack_id)
    focus_entry = (
        focus_pack.get("focus_version", {})
        if isinstance(focus_pack, dict) and isinstance(focus_pack.get("focus_version"), dict)
        else {}
    )
    focus_pack_id = str((focus_pack or {}).get("pack_id", "")).strip()
    focus_entry_id = str(focus_entry.get("id", "")).strip()

    rows: list[dict[str, Any]] = []
    staged_count = 0
    active_count = 0
    superseded_count = 0
    external_count = 0
    review_required_count = 0
    quarantined_count = 0
    revoked_count = 0
    high_provenance_count = 0
    for pack in packs:
        entry = pack.get("focus_version", {}) if isinstance(pack.get("focus_version"), dict) else {}
        if not entry:
            continue
        status = _entry_status(entry)
        if status == "staged":
            staged_count += 1
        if status == "active":
            active_count += 1
        if status == "superseded":
            superseded_count += 1
        promote_approval = _approval_for_entry(fs, str(entry.get("id", "")).strip(), action="forge.promote")
        revoke_approval = _approval_for_entry(fs, str(entry.get("id", "")).strip(), action="forge.revoke")
        promote_approval_status = str((promote_approval or {}).get("status", "")).strip().lower()
        provenance = build_capability_provenance(entry, approval_status=promote_approval_status)
        if bool(provenance.get("external")):
            external_count += 1
        if bool(provenance.get("review_required")):
            review_required_count += 1
        if bool(provenance.get("quarantined")):
            quarantined_count += 1
        if bool(provenance.get("revoked")):
            revoked_count += 1
        if str(provenance.get("tone", "")).strip() == "high":
            high_provenance_count += 1
        detail_state = _detail_state(str(pack.get("pack_id", "")).strip(), focus_pack_id)
        rows.append(
            {
                "id": str(entry.get("id", "")).strip(),
                "pack_id": str(pack.get("pack_id", "")).strip(),
                "name": str(entry.get("name", "Capability pack")).strip() or "Capability pack",
                "version": _entry_version(entry),
                "status": status,
                "risk_tier": str(entry.get("risk_tier", "low")).strip().lower() or "low",
                "provenance_label": str(provenance.get("label", "Internal")).strip() or "Internal",
                "provenance_tone": str(provenance.get("tone", "low")).strip() or "low",
                "provenance_summary": str(provenance.get("summary", "")).strip(),
                "summary": _entry_summary(entry, promote_approval, revoke_approval, pack),
                "detail_summary": _entry_summary(entry, promote_approval, revoke_approval, pack),
                "detail_state": detail_state,
                "detail_cards": _detail_cards(entry, promote_approval, revoke_approval, pack),
                "audit": _audit(entry, promote_approval, revoke_approval, detail_state, pack),
                "controls": _row_controls(
                    fs=fs,
                    repo_root=repo_root,
                    workspace_root=workspace_root,
                    entry=entry,
                    promote_approval=promote_approval,
                    revoke_approval=revoke_approval,
                ),
            }
        )

    severity = "high" if high_provenance_count > 0 else "medium" if staged_count > 0 or review_required_count > 0 or external_count > 0 else "low"
    summary = (
        f"{int(library.get('pack_count', 0) or 0)} capability pack(s), {staged_count} staged, {active_count} active, {superseded_count} superseded."
        if rows
        else "No capability packs are cataloged yet."
    )
    focused_row = next((row for row in rows if str(row.get("id", "")).strip() == focus_entry_id), None)

    return {
        "status": "ok",
        "surface": "capability_library",
        "summary": summary,
        "severity": severity,
        "focus_entry_id": focus_entry_id,
        "focus_pack_id": focus_pack_id,
        "cards": [
            {"label": "Packs", "value": str(int(library.get("pack_count", 0) or 0)), "tone": "low"},
            {"label": "Staged", "value": str(staged_count), "tone": "medium" if staged_count else "low"},
            {"label": "Active", "value": str(active_count), "tone": "low"},
            {"label": "Superseded", "value": str(superseded_count), "tone": "medium" if superseded_count else "low"},
            {"label": "External", "value": str(external_count), "tone": "medium" if external_count else "low"},
            {"label": "Review", "value": str(review_required_count), "tone": "high" if review_required_count else "low"},
            {"label": "Quarantined", "value": str(quarantined_count), "tone": "high" if quarantined_count else "low"},
            {"label": "Revoked", "value": str(revoked_count), "tone": "high" if revoked_count else "low"},
        ],
        "entries": rows,
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
