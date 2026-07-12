from __future__ import annotations

import json
from base64 import b64encode
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from francis.unreal_presence_adapter import UnrealPresenceAdapter, UnrealPresenceAdapterConfig
from francis.unreal_presence_wire import (
    PRESENCE_RENDER_ACK_CHANNEL,
    PRESENCE_RENDER_CHANNEL,
    PresenceIpcAuthenticator,
    build_presence_delivery_ack,
    validate_presence_delivery_ack,
)
from francis.world_state.presence import build_grounded_presence_snapshot
from francis.world_state.presence_transport import bind_presence_transport_envelope


ISSUED_AT = "2026-07-10T12:00:00+00:00"
SECRET = b"francis-presence-test-secret-32b!"
ENDPOINT_ID = "francis.grounded_presence.unreal_presence_wire"


def _authenticator() -> PresenceIpcAuthenticator:
    return PresenceIpcAuthenticator(key_id="presence_test_v1", secret=SECRET)


def _envelope() -> dict[str, Any]:
    snapshot = build_grounded_presence_snapshot(
        briefing={"headline": "Render this grounded state.", "generated_at": ISSUED_AT},
        operator={"available": True, "observed_at": ISSUED_AT},
        orb={"available": True, "observed_at": ISSUED_AT, "state": {}},
        generated_at=ISSUED_AT,
    )
    adapter = UnrealPresenceAdapter(
        UnrealPresenceAdapterConfig(
            adapter_id="unreal_presence_wire",
            session_id="session_wire",
        )
    )
    prepared = adapter.prepare(snapshot, issued_at=ISSUED_AT)
    assert prepared.ok is True
    return bind_presence_transport_envelope(
        prepared.envelope,
        binding_status="windows_named_pipe",
        endpoint_id=ENDPOINT_ID,
    )


def _schema(name: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[2] / "schemas" / name
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return schema


def test_authenticated_wire_message_is_versioned_and_secret_free() -> None:
    authenticator = _authenticator()
    message = authenticator.sign(
        _envelope(),
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
        nonce="0123456789abcdef0123456789abcdef",
    )

    Draft202012Validator(
        _schema("grounded_presence_ipc_message.schema.json"),
        format_checker=FormatChecker(),
    ).validate(message)
    validation = authenticator.validate(
        message,
        expected_channel=PRESENCE_RENDER_CHANNEL,
        expected_direction="francis_core_to_unreal",
        now="2026-07-10T12:00:00.500000+00:00",
    )

    assert validation.ok is True
    assert validation.authenticated is True
    assert validation.digest_valid is True
    assert message["authentication"]["key_id"] == "presence_test_v1"
    assert SECRET.decode("ascii") not in json.dumps(message)
    assert authenticator.describe()["secret_exposed"] is False


def test_authenticator_loads_strict_process_environment_without_exposing_secret() -> None:
    encoded = b64encode(SECRET).decode("ascii")
    authenticator = PresenceIpcAuthenticator.from_environment(
        {
            "FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID": "presence_environment_v1",
            "FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64": encoded,
        }
    )
    description = authenticator.describe()

    assert description["key_id"] == "presence_environment_v1"
    assert description["source"] == "process_environment"
    assert description["secret_exposed"] is False
    assert encoded not in json.dumps(description)


@pytest.mark.parametrize(
    ("environment", "reason"),
    [
        ({}, "presence_ipc_auth_key_id_missing"),
        (
            {"FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID": "presence_environment_v1"},
            "presence_ipc_auth_secret_missing",
        ),
        (
            {
                "FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID": "presence_environment_v1",
                "FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64": "not-base64",
            },
            "presence_ipc_auth_secret_encoding_invalid",
        ),
    ],
)
def test_authenticator_environment_loader_fails_closed(environment: dict[str, str], reason: str) -> None:
    with pytest.raises(ValueError, match=reason):
        PresenceIpcAuthenticator.from_environment(environment)


def test_authenticated_wire_message_rejects_tampering_wrong_key_and_expiry() -> None:
    authenticator = _authenticator()
    message = authenticator.sign(
        _envelope(),
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
        ttl_ms=1_000,
    )
    tampered = deepcopy(message)
    tampered["payload"]["sequence"] = 99

    tampered_result = authenticator.validate(
        tampered,
        expected_channel=PRESENCE_RENDER_CHANNEL,
        expected_direction="francis_core_to_unreal",
        now="2026-07-10T12:00:00.500000+00:00",
    )
    wrong_key = PresenceIpcAuthenticator(key_id="presence_other_v1", secret=b"another-francis-presence-secret!!")
    wrong_key_result = wrong_key.validate(
        message,
        expected_channel=PRESENCE_RENDER_CHANNEL,
        expected_direction="francis_core_to_unreal",
        now="2026-07-10T12:00:00.500000+00:00",
    )
    expired_result = authenticator.validate(
        message,
        expected_channel=PRESENCE_RENDER_CHANNEL,
        expected_direction="francis_core_to_unreal",
        now="2026-07-10T12:00:02+00:00",
    )

    assert "authentication_signature_invalid" in tampered_result.reasons
    assert "payload_digest_mismatch" in tampered_result.reasons
    assert "authentication_key_mismatch" in wrong_key_result.reasons
    assert "message_expired" in expired_result.reasons


def test_signed_delivery_ack_proves_durable_dedup_without_render_claim() -> None:
    authenticator = _authenticator()
    request = authenticator.sign(
        _envelope(),
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
    )
    ack = build_presence_delivery_ack(
        request_message=request,
        endpoint_id=ENDPOINT_ID,
        consumer_status="accepted_for_render",
        acknowledged_at="2026-07-10T12:00:00.250000+00:00",
    )
    signed_ack = authenticator.sign(
        ack,
        channel=PRESENCE_RENDER_ACK_CHANNEL,
        direction="unreal_to_francis_core",
        issued_at="2026-07-10T12:00:00.250000+00:00",
    )

    Draft202012Validator(
        _schema("grounded_presence_delivery_ack.schema.json"),
        format_checker=FormatChecker(),
    ).validate(ack)
    wrapper_validation = authenticator.validate(
        signed_ack,
        expected_channel=PRESENCE_RENDER_ACK_CHANNEL,
        expected_direction="unreal_to_francis_core",
        now="2026-07-10T12:00:00.500000+00:00",
    )
    ack_validation = validate_presence_delivery_ack(
        signed_ack["payload"],
        request_message=request,
        endpoint_id=ENDPOINT_ID,
    )

    assert wrapper_validation.ok is True
    assert ack_validation.ok is True
    assert ack_validation.durable_deduplication is True
    assert ack_validation.to_dict()["render_applied"] is False


def test_delivery_ack_rejects_dedup_and_correlation_drift() -> None:
    authenticator = _authenticator()
    request = authenticator.sign(
        _envelope(),
        channel=PRESENCE_RENDER_CHANNEL,
        direction="francis_core_to_unreal",
        issued_at=ISSUED_AT,
    )
    ack = build_presence_delivery_ack(
        request_message=request,
        endpoint_id=ENDPOINT_ID,
        consumer_status="accepted_for_render",
    )
    ack["consumer"]["durable_deduplication"] = False
    ack["request"]["envelope_id"] = "gpe_ffffffffffffffffffffffffffffffff"

    validation = validate_presence_delivery_ack(
        ack,
        request_message=request,
        endpoint_id=ENDPOINT_ID,
    )

    assert "ack_durable_deduplication_missing" in validation.reasons
    assert "ack_envelope_id_mismatch" in validation.reasons
    assert "ack_id_mismatch" in validation.reasons
