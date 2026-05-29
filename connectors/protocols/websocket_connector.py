"""
===============================================================================
Francis 2.0 — Protocol Connectors (WebSocket Connector)
Path: connectors/protocols/websocket_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a synchronous WebSocket (RFC 6455) client connector using
ONLY the Python standard library (socket + ssl + base64 + hashlib).

It fits the provider-agnostic ProtocolConnector contract in connectors/protocols/__init__.py.

Supported:
  - ws:// and wss:// targets
  - RFC 6455 handshake (Sec-WebSocket-Key / Sec-WebSocket-Accept validation)
  - Client-to-server masked frames
  - Text (opcode 0x1) and Binary (opcode 0x2) messages
  - PING/PONG
  - CLOSE (best-effort close handshake)
  - Optional persistent connection guarded by a lock
  - Minimal receive-queue so PING waits don't discard messages

Not supported (intentionally, to keep footprint small + safe):
  - Per-message compression (permessage-deflate)
  - HTTP proxy CONNECT tunneling
  - HTTP/2 WebSockets
  - Streaming callback subscriptions (this is request/response oriented)
  - QoS semantics beyond WebSocket frames
  - Advanced fragmentation controls (we DO assemble fragmented inbound messages)

SAFETY & OBSERVABILITY
----------------------
- Never logs raw message payloads.
- Never logs raw headers that might contain secrets (Authorization/Cookie/etc).
- Provides hashes/lengths only.
- Limits:
    * max_handshake_bytes for response header parsing
    * max_message_bytes for inbound message assembly
    * max_frame_bytes for individual frame payload

REQUEST MAPPING (ProtocolRequest)
---------------------------------
operation patterns:
  - "CONNECT"
  - "CLOSE"
  - "PING"
  - "SEND" / "SEND_TEXT" / "SEND_BINARY"
  - "RECV"
  - "EXCHANGE" (send then receive one message)

Endpoint formats:
  - req.endpoint.uri: "ws://host:port/path?query" or "wss://host/path"
  - req.endpoint.address: same as above, or shorthand "host:port/path"

Message payload:
  - bytes/bytearray => binary send (unless forced text)
  - str => text send (utf-8)
  - Mapping/list/tuple => JSON text send (utf-8)
  - None => empty payload

Per-request options (req.meta):
  - message_type: "auto" | "text" | "binary"
  - headers: mapping[str,str] (merged with req.headers; CRLF is rejected)
  - subprotocols: sequence[str]
  - origin: str
  - receive_timeout_s: float (overrides timeout when waiting for RECV in EXCHANGE)
  - auto_pong: bool (default True)

===============================================================================
"""

from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import socket
import ssl
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import (
    ProtocolAuthError,
    ProtocolBackoffPolicy,
    ProtocolConnectorInfo,
    ProtocolEndpoint,
    ProtocolError,
    ProtocolErrorContext,
    ProtocolHealth,
    ProtocolIdentity,
    ProtocolNetworkError,
    ProtocolPermissionError,
    ProtocolRateLimitError,
    ProtocolRequest,
    ProtocolResponse,
    ProtocolSerializationError,
    ProtocolTimeoutError,
    ProtocolUnavailableError,
    ProtocolUnsupportedError,
    ProtocolValidationError,
    compute_backoff_s,
    redact_mapping,
    redact_uri,
    redact_value,
)

__all__ = [
    "WEBSOCKET_PROTOCOL_ID",
    "WS_DEFAULT_PORT",
    "WSS_DEFAULT_PORT",
    "WebSocketConnectorConfig",
    "WebSocketRequest",
    "WebSocketMessage",
    "WebSocketClose",
    "WebSocketPong",
    "WebSocketProtocolConnector",
    "normalize_ws_target",
    "normalize_ws_headers",
    "websocket_request_summary",
    "websocket_message_summary",
    "websocket_close_summary",
]


WEBSOCKET_PROTOCOL_ID = "websocket"
WS_DEFAULT_PORT = 80
WSS_DEFAULT_PORT = 443
_LOG = logging.getLogger(__name__)
_MIN_TLS_VERSION = ssl.TLSVersion.TLSv1_2

# WebSocket opcodes
_OP_CONT = 0x0
_OP_TEXT = 0x1
_OP_BIN = 0x2
_OP_CLOSE = 0x8
_OP_PING = 0x9
_OP_PONG = 0xA

# RFC 6455 GUID
_WS_GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Conservative bounds
_DEFAULT_MAX_HANDSHAKE_BYTES = 16 * 1024
_DEFAULT_MAX_FRAME_BYTES = 2 * 1024 * 1024
_DEFAULT_MAX_MESSAGE_BYTES = 8 * 1024 * 1024


def _set_minimum_tls_version(ctx: ssl.SSLContext) -> ssl.SSLContext:
    ctx.minimum_version = _MIN_TLS_VERSION
    return ctx


def _websocket_ssl_context(*, tls_verify: bool, ca_file: str | None = None) -> ssl.SSLContext:
    if tls_verify:
        ctx = ssl.create_default_context(cafile=ca_file)
    else:
        ctx = ssl._create_unverified_context()  # noqa: SLF001
    return _set_minimum_tls_version(ctx)


# =============================================================================
# Safe hashing / shapes (never log raw payload)
# =============================================================================


def _hash_stable(value: str, *, salt: str = "francis") -> str:
    v = (value or "").encode("utf-8", errors="ignore")
    s = (salt or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(s + b":" + v).hexdigest()[:12]


def _shape_value(v: Any) -> dict[str, Any]:
    if v is None:
        return {"type": "null"}
    if isinstance(v, bool):
        return {"type": "bool"}
    if isinstance(v, int) and not isinstance(v, bool):
        return {"type": "int"}
    if isinstance(v, float):
        return {"type": "float"}
    if isinstance(v, str):
        return {"type": "str", "len": len(v), "hash": _hash_stable(v)}
    if isinstance(v, (bytes, bytearray)):
        b = bytes(v)
        return {"type": "bytes", "len": len(b), "hash": _hash_stable(b[:256].hex())}
    if isinstance(v, Mapping):
        return {"type": "object", "keys": len(v)}
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {"type": "array", "len": len(v)}
    try:
        s = str(v)
    except Exception:
        s = type(v).__name__
    return {"type": type(v).__name__, "hash": _hash_stable(s)}


# =============================================================================
# Normalization helpers
# =============================================================================


def normalize_ws_target(target: str) -> dict[str, Any]:
    """
    Normalize a WebSocket target string.

    Accepts:
      - "ws://host:port/path?query"
      - "wss://host/path"
      - shorthand "host:port/path" or "host/path" (assumes wss://)

    Returns:
      {
        "url": "ws(s)://host:port/path?query",
        "scheme": "ws"|"wss",
        "host": "...",
        "port": int,
        "resource": "/path?query",
        "tls": bool,
        "host_header": "host[:port]" (as sent in Host)
      }
    """
    raw = (target or "").strip()
    if not raw:
        raise ProtocolValidationError(
            "websocket target is required",
            details={"field": "target"},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "websocket target contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )

    if "://" not in raw:
        # Shorthand host[:port][/path[?query]]
        # Split hostport vs path
        hostport, pathq = (raw.split("/", 1) + [""])[:2]
        hostport = hostport.strip()
        if not hostport:
            raise ProtocolValidationError(
                "websocket target missing host",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
            )
        scheme = "wss"
        tls = True

        host = hostport
        port = WSS_DEFAULT_PORT
        if ":" in hostport:
            h, port_text = hostport.rsplit(":", 1)
            h = h.strip()
            if not h:
                raise ProtocolValidationError(
                    "websocket target missing host",
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
                )
            try:
                port = int(port_text.strip())
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "invalid websocket port",
                    details={"port": redact_value(port_text)},
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
                    cause=exc,
                ) from exc
            host = h

        if not (1 <= int(port) <= 65535):
            raise ProtocolValidationError(
                "websocket port out of range (1..65535)",
                details={"port": port},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
            )

        resource = "/" + pathq if pathq else "/"
        url = f"{scheme}://{host}:{port}{resource}" if port != WSS_DEFAULT_PORT else f"{scheme}://{host}{resource}"
        host_header = f"{host}:{port}" if port != WSS_DEFAULT_PORT else host
        return {
            "url": url,
            "scheme": scheme,
            "host": host,
            "port": int(port),
            "resource": resource,
            "tls": tls,
            "host_header": host_header,
        }

    parsed = urlsplit(raw)
    scheme = (parsed.scheme or "").lower()
    if scheme not in ("ws", "wss"):
        raise ProtocolValidationError(
            "unsupported websocket scheme",
            details={"scheme": redact_value(scheme)},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )

    if parsed.username or parsed.password:
        raise ProtocolValidationError(
            "websocket target must not include userinfo",
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )

    parsed_host = parsed.hostname
    if not parsed_host:
        raise ProtocolValidationError(
            "websocket target missing host",
            details={"target": redact_value(raw)},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )
    host = str(parsed_host)

    tls = scheme == "wss"
    port = int(parsed.port or (WSS_DEFAULT_PORT if tls else WS_DEFAULT_PORT))
    if not (1 <= port <= 65535):
        raise ProtocolValidationError(
            "websocket port out of range (1..65535)",
            details={"port": port},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_target"),
        )

    path = parsed.path or "/"
    query = parsed.query or ""
    resource = path + (f"?{query}" if query else "")

    netloc = f"{host}:{port}"
    url = urlunsplit((scheme, netloc, path, query, ""))

    # Host header: include port if non-default
    default_port = WSS_DEFAULT_PORT if tls else WS_DEFAULT_PORT
    host_header = f"{host}:{port}" if port != default_port else host

    return {
        "url": url,
        "scheme": scheme,
        "host": host,
        "port": port,
        "resource": resource,
        "tls": tls,
        "host_header": host_header,
    }


def normalize_ws_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """
    Validate headers are safe for HTTP-like framing (no CRLF/NUL injection).
    Returns a copy.
    """
    if not headers:
        return {}
    out: dict[str, str] = {}
    for k, v in headers.items():
        kk = ("" if k is None else str(k)).strip()
        if not kk:
            raise ProtocolValidationError(
                "header name cannot be empty",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_headers"),
            )
        vv = "" if v is None else str(v)
        if "\r" in kk or "\n" in kk or "\x00" in kk:
            raise ProtocolValidationError(
                "header name contains illegal control characters",
                details={"header": redact_value(kk)},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise ProtocolValidationError(
                "header value contains illegal control characters",
                details={"header": redact_value(kk)},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.normalize_headers"),
            )
        out[kk] = vv
    return out


def _parse_operation(op: str) -> tuple[str, str]:
    """
    Parse operation into (verb, mode).

    verb: CONNECT|CLOSE|PING|SEND|RECV|EXCHANGE
    mode: auto|text|binary  (relevant for SEND/EXCHANGE)
    """
    s = (op or "").strip().upper()
    if not s:
        raise ProtocolValidationError(
            "operation is required",
            details={"field": "operation"},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.parse_operation"),
        )

    if s in ("CONNECT", "CLOSE", "PING", "RECV", "EXCHANGE", "SEND"):
        return s, "auto"
    if s == "SEND_TEXT":
        return "SEND", "text"
    if s == "SEND_BINARY":
        return "SEND", "binary"
    if s == "EXCHANGE_TEXT":
        return "EXCHANGE", "text"
    if s == "EXCHANGE_BINARY":
        return "EXCHANGE", "binary"

    # Allow "SEND text" / "SEND binary"
    parts = s.split(None, 1)
    if parts and parts[0] in ("SEND", "EXCHANGE"):
        mode = parts[1].strip().lower() if len(parts) > 1 else "auto"
        if mode not in ("auto", "text", "binary"):
            raise ProtocolValidationError(
                "unsupported websocket message mode",
                details={"mode": redact_value(mode)},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.parse_operation"),
            )
        return parts[0], mode

    raise ProtocolValidationError(
        "unsupported websocket operation",
        details={"operation": redact_value(s)},
        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.parse_operation"),
    )


# =============================================================================
# Typed models
# =============================================================================


@dataclass(frozen=True, slots=True)
class WebSocketConnectorConfig:
    """
    Connector-level configuration.

    target: ws://... or wss://... or shorthand host:port/path
    """

    target: str

    # Optional HTTP headers for handshake (do not include Upgrade/Connection/Sec-WebSocket-* here)
    headers: Mapping[str, str] = field(default_factory=dict)

    # Optional
    subprotocols: Sequence[str] = field(default_factory=tuple)
    origin: str | None = None

    # TLS options (for wss)
    allow_plaintext: bool = False
    verify_tls: bool = True
    ca_file: str | None = None
    server_hostname: str | None = None

    # Timeouts
    connect_timeout_s: float = 5.0
    io_timeout_s: float = 10.0

    # Limits
    max_handshake_bytes: int = _DEFAULT_MAX_HANDSHAKE_BYTES
    max_frame_bytes: int = _DEFAULT_MAX_FRAME_BYTES
    max_message_bytes: int = _DEFAULT_MAX_MESSAGE_BYTES

    # Connection behavior
    keep_connection: bool = False
    auto_pong: bool = True

    # Retry policy (idempotent only)
    backoff_policy: ProtocolBackoffPolicy = field(default_factory=ProtocolBackoffPolicy)

    def __post_init__(self) -> None:
        if self.connect_timeout_s <= 0 or self.io_timeout_s <= 0:
            raise ProtocolValidationError(
                "timeouts must be > 0",
                details={
                    "connect_timeout_s": self.connect_timeout_s,
                    "io_timeout_s": self.io_timeout_s,
                },
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.config.validate"),
            )
        if self.max_handshake_bytes <= 0 or self.max_frame_bytes <= 0 or self.max_message_bytes <= 0:
            raise ProtocolValidationError(
                "limits must be > 0",
                details={
                    "max_handshake_bytes": self.max_handshake_bytes,
                    "max_frame_bytes": self.max_frame_bytes,
                    "max_message_bytes": self.max_message_bytes,
                },
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class WebSocketRequest:
    """
    Typed request envelope (optional for callers).

    SAFETY:
      - message suppressed from repr()
      - use redacted_dict() for logs
    """

    operation: str  # CONNECT/CLOSE/PING/SEND/RECV/EXCHANGE
    message: Any = field(default=None, repr=False)

    message_type: str = "auto"  # auto|text|binary
    receive_timeout_s: float | None = None  # for EXCHANGE/RECV

    close_code: int | None = None
    close_reason: str | None = field(default=None, repr=False)

    timeout_s: float | None = None
    idempotent: bool | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return websocket_request_summary(self)


@dataclass(frozen=True, slots=True)
class WebSocketMessage:
    """
    One received message (text or binary).

    SAFETY:
      - data suppressed from repr()
      - summaries never include raw bytes
    """

    opcode: int
    data: bytes = field(default=b"", repr=False)
    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def is_text(self) -> bool:
        return int(self.opcode) == _OP_TEXT

    def is_binary(self) -> bool:
        return int(self.opcode) == _OP_BIN

    def text(self, encoding: str = "utf-8", *, errors: str = "strict") -> str:
        return (self.data or b"").decode(encoding, errors=errors)

    def redacted_dict(self) -> dict[str, Any]:
        return websocket_message_summary(self)


@dataclass(frozen=True, slots=True)
class WebSocketPong:
    """
    PONG control frame.
    """

    payload: bytes = field(default=b"", repr=False)
    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        b = self.payload or b""
        return {
            "type": "pong",
            "payload_len": len(b),
            "payload_hash": _hash_stable(b[:256].hex()),
            "ts": self.ts,
            "meta": redact_mapping(self.meta),
        }


@dataclass(frozen=True, slots=True)
class WebSocketClose:
    """
    CLOSE control frame.

    SAFETY:
      - reason suppressed from repr()
      - summaries show only hash/length
    """

    code: int | None = None
    reason: str | None = field(default=None, repr=False)
    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return websocket_close_summary(self)


def websocket_request_summary(r: WebSocketRequest) -> dict[str, Any]:
    if not isinstance(r, WebSocketRequest):
        return {"type": type(r).__name__}
    return {
        "operation": redact_value(r.operation),
        "message_shape": _shape_value(r.message),
        "message_type": redact_value(r.message_type),
        "receive_timeout_s": r.receive_timeout_s,
        "close_code": r.close_code,
        "close_reason_len": len(r.close_reason) if r.close_reason else 0,
        "close_reason_hash": _hash_stable(r.close_reason) if r.close_reason else None,
        "timeout_s": r.timeout_s,
        "idempotent": r.idempotent,
        "meta": redact_mapping(r.meta),
    }


def websocket_message_summary(m: WebSocketMessage) -> dict[str, Any]:
    if not isinstance(m, WebSocketMessage):
        return {"type": type(m).__name__}
    b = m.data or b""
    return {
        "type": "message",
        "opcode": int(m.opcode),
        "is_text": bool(m.is_text()),
        "is_binary": bool(m.is_binary()),
        "data_len": len(b),
        "data_hash": _hash_stable(b[:256].hex()),
        "ts": m.ts,
        "meta": redact_mapping(m.meta),
    }


def websocket_close_summary(c: WebSocketClose) -> dict[str, Any]:
    if not isinstance(c, WebSocketClose):
        return {"type": type(c).__name__}
    return {
        "type": "close",
        "code": c.code,
        "reason_len": len(c.reason) if c.reason else 0,
        "reason_hash": _hash_stable(c.reason) if c.reason else None,
        "ts": c.ts,
        "meta": redact_mapping(c.meta),
    }


# =============================================================================
# WebSocket wire implementation (RFC 6455 subset)
# =============================================================================


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except TimeoutError as exc:
            raise ProtocolTimeoutError(
                "websocket recv timed out",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv"),
                code="timeout",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ProtocolNetworkError(
                "websocket recv failed",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv"),
                code="recv_error",
                cause=exc,
            ) from exc
        if not chunk:
            raise ProtocolNetworkError(
                "websocket connection closed by peer",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv"),
                code="connection_closed",
            )
        buf.extend(chunk)
    return bytes(buf)


def _send_all(sock: socket.socket, data: bytes) -> None:
    try:
        sock.sendall(data)
    except TimeoutError as exc:
        raise ProtocolTimeoutError(
            "websocket send timed out",
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.send"),
            code="timeout",
            cause=exc,
        ) from exc
    except OSError as exc:
        raise ProtocolNetworkError(
            "websocket send failed",
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.send"),
            code="send_error",
            cause=exc,
        ) from exc


def _mask_payload(payload: bytes, mask_key: bytes) -> bytes:
    out = bytearray(payload)
    for i in range(len(out)):
        out[i] ^= mask_key[i % 4]
    return bytes(out)


def _build_frame(*, opcode: int, payload: bytes, fin: bool = True) -> bytes:
    """
    Build a client->server frame (masked).
    """
    op = int(opcode) & 0x0F
    b0 = (0x80 if fin else 0x00) | op

    pl = payload or b""
    n = len(pl)

    mask_bit = 0x80
    header = bytearray([b0])

    if n < 126:
        header.append(mask_bit | n)
        ext = b""
    elif n <= 0xFFFF:
        header.append(mask_bit | 126)
        ext = n.to_bytes(2, "big")
    else:
        header.append(mask_bit | 127)
        ext = n.to_bytes(8, "big")

    mask_key = os.urandom(4)
    masked = _mask_payload(pl, mask_key)

    return bytes(header) + ext + mask_key + masked


def _read_frame(sock: socket.socket, *, max_frame_bytes: int) -> tuple[bool, int, bool, bytes]:
    """
    Read one WebSocket frame.

    Returns: (fin, opcode, masked, payload_bytes)
    """
    b = _recv_exact(sock, 2)
    b0 = b[0]
    b1 = b[1]

    fin = bool(b0 & 0x80)
    opcode = b0 & 0x0F

    masked = bool(b1 & 0x80)
    ln = b1 & 0x7F

    if ln == 126:
        ext = _recv_exact(sock, 2)
        ln = int.from_bytes(ext, "big")
    elif ln == 127:
        ext = _recv_exact(sock, 8)
        ln = int.from_bytes(ext, "big")

    if ln > max_frame_bytes:
        raise ProtocolSerializationError(
            "websocket frame payload exceeds max_frame_bytes",
            context=ProtocolErrorContext(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                operation="ws.read_frame",
                details={"payload_len": ln, "max_frame_bytes": max_frame_bytes},
            ),
            code="frame_too_large",
        )

    mask_key = b""
    if masked:
        mask_key = _recv_exact(sock, 4)

    payload = _recv_exact(sock, ln) if ln else b""
    if masked and payload:
        payload = _mask_payload(payload, mask_key)
    return fin, int(opcode), masked, payload


def _parse_close_payload(payload: bytes) -> tuple[int | None, str | None]:
    if not payload:
        return None, None
    if len(payload) == 1:
        return None, None
    code = int.from_bytes(payload[:2], "big")
    reason = None
    if len(payload) > 2:
        try:
            reason = payload[2:].decode("utf-8", errors="strict")
        except Exception:
            reason = None
    return code, reason


def _build_close_payload(code: int | None, reason: str | None) -> bytes:
    if code is None and not reason:
        return b""
    c = int(code if code is not None else 1000)
    if not (0 <= c <= 0xFFFF):
        raise ProtocolValidationError(
            "close code out of range (0..65535)",
            details={"code": c},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.close_payload"),
        )
    out = bytearray(c.to_bytes(2, "big"))
    if reason:
        rb = reason.encode("utf-8", errors="strict")
        out.extend(rb)
    return bytes(out)


# =============================================================================
# Handshake (HTTP Upgrade)
# =============================================================================


def _http_read_headers(sock: socket.socket, *, max_bytes: int) -> tuple[str, dict[str, str]]:
    """
    Read HTTP response headers until CRLFCRLF (bounded).
    Returns (status_line, headers_lowercase).
    """
    buf = bytearray()
    while True:
        if len(buf) >= max_bytes:
            raise ProtocolSerializationError(
                "websocket handshake response headers too large",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.handshake.read_headers"),
                code="handshake_headers_too_large",
            )
        chunk = _recv_exact(sock, 1)
        buf.extend(chunk)
        if buf.endswith(b"\r\n\r\n"):
            break
    text = buf.decode("iso-8859-1", errors="replace")
    lines = text.split("\r\n")
    status_line = lines[0].strip()
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line.strip():
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        headers[k.strip().lower()] = v.strip()
    return status_line, headers


def _http_status_code(status_line: str) -> int:
    # Expect: HTTP/1.1 101 Switching Protocols
    parts = (status_line or "").split()
    if len(parts) < 2:
        return 0
    try:
        return int(parts[1])
    except Exception:
        return 0


def _compute_accept(sec_key: str) -> str:
    raw = (sec_key + _WS_GUID).encode("utf-8")
    sha1 = hashlib.sha1(raw).digest()  # noqa: S324 (required by RFC 6455)
    return base64.b64encode(sha1).decode("ascii")


def _build_handshake_request(
    *,
    resource: str,
    host_header: str,
    sec_key: str,
    headers: Mapping[str, str],
    subprotocols: Sequence[str] | None,
    origin: str | None,
) -> bytes:
    lines = [
        f"GET {resource} HTTP/1.1",
        f"Host: {host_header}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {sec_key}",
        "Sec-WebSocket-Version: 13",
    ]

    if origin:
        lines.append(f"Origin: {origin}")

    if subprotocols:
        # Comma-separated list
        sp = ", ".join(str(x).strip() for x in subprotocols if str(x).strip())
        if sp:
            lines.append(f"Sec-WebSocket-Protocol: {sp}")

    # Caller headers (validated earlier); avoid letting caller override required lines.
    forbidden = {
        "upgrade",
        "connection",
        "sec-websocket-key",
        "sec-websocket-version",
        "host",
    }
    for k, v in headers.items():
        if k.strip().lower() in forbidden:
            continue
        lines.append(f"{k}: {v}")

    lines.append("")  # end headers
    lines.append("")
    return ("\r\n".join(lines)).encode("iso-8859-1", errors="replace")


def _connect_websocket_once(
    *,
    target: dict[str, Any],
    tls_verify: bool,
    ca_file: str | None,
    server_hostname: str | None,
    connect_timeout_s: float,
    io_timeout_s: float,
    max_handshake_bytes: int,
    headers: Mapping[str, str],
    subprotocols: Sequence[str],
    origin: str | None,
) -> socket.socket:
    host = str(target["host"])
    port = int(target["port"])
    tls = bool(target["tls"])
    resource = str(target["resource"])
    host_header = str(target["host_header"])

    s: socket.socket | None = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(float(connect_timeout_s))
        s.connect((host, port))

        if tls:
            try:
                ssl_ctx = _websocket_ssl_context(tls_verify=tls_verify, ca_file=ca_file)
            except Exception:
                ssl_ctx = _websocket_ssl_context(tls_verify=True)

            hn = server_hostname or host
            s = ssl_ctx.wrap_socket(s, server_hostname=hn)

        # From here on, IO timeout
        s.settimeout(float(io_timeout_s))

        sec_key = base64.b64encode(os.urandom(16)).decode("ascii")
        req_bytes = _build_handshake_request(
            resource=resource,
            host_header=host_header,
            sec_key=sec_key,
            headers=headers,
            subprotocols=subprotocols,
            origin=origin,
        )
        _send_all(s, req_bytes)

        status_line, resp_headers = _http_read_headers(s, max_bytes=max_handshake_bytes)
        code = _http_status_code(status_line)

        if code != 101:
            # Map common auth/rate-limit/unavailable
            error_ctx = ProtocolErrorContext(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                operation="ws.handshake",
                details={
                    "status_line": redact_value(status_line),
                    "status_code": code,
                    "url": redact_uri(str(target["url"])),
                    "headers": redact_mapping(resp_headers),
                },
            )
            if code == 401:
                raise ProtocolAuthError("websocket handshake unauthorized", context=error_ctx, code="handshake_401")
            if code == 403:
                raise ProtocolPermissionError("websocket handshake forbidden", context=error_ctx, code="handshake_403")
            if code == 429:
                raise ProtocolRateLimitError(
                    "websocket handshake rate limited",
                    context=error_ctx,
                    code="handshake_429",
                )
            if code in (502, 503, 504):
                raise ProtocolUnavailableError(
                    "websocket handshake failed (gateway/unavailable)",
                    context=error_ctx,
                    code=f"handshake_{code}",
                )
            raise ProtocolError("websocket handshake failed", context=error_ctx, code=f"handshake_{code}")

        # Validate Sec-WebSocket-Accept
        accept = (resp_headers.get("sec-websocket-accept") or "").strip()
        expected = _compute_accept(sec_key)
        if accept != expected:
            raise ProtocolSerializationError(
                "invalid Sec-WebSocket-Accept in handshake response",
                context=ProtocolErrorContext(
                    protocol_id=WEBSOCKET_PROTOCOL_ID,
                    operation="ws.handshake.validate",
                    details={
                        "url": redact_uri(str(target["url"])),
                        "accept_present": bool(accept),
                    },
                ),
                code="bad_accept",
            )

        return s

    except Exception:
        if s is not None:
            try:
                s.close()
            except Exception:
                pass
        raise


# =============================================================================
# Connector
# =============================================================================


class WebSocketProtocolConnector:
    """
    WebSocket ProtocolConnector (ws/wss) using stdlib sockets.

    - keep_connection=False: connect per request (CONNECT just validates connectability).
    - keep_connection=True: maintains a single open connection guarded by a lock.
      A small receive queue buffers messages that arrive while waiting for PONG, etc.
    """

    def __init__(self, config: WebSocketConnectorConfig) -> None:
        self._cfg = config
        self._base_target = normalize_ws_target(config.target)
        self._enforce_transport_governance(self._base_target)

        self._default_headers = normalize_ws_headers(dict(config.headers) if config.headers else {})
        self._default_subprotocols = tuple(str(x) for x in (config.subprotocols or ()))
        self._default_origin = config.origin

        self._sock: socket.socket | None = None
        self._sock_target_url: str | None = None
        self._lock = threading.RLock()

        # Receive queue for persistent mode
        self._rx_queue: list[Any] = []  # WebSocketMessage | WebSocketClose | WebSocketPong

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=WEBSOCKET_PROTOCOL_ID,
            name="WebSocket Connector (stdlib)",
            version=None,
            description="Synchronous WebSocket (RFC 6455) client connector using stdlib sockets.",
            capabilities=(
                "request",
                "connect",
                "send",
                "recv",
                "exchange",
                "ping",
                "close",
                "idempotent_retry",
            ),
            meta={
                "target": redact_uri(str(self._base_target["url"])),
                "keep_connection": bool(self._cfg.keep_connection),
                "tls": bool(self._base_target["tls"]),
                "allow_plaintext": bool(self._cfg.allow_plaintext),
                "max_message_bytes": int(self._cfg.max_message_bytes),
                "max_frame_bytes": int(self._cfg.max_frame_bytes),
                "auto_pong": bool(self._cfg.auto_pong),
            },
        )

    def _enforce_transport_governance(self, target: dict[str, Any]) -> None:
        if bool(target.get("tls")):
            return
        if not self._cfg.allow_plaintext:
            raise ProtocolValidationError(
                "plaintext websocket requires explicit allow_plaintext governance opt-in",
                details={"url": redact_uri(str(target.get("url", ""))), "allow_plaintext": False},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.transport_governance"),
            )
        _LOG.warning(
            "Plaintext WebSocket enabled by explicit governance opt-in for url=%s",
            redact_uri(str(target.get("url", ""))),
        )

    def _close_socket(self) -> None:
        try:
            if self._sock is not None:
                try:
                    # best-effort close frame
                    _send_all(self._sock, _build_frame(opcode=_OP_CLOSE, payload=b""))
                except Exception:
                    pass
                try:
                    self._sock.close()
                except Exception:
                    pass
        finally:
            self._sock = None
            self._sock_target_url = None
            self._rx_queue.clear()

    def _connect(
        self,
        target: dict[str, Any],
        *,
        headers: Mapping[str, str],
        subprotocols: Sequence[str],
        origin: str | None,
        timeout_s: float,
    ) -> socket.socket:
        return _connect_websocket_once(
            target=target,
            tls_verify=bool(self._cfg.verify_tls),
            ca_file=self._cfg.ca_file,
            server_hostname=self._cfg.server_hostname,
            connect_timeout_s=float(timeout_s),
            io_timeout_s=float(self._cfg.io_timeout_s),
            max_handshake_bytes=int(self._cfg.max_handshake_bytes),
            headers=headers,
            subprotocols=subprotocols,
            origin=origin,
        )

    def _ensure_connected(
        self,
        target: dict[str, Any],
        *,
        headers: Mapping[str, str],
        subprotocols: Sequence[str],
        origin: str | None,
        timeout_s: float,
    ) -> socket.socket:
        """
        Ensure persistent socket is connected to the target URL.
        """
        url = str(target["url"])
        if self._sock is not None and self._sock_target_url == url:
            return self._sock

        self._close_socket()
        self._sock = self._connect(
            target, headers=headers, subprotocols=subprotocols, origin=origin, timeout_s=timeout_s
        )
        self._sock_target_url = url
        return self._sock

    def health_check(
        self,
        *,
        endpoint: ProtocolEndpoint | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolHealth:
        """
        Lightweight health check: perform handshake and close immediately.
        """
        target = self._base_target
        if endpoint and (endpoint.uri or endpoint.address):
            try:
                target = normalize_ws_target(endpoint.uri or endpoint.address)
                self._enforce_transport_governance(target)
            except Exception as exc:
                return ProtocolHealth(
                    ok=False,
                    degraded=True,
                    message="invalid endpoint",
                    details={"error": redact_value(str(exc))},
                )

        tmo = float(timeout_s if timeout_s is not None else self._cfg.connect_timeout_s)
        start = time.time()
        s: socket.socket | None = None
        try:
            s = self._connect(
                target,
                headers=self._default_headers,
                subprotocols=self._default_subprotocols,
                origin=self._default_origin,
                timeout_s=tmo,
            )
            # best-effort close
            try:
                _send_all(s, _build_frame(opcode=_OP_CLOSE, payload=b""))
            except Exception:
                pass
            return ProtocolHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "url": redact_uri(str(target["url"])),
                    "connect_ms": round((time.time() - start) * 1000.0, 3),
                    "tls": bool(target["tls"]),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={"url": redact_uri(str(target["url"])), "error": redact_value(str(exc))},
            )
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass

    def request(
        self,
        req: ProtocolRequest,
        *,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolResponse:
        """
        Execute a websocket operation.
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.request"),
            )

        # Coerce to typed request if provided
        if isinstance(req.payload, WebSocketRequest):
            wreq = req.payload
            verb, mode = _parse_operation(wreq.operation)
            mode = (wreq.message_type or mode).strip().lower()
        else:
            verb, mode = _parse_operation(req.operation)
            mode = (
                str((req.meta.get("message_type") if isinstance(req.meta, Mapping) else mode) or mode).strip().lower()
            )
            if mode not in ("auto", "text", "binary"):
                mode = "auto"
            wreq = WebSocketRequest(
                operation=verb,
                message=req.payload,
                message_type=mode,
                receive_timeout_s=(req.meta.get("receive_timeout_s") if isinstance(req.meta, Mapping) else None),
                timeout_s=req.timeout_s,
                idempotent=req.idempotent,
                meta={"from_protocol_request": True},
            )

        # Target override
        target = self._base_target
        override_target = False
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            target = normalize_ws_target(req.endpoint.uri or req.endpoint.address)
            self._enforce_transport_governance(target)
            override_target = True

        # Header merge: config.headers -> req.headers -> req.meta.headers (if provided)
        headers: dict[str, str] = {}
        headers.update(self._default_headers)
        headers.update(normalize_ws_headers(dict(req.headers) if req.headers else {}))
        if isinstance(req.meta, Mapping) and isinstance(req.meta.get("headers"), Mapping):
            headers.update(normalize_ws_headers({str(k): str(v) for k, v in req.meta["headers"].items()}))

        # Optional per-request subprotocols / origin
        subprotocols = self._default_subprotocols
        if isinstance(req.meta, Mapping) and req.meta.get("subprotocols") is not None:
            sp = req.meta.get("subprotocols")
            if isinstance(sp, Sequence) and not isinstance(sp, (str, bytes, bytearray)):
                subprotocols = tuple(str(x) for x in sp)
            else:
                subprotocols = (str(sp),)

        origin = self._default_origin
        if isinstance(req.meta, Mapping) and req.meta.get("origin") is not None:
            origin = str(req.meta.get("origin"))

        # Timeouts
        connect_tmo = float(timeout_s if timeout_s is not None else self._cfg.connect_timeout_s)
        if connect_tmo <= 0:
            raise ProtocolValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": connect_tmo},
                context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.request"),
            )

        # Determine idempotency (safe defaults)
        idempotent_default = verb in ("CONNECT", "RECV", "PING", "CLOSE")
        idempotent = (
            bool(req.idempotent)
            if req.idempotent is not None
            else bool(wreq.idempotent if wreq.idempotent is not None else idempotent_default)
        )

        # Retry loop
        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        attempt = 0

        while True:
            try:
                start_ns = time.time_ns()

                # socket selection:
                # - persistent only if keep_connection and not override_target
                if self._cfg.keep_connection and not override_target:
                    with self._lock:
                        sock = self._ensure_connected(
                            target,
                            headers=headers,
                            subprotocols=subprotocols,
                            origin=origin,
                            timeout_s=connect_tmo,
                        )
                        resp = self._handle(sock, verb=verb, wreq=wreq, mode=mode, req=req)
                else:
                    sock = self._connect(
                        target,
                        headers=headers,
                        subprotocols=subprotocols,
                        origin=origin,
                        timeout_s=connect_tmo,
                    )
                    try:
                        resp = self._handle(sock, verb=verb, wreq=wreq, mode=mode, req=req)
                    finally:
                        # best-effort close frame then close
                        try:
                            _send_all(sock, _build_frame(opcode=_OP_CLOSE, payload=b""))
                        except Exception:
                            pass
                        try:
                            sock.close()
                        except Exception:
                            pass

                duration_ms = (time.time_ns() - start_ns) / 1_000_000.0

                stats = dict(resp.stats or {})
                stats.update(
                    redact_mapping(
                        {
                            "attempt": attempt,
                            "duration_ms": round(duration_ms, 3),
                            "url": redact_uri(str(target["url"])),
                            "tls": bool(target["tls"]),
                            "operation": verb,
                        }
                    )
                )

                return ProtocolResponse(
                    protocol_id=WEBSOCKET_PROTOCOL_ID,
                    ok=resp.ok,
                    status_code=resp.status_code,
                    headers=resp.headers,
                    payload=resp.payload,
                    stats=stats,
                    ts=resp.ts,
                    meta=redact_mapping(req.meta) if isinstance(req.meta, Mapping) else {},
                )

            except (ProtocolTimeoutError, ProtocolNetworkError, ProtocolSerializationError):
                # Drop persistent socket on these errors
                if self._cfg.keep_connection and not override_target:
                    with self._lock:
                        self._close_socket()

                if idempotent:
                    attempt += 1
                    if attempt > max_attempts:
                        raise
                    time.sleep(compute_backoff_s(policy, attempt=attempt))
                    continue
                raise

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _coerce_message_bytes(self, message: Any, *, mode: str) -> tuple[int, bytes]:
        """
        Convert message into (opcode, bytes) according to mode.
        """
        m = message
        if m is None:
            # empty text by default unless forced binary
            if mode == "binary":
                return _OP_BIN, b""
            return _OP_TEXT, b""

        if mode == "binary":
            if isinstance(m, (bytes, bytearray)):
                return _OP_BIN, bytes(m)
            # allow str -> encoded bytes but still binary
            if isinstance(m, str):
                return _OP_BIN, m.encode("utf-8", errors="strict")
            # JSON -> bytes
            if isinstance(m, (Mapping, list, tuple)):
                s = json.dumps(m, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
                return _OP_BIN, s.encode("utf-8", errors="strict")
            return _OP_BIN, str(m).encode("utf-8", errors="strict")

        if mode == "text":
            if isinstance(m, str):
                return _OP_TEXT, m.encode("utf-8", errors="strict")
            if isinstance(m, (Mapping, list, tuple)):
                s = json.dumps(m, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
                return _OP_TEXT, s.encode("utf-8", errors="strict")
            if isinstance(m, (bytes, bytearray)):
                # Treat bytes as utf-8 text
                try:
                    _ = bytes(m).decode("utf-8", errors="strict")
                except Exception as exc:  # noqa: BLE001
                    raise ProtocolSerializationError(
                        "bytes payload is not valid utf-8 for text message",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.coerce_message"),
                        code="invalid_utf8",
                        cause=exc,
                    ) from exc
                return _OP_TEXT, bytes(m)
            return _OP_TEXT, str(m).encode("utf-8", errors="strict")

        # auto
        if isinstance(m, (bytes, bytearray)):
            return _OP_BIN, bytes(m)
        if isinstance(m, str):
            return _OP_TEXT, m.encode("utf-8", errors="strict")
        if isinstance(m, (Mapping, list, tuple)):
            s = json.dumps(m, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
            return _OP_TEXT, s.encode("utf-8", errors="strict")
        return _OP_TEXT, str(m).encode("utf-8", errors="strict")

    def _recv_event(self, sock: socket.socket, *, auto_pong: bool) -> Any:
        """
        Receive the next meaningful event:
          - WebSocketMessage (text/binary)
          - WebSocketPong
          - WebSocketClose

        Handles:
          - fragmented messages (continuation frames)
          - responds to PING with PONG when auto_pong=True
        """
        max_frame = int(self._cfg.max_frame_bytes)
        max_msg = int(self._cfg.max_message_bytes)

        cur_opcode: int | None = None
        acc = bytearray()

        while True:
            fin, opcode, _masked, payload = _read_frame(sock, max_frame_bytes=max_frame)

            # Control frames must not be fragmented and must be <=125
            if opcode in (_OP_CLOSE, _OP_PING, _OP_PONG):
                if not fin:
                    raise ProtocolSerializationError(
                        "fragmented control frame is invalid",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv_event"),
                        code="fragmented_control",
                    )
                if len(payload) > 125:
                    raise ProtocolSerializationError(
                        "control frame payload too large",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv_event"),
                        code="control_too_large",
                    )

                if opcode == _OP_PING:
                    if auto_pong:
                        _send_all(sock, _build_frame(opcode=_OP_PONG, payload=payload))
                    # Continue waiting for a message/pong/close
                    continue

                if opcode == _OP_PONG:
                    return WebSocketPong(payload=payload, meta={})

                # CLOSE
                code, reason = _parse_close_payload(payload)
                # Best-effort echo close if we haven't already
                try:
                    _send_all(sock, _build_frame(opcode=_OP_CLOSE, payload=payload))
                except Exception:
                    pass
                return WebSocketClose(code=code, reason=reason, meta={})

            # Data frames
            if opcode == _OP_CONT:
                if cur_opcode is None:
                    # Continuation without a start
                    raise ProtocolSerializationError(
                        "unexpected continuation frame",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv_event"),
                        code="unexpected_continuation",
                    )
            elif opcode in (_OP_TEXT, _OP_BIN):
                if cur_opcode is not None:
                    # New data frame while assembling another
                    raise ProtocolSerializationError(
                        "received new data frame while previous message incomplete",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv_event"),
                        code="interleaved_data",
                    )
                cur_opcode = opcode
            else:
                # Unknown / reserved opcode
                raise ProtocolSerializationError(
                    "unknown websocket opcode",
                    context=ProtocolErrorContext(
                        protocol_id=WEBSOCKET_PROTOCOL_ID,
                        operation="ws.recv_event",
                        details={"opcode": opcode},
                    ),
                    code="unknown_opcode",
                )

            if payload:
                acc.extend(payload)
                if len(acc) > max_msg:
                    raise ProtocolSerializationError(
                        "websocket message exceeds max_message_bytes",
                        context=ProtocolErrorContext(
                            protocol_id=WEBSOCKET_PROTOCOL_ID,
                            operation="ws.recv_event",
                            details={"msg_len": len(acc), "max_message_bytes": max_msg},
                        ),
                        code="message_too_large",
                    )

            if fin:
                op = int(cur_opcode) if cur_opcode is not None else _OP_TEXT
                data = bytes(acc)
                # reset assembler
                cur_opcode = None
                acc = bytearray()
                return WebSocketMessage(opcode=op, data=data, meta={})

    def _handle(
        self,
        sock: socket.socket,
        *,
        verb: str,
        wreq: WebSocketRequest,
        mode: str,
        req: ProtocolRequest,
    ) -> ProtocolResponse:
        now_ts = int(time.time())
        meta = req.meta if isinstance(req.meta, Mapping) else {}
        auto_pong = bool(meta.get("auto_pong", self._cfg.auto_pong))

        # If we have queued events (persistent mode), consume them first for RECV / ping waits, etc.
        def pop_queue() -> Any | None:
            if not self._cfg.keep_connection:
                return None
            if self._rx_queue:
                return self._rx_queue.pop(0)
            return None

        if verb == "CONNECT":
            # In per-request mode, CONNECT is a connectivity probe (handshake already done)
            return ProtocolResponse(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping({"connected": True}),
                ts=now_ts,
                meta={},
            )

        if verb == "CLOSE":
            payload = _build_close_payload(wreq.close_code, wreq.close_reason)
            _send_all(sock, _build_frame(opcode=_OP_CLOSE, payload=payload))
            if self._cfg.keep_connection:
                self._close_socket()
            return ProtocolResponse(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping({"closed": True, "close_code": wreq.close_code}),
                ts=now_ts,
                meta={},
            )

        if verb == "SEND":
            opcode, payload = self._coerce_message_bytes(wreq.message, mode=mode)
            if len(payload) > int(self._cfg.max_message_bytes):
                raise ProtocolValidationError(
                    "send payload exceeds max_message_bytes",
                    details={
                        "len": len(payload),
                        "max_message_bytes": int(self._cfg.max_message_bytes),
                    },
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.send"),
                )
            _send_all(sock, _build_frame(opcode=opcode, payload=payload))
            return ProtocolResponse(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping(
                    {
                        "sent": True,
                        "opcode": opcode,
                        "payload_len": len(payload),
                        "payload_hash": _hash_stable(payload[:256].hex()),
                    }
                ),
                ts=now_ts,
                meta={},
            )

        if verb == "PING":
            # send ping (payload optional but must be <=125)
            ping_payload = b""
            if wreq.message is not None:
                _op, b = self._coerce_message_bytes(wreq.message, mode="binary" if mode == "binary" else "text")
                ping_payload = b
            if len(ping_payload) > 125:
                raise ProtocolValidationError(
                    "ping payload too large (<=125 bytes)",
                    details={"len": len(ping_payload)},
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.ping"),
                )
            _send_all(sock, _build_frame(opcode=_OP_PING, payload=ping_payload))

            # Wait for pong, buffering messages into rx_queue to avoid message loss in persistent mode
            deadline = time.time() + float(wreq.receive_timeout_s or req.timeout_s or self._cfg.io_timeout_s)
            while True:
                q = pop_queue()
                if isinstance(q, WebSocketPong):
                    return ProtocolResponse(
                        protocol_id=WEBSOCKET_PROTOCOL_ID,
                        ok=True,
                        status_code=0,
                        headers={},
                        payload=q,
                        stats=redact_mapping(q.redacted_dict()),
                        ts=now_ts,
                        meta={},
                    )
                if q is not None:
                    # Not a pong; keep it buffered (we popped it)
                    self._rx_queue.insert(0, q)

                # Adjust socket timeout to remaining window
                remaining = deadline - time.time()
                if remaining <= 0:
                    raise ProtocolTimeoutError(
                        "websocket ping timed out waiting for pong",
                        context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.ping"),
                        code="pong_timeout",
                    )
                prev = sock.gettimeout()
                try:
                    sock.settimeout(remaining)
                    ev = self._recv_event(sock, auto_pong=auto_pong)
                finally:
                    try:
                        sock.settimeout(prev)
                    except Exception:
                        pass

                if isinstance(ev, WebSocketPong):
                    return ProtocolResponse(
                        protocol_id=WEBSOCKET_PROTOCOL_ID,
                        ok=True,
                        status_code=0,
                        headers={},
                        payload=ev,
                        stats=redact_mapping(ev.redacted_dict()),
                        ts=now_ts,
                        meta={},
                    )

                # If close, return not-ok but include event
                if isinstance(ev, WebSocketClose):
                    if self._cfg.keep_connection:
                        self._close_socket()
                    return ProtocolResponse(
                        protocol_id=WEBSOCKET_PROTOCOL_ID,
                        ok=False,
                        status_code=int(ev.code or 1),
                        headers={},
                        payload=ev,
                        stats=redact_mapping(ev.redacted_dict()),
                        ts=now_ts,
                        meta={},
                    )

                # Otherwise it's a message; buffer and continue waiting for pong
                if self._cfg.keep_connection:
                    self._rx_queue.append(ev)

        if verb == "RECV":
            q = pop_queue()
            if q is not None:
                if isinstance(q, WebSocketClose):
                    return ProtocolResponse(
                        protocol_id=WEBSOCKET_PROTOCOL_ID,
                        ok=False,
                        status_code=int(q.code or 1),
                        headers={},
                        payload=q,
                        stats=redact_mapping(q.redacted_dict()),
                        ts=now_ts,
                        meta={},
                    )
                return ProtocolResponse(
                    protocol_id=WEBSOCKET_PROTOCOL_ID,
                    ok=True,
                    status_code=0,
                    headers={},
                    payload=q,
                    stats=redact_mapping(getattr(q, "redacted_dict", lambda: {})()),
                    ts=now_ts,
                    meta={},
                )

            # Wait for one message/close
            rx_tmo = float(wreq.receive_timeout_s or req.timeout_s or self._cfg.io_timeout_s)
            if rx_tmo <= 0:
                raise ProtocolValidationError(
                    "receive timeout must be > 0",
                    details={"receive_timeout_s": rx_tmo},
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.recv"),
                )
            prev = sock.gettimeout()
            try:
                sock.settimeout(rx_tmo)
                ev = self._recv_event(sock, auto_pong=auto_pong)
            finally:
                try:
                    sock.settimeout(prev)
                except Exception:
                    pass

            if isinstance(ev, WebSocketClose):
                if self._cfg.keep_connection:
                    self._close_socket()
                return ProtocolResponse(
                    protocol_id=WEBSOCKET_PROTOCOL_ID,
                    ok=False,
                    status_code=int(ev.code or 1),
                    headers={},
                    payload=ev,
                    stats=redact_mapping(ev.redacted_dict()),
                    ts=now_ts,
                    meta={},
                )

            return ProtocolResponse(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=ev,
                stats=redact_mapping(getattr(ev, "redacted_dict", lambda: {})()),
                ts=now_ts,
                meta={},
            )

        if verb == "EXCHANGE":
            # Send then receive one event
            opcode, payload = self._coerce_message_bytes(wreq.message, mode=mode)
            if len(payload) > int(self._cfg.max_message_bytes):
                raise ProtocolValidationError(
                    "send payload exceeds max_message_bytes",
                    details={
                        "len": len(payload),
                        "max_message_bytes": int(self._cfg.max_message_bytes),
                    },
                    context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.exchange"),
                )
            _send_all(sock, _build_frame(opcode=opcode, payload=payload))

            # Receive
            rx_tmo = float(wreq.receive_timeout_s or req.timeout_s or self._cfg.io_timeout_s)
            prev = sock.gettimeout()
            try:
                sock.settimeout(rx_tmo)
                ev = self._recv_event(sock, auto_pong=auto_pong)
            finally:
                try:
                    sock.settimeout(prev)
                except Exception:
                    pass

            if isinstance(ev, WebSocketClose):
                if self._cfg.keep_connection:
                    self._close_socket()
                return ProtocolResponse(
                    protocol_id=WEBSOCKET_PROTOCOL_ID,
                    ok=False,
                    status_code=int(ev.code or 1),
                    headers={},
                    payload=ev,
                    stats=redact_mapping(
                        {
                            "sent_opcode": opcode,
                            "sent_len": len(payload),
                            "sent_hash": _hash_stable(payload[:256].hex()),
                            **ev.redacted_dict(),
                        }
                    ),
                    ts=now_ts,
                    meta={},
                )

            return ProtocolResponse(
                protocol_id=WEBSOCKET_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=ev,
                stats=redact_mapping(
                    {
                        "sent_opcode": opcode,
                        "sent_len": len(payload),
                        "sent_hash": _hash_stable(payload[:256].hex()),
                        "recv": getattr(ev, "redacted_dict", lambda: {})(),
                    }
                ),
                ts=now_ts,
                meta={},
            )

        raise ProtocolUnsupportedError(
            "unsupported websocket operation",
            details={"operation": redact_value(verb)},
            context=ProtocolErrorContext(protocol_id=WEBSOCKET_PROTOCOL_ID, operation="ws.handle"),
            code="unsupported_operation",
        )
