"""
===============================================================================
Francis 2.0 — Protocol Connectors (MQTT 3.1.1)
Path: connectors/protocols/mqtt.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a synchronous MQTT 3.1.1 connector using ONLY the Python
standard library (socket + ssl). It fits the provider-agnostic ProtocolConnector
contract in connectors/protocols/__init__.py.

Supported:
  - MQTT 3.1.1 (Protocol Name "MQTT", Level 4)
  - CONNECT / CONNACK
  - PUBLISH (QoS 0 only)
  - SUBSCRIBE / SUBACK (QoS 0 requested); optional "subscribe_once" semantics
  - PINGREQ / PINGRESP
  - DISCONNECT

Not supported (intentionally, to keep footprint small + safe):
  - QoS 1/2 flows (PUBACK/PUBREC/PUBREL/PUBCOMP)
  - Retained message management beyond retain flag on publish
  - Will messages
  - MQTT v5 properties
  - Long-lived streaming subscription callbacks (this connector is request/response oriented)

SAFETY & OBSERVABILITY
----------------------
- Never logs raw payloads or raw topic values; summaries include hashes/lengths only.
- Username/password are never logged.
- Packet size is bounded (max_packet_bytes) to avoid memory blowups.
- Retries:
    * only for idempotent operations (reads/subscribe_once/ping)
    * only on network/timeouts and a small set of transient conditions

REQUEST MAPPING (ProtocolRequest)
---------------------------------
operation patterns:
  - "PUBLISH <topic>"
  - "SUBSCRIBE <topic_filter>"
  - "PING"
  - "CONNECT"
  - "DISCONNECT"

topic can also be provided via req.meta:
  - req.meta["topic"] or req.meta["topic_filter"]

Publish options (req.meta):
  - qos: 0 only
  - retain: bool
  - encoding: "utf-8" (default) for str/json payloads

Subscribe options (req.meta):
  - qos: 0 only
  - wait: bool (default True). If False, returns after SUBACK.
  - receive_timeout_s: float (override timeout for receiving one message)

Payload mapping:
  - bytes/bytearray -> sent raw
  - str -> utf-8 bytes
  - Mapping/list/tuple -> JSON bytes (utf-8)

Response payloads:
  - PUBLISH: None (ok=True if sent)
  - SUBSCRIBE(wait=True): MqttMessage
  - SUBSCRIBE(wait=False): MqttSubAck
  - PING: None
  - CONNECT/DISCONNECT: None

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import socket
import ssl
import threading
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

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
    ProtocolRequest,
    ProtocolResponse,
    ProtocolSerializationError,
    ProtocolTimeoutError,
    ProtocolUnavailableError,
    ProtocolUnsupportedError,
    ProtocolValidationError,
    compute_backoff_s,
    redact_mapping,
    redact_value,
)

__all__ = [
    "MQTT_PROTOCOL_ID",
    "MQTT_DEFAULT_PORT",
    "MQTTS_DEFAULT_PORT",
    "MqttConnectorConfig",
    "MqttMessage",
    "MqttSubAck",
    "MqttRequest",
    "normalize_mqtt_target",
    "normalize_mqtt_topic",
    "normalize_mqtt_topic_filter",
    "MqttProtocolConnector",
    "mqtt_request_summary",
    "mqtt_message_summary",
]


MQTT_PROTOCOL_ID = "mqtt"
MQTT_DEFAULT_PORT = 1883
MQTTS_DEFAULT_PORT = 8883

# MQTT control packet types (high 4 bits)
_PKT_CONNECT = 0x01
_PKT_CONNACK = 0x02
_PKT_PUBLISH = 0x03
_PKT_SUBSCRIBE = 0x08
_PKT_SUBACK = 0x09
_PKT_PINGREQ = 0x0C
_PKT_PINGRESP = 0x0D
_PKT_DISCONNECT = 0x0E

# QoS supported by this connector
_SUPPORTED_QOS = {0}

# Conservative bounds
_MAX_TOPIC_LEN = 512
_MAX_PACKET_BYTES_DEFAULT = 2 * 1024 * 1024  # 2MB


# =============================================================================
# Small hashing + safe shapes (no raw payloads/topics in logs)
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


def normalize_mqtt_target(target: str) -> tuple[str, int, bool]:
    """
    Normalize a MQTT target into (host, port, tls).

    Accepts:
      - "host:port"
      - "host" (defaults to 1883)
      - "mqtt://host:port"
      - "mqtts://host:port" (TLS, defaults to 8883)

    Safety:
      - rejects userinfo
      - strips query/fragment
    """
    raw = (target or "").strip()
    if not raw:
        raise ProtocolValidationError(
            "mqtt target is required",
            details={"field": "target"},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
        )
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "mqtt target contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
        )

    if "://" in raw:
        p = urlsplit(raw)
        if p.username or p.password:
            raise ProtocolValidationError(
                "mqtt target must not include userinfo",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        scheme = (p.scheme or "").lower()
        if scheme not in ("mqtt", "mqtts"):
            raise ProtocolValidationError(
                "unsupported mqtt scheme",
                details={"scheme": redact_value(scheme)},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        host = p.hostname
        if not host:
            raise ProtocolValidationError(
                "mqtt target missing host",
                details={"target": redact_value(raw)},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        tls = scheme == "mqtts"
        port = int(p.port or (MQTTS_DEFAULT_PORT if tls else MQTT_DEFAULT_PORT))
        if not (1 <= port <= 65535):
            raise ProtocolValidationError(
                "port out of range (1..65535)",
                details={"port": port},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        return host, port, tls

    # host:port or host
    if ":" in raw:
        host, port_s = raw.rsplit(":", 1)
        host = host.strip()
        if not host:
            raise ProtocolValidationError(
                "mqtt target missing host",
                details={"target": redact_value(raw)},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        try:
            port = int(port_s.strip())
        except Exception as exc:  # noqa: BLE001
            raise ProtocolValidationError(
                "invalid port",
                details={"port": redact_value(port_s)},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
                cause=exc,
            ) from exc
        if not (1 <= port <= 65535):
            raise ProtocolValidationError(
                "port out of range (1..65535)",
                details={"port": port},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_target"),
            )
        return host, port, False

    return raw, MQTT_DEFAULT_PORT, False


def normalize_mqtt_topic(topic: str) -> str:
    """
    Validate a publish topic.

    - must be non-empty
    - must not contain wildcards (+ or #)
    - must not contain NUL/CR/LF
    """
    t = (topic or "").strip()
    if not t:
        raise ProtocolValidationError(
            "mqtt topic is required",
            details={"field": "topic"},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic"),
        )
    if "\x00" in t or "\r" in t or "\n" in t:
        raise ProtocolValidationError(
            "mqtt topic contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic"),
        )
    if "+" in t or "#" in t:
        raise ProtocolValidationError(
            "mqtt publish topic must not contain wildcards (+ or #)",
            details={"topic_hash": _hash_stable(t), "topic_len": len(t)},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic"),
        )
    if len(t) > _MAX_TOPIC_LEN:
        raise ProtocolValidationError(
            "mqtt topic too long",
            details={"topic_len": len(t), "max": _MAX_TOPIC_LEN},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic"),
        )
    return t


def normalize_mqtt_topic_filter(topic_filter: str) -> str:
    """
    Validate a subscribe topic filter.

    We allow wildcards, but still enforce:
      - non-empty
      - no NUL/CR/LF
      - length cap
    """
    t = (topic_filter or "").strip()
    if not t:
        raise ProtocolValidationError(
            "mqtt topic_filter is required",
            details={"field": "topic_filter"},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic_filter"),
        )
    if "\x00" in t or "\r" in t or "\n" in t:
        raise ProtocolValidationError(
            "mqtt topic_filter contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic_filter"),
        )
    if len(t) > _MAX_TOPIC_LEN:
        raise ProtocolValidationError(
            "mqtt topic_filter too long",
            details={"topic_filter_len": len(t), "max": _MAX_TOPIC_LEN},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.normalize_topic_filter"),
        )
    return t


def _parse_operation(op: str) -> tuple[str, str | None]:
    """
    Parse operation string -> (verb, arg).

    Supported:
      - "PUBLISH <topic>"
      - "SUBSCRIBE <filter>"
      - "PING"
      - "CONNECT"
      - "DISCONNECT"
    """
    s = (op or "").strip()
    if not s:
        raise ProtocolValidationError(
            "operation is required",
            details={"field": "operation"},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.parse_operation"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise ProtocolValidationError(
            "operation contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.parse_operation"),
        )
    parts = s.split(None, 1)
    verb = parts[0].strip().upper()
    arg = parts[1].strip() if len(parts) > 1 else None
    return verb, arg


# =============================================================================
# MQTT wire helpers (3.1.1)
# =============================================================================


def _encode_varint(n: int) -> bytes:
    """
    MQTT Remaining Length encoding (7-bit varint).
    """
    if n < 0:
        raise ProtocolValidationError(
            "negative remaining length",
            details={"n": n},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.encode_varint"),
        )
    out = bytearray()
    x = n
    while True:
        digit = x % 128
        x //= 128
        if x > 0:
            digit |= 0x80
        out.append(digit)
        if x == 0:
            break
        if len(out) > 4:
            raise ProtocolValidationError(
                "remaining length too large",
                details={"n": n},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.encode_varint"),
            )
    return bytes(out)


def _decode_varint(recv1: callable) -> int:
    """
    Decode MQTT Remaining Length by repeatedly calling recv1() -> bytes(1).
    """
    multiplier = 1
    value = 0
    for _i in range(4):
        b = recv1()
        if not b:
            raise ProtocolSerializationError(
                "unexpected EOF while decoding remaining length",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.decode_varint"),
                code="eof_varint",
            )
        digit = b[0]
        value += (digit & 0x7F) * multiplier
        multiplier *= 128
        if (digit & 0x80) == 0:
            return value
    raise ProtocolSerializationError(
        "malformed remaining length (too long)",
        context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.decode_varint"),
        code="bad_varint",
    )


def _enc_utf8(s: str) -> bytes:
    b = (s or "").encode("utf-8", errors="strict")
    if len(b) > 0xFFFF:
        raise ProtocolValidationError(
            "utf8 string too long",
            details={"len": len(b)},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.enc_utf8"),
        )
    return bytes([(len(b) >> 8) & 0xFF, len(b) & 0xFF]) + b


def _dec_utf8(buf: bytes, off: int) -> tuple[str, int]:
    if off + 2 > len(buf):
        raise ProtocolSerializationError(
            "short buffer decoding utf8 length",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.dec_utf8"),
            code="short_utf8_len",
        )
    ln = (buf[off] << 8) | buf[off + 1]
    off += 2
    if off + ln > len(buf):
        raise ProtocolSerializationError(
            "short buffer decoding utf8 string",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.dec_utf8"),
            code="short_utf8_str",
        )
    s = buf[off : off + ln].decode("utf-8", errors="strict")
    return s, off + ln


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except TimeoutError as exc:
            raise ProtocolTimeoutError(
                "mqtt recv timed out",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.recv"),
                code="timeout",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ProtocolNetworkError(
                "mqtt recv failed",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.recv"),
                code="recv_error",
                cause=exc,
            ) from exc
        if not chunk:
            raise ProtocolNetworkError(
                "mqtt connection closed by peer",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.recv"),
                code="connection_closed",
            )
        buf.extend(chunk)
    return bytes(buf)


def _read_packet(sock: socket.socket, *, max_packet_bytes: int) -> tuple[int, int, bytes]:
    """
    Read one MQTT control packet.

    Returns: (packet_type, flags, body_bytes)
    """
    first = _recv_exact(sock, 1)
    b0 = first[0]
    pkt_type = (b0 >> 4) & 0x0F
    flags = b0 & 0x0F

    def recv1() -> bytes:
        return _recv_exact(sock, 1)

    remaining = _decode_varint(recv1)
    if remaining > max_packet_bytes:
        raise ProtocolSerializationError(
            "mqtt packet too large",
            context=ProtocolErrorContext(
                protocol_id=MQTT_PROTOCOL_ID,
                operation="mqtt.read_packet",
                details={"remaining": remaining, "max_packet_bytes": max_packet_bytes},
            ),
            code="packet_too_large",
        )
    body = _recv_exact(sock, remaining) if remaining else b""
    return pkt_type, flags, body


def _build_connect_packet(
    *,
    client_id: str,
    keep_alive_s: int,
    clean_session: bool,
    username: str | None,
    password: str | None,
) -> bytes:
    # Variable header
    vh = bytearray()
    vh.extend(_enc_utf8("MQTT"))
    vh.append(0x04)  # protocol level 4 (3.1.1)

    # Connect flags
    flags = 0
    if clean_session:
        flags |= 0x02
    if username is not None:
        flags |= 0x80
    if password is not None:
        flags |= 0x40
    # Will flags not supported here (0)

    vh.append(flags)
    if not (0 <= int(keep_alive_s) <= 0xFFFF):
        raise ProtocolValidationError(
            "keep_alive_s out of range (0..65535)",
            details={"keep_alive_s": keep_alive_s},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.build_connect"),
        )
    vh.append((keep_alive_s >> 8) & 0xFF)
    vh.append(keep_alive_s & 0xFF)

    # Payload
    pl = bytearray()
    pl.extend(_enc_utf8(client_id))
    if username is not None:
        pl.extend(_enc_utf8(username))
    if password is not None:
        pl.extend(_enc_utf8(password))

    body = bytes(vh) + bytes(pl)
    fixed = bytes([(_PKT_CONNECT << 4) | 0x00]) + _encode_varint(len(body))
    return fixed + body


def _build_pingreq() -> bytes:
    return bytes([(_PKT_PINGREQ << 4) | 0x00, 0x00])


def _build_disconnect() -> bytes:
    return bytes([(_PKT_DISCONNECT << 4) | 0x00, 0x00])


def _build_publish_packet(topic: str, payload: bytes, *, retain: bool, qos: int) -> bytes:
    if qos not in _SUPPORTED_QOS:
        raise ProtocolUnsupportedError(
            "only QoS 0 is supported by this connector",
            details={"qos": qos},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.build_publish"),
            code="qos_not_supported",
        )
    t = normalize_mqtt_topic(topic)
    vh = _enc_utf8(t)  # topic name
    # QoS 0 => no packet id
    body = vh + (payload or b"")
    flags = 0x00
    if retain:
        flags |= 0x01
    # dup=0, qos=0
    fixed = bytes([(_PKT_PUBLISH << 4) | flags]) + _encode_varint(len(body))
    return fixed + body


def _build_subscribe_packet(packet_id: int, topic_filter: str, qos: int) -> bytes:
    if qos not in _SUPPORTED_QOS:
        raise ProtocolUnsupportedError(
            "only QoS 0 is supported by this connector",
            details={"qos": qos},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.build_subscribe"),
            code="qos_not_supported",
        )
    tf = normalize_mqtt_topic_filter(topic_filter)

    vh = bytes([(packet_id >> 8) & 0xFF, packet_id & 0xFF])
    pl = _enc_utf8(tf) + bytes([qos])
    body = vh + pl

    # SUBSCRIBE flags must be 0b0010
    fixed = bytes([(_PKT_SUBSCRIBE << 4) | 0x02]) + _encode_varint(len(body))
    return fixed + body


def _decode_connack(body: bytes) -> tuple[int, int]:
    if len(body) != 2:
        raise ProtocolSerializationError(
            "invalid CONNACK length",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.decode_connack"),
            code="bad_connack_len",
        )
    ack_flags = body[0]
    rc = body[1]
    return ack_flags, rc


def _decode_suback(body: bytes) -> tuple[int, list[int]]:
    if len(body) < 3:
        raise ProtocolSerializationError(
            "invalid SUBACK length",
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.decode_suback"),
            code="bad_suback_len",
        )
    pid = (body[0] << 8) | body[1]
    codes = list(body[2:])
    return pid, codes


def _decode_publish(flags: int, body: bytes) -> tuple[str, bytes, int, bool]:
    # flags includes retain in bit0; qos in bits 1-2; dup in bit3
    retain = bool(flags & 0x01)
    qos = (flags >> 1) & 0x03

    off = 0
    topic, off = _dec_utf8(body, off)

    if qos != 0:
        # QoS>0 requires packet identifier; not supported here
        raise ProtocolUnsupportedError(
            "received QoS>0 publish, not supported by this connector",
            details={"qos": qos},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.decode_publish"),
            code="rx_qos_not_supported",
        )

    payload = body[off:]
    return topic, payload, qos, retain


# =============================================================================
# Public models
# =============================================================================


@dataclass(frozen=True, slots=True)
class MqttConnectorConfig:
    """
    Configuration for MqttProtocolConnector.

    target:
      - "host:port" or "mqtt(s)://host:port"
    """

    target: str

    client_id: str | None = None
    clean_session: bool = True
    keep_alive_s: int = 30

    # Optional authentication (never logged)
    username: str | None = None
    password: str | None = None

    # TLS options (only used when mqtts:// or when force_tls=True)
    force_tls: bool = False
    verify_tls: bool = True
    ca_file: str | None = None
    server_hostname: str | None = None  # optional override

    # Transport timeouts
    connect_timeout_s: float = 5.0
    io_timeout_s: float = 5.0

    # Packet limit
    max_packet_bytes: int = _MAX_PACKET_BYTES_DEFAULT

    # Connection reuse
    keep_connection: bool = False

    # Retry policy (applies ONLY if request is idempotent)
    backoff_policy: ProtocolBackoffPolicy = field(default_factory=ProtocolBackoffPolicy)


@dataclass(frozen=True, slots=True)
class MqttMessage:
    """
    One MQTT message (PUBLISH received).

    SAFETY:
      - payload suppressed from repr()
      - use mqtt_message_summary() for log-safe view
    """

    topic: str
    payload: bytes = field(default=b"", repr=False)

    qos: int = 0
    retain: bool = False
    ts: int = field(default_factory=lambda: int(time.time()))
    meta: Mapping[str, Any] = field(default_factory=dict)

    def payload_text(self, encoding: str = "utf-8", *, errors: str = "strict") -> str:
        return (self.payload or b"").decode(encoding, errors=errors)

    def redacted_dict(self) -> dict[str, Any]:
        return mqtt_message_summary(self)


@dataclass(frozen=True, slots=True)
class MqttSubAck:
    """
    Acknowledge for SUBSCRIBE request.
    """

    packet_id: int
    return_codes: Sequence[int] = field(default_factory=tuple)
    meta: Mapping[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        # 0x80 indicates failure
        return all(int(c) != 0x80 for c in self.return_codes)


@dataclass(frozen=True, slots=True)
class MqttRequest:
    """
    A typed MQTT request envelope (optional for callers).

    SAFETY:
      - payload suppressed from repr()
      - redacted_dict() is safe for logs
    """

    operation: str  # "PUBLISH"|"SUBSCRIBE"|"PING"|"CONNECT"|"DISCONNECT"
    topic: str | None = None
    topic_filter: str | None = None

    payload: Any = field(default=None, repr=False)

    qos: int = 0
    retain: bool = False

    wait: bool = True  # for SUBSCRIBE: wait for one message
    receive_timeout_s: float | None = None

    timeout_s: float | None = None
    idempotent: bool | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return mqtt_request_summary(self)


def mqtt_request_summary(r: MqttRequest) -> dict[str, Any]:
    if not isinstance(r, MqttRequest):
        return {"type": type(r).__name__}
    return {
        "operation": redact_value(r.operation),
        "topic_hash": _hash_stable(r.topic or "") if r.topic else None,
        "topic_filter_hash": _hash_stable(r.topic_filter or "") if r.topic_filter else None,
        "payload_shape": _shape_value(r.payload),
        "qos": r.qos,
        "retain": bool(r.retain),
        "wait": bool(r.wait),
        "receive_timeout_s": r.receive_timeout_s,
        "timeout_s": r.timeout_s,
        "idempotent": r.idempotent,
        "meta": redact_mapping(r.meta),
    }


def mqtt_message_summary(m: MqttMessage) -> dict[str, Any]:
    if not isinstance(m, MqttMessage):
        return {"type": type(m).__name__}
    return {
        "topic_hash": _hash_stable(m.topic or ""),
        "topic_len": len(m.topic or ""),
        "payload_len": len(m.payload or b""),
        "payload_hash": _hash_stable((m.payload or b"")[:256].hex()),
        "qos": m.qos,
        "retain": bool(m.retain),
        "ts": m.ts,
        "meta": redact_mapping(m.meta),
    }


# =============================================================================
# Connector
# =============================================================================


class _PacketId:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._pid = 0

    def next(self) -> int:
        with self._lock:
            self._pid = (self._pid + 1) & 0xFFFF
            if self._pid == 0:
                self._pid = 1
            return self._pid


class MqttProtocolConnector:
    """
    MQTT 3.1.1 ProtocolConnector (stdlib sockets).

    If keep_connection=True, a single socket is maintained with a lock (one request at a time).
    """

    def __init__(self, config: MqttConnectorConfig) -> None:
        self._cfg = config

        host, port, tls = normalize_mqtt_target(config.target)
        self._host = host
        self._port = port
        self._tls = bool(tls or config.force_tls)

        if self._cfg.keep_alive_s < 0 or self._cfg.keep_alive_s > 65535:
            raise ProtocolValidationError(
                "keep_alive_s out of range (0..65535)",
                details={"keep_alive_s": self._cfg.keep_alive_s},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.config.validate"),
            )

        if self._cfg.connect_timeout_s <= 0 or self._cfg.io_timeout_s <= 0:
            raise ProtocolValidationError(
                "timeouts must be > 0",
                details={
                    "connect_timeout_s": self._cfg.connect_timeout_s,
                    "io_timeout_s": self._cfg.io_timeout_s,
                },
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.config.validate"),
            )

        if self._cfg.max_packet_bytes <= 0:
            raise ProtocolValidationError(
                "max_packet_bytes must be > 0",
                details={"max_packet_bytes": self._cfg.max_packet_bytes},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.config.validate"),
            )

        self._client_id = (config.client_id or f"francis-{uuid.uuid4().hex[:12]}").strip()
        if not self._client_id:
            raise ProtocolValidationError(
                "client_id cannot be empty",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.config.validate"),
            )

        self._ssl_context: ssl.SSLContext | None = None
        if self._tls:
            try:
                if self._cfg.verify_tls:
                    self._ssl_context = ssl.create_default_context(cafile=self._cfg.ca_file)
                else:
                    self._ssl_context = ssl._create_unverified_context()  # noqa: SLF001
            except Exception:
                self._ssl_context = None

        self._sock: socket.socket | None = None
        self._sock_lock = threading.RLock()
        self._last_io_ts = 0.0
        self._pid = _PacketId()

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=MQTT_PROTOCOL_ID,
            name="MQTT Connector (stdlib)",
            version=None,
            description="Synchronous MQTT 3.1.1 over TCP/TLS connector using stdlib sockets.",
            capabilities=(
                "request",
                "publish_qos0",
                "subscribe_qos0",
                "ping",
                "health_check",
                "idempotent_retry",
            ),
            meta={
                "target": f"{self._host}:{self._port}",
                "tls": bool(self._tls),
                "clean_session": bool(self._cfg.clean_session),
                "keep_alive_s": int(self._cfg.keep_alive_s),
                "keep_connection": bool(self._cfg.keep_connection),
                "max_packet_bytes": int(self._cfg.max_packet_bytes),
            },
        )

    def _close_socket(self) -> None:
        try:
            if self._sock is not None:
                try:
                    # best-effort DISCONNECT
                    self._sock.sendall(_build_disconnect())
                except Exception:
                    pass
                try:
                    self._sock.close()
                except Exception:
                    pass
        finally:
            self._sock = None
            self._last_io_ts = 0.0

    def _connect_once(self, *, host: str, port: int, tls: bool, timeout_s: float) -> socket.socket:
        s: socket.socket | None = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(float(timeout_s))
            s.connect((host, port))

            if tls:
                ctx = self._ssl_context
                server_hostname = self._cfg.server_hostname or host
                if ctx is None:
                    ctx = ssl.create_default_context()
                s = ctx.wrap_socket(s, server_hostname=server_hostname)

            # set io timeout
            s.settimeout(float(self._cfg.io_timeout_s))

            # Send CONNECT
            pkt = _build_connect_packet(
                client_id=self._client_id,
                keep_alive_s=int(self._cfg.keep_alive_s),
                clean_session=bool(self._cfg.clean_session),
                username=self._cfg.username,
                password=self._cfg.password,
            )
            s.sendall(pkt)

            # Receive CONNACK
            pkt_type, flags, body = _read_packet(s, max_packet_bytes=self._cfg.max_packet_bytes)
            if pkt_type != _PKT_CONNACK:
                raise ProtocolSerializationError(
                    "expected CONNACK",
                    context=ProtocolErrorContext(
                        protocol_id=MQTT_PROTOCOL_ID,
                        operation="mqtt.connect",
                        details={"pkt_type": pkt_type},
                    ),
                    code="expected_connack",
                )
            _ack_flags, rc = _decode_connack(body)
            if rc != 0:
                # Map common reasons
                if rc == 3:
                    raise ProtocolUnavailableError(
                        "mqtt server unavailable",
                        context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.connect"),
                        code="connack_server_unavailable",
                    )
                if rc == 4:
                    raise ProtocolAuthError(
                        "mqtt bad username or password",
                        context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.connect"),
                        code="connack_bad_credentials",
                    )
                if rc == 5:
                    raise ProtocolPermissionError(
                        "mqtt not authorized",
                        context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.connect"),
                        code="connack_not_authorized",
                    )
                raise ProtocolError(
                    "mqtt connection refused",
                    context=ProtocolErrorContext(
                        protocol_id=MQTT_PROTOCOL_ID,
                        operation="mqtt.connect",
                        details={"connack_rc": rc},
                    ),
                    code=f"connack_{rc}",
                )

            self._last_io_ts = time.time()
            return s

        except TimeoutError as exc:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
            raise ProtocolTimeoutError(
                "mqtt connect timed out",
                context=ProtocolErrorContext(
                    protocol_id=MQTT_PROTOCOL_ID,
                    operation="mqtt.connect",
                    details={"host": host, "port": port, "tls": bool(tls)},
                ),
                code="connect_timeout",
                cause=exc,
            ) from exc

        except OSError as exc:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass
            raise ProtocolNetworkError(
                "mqtt connect failed",
                context=ProtocolErrorContext(
                    protocol_id=MQTT_PROTOCOL_ID,
                    operation="mqtt.connect",
                    details={"host": host, "port": port, "tls": bool(tls)},
                ),
                code="connect_error",
                cause=exc,
            ) from exc

    def _ensure_connected(self, *, host: str, port: int, tls: bool, timeout_s: float) -> socket.socket:
        """
        Ensure we have an open socket. Only used when keep_connection=True.
        """
        if self._sock is not None:
            # Best-effort keepalive: if idle longer than keepalive, ping once
            if self._cfg.keep_alive_s and self._last_io_ts:
                idle = time.time() - self._last_io_ts
                if idle > max(1.0, float(self._cfg.keep_alive_s) * 0.75):
                    try:
                        self._sock.sendall(_build_pingreq())
                        pkt_type, _flags, _body = _read_packet(self._sock, max_packet_bytes=self._cfg.max_packet_bytes)
                        if pkt_type != _PKT_PINGRESP:
                            # drop unsafe socket
                            self._close_socket()
                    except Exception:
                        self._close_socket()
            if self._sock is not None:
                return self._sock

        self._sock = self._connect_once(host=host, port=port, tls=tls, timeout_s=timeout_s)
        return self._sock

    def health_check(
        self,
        *,
        endpoint: ProtocolEndpoint | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolHealth:
        """
        Lightweight health check:
          - TCP/TLS connect + CONNECT/CONNACK + PINGREQ/PINGRESP + DISCONNECT.
        """
        host, port, tls = self._host, self._port, self._tls
        if endpoint and (endpoint.uri or endpoint.address):
            try:
                host, port, tls = normalize_mqtt_target(endpoint.uri or endpoint.address)
            except Exception as exc:
                return ProtocolHealth(
                    ok=False,
                    degraded=True,
                    message="invalid endpoint",
                    details={"endpoint": endpoint.redacted_dict(), "error": redact_value(str(exc))},
                )

        tmo = float(timeout_s if timeout_s is not None else self._cfg.connect_timeout_s)
        start = time.time()
        s: socket.socket | None = None
        try:
            s = self._connect_once(host=host, port=port, tls=tls, timeout_s=tmo)
            # ping
            s.sendall(_build_pingreq())
            pkt_type, _flags, _body = _read_packet(s, max_packet_bytes=self._cfg.max_packet_bytes)
            if pkt_type != _PKT_PINGRESP:
                return ProtocolHealth(
                    ok=False,
                    degraded=True,
                    message="unexpected ping response",
                    details={"target": f"{host}:{port}", "tls": bool(tls), "pkt_type": pkt_type},
                )
            # disconnect
            try:
                s.sendall(_build_disconnect())
            except Exception:
                pass
            return ProtocolHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "target": f"{host}:{port}",
                    "tls": bool(tls),
                    "connect_ms": round((time.time() - start) * 1000.0, 3),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={
                    "target": f"{host}:{port}",
                    "tls": bool(tls),
                    "error": redact_value(str(exc)),
                },
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
        Execute a MQTT operation.

        - Returns ProtocolResponse
        - Raises ProtocolTimeoutError / ProtocolNetworkError / ProtocolSerializationError for transport/parse failures
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.request"),
            )

        verb, arg = _parse_operation(req.operation)

        # Allow target override per request
        host, port, tls = self._host, self._port, self._tls
        override_target = False
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            host, port, tls = normalize_mqtt_target(req.endpoint.uri or req.endpoint.address)
            override_target = True

        # Determine idempotency (reads/ping/connect/disconnect are idempotent)
        idempotent_default = verb in ("SUBSCRIBE", "PING", "CONNECT", "DISCONNECT")
        idempotent = bool(req.idempotent) if req.idempotent is not None else bool(idempotent_default)

        # Timeouts
        connect_tmo = float(timeout_s if timeout_s is not None else self._cfg.connect_timeout_s)
        if connect_tmo <= 0:
            raise ProtocolValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": connect_tmo},
                context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.request"),
            )

        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        attempt = 0

        while True:
            try:
                start_ns = time.time_ns()

                # socket selection:
                # - if keep_connection enabled and no override_target, reuse locked socket
                # - otherwise connect per request
                if self._cfg.keep_connection and not override_target:
                    with self._sock_lock:
                        sock = self._ensure_connected(host=host, port=port, tls=tls, timeout_s=connect_tmo)
                        resp = self._handle_verb(sock, verb=verb, arg=arg, req=req)
                else:
                    sock = self._connect_once(host=host, port=port, tls=tls, timeout_s=connect_tmo)
                    try:
                        resp = self._handle_verb(sock, verb=verb, arg=arg, req=req)
                    finally:
                        try:
                            sock.sendall(_build_disconnect())
                        except Exception:
                            pass
                        try:
                            sock.close()
                        except Exception:
                            pass

                duration_ms = (time.time_ns() - start_ns) / 1_000_000.0

                # Enrich stats (safe)
                stats = dict(resp.stats or {})
                stats.update(
                    redact_mapping(
                        {
                            "attempt": attempt,
                            "duration_ms": round(duration_ms, 3),
                            "target": f"{host}:{port}",
                            "tls": bool(tls),
                            "operation": verb,
                        }
                    )
                )

                return ProtocolResponse(
                    protocol_id=MQTT_PROTOCOL_ID,
                    ok=resp.ok,
                    status_code=resp.status_code,
                    headers=resp.headers,
                    payload=resp.payload,
                    stats=stats,
                    ts=resp.ts,
                    meta=redact_mapping(req.meta) if isinstance(req.meta, Mapping) else {},
                )

            except (ProtocolTimeoutError, ProtocolNetworkError, ProtocolSerializationError):
                # Drop persistent socket on errors
                if self._cfg.keep_connection and not override_target:
                    with self._sock_lock:
                        self._close_socket()

                if idempotent:
                    attempt += 1
                    if attempt > max_attempts:
                        raise
                    time.sleep(compute_backoff_s(policy, attempt=attempt))
                    continue
                raise

    def _handle_verb(
        self, sock: socket.socket, *, verb: str, arg: str | None, req: ProtocolRequest
    ) -> ProtocolResponse:
        """
        Handle one MQTT verb on an already-connected socket.
        """
        now_ts = int(time.time())
        meta = req.meta if isinstance(req.meta, Mapping) else {}

        if verb == "CONNECT":
            # Already connected by caller
            return ProtocolResponse(
                protocol_id=MQTT_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping({"connected": True}),
                ts=now_ts,
                meta={},
            )

        if verb == "DISCONNECT":
            try:
                sock.sendall(_build_disconnect())
            finally:
                if self._cfg.keep_connection:
                    # In persistent mode, caller expects socket to be dropped
                    self._close_socket()
            return ProtocolResponse(
                protocol_id=MQTT_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping({"disconnected": True}),
                ts=now_ts,
                meta={},
            )

        if verb == "PING":
            sock.sendall(_build_pingreq())
            pkt_type, _flags, _body = _read_packet(sock, max_packet_bytes=self._cfg.max_packet_bytes)
            self._last_io_ts = time.time()
            if pkt_type != _PKT_PINGRESP:
                return ProtocolResponse(
                    protocol_id=MQTT_PROTOCOL_ID,
                    ok=False,
                    status_code=1,
                    headers={},
                    payload=None,
                    stats=redact_mapping({"expected": "PINGRESP", "got_pkt_type": pkt_type}),
                    ts=now_ts,
                    meta={},
                )
            return ProtocolResponse(
                protocol_id=MQTT_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping({"ping": "ok"}),
                ts=now_ts,
                meta={},
            )

        if verb == "PUBLISH":
            topic = arg or str(meta.get("topic") or "")
            topic = normalize_mqtt_topic(topic)

            qos = int(meta.get("qos", 0))
            if qos not in _SUPPORTED_QOS:
                raise ProtocolUnsupportedError(
                    "only QoS 0 is supported",
                    details={"qos": qos},
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.publish"),
                    code="qos_not_supported",
                )
            retain = bool(meta.get("retain", False))

            payload_bytes = self._coerce_payload_bytes(req.payload, encoding=str(meta.get("encoding", "utf-8")))
            pkt = _build_publish_packet(topic, payload_bytes, retain=retain, qos=qos)
            sock.sendall(pkt)
            self._last_io_ts = time.time()

            return ProtocolResponse(
                protocol_id=MQTT_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=None,
                stats=redact_mapping(
                    {
                        "topic_hash": _hash_stable(topic),
                        "topic_len": len(topic),
                        "payload_len": len(payload_bytes),
                        "retain": bool(retain),
                        "qos": qos,
                    }
                ),
                ts=now_ts,
                meta={},
            )

        if verb == "SUBSCRIBE":
            topic_filter = arg or str(meta.get("topic_filter") or meta.get("topic") or "")
            topic_filter = normalize_mqtt_topic_filter(topic_filter)

            qos = int(meta.get("qos", 0))
            if qos not in _SUPPORTED_QOS:
                raise ProtocolUnsupportedError(
                    "only QoS 0 is supported",
                    details={"qos": qos},
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.subscribe"),
                    code="qos_not_supported",
                )

            wait = bool(meta.get("wait", True))
            receive_timeout_s = meta.get("receive_timeout_s")
            if receive_timeout_s is None:
                receive_timeout_s = req.timeout_s if req.timeout_s is not None else self._cfg.io_timeout_s
            try:
                rx_tmo = float(receive_timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "receive_timeout_s must be numeric",
                    details={"receive_timeout_s": redact_value(str(receive_timeout_s))},
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.subscribe"),
                    cause=exc,
                ) from exc
            if rx_tmo <= 0:
                raise ProtocolValidationError(
                    "receive_timeout_s must be > 0",
                    details={"receive_timeout_s": rx_tmo},
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.subscribe"),
                )

            # Send SUBSCRIBE
            pid = self._pid.next()
            pkt = _build_subscribe_packet(pid, topic_filter, qos=qos)
            sock.sendall(pkt)

            # Expect SUBACK
            pkt_type, _flags, body = _read_packet(sock, max_packet_bytes=self._cfg.max_packet_bytes)
            self._last_io_ts = time.time()
            if pkt_type != _PKT_SUBACK:
                raise ProtocolSerializationError(
                    "expected SUBACK",
                    context=ProtocolErrorContext(
                        protocol_id=MQTT_PROTOCOL_ID,
                        operation="mqtt.subscribe",
                        details={"got_pkt_type": pkt_type},
                    ),
                    code="expected_suback",
                )
            pid_r, codes = _decode_suback(body)
            suback = MqttSubAck(
                packet_id=pid_r,
                return_codes=tuple(codes),
                meta={"topic_filter_hash": _hash_stable(topic_filter)},
            )

            if pid_r != pid:
                raise ProtocolSerializationError(
                    "SUBACK packet id mismatch",
                    context=ProtocolErrorContext(
                        protocol_id=MQTT_PROTOCOL_ID,
                        operation="mqtt.subscribe",
                        details={"expected_pid": pid, "got_pid": pid_r},
                    ),
                    code="suback_pid_mismatch",
                )

            if not suback.ok():
                # 0x80 indicates failure
                return ProtocolResponse(
                    protocol_id=MQTT_PROTOCOL_ID,
                    ok=False,
                    status_code=2,
                    headers={},
                    payload=suback,
                    stats=redact_mapping(
                        {
                            "topic_filter_hash": _hash_stable(topic_filter),
                            "topic_filter_len": len(topic_filter),
                            "packet_id": pid_r,
                            "return_codes": [int(c) for c in codes],
                        }
                    ),
                    ts=now_ts,
                    meta={},
                )

            if not wait:
                return ProtocolResponse(
                    protocol_id=MQTT_PROTOCOL_ID,
                    ok=True,
                    status_code=0,
                    headers={},
                    payload=suback,
                    stats=redact_mapping(
                        {
                            "subscribed": True,
                            "topic_filter_hash": _hash_stable(topic_filter),
                            "topic_filter_len": len(topic_filter),
                            "packet_id": pid_r,
                        }
                    ),
                    ts=now_ts,
                    meta={},
                )

            # Wait for one PUBLISH message
            prev_timeout = sock.gettimeout()
            try:
                sock.settimeout(rx_tmo)
                pkt_type, flags, body = _read_packet(sock, max_packet_bytes=self._cfg.max_packet_bytes)
                self._last_io_ts = time.time()
            finally:
                try:
                    sock.settimeout(prev_timeout)
                except Exception:
                    pass

            if pkt_type != _PKT_PUBLISH:
                return ProtocolResponse(
                    protocol_id=MQTT_PROTOCOL_ID,
                    ok=False,
                    status_code=3,
                    headers={},
                    payload=None,
                    stats=redact_mapping({"expected": "PUBLISH", "got_pkt_type": pkt_type}),
                    ts=now_ts,
                    meta={},
                )

            topic, payload, rx_qos, retain = _decode_publish(flags, body)
            msg = MqttMessage(
                topic=topic,
                payload=payload,
                qos=rx_qos,
                retain=retain,
                ts=now_ts,
                meta={"topic_filter_hash": _hash_stable(topic_filter), "suback_pid": pid_r},
            )

            return ProtocolResponse(
                protocol_id=MQTT_PROTOCOL_ID,
                ok=True,
                status_code=0,
                headers={},
                payload=msg,
                stats=redact_mapping(msg.redacted_dict()),
                ts=now_ts,
                meta={},
            )

        raise ProtocolUnsupportedError(
            "unsupported mqtt operation",
            details={"operation": redact_value(verb)},
            context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.request"),
            code="unsupported_operation",
        )

    def _coerce_payload_bytes(self, payload: Any, *, encoding: str = "utf-8") -> bytes:
        """
        Convert payload into bytes for MQTT publish.

        Rules:
          - None -> b""
          - bytes/bytearray -> bytes
          - str -> encode
          - Mapping/list/tuple -> JSON encode
        """
        if payload is None:
            return b""
        if isinstance(payload, (bytes, bytearray)):
            return bytes(payload)
        if isinstance(payload, str):
            try:
                return payload.encode(encoding, errors="strict")
            except Exception as exc:  # noqa: BLE001
                raise ProtocolSerializationError(
                    "failed to encode string payload",
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.payload.encode"),
                    code="encode_error",
                    cause=exc,
                ) from exc
        if isinstance(payload, (Mapping, list, tuple)):
            try:
                s = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
                return s.encode(encoding, errors="strict")
            except Exception as exc:  # noqa: BLE001
                raise ProtocolSerializationError(
                    "failed to JSON-encode payload",
                    context=ProtocolErrorContext(protocol_id=MQTT_PROTOCOL_ID, operation="mqtt.payload.json_encode"),
                    code="json_encode_error",
                    cause=exc,
                ) from exc

        raise ProtocolSerializationError(
            "unsupported payload type for mqtt publish",
            context=ProtocolErrorContext(
                protocol_id=MQTT_PROTOCOL_ID,
                operation="mqtt.payload.coerce",
                details={"payload_type": type(payload).__name__},
            ),
            code="unsupported_payload",
        )
