from __future__ import annotations

import json
from typing import Any

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS

REGISTRY_PATH = "connectors/registry.json"

_BUILTIN_CONNECTORS: list[dict[str, Any]] = [
    {
        "id": "filesystem",
        "name": "Filesystem",
        "slug": "filesystem",
        "description": "Local workspace filesystem connector shipped with Francis.",
        "module": "francis_connectors.filesystem",
        "status": "available",
        "enabled": False,
        "risk_tier": "low",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/filesystem.py",
            "review_state": "internal",
        },
    },
    {
        "id": "calendar",
        "name": "Calendar",
        "slug": "calendar",
        "description": "Calendar service connector adapter shipped with Francis.",
        "module": "francis_connectors.calendar",
        "status": "available",
        "enabled": False,
        "risk_tier": "medium",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/calendar.py",
            "review_state": "internal",
        },
    },
    {
        "id": "discord",
        "name": "Discord",
        "slug": "discord",
        "description": "Discord connector adapter shipped with Francis.",
        "module": "francis_connectors.discord",
        "status": "available",
        "enabled": False,
        "risk_tier": "medium",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/discord.py",
            "review_state": "internal",
        },
    },
    {
        "id": "email",
        "name": "Email",
        "slug": "email",
        "description": "Email connector adapter shipped with Francis.",
        "module": "francis_connectors.email",
        "status": "available",
        "enabled": False,
        "risk_tier": "medium",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/email.py",
            "review_state": "internal",
        },
    },
    {
        "id": "home_assistant",
        "name": "Home Assistant",
        "slug": "home-assistant",
        "description": "Home Assistant connector adapter shipped with Francis.",
        "module": "francis_connectors.home_assistant",
        "status": "available",
        "enabled": False,
        "risk_tier": "high",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/home_assistant.py",
            "review_state": "internal",
        },
    },
    {
        "id": "telegram",
        "name": "Telegram",
        "slug": "telegram",
        "description": "Telegram connector adapter shipped with Francis.",
        "module": "francis_connectors.telegram",
        "status": "available",
        "enabled": False,
        "risk_tier": "medium",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/telegram.py",
            "review_state": "internal",
        },
    },
    {
        "id": "webhooks",
        "name": "Webhooks",
        "slug": "webhooks",
        "description": "Webhook connector adapter shipped with Francis.",
        "module": "francis_connectors.webhooks",
        "status": "available",
        "enabled": False,
        "risk_tier": "medium",
        "provenance": {
            "source_kind": "internal",
            "source_ref": "packages/francis_connectors/francis_connectors/webhooks.py",
            "review_state": "internal",
        },
    },
]


def _read_registry(fs: WorkspaceFS) -> list[dict[str, Any]]:
    try:
        payload = json.loads(fs.read_text(REGISTRY_PATH))
    except Exception:
        return []
    rows = payload.get("connectors", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _write_registry(fs: WorkspaceFS, rows: list[dict[str, Any]]) -> None:
    fs.write_text(REGISTRY_PATH, json.dumps({"connectors": rows}, ensure_ascii=False, indent=2))


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"active", "enabled", "connected"}:
        return "active"
    if normalized in {"available", "cataloged", "installed"}:
        return "available"
    if normalized in {"disabled", "inactive"}:
        return "disabled"
    if normalized in {"quarantine", "quarantined"}:
        return "quarantined"
    if normalized in {"revoke", "revoked", "retired"}:
        return "revoked"
    return normalized or "available"


def _normalize_entry(entry: dict[str, Any], *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**(base or {}), **entry}
    base_provenance = base.get("provenance", {}) if isinstance((base or {}).get("provenance"), dict) else {}
    entry_provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    merged["provenance"] = {**base_provenance, **entry_provenance}
    merged["id"] = str(merged.get("id", "")).strip()
    merged["name"] = str(merged.get("name", "")).strip() or merged["id"] or "Connector"
    merged["slug"] = str(merged.get("slug", "")).strip() or merged["id"]
    merged["description"] = str(merged.get("description", "")).strip()
    merged["module"] = str(merged.get("module", "")).strip()
    merged["status"] = _normalize_status(merged.get("status"))
    merged["risk_tier"] = str(merged.get("risk_tier", "medium")).strip().lower() or "medium"
    if "enabled" not in merged:
        merged["enabled"] = merged["status"] == "active"
    else:
        merged["enabled"] = bool(merged.get("enabled", False))
    return merged


def _builtin_map() -> dict[str, dict[str, Any]]:
    return {row["id"]: _normalize_entry(row) for row in _BUILTIN_CONNECTORS}


def list_connector_entries(fs: WorkspaceFS) -> list[dict[str, Any]]:
    registry_rows = _read_registry(fs)
    entries = _builtin_map()
    for row in registry_rows:
        connector_id = str(row.get("id", "")).strip()
        if not connector_id:
            continue
        entries[connector_id] = _normalize_entry(row, base=entries.get(connector_id))
    return sorted(entries.values(), key=lambda row: (str(row.get("name", "")).lower(), str(row.get("id", "")).lower()))


def build_connector_provenance(entry: dict[str, Any], *, approval_status: str = "") -> dict[str, Any]:
    provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    status = _normalize_status(entry.get("status"))
    explicit_kind = str(
        provenance.get("kind")
        or provenance.get("source_kind")
        or provenance.get("origin_kind")
        or ""
    ).strip().lower()
    vendor_name = str(
        provenance.get("vendor")
        or provenance.get("provider")
        or provenance.get("publisher")
        or ""
    ).strip()
    source_ref = str(
        provenance.get("source_ref")
        or provenance.get("source_url")
        or provenance.get("source")
        or provenance.get("registry")
        or provenance.get("path")
        or ""
    ).strip()
    imported_at = str(provenance.get("imported_at") or entry.get("imported_at") or "").strip()
    review_state = str(
        provenance.get("review_state")
        or provenance.get("review_status")
        or ("approved" if approval_status == "approved" else "")
    ).strip().lower()

    if status == "quarantined":
        kind = "quarantined"
        review_state = "quarantined"
    elif status == "revoked":
        kind = "revoked"
        review_state = "revoked"
    elif explicit_kind in {"vendor", "vendor_provided", "official"}:
        kind = "vendor"
    elif explicit_kind in {"third_party", "thirdparty", "external", "community", "dependency"}:
        kind = "third_party"
    elif explicit_kind in {"local_import", "local", "imported"}:
        kind = "local_import"
    else:
        kind = "internal"

    traceable = kind == "internal" or bool(source_ref or vendor_name or str(entry.get("module", "")).strip())
    external = kind in {"local_import", "vendor", "third_party"}

    review_required = False
    tone = "low"
    review_label = "internal"
    summary = "Connector ships with Francis and remains under internal governance."
    rule_detail = ""

    if kind == "quarantined":
        review_required = True
        tone = "high"
        review_label = "quarantined"
        summary = "Connector is quarantined and blocked from governed use."
        rule_detail = "Connector is quarantined and must not remain active."
    elif kind == "revoked":
        review_required = False
        tone = "high"
        review_label = "revoked"
        summary = "Connector is revoked and remains cataloged only for audit continuity."
        rule_detail = "Connector is revoked and cannot be restored without a new trusted import."
    elif not external:
        review_required = False
        tone = "low"
        review_label = "internal"
    else:
        review_label = review_state or "review required"
        if not traceable:
            review_required = True
            tone = "high" if kind == "third_party" else "medium"
            summary = "External connector is missing provenance anchors and cannot be trusted for governed use."
            rule_detail = "Connector is missing provenance anchors."
        elif review_state in {"approved", "internal"}:
            review_required = False
            tone = "low"
            summary = (
                f"{'Vendor provided' if kind == 'vendor' else 'Imported'} connector is traceable and approved for governed use."
            )
            rule_detail = "Connector provenance is traceable and approved."
        else:
            review_required = True
            tone = "high" if kind == "third_party" else "medium"
            summary = (
                f"{'Vendor provided' if kind == 'vendor' else 'Imported'} connector is traceable but still requires governance review."
            )
            rule_detail = "Connector provenance is traceable but still awaiting review."

    label_map = {
        "internal": "Internal",
        "local_import": "Local Import",
        "vendor": "Vendor Provided",
        "third_party": "Third-Party",
        "quarantined": "Quarantined",
        "revoked": "Revoked",
    }
    source_label = (
        vendor_name
        or source_ref
        or str(entry.get("module", "")).strip()
        or "generated inside Francis"
    )
    return {
        "kind": kind,
        "label": label_map.get(kind, "Internal"),
        "tone": tone,
        "summary": summary,
        "review_required": review_required,
        "review_state": review_state or ("internal" if kind == "internal" else ""),
        "review_label": review_label,
        "source_label": source_label,
        "source_ref": source_ref or None,
        "vendor_name": vendor_name or None,
        "traceable": traceable,
        "external": external,
        "imported_at": imported_at or None,
        "promotion_rule_detail": rule_detail,
        "quarantined": kind == "quarantined",
        "revoked": kind == "revoked",
    }


def build_connector_library(entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [entry for entry in entries if isinstance(entry, dict)]
    statuses = [_normalize_status(row.get("status")) for row in rows]
    active_count = sum(1 for status in statuses if status == "active")
    available_count = sum(1 for status in statuses if status == "available")
    disabled_count = sum(1 for status in statuses if status == "disabled")
    quarantined_count = sum(1 for status in statuses if status == "quarantined")
    revoked_count = sum(1 for status in statuses if status == "revoked")
    provenance_rows = [build_connector_provenance(row) for row in rows]
    external_count = sum(1 for row in provenance_rows if bool(row.get("external")))
    review_required_count = sum(1 for row in provenance_rows if bool(row.get("review_required")))
    return {
        "connector_count": len(rows),
        "active_count": active_count,
        "available_count": available_count,
        "disabled_count": disabled_count,
        "quarantined_count": quarantined_count,
        "revoked_count": revoked_count,
        "external_count": external_count,
        "review_required_count": review_required_count,
    }


def _upsert_registry_entry(
    fs: WorkspaceFS,
    connector_id: str,
    *,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    normalized_id = str(connector_id or "").strip()
    if not normalized_id:
        return None
    current_entries = {row["id"]: row for row in list_connector_entries(fs) if str(row.get("id", "")).strip()}
    base = current_entries.get(normalized_id)
    if base is None:
        return None

    rows = _read_registry(fs)
    index = next((idx for idx, row in enumerate(rows) if str(row.get("id", "")).strip() == normalized_id), None)
    existing = rows[index] if index is not None else {}
    merged = _normalize_entry({**existing, **patch, "id": normalized_id}, base=base)
    if index is None:
        rows.append(merged)
    else:
        rows[index] = merged
    _write_registry(fs, rows)
    refreshed = {row["id"]: row for row in list_connector_entries(fs) if str(row.get("id", "")).strip()}
    return refreshed.get(normalized_id)


def quarantine_connector(
    fs: WorkspaceFS,
    connector_id: str,
    *,
    reason: str,
    actor: str,
) -> dict[str, Any] | None:
    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Connector quarantined from Lens."
    normalized_actor = str(actor or "").strip() or "lens:architect"
    return _upsert_registry_entry(
        fs,
        connector_id,
        patch={
            "status": "quarantined",
            "enabled": False,
            "previous_status": _normalize_status(next((row for row in list_connector_entries(fs) if row.get("id") == connector_id), {}).get("status")),
            "quarantined_at": now,
            "quarantine_reason": normalized_reason,
            "quarantined_by": normalized_actor,
            "provenance": {
                "review_state": "quarantined",
                "reviewed_at": now,
                "reviewed_by": normalized_actor,
                "review_note": normalized_reason,
            },
        },
    )


def revoke_connector(
    fs: WorkspaceFS,
    connector_id: str,
    *,
    reason: str,
    actor: str,
) -> dict[str, Any] | None:
    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Connector revoked from Lens."
    normalized_actor = str(actor or "").strip() or "lens:architect"
    current = next((row for row in list_connector_entries(fs) if str(row.get("id", "")).strip() == str(connector_id).strip()), None)
    if current is None:
        return None
    patch: dict[str, Any] = {
        "status": "revoked",
        "enabled": False,
        "previous_status": _normalize_status(current.get("status")),
        "revoked_at": now,
        "revocation_reason": normalized_reason,
        "revoked_by": normalized_actor,
        "provenance": {
            "review_state": "revoked",
            "reviewed_at": now,
            "reviewed_by": normalized_actor,
            "review_note": normalized_reason,
        },
    }
    if not current.get("quarantined_at"):
        patch["quarantined_at"] = None
    return _upsert_registry_entry(fs, connector_id, patch=patch)
