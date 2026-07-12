from __future__ import annotations

import ctypes
import json
import os
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from francis.unreal_presence_intent_ipc import (
    PresenceIntentPipeConfig,
    WindowsNamedPipePresenceIntentReceiver,
)
from francis.unreal_presence_intents import (
    LocalJsonPresenceIntentReceiptStore,
    UnrealPresenceIntentGateway,
)
from francis.unreal_presence_ipc import encode_presence_pipe_frame
from francis.unreal_presence_wire import PRESENCE_INTENT_CHANNEL, PresenceIpcAuthenticator
from francis.world_state.presence_intent import build_presence_intent_event


SOURCE_ENVELOPE_ID = "gpe_0123456789abcdef0123456789abcdef"
AUTHENTICATION_KEY_ID = "francis_presence_local_v1"
AUTHENTICATION_SECRET = b"francis-presence-intent-ipc-secret"


def _authenticator() -> PresenceIpcAuthenticator:
    return PresenceIpcAuthenticator(
        key_id=AUTHENTICATION_KEY_ID,
        secret=AUTHENTICATION_SECRET,
    )


def _signed_frame(event: dict[str, Any], *, tamper_signature: bool = False) -> bytes:
    message = _authenticator().sign(
        event,
        channel=PRESENCE_INTENT_CHANNEL,
        direction="unreal_to_francis_core",
    )
    if tamper_signature:
        message["authentication"]["signature"] = "0" * 64
    return encode_presence_pipe_frame(message)


def _event(*, adapter_id: str, session_id: str, sequence: int = 1) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return build_presence_intent_event(
        adapter_id=adapter_id,
        session_id=session_id,
        event_sequence=sequence,
        source_envelope_id=SOURCE_ENVELOPE_ID,
        source_sequence=4,
        intent="request_review",
        target_kind="mission",
        target_id="mission_1",
        issued_at=now,
        ttl_ms=2_000,
    )


def _receiver(
    tmp_path: Path,
    *,
    adapter_id: str,
    session_id: str,
    wait_timeout_ms: int = 1_000,
) -> tuple[PresenceIntentPipeConfig, WindowsNamedPipePresenceIntentReceiver]:
    config = PresenceIntentPipeConfig(
        adapter_id=adapter_id,
        session_id=session_id,
        wait_timeout_ms=wait_timeout_ms,
        poll_interval_ms=5,
    )
    gateway = UnrealPresenceIntentGateway(
        adapter_id=adapter_id,
        session_id=session_id,
        receipt_store=LocalJsonPresenceIntentReceiptStore(tmp_path / "receipts"),
    )
    return config, WindowsNamedPipePresenceIntentReceiver(
        config,
        gateway=gateway,
        authenticator=_authenticator(),
    )


def test_intent_pipe_config_is_local_bounded_and_inbound_only() -> None:
    config = PresenceIntentPipeConfig(adapter_id="unreal_presence_1", session_id="session_1")
    payload = config.to_dict()

    assert config.endpoint_id == "francis.grounded_presence.intent.unreal_presence_1"
    assert payload["direction"] == "unreal_to_francis_core"
    assert payload["remote_clients_rejected"] is True
    assert payload["network_allowed"] is False
    assert payload["authentication_status"] == "hmac_sha256_required"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"adapter_id": "", "session_id": "session_1"},
        {"adapter_id": "unreal_presence_1", "session_id": "bad session"},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "wait_timeout_ms": 0},
        {"adapter_id": "unreal_presence_1", "session_id": "session_1", "max_message_bytes": 1024},
    ],
)
def test_intent_pipe_config_rejects_unbounded_values(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError):
        PresenceIntentPipeConfig(**kwargs)


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_intent_pipe_receives_and_receipts_without_dispatch(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config, receiver = _receiver(tmp_path, adapter_id=adapter_id, session_id=session_id)
    event = _event(adapter_id=adapter_id, session_id=session_id)
    frame = _signed_frame(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(
            receiver.receive_once,
            expected_source_envelope_id=SOURCE_ENVELOPE_ID,
        )
        _write_one_pipe_message(config.pipe_path, frame, timeout_seconds=2.0)
        result = future.result(timeout=3.0)

    assert result.ok is True
    assert result.received is True
    assert result.accepted is True
    assert result.receipt_written is True
    assert result.bytes_read == len(frame)
    assert result.to_dict()["dispatch_attempted"] is False
    assert result.to_dict()["mutation_applied"] is False
    assert Path(result.receipt_path).is_file()
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["security"]["application_authenticated"] is True
    assert receipt["security"]["authentication_status"] == "hmac_sha256_verified"
    readback = receiver.readback()
    assert readback["receive_count"] == 1
    assert readback["gateway"]["last_event_sequence"] == 1
    assert readback["dispatch_supported"] is False


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_intent_pipe_receipts_tampered_event_as_rejected(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config, receiver = _receiver(tmp_path, adapter_id=adapter_id, session_id=session_id)
    event = _event(adapter_id=adapter_id, session_id=session_id)
    event["routing"]["dispatch_allowed"] = True
    frame = _signed_frame(event)

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(receiver.receive_once)
        _write_one_pipe_message(config.pipe_path, frame, timeout_seconds=2.0)
        result = future.result(timeout=3.0)

    assert result.ok is False
    assert result.received is True
    assert result.accepted is False
    assert result.receipt_written is True
    assert result.reason == "dispatch_authority_drift"
    assert Path(result.receipt_path).is_file()


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_intent_pipe_rejects_and_receipts_invalid_application_signature(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    config, receiver = _receiver(tmp_path, adapter_id=adapter_id, session_id=session_id)
    frame = _signed_frame(
        _event(adapter_id=adapter_id, session_id=session_id),
        tamper_signature=True,
    )

    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(receiver.receive_once)
        _write_one_pipe_message(config.pipe_path, frame, timeout_seconds=2.0)
        result = future.result(timeout=3.0)

    assert result.accepted is False
    assert result.receipt_written is True
    assert result.reason == "ipc_authentication_signature_invalid"
    receipt = json.loads(Path(result.receipt_path).read_text(encoding="utf-8"))
    assert receipt["security"]["application_authenticated"] is False
    assert receipt["security"]["authentication_status"] == "hmac_sha256_rejected"


@pytest.mark.skipif(os.name != "nt", reason="Windows named pipe proof requires Windows")
def test_intent_pipe_timeout_is_bounded(tmp_path: Path) -> None:
    suffix = uuid.uuid4().hex[:12]
    adapter_id = f"unreal_presence_{suffix}"
    session_id = f"session_{suffix}"
    _, receiver = _receiver(
        tmp_path,
        adapter_id=adapter_id,
        session_id=session_id,
        wait_timeout_ms=50,
    )

    started = time.monotonic()
    result = receiver.receive_once()
    elapsed = time.monotonic() - started

    assert result.ok is False
    assert result.status == "client_timeout"
    assert result.received is False
    assert result.receipt_written is False
    assert elapsed < 1.0


def _write_one_pipe_message(pipe_path: str, frame: bytes, *, timeout_seconds: float) -> None:
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
            0x40000000,
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
        buffer = ctypes.create_string_buffer(frame)
        written = wintypes.DWORD(0)
        ctypes.set_last_error(0)
        ok = kernel32.WriteFile(
            handle,
            buffer,
            len(frame),
            ctypes.byref(written),
            None,
        )
        if not ok or written.value != len(frame):
            raise AssertionError(f"named pipe write failed: win32_error_{ctypes.get_last_error()}")
    finally:
        kernel32.CloseHandle(handle)
