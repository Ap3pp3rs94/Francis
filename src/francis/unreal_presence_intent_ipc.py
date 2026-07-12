from __future__ import annotations

import ctypes
import os
import time
from ctypes import wintypes
from dataclasses import dataclass
from threading import Lock
from typing import Any

from francis.unreal_presence_intents import (
    PresenceIntentGatewayResult,
    UnrealPresenceIntentGateway,
)
from francis.unreal_presence_ipc import decode_presence_pipe_frame
from francis.unreal_presence_wire import (
    PRESENCE_INTENT_CHANNEL,
    PresenceIpcAuthenticator,
)
from francis.windows_ctypes import get_last_error, load_win_dll, set_last_error


PRESENCE_INTENT_PIPE_MAX_MESSAGE_BYTES = 64 * 1024
PRESENCE_INTENT_PIPE_MAX_WAIT_MS = 2_000

_PIPE_ACCESS_INBOUND = 0x00000001
_PIPE_TYPE_MESSAGE = 0x00000004
_PIPE_READMODE_MESSAGE = 0x00000002
_PIPE_NOWAIT = 0x00000001
_PIPE_REJECT_REMOTE_CLIENTS = 0x00000008
_ERROR_PIPE_CONNECTED = 535
_ERROR_PIPE_LISTENING = 536
_ERROR_NO_DATA = 232


@dataclass(frozen=True, slots=True)
class PresenceIntentPipeConfig:
    adapter_id: str
    session_id: str
    wait_timeout_ms: int = 1_000
    poll_interval_ms: int = 10
    max_message_bytes: int = PRESENCE_INTENT_PIPE_MAX_MESSAGE_BYTES
    authentication_key_id: str = "francis_presence_local_v1"

    def __post_init__(self) -> None:
        if not _contract_id(self.adapter_id):
            raise ValueError("presence_intent_pipe_adapter_id_invalid")
        if not _contract_id(self.session_id):
            raise ValueError("presence_intent_pipe_session_id_invalid")
        if not _bounded_integer(self.wait_timeout_ms, minimum=1, maximum=PRESENCE_INTENT_PIPE_MAX_WAIT_MS):
            raise ValueError("presence_intent_pipe_wait_timeout_invalid")
        if not _bounded_integer(self.poll_interval_ms, minimum=1, maximum=100):
            raise ValueError("presence_intent_pipe_poll_interval_invalid")
        if not _bounded_integer(self.max_message_bytes, minimum=4_096, maximum=PRESENCE_INTENT_PIPE_MAX_MESSAGE_BYTES):
            raise ValueError("presence_intent_pipe_message_limit_invalid")
        if not _contract_id(self.authentication_key_id):
            raise ValueError("presence_intent_pipe_authentication_key_id_invalid")

    @property
    def endpoint_id(self) -> str:
        return f"francis.grounded_presence.intent.{self.adapter_id}"

    @property
    def pipe_path(self) -> str:
        return rf"\\.\pipe\{self.endpoint_id}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "francis.grounded_presence.intent_windows_named_pipe.config",
            "adapter_id": self.adapter_id,
            "session_id": self.session_id,
            "endpoint_id": self.endpoint_id,
            "pipe_path": self.pipe_path,
            "wait_timeout_ms": self.wait_timeout_ms,
            "poll_interval_ms": self.poll_interval_ms,
            "max_message_bytes": self.max_message_bytes,
            "direction": "unreal_to_francis_core",
            "message_framing": "uint32_le_length_plus_authenticated_json_utf8",
            "remote_clients_rejected": True,
            "network_allowed": False,
            "authentication_status": "hmac_sha256_required",
            "authentication_key_id": self.authentication_key_id,
        }


@dataclass(frozen=True, slots=True)
class PresenceIntentPipeReceiveResult:
    ok: bool
    received: bool
    accepted: bool
    status: str
    reason: str
    event_id: str
    intent: str
    endpoint_id: str
    bytes_read: int
    client_connected: bool
    receipt_id: str
    receipt_path: str
    receipt_written: bool
    gateway: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "received": self.received,
            "accepted": self.accepted,
            "status": self.status,
            "reason": self.reason,
            "event_id": self.event_id,
            "intent": self.intent,
            "endpoint_id": self.endpoint_id,
            "bytes_read": self.bytes_read,
            "client_connected": self.client_connected,
            "receipt_id": self.receipt_id,
            "receipt_path": self.receipt_path,
            "receipt_written": self.receipt_written,
            "gateway": dict(self.gateway),
            "dispatch_attempted": False,
            "dispatch_allowed": False,
            "mutation_applied": False,
            "network_used": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


class WindowsNamedPipePresenceIntentReceiver:
    """Receive one bounded event, then validate and receipt it without dispatch."""

    def __init__(
        self,
        config: PresenceIntentPipeConfig,
        *,
        gateway: UnrealPresenceIntentGateway,
        authenticator: PresenceIpcAuthenticator,
    ) -> None:
        gateway_state = gateway.readback()
        if gateway_state.get("adapter_id") != config.adapter_id:
            raise ValueError("presence_intent_pipe_gateway_adapter_mismatch")
        if gateway_state.get("session_id") != config.session_id:
            raise ValueError("presence_intent_pipe_gateway_session_mismatch")
        if authenticator.key_id != config.authentication_key_id:
            raise ValueError("presence_intent_pipe_authentication_key_mismatch")
        self.config = config
        self.gateway = gateway
        self.authenticator = authenticator
        self._lock = Lock()
        self._receive_count = 0
        self._failure_count = 0
        self._last_receive: dict[str, Any] = {}

    def receive_once(self, *, expected_source_envelope_id: str = "") -> PresenceIntentPipeReceiveResult:
        with self._lock:
            return self._receive_once_locked(expected_source_envelope_id=expected_source_envelope_id)

    def readback(self) -> dict[str, Any]:
        with self._lock:
            return {
                "kind": "francis.grounded_presence.intent_windows_named_pipe.readback",
                "status": "ready_on_demand" if os.name == "nt" else "unsupported_platform",
                "config": self.config.to_dict(),
                "receive_count": self._receive_count,
                "failure_count": self._failure_count,
                "last_receive": dict(self._last_receive),
                "gateway": self.gateway.readback(),
                "authentication": self.authenticator.describe(),
                "background_worker": False,
                "dispatch_supported": False,
                "dispatch_attempted": False,
                "writes_intent_receipts": True,
                "writes_memory": False,
                "network_allowed": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            }

    def _receive_once_locked(self, *, expected_source_envelope_id: str) -> PresenceIntentPipeReceiveResult:
        if os.name != "nt":
            return self._failure(
                status="unsupported_platform",
                reason="windows_named_pipe_requires_windows",
                client_connected=False,
            )
        handle = _create_named_pipe(self.config)
        if handle is None:
            return self._failure(
                status="pipe_create_failed",
                reason=f"win32_error_{get_last_error()}",
                client_connected=False,
            )
        connected = False
        try:
            connected, connect_reason = _wait_for_client(handle, self.config)
            if not connected:
                return self._failure(
                    status="client_timeout" if connect_reason == "client_not_connected" else "connect_failed",
                    reason=connect_reason,
                    client_connected=False,
                )
            frame, read_reason = _read_pipe_frame(handle, self.config)
            if not frame:
                gateway_result = self.gateway.evaluate(
                    {},
                    expected_source_envelope_id=expected_source_envelope_id,
                )
                return self._failure(
                    status="read_failed",
                    reason=read_reason or "empty_pipe_frame",
                    client_connected=True,
                    gateway_result=gateway_result,
                )
            try:
                signed_event = decode_presence_pipe_frame(
                    frame,
                    max_message_bytes=self.config.max_message_bytes,
                )
            except ValueError as exc:
                gateway_result = self.gateway.evaluate(
                    {},
                    expected_source_envelope_id=expected_source_envelope_id,
                )
                return self._failure(
                    status="frame_rejected",
                    reason=_bounded_text(str(exc)),
                    client_connected=True,
                    bytes_read=len(frame),
                    gateway_result=gateway_result,
                )

            authentication = self.authenticator.validate(
                signed_event,
                expected_channel=PRESENCE_INTENT_CHANNEL,
                expected_direction="unreal_to_francis_core",
            )
            event = signed_event.get("payload") if isinstance(signed_event.get("payload"), dict) else {}
            gateway_result = self.gateway.evaluate(
                event,
                expected_source_envelope_id=expected_source_envelope_id,
                authentication=authentication.to_dict(),
            )
            self._receive_count += 1
            if not gateway_result.accepted:
                self._failure_count += 1
            self._last_receive = {
                "status": gateway_result.status,
                "event_id": gateway_result.event_id,
                "intent": gateway_result.intent,
                "bytes_read": len(frame),
                "client_connected": True,
                "receipt_id": gateway_result.receipt_id,
                "receipt_path": gateway_result.receipt_path,
                "receipt_written": gateway_result.receipt_written,
                "dispatch_attempted": False,
            }
            return PresenceIntentPipeReceiveResult(
                ok=gateway_result.ok,
                received=True,
                accepted=gateway_result.accepted,
                status=gateway_result.status,
                reason=gateway_result.reasons[0] if gateway_result.reasons else "",
                event_id=gateway_result.event_id,
                intent=gateway_result.intent,
                endpoint_id=self.config.endpoint_id,
                bytes_read=len(frame),
                client_connected=True,
                receipt_id=gateway_result.receipt_id,
                receipt_path=gateway_result.receipt_path,
                receipt_written=gateway_result.receipt_written,
                gateway=gateway_result.to_dict(),
            )
        finally:
            _close_named_pipe(handle, disconnect=connected)

    def _failure(
        self,
        *,
        status: str,
        reason: str,
        client_connected: bool,
        bytes_read: int = 0,
        gateway_result: PresenceIntentGatewayResult | None = None,
    ) -> PresenceIntentPipeReceiveResult:
        self._failure_count += 1
        gateway_payload = gateway_result.to_dict() if gateway_result is not None else {}
        self._last_receive = {
            "status": status,
            "reason": reason,
            "bytes_read": bytes_read,
            "client_connected": client_connected,
            "receipt_id": gateway_result.receipt_id if gateway_result is not None else "",
            "receipt_written": gateway_result.receipt_written if gateway_result is not None else False,
            "dispatch_attempted": False,
        }
        return PresenceIntentPipeReceiveResult(
            ok=False,
            received=bytes_read > 0,
            accepted=False,
            status=status,
            reason=reason,
            event_id=gateway_result.event_id if gateway_result is not None else "",
            intent=gateway_result.intent if gateway_result is not None else "",
            endpoint_id=self.config.endpoint_id,
            bytes_read=bytes_read,
            client_connected=client_connected,
            receipt_id=gateway_result.receipt_id if gateway_result is not None else "",
            receipt_path=gateway_result.receipt_path if gateway_result is not None else "",
            receipt_written=gateway_result.receipt_written if gateway_result is not None else False,
            gateway=gateway_payload,
        )


def _create_named_pipe(config: PresenceIntentPipeConfig) -> int | None:
    kernel32 = _kernel32()
    handle = kernel32.CreateNamedPipeW(
        config.pipe_path,
        _PIPE_ACCESS_INBOUND,
        _PIPE_TYPE_MESSAGE | _PIPE_READMODE_MESSAGE | _PIPE_NOWAIT | _PIPE_REJECT_REMOTE_CLIENTS,
        1,
        config.max_message_bytes + 4,
        config.max_message_bytes + 4,
        config.wait_timeout_ms,
        None,
    )
    invalid_handle = ctypes.c_void_p(-1).value
    if handle == invalid_handle:
        return None
    return int(handle)


def _wait_for_client(handle: int, config: PresenceIntentPipeConfig) -> tuple[bool, str]:
    kernel32 = _kernel32()
    deadline = time.monotonic() + config.wait_timeout_ms / 1_000
    while True:
        set_last_error(0)
        if kernel32.ConnectNamedPipe(handle, None):
            return True, ""
        error = get_last_error()
        if error in {_ERROR_PIPE_CONNECTED, _ERROR_NO_DATA}:
            return True, ""
        if error != _ERROR_PIPE_LISTENING:
            return False, f"win32_error_{error}"
        if time.monotonic() >= deadline:
            return False, "client_not_connected"
        time.sleep(config.poll_interval_ms / 1_000)


def _read_pipe_frame(handle: int, config: PresenceIntentPipeConfig) -> tuple[bytes, str]:
    kernel32 = _kernel32()
    deadline = time.monotonic() + config.wait_timeout_ms / 1_000
    while True:
        buffer = ctypes.create_string_buffer(config.max_message_bytes + 4)
        read = wintypes.DWORD(0)
        set_last_error(0)
        ok = kernel32.ReadFile(
            handle,
            buffer,
            config.max_message_bytes + 4,
            ctypes.byref(read),
            None,
        )
        if ok and read.value > 0:
            return bytes(buffer.raw[: read.value]), ""
        error = get_last_error()
        if error not in {_ERROR_NO_DATA, _ERROR_PIPE_LISTENING}:
            return b"", f"win32_error_{error}"
        if time.monotonic() >= deadline:
            return b"", "client_data_timeout"
        time.sleep(config.poll_interval_ms / 1_000)


def _close_named_pipe(handle: int, *, disconnect: bool) -> None:
    kernel32 = _kernel32()
    if disconnect:
        kernel32.DisconnectNamedPipe(handle)
    kernel32.CloseHandle(handle)


def _kernel32() -> Any:
    kernel32 = load_win_dll("kernel32")
    kernel32.CreateNamedPipeW.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
    ]
    kernel32.CreateNamedPipeW.restype = wintypes.HANDLE
    kernel32.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
    kernel32.ConnectNamedPipe.restype = wintypes.BOOL
    kernel32.ReadFile.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.LPVOID,
    ]
    kernel32.ReadFile.restype = wintypes.BOOL
    kernel32.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
    kernel32.DisconnectNamedPipe.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel32.CloseHandle.restype = wintypes.BOOL
    return kernel32


def _contract_id(value: Any) -> str:
    text = str(value or "").strip()
    if not text or len(text) > 120:
        return ""
    return text if all(character.isalnum() or character in {"-", "_", "."} for character in text) else ""


def _bounded_integer(value: Any, *, minimum: int, maximum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and minimum <= value <= maximum


def _bounded_text(value: Any, *, limit: int = 240) -> str:
    return str(value or "").strip()[:limit]
