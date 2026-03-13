from __future__ import annotations

from typing import Any


def _parse_version(raw: Any) -> tuple[int, int, int]:
    text = str(raw or "").strip()
    if not text:
        return (0, 1, 0)
    parts = text.split(".")
    numbers: list[int] = []
    for part in parts[:3]:
        try:
            numbers.append(max(0, int(part)))
        except Exception:
            numbers.append(0)
    while len(numbers) < 3:
        numbers.append(0)
    return (numbers[0], numbers[1], numbers[2])


def normalize_version(raw: Any) -> str:
    major, minor, patch = _parse_version(raw)
    return f"{major}.{minor}.{patch}"


def next_patch_version(entries: list[dict[str, Any]], slug: str) -> str:
    normalized_slug = str(slug or "").strip()
    versions = [
        _parse_version(entry.get("version"))
        for entry in entries
        if isinstance(entry, dict) and str(entry.get("slug", "")).strip() == normalized_slug
    ]
    if not versions:
        return "0.1.0"
    highest = max(versions)
    return f"{highest[0]}.{highest[1]}.{highest[2] + 1}"


def build_quality_standard(entry: dict[str, Any]) -> dict[str, Any]:
    diff_summary = entry.get("diff_summary", {}) if isinstance(entry.get("diff_summary"), dict) else {}
    validation = entry.get("validation", {}) if isinstance(entry.get("validation"), dict) else {}
    tool_pack = entry.get("tool_pack", {}) if isinstance(entry.get("tool_pack"), dict) else {}
    files = diff_summary.get("files", []) if isinstance(diff_summary.get("files"), list) else []
    file_count = int(diff_summary.get("file_count", 0) or 0)
    legacy_file_metadata = not files and file_count > 0

    has_readme = any(str(item.get("path", "")).strip().lower().endswith("/readme.md") for item in files if isinstance(item, dict)) or legacy_file_metadata
    has_tests = any("/tests/" in str(item.get("path", "")).strip().lower() for item in files if isinstance(item, dict)) or (legacy_file_metadata and file_count >= 2)
    validation_ok = bool(validation.get("ok"))
    tool_pack_skill = str(tool_pack.get("skill_name", "")).strip()

    checks = [
        {
            "kind": "validation",
            "label": "Validation",
            "ok": validation_ok,
            "detail": "Validation passed." if validation_ok else "Validation must pass before promotion.",
            "severity": "low" if validation_ok else "high",
        },
        {
            "kind": "tool_pack",
            "label": "Tool Pack",
            "ok": bool(tool_pack_skill),
            "detail": tool_pack_skill or "A registered tool-pack skill is required.",
            "severity": "low" if tool_pack_skill else "medium",
        },
        {
            "kind": "docs",
            "label": "Docs",
            "ok": has_readme,
            "detail": (
                "README scaffold is present."
                if files and has_readme
                else "Legacy catalog metadata indicates documentation is present."
                if legacy_file_metadata and has_readme
                else "A README is required for durable capability use."
            ),
            "severity": "low" if has_readme else "medium",
        },
        {
            "kind": "tests",
            "label": "Tests",
            "ok": has_tests,
            "detail": (
                "Generated test coverage is present."
                if files and has_tests
                else "Legacy catalog metadata indicates test coverage is present."
                if legacy_file_metadata and has_tests
                else "A test file is required before promotion."
            ),
            "severity": "low" if has_tests else "high",
        },
        {
            "kind": "files",
            "label": "Files",
            "ok": file_count > 0,
            "detail": f"{file_count} file(s) captured in the pack." if file_count > 0 else "Pack has no captured files.",
            "severity": "low" if file_count > 0 else "high",
        },
    ]
    passing = sum(1 for item in checks if bool(item.get("ok")))
    summary = (
        "Quality standards are satisfied."
        if passing == len(checks)
        else f"{len(checks) - passing} quality gate(s) still need attention."
    )
    return {
        "ok": passing == len(checks),
        "score": f"{passing}/{len(checks)}",
        "summary": summary,
        "checks": checks,
    }


def _first_text(*values: Any) -> str:
    for value in values:
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _normalize_review_state(raw: str) -> str:
    normalized = str(raw or "").strip().lower().replace("-", "_")
    if normalized in {"approved", "accepted", "verified", "trusted"}:
        return "approved"
    if normalized in {"rejected", "blocked", "denied"}:
        return "rejected"
    if normalized in {"quarantined", "quarantine"}:
        return "quarantined"
    if normalized in {"revoked", "disabled", "retired"}:
        return "revoked"
    if normalized in {"pending", "requested", "needs_review", "review_required", "unreviewed"}:
        return "review_required"
    return ""


def build_capability_provenance(
    entry: dict[str, Any],
    *,
    approval_status: str = "",
) -> dict[str, Any]:
    provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    status = str(entry.get("status", "")).strip().lower() or "staged"
    imported_bundle_id = _first_text(
        entry.get("imported_from_bundle_id"),
        provenance.get("bundle_id"),
        provenance.get("import_bundle_id"),
    )
    imported_at = _first_text(entry.get("imported_at"), provenance.get("imported_at"))
    explicit_kind = _first_text(
        provenance.get("kind"),
        provenance.get("source_kind"),
        provenance.get("origin_kind"),
        entry.get("source_kind"),
        entry.get("origin_kind"),
    ).strip().lower().replace("-", "_")
    vendor_name = _first_text(
        provenance.get("vendor"),
        provenance.get("vendor_name"),
        provenance.get("provider"),
        provenance.get("publisher"),
        entry.get("vendor"),
        entry.get("vendor_name"),
        entry.get("provider"),
        entry.get("publisher"),
    )
    source_ref = _first_text(
        provenance.get("source_ref"),
        provenance.get("source_url"),
        provenance.get("source"),
        provenance.get("package"),
        provenance.get("registry"),
        provenance.get("path"),
        provenance.get("import_path"),
        entry.get("source_ref"),
        entry.get("source_url"),
        entry.get("source"),
        imported_bundle_id,
    )
    review_state = _normalize_review_state(
        _first_text(
            provenance.get("review_state"),
            provenance.get("review_status"),
            provenance.get("trust_state"),
            entry.get("review_state"),
            entry.get("review_status"),
        )
    )
    normalized_approval_status = str(approval_status or "").strip().lower()
    revoked = bool(entry.get("revoked_at")) or status in {"revoked", "disabled", "retired"}
    quarantined = bool(entry.get("quarantined_at")) or status == "quarantined"

    if quarantined:
        kind = "quarantined"
    elif revoked:
        kind = "revoked"
    elif explicit_kind in {"vendor", "vendor_provided", "official", "first_party_vendor"}:
        kind = "vendor"
    elif explicit_kind in {"third_party", "thirdparty", "external", "community", "dependency"}:
        kind = "third_party"
    elif imported_bundle_id or imported_at or explicit_kind in {"imported", "local_import", "portable"}:
        kind = "local_import"
    elif vendor_name:
        kind = "vendor"
    else:
        kind = "internal"

    if not review_state:
        if kind == "internal":
            review_state = "internal"
        elif kind in {"quarantined", "revoked"}:
            review_state = kind
        elif normalized_approval_status == "approved":
            review_state = "approved"
        elif normalized_approval_status == "rejected":
            review_state = "rejected"
        else:
            review_state = "review_required"

    source_label = (
        "generated inside Francis"
        if kind == "internal"
        else f"portability bundle {imported_bundle_id}"
        if imported_bundle_id
        else vendor_name
        or source_ref
        or "external source"
    )
    traceable = kind == "internal" or bool(imported_bundle_id or vendor_name or source_ref)
    external = kind in {"local_import", "vendor", "third_party"}
    review_required = external and review_state != "approved"

    if kind == "quarantined":
        label = "Quarantined"
        tone = "high"
        review_label = "quarantined"
        summary = "Capability is quarantined and cannot be promoted."
        promotion_rule_detail = "Capability is quarantined and must not be promoted."
        promotion_ready = False
    elif kind == "revoked":
        label = "Revoked"
        tone = "high"
        review_label = "revoked"
        summary = "Capability is revoked and remains cataloged only for audit continuity."
        promotion_rule_detail = "Capability is revoked and cannot be promoted."
        promotion_ready = False
    elif kind == "internal":
        label = "Internal"
        tone = "low"
        review_label = "self-governed"
        summary = "Generated inside Francis and governed locally."
        promotion_rule_detail = "Capability is internally generated and traceable."
        promotion_ready = True
    else:
        if kind == "local_import":
            label = "Local Import"
        elif kind == "vendor":
            label = "Vendor Provided"
        else:
            label = "Third-Party"
        if not traceable:
            tone = "high"
            summary = f"{label} capability is missing provenance anchors and cannot be trusted for promotion."
            promotion_rule_detail = "External capability is missing provenance anchors."
            promotion_ready = False
        elif review_state == "approved":
            tone = "medium" if kind == "third_party" else "low"
            summary = f"{label} capability from {source_label} is locally approved and traceable."
            promotion_rule_detail = "External capability is traceable and has local approval."
            promotion_ready = True
        elif review_state == "rejected":
            tone = "high"
            summary = f"{label} capability from {source_label} was rejected during local review."
            promotion_rule_detail = "External capability was rejected during local review."
            promotion_ready = False
        else:
            tone = "high" if kind == "third_party" else "medium"
            summary = f"{label} capability from {source_label} requires explicit local review before promotion."
            promotion_rule_detail = "External capability requires explicit local review before promotion."
            promotion_ready = False
        review_label = "approved" if review_state == "approved" else "rejected" if review_state == "rejected" else "review required"

    items = [
        {"label": "Provenance", "value": label, "tone": tone},
        {"label": "Source", "value": source_label, "tone": "low" if traceable else "high"},
        {"label": "Review", "value": review_label, "tone": "low" if review_state in {"approved", "internal"} else "high" if review_state in {"quarantined", "revoked", "rejected"} else "medium"},
        {"label": "Catalog Status", "value": status, "tone": tone if kind in {"quarantined", "revoked"} else "low" if status == "active" else "medium" if status == "staged" else "medium"},
    ]

    return {
        "kind": kind,
        "label": label,
        "tone": tone,
        "summary": summary,
        "source_label": source_label,
        "source_ref": source_ref or None,
        "vendor_name": vendor_name or None,
        "imported_bundle_id": imported_bundle_id or None,
        "imported_at": imported_at or None,
        "review_state": review_state,
        "review_label": review_label,
        "review_required": review_required,
        "external": external,
        "traceable": traceable,
        "revoked": kind == "revoked",
        "quarantined": kind == "quarantined",
        "promotion_ready": promotion_ready,
        "promotion_rule_detail": promotion_rule_detail,
        "items": items,
    }


def build_promotion_rules(
    entry: dict[str, Any],
    *,
    approval_status: str = "",
) -> dict[str, Any]:
    quality = build_quality_standard(entry)
    status = str(entry.get("status", "")).strip().lower() or "staged"
    normalized_approval_status = str(approval_status or "").strip().lower()
    provenance = build_capability_provenance(entry, approval_status=normalized_approval_status)
    rules = [
        {
            "kind": "staged_only",
            "label": "Staged",
            "ok": status == "staged",
            "detail": "Only staged capability packs can be promoted.",
        },
        {
            "kind": "quality_standard",
            "label": "Quality Standard",
            "ok": bool(quality.get("ok")),
            "detail": str(quality.get("summary", "")).strip() or "Quality standards must pass before promotion.",
        },
        {
            "kind": "approval",
            "label": "Approval",
            "ok": normalized_approval_status == "approved",
            "detail": (
                "Promotion approval is present."
                if normalized_approval_status == "approved"
                else "Promotion approval is required."
            ),
        },
        {
            "kind": "provenance",
            "label": "Provenance",
            "ok": bool(provenance.get("promotion_ready")),
            "detail": str(provenance.get("promotion_rule_detail", "")).strip()
            or "Capability provenance must remain traceable and reviewable.",
        },
    ]
    return {
        "ready": all(bool(rule.get("ok")) for rule in rules),
        "requires_approval": True,
        "approval_status": normalized_approval_status or "not_requested",
        "rules": rules,
    }


def build_capability_library(entries: list[dict[str, Any]]) -> dict[str, Any]:
    packs: dict[str, dict[str, Any]] = {}
    for entry in [row for row in entries if isinstance(row, dict)]:
        slug = str(entry.get("slug", "")).strip() or str(entry.get("id", "")).strip() or "capability"
        name = str(entry.get("name", "Capability pack")).strip() or "Capability pack"
        normalized = {**entry, "pack_id": slug, "version": normalize_version(entry.get("version"))}
        pack = packs.setdefault(
            slug,
            {
                "pack_id": slug,
                "name": name,
                "entries": [],
            },
        )
        pack["entries"].append(normalized)

    rows: list[dict[str, Any]] = []
    for pack in packs.values():
        versions = sorted(
            [row for row in pack.get("entries", []) if isinstance(row, dict)],
            key=lambda row: (_parse_version(row.get("version")), str(row.get("created_at", "")), str(row.get("id", ""))),
            reverse=True,
        )
        staged = [row for row in versions if str(row.get("status", "")).strip().lower() == "staged"]
        active = [row for row in versions if str(row.get("status", "")).strip().lower() == "active"]
        superseded = [row for row in versions if str(row.get("status", "")).strip().lower() == "superseded"]
        focus_version = (staged[0] if staged else active[0] if active else versions[0] if versions else None)
        rows.append(
            {
                "pack_id": str(pack.get("pack_id", "")).strip(),
                "name": str(pack.get("name", "Capability pack")).strip() or "Capability pack",
                "version_count": len(versions),
                "staged_count": len(staged),
                "active_count": len(active),
                "superseded_count": len(superseded),
                "latest_version": versions[0].get("version") if versions else None,
                "active_version": active[0].get("version") if active else None,
                "focus_version": focus_version,
                "versions": [
                    {
                        "id": str(row.get("id", "")).strip(),
                        "version": str(row.get("version", "")).strip(),
                        "status": str(row.get("status", "")).strip().lower() or "staged",
                        "risk_tier": str(row.get("risk_tier", "low")).strip().lower() or "low",
                        "promoted_at": row.get("promoted_at"),
                    }
                    for row in versions
                ],
            }
        )

    rows.sort(
        key=lambda row: (
            int(row.get("staged_count", 0) or 0) > 0,
            _parse_version(row.get("latest_version")),
            str(row.get("name", "")),
        ),
        reverse=True,
    )
    return {
        "pack_count": len(rows),
        "packs": rows,
        "staged_pack_count": sum(1 for row in rows if int(row.get("staged_count", 0) or 0) > 0),
        "active_pack_count": sum(1 for row in rows if int(row.get("active_count", 0) or 0) > 0),
    }
