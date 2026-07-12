from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError

from francis.world_state.presence_intent import (
    PresenceIntentReplayGuard,
    build_presence_intent_event,
    validate_presence_intent_event,
)


ISSUED_AT = "2026-07-09T20:00:00+00:00"
SOURCE_ENVELOPE_ID = "gpe_0123456789abcdef0123456789abcdef"


def _event(intent: str = "request_context_refresh", *, sequence: int = 1) -> dict[str, Any]:
    return build_presence_intent_event(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        event_sequence=sequence,
        source_envelope_id=SOURCE_ENVELOPE_ID,
        source_sequence=4,
        intent=intent,
        issued_at=ISSUED_AT,
    )


def _validator() -> Draft202012Validator:
    path = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_intent_event.schema.json"
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


@pytest.mark.parametrize(
    ("intent", "intent_class", "route"),
    [
        ("request_context_refresh", "read_request", "/continuity/presence"),
        ("acknowledge_handback", "acknowledgement_request", "operator_review_required"),
        ("request_review", "governed_action_request", "operator_review_required"),
        ("request_panic_stop", "safety_request", "/takeover/panic-stop"),
    ],
)
def test_intent_contract_is_request_only_and_never_self_dispatches(
    intent: str,
    intent_class: str,
    route: str,
) -> None:
    event = _event(intent)

    _validator().validate(event)
    validation = validate_presence_intent_event(
        event,
        now="2026-07-09T20:00:00.500000+00:00",
        expected_adapter_id="unreal_presence_1",
        expected_session_id="session_1",
        expected_source_envelope_id=SOURCE_ENVELOPE_ID,
    )

    assert validation.ok is True
    assert event["intent"]["class"] == intent_class
    assert event["intent"]["request_only"] is True
    assert event["routing"]["required_core_route"] == route
    assert event["routing"]["dispatch_allowed"] is False
    assert event["routing"]["mutation_allowed"] is False
    assert event["authority"]["grants_execution_authority"] is False


def test_intent_contract_supports_only_typed_bounded_targets() -> None:
    event = build_presence_intent_event(
        adapter_id="unreal_presence_1",
        session_id="session_1",
        event_sequence=1,
        source_envelope_id=SOURCE_ENVELOPE_ID,
        source_sequence=4,
        intent="request_review",
        target_kind="mission",
        target_id="mission_1",
        issued_at=ISSUED_AT,
    )

    assert event["intent"]["target"] == {"kind": "mission", "id": "mission_1"}
    assert "payload" not in event
    assert "prompt" not in event


@pytest.mark.parametrize(
    "kwargs",
    [
        {"intent": "click_desktop"},
        {"intent": "request_review", "target_kind": "desktop", "target_id": "button"},
        {"intent": "request_review", "target_kind": "mission", "target_id": ""},
        {"intent": "request_review", "target_kind": "none", "target_id": "mission_1"},
        {"intent": "request_review", "ttl_ms": 2_001},
    ],
)
def test_intent_builder_rejects_unbounded_or_unknown_requests(kwargs: dict[str, Any]) -> None:
    inputs: dict[str, Any] = {
        "adapter_id": "unreal_presence_1",
        "session_id": "session_1",
        "event_sequence": 1,
        "source_envelope_id": SOURCE_ENVELOPE_ID,
        "source_sequence": 4,
        "intent": "request_context_refresh",
        "issued_at": ISSUED_AT,
    }
    inputs.update(kwargs)

    with pytest.raises(ValueError):
        build_presence_intent_event(**inputs)


def test_intent_validation_rejects_tampering_and_authority_drift() -> None:
    event = _event("request_review")
    event["routing"]["dispatch_allowed"] = True
    event["authority"]["grants_desktop_authority"] = True

    validation = validate_presence_intent_event(
        event,
        now="2026-07-09T20:00:01+00:00",
    )

    assert validation.ok is False
    assert validation.digest_valid is False
    assert "event_digest_mismatch" in validation.reasons
    assert "dispatch_authority_drift" in validation.reasons
    assert "grants_desktop_authority_drift" in validation.reasons
    with pytest.raises(ValidationError):
        _validator().validate(event)


def test_intent_validation_rejects_expiry_replay_and_source_mismatch() -> None:
    validation = validate_presence_intent_event(
        _event(sequence=2),
        now="2026-07-09T20:00:03+00:00",
        expected_source_envelope_id="gpe_aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        last_event_sequence=2,
    )

    assert validation.ok is False
    assert validation.expired is True
    assert validation.replayed is True
    assert "intent_expired" in validation.reasons
    assert "event_sequence_replayed" in validation.reasons
    assert "source_envelope_mismatch" in validation.reasons


def test_intent_replay_guard_advances_only_after_valid_event() -> None:
    guard = PresenceIntentReplayGuard()
    first = _event(sequence=1)
    second = _event(sequence=2)

    assert guard.accept(first, now="2026-07-09T20:00:00.500000+00:00").ok is True
    replay = guard.accept(first, now="2026-07-09T20:00:00.500000+00:00")
    assert replay.ok is False
    assert replay.replayed is True
    assert guard.accept(second, now="2026-07-09T20:00:00.500000+00:00").ok is True
