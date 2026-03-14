from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any

from .clock import utc_now_iso
from .workspace_fs import WorkspaceFS

REGISTRY_PATH = "dependencies/registry.json"

_MANIFESTS: tuple[dict[str, str | None], ...] = (
    {
        "ecosystem": "python",
        "package_name": "francis",
        "manifest_path": "pyproject.toml",
        "lockfile_path": None,
    },
    {
        "ecosystem": "node",
        "package_name": "francis-overlay-shell",
        "manifest_path": "package.json",
        "lockfile_path": "package-lock.json",
    },
    {
        "ecosystem": "node",
        "package_name": "francis-orb",
        "manifest_path": "francis-orb/package.json",
        "lockfile_path": "francis-orb/package-lock.json",
    },
)


def _read_registry(fs: WorkspaceFS) -> list[dict[str, Any]]:
    try:
        payload = json.loads(fs.read_text(REGISTRY_PATH))
    except Exception:
        return []
    rows = payload.get("dependencies", []) if isinstance(payload, dict) else []
    return [row for row in rows if isinstance(row, dict)]


def _write_registry(fs: WorkspaceFS, rows: list[dict[str, Any]]) -> None:
    fs.write_text(REGISTRY_PATH, json.dumps({"dependencies": rows}, ensure_ascii=False, indent=2))


def _repo_root(fs: WorkspaceFS) -> Path:
    return fs.roots[0].parent.resolve()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_toml(path: Path) -> dict[str, Any]:
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _parse_python_requirement(requirement: str) -> tuple[str, str]:
    text = str(requirement or "").strip()
    match = re.match(r"^\s*([A-Za-z0-9_.-]+)", text)
    name = match.group(1).lower() if match else text.lower()
    return name, text


def _dependency_id(ecosystem: str, package_name: str, dependency_name: str) -> str:
    return f"{ecosystem}:{package_name}:{dependency_name}".lower()


def _normalize_status(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"declared", "active", "present", "required", "build"}:
        return "declared"
    if normalized in {"quarantine", "quarantined"}:
        return "quarantined"
    if normalized in {"revoke", "revoked", "retired"}:
        return "revoked"
    return normalized or "declared"


def _normalize_entry(entry: dict[str, Any], *, base: dict[str, Any] | None = None) -> dict[str, Any]:
    merged = {**(base or {}), **entry}
    base_provenance = base.get("provenance", {}) if isinstance((base or {}).get("provenance"), dict) else {}
    entry_provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    merged["provenance"] = {**base_provenance, **entry_provenance}
    merged["id"] = str(merged.get("id", "")).strip().lower()
    merged["ecosystem"] = str(merged.get("ecosystem", "")).strip().lower() or "python"
    merged["package_name"] = str(merged.get("package_name", "")).strip() or "unknown"
    merged["name"] = str(merged.get("name", "")).strip() or merged["id"] or "dependency"
    merged["status"] = _normalize_status(merged.get("status"))
    merged["section"] = str(merged.get("section", "")).strip().lower() or "runtime"
    merged["requirement"] = str(merged.get("requirement", "")).strip()
    merged["locked_version"] = str(merged.get("locked_version", "")).strip()
    merged["manifest_path"] = str(merged.get("manifest_path", "")).strip()
    merged["lockfile_path"] = str(merged.get("lockfile_path", "")).strip()
    merged["risk_tier"] = str(merged.get("risk_tier", "medium")).strip().lower() or "medium"
    merged["present_in_manifest"] = bool(merged.get("present_in_manifest", True))
    return merged


def _scan_python_manifest(repo_root: Path, spec: dict[str, str | None]) -> list[dict[str, Any]]:
    manifest_path = repo_root / str(spec["manifest_path"])
    payload = _load_toml(manifest_path)
    project = payload.get("project", {}) if isinstance(payload.get("project"), dict) else {}
    package_name = str(project.get("name", spec["package_name"] or "francis")).strip() or "francis"
    entries: list[dict[str, Any]] = []
    dependencies = project.get("dependencies", [])
    if isinstance(dependencies, list):
        for requirement in dependencies:
            name, requirement_text = _parse_python_requirement(str(requirement))
            entries.append(
                {
                    "id": _dependency_id("python", package_name, name),
                    "name": name,
                    "ecosystem": "python",
                    "package_name": package_name,
                    "status": "declared",
                    "section": "runtime",
                    "requirement": requirement_text,
                    "locked_version": "",
                    "manifest_path": str(spec["manifest_path"]),
                    "lockfile_path": "",
                    "risk_tier": "high",
                    "present_in_manifest": True,
                    "provenance": {
                        "source_kind": "third_party" if not name.startswith("francis") else "internal",
                        "source_ref": str(spec["manifest_path"]),
                        "registry": "python",
                    },
                }
            )
    optional = project.get("optional-dependencies", {})
    if isinstance(optional, dict):
        for group_name, group_entries in optional.items():
            if not isinstance(group_entries, list):
                continue
            for requirement in group_entries:
                name, requirement_text = _parse_python_requirement(str(requirement))
                entries.append(
                    {
                        "id": _dependency_id("python", package_name, name),
                        "name": name,
                        "ecosystem": "python",
                        "package_name": package_name,
                        "status": "declared",
                        "section": "dev",
                        "requirement": requirement_text,
                        "locked_version": "",
                        "manifest_path": str(spec["manifest_path"]),
                        "lockfile_path": "",
                        "risk_tier": "medium",
                        "present_in_manifest": True,
                        "provenance": {
                            "source_kind": "third_party" if not name.startswith("francis") else "internal",
                            "source_ref": str(spec["manifest_path"]),
                            "registry": f"python:{group_name}",
                        },
                    }
                )
    return entries


def _lock_version_map(lock_payload: dict[str, Any]) -> dict[str, str]:
    packages = lock_payload.get("packages", {}) if isinstance(lock_payload.get("packages"), dict) else {}
    versions: dict[str, str] = {}
    for key, row in packages.items():
        if not isinstance(key, str) or not key.startswith("node_modules/") or not isinstance(row, dict):
            continue
        name = key[len("node_modules/") :]
        version = str(row.get("version", "")).strip()
        if name and version:
            versions[name] = version
    return versions


def _scan_node_manifest(repo_root: Path, spec: dict[str, str | None]) -> list[dict[str, Any]]:
    manifest_path = repo_root / str(spec["manifest_path"])
    payload = _load_json(manifest_path)
    package_name = str(payload.get("name", spec["package_name"] or "node-package")).strip() or "node-package"
    lockfile_path = str(spec["lockfile_path"] or "")
    lock_versions = _lock_version_map(_load_json(repo_root / lockfile_path)) if lockfile_path else {}
    entries: list[dict[str, Any]] = []
    for field_name, section, risk_tier in (
        ("dependencies", "runtime", "medium"),
        ("devDependencies", "dev", "low"),
    ):
        rows = payload.get(field_name, {})
        if not isinstance(rows, dict):
            continue
        for dependency_name, requirement in rows.items():
            name = str(dependency_name).strip()
            if not name:
                continue
            entries.append(
                {
                    "id": _dependency_id("node", package_name, name),
                    "name": name,
                    "ecosystem": "node",
                    "package_name": package_name,
                    "status": "declared",
                    "section": section,
                    "requirement": str(requirement).strip(),
                    "locked_version": str(lock_versions.get(name, "")).strip(),
                    "manifest_path": str(spec["manifest_path"]),
                    "lockfile_path": lockfile_path,
                    "risk_tier": risk_tier,
                    "present_in_manifest": True,
                    "provenance": {
                        "source_kind": "third_party" if not name.startswith("francis") else "internal",
                        "source_ref": str(spec["manifest_path"]),
                        "registry": "npm",
                    },
                }
            )
    return entries


def _scanned_entries(repo_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in _MANIFESTS:
        if str(spec["ecosystem"]) == "python":
            rows.extend(_scan_python_manifest(repo_root, spec))
        elif str(spec["ecosystem"]) == "node":
            rows.extend(_scan_node_manifest(repo_root, spec))
    return rows


def list_dependency_entries(fs: WorkspaceFS) -> list[dict[str, Any]]:
    scanned = {
        row["id"]: _normalize_entry(row)
        for row in _scanned_entries(_repo_root(fs))
        if str(row.get("id", "")).strip()
    }
    registry_rows = _read_registry(fs)
    for row in registry_rows:
        dependency_id = str(row.get("id", "")).strip().lower()
        if not dependency_id:
            continue
        scanned[dependency_id] = _normalize_entry(row, base=scanned.get(dependency_id))
    return sorted(
        scanned.values(),
        key=lambda row: (
            str(row.get("ecosystem", "")).lower(),
            str(row.get("package_name", "")).lower(),
            str(row.get("section", "")).lower(),
            str(row.get("name", "")).lower(),
        ),
    )


def build_dependency_provenance(entry: dict[str, Any]) -> dict[str, Any]:
    provenance = entry.get("provenance", {}) if isinstance(entry.get("provenance"), dict) else {}
    status = _normalize_status(entry.get("status"))
    explicit_kind = str(
        provenance.get("kind")
        or provenance.get("source_kind")
        or provenance.get("origin_kind")
        or ""
    ).strip().lower()
    if status == "quarantined":
        kind = "quarantined"
    elif status == "revoked":
        kind = "revoked"
    elif explicit_kind in {"internal", "workspace"}:
        kind = "internal"
    elif explicit_kind in {"vendor", "vendor_provided", "official"}:
        kind = "vendor"
    elif explicit_kind in {"local_import", "local", "imported"}:
        kind = "local_import"
    else:
        kind = "third_party"

    locked_version = str(entry.get("locked_version", "")).strip()
    manifest_path = str(entry.get("manifest_path", "")).strip()
    lockfile_path = str(entry.get("lockfile_path", "")).strip()
    section = str(entry.get("section", "runtime")).strip().lower() or "runtime"
    package_name = str(entry.get("package_name", "")).strip()
    review_state = str(
        provenance.get("review_state")
        or provenance.get("review_status")
        or ("internal" if kind == "internal" else "")
    ).strip().lower()
    traceable = bool(manifest_path and package_name and str(entry.get("name", "")).strip())
    pinned = bool(locked_version)
    review_required = False
    tone = "low"
    review_label = review_state or ("internal" if kind == "internal" else "review required")

    if kind == "quarantined":
        review_required = True
        tone = "high"
        review_label = "quarantined"
        summary = "Dependency is quarantined and should not remain on the governed runtime path."
        rule_detail = "Dependency is quarantined."
    elif kind == "revoked":
        tone = "high"
        review_label = "revoked"
        summary = "Dependency is revoked and remains cataloged only for supply-chain audit continuity."
        rule_detail = "Dependency is revoked."
    elif kind == "internal":
        summary = "Dependency is internal to Francis and remains under workspace governance."
        rule_detail = "Dependency is internal."
    elif not pinned:
        review_required = True
        tone = "high" if section == "runtime" else "medium"
        summary = "Dependency is declared without a locked resolved version."
        rule_detail = "Dependency version pinning is incomplete."
    elif review_state in {"approved", "internal"}:
        summary = "Dependency is traceable, pinned, and approved for governed use."
        rule_detail = "Dependency is traceable and pinned."
    else:
        review_required = True
        tone = "medium"
        summary = "Dependency is traceable and pinned but still awaits explicit governance review."
        rule_detail = "Dependency review is still required."

    label_map = {
        "internal": "Internal",
        "local_import": "Local Import",
        "vendor": "Vendor Provided",
        "third_party": "Third-Party",
        "quarantined": "Quarantined",
        "revoked": "Revoked",
    }
    source_label = lockfile_path or manifest_path or "unknown"
    return {
        "kind": kind,
        "label": label_map.get(kind, "Third-Party"),
        "tone": tone,
        "summary": summary,
        "review_required": review_required,
        "review_state": review_state or ("internal" if kind == "internal" else ""),
        "review_label": review_label,
        "source_label": source_label,
        "source_ref": manifest_path or None,
        "traceable": traceable,
        "pinned": pinned,
        "locked_version": locked_version or None,
        "registry": str(provenance.get("registry") or entry.get("ecosystem", "")).strip() or None,
        "promotion_rule_detail": rule_detail,
        "quarantined": kind == "quarantined",
        "revoked": kind == "revoked",
    }


def build_dependency_library(entries: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [entry for entry in entries if isinstance(entry, dict)]
    statuses = [_normalize_status(row.get("status")) for row in rows]
    runtime_count = sum(1 for row in rows if str(row.get("section", "")).strip().lower() == "runtime")
    dev_count = sum(1 for row in rows if str(row.get("section", "")).strip().lower() == "dev")
    quarantined_count = sum(1 for status in statuses if status == "quarantined")
    revoked_count = sum(1 for status in statuses if status == "revoked")
    provenances = [build_dependency_provenance(row) for row in rows]
    review_required_count = sum(1 for row in provenances if bool(row.get("review_required")))
    pinned_count = sum(1 for row in provenances if bool(row.get("pinned")))
    unpinned_count = sum(1 for row in provenances if not bool(row.get("pinned")))
    return {
        "dependency_count": len(rows),
        "runtime_count": runtime_count,
        "dev_count": dev_count,
        "quarantined_count": quarantined_count,
        "revoked_count": revoked_count,
        "review_required_count": review_required_count,
        "pinned_count": pinned_count,
        "unpinned_count": unpinned_count,
    }


def _upsert_registry_entry(
    fs: WorkspaceFS,
    dependency_id: str,
    *,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    normalized_id = str(dependency_id or "").strip().lower()
    if not normalized_id:
        return None
    current_entries = {row["id"]: row for row in list_dependency_entries(fs) if str(row.get("id", "")).strip()}
    base = current_entries.get(normalized_id)
    if base is None:
        return None
    rows = _read_registry(fs)
    index = next((idx for idx, row in enumerate(rows) if str(row.get("id", "")).strip().lower() == normalized_id), None)
    existing = rows[index] if index is not None else {}
    merged = _normalize_entry({**existing, **patch, "id": normalized_id}, base=base)
    if index is None:
        rows.append(merged)
    else:
        rows[index] = merged
    _write_registry(fs, rows)
    refreshed = {row["id"]: row for row in list_dependency_entries(fs) if str(row.get("id", "")).strip()}
    return refreshed.get(normalized_id)


def quarantine_dependency(fs: WorkspaceFS, dependency_id: str, *, reason: str, actor: str) -> dict[str, Any] | None:
    current = next(
        (row for row in list_dependency_entries(fs) if str(row.get("id", "")).strip().lower() == str(dependency_id).strip().lower()),
        None,
    )
    if current is None:
        return None
    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Dependency quarantined from Lens."
    normalized_actor = str(actor or "").strip() or "dependencies:architect"
    return _upsert_registry_entry(
        fs,
        dependency_id,
        patch={
            "status": "quarantined",
            "previous_status": _normalize_status(current.get("status")),
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


def revoke_dependency(fs: WorkspaceFS, dependency_id: str, *, reason: str, actor: str) -> dict[str, Any] | None:
    current = next(
        (row for row in list_dependency_entries(fs) if str(row.get("id", "")).strip().lower() == str(dependency_id).strip().lower()),
        None,
    )
    if current is None:
        return None
    now = utc_now_iso()
    normalized_reason = str(reason or "").strip() or "Dependency revoked from Lens."
    normalized_actor = str(actor or "").strip() or "dependencies:architect"
    patch: dict[str, Any] = {
        "status": "revoked",
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
    return _upsert_registry_entry(fs, dependency_id, patch=patch)
