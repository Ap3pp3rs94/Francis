from __future__ import annotations

import hashlib
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Query, Request
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir

router = APIRouter()

_SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_FORGE_WRITE_SCOPE = "plugins.write"
_PROPOSAL_DECISIONS = {
    "approve": "approved",
    "approved": "approved",
    "reject": "rejected",
    "rejected": "rejected",
    "request_changes": "needs_revision",
    "needs_revision": "needs_revision",
}


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


def _now_s() -> int:
    return int(time.time())


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


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
    if collection == "proposal_reviews":
        return _safe_str(item.get("receipt_id")).strip() or path.stem
    return path.stem


def _record_ts(item: dict[str, Any], collection: str, path: Path) -> int:
    if collection == "proposals":
        fields = ("created_ts", "staged_ts", "updated_ts")
    elif collection == "proposal_reviews":
        fields = ("decided_ts", "created_ts", "updated_ts")
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


def _read_raw_record(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


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
    proposal_id: str,
    status: str,
) -> bool:
    if record_id and _safe_str(item.get("id")).strip().lower() != record_id:
        return False
    if plugin_id and _safe_str(item.get("plugin_id")).strip().lower() != plugin_id:
        return False
    if proposal_id and _safe_str(item.get("proposal_id")).strip().lower() != proposal_id:
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
    proposal_id: str | None,
    status: str | None,
) -> dict[str, Any]:
    record_filter = _safe_str(id).strip().lower()
    plugin_filter = _safe_str(plugin_id).strip().lower()
    proposal_filter = _safe_str(proposal_id).strip().lower()
    status_filter = _safe_str(status).strip().lower()
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    items = [
        item
        for item in _records(collection)
        if _matches(
            item,
            record_id=record_filter,
            plugin_id=plugin_filter,
            proposal_id=proposal_filter,
            status=status_filter,
        )
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


def _write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_FORGE_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "applied": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "scope": _FORGE_WRITE_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_mutating_forge_proposals",
            "evidence": decision.evidence,
        },
    }


def _proposal_receipt_id(proposal_id: str, decided_ts: int) -> str:
    digest = hashlib.sha256(_safe_str(proposal_id).strip().encode("utf-8")).hexdigest()[:12]
    nonce = time.time_ns() % 1_000_000
    return f"plugin_proposal_review_{decided_ts}_{digest}_{nonce:06d}"


class ProposalDecisionIn(BaseModel):
    id: str
    action: str
    actor: str = ""
    reason: str = "requested"
    notes: str = ""
    meta: dict[str, Any] = Field(default_factory=dict)


@router.get("/status")
def status() -> dict[str, Any]:
    return {
        "ok": True,
        "route": "forge",
        "status": "ready",
        "proposal_count": len(_records("proposals")),
        "proposal_review_count": len(_records("proposal_reviews")),
        "promotion_count": len(_records("promotions")),
    }


@router.get("/proposals/list")
def list_proposals(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection(
        "proposals",
        limit=limit,
        offset=offset,
        id=id,
        plugin_id=plugin_id,
        proposal_id=proposal_id,
        status=status,
    )


@router.get("/proposals/get")
def get_proposal(id: str) -> dict[str, Any]:
    return _get_collection("proposals", id)


@router.post("/proposals/decision")
def decide_proposal(payload: ProposalDecisionIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)

    proposal_id = _safe_str(payload.id).strip()
    if not proposal_id:
        return {"ok": False, "applied": False, "error": "id_required", "item": None}
    if not _SAFE_RECORD_ID_RE.match(proposal_id):
        return {"ok": False, "applied": False, "error": "invalid_id", "item": None}

    action = _safe_str(payload.action).strip().lower()
    decided_status = _PROPOSAL_DECISIONS.get(action)
    if decided_status is None:
        return {
            "ok": False,
            "applied": False,
            "error": "invalid_decision",
            "allowed_actions": sorted(_PROPOSAL_DECISIONS),
            "item": None,
        }

    proposal_root = _collection_dir("proposals")
    proposal_path = proposal_root / f"{proposal_id}.json"
    if not _is_under(proposal_root, proposal_path):
        return {"ok": False, "applied": False, "error": "invalid_id", "item": None}
    if not proposal_path.exists() or not proposal_path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": None}

    proposal = _read_raw_record(proposal_path)
    if proposal is None:
        return {"ok": False, "applied": False, "error": "unreadable_record", "item": None}

    previous_status = _safe_str(proposal.get("status")).strip() or "unknown"
    decided_ts = _now_s()
    receipt_id = _proposal_receipt_id(proposal_id, decided_ts)
    receipt_path = _collection_dir("proposal_reviews") / f"{receipt_id}.json"
    receipt = {
        "kind": "plugin.proposal.review.receipt",
        "receipt_id": receipt_id,
        "proposal_id": proposal_id,
        "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
        "previous_status": previous_status,
        "status": decided_status,
        "decision": action,
        "decided_ts": decided_ts,
        "actor": _safe_str(payload.actor).strip(),
        "reason": _safe_str(payload.reason).strip() or "requested",
        "notes": _safe_str(payload.notes).strip(),
        "meta": payload.meta if isinstance(payload.meta, dict) else {},
        "proposal_path": str(proposal_path),
        "governance": {
            "gate": "permission_gate",
            "scope": _FORGE_WRITE_SCOPE,
            "route": "/forge/proposals/decision",
            "promotion_authority": False,
            "execution_authority": False,
        },
        "path": str(receipt_path),
    }
    redacted_receipt = redact_governed_display_value(receipt)
    receipt_out = redacted_receipt if isinstance(redacted_receipt, dict) else {}

    history = proposal.get("review_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "receipt_id": receipt_id,
            "status": decided_status,
            "decision": action,
            "decided_ts": decided_ts,
            "actor": receipt_out.get("actor", ""),
        }
    )
    proposal["status"] = decided_status
    proposal["updated_ts"] = decided_ts
    proposal["review_receipt_id"] = receipt_id
    proposal["review_receipt_path"] = str(receipt_path)
    proposal["review"] = {
        "status": decided_status,
        "decision": action,
        "reason": receipt_out.get("reason", ""),
        "notes": receipt_out.get("notes", ""),
        "actor": receipt_out.get("actor", ""),
        "decided_ts": decided_ts,
        "receipt_id": receipt_id,
    }
    proposal["review_history"] = history

    redacted_proposal = redact_governed_display_value(proposal)
    proposal_out = redacted_proposal if isinstance(redacted_proposal, dict) else {}
    _atomic_write_json(receipt_path, receipt_out)
    _atomic_write_json(proposal_path, proposal_out)
    item = _read_json_record(proposal_path, "proposals") or proposal_out

    return {
        "ok": True,
        "applied": True,
        "status": decided_status,
        "proposal_id": proposal_id,
        "plugin_id": _safe_str(proposal.get("plugin_id")).strip(),
        "review_receipt_id": receipt_id,
        "review_receipt": receipt_out,
        "item": item,
        "governance": {
            "gate": "forge_proposal_review",
            "promotion_authority": False,
            "execution_authority": False,
            "next_step": "review_staged_output_before_explicit_promotion",
        },
    }


@router.get("/proposal_reviews/list")
def list_proposal_reviews(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection(
        "proposal_reviews",
        limit=limit,
        offset=offset,
        id=id,
        plugin_id=plugin_id,
        proposal_id=proposal_id,
        status=status,
    )


@router.get("/proposal_reviews/get")
def get_proposal_review(id: str) -> dict[str, Any]:
    return _get_collection("proposal_reviews", id)


@router.get("/promotions/list")
def list_promotions(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection(
        "promotions",
        limit=limit,
        offset=offset,
        id=id,
        plugin_id=plugin_id,
        proposal_id=proposal_id,
        status=status,
    )


@router.get("/promotions/get")
def get_promotion(id: str) -> dict[str, Any]:
    return _get_collection("promotions", id)
