from __future__ import annotations

import hashlib
import hmac
import json
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Mapping


GROUNDED_PRESENCE_INTENT_KIND = "francis.grounded_presence.intent_event"
GROUNDED_PRESENCE_INTENT_SCHEMA_VERSION = "francis.grounded_presence.intent_event.v1"
GROUNDED_PRESENCE_INTENT_SCHEMA_PATH = "schemas/grounded_presence_intent_event.schema.json"
GROUNDED_PRESENCE_INTENT_DEFAULT_TTL_MS = 1_000
GROUNDED_PRESENCE_INTENT_MAX_TTL_MS = 2_000

_INTENT_ROUTES = {
    "request_context_refresh": "/continuity/presence",
    "acknowledge_handback": "operator_review_required",
    "request_review": "operator_review_required",
    "request_panic_stop": "/takeover/panic-stop",
}
_INTENT_CLASSES = {
    "request_context_refresh": "read_request",
    "acknowledge_handback": "acknowledgement_request",
    "request_review": "governed_action_request",
    "request_panic_stop": "safety_request",
}


@dataclass(frozen=True, slots=True)
class PresenceIntentValidation:
    ok: bool
    status: str
    reasons: tuple[str, ...]
    event_id: str
    adapter_id: str
    session_id: str
    event_sequence: int
    intent: str
    expired: bool
    replayed: bool
    digest_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reasons": list(self.reasons),
            "event_id": self.event_id,
            "adapter_id": self.adapter_id,
            "session_id": self.session_id,
            "event_sequence": self.event_sequence,
            "intent": self.intent,
            "expired": self.expired,
            "replayed": self.replayed,
            "digest_valid": self.digest_valid,
            "dispatch_allowed": False,
            "mutation_applied": False,
            "grants_execution_authority": False,
        }


def build_presence_intent_event(
    *,
    adapter_id: str,
    session_id: str,
    event_sequence: int,
    source_envelope_id: str,
    source_sequence: int,
    intent: str,
    target_kind: str = "none",
    target_id: str = "",
    issued_at: str | datetime | None = None,
    ttl_ms: int = GROUNDED_PRESENCE_INTENT_DEFAULT_TTL_MS,
) -> dict[str, Any]:
    normalized_adapter_id = _required_id(adapter_id, "presence_intent_adapter_id_invalid")
    normalized_session_id = _required_id(session_id, "presence_intent_session_id_invalid")
    normalized_event_sequence = _positive_int(event_sequence, "presence_intent_event_sequence_invalid")
    normalized_source_envelope_id = _required_id(
        source_envelope_id,
        "presence_intent_source_envelope_id_invalid",
    )
    if not normalized_source_envelope_id.startswith("gpe_"):
        raise ValueError("presence_intent_source_envelope_id_invalid")
    normalized_source_sequence = _positive_int(source_sequence, "presence_intent_source_sequence_invalid")
    normalized_intent = str(intent or "").strip()
    if normalized_intent not in _INTENT_ROUTES:
        raise ValueError("presence_intent_kind_invalid")
    normalized_target_kind = str(target_kind or "none").strip()
    if normalized_target_kind not in {"none", "mission", "operation", "receipt", "surface"}:
        raise ValueError("presence_intent_target_kind_invalid")
    normalized_target_id = _contract_id(target_id)
    if normalized_target_kind == "none" and str(target_id or "").strip():
        raise ValueError("presence_intent_target_not_allowed")
    if normalized_target_kind != "none" and not normalized_target_id:
        raise ValueError("presence_intent_target_id_required")
    normalized_ttl_ms = _bounded_ttl(ttl_ms)
    issued_dt = _parse_datetime(issued_at)
    if issued_at is not None and issued_dt is None:
        raise ValueError("presence_intent_issued_at_invalid")
    issued_dt = issued_dt or datetime.now(UTC)
    expires_dt = issued_dt + timedelta(milliseconds=normalized_ttl_ms)
    event_id = _event_id(
        adapter_id=normalized_adapter_id,
        session_id=normalized_session_id,
        event_sequence=normalized_event_sequence,
        source_envelope_id=normalized_source_envelope_id,
        intent=normalized_intent,
        issued_at=issued_dt,
    )
    event = {
        "kind": GROUNDED_PRESENCE_INTENT_KIND,
        "schema_version": GROUNDED_PRESENCE_INTENT_SCHEMA_VERSION,
        "schema_path": GROUNDED_PRESENCE_INTENT_SCHEMA_PATH,
        "event_id": event_id,
        "adapter": {
            "id": normalized_adapter_id,
            "kind": "unreal",
            "role": "governed_renderer_adapter",
            "engine_version": "5.8",
            "session_id": normalized_session_id,
            "authentication_status": "ipc_hmac_wrapper_required",
        },
        "event_sequence": normalized_event_sequence,
        "source": {
            "envelope_id": normalized_source_envelope_id,
            "sequence": normalized_source_sequence,
            "channel": "francis.presence.render.v1",
        },
        "issued_at": issued_dt.isoformat(),
        "expires_at": expires_dt.isoformat(),
        "ttl_ms": normalized_ttl_ms,
        "intent": {
            "kind": normalized_intent,
            "class": _INTENT_CLASSES[normalized_intent],
            "target": {
                "kind": normalized_target_kind,
                "id": normalized_target_id,
            },
            "request_only": True,
        },
        "routing": {
            "required_core_route": _INTENT_ROUTES[normalized_intent],
            "status": "not_dispatched",
            "dispatch_allowed": False,
            "mutation_allowed": False,
            "receipt_required_before_dispatch": True,
        },
        "authority": {
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
        "limitations": [
            "application_authentication_applied_at_ipc_wrapper",
            "intent_is_not_a_dispatched_action",
            "core_policy_route_required",
        ],
    }
    event["integrity"] = {
        "algorithm": "sha256",
        "canonicalization": "json_sort_keys_compact_utf8_without_integrity",
        "event_digest": _event_digest(event),
    }
    return event


def validate_presence_intent_event(
    event: Mapping[str, Any] | None,
    *,
    now: str | datetime | None = None,
    expected_adapter_id: str = "",
    expected_session_id: str = "",
    expected_source_envelope_id: str = "",
    last_event_sequence: int = 0,
) -> PresenceIntentValidation:
    payload = _mapping(event)
    adapter = _mapping(payload.get("adapter"))
    source = _mapping(payload.get("source"))
    intent_map = _mapping(payload.get("intent"))
    target = _mapping(intent_map.get("target"))
    routing = _mapping(payload.get("routing"))
    authority = _mapping(payload.get("authority"))
    integrity = _mapping(payload.get("integrity"))
    event_id = _text(payload.get("event_id"), limit=64)
    adapter_id = _text(adapter.get("id"), limit=160)
    session_id = _text(adapter.get("session_id"), limit=160)
    event_sequence = _nonnegative_int(payload.get("event_sequence"))
    intent = _text(intent_map.get("kind"))
    reasons: list[str] = []

    _require(payload.get("kind") == GROUNDED_PRESENCE_INTENT_KIND, "kind_invalid", reasons)
    _require(
        payload.get("schema_version") == GROUNDED_PRESENCE_INTENT_SCHEMA_VERSION,
        "schema_version_invalid",
        reasons,
    )
    _require(event_id.startswith("gpi_"), "event_id_invalid", reasons)
    _require(bool(_contract_id(adapter_id)), "adapter_id_invalid", reasons)
    _require(bool(_contract_id(session_id)), "session_id_invalid", reasons)
    _require(adapter.get("kind") == "unreal", "adapter_kind_invalid", reasons)
    _require(adapter.get("role") == "governed_renderer_adapter", "adapter_role_invalid", reasons)
    _require(adapter.get("engine_version") == "5.8", "engine_version_invalid", reasons)
    _require(
        adapter.get("authentication_status") == "ipc_hmac_wrapper_required",
        "authentication_status_invalid",
        reasons,
    )
    if expected_adapter_id:
        _require(adapter_id == _contract_id(expected_adapter_id), "adapter_identity_mismatch", reasons)
    if expected_session_id:
        _require(session_id == _contract_id(expected_session_id), "session_identity_mismatch", reasons)

    _require(event_sequence > 0, "event_sequence_invalid", reasons)
    replayed = event_sequence > 0 and event_sequence <= _nonnegative_int(last_event_sequence)
    _require(not replayed, "event_sequence_replayed", reasons)
    source_envelope_id = _text(source.get("envelope_id"), limit=64)
    _require(source_envelope_id.startswith("gpe_"), "source_envelope_id_invalid", reasons)
    _require(_nonnegative_int(source.get("sequence")) > 0, "source_sequence_invalid", reasons)
    _require(source.get("channel") == "francis.presence.render.v1", "source_channel_invalid", reasons)
    if expected_source_envelope_id:
        _require(
            source_envelope_id == _contract_id(expected_source_envelope_id),
            "source_envelope_mismatch",
            reasons,
        )

    _require(intent in _INTENT_ROUTES, "intent_kind_invalid", reasons)
    _require(intent_map.get("class") == _INTENT_CLASSES.get(intent), "intent_class_invalid", reasons)
    _require(intent_map.get("request_only") is True, "request_only_required", reasons)
    target_kind = _text(target.get("kind"))
    target_id = _text(target.get("id"), limit=160)
    _require(target_kind in {"none", "mission", "operation", "receipt", "surface"}, "target_kind_invalid", reasons)
    if target_kind == "none":
        _require(not target_id, "target_not_allowed", reasons)
    else:
        _require(bool(_contract_id(target_id)), "target_id_invalid", reasons)

    _require(routing.get("required_core_route") == _INTENT_ROUTES.get(intent), "core_route_invalid", reasons)
    _require(routing.get("status") == "not_dispatched", "routing_status_invalid", reasons)
    _require(routing.get("dispatch_allowed") is False, "dispatch_authority_drift", reasons)
    _require(routing.get("mutation_allowed") is False, "mutation_authority_drift", reasons)
    _require(routing.get("receipt_required_before_dispatch") is True, "receipt_gate_missing", reasons)

    now_dt = _parse_datetime(now) or datetime.now(UTC)
    issued_dt = _parse_datetime(payload.get("issued_at"))
    expires_dt = _parse_datetime(payload.get("expires_at"))
    ttl_ms = _nonnegative_int(payload.get("ttl_ms"))
    _require(issued_dt is not None, "issued_at_invalid", reasons)
    _require(expires_dt is not None, "expires_at_invalid", reasons)
    _require(0 < ttl_ms <= GROUNDED_PRESENCE_INTENT_MAX_TTL_MS, "ttl_invalid", reasons)
    if issued_dt is not None:
        _require((issued_dt - now_dt).total_seconds() <= 5, "issued_at_in_future", reasons)
    if issued_dt is not None and expires_dt is not None:
        actual_ttl_ms = round((expires_dt - issued_dt).total_seconds() * 1_000)
        _require(actual_ttl_ms == ttl_ms, "ttl_mismatch", reasons)
    expired = expires_dt is not None and now_dt >= expires_dt
    _require(not expired, "intent_expired", reasons)

    _require(integrity.get("algorithm") == "sha256", "integrity_algorithm_invalid", reasons)
    _require(
        integrity.get("canonicalization") == "json_sort_keys_compact_utf8_without_integrity",
        "integrity_canonicalization_invalid",
        reasons,
    )
    expected_digest = _text(integrity.get("event_digest"), limit=64).lower()
    try:
        actual_digest = _event_digest(payload)
    except (TypeError, ValueError):
        actual_digest = ""
    digest_valid = bool(expected_digest) and hmac.compare_digest(expected_digest, actual_digest)
    _require(digest_valid, "event_digest_mismatch", reasons)
    if adapter_id and session_id and event_sequence > 0 and source_envelope_id and issued_dt is not None:
        expected_event_id = _event_id(
            adapter_id=adapter_id,
            session_id=session_id,
            event_sequence=event_sequence,
            source_envelope_id=source_envelope_id,
            intent=intent,
            issued_at=issued_dt,
        )
        _require(event_id == expected_event_id, "event_id_mismatch", reasons)

    _require(authority.get("francis_core_authoritative") is True, "core_authority_missing", reasons)
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        _require(authority.get(field) is False, f"{field}_drift", reasons)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return PresenceIntentValidation(
        ok=not unique_reasons,
        status="accepted_for_core_routing" if not unique_reasons else "rejected",
        reasons=unique_reasons,
        event_id=event_id,
        adapter_id=adapter_id,
        session_id=session_id,
        event_sequence=event_sequence,
        intent=intent,
        expired=expired,
        replayed=replayed,
        digest_valid=digest_valid,
    )


class PresenceIntentReplayGuard:
    """Process-local replay guard for validated, non-dispatched renderer intents."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_sequences: dict[tuple[str, str], int] = {}

    def accept(
        self,
        event: Mapping[str, Any] | None,
        *,
        now: str | datetime | None = None,
        expected_adapter_id: str = "",
        expected_session_id: str = "",
        expected_source_envelope_id: str = "",
    ) -> PresenceIntentValidation:
        adapter = _mapping(_mapping(event).get("adapter"))
        key = (_text(adapter.get("id"), limit=160), _text(adapter.get("session_id"), limit=160))
        with self._lock:
            result = validate_presence_intent_event(
                event,
                now=now,
                expected_adapter_id=expected_adapter_id,
                expected_session_id=expected_session_id,
                expected_source_envelope_id=expected_source_envelope_id,
                last_event_sequence=self._last_sequences.get(key, 0),
            )
            if result.ok:
                self._last_sequences[key] = result.event_sequence
            return result


def _event_digest(event: Mapping[str, Any]) -> str:
    claims = {key: value for key, value in event.items() if key != "integrity"}
    canonical = json.dumps(
        claims,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _event_id(
    *,
    adapter_id: str,
    session_id: str,
    event_sequence: int,
    source_envelope_id: str,
    intent: str,
    issued_at: datetime,
) -> str:
    seed = "|".join(
        (
            adapter_id,
            session_id,
            str(event_sequence),
            source_envelope_id,
            intent,
            issued_at.isoformat(),
        )
    )
    return f"gpi_{hashlib.sha256(seed.encode()).hexdigest()[:32]}"


def _required_id(value: Any, error: str) -> str:
    normalized = _contract_id(value)
    if not normalized:
        raise ValueError(error)
    return normalized


def _contract_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _positive_int(value: Any, error: str) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(error)
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(error) from exc
    if parsed <= 0:
        raise ValueError(error)
    return parsed


def _bounded_ttl(value: Any) -> int:
    ttl_ms = _positive_int(value, "presence_intent_ttl_invalid")
    if ttl_ms > GROUNDED_PRESENCE_INTENT_MAX_TTL_MS:
        raise ValueError("presence_intent_ttl_invalid")
    return ttl_ms


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric = float(value)
        if not math.isfinite(numeric) or numeric <= 0:
            return None
        try:
            parsed = datetime.fromtimestamp(numeric, tz=UTC)
        except (OverflowError, OSError, ValueError):
            return None
    else:
        text = _text(value, limit=80)
        if not text:
            return None
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _require(condition: bool, reason: str, reasons: list[str]) -> None:
    if not condition:
        reasons.append(reason)
