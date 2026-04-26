from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.kernel.paths import data_dir

router = APIRouter()

_DOMAIN_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")
_DEFAULT_STATUS = "active"
_ALLOWED_STATUSES = {"active", "archived", "disabled", "error"}
_DOMAIN_WRITE_SCOPE = "domains.write"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _slugify(value: str) -> str:
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
    return slug[:64] or "domain"


def _domains_registry_path() -> Path:
    return data_dir() / "domains" / "_registry.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_s(), "domains": {}}


def _load_registry() -> dict[str, Any]:
    path = _domains_registry_path()
    if not path.exists():
        return _default_registry()

    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()

    domains = raw.get("domains")
    if isinstance(domains, dict):
        return {
            "version": int(raw.get("version") or 1),
            "updated_at": int(raw.get("updated_at") or _now_s()),
            "domains": domains,
        }

    # Backward compatibility for legacy "{}" layout where top-level keys were domains.
    legacy_domains = {k: v for k, v in raw.items() if isinstance(v, dict)}
    if legacy_domains:
        return {"version": 1, "updated_at": _now_s(), "domains": legacy_domains}
    return _default_registry()


def _save_registry(registry: dict[str, Any]) -> None:
    domains = registry.get("domains")
    if not isinstance(domains, dict):
        domains = {}
    normalized: dict[str, Any] = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "domains": domains,
    }
    _atomic_write_json(_domains_registry_path(), normalized)


def _validate_domain_id(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("domain_id is required")
    if not _DOMAIN_ID_RE.match(text):
        raise ValueError("invalid domain_id")
    return text


def _coerce_status(value: Any) -> str:
    status = _safe_str(value).strip().lower()
    if not status:
        return _DEFAULT_STATUS
    return status if status in _ALLOWED_STATUSES else status


def _parse_tags(value: Any) -> list[str]:
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


def _normalize_domain_record(domain_id: str, record: dict[str, Any]) -> dict[str, Any]:
    created_ts = int(record.get("created_ts") or _now_s())
    updated_ts = int(record.get("updated_ts") or created_ts)
    tags = _parse_tags(record.get("tags"))
    meta = dict(record.get("meta") or {}) if isinstance(record.get("meta"), dict) else {}

    out = {
        "id": domain_id,
        "name": _safe_str(record.get("name")).strip() or domain_id,
        "status": _coerce_status(record.get("status")),
        "created_ts": created_ts,
        "updated_ts": updated_ts,
        "created_at": _safe_str(record.get("created_at")).strip()
        or datetime.fromtimestamp(created_ts, tz=UTC).isoformat(),
        "updated_at": _safe_str(record.get("updated_at")).strip()
        or datetime.fromtimestamp(updated_ts, tz=UTC).isoformat(),
        "risk": _safe_str(record.get("risk")).strip() or "",
        "requires_approval": bool(record.get("requires_approval", False)),
        "tags": tags,
        "meta": meta,
    }
    return out


def _read_domain(registry: dict[str, Any], domain_id: str) -> dict[str, Any] | None:
    domains = registry.get("domains")
    if not isinstance(domains, dict):
        return None
    raw = domains.get(domain_id)
    if not isinstance(raw, dict):
        return None
    return _normalize_domain_record(domain_id, raw)


def _write_domain(registry: dict[str, Any], domain: dict[str, Any]) -> None:
    domains = registry.get("domains")
    if not isinstance(domains, dict):
        domains = {}
        registry["domains"] = domains
    domains[domain["id"]] = domain


def _delete_domain(registry: dict[str, Any], domain_id: str) -> bool:
    domains = registry.get("domains")
    if not isinstance(domains, dict):
        return False
    if domain_id in domains:
        del domains[domain_id]
        return True
    return False


def _summarize_domain(domain: dict[str, Any]) -> dict[str, Any]:
    meta = domain.get("meta")
    meta_obj = meta if isinstance(meta, dict) else {}
    trust_level = meta_obj.get("trust_level")
    if not isinstance(trust_level, (int, float)):
        trust_level = 0

    memory_items = meta_obj.get("memory_items")
    if not isinstance(memory_items, int):
        memory_items = 0

    plugin_count = meta_obj.get("plugin_count")
    if not isinstance(plugin_count, int):
        plugin_count = 0

    return {
        "domain_id": domain["id"],
        "trust_level": trust_level,
        "memory_items": memory_items,
        "plugin_count": plugin_count,
        "meta": {
            "status": domain.get("status"),
            "risk": domain.get("risk"),
            "updated_ts": domain.get("updated_ts"),
        },
    }


class DomainCreateIn(BaseModel):
    id: str | None = None
    name: str
    description: str = ""
    tags: list[str] = Field(default_factory=list)
    reason: str = "requested"
    meta: dict[str, Any] = Field(default_factory=dict)
    actor: str | None = None


class DomainUpdateIn(BaseModel):
    domain_id: str
    updates: dict[str, Any] = Field(default_factory=dict)
    reason: str = "requested"
    actor: str | None = None


class DomainDeleteIn(BaseModel):
    domain_id: str
    reason: str = "requested"
    actor: str | None = None


def _write_permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_DOMAIN_WRITE_SCOPE],
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
            "next_step": "configure_actor_scope_or_use_read_only_domain_routes",
            "evidence": decision.evidence,
        },
    }


@router.get("/status")
def status() -> dict[str, object]:
    try:
        registry = _load_registry()
        domains = registry.get("domains") if isinstance(registry.get("domains"), dict) else {}
        return {
            "ok": True,
            "route": "domains",
            "status": "ready",
            "total": len(domains),
        }
    except Exception as exc:
        return {"ok": False, "route": "domains", "status": "error", "error": str(exc)}


@router.get("/list")
def list_domains(
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    tags: str | None = None,
) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        status_filter = _safe_str(status).strip().lower()
        tag_filter = _parse_tags(tags)

        registry = _load_registry()
        domains_obj = registry.get("domains")
        if not isinstance(domains_obj, dict):
            domains_obj = {}

        items: list[dict[str, Any]] = []
        for domain_id, raw in domains_obj.items():
            if not isinstance(raw, dict):
                continue
            item = _normalize_domain_record(_safe_str(domain_id), raw)
            if status_filter and _safe_str(item.get("status")).lower() != status_filter:
                continue
            if tag_filter:
                current_tags = set(_parse_tags(item.get("tags")))
                if not set(tag_filter).issubset(current_tags):
                    continue
            items.append(item)

        items.sort(key=lambda item: (int(item.get("updated_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        total = len(items)
        page = items[safe_offset : safe_offset + safe_limit]
        return {"items": page, "domains": page, "total": total, "offset": safe_offset, "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "domains": [], "total": 0, "offset": 0, "limit": 0, "error": str(exc)}


@router.get("/get")
def get_domain(domain_id: str) -> dict[str, object]:
    try:
        normalized_id = _validate_domain_id(domain_id)
        registry = _load_registry()
        item = _read_domain(registry, normalized_id)
        if item is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "item": item}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/create")
def create_domain(payload: DomainCreateIn) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route="/domains/create", method="POST")
        if not permission.allowed:
            return _permission_denied(permission)

        name = _safe_str(payload.name).strip()
        if not name:
            return {"ok": False, "error": "name_required"}

        requested_id = _safe_str(payload.id).strip() if payload.id else ""
        domain_id = requested_id or _slugify(name)
        try:
            domain_id = _validate_domain_id(domain_id)
        except Exception:
            domain_id = _validate_domain_id(_slugify(domain_id))

        registry = _load_registry()
        existing = _read_domain(registry, domain_id)
        if existing is not None:
            return {"ok": False, "error": "already_exists", "id": domain_id, "domain_id": domain_id}

        now_s = _now_s()
        record = _normalize_domain_record(
            domain_id,
            {
                "name": name,
                "status": _DEFAULT_STATUS,
                "created_ts": now_s,
                "updated_ts": now_s,
                "created_at": _utc_now_iso(),
                "updated_at": _utc_now_iso(),
                "tags": payload.tags,
                "risk": "",
                "requires_approval": False,
                "meta": {
                    **dict(payload.meta or {}),
                    "description": _safe_str(payload.description).strip(),
                    "reason": _safe_str(payload.reason).strip(),
                },
            },
        )
        _write_domain(registry, record)
        _save_registry(registry)
        return {
            "ok": True,
            "id": domain_id,
            "domain_id": domain_id,
            "status": record.get("status", _DEFAULT_STATUS),
            "item": record,
            "message": "created",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.patch("/update")
def update_domain(payload: DomainUpdateIn) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route="/domains/update", method="PATCH")
        if not permission.allowed:
            return _permission_denied(permission)

        domain_id = _validate_domain_id(payload.domain_id)
        registry = _load_registry()
        current = _read_domain(registry, domain_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": domain_id, "domain_id": domain_id}

        updates = payload.updates if isinstance(payload.updates, dict) else {}
        if "name" in updates:
            name = _safe_str(updates.get("name")).strip()
            if name:
                current["name"] = name

        if "status" in updates:
            current["status"] = _coerce_status(updates.get("status"))

        if "tags" in updates:
            current["tags"] = _parse_tags(updates.get("tags"))

        if "meta" in updates and isinstance(updates.get("meta"), dict):
            merged_meta = dict(current.get("meta") or {}) if isinstance(current.get("meta"), dict) else {}
            merged_meta.update(updates.get("meta"))
            current["meta"] = merged_meta

        current["updated_ts"] = _now_s()
        current["updated_at"] = _utc_now_iso()
        _write_domain(registry, _normalize_domain_record(domain_id, current))
        _save_registry(registry)

        return {
            "ok": True,
            "id": domain_id,
            "domain_id": domain_id,
            "status": current.get("status", _DEFAULT_STATUS),
            "item": current,
            "message": "updated",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/delete")
def delete_domain(payload: DomainDeleteIn) -> dict[str, object]:
    try:
        permission = _write_permission(payload.actor, route="/domains/delete", method="POST")
        if not permission.allowed:
            return _permission_denied(permission)

        domain_id = _validate_domain_id(payload.domain_id)
        registry = _load_registry()
        removed = _delete_domain(registry, domain_id)
        if not removed:
            return {"ok": False, "error": "not_found", "id": domain_id, "domain_id": domain_id}
        _save_registry(registry)
        return {
            "ok": True,
            "id": domain_id,
            "domain_id": domain_id,
            "status": "deleted",
            "message": "deleted",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/summary")
def domain_summary(domain_id: str) -> dict[str, object]:
    try:
        normalized_id = _validate_domain_id(domain_id)
        registry = _load_registry()
        item = _read_domain(registry, normalized_id)
        if item is None:
            return {"ok": False, "error": "not_found"}
        return {"ok": True, "summary": _summarize_domain(item)}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
