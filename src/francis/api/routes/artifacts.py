from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Query

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

router = APIRouter()


def _artifact_root() -> Path:
    return (data_dir() / "artifacts").resolve()


def _display_path(path: Path) -> str:
    return redact_secret_text(str(path))


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

    if not target.exists():
        return {
            "ok": False,
            "error": "artifact_not_found",
            "artifact_root": _display_path(root),
            "artifact_dir": _display_path(target),
            "relative_path": _relative_artifact_path(root, target),
            "exists": False,
            **_recovery_projection("artifact_not_found"),
        }

    projection = _entry_projection(root, target)
    if target.is_file():
        return {
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

    try:
        children = sorted(target.iterdir(), key=lambda item: item.name.lower())
    except OSError as exc:
        error = f"artifact_unreadable:{type(exc).__name__}"
        return {
            "ok": False,
            "error": error,
            "artifact_root": _display_path(root),
            "artifact_dir": _display_path(target),
            "relative_path": _relative_artifact_path(root, target),
            "exists": True,
            **_recovery_projection(error),
        }

    entries = [_entry_projection(root, child) for child in children[:limit]]
    return {
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
