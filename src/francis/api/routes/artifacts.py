from __future__ import annotations

import math
import os
from pathlib import Path

from fastapi import APIRouter, Query

from francis.chat.continuity.ledger import tail as continuity_tail
from francis.governance.operation_redaction import redact_operation_text
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

router = APIRouter()

_RECEIPT_ARTIFACT_FIELDS = ("artifact_dir", "handoff_artifact_dir", "current_task_artifact_dir", "artifact_path")
_ORIGIN_RECEIPT_FIELDS = (
    "mission_id",
    "current_task_mission_id",
    "handoff_mission_id",
    "operation_id",
    "task_id",
    "approval_id",
    "trace_id",
    "run_id",
    "artifact_dir",
    "active_stage",
    "handoff_stage",
    "handoff_operation_id",
    "handoff_trace_id",
    "handoff_run_id",
    "handoff_artifact_dir",
    "operation_status",
    "handoff_action",
    "handoff_gate",
    "handoff_approval_id",
    "handoff_approval_status",
    "current_task_source",
    "current_task_gate",
    "current_task_approval_id",
    "current_task_approval_status",
    "current_task_previous_approval_id",
    "current_task_previous_approval_status",
    "current_task_operation_id",
    "current_task_operation_name",
    "current_task_operation_plane",
    "current_task_advance_action",
    "current_task_trace_id",
    "current_task_run_id",
    "current_task_artifact_dir",
    "current_task_next_step",
)
_ORIGIN_RECEIPT_TEXT_FIELDS = ("operation_error", "result_message", "recovery_next_step")
_ORIGIN_RECEIPT_PLAN_TEXT_FIELDS = ("plan_status", "plan_current_step_id", "plan_current_step_title")
_ORIGIN_RECEIPT_PLAN_NUMBER_FIELDS = ("plan_step_count", "plan_checkpoint_count")


def _artifact_root() -> Path:
    return _real_path(data_dir() / "artifacts")


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _display_path(path: Path) -> str:
    return redact_secret_text(str(path))


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_nonnegative_int(value: object) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        if not math.isfinite(value):
            return None
        return max(0, int(value))
    text = _safe_str(value).strip()
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if not math.isfinite(parsed):
        return None
    return max(0, int(parsed))


def _is_under(root: Path, target: Path) -> bool:
    try:
        root_text = os.path.normcase(os.path.realpath(os.fspath(root)))
        target_text = os.path.normcase(os.path.realpath(os.fspath(target)))
        return os.path.commonpath([root_text, target_text]) == root_text
    except (OSError, ValueError):
        return False


def _resolve_artifact_handle(raw: str) -> tuple[Path | None, str]:
    cleaned = raw.strip()
    if not cleaned:
        return None, "artifact_dir_required"
    if any(ch in cleaned for ch in ("\x00", "\n", "\r")):
        return None, "artifact_path_invalid"
    raw_path = Path(cleaned)
    if not raw_path.is_absolute() and any(part == ".." for part in raw_path.parts):
        return None, "artifact_path_invalid"

    root = _artifact_root()
    candidate = cleaned if os.path.isabs(cleaned) else os.path.join(os.fspath(root), cleaned)
    try:
        resolved = _real_path(candidate)
    except OSError:
        return None, "artifact_path_invalid"
    if not _is_under(root, resolved):
        return None, "artifact_outside_data_root"
    return resolved, ""


def _recovery_projection(error: str) -> dict[str, object]:
    if error == "artifact_dir_required":
        return {
            "recovery_hint": "Open a mission or operation receipt with an artifact_dir before inspecting artifacts.",
            "next_step": "select_artifact_handle",
            "retryable": False,
        }
    if error == "artifact_path_invalid":
        return {
            "recovery_hint": "Use a local artifact handle returned by a Francis receipt.",
            "next_step": "use_receipt_artifact_handle",
            "retryable": False,
        }
    if error == "artifact_outside_data_root":
        return {
            "recovery_hint": "Use the artifact_dir handle from the originating Francis receipt; inspection is limited to data/artifacts.",
            "next_step": "inspect_originating_receipt",
            "retryable": False,
        }
    if error == "artifact_not_found":
        return {
            "recovery_hint": "Refresh the mission or operation receipt, then inspect the latest artifact_dir handle.",
            "next_step": "refresh_originating_receipt",
            "retryable": True,
        }
    if error.startswith("artifact_unreadable:"):
        return {
            "recovery_hint": "Check local file permissions for this artifact handle, then retry inspection.",
            "next_step": "check_artifact_permissions",
            "retryable": True,
        }
    return {
        "recovery_hint": "Inspect the originating mission or operation receipt before retrying artifact inspection.",
        "next_step": "inspect_originating_receipt",
        "retryable": False,
    }


def _relative_artifact_path(root: Path, path: Path) -> str:
    try:
        return redact_secret_text(path.relative_to(root).as_posix())
    except ValueError:
        return ""


def _normalized_handle(value: object) -> str:
    text = _safe_str(value).strip()
    if not text:
        return ""
    return text.replace("\\", "/").rstrip("/").lower()


def _artifact_match_handles(root: Path, target: Path, raw: str) -> set[str]:
    handles: set[str] = set()
    for value in (raw, str(target), _display_path(target), _relative_artifact_path(root, target)):
        normalized = _normalized_handle(value)
        if normalized:
            handles.add(normalized)
    return handles


def _receipt_artifact_field(meta: dict[str, object], handles: set[str]) -> str:
    for field in _RECEIPT_ARTIFACT_FIELDS:
        if _normalized_handle(meta.get(field)) in handles:
            return field
    return ""


def _first_projection_text(projection: dict[str, object], *fields: str) -> str:
    for field in fields:
        value = _safe_str(projection.get(field)).strip()
        if value:
            return value
    return ""


def _originating_receipt_projection(root: Path, target: Path, raw: str) -> dict[str, object]:
    handles = _artifact_match_handles(root, target, raw)
    if not handles:
        return {}

    try:
        entries = continuity_tail(limit=1000)
    except Exception:
        return {}

    for item in reversed(entries):
        if not isinstance(item, dict):
            continue
        meta_obj = item.get("meta")
        if not isinstance(meta_obj, dict):
            continue
        meta = {str(key): value for key, value in meta_obj.items()}
        matched_field = _receipt_artifact_field(meta, handles)
        if not matched_field:
            continue
        if _safe_str(meta.get("subsystem")).strip() != "operations.runtime":
            continue
        if _safe_str(meta.get("scope")).strip() != "mission.loop":
            continue

        projection: dict[str, object] = {
            "source": "continuity.ledger",
            "matched_artifact_field": matched_field,
        }
        for field in _ORIGIN_RECEIPT_FIELDS:
            value = redact_secret_text(_safe_str(meta.get(field)).strip())
            if value:
                projection[field] = value
        for field in _ORIGIN_RECEIPT_TEXT_FIELDS:
            value = redact_operation_text(meta.get(field))
            if value:
                projection[field] = value
        for field in _ORIGIN_RECEIPT_PLAN_TEXT_FIELDS:
            value = redact_secret_text(_safe_str(meta.get(field)).strip())
            if value:
                projection[field] = value
        for field in _ORIGIN_RECEIPT_PLAN_NUMBER_FIELDS:
            count_value = _safe_nonnegative_int(meta.get(field))
            if count_value is not None:
                projection[field] = count_value

        reference_values = {
            "mission_id": _first_projection_text(
                projection, "mission_id", "current_task_mission_id", "handoff_mission_id"
            ),
            "operation_id": _first_projection_text(
                projection, "operation_id", "task_id", "current_task_operation_id", "handoff_operation_id"
            ),
            "approval_id": _first_projection_text(
                projection, "approval_id", "current_task_approval_id", "handoff_approval_id"
            ),
            "trace_id": _first_projection_text(projection, "trace_id", "current_task_trace_id", "handoff_trace_id"),
            "run_id": _first_projection_text(projection, "run_id", "current_task_run_id", "handoff_run_id"),
            "artifact_dir": _first_projection_text(
                projection, "artifact_dir", "current_task_artifact_dir", "handoff_artifact_dir"
            ),
        }
        for key, value in reference_values.items():
            if value:
                projection[key] = value
        projection.pop("task_id", None)
        references = {key: value for key, value in reference_values.items() if value}
        if references:
            projection["references"] = references
        return projection
    return {}


def _entry_projection(root: Path, path: Path) -> dict[str, object]:
    resolved = _real_path(path)
    base = {
        "name": redact_secret_text(resolved.name),
        "relative_path": _relative_artifact_path(root, resolved),
    }
    if not _is_under(root, resolved):
        return {**base, "kind": "external_link", "bytes": 0, "modified_ts": None}
    try:
        stat = resolved.stat()
    except OSError:
        return {**base, "kind": "unavailable", "bytes": 0, "modified_ts": None}
    return {
        **base,
        "kind": "directory" if resolved.is_dir() else "file",
        "bytes": stat.st_size if resolved.is_file() else 0,
        "modified_ts": stat.st_mtime,
    }


@router.get("/inspect")
def inspect_artifact(
    artifact_dir: str = Query("", description="Absolute or artifact-root-relative artifact handle."),
    limit: int = Query(50, ge=1, le=200),
) -> dict[str, object]:
    target, error = _resolve_artifact_handle(artifact_dir)
    root = _artifact_root()
    if target is None:
        return {
            "ok": False,
            "error": error,
            "artifact_root": _display_path(root),
            "artifact_dir": redact_secret_text(artifact_dir.strip()),
            **_recovery_projection(error),
        }

    originating_receipt = _originating_receipt_projection(root, target, artifact_dir)
    if not target.exists():
        body = {
            "ok": False,
            "error": "artifact_not_found",
            "artifact_root": _display_path(root),
            "artifact_dir": _display_path(target),
            "relative_path": _relative_artifact_path(root, target),
            "exists": False,
            **_recovery_projection("artifact_not_found"),
        }
        if originating_receipt:
            body["originating_receipt"] = originating_receipt
        return body

    projection = _entry_projection(root, target)
    if target.is_file():
        body = {
            "ok": True,
            "artifact_root": _display_path(root),
            "artifact_dir": _display_path(target),
            "relative_path": _relative_artifact_path(root, target),
            "exists": True,
            "kind": "file",
            "bytes": projection.get("bytes", 0),
            "modified_ts": projection.get("modified_ts"),
            "entries": [],
            "entry_count": 0,
            "truncated": False,
        }
        if originating_receipt:
            body["originating_receipt"] = originating_receipt
        return body

    try:
        children = sorted(target.iterdir(), key=lambda item: item.name.lower())
    except OSError as exc:
        error = f"artifact_unreadable:{type(exc).__name__}"
        body = {
            "ok": False,
            "error": error,
            "artifact_root": _display_path(root),
            "artifact_dir": _display_path(target),
            "relative_path": _relative_artifact_path(root, target),
            "exists": True,
            **_recovery_projection(error),
        }
        if originating_receipt:
            body["originating_receipt"] = originating_receipt
        return body

    entries = [_entry_projection(root, child) for child in children[:limit]]
    body = {
        "ok": True,
        "artifact_root": _display_path(root),
        "artifact_dir": _display_path(target),
        "relative_path": _relative_artifact_path(root, target),
        "exists": True,
        "kind": "directory",
        "entries": entries,
        "entry_count": len(children),
        "truncated": len(children) > limit,
    }
    if originating_receipt:
        body["originating_receipt"] = originating_receipt
    return body
