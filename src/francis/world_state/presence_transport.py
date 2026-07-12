from __future__ import annotations

import hashlib
import hmac
import json
import math
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from typing import Any, Mapping

from francis.world_state.presence import (
    GROUNDED_PRESENCE_KIND,
    GROUNDED_PRESENCE_SCHEMA_VERSION,
)


GROUNDED_PRESENCE_TRANSPORT_KIND = "francis.grounded_presence.transport_envelope"
GROUNDED_PRESENCE_TRANSPORT_SCHEMA_VERSION = "francis.grounded_presence.transport_envelope.v1"
GROUNDED_PRESENCE_TRANSPORT_SCHEMA_PATH = "schemas/grounded_presence_transport_envelope.schema.json"
GROUNDED_PRESENCE_TRANSPORT_CHANNEL = "francis.presence.render.v1"
GROUNDED_PRESENCE_TRANSPORT_DEFAULT_TTL_MS = 2_000
GROUNDED_PRESENCE_TRANSPORT_MAX_TTL_MS = 5_000


@dataclass(frozen=True, slots=True)
class PresenceEnvelopeValidation:
    ok: bool
    status: str
    reasons: tuple[str, ...]
    adapter_id: str
    session_id: str
    sequence: int
    expired: bool
    replayed: bool
    digest_valid: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reasons": list(self.reasons),
            "adapter_id": self.adapter_id,
            "session_id": self.session_id,
            "sequence": self.sequence,
            "expired": self.expired,
            "replayed": self.replayed,
            "digest_valid": self.digest_valid,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


def build_presence_transport_envelope(
    *,
    snapshot: Mapping[str, Any],
    adapter_id: str,
    session_id: str,
    sequence: int,
    issued_at: str | datetime | None = None,
    ttl_ms: int = GROUNDED_PRESENCE_TRANSPORT_DEFAULT_TTL_MS,
) -> dict[str, Any]:
    """Wrap a grounded snapshot in the bounded Core-to-renderer transport contract."""

    normalized_adapter_id = _contract_id(adapter_id)
    normalized_session_id = _contract_id(session_id)
    if not normalized_adapter_id:
        raise ValueError("grounded_presence_transport_adapter_id_invalid")
    if not normalized_session_id:
        raise ValueError("grounded_presence_transport_session_id_invalid")
    normalized_sequence = _positive_int(sequence)
    normalized_ttl_ms = _bounded_ttl_ms(ttl_ms)
    issued_dt = _parse_datetime(issued_at)
    if issued_at is not None and issued_dt is None:
        raise ValueError("grounded_presence_transport_issued_at_invalid")
    issued_dt = issued_dt or datetime.now(UTC)
    expires_dt = issued_dt + timedelta(milliseconds=normalized_ttl_ms)
    payload = deepcopy(dict(snapshot))
    _validate_payload_identity(payload)
    payload_digest = _payload_digest(payload)
    envelope_id = _envelope_id(
        adapter_id=normalized_adapter_id,
        session_id=normalized_session_id,
        sequence=normalized_sequence,
        issued_at=issued_dt,
        payload_digest=payload_digest,
    )

    return {
        "kind": GROUNDED_PRESENCE_TRANSPORT_KIND,
        "schema_version": GROUNDED_PRESENCE_TRANSPORT_SCHEMA_VERSION,
        "schema_path": GROUNDED_PRESENCE_TRANSPORT_SCHEMA_PATH,
        "envelope_id": envelope_id,
        "channel": GROUNDED_PRESENCE_TRANSPORT_CHANNEL,
        "direction": "francis_core_to_unreal",
        "adapter": {
            "id": normalized_adapter_id,
            "kind": "unreal",
            "role": "governed_renderer_adapter",
            "engine": "Unreal Engine",
            "engine_version": "5.8",
            "session_id": normalized_session_id,
        },
        "sequence": normalized_sequence,
        "issued_at": issued_dt.isoformat(),
        "expires_at": expires_dt.isoformat(),
        "ttl_ms": normalized_ttl_ms,
        "integrity": {
            "algorithm": "sha256",
            "canonicalization": "json_sort_keys_compact_utf8",
            "payload_digest": payload_digest,
        },
        "transport": {
            "protocol": "local_ipc",
            "binding_status": "unbound",
            "endpoint_id": "",
            "local_only": True,
            "network_allowed": False,
            "monotonic_sequence_required": True,
            "expiry_required": True,
            "replay_rejection_required": True,
            "runtime_enforcement_status": "consumer_guard_required",
        },
        "payload": payload,
        "authority": {
            "francis_core_authoritative": True,
            "adapter_read_only": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
        "limitations": [
            "transport_binding_not_implemented",
            "ipc_hmac_authentication_required_at_binding",
            "durable_consumer_deduplication_required",
        ],
    }


def bind_presence_transport_envelope(
    envelope: Mapping[str, Any],
    *,
    binding_status: str,
    endpoint_id: str,
) -> dict[str, Any]:
    """Bind an immutable envelope copy to an approved local transport endpoint."""

    if binding_status != "windows_named_pipe":
        raise ValueError("grounded_presence_transport_binding_invalid")
    normalized_endpoint_id = _contract_id(endpoint_id)
    if not normalized_endpoint_id:
        raise ValueError("grounded_presence_transport_endpoint_id_invalid")
    bound = deepcopy(dict(envelope))
    transport = _mapping(bound.get("transport"))
    if transport.get("binding_status") != "unbound":
        raise ValueError("grounded_presence_transport_already_bound")
    transport.update(
        {
            "binding_status": "windows_named_pipe",
            "endpoint_id": normalized_endpoint_id,
            "runtime_enforcement_status": "publisher_guard_active",
        }
    )
    bound["transport"] = transport
    limitations = [
        str(item) for item in bound.get("limitations", []) if str(item) != "transport_binding_not_implemented"
    ]
    bound["limitations"] = list(dict.fromkeys(limitations))
    return bound


def validate_presence_transport_envelope(
    envelope: Mapping[str, Any] | None,
    *,
    now: str | datetime | None = None,
    expected_adapter_id: str = "",
    expected_session_id: str = "",
    last_sequence: int = 0,
) -> PresenceEnvelopeValidation:
    """Validate identity, integrity, expiry, and monotonic sequencing without mutation."""

    payload = _mapping(envelope)
    adapter = _mapping(payload.get("adapter"))
    integrity = _mapping(payload.get("integrity"))
    transport = _mapping(payload.get("transport"))
    authority = _mapping(payload.get("authority"))
    grounded_payload = _mapping(payload.get("payload"))
    adapter_id = _text(adapter.get("id"), limit=160)
    session_id = _text(adapter.get("session_id"), limit=160)
    sequence = _nonnegative_int(payload.get("sequence"))
    reasons: list[str] = []

    _require(payload.get("kind") == GROUNDED_PRESENCE_TRANSPORT_KIND, "kind_invalid", reasons)
    _require(
        payload.get("schema_version") == GROUNDED_PRESENCE_TRANSPORT_SCHEMA_VERSION,
        "schema_version_invalid",
        reasons,
    )
    _require(payload.get("channel") == GROUNDED_PRESENCE_TRANSPORT_CHANNEL, "channel_invalid", reasons)
    _require(payload.get("direction") == "francis_core_to_unreal", "direction_invalid", reasons)
    _require(bool(_text(payload.get("envelope_id"), limit=64)), "envelope_id_invalid", reasons)
    _require(bool(_contract_id(adapter_id)), "adapter_id_invalid", reasons)
    _require(bool(_contract_id(session_id)), "session_id_invalid", reasons)
    _require(adapter.get("kind") == "unreal", "adapter_kind_invalid", reasons)
    _require(adapter.get("role") == "governed_renderer_adapter", "adapter_role_invalid", reasons)
    _require(adapter.get("engine_version") == "5.8", "engine_version_invalid", reasons)
    _require(sequence > 0, "sequence_invalid", reasons)

    normalized_expected_adapter = _contract_id(expected_adapter_id) if expected_adapter_id else ""
    normalized_expected_session = _contract_id(expected_session_id) if expected_session_id else ""
    if normalized_expected_adapter:
        _require(adapter_id == normalized_expected_adapter, "adapter_identity_mismatch", reasons)
    if normalized_expected_session:
        _require(session_id == normalized_expected_session, "session_identity_mismatch", reasons)

    replayed = sequence > 0 and sequence <= _nonnegative_int(last_sequence)
    _require(not replayed, "sequence_replayed", reasons)

    now_dt = _parse_datetime(now) or datetime.now(UTC)
    issued_dt = _parse_datetime(payload.get("issued_at"))
    expires_dt = _parse_datetime(payload.get("expires_at"))
    ttl_ms = _nonnegative_int(payload.get("ttl_ms"))
    _require(issued_dt is not None, "issued_at_invalid", reasons)
    _require(expires_dt is not None, "expires_at_invalid", reasons)
    _require(0 < ttl_ms <= GROUNDED_PRESENCE_TRANSPORT_MAX_TTL_MS, "ttl_invalid", reasons)
    if issued_dt is not None:
        _require((issued_dt - now_dt).total_seconds() <= 5, "issued_at_in_future", reasons)
    if issued_dt is not None and expires_dt is not None:
        actual_ttl_ms = round((expires_dt - issued_dt).total_seconds() * 1000)
        _require(actual_ttl_ms == ttl_ms, "ttl_mismatch", reasons)
    expired = expires_dt is not None and now_dt >= expires_dt
    _require(not expired, "envelope_expired", reasons)

    _require(integrity.get("algorithm") == "sha256", "integrity_algorithm_invalid", reasons)
    _require(
        integrity.get("canonicalization") == "json_sort_keys_compact_utf8",
        "integrity_canonicalization_invalid",
        reasons,
    )
    expected_digest = _text(integrity.get("payload_digest"), limit=64).lower()
    try:
        actual_digest = _payload_digest(grounded_payload) if grounded_payload else ""
    except (TypeError, ValueError):
        actual_digest = ""
    digest_valid = bool(expected_digest) and hmac.compare_digest(expected_digest, actual_digest)
    _require(digest_valid, "payload_digest_mismatch", reasons)
    _require(grounded_payload.get("kind") == GROUNDED_PRESENCE_KIND, "payload_kind_invalid", reasons)
    _require(
        grounded_payload.get("schema_version") == GROUNDED_PRESENCE_SCHEMA_VERSION,
        "payload_schema_version_invalid",
        reasons,
    )
    payload_authority = _mapping(grounded_payload.get("authority"))
    payload_intent = _mapping(grounded_payload.get("intent"))
    payload_unreal = _mapping(grounded_payload.get("unreal_adapter"))
    _require(
        payload_authority.get("francis_core_authoritative") is True,
        "payload_core_authority_missing",
        reasons,
    )
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        _require(payload_authority.get(field) is False, f"payload_{field}_drift", reasons)
    _require(
        payload_intent.get("grants_execution_authority") is False,
        "payload_intent_authority_drift",
        reasons,
    )
    _require(payload_unreal.get("accepts_authority") is False, "payload_unreal_authority_drift", reasons)

    if adapter_id and session_id and sequence > 0 and issued_dt is not None and expected_digest:
        expected_envelope_id = _envelope_id(
            adapter_id=adapter_id,
            session_id=session_id,
            sequence=sequence,
            issued_at=issued_dt,
            payload_digest=expected_digest,
        )
        _require(payload.get("envelope_id") == expected_envelope_id, "envelope_id_mismatch", reasons)

    _require(transport.get("protocol") == "local_ipc", "transport_protocol_invalid", reasons)
    binding_status = _text(transport.get("binding_status"))
    endpoint_id = _text(transport.get("endpoint_id"), limit=160)
    _require(
        binding_status in {"unbound", "windows_named_pipe"},
        "transport_binding_status_invalid",
        reasons,
    )
    if binding_status == "unbound":
        _require(not endpoint_id, "unbound_transport_endpoint_present", reasons)
        _require(
            transport.get("runtime_enforcement_status") == "consumer_guard_required",
            "runtime_enforcement_status_invalid",
            reasons,
        )
    elif binding_status == "windows_named_pipe":
        _require(bool(_contract_id(endpoint_id)), "transport_endpoint_id_invalid", reasons)
        _require(
            transport.get("runtime_enforcement_status") == "publisher_guard_active",
            "runtime_enforcement_status_invalid",
            reasons,
        )
    _require(transport.get("local_only") is True, "local_only_required", reasons)
    _require(transport.get("network_allowed") is False, "network_authority_drift", reasons)
    _require(transport.get("monotonic_sequence_required") is True, "sequence_control_missing", reasons)
    _require(transport.get("expiry_required") is True, "expiry_control_missing", reasons)
    _require(transport.get("replay_rejection_required") is True, "replay_control_missing", reasons)

    _require(authority.get("francis_core_authoritative") is True, "core_authority_missing", reasons)
    _require(authority.get("adapter_read_only") is True, "adapter_read_only_missing", reasons)
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        _require(authority.get(field) is False, f"{field}_drift", reasons)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return PresenceEnvelopeValidation(
        ok=not unique_reasons,
        status="accepted" if not unique_reasons else "rejected",
        reasons=unique_reasons,
        adapter_id=adapter_id,
        session_id=session_id,
        sequence=sequence,
        expired=expired,
        replayed=replayed,
        digest_valid=digest_valid,
    )


class PresenceReplayGuard:
    """Process-local monotonic sequence guard; durable reconnect state remains future work."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._last_sequences: dict[tuple[str, str], int] = {}

    def accept(
        self,
        envelope: Mapping[str, Any] | None,
        *,
        now: str | datetime | None = None,
        expected_adapter_id: str = "",
        expected_session_id: str = "",
    ) -> PresenceEnvelopeValidation:
        adapter = _mapping(_mapping(envelope).get("adapter"))
        adapter_id = _text(adapter.get("id"), limit=160)
        session_id = _text(adapter.get("session_id"), limit=160)
        key = (adapter_id, session_id)
        with self._lock:
            last_sequence = self._last_sequences.get(key, 0)
            result = validate_presence_transport_envelope(
                envelope,
                now=now,
                expected_adapter_id=expected_adapter_id,
                expected_session_id=expected_session_id,
                last_sequence=last_sequence,
            )
            if result.ok:
                self._last_sequences[key] = result.sequence
            return result

    def last_sequence(self, *, adapter_id: str, session_id: str) -> int:
        key = (_contract_id(adapter_id), _contract_id(session_id))
        with self._lock:
            return self._last_sequences.get(key, 0)

    def describe(self) -> dict[str, Any]:
        with self._lock:
            tracked_session_count = len(self._last_sequences)
        return {
            "kind": "francis.grounded_presence.process_local_replay_guard",
            "tracked_session_count": tracked_session_count,
            "durable": False,
            "local_only": True,
            "writes_memory": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


def _validate_payload_identity(payload: Mapping[str, Any]) -> None:
    if payload.get("kind") != GROUNDED_PRESENCE_KIND:
        raise ValueError("grounded_presence_payload_kind_invalid")
    if payload.get("schema_version") != GROUNDED_PRESENCE_SCHEMA_VERSION:
        raise ValueError("grounded_presence_payload_schema_version_invalid")


def _payload_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _envelope_id(
    *,
    adapter_id: str,
    session_id: str,
    sequence: int,
    issued_at: datetime,
    payload_digest: str,
) -> str:
    seed = "|".join((adapter_id, session_id, str(sequence), issued_at.isoformat(), payload_digest))
    return f"gpe_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _bounded_ttl_ms(value: Any) -> int:
    ttl_ms = _positive_int(value)
    if ttl_ms > GROUNDED_PRESENCE_TRANSPORT_MAX_TTL_MS:
        raise ValueError("grounded_presence_transport_ttl_exceeds_maximum")
    return ttl_ms


def _positive_int(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError("positive_integer_required")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("positive_integer_required") from exc
    if parsed <= 0:
        raise ValueError("positive_integer_required")
    return parsed


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _contract_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, *, limit: int = 240) -> str:
    if value is None:
        return ""
    return str(value).strip()[:limit]


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
