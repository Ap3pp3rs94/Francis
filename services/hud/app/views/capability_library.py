from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
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


def _approval_for_stage(fs: WorkspaceFS, stage_id: str) -> dict[str, Any] | None:
    requests = list_requests(fs, action="forge.promote", limit=50)
    for row in reversed(requests):
        if not isinstance(row, dict):
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if str(metadata.get("stage_id", "")).strip() != stage_id:
            continue
        return row
    return None


def _focus_entry(
    entries: list[dict[str, Any]],
    *,
    focus_entry_id: str = "",
) -> dict[str, Any] | None:
    if focus_entry_id:
        explicit = next(
            (entry for entry in entries if str(entry.get("id", "")).strip() == focus_entry_id),
            None,
        )
        if explicit is not None:
            return explicit
    for status in ("staged", "active"):
        for entry in reversed(entries):
            if _entry_status(entry) == status:
                return entry
    return entries[-1] if entries else None


def _detail_state(entry: dict[str, Any], focus_entry_id: str) -> str:
    entry_id = str(entry.get("id", "")).strip()
    if not entry_id:
        return "historical"
    return "current" if entry_id == focus_entry_id else "historical"


def _detail_cards(entry: dict[str, Any], approval: dict[str, Any] | None) -> list[dict[str, str]]:
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    approval_status = str((approval or {}).get("status", "")).strip().lower()
    return [
        {
            "label": "Status",
            "value": _entry_status(entry),
            "tone": "medium" if _entry_status(entry) == "staged" else "low",
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
            "label": "Files",
            "value": str(int(diff_summary.get("file_count", 0) or 0)),
            "tone": "low" if int(diff_summary.get("file_count", 0) or 0) > 0 else "medium",
        },
        {
            "label": "Promotion",
            "value": approval_status or ("active" if _entry_status(entry) == "active" else "not requested"),
            "tone": "medium" if approval_status == "pending" else "low",
        },
        {
            "label": "Tool Pack",
            "value": str(tool_pack.get("skill_name", "")).strip() or "not registered",
            "tone": "low" if str(tool_pack.get("skill_name", "")).strip() else "medium",
        },
    ]


def _audit(entry: dict[str, Any], approval: dict[str, Any] | None, detail_state: str) -> dict[str, Any]:
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    return {
        "id": str(entry.get("id", "")).strip(),
        "status": _entry_status(entry),
        "version": _entry_version(entry),
        "name": str(entry.get("name", "")).strip(),
        "slug": str(entry.get("slug", "")).strip(),
        "risk_tier": str(entry.get("risk_tier", "low")).strip().lower() or "low",
        "detail_state": detail_state,
        "path": str(entry.get("path", "")).strip(),
        "validation_ok": bool(validation.get("ok")),
        "file_count": int(diff_summary.get("file_count", 0) or 0),
        "approval_id": str((approval or {}).get("id", "")).strip(),
        "approval_status": str((approval or {}).get("status", "")).strip().lower(),
        "tool_pack_skill": str(tool_pack.get("skill_name", "")).strip(),
        "promoted_at": str(entry.get("promoted_at", "")).strip(),
    }


def _row_controls(
    *,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
    entry: dict[str, Any],
    approval: dict[str, Any] | None,
) -> dict[str, dict[str, Any]]:
    stage_id = str(entry.get("id", "")).strip()
    status = _entry_status(entry)
    approval_status = str((approval or {}).get("status", "")).strip().lower()
    approval_id = str((approval or {}).get("id", "")).strip()
    promote_allowed, promote_reason = _action_allowed(
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        app="forge",
        action="forge.promote",
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
            "enabled": status == "staged" and approval_status not in {"pending", "approved"} and request_allowed,
            "summary": (
                f"Request approval to promote {str(entry.get('name', 'staged capability')).strip() or 'the staged capability'}."
                if status == "staged" and approval_status not in {"pending", "approved"} and request_allowed
                else f"Promotion approval is waiting as {approval_status}."
                if approval_status in {"pending", "approved"}
                else f"Promotion approval is blocked: {request_reason}."
            ),
            "control_type": "execute",
            "execute_kind": "forge.promote.request_approval",
            "args": {"stage_id": stage_id},
        },
        "promote": {
            "kind": "forge.promote",
            "label": "Promote Capability",
            "enabled": status == "staged" and approval_status == "approved" and promote_allowed,
            "summary": (
                f"Promote {str(entry.get('name', 'staged capability')).strip() or 'the staged capability'} into the active library."
                if status == "staged" and approval_status == "approved" and promote_allowed
                else "Capability is already active."
                if status == "active"
                else f"Promotion is waiting on approval {approval_id}."
                if approval_status == "pending"
                else f"Promotion is blocked: {promote_reason}."
                if not promote_allowed
                else "Promotion requires approval before execution."
            ),
            "control_type": "execute",
            "execute_kind": "forge.promote",
            "args": {"stage_id": stage_id, "approval_id": approval_id},
        },
    }


def _entry_summary(entry: dict[str, Any], approval: dict[str, Any] | None) -> str:
    status = _entry_status(entry)
    version = _entry_version(entry)
    name = str(entry.get("name", "Capability pack")).strip() or "Capability pack"
    approval_status = str((approval or {}).get("status", "")).strip().lower()
    if status == "staged":
        suffix = (
            f" Approval is {approval_status}."
            if approval_status
            else " Promotion approval has not been requested yet."
        )
        return f"{name} {version} is staged and waiting for governed promotion.{suffix}"
    if status == "active":
        return f"{name} {version} is active in the capability library."
    return f"{name} {version} is cataloged with status {status}."


def get_capability_library_view(
    *,
    snapshot: dict[str, object] | None = None,
) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    workspace_root, repo_root, fs = _workspace_context()
    entries = [row for row in list_entries(fs) if isinstance(row, dict)]
    current_work = snapshot.get("current_work", {}) if isinstance(snapshot.get("current_work"), dict) else {}
    capabilities = current_work.get("capabilities", {}) if isinstance(current_work.get("capabilities"), dict) else {}
    capability_focus = (
        capabilities.get("focus_entry", {}) if isinstance(capabilities.get("focus_entry"), dict) else {}
    )
    requested_focus_entry_id = str(capability_focus.get("id", "")).strip()
    focus_entry = _focus_entry(entries, focus_entry_id=requested_focus_entry_id)
    focus_entry_id = str((focus_entry or {}).get("id", "")).strip()

    rows: list[dict[str, Any]] = []
    staged_count = 0
    active_count = 0
    for entry in entries:
        status = _entry_status(entry)
        if status == "staged":
            staged_count += 1
        if status == "active":
            active_count += 1
        approval = _approval_for_stage(fs, str(entry.get("id", "")).strip())
        detail_state = _detail_state(entry, focus_entry_id)
        rows.append(
            {
                "id": str(entry.get("id", "")).strip(),
                "name": str(entry.get("name", "Capability pack")).strip() or "Capability pack",
                "version": _entry_version(entry),
                "status": status,
                "risk_tier": str(entry.get("risk_tier", "low")).strip().lower() or "low",
                "summary": _entry_summary(entry, approval),
                "detail_summary": _entry_summary(entry, approval),
                "detail_state": detail_state,
                "detail_cards": _detail_cards(entry, approval),
                "audit": _audit(entry, approval, detail_state),
                "controls": _row_controls(
                    fs=fs,
                    repo_root=repo_root,
                    workspace_root=workspace_root,
                    entry=entry,
                    approval=approval,
                ),
            }
        )

    severity = "medium" if staged_count > 0 else "low"
    summary = (
        f"{staged_count} staged capability pack(s) and {active_count} active pack(s) are in the internal library."
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
        "cards": [
            {"label": "Catalog", "value": str(len(rows)), "tone": "low"},
            {"label": "Staged", "value": str(staged_count), "tone": "medium" if staged_count else "low"},
            {"label": "Active", "value": str(active_count), "tone": "low"},
        ],
        "entries": rows,
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
