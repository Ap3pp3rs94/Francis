from __future__ import annotations

import hashlib
import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol

from francis.kernel.paths import data_dir
from francis.unreal_presence_wire import validate_presence_delivery_ack


PRESENCE_DELIVERY_RECEIPT_KIND = "francis.grounded_presence.delivery_receipt"
PRESENCE_DELIVERY_RECEIPT_SCHEMA_VERSION = "francis.grounded_presence.delivery_receipt.v1"
PRESENCE_DELIVERY_RECEIPT_SCHEMA_PATH = "schemas/grounded_presence_delivery_receipt.schema.json"
PRESENCE_DELIVERY_RECEIPT_MAX_BYTES = 64 * 1024
PRESENCE_DELIVERY_JOURNAL_KIND = "francis.grounded_presence.delivery_journal"
PRESENCE_DELIVERY_JOURNAL_SCHEMA_VERSION = "francis.grounded_presence.delivery_journal.v1"
PRESENCE_DELIVERY_JOURNAL_SCHEMA_PATH = "schemas/grounded_presence_delivery_journal.schema.json"
PRESENCE_DELIVERY_JOURNAL_MAX_BYTES = 16 * 1024
PRESENCE_DELIVERY_ATTEMPT_KIND = "francis.grounded_presence.delivery_attempt"
PRESENCE_DELIVERY_ATTEMPT_SCHEMA_VERSION = "francis.grounded_presence.delivery_attempt.v1"
PRESENCE_DELIVERY_ATTEMPT_SCHEMA_PATH = "schemas/grounded_presence_delivery_attempt.schema.json"
PRESENCE_DELIVERY_ATTEMPT_MAX_BYTES = 16 * 1024
PRESENCE_DELIVERY_MAX_RECORDED_BYTES = 256 * 1024 + 4


class PresenceDeliveryReceiptStore(Protocol):
    def has_delivery(self, *, envelope_id: str, endpoint_id: str) -> bool: ...

    def highest_delivered_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        endpoint_id: str,
        refresh: bool = False,
    ) -> int: ...

    def write(self, receipt: Mapping[str, Any]) -> Path: ...

    def read_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]: ...

    def write_pending_delivery(self, journal: Mapping[str, Any]) -> Path: ...

    def clear_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None: ...

    def read_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]: ...

    def write_pending_attempt(self, attempt: Mapping[str, Any]) -> Path: ...

    def clear_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None: ...


class LocalJsonPresenceDeliveryReceiptStore:
    """Atomic local receipt store that persists metadata only, never renderer payloads."""

    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else data_dir() / "receipts" / "grounded_presence" / "deliveries"
        self._lock = Lock()
        self._sequence_cache: dict[tuple[str, str, str], int] = {}

    def has_delivery(self, *, envelope_id: str, endpoint_id: str) -> bool:
        with self._lock:
            receipt_id = presence_delivery_receipt_id(envelope_id=envelope_id, endpoint_id=endpoint_id)
            path = self._receipt_path(receipt_id)
            if not path.is_file():
                return False
            receipt = _read_delivery_receipt(path)
            delivery = _mapping(receipt.get("delivery"))
            if delivery.get("envelope_id") != _safe_id(envelope_id) or delivery.get("endpoint_id") != _safe_id(
                endpoint_id
            ):
                raise ValueError("presence_delivery_receipt_identity_conflict")
            return delivery.get("status") == "delivered"

    def highest_delivered_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        endpoint_id: str,
        refresh: bool = False,
    ) -> int:
        normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
        normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
        normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
        key = (normalized_adapter_id, normalized_session_id, normalized_endpoint_id)
        with self._lock:
            if refresh or key not in self._sequence_cache:
                self._sequence_cache[key] = self._scan_highest_sequence(*key)
            return self._sequence_cache[key]

    def write(self, receipt: Mapping[str, Any]) -> Path:
        payload = dict(receipt)
        if payload.get("kind") != PRESENCE_DELIVERY_RECEIPT_KIND:
            raise ValueError("presence_delivery_receipt_kind_invalid")
        receipt_id = _safe_id(payload.get("receipt_id"))
        if not receipt_id:
            raise ValueError("presence_delivery_receipt_id_invalid")
        with self._lock:
            path = self._receipt_path(receipt_id)
            self.root.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                if not _same_receipt_payload(_read_delivery_receipt(path), payload):
                    raise ValueError("presence_delivery_receipt_id_conflict")
                self._record_sequence(payload)
                return path
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            self._record_sequence(payload)
            return path

    def read_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]:
        normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
        normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
        normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
        with self._lock:
            path = self._pending_path(normalized_adapter_id, normalized_session_id, normalized_endpoint_id)
            if not path.is_file():
                return {}
            journal = _read_delivery_journal(path)
            delivery = _mapping(journal.get("delivery"))
            if (
                delivery.get("adapter_id") != normalized_adapter_id
                or delivery.get("session_id") != normalized_session_id
                or delivery.get("endpoint_id") != normalized_endpoint_id
            ):
                raise ValueError("presence_delivery_journal_identity_conflict")
            return journal

    def write_pending_delivery(self, journal: Mapping[str, Any]) -> Path:
        payload = dict(journal)
        if payload.get("kind") != PRESENCE_DELIVERY_JOURNAL_KIND:
            raise ValueError("presence_delivery_journal_kind_invalid")
        delivery = _mapping(payload.get("delivery"))
        adapter_id = _required_safe_id(delivery.get("adapter_id"), "presence_delivery_adapter_id_invalid")
        session_id = _required_safe_id(delivery.get("session_id"), "presence_delivery_session_id_invalid")
        endpoint_id = _required_safe_id(delivery.get("endpoint_id"), "presence_delivery_endpoint_id_invalid")
        _validate_pending_delivery(payload)
        with self._lock:
            path = self._pending_path(adapter_id, session_id, endpoint_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                if not _same_receipt_payload(_read_delivery_journal(path), payload):
                    raise ValueError("presence_delivery_journal_conflict")
                return path
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return path

    def clear_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None:
        normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
        normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
        normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
        with self._lock:
            path = self._pending_path(normalized_adapter_id, normalized_session_id, normalized_endpoint_id)
            if path.is_file():
                journal = _read_delivery_journal(path)
                delivery = _mapping(journal.get("delivery"))
                if (
                    delivery.get("adapter_id") != normalized_adapter_id
                    or delivery.get("session_id") != normalized_session_id
                    or delivery.get("endpoint_id") != normalized_endpoint_id
                ):
                    raise ValueError("presence_delivery_journal_identity_conflict")
                path.unlink()

    def read_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]:
        normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
        normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
        normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
        with self._lock:
            path = self._attempt_path(normalized_adapter_id, normalized_session_id, normalized_endpoint_id)
            if not path.is_file():
                return {}
            attempt = _read_delivery_attempt(path)
            delivery = _mapping(attempt.get("delivery"))
            if (
                delivery.get("adapter_id") != normalized_adapter_id
                or delivery.get("session_id") != normalized_session_id
                or delivery.get("endpoint_id") != normalized_endpoint_id
            ):
                raise ValueError("presence_delivery_attempt_identity_conflict")
            return attempt

    def write_pending_attempt(self, attempt: Mapping[str, Any]) -> Path:
        payload = dict(attempt)
        if payload.get("kind") != PRESENCE_DELIVERY_ATTEMPT_KIND:
            raise ValueError("presence_delivery_attempt_kind_invalid")
        delivery = _mapping(payload.get("delivery"))
        adapter_id = _required_safe_id(delivery.get("adapter_id"), "presence_delivery_adapter_id_invalid")
        session_id = _required_safe_id(delivery.get("session_id"), "presence_delivery_session_id_invalid")
        endpoint_id = _required_safe_id(delivery.get("endpoint_id"), "presence_delivery_endpoint_id_invalid")
        _validate_pending_attempt(payload)
        with self._lock:
            path = self._attempt_path(adapter_id, session_id, endpoint_id)
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.is_file():
                if not _same_receipt_payload(_read_delivery_attempt(path), payload):
                    raise ValueError("presence_delivery_attempt_conflict")
                return path
            temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
            try:
                temporary.write_text(
                    json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n",
                    encoding="utf-8",
                )
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
            return path

    def clear_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None:
        normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
        normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
        normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
        with self._lock:
            path = self._attempt_path(normalized_adapter_id, normalized_session_id, normalized_endpoint_id)
            if path.is_file():
                attempt = _read_delivery_attempt(path)
                delivery = _mapping(attempt.get("delivery"))
                if (
                    delivery.get("adapter_id") != normalized_adapter_id
                    or delivery.get("session_id") != normalized_session_id
                    or delivery.get("endpoint_id") != normalized_endpoint_id
                ):
                    raise ValueError("presence_delivery_attempt_identity_conflict")
                path.unlink()

    def _receipt_path(self, receipt_id: str) -> Path:
        safe_id = _safe_id(receipt_id)
        if not safe_id:
            raise ValueError("presence_delivery_receipt_id_invalid")
        return self.root / f"{safe_id}.json"

    def _pending_path(self, adapter_id: str, session_id: str, endpoint_id: str) -> Path:
        journal_id = presence_delivery_journal_id(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )
        return self.root / "pending" / f"{journal_id}.json"

    def _attempt_path(self, adapter_id: str, session_id: str, endpoint_id: str) -> Path:
        attempt_id = presence_delivery_attempt_id(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )
        return self.root / "pending_attempt" / f"{attempt_id}.json"

    def _record_sequence(self, receipt: Mapping[str, Any]) -> None:
        delivery = _mapping(receipt.get("delivery"))
        key = (
            _required_safe_id(delivery.get("adapter_id"), "presence_delivery_adapter_id_invalid"),
            _required_safe_id(delivery.get("session_id"), "presence_delivery_session_id_invalid"),
            _required_safe_id(delivery.get("endpoint_id"), "presence_delivery_endpoint_id_invalid"),
        )
        sequence = _positive_int(delivery.get("sequence"))
        if key not in self._sequence_cache:
            self._sequence_cache[key] = self._scan_highest_sequence(*key)
        self._sequence_cache[key] = max(self._sequence_cache[key], sequence)

    def _scan_highest_sequence(self, adapter_id: str, session_id: str, endpoint_id: str) -> int:
        if not self.root.is_dir():
            return 0
        highest = 0
        for path in self.root.glob("gpd_*.json"):
            receipt = _read_delivery_receipt(path)
            delivery = _mapping(receipt.get("delivery"))
            if (
                delivery.get("adapter_id") != adapter_id
                or delivery.get("session_id") != session_id
                or delivery.get("endpoint_id") != endpoint_id
            ):
                continue
            if delivery.get("status") != "delivered":
                raise ValueError("presence_delivery_receipt_status_invalid")
            highest = max(highest, _positive_int(delivery.get("sequence")))
        return highest


def build_presence_delivery_receipt(
    *,
    envelope: Mapping[str, Any],
    endpoint_id: str,
    bytes_written: int,
    request_message: Mapping[str, Any] | None = None,
    acknowledgement: Mapping[str, Any] | None = None,
    acknowledgement_evidence: Mapping[str, Any] | None = None,
    recorded_at: str | datetime | None = None,
) -> dict[str, Any]:
    envelope_map = _mapping(envelope)
    adapter = _mapping(envelope_map.get("adapter"))
    transport = _mapping(envelope_map.get("transport"))
    integrity = _mapping(envelope_map.get("integrity"))
    payload = _mapping(envelope_map.get("payload"))
    evidence = _mapping(payload.get("evidence"))
    correlation = _mapping(evidence.get("correlation"))
    stage = _mapping(payload.get("stage"))
    envelope_id = _safe_id(envelope_map.get("envelope_id"))
    normalized_endpoint_id = _safe_id(endpoint_id)
    if not envelope_id:
        raise ValueError("presence_delivery_envelope_id_invalid")
    if not normalized_endpoint_id:
        raise ValueError("presence_delivery_endpoint_id_invalid")
    if transport.get("binding_status") != "windows_named_pipe":
        raise ValueError("presence_delivery_transport_not_bound")
    if transport.get("endpoint_id") != normalized_endpoint_id:
        raise ValueError("presence_delivery_endpoint_mismatch")
    if isinstance(bytes_written, bool) or not isinstance(bytes_written, int) or bytes_written <= 0:
        raise ValueError("presence_delivery_bytes_written_invalid")
    recorded_dt = _parse_datetime(recorded_at)
    if recorded_at is not None and recorded_dt is None:
        raise ValueError("presence_delivery_recorded_at_invalid")
    recorded_dt = recorded_dt or datetime.now(UTC)
    receipt_id = presence_delivery_receipt_id(
        envelope_id=envelope_id,
        endpoint_id=normalized_endpoint_id,
    )
    receipt_ids = [_safe_id(item) for item in correlation.get("receipt_ids", []) if _safe_id(item)]
    ack_evidence = _delivery_ack_evidence(
        envelope=envelope_map,
        endpoint_id=normalized_endpoint_id,
        request_message=request_message,
        acknowledgement=acknowledgement,
        acknowledgement_evidence=acknowledgement_evidence,
    )
    return {
        "kind": PRESENCE_DELIVERY_RECEIPT_KIND,
        "schema_version": PRESENCE_DELIVERY_RECEIPT_SCHEMA_VERSION,
        "schema_path": PRESENCE_DELIVERY_RECEIPT_SCHEMA_PATH,
        "receipt_id": receipt_id,
        "recorded_at": recorded_dt.isoformat(),
        "delivery": {
            "status": "delivered",
            "envelope_id": envelope_id,
            "channel": str(envelope_map.get("channel") or ""),
            "adapter_id": _safe_id(adapter.get("id")),
            "session_id": _safe_id(adapter.get("session_id")),
            "sequence": _positive_int(envelope_map.get("sequence")),
            "endpoint_id": normalized_endpoint_id,
            "transport": "windows_named_pipe",
            "bytes_written": bytes_written,
            "payload_digest": str(integrity.get("payload_digest") or ""),
            "issued_at": str(envelope_map.get("issued_at") or ""),
            "expires_at": str(envelope_map.get("expires_at") or ""),
            "message_id": ack_evidence["message_id"],
            "ack_id": ack_evidence["ack_id"],
            "consumer_status": ack_evidence["consumer_status"],
            "consumer_durable_deduplication": True,
        },
        "evidence": {
            "payload_kind": str(payload.get("kind") or ""),
            "payload_schema_version": str(payload.get("schema_version") or ""),
            "presence_stage_status": str(stage.get("status") or ""),
            "source_receipt_ids": list(dict.fromkeys(receipt_ids)),
            "payload_persisted": False,
        },
        "security": {
            "local_only": True,
            "remote_clients_rejected": True,
            "application_authenticated": True,
            "authentication_status": "hmac_sha256_signed_ack",
            "authentication_key_id": ack_evidence["authentication_key_id"],
            "acknowledgement_authenticated": True,
            "replay_posture": "cross_process_mutex_plus_durable_receipt_sequence_watermark",
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
            "render_application_not_proven_by_transport_ack",
        ],
    }


def build_presence_delivery_journal(
    *,
    envelope: Mapping[str, Any],
    endpoint_id: str,
    bytes_written: int,
    request_message: Mapping[str, Any] | None = None,
    acknowledgement: Mapping[str, Any] | None = None,
    acknowledgement_evidence: Mapping[str, Any] | None = None,
    recorded_at: str | datetime | None = None,
) -> dict[str, Any]:
    envelope_map = _mapping(envelope)
    adapter = _mapping(envelope_map.get("adapter"))
    transport = _mapping(envelope_map.get("transport"))
    integrity = _mapping(envelope_map.get("integrity"))
    normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
    if transport.get("binding_status") != "windows_named_pipe":
        raise ValueError("presence_delivery_transport_not_bound")
    if transport.get("endpoint_id") != normalized_endpoint_id:
        raise ValueError("presence_delivery_endpoint_mismatch")
    if isinstance(bytes_written, bool) or not isinstance(bytes_written, int) or bytes_written <= 0:
        raise ValueError("presence_delivery_bytes_written_invalid")
    recorded_dt = _parse_datetime(recorded_at)
    if recorded_at is not None and recorded_dt is None:
        raise ValueError("presence_delivery_recorded_at_invalid")
    recorded_dt = recorded_dt or datetime.now(UTC)
    adapter_id = _required_safe_id(adapter.get("id"), "presence_delivery_adapter_id_invalid")
    session_id = _required_safe_id(adapter.get("session_id"), "presence_delivery_session_id_invalid")
    envelope_id = _required_safe_id(envelope_map.get("envelope_id"), "presence_delivery_envelope_id_invalid")
    payload_digest = str(integrity.get("payload_digest") or "").strip().lower()
    if len(payload_digest) != 64 or any(character not in "0123456789abcdef" for character in payload_digest):
        raise ValueError("presence_delivery_payload_digest_invalid")
    ack_evidence = _delivery_ack_evidence(
        envelope=envelope_map,
        endpoint_id=normalized_endpoint_id,
        request_message=request_message,
        acknowledgement=acknowledgement,
        acknowledgement_evidence=acknowledgement_evidence,
    )
    journal = {
        "kind": PRESENCE_DELIVERY_JOURNAL_KIND,
        "schema_version": PRESENCE_DELIVERY_JOURNAL_SCHEMA_VERSION,
        "schema_path": PRESENCE_DELIVERY_JOURNAL_SCHEMA_PATH,
        "journal_id": presence_delivery_journal_id(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=normalized_endpoint_id,
        ),
        "recorded_at": recorded_dt.isoformat(),
        "delivery": {
            "state": "delivered_receipt_pending",
            "envelope_id": envelope_id,
            "adapter_id": adapter_id,
            "session_id": session_id,
            "sequence": _positive_int(envelope_map.get("sequence")),
            "endpoint_id": normalized_endpoint_id,
            "bytes_written": bytes_written,
            "payload_digest": payload_digest,
            "message_id": ack_evidence["message_id"],
            "ack_id": ack_evidence["ack_id"],
            "consumer_status": ack_evidence["consumer_status"],
            "authentication_key_id": ack_evidence["authentication_key_id"],
        },
        "persistence": {
            "payload_persisted": False,
            "receipt_pending": True,
            "safe_redelivery": True,
            "exact_envelope_retry_repairs_receipt": True,
            "consumer_durable_deduplication": True,
            "acknowledgement_authenticated": True,
        },
        "authority": {
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
    }
    _validate_pending_delivery(journal)
    return journal


def build_presence_delivery_attempt(
    *,
    envelope: Mapping[str, Any],
    endpoint_id: str,
    request_message: Mapping[str, Any],
    recorded_at: str | datetime | None = None,
) -> dict[str, Any]:
    envelope_map = _mapping(envelope)
    adapter = _mapping(envelope_map.get("adapter"))
    transport = _mapping(envelope_map.get("transport"))
    integrity = _mapping(envelope_map.get("integrity"))
    request = _mapping(request_message)
    authentication = _mapping(request.get("authentication"))
    normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
    if transport.get("binding_status") != "windows_named_pipe":
        raise ValueError("presence_delivery_transport_not_bound")
    if transport.get("endpoint_id") != normalized_endpoint_id:
        raise ValueError("presence_delivery_endpoint_mismatch")
    if _mapping(request.get("payload")) != envelope_map:
        raise ValueError("presence_delivery_request_envelope_mismatch")
    if authentication.get("algorithm") != "hmac-sha256":
        raise ValueError("presence_delivery_authentication_invalid")
    recorded_dt = _parse_datetime(recorded_at)
    if recorded_at is not None and recorded_dt is None:
        raise ValueError("presence_delivery_recorded_at_invalid")
    recorded_dt = recorded_dt or datetime.now(UTC)
    adapter_id = _required_safe_id(adapter.get("id"), "presence_delivery_adapter_id_invalid")
    session_id = _required_safe_id(adapter.get("session_id"), "presence_delivery_session_id_invalid")
    envelope_id = _required_safe_id(envelope_map.get("envelope_id"), "presence_delivery_envelope_id_invalid")
    payload_digest = str(integrity.get("payload_digest") or "").strip().lower()
    if len(payload_digest) != 64 or any(character not in "0123456789abcdef" for character in payload_digest):
        raise ValueError("presence_delivery_payload_digest_invalid")
    attempt = {
        "kind": PRESENCE_DELIVERY_ATTEMPT_KIND,
        "schema_version": PRESENCE_DELIVERY_ATTEMPT_SCHEMA_VERSION,
        "schema_path": PRESENCE_DELIVERY_ATTEMPT_SCHEMA_PATH,
        "attempt_id": presence_delivery_attempt_id(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=normalized_endpoint_id,
        ),
        "recorded_at": recorded_dt.isoformat(),
        "delivery": {
            "state": "delivery_attempt_pending",
            "envelope_id": envelope_id,
            "adapter_id": adapter_id,
            "session_id": session_id,
            "sequence": _positive_int(envelope_map.get("sequence")),
            "endpoint_id": normalized_endpoint_id,
            "payload_digest": payload_digest,
            "message_id": _required_safe_id(request.get("message_id"), "presence_delivery_message_id_invalid"),
            "authentication_key_id": _required_safe_id(
                authentication.get("key_id"),
                "presence_delivery_authentication_key_id_invalid",
            ),
        },
        "reconciliation": {
            "payload_persisted": False,
            "delivery_acknowledged": False,
            "receipt_written": False,
            "exact_envelope_required": True,
            "fresh_authenticated_wrapper_required": True,
            "consumer_durable_deduplication_required": True,
        },
        "authority": {
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
    }
    _validate_pending_attempt(attempt)
    return attempt


def presence_delivery_receipt_id(*, envelope_id: str, endpoint_id: str) -> str:
    normalized_envelope_id = _safe_id(envelope_id)
    normalized_endpoint_id = _safe_id(endpoint_id)
    if not normalized_envelope_id:
        raise ValueError("presence_delivery_envelope_id_invalid")
    if not normalized_endpoint_id:
        raise ValueError("presence_delivery_endpoint_id_invalid")
    digest = hashlib.sha256(f"{normalized_envelope_id}|{normalized_endpoint_id}".encode()).hexdigest()
    return f"gpd_{digest[:32]}"


def presence_delivery_journal_id(*, adapter_id: str, session_id: str, endpoint_id: str) -> str:
    normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
    normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
    normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
    digest = hashlib.sha256(
        f"{normalized_adapter_id}|{normalized_session_id}|{normalized_endpoint_id}".encode("utf-8")
    ).hexdigest()
    return f"gpp_{digest[:32]}"


def presence_delivery_attempt_id(*, adapter_id: str, session_id: str, endpoint_id: str) -> str:
    normalized_adapter_id = _required_safe_id(adapter_id, "presence_delivery_adapter_id_invalid")
    normalized_session_id = _required_safe_id(session_id, "presence_delivery_session_id_invalid")
    normalized_endpoint_id = _required_safe_id(endpoint_id, "presence_delivery_endpoint_id_invalid")
    digest = hashlib.sha256(
        f"{normalized_adapter_id}|{normalized_session_id}|{normalized_endpoint_id}".encode("utf-8")
    ).hexdigest()
    return f"gpt_{digest[:32]}"


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _required_safe_id(value: Any, error: str) -> str:
    normalized = _safe_id(value)
    if not normalized:
        raise ValueError(error)
    return normalized


def _read_delivery_receipt(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > PRESENCE_DELIVERY_RECEIPT_MAX_BYTES:
            raise ValueError("presence_delivery_receipt_oversized")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence_delivery_receipt_corrupt") from exc
    if not isinstance(payload, dict) or payload.get("kind") != PRESENCE_DELIVERY_RECEIPT_KIND:
        raise ValueError("presence_delivery_receipt_corrupt")
    return payload


def _read_delivery_journal(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > PRESENCE_DELIVERY_JOURNAL_MAX_BYTES:
            raise ValueError("presence_delivery_journal_oversized")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence_delivery_journal_corrupt") from exc
    if not isinstance(payload, dict):
        raise ValueError("presence_delivery_journal_corrupt")
    _validate_pending_delivery(payload)
    return payload


def _read_delivery_attempt(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > PRESENCE_DELIVERY_ATTEMPT_MAX_BYTES:
            raise ValueError("presence_delivery_attempt_oversized")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence_delivery_attempt_corrupt") from exc
    if not isinstance(payload, dict):
        raise ValueError("presence_delivery_attempt_corrupt")
    _validate_pending_attempt(payload)
    return payload


def _validate_pending_delivery(payload: Mapping[str, Any]) -> None:
    if payload.get("kind") != PRESENCE_DELIVERY_JOURNAL_KIND:
        raise ValueError("presence_delivery_journal_corrupt")
    if payload.get("schema_version") != PRESENCE_DELIVERY_JOURNAL_SCHEMA_VERSION:
        raise ValueError("presence_delivery_journal_corrupt")
    if payload.get("schema_path") != PRESENCE_DELIVERY_JOURNAL_SCHEMA_PATH:
        raise ValueError("presence_delivery_journal_corrupt")
    if _parse_datetime(payload.get("recorded_at")) is None:
        raise ValueError("presence_delivery_journal_recorded_at_invalid")
    delivery = _mapping(payload.get("delivery"))
    persistence = _mapping(payload.get("persistence"))
    authority = _mapping(payload.get("authority"))
    adapter_id = _required_safe_id(delivery.get("adapter_id"), "presence_delivery_adapter_id_invalid")
    session_id = _required_safe_id(delivery.get("session_id"), "presence_delivery_session_id_invalid")
    endpoint_id = _required_safe_id(delivery.get("endpoint_id"), "presence_delivery_endpoint_id_invalid")
    expected_journal_id = presence_delivery_journal_id(
        adapter_id=adapter_id,
        session_id=session_id,
        endpoint_id=endpoint_id,
    )
    if payload.get("journal_id") != expected_journal_id:
        raise ValueError("presence_delivery_journal_id_invalid")
    if delivery.get("state") != "delivered_receipt_pending":
        raise ValueError("presence_delivery_journal_state_invalid")
    _required_safe_id(delivery.get("envelope_id"), "presence_delivery_envelope_id_invalid")
    _positive_int(delivery.get("sequence"))
    if _positive_int(delivery.get("bytes_written")) > PRESENCE_DELIVERY_MAX_RECORDED_BYTES:
        raise ValueError("presence_delivery_bytes_written_invalid")
    payload_digest = str(delivery.get("payload_digest") or "").strip().lower()
    if len(payload_digest) != 64 or any(character not in "0123456789abcdef" for character in payload_digest):
        raise ValueError("presence_delivery_payload_digest_invalid")
    _required_safe_id(delivery.get("message_id"), "presence_delivery_message_id_invalid")
    _required_safe_id(delivery.get("ack_id"), "presence_delivery_ack_id_invalid")
    if delivery.get("consumer_status") not in {"accepted_for_render", "duplicate_already_accepted"}:
        raise ValueError("presence_delivery_consumer_status_invalid")
    _required_safe_id(
        delivery.get("authentication_key_id"),
        "presence_delivery_authentication_key_id_invalid",
    )
    if (
        persistence.get("payload_persisted") is not False
        or persistence.get("receipt_pending") is not True
        or persistence.get("safe_redelivery") is not True
        or persistence.get("exact_envelope_retry_repairs_receipt") is not True
        or persistence.get("consumer_durable_deduplication") is not True
        or persistence.get("acknowledgement_authenticated") is not True
    ):
        raise ValueError("presence_delivery_journal_persistence_invalid")
    if authority.get("francis_core_authoritative") is not True:
        raise ValueError("presence_delivery_journal_authority_invalid")
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        if authority.get(field) is not False:
            raise ValueError("presence_delivery_journal_authority_invalid")


def _validate_pending_attempt(payload: Mapping[str, Any]) -> None:
    if payload.get("kind") != PRESENCE_DELIVERY_ATTEMPT_KIND:
        raise ValueError("presence_delivery_attempt_corrupt")
    if payload.get("schema_version") != PRESENCE_DELIVERY_ATTEMPT_SCHEMA_VERSION:
        raise ValueError("presence_delivery_attempt_corrupt")
    if payload.get("schema_path") != PRESENCE_DELIVERY_ATTEMPT_SCHEMA_PATH:
        raise ValueError("presence_delivery_attempt_corrupt")
    if _parse_datetime(payload.get("recorded_at")) is None:
        raise ValueError("presence_delivery_attempt_recorded_at_invalid")
    delivery = _mapping(payload.get("delivery"))
    reconciliation = _mapping(payload.get("reconciliation"))
    authority = _mapping(payload.get("authority"))
    adapter_id = _required_safe_id(delivery.get("adapter_id"), "presence_delivery_adapter_id_invalid")
    session_id = _required_safe_id(delivery.get("session_id"), "presence_delivery_session_id_invalid")
    endpoint_id = _required_safe_id(delivery.get("endpoint_id"), "presence_delivery_endpoint_id_invalid")
    expected_attempt_id = presence_delivery_attempt_id(
        adapter_id=adapter_id,
        session_id=session_id,
        endpoint_id=endpoint_id,
    )
    if payload.get("attempt_id") != expected_attempt_id:
        raise ValueError("presence_delivery_attempt_id_invalid")
    if delivery.get("state") != "delivery_attempt_pending":
        raise ValueError("presence_delivery_attempt_state_invalid")
    _required_safe_id(delivery.get("envelope_id"), "presence_delivery_envelope_id_invalid")
    _positive_int(delivery.get("sequence"))
    payload_digest = str(delivery.get("payload_digest") or "").strip().lower()
    if len(payload_digest) != 64 or any(character not in "0123456789abcdef" for character in payload_digest):
        raise ValueError("presence_delivery_payload_digest_invalid")
    _required_safe_id(delivery.get("message_id"), "presence_delivery_message_id_invalid")
    _required_safe_id(
        delivery.get("authentication_key_id"),
        "presence_delivery_authentication_key_id_invalid",
    )
    if (
        reconciliation.get("payload_persisted") is not False
        or reconciliation.get("delivery_acknowledged") is not False
        or reconciliation.get("receipt_written") is not False
        or reconciliation.get("exact_envelope_required") is not True
        or reconciliation.get("fresh_authenticated_wrapper_required") is not True
        or reconciliation.get("consumer_durable_deduplication_required") is not True
    ):
        raise ValueError("presence_delivery_attempt_reconciliation_invalid")
    if authority.get("francis_core_authoritative") is not True:
        raise ValueError("presence_delivery_attempt_authority_invalid")
    for field in (
        "grants_execution_authority",
        "grants_desktop_authority",
        "grants_network_authority",
        "grants_memory_write_authority",
        "grants_approval_authority",
    ):
        if authority.get(field) is not False:
            raise ValueError("presence_delivery_attempt_authority_invalid")


def _delivery_ack_evidence(
    *,
    envelope: Mapping[str, Any],
    endpoint_id: str,
    request_message: Mapping[str, Any] | None,
    acknowledgement: Mapping[str, Any] | None,
    acknowledgement_evidence: Mapping[str, Any] | None,
) -> dict[str, str]:
    envelope_map = _mapping(envelope)
    adapter = _mapping(envelope_map.get("adapter"))
    integrity = _mapping(envelope_map.get("integrity"))
    if acknowledgement_evidence is not None:
        evidence = _mapping(acknowledgement_evidence)
        if evidence.get("envelope_id") != envelope_map.get("envelope_id"):
            raise ValueError("presence_delivery_ack_envelope_mismatch")
        if _positive_int(evidence.get("sequence")) != _positive_int(envelope_map.get("sequence")):
            raise ValueError("presence_delivery_ack_sequence_mismatch")
        if evidence.get("endpoint_id") != endpoint_id:
            raise ValueError("presence_delivery_ack_endpoint_mismatch")
        if evidence.get("payload_digest") != integrity.get("payload_digest"):
            raise ValueError("presence_delivery_ack_digest_mismatch")
        consumer_status = str(evidence.get("consumer_status") or "")
        if consumer_status not in {"accepted_for_render", "duplicate_already_accepted"}:
            raise ValueError("presence_delivery_consumer_status_invalid")
        return {
            "message_id": _required_safe_id(evidence.get("message_id"), "presence_delivery_message_id_invalid"),
            "ack_id": _required_safe_id(evidence.get("ack_id"), "presence_delivery_ack_id_invalid"),
            "consumer_status": consumer_status,
            "authentication_key_id": _required_safe_id(
                evidence.get("authentication_key_id"),
                "presence_delivery_authentication_key_id_invalid",
            ),
        }

    request = _mapping(request_message)
    ack = _mapping(acknowledgement)
    if not request or not ack:
        raise ValueError("presence_delivery_authenticated_ack_required")
    request_payload = _mapping(request.get("payload"))
    if request_payload != envelope_map:
        raise ValueError("presence_delivery_request_envelope_mismatch")
    ack_validation = validate_presence_delivery_ack(
        ack,
        request_message=request,
        endpoint_id=endpoint_id,
    )
    if not ack_validation.ok:
        raise ValueError(ack_validation.reasons[0] if ack_validation.reasons else "presence_delivery_ack_invalid")
    authentication = _mapping(request.get("authentication"))
    if authentication.get("algorithm") != "hmac-sha256":
        raise ValueError("presence_delivery_authentication_invalid")
    if adapter.get("id") != _mapping(ack.get("request")).get("adapter_id"):
        raise ValueError("presence_delivery_ack_adapter_mismatch")
    return {
        "message_id": _required_safe_id(request.get("message_id"), "presence_delivery_message_id_invalid"),
        "ack_id": _required_safe_id(ack.get("ack_id"), "presence_delivery_ack_id_invalid"),
        "consumer_status": ack_validation.consumer_status,
        "authentication_key_id": _required_safe_id(
            authentication.get("key_id"),
            "presence_delivery_authentication_key_id_invalid",
        ),
    }


def _same_receipt_payload(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    existing_payload = dict(existing)
    candidate_payload = dict(candidate)
    existing_payload.pop("recorded_at", None)
    candidate_payload.pop("recorded_at", None)
    return existing_payload == candidate_payload


def _positive_int(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("presence_delivery_sequence_invalid")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("presence_delivery_sequence_invalid") from exc
    if parsed <= 0:
        raise ValueError("presence_delivery_sequence_invalid")
    return parsed


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
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
