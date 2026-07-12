from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from francis.unreal_presence_intents import (
    LocalJsonPresenceIntentReceiptStore,
    UnrealPresenceIntentGateway,
)
from francis.world_state.presence_intent import build_presence_intent_event


ISSUED_AT = "2026-07-09T20:00:00+00:00"
NOW = "2026-07-09T20:00:00.500000+00:00"
SOURCE_ENVELOPE_ID = "gpe_0123456789abcdef0123456789abcdef"


def _event(*, sequence: int = 1, intent: str = "request_review") -> dict[str, Any]:
    return build_presence_intent_event(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        event_sequence=sequence,
        source_envelope_id=SOURCE_ENVELOPE_ID,
        source_sequence=4,
        intent=intent,
        issued_at=ISSUED_AT,
    )


def _schema() -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_intent_receipt.schema.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _gateway(tmp_path: Path) -> UnrealPresenceIntentGateway:
    return UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=LocalJsonPresenceIntentReceiptStore(tmp_path / "receipts"),
    )


def test_gateway_receipts_valid_intent_without_dispatching_it(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)

    result = gateway.evaluate(
        _event(intent="request_panic_stop"),
        expected_source_envelope_id=SOURCE_ENVELOPE_ID,
        now=NOW,
    )

    assert result.ok is True
    assert result.accepted is True
    assert result.status == "accepted_for_core_routing_not_dispatched"
    assert result.required_core_route == "/takeover/panic-stop"
    assert result.to_dict()["dispatch_attempted"] is False
    assert result.to_dict()["mutation_applied"] is False
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(receipt)
    assert receipt["decision"]["dispatch_allowed"] is False
    assert receipt["event"]["raw_event_persisted"] is False
    assert "integrity" not in receipt


def test_gateway_receipts_tampered_intent_as_rejected(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    event = _event()
    event["routing"]["dispatch_allowed"] = True

    result = gateway.evaluate(event, now=NOW)

    assert result.ok is False
    assert result.accepted is False
    assert result.status == "rejected"
    assert "dispatch_authority_drift" in result.reasons
    assert "event_digest_mismatch" in result.reasons
    assert result.receipt_written is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(receipt)
    assert receipt["decision"]["accepted"] is False


def test_gateway_rejects_replay_and_accepts_next_sequence(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)
    first = _event(sequence=1)
    second = _event(sequence=2)

    assert gateway.evaluate(first, now=NOW).accepted is True
    replay = gateway.evaluate(first, now=NOW)
    assert replay.accepted is False
    assert "event_sequence_replayed" in replay.reasons
    assert gateway.evaluate(second, now=NOW).accepted is True
    readback = gateway.readback()
    assert readback["last_event_sequence"] == 2
    assert readback["accepted_count"] == 2
    assert readback["rejected_count"] == 1


def test_gateway_restores_durable_sequence_and_rejects_replay_after_restart(tmp_path: Path) -> None:
    store = LocalJsonPresenceIntentReceiptStore(tmp_path / "receipts")
    first_gateway = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=store,
    )
    event = _event(sequence=1)

    assert first_gateway.evaluate(event, now=NOW).accepted is True

    restarted_gateway = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=store,
    )
    replay = restarted_gateway.evaluate(event, now=NOW)
    repeated_replay = restarted_gateway.evaluate(event, now="2026-07-09T20:00:00.750000+00:00")

    assert restarted_gateway.readback()["durable_session_sequence_state"] is True
    assert restarted_gateway.readback()["last_event_sequence"] == 1
    assert replay.accepted is False
    assert "event_sequence_replayed" in replay.reasons
    assert repeated_replay.status == "rejected"
    assert repeated_replay.receipt_written is True
    assert repeated_replay.receipt_path == replay.receipt_path


@pytest.mark.skipif(os.name != "nt", reason="Windows named mutex proof requires Windows")
def test_gateway_named_mutex_serializes_independent_receipt_stores(tmp_path: Path) -> None:
    root = tmp_path / "receipts"
    first = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=LocalJsonPresenceIntentReceiptStore(root),
    )
    second = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=LocalJsonPresenceIntentReceiptStore(root),
    )
    event = _event(sequence=1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(
                lambda gateway: gateway.evaluate(event, now=NOW),
                (first, second),
            )
        )

    assert sum(result.accepted for result in results) == 1
    rejected = next(result for result in results if not result.accepted)
    assert "event_sequence_replayed" in rejected.reasons
    assert first.readback()["cross_process_writer_lock"]["kind"] == "windows_named_mutex"
    assert second.readback()["cross_process_writer_lock"]["kind"] == "windows_named_mutex"


def test_gateway_receipt_failure_does_not_consume_event_sequence(tmp_path: Path) -> None:
    store = _FailOnceReceiptStore(LocalJsonPresenceIntentReceiptStore(tmp_path / "receipts"))
    gateway = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=store,
    )
    event = _event(sequence=1)

    failed = gateway.evaluate(event, now=NOW)
    retried = gateway.evaluate(event, now=NOW)

    assert failed.status == "receipt_failed"
    assert failed.accepted is False
    assert retried.accepted is True
    assert gateway.readback()["last_event_sequence"] == 1


def test_gateway_fails_closed_when_durable_receipt_state_is_corrupt(tmp_path: Path) -> None:
    store = LocalJsonPresenceIntentReceiptStore(tmp_path / "receipts")
    store.root.mkdir(parents=True)
    (store.root / "gpr_corrupt.json").write_text("{", encoding="utf-8")
    gateway = UnrealPresenceIntentGateway(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        receipt_store=store,
    )

    result = gateway.evaluate(_event(), now=NOW)

    assert gateway.readback()["status"] == "receipt_state_invalid"
    assert result.status == "receipt_state_invalid"
    assert result.accepted is False
    assert result.receipt_written is False


def test_gateway_receipts_malformed_input_without_persisting_raw_event(tmp_path: Path) -> None:
    gateway = _gateway(tmp_path)

    result = gateway.evaluate({}, now=NOW)

    assert result.accepted is False
    assert result.receipt_written is True
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    Draft202012Validator(_schema(), format_checker=FormatChecker()).validate(receipt)
    assert receipt["event"]["event_id"] == "invalid_event"
    assert receipt["event"]["raw_event_persisted"] is False


class _FailOnceReceiptStore:
    def __init__(self, delegate: LocalJsonPresenceIntentReceiptStore) -> None:
        self.delegate = delegate
        self.failed = False

    def write(self, receipt: Mapping[str, Any]) -> Path:
        if not self.failed:
            self.failed = True
            raise OSError("simulated_receipt_failure")
        return self.delegate.write(receipt)

    def highest_accepted_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        refresh: bool = False,
    ) -> int:
        return self.delegate.highest_accepted_sequence(
            adapter_id=adapter_id,
            session_id=session_id,
            refresh=refresh,
        )
