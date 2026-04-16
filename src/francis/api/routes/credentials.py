from __future__ import annotations

import json
import os
import re
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.governance import approvals as approval_store
from francis.kernel.paths import data_dir

router = APIRouter()

_CREDENTIAL_ID_RE = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$")
_ALLOWED_STATUS = {"active", "revoked", "expired", "pending", "error"}


def _credentials_dir() -> Path:
    return data_dir() / "credentials"


def _registry_path() -> Path:
    return _credentials_dir() / "_registry.json"


def _scopes_dir() -> Path:
    return _credentials_dir() / "scopes"


def _delegations_dir() -> Path:
    return _credentials_dir() / "delegations"


def _vault_path() -> Path:
    return _credentials_dir() / "vault.db"


def _usage_events_path() -> Path:
    return _credentials_dir() / "usage_logs" / "api_events.jsonl"


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _now_s() -> int:
    return int(time.time())


def _now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    return _safe_str(value).strip().lower() in {"1", "true", "t", "yes", "y", "on"}


def _strip_quotes(text: str) -> str:
    value = text.strip()
    if len(value) >= 2 and ((value[0] == '"' and value[-1] == '"') or (value[0] == "'" and value[-1] == "'")):
        return value[1:-1]
    return value


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
    return slug[:64] or "credential"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _default_registry() -> dict[str, Any]:
    return {"version": 1, "updated_at": _now_s(), "credentials": {}, "events": []}


def _load_registry() -> dict[str, Any]:
    path = _registry_path()
    if not path.exists():
        return _default_registry()
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return _default_registry()
    if not isinstance(raw, dict):
        return _default_registry()

    credentials = raw.get("credentials")
    if isinstance(credentials, dict):
        events = raw.get("events")
        return {
            "version": int(raw.get("version") or 1),
            "updated_at": int(raw.get("updated_at") or _now_s()),
            "credentials": credentials,
            "events": events if isinstance(events, list) else [],
        }

    legacy_credentials = {k: v for k, v in raw.items() if isinstance(v, dict)}
    if legacy_credentials:
        return {"version": 1, "updated_at": _now_s(), "credentials": legacy_credentials, "events": []}
    return _default_registry()


def _save_registry(registry: dict[str, Any]) -> None:
    credentials = registry.get("credentials")
    if not isinstance(credentials, dict):
        credentials = {}
    events = registry.get("events")
    if not isinstance(events, list):
        events = []
    normalized: dict[str, Any] = {
        "version": int(registry.get("version") or 1),
        "updated_at": _now_s(),
        "credentials": credentials,
        "events": events[-2000:],
    }
    _atomic_write_json(_registry_path(), normalized)


def _validate_credential_id(value: str) -> str:
    text = value.strip()
    if not text:
        raise ValueError("id is required")
    if not _CREDENTIAL_ID_RE.match(text):
        raise ValueError("invalid credential id")
    return text


def _normalize_status(raw: Any) -> str:
    status = _safe_str(raw).strip().lower()
    if not status:
        return "active"
    return status if status in _ALLOWED_STATUS else status


def _hint_for_credential(credential_id: str, provider: str) -> str:
    tail = credential_id[-4:] if len(credential_id) >= 4 else credential_id
    if provider:
        return f"{provider}:...{tail}"
    return f"...{tail}"


def _normalize_credential_record(credential_id: str, raw: dict[str, Any]) -> dict[str, Any]:
    created_ts = int(raw.get("created_ts") or _now_s())
    last_used_ts = int(raw.get("last_used_ts") or 0)
    expires_ts = int(raw.get("expires_ts") or 0)
    provider = _safe_str(raw.get("provider")).strip()
    out = {
        "id": credential_id,
        "type": _safe_str(raw.get("type")).strip() or "api_key",
        "status": _normalize_status(raw.get("status")),
        "scope_id": _safe_str(raw.get("scope_id")).strip() or "",
        "provider": provider,
        "domain": _safe_str(raw.get("domain")).strip() or "",
        "actor": _safe_str(raw.get("actor")).strip() or "",
        "created_ts": created_ts,
        "last_used_ts": last_used_ts,
        "expires_ts": expires_ts,
        "label": _safe_str(raw.get("label")).strip() or credential_id,
        "fingerprint": _safe_str(raw.get("fingerprint")).strip() or "",
        "hint": _safe_str(raw.get("hint")).strip() or _hint_for_credential(credential_id, provider),
        "meta": dict(raw.get("meta") or {}) if isinstance(raw.get("meta"), dict) else {},
    }
    return out


def _read_credential(registry: dict[str, Any], credential_id: str) -> dict[str, Any] | None:
    credentials = registry.get("credentials")
    if not isinstance(credentials, dict):
        return None
    raw = credentials.get(credential_id)
    if not isinstance(raw, dict):
        return None
    return _normalize_credential_record(credential_id, raw)


def _write_credential(registry: dict[str, Any], credential: dict[str, Any]) -> None:
    credentials = registry.get("credentials")
    if not isinstance(credentials, dict):
        credentials = {}
        registry["credentials"] = credentials
    credentials[credential["id"]] = credential


def _append_event(registry: dict[str, Any], event_type: str, payload: dict[str, Any]) -> None:
    events = registry.get("events")
    if not isinstance(events, list):
        events = []
        registry["events"] = events
    item = {
        "id": f"evt_{uuid.uuid4().hex}",
        "event_type": event_type,
        "ts": _now_s(),
        "emitted_at": _now_iso(),
        **payload,
    }
    events.append(item)
    if len(events) > 2000:
        del events[: len(events) - 2000]
    _usage_events_path().parent.mkdir(parents=True, exist_ok=True)
    try:
        with _usage_events_path().open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(item, ensure_ascii=False, default=str))
            handle.write("\n")
    except OSError:
        pass


def _approval_status(approval_id: str) -> tuple[str, dict[str, Any] | None]:
    resolved_id = _safe_str(approval_id).strip()
    if not resolved_id:
        return "", None
    candidates: list[tuple[str, Path]] = [
        ("pending", approval_store.pending_dir() / f"{resolved_id}.json"),
        ("approved", approval_store.approved_dir() / f"{resolved_id}.json"),
        ("rejected", approval_store.rejected_dir() / f"{resolved_id}.json"),
        ("emergency", approval_store.emergency_dir() / f"{resolved_id}.json"),
    ]
    for status, path in candidates:
        if not path.exists():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "corrupt", None
        return status, payload if isinstance(payload, dict) else None
    return "missing", None


def _reconcile_credential_approvals(registry: dict[str, Any]) -> bool:
    credentials = registry.get("credentials")
    if not isinstance(credentials, dict):
        return False

    changed = False
    for credential_id, raw in list(credentials.items()):
        if not isinstance(raw, dict):
            continue
        record = _normalize_credential_record(_safe_str(credential_id), raw)
        meta = dict(record.get("meta") or {})
        prior_status = _safe_str(record.get("status")).strip() or "active"
        updated = False

        request_approval_id = _safe_str(meta.get("approval_id")).strip()
        prior_request_status = _safe_str(meta.get("approval_status")).strip()
        if request_approval_id:
            request_status, _ = _approval_status(request_approval_id)
            if request_status and request_status != prior_request_status:
                meta["approval_status"] = request_status
                updated = True
                _append_event(
                    registry,
                    "credential.request.approval_status",
                    {
                        "credential_id": credential_id,
                        "approval_id": request_approval_id,
                        "previous_status": prior_request_status,
                        "approval_status": request_status,
                        "actor": "credential_manager_reconcile",
                    },
                )
            if prior_status == "pending" and not _to_bool(meta.get("revocation_requested")):
                if request_status == "approved":
                    record["status"] = "active"
                    updated = True
                elif request_status in {"rejected", "emergency"}:
                    record["status"] = "error"
                    updated = True

        revocation_approval_id = _safe_str(meta.get("revocation_approval_id")).strip()
        prior_revocation_status = _safe_str(meta.get("revocation_approval_status")).strip()
        if revocation_approval_id and _to_bool(meta.get("revocation_requested")):
            revocation_status, _ = _approval_status(revocation_approval_id)
            if revocation_status and revocation_status != prior_revocation_status:
                meta["revocation_approval_status"] = revocation_status
                updated = True
                _append_event(
                    registry,
                    "credential.revoke.approval_status",
                    {
                        "credential_id": credential_id,
                        "approval_id": revocation_approval_id,
                        "previous_status": prior_revocation_status,
                        "approval_status": revocation_status,
                        "actor": "credential_manager_reconcile",
                    },
                )
            previous_status = _safe_str(meta.get("revocation_previous_status")).strip() or "active"
            if revocation_status == "approved":
                record["status"] = "revoked"
                meta["revocation_requested"] = False
                updated = True
            elif revocation_status in {"rejected", "emergency"}:
                record["status"] = previous_status
                meta["revocation_requested"] = False
                updated = True

        if _safe_str(record.get("status")).strip() != prior_status:
            _append_event(
                registry,
                "credential.status_reconciled",
                {
                    "credential_id": credential_id,
                    "previous_status": prior_status,
                    "status": _safe_str(record.get("status")).strip(),
                    "approval_id": request_approval_id or revocation_approval_id,
                    "actor": "credential_manager_reconcile",
                },
            )

        if updated:
            record["meta"] = meta
            _write_credential(registry, _normalize_credential_record(credential_id, record))
            changed = True

    return changed


def _parse_ts(value: Any) -> int:
    if isinstance(value, (int, float)):
        ts = int(value)
        if ts > 10_000_000_000:
            ts = int(ts / 1000)
        return max(ts, 0)
    text = _safe_str(value).strip()
    if not text:
        return 0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except Exception:
        return 0
    return int(parsed.timestamp())


def _seed_from_vault(registry: dict[str, Any]) -> bool:
    path = _vault_path()
    if not path.exists() or not path.is_file():
        return False

    changed = False
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return False

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        try:
            obj = json.loads(stripped)
        except Exception:
            continue
        if not isinstance(obj, dict):
            continue

        credential_obj = obj.get("credential")
        if not isinstance(credential_obj, dict):
            continue
        credential_id = _safe_str(credential_obj.get("credential_id")).strip()
        if not credential_id:
            continue
        try:
            credential_id = _validate_credential_id(credential_id)
        except Exception:
            continue

        emitted_ts = _parse_ts(obj.get("emitted_at")) or _parse_ts(obj.get("ts")) or _now_s()
        provider = _safe_str(credential_obj.get("provider")).strip()
        scope_id = _safe_str(credential_obj.get("scope_set_id")).strip()
        record = _read_credential(registry, credential_id)
        if record is None:
            record = _normalize_credential_record(
                credential_id,
                {
                    "id": credential_id,
                    "type": _safe_str(credential_obj.get("credential_type")).strip() or "api_key",
                    "status": "active",
                    "scope_id": scope_id,
                    "provider": provider,
                    "domain": _safe_str(obj.get("request", {}).get("domain_id") if isinstance(obj.get("request"), dict) else "").strip(),
                    "actor": _safe_str(obj.get("actor", {}).get("id") if isinstance(obj.get("actor"), dict) else "").strip(),
                    "created_ts": emitted_ts,
                    "last_used_ts": emitted_ts,
                    "label": credential_id,
                    "hint": _hint_for_credential(credential_id, provider),
                    "meta": {
                        "source": "vault.db",
                        "scope_set_id": scope_id,
                        "delegation_id": _safe_str(credential_obj.get("delegation_id")).strip(),
                    },
                },
            )
            _write_credential(registry, record)
            changed = True
            continue

        updated = False
        if emitted_ts > int(record.get("last_used_ts") or 0):
            record["last_used_ts"] = emitted_ts
            updated = True
        if not _safe_str(record.get("provider")).strip() and provider:
            record["provider"] = provider
            updated = True
        if not _safe_str(record.get("scope_id")).strip() and scope_id:
            record["scope_id"] = scope_id
            updated = True
        if updated:
            _write_credential(registry, _normalize_credential_record(credential_id, record))
            changed = True
    return changed


def _match_credential(item: dict[str, Any], status_filter: str, scope_filter: str, provider_filter: str, search_filter: str) -> bool:
    if status_filter and _safe_str(item.get("status")).strip().lower() != status_filter:
        return False
    if scope_filter and _safe_str(item.get("scope_id")).strip().lower() != scope_filter:
        return False
    if provider_filter and _safe_str(item.get("provider")).strip().lower() != provider_filter:
        return False
    if search_filter:
        haystack = " ".join(
            [
                _safe_str(item.get("id")),
                _safe_str(item.get("label")),
                _safe_str(item.get("provider")),
                _safe_str(item.get("scope_id")),
                _safe_str(item.get("hint")),
            ]
        ).lower()
        if search_filter not in haystack:
            return False
    return True


def _parse_scopes_from_yaml(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []

    out: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- scope_id:"):
            if current is not None and _safe_str(current.get("id")).strip():
                out.append(current)
            scope_id = _strip_quotes(stripped.split(":", 1)[1].strip())
            current = {
                "id": scope_id,
                "name": scope_id,
                "description": "",
                "requires_approval": True,
                "risk": "unknown",
                "meta": {"source": str(path.relative_to(_credentials_dir()))},
            }
            continue

        if current is None:
            continue

        if stripped.startswith("name:"):
            current["name"] = _strip_quotes(stripped.split(":", 1)[1].strip()) or current["name"]
            continue
        if stripped.startswith("provider:"):
            current_meta = current.get("meta")
            current_meta_obj = current_meta if isinstance(current_meta, dict) else {}
            current_meta_obj["provider"] = _strip_quotes(stripped.split(":", 1)[1].strip())
            current["meta"] = current_meta_obj
            continue
        if stripped.startswith("status:"):
            current_meta = current.get("meta")
            current_meta_obj = current_meta if isinstance(current_meta, dict) else {}
            current_meta_obj["status"] = _strip_quotes(stripped.split(":", 1)[1].strip())
            current["meta"] = current_meta_obj
            continue
        if stripped.startswith("risk_level:"):
            current["risk"] = _strip_quotes(stripped.split(":", 1)[1].strip()) or current["risk"]
            continue
        if stripped.startswith("notes:"):
            current["description"] = _strip_quotes(stripped.split(":", 1)[1].strip())
            continue

    if current is not None and _safe_str(current.get("id")).strip():
        out.append(current)
    return out


def _load_scopes(registry: dict[str, Any]) -> list[dict[str, Any]]:
    scopes: dict[str, dict[str, Any]] = {}
    scope_dir = _scopes_dir()
    if scope_dir.exists():
        for path in sorted(scope_dir.glob("*.yaml")) + sorted(scope_dir.glob("*.yml")):
            for item in _parse_scopes_from_yaml(path):
                scope_id = _safe_str(item.get("id")).strip()
                if not scope_id:
                    continue
                scopes[scope_id] = item

    credentials = registry.get("credentials")
    if isinstance(credentials, dict):
        for credential_id, raw in credentials.items():
            if not isinstance(raw, dict):
                continue
            item = _normalize_credential_record(_safe_str(credential_id), raw)
            scope_id = _safe_str(item.get("scope_id")).strip()
            if not scope_id:
                continue
            if scope_id in scopes:
                continue
            scopes[scope_id] = {
                "id": scope_id,
                "name": scope_id,
                "description": "",
                "requires_approval": True,
                "risk": "unknown",
                "meta": {"source": "credential_registry"},
            }
    return list(sorted(scopes.values(), key=lambda item: _safe_str(item.get("id"))))


def _parse_delegation_yaml(path: Path) -> dict[str, Any] | None:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return None

    delegation_id = ""
    status = ""
    grantor = ""
    delegate = ""
    reason = ""
    created_ts = 0
    scope_ids: list[str] = []
    context = ""
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "grantor:":
            context = "grantor"
            continue
        if stripped == "delegate:":
            context = "delegate"
            continue

        if stripped.startswith("id:"):
            value = _strip_quotes(stripped.split(":", 1)[1].strip())
            if not delegation_id:
                delegation_id = value
                continue
            if context == "grantor" and not grantor:
                grantor = value
                continue
            if context == "delegate" and not delegate:
                delegate = value
                continue
        if stripped.startswith("status:") and not status:
            status = _strip_quotes(stripped.split(":", 1)[1].strip())
            continue
        if stripped.startswith("created_at:"):
            created_ts = _parse_ts(_strip_quotes(stripped.split(":", 1)[1].strip()))
            continue
        if stripped.startswith("description:") and not reason:
            reason = _strip_quotes(stripped.split(":", 1)[1].strip())
            continue
        if stripped.startswith("- scope_id:"):
            scope_id = _strip_quotes(stripped.split(":", 1)[1].strip())
            if scope_id and scope_id not in scope_ids:
                scope_ids.append(scope_id)
            continue

    if not delegation_id or "<" in delegation_id:
        return None
    return {
        "id": delegation_id,
        "ts": created_ts or int(path.stat().st_mtime),
        "from": grantor,
        "to": delegate,
        "scope_id": scope_ids[0] if scope_ids else "",
        "status": status or "draft",
        "reason": reason,
        "meta": {"scope_ids": scope_ids, "source": str(path.relative_to(_credentials_dir()))},
    }


def _load_delegations(registry: dict[str, Any]) -> list[dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    delegation_dir = _delegations_dir()
    if delegation_dir.exists():
        for path in sorted(delegation_dir.glob("*.yaml")) + sorted(delegation_dir.glob("*.yml")):
            item = _parse_delegation_yaml(path)
            if item is None:
                continue
            delegation_id = _safe_str(item.get("id")).strip()
            if delegation_id:
                out[delegation_id] = item

    events = registry.get("events")
    if isinstance(events, list):
        for event in events:
            if not isinstance(event, dict):
                continue
            if _safe_str(event.get("event_type")).strip() not in {"credential.request", "credential.revoke"}:
                continue
            approval_id = _safe_str(event.get("approval_id")).strip()
            if not approval_id or approval_id in out:
                continue
            scope_id = _safe_str(event.get("scope_id")).strip()
            out[approval_id] = {
                "id": approval_id,
                "ts": int(event.get("ts") or 0),
                "from": "governance.approvals",
                "to": _safe_str(event.get("actor")).strip(),
                "scope_id": scope_id,
                "status": "pending",
                "reason": _safe_str(event.get("reason")).strip(),
                "meta": {"source": "credential_api_event", "credential_id": _safe_str(event.get("credential_id")).strip()},
            }
    return list(sorted(out.values(), key=lambda item: int(item.get("ts") or 0), reverse=True))


def _new_request_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class CredentialRequestIn(BaseModel):
    scope_id: str
    provider: str = ""
    type: str = "api_key"
    label: str = ""
    reason: str = "requested"
    meta: dict[str, Any] = Field(default_factory=dict)


class CredentialRevokeIn(BaseModel):
    id: str
    reason: str = "requested"


@router.get("/status")
def status() -> dict[str, object]:
    try:
        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        if changed:
            _save_registry(registry)
        credentials = registry.get("credentials")
        total_credentials = len(credentials) if isinstance(credentials, dict) else 0
        return {
            "ok": True,
            "route": "credentials",
            "status": "ready",
            "credentials": total_credentials,
            "scopes": len(_load_scopes(registry)),
            "delegations": len(_load_delegations(registry)),
        }
    except Exception as exc:
        return {"ok": False, "route": "credentials", "status": "error", "error": str(exc)}


@router.get("/list")
def list_credentials(
    limit: int = 200,
    offset: int = 0,
    status: str | None = None,
    scope_id: str | None = None,
    provider: str | None = None,
    search: str | None = None,
) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        safe_offset = max(0, int(offset))
        status_filter = _safe_str(status).strip().lower()
        scope_filter = _safe_str(scope_id).strip().lower()
        provider_filter = _safe_str(provider).strip().lower()
        search_filter = _safe_str(search).strip().lower()

        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        if changed:
            _save_registry(registry)

        credentials_obj = registry.get("credentials")
        if not isinstance(credentials_obj, dict):
            credentials_obj = {}

        items: list[dict[str, Any]] = []
        for credential_id, raw in credentials_obj.items():
            if not isinstance(raw, dict):
                continue
            item = _normalize_credential_record(_safe_str(credential_id), raw)
            if _match_credential(item, status_filter, scope_filter, provider_filter, search_filter):
                items.append(item)

        items.sort(key=lambda item: (int(item.get("last_used_ts") or 0), int(item.get("created_ts") or 0), _safe_str(item.get("id"))), reverse=True)
        total = len(items)
        page = items[safe_offset : safe_offset + safe_limit]
        return {"items": page, "credentials": page, "total": total, "offset": safe_offset, "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "credentials": [], "total": 0, "offset": 0, "limit": 0, "error": str(exc)}


@router.get("/scopes")
def list_scopes() -> dict[str, object]:
    try:
        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        if changed:
            _save_registry(registry)
        items = _load_scopes(registry)
        return {"items": items, "scopes": items, "total": len(items)}
    except Exception as exc:
        return {"items": [], "scopes": [], "total": 0, "error": str(exc)}


@router.get("/delegations")
def list_delegations(limit: int = 200) -> dict[str, object]:
    try:
        safe_limit = max(1, min(int(limit), 5000))
        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        if changed:
            _save_registry(registry)
        items = _load_delegations(registry)[:safe_limit]
        return {"items": items, "delegations": items, "total": len(items), "limit": safe_limit}
    except Exception as exc:
        return {"items": [], "delegations": [], "total": 0, "error": str(exc)}


@router.post("/request")
def request_credential(payload: CredentialRequestIn) -> dict[str, object]:
    try:
        scope_id = _safe_str(payload.scope_id).strip()
        if not scope_id:
            return {"ok": False, "error": "scope_id_required"}

        provider = _safe_str(payload.provider).strip().lower()
        cred_type = _safe_str(payload.type).strip().lower() or "api_key"
        reason = _safe_str(payload.reason).strip() or "requested"
        label = _safe_str(payload.label).strip() or f"{provider or 'credential'}:{scope_id}"

        request_id = _new_request_id("creq")
        approval = approval_store.request(
            "credential.request",
            reason,
            {
                "scope_id": scope_id,
                "provider": provider,
                "type": cred_type,
                "label": label,
                "request_id": request_id,
                "meta": dict(payload.meta or {}),
            },
        )
        approval_id = _safe_str(approval.get("id")).strip()

        credential_id = _validate_credential_id(f"cred_{_slugify(provider or 'generic')}_{uuid.uuid4().hex[:10]}")
        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        record = _normalize_credential_record(
            credential_id,
            {
                "id": credential_id,
                "type": cred_type,
                "status": "pending",
                "scope_id": scope_id,
                "provider": provider,
                "created_ts": _now_s(),
                "last_used_ts": 0,
                "label": label,
                "hint": _hint_for_credential(credential_id, provider),
                "meta": {
                    **dict(payload.meta or {}),
                    "request_id": request_id,
                    "approval_id": approval_id,
                    "reason": reason,
                    "approval_status": _safe_str(approval.get("status")).strip() or "pending",
                },
            },
        )
        _write_credential(registry, record)
        _append_event(
            registry,
            "credential.request",
            {
                "credential_id": credential_id,
                "scope_id": scope_id,
                "provider": provider,
                "request_id": request_id,
                "approval_id": approval_id,
                "reason": reason,
                "actor": "credential_manager_api",
            },
        )
        if changed:
            _append_event(registry, "credential.vault_seed", {"count": len(registry.get("credentials", {}))})
        _save_registry(registry)

        return {
            "ok": True,
            "id": credential_id,
            "request_id": request_id,
            "approval_id": approval_id,
            "status": "pending",
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.post("/revoke")
def revoke_credential(payload: CredentialRevokeIn) -> dict[str, object]:
    try:
        credential_id = _validate_credential_id(payload.id)
        reason = _safe_str(payload.reason).strip() or "requested"

        registry = _load_registry()
        changed = _seed_from_vault(registry)
        changed = _reconcile_credential_approvals(registry) or changed
        current = _read_credential(registry, credential_id)
        if current is None:
            return {"ok": False, "error": "not_found", "id": credential_id}

        approval = approval_store.request(
            "credential.revoke",
            reason,
            {
                "id": credential_id,
                "scope_id": _safe_str(current.get("scope_id")).strip(),
                "provider": _safe_str(current.get("provider")).strip(),
            },
        )
        approval_id = _safe_str(approval.get("id")).strip()

        current["status"] = "pending"
        current_meta = current.get("meta")
        current_meta_obj = current_meta if isinstance(current_meta, dict) else {}
        current_meta_obj["revocation_requested"] = True
        current_meta_obj["revocation_previous_status"] = _safe_str(current.get("status")).strip() or "active"
        current_meta_obj["revocation_approval_id"] = approval_id
        current_meta_obj["revocation_approval_status"] = _safe_str(approval.get("status")).strip() or "pending"
        current_meta_obj["revocation_reason"] = reason
        current["meta"] = current_meta_obj
        _write_credential(registry, _normalize_credential_record(credential_id, current))
        _append_event(
            registry,
            "credential.revoke",
            {
                "credential_id": credential_id,
                "approval_id": approval_id,
                "reason": reason,
                "scope_id": _safe_str(current.get("scope_id")).strip(),
                "actor": "credential_manager_api",
            },
        )
        if changed:
            _append_event(registry, "credential.vault_seed", {"count": len(registry.get("credentials", {}))})
        _save_registry(registry)

        return {"ok": True, "id": credential_id, "approval_id": approval_id, "status": "pending"}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}
