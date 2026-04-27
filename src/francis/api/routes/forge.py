from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query

from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir

router = APIRouter()

_SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_nonnegative_int(value: Any, *, default: int) -> int:
    if isinstance(value, bool) or value is None:
        return default
    if isinstance(value, int):
        return max(0, value)
    if isinstance(value, float):
        return max(0, int(value)) if math.isfinite(value) else default
    text = _safe_str(value).strip()
    if not text:
        return default
    try:
        parsed = float(text)
    except ValueError:
        return default
    return max(0, int(parsed)) if math.isfinite(parsed) else default


def _artifact_root() -> Path:
    return (data_dir() / "artifacts" / "plugins").resolve()


def _collection_dir(collection: str) -> Path:
    return _artifact_root() / collection


def _is_under(root: Path, target: Path) -> bool:
    try:
        target.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _record_id(item: dict[str, Any], collection: str, path: Path) -> str:
    if collection == "proposals":
        return _safe_str(item.get("proposal_id")).strip() or path.stem
    if collection == "promotions":
        return _safe_str(item.get("receipt_id")).strip() or path.stem
    return path.stem


def _record_ts(item: dict[str, Any], collection: str, path: Path) -> int:
    if collection == "proposals":
        fields = ("created_ts", "staged_ts", "updated_ts")
    else:
        fields = ("promoted_ts", "created_ts", "updated_ts")
    for field in fields:
        parsed = _safe_nonnegative_int(item.get(field), default=-1)
        if parsed >= 0:
            return parsed
    try:
        return int(path.stat().st_mtime)
    except OSError:
        return 0


def _read_json_record(path: Path, collection: str) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    redacted = redact_governed_display_value(raw)
    item = redacted if isinstance(redacted, dict) else {}
    item["id"] = _record_id(item, collection, path)
    item["artifact_path"] = redact_secret_text(str(path))
    try:
        item["relative_path"] = redact_secret_text(path.relative_to(_artifact_root()).as_posix())
    except ValueError:
        item["relative_path"] = ""
    return item


def _records(collection: str) -> list[dict[str, Any]]:
    root = _collection_dir(collection)
    if not root.exists() or not root.is_dir():
        return []

    items: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json")):
        if not path.is_file() or not _is_under(root, path):
            continue
        item = _read_json_record(path, collection)
        if item is not None:
            items.append(item)

    items.sort(
        key=lambda item: (
            _record_ts(item, collection, Path(_safe_str(item.get("artifact_path")))),
            _safe_str(item.get("id")),
        ),
        reverse=True,
    )
    return items


def _matches(
    item: dict[str, Any],
    *,
    record_id: str,
    plugin_id: str,
    status: str,
) -> bool:
    if record_id and _safe_str(item.get("id")).strip().lower() != record_id:
        return False
    if plugin_id and _safe_str(item.get("plugin_id")).strip().lower() != plugin_id:
        return False
    if status and _safe_str(item.get("status")).strip().lower() != status:
        return False
    return True


def _list_collection(
    collection: str,
    *,
    limit: int,
    offset: int,
    id: str | None,
    plugin_id: str | None,
    status: str | None,
) -> dict[str, Any]:
    record_filter = _safe_str(id).strip().lower()
    plugin_filter = _safe_str(plugin_id).strip().lower()
    status_filter = _safe_str(status).strip().lower()
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    items = [
        item
        for item in _records(collection)
        if _matches(item, record_id=record_filter, plugin_id=plugin_filter, status=status_filter)
    ]
    page = items[safe_offset : safe_offset + safe_limit]
    return {"items": page, "total": len(items), "offset": safe_offset, "limit": safe_limit}


def _get_collection(collection: str, id: str) -> dict[str, Any]:
    record_id = _safe_str(id).strip()
    if not record_id:
        return {"ok": False, "error": "id_required", "item": None}
    if not _SAFE_RECORD_ID_RE.match(record_id):
        return {"ok": False, "error": "invalid_id", "item": None}

    root = _collection_dir(collection)
    path = root / f"{record_id}.json"
    if not _is_under(root, path):
        return {"ok": False, "error": "invalid_id", "item": None}
    if not path.exists() or not path.is_file():
        return {"ok": False, "error": "not_found", "item": None}
    item = _read_json_record(path, collection)
    if item is None:
        return {"ok": False, "error": "unreadable_record", "item": None}
    return {"ok": True, "item": item}


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ok": True,
        "route": "forge",
        "status": "ready",
        "proposal_count": len(_records("proposals")),
        "promotion_count": len(_records("promotions")),
    }


@router.get("/proposals/list")
def list_proposals(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection("proposals", limit=limit, offset=offset, id=id, plugin_id=plugin_id, status=status)


@router.get("/proposals/get")
def get_proposal(id: str) -> dict[str, Any]:
    return _get_collection("proposals", id)


@router.get("/promotions/list")
def list_promotions(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection("promotions", limit=limit, offset=offset, id=id, plugin_id=plugin_id, status=status)


@router.get("/promotions/get")
def get_promotion(id: str) -> dict[str, Any]:
    return _get_collection("promotions", id)
