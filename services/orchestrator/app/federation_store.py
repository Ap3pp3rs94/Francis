from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

FEDERATION_TOPOLOGY_PATH = "federation/topology.json"
DEFAULT_NODE_APPS = ["control", "approvals", "lens"]
VALID_TRUST_LEVELS = {"low", "scoped", "high"}
VALID_NODE_ROLES = {
    "primary",
    "always_on",
    "remote_executor",
    "phone",
    "support",
    "customer",
    "paired",
}
VALID_NODE_STATUSES = {"active", "stale", "revoked"}


def _normalize_string_list(values: list[Any], *, lowercase: bool = False) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if not stripped:
            continue
        normalized.append(stripped.lower() if lowercase else stripped)
    return sorted(set(normalized))


def _normalize_capabilities(payload: dict[str, Any] | None) -> dict[str, bool]:
    source = payload if isinstance(payload, dict) else {}
    return {
        "remote_approvals": bool(source.get("remote_approvals", True)),
        "away_continuity": bool(source.get("away_continuity", False)),
        "receipt_summary": bool(source.get("receipt_summary", True)),
    }


def _normalize_scopes(
    *,
    repo_root: Path,
    workspace_root: Path,
    scopes: dict[str, Any] | None,
) -> dict[str, list[str]]:
    source = scopes if isinstance(scopes, dict) else {}
    repos = _normalize_string_list(source.get("repos", []) if isinstance(source.get("repos"), list) else [])
    workspaces = _normalize_string_list(
        source.get("workspaces", []) if isinstance(source.get("workspaces"), list) else []
    )
    apps = _normalize_string_list(source.get("apps", []) if isinstance(source.get("apps"), list) else [], lowercase=True)
    if not repos:
        repos = [str(repo_root.resolve())]
    if not workspaces:
        workspaces = [str(workspace_root.resolve())]
    if not apps:
        apps = list(DEFAULT_NODE_APPS)
    return {"repos": repos, "workspaces": workspaces, "apps": apps}


def _default_local_node(*, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "node_id": f"node-{uuid4().hex[:12]}",
        "label": "Primary Node",
        "role": "primary",
        "trust_level": "high",
        "status": "active",
        "local": True,
        "paired_by": "system",
        "paired_at": now,
        "last_seen_at": now,
        "last_sync_at": now,
        "last_sync_summary": "Primary workspace initialized.",
        "scopes": _normalize_scopes(repo_root=repo_root, workspace_root=workspace_root, scopes=None),
        "capabilities": _normalize_capabilities(
            {"remote_approvals": True, "away_continuity": True, "receipt_summary": True}
        ),
        "notes": "Primary Francis workspace node.",
        "revoked_at": None,
        "revocation_reason": "",
    }


def _normalize_node(
    entry: dict[str, Any],
    *,
    repo_root: Path,
    workspace_root: Path,
    local: bool,
) -> dict[str, Any]:
    now = utc_now_iso()
    node_id = str(entry.get("node_id", "")).strip() or f"node-{uuid4().hex[:12]}"
    role = str(entry.get("role", "paired")).strip().lower() or "paired"
    if role not in VALID_NODE_ROLES:
        role = "paired"
    trust_level = str(entry.get("trust_level", "scoped")).strip().lower() or "scoped"
    if trust_level not in VALID_TRUST_LEVELS:
        trust_level = "scoped"
    status = str(entry.get("status", "active")).strip().lower() or "active"
    if status not in VALID_NODE_STATUSES:
        status = "active"
    paired_at = str(entry.get("paired_at", "")).strip() or now
    last_seen_at = str(entry.get("last_seen_at", "")).strip() or paired_at
    last_sync_at = str(entry.get("last_sync_at", "")).strip() or paired_at
    return {
        "node_id": node_id,
        "label": str(entry.get("label", "Paired Node")).strip() or "Paired Node",
        "role": role,
        "trust_level": trust_level,
        "status": status,
        "local": bool(local),
        "paired_by": str(entry.get("paired_by", "system")).strip() or "system",
        "paired_at": paired_at,
        "last_seen_at": last_seen_at,
        "last_sync_at": last_sync_at,
        "last_sync_summary": str(entry.get("last_sync_summary", "")).strip(),
        "scopes": _normalize_scopes(
            repo_root=repo_root,
            workspace_root=workspace_root,
            scopes=entry.get("scopes", {}) if isinstance(entry.get("scopes"), dict) else None,
        ),
        "capabilities": _normalize_capabilities(
            entry.get("capabilities", {}) if isinstance(entry.get("capabilities"), dict) else None
        ),
        "notes": str(entry.get("notes", "")).strip(),
        "revoked_at": str(entry.get("revoked_at", "")).strip() or None,
        "revocation_reason": str(entry.get("revocation_reason", "")).strip(),
    }


def _read_topology(fs: WorkspaceFS) -> dict[str, Any] | None:
    try:
        raw = fs.read_text(FEDERATION_TOPOLOGY_PATH)
    except Exception:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_topology(fs: WorkspaceFS, topology: dict[str, Any]) -> dict[str, Any]:
    fs.write_text(FEDERATION_TOPOLOGY_PATH, json.dumps(topology, ensure_ascii=False, indent=2))
    return topology


def get_paired_node(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    node_id: str,
) -> dict[str, Any] | None:
    normalized_node_id = str(node_id).strip()
    if not normalized_node_id:
        return None
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    paired_nodes = topology.get("paired_nodes", []) if isinstance(topology.get("paired_nodes"), list) else []
    for entry in paired_nodes:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("node_id", "")).strip() == normalized_node_id:
            return entry
    return None


def node_has_app_scope(node: dict[str, Any], app: str) -> bool:
    scopes = node.get("scopes", {}) if isinstance(node.get("scopes"), dict) else {}
    apps = scopes.get("apps", []) if isinstance(scopes.get("apps"), list) else []
    normalized_app = str(app).strip().lower()
    return normalized_app in {str(item).strip().lower() for item in apps if isinstance(item, str)}


def load_or_init_topology(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    parsed = _read_topology(fs)
    if not isinstance(parsed, dict):
        parsed = {}
    local_entry = parsed.get("local_node", {}) if isinstance(parsed.get("local_node"), dict) else {}
    paired_entries = parsed.get("paired_nodes", []) if isinstance(parsed.get("paired_nodes"), list) else []
    topology = {
        "version": int(parsed.get("version", 1) or 1),
        "updated_at": utc_now_iso(),
        "local_node": _normalize_node(local_entry or _default_local_node(repo_root=repo_root, workspace_root=workspace_root), repo_root=repo_root, workspace_root=workspace_root, local=True),
        "paired_nodes": [
            _normalize_node(entry, repo_root=repo_root, workspace_root=workspace_root, local=False)
            for entry in paired_entries
            if isinstance(entry, dict)
        ],
    }
    return _write_topology(fs, topology)


def _replace_paired_node(topology: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    node_id = str(node.get("node_id", "")).strip()
    paired_nodes = topology.get("paired_nodes", []) if isinstance(topology.get("paired_nodes"), list) else []
    replaced = False
    next_nodes: list[dict[str, Any]] = []
    for entry in paired_nodes:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("node_id", "")).strip() == node_id:
            next_nodes.append(node)
            replaced = True
        else:
            next_nodes.append(entry)
    if not replaced:
        next_nodes.append(node)
    topology["paired_nodes"] = next_nodes
    topology["updated_at"] = utc_now_iso()
    return topology


def pair_node(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    label: str,
    role: str,
    trust_level: str,
    scopes: dict[str, Any] | None,
    capabilities: dict[str, Any] | None,
    notes: str,
    paired_by: str,
) -> dict[str, Any]:
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    now = utc_now_iso()
    node = _normalize_node(
        {
            "node_id": f"node-{uuid4().hex[:12]}",
            "label": label,
            "role": role,
            "trust_level": trust_level,
            "status": "active",
            "local": False,
            "paired_by": paired_by,
            "paired_at": now,
            "last_seen_at": now,
            "last_sync_at": now,
            "last_sync_summary": "Node paired and awaiting continuity traffic.",
            "scopes": scopes,
            "capabilities": capabilities,
            "notes": notes,
            "revoked_at": None,
            "revocation_reason": "",
        },
        repo_root=repo_root,
        workspace_root=workspace_root,
        local=False,
    )
    _write_topology(fs, _replace_paired_node(topology, node))
    return node


def heartbeat_node(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    node_id: str,
    status: str,
    sync_summary: str,
    capabilities: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    paired_nodes = topology.get("paired_nodes", []) if isinstance(topology.get("paired_nodes"), list) else []
    for entry in paired_nodes:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("node_id", "")).strip() != node_id:
            continue
        if str(entry.get("status", "")).strip().lower() == "revoked":
            raise ValueError("revoked node cannot heartbeat")
        entry["status"] = status if status in VALID_NODE_STATUSES - {"revoked"} else "active"
        entry["last_seen_at"] = utc_now_iso()
        entry["last_sync_at"] = utc_now_iso()
        if sync_summary.strip():
            entry["last_sync_summary"] = sync_summary.strip()
        if isinstance(capabilities, dict):
            entry["capabilities"] = _normalize_capabilities(capabilities)
        normalized = _normalize_node(entry, repo_root=repo_root, workspace_root=workspace_root, local=False)
        _write_topology(fs, _replace_paired_node(topology, normalized))
        return normalized
    return None


def revoke_node(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    node_id: str,
    reason: str,
) -> dict[str, Any] | None:
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    paired_nodes = topology.get("paired_nodes", []) if isinstance(topology.get("paired_nodes"), list) else []
    for entry in paired_nodes:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("node_id", "")).strip() != node_id:
            continue
        entry["status"] = "revoked"
        entry["revoked_at"] = utc_now_iso()
        entry["revocation_reason"] = reason.strip()
        entry["last_sync_summary"] = reason.strip() or "Node trust revoked."
        normalized = _normalize_node(entry, repo_root=repo_root, workspace_root=workspace_root, local=False)
        _write_topology(fs, _replace_paired_node(topology, normalized))
        return normalized
    return None
