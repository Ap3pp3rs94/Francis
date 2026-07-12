from __future__ import annotations

import hashlib
import json
import os
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import Any, Mapping, Protocol

from francis.kernel.paths import data_dir
from francis.windows_named_mutex import WindowsNamedMutex
from francis.world_state.presence_intent import (
    PresenceIntentValidation,
    validate_presence_intent_event,
)


PRESENCE_INTENT_RECEIPT_KIND = "francis.grounded_presence.intent_receipt"
PRESENCE_INTENT_RECEIPT_SCHEMA_VERSION = "francis.grounded_presence.intent_receipt.v1"
PRESENCE_INTENT_RECEIPT_SCHEMA_PATH = "schemas/grounded_presence_intent_receipt.schema.json"
PRESENCE_INTENT_RECEIPT_MAX_BYTES = 64 * 1024


class PresenceIntentReceiptStore(Protocol):
    def highest_accepted_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        refresh: bool = False,
    ) -> int: ...

    def write(self, receipt: Mapping[str, Any]) -> Path: ...


class LocalJsonPresenceIntentReceiptStore:
    def __init__(self, root: Path | str | None = None) -> None:
        self.root = Path(root) if root is not None else data_dir() / "receipts" / "grounded_presence" / "intents"
        self._lock = Lock()
        self._sequence_cache: dict[tuple[str, str], int] = {}

    def write(self, receipt: Mapping[str, Any]) -> Path:
        payload = dict(receipt)
        if payload.get("kind") != PRESENCE_INTENT_RECEIPT_KIND:
            raise ValueError("presence_intent_receipt_kind_invalid")
        receipt_id = _safe_id(payload.get("receipt_id"))
        if not receipt_id:
            raise ValueError("presence_intent_receipt_id_invalid")
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            path = self.root / f"{receipt_id}.json"
            if path.is_file():
                if not _same_receipt_payload(_read_intent_receipt(path), payload):
                    raise ValueError("presence_intent_receipt_id_conflict")
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

    def highest_accepted_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        refresh: bool = False,
    ) -> int:
        normalized_adapter_id = _required_id(adapter_id, "presence_intent_receipt_adapter_id_invalid")
        normalized_session_id = _required_id(session_id, "presence_intent_receipt_session_id_invalid")
        key = (normalized_adapter_id, normalized_session_id)
        with self._lock:
            if refresh or key not in self._sequence_cache:
                self._sequence_cache[key] = self._scan_highest_sequence(*key)
            return self._sequence_cache[key]

    def _record_sequence(self, receipt: Mapping[str, Any]) -> None:
        decision = _mapping(receipt.get("decision"))
        if decision.get("accepted") is not True:
            return
        event = _mapping(receipt.get("event"))
        key = (
            _required_id(event.get("adapter_id"), "presence_intent_receipt_adapter_id_invalid"),
            _required_id(event.get("session_id"), "presence_intent_receipt_session_id_invalid"),
        )
        sequence = _positive_int(event.get("event_sequence"))
        if key not in self._sequence_cache:
            self._sequence_cache[key] = self._scan_highest_sequence(*key)
        self._sequence_cache[key] = max(self._sequence_cache[key], sequence)

    def _scan_highest_sequence(self, adapter_id: str, session_id: str) -> int:
        if not self.root.is_dir():
            return 0
        highest = 0
        for path in self.root.glob("gpr_*.json"):
            receipt = _read_intent_receipt(path)
            decision = _mapping(receipt.get("decision"))
            event = _mapping(receipt.get("event"))
            if decision.get("accepted") is not True:
                continue
            if event.get("adapter_id") != adapter_id or event.get("session_id") != session_id:
                continue
            highest = max(highest, _positive_int(event.get("event_sequence")))
        return highest


@dataclass(frozen=True, slots=True)
class PresenceIntentGatewayResult:
    ok: bool
    accepted: bool
    status: str
    reasons: tuple[str, ...]
    event_id: str
    intent: str
    required_core_route: str
    receipt_id: str
    receipt_path: str
    receipt_written: bool
    validation: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "accepted": self.accepted,
            "status": self.status,
            "reasons": list(self.reasons),
            "event_id": self.event_id,
            "intent": self.intent,
            "required_core_route": self.required_core_route,
            "receipt_id": self.receipt_id,
            "receipt_path": self.receipt_path,
            "receipt_written": self.receipt_written,
            "validation": dict(self.validation),
            "dispatch_attempted": False,
            "dispatch_allowed": False,
            "mutation_applied": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


class UnrealPresenceIntentGateway:
    """Validate and receipt renderer intents without dispatching them."""

    def __init__(
        self,
        *,
        adapter_id: str,
        session_id: str,
        receipt_store: PresenceIntentReceiptStore | None = None,
    ) -> None:
        self.adapter_id = _required_id(adapter_id, "presence_intent_gateway_adapter_id_invalid")
        self.session_id = _required_id(session_id, "presence_intent_gateway_session_id_invalid")
        self.receipt_store = receipt_store or LocalJsonPresenceIntentReceiptStore()
        self._lock = Lock()
        self._last_event_sequence = 0
        self._accepted_count = 0
        self._rejected_count = 0
        self._last_decision: dict[str, Any] = {}
        self._durable_sequence_error = ""
        self._writer_mutex = WindowsNamedMutex(
            scope=f"intent|{self.adapter_id}|{self.session_id}",
            timeout_ms=2_000,
        )
        self._last_writer_lock: dict[str, Any] = {}
        self._writer_lock_release_error = ""
        self._refresh_durable_sequence()

    def evaluate(
        self,
        event: Mapping[str, Any] | None,
        *,
        expected_source_envelope_id: str = "",
        now: str | datetime | None = None,
        authentication: Mapping[str, Any] | None = None,
    ) -> PresenceIntentGatewayResult:
        with self._lock:
            if os.name != "nt":
                return self._evaluate_locked(
                    event,
                    expected_source_envelope_id=expected_source_envelope_id,
                    now=now,
                    authentication=authentication,
                )
            lock_result = self._writer_mutex.acquire()
            self._last_writer_lock = lock_result.to_dict()
            if not lock_result.acquired:
                event_map = _mapping(event)
                routing = _mapping(event_map.get("routing"))
                reason = lock_result.reason or lock_result.status
                self._rejected_count += 1
                self._last_decision = {
                    "status": "writer_lock_unavailable",
                    "reason": reason,
                    "receipt_written": False,
                }
                return PresenceIntentGatewayResult(
                    ok=False,
                    accepted=False,
                    status="writer_lock_unavailable",
                    reasons=(reason,),
                    event_id=_safe_id(event_map.get("event_id")),
                    intent=_bounded_text(_mapping(event_map.get("intent")).get("name")),
                    required_core_route=_bounded_text(routing.get("required_core_route")),
                    receipt_id="",
                    receipt_path="",
                    receipt_written=False,
                    validation={},
                )
            try:
                return self._evaluate_locked(
                    event,
                    expected_source_envelope_id=expected_source_envelope_id,
                    now=now,
                    authentication=authentication,
                )
            finally:
                self._writer_lock_release_error = self._writer_mutex.release()

    def _evaluate_locked(
        self,
        event: Mapping[str, Any] | None,
        *,
        expected_source_envelope_id: str,
        now: str | datetime | None,
        authentication: Mapping[str, Any] | None,
    ) -> PresenceIntentGatewayResult:
        durable_sequence_error = self._refresh_durable_sequence()
        if durable_sequence_error:
            event_map = _mapping(event)
            routing = _mapping(event_map.get("routing"))
            return PresenceIntentGatewayResult(
                ok=False,
                accepted=False,
                status="receipt_state_invalid",
                reasons=(durable_sequence_error,),
                event_id=_safe_id(event_map.get("event_id")),
                intent=_bounded_text(_mapping(event_map.get("intent")).get("name")),
                required_core_route=_bounded_text(routing.get("required_core_route")),
                receipt_id="",
                receipt_path="",
                receipt_written=False,
                validation={},
            )
        validation = validate_presence_intent_event(
            event,
            now=now,
            expected_adapter_id=self.adapter_id,
            expected_session_id=self.session_id,
            expected_source_envelope_id=expected_source_envelope_id,
            last_event_sequence=self._last_event_sequence,
        )
        event_map = _mapping(event)
        routing = _mapping(event_map.get("routing"))
        authentication_map = _mapping(authentication)
        authentication_required = authentication is not None
        authentication_ok = (
            not authentication_required
            or authentication_map.get("ok") is True
            and authentication_map.get("authenticated") is True
        )
        authentication_reasons = (
            tuple(f"ipc_{reason}" for reason in authentication_map.get("reasons", []) if str(reason))
            if authentication_required and not authentication_ok
            else ()
        )
        decision_reasons = tuple(dict.fromkeys((*validation.reasons, *authentication_reasons)))
        accepted = validation.ok and authentication_ok
        decision_status = "accepted_for_core_routing_not_dispatched" if accepted else "rejected"
        receipt = build_presence_intent_receipt(
            event=event_map,
            validation=validation,
            decision_status=decision_status,
            accepted=accepted,
            decision_reasons=decision_reasons,
            authentication=authentication_map if authentication_required else None,
            recorded_at=now,
        )
        try:
            receipt_path = self.receipt_store.write(receipt)
        except (OSError, TypeError, ValueError) as exc:
            reason = _bounded_text(str(exc)) or type(exc).__name__
            self._rejected_count += 1
            self._last_decision = {
                "status": "receipt_failed",
                "event_id": validation.event_id,
                "intent": validation.intent,
                "reason": reason,
                "receipt_written": False,
            }
            return PresenceIntentGatewayResult(
                ok=False,
                accepted=False,
                status="receipt_failed",
                reasons=(reason,),
                event_id=validation.event_id,
                intent=validation.intent,
                required_core_route=_bounded_text(routing.get("required_core_route")),
                receipt_id=_bounded_text(receipt.get("receipt_id"), limit=64),
                receipt_path="",
                receipt_written=False,
                validation={
                    **validation.to_dict(),
                    "ipc_authentication": authentication_map,
                },
            )

        if accepted:
            self._last_event_sequence = validation.event_sequence
            self._accepted_count += 1
        else:
            self._rejected_count += 1
        receipt_id = _bounded_text(receipt.get("receipt_id"), limit=64)
        required_route = _bounded_text(routing.get("required_core_route"))
        self._last_decision = {
            "status": decision_status,
            "event_id": validation.event_id,
            "intent": validation.intent,
            "required_core_route": required_route,
            "receipt_id": receipt_id,
            "receipt_path": str(receipt_path),
            "receipt_written": True,
            "dispatch_attempted": False,
        }
        return PresenceIntentGatewayResult(
            ok=accepted,
            accepted=accepted,
            status=decision_status,
            reasons=decision_reasons,
            event_id=validation.event_id,
            intent=validation.intent,
            required_core_route=required_route,
            receipt_id=receipt_id,
            receipt_path=str(receipt_path),
            receipt_written=True,
            validation={
                **validation.to_dict(),
                "ipc_authentication": authentication_map,
            },
        )

    def readback(self) -> dict[str, Any]:
        with self._lock:
            return {
                "kind": "francis.grounded_presence.intent_gateway_readback",
                "status": "receipt_state_invalid" if self._durable_sequence_error else "default_deny_receipt_only",
                "adapter_id": self.adapter_id,
                "session_id": self.session_id,
                "accepted_count": self._accepted_count,
                "rejected_count": self._rejected_count,
                "last_event_sequence": self._last_event_sequence,
                "durable_session_sequence_state": not self._durable_sequence_error,
                "durable_replay_state": "accepted_intent_receipt_sequence_watermark",
                "durable_sequence_error": self._durable_sequence_error,
                "cross_process_writer_lock": {
                    "kind": "windows_named_mutex",
                    "name": self._writer_mutex.name,
                    "last_acquire": dict(self._last_writer_lock),
                    "release_error": self._writer_lock_release_error,
                },
                "last_decision": dict(self._last_decision),
                "dispatch_supported": False,
                "dispatch_attempted": False,
                "writes_intent_receipts": True,
                "writes_memory": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

    def _refresh_durable_sequence(self) -> str:
        try:
            durable_sequence = self.receipt_store.highest_accepted_sequence(
                adapter_id=self.adapter_id,
                session_id=self.session_id,
                refresh=True,
            )
        except (OSError, TypeError, ValueError) as exc:
            self._durable_sequence_error = _bounded_text(str(exc)) or type(exc).__name__
            return self._durable_sequence_error
        self._durable_sequence_error = ""
        self._last_event_sequence = max(self._last_event_sequence, durable_sequence)
        return ""


def build_presence_intent_receipt(
    *,
    event: Mapping[str, Any],
    validation: PresenceIntentValidation,
    decision_status: str,
    accepted: bool | None = None,
    decision_reasons: tuple[str, ...] | None = None,
    authentication: Mapping[str, Any] | None = None,
    recorded_at: str | datetime | None = None,
) -> dict[str, Any]:
    if decision_status not in {"accepted_for_core_routing_not_dispatched", "rejected"}:
        raise ValueError("presence_intent_decision_status_invalid")
    event_map = _mapping(event)
    adapter = _mapping(event_map.get("adapter"))
    source = _mapping(event_map.get("source"))
    intent = _mapping(event_map.get("intent"))
    target = _mapping(intent.get("target"))
    routing = _mapping(event_map.get("routing"))
    authentication_map = _mapping(authentication)
    normalized_accepted = validation.ok if accepted is None else bool(accepted)
    normalized_reasons = validation.reasons if decision_reasons is None else tuple(decision_reasons)
    if (decision_status == "accepted_for_core_routing_not_dispatched") is not normalized_accepted:
        raise ValueError("presence_intent_decision_acceptance_mismatch")
    authentication_required = authentication is not None
    application_authenticated = (
        authentication_required
        and authentication_map.get("ok") is True
        and authentication_map.get("authenticated") is True
    )
    event_id = _safe_id(validation.event_id) or "invalid_event"
    recorded_dt = _parse_datetime(recorded_at)
    if recorded_at is not None and recorded_dt is None:
        raise ValueError("presence_intent_receipt_recorded_at_invalid")
    recorded_dt = recorded_dt or datetime.now(UTC)
    receipt_id = _intent_receipt_id(
        event_id=event_id,
        decision_status=decision_status,
        reasons=normalized_reasons,
    )
    return {
        "kind": PRESENCE_INTENT_RECEIPT_KIND,
        "schema_version": PRESENCE_INTENT_RECEIPT_SCHEMA_VERSION,
        "schema_path": PRESENCE_INTENT_RECEIPT_SCHEMA_PATH,
        "receipt_id": receipt_id,
        "recorded_at": recorded_dt.isoformat(),
        "decision": {
            "status": decision_status,
            "accepted": normalized_accepted,
            "reasons": list(normalized_reasons),
            "dispatch_attempted": False,
            "dispatch_allowed": False,
            "mutation_applied": False,
        },
        "event": {
            "event_id": event_id,
            "intent": validation.intent or "unknown",
            "intent_class": _bounded_text(intent.get("class")) or "unknown",
            "event_sequence": validation.event_sequence,
            "adapter_id": _safe_id(adapter.get("id")) or "unknown",
            "session_id": _safe_id(adapter.get("session_id")) or "unknown",
            "source_envelope_id": _safe_id(source.get("envelope_id")) or "unknown",
            "source_sequence": _nonnegative_int(source.get("sequence")),
            "target_kind": _bounded_text(target.get("kind")) or "none",
            "target_id": _safe_id(target.get("id")),
            "required_core_route": _bounded_text(routing.get("required_core_route")) or "unknown",
            "raw_event_persisted": False,
        },
        "security": {
            "application_authenticated": application_authenticated,
            "authentication_status": (
                "hmac_sha256_verified"
                if application_authenticated
                else "not_evaluated_internal_gateway"
                if not authentication_required
                else "hmac_sha256_rejected"
            ),
            "authentication_key_id": _safe_id(authentication_map.get("key_id")),
            "digest_valid": validation.digest_valid,
            "expired": validation.expired,
            "replayed": validation.replayed,
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
            "intent_not_dispatched",
            "raw_event_not_persisted",
            *([] if application_authenticated else ["application_authentication_not_verified"]),
        ],
    }


def _intent_receipt_id(*, event_id: str, decision_status: str, reasons: tuple[str, ...]) -> str:
    seed = "|".join((event_id, decision_status, *reasons))
    return f"gpr_{hashlib.sha256(seed.encode()).hexdigest()[:32]}"


def _required_id(value: Any, error: str) -> str:
    normalized = _safe_id(value)
    if not normalized:
        raise ValueError(error)
    return normalized


def _safe_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _nonnegative_int(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def _positive_int(value: Any) -> int:
    parsed = _nonnegative_int(value)
    if parsed <= 0:
        raise ValueError("presence_intent_receipt_sequence_invalid")
    return parsed


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]


def _read_intent_receipt(path: Path) -> dict[str, Any]:
    try:
        if path.stat().st_size > PRESENCE_INTENT_RECEIPT_MAX_BYTES:
            raise ValueError("presence_intent_receipt_oversized")
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("presence_intent_receipt_corrupt") from exc
    if not isinstance(payload, dict) or payload.get("kind") != PRESENCE_INTENT_RECEIPT_KIND:
        raise ValueError("presence_intent_receipt_corrupt")
    return payload


def _same_receipt_payload(existing: Mapping[str, Any], candidate: Mapping[str, Any]) -> bool:
    existing_payload = dict(existing)
    candidate_payload = dict(candidate)
    existing_payload.pop("recorded_at", None)
    candidate_payload.pop("recorded_at", None)
    return existing_payload == candidate_payload


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
