from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.apprenticeship import summarize_apprenticeship
from francis_brain.recall import summarize_fabric
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.catalog import list_entries
from francis_forge.library import build_capability_library
from services.orchestrator.app.approvals_store import APPROVAL_REQUESTS_PATH, DECISIONS_PATH
from services.orchestrator.app.control_state import load_or_init_control_state, save_control_state
from services.orchestrator.app.federation_store import FEDERATION_TOPOLOGY_PATH, load_or_init_topology
from services.orchestrator.app.managed_copy_store import (
    MANAGED_COPY_DELTAS_PATH,
    MANAGED_COPY_REGISTRY_PATH,
    build_managed_copy_state,
)
from services.orchestrator.app.swarm_store import (
    SWARM_DEADLETTER_PATH,
    SWARM_DELEGATIONS_PATH,
    SWARM_UNITS_PATH,
    build_swarm_state,
    load_or_init_units,
)
from services.orchestrator.app.takeover_snapshot import load_takeover_state
from services.orchestrator.app.telemetry_store import TELEMETRY_CONFIG_PATH, read_config

PORTABILITY_EXPORT_INDEX_PATH = "portability/exports/index.jsonl"
PORTABILITY_IMPORT_INDEX_PATH = "portability/imports/index.jsonl"
PORTABILITY_PREVIEW_PATH = "portability/preview.json"
PORTABILITY_EXPORT_DIR = "portability/exports"
PORTABILITY_IMPORT_BUNDLE_DIR = "portability/imports/bundles"
PORTABILITY_IMPORT_ARCHIVE_DIR = "portability/imports/archive"
PORTABILITY_SCHEMA = "francis.portability.v1"
PORTABILITY_VERSION = 1


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write_json(fs: WorkspaceFS, rel_path: str, payload: Any) -> None:
    fs.write_text(rel_path, json.dumps(payload, ensure_ascii=False, indent=2))


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            parsed = json.loads(stripped)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


def _write_jsonl(fs: WorkspaceFS, rel_path: str, rows: list[dict[str, Any]]) -> None:
    payload = ""
    if rows:
        payload = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n"
    fs.write_text(rel_path, payload)


def _tail(rows: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    normalized_limit = max(0, min(int(limit), 50))
    if normalized_limit == 0:
        return []
    return rows[-normalized_limit:]


def _safe_timestamp(ts: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in str(ts).strip()) or "portable"


def _normalize_text(value: Any, *, fallback: str = "", max_length: int = 280) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        text = fallback
    return text[:max_length]


def _bundle_workspace_meta(repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    return {
        "repo_root": str(repo_root.resolve()),
        "workspace_root": str(workspace_root.resolve()),
        "repo_name": repo_root.resolve().name,
        "workspace_name": workspace_root.resolve().name,
    }


def _safe_import_mode(mode: str) -> tuple[str, str | None]:
    normalized = str(mode or "").strip().lower()
    if normalized in {"observe", "assist"}:
        return (normalized, None)
    if normalized in {"pilot", "away"}:
        return ("assist", f"Imported mode {normalized} is downgraded to assist until authority is re-confirmed.")
    return ("assist", "Imported control mode was invalid and has been normalized to assist.")


def _approval_summary(requests: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> dict[str, Any]:
    latest_decisions: dict[str, str] = {}
    for row in decisions:
        if str(row.get("kind", "")).strip().lower() != "approval.decision":
            continue
        request_id = str(row.get("request_id", "")).strip()
        decision = str(row.get("decision", "")).strip().lower()
        if request_id and decision:
            latest_decisions[request_id] = decision
    pending = 0
    approved = 0
    rejected = 0
    for row in requests:
        request_id = str(row.get("id", "")).strip()
        decision = latest_decisions.get(request_id, "pending")
        if decision == "approved":
            approved += 1
        elif decision == "rejected":
            rejected += 1
        else:
            pending += 1
    return {
        "request_count": len(requests),
        "decision_count": len(decisions),
        "pending_count": pending,
        "approved_count": approved,
        "rejected_count": rejected,
    }


def _build_bundle_sections(fs: WorkspaceFS, *, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    control_state = load_or_init_control_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    telemetry_config = read_config(fs)
    missions_doc = _read_json(fs, "missions/missions.json", {"missions": []})
    mission_history = _read_jsonl(fs, "missions/history.jsonl")
    approvals_requests = _read_jsonl(fs, APPROVAL_REQUESTS_PATH)
    decisions = _read_jsonl(fs, DECISIONS_PATH)
    catalog_doc = _read_json(fs, "forge/catalog.json", {"entries": []})
    catalog_entries = list_entries(fs)
    capability_library = build_capability_library(catalog_entries)
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    managed_registry = _read_json(fs, MANAGED_COPY_REGISTRY_PATH, {"version": 1, "copies": []})
    managed_deltas = _read_jsonl(fs, MANAGED_COPY_DELTAS_PATH)
    managed_state = build_managed_copy_state(fs)
    swarm_units_doc = _read_json(fs, SWARM_UNITS_PATH, {})
    if not isinstance(swarm_units_doc, dict) or not isinstance(swarm_units_doc.get("units"), list):
        swarm_units_doc = {
            "version": 1,
            "updated_at": utc_now_iso(),
            "units": load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root),
        }
    swarm_delegations = _read_jsonl(fs, SWARM_DELEGATIONS_PATH)
    swarm_deadletter = _read_jsonl(fs, SWARM_DEADLETTER_PATH)
    swarm_state = build_swarm_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    takeover_state = load_takeover_state(workspace_root)
    handback_exports = _read_jsonl(fs, "control/handback_exports/index.jsonl")
    apprenticeship_summary = summarize_apprenticeship(fs)
    fabric_summary = summarize_fabric(fs, refresh=False)

    return {
        "control": {
            "state": control_state,
            "import_policy": {
                "rebind_scope_to_current_machine": True,
                "downgrade_unsafe_modes_to": "assist",
                "clear_kill_switch": True,
            },
        },
        "telemetry": {
            "config": telemetry_config,
            "import_policy": {"restore_config": True, "restore_event_history": False},
        },
        "missions": {
            "doc": missions_doc,
            "history": mission_history,
            "import_policy": {"restore_queue_jobs": False, "restore_history": True},
        },
        "approvals_archive": {
            "requests": approvals_requests,
            "decisions": decisions,
            "summary": _approval_summary(approvals_requests, decisions),
            "import_policy": {"reactivate_pending": False, "archive_only": True},
        },
        "capabilities": {
            "catalog": catalog_doc,
            "library": capability_library,
            "import_policy": {"preserve_provenance": True, "restore_catalog": True},
        },
        "federation": {
            "topology": topology,
            "import_policy": {"revalidate_pairs": True, "import_remote_nodes_as": "stale"},
        },
        "managed_copies": {
            "registry": managed_registry,
            "deltas": managed_deltas,
            "state": managed_state,
            "import_policy": {"restore_registry": True, "preserve_isolation": True},
        },
        "swarm": {
            "units": swarm_units_doc,
            "delegations": swarm_delegations,
            "deadletter": swarm_deadletter,
            "state": swarm_state,
            "import_policy": {"restore_units": True, "reactivate_delegations": False},
        },
        "takeover": {
            "state": takeover_state,
            "handback_exports": handback_exports,
            "import_policy": {"restore_live_authority": False, "archive_only": True},
        },
        "apprenticeship": {
            "summary": apprenticeship_summary,
            "import_policy": {"archive_summary_only": True},
        },
        "fabric": {
            "summary": fabric_summary,
            "import_policy": {"restore_snapshot": False, "archive_summary_only": True},
        },
    }


def _bundle_rel_path(bundle_id: str) -> str:
    return f"{PORTABILITY_EXPORT_DIR}/{str(bundle_id).strip()}.json"


def _import_bundle_rel_path(bundle_id: str) -> str:
    return f"{PORTABILITY_IMPORT_BUNDLE_DIR}/{str(bundle_id).strip()}.json"


def _archive_rel_path(bundle_id: str, name: str) -> str:
    return f"{PORTABILITY_IMPORT_ARCHIVE_DIR}/{str(bundle_id).strip()}/{name}"


def _bundle_counts(sections: dict[str, Any]) -> dict[str, int]:
    approvals = sections.get("approvals_archive", {}) if isinstance(sections.get("approvals_archive"), dict) else {}
    capabilities = sections.get("capabilities", {}) if isinstance(sections.get("capabilities"), dict) else {}
    catalog = capabilities.get("catalog", {}) if isinstance(capabilities.get("catalog"), dict) else {}
    federation = sections.get("federation", {}) if isinstance(sections.get("federation"), dict) else {}
    topology = federation.get("topology", {}) if isinstance(federation.get("topology"), dict) else {}
    managed_copies = sections.get("managed_copies", {}) if isinstance(sections.get("managed_copies"), dict) else {}
    managed_state = managed_copies.get("state", {}) if isinstance(managed_copies.get("state"), dict) else {}
    swarm = sections.get("swarm", {}) if isinstance(sections.get("swarm"), dict) else {}
    swarm_units = swarm.get("units", {}) if isinstance(swarm.get("units"), dict) else {}
    missions = sections.get("missions", {}) if isinstance(sections.get("missions"), dict) else {}
    missions_doc = missions.get("doc", {}) if isinstance(missions.get("doc"), dict) else {}
    return {
        "mission_count": len(missions_doc.get("missions", [])) if isinstance(missions_doc.get("missions"), list) else 0,
        "pending_approvals": int(approvals.get("summary", {}).get("pending_count", 0) or 0),
        "capability_count": len(catalog.get("entries", [])) if isinstance(catalog.get("entries"), list) else 0,
        "paired_node_count": len(topology.get("paired_nodes", [])) if isinstance(topology.get("paired_nodes"), list) else 0,
        "managed_copy_count": int(managed_state.get("copy_count", 0) or 0),
        "swarm_unit_count": len(swarm_units.get("units", [])) if isinstance(swarm_units.get("units"), list) else 0,
    }


def _build_preview(
    bundle: dict[str, Any],
    *,
    source_path: str,
    repo_root: Path,
    workspace_root: Path,
    preview_id: str | None = None,
) -> dict[str, Any]:
    sections = bundle.get("sections", {}) if isinstance(bundle.get("sections"), dict) else {}
    workspace = bundle.get("workspace", {}) if isinstance(bundle.get("workspace"), dict) else {}
    control = sections.get("control", {}) if isinstance(sections.get("control"), dict) else {}
    control_state = control.get("state", {}) if isinstance(control.get("state"), dict) else {}
    imported_mode = str(control_state.get("mode", "assist")).strip().lower() or "assist"
    safe_mode, mode_warning = _safe_import_mode(imported_mode)

    approvals = sections.get("approvals_archive", {}) if isinstance(sections.get("approvals_archive"), dict) else {}
    approval_summary = approvals.get("summary", {}) if isinstance(approvals.get("summary"), dict) else {}
    federation = sections.get("federation", {}) if isinstance(sections.get("federation"), dict) else {}
    topology = federation.get("topology", {}) if isinstance(federation.get("topology"), dict) else {}
    managed = sections.get("managed_copies", {}) if isinstance(sections.get("managed_copies"), dict) else {}
    managed_state = managed.get("state", {}) if isinstance(managed.get("state"), dict) else {}
    swarm = sections.get("swarm", {}) if isinstance(sections.get("swarm"), dict) else {}
    swarm_state = swarm.get("state", {}) if isinstance(swarm.get("state"), dict) else {}
    takeover = sections.get("takeover", {}) if isinstance(sections.get("takeover"), dict) else {}
    handback_exports = takeover.get("handback_exports", []) if isinstance(takeover.get("handback_exports"), list) else []
    capabilities = sections.get("capabilities", {}) if isinstance(sections.get("capabilities"), dict) else {}
    catalog = capabilities.get("catalog", {}) if isinstance(capabilities.get("catalog"), dict) else {}
    catalog_entries = catalog.get("entries", []) if isinstance(catalog.get("entries"), list) else []
    missions = sections.get("missions", {}) if isinstance(sections.get("missions"), dict) else {}
    missions_doc = missions.get("doc", {}) if isinstance(missions.get("doc"), dict) else {}
    mission_rows = missions_doc.get("missions", []) if isinstance(missions_doc.get("missions"), list) else []

    warnings: list[str] = []
    if mode_warning:
        warnings.append(mode_warning)
    if str(workspace.get("repo_name", "")).strip() and str(workspace.get("repo_name", "")).strip() != repo_root.name:
        warnings.append(
            f"Bundle repo {str(workspace.get('repo_name', '')).strip()} differs from current repo {repo_root.name}; scopes will bind to this machine."
        )
    if int(approval_summary.get("pending_count", 0) or 0) > 0:
        warnings.append("Imported approvals remain historical only and will not reactivate pending decisions.")
    if int(swarm_state.get("queued_count", 0) or 0) > 0 or int(swarm_state.get("leased_count", 0) or 0) > 0:
        warnings.append("Imported swarm delegations are archived only and will not resume active work.")
    if topology.get("paired_nodes"):
        warnings.append("Imported paired nodes are restored as stale metadata and require revalidation.")
    if takeover.get("state"):
        warnings.append("Imported takeover state is archived only; live Pilot or Away authority does not restore.")
    if bool(control_state.get("kill_switch", False)):
        warnings.append("Imported kill switch state is cleared during apply so the new machine starts in a known-safe posture.")

    restore_sections = [
        {
            "id": "control",
            "label": "Control posture",
            "count": "1 state",
            "policy": f"Mode imports as {safe_mode}; repo and workspace scopes rebind to this machine.",
        },
        {
            "id": "telemetry",
            "label": "Telemetry config",
            "count": "1 config",
            "policy": "Telemetry preferences restore, but event history does not.",
        },
        {
            "id": "missions",
            "label": "Mission continuity",
            "count": f"{len(mission_rows)} mission(s)",
            "policy": "Mission state and history restore; queue churn does not auto-dispatch.",
        },
        {
            "id": "capabilities",
            "label": "Capability catalog",
            "count": f"{len(catalog_entries)} entry(ies)",
            "policy": "Catalog entries merge with provenance preserved.",
        },
        {
            "id": "federation",
            "label": "Federated nodes",
            "count": f"{len(topology.get('paired_nodes', [])) if isinstance(topology.get('paired_nodes'), list) else 0} paired node(s)",
            "policy": "Remote node metadata restores as stale until revalidated.",
        },
        {
            "id": "managed_copies",
            "label": "Managed copies",
            "count": f"{int(managed_state.get('copy_count', 0) or 0)} copy(ies)",
            "policy": "Registry and safe deltas restore with import provenance.",
        },
        {
            "id": "swarm",
            "label": "Swarm unit registry",
            "count": f"{int(swarm_state.get('unit_count', 0) or 0)} unit(s)",
            "policy": "Unit registry restores; live delegations stay archived.",
        },
    ]
    archive_sections = [
        {
            "id": "approvals_archive",
            "label": "Approval history",
            "count": f"{int(approval_summary.get('request_count', 0) or 0)} request(s)",
            "policy": "Approval history is archived and never reactivated automatically.",
        },
        {
            "id": "takeover",
            "label": "Takeover and handbacks",
            "count": f"{len(handback_exports)} handback export(s)",
            "policy": "Pilot and Away authority remain historical only.",
        },
        {
            "id": "apprenticeship",
            "label": "Apprenticeship summary",
            "count": "summary only",
            "policy": "Teaching continuity is archived for context, not replayed as live execution.",
        },
        {
            "id": "fabric",
            "label": "Knowledge fabric summary",
            "count": "summary only",
            "policy": "Fabric posture imports as context, not as live claims.",
        },
    ]

    warning_count = len(warnings)
    severity = "high" if warning_count else "medium" if len(restore_sections) else "low"
    bundle_label = _normalize_text(
        bundle.get("label"),
        fallback=f"{workspace_root.name} governed portability bundle",
        max_length=120,
    )
    summary = (
        f"Preview {bundle_label}: {len(restore_sections)} continuity section(s) restore, "
        f"{len(archive_sections)} archive-only section(s), {warning_count} warning(s)."
    )
    return {
        "preview_id": preview_id or f"preview-{uuid4().hex[:12]}",
        "created_at": utc_now_iso(),
        "bundle_id": str(bundle.get("bundle_id", "")).strip(),
        "bundle_label": bundle_label,
        "source_path": source_path,
        "workspace": workspace,
        "summary": summary,
        "severity": severity,
        "warnings": warnings,
        "cards": [
            {"label": "Restore", "value": str(len(restore_sections)), "tone": "medium"},
            {"label": "Archive", "value": str(len(archive_sections)), "tone": "low"},
            {"label": "Warnings", "value": str(warning_count), "tone": "high" if warning_count else "low"},
            {"label": "Imported Mode", "value": imported_mode or "assist", "tone": "medium" if imported_mode in {"pilot", "away"} else "low"},
            {"label": "Apply Mode", "value": safe_mode, "tone": "low"},
        ],
        "restore_sections": restore_sections,
        "archive_sections": archive_sections,
        "effects": {
            "imported_mode": imported_mode or "assist",
            "applied_mode": safe_mode,
            "pending_approvals": int(approval_summary.get("pending_count", 0) or 0),
            "paired_nodes": len(topology.get("paired_nodes", [])) if isinstance(topology.get("paired_nodes"), list) else 0,
            "managed_copies": int(managed_state.get("copy_count", 0) or 0),
            "capability_entries": len(catalog_entries),
            "swarm_units": int(swarm_state.get("unit_count", 0) or 0),
        },
    }


def _current_continuity_state(fs: WorkspaceFS, *, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    control_state = load_or_init_control_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    approvals_requests = _read_jsonl(fs, APPROVAL_REQUESTS_PATH)
    decisions = _read_jsonl(fs, DECISIONS_PATH)
    approval_summary = _approval_summary(approvals_requests, decisions)
    missions_doc = _read_json(fs, "missions/missions.json", {"missions": []})
    catalog_doc = _read_json(fs, "forge/catalog.json", {"entries": []})
    topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    managed_state = build_managed_copy_state(fs)
    swarm_state = build_swarm_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    return {
        "mode": str(control_state.get("mode", "assist")).strip().lower() or "assist",
        "kill_switch": bool(control_state.get("kill_switch", False)),
        "mission_count": len(missions_doc.get("missions", [])) if isinstance(missions_doc.get("missions"), list) else 0,
        "pending_approvals": int(approval_summary.get("pending_count", 0) or 0),
        "capability_count": len(catalog_doc.get("entries", [])) if isinstance(catalog_doc.get("entries"), list) else 0,
        "paired_node_count": len(topology.get("paired_nodes", [])) if isinstance(topology.get("paired_nodes"), list) else 0,
        "managed_copy_count": int(managed_state.get("copy_count", 0) or 0),
        "swarm_unit_count": int(swarm_state.get("unit_count", 0) or 0),
    }


def build_portability_state(fs: WorkspaceFS, *, repo_root: Path, workspace_root: Path) -> dict[str, Any]:
    exports = _read_jsonl(fs, PORTABILITY_EXPORT_INDEX_PATH)
    imports = _read_jsonl(fs, PORTABILITY_IMPORT_INDEX_PATH)
    preview = _read_json(fs, PORTABILITY_PREVIEW_PATH, {})
    continuity = _current_continuity_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    latest_export = exports[-1] if exports else {}
    latest_import = imports[-1] if imports else {}
    warning_count = len(preview.get("warnings", [])) if isinstance(preview, dict) else 0
    severity = "high" if warning_count else "medium" if preview or imports or exports else "low"
    preview_state = (
        "ready"
        if isinstance(preview, dict) and str(preview.get("preview_id", "")).strip() and not str(preview.get("applied_at", "")).strip()
        else "applied"
        if isinstance(preview, dict) and str(preview.get("applied_at", "")).strip()
        else "idle"
    )
    summary = (
        f"{len(exports)} export bundle(s), {len(imports)} import application(s), "
        f"preview {preview_state} with {warning_count} warning(s)."
    )
    return {
        "summary": summary,
        "severity": severity,
        "export_count": len(exports),
        "import_count": len(imports),
        "preview_state": preview_state,
        "latest_export_id": str(latest_export.get("bundle_id", "")).strip(),
        "latest_import_id": str(latest_import.get("import_id", "")).strip(),
        "continuity": continuity,
        "exports": _tail(exports, 6),
        "imports": _tail(imports, 6),
        "preview": preview if isinstance(preview, dict) else {},
        "workspace": _bundle_workspace_meta(repo_root, workspace_root),
    }


def export_portability_bundle(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    actor: str,
    label: str = "",
    note: str = "",
) -> dict[str, Any]:
    bundle_id = f"bundle-{uuid4().hex[:12]}"
    created_at = utc_now_iso()
    sections = _build_bundle_sections(fs, repo_root=repo_root, workspace_root=workspace_root)
    counts = _bundle_counts(sections)
    bundle_label = _normalize_text(label, fallback=f"{workspace_root.name} governed portability bundle", max_length=120)
    bundle = {
        "schema": PORTABILITY_SCHEMA,
        "version": PORTABILITY_VERSION,
        "bundle_id": bundle_id,
        "created_at": created_at,
        "created_by": _normalize_text(actor, fallback="architect", max_length=80),
        "label": bundle_label,
        "note": _normalize_text(note, max_length=240),
        "workspace": _bundle_workspace_meta(repo_root, workspace_root),
        "sections": sections,
    }
    rel_path = _bundle_rel_path(bundle_id)
    _write_json(fs, rel_path, bundle)
    index_row = {
        "bundle_id": bundle_id,
        "created_at": created_at,
        "created_by": bundle["created_by"],
        "label": bundle_label,
        "note": bundle["note"],
        "path": rel_path,
        "summary": (
            f"{counts['mission_count']} mission(s), {counts['capability_count']} capability entry(ies), "
            f"{counts['paired_node_count']} paired node(s), {counts['pending_approvals']} pending approval(s)."
        ),
        **counts,
    }
    _append_jsonl(fs, PORTABILITY_EXPORT_INDEX_PATH, index_row)
    return {
        "bundle_id": bundle_id,
        "path": rel_path,
        "label": bundle_label,
        "created_at": created_at,
        "summary": index_row["summary"],
        "counts": counts,
        "state": build_portability_state(fs, repo_root=repo_root, workspace_root=workspace_root),
    }


def _resolve_source_path(*, repo_root: Path, workspace_root: Path, bundle_id: str = "", path: str = "") -> Path:
    normalized_bundle_id = str(bundle_id).strip()
    if normalized_bundle_id:
        return (workspace_root / "portability" / "exports" / f"{normalized_bundle_id}.json").resolve()

    raw_path = str(path).strip()
    if not raw_path:
        export_rows = _tail(_read_jsonl(WorkspaceFS(roots=[workspace_root], journal_path=(workspace_root / "journals" / "fs.jsonl").resolve()), PORTABILITY_EXPORT_INDEX_PATH), 1)
        if not export_rows:
            raise FileNotFoundError("No portability bundle is available to preview.")
        return (workspace_root / str(export_rows[0].get("path", "")).strip()).resolve()

    candidate = Path(raw_path)
    if not candidate.is_absolute():
        candidate = (repo_root / candidate).resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo_root)
    except Exception as exc:
        raise ValueError("Portability import path must stay inside the current repository.") from exc
    return resolved


def _load_bundle_from_path(source_path: Path) -> dict[str, Any]:
    raw = source_path.read_text(encoding="utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise ValueError("Portability bundle is invalid.")
    if str(parsed.get("schema", "")).strip() != PORTABILITY_SCHEMA:
        raise ValueError("Portability bundle schema is not supported.")
    return parsed


def preview_portability_import(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    bundle_id: str = "",
    path: str = "",
) -> dict[str, Any]:
    source_path = _resolve_source_path(repo_root=repo_root, workspace_root=workspace_root, bundle_id=bundle_id, path=path)
    bundle = _load_bundle_from_path(source_path)
    preview = _build_preview(
        bundle,
        source_path=str(source_path),
        repo_root=repo_root,
        workspace_root=workspace_root,
    )
    _write_json(fs, PORTABILITY_PREVIEW_PATH, preview)
    return {
        "preview": preview,
        "state": build_portability_state(fs, repo_root=repo_root, workspace_root=workspace_root),
    }


def _deep_copy_json(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False))


def _merge_string_list(values: list[Any]) -> list[str]:
    items: list[str] = []
    for value in values:
        text = str(value).strip()
        if text and text not in items:
            items.append(text)
    return items


def _annotate_imported_entry(entry: dict[str, Any], *, bundle_id: str) -> dict[str, Any]:
    annotated = _deep_copy_json(entry)
    if not isinstance(annotated, dict):
        annotated = {}
    annotated["imported_from_bundle_id"] = bundle_id
    annotated["imported_at"] = utc_now_iso()
    return annotated


def _dict_key(row: dict[str, Any], *, fields: tuple[str, ...]) -> str:
    for field in fields:
        value = str(row.get(field, "")).strip()
        if value:
            return f"{field}:{value}"
    return json.dumps(row, ensure_ascii=False, sort_keys=True)


def _merge_catalog_doc(current_doc: dict[str, Any], imported_doc: dict[str, Any], *, bundle_id: str) -> dict[str, Any]:
    current_entries = current_doc.get("entries", []) if isinstance(current_doc.get("entries"), list) else []
    imported_entries = imported_doc.get("entries", []) if isinstance(imported_doc.get("entries"), list) else []
    merged: dict[str, dict[str, Any]] = {}
    for row in current_entries:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("id", "name", "stage_id"))] = _deep_copy_json(row)
    for row in imported_entries:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("id", "name", "stage_id"))] = _annotate_imported_entry(row, bundle_id=bundle_id)
    return {
        "version": int(max(int(current_doc.get("version", 1) or 1), int(imported_doc.get("version", 1) or 1))),
        "updated_at": utc_now_iso(),
        "entries": list(merged.values()),
    }


def _merge_jsonl_rows(
    current_rows: list[dict[str, Any]],
    imported_rows: list[dict[str, Any]],
    *,
    key_fields: tuple[str, ...],
    annotate_imports: bool = True,
    bundle_id: str,
) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for row in current_rows:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=key_fields)] = _deep_copy_json(row)
    for row in imported_rows:
        if not isinstance(row, dict):
            continue
        value = _annotate_imported_entry(row, bundle_id=bundle_id) if annotate_imports else _deep_copy_json(row)
        merged[_dict_key(row, fields=key_fields)] = value
    items = list(merged.values())
    items.sort(key=lambda row: str(row.get("ts", row.get("created_at", row.get("updated_at", "")))))
    return items


def _merge_managed_registry(current_registry: dict[str, Any], imported_registry: dict[str, Any], *, bundle_id: str) -> dict[str, Any]:
    current_copies = current_registry.get("copies", []) if isinstance(current_registry.get("copies"), list) else []
    imported_copies = imported_registry.get("copies", []) if isinstance(imported_registry.get("copies"), list) else []
    merged: dict[str, dict[str, Any]] = {}
    for row in current_copies:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("copy_id",))] = _deep_copy_json(row)
    for row in imported_copies:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("copy_id",))] = _annotate_imported_entry(row, bundle_id=bundle_id)
    return {
        "version": int(max(int(current_registry.get("version", 1) or 1), int(imported_registry.get("version", 1) or 1))),
        "updated_at": utc_now_iso(),
        "copies": list(merged.values()),
    }


def _merge_swarm_units_doc(
    current_doc: dict[str, Any],
    imported_doc: dict[str, Any],
    *,
    bundle_id: str,
    fs: WorkspaceFS,
    repo_root: Path,
    workspace_root: Path,
) -> dict[str, Any]:
    current_units = current_doc.get("units", []) if isinstance(current_doc.get("units"), list) else []
    if not current_units:
        current_units = load_or_init_units(fs, repo_root=repo_root, workspace_root=workspace_root)
    imported_units = imported_doc.get("units", []) if isinstance(imported_doc.get("units"), list) else []
    merged: dict[str, dict[str, Any]] = {}
    for row in current_units:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("unit_id",))] = _deep_copy_json(row)
    for row in imported_units:
        if not isinstance(row, dict):
            continue
        annotated = _annotate_imported_entry(row, bundle_id=bundle_id)
        annotated["local"] = False
        merged[_dict_key(row, fields=("unit_id",))] = annotated
    return {
        "version": int(max(int(current_doc.get("version", 1) or 1), int(imported_doc.get("version", 1) or 1))),
        "updated_at": utc_now_iso(),
        "units": list(merged.values()),
    }


def _merge_federation_topology(
    current_topology: dict[str, Any],
    imported_topology: dict[str, Any],
    *,
    bundle_id: str,
) -> dict[str, Any]:
    local_node = current_topology.get("local_node", {}) if isinstance(current_topology.get("local_node"), dict) else {}
    current_paired = current_topology.get("paired_nodes", []) if isinstance(current_topology.get("paired_nodes"), list) else []
    imported_local = imported_topology.get("local_node", {}) if isinstance(imported_topology.get("local_node"), dict) else {}
    imported_paired = imported_topology.get("paired_nodes", []) if isinstance(imported_topology.get("paired_nodes"), list) else []
    merged: dict[str, dict[str, Any]] = {}
    local_node_id = str(local_node.get("node_id", "")).strip()
    for row in current_paired:
        if isinstance(row, dict):
            merged[_dict_key(row, fields=("node_id",))] = _deep_copy_json(row)

    candidates: list[dict[str, Any]] = []
    if imported_local:
        candidates.append(imported_local)
    candidates.extend(row for row in imported_paired if isinstance(row, dict))
    for row in candidates:
        if not isinstance(row, dict):
            continue
        node_id = str(row.get("node_id", "")).strip()
        if node_id and node_id == local_node_id:
            continue
        annotated = _annotate_imported_entry(row, bundle_id=bundle_id)
        annotated["local"] = False
        status = str(annotated.get("status", "stale")).strip().lower()
        annotated["status"] = "revoked" if status == "revoked" else "stale"
        annotated["last_sync_summary"] = _normalize_text(
            f"{str(annotated.get('last_sync_summary', '')).strip()} Imported from portability bundle {bundle_id}; revalidation required.",
            fallback=f"Imported from portability bundle {bundle_id}; revalidation required.",
            max_length=240,
        )
        notes = _normalize_text(
            f"{str(annotated.get('notes', '')).strip()} Imported from portability bundle {bundle_id}.",
            fallback=f"Imported from portability bundle {bundle_id}.",
            max_length=240,
        )
        annotated["notes"] = notes
        merged[_dict_key(annotated, fields=("node_id",))] = annotated

    return {
        "version": int(max(int(current_topology.get("version", 1) or 1), int(imported_topology.get("version", 1) or 1))),
        "updated_at": utc_now_iso(),
        "local_node": _deep_copy_json(local_node),
        "paired_nodes": list(merged.values()),
    }


def _write_archive_sections(fs: WorkspaceFS, *, bundle_id: str, sections: dict[str, Any]) -> None:
    approvals = sections.get("approvals_archive", {}) if isinstance(sections.get("approvals_archive"), dict) else {}
    _write_jsonl(
        fs,
        _archive_rel_path(bundle_id, "approvals_requests.jsonl"),
        approvals.get("requests", []) if isinstance(approvals.get("requests"), list) else [],
    )
    _write_jsonl(
        fs,
        _archive_rel_path(bundle_id, "approval_decisions.jsonl"),
        approvals.get("decisions", []) if isinstance(approvals.get("decisions"), list) else [],
    )

    takeover = sections.get("takeover", {}) if isinstance(sections.get("takeover"), dict) else {}
    _write_json(fs, _archive_rel_path(bundle_id, "takeover_state.json"), takeover.get("state", {}))
    _write_jsonl(
        fs,
        _archive_rel_path(bundle_id, "handback_exports.jsonl"),
        takeover.get("handback_exports", []) if isinstance(takeover.get("handback_exports"), list) else [],
    )

    apprenticeship = sections.get("apprenticeship", {}) if isinstance(sections.get("apprenticeship"), dict) else {}
    fabric = sections.get("fabric", {}) if isinstance(sections.get("fabric"), dict) else {}
    _write_json(fs, _archive_rel_path(bundle_id, "apprenticeship_summary.json"), apprenticeship.get("summary", {}))
    _write_json(fs, _archive_rel_path(bundle_id, "fabric_summary.json"), fabric.get("summary", {}))

    swarm = sections.get("swarm", {}) if isinstance(sections.get("swarm"), dict) else {}
    _write_jsonl(
        fs,
        _archive_rel_path(bundle_id, "swarm_delegations.jsonl"),
        swarm.get("delegations", []) if isinstance(swarm.get("delegations"), list) else [],
    )
    _write_jsonl(
        fs,
        _archive_rel_path(bundle_id, "swarm_deadletter.jsonl"),
        swarm.get("deadletter", []) if isinstance(swarm.get("deadletter"), list) else [],
    )


def _apply_control_import(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    imported_state: dict[str, Any],
) -> tuple[dict[str, Any], str | None]:
    current_state = load_or_init_control_state(fs, repo_root=repo_root, workspace_root=workspace_root)
    safe_mode, warning = _safe_import_mode(str(imported_state.get("mode", current_state.get("mode", "assist"))))
    imported_scopes = imported_state.get("scopes", {}) if isinstance(imported_state.get("scopes"), dict) else {}
    imported_apps = imported_scopes.get("apps", []) if isinstance(imported_scopes.get("apps"), list) else []
    current_scopes = current_state.get("scopes", {}) if isinstance(current_state.get("scopes"), dict) else {}
    current_apps = current_scopes.get("apps", []) if isinstance(current_scopes.get("apps"), list) else []
    merged_apps = sorted(set(_merge_string_list([*current_apps, *imported_apps, "portability"])))
    applied_state = {
        **current_state,
        "mode": safe_mode,
        "kill_switch": False,
        "scopes": {
            "repos": [str(repo_root.resolve())],
            "workspaces": [str(workspace_root.resolve())],
            "apps": merged_apps,
        },
        "updated_at": utc_now_iso(),
    }
    saved = save_control_state(fs, applied_state, repo_root=repo_root, workspace_root=workspace_root)
    return (saved, warning)


def apply_portability_import(
    fs: WorkspaceFS,
    *,
    repo_root: Path,
    workspace_root: Path,
    actor: str,
    preview_id: str = "",
    bundle_id: str = "",
    path: str = "",
) -> dict[str, Any]:
    preview = _read_json(fs, PORTABILITY_PREVIEW_PATH, {})
    use_preview = (
        isinstance(preview, dict)
        and str(preview.get("preview_id", "")).strip()
        and (
            not preview_id
            or str(preview.get("preview_id", "")).strip() == str(preview_id).strip()
        )
    )
    if use_preview:
        source_path = Path(str(preview.get("source_path", "")).strip()).resolve()
    else:
        source_path = _resolve_source_path(repo_root=repo_root, workspace_root=workspace_root, bundle_id=bundle_id, path=path)

    bundle = _load_bundle_from_path(source_path)
    if not use_preview:
        preview = _build_preview(bundle, source_path=str(source_path), repo_root=repo_root, workspace_root=workspace_root, preview_id=str(preview_id or ""))

    bundle_id_value = str(bundle.get("bundle_id", "")).strip() or f"bundle-{uuid4().hex[:12]}"
    sections = bundle.get("sections", {}) if isinstance(bundle.get("sections"), dict) else {}

    _write_json(fs, _import_bundle_rel_path(bundle_id_value), bundle)
    _write_archive_sections(fs, bundle_id=bundle_id_value, sections=sections)

    control_section = sections.get("control", {}) if isinstance(sections.get("control"), dict) else {}
    applied_control, control_warning = _apply_control_import(
        fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        imported_state=control_section.get("state", {}) if isinstance(control_section.get("state"), dict) else {},
    )

    telemetry = sections.get("telemetry", {}) if isinstance(sections.get("telemetry"), dict) else {}
    telemetry_config = telemetry.get("config", {}) if isinstance(telemetry.get("config"), dict) else {}
    telemetry_payload = _deep_copy_json(telemetry_config)
    telemetry_payload["imported_from_bundle_id"] = bundle_id_value
    telemetry_payload["imported_at"] = utc_now_iso()
    _write_json(fs, TELEMETRY_CONFIG_PATH, telemetry_payload)

    missions = sections.get("missions", {}) if isinstance(sections.get("missions"), dict) else {}
    missions_doc = missions.get("doc", {}) if isinstance(missions.get("doc"), dict) else {"missions": []}
    missions_doc = _deep_copy_json(missions_doc)
    if not isinstance(missions_doc.get("missions"), list):
        missions_doc["missions"] = []
    missions_doc["imported_from_bundle_id"] = bundle_id_value
    missions_doc["imported_at"] = utc_now_iso()
    _write_json(fs, "missions/missions.json", missions_doc)
    _write_jsonl(
        fs,
        "missions/history.jsonl",
        missions.get("history", []) if isinstance(missions.get("history"), list) else [],
    )

    capabilities = sections.get("capabilities", {}) if isinstance(sections.get("capabilities"), dict) else {}
    current_catalog = _read_json(fs, "forge/catalog.json", {"version": 1, "entries": []})
    imported_catalog = capabilities.get("catalog", {}) if isinstance(capabilities.get("catalog"), dict) else {"entries": []}
    merged_catalog = _merge_catalog_doc(current_catalog, imported_catalog, bundle_id=bundle_id_value)
    _write_json(fs, "forge/catalog.json", merged_catalog)

    current_topology = load_or_init_topology(fs, repo_root=repo_root, workspace_root=workspace_root)
    imported_topology = sections.get("federation", {}).get("topology", {}) if isinstance(sections.get("federation"), dict) else {}
    merged_topology = _merge_federation_topology(
        current_topology,
        imported_topology if isinstance(imported_topology, dict) else {},
        bundle_id=bundle_id_value,
    )
    _write_json(fs, FEDERATION_TOPOLOGY_PATH, merged_topology)

    current_registry = _read_json(fs, MANAGED_COPY_REGISTRY_PATH, {"version": 1, "copies": []})
    imported_registry = sections.get("managed_copies", {}).get("registry", {}) if isinstance(sections.get("managed_copies"), dict) else {}
    merged_registry = _merge_managed_registry(
        current_registry if isinstance(current_registry, dict) else {"version": 1, "copies": []},
        imported_registry if isinstance(imported_registry, dict) else {"version": 1, "copies": []},
        bundle_id=bundle_id_value,
    )
    _write_json(fs, MANAGED_COPY_REGISTRY_PATH, merged_registry)
    current_deltas = _read_jsonl(fs, MANAGED_COPY_DELTAS_PATH)
    imported_deltas = sections.get("managed_copies", {}).get("deltas", []) if isinstance(sections.get("managed_copies"), dict) else []
    merged_deltas = _merge_jsonl_rows(
        current_deltas,
        imported_deltas if isinstance(imported_deltas, list) else [],
        key_fields=("id", "copy_id", "ts"),
        bundle_id=bundle_id_value,
    )
    _write_jsonl(fs, MANAGED_COPY_DELTAS_PATH, merged_deltas)

    current_units_doc = _read_json(fs, SWARM_UNITS_PATH, {"version": 1, "units": []})
    imported_units_doc = sections.get("swarm", {}).get("units", {}) if isinstance(sections.get("swarm"), dict) else {}
    merged_units_doc = _merge_swarm_units_doc(
        current_units_doc if isinstance(current_units_doc, dict) else {"version": 1, "units": []},
        imported_units_doc if isinstance(imported_units_doc, dict) else {"version": 1, "units": []},
        bundle_id=bundle_id_value,
        fs=fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
    )
    _write_json(fs, SWARM_UNITS_PATH, merged_units_doc)

    warnings = [str(item).strip() for item in preview.get("warnings", []) if str(item).strip()]
    if control_warning and control_warning not in warnings:
        warnings.append(control_warning)

    import_id = f"import-{uuid4().hex[:12]}"
    import_row = {
        "import_id": import_id,
        "bundle_id": bundle_id_value,
        "preview_id": str(preview.get("preview_id", "")).strip() or None,
        "source_path": str(source_path),
        "applied_at": utc_now_iso(),
        "applied_by": _normalize_text(actor, fallback="architect", max_length=80),
        "summary": _normalize_text(
            f"Applied governed continuity from {str(bundle.get('label', '')).strip() or bundle_id_value}; "
            f"mode set to {applied_control.get('mode', 'assist')}, approvals archived, live authority withheld.",
            max_length=280,
        ),
        "warning_count": len(warnings),
        "warnings": warnings[:6],
        "restored_sections": [
            "control",
            "telemetry",
            "missions",
            "capabilities",
            "federation",
            "managed_copies",
            "swarm",
        ],
        "archived_sections": [
            "approvals_archive",
            "takeover",
            "apprenticeship",
            "fabric",
        ],
    }
    _append_jsonl(fs, PORTABILITY_IMPORT_INDEX_PATH, import_row)

    preview["applied_at"] = import_row["applied_at"]
    preview["import_id"] = import_id
    preview["warnings"] = warnings
    _write_json(fs, PORTABILITY_PREVIEW_PATH, preview)

    return {
        "import_id": import_id,
        "bundle_id": bundle_id_value,
        "summary": import_row["summary"],
        "warnings": warnings,
        "state": build_portability_state(fs, repo_root=repo_root, workspace_root=workspace_root),
    }


