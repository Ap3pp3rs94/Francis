from __future__ import annotations

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


def _artifact_root() -> Path:
    return (data_dir() / "artifacts").resolve()


def _display_path(path: Path) -> str:
    return redact_secret_text(str(path))


def _safe_str(value: object) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _is_under(root: Path, target: Path) -> bool:
    try:
        return target.resolve(strict=False).is_relative_to(root)
    except OSError:
        return False


def _resolve_artifact_handle(raw: str) -> tuple[Path | None, str]:
    cleaned = raw.strip()
    if not cleaned:
        return None, "artifact_dir_required"

    root = _artifact_root()
    candidate = Path(cleaned).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = candidate.resolve(strict=False)
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

        operation_id = _safe_str(projection.get("operation_id") or projection.get("task_id")).strip()
        if operation_id:
            projection["operation_id"] = operation_id
        projection.pop("task_id", None)
        references = {
            key: projection[key]
            for key in ("mission_id", "operation_id", "approval_id", "trace_id", "run_id", "artifact_dir")
            if _safe_str(projection.get(key)).strip()
        }
        if references:
            projection["references"] = references
        return projection
    return {}


def _entry_projection(root: Path, path: Path) -> dict[str, object]:
    resolved = path.resolve(strict=False)
    base = {
        "name": redact_secret_text(path.name),
        "relative_path": _relative_artifact_path(root, resolved),
    }
    if not _is_under(root, resolved):
        return {**base, "kind": "external_link", "bytes": 0, "modified_ts": None}
    try:
        stat = path.stat()
    except OSError:
        return {**base, "kind": "unavailable", "bytes": 0, "modified_ts": None}
    return {
        **base,
        "kind": "directory" if path.is_dir() else "file",
        "bytes": stat.st_size if path.is_file() else 0,
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
