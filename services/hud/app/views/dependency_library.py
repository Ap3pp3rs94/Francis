from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.dependency_library import (
    build_dependency_library,
    build_dependency_provenance,
    list_dependency_entries,
)
from francis_core.workspace_fs import WorkspaceFS
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


def _approval_for_dependency(fs: WorkspaceFS, dependency_id: str, *, action: str) -> dict[str, Any] | None:
    for row in reversed(list_requests(fs, action=action, limit=100)):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("dependency_id", "")).strip().lower() == dependency_id.lower():
            return row
    return None


def _focus_entry(entries: list[dict[str, Any]], *, focus_dependency_id: str = "") -> dict[str, Any] | None:
    if focus_dependency_id:
        explicit = next((row for row in entries if str(row.get("id", "")).strip() == focus_dependency_id), None)
        if explicit is not None:
            return explicit
    for row in entries:
        if str(row.get("status", "")).strip().lower() == "quarantined":
            return row
    for row in entries:
        if str(row.get("status", "")).strip().lower() == "revoked":
            return row
    for row in entries:
        if bool(build_dependency_provenance(row).get("review_required")):
            return row
    return entries[0] if entries else None


def _detail_state(dependency_id: str, focus_dependency_id: str) -> str:
    if dependency_id and focus_dependency_id and dependency_id == focus_dependency_id:
        return "current"
    return "historical"


def _detail_cards(
    entry: dict[str, Any],
    *,
    revoke_approval: dict[str, Any] | None,
) -> list[dict[str, str]]:
    provenance = build_dependency_provenance(entry)
    status = str(entry.get("status", "declared")).strip().lower() or "declared"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    return [
        {"label": "Status", "value": status, "tone": "high" if status in {"quarantined", "revoked"} else "low"},
        {"label": "Ecosystem", "value": str(entry.get("ecosystem", "python")).strip() or "python", "tone": "low"},
        {"label": "Package", "value": str(entry.get("package_name", "unknown")).strip() or "unknown", "tone": "low"},
        {"label": "Section", "value": str(entry.get("section", "runtime")).strip() or "runtime", "tone": "medium"},
        {
            "label": "Provenance",
            "value": str(provenance.get("label", "Third-Party")).strip() or "Third-Party",
            "tone": str(provenance.get("tone", "low")).strip() or "low",
        },
        {
            "label": "Review",
            "value": str(provenance.get("review_label", "review required")).strip() or "review required",
            "tone": "high" if bool(provenance.get("review_required")) else "low",
        },
        {
            "label": "Pinning",
            "value": str(provenance.get("locked_version") or entry.get("requirement") or "unlocked"),
            "tone": "low" if bool(provenance.get("pinned")) else "high",
        },
        {
            "label": "Manifest",
            "value": str(entry.get("manifest_path", "")).strip() or "unknown",
            "tone": "low",
        },
        {
            "label": "Revocation",
            "value": revoke_status or ("complete" if status == "revoked" else "not requested"),
            "tone": "medium" if revoke_status == "pending" else "high" if status == "revoked" else "low",
        },
    ]


def _audit(entry: dict[str, Any], *, revoke_approval: dict[str, Any] | None, detail_state: str) -> dict[str, Any]:
    provenance = build_dependency_provenance(entry)
    return {
        "id": str(entry.get("id", "")).strip(),
        "name": str(entry.get("name", "")).strip(),
        "ecosystem": str(entry.get("ecosystem", "")).strip(),
        "package_name": str(entry.get("package_name", "")).strip(),
        "status": str(entry.get("status", "")).strip().lower() or "declared",
        "section": str(entry.get("section", "")).strip().lower() or "runtime",
        "detail_state": detail_state,
        "requirement": str(entry.get("requirement", "")).strip(),
        "locked_version": str(entry.get("locked_version", "")).strip(),
        "manifest_path": str(entry.get("manifest_path", "")).strip(),
        "lockfile_path": str(entry.get("lockfile_path", "")).strip(),
        "risk_tier": str(entry.get("risk_tier", "medium")).strip().lower() or "medium",
        "approval_action": "dependencies.revoke",
        "approval_id": str((revoke_approval or {}).get("id", "")).strip(),
        "approval_status": str((revoke_approval or {}).get("status", "")).strip().lower(),
        "quarantined_at": entry.get("quarantined_at"),
        "quarantine_reason": str(entry.get("quarantine_reason", "")).strip(),
        "quarantined_by": str(entry.get("quarantined_by", "")).strip(),
        "revoked_at": entry.get("revoked_at"),
        "revocation_reason": str(entry.get("revocation_reason", "")).strip(),
        "revoked_by": str(entry.get("revoked_by", "")).strip(),
        "previous_status": str(entry.get("previous_status", "")).strip().lower(),
        "provenance": provenance,
    }


def _controls(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    entry: dict[str, Any],
    revoke_approval: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    dependency_id = str(entry.get("id", "")).strip()
    status = str(entry.get("status", "declared")).strip().lower() or "declared"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    revoke_id = str((revoke_approval or {}).get("id", "")).strip()
    quarantine_allowed, quarantine_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="dependencies",
        action="dependencies.quarantine",
        mutating=True,
    )
    revoke_allowed, revoke_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="dependencies",
        action="dependencies.revoke",
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
        "quarantine": {
            "label": "Quarantine Dependency",
            "enabled": bool(dependency_id) and status == "declared" and quarantine_allowed,
            "summary": (
                "Quarantine this dependency and mark it unsafe for governed runtime use."
                if bool(dependency_id) and status == "declared" and quarantine_allowed
                else "Only declared dependencies can be quarantined."
                if status != "declared"
                else f"Dependency quarantine is blocked: {quarantine_reason}."
            ),
        },
        "request_revoke": {
            "label": "Request Revocation Approval",
            "enabled": bool(dependency_id)
            and status in {"declared", "quarantined"}
            and revoke_status not in {"pending", "approved"}
            and request_allowed,
            "summary": (
                f"Request approval to revoke {str(entry.get('name', 'dependency')).strip() or 'the dependency'}."
                if bool(dependency_id)
                and status in {"declared", "quarantined"}
                and revoke_status not in {"pending", "approved"}
                and request_allowed
                else f"Revocation approval is {revoke_status}."
                if revoke_status
                else f"Dependency revocation approval is blocked: {request_reason}."
            ),
        },
        "revoke": {
            "label": "Revoke Dependency",
            "enabled": bool(dependency_id)
            and status in {"declared", "quarantined"}
            and revoke_status == "approved"
            and revoke_allowed,
            "summary": (
                "Revoke this dependency and keep only audit continuity until the manifest is repaired."
                if bool(dependency_id)
                and status in {"declared", "quarantined"}
                and revoke_status == "approved"
                and revoke_allowed
                else "Dependency is already revoked."
                if status == "revoked"
                else f"Revocation is waiting on approval {revoke_id}."
                if revoke_status == "pending"
                else f"Dependency revocation is blocked: {revoke_reason}."
                if not revoke_allowed
                else "Dependency revocation requires approval before execution."
            ),
        },
    }


def _entry_summary(entry: dict[str, Any], *, revoke_approval: dict[str, Any] | None) -> str:
    provenance = build_dependency_provenance(entry)
    name = str(entry.get("name", "dependency")).strip() or "dependency"
    status = str(entry.get("status", "declared")).strip().lower() or "declared"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    if status == "quarantined":
        summary = f"{name} is quarantined and should be removed from governed use."
        if revoke_status:
            summary = f"{summary} Revocation approval is {revoke_status}."
        if str(entry.get("quarantine_reason", "")).strip():
            summary = f"{summary} {str(entry.get('quarantine_reason', '')).strip()}".strip()
        return summary
    if status == "revoked":
        summary = f"{name} is revoked and remains cataloged only for supply-chain audit continuity."
        if str(entry.get("revocation_reason", "")).strip():
            summary = f"{summary} {str(entry.get('revocation_reason', '')).strip()}".strip()
        return summary
    summary = f"{name} is declared in {str(entry.get('manifest_path', '')).strip() or 'the repo'}. {str(provenance.get('summary', '')).strip()}".strip()
    if revoke_status:
        summary = f"{summary} Revocation approval is {revoke_status}.".strip()
    return summary


def get_dependency_library_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    workspace_root, repo_root, fs = _workspace_context()
    entries = list_dependency_entries(fs)
    library = build_dependency_library(entries)
    focus_entry = _focus_entry(entries)
    focus_dependency_id = str((focus_entry or {}).get("id", "")).strip()

    rows: list[dict[str, Any]] = []
    for entry in entries:
        dependency_id = str(entry.get("id", "")).strip()
        revoke_approval = _approval_for_dependency(fs, dependency_id, action="dependencies.revoke") if dependency_id else None
        detail_state = _detail_state(dependency_id, focus_dependency_id)
        provenance = build_dependency_provenance(entry)
        rows.append(
            {
                "id": dependency_id,
                "name": str(entry.get("name", "dependency")).strip() or "dependency",
                "ecosystem": str(entry.get("ecosystem", "python")).strip() or "python",
                "package_name": str(entry.get("package_name", "unknown")).strip() or "unknown",
                "status": str(entry.get("status", "declared")).strip().lower() or "declared",
                "section": str(entry.get("section", "runtime")).strip().lower() or "runtime",
                "requirement": str(entry.get("requirement", "")).strip(),
                "locked_version": str(entry.get("locked_version", "")).strip(),
                "risk_tier": str(entry.get("risk_tier", "medium")).strip().lower() or "medium",
                "provenance_label": str(provenance.get("label", "Third-Party")).strip() or "Third-Party",
                "provenance_tone": str(provenance.get("tone", "low")).strip() or "low",
                "summary": _entry_summary(entry, revoke_approval=revoke_approval),
                "detail_summary": _entry_summary(entry, revoke_approval=revoke_approval),
                "detail_state": detail_state,
                "detail_cards": _detail_cards(entry, revoke_approval=revoke_approval),
                "audit": _audit(entry, revoke_approval=revoke_approval, detail_state=detail_state),
                "controls": _controls(
                    fs=fs,
                    repo_root=repo_root,
                    workspace_root=workspace_root,
                    entry=entry,
                    revoke_approval=revoke_approval,
                ),
            }
        )

    focused_row = next((row for row in rows if str(row.get("id", "")).strip() == focus_dependency_id), None)
    severity = (
        "high"
        if int(library.get("quarantined_count", 0) or 0) > 0
        or int(library.get("revoked_count", 0) or 0) > 0
        or int(library.get("unpinned_count", 0) or 0) > 0
        else "medium"
        if int(library.get("review_required_count", 0) or 0) > 0
        else "low"
    )
    return {
        "status": "ok",
        "surface": "dependency_library",
        "summary": (
            f"{library['dependency_count']} dependency row(s), {library['runtime_count']} runtime, "
            f"{library['quarantined_count']} quarantined, {library['revoked_count']} revoked."
            if library["dependency_count"]
            else "No dependency rows are cataloged yet."
        ),
        "severity": severity,
        "focus_dependency_id": focus_dependency_id,
        "cards": [
            {"label": "Dependencies", "value": str(int(library.get("dependency_count", 0) or 0)), "tone": "low"},
            {"label": "Runtime", "value": str(int(library.get("runtime_count", 0) or 0)), "tone": "medium" if int(library.get("runtime_count", 0) or 0) else "low"},
            {"label": "Dev", "value": str(int(library.get("dev_count", 0) or 0)), "tone": "low"},
            {"label": "Pinned", "value": str(int(library.get("pinned_count", 0) or 0)), "tone": "low"},
            {"label": "Unpinned", "value": str(int(library.get("unpinned_count", 0) or 0)), "tone": "high" if int(library.get("unpinned_count", 0) or 0) else "low"},
            {"label": "Review", "value": str(int(library.get("review_required_count", 0) or 0)), "tone": "high" if int(library.get("review_required_count", 0) or 0) else "low"},
            {"label": "Quarantined", "value": str(int(library.get("quarantined_count", 0) or 0)), "tone": "high" if int(library.get("quarantined_count", 0) or 0) else "low"},
            {"label": "Revoked", "value": str(int(library.get("revoked_count", 0) or 0)), "tone": "high" if int(library.get("revoked_count", 0) or 0) else "low"},
        ],
        "entries": rows,
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
