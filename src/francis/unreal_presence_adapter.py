from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from threading import Lock
from typing import Any, Mapping

from francis.unreal_presence_receipts import PresenceDeliveryReceiptStore
from francis.world_state.presence_transport import (
    GROUNDED_PRESENCE_TRANSPORT_DEFAULT_TTL_MS,
    GROUNDED_PRESENCE_TRANSPORT_MAX_TTL_MS,
    build_presence_transport_envelope,
    validate_presence_transport_envelope,
)


@dataclass(frozen=True, slots=True)
class UnrealPresenceAdapterConfig:
    adapter_id: str
    session_id: str
    ttl_ms: int = GROUNDED_PRESENCE_TRANSPORT_DEFAULT_TTL_MS
    engine_version: str = "5.8"

    def __post_init__(self) -> None:
        if not _contract_id(self.adapter_id):
            raise ValueError("unreal_presence_adapter_id_invalid")
        if not _contract_id(self.session_id):
            raise ValueError("unreal_presence_session_id_invalid")
        if isinstance(self.ttl_ms, bool) or not isinstance(self.ttl_ms, int):
            raise ValueError("unreal_presence_ttl_invalid")
        if not 0 < self.ttl_ms <= GROUNDED_PRESENCE_TRANSPORT_MAX_TTL_MS:
            raise ValueError("unreal_presence_ttl_invalid")
        if self.engine_version != "5.8":
            raise ValueError("unreal_presence_engine_version_invalid")

    def to_dict(self) -> dict[str, Any]:
        return {
            "adapter_id": self.adapter_id,
            "adapter_kind": "unreal",
            "session_id": self.session_id,
            "engine": "Unreal Engine",
            "engine_version": self.engine_version,
            "role": "governed_renderer_adapter",
            "ttl_ms": self.ttl_ms,
            "technology_selection_status": "operator_confirmation_required",
            "project_selection_status": "operator_confirmation_required",
            "local_only": True,
            "read_only": True,
            "allow_network": False,
            "allow_desktop": False,
            "allow_memory_write": False,
            "allow_approval": False,
        }


@dataclass(frozen=True, slots=True)
class UnrealPresenceProjectionResult:
    ok: bool
    accepted: bool
    status: str
    denial_reason: str
    sequence: int
    envelope_id: str
    envelope: dict[str, Any] = field(default_factory=dict)
    validation: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "accepted": self.accepted,
            "status": self.status,
            "denial_reason": self.denial_reason,
            "sequence": self.sequence,
            "envelope_id": self.envelope_id,
            "envelope": dict(self.envelope),
            "validation": dict(self.validation),
            "delivery_attempted": False,
            "delivery_succeeded": False,
            "receipt_written": False,
            "stores_payload": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


class UnrealPresenceAdapter:
    """Core-owned envelope producer. Actual Unreal delivery remains deliberately unbound."""

    def __init__(self, config: UnrealPresenceAdapterConfig, *, sequence_floor: int = 0) -> None:
        if isinstance(sequence_floor, bool) or not isinstance(sequence_floor, int) or sequence_floor < 0:
            raise ValueError("unreal_presence_sequence_floor_invalid")
        self.config = config
        self._lock = Lock()
        self._sequence_floor = sequence_floor
        self._last_sequence = sequence_floor
        self._prepared_envelope_count = 0
        self._last_envelope: dict[str, Any] = {}
        self._last_denial_reason = ""

    @classmethod
    def from_delivery_receipts(
        cls,
        config: UnrealPresenceAdapterConfig,
        *,
        receipt_store: PresenceDeliveryReceiptStore,
    ) -> UnrealPresenceAdapter:
        endpoint_id = f"francis.grounded_presence.{config.adapter_id}"
        sequence_floor = receipt_store.highest_delivered_sequence(
            adapter_id=config.adapter_id,
            session_id=config.session_id,
            endpoint_id=endpoint_id,
            refresh=True,
        )
        return cls(config, sequence_floor=sequence_floor)

    def prepare(
        self,
        snapshot: Mapping[str, Any],
        *,
        issued_at: str | datetime | None = None,
    ) -> UnrealPresenceProjectionResult:
        with self._lock:
            sequence = self._last_sequence + 1
            try:
                envelope = build_presence_transport_envelope(
                    snapshot=snapshot,
                    adapter_id=self.config.adapter_id,
                    session_id=self.config.session_id,
                    sequence=sequence,
                    issued_at=issued_at,
                    ttl_ms=self.config.ttl_ms,
                )
                validation = validate_presence_transport_envelope(
                    envelope,
                    now=envelope["issued_at"],
                    expected_adapter_id=self.config.adapter_id,
                    expected_session_id=self.config.session_id,
                    last_sequence=self._last_sequence,
                )
            except (TypeError, ValueError) as exc:
                denial_reason = _bounded_text(str(exc)) or type(exc).__name__
                self._last_denial_reason = denial_reason
                return UnrealPresenceProjectionResult(
                    ok=False,
                    accepted=False,
                    status="rejected",
                    denial_reason=denial_reason,
                    sequence=sequence,
                    envelope_id="",
                )

            if not validation.ok:
                denial_reason = validation.reasons[0] if validation.reasons else "transport_validation_failed"
                self._last_denial_reason = denial_reason
                return UnrealPresenceProjectionResult(
                    ok=False,
                    accepted=False,
                    status="rejected",
                    denial_reason=denial_reason,
                    sequence=sequence,
                    envelope_id=str(envelope.get("envelope_id") or ""),
                    validation=validation.to_dict(),
                )

            self._last_sequence = sequence
            self._prepared_envelope_count += 1
            self._last_denial_reason = ""
            self._last_envelope = {
                "envelope_id": str(envelope.get("envelope_id") or ""),
                "sequence": sequence,
                "issued_at": str(envelope.get("issued_at") or ""),
                "expires_at": str(envelope.get("expires_at") or ""),
                "payload_digest": str(_mapping(envelope.get("integrity")).get("payload_digest") or ""),
            }
            return UnrealPresenceProjectionResult(
                ok=True,
                accepted=True,
                status="prepared_unbound",
                denial_reason="",
                sequence=sequence,
                envelope_id=self._last_envelope["envelope_id"],
                envelope=envelope,
                validation=validation.to_dict(),
            )

    def readback(self) -> dict[str, Any]:
        with self._lock:
            return {
                "kind": "francis.unreal_presence.adapter_readback",
                "status": "contract_ready_unbound",
                "config": self.config.to_dict(),
                "sequence_floor": self._sequence_floor,
                "last_sequence": self._last_sequence,
                "prepared_envelope_count": self._prepared_envelope_count,
                "last_envelope": dict(self._last_envelope),
                "last_denial_reason": self._last_denial_reason,
                "binding_status": "unbound",
                "publisher_binding_status": "binds_on_delivery",
                "sequence_recovery_supported": True,
                "sequence_recovery_source": "delivery_receipt_watermark" if self._sequence_floor else "process_start",
                "runtime_observed": False,
                "delivery_supported": False,
                "delivery_attempted": False,
                "stores_payload": False,
                "writes_memory": False,
                "writes_receipts": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }


def _contract_id(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if not text or len(text) > 160:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]
