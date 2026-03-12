from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_state(node_id: str, focus_node_id: str) -> str:
    if node_id and focus_node_id and node_id == focus_node_id:
        return "current"
    return "historical"


def _has_approvals_scope(node: dict[str, Any]) -> bool:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    apps = scopes.get("apps", []) if isinstance(scopes.get("apps"), list) else []
    return "approvals" in {str(item).strip().lower() for item in apps if isinstance(item, str)}


def _remote_approval_state(
    node: dict[str, Any],
    *,
    remote_pending_count: int,
    remote_pending_preview: list[dict[str, Any]],
) -> dict[str, Any]:
    capabilities = node.get("capabilities", {}) if isinstance(node.get("capabilities"), dict) else {}
    status = str(node.get("status", "active")).strip().lower() or "active"
    local = bool(node.get("local", False))
    enabled = bool(capabilities.get("remote_approvals", False))
    has_scope = _has_approvals_scope(node)
    top_pending = remote_pending_preview[0] if remote_pending_preview else {}
    if local:
        availability = "local"
        summary = "The local node owns the workspace directly; remote approval support applies to paired nodes."
    elif not enabled:
        availability = "blocked"
        summary = "This node is paired without remote approval capability."
    elif not has_scope:
        availability = "blocked"
        summary = "This node is paired without approvals scope."
    elif status != "active":
        availability = "blocked"
        summary = f"This node is {status} and cannot safely decide remote approvals."
    elif remote_pending_count > 0:
        availability = "ready"
        summary = f"{remote_pending_count} pending approval(s) can be decided from this node."
    else:
        availability = "idle"
        summary = "This node is approval-capable and waiting for pending requests."
    return {
        "enabled": enabled and has_scope and not local,
        "has_scope": has_scope,
        "availability": availability,
        "pending_count": remote_pending_count if enabled and has_scope and not local else 0,
        "summary": summary,
        "top_pending": top_pending if isinstance(top_pending, dict) else {},
        "top_pending_id": str(top_pending.get("id", "")).strip() if isinstance(top_pending, dict) else "",
        "top_pending_action": str(top_pending.get("action", "")).strip() if isinstance(top_pending, dict) else "",
    }


def _row_summary(node: dict[str, Any], remote_approval: dict[str, Any]) -> str:
    label = str(node.get("label", "Node")).strip() or "Node"
    role = str(node.get("role", "paired")).strip() or "paired"
    trust = str(node.get("trust_level", "scoped")).strip() or "scoped"
    status = str(node.get("status", "active")).strip() or "active"
    base = (
        f"{label} is the local {role} node with {trust} trust and {status} federation status."
        if bool(node.get("local", False))
        else f"{label} is a {role} node with {trust} trust and {status} federation status."
    )
    remote_summary = str(remote_approval.get("summary", "")).strip()
    continuity = node.get("continuity", {}) if isinstance(node.get("continuity"), dict) else {}
    continuity_summary = str(continuity.get("summary", "")).strip()
    return f"{base} {remote_summary} {continuity_summary}".strip()


def _detail_cards(node: dict[str, Any], remote_approval: dict[str, Any]) -> list[dict[str, str]]:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    capabilities = node.get("capabilities", {}) if isinstance(node.get("capabilities"), dict) else {}
    continuity = node.get("continuity", {}) if isinstance(node.get("continuity"), dict) else {}
    status = str(node.get("status", "active")).strip().lower() or "active"
    pending_count = int(remote_approval.get("pending_count", 0) or 0)
    return [
        {"label": "Role", "value": str(node.get("role", "paired")).strip() or "paired", "tone": "medium"},
        {
            "label": "Trust",
            "value": str(node.get("trust_level", "scoped")).strip() or "scoped",
            "tone": "medium" if str(node.get("trust_level", "")).strip().lower() != "high" else "low",
        },
        {
            "label": "Status",
            "value": str(node.get("status", "active")).strip() or "active",
            "tone": "high" if status == "stale" else "medium" if status == "revoked" else "low",
        },
        {
            "label": "Apps",
            "value": str(len(scopes.get("apps", []))) if isinstance(scopes.get("apps"), list) else "0",
            "tone": "low",
        },
        {"label": "Seen", "value": str(node.get("last_seen_at", "")).strip() or "never", "tone": "low"},
        {
            "label": "Heartbeat Age",
            "value": (
                f"{int(node.get('heartbeat_age_seconds', 0) or 0)}s"
                if node.get("heartbeat_age_seconds") is not None
                else "unknown"
            ),
            "tone": "high" if status == "stale" else "low",
        },
        {
            "label": "Remote Approvals",
            "value": str(remote_approval.get("availability", "blocked")).strip() or "blocked",
            "tone": (
                "high"
                if str(remote_approval.get("availability", "")).strip().lower() == "ready"
                else "medium" if str(remote_approval.get("availability", "")).strip().lower() == "blocked" else "low"
            ),
        },
        {
            "label": "Pending",
            "value": str(pending_count),
            "tone": "high" if pending_count else "low",
        },
        {
            "label": "Continuity",
            "value": str(continuity.get("latest_run_id", "")).strip() or "unreported",
            "tone": "medium" if str(continuity.get("latest_run_id", "")).strip() else "low",
        },
        {
            "label": "Missions",
            "value": str(int(continuity.get("active_missions", 0) or 0)),
            "tone": "medium" if int(continuity.get("active_missions", 0) or 0) else "low",
        },
        {
            "label": "Scope",
            "value": "approvals" if bool(capabilities.get("remote_approvals", False)) and _has_approvals_scope(node) else "limited",
            "tone": "low" if _has_approvals_scope(node) else "medium",
        },
    ]


def _audit(node: dict[str, Any], detail_state: str, remote_approval: dict[str, Any]) -> dict[str, Any]:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    capabilities = node.get("capabilities", {}) if isinstance(node.get("capabilities"), dict) else {}
    return {
        "node_id": str(node.get("node_id", "")).strip(),
        "label": str(node.get("label", "")).strip(),
        "role": str(node.get("role", "")).strip(),
        "trust_level": str(node.get("trust_level", "")).strip(),
        "status": str(node.get("status", "")).strip(),
        "status_reason": str(node.get("status_reason", "")).strip(),
        "detail_state": detail_state,
        "local": bool(node.get("local", False)),
        "paired_at": str(node.get("paired_at", "")).strip(),
        "last_seen_at": str(node.get("last_seen_at", "")).strip(),
        "heartbeat_age_seconds": node.get("heartbeat_age_seconds"),
        "last_sync_at": str(node.get("last_sync_at", "")).strip(),
        "last_sync_summary": str(node.get("last_sync_summary", "")).strip(),
        "scopes": {
            "repos": len(scopes.get("repos", [])) if isinstance(scopes.get("repos"), list) else 0,
            "workspaces": len(scopes.get("workspaces", [])) if isinstance(scopes.get("workspaces"), list) else 0,
            "apps": len(scopes.get("apps", [])) if isinstance(scopes.get("apps"), list) else 0,
        },
        "capabilities": {
            "remote_approvals": bool(capabilities.get("remote_approvals", False)),
            "away_continuity": bool(capabilities.get("away_continuity", False)),
            "receipt_summary": bool(capabilities.get("receipt_summary", False)),
        },
        "continuity": node.get("continuity", {}) if isinstance(node.get("continuity"), dict) else {},
        "remote_approval": remote_approval,
        "revoked_at": node.get("revoked_at"),
        "revocation_reason": str(node.get("revocation_reason", "")).strip(),
    }


def _controls(node: dict[str, Any], remote_approval: dict[str, Any]) -> dict[str, dict[str, Any]]:
    node_id = str(node.get("node_id", "")).strip()
    status = str(node.get("status", "")).strip().lower()
    local = bool(node.get("local", False))
    top_pending_id = str(remote_approval.get("top_pending_id", "")).strip()
    can_remote_decide = (
        bool(node_id)
        and not local
        and status == "active"
        and bool(remote_approval.get("enabled", False))
        and bool(top_pending_id)
    )
    return {
        "sync": {
            "label": "Sync Continuity",
            "enabled": bool(node_id) and not local and status != "revoked",
            "kind": "federation.sync",
            "summary": (
                "Record a fresh continuity envelope for this paired node."
                if bool(node_id) and not local and status != "revoked"
                else "Local or revoked nodes do not accept paired sync updates."
            ),
            "node_id": node_id,
        },
        "revoke": {
            "label": "Revoke Node",
            "enabled": bool(node_id) and not local and status != "revoked",
            "kind": "federation.revoke",
            "summary": (
                "Revoke this node's federation trust and keep continuity receipts."
                if bool(node_id) and not local and status != "revoked"
                else "Local or already revoked nodes cannot be revoked from this surface."
            ),
            "node_id": node_id,
        },
        "approve_top": {
            "label": "Approve Top Remote Request",
            "enabled": can_remote_decide,
            "kind": "federation.remote.approval.approve",
            "summary": (
                f"Approve {top_pending_id[:8]}... through this paired node."
                if can_remote_decide
                else str(remote_approval.get("summary", "")).strip() or "No remote approval is ready."
            ),
            "node_id": node_id,
            "approval_id": top_pending_id or None,
        },
        "reject_top": {
            "label": "Reject Top Remote Request",
            "enabled": can_remote_decide,
            "kind": "federation.remote.approval.reject",
            "summary": (
                f"Reject {top_pending_id[:8]}... through this paired node."
                if can_remote_decide
                else str(remote_approval.get("summary", "")).strip() or "No remote approval is ready."
            ),
            "node_id": node_id,
            "approval_id": top_pending_id or None,
        },
    }


def get_federation_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    federation = snapshot.get("federation", {}) if isinstance(snapshot.get("federation"), dict) else {}
    local_node = federation.get("local_node", {}) if isinstance(federation.get("local_node"), dict) else {}
    paired_nodes = [row for row in federation.get("paired_nodes", []) if isinstance(row, dict)]
    all_nodes = [local_node] if local_node else []
    all_nodes.extend(paired_nodes)
    remote_pending_count = int(federation.get("remote_pending_count", 0) or 0)
    remote_pending_preview = [
        row for row in federation.get("remote_pending_preview", []) if isinstance(row, dict)
    ]

    focus_node = next(
        (row for row in paired_nodes if str(row.get("status", "")).strip().lower() == "stale"),
        None,
    )
    if focus_node is None:
        focus_node = next(
            (
                row
                for row in paired_nodes
                if str(row.get("status", "")).strip().lower() == "active"
                and bool(
                    _remote_approval_state(
                        row,
                        remote_pending_count=remote_pending_count,
                        remote_pending_preview=remote_pending_preview,
                    ).get("pending_count", 0)
                )
            ),
            None,
        )
    if focus_node is None:
        focus_node = next(
            (row for row in paired_nodes if str(row.get("status", "")).strip().lower() == "active"),
            None,
        )
    if focus_node is None:
        focus_node = local_node if local_node else None
    focus_node_id = str((focus_node or {}).get("node_id", "")).strip()

    rows: list[dict[str, Any]] = []
    for node in all_nodes:
        node_id = str(node.get("node_id", "")).strip()
        detail_state = _detail_state(node_id, focus_node_id)
        remote_approval = _remote_approval_state(
            node,
            remote_pending_count=remote_pending_count,
            remote_pending_preview=remote_pending_preview,
        )
        summary = _row_summary(node, remote_approval)
        rows.append(
            {
                "node_id": node_id,
                "label": str(node.get("label", "Node")).strip() or "Node",
                "role": str(node.get("role", "paired")).strip() or "paired",
                "trust_level": str(node.get("trust_level", "scoped")).strip() or "scoped",
                "status": str(node.get("status", "active")).strip() or "active",
                "local": bool(node.get("local", False)),
                "summary": summary,
                "detail_summary": summary,
                "detail_state": detail_state,
                "detail_cards": _detail_cards(node, remote_approval),
                "audit": _audit(node, detail_state, remote_approval),
                "controls": _controls(node, remote_approval),
                "remote_approval": remote_approval,
            }
        )

    focused_row = next((row for row in rows if str(row.get("node_id", "")).strip() == focus_node_id), None)
    stale_count = int(federation.get("stale_count", 0) or 0)
    severity = "high" if stale_count > 0 else "medium" if paired_nodes or remote_pending_count else "low"
    return {
        "status": "ok",
        "surface": "federation",
        "summary": str(federation.get("summary", "")).strip() or "No federated node topology has been recorded yet.",
        "severity": severity,
        "focus_node_id": focus_node_id,
        "pairing": {
            "default_role": "always_on",
            "default_trust_level": "scoped",
            "default_apps": ["control", "approvals", "lens"],
            "roles": ["always_on", "remote_executor", "phone", "support", "customer"],
            "trust_levels": ["low", "scoped", "high"],
        },
        "cards": [
            {
                "label": "Local",
                "value": str(local_node.get("label", "Primary Node")).strip() or "Primary Node",
                "tone": "low",
            },
            {
                "label": "Paired",
                "value": str(int(federation.get("paired_count", 0) or 0)),
                "tone": "medium" if paired_nodes else "low",
            },
            {"label": "Stale", "value": str(stale_count), "tone": "high" if stale_count else "low"},
            {
                "label": "Remote Pending",
                "value": str(remote_pending_count),
                "tone": "high" if remote_pending_count else "low",
            },
            {
                "label": "Revoked",
                "value": str(int(federation.get("revoked_count", 0) or 0)),
                "tone": "medium" if int(federation.get("revoked_count", 0) or 0) else "low",
            },
        ],
        "nodes": rows,
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
