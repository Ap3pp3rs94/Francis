from __future__ import annotations

from francis.api.errors import api_error_message
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.kernel.paths import data_dir

router = APIRouter()
_FEDERATION_WRITE_SCOPE = "federation.write"

_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _federation_write_actor(payload: dict[str, Any]) -> str:
    return (
        _safe_str(payload.get("request_actor")).strip()
        or _safe_str(payload.get("api_actor")).strip()
        or _safe_str(payload.get("actor")).strip()
        or "api.federation"
    )


def _federation_write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_FEDERATION_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_writing_federation",
            "evidence": decision.evidence,
        },
    }


def _write_permission_denial(payload: dict[str, Any], request: Request) -> dict[str, object] | None:
    decision = _federation_write_permission(
        _federation_write_actor(payload),
        route=request.url.path,
        method=request.method,
    )
    if decision.allowed:
        return None
    return _permission_denied(decision)


def _now_s() -> int:
    return int(time.time())


def _slug(value: str) -> str:
    out = []
    last_sep = False
    for ch in value.strip().lower():
        if ch.isalnum():
            out.append(ch)
            last_sep = False
            continue
        if ch in {" ", "-", "_", ".", ":"} and not last_sep:
            out.append("-")
            last_sep = True
    slug = "".join(out).strip("-")
    return slug[:64] or "item"


def _new_id(prefix: str, seed: str) -> str:
    return f"{prefix}_{_slug(seed)}_{uuid.uuid4().hex[:8]}"


def _to_bool(value: Any, *, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, (int, float)):
        return bool(value)
    text = _safe_str(value).strip().lower()
    if text in {"1", "true", "t", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "f", "no", "n", "off"}:
        return False
    return default


def _parse_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [part.strip() for part in value.split(",")]
    elif isinstance(value, list):
        candidates = [_safe_str(item).strip() for item in value]
    else:
        return []

    out: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in out:
            out.append(candidate)
    return out


def _meta(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _validate_id(value: str, field: str = "id") -> str:
    text = value.strip()
    if not text:
        raise ValueError(f"{field} is required")
    if not _ID_RE.match(text):
        raise ValueError(f"invalid {field}")
    return text


def _federation_path() -> Path:
    return data_dir() / "federation" / "_registry.json"


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {
        "version": 1,
        "updated_at": _now_s(),
        "instances": {},
        "delegations": [],
        "consensus_logs": [],
        "shared_knowledge": [],
    }


def _normalize_instance(instance_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    first_seen_ts = int(raw.get("first_seen_ts") or _now_s())
    last_seen_ts = int(raw.get("last_seen_ts") or first_seen_ts)
    trust_level_raw = raw.get("trust_level")
    trust_level = float(trust_level_raw) if isinstance(trust_level_raw, (int, float)) else 0.0
    return {
        "id": instance_id,
        "name": _safe_str(raw.get("name")).strip() or instance_id,
        "status": _safe_str(raw.get("status")).strip() or "unknown",
        "endpoint": _safe_str(raw.get("endpoint")).strip(),
        "region": _safe_str(raw.get("region")).strip(),
        "role": _safe_str(raw.get("role")).strip(),
        "first_seen_ts": first_seen_ts,
        "last_seen_ts": last_seen_ts,
        "capabilities": _parse_list(raw.get("capabilities")),
        "trust_level": trust_level,
        "requires_approval": _to_bool(raw.get("requires_approval"), default=False),
        "tags": _parse_list(raw.get("tags")),
        "health": _meta(raw.get("health")),
        "inventory": _meta(raw.get("inventory")),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_delegation(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("deleg", _safe_str(raw.get("scope")).strip() or "scope"),
        "ts": int(raw.get("ts") or _now_s()),
        "from": _safe_str(raw.get("from")).strip() or _safe_str(raw.get("from_instance_id")).strip(),
        "to": _safe_str(raw.get("to")).strip() or _safe_str(raw.get("to_instance_id")).strip(),
        "scope": _safe_str(raw.get("scope")).strip() or _safe_str(raw.get("scope_id")).strip(),
        "status": _safe_str(raw.get("status")).strip() or "pending",
        "reason": _safe_str(raw.get("reason")).strip(),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_consensus_log(raw: dict[str, Any]) -> dict[str, Any]:
    term_raw = raw.get("term")
    index_raw = raw.get("index")
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("clog", _safe_str(raw.get("kind")).strip() or "entry"),
        "ts": int(raw.get("ts") or _now_s()),
        "level": _safe_str(raw.get("level")).strip() or "info",
        "kind": _safe_str(raw.get("kind")).strip(),
        "instance_id": _safe_str(raw.get("instance_id")).strip(),
        "term": int(term_raw) if isinstance(term_raw, (int, float)) else None,
        "index": int(index_raw) if isinstance(index_raw, (int, float)) else None,
        "message": _safe_str(raw.get("message")).strip(),
        "meta": _meta(raw.get("meta")),
    }


def _normalize_shared_knowledge(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": _safe_str(raw.get("id")).strip() or _new_id("know", _safe_str(raw.get("title")).strip() or "knowledge"),
        "ts": int(raw.get("ts") or _now_s()),
        "kind": _safe_str(raw.get("kind")).strip() or "fact",
        "title": _safe_str(raw.get("title")).strip() or _safe_str(raw.get("name")).strip(),
        "source_instance_id": _safe_str(raw.get("source_instance_id")).strip() or _safe_str(raw.get("source")).strip(),
        "domain": _safe_str(raw.get("domain")).strip(),
        "tags": _parse_list(raw.get("tags")),
        "meta": _meta(raw.get("meta")),
    }


def _load_registry() -> dict[str, Any]:
    path = _federation_path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()

    out = _default_registry()
    out["version"] = int(raw.get("version") or 1)
    out["updated_at"] = int(raw.get("updated_at") or _now_s())

    instances_raw = raw.get("instances")
    if isinstance(instances_raw, dict):
        instances: dict[str, dict[str, Any]] = {}
        for instance_id, item in instances_raw.items():
            normalized_id = _safe_str(instance_id).strip()
            if not normalized_id or not isinstance(item, dict):
                continue
            instances[normalized_id] = _normalize_instance(normalized_id, item)
        out["instances"] = instances

    for key, normalizer, max_items in (
        ("delegations", _normalize_delegation, 20_000),
        ("consensus_logs", _normalize_consensus_log, 50_000),
        ("shared_knowledge", _normalize_shared_knowledge, 20_000),
    ):
        raw_list = raw.get(key)
        if isinstance(raw_list, list):
            out[key] = [normalizer(item) for item in raw_list if isinstance(item, dict)][-max_items:]

    return out


def _save_registry(registry: dict[str, Any]) -> None:
    normalized = _load_registry()
    if isinstance(registry.get("instances"), dict):
        normalized_instances: dict[str, dict[str, Any]] = {}
        for instance_id, item in registry["instances"].items():
            key = _safe_str(instance_id).strip()
            if key and isinstance(item, dict):
                normalized_instances[key] = _normalize_instance(key, item)
        normalized["instances"] = normalized_instances

    for key, normalizer, max_items in (
        ("delegations", _normalize_delegation, 20_000),
        ("consensus_logs", _normalize_consensus_log, 50_000),
        ("shared_knowledge", _normalize_shared_knowledge, 20_000),
    ):
        if isinstance(registry.get(key), list):
            normalized[key] = [normalizer(item) for item in registry[key] if isinstance(item, dict)][-max_items:]

    normalized["version"] = int(registry.get("version") or normalized.get("version") or 1)
    normalized["updated_at"] = _now_s()
    _atomic_write(_federation_path(), normalized)


def _paginate(items: list[dict[str, Any]], limit: int, offset: int) -> tuple[list[dict[str, Any]], int, int, int]:
    safe_limit = max(1, min(int(limit), 5000))
    safe_offset = max(0, int(offset))
    total = len(items)
    return items[safe_offset : safe_offset + safe_limit], total, safe_limit, safe_offset


def _list_instances(
    registry: dict[str, Any],
    *,
    status: str | None,
    limit: int,
    offset: int,
    tags: list[str],
) -> dict[str, Any]:
    status_filter = _safe_str(status).strip().lower()
    tag_filter = set(_parse_list(tags))
    instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}

    items: list[dict[str, Any]] = []
    for instance_id, raw in instances_obj.items():
        if not isinstance(raw, dict):
            continue
        item = _normalize_instance(_safe_str(instance_id), raw)
        if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
            continue
        if tag_filter and not tag_filter.issubset(set(_parse_list(item.get("tags")))):
            continue
        items.append(item)

    items.sort(key=lambda item: (int(item.get("last_seen_ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(items, limit, offset)
    return {"items": page, "instances": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_delegations(registry: dict[str, Any], *, status: str | None, limit: int, offset: int) -> dict[str, Any]:
    status_filter = _safe_str(status).strip().lower()
    entries = registry.get("delegations") if isinstance(registry.get("delegations"), list) else []
    items = [_normalize_delegation(item) for item in entries if isinstance(item, dict)]
    if status_filter:
        items = [item for item in items if _safe_str(item.get("status")).strip().lower() == status_filter]
    items.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(items, limit, offset)
    return {"items": page, "delegations": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_consensus_logs(
    registry: dict[str, Any],
    *,
    level: str | None,
    instance_id: str | None,
    start_ts: int | None,
    end_ts: int | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    level_filter = _safe_str(level).strip().lower()
    instance_filter = _safe_str(instance_id).strip()
    entries = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
    items = [_normalize_consensus_log(item) for item in entries if isinstance(item, dict)]

    out: list[dict[str, Any]] = []
    for item in items:
        if level_filter and _safe_str(item.get("level")).strip().lower() != level_filter:
            continue
        if instance_filter and _safe_str(item.get("instance_id")).strip() != instance_filter:
            continue
        ts = int(item.get("ts") or 0)
        if start_ts is not None and ts < int(start_ts):
            continue
        if end_ts is not None and ts > int(end_ts):
            continue
        out.append(item)

    out.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(out, limit, offset)
    return {"items": page, "logs": page, "total": total, "limit": safe_limit, "offset": safe_offset}


def _list_shared_knowledge(
    registry: dict[str, Any],
    *,
    kind: str | None,
    domain: str | None,
    limit: int,
    offset: int,
    tags: list[str],
) -> dict[str, Any]:
    kind_filter = _safe_str(kind).strip().lower()
    domain_filter = _safe_str(domain).strip().lower()
    tag_filter = set(_parse_list(tags))
    entries = registry.get("shared_knowledge") if isinstance(registry.get("shared_knowledge"), list) else []
    items = [_normalize_shared_knowledge(item) for item in entries if isinstance(item, dict)]

    out: list[dict[str, Any]] = []
    for item in items:
        if kind_filter and _safe_str(item.get("kind")).strip().lower() != kind_filter:
            continue
        if domain_filter and _safe_str(item.get("domain")).strip().lower() != domain_filter:
            continue
        if tag_filter and not tag_filter.issubset(set(_parse_list(item.get("tags")))):
            continue
        out.append(item)

    out.sort(key=lambda item: (int(item.get("ts") or 0), _safe_str(item.get("id"))), reverse=True)
    page, total, safe_limit, safe_offset = _paginate(out, limit, offset)
    return {"items": page, "knowledge": page, "total": total, "limit": safe_limit, "offset": safe_offset}


@router.get("/status")
def status() -> dict[str, Any]:
    try:
        registry = _load_registry()
        instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}
        instances = [
            _normalize_instance(_safe_str(instance_id), item)
            for instance_id, item in instances_obj.items()
            if isinstance(item, dict)
        ]
        online = len([i for i in instances if _safe_str(i.get("status")).strip().lower() == "online"])
        degraded = len([i for i in instances if _safe_str(i.get("status")).strip().lower() == "degraded"])
        return {
            "ok": True,
            "route": "federation",
            "status": "ready",
            "ts": _now_s(),
            "counts": {
                "instances": len(instances),
                "online": online,
                "degraded": degraded,
                "delegations": len(registry.get("delegations") or []),
                "consensus_logs": len(registry.get("consensus_logs") or []),
                "shared_knowledge": len(registry.get("shared_knowledge") or []),
            },
        }
    except Exception as exc:
        return {"ok": False, "route": "federation", "status": "error", "error": api_error_message(exc)}


@router.get("/health")
def health() -> dict[str, Any]:
    body = status()
    body["route"] = "federation.health"
    return body


@router.get("/instances/list")
def list_instances(
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
    tags: str | None = None,
) -> dict[str, Any]:
    try:
        registry = _load_registry()
        return _list_instances(registry, status=status, limit=limit, offset=offset, tags=_parse_list(tags))
    except Exception as exc:
        return {"items": [], "instances": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/instances/get")
def get_instance(id: str) -> dict[str, Any]:
    try:
        instance_id = _validate_id(id, "instance id")
        registry = _load_registry()
        instances_obj = registry.get("instances") if isinstance(registry.get("instances"), dict) else {}
        raw = instances_obj.get(instance_id)
        if not isinstance(raw, dict):
            return {"ok": False, "error": "not_found"}
        full = _normalize_instance(instance_id, raw)
        item = {k: v for k, v in full.items() if k not in {"health", "inventory"}}
        return {"ok": True, "item": item, "health": full.get("health") or {}, "inventory": full.get("inventory") or {}}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.get("/delegations/list")
def list_delegations(
    status: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        return _list_delegations(_load_registry(), status=status, limit=limit, offset=offset)
    except Exception as exc:
        return {"items": [], "delegations": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/consensus_logs/list")
def list_consensus_logs(
    level: str | None = None,
    instance_id: str | None = None,
    start_ts: int | None = None,
    end_ts: int | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    try:
        return _list_consensus_logs(
            _load_registry(),
            level=level,
            instance_id=instance_id,
            start_ts=start_ts,
            end_ts=end_ts,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        return {"items": [], "logs": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.get("/shared_knowledge/list")
def list_shared_knowledge(
    kind: str | None = None,
    domain: str | None = None,
    limit: int = 200,
    offset: int = 0,
    tags: str | None = None,
) -> dict[str, Any]:
    try:
        return _list_shared_knowledge(
            _load_registry(), kind=kind, domain=domain, limit=limit, offset=offset, tags=_parse_list(tags)
        )
    except Exception as exc:
        return {"items": [], "knowledge": [], "total": 0, "limit": 0, "offset": 0, "error": api_error_message(exc)}


@router.post("/instances/upsert")
def upsert_instance(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        requested_id = _safe_str(payload.get("id")).strip()
        name = _safe_str(payload.get("name")).strip()
        if not requested_id and not name:
            return {"ok": False, "error": "id_or_name_required"}

        instance_id = requested_id or _new_id("inst", name)
        instance_id = _validate_id(instance_id, "instance id")

        registry = _load_registry()
        instances_obj = registry.get("instances")
        if not isinstance(instances_obj, dict):
            instances_obj = {}
            registry["instances"] = instances_obj

        existing = instances_obj.get(instance_id) if isinstance(instances_obj.get(instance_id), dict) else {}
        now_s = _now_s()
        first_seen_ts = int(existing.get("first_seen_ts") or payload.get("first_seen_ts") or now_s)

        merged = {
            **existing,
            "id": instance_id,
            "name": name or _safe_str(existing.get("name")).strip() or instance_id,
            "status": _safe_str(payload.get("status")).strip()
            or _safe_str(existing.get("status")).strip()
            or "unknown",
            "endpoint": _safe_str(payload.get("endpoint")).strip() or _safe_str(existing.get("endpoint")).strip(),
            "region": _safe_str(payload.get("region")).strip() or _safe_str(existing.get("region")).strip(),
            "role": _safe_str(payload.get("role")).strip() or _safe_str(existing.get("role")).strip(),
            "first_seen_ts": first_seen_ts,
            "last_seen_ts": int(payload.get("last_seen_ts") or now_s),
            "capabilities": _parse_list(
                payload.get("capabilities") if "capabilities" in payload else existing.get("capabilities")
            ),
            "trust_level": payload.get("trust_level")
            if isinstance(payload.get("trust_level"), (int, float))
            else existing.get("trust_level", 0),
            "requires_approval": _to_bool(
                payload.get("requires_approval"), default=_to_bool(existing.get("requires_approval"), default=False)
            ),
            "tags": _parse_list(payload.get("tags") if "tags" in payload else existing.get("tags")),
            "health": _meta(payload.get("health") if "health" in payload else existing.get("health")),
            "inventory": _meta(payload.get("inventory") if "inventory" in payload else existing.get("inventory")),
            "meta": {**_meta(existing.get("meta")), **_meta(payload.get("meta"))},
        }
        item = _normalize_instance(instance_id, merged)
        instances_obj[instance_id] = item

        _append = {
            "ts": now_s,
            "level": "info",
            "kind": "instance_upsert",
            "instance_id": instance_id,
            "message": f"Federation instance upserted: {instance_id}",
            "meta": {"status": item.get("status")},
        }
        logs = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
        logs.append(_normalize_consensus_log(_append))
        registry["consensus_logs"] = logs

        _save_registry(registry)
        return {"ok": True, "id": instance_id, "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/delegations/record")
def record_delegation(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        scope = _safe_str(payload.get("scope")).strip() or _safe_str(payload.get("scope_id")).strip()
        if not scope:
            return {"ok": False, "error": "scope_required"}

        registry = _load_registry()
        delegations = registry.get("delegations") if isinstance(registry.get("delegations"), list) else []
        item = _normalize_delegation(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "from": payload.get("from") or payload.get("from_instance_id"),
                "to": payload.get("to") or payload.get("to_instance_id"),
                "scope": scope,
                "status": payload.get("status") or "pending",
                "reason": payload.get("reason"),
                "meta": payload.get("meta"),
            }
        )
        delegations.append(item)
        registry["delegations"] = delegations
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/consensus_logs/append")
def append_consensus_log(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        message = _safe_str(payload.get("message")).strip() or _safe_str(payload.get("msg")).strip()
        if not message:
            return {"ok": False, "error": "message_required"}

        registry = _load_registry()
        logs = registry.get("consensus_logs") if isinstance(registry.get("consensus_logs"), list) else []
        item = _normalize_consensus_log(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "level": payload.get("level") or "info",
                "kind": payload.get("kind"),
                "instance_id": payload.get("instance_id"),
                "term": payload.get("term"),
                "index": payload.get("index"),
                "message": message,
                "meta": payload.get("meta"),
            }
        )
        logs.append(item)
        registry["consensus_logs"] = logs
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


@router.post("/shared_knowledge/publish")
def publish_shared_knowledge(payload: dict[str, Any], request: Request) -> dict[str, Any]:
    try:
        if denial := _write_permission_denial(payload, request):
            return denial

        title = _safe_str(payload.get("title")).strip() or _safe_str(payload.get("name")).strip()
        if not title and not _safe_str(payload.get("id")).strip():
            return {"ok": False, "error": "title_or_id_required"}

        registry = _load_registry()
        knowledge = registry.get("shared_knowledge") if isinstance(registry.get("shared_knowledge"), list) else []
        item = _normalize_shared_knowledge(
            {
                "id": payload.get("id"),
                "ts": payload.get("ts") or _now_s(),
                "kind": payload.get("kind") or "fact",
                "title": title,
                "source_instance_id": payload.get("source_instance_id") or payload.get("source"),
                "domain": payload.get("domain"),
                "tags": payload.get("tags"),
                "meta": payload.get("meta"),
            }
        )
        knowledge.append(item)
        registry["shared_knowledge"] = knowledge
        _save_registry(registry)
        return {"ok": True, "id": item.get("id"), "item": item}
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}
