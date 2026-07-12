from __future__ import annotations

import ctypes
import json
import os
import struct
import time
from copy import deepcopy
from ctypes import wintypes
from dataclasses import dataclass
from threading import Lock
from typing import Any, Mapping

from francis.unreal_presence_receipts import (
    LocalJsonPresenceDeliveryReceiptStore,
    PresenceDeliveryReceiptStore,
    build_presence_delivery_attempt,
    build_presence_delivery_journal,
    build_presence_delivery_receipt,
)
from francis.unreal_presence_wire import (
    PRESENCE_RENDER_ACK_CHANNEL,
    PRESENCE_RENDER_CHANNEL,
    PresenceIpcAuthenticator,
    validate_presence_delivery_ack,
)
from francis.windows_named_mutex import WindowsNamedMutex
from francis.world_state.presence_transport import (
    bind_presence_transport_envelope,
    validate_presence_transport_envelope,
)


PRESENCE_PIPE_MAX_MESSAGE_BYTES = 256 * 1024
PRESENCE_PIPE_MAX_CONNECT_TIMEOUT_MS = 5_000
PRESENCE_PIPE_DEFAULT_CONNECT_TIMEOUT_MS = 1_000
PRESENCE_PIPE_DEFAULT_POLL_INTERVAL_MS = 10

_PIPE_ACCESS_DUPLEX = 0x00000003
_PIPE_TYPE_MESSAGE = 0x00000004
_PIPE_READMODE_MESSAGE = 0x00000002
_PIPE_NOWAIT = 0x00000001
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_ERROR_PIPE_CONNECTED = 535
_ERROR_PIPE_LISTENING = 536
_ERROR_NO_DATA = 232


@dataclass(frozen=True, slots=True)
class PresencePipeConfig:
    adapter_id: str
    session_id: str
    connect_timeout_ms: int = PRESENCE_PIPE_DEFAULT_CONNECT_TIMEOUT_MS
    poll_interval_ms: int = PRESENCE_PIPE_DEFAULT_POLL_INTERVAL_MS
    max_message_bytes: int = PRESENCE_PIPE_MAX_MESSAGE_BYTES
    writer_lock_timeout_ms: int = PRESENCE_PIPE_MAX_CONNECT_TIMEOUT_MS
    ack_timeout_ms: int = PRESENCE_PIPE_DEFAULT_CONNECT_TIMEOUT_MS
    authentication_key_id: str = "francis_presence_local_v1"

    def __post_init__(self) -> None:
        if not _contract_id(self.adapter_id):
            raise ValueError("presence_pipe_adapter_id_invalid")
        if not _contract_id(self.session_id):
            raise ValueError("presence_pipe_session_id_invalid")
        if not _bounded_integer(self.connect_timeout_ms, minimum=1, maximum=PRESENCE_PIPE_MAX_CONNECT_TIMEOUT_MS):
            raise ValueError("presence_pipe_connect_timeout_invalid")
        if not _bounded_integer(self.poll_interval_ms, minimum=1, maximum=100):
            raise ValueError("presence_pipe_poll_interval_invalid")
        if not _bounded_integer(self.max_message_bytes, minimum=4_096, maximum=PRESENCE_PIPE_MAX_MESSAGE_BYTES):
            raise ValueError("presence_pipe_message_limit_invalid")
        if not _bounded_integer(self.writer_lock_timeout_ms, minimum=1, maximum=10_000):
            raise ValueError("presence_pipe_writer_lock_timeout_invalid")
        if not _bounded_integer(self.ack_timeout_ms, minimum=1, maximum=PRESENCE_PIPE_MAX_CONNECT_TIMEOUT_MS):
            raise ValueError("presence_pipe_ack_timeout_invalid")
        if not _contract_id(self.authentication_key_id):
            raise ValueError("presence_pipe_authentication_key_id_invalid")

    @property
    def endpoint_id(self) -> str:
        return f"francis.grounded_presence.{self.adapter_id}"

    @property
    def pipe_path(self) -> str:
        return rf"\\.\pipe\{self.endpoint_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "francis.grounded_presence.windows_named_pipe.config",
            "adapter_id": self.adapter_id,
            "session_id": self.session_id,
            "endpoint_id": self.endpoint_id,
            "pipe_path": self.pipe_path,
            "connect_timeout_ms": self.connect_timeout_ms,
            "poll_interval_ms": self.poll_interval_ms,
            "max_message_bytes": self.max_message_bytes,
            "writer_lock_timeout_ms": self.writer_lock_timeout_ms,
            "ack_timeout_ms": self.ack_timeout_ms,
            "direction": "francis_core_to_unreal_with_signed_ack",
            "message_framing": "uint32_le_length_plus_authenticated_json_utf8",
            "remote_clients_rejected": True,
            "network_allowed": False,
            "authentication_status": "hmac_sha256_required",
            "authentication_key_id": self.authentication_key_id,
            "delivery_acknowledgement_required": True,
            "consumer_durable_deduplication_required": True,
            "cross_process_writer_lock": "windows_named_mutex",
        }


@dataclass(frozen=True, slots=True)
class PresencePipePublishResult:
    ok: bool
    delivered: bool
    status: str
    reason: str
    envelope_id: str
    sequence: int
    endpoint_id: str
    bytes_written: int
    client_connected: bool
    delivery_attempted: bool
    validation: dict[str, Any]
    receipt_id: str = ""
    receipt_path: str = ""
    receipt_written: bool = False
    acknowledged: bool = False
    ack_id: str = ""
    consumer_status: str = ""
    consumer_durable_deduplication: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "delivered": self.delivered,
            "status": self.status,
            "reason": self.reason,
            "envelope_id": self.envelope_id,
            "sequence": self.sequence,
            "endpoint_id": self.endpoint_id,
            "bytes_written": self.bytes_written,
            "client_connected": self.client_connected,
            "delivery_attempted": self.delivery_attempted,
            "validation": dict(self.validation),
            "receipt_id": self.receipt_id,
            "receipt_path": self.receipt_path,
            "receipt_written": self.receipt_written,
            "acknowledged": self.acknowledged,
            "ack_id": self.ack_id,
            "consumer_status": self.consumer_status,
            "consumer_durable_deduplication": self.consumer_durable_deduplication,
            "stores_payload": False,
            "network_used": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


class WindowsNamedPipePresencePublisher:
    """Synchronous one-way publisher with a bounded local-client wait."""

    def __init__(
        self,
        config: PresencePipeConfig,
        *,
        authenticator: PresenceIpcAuthenticator,
        receipt_store: PresenceDeliveryReceiptStore | None = None,
    ) -> None:
        if authenticator.key_id != config.authentication_key_id:
            raise ValueError("presence_pipe_authentication_key_mismatch")
        self.config = config
        self.authenticator = authenticator
        self.receipt_store = receipt_store or LocalJsonPresenceDeliveryReceiptStore()
        self._lock = Lock()
        self._last_sequence = 0
        self._delivery_count = 0
        self._failure_count = 0
        self._receipt_recovery_count = 0
        self._attempt_reconciliation_count = 0
        self._last_delivery: dict[str, Any] = {}
        self._pending_receipt_recovery: dict[str, Any] = {}
        self._pending_recovery_source = ""
        self._durable_sequence_error = ""
        self._pending_recovery_error = ""
        self._writer_mutex = WindowsNamedMutex(
            scope=f"delivery|{config.adapter_id}|{config.session_id}|{config.endpoint_id}",
            timeout_ms=config.writer_lock_timeout_ms,
        )
        self._last_writer_lock: dict[str, Any] = {}
        self._writer_lock_release_error = ""
        self._refresh_durable_sequence()
        self._pending_recovery_error = self._refresh_pending_recovery()

    def publish(self, envelope: Mapping[str, Any]) -> PresencePipePublishResult:
        with self._lock:
            if os.name != "nt":
                return self._publish_locked(envelope)
            lock_result = self._writer_mutex.acquire()
            self._last_writer_lock = lock_result.to_dict()
            if not lock_result.acquired:
                return self._failure(
                    _mapping(envelope),
                    status="writer_lock_unavailable",
                    reason=lock_result.reason or lock_result.status,
                    delivery_attempted=False,
                )
            try:
                return self._publish_locked(envelope)
            finally:
                self._writer_lock_release_error = self._writer_mutex.release()

    def readback(self) -> dict[str, Any]:
        with self._lock:
            if self._durable_sequence_error or self._pending_recovery_error:
                status = "receipt_state_invalid"
            elif self._pending_receipt_recovery:
                status = "receipt_recovery_required"
            else:
                status = "ready_on_demand" if os.name == "nt" else "unsupported_platform"
            return {
                "kind": "francis.grounded_presence.windows_named_pipe.readback",
                "status": status,
                "config": self.config.to_dict(),
                "last_sequence": self._last_sequence,
                "delivery_count": self._delivery_count,
                "failure_count": self._failure_count,
                "receipt_recovery_count": self._receipt_recovery_count,
                "attempt_reconciliation_count": self._attempt_reconciliation_count,
                "last_delivery": dict(self._last_delivery),
                "receipt_recovery_pending": bool(self._pending_receipt_recovery),
                "pending_receipt_recovery": dict(self._pending_receipt_recovery),
                "pending_recovery_source": self._pending_recovery_source,
                "durable_replay_state": "delivery_receipt_sequence_watermark",
                "durable_session_sequence_state": not self._durable_sequence_error,
                "durable_sequence_error": self._durable_sequence_error,
                "pending_recovery_error": self._pending_recovery_error,
                "durable_receipt_recovery": "pre_send_attempt_plus_post_ack_delivery_journal",
                "authentication": self.authenticator.describe(),
                "delivery_acknowledgement_required": True,
                "consumer_durable_deduplication_required": True,
                "cross_process_writer_lock": {
                    "kind": "windows_named_mutex",
                    "name": self._writer_mutex.name,
                    "last_acquire": dict(self._last_writer_lock),
                    "release_error": self._writer_lock_release_error,
                },
                "background_worker": False,
                "bidirectional": True,
                "writes_memory": False,
                "writes_receipts": True,
                "delivery_receipts_required": True,
                "network_allowed": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

    def _publish_locked(self, envelope: Mapping[str, Any]) -> PresencePipePublishResult:
        envelope_map = deepcopy(dict(envelope))
        durable_sequence_error = self._refresh_durable_sequence()
        if durable_sequence_error:
            return self._failure(
                envelope_map,
                status="receipt_state_invalid",
                reason=durable_sequence_error,
                delivery_attempted=False,
            )
        pending_recovery_error = self._refresh_pending_recovery()
        self._pending_recovery_error = pending_recovery_error
        if pending_recovery_error:
            return self._failure(
                envelope_map,
                status="receipt_recovery_state_invalid",
                reason=pending_recovery_error,
                delivery_attempted=False,
            )
        transport = _mapping(envelope_map.get("transport"))
        try:
            if transport.get("binding_status") == "unbound":
                bound = bind_presence_transport_envelope(
                    envelope_map,
                    binding_status="windows_named_pipe",
                    endpoint_id=self.config.endpoint_id,
                )
            elif (
                transport.get("binding_status") == "windows_named_pipe"
                and transport.get("endpoint_id") == self.config.endpoint_id
            ):
                bound = envelope_map
            else:
                return self._failure(
                    envelope_map,
                    status="rejected",
                    reason="transport_binding_mismatch",
                    delivery_attempted=False,
                )
        except (TypeError, ValueError) as exc:
            return self._failure(
                envelope_map,
                status="rejected",
                reason=_bounded_text(str(exc)) or type(exc).__name__,
                delivery_attempted=False,
            )

        attempt_reconciliation = False
        if self._pending_receipt_recovery:
            if self._pending_recovery_source in {
                "delivery_journal",
                "journal_cleanup",
                "process_memory_outcome_unknown",
            }:
                recovery = self._recover_pending_receipt(bound)
                if recovery is not None:
                    return recovery
            elif self._pending_recovery_source == "delivery_attempt":
                attempt_reconciliation = self._pending_matches_envelope(bound)
            if not attempt_reconciliation:
                return self._failure(
                    bound,
                    status="receipt_recovery_required",
                    reason="previous_delivery_recovery_requires_exact_envelope",
                    delivery_attempted=False,
                )

        sequence = _nonnegative_int(bound.get("sequence"))
        validation = validate_presence_transport_envelope(
            bound,
            now=str(bound.get("issued_at") or "") if attempt_reconciliation else None,
            expected_adapter_id=self.config.adapter_id,
            expected_session_id=self.config.session_id,
            last_sequence=max(0, sequence - 1) if attempt_reconciliation else self._last_sequence,
        )
        if not validation.ok:
            return self._failure(
                bound,
                status="rejected",
                reason=validation.reasons[0] if validation.reasons else "transport_validation_failed",
                delivery_attempted=False,
                validation=validation.to_dict(),
            )
        try:
            already_delivered = self.receipt_store.has_delivery(
                envelope_id=_bounded_text(bound.get("envelope_id"), limit=64),
                endpoint_id=self.config.endpoint_id,
            )
        except (OSError, ValueError) as exc:
            return self._failure(
                bound,
                status="receipt_preflight_failed",
                reason=_bounded_text(str(exc)) or type(exc).__name__,
                delivery_attempted=False,
                validation=validation.to_dict(),
            )
        if already_delivered:
            return self._failure(
                bound,
                status="rejected",
                reason="envelope_already_delivered",
                delivery_attempted=False,
                validation=validation.to_dict(),
            )
        try:
            wire_message = self.authenticator.sign(
                bound,
                channel=PRESENCE_RENDER_CHANNEL,
                direction="francis_core_to_unreal",
                ttl_ms=min(_nonnegative_int(bound.get("ttl_ms")), 5_000),
            )
            frame = encode_presence_pipe_frame(wire_message, max_message_bytes=self.config.max_message_bytes)
        except (TypeError, ValueError) as exc:
            return self._failure(
                bound,
                status="rejected",
                reason=_bounded_text(str(exc)) or type(exc).__name__,
                delivery_attempted=False,
                validation=validation.to_dict(),
            )
        if os.name != "nt":
            return self._failure(
                bound,
                status="unsupported_platform",
                reason="windows_named_pipe_requires_windows",
                delivery_attempted=False,
                validation=validation.to_dict(),
            )

        if not attempt_reconciliation:
            try:
                attempt = build_presence_delivery_attempt(
                    envelope=bound,
                    endpoint_id=self.config.endpoint_id,
                    request_message=wire_message,
                )
                self.receipt_store.write_pending_attempt(attempt)
                self._set_pending_recovery(
                    _mapping(attempt.get("delivery")),
                    source="delivery_attempt",
                )
            except (OSError, TypeError, ValueError) as exc:
                return self._failure(
                    bound,
                    status="delivery_attempt_persistence_failed",
                    reason=_bounded_text(str(exc)) or type(exc).__name__,
                    delivery_attempted=False,
                    validation=validation.to_dict(),
                )

        handle = _create_named_pipe(self.config)
        if handle is None:
            if not attempt_reconciliation:
                self._clear_pending_attempt()
            return self._failure(
                bound,
                status="pipe_create_failed",
                reason=f"win32_error_{ctypes.get_last_error()}",
                delivery_attempted=True,
                validation=validation.to_dict(),
            )

        connected = False
        try:
            connected, connect_reason = _wait_for_client(handle, self.config)
            if not connected:
                if not attempt_reconciliation:
                    self._clear_pending_attempt()
                return self._failure(
                    bound,
                    status="client_timeout" if connect_reason == "client_not_connected" else "connect_failed",
                    reason=connect_reason,
                    delivery_attempted=True,
                    validation=validation.to_dict(),
                )

            current_validation = validate_presence_transport_envelope(
                bound,
                now=str(bound.get("issued_at") or "") if attempt_reconciliation else None,
                expected_adapter_id=self.config.adapter_id,
                expected_session_id=self.config.session_id,
                last_sequence=max(0, sequence - 1) if attempt_reconciliation else self._last_sequence,
            )
            if not current_validation.ok:
                if not attempt_reconciliation:
                    self._clear_pending_attempt()
                return self._failure(
                    bound,
                    status="rejected_after_connect",
                    reason=(
                        current_validation.reasons[0] if current_validation.reasons else "transport_validation_failed"
                    ),
                    delivery_attempted=True,
                    client_connected=True,
                    validation=current_validation.to_dict(),
                )

            bytes_written, write_reason = _write_pipe_frame(handle, frame)
            if bytes_written != len(frame):
                return self._failure(
                    bound,
                    status="write_failed",
                    reason=write_reason or "partial_pipe_write",
                    delivery_attempted=True,
                    client_connected=True,
                    validation=current_validation.to_dict(),
                    bytes_written=bytes_written,
                )

            ack_frame, ack_read_reason = _read_pipe_frame(handle, self.config)
            if not ack_frame:
                return self._failure(
                    bound,
                    status="ack_timeout" if ack_read_reason == "client_data_timeout" else "ack_read_failed",
                    reason=ack_read_reason or "delivery_ack_missing",
                    delivery_attempted=True,
                    client_connected=True,
                    validation=current_validation.to_dict(),
                    bytes_written=bytes_written,
                )
            try:
                signed_ack = decode_presence_pipe_frame(
                    ack_frame,
                    max_message_bytes=self.config.max_message_bytes,
                )
            except ValueError as exc:
                return self._failure(
                    bound,
                    status="ack_frame_rejected",
                    reason=_bounded_text(str(exc)),
                    delivery_attempted=True,
                    client_connected=True,
                    validation=current_validation.to_dict(),
                    bytes_written=bytes_written,
                )
            ack_authentication = self.authenticator.validate(
                signed_ack,
                expected_channel=PRESENCE_RENDER_ACK_CHANNEL,
                expected_direction="unreal_to_francis_core",
            )
            if not ack_authentication.ok:
                return self._failure(
                    bound,
                    status="ack_authentication_rejected",
                    reason=(
                        ack_authentication.reasons[0]
                        if ack_authentication.reasons
                        else "delivery_ack_authentication_failed"
                    ),
                    delivery_attempted=True,
                    client_connected=True,
                    validation={
                        **current_validation.to_dict(),
                        "ack_authentication": ack_authentication.to_dict(),
                    },
                    bytes_written=bytes_written,
                )
            acknowledgement = _mapping(signed_ack.get("payload"))
            ack_validation = validate_presence_delivery_ack(
                acknowledgement,
                request_message=wire_message,
                endpoint_id=self.config.endpoint_id,
            )
            if not ack_validation.ok:
                return self._failure(
                    bound,
                    status="ack_rejected",
                    reason=(ack_validation.reasons[0] if ack_validation.reasons else "delivery_ack_invalid"),
                    delivery_attempted=True,
                    client_connected=True,
                    validation={
                        **current_validation.to_dict(),
                        "ack_authentication": ack_authentication.to_dict(),
                        "ack": ack_validation.to_dict(),
                    },
                    bytes_written=bytes_written,
                )

            sequence = _nonnegative_int(bound.get("sequence"))
            envelope_id = _bounded_text(bound.get("envelope_id"), limit=64)
            ack_id = ack_validation.ack_id
            consumer_status = ack_validation.consumer_status
            self._last_sequence = sequence
            self._delivery_count += 1
            if attempt_reconciliation:
                self._attempt_reconciliation_count += 1
            journal_written = False
            journal_error = ""
            try:
                journal = build_presence_delivery_journal(
                    envelope=bound,
                    endpoint_id=self.config.endpoint_id,
                    bytes_written=bytes_written,
                    request_message=wire_message,
                    acknowledgement=acknowledgement,
                )
                self.receipt_store.write_pending_delivery(journal)
                self._set_pending_recovery(
                    _mapping(journal.get("delivery")),
                    source="delivery_journal",
                )
                journal_written = True
                self._clear_pending_attempt(clear_memory=False)
            except (OSError, TypeError, ValueError) as exc:
                journal_error = _bounded_text(str(exc)) or type(exc).__name__

            try:
                receipt = build_presence_delivery_receipt(
                    envelope=bound,
                    endpoint_id=self.config.endpoint_id,
                    bytes_written=bytes_written,
                    request_message=wire_message,
                    acknowledgement=acknowledgement,
                )
                receipt_path = self.receipt_store.write(receipt)
                receipt_id = _bounded_text(receipt.get("receipt_id"), limit=64)
            except (OSError, TypeError, ValueError) as exc:
                receipt_error = _bounded_text(str(exc)) or type(exc).__name__
                reason = receipt_error
                if journal_error:
                    reason = _bounded_text(f"receipt={receipt_error}; journal={journal_error}")
                self._failure_count += 1
                failure_status = "delivered_receipt_failed" if journal_written else "delivered_recovery_state_failed"
                self._last_delivery = {
                    "status": failure_status,
                    "reason": reason,
                    "envelope_id": envelope_id,
                    "sequence": sequence,
                    "bytes_written": bytes_written,
                    "client_connected": True,
                    "receipt_written": False,
                    "delivery_journal_written": journal_written,
                    "acknowledged": True,
                    "ack_id": ack_id,
                    "consumer_status": consumer_status,
                }
                return PresencePipePublishResult(
                    ok=False,
                    delivered=True,
                    status=failure_status,
                    reason=reason,
                    envelope_id=envelope_id,
                    sequence=sequence,
                    endpoint_id=self.config.endpoint_id,
                    bytes_written=bytes_written,
                    client_connected=True,
                    delivery_attempted=True,
                    validation=current_validation.to_dict(),
                    acknowledged=True,
                    ack_id=ack_id,
                    consumer_status=consumer_status,
                    consumer_durable_deduplication=True,
                )

            cleanup_error = ""
            if journal_written:
                try:
                    self.receipt_store.clear_pending_delivery(
                        adapter_id=self.config.adapter_id,
                        session_id=self.config.session_id,
                        endpoint_id=self.config.endpoint_id,
                    )
                except (OSError, TypeError, ValueError) as exc:
                    cleanup_error = _bounded_text(str(exc)) or type(exc).__name__
            attempt_cleanup_error = self._clear_pending_attempt(clear_memory=False)
            if attempt_cleanup_error and not cleanup_error:
                cleanup_error = attempt_cleanup_error
            if not cleanup_error:
                self._pending_receipt_recovery = {}
                self._pending_recovery_source = ""
            delivery_status = (
                "delivered_journal_cleanup_pending"
                if cleanup_error
                else "delivered_after_reconciliation"
                if attempt_reconciliation
                else "delivered"
            )
            self._last_delivery = {
                "status": delivery_status,
                "envelope_id": envelope_id,
                "sequence": sequence,
                "bytes_written": bytes_written,
                "client_connected": True,
                "receipt_id": receipt_id,
                "receipt_path": str(receipt_path),
                "receipt_written": True,
                "delivery_journal_written": journal_written,
                "delivery_journal_cleanup_error": cleanup_error,
                "delivery_attempt_reconciled": attempt_reconciliation,
                "acknowledged": True,
                "ack_id": ack_id,
                "consumer_status": consumer_status,
            }
            return PresencePipePublishResult(
                ok=True,
                delivered=True,
                status=delivery_status,
                reason=cleanup_error,
                envelope_id=envelope_id,
                sequence=sequence,
                endpoint_id=self.config.endpoint_id,
                bytes_written=bytes_written,
                client_connected=True,
                delivery_attempted=True,
                validation=current_validation.to_dict(),
                receipt_id=receipt_id,
                receipt_path=str(receipt_path),
                receipt_written=True,
                acknowledged=True,
                ack_id=ack_id,
                consumer_status=consumer_status,
                consumer_durable_deduplication=True,
            )
        finally:
            _close_named_pipe(handle, disconnect=connected)

    def _recover_pending_receipt(self, envelope: Mapping[str, Any]) -> PresencePipePublishResult | None:
        pending = self._pending_receipt_recovery
        integrity = _mapping(envelope.get("integrity"))
        if (
            _bounded_text(envelope.get("envelope_id"), limit=64) != pending.get("envelope_id")
            or _nonnegative_int(envelope.get("sequence")) != pending.get("sequence")
            or _bounded_text(integrity.get("payload_digest"), limit=64) != pending.get("payload_digest")
        ):
            return None
        sequence = _nonnegative_int(envelope.get("sequence"))
        recovery_validation = validate_presence_transport_envelope(
            envelope,
            now=str(envelope.get("issued_at") or ""),
            expected_adapter_id=self.config.adapter_id,
            expected_session_id=self.config.session_id,
            last_sequence=max(0, sequence - 1),
        )
        if not recovery_validation.ok:
            return self._failure(
                envelope,
                status="receipt_recovery_rejected",
                reason=(
                    recovery_validation.reasons[0] if recovery_validation.reasons else "transport_validation_failed"
                ),
                delivery_attempted=False,
                validation=recovery_validation.to_dict(),
            )
        try:
            receipt = build_presence_delivery_receipt(
                envelope=envelope,
                endpoint_id=self.config.endpoint_id,
                bytes_written=_nonnegative_int(pending.get("bytes_written")),
                acknowledgement_evidence=pending,
            )
            receipt_path = self.receipt_store.write(receipt)
            receipt_id = _bounded_text(receipt.get("receipt_id"), limit=64)
        except (OSError, TypeError, ValueError) as exc:
            return self._failure(
                envelope,
                status="receipt_recovery_failed",
                reason=_bounded_text(str(exc)) or type(exc).__name__,
                delivery_attempted=False,
                validation=recovery_validation.to_dict(),
                bytes_written=_nonnegative_int(pending.get("bytes_written")),
            )
        bytes_written = _nonnegative_int(pending.get("bytes_written"))
        cleanup_error = ""
        try:
            self.receipt_store.clear_pending_delivery(
                adapter_id=self.config.adapter_id,
                session_id=self.config.session_id,
                endpoint_id=self.config.endpoint_id,
            )
        except (OSError, TypeError, ValueError) as exc:
            cleanup_error = _bounded_text(str(exc)) or type(exc).__name__
        if not cleanup_error:
            self._pending_receipt_recovery = {}
            self._pending_recovery_source = ""
        self._receipt_recovery_count += 1
        recovery_status = (
            "delivery_receipt_recovered_cleanup_pending" if cleanup_error else "delivery_receipt_recovered"
        )
        self._last_delivery = {
            "status": recovery_status,
            "envelope_id": _bounded_text(envelope.get("envelope_id"), limit=64),
            "sequence": sequence,
            "bytes_written": bytes_written,
            "client_connected": True,
            "receipt_id": receipt_id,
            "receipt_path": str(receipt_path),
            "receipt_written": True,
            "redelivery_attempted": False,
            "delivery_journal_cleanup_error": cleanup_error,
        }
        return PresencePipePublishResult(
            ok=True,
            delivered=True,
            status=recovery_status,
            reason=cleanup_error,
            envelope_id=_bounded_text(envelope.get("envelope_id"), limit=64),
            sequence=sequence,
            endpoint_id=self.config.endpoint_id,
            bytes_written=bytes_written,
            client_connected=True,
            delivery_attempted=False,
            validation=recovery_validation.to_dict(),
            receipt_id=receipt_id,
            receipt_path=str(receipt_path),
            receipt_written=True,
            acknowledged=True,
            ack_id=_bounded_text(pending.get("ack_id"), limit=64),
            consumer_status=_bounded_text(pending.get("consumer_status"), limit=64),
            consumer_durable_deduplication=True,
        )

    def _refresh_durable_sequence(self) -> str:
        try:
            durable_sequence = self.receipt_store.highest_delivered_sequence(
                adapter_id=self.config.adapter_id,
                session_id=self.config.session_id,
                endpoint_id=self.config.endpoint_id,
                refresh=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            self._durable_sequence_error = _bounded_text(str(exc)) or type(exc).__name__
            return self._durable_sequence_error
        self._durable_sequence_error = ""
        self._last_sequence = max(self._last_sequence, durable_sequence)
        return ""

    def _refresh_pending_recovery(self) -> str:
        try:
            journal = self.receipt_store.read_pending_delivery(
                adapter_id=self.config.adapter_id,
                session_id=self.config.session_id,
                endpoint_id=self.config.endpoint_id,
            )
            attempt = self.receipt_store.read_pending_attempt(
                adapter_id=self.config.adapter_id,
                session_id=self.config.session_id,
                endpoint_id=self.config.endpoint_id,
            )
        except (OSError, TypeError, ValueError) as exc:
            return _bounded_text(str(exc)) or type(exc).__name__
        recovery_record = journal or attempt
        if not recovery_record:
            if self._pending_recovery_source in {"delivery_journal", "journal_cleanup", "delivery_attempt"}:
                self._pending_receipt_recovery = {}
                self._pending_recovery_source = ""
            return ""

        delivery = _mapping(recovery_record.get("delivery"))
        recovery_source = "delivery_journal" if journal else "delivery_attempt"
        self._set_pending_recovery(delivery, source=recovery_source)
        self._last_sequence = max(self._last_sequence, _nonnegative_int(delivery.get("sequence")))
        try:
            already_receipted = self.receipt_store.has_delivery(
                envelope_id=_bounded_text(delivery.get("envelope_id"), limit=64),
                endpoint_id=self.config.endpoint_id,
            )
        except (OSError, TypeError, ValueError) as exc:
            return _bounded_text(str(exc)) or type(exc).__name__
        if not already_receipted:
            if journal and attempt:
                attempt_cleanup_error = self._clear_pending_attempt(clear_memory=False)
                if attempt_cleanup_error:
                    return attempt_cleanup_error
            return ""
        try:
            if journal:
                self.receipt_store.clear_pending_delivery(
                    adapter_id=self.config.adapter_id,
                    session_id=self.config.session_id,
                    endpoint_id=self.config.endpoint_id,
                )
            if attempt:
                self.receipt_store.clear_pending_attempt(
                    adapter_id=self.config.adapter_id,
                    session_id=self.config.session_id,
                    endpoint_id=self.config.endpoint_id,
                )
        except (OSError, TypeError, ValueError) as exc:
            self._pending_recovery_source = "journal_cleanup" if journal else "delivery_attempt"
            return _bounded_text(str(exc)) or type(exc).__name__
        self._pending_receipt_recovery = {}
        self._pending_recovery_source = ""
        return ""

    def _set_pending_recovery(self, delivery: Mapping[str, Any], *, source: str) -> None:
        self._pending_receipt_recovery = {
            "state": _bounded_text(delivery.get("state"), limit=64),
            "envelope_id": _bounded_text(delivery.get("envelope_id"), limit=64),
            "sequence": _nonnegative_int(delivery.get("sequence")),
            "bytes_written": _nonnegative_int(delivery.get("bytes_written")),
            "endpoint_id": _bounded_text(delivery.get("endpoint_id"), limit=160),
            "payload_digest": _bounded_text(delivery.get("payload_digest"), limit=64),
            "message_id": _bounded_text(delivery.get("message_id"), limit=64),
            "ack_id": _bounded_text(delivery.get("ack_id"), limit=64),
            "consumer_status": _bounded_text(delivery.get("consumer_status"), limit=64),
            "authentication_key_id": _bounded_text(delivery.get("authentication_key_id"), limit=160),
            "safe_redelivery": True,
        }
        self._pending_recovery_source = source

    def _pending_matches_envelope(self, envelope: Mapping[str, Any]) -> bool:
        pending = self._pending_receipt_recovery
        integrity = _mapping(envelope.get("integrity"))
        return (
            _bounded_text(envelope.get("envelope_id"), limit=64) == pending.get("envelope_id")
            and _nonnegative_int(envelope.get("sequence")) == pending.get("sequence")
            and _bounded_text(integrity.get("payload_digest"), limit=64) == pending.get("payload_digest")
            and self.authenticator.key_id == pending.get("authentication_key_id")
        )

    def _clear_pending_attempt(self, *, clear_memory: bool = True) -> str:
        try:
            self.receipt_store.clear_pending_attempt(
                adapter_id=self.config.adapter_id,
                session_id=self.config.session_id,
                endpoint_id=self.config.endpoint_id,
            )
        except (OSError, TypeError, ValueError) as exc:
            return _bounded_text(str(exc)) or type(exc).__name__
        if clear_memory and self._pending_recovery_source == "delivery_attempt":
            self._pending_receipt_recovery = {}
            self._pending_recovery_source = ""
        return ""

    def _failure(
        self,
        envelope: Mapping[str, Any],
        *,
        status: str,
        reason: str,
        delivery_attempted: bool,
        client_connected: bool = False,
        validation: Mapping[str, Any] | None = None,
        bytes_written: int = 0,
    ) -> PresencePipePublishResult:
        sequence = _nonnegative_int(envelope.get("sequence"))
        envelope_id = _bounded_text(envelope.get("envelope_id"), limit=64)
        self._failure_count += 1
        self._last_delivery = {
            "status": status,
            "reason": reason,
            "envelope_id": envelope_id,
            "sequence": sequence,
            "bytes_written": bytes_written,
            "client_connected": client_connected,
            "receipt_written": False,
        }
        return PresencePipePublishResult(
            ok=False,
            delivered=False,
            status=status,
            reason=reason,
            envelope_id=envelope_id,
            sequence=sequence,
            endpoint_id=self.config.endpoint_id,
            bytes_written=bytes_written,
            client_connected=client_connected,
            delivery_attempted=delivery_attempted,
            validation=dict(validation or {}),
        )


def encode_presence_pipe_frame(
    envelope: Mapping[str, Any],
    *,
    max_message_bytes: int = PRESENCE_PIPE_MAX_MESSAGE_BYTES,
) -> bytes:
    if not _bounded_integer(max_message_bytes, minimum=4_096, maximum=PRESENCE_PIPE_MAX_MESSAGE_BYTES):
        raise ValueError("presence_pipe_message_limit_invalid")
    payload = json.dumps(
        dict(envelope),
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    if not payload:
        raise ValueError("presence_pipe_payload_empty")
    if len(payload) > max_message_bytes:
        raise ValueError("presence_pipe_payload_too_large")
    return struct.pack("<I", len(payload)) + payload


def decode_presence_pipe_frame(
    frame: bytes,
    *,
    max_message_bytes: int = PRESENCE_PIPE_MAX_MESSAGE_BYTES,
) -> dict[str, Any]:
    if not isinstance(frame, bytes) or len(frame) < 5:
        raise ValueError("presence_pipe_frame_invalid")
    declared_length = struct.unpack("<I", frame[:4])[0]
    if declared_length <= 0 or declared_length > max_message_bytes:
        raise ValueError("presence_pipe_frame_length_invalid")
    if len(frame) != declared_length + 4:
        raise ValueError("presence_pipe_frame_length_mismatch")
    try:
        payload = json.loads(frame[4:].decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence_pipe_frame_json_invalid") from exc
    if not isinstance(payload, dict):
        raise ValueError("presence_pipe_frame_payload_invalid")
    return payload


def _create_named_pipe(config: PresencePipeConfig) -> int | None:
    kernel32 = _kernel32()
    handle = kernel32.CreateNamedPipeW(
        config.pipe_path,
        _PIPE_ACCESS_DUPLEX,
        _PIPE_TYPE_MESSAGE | _PIPE_READMODE_MESSAGE | _PIPE_NOWAIT | _PIPE_REJECT_REMOTE_CLIENTS,
        1,
        config.max_message_bytes + 4,
        config.max_message_bytes + 4,
        config.connect_timeout_ms,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        return None
    return int(handle)


def _wait_for_client(handle: int, config: PresencePipeConfig) -> tuple[bool, str]:
    kernel32 = _kernel32()
    deadline = time.monotonic() + config.connect_timeout_ms / 1_000
    while True:
        ctypes.set_last_error(0)
        if kernel32.ConnectNamedPipe(handle, None):
            return True, ""
        error = ctypes.get_last_error()
        if error == _ERROR_PIPE_CONNECTED:
            return True, ""
        if error not in {_ERROR_PIPE_LISTENING, _ERROR_NO_DATA}:
            return False, f"win32_error_{error}"
        if time.monotonic() >= deadline:
            return False, "client_not_connected"
        time.sleep(config.poll_interval_ms / 1_000)


def _write_pipe_frame(handle: int, frame: bytes) -> tuple[int, str]:
    kernel32 = _kernel32()
    written = wintypes.DWORD(0)
    buffer = ctypes.create_string_buffer(frame)
    ctypes.set_last_error(0)
    ok = kernel32.WriteFile(
        handle,
        buffer,
        len(frame),
        ctypes.byref(written),
        None,
    )
    if not ok:
        return int(written.value), f"win32_error_{ctypes.get_last_error()}"
    return int(written.value), ""


def _read_pipe_frame(handle: int, config: PresencePipeConfig) -> tuple[bytes, str]:
    kernel32 = _kernel32()
    deadline = time.monotonic() + config.ack_timeout_ms / 1_000
    while True:
        available = wintypes.DWORD(0)
        ctypes.set_last_error(0)
        ready = kernel32.PeekNamedPipe(
            handle,
            None,
            0,
            None,
            ctypes.byref(available),
            None,
        )
        if ready and available.value > 0:
            buffer = ctypes.create_string_buffer(config.max_message_bytes + 4)
            read = wintypes.DWORD(0)
            ctypes.set_last_error(0)
            ok = kernel32.ReadFile(
                handle,
                buffer,
                config.max_message_bytes + 4,
                ctypes.byref(read),
                None,
            )
            if ok and read.value > 0:
                return bytes(buffer.raw[: read.value]), ""
            error = ctypes.get_last_error()
            if error not in {_ERROR_NO_DATA, _ERROR_PIPE_LISTENING}:
                return b"", f"win32_error_{error}"
        elif not ready:
            error = ctypes.get_last_error()
            if error not in {_ERROR_NO_DATA, _ERROR_PIPE_LISTENING}:
                return b"", f"win32_error_{error}"
        if time.monotonic() >= deadline:
            return b"", "client_data_timeout"
        time.sleep(config.poll_interval_ms / 1_000)


def _close_named_pipe(handle: int, *, disconnect: bool) -> None:
    kernel32 = _kernel32()
    if disconnect:
        kernel32.DisconnectNamedPipe(handle)
    kernel32.CloseHandle(handle)


def _kernel32() -> Any:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.PeekNamedPipe.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.PeekNamedPipe.restype = wintypes.BOOL
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _contract_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or len(text) > 120:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _bounded_integer(value: Any, *, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]
