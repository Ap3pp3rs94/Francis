from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_state(copy_id: str, focus_copy_id: str) -> str:
    if copy_id and focus_copy_id and copy_id == focus_copy_id:
        return "current"
    return "historical"


def _row_summary(copy_row: dict[str, Any]) -> str:
    label = str(copy_row.get("customer_label", "Managed Copy")).strip() or "Managed Copy"
    status = str(copy_row.get("status", "active")).strip() or "active"
    baseline = str(copy_row.get("baseline_version", "francis-core")).strip() or "francis-core"
    delta_count = int(copy_row.get("delta_count", 0) or 0)
    return f"{label} is {status} on {baseline} with {delta_count} safe delta(s) recorded."


def _detail_cards(copy_row: dict[str, Any]) -> list[dict[str, str]]:
    status = str(copy_row.get("status", "active")).strip().lower() or "active"
    delta_count = int(copy_row.get("delta_count", 0) or 0)
    return [
        {"label": "Status", "value": status, "tone": "high" if status == "quarantined" else "medium" if status == "replaced" else "low"},
        {"label": "SLA", "value": str(copy_row.get("sla_tier", "standard")).strip() or "standard", "tone": "medium"},
        {"label": "Baseline", "value": str(copy_row.get("baseline_version", "francis-core")).strip() or "francis-core", "tone": "low"},
        {"label": "Namespace", "value": str(copy_row.get("workspace_namespace", "")).strip() or "managed_copies", "tone": "low"},
        {"label": "Delta Count", "value": str(delta_count), "tone": "high" if delta_count else "low"},
        {"label": "Isolation", "value": "signals only", "tone": "low"},
    ]


def _audit(copy_row: dict[str, Any], detail_state: str) -> dict[str, Any]:
    isolation = copy_row.get("isolation", {}) if isinstance(copy_row.get("isolation"), dict) else {}
    return {
        "copy_id": str(copy_row.get("copy_id", "")).strip(),
        "customer_label": str(copy_row.get("customer_label", "")).strip(),
        "status": str(copy_row.get("status", "")).strip(),
        "detail_state": detail_state,
        "baseline_version": str(copy_row.get("baseline_version", "")).strip(),
        "sla_tier": str(copy_row.get("sla_tier", "")).strip(),
        "workspace_namespace": str(copy_row.get("workspace_namespace", "")).strip(),
        "capability_packs": copy_row.get("capability_packs", []) if isinstance(copy_row.get("capability_packs"), list) else [],
        "last_delta_at": copy_row.get("last_delta_at"),
        "last_delta_summary": str(copy_row.get("last_delta_summary", "")).strip(),
        "delta_count": int(copy_row.get("delta_count", 0) or 0),
        "quarantined_at": copy_row.get("quarantined_at"),
        "quarantine_reason": str(copy_row.get("quarantine_reason", "")).strip(),
        "replaced_at": copy_row.get("replaced_at"),
        "replacement_reason": str(copy_row.get("replacement_reason", "")).strip(),
        "replacement_copy_id": str(copy_row.get("replacement_copy_id", "")).strip() or None,
        "replaces_copy_id": str(copy_row.get("replaces_copy_id", "")).strip() or None,
        "isolation": {
            "customer_isolated": bool(isolation.get("customer_isolated", True)),
            "data_pooling": bool(isolation.get("data_pooling", False)),
            "delta_model": str(isolation.get("delta_model", "safe_signals_only")).strip() or "safe_signals_only",
        },
    }


def _controls(copy_row: dict[str, Any]) -> dict[str, dict[str, Any]]:
    copy_id = str(copy_row.get("copy_id", "")).strip()
    status = str(copy_row.get("status", "active")).strip().lower() or "active"
    active = status == "active"
    return {
        "record_delta": {
            "label": "Record Safe Delta",
            "enabled": bool(copy_id) and active,
            "kind": "managed_copies.delta",
            "summary": (
                "Record a summarized safe delta signal for this managed copy."
                if bool(copy_id) and active
                else "Only active copies can accept safe deltas."
            ),
            "copy_id": copy_id,
        },
        "quarantine": {
            "label": "Quarantine Copy",
            "enabled": bool(copy_id) and active,
            "kind": "managed_copies.quarantine",
            "summary": (
                "Quarantine this copy while preserving traceable evidence."
                if bool(copy_id) and active
                else "Only active copies can be quarantined."
            ),
            "copy_id": copy_id,
        },
        "replace": {
            "label": "Replace From Clean Baseline",
            "enabled": bool(copy_id) and status in {"active", "quarantined"},
            "kind": "managed_copies.replace",
            "summary": (
                "Replace this copy from a clean baseline while preserving lineage."
                if bool(copy_id) and status in {"active", "quarantined"}
                else "Replaced copies cannot be replaced again from this surface."
            ),
            "copy_id": copy_id,
        },
    }


def get_managed_copies_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    managed = snapshot.get("managed_copies", {}) if isinstance(snapshot.get("managed_copies"), dict) else {}
    copies = [row for row in managed.get("copies", []) if isinstance(row, dict)]

    focus_row = next((row for row in copies if str(row.get("status", "")).strip().lower() == "quarantined"), None)
    if focus_row is None:
        focus_row = next((row for row in copies if int(row.get("delta_count", 0) or 0) > 0), None)
    if focus_row is None:
        focus_row = copies[0] if copies else None
    focus_copy_id = str((focus_row or {}).get("copy_id", "")).strip()

    rows: list[dict[str, Any]] = []
    for copy_row in copies:
        copy_id = str(copy_row.get("copy_id", "")).strip()
        detail_state = _detail_state(copy_id, focus_copy_id)
        rows.append(
            {
                "copy_id": copy_id,
                "customer_label": str(copy_row.get("customer_label", "Managed Copy")).strip() or "Managed Copy",
                "status": str(copy_row.get("status", "active")).strip() or "active",
                "summary": _row_summary(copy_row),
                "detail_summary": _row_summary(copy_row),
                "detail_state": detail_state,
                "detail_cards": _detail_cards(copy_row),
                "audit": _audit(copy_row, detail_state),
                "controls": _controls(copy_row),
            }
        )

    focused = next((row for row in rows if str(row.get("copy_id", "")).strip() == focus_copy_id), None)
    quarantined_count = int(managed.get("quarantined_count", 0) or 0)
    severity = "high" if quarantined_count > 0 else "medium" if rows else "low"
    return {
        "status": "ok",
        "surface": "managed_copies",
        "summary": str(managed.get("summary", "")).strip() or "No managed copies have been created yet.",
        "severity": severity,
        "focus_copy_id": focus_copy_id,
        "creation": {
            "default_baseline_version": "francis-core",
            "default_sla_tier": "standard",
            "sla_tiers": ["standard", "premium", "critical"],
        },
        "cards": [
            {"label": "Copies", "value": str(int(managed.get("copy_count", 0) or 0)), "tone": "medium" if rows else "low"},
            {"label": "Active", "value": str(int(managed.get("active_count", 0) or 0)), "tone": "low"},
            {"label": "Quarantined", "value": str(quarantined_count), "tone": "high" if quarantined_count else "low"},
            {"label": "Replaced", "value": str(int(managed.get("replaced_count", 0) or 0)), "tone": "medium" if int(managed.get("replaced_count", 0) or 0) else "low"},
            {"label": "Safe Deltas", "value": str(int(managed.get("delta_count", 0) or 0)), "tone": "medium" if int(managed.get("delta_count", 0) or 0) else "low"},
        ],
        "copies": rows,
        "detail": {
            "audit": focused.get("audit", {}) if isinstance(focused, dict) else {},
            "controls": focused.get("controls", {}) if isinstance(focused, dict) else {},
        },
    }
