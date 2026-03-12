from __future__ import annotations

from typing import Any

from services.hud.app.state import build_lens_snapshot


def _detail_state(row_id: str, focus_id: str) -> str:
    if row_id and focus_id and row_id == focus_id:
        return "current"
    return "historical"


def _export_counts(row: dict[str, Any]) -> dict[str, int]:
    counts = row.get("counts", {}) if isinstance(row.get("counts"), dict) else {}
    if counts:
        return {
            "mission_count": int(counts.get("mission_count", 0) or 0),
            "pending_approvals": int(counts.get("pending_approvals", 0) or 0),
            "capability_count": int(counts.get("capability_count", 0) or 0),
            "paired_node_count": int(counts.get("paired_node_count", 0) or 0),
            "managed_copy_count": int(counts.get("managed_copy_count", 0) or 0),
            "swarm_unit_count": int(counts.get("swarm_unit_count", 0) or 0),
        }
    return {
        "mission_count": int(row.get("mission_count", 0) or 0),
        "pending_approvals": int(row.get("pending_approvals", 0) or 0),
        "capability_count": int(row.get("capability_count", 0) or 0),
        "paired_node_count": int(row.get("paired_node_count", 0) or 0),
        "managed_copy_count": int(row.get("managed_copy_count", 0) or 0),
        "swarm_unit_count": int(row.get("swarm_unit_count", 0) or 0),
    }


def _export_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    counts = _export_counts(row)
    return [
        {"label": "Missions", "value": str(counts["mission_count"]), "tone": "medium" if counts["mission_count"] else "low"},
        {"label": "Capabilities", "value": str(counts["capability_count"]), "tone": "medium" if counts["capability_count"] else "low"},
        {"label": "Pending Approvals", "value": str(counts["pending_approvals"]), "tone": "high" if counts["pending_approvals"] else "low"},
        {"label": "Paired Nodes", "value": str(counts["paired_node_count"]), "tone": "high" if counts["paired_node_count"] else "low"},
        {"label": "Managed Copies", "value": str(counts["managed_copy_count"]), "tone": "medium" if counts["managed_copy_count"] else "low"},
        {"label": "Swarm Units", "value": str(counts["swarm_unit_count"]), "tone": "medium" if counts["swarm_unit_count"] else "low"},
    ]


def _import_cards(row: dict[str, Any]) -> list[dict[str, str]]:
    warnings = int(row.get("warning_count", 0) or 0)
    restored = row.get("restored_sections", []) if isinstance(row.get("restored_sections"), list) else []
    archived = row.get("archived_sections", []) if isinstance(row.get("archived_sections"), list) else []
    return [
        {"label": "Warnings", "value": str(warnings), "tone": "high" if warnings else "low"},
        {"label": "Restored", "value": str(len(restored)), "tone": "medium" if restored else "low"},
        {"label": "Archived", "value": str(len(archived)), "tone": "low"},
        {"label": "Applied By", "value": str(row.get("applied_by", "operator")).strip() or "operator", "tone": "low"},
    ]


def _export_audit(row: dict[str, Any], detail_state: str) -> dict[str, Any]:
    return {
        "bundle_id": str(row.get("bundle_id", "")).strip(),
        "label": str(row.get("label", "")).strip(),
        "created_at": row.get("created_at"),
        "created_by": str(row.get("created_by", "")).strip(),
        "path": str(row.get("path", "")).strip(),
        "summary": str(row.get("summary", "")).strip(),
        "detail_state": detail_state,
        "counts": _export_counts(row),
        "note": str(row.get("note", "")).strip(),
    }


def _import_audit(row: dict[str, Any], detail_state: str) -> dict[str, Any]:
    return {
        "import_id": str(row.get("import_id", "")).strip(),
        "bundle_id": str(row.get("bundle_id", "")).strip(),
        "preview_id": str(row.get("preview_id", "")).strip(),
        "source_path": str(row.get("source_path", "")).strip(),
        "applied_at": row.get("applied_at"),
        "applied_by": str(row.get("applied_by", "")).strip(),
        "summary": str(row.get("summary", "")).strip(),
        "warnings": row.get("warnings", []) if isinstance(row.get("warnings"), list) else [],
        "detail_state": detail_state,
        "restored_sections": row.get("restored_sections", []) if isinstance(row.get("restored_sections"), list) else [],
        "archived_sections": row.get("archived_sections", []) if isinstance(row.get("archived_sections"), list) else [],
    }


def get_portability_view(*, snapshot: dict[str, object] | None = None) -> dict[str, Any]:
    if snapshot is None:
        snapshot = build_lens_snapshot()
    portability = snapshot.get("portability", {}) if isinstance(snapshot.get("portability"), dict) else {}
    exports = [row for row in portability.get("exports", []) if isinstance(row, dict)]
    imports = [row for row in portability.get("imports", []) if isinstance(row, dict)]
    preview = portability.get("preview", {}) if isinstance(portability.get("preview"), dict) else {}
    continuity = portability.get("continuity", {}) if isinstance(portability.get("continuity"), dict) else {}

    focus_bundle_id = str(preview.get("bundle_id", "")).strip()
    if not focus_bundle_id and exports:
        focus_bundle_id = str(exports[-1].get("bundle_id", "")).strip()
    focus_import_id = str(preview.get("import_id", "")).strip()
    if not focus_import_id and imports:
        focus_import_id = str(imports[-1].get("import_id", "")).strip()

    export_rows: list[dict[str, Any]] = []
    for row in reversed(exports):
        bundle_id = str(row.get("bundle_id", "")).strip()
        detail_state = _detail_state(bundle_id, focus_bundle_id)
        summary = str(row.get("summary", "")).strip() or "Governed continuity bundle ready."
        export_rows.append(
            {
                "bundle_id": bundle_id,
                "label": str(row.get("label", "Continuity Bundle")).strip() or "Continuity Bundle",
                "summary": summary,
                "detail_summary": summary,
                "detail_state": detail_state,
                "detail_cards": _export_cards(row),
                "audit": _export_audit(row, detail_state),
            }
        )

    import_rows: list[dict[str, Any]] = []
    for row in reversed(imports):
        import_id = str(row.get("import_id", "")).strip()
        detail_state = _detail_state(import_id, focus_import_id)
        summary = str(row.get("summary", "")).strip() or "Governed continuity import applied."
        import_rows.append(
            {
                "import_id": import_id,
                "bundle_id": str(row.get("bundle_id", "")).strip(),
                "summary": summary,
                "detail_summary": summary,
                "detail_state": detail_state,
                "detail_cards": _import_cards(row),
                "audit": _import_audit(row, detail_state),
            }
        )

    focused_export = next((row for row in export_rows if str(row.get("bundle_id", "")).strip() == focus_bundle_id), None)
    focused_import = next((row for row in import_rows if str(row.get("import_id", "")).strip() == focus_import_id), None)
    warning_count = len(preview.get("warnings", [])) if isinstance(preview.get("warnings"), list) else 0
    apply_enabled = bool(str(preview.get("preview_id", "")).strip()) and not bool(str(preview.get("applied_at", "")).strip())

    return {
        "status": "ok",
        "surface": "portability",
        "summary": str(portability.get("summary", "")).strip() or "Governed continuity export and import will render here.",
        "severity": str(portability.get("severity", "low")).strip().lower() or "low",
        "preview_state": str(portability.get("preview_state", "idle")).strip().lower() or "idle",
        "focus_bundle_id": focus_bundle_id,
        "focus_import_id": focus_import_id,
        "cards": [
            {"label": "Exports", "value": str(int(portability.get("export_count", 0) or 0)), "tone": "medium" if int(portability.get("export_count", 0) or 0) else "low"},
            {"label": "Imports", "value": str(int(portability.get("import_count", 0) or 0)), "tone": "medium" if int(portability.get("import_count", 0) or 0) else "low"},
            {"label": "Preview Warnings", "value": str(warning_count), "tone": "high" if warning_count else "low"},
            {"label": "Mode", "value": str(continuity.get("mode", "assist")).strip() or "assist", "tone": "medium" if str(continuity.get("mode", "")).strip().lower() in {"pilot", "away"} else "low"},
            {"label": "Pending Approvals", "value": str(int(continuity.get("pending_approvals", 0) or 0)), "tone": "high" if int(continuity.get("pending_approvals", 0) or 0) else "low"},
        ],
        "exports": export_rows,
        "imports": import_rows,
        "preview": {
            "preview_id": str(preview.get("preview_id", "")).strip(),
            "bundle_id": str(preview.get("bundle_id", "")).strip(),
            "bundle_label": str(preview.get("bundle_label", "")).strip(),
            "source_path": str(preview.get("source_path", "")).strip(),
            "summary": str(preview.get("summary", "")).strip() or "Preview a governed continuity bundle to inspect restore and archive effects.",
            "severity": str(preview.get("severity", "low")).strip().lower() or "low",
            "warnings": [str(item).strip() for item in preview.get("warnings", []) if str(item).strip()] if isinstance(preview.get("warnings"), list) else [],
            "cards": [row for row in preview.get("cards", []) if isinstance(row, dict)],
            "restore_sections": [row for row in preview.get("restore_sections", []) if isinstance(row, dict)],
            "archive_sections": [row for row in preview.get("archive_sections", []) if isinstance(row, dict)],
            "effects": preview.get("effects", {}) if isinstance(preview.get("effects"), dict) else {},
            "applied_at": preview.get("applied_at"),
            "import_id": str(preview.get("import_id", "")).strip(),
        },
        "controls": {
            "export": {
                "kind": "portability.export",
                "label": "Export Continuity Bundle",
                "enabled": True,
                "summary": "Export governed continuity without replaying live authority on import.",
            },
            "preview_latest": {
                "kind": "portability.import.preview",
                "label": "Preview Latest Import",
                "enabled": bool(focus_bundle_id),
                "bundle_id": focus_bundle_id,
                "summary": (
                    "Preview the latest continuity bundle against current-machine import rules."
                    if focus_bundle_id
                    else "Export a continuity bundle before previewing import."
                ),
            },
            "apply_preview": {
                "kind": "portability.import.apply",
                "label": "Apply Previewed Import",
                "enabled": apply_enabled,
                "preview_id": str(preview.get("preview_id", "")).strip(),
                "summary": (
                    "Apply the current preview with authority downgraded and archive-only sections preserved."
                    if apply_enabled
                    else "Preview a continuity bundle before applying import."
                ),
            },
        },
        "detail": {
            "continuity": continuity,
            "focused_export_audit": focused_export.get("audit", {}) if isinstance(focused_export, dict) else {},
            "focused_import_audit": focused_import.get("audit", {}) if isinstance(focused_import, dict) else {},
        },
    }
