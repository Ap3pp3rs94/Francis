from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_connectors.library import (
    build_connector_library,
    build_connector_provenance,
    list_connector_entries,
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


def _approval_for_connector(fs: WorkspaceFS, connector_id: str, *, action: str) -> dict[str, Any] | None:
    for row in reversed(list_requests(fs, action=action, limit=100)):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("connector_id", "")).strip() == connector_id:
            return row
    return None


def _focus_entry(entries: list[dict[str, Any]], *, focus_connector_id: str = "") -> dict[str, Any] | None:
    if focus_connector_id:
        explicit = next((row for row in entries if str(row.get("id", "")).strip() == focus_connector_id), None)
        if explicit is not None:
            return explicit
    for row in entries:
        if str(row.get("status", "")).strip().lower() == "quarantined":
            return row
    for row in entries:
        if bool(build_connector_provenance(row).get("review_required")):
            return row
    for row in entries:
        if str(row.get("status", "")).strip().lower() == "active":
            return row
    return entries[0] if entries else None


def _detail_state(connector_id: str, focus_connector_id: str) -> str:
    if connector_id and focus_connector_id and connector_id == focus_connector_id:
        return "current"
    return "historical"


def _detail_cards(
    entry: dict[str, Any],
    *,
    revoke_approval: dict[str, Any] | None,
) -> list[dict[str, str]]:
    provenance = build_connector_provenance(entry)
    status = str(entry.get("status", "available")).strip().lower() or "available"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    return [
        {"label": "Status", "value": status, "tone": "high" if status in {"quarantined", "revoked"} else "low"},
        {
            "label": "Enabled",
            "value": "yes" if bool(entry.get("enabled", False)) else "no",
            "tone": "low" if bool(entry.get("enabled", False)) else "medium",
        },
        {
            "label": "Provenance",
            "value": str(provenance.get("label", "Internal")).strip() or "Internal",
            "tone": str(provenance.get("tone", "low")).strip() or "low",
        },
        {
            "label": "Review",
            "value": str(provenance.get("review_label", "internal")).strip() or "internal",
            "tone": "high" if bool(provenance.get("review_required")) else "low",
        },
        {
            "label": "Source",
            "value": str(provenance.get("source_label", "generated inside Francis")).strip() or "generated inside Francis",
            "tone": "low" if bool(provenance.get("traceable")) else "high",
        },
        {
            "label": "Risk",
            "value": str(entry.get("risk_tier", "medium")).strip().lower() or "medium",
            "tone": "medium",
        },
        {
            "label": "Revocation",
            "value": revoke_status or ("complete" if status == "revoked" else "not requested"),
            "tone": "medium" if revoke_status == "pending" else "high" if status == "revoked" else "low",
        },
        {
            "label": "Module",
            "value": str(entry.get("module", "")).strip() or "unregistered",
            "tone": "low" if str(entry.get("module", "")).strip() else "medium",
        },
    ]


def _audit(entry: dict[str, Any], *, revoke_approval: dict[str, Any] | None, detail_state: str) -> dict[str, Any]:
    provenance = build_connector_provenance(entry)
    return {
        "id": str(entry.get("id", "")).strip(),
        "name": str(entry.get("name", "")).strip(),
        "slug": str(entry.get("slug", "")).strip(),
        "status": str(entry.get("status", "")).strip().lower() or "available",
        "enabled": bool(entry.get("enabled", False)),
        "detail_state": detail_state,
        "description": str(entry.get("description", "")).strip(),
        "module": str(entry.get("module", "")).strip(),
        "risk_tier": str(entry.get("risk_tier", "medium")).strip().lower() or "medium",
        "approval_action": "connectors.revoke",
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
    connector_id = str(entry.get("id", "")).strip()
    status = str(entry.get("status", "available")).strip().lower() or "available"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    revoke_id = str((revoke_approval or {}).get("id", "")).strip()
    quarantine_allowed, quarantine_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="connectors",
        action="connectors.quarantine",
        mutating=True,
    )
    revoke_allowed, revoke_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="connectors",
        action="connectors.revoke",
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
            "label": "Quarantine Connector",
            "enabled": bool(connector_id) and status in {"active", "available"} and quarantine_allowed,
            "summary": (
                "Quarantine this connector and disable governed use."
                if bool(connector_id) and status in {"active", "available"} and quarantine_allowed
                else "Only active or available connectors can be quarantined."
                if status not in {"active", "available"}
                else f"Connector quarantine is blocked: {quarantine_reason}."
            ),
        },
        "request_revoke": {
            "label": "Request Revocation Approval",
            "enabled": bool(connector_id)
            and status in {"active", "quarantined"}
            and revoke_status not in {"pending", "approved"}
            and request_allowed,
            "summary": (
                f"Request approval to revoke {str(entry.get('name', 'connector')).strip() or 'the connector'}."
                if bool(connector_id)
                and status in {"active", "quarantined"}
                and revoke_status not in {"pending", "approved"}
                and request_allowed
                else f"Revocation approval is {revoke_status}."
                if revoke_status
                else f"Connector revocation approval is blocked: {request_reason}."
            ),
        },
        "revoke": {
            "label": "Revoke Connector",
            "enabled": bool(connector_id) and status in {"active", "quarantined"} and revoke_status == "approved" and revoke_allowed,
            "summary": (
                "Revoke this connector and keep only audit continuity."
                if bool(connector_id) and status in {"active", "quarantined"} and revoke_status == "approved" and revoke_allowed
                else "Connector is already revoked."
                if status == "revoked"
                else f"Revocation is waiting on approval {revoke_id}."
                if revoke_status == "pending"
                else f"Connector revocation is blocked: {revoke_reason}."
                if not revoke_allowed
                else "Connector revocation requires approval before execution."
            ),
        },
    }


def _entry_summary(entry: dict[str, Any], *, revoke_approval: dict[str, Any] | None) -> str:
    provenance = build_connector_provenance(entry)
    name = str(entry.get("name", "Connector")).strip() or "Connector"
    status = str(entry.get("status", "available")).strip().lower() or "available"
    revoke_status = str((revoke_approval or {}).get("status", "")).strip().lower()
    if status == "quarantined":
        summary = f"{name} is quarantined and blocked from governed use."
        if revoke_status:
            summary = f"{summary} Revocation approval is {revoke_status}."
        if str(entry.get("quarantine_reason", "")).strip():
            summary = f"{summary} {str(entry.get('quarantine_reason', '')).strip()}".strip()
        return summary
    if status == "revoked":
        summary = f"{name} is revoked and remains cataloged only for audit continuity."
        if str(entry.get("revocation_reason", "")).strip():
            summary = f"{summary} {str(entry.get('revocation_reason', '')).strip()}".strip()
        return summary
    summary = f"{name} is {status} under connector governance. {str(provenance.get('summary', '')).strip()}".strip()
    if revoke_status:
        summary = f"{summary} Revocation approval is {revoke_status}.".strip()
    return summary


def get_connector_library_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    workspace_root, repo_root, fs = _workspace_context()
    entries = list_connector_entries(fs)
    library = build_connector_library(entries)
    focus_entry = _focus_entry(entries)
    focus_connector_id = str((focus_entry or {}).get("id", "")).strip()

    rows: list[dict[str, Any]] = []
    for entry in entries:
        connector_id = str(entry.get("id", "")).strip()
        revoke_approval = _approval_for_connector(fs, connector_id, action="connectors.revoke") if connector_id else None
        detail_state = _detail_state(connector_id, focus_connector_id)
        provenance = build_connector_provenance(entry)
        rows.append(
            {
                "id": connector_id,
                "name": str(entry.get("name", "Connector")).strip() or "Connector",
                "status": str(entry.get("status", "available")).strip().lower() or "available",
                "risk_tier": str(entry.get("risk_tier", "medium")).strip().lower() or "medium",
                "provenance_label": str(provenance.get("label", "Internal")).strip() or "Internal",
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

    focused_row = next((row for row in rows if str(row.get("id", "")).strip() == focus_connector_id), None)
    severity = (
        "high"
        if int(library.get("quarantined_count", 0) or 0) > 0 or int(library.get("revoked_count", 0) or 0) > 0
        else "medium"
        if int(library.get("review_required_count", 0) or 0) > 0 or int(library.get("external_count", 0) or 0) > 0
        else "low"
    )
    return {
        "status": "ok",
        "surface": "connector_library",
        "summary": (
            f"{library['connector_count']} connector(s), {library['active_count']} active, "
            f"{library['quarantined_count']} quarantined, {library['revoked_count']} revoked."
            if library["connector_count"]
            else "No connector entries are cataloged yet."
        ),
        "severity": severity,
        "focus_connector_id": focus_connector_id,
        "cards": [
            {"label": "Connectors", "value": str(int(library.get("connector_count", 0) or 0)), "tone": "low"},
            {"label": "Active", "value": str(int(library.get("active_count", 0) or 0)), "tone": "low"},
            {"label": "Available", "value": str(int(library.get("available_count", 0) or 0)), "tone": "medium" if int(library.get("available_count", 0) or 0) else "low"},
            {"label": "External", "value": str(int(library.get("external_count", 0) or 0)), "tone": "medium" if int(library.get("external_count", 0) or 0) else "low"},
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
