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

from francis.forge import analyze_proposal_quality, summarize_proposal_quality
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir, repo_root

router = APIRouter()

_SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_COLLECTIONS = {"proposals", "validations", "promotions", "proposal_reviews"}
_FORGE_WRITE_SCOPE = "plugins.write"
_RISK_ORDER = {"readonly": 0, "normal": 1, "critical": 2, "safety_critical": 3}
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


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _safe_record_id(value: Any) -> str:
    record_id = _safe_str(value).strip()
    return record_id if _SAFE_RECORD_ID_RE.match(record_id) else ""


def _atomic_write_json(path: Path, obj: dict[str, Any], *, collection: str) -> bool:
    resolved_path = _collection_path(collection, path)
    if resolved_path is None:
        return False
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = resolved_path.with_suffix(resolved_path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, resolved_path)
    return True


def _artifact_root() -> Path:
    return _real_path(data_dir() / "artifacts" / "plugins")


def _collection_dir(collection: str) -> Path:
    if collection not in _COLLECTIONS:
        raise ValueError("invalid collection")
    return _real_path(_artifact_root() / collection)


def _registry_path() -> Path:
    return data_dir() / "plugins" / "_registry.json"


def _is_under(root: Path, target: Path) -> bool:
    try:
        _real_path(target).relative_to(_real_path(root))
        return True
    except Exception:
        return False


def _collection_path(collection: str, path: str | Path) -> Path | None:
    try:
        root = _collection_dir(collection)
        resolved = _real_path(path)
    except Exception:
        return None
    if not _is_under(root, resolved):
        return None
    if resolved.suffix != ".json" or not _safe_record_id(resolved.stem):
        return None
    return resolved


def _collection_record_path(collection: str, record_id: str) -> Path | None:
    safe_id = _safe_record_id(record_id)
    if not safe_id:
        return None
    try:
        root = _collection_dir(collection)
    except ValueError:
        return None
    return _collection_path(collection, root / f"{safe_id}.json")


def _resolve_generated_plugin_dir(plugin_id: str, generated_dir: str = "") -> Path | None:
    text = _safe_str(generated_dir).strip() or plugin_id
    if not text or any(ch in text for ch in ("\x00", "\n", "\r")):
        return None
    root = _real_path(repo_root() / "plugins" / "generated")
    candidate = Path(text).expanduser()
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = _real_path(candidate)
    return resolved if _is_under(root, resolved) else None


def _record_id(item: dict[str, Any], collection: str, path: Path) -> str:
    candidates: tuple[Any, ...]
    if collection == "proposals":
        candidates = (item.get("proposal_id"), path.stem)
    elif collection == "validations":
        candidates = (item.get("validation_id"), path.stem)
    elif collection in {"promotions", "proposal_reviews"}:
        candidates = (item.get("receipt_id"), path.stem)
    else:
        candidates = (path.stem,)
    for candidate in candidates:
        safe_id = _safe_record_id(candidate)
        if safe_id:
            return safe_id
    return ""


def _record_ts(item: dict[str, Any], collection: str, path: Path) -> int:
    if collection == "proposals":
        fields = ("created_ts", "staged_ts", "updated_ts")
    elif collection == "validations":
        fields = ("validated_ts", "created_ts", "updated_ts")
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
    resolved_path = _collection_path(collection, path)
    if resolved_path is None:
        return None
    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    redacted = redact_governed_display_value(raw)
    item = redacted if isinstance(redacted, dict) else {}
    item["id"] = _record_id(item, collection, resolved_path)
    if not item["id"]:
        return None
    item["artifact_path"] = redact_secret_text(str(resolved_path))
    try:
        item["relative_path"] = redact_secret_text(resolved_path.relative_to(_artifact_root()).as_posix())
    except ValueError:
        item["relative_path"] = ""
    if collection == "proposals":
        item["quality_analysis"] = _proposal_quality_analysis(item)
    return item


def _proposal_quality_analysis(item: dict[str, Any]) -> dict[str, Any]:
    analysis = analyze_proposal_quality(item)
    redacted = redact_governed_display_value(analysis)
    return redacted if isinstance(redacted, dict) else {}


def _read_raw_record(path: Path, collection: str) -> dict[str, Any] | None:
    resolved_path = _collection_path(collection, path)
    if resolved_path is None:
        return None
    try:
        raw = json.loads(resolved_path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _has_readiness_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_readiness_value(item) for item in value)
    if isinstance(value, tuple | set):
        return any(_has_readiness_value(item) for item in value)
    if isinstance(value, dict):
        return any(_has_readiness_value(item) for item in value.values())
    return value is not None


def _registry_plugins() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists() or not path.is_file():
        return {}
    try:
        registry = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}
    if not isinstance(registry, dict):
        return {}
    plugins = registry.get("plugins")
    return plugins if isinstance(plugins, dict) else {}


def _read_proposal(proposal_id: str) -> dict[str, Any]:
    resolved_id = _safe_record_id(proposal_id)
    if not resolved_id:
        return {}
    path = _collection_record_path("proposals", resolved_id)
    if path is None or not path.exists() or not path.is_file():
        return {}
    proposal = _read_raw_record(path, "proposals")
    return proposal if isinstance(proposal, dict) else {}


def _proposal_review_state(proposal: dict[str, Any]) -> dict[str, Any]:
    if not proposal:
        return {"status": "missing", "receipt_id": "", "approved": False}
    review_raw = proposal.get("review")
    review: dict[str, Any] = review_raw if isinstance(review_raw, dict) else {}
    proposal_status = _safe_str(proposal.get("status")).strip().lower() or "unknown"
    review_status = _safe_str(review.get("status")).strip().lower() or proposal_status
    receipt_id = _safe_str(proposal.get("review_receipt_id") or review.get("receipt_id")).strip()
    return {
        "status": review_status,
        "receipt_id": receipt_id,
        "approved": proposal_status == "approved" and review_status == "approved" and bool(receipt_id),
    }


def _promotion_readiness_for_plugin(plugin_id: str, plugin: dict[str, Any]) -> dict[str, Any]:
    meta_raw = plugin.get("meta")
    meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
    proposal_id = _safe_str(meta.get("proposal_id") or meta.get("forge_proposal_id")).strip()
    proposal = _read_proposal(proposal_id)
    friction_raw = proposal.get("friction")
    friction: dict[str, Any] = friction_raw if isinstance(friction_raw, dict) else {}
    quality_raw = proposal.get("quality_requirements")
    quality: dict[str, Any] = quality_raw if isinstance(quality_raw, dict) else {}
    validation_raw = proposal.get("validation")
    validation: dict[str, Any] = validation_raw if isinstance(validation_raw, dict) else {}
    review = _proposal_review_state(proposal)

    evidence = meta.get("proposal_evidence") or meta.get("evidence") or friction.get("evidence") or []
    tests = meta.get("tests") or meta.get("test_refs") or quality.get("tests") or []
    docs = meta.get("docs") or meta.get("documentation") or quality.get("docs") or []
    generated_dir = _safe_str(plugin.get("generated_dir")).strip()
    generated_plugin_dir = _resolve_generated_plugin_dir(plugin_id, generated_dir)
    readme_path = generated_plugin_dir / "README.md" if generated_plugin_dir is not None else None
    if not _has_readiness_value(docs) and readme_path is not None and readme_path.exists():
        docs = [str(readme_path.resolve())]
    risk_tier = _safe_str(meta.get("risk_tier") or quality.get("risk_tier")).strip().lower()

    requirements = {
        "proposal_id": bool(proposal_id),
        "proposal_review": bool(review["approved"]),
        "proposal_evidence": _has_readiness_value(evidence),
        "tests": _has_readiness_value(tests),
        "docs": _has_readiness_value(docs),
        "risk_tier": risk_tier in _RISK_ORDER,
    }
    missing = [key for key, present in requirements.items() if not present]
    item = {
        "kind": "plugin.promotion.readiness",
        "plugin_id": plugin_id,
        "proposal_id": proposal_id,
        "ready": not missing,
        "status": "ready" if not missing else "blocked",
        "missing_requirements": missing,
        "requirements": requirements,
        "plugin": {
            "id": plugin_id,
            "name": _safe_str(plugin.get("name")).strip() or plugin_id,
            "status": _safe_str(plugin.get("status")).strip() or "unknown",
            "enabled": bool(plugin.get("enabled", False)),
            "source_kind": _safe_str(plugin.get("source_kind")).strip() or "unknown",
        },
        "evidence": {
            "proposal_review_status": review["status"],
            "proposal_review_receipt_id": review["receipt_id"],
            "proposal_evidence": evidence,
            "tests": tests,
            "docs": docs,
            "risk_tier": risk_tier,
            "validation_receipt_id": _safe_str(
                meta.get("validation_receipt_id") or validation.get("validation_receipt_id")
            ).strip(),
            "validation_receipt_path": _safe_str(
                meta.get("validation_receipt_path") or validation.get("validation_receipt_path")
            ).strip(),
        },
        "governance": {
            "gate": "forge_promotion_readiness",
            "scope": _FORGE_WRITE_SCOPE,
            "inspection_route": "/forge/promotion_readiness/list",
            "promotion_route": "/plugins/enable",
            "promotion_authority": False,
            "execution_authority": False,
            "next_step": (
                "explicit_enable_with_plugins_write_scope"
                if not missing
                else "satisfy_missing_requirements_before_promotion"
            ),
        },
    }
    redacted = redact_governed_display_value(item)
    return redacted if isinstance(redacted, dict) else {}


def _promotion_readiness_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for raw_plugin_id, raw in _registry_plugins().items():
        if not isinstance(raw, dict):
            continue
        plugin_id = _safe_str(raw.get("id")).strip() or _safe_str(raw_plugin_id).strip()
        if not plugin_id:
            continue
        if _safe_str(raw.get("status")).strip().lower() != "staged":
            continue
        items.append(_promotion_readiness_for_plugin(plugin_id, raw))
    items.sort(key=lambda item: (_safe_str(item.get("status")), _safe_str(item.get("plugin_id"))))
    return items


def _records(collection: str) -> list[dict[str, Any]]:
    root = _collection_dir(collection)
    if not root.exists() or not root.is_dir():
        return []

    items: list[tuple[dict[str, Any], int]] = []
    for path in sorted(root.glob("*.json")):
        resolved_path = _collection_path(collection, path)
        if resolved_path is None or not resolved_path.is_file():
            continue
        item = _read_json_record(resolved_path, collection)
        if item is not None:
            items.append((item, _record_ts(item, collection, resolved_path)))

    items.sort(
        key=lambda entry: (
            entry[1],
            _safe_str(entry[0].get("id")),
        ),
        reverse=True,
    )
    return [item for item, _ts in items]


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
    raw_record_id = _safe_str(id).strip()
    if not raw_record_id:
        return {"ok": False, "error": "id_required", "item": None}
    record_id = _safe_record_id(raw_record_id)
    if not record_id:
        return {"ok": False, "error": "invalid_id", "item": None}

    path = _collection_record_path(collection, record_id)
    if path is None:
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
    proposals = _records("proposals")
    readiness_items = _promotion_readiness_items()
    return {
        "ok": True,
        "route": "forge",
        "status": "ready",
        "proposal_count": len(proposals),
        "proposal_quality_summary": summarize_proposal_quality(proposals),
        "validation_count": len(_records("validations")),
        "proposal_review_count": len(_records("proposal_reviews")),
        "promotion_count": len(_records("promotions")),
        "promotion_candidate_count": len(readiness_items),
        "promotion_ready_count": sum(1 for item in readiness_items if bool(item.get("ready"))),
        "promotion_blocked_count": sum(1 for item in readiness_items if not bool(item.get("ready"))),
    }


@router.get("/promotion_readiness/list")
def list_promotion_readiness(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    plugin_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    plugin_filter = _safe_str(plugin_id).strip().lower()
    proposal_filter = _safe_str(proposal_id).strip().lower()
    status_filter = _safe_str(status).strip().lower()
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    items = [
        item
        for item in _promotion_readiness_items()
        if (not plugin_filter or _safe_str(item.get("plugin_id")).strip().lower() == plugin_filter)
        and (not proposal_filter or _safe_str(item.get("proposal_id")).strip().lower() == proposal_filter)
        and (not status_filter or _safe_str(item.get("status")).strip().lower() == status_filter)
    ]
    page = items[safe_offset : safe_offset + safe_limit]
    return {"items": page, "total": len(items), "offset": safe_offset, "limit": safe_limit}


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


@router.get("/validations/list")
def list_validations(
    limit: int = Query(200, ge=1, le=5000),
    offset: int = Query(0, ge=0),
    id: str | None = None,
    plugin_id: str | None = None,
    proposal_id: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    return _list_collection(
        "validations",
        limit=limit,
        offset=offset,
        id=id,
        plugin_id=plugin_id,
        proposal_id=proposal_id,
        status=status,
    )


@router.get("/validations/get")
def get_validation(id: str) -> dict[str, Any]:
    return _get_collection("validations", id)


@router.post("/proposals/decision")
def decide_proposal(payload: ProposalDecisionIn, request: Request) -> dict[str, Any]:
    permission = _write_permission(payload.actor, route=request.url.path, method=request.method)
    if not permission.allowed:
        return _permission_denied(permission)

    raw_proposal_id = _safe_str(payload.id).strip()
    if not raw_proposal_id:
        return {"ok": False, "applied": False, "error": "id_required", "item": None}
    proposal_id = _safe_record_id(raw_proposal_id)
    if not proposal_id:
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

    proposal_path = _collection_record_path("proposals", proposal_id)
    if proposal_path is None:
        return {"ok": False, "applied": False, "error": "invalid_id", "item": None}
    if not proposal_path.exists() or not proposal_path.is_file():
        return {"ok": False, "applied": False, "error": "not_found", "item": None}

    proposal = _read_raw_record(proposal_path, "proposals")
    if proposal is None:
        return {"ok": False, "applied": False, "error": "unreadable_record", "item": None}

    previous_status = _safe_str(proposal.get("status")).strip() or "unknown"
    decided_ts = _now_s()
    receipt_id = _proposal_receipt_id(proposal_id, decided_ts)
    receipt_path = _collection_record_path("proposal_reviews", receipt_id)
    if receipt_path is None:
        return {"ok": False, "applied": False, "error": "invalid_receipt_id", "item": None}
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
    if not _atomic_write_json(receipt_path, receipt_out, collection="proposal_reviews"):
        return {"ok": False, "applied": False, "error": "invalid_receipt_path", "item": None}
    if not _atomic_write_json(proposal_path, proposal_out, collection="proposals"):
        return {"ok": False, "applied": False, "error": "invalid_id", "item": None}
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
