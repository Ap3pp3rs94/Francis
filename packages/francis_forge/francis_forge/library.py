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


def build_promotion_rules(
    entry: dict[str, Any],
    *,
    approval_status: str = "",
) -> dict[str, Any]:
    quality = build_quality_standard(entry)
    status = str(entry.get("status", "")).strip().lower() or "staged"
    normalized_approval_status = str(approval_status or "").strip().lower()
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
