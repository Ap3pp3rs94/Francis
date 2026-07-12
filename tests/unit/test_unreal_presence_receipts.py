from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from francis.unreal_presence_receipts import (
    LocalJsonPresenceDeliveryReceiptStore,
    build_presence_delivery_attempt,
    build_presence_delivery_journal,
    build_presence_delivery_receipt,
    presence_delivery_attempt_id,
    presence_delivery_journal_id,
    presence_delivery_receipt_id,
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
ENDPOINT_ID = "francis.grounded_presence.unreal_presence_1"
AUTHENTICATION_KEY_ID = "presence_test_v1"
AUTHENTICATION_SECRET = b"francis-presence-receipt-test-secret"


def _envelope(*, bound: bool = True, sequence: int = 1) -> dict[str, Any]:
    snapshot = build_grounded_presence_snapshot(
        briefing={
            "headline": "Deliver the receipt-linked handback.",
            "focus": [
                {
                    "id": "mission_1",
                    "objective": "Review the operation.",
                    "recommended_action": "review_result",
                    "current_task": {"mission_id": "mission_1", "operation_id": "operation_1"},
                }
            ],
            "memory_receipts": [
                {
                    "receipt_id": "source_receipt_1",
                    "mission_id": "mission_1",
                    "operation_id": "operation_1",
                }
            ],
            "generated_at": "2026-07-09T19:59:59+00:00",
        },
        operator={"available": True, "observed_at": "2026-07-09T19:59:59+00:00"},
        orb={"available": True, "observed_at": "2026-07-09T19:59:59+00:00", "state": {}},
        generated_at=ISSUED_AT,
    )
    envelope = build_presence_transport_envelope(
        snapshot=snapshot,
        adapter_id="unreal_presence_1",
        session_id="session_1",
        sequence=sequence,
        issued_at=ISSUED_AT,
    )
    if not bound:
        return envelope
    return bind_presence_transport_envelope(
        envelope,
        binding_status="windows_named_pipe",
        endpoint_id=ENDPOINT_ID,
    )


def _schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_delivery_receipt.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _journal_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_delivery_journal.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _attempt_schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_delivery_attempt.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _authentication_kwargs(envelope: dict[str, Any]) -> dict[str, Any]:
    authenticator = PresenceIpcAuthenticator(
        key_id=AUTHENTICATION_KEY_ID,
        secret=AUTHENTICATION_SECRET,
    )
    request = authenticator.sign(
        envelope,
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
        nonce="0123456789abcdef0123456789abcdef",
    )
    acknowledgement = build_presence_delivery_ack(
        request_message=request,
        endpoint_id=ENDPOINT_ID,
        consumer_status="accepted_for_render",
        acknowledged_at="2026-07-09T20:00:00.500000+00:00",
    )
    return {"request_message": request, "acknowledgement": acknowledgement}


def _receipt(*, sequence: int = 1, recorded_at: str | None = None) -> dict[str, Any]:
    envelope = _envelope(sequence=sequence)
    return build_presence_delivery_receipt(
        envelope=envelope,
        endpoint_id=ENDPOINT_ID,
        bytes_written=12_345,
        recorded_at=recorded_at,
        **_authentication_kwargs(envelope),
    )


def test_delivery_receipt_is_versioned_metadata_only_and_source_linked() -> None:
    receipt = _receipt(
        recorded_at="2026-07-09T20:00:01+00:00",
    )

    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(receipt)
    assert receipt["evidence"]["source_receipt_ids"] == ["source_receipt_1"]
    assert receipt["evidence"]["payload_persisted"] is False
    assert receipt["authority"]["grants_execution_authority"] is False
    assert receipt["security"]["application_authenticated"] is True
    assert receipt["delivery"]["consumer_durable_deduplication"] is True
    assert AUTHENTICATION_SECRET.decode("ascii") not in json.dumps(receipt)
    assert "payload" not in receipt


def test_delivery_receipt_store_is_atomic_and_idempotently_discoverable(tmp_path: Path) -> None:
    receipt = _receipt(
        recorded_at="2026-07-09T20:00:01+00:00",
    )
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")

    path = store.write(receipt)

    assert path.is_file()
    assert not list(path.parent.glob("*.tmp"))
    assert store.has_delivery(
        envelope_id=receipt["delivery"]["envelope_id"],
        endpoint_id=ENDPOINT_ID,
    )
    assert json.loads(path.read_text(encoding="utf-8")) == receipt
    later_copy = _receipt(
        recorded_at="2026-07-09T20:00:02+00:00",
    )
    assert store.write(later_copy) == path
    assert json.loads(path.read_text(encoding="utf-8"))["recorded_at"] == "2026-07-09T20:00:01+00:00"
    assert (
        store.highest_delivered_sequence(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
        )
        == 1
    )


def test_delivery_receipt_store_restores_highest_session_sequence(tmp_path: Path) -> None:
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    for sequence in (1, 3, 2):
        store.write(
            _receipt(
                sequence=sequence,
                recorded_at=f"2026-07-09T20:00:0{sequence}+00:00",
            )
        )

    assert (
        store.highest_delivered_sequence(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
        )
        == 3
    )


def test_delivery_receipt_store_force_refresh_observes_another_writer(tmp_path: Path) -> None:
    root = tmp_path / "receipts"
    first = LocalJsonPresenceDeliveryReceiptStore(root)
    second = LocalJsonPresenceDeliveryReceiptStore(root)
    assert (
        first.highest_delivered_sequence(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
        )
        == 0
    )
    second.write(_receipt())

    assert (
        first.highest_delivered_sequence(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
            refresh=True,
        )
        == 1
    )


def test_delivery_journal_is_versioned_metadata_only_and_restart_discoverable(tmp_path: Path) -> None:
    envelope = _envelope()
    journal = build_presence_delivery_journal(
        envelope=envelope,
        endpoint_id=ENDPOINT_ID,
        bytes_written=12_345,
        recorded_at="2026-07-09T20:00:01+00:00",
        **_authentication_kwargs(envelope),
    )
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")

    Draft202012Validator(_journal_schema(), format_checker=FormatChecker()).validate(journal)
    path = store.write_pending_delivery(journal)
    restarted = LocalJsonPresenceDeliveryReceiptStore(store.root)
    restored = restarted.read_pending_delivery(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )

    assert path.is_file()
    assert restored == journal
    assert restored["persistence"]["payload_persisted"] is False
    assert restored["persistence"]["safe_redelivery"] is True
    assert restored["persistence"]["consumer_durable_deduplication"] is True
    assert "payload" not in restored
    restarted.clear_pending_delivery(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )
    assert not path.exists()


def test_delivery_journal_id_is_stable_per_session_endpoint() -> None:
    first = presence_delivery_journal_id(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )
    second = presence_delivery_journal_id(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )

    assert first == second
    assert first.startswith("gpp_")


def test_delivery_attempt_is_versioned_payload_free_and_restart_discoverable(tmp_path: Path) -> None:
    envelope = _envelope()
    authentication = _authentication_kwargs(envelope)
    attempt = build_presence_delivery_attempt(
        envelope=envelope,
        endpoint_id=ENDPOINT_ID,
        request_message=authentication["request_message"],
        recorded_at="2026-07-09T20:00:00.250000+00:00",
    )
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")

    Draft202012Validator(_attempt_schema(), format_checker=FormatChecker()).validate(attempt)
    path = store.write_pending_attempt(attempt)
    restarted = LocalJsonPresenceDeliveryReceiptStore(store.root)
    restored = restarted.read_pending_attempt(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )

    assert restored == attempt
    assert restored["reconciliation"]["exact_envelope_required"] is True
    assert restored["reconciliation"]["delivery_acknowledged"] is False
    assert "payload" not in restored
    assert AUTHENTICATION_SECRET.decode("ascii") not in json.dumps(restored)
    restarted.clear_pending_attempt(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )
    assert not path.exists()


def test_delivery_attempt_id_is_stable_per_session_endpoint() -> None:
    first = presence_delivery_attempt_id(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )
    second = presence_delivery_attempt_id(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )

    assert first == second
    assert first.startswith("gpt_")


def test_delivery_attempt_store_fails_closed_on_corrupt_recovery_state(tmp_path: Path) -> None:
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    attempt_id = presence_delivery_attempt_id(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        endpoint_id=ENDPOINT_ID,
    )
    path = store.root / "pending_attempt" / f"{attempt_id}.json"
    path.parent.mkdir(parents=True)
    path.write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="presence_delivery_attempt_corrupt"):
        store.read_pending_attempt(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
        )


def test_delivery_receipt_store_fails_closed_on_corrupt_sequence_evidence(tmp_path: Path) -> None:
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    store.root.mkdir(parents=True)
    (store.root / "gpd_corrupt.json").write_text("{", encoding="utf-8")

    with pytest.raises(ValueError, match="presence_delivery_receipt_corrupt"):
        store.highest_delivered_sequence(
            adapter_id="unreal_presence_1",
            session_id="session_1",
            endpoint_id=ENDPOINT_ID,
        )


def test_delivery_receipt_id_is_stable_for_one_envelope_endpoint_pair() -> None:
    envelope_id = _envelope()["envelope_id"]

    first = presence_delivery_receipt_id(envelope_id=envelope_id, endpoint_id=ENDPOINT_ID)
    second = presence_delivery_receipt_id(envelope_id=envelope_id, endpoint_id=ENDPOINT_ID)

    assert first == second
    assert first.startswith("gpd_")


def test_delivery_receipt_rejects_unbound_transport() -> None:
    with pytest.raises(ValueError, match="presence_delivery_transport_not_bound"):
        envelope = _envelope(bound=False)
        build_presence_delivery_receipt(
            envelope=envelope,
            endpoint_id=ENDPOINT_ID,
            bytes_written=12_345,
            **_authentication_kwargs(envelope),
        )
