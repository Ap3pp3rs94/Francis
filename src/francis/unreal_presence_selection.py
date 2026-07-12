from __future__ import annotations

import hashlib
import json
import os
import re
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


UNREAL_PRESENCE_SELECTION_KIND = "francis.grounded_presence.unreal_selection"
UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION = "francis.grounded_presence.unreal_selection.v1"
UNREAL_PRESENCE_SELECTION_SCHEMA_PATH = "schemas/grounded_presence_unreal_selection.schema.json"
UNREAL_PRESENCE_SELECTION_PATH_ENV = "FRANCIS_UNREAL_PRESENCE_SELECTION_PATH"
UNREAL_PRESENCE_ENGINE_NAME = "Unreal Engine"
UNREAL_PRESENCE_ENGINE_VERSION = "5.8"
UNREAL_PRESENCE_SELECTION_MAX_BYTES = 64 * 1024
UNREAL_DESCRIPTOR_MAX_BYTES = 1024 * 1024

_CONTRACT_ID = re.compile(r"^[A-Za-z0-9._-]{1,160}$")
_SELECTION_ID = re.compile(r"^gpu_[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_AUTHORITY = {
    "francis_core_authoritative": True,
    "grants_execution_authority": False,
    "grants_desktop_authority": False,
    "grants_network_authority": False,
    "grants_memory_write_authority": False,
    "grants_approval_authority": False,
}


def build_unreal_presence_selection(
    *,
    engine_root: str | Path,
    project_path: str | Path,
    technology_stack: Sequence[Mapping[str, Any]],
    confirmed_at: str | datetime | None = None,
) -> dict[str, Any]:
    """Build an in-memory selection only from explicit operator-supplied inputs."""

    resolved_engine = _resolve_local_path(engine_root, expected="directory")
    resolved_project = _resolve_local_path(project_path, expected="file", suffix=".uproject")
    build_path = resolved_engine / "Engine" / "Build" / "Build.version"
    editor_path = resolved_engine / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
    build = _read_json_object(build_path, max_bytes=UNREAL_DESCRIPTOR_MAX_BYTES)
    descriptor = _read_json_object(resolved_project, max_bytes=UNREAL_DESCRIPTOR_MAX_BYTES)
    _validate_engine_evidence(build, editor_path=editor_path)
    _validate_project_evidence(descriptor)
    technologies = _normalize_technology_stack(technology_stack)
    timestamp = _timestamp(confirmed_at)

    payload: dict[str, Any] = {
        "kind": UNREAL_PRESENCE_SELECTION_KIND,
        "schema_version": UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION,
        "schema_path": UNREAL_PRESENCE_SELECTION_SCHEMA_PATH,
        "confirmed_at": timestamp,
        "confirmation": {
            "actor": "operator",
            "project_selected": True,
            "technology_stack_selected": True,
        },
        "engine": {
            "name": UNREAL_PRESENCE_ENGINE_NAME,
            "version": UNREAL_PRESENCE_ENGINE_VERSION,
            "root_path": str(resolved_engine),
            "build_changelist": _required_positive_int(build.get("Changelist"), "engine_build_changelist_invalid"),
            "build_version_sha256": _file_sha256(build_path),
        },
        "project": {
            "path": str(resolved_project),
            "descriptor_sha256": _file_sha256(resolved_project),
        },
        "technology_stack": technologies,
        "authority": dict(_AUTHORITY),
    }
    payload["selection_id"] = _selection_id_for(payload)
    return payload


def validate_unreal_presence_selection(payload: Mapping[str, Any]) -> tuple[str, ...]:
    reasons: list[str] = []
    expected_keys = {
        "kind",
        "schema_version",
        "schema_path",
        "selection_id",
        "confirmed_at",
        "confirmation",
        "engine",
        "project",
        "technology_stack",
        "authority",
    }
    if set(payload) != expected_keys:
        reasons.append("selection_fields_invalid")
    if payload.get("kind") != UNREAL_PRESENCE_SELECTION_KIND:
        reasons.append("selection_kind_invalid")
    if payload.get("schema_version") != UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION:
        reasons.append("selection_schema_version_invalid")
    if payload.get("schema_path") != UNREAL_PRESENCE_SELECTION_SCHEMA_PATH:
        reasons.append("selection_schema_path_invalid")
    selection_id = str(payload.get("selection_id") or "")
    if not _SELECTION_ID.fullmatch(selection_id):
        reasons.append("selection_id_invalid")
    if _parse_timestamp(payload.get("confirmed_at")) is None:
        reasons.append("selection_confirmed_at_invalid")

    confirmation = payload.get("confirmation")
    if confirmation != {
        "actor": "operator",
        "project_selected": True,
        "technology_stack_selected": True,
    }:
        reasons.append("selection_confirmation_invalid")

    engine = _mapping(payload.get("engine"))
    if set(engine) != {"name", "version", "root_path", "build_changelist", "build_version_sha256"}:
        reasons.append("selection_engine_fields_invalid")
    if engine.get("name") != UNREAL_PRESENCE_ENGINE_NAME or engine.get("version") != UNREAL_PRESENCE_ENGINE_VERSION:
        reasons.append("selection_engine_version_invalid")
    if not _positive_int(engine.get("build_changelist")):
        reasons.append("selection_engine_changelist_invalid")
    if not _SHA256.fullmatch(str(engine.get("build_version_sha256") or "")):
        reasons.append("selection_engine_digest_invalid")

    project = _mapping(payload.get("project"))
    if set(project) != {"path", "descriptor_sha256"}:
        reasons.append("selection_project_fields_invalid")
    if not _SHA256.fullmatch(str(project.get("descriptor_sha256") or "")):
        reasons.append("selection_project_digest_invalid")

    try:
        technologies = _normalize_technology_stack(payload.get("technology_stack"))
    except (TypeError, ValueError) as exc:
        reasons.append(str(exc))
        technologies = []
    if technologies != payload.get("technology_stack"):
        reasons.append("selection_technology_stack_not_canonical")
    if payload.get("authority") != _AUTHORITY:
        reasons.append("selection_authority_invalid")

    if not reasons:
        try:
            engine_root = _resolve_local_path(engine.get("root_path"), expected="directory")
            build_path = engine_root / "Engine" / "Build" / "Build.version"
            editor_path = engine_root / "Engine" / "Binaries" / "Win64" / "UnrealEditor.exe"
            build = _read_json_object(build_path, max_bytes=UNREAL_DESCRIPTOR_MAX_BYTES)
            _validate_engine_evidence(build, editor_path=editor_path)
            if _file_sha256(build_path) != engine["build_version_sha256"]:
                reasons.append("selection_engine_build_drift")
            if build.get("Changelist") != engine["build_changelist"]:
                reasons.append("selection_engine_changelist_drift")

            project_path = _resolve_local_path(project.get("path"), expected="file", suffix=".uproject")
            descriptor = _read_json_object(project_path, max_bytes=UNREAL_DESCRIPTOR_MAX_BYTES)
            _validate_project_evidence(descriptor)
            if _file_sha256(project_path) != project["descriptor_sha256"]:
                reasons.append("selection_project_descriptor_drift")
        except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
            reasons.append(_bounded_reason(exc))

    if not reasons:
        expected_id = _selection_id_for({key: value for key, value in payload.items() if key != "selection_id"})
        if selection_id != expected_id:
            reasons.append("selection_id_digest_mismatch")
    return tuple(dict.fromkeys(reasons))


def unreal_presence_selection_readback(
    *,
    selection_path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    environment = os.environ if environ is None else environ
    configured_path = str(selection_path or environment.get(UNREAL_PRESENCE_SELECTION_PATH_ENV) or "").strip()
    if not configured_path:
        return _selection_readback(
            status="operator_confirmation_required",
            configured=False,
            valid=False,
            selection_path="",
            reasons=("selection_path_not_configured",),
        )

    try:
        manifest_path = _resolve_local_path(configured_path, expected="file", suffix=".json")
        payload = _read_json_object(manifest_path, max_bytes=UNREAL_PRESENCE_SELECTION_MAX_BYTES)
        reasons = validate_unreal_presence_selection(payload)
        if reasons:
            status = "selection_stale" if any(reason.endswith("_drift") for reason in reasons) else "selection_invalid"
            return _selection_readback(
                status=status,
                configured=True,
                valid=False,
                selection_path=str(manifest_path),
                reasons=reasons,
                manifest_sha256=_file_sha256(manifest_path),
            )
        return _selection_readback(
            status="operator_selection_confirmed",
            configured=True,
            valid=True,
            selection_path=str(manifest_path),
            reasons=(),
            manifest_sha256=_file_sha256(manifest_path),
            payload=payload,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return _selection_readback(
            status="selection_invalid",
            configured=True,
            valid=False,
            selection_path=configured_path[:1024],
            reasons=(_bounded_reason(exc),),
        )


def _selection_readback(
    *,
    status: str,
    configured: bool,
    valid: bool,
    selection_path: str,
    reasons: tuple[str, ...],
    manifest_sha256: str = "",
    payload: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    selection = _mapping(payload)
    project_status = "operator_confirmed" if valid else "operator_confirmation_required"
    technology_status = "operator_confirmed" if valid else "operator_confirmation_required"
    return {
        "kind": "francis.grounded_presence.unreal_selection_readback",
        "schema_version": UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION,
        "schema_path": UNREAL_PRESENCE_SELECTION_SCHEMA_PATH,
        "status": status,
        "configured": configured,
        "valid": valid,
        "selection_path": selection_path,
        "manifest_sha256": manifest_sha256,
        "selection_id": str(selection.get("selection_id") or ""),
        "confirmed_at": str(selection.get("confirmed_at") or ""),
        "engine": _mapping(selection.get("engine")) if valid else {},
        "project": _mapping(selection.get("project")) if valid else {},
        "technology_stack": list(selection.get("technology_stack") or []) if valid else [],
        "project_selection_status": project_status,
        "technology_selection_status": technology_status,
        "runtime_configured": False,
        "runtime_observed": False,
        "validation": {"ok": valid, "reasons": list(reasons)},
        "authority": dict(_AUTHORITY),
        "read_only": True,
        "writes_state": False,
        "launches_unreal": False,
    }


def _normalize_technology_stack(value: Any) -> list[dict[str, str]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("selection_technology_stack_invalid")
    if not 1 <= len(value) <= 32:
        raise ValueError("selection_technology_stack_invalid")
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, Mapping) or set(item) != {"id", "role"}:
            raise ValueError("selection_technology_entry_invalid")
        technology_id = str(item.get("id") or "").strip()
        role = str(item.get("role") or "").strip()
        if not _CONTRACT_ID.fullmatch(technology_id) or not _CONTRACT_ID.fullmatch(role):
            raise ValueError("selection_technology_entry_invalid")
        if technology_id in seen:
            raise ValueError("selection_technology_duplicate")
        seen.add(technology_id)
        normalized.append({"id": technology_id, "role": role})
    return normalized


def _validate_engine_evidence(build: Mapping[str, Any], *, editor_path: Path) -> None:
    if build.get("MajorVersion") != 5 or build.get("MinorVersion") != 8:
        raise ValueError("selection_engine_version_not_5_8")
    _required_positive_int(build.get("Changelist"), "selection_engine_changelist_invalid")
    if not editor_path.is_file():
        raise ValueError("selection_unreal_editor_not_found")


def _validate_project_evidence(descriptor: Mapping[str, Any]) -> None:
    if descriptor.get("EngineAssociation") != UNREAL_PRESENCE_ENGINE_VERSION:
        raise ValueError("selection_project_engine_association_not_5_8")


def _resolve_local_path(value: Any, *, expected: str, suffix: str = "") -> Path:
    text = str(value or "").strip()
    candidate = Path(text)
    if not text or not candidate.is_absolute() or text.startswith("\\\\") or text.startswith("//"):
        raise ValueError("selection_path_not_local_absolute")
    resolved = candidate.resolve(strict=True)
    if expected == "file" and not resolved.is_file():
        raise ValueError("selection_file_not_found")
    if expected == "directory" and not resolved.is_dir():
        raise ValueError("selection_directory_not_found")
    if suffix and resolved.suffix.lower() != suffix:
        raise ValueError("selection_path_suffix_invalid")
    return resolved


def _read_json_object(path: Path, *, max_bytes: int) -> dict[str, Any]:
    if path.stat().st_size > max_bytes:
        raise ValueError("selection_json_too_large")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError("selection_json_object_required")
    return payload


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _selection_id_for(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return f"gpu_{hashlib.sha256(canonical).hexdigest()[:32]}"


def _timestamp(value: str | datetime | None) -> str:
    parsed: datetime | None
    if value is None:
        parsed = datetime.now(UTC)
    elif isinstance(value, datetime):
        parsed = value
    else:
        parsed = _parse_timestamp(value)
        if parsed is None:
            raise ValueError("selection_confirmed_at_invalid")
    if parsed is None:
        raise ValueError("selection_confirmed_at_invalid")
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _required_positive_int(value: Any, reason: str) -> int:
    if not _positive_int(value):
        raise ValueError(reason)
    return value


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bounded_reason(exc: BaseException) -> str:
    text = str(exc).strip()
    if _CONTRACT_ID.fullmatch(text):
        return text
    return type(exc).__name__[:80]
