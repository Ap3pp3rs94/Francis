from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

MANAGED_COPY_REGISTRY_PATH = "managed_copies/registry.json"
MANAGED_COPY_DELTAS_PATH = "managed_copies/deltas.jsonl"
MANAGED_COPY_RUNTIME_MANIFEST = "runtime/managed_copy.json"
MANAGED_COPY_RUNTIME_HEALTH = "runtime/health.json"
MANAGED_COPY_RUNTIME_LEDGER = "runs/run_ledger.jsonl"
MANAGED_COPY_RUNTIME_DECISIONS = "journals/decisions.jsonl"
MANAGED_COPY_RUNTIME_INBOX = "inbox/messages.jsonl"
VALID_COPY_STATUSES = {"active", "quarantined", "replaced"}
VALID_SLA_TIERS = {"standard", "premium", "critical"}


def _normalize_string_list(values: list[Any]) -> list[str]:
    normalized: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        stripped = value.strip()
        if stripped:
            normalized.append(stripped)
    return sorted(set(normalized))


def _runtime_rel_path(namespace: str, suffix: str) -> str:
    return f"{namespace.rstrip('/')}/{suffix}".replace("//", "/")


def _read_json(fs: WorkspaceFS, rel_path: str) -> dict[str, Any] | None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        raw = ""
    if raw and not raw.endswith("\n"):
        raw += "\n"
    fs.write_text(rel_path, raw + json.dumps(row, ensure_ascii=False) + "\n")


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


def _read_registry(fs: WorkspaceFS) -> dict[str, Any] | None:
    try:
        raw = fs.read_text(MANAGED_COPY_REGISTRY_PATH)
    except Exception:
        return None
    try:
        parsed = json.loads(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _write_registry(fs: WorkspaceFS, registry: dict[str, Any]) -> dict[str, Any]:
    fs.write_text(MANAGED_COPY_REGISTRY_PATH, json.dumps(registry, ensure_ascii=False, indent=2))
    return registry


def _runtime_paths(namespace: str) -> dict[str, str]:
    return {
        "manifest_path": _runtime_rel_path(namespace, MANAGED_COPY_RUNTIME_MANIFEST),
        "health_path": _runtime_rel_path(namespace, MANAGED_COPY_RUNTIME_HEALTH),
        "ledger_path": _runtime_rel_path(namespace, MANAGED_COPY_RUNTIME_LEDGER),
        "decisions_path": _runtime_rel_path(namespace, MANAGED_COPY_RUNTIME_DECISIONS),
        "inbox_path": _runtime_rel_path(namespace, MANAGED_COPY_RUNTIME_INBOX),
    }


def _runtime_payloads(copy_entry: dict[str, Any]) -> dict[str, str]:
    manifest = {
        "copy_id": str(copy_entry.get("copy_id", "")).strip(),
        "customer_label": str(copy_entry.get("customer_label", "")).strip(),
        "status": str(copy_entry.get("status", "")).strip(),
        "baseline_version": str(copy_entry.get("baseline_version", "")).strip(),
        "sla_tier": str(copy_entry.get("sla_tier", "")).strip(),
        "workspace_namespace": str(copy_entry.get("workspace_namespace", "")).strip(),
        "capability_packs": copy_entry.get("capability_packs", []) if isinstance(copy_entry.get("capability_packs"), list) else [],
        "updated_at": utc_now_iso(),
    }
    health = {
        "copy_id": str(copy_entry.get("copy_id", "")).strip(),
        "status": str(copy_entry.get("status", "")).strip(),
        "last_delta_at": copy_entry.get("last_delta_at"),
        "last_delta_summary": str(copy_entry.get("last_delta_summary", "")).strip(),
        "quarantined_at": copy_entry.get("quarantined_at"),
        "quarantine_reason": str(copy_entry.get("quarantine_reason", "")).strip(),
        "replacement_copy_id": str(copy_entry.get("replacement_copy_id", "")).strip() or None,
        "updated_at": utc_now_iso(),
    }
    return {
        "manifest": json.dumps(manifest, ensure_ascii=False, indent=2),
        "health": json.dumps(health, ensure_ascii=False, indent=2),
        "ledger": "",
        "decisions": "",
        "inbox": "",
    }


def _materialize_runtime(fs: WorkspaceFS, copy_entry: dict[str, Any], *, write_missing: bool) -> dict[str, Any]:
    namespace = str(copy_entry.get("workspace_namespace", "")).strip() or f"managed_copies/{copy_entry.get('copy_id', 'copy')}"
    runtime = copy_entry.get("runtime", {}) if isinstance(copy_entry.get("runtime"), dict) else {}
    paths = _runtime_paths(namespace)
    payloads = _runtime_payloads(copy_entry)
    missing_paths: list[str] = []

    for key, path in paths.items():
        try:
            fs.read_text(path)
            exists = True
        except Exception:
            exists = False
        if not exists:
            missing_paths.append(path)
            if write_missing:
                if key == "manifest_path":
                    fs.write_text(path, payloads["manifest"])
                elif key == "health_path":
                    fs.write_text(path, payloads["health"])
                elif key == "ledger_path":
                    fs.write_text(path, payloads["ledger"])
                elif key == "decisions_path":
                    fs.write_text(path, payloads["decisions"])
                elif key == "inbox_path":
                    fs.write_text(path, payloads["inbox"])
        elif write_missing and key == "health_path":
            fs.write_text(path, payloads["health"])
        elif write_missing and key == "manifest_path":
            fs.write_text(path, payloads["manifest"])

    manifest = _read_json(fs, paths["manifest_path"])
    health = _read_json(fs, paths["health_path"])
    materialized = not missing_paths or write_missing
    now = utc_now_iso()
    return {
        **runtime,
        "namespace_root": namespace,
        **paths,
        "materialized": materialized,
        "materialized_at": runtime.get("materialized_at") if materialized and runtime.get("materialized_at") else (now if materialized else None),
        "last_checked_at": now,
        "missing_count": 0 if materialized else len(missing_paths),
        "missing_paths": [] if materialized else missing_paths,
        "manifest": manifest if isinstance(manifest, dict) else {},
        "health": health if isinstance(health, dict) else {},
        "health_status": str((health or {}).get("status", copy_entry.get("status", ""))).strip() or str(copy_entry.get("status", "")).strip() or "active",
        "manifest_updated_at": (manifest or {}).get("updated_at"),
        "health_updated_at": (health or {}).get("updated_at"),
    }


def _normalize_copy(entry: dict[str, Any]) -> dict[str, Any]:
    now = utc_now_iso()
    copy_id = str(entry.get("copy_id", "")).strip() or f"copy-{uuid4().hex[:12]}"
    status = str(entry.get("status", "active")).strip().lower() or "active"
    if status not in VALID_COPY_STATUSES:
        status = "active"
    sla_tier = str(entry.get("sla_tier", "standard")).strip().lower() or "standard"
    if sla_tier not in VALID_SLA_TIERS:
        sla_tier = "standard"
    namespace = str(entry.get("workspace_namespace", "")).strip() or f"managed_copies/{copy_id}"
    return {
        "copy_id": copy_id,
        "customer_label": str(entry.get("customer_label", "Managed Copy")).strip() or "Managed Copy",
        "status": status,
        "baseline_version": str(entry.get("baseline_version", "francis-core")).strip() or "francis-core",
        "sla_tier": sla_tier,
        "workspace_namespace": namespace,
        "capability_packs": _normalize_string_list(
            entry.get("capability_packs", []) if isinstance(entry.get("capability_packs"), list) else []
        ),
        "created_by": str(entry.get("created_by", "system")).strip() or "system",
        "created_at": str(entry.get("created_at", "")).strip() or now,
        "last_delta_at": str(entry.get("last_delta_at", "")).strip() or None,
        "last_delta_summary": str(entry.get("last_delta_summary", "")).strip(),
        "delta_count": int(entry.get("delta_count", 0) or 0),
        "quarantined_at": str(entry.get("quarantined_at", "")).strip() or None,
        "quarantine_reason": str(entry.get("quarantine_reason", "")).strip(),
        "replaced_at": str(entry.get("replaced_at", "")).strip() or None,
        "replacement_reason": str(entry.get("replacement_reason", "")).strip(),
        "replacement_copy_id": str(entry.get("replacement_copy_id", "")).strip() or None,
        "replaces_copy_id": str(entry.get("replaces_copy_id", "")).strip() or None,
        "notes": str(entry.get("notes", "")).strip(),
        "isolation": {
            "customer_isolated": True,
            "data_pooling": False,
            "delta_model": "safe_signals_only",
            "workspace_namespace": namespace,
        },
        "runtime": entry.get("runtime", {}) if isinstance(entry.get("runtime"), dict) else {},
    }


def load_or_init_registry(fs: WorkspaceFS) -> dict[str, Any]:
    parsed = _read_registry(fs)
    if not isinstance(parsed, dict):
        parsed = {}
    copies = parsed.get("copies", []) if isinstance(parsed.get("copies"), list) else []
    registry = {
        "version": int(parsed.get("version", 1) or 1),
        "updated_at": utc_now_iso(),
        "copies": [_normalize_copy(entry) for entry in copies if isinstance(entry, dict)],
    }
    return _write_registry(fs, registry)


def _replace_copy(registry: dict[str, Any], copy_entry: dict[str, Any]) -> dict[str, Any]:
    copy_id = str(copy_entry.get("copy_id", "")).strip()
    next_rows: list[dict[str, Any]] = []
    replaced = False
    for entry in registry.get("copies", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("copy_id", "")).strip() == copy_id:
            next_rows.append(copy_entry)
            replaced = True
        else:
            next_rows.append(entry)
    if not replaced:
        next_rows.append(copy_entry)
    registry["copies"] = next_rows
    registry["updated_at"] = utc_now_iso()
    return registry


def get_copy(fs: WorkspaceFS, copy_id: str) -> dict[str, Any] | None:
    registry = load_or_init_registry(fs)
    normalized_copy_id = str(copy_id).strip()
    for entry in registry.get("copies", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("copy_id", "")).strip() == normalized_copy_id:
            return entry
    return None


def create_copy(
    fs: WorkspaceFS,
    *,
    customer_label: str,
    baseline_version: str,
    sla_tier: str,
    capability_packs: list[str] | None,
    notes: str,
    created_by: str,
) -> dict[str, Any]:
    registry = load_or_init_registry(fs)
    copy_entry = _normalize_copy(
        {
            "copy_id": f"copy-{uuid4().hex[:12]}",
            "customer_label": customer_label,
            "status": "active",
            "baseline_version": baseline_version,
            "sla_tier": sla_tier,
            "capability_packs": capability_packs or [],
            "created_by": created_by,
            "created_at": utc_now_iso(),
            "notes": notes,
        }
    )
    copy_entry["runtime"] = _materialize_runtime(fs, copy_entry, write_missing=True)
    _write_registry(fs, _replace_copy(registry, copy_entry))
    return copy_entry


def record_delta(
    fs: WorkspaceFS,
    *,
    run_id: str,
    copy_id: str,
    signal_kind: str,
    summary: str,
    evidence_refs: list[str] | None,
    capability_packs: list[str] | None,
    source_node_id: str | None = None,
) -> dict[str, Any] | None:
    registry = load_or_init_registry(fs)
    copy_entry = get_copy(fs, copy_id)
    if copy_entry is None:
        return None
    if str(copy_entry.get("status", "")).strip().lower() != "active":
        raise ValueError("Only active managed copies can accept deltas")
    delta = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "copy_id": str(copy_entry.get("copy_id", "")).strip(),
        "signal_kind": str(signal_kind).strip().lower() or "capability_signal",
        "summary": str(summary).strip(),
        "evidence_refs": _normalize_string_list(evidence_refs or []),
        "capability_packs": _normalize_string_list(capability_packs or []),
        "source_node_id": str(source_node_id or "").strip() or None,
        "delta_model": "safe_signals_only",
    }
    _append_jsonl(fs, MANAGED_COPY_DELTAS_PATH, delta)
    copy_entry["last_delta_at"] = delta["ts"]
    copy_entry["last_delta_summary"] = delta["summary"]
    copy_entry["delta_count"] = int(copy_entry.get("delta_count", 0) or 0) + 1
    if delta["capability_packs"]:
        existing = _normalize_string_list(copy_entry.get("capability_packs", []) if isinstance(copy_entry.get("capability_packs"), list) else [])
        copy_entry["capability_packs"] = _normalize_string_list(existing + delta["capability_packs"])
    copy_entry["runtime"] = _materialize_runtime(fs, copy_entry, write_missing=True)
    _write_registry(fs, _replace_copy(registry, _normalize_copy(copy_entry)))
    return delta


def quarantine_copy(
    fs: WorkspaceFS,
    *,
    copy_id: str,
    reason: str,
) -> dict[str, Any] | None:
    registry = load_or_init_registry(fs)
    copy_entry = get_copy(fs, copy_id)
    if copy_entry is None:
        return None
    copy_entry["status"] = "quarantined"
    copy_entry["quarantined_at"] = utc_now_iso()
    copy_entry["quarantine_reason"] = str(reason).strip() or "Managed copy quarantined."
    copy_entry["runtime"] = _materialize_runtime(fs, copy_entry, write_missing=True)
    _write_registry(fs, _replace_copy(registry, _normalize_copy(copy_entry)))
    return _normalize_copy(copy_entry)


def replace_copy(
    fs: WorkspaceFS,
    *,
    copy_id: str,
    reason: str,
    baseline_version: str | None,
    replaced_by: str,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    registry = load_or_init_registry(fs)
    copy_entry = get_copy(fs, copy_id)
    if copy_entry is None:
        return None
    if str(copy_entry.get("status", "")).strip().lower() == "replaced":
        raise ValueError("Managed copy is already replaced")
    replacement = _normalize_copy(
        {
            "copy_id": f"copy-{uuid4().hex[:12]}",
            "customer_label": copy_entry.get("customer_label"),
            "status": "active",
            "baseline_version": str(baseline_version or copy_entry.get("baseline_version", "francis-core")).strip()
            or "francis-core",
            "sla_tier": copy_entry.get("sla_tier", "standard"),
            "capability_packs": copy_entry.get("capability_packs", []),
            "created_by": replaced_by,
            "created_at": utc_now_iso(),
            "notes": f"Replacement for {str(copy_entry.get('copy_id', '')).strip()}",
            "replaces_copy_id": str(copy_entry.get("copy_id", "")).strip(),
        }
    )
    replacement["runtime"] = _materialize_runtime(fs, replacement, write_missing=True)
    copy_entry["status"] = "replaced"
    copy_entry["replaced_at"] = utc_now_iso()
    copy_entry["replacement_reason"] = str(reason).strip() or "Managed copy replaced from a clean baseline."
    copy_entry["replacement_copy_id"] = str(replacement.get("copy_id", "")).strip()
    copy_entry["runtime"] = _materialize_runtime(fs, copy_entry, write_missing=True)
    _write_registry(fs, _replace_copy(registry, _normalize_copy(copy_entry)))
    registry = load_or_init_registry(fs)
    _write_registry(fs, _replace_copy(registry, replacement))
    return (_normalize_copy(copy_entry), replacement)


def materialize_copy(fs: WorkspaceFS, *, copy_id: str) -> dict[str, Any] | None:
    registry = load_or_init_registry(fs)
    copy_entry = get_copy(fs, copy_id)
    if copy_entry is None:
        return None
    copy_entry["runtime"] = _materialize_runtime(fs, copy_entry, write_missing=True)
    normalized = _normalize_copy(copy_entry)
    _write_registry(fs, _replace_copy(registry, normalized))
    return normalized


def build_managed_copy_state(fs: WorkspaceFS) -> dict[str, Any]:
    registry = load_or_init_registry(fs)
    copies: list[dict[str, Any]] = []
    for entry in registry.get("copies", []):
        if not isinstance(entry, dict):
            continue
        normalized = _normalize_copy(entry)
        normalized["runtime"] = _materialize_runtime(fs, normalized, write_missing=False)
        copies.append(normalized)
    deltas = _read_jsonl(fs, MANAGED_COPY_DELTAS_PATH)
    active_count = sum(1 for entry in copies if str(entry.get("status", "")).strip().lower() == "active")
    quarantined_count = sum(1 for entry in copies if str(entry.get("status", "")).strip().lower() == "quarantined")
    replaced_count = sum(1 for entry in copies if str(entry.get("status", "")).strip().lower() == "replaced")
    materialized_count = sum(
        1
        for entry in copies
        if bool((entry.get("runtime", {}) if isinstance(entry.get("runtime"), dict) else {}).get("materialized", False))
    )
    unmaterialized_count = max(len(copies) - materialized_count, 0)
    return {
        "copies": copies,
        "deltas": deltas[-20:],
        "copy_count": len(copies),
        "active_count": active_count,
        "quarantined_count": quarantined_count,
        "replaced_count": replaced_count,
        "delta_count": len(deltas),
        "materialized_count": materialized_count,
        "unmaterialized_count": unmaterialized_count,
        "summary": (
            f"{len(copies)} managed copy(ies), {active_count} active, "
            f"{quarantined_count} quarantined, {replaced_count} replaced, "
            f"{materialized_count} materialized, {unmaterialized_count} with runtime drift, "
            f"{len(deltas)} safe delta(s)."
        ),
        "updated_at": registry.get("updated_at"),
    }
