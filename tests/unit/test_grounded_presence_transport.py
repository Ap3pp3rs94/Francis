from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError
from referencing import Registry, Resource

from francis.world_state.presence import build_grounded_presence_snapshot
from francis.world_state.presence_transport import (
    PresenceReplayGuard,
    bind_presence_transport_envelope,
    build_presence_transport_envelope,
    validate_presence_transport_envelope,
)


ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT_SCHEMA_PATH = ROOT / "schemas" / "grounded_presence_snapshot.schema.json"
ENVELOPE_SCHEMA_PATH = ROOT / "schemas" / "grounded_presence_transport_envelope.schema.json"
ISSUED_AT = "2026-07-09T20:00:00+00:00"


def _snapshot() -> dict[str, Any]:
    return build_grounded_presence_snapshot(
        briefing={
            "headline": "Grounded presence is ready for renderer projection.",
            "generated_at": "2026-07-09T19:59:59+00:00",
        },
        operator={"available": True, "observed_at": "2026-07-09T19:59:59+00:00"},
        orb={
            "available": True,
            "observed_at": "2026-07-09T19:59:59+00:00",
            "state": {
                "semantic_state": "idle",
                "render_state": "ambient_rest",
                "activity_intensity": {"level": "ambient"},
                "incident_pressure": {"level": "quiet"},
                "handback_state": {"state": "none"},
            },
        },
        generated_at=ISSUED_AT,
    )


def _envelope(*, sequence: int = 1) -> dict[str, Any]:
    return build_presence_transport_envelope(
        snapshot=_snapshot(),
        adapter_id="unreal_presence_1",
        session_id="session_1",
        sequence=sequence,
        issued_at=ISSUED_AT,
        ttl_ms=2_000,
    )


def _validator() -> Draft202012Validator:
    snapshot_schema = json.loads(SNAPSHOT_SCHEMA_PATH.read_text(encoding="utf-8"))
    envelope_schema = json.loads(ENVELOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(snapshot_schema)
    Draft202012Validator.check_schema(envelope_schema)
    registry = Registry().with_resource(
        snapshot_schema["$id"],
        Resource.from_contents(snapshot_schema),
    )
    return Draft202012Validator(
        envelope_schema,
        registry=registry,
        format_checker=FormatChecker(),
    )


def _digest(payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_transport_envelope_validates_and_keeps_binding_truthful() -> None:
    envelope = _envelope()

    _validator().validate(envelope)
    validation = validate_presence_transport_envelope(
        envelope,
        now="2026-07-09T20:00:01+00:00",
        expected_adapter_id="unreal_presence_1",
        expected_session_id="session_1",
    )

    assert validation.ok is True
    assert envelope["transport"]["binding_status"] == "unbound"
    assert envelope["transport"]["network_allowed"] is False
    assert envelope["authority"]["grants_execution_authority"] is False
    assert "ipc_hmac_authentication_required_at_binding" in envelope["limitations"]
    assert "durable_consumer_deduplication_required" in envelope["limitations"]


def test_transport_binding_produces_a_valid_named_pipe_envelope_copy() -> None:
    unbound = _envelope()

    bound = bind_presence_transport_envelope(
        unbound,
        binding_status="windows_named_pipe",
        endpoint_id="francis.grounded_presence.unreal_presence_1",
    )

    _validator().validate(bound)
    validation = validate_presence_transport_envelope(
        bound,
        now="2026-07-09T20:00:01+00:00",
    )
    assert validation.ok is True
    assert unbound["transport"]["binding_status"] == "unbound"
    assert bound["transport"]["binding_status"] == "windows_named_pipe"
    assert bound["transport"]["runtime_enforcement_status"] == "publisher_guard_active"
    assert "transport_binding_not_implemented" not in bound["limitations"]


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("adapter_id", "", "grounded_presence_transport_adapter_id_invalid"),
        ("adapter_id", "invalid adapter", "grounded_presence_transport_adapter_id_invalid"),
        ("session_id", "", "grounded_presence_transport_session_id_invalid"),
        ("sequence", 0, "positive_integer_required"),
        ("sequence", 1.5, "positive_integer_required"),
        ("ttl_ms", 5001, "grounded_presence_transport_ttl_exceeds_maximum"),
    ],
)
def test_transport_builder_rejects_invalid_bounds(field: str, value: Any, reason: str) -> None:
    kwargs: dict[str, Any] = {
        "snapshot": _snapshot(),
        "adapter_id": "unreal_presence_1",
        "session_id": "session_1",
        "sequence": 1,
        "issued_at": ISSUED_AT,
        "ttl_ms": 2_000,
    }
    kwargs[field] = value

    with pytest.raises(ValueError, match=reason):
        build_presence_transport_envelope(**kwargs)


def test_transport_validation_rejects_payload_tampering() -> None:
    envelope = _envelope()
    envelope["payload"]["presence"]["headline"] = "Tampered after envelope creation."

    validation = validate_presence_transport_envelope(
        envelope,
        now="2026-07-09T20:00:01+00:00",
    )

    assert validation.ok is False
    assert validation.digest_valid is False
    assert "payload_digest_mismatch" in validation.reasons


def test_transport_validation_rejects_expired_envelope() -> None:
    validation = validate_presence_transport_envelope(
        _envelope(),
        now="2026-07-09T20:00:03+00:00",
    )

    assert validation.ok is False
    assert validation.expired is True
    assert "envelope_expired" in validation.reasons


def test_transport_validation_rejects_replayed_or_wrong_session_envelope() -> None:
    validation = validate_presence_transport_envelope(
        _envelope(sequence=2),
        now="2026-07-09T20:00:01+00:00",
        expected_adapter_id="unreal_presence_1",
        expected_session_id="session_other",
        last_sequence=2,
    )

    assert validation.ok is False
    assert validation.replayed is True
    assert "session_identity_mismatch" in validation.reasons
    assert "sequence_replayed" in validation.reasons


def test_replay_guard_accepts_only_strictly_newer_sequence_per_session() -> None:
    guard = PresenceReplayGuard()
    first = _envelope(sequence=1)
    second = _envelope(sequence=2)

    assert guard.accept(first, now="2026-07-09T20:00:01+00:00").ok is True
    replay = guard.accept(first, now="2026-07-09T20:00:01+00:00")
    assert replay.ok is False
    assert replay.replayed is True
    assert guard.accept(second, now="2026-07-09T20:00:01+00:00").ok is True
    assert guard.last_sequence(adapter_id="unreal_presence_1", session_id="session_1") == 2
    assert guard.describe()["durable"] is False


def test_transport_validation_rejects_envelope_authority_drift() -> None:
    envelope = _envelope()
    envelope["authority"]["grants_desktop_authority"] = True

    validation = validate_presence_transport_envelope(
        envelope,
        now="2026-07-09T20:00:01+00:00",
    )

    assert validation.ok is False
    assert "grants_desktop_authority_drift" in validation.reasons
    with pytest.raises(ValidationError):
        _validator().validate(envelope)


def test_transport_validation_rejects_rehashed_payload_authority_drift() -> None:
    envelope = _envelope()
    envelope["payload"]["authority"]["grants_execution_authority"] = True
    envelope["integrity"]["payload_digest"] = _digest(envelope["payload"])

    validation = validate_presence_transport_envelope(
        envelope,
        now="2026-07-09T20:00:01+00:00",
    )

    assert validation.ok is False
    assert validation.digest_valid is True
    assert "payload_grants_execution_authority_drift" in validation.reasons


def test_transport_builder_deep_copies_snapshot() -> None:
    snapshot = _snapshot()
    original = deepcopy(snapshot)
    envelope = build_presence_transport_envelope(
        snapshot=snapshot,
        adapter_id="unreal_presence_1",
        session_id="session_1",
        sequence=1,
        issued_at=ISSUED_AT,
    )

    snapshot["presence"]["headline"] = "Changed by caller."

    assert envelope["payload"] == original
