from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from francis.unreal_presence_adapter import (
    UnrealPresenceAdapter,
    UnrealPresenceAdapterConfig,
)
from francis.unreal_presence_receipts import (
    LocalJsonPresenceDeliveryReceiptStore,
    build_presence_delivery_receipt,
)
from francis.unreal_presence_wire import (
    PRESENCE_RENDER_CHANNEL,
    PresenceIpcAuthenticator,
    build_presence_delivery_ack,
)
from francis.world_state.presence import build_grounded_presence_snapshot
from francis.world_state.presence_transport import (
    bind_presence_transport_envelope,
    build_presence_transport_envelope,
)


ISSUED_AT = "2026-07-09T20:00:00+00:00"


def _snapshot() -> dict[str, Any]:
    return build_grounded_presence_snapshot(
        briefing={
            "headline": "Core state is ready for bounded renderer projection.",
            "generated_at": "2026-07-09T19:59:59+00:00",
        },
        operator={"available": True, "observed_at": "2026-07-09T19:59:59+00:00"},
        orb={
            "available": True,
            "observed_at": "2026-07-09T19:59:59+00:00",
            "state": {"semantic_state": "idle", "render_state": "ambient_rest"},
        },
        generated_at=ISSUED_AT,
    )


def _adapter() -> UnrealPresenceAdapter:
    return UnrealPresenceAdapter(
        UnrealPresenceAdapterConfig(
            adapter_id="unreal_presence_1",
            session_id="session_1",
        )
    )


def test_adapter_prepares_validated_envelopes_without_claiming_delivery() -> None:
    adapter = _adapter()

    first = adapter.prepare(_snapshot(), issued_at=ISSUED_AT)
    second = adapter.prepare(_snapshot(), issued_at=ISSUED_AT)

    assert first.ok is True
    assert first.status == "prepared_unbound"
    assert first.sequence == 1
    assert first.validation["ok"] is True
    assert first.to_dict()["delivery_attempted"] is False
    assert second.sequence == 2
    assert adapter.readback()["last_sequence"] == 2


def test_adapter_rejects_authority_drift_without_advancing_sequence() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    snapshot["authority"]["grants_execution_authority"] = True

    rejected = adapter.prepare(snapshot, issued_at=ISSUED_AT)
    accepted = adapter.prepare(_snapshot(), issued_at=ISSUED_AT)

    assert rejected.ok is False
    assert rejected.accepted is False
    assert rejected.denial_reason == "payload_grants_execution_authority_drift"
    assert accepted.sequence == 1
    assert adapter.readback()["prepared_envelope_count"] == 1


def test_adapter_sequence_is_unique_under_concurrent_prepare() -> None:
    adapter = _adapter()

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: adapter.prepare(_snapshot(), issued_at=ISSUED_AT), range(20)))

    assert all(result.ok for result in results)
    assert sorted(result.sequence for result in results) == list(range(1, 21))
    assert adapter.readback()["prepared_envelope_count"] == 20


def test_adapter_does_not_retain_or_mutate_payload() -> None:
    adapter = _adapter()
    snapshot = _snapshot()
    original = deepcopy(snapshot)

    result = adapter.prepare(snapshot, issued_at=ISSUED_AT)
    snapshot["presence"]["headline"] = "Caller mutation."
    readback = adapter.readback()

    assert result.envelope["payload"] == original
    assert "payload" not in readback["last_envelope"]
    assert readback["stores_payload"] is False
    assert readback["writes_receipts"] is False


def test_adapter_readback_keeps_unconfirmed_unreal_choices_open() -> None:
    readback = _adapter().readback()

    assert readback["status"] == "contract_ready_unbound"
    assert readback["binding_status"] == "unbound"
    assert readback["runtime_observed"] is False
    assert readback["delivery_supported"] is False
    assert readback["config"]["technology_selection_status"] == "operator_confirmation_required"
    assert readback["config"]["project_selection_status"] == "operator_confirmation_required"
    assert readback["config"]["allow_network"] is False


def test_adapter_resumes_sequence_from_durable_delivery_receipts(tmp_path: Path) -> None:
    config = UnrealPresenceAdapterConfig(
        adapter_id="unreal_presence_1",
        session_id="session_1",
    )
    endpoint_id = "francis.grounded_presence.unreal_presence_1"
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    envelope = build_presence_transport_envelope(
        snapshot=_snapshot(),
        adapter_id=config.adapter_id,
        session_id=config.session_id,
        sequence=3,
        issued_at=ISSUED_AT,
    )
    bound = bind_presence_transport_envelope(
        envelope,
        binding_status="windows_named_pipe",
        endpoint_id=endpoint_id,
    )
    authenticator = PresenceIpcAuthenticator(
        key_id="presence_test_v1",
        secret=b"francis-presence-adapter-test-secret",
    )
    request = authenticator.sign(
        bound,
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
    )
    acknowledgement = build_presence_delivery_ack(
        request_message=request,
        endpoint_id=endpoint_id,
        consumer_status="accepted_for_render",
    )
    store.write(
        build_presence_delivery_receipt(
            envelope=bound,
            endpoint_id=endpoint_id,
            bytes_written=12_345,
            request_message=request,
            acknowledgement=acknowledgement,
            recorded_at="2026-07-09T20:00:01+00:00",
        )
    )

    adapter = UnrealPresenceAdapter.from_delivery_receipts(config, receipt_store=store)
    result = adapter.prepare(_snapshot(), issued_at=ISSUED_AT)

    assert adapter.readback()["sequence_floor"] == 3
    assert adapter.readback()["sequence_recovery_source"] == "delivery_receipt_watermark"
    assert result.sequence == 4


@pytest.mark.parametrize(
    "config",
    [
        {"adapter_id": "", "session_id": "session_1"},
        {"adapter_id": "unreal_presence_1", "session_id": "invalid session"},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "ttl_ms": 5001},
        {
            "adapter_id": "unreal_presence_1",
            "session_id": "session_1",
            "engine_version": "5.7",
        },
    ],
)
def test_adapter_config_rejects_contract_drift(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        UnrealPresenceAdapterConfig(**config)
