from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_state(node_id: str, focus_node_id: str) -> str:
    if node_id and focus_node_id and node_id == focus_node_id:
        return "current"
    return "historical"


def _row_summary(node: dict[str, Any]) -> str:
    label = str(node.get("label", "Node")).strip() or "Node"
    role = str(node.get("role", "paired")).strip() or "paired"
    trust = str(node.get("trust_level", "scoped")).strip() or "scoped"
    status = str(node.get("status", "active")).strip() or "active"
    if bool(node.get("local", False)):
        return f"{label} is the local {role} node with {trust} trust and {status} federation status."
    return f"{label} is a {role} node with {trust} trust and {status} federation status."


def _detail_cards(node: dict[str, Any]) -> list[dict[str, str]]:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    capabilities = node.get("capabilities", {}) if isinstance(node.get("capabilities"), dict) else {}
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
            "tone": "high" if str(node.get("status", "")).strip().lower() == "stale" else "low",
        },
        {"label": "Apps", "value": str(len(scopes.get("apps", []))) if isinstance(scopes.get("apps"), list) else "0", "tone": "low"},
        {"label": "Seen", "value": str(node.get("last_seen_at", "")).strip() or "never", "tone": "low"},
        {
            "label": "Remote Approvals",
            "value": "enabled" if bool(capabilities.get("remote_approvals", False)) else "disabled",
            "tone": "low" if bool(capabilities.get("remote_approvals", False)) else "medium",
        },
    ]


def _audit(node: dict[str, Any], detail_state: str) -> dict[str, Any]:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    capabilities = node.get("capabilities", {}) if isinstance(node.get("capabilities"), dict) else {}
    return {
        "node_id": str(node.get("node_id", "")).strip(),
        "label": str(node.get("label", "")).strip(),
        "role": str(node.get("role", "")).strip(),
        "trust_level": str(node.get("trust_level", "")).strip(),
        "status": str(node.get("status", "")).strip(),
        "detail_state": detail_state,
        "local": bool(node.get("local", False)),
        "paired_at": str(node.get("paired_at", "")).strip(),
        "last_seen_at": str(node.get("last_seen_at", "")).strip(),
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
        "revoked_at": node.get("revoked_at"),
        "revocation_reason": str(node.get("revocation_reason", "")).strip(),
    }


def _controls(node: dict[str, Any]) -> dict[str, dict[str, Any]]:
    node_id = str(node.get("node_id", "")).strip()
    status = str(node.get("status", "")).strip().lower()
    local = bool(node.get("local", False))
    return {
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
        }
    }


def get_federation_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    federation = snapshot.get("federation", {}) if isinstance(snapshot.get("federation"), dict) else {}
    local_node = federation.get("local_node", {}) if isinstance(federation.get("local_node"), dict) else {}
    paired_nodes = [row for row in federation.get("paired_nodes", []) if isinstance(row, dict)]
    all_nodes = [local_node] if local_node else []
    all_nodes.extend(paired_nodes)

    focus_node = next(
        (
            row
            for row in paired_nodes
            if str(row.get("status", "")).strip().lower() == "stale"
        ),
        None,
    )
    if focus_node is None:
        focus_node = next(
            (
                row
                for row in paired_nodes
                if str(row.get("status", "")).strip().lower() == "active"
            ),
            None,
        )
    if focus_node is None:
        focus_node = local_node if local_node else None
    focus_node_id = str((focus_node or {}).get("node_id", "")).strip()

    rows: list[dict[str, Any]] = []
    for node in all_nodes:
        node_id = str(node.get("node_id", "")).strip()
        detail_state = _detail_state(node_id, focus_node_id)
        rows.append(
            {
                "node_id": node_id,
                "label": str(node.get("label", "Node")).strip() or "Node",
                "role": str(node.get("role", "paired")).strip() or "paired",
                "trust_level": str(node.get("trust_level", "scoped")).strip() or "scoped",
                "status": str(node.get("status", "active")).strip() or "active",
                "local": bool(node.get("local", False)),
                "summary": _row_summary(node),
                "detail_summary": _row_summary(node),
                "detail_state": detail_state,
                "detail_cards": _detail_cards(node),
                "audit": _audit(node, detail_state),
                "controls": _controls(node),
            }
        )

    focused_row = next((row for row in rows if str(row.get("node_id", "")).strip() == focus_node_id), None)
    stale_count = int(federation.get("stale_count", 0) or 0)
    severity = "high" if stale_count > 0 else "medium" if paired_nodes else "low"
    return {
        "status": "ok",
        "surface": "federation",
        "summary": str(federation.get("summary", "")).strip()
        or "No federated node topology has been recorded yet.",
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
            {"label": "Paired", "value": str(int(federation.get("paired_count", 0) or 0)), "tone": "medium" if paired_nodes else "low"},
            {"label": "Stale", "value": str(stale_count), "tone": "high" if stale_count else "low"},
            {"label": "Revoked", "value": str(int(federation.get("revoked_count", 0) or 0)), "tone": "medium" if int(federation.get("revoked_count", 0) or 0) else "low"},
        ],
        "nodes": rows,
        "detail": {
            "audit": focused_row.get("audit", {}) if isinstance(focused_row, dict) else {},
            "controls": focused_row.get("controls", {}) if isinstance(focused_row, dict) else {},
        },
    }
