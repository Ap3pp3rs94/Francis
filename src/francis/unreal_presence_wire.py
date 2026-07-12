from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import secrets
from base64 import b64decode
from binascii import Error as BinasciiError
from copy import deepcopy
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Mapping


PRESENCE_IPC_MESSAGE_KIND = "francis.grounded_presence.ipc_message"
PRESENCE_IPC_MESSAGE_SCHEMA_VERSION = "francis.grounded_presence.ipc_message.v1"
PRESENCE_IPC_MESSAGE_SCHEMA_PATH = "schemas/grounded_presence_ipc_message.schema.json"
PRESENCE_DELIVERY_ACK_KIND = "francis.grounded_presence.delivery_ack"
PRESENCE_DELIVERY_ACK_SCHEMA_VERSION = "francis.grounded_presence.delivery_ack.v1"
PRESENCE_DELIVERY_ACK_SCHEMA_PATH = "schemas/grounded_presence_delivery_ack.schema.json"
PRESENCE_RENDER_CHANNEL = "francis.presence.render.v1"
PRESENCE_RENDER_ACK_CHANNEL = "francis.presence.render.ack.v1"
PRESENCE_INTENT_CHANNEL = "francis.presence.intent.v1"
PRESENCE_IPC_MAX_TTL_MS = 5_000
PRESENCE_IPC_MIN_SECRET_BYTES = 32
PRESENCE_IPC_MAX_SECRET_BYTES = 128
PRESENCE_IPC_KEY_ID_ENV = "FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID"
PRESENCE_IPC_KEY_B64_ENV = "FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64"


@dataclass(frozen=True, slots=True)
class PresenceIpcMessageValidation:
    ok: bool
    status: str
    reasons: tuple[str, ...]
    message_id: str
    key_id: str
    authenticated: bool
    digest_valid: bool
    expired: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reasons": list(self.reasons),
            "message_id": self.message_id,
            "key_id": self.key_id,
            "authenticated": self.authenticated,
            "digest_valid": self.digest_valid,
            "expired": self.expired,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


@dataclass(frozen=True, slots=True)
class PresenceDeliveryAckValidation:
    ok: bool
    status: str
    reasons: tuple[str, ...]
    ack_id: str
    consumer_status: str
    durable_deduplication: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "status": self.status,
            "reasons": list(self.reasons),
            "ack_id": self.ack_id,
            "consumer_status": self.consumer_status,
            "durable_deduplication": self.durable_deduplication,
            "render_applied": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


class PresenceIpcAuthenticator:
    """HMAC boundary for local Core/renderer messages; secret material is never exposed."""

    def __init__(self, *, key_id: str, secret: bytes, source: str = "injected") -> None:
        normalized_key_id = _contract_id(key_id)
        if not normalized_key_id:
            raise ValueError("presence_ipc_auth_key_id_invalid")
        if (
            not isinstance(secret, bytes)
            or not PRESENCE_IPC_MIN_SECRET_BYTES <= len(secret) <= PRESENCE_IPC_MAX_SECRET_BYTES
        ):
            raise ValueError("presence_ipc_auth_secret_invalid")
        if source not in {"injected", "process_environment"}:
            raise ValueError("presence_ipc_auth_source_invalid")
        self.key_id = normalized_key_id
        self._secret = bytes(secret)
        self._source = source

    @classmethod
    def from_environment(
        cls,
        environ: Mapping[str, str] | None = None,
    ) -> PresenceIpcAuthenticator:
        values = os.environ if environ is None else environ
        key_id = str(values.get(PRESENCE_IPC_KEY_ID_ENV) or "").strip()
        encoded_secret = str(values.get(PRESENCE_IPC_KEY_B64_ENV) or "").strip()
        if not key_id:
            raise ValueError("presence_ipc_auth_key_id_missing")
        if not encoded_secret:
            raise ValueError("presence_ipc_auth_secret_missing")
        try:
            secret = b64decode(encoded_secret, validate=True)
        except (BinasciiError, ValueError) as exc:
            raise ValueError("presence_ipc_auth_secret_encoding_invalid") from exc
        return cls(key_id=key_id, secret=secret, source="process_environment")

    def describe(self) -> dict[str, Any]:
        return {
            "kind": "francis.grounded_presence.ipc_authenticator",
            "status": "configured",
            "algorithm": "hmac-sha256",
            "key_id": self.key_id,
            "source": self._source,
            "secret_present": True,
            "secret_exposed": False,
            "local_only": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }

    def sign(
        self,
        payload: Mapping[str, Any],
        *,
        channel: str,
        direction: str,
        issued_at: str | datetime | None = None,
        ttl_ms: int = 2_000,
        nonce: str | None = None,
    ) -> dict[str, Any]:
        normalized_channel = _contract_id(channel)
        if normalized_channel not in {PRESENCE_RENDER_CHANNEL, PRESENCE_RENDER_ACK_CHANNEL, PRESENCE_INTENT_CHANNEL}:
            raise ValueError("presence_ipc_channel_invalid")
        if direction not in {"francis_core_to_unreal", "unreal_to_francis_core"}:
            raise ValueError("presence_ipc_direction_invalid")
        normalized_ttl_ms = _bounded_ttl(ttl_ms)
        issued_dt = _parse_datetime(issued_at)
        if issued_at is not None and issued_dt is None:
            raise ValueError("presence_ipc_issued_at_invalid")
        issued_dt = issued_dt or datetime.now(UTC)
        normalized_nonce = str(nonce or secrets.token_hex(16)).strip().lower()
        if len(normalized_nonce) != 32 or any(character not in "0123456789abcdef" for character in normalized_nonce):
            raise ValueError("presence_ipc_nonce_invalid")
        payload_copy = deepcopy(dict(payload))
        payload_digest = _payload_digest(payload_copy)
        message_id = _message_id(
            key_id=self.key_id,
            channel=normalized_channel,
            direction=direction,
            nonce=normalized_nonce,
            issued_at=issued_dt,
            payload_digest=payload_digest,
        )
        message: dict[str, Any] = {
            "kind": PRESENCE_IPC_MESSAGE_KIND,
            "schema_version": PRESENCE_IPC_MESSAGE_SCHEMA_VERSION,
            "schema_path": PRESENCE_IPC_MESSAGE_SCHEMA_PATH,
            "message_id": message_id,
            "channel": normalized_channel,
            "direction": direction,
            "issued_at": issued_dt.isoformat(),
            "expires_at": (issued_dt + timedelta(milliseconds=normalized_ttl_ms)).isoformat(),
            "ttl_ms": normalized_ttl_ms,
            "nonce": normalized_nonce,
            "integrity": {
                "algorithm": "sha256",
                "canonicalization": "json_sort_keys_compact_utf8",
                "payload_digest": payload_digest,
            },
            "authentication": {
                "algorithm": "hmac-sha256",
                "key_id": self.key_id,
                "signature": "",
            },
            "payload": payload_copy,
            "authority": _authority_boundary(),
        }
        message["authentication"]["signature"] = self._signature(message)
        return message

    def validate(
        self,
        message: Mapping[str, Any] | None,
        *,
        expected_channel: str,
        expected_direction: str,
        now: str | datetime | None = None,
    ) -> PresenceIpcMessageValidation:
        payload = _mapping(message)
        integrity = _mapping(payload.get("integrity"))
        authentication = _mapping(payload.get("authentication"))
        authority = _mapping(payload.get("authority"))
        embedded_payload = _mapping(payload.get("payload"))
        reasons: list[str] = []
        message_id = _safe_id(payload.get("message_id"), limit=64)
        key_id = _contract_id(authentication.get("key_id"))

        _require(payload.get("kind") == PRESENCE_IPC_MESSAGE_KIND, "kind_invalid", reasons)
        _require(
            payload.get("schema_version") == PRESENCE_IPC_MESSAGE_SCHEMA_VERSION, "schema_version_invalid", reasons
        )
        _require(payload.get("schema_path") == PRESENCE_IPC_MESSAGE_SCHEMA_PATH, "schema_path_invalid", reasons)
        _require(bool(message_id), "message_id_invalid", reasons)
        _require(payload.get("channel") == expected_channel, "channel_mismatch", reasons)
        _require(payload.get("direction") == expected_direction, "direction_mismatch", reasons)
        _require(authentication.get("algorithm") == "hmac-sha256", "authentication_algorithm_invalid", reasons)
        _require(key_id == self.key_id, "authentication_key_mismatch", reasons)
        signature = str(authentication.get("signature") or "").strip().lower()
        expected_signature = self._signature(payload) if payload else ""
        authenticated = (
            len(signature) == 64 and key_id == self.key_id and hmac.compare_digest(signature, expected_signature)
        )
        _require(authenticated, "authentication_signature_invalid", reasons)

        now_dt = _parse_datetime(now) or datetime.now(UTC)
        issued_dt = _parse_datetime(payload.get("issued_at"))
        expires_dt = _parse_datetime(payload.get("expires_at"))
        ttl_ms = _nonnegative_int(payload.get("ttl_ms"))
        _require(issued_dt is not None, "issued_at_invalid", reasons)
        _require(expires_dt is not None, "expires_at_invalid", reasons)
        _require(0 < ttl_ms <= PRESENCE_IPC_MAX_TTL_MS, "ttl_invalid", reasons)
        if issued_dt is not None:
            _require((issued_dt - now_dt).total_seconds() <= 5, "issued_at_in_future", reasons)
        if issued_dt is not None and expires_dt is not None:
            actual_ttl_ms = round((expires_dt - issued_dt).total_seconds() * 1_000)
            _require(actual_ttl_ms == ttl_ms, "ttl_mismatch", reasons)
        expired = expires_dt is not None and now_dt >= expires_dt
        _require(not expired, "message_expired", reasons)

        nonce = str(payload.get("nonce") or "").strip().lower()
        _require(
            len(nonce) == 32 and all(character in "0123456789abcdef" for character in nonce),
            "nonce_invalid",
            reasons,
        )
        _require(integrity.get("algorithm") == "sha256", "integrity_algorithm_invalid", reasons)
        _require(
            integrity.get("canonicalization") == "json_sort_keys_compact_utf8",
            "integrity_canonicalization_invalid",
            reasons,
        )
        expected_digest = str(integrity.get("payload_digest") or "").strip().lower()
        try:
            actual_digest = _payload_digest(embedded_payload) if embedded_payload else ""
        except (TypeError, ValueError):
            actual_digest = ""
        digest_valid = len(expected_digest) == 64 and hmac.compare_digest(expected_digest, actual_digest)
        _require(digest_valid, "payload_digest_mismatch", reasons)
        if key_id and issued_dt is not None and nonce and expected_digest:
            expected_message_id = _message_id(
                key_id=key_id,
                channel=str(payload.get("channel") or ""),
                direction=str(payload.get("direction") or ""),
                nonce=nonce,
                issued_at=issued_dt,
                payload_digest=expected_digest,
            )
            _require(message_id == expected_message_id, "message_id_mismatch", reasons)
        _validate_authority(authority, reasons)

        unique_reasons = tuple(dict.fromkeys(reasons))
        return PresenceIpcMessageValidation(
            ok=not unique_reasons,
            status="accepted" if not unique_reasons else "rejected",
            reasons=unique_reasons,
            message_id=message_id,
            key_id=key_id,
            authenticated=authenticated,
            digest_valid=digest_valid,
            expired=expired,
        )

    def _signature(self, message: Mapping[str, Any]) -> str:
        canonical_message = deepcopy(dict(message))
        authentication = _mapping(canonical_message.get("authentication"))
        authentication["signature"] = ""
        canonical_message["authentication"] = authentication
        canonical = json.dumps(
            canonical_message,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
            allow_nan=False,
        ).encode("utf-8")
        return hmac.new(self._secret, canonical, hashlib.sha256).hexdigest()


def build_presence_delivery_ack(
    *,
    request_message: Mapping[str, Any],
    endpoint_id: str,
    consumer_status: str,
    acknowledged_at: str | datetime | None = None,
) -> dict[str, Any]:
    if consumer_status not in {"accepted_for_render", "duplicate_already_accepted"}:
        raise ValueError("presence_delivery_ack_consumer_status_invalid")
    request = _mapping(request_message)
    envelope = _mapping(request.get("payload"))
    adapter = _mapping(envelope.get("adapter"))
    integrity = _mapping(envelope.get("integrity"))
    normalized_endpoint_id = _required_id(endpoint_id, "presence_delivery_ack_endpoint_id_invalid")
    message_id = _required_id(request.get("message_id"), "presence_delivery_ack_message_id_invalid")
    envelope_id = _required_id(envelope.get("envelope_id"), "presence_delivery_ack_envelope_id_invalid")
    adapter_id = _required_id(adapter.get("id"), "presence_delivery_ack_adapter_id_invalid")
    session_id = _required_id(adapter.get("session_id"), "presence_delivery_ack_session_id_invalid")
    sequence = _positive_int(envelope.get("sequence"), "presence_delivery_ack_sequence_invalid")
    payload_digest = str(integrity.get("payload_digest") or "").strip().lower()
    if len(payload_digest) != 64 or any(character not in "0123456789abcdef" for character in payload_digest):
        raise ValueError("presence_delivery_ack_payload_digest_invalid")
    acknowledged_dt = _parse_datetime(acknowledged_at)
    if acknowledged_at is not None and acknowledged_dt is None:
        raise ValueError("presence_delivery_ack_timestamp_invalid")
    acknowledged_dt = acknowledged_dt or datetime.now(UTC)
    ack_id = _ack_id(
        message_id=message_id,
        envelope_id=envelope_id,
        endpoint_id=normalized_endpoint_id,
        consumer_status=consumer_status,
    )
    return {
        "kind": PRESENCE_DELIVERY_ACK_KIND,
        "schema_version": PRESENCE_DELIVERY_ACK_SCHEMA_VERSION,
        "schema_path": PRESENCE_DELIVERY_ACK_SCHEMA_PATH,
        "ack_id": ack_id,
        "acknowledged_at": acknowledged_dt.isoformat(),
        "request": {
            "message_id": message_id,
            "envelope_id": envelope_id,
            "adapter_id": adapter_id,
            "session_id": session_id,
            "sequence": sequence,
            "endpoint_id": normalized_endpoint_id,
            "payload_digest": payload_digest,
        },
        "consumer": {
            "status": consumer_status,
            "durable_deduplication": True,
            "sequence_committed": True,
            "render_application_status": "queued_not_proven",
            "payload_persisted": False,
        },
        "authority": _authority_boundary(),
    }


def validate_presence_delivery_ack(
    ack: Mapping[str, Any] | None,
    *,
    request_message: Mapping[str, Any],
    endpoint_id: str,
) -> PresenceDeliveryAckValidation:
    payload = _mapping(ack)
    request = _mapping(payload.get("request"))
    consumer = _mapping(payload.get("consumer"))
    authority = _mapping(payload.get("authority"))
    expected_message = _mapping(request_message)
    envelope = _mapping(expected_message.get("payload"))
    adapter = _mapping(envelope.get("adapter"))
    integrity = _mapping(envelope.get("integrity"))
    reasons: list[str] = []
    ack_id = _safe_id(payload.get("ack_id"), limit=64)
    consumer_status = str(consumer.get("status") or "")
    normalized_endpoint_id = _contract_id(endpoint_id)

    _require(payload.get("kind") == PRESENCE_DELIVERY_ACK_KIND, "ack_kind_invalid", reasons)
    _require(
        payload.get("schema_version") == PRESENCE_DELIVERY_ACK_SCHEMA_VERSION, "ack_schema_version_invalid", reasons
    )
    _require(payload.get("schema_path") == PRESENCE_DELIVERY_ACK_SCHEMA_PATH, "ack_schema_path_invalid", reasons)
    _require(_parse_datetime(payload.get("acknowledged_at")) is not None, "ack_timestamp_invalid", reasons)
    _require(request.get("message_id") == expected_message.get("message_id"), "ack_message_id_mismatch", reasons)
    _require(request.get("envelope_id") == envelope.get("envelope_id"), "ack_envelope_id_mismatch", reasons)
    _require(request.get("adapter_id") == adapter.get("id"), "ack_adapter_id_mismatch", reasons)
    _require(request.get("session_id") == adapter.get("session_id"), "ack_session_id_mismatch", reasons)
    _require(
        _nonnegative_int(request.get("sequence")) == _nonnegative_int(envelope.get("sequence")),
        "ack_sequence_mismatch",
        reasons,
    )
    _require(request.get("endpoint_id") == normalized_endpoint_id, "ack_endpoint_id_mismatch", reasons)
    _require(request.get("payload_digest") == integrity.get("payload_digest"), "ack_payload_digest_mismatch", reasons)
    _require(
        consumer_status in {"accepted_for_render", "duplicate_already_accepted"}, "ack_consumer_status_invalid", reasons
    )
    durable_deduplication = consumer.get("durable_deduplication") is True
    _require(durable_deduplication, "ack_durable_deduplication_missing", reasons)
    _require(consumer.get("sequence_committed") is True, "ack_sequence_commit_missing", reasons)
    _require(consumer.get("render_application_status") == "queued_not_proven", "ack_render_status_invalid", reasons)
    _require(consumer.get("payload_persisted") is False, "ack_payload_persistence_drift", reasons)
    expected_ack_id = ""
    if request.get("message_id") and request.get("envelope_id") and normalized_endpoint_id and consumer_status:
        expected_ack_id = _ack_id(
            message_id=str(request.get("message_id")),
            envelope_id=str(request.get("envelope_id")),
            endpoint_id=normalized_endpoint_id,
            consumer_status=consumer_status,
        )
    _require(bool(ack_id) and ack_id == expected_ack_id, "ack_id_mismatch", reasons)
    _validate_authority(authority, reasons)
    unique_reasons = tuple(dict.fromkeys(reasons))
    return PresenceDeliveryAckValidation(
        ok=not unique_reasons,
        status="accepted" if not unique_reasons else "rejected",
        reasons=unique_reasons,
        ack_id=ack_id,
        consumer_status=consumer_status,
        durable_deduplication=durable_deduplication,
    )


def _payload_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _message_id(
    *,
    key_id: str,
    channel: str,
    direction: str,
    nonce: str,
    issued_at: datetime,
    payload_digest: str,
) -> str:
    seed = "|".join((key_id, channel, direction, nonce, issued_at.isoformat(), payload_digest))
    return f"gpm_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _ack_id(*, message_id: str, envelope_id: str, endpoint_id: str, consumer_status: str) -> str:
    seed = "|".join((message_id, envelope_id, endpoint_id, consumer_status))
    return f"gpa_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:32]}"


def _authority_boundary() -> dict[str, bool]:
    return {
        "francis_core_authoritative": True,
        "grants_execution_authority": False,
        "grants_desktop_authority": False,
        "grants_network_authority": False,
        "grants_memory_write_authority": False,
        "grants_approval_authority": False,
    }


def _validate_authority(authority: Mapping[str, Any], reasons: list[str]) -> None:
    _require(authority.get("francis_core_authoritative") is True, "core_authority_missing", reasons)
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        _require(authority.get(field) is False, f"{field}_drift", reasons)


def _bounded_ttl(value: Any) -> int:
    ttl_ms = _positive_int(value, "presence_ipc_ttl_invalid")
    if ttl_ms > PRESENCE_IPC_MAX_TTL_MS:
        raise ValueError("presence_ipc_ttl_invalid")
    return ttl_ms


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


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _contract_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _required_id(value: Any, error: str) -> str:
    normalized = _contract_id(value)
    if not normalized:
        raise ValueError(error)
    return normalized


def _safe_id(value: Any, *, limit: int) -> str:
    text = str(value or "").strip()[:limit]
    return text if text and all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


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
        text = str(value or "").strip()
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
