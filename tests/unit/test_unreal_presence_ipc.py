from __future__ import annotations

import ctypes
import json
import os
import struct
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from francis.unreal_presence_adapter import UnrealPresenceAdapter, UnrealPresenceAdapterConfig
from francis.unreal_presence_ipc import (
    PresencePipeConfig,
    WindowsNamedPipePresencePublisher,
    decode_presence_pipe_frame,
    encode_presence_pipe_frame,
)
from francis.unreal_presence_receipts import LocalJsonPresenceDeliveryReceiptStore
from francis.unreal_presence_wire import (
    PRESENCE_RENDER_ACK_CHANNEL,
    PRESENCE_RENDER_CHANNEL,
    PresenceIpcAuthenticator,
    build_presence_delivery_ack,
)
from francis.world_state.presence import build_grounded_presence_snapshot
from francis.world_state.presence_transport import validate_presence_transport_envelope


AUTHENTICATION_KEY_ID = "francis_presence_local_v1"
AUTHENTICATION_SECRET = b"francis-presence-ipc-test-secret!!"


def _authenticator() -> PresenceIpcAuthenticator:
    return PresenceIpcAuthenticator(
        key_id=AUTHENTICATION_KEY_ID,
        secret=AUTHENTICATION_SECRET,
    )


def _envelope(
    *,
    adapter_id: str = "unreal_presence_ipc",
    session_id: str = "session_ipc",
    ttl_ms: int = 5_000,
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    snapshot = build_grounded_presence_snapshot(
        briefing={"headline": "Publish this grounded renderer state.", "generated_at": now},
        operator={"available": True, "observed_at": now},
        orb={
            "available": True,
            "observed_at": now,
            "state": {"semantic_state": "idle", "render_state": "ambient_rest"},
        },
        generated_at=now,
    )
    adapter = UnrealPresenceAdapter(
        UnrealPresenceAdapterConfig(
            adapter_id=adapter_id,
            session_id=session_id,
            ttl_ms=ttl_ms,
        )
    )
    result = adapter.prepare(snapshot, issued_at=now)
    assert result.ok is True
    return result.envelope


def test_pipe_frame_round_trip_is_exact_and_bounded() -> None:
    envelope = _envelope()

    frame = encode_presence_pipe_frame(envelope)
    decoded = decode_presence_pipe_frame(frame)

    assert struct.unpack("<I", frame[:4])[0] == len(frame) - 4
    assert decoded == envelope


@pytest.mark.parametrize(
    "frame",
    [
        b"",
        struct.pack("<I", 2) + b"{}" + b"trailing",
        struct.pack("<I", 0),
        struct.pack("<I", 3) + b"bad",
    ],
)
def test_pipe_frame_decoder_rejects_malformed_messages(frame: bytes) -> None:
    with pytest.raises(ValueError):
        decode_presence_pipe_frame(frame)


def test_pipe_config_is_derived_and_denies_network() -> None:
    config = PresencePipeConfig(adapter_id="unreal_presence_1", session_id="session_1")
    payload = config.to_dict()

    assert config.endpoint_id == "francis.grounded_presence.unreal_presence_1"
    assert config.pipe_path == r"\\.\pipe\francis.grounded_presence.unreal_presence_1"
    assert payload["remote_clients_rejected"] is True
    assert payload["network_allowed"] is False
    assert payload["direction"] == "francis_core_to_unreal_with_signed_ack"
    assert payload["authentication_status"] == "hmac_sha256_required"
    assert payload["delivery_acknowledgement_required"] is True


@pytest.mark.parametrize(
    "kwargs",
    [
        {"adapter_id": "", "session_id": "session_1"},
        {"adapter_id": "unreal_presence_1", "session_id": "invalid session"},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "connect_timeout_ms": 0},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "poll_interval_ms": 101},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "max_message_bytes": 1024},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "writer_lock_timeout_ms": 0},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "ack_timeout_ms": 0},
    ],
)
def test_pipe_config_rejects_unbounded_values(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        PresencePipeConfig(**kwargs)


def test_publisher_fails_closed_when_durable_receipt_state_is_corrupt(tmp_path: Path) -> None:
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    store.root.mkdir(parents=True)
    (store.root / "gpd_corrupt.json").write_text("{", encoding="utf-8")
    config = PresencePipeConfig(adapter_id="unreal_presence_corrupt", session_id="session_corrupt")
    publisher = WindowsNamedPipePresencePublisher(config, authenticator=_authenticator(), receipt_store=store)

    result = publisher.publish(
        _envelope(adapter_id=config.adapter_id, session_id=config.session_id),
    )

    assert publisher.readback()["status"] == "receipt_state_invalid"
    assert result.status == "receipt_state_invalid"
    assert result.delivery_attempted is False


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_publishes_one_bound_envelope_and_rejects_replay(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config = PresencePipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        connect_timeout_ms=2_000,
    )
    receipt_store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    publisher = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=receipt_store,
    )
    envelope = _envelope(adapter_id=adapter_id, session_id=session_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(publisher.publish, envelope)
        frame = _read_one_pipe_message(config.pipe_path, config.max_message_bytes + 4, timeout_seconds=2.0)
        result = future.result(timeout=3.0)

    signed_request = decode_presence_pipe_frame(frame)
    assert (
        _authenticator()
        .validate(
            signed_request,
            expected_channel=PRESENCE_RENDER_CHANNEL,
            expected_direction="francis_core_to_unreal",
        )
        .ok
    )
    delivered = signed_request["payload"]
    validation = validate_presence_transport_envelope(
        delivered,
        expected_adapter_id=adapter_id,
        expected_session_id=session_id,
    )

    assert result.ok is True
    assert result.delivered is True
    assert result.client_connected is True
    assert result.bytes_written == len(frame)
    assert result.receipt_written is True
    receipt_path = Path(result.receipt_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_schema = json.loads(
        (Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_delivery_receipt.schema.json").read_text(
            encoding="utf-8"
        )
    )
    Draft202012Validator(receipt_schema, format_checker=FormatChecker()).validate(receipt)
    assert receipt["delivery"]["envelope_id"] == result.envelope_id
    assert receipt["security"]["application_authenticated"] is True
    assert receipt["delivery"]["consumer_durable_deduplication"] is True
    assert receipt["evidence"]["payload_persisted"] is False
    assert "payload" not in receipt
    assert delivered["transport"]["binding_status"] == "windows_named_pipe"
    assert delivered["transport"]["endpoint_id"] == config.endpoint_id
    assert validation.ok is True
    replay = publisher.publish(envelope)
    assert replay.ok is False
    assert replay.status == "rejected"
    assert replay.reason == "sequence_replayed"
    assert publisher.readback()["delivery_count"] == 1
    restarted = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=receipt_store,
    )
    assert restarted.readback()["last_sequence"] == 1
    assert restarted.readback()["durable_session_sequence_state"] is True
    durable_replay = restarted.publish(envelope)
    assert durable_replay.reason == "sequence_replayed"


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_recovers_failed_delivery_receipt_without_redelivery(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config = PresencePipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        connect_timeout_ms=2_000,
    )
    store = _FailOnceDeliveryReceiptStore(LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts"))
    publisher = WindowsNamedPipePresencePublisher(config, authenticator=_authenticator(), receipt_store=store)
    envelope = _envelope(adapter_id=adapter_id, session_id=session_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(publisher.publish, envelope)
        _read_one_pipe_message(config.pipe_path, config.max_message_bytes + 4, timeout_seconds=2.0)
        failed = future.result(timeout=3.0)

    started = time.monotonic()
    recovered = publisher.publish(envelope)
    elapsed = time.monotonic() - started

    assert failed.delivered is True
    assert failed.status == "delivered_receipt_failed"
    assert publisher.readback()["receipt_recovery_pending"] is False
    assert recovered.ok is True
    assert recovered.delivered is True
    assert recovered.status == "delivery_receipt_recovered"
    assert recovered.delivery_attempted is False
    assert recovered.receipt_written is True
    assert elapsed < 1.0
    readback = publisher.readback()
    assert readback["delivery_count"] == 1
    assert readback["receipt_recovery_count"] == 1


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_recovers_durable_pending_receipt_after_publisher_restart(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config = PresencePipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        connect_timeout_ms=2_000,
    )
    durable_store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    failing_store = _FailOnceDeliveryReceiptStore(durable_store)
    publisher = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=failing_store,
    )
    envelope = _envelope(adapter_id=adapter_id, session_id=session_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(publisher.publish, envelope)
        _read_one_pipe_message(config.pipe_path, config.max_message_bytes + 4, timeout_seconds=2.0)
        failed = future.result(timeout=3.0)

    restarted = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=durable_store,
    )
    before = restarted.readback()
    recovered = restarted.publish(envelope)

    assert failed.status == "delivered_receipt_failed"
    assert before["receipt_recovery_pending"] is True
    assert before["pending_recovery_source"] == "delivery_journal"
    assert recovered.status == "delivery_receipt_recovered"
    assert recovered.delivery_attempted is False
    assert recovered.receipt_written is True
    assert restarted.readback()["receipt_recovery_pending"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_cross_process_mutex_serializes_independent_publishers(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config = PresencePipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        connect_timeout_ms=2_000,
    )
    root = tmp_path / "receipts"
    first = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=LocalJsonPresenceDeliveryReceiptStore(root),
    )
    second = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=LocalJsonPresenceDeliveryReceiptStore(root),
    )
    envelope = _envelope(adapter_id=adapter_id, session_id=session_id)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(first.publish, envelope), executor.submit(second.publish, envelope)]
        _read_one_pipe_message(config.pipe_path, config.max_message_bytes + 4, timeout_seconds=2.0)
        results = [future.result(timeout=4.0) for future in futures]

    delivered = [result for result in results if result.delivered]
    rejected = [result for result in results if not result.delivered]
    assert len(delivered) == 1
    assert delivered[0].status == "delivered"
    assert len(rejected) == 1
    assert rejected[0].reason == "sequence_replayed"
    assert first.readback()["cross_process_writer_lock"]["kind"] == "windows_named_mutex"
    assert second.readback()["cross_process_writer_lock"]["kind"] == "windows_named_mutex"


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
@pytest.mark.parametrize(
    ("ack_mode", "expected_status"),
    [
        ("timeout", "ack_timeout"),
        ("invalid_signature", "ack_authentication_rejected"),
    ],
)
def test_named_pipe_requires_authenticated_consumer_ack(
    tmp_path: Path,
    ack_mode: str,
    expected_status: str,
) -> None:
    suffix = uuid.uuid4().hex[:12]
    config = PresencePipeConfig(
        adapter_id=f"unreal_presence_{suffix}",
        session_id=f"session_{suffix}",
        connect_timeout_ms=2_000,
        ack_timeout_ms=100,
    )
    publisher = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts"),
    )
    envelope = _envelope(adapter_id=config.adapter_id, session_id=config.session_id)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(publisher.publish, envelope)
        _read_one_pipe_message(
            config.pipe_path,
            config.max_message_bytes + 4,
            timeout_seconds=2.0,
            ack_mode=ack_mode,
        )
        result = future.result(timeout=3.0)

    assert result.status == expected_status
    assert result.acknowledged is False
    assert result.receipt_written is False
    assert publisher.readback()["last_sequence"] == 0
    assert publisher.readback()["receipt_recovery_pending"] is True
    assert publisher.readback()["pending_recovery_source"] == "delivery_attempt"


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_reconciles_ambiguous_attempt_after_restart_and_envelope_expiry(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    config = PresencePipeConfig(
        adapter_id=f"unreal_presence_{suffix}",
        session_id=f"session_{suffix}",
        connect_timeout_ms=2_000,
        ack_timeout_ms=100,
    )
    store = LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts")
    publisher = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=store,
    )
    envelope = _envelope(
        adapter_id=config.adapter_id,
        session_id=config.session_id,
        ttl_ms=200,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(publisher.publish, envelope)
        _read_one_pipe_message(
            config.pipe_path,
            config.max_message_bytes + 4,
            timeout_seconds=2.0,
            ack_mode="timeout",
        )
        ambiguous = future.result(timeout=3.0)

    assert ambiguous.status == "ack_timeout"
    assert publisher.readback()["pending_recovery_source"] == "delivery_attempt"
    time.sleep(0.1)
    restarted = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=store,
    )
    assert restarted.readback()["receipt_recovery_pending"] is True
    mismatched = restarted.publish(
        _envelope(
            adapter_id=config.adapter_id,
            session_id=config.session_id,
            ttl_ms=200,
        )
    )
    assert mismatched.status == "receipt_recovery_required"
    assert mismatched.delivery_attempted is False

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(restarted.publish, envelope)
        _read_one_pipe_message(
            config.pipe_path,
            config.max_message_bytes + 4,
            timeout_seconds=2.0,
        )
        reconciled = future.result(timeout=3.0)

    assert reconciled.ok is True
    assert reconciled.status == "delivered_after_reconciliation"
    assert reconciled.acknowledged is True
    assert reconciled.receipt_written is True
    readback = restarted.readback()
    assert readback["attempt_reconciliation_count"] == 1
    assert readback["receipt_recovery_pending"] is False
    assert not list((store.root / "pending_attempt").glob("*.json"))


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_named_pipe_timeout_is_bounded_and_does_not_consume_sequence(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config = PresencePipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        connect_timeout_ms=50,
        poll_interval_ms=5,
    )
    publisher = WindowsNamedPipePresencePublisher(
        config,
        authenticator=_authenticator(),
        receipt_store=LocalJsonPresenceDeliveryReceiptStore(tmp_path / "receipts"),
    )

    started = time.monotonic()
    result = publisher.publish(_envelope(adapter_id=adapter_id, session_id=session_id))
    elapsed = time.monotonic() - started

    assert result.ok is False
    assert result.status == "client_timeout"
    assert result.client_connected is False
    assert elapsed < 1.0
    assert publisher.readback()["last_sequence"] == 0
    assert publisher.readback()["receipt_recovery_pending"] is False


def _read_one_pipe_message(
    pipe_path: str,
    buffer_size: int,
    *,
    timeout_seconds: float,
    ack_mode: str = "valid",
) -> bytes:
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.WriteFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPCVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.WriteFile.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL

    invalid_handle = ctypes.c_void_p(-1).value
    deadline = time.monotonic() + timeout_seconds
    handle: int | None = None
    while time.monotonic() < deadline:
        ctypes.set_last_error(0)
        candidate = kernel32.CreateFileW(
            pipe_path,
            0xC0000000,
            0,
            None,
            3,
            0,
            None,
        )
        if candidate != invalid_handle:
            handle = int(candidate)
            break
        time.sleep(0.01)
    if handle is None:
        raise AssertionError(f"named pipe client could not connect: win32_error_{ctypes.get_last_error()}")

    try:
        buffer = ctypes.create_string_buffer(buffer_size)
        read = wintypes.DWORD(0)
        ctypes.set_last_error(0)
        ok = kernel32.ReadFile(
            handle,
            buffer,
            buffer_size,
            ctypes.byref(read),
            None,
        )
        if not ok:
            raise AssertionError(f"named pipe read failed: win32_error_{ctypes.get_last_error()}")
        frame = bytes(buffer.raw[: read.value])
        request = decode_presence_pipe_frame(frame)
        authenticator = _authenticator()
        request_validation = authenticator.validate(
            request,
            expected_channel=PRESENCE_RENDER_CHANNEL,
            expected_direction="francis_core_to_unreal",
        )
        if not request_validation.ok:
            raise AssertionError(f"named pipe request authentication failed: {request_validation.reasons}")
        if ack_mode == "timeout":
            time.sleep(0.25)
            return frame
        acknowledgement = build_presence_delivery_ack(
            request_message=request,
            endpoint_id=str(request["payload"]["transport"]["endpoint_id"]),
            consumer_status="accepted_for_render",
        )
        signed_ack = authenticator.sign(
            acknowledgement,
            channel=PRESENCE_RENDER_ACK_CHANNEL,
            direction="unreal_to_francis_core",
        )
        if ack_mode == "invalid_signature":
            signed_ack["authentication"]["signature"] = "0" * 64
        elif ack_mode != "valid":
            raise AssertionError(f"unsupported ack mode: {ack_mode}")
        ack_frame = encode_presence_pipe_frame(signed_ack)
        written = wintypes.DWORD(0)
        ack_buffer = ctypes.create_string_buffer(ack_frame)
        ctypes.set_last_error(0)
        write_ok = kernel32.WriteFile(
            handle,
            ack_buffer,
            len(ack_frame),
            ctypes.byref(written),
            None,
        )
        if not write_ok or written.value != len(ack_frame):
            raise AssertionError(f"named pipe ack write failed: win32_error_{ctypes.get_last_error()}")
        return frame
    finally:
        kernel32.CloseHandle(handle)


class _FailOnceDeliveryReceiptStore:
    def __init__(self, delegate: LocalJsonPresenceDeliveryReceiptStore) -> None:
        self.delegate = delegate
        self.failed = False

    def has_delivery(self, *, envelope_id: str, endpoint_id: str) -> bool:
        return self.delegate.has_delivery(envelope_id=envelope_id, endpoint_id=endpoint_id)

    def highest_delivered_sequence(
        self,
        *,
        adapter_id: str,
        session_id: str,
        endpoint_id: str,
        refresh: bool = False,
    ) -> int:
        return self.delegate.highest_delivered_sequence(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
            refresh=refresh,
        )

    def write(self, receipt: Mapping[str, Any]) -> Path:
        if not self.failed:
            self.failed = True
            raise OSError("simulated_delivery_receipt_failure")
        return self.delegate.write(receipt)

    def read_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]:
        return self.delegate.read_pending_delivery(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )

    def write_pending_delivery(self, journal: Mapping[str, Any]) -> Path:
        return self.delegate.write_pending_delivery(journal)

    def clear_pending_delivery(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None:
        self.delegate.clear_pending_delivery(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )

    def read_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> dict[str, Any]:
        return self.delegate.read_pending_attempt(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )

    def write_pending_attempt(self, attempt: Mapping[str, Any]) -> Path:
        return self.delegate.write_pending_attempt(attempt)

    def clear_pending_attempt(self, *, adapter_id: str, session_id: str, endpoint_id: str) -> None:
        self.delegate.clear_pending_attempt(
            adapter_id=adapter_id,
            session_id=session_id,
            endpoint_id=endpoint_id,
        )
