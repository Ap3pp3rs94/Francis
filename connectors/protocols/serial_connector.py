"""
===============================================================================
Francis 2.0 — Protocol Connectors (Serial / UART Connector)
Path: connectors/protocols/serial_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides a serial (UART/COM) connector that fits the provider-agnostic
ProtocolConnector contract (connectors/protocols/__init__.py).

Key points:
  - Serial I/O is OS-specific; the practical, stable implementation uses pyserial.
  - This connector therefore requires `pyserial` at runtime to actually talk to ports.
  - The module remains safe-by-default:
      * never logs raw serial payloads
      * never logs decoded text content
      * uses hashes/lengths for observability
      * blocks header/CRLF injection-like patterns in endpoint strings
  - Deterministic behavior:
      * explicit, synchronous request model
      * optional persistent connection (keep_connection) guarded by a lock
      * retries only for idempotent operations

Supported operations (ProtocolRequest.operation or SerialRequest.operation):
  - "WRITE"
  - "READ"
  - "EXCHANGE"   (write then read)
  - "FLUSH"      (reset input/output buffers)
  - "OPEN"       (open connection)
  - "CLOSE"      (close connection)

Endpoint formats:
  - address: "COM3" or "/dev/ttyUSB0"
  - uri:     "serial://COM3?baud=115200&parity=N&stopbits=1&bytesize=8&timeout=1&write_timeout=1"
             "serial:///dev/ttyUSB0?baud=9600"

Payload mapping:
  - bytes/bytearray -> sent as-is
  - str -> encoded using encoding (default utf-8)
  - Mapping/list/tuple -> JSON-encoded (utf-8) for convenience

Read behavior:
  - specify one of:
      * read_len (exact length attempt)
      * read_until (terminator bytes/str)
  - if neither provided, reads up to max_read_bytes once (may return empty on timeout)

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlsplit

from . import (
    ProtocolBackoffPolicy,
    ProtocolConnectorInfo,
    ProtocolEndpoint,
    ProtocolErrorContext,
    ProtocolHealth,
    ProtocolIdentity,
    ProtocolNetworkError,
    ProtocolRequest,
    ProtocolResponse,
    ProtocolSerializationError,
    ProtocolTimeoutError,
    ProtocolUnsupportedError,
    ProtocolValidationError,
    compute_backoff_s,
    redact_mapping,
    redact_value,
)

# Optional runtime dependency
try:
    import serial  # type: ignore
except Exception:  # pragma: no cover
    serial = None  # type: ignore

__all__ = [
    "SERIAL_PROTOCOL_ID",
    "SerialConnectorConfig",
    "SerialRequest",
    "SerialResponse",
    "SerialProtocolConnector",
    "normalize_serial_port",
    "parse_serial_endpoint",
    "serial_request_summary",
    "serial_response_summary",
]

SERIAL_PROTOCOL_ID = "serial"

_ALLOWED_OPS = {"WRITE", "READ", "EXCHANGE", "FLUSH", "OPEN", "CLOSE"}


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
# Endpoint parsing / normalization
# =============================================================================


def normalize_serial_port(port: str) -> str:
    """
    Normalize and validate a serial port identifier.

    Accepts:
      - Windows: "COM3"
      - POSIX: "/dev/ttyUSB0"
      - Named ports like "ttyS0"

    Safety:
      - rejects NUL/CR/LF
      - strips whitespace
    """
    p = (port or "").strip()
    if not p:
        raise ProtocolValidationError(
            "serial port is required",
            details={"field": "port"},
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.normalize_port"),
        )
    if "\x00" in p or "\r" in p or "\n" in p:
        raise ProtocolValidationError(
            "serial port contains illegal control characters",
            details={"port": redact_value(p)},
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.normalize_port"),
        )
    if len(p) > 256:
        raise ProtocolValidationError(
            "serial port too long",
            details={"len": len(p), "max": 256},
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.normalize_port"),
        )
    return p


def _qfirst(qs: Mapping[str, list[str]], key: str) -> str | None:
    v = qs.get(key)
    if not v:
        return None
    s = (v[0] or "").strip()
    return s if s else None


def parse_serial_endpoint(endpoint: ProtocolEndpoint | None, *, fallback_port: str) -> dict[str, Any]:
    """
    Parse a ProtocolEndpoint into serial config overrides.

    Returns dict with optional keys:
      - port, baud, bytesize, parity, stopbits, timeout, write_timeout,
        xonxoff, rtscts, dsrdtr
    """
    if endpoint is None or not (endpoint.uri or endpoint.address):
        return {"port": normalize_serial_port(fallback_port)}

    raw = (endpoint.uri or endpoint.address or "").strip()
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "serial endpoint contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.parse_endpoint"),
        )

    # URI form: serial://COM3?... or serial:///dev/ttyUSB0?...
    if "://" in raw:
        p = urlsplit(raw)
        scheme = (p.scheme or "").lower()
        if scheme not in ("serial", "uart", "com"):
            raise ProtocolValidationError(
                "unsupported serial endpoint scheme",
                details={"scheme": redact_value(scheme)},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.parse_endpoint"),
            )

        # Port can be in netloc (serial://COM3) or path (serial:///dev/ttyUSB0)
        port = (p.netloc or "").strip()
        if not port:
            port = (p.path or "").lstrip("/").strip()

        port = normalize_serial_port(port or fallback_port)

        qs = parse_qs(p.query or "", keep_blank_values=False)

        out: dict[str, Any] = {"port": port}

        def as_int(name: str) -> int | None:
            s = _qfirst(qs, name)
            if s is None:
                return None
            try:
                return int(s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    f"invalid int for {name}",
                    details={name: redact_value(s)},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.parse_endpoint"),
                    cause=exc,
                ) from exc

        def as_float(name: str) -> float | None:
            s = _qfirst(qs, name)
            if s is None:
                return None
            try:
                return float(s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    f"invalid float for {name}",
                    details={name: redact_value(s)},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.parse_endpoint"),
                    cause=exc,
                ) from exc

        def as_bool(name: str) -> bool | None:
            s = _qfirst(qs, name)
            if s is None:
                return None
            sl = s.lower()
            if sl in ("1", "true", "yes", "y", "on"):
                return True
            if sl in ("0", "false", "no", "n", "off"):
                return False
            raise ProtocolValidationError(
                f"invalid bool for {name}",
                details={name: redact_value(s)},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.parse_endpoint"),
            )

        # Common serial params
        out["baud"] = as_int("baud") or as_int("baudrate")
        out["bytesize"] = as_int("bytesize")
        out["parity"] = _qfirst(qs, "parity")
        out["stopbits"] = as_float("stopbits")
        out["timeout"] = as_float("timeout")  # read timeout
        out["write_timeout"] = as_float("write_timeout")

        out["xonxoff"] = as_bool("xonxoff")
        out["rtscts"] = as_bool("rtscts")
        out["dsrdtr"] = as_bool("dsrdtr")

        # Remove None keys
        return {k: v for k, v in out.items() if v is not None}

    # Address form: "COM3" or "/dev/ttyUSB0"
    return {"port": normalize_serial_port(raw)}


# =============================================================================
# Config / typed request / typed response
# =============================================================================


@dataclass(frozen=True, slots=True)
class SerialConnectorConfig:
    """
    Configuration for SerialProtocolConnector.

    Requires pyserial at runtime to function.
    """

    port: str
    baudrate: int = 9600
    bytesize: int = 8  # 5..8 typically
    parity: str = "N"  # N/E/O/M/S
    stopbits: float = 1.0  # 1, 1.5, 2

    # Flow control
    xonxoff: bool = False
    rtscts: bool = False
    dsrdtr: bool = False

    # Timeouts (seconds)
    read_timeout_s: float = 1.0
    write_timeout_s: float = 1.0
    open_timeout_s: float = 3.0

    # Limits
    max_read_bytes: int = 1024 * 1024
    max_write_bytes: int = 1024 * 1024

    # Connection behavior
    keep_connection: bool = False

    # Retry policy (only for idempotent operations)
    backoff_policy: ProtocolBackoffPolicy = field(default_factory=ProtocolBackoffPolicy)

    def __post_init__(self) -> None:
        p = normalize_serial_port(self.port)
        object.__setattr__(self, "port", p)

        if self.baudrate <= 0:
            raise ProtocolValidationError(
                "baudrate must be > 0",
                details={"baudrate": self.baudrate},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
            )
        if self.bytesize not in (5, 6, 7, 8):
            raise ProtocolValidationError(
                "bytesize must be one of 5,6,7,8",
                details={"bytesize": self.bytesize},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
            )
        par = (self.parity or "").upper()
        if par not in ("N", "E", "O", "M", "S"):
            raise ProtocolValidationError(
                "parity must be one of N,E,O,M,S",
                details={"parity": redact_value(par)},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
            )
        object.__setattr__(self, "parity", par)

        if self.stopbits not in (1, 1.0, 1.5, 2, 2.0):
            raise ProtocolValidationError(
                "stopbits must be 1, 1.5, or 2",
                details={"stopbits": self.stopbits},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
            )

        for name in ("read_timeout_s", "write_timeout_s", "open_timeout_s"):
            v = float(getattr(self, name))
            if v <= 0:
                raise ProtocolValidationError(
                    f"{name} must be > 0",
                    details={name: v},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
                )

        if self.max_read_bytes <= 0 or self.max_write_bytes <= 0:
            raise ProtocolValidationError(
                "max_read_bytes and max_write_bytes must be > 0",
                details={
                    "max_read_bytes": self.max_read_bytes,
                    "max_write_bytes": self.max_write_bytes,
                },
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class SerialRequest:
    """
    A typed serial request.

    SAFETY:
      - data/read_until suppressed from repr()
      - use redacted_dict()/serial_request_summary() for logs
    """

    operation: str  # WRITE/READ/EXCHANGE/FLUSH/OPEN/CLOSE

    data: Any = field(default=None, repr=False)

    read_len: int | None = None
    read_until: bytes | str | None = field(default=None, repr=False)

    # Optional encoding for str payloads and for read_until if given as str
    encoding: str = "utf-8"

    # Overrides
    timeout_s: float | None = None
    idempotent: bool | None = None

    # Hints
    strip_terminator: bool = False

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        op = (self.operation or "").strip().upper()
        if op not in _ALLOWED_OPS:
            raise ProtocolValidationError(
                "unsupported serial operation",
                details={"operation": redact_value(op), "allowed": sorted(_ALLOWED_OPS)},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request.validate"),
            )
        object.__setattr__(self, "operation", op)

        if self.read_len is not None:
            try:
                rl = int(self.read_len)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "read_len must be an integer",
                    details={"read_len": redact_value(str(self.read_len))},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request.validate"),
                    cause=exc,
                ) from exc
            if rl <= 0:
                raise ProtocolValidationError(
                    "read_len must be > 0",
                    details={"read_len": rl},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request.validate"),
                )
            object.__setattr__(self, "read_len", rl)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request.validate"),
                    cause=exc,
                ) from exc
            if ts <= 0:
                raise ProtocolValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

        if self.idempotent is None:
            # Conservative default: reads/flush/open/close are idempotent
            object.__setattr__(self, "idempotent", op in ("READ", "FLUSH", "OPEN", "CLOSE"))

    def fingerprint(self, *, salt: str = "francis") -> str:
        # Do not include raw data; include shapes only.
        until_shape = _shape_value(
            self.read_until
            if isinstance(self.read_until, (bytes, bytearray))
            else (str(self.read_until) if self.read_until is not None else None)
        )
        payload = {
            "op": self.operation,
            "data_shape": _shape_value(self.data),
            "read_len": self.read_len,
            "read_until_shape": until_shape,
            "encoding": self.encoding,
            "timeout_s": self.timeout_s,
            "idempotent": bool(self.idempotent),
            "strip_terminator": bool(self.strip_terminator),
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return _hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return serial_request_summary(self)


@dataclass(frozen=True, slots=True)
class SerialResponse:
    """
    Typed serial response.

    SAFETY:
      - data suppressed from repr()
      - summaries never include raw bytes
    """

    request_fingerprint: str
    operation: str

    ok: bool
    bytes_written: int = 0
    bytes_read: int = 0

    data: bytes = field(default=b"", repr=False)

    duration_ms: float | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def redacted_dict(self) -> dict[str, Any]:
        return serial_response_summary(self)


def serial_request_summary(r: SerialRequest) -> dict[str, Any]:
    if not isinstance(r, SerialRequest):
        return {"type": type(r).__name__}
    until = r.read_until
    until_shape = _shape_value(
        until if isinstance(until, (bytes, bytearray)) else (str(until) if until is not None else None)
    )
    return {
        "operation": r.operation,
        "fingerprint": r.fingerprint(),
        "data_shape": _shape_value(r.data),
        "read_len": r.read_len,
        "read_until_shape": until_shape,
        "encoding": redact_value(r.encoding),
        "timeout_s": r.timeout_s,
        "idempotent": bool(r.idempotent),
        "strip_terminator": bool(r.strip_terminator),
        "meta": redact_mapping(r.meta),
    }


def serial_response_summary(r: SerialResponse) -> dict[str, Any]:
    if not isinstance(r, SerialResponse):
        return {"type": type(r).__name__}
    b = r.data or b""
    return {
        "request_fingerprint": r.request_fingerprint,
        "operation": r.operation,
        "ok": bool(r.ok),
        "bytes_written": int(r.bytes_written),
        "bytes_read": int(r.bytes_read),
        "data_len": len(b),
        "data_hash": _hash_stable(b[:256].hex()),
        "duration_ms": r.duration_ms,
        "meta": redact_mapping(r.meta),
    }


# =============================================================================
# Connector implementation (pyserial)
# =============================================================================


def _require_pyserial() -> None:
    if serial is None:
        raise ProtocolUnsupportedError(
            "pyserial is required for SerialProtocolConnector (pip install pyserial)",
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.require_pyserial"),
            code="pyserial_missing",
        )


def _normalize_operation(op: str) -> str:
    s = (op or "").strip().upper()
    if not s:
        raise ProtocolValidationError(
            "operation is required",
            details={"field": "operation"},
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.normalize_operation"),
        )
    if s not in _ALLOWED_OPS:
        raise ProtocolValidationError(
            "unsupported serial operation",
            details={"operation": redact_value(s), "allowed": sorted(_ALLOWED_OPS)},
            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.normalize_operation"),
        )
    return s


def _coerce_bytes(payload: Any, *, encoding: str = "utf-8") -> bytes:
    """
    Convert payload to bytes for serial write.

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
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.payload.encode"),
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
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.payload.json_encode"),
                code="json_encode_error",
                cause=exc,
            ) from exc
    raise ProtocolSerializationError(
        "unsupported payload type for serial write",
        context=ProtocolErrorContext(
            protocol_id=SERIAL_PROTOCOL_ID,
            operation="serial.payload.coerce",
            details={"payload_type": type(payload).__name__},
        ),
        code="unsupported_payload",
    )


class SerialProtocolConnector:
    """
    Serial/UART connector using pyserial.

    - keep_connection=False (default): open -> operate -> close per request (safer).
    - keep_connection=True: maintain a single open port guarded by a lock.
    """

    def __init__(self, config: SerialConnectorConfig) -> None:
        _require_pyserial()
        self._cfg = config

        self._lock = threading.RLock()
        self._ser = None  # serial.Serial instance (runtime type)

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=SERIAL_PROTOCOL_ID,
            name="Serial Connector",
            version=None,
            description="Synchronous serial/COM connector (pyserial-backed).",
            capabilities=(
                "request",
                "write",
                "read",
                "exchange",
                "flush",
                "open",
                "close",
                "idempotent_retry",
            ),
            meta={
                "port": self._cfg.port,
                "baudrate": int(self._cfg.baudrate),
                "bytesize": int(self._cfg.bytesize),
                "parity": self._cfg.parity,
                "stopbits": float(self._cfg.stopbits),
                "keep_connection": bool(self._cfg.keep_connection),
                "max_read_bytes": int(self._cfg.max_read_bytes),
                "max_write_bytes": int(self._cfg.max_write_bytes),
            },
        )

    def health_check(
        self,
        *,
        endpoint: ProtocolEndpoint | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolHealth:
        """
        Lightweight health check: open then close.

        No data is transmitted.
        """
        _require_pyserial()

        overrides = parse_serial_endpoint(endpoint, fallback_port=self._cfg.port)
        port = overrides.get("port", self._cfg.port)

        start = time.time()
        s = None
        try:
            s = serial.Serial(
                port=port,
                baudrate=int(overrides.get("baud", overrides.get("baudrate", self._cfg.baudrate))),
                bytesize=int(overrides.get("bytesize", self._cfg.bytesize)),
                parity=str(overrides.get("parity", self._cfg.parity)),
                stopbits=float(overrides.get("stopbits", self._cfg.stopbits)),
                timeout=float(overrides.get("timeout", self._cfg.read_timeout_s)),
                write_timeout=float(overrides.get("write_timeout", self._cfg.write_timeout_s)),
                xonxoff=bool(overrides.get("xonxoff", self._cfg.xonxoff)),
                rtscts=bool(overrides.get("rtscts", self._cfg.rtscts)),
                dsrdtr=bool(overrides.get("dsrdtr", self._cfg.dsrdtr)),
            )
            # pyserial opens immediately by default
            ok = bool(getattr(s, "is_open", True))
            return ProtocolHealth(
                ok=ok,
                degraded=False if ok else True,
                message="ok" if ok else "failed",
                details={
                    "port": port,
                    "open_ms": round((time.time() - start) * 1000.0, 3),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={
                    "port": port,
                    "error": redact_value(str(exc)),
                },
            )
        finally:
            try:
                if s is not None:
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
        Execute a serial operation.

        Payload can be:
          - SerialRequest
          - bytes/str/mapping/etc (interpreted based on operation)
          - None

        For READ/EXCHANGE, read controls can be provided via:
          - SerialRequest.read_len / read_until
          - req.meta["read_len"] / req.meta["read_until"]
          - req.meta["strip_terminator"]
          - req.meta["encoding"]
        """
        _require_pyserial()

        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request"),
            )

        # Resolve per-request endpoint overrides
        overrides = parse_serial_endpoint(req.endpoint, fallback_port=self._cfg.port)
        port = str(overrides.get("port", self._cfg.port))

        # Determine operation + typed request
        if isinstance(req.payload, SerialRequest):
            sreq = req.payload
            op = sreq.operation
        else:
            op = _normalize_operation(req.operation)
            sreq = SerialRequest(
                operation=op,
                data=req.payload,
                read_len=(req.meta.get("read_len") if isinstance(req.meta, Mapping) else None),
                read_until=(req.meta.get("read_until") if isinstance(req.meta, Mapping) else None),
                encoding=str(req.meta.get("encoding", "utf-8")) if isinstance(req.meta, Mapping) else "utf-8",
                timeout_s=req.timeout_s,
                idempotent=req.idempotent,
                strip_terminator=bool(req.meta.get("strip_terminator", False))
                if isinstance(req.meta, Mapping)
                else False,
                meta={"from_protocol_request": True},
            )

        # Determine idempotency
        idempotent = bool(req.idempotent) if req.idempotent is not None else bool(sreq.idempotent)

        # Determine timeout
        effective_timeout = float(
            timeout_s
            if timeout_s is not None
            else (sreq.timeout_s if sreq.timeout_s is not None else self._cfg.read_timeout_s)
        )
        if effective_timeout <= 0:
            raise ProtocolValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": effective_timeout},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.request"),
            )

        # Retry loop (idempotent only)
        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        attempt = 0

        while True:
            try:
                start_ns = time.time_ns()
                if self._cfg.keep_connection:
                    with self._lock:
                        ser = self._ensure_open(port=port, overrides=overrides)
                        sresp = self._execute_once(ser, sreq, overrides=overrides, timeout_s=effective_timeout)
                else:
                    ser = self._open_once(port=port, overrides=overrides)
                    try:
                        sresp = self._execute_once(ser, sreq, overrides=overrides, timeout_s=effective_timeout)
                    finally:
                        try:
                            ser.close()
                        except Exception:
                            pass

                duration_ms = (time.time_ns() - start_ns) / 1_000_000.0
                sresp = SerialResponse(
                    request_fingerprint=sresp.request_fingerprint,
                    operation=sresp.operation,
                    ok=sresp.ok,
                    bytes_written=sresp.bytes_written,
                    bytes_read=sresp.bytes_read,
                    data=sresp.data,
                    duration_ms=round(duration_ms, 3),
                    meta=sresp.meta,
                )

                return ProtocolResponse(
                    protocol_id=SERIAL_PROTOCOL_ID,
                    ok=bool(sresp.ok),
                    status_code=0 if sresp.ok else 1,
                    headers={},  # serial has no headers
                    payload=sresp,
                    stats=redact_mapping(
                        {
                            "port": port,
                            "operation": sresp.operation,
                            "attempt": attempt,
                            "bytes_written": sresp.bytes_written,
                            "bytes_read": sresp.bytes_read,
                            "data_len": len(sresp.data or b""),
                            "data_hash": _hash_stable((sresp.data or b"")[:256].hex()),
                            "duration_ms": sresp.duration_ms,
                        }
                    ),
                    ts=int(time.time()),
                    meta=redact_mapping(req.meta) if isinstance(req.meta, Mapping) else {},
                )

            except (ProtocolTimeoutError, ProtocolNetworkError, ProtocolSerializationError):
                # If persistent, drop port on failure (safer than keeping a wedged handle).
                if self._cfg.keep_connection:
                    with self._lock:
                        self._close_current()

                if idempotent:
                    attempt += 1
                    if attempt > max_attempts:
                        raise
                    time.sleep(compute_backoff_s(policy, attempt=attempt))
                    continue
                raise

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    def _open_once(self, *, port: str, overrides: Mapping[str, Any]) -> Any:
        try:
            return serial.Serial(
                port=port,
                baudrate=int(overrides.get("baud", overrides.get("baudrate", self._cfg.baudrate))),
                bytesize=int(overrides.get("bytesize", self._cfg.bytesize)),
                parity=str(overrides.get("parity", self._cfg.parity)),
                stopbits=float(overrides.get("stopbits", self._cfg.stopbits)),
                timeout=float(overrides.get("timeout", self._cfg.read_timeout_s)),
                write_timeout=float(overrides.get("write_timeout", self._cfg.write_timeout_s)),
                xonxoff=bool(overrides.get("xonxoff", self._cfg.xonxoff)),
                rtscts=bool(overrides.get("rtscts", self._cfg.rtscts)),
                dsrdtr=bool(overrides.get("dsrdtr", self._cfg.dsrdtr)),
            )
        except Exception as exc:  # noqa: BLE001
            raise ProtocolNetworkError(
                "failed to open serial port",
                context=ProtocolErrorContext(
                    protocol_id=SERIAL_PROTOCOL_ID,
                    operation="serial.open",
                    details={"port": port},
                ),
                code="open_failed",
                cause=exc,
            ) from exc

    def _ensure_open(self, *, port: str, overrides: Mapping[str, Any]) -> Any:
        """
        Ensure persistent serial port is open with current target.
        If port differs from existing, close and reopen.
        """
        if self._ser is not None:
            try:
                # if different port or not open -> reopen
                cur_port = getattr(self._ser, "port", None)
                is_open = bool(getattr(self._ser, "is_open", True))
                if cur_port == port and is_open:
                    return self._ser
            except Exception:
                self._close_current()

        self._ser = self._open_once(port=port, overrides=overrides)
        return self._ser

    def _close_current(self) -> None:
        try:
            if self._ser is not None:
                try:
                    self._ser.close()
                except Exception:
                    pass
        finally:
            self._ser = None

    def _execute_once(
        self, ser: Any, sreq: SerialRequest, *, overrides: Mapping[str, Any], timeout_s: float
    ) -> SerialResponse:
        """
        Execute one SerialRequest against an open serial port instance.
        """
        op = sreq.operation
        fp = sreq.fingerprint()

        # Apply per-request timeouts (read/write) if provided via overrides/meta
        # We keep this minimal: set read timeout temporarily.
        prev_timeout = None
        prev_write_timeout = None
        try:
            prev_timeout = getattr(ser, "timeout", None)
            prev_write_timeout = getattr(ser, "write_timeout", None)
            ser.timeout = float(overrides.get("timeout", timeout_s))
            ser.write_timeout = float(overrides.get("write_timeout", self._cfg.write_timeout_s))
        except Exception:
            # If setting attributes fails, continue; pyserial typically supports these.
            pass

        try:
            if op == "OPEN":
                # already open by virtue of ser existing
                return SerialResponse(request_fingerprint=fp, operation=op, ok=True, meta={"open": True})

            if op == "CLOSE":
                try:
                    ser.close()
                except Exception as exc:  # noqa: BLE001
                    raise ProtocolNetworkError(
                        "failed to close serial port",
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.close"),
                        code="close_failed",
                        cause=exc,
                    ) from exc
                # If persistent, drop handle
                if self._cfg.keep_connection:
                    self._ser = None
                return SerialResponse(request_fingerprint=fp, operation=op, ok=True, meta={"closed": True})

            if op == "FLUSH":
                # reset buffers
                try:
                    if hasattr(ser, "reset_input_buffer"):
                        ser.reset_input_buffer()
                    if hasattr(ser, "reset_output_buffer"):
                        ser.reset_output_buffer()
                except Exception as exc:  # noqa: BLE001
                    raise ProtocolNetworkError(
                        "failed to flush serial buffers",
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.flush"),
                        code="flush_failed",
                        cause=exc,
                    ) from exc
                return SerialResponse(request_fingerprint=fp, operation=op, ok=True, meta={"flushed": True})

            if op == "WRITE":
                data = _coerce_bytes(sreq.data, encoding=sreq.encoding)
                if len(data) > self._cfg.max_write_bytes:
                    raise ProtocolValidationError(
                        "write payload exceeds max_write_bytes",
                        details={"len": len(data), "max_write_bytes": self._cfg.max_write_bytes},
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.write"),
                    )
                try:
                    n = int(ser.write(data))
                    # best-effort flush
                    if hasattr(ser, "flush"):
                        ser.flush()
                except Exception as exc:  # noqa: BLE001
                    # pyserial uses SerialTimeoutException for write timeouts
                    if (
                        serial is not None
                        and getattr(serial, "SerialTimeoutException", None)
                        and isinstance(exc, serial.SerialTimeoutException)
                    ):  # type: ignore[attr-defined]
                        raise ProtocolTimeoutError(
                            "serial write timed out",
                            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.write"),
                            code="write_timeout",
                            cause=exc,
                        ) from exc
                    raise ProtocolNetworkError(
                        "serial write failed",
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.write"),
                        code="write_failed",
                        cause=exc,
                    ) from exc
                return SerialResponse(
                    request_fingerprint=fp,
                    operation=op,
                    ok=True,
                    bytes_written=n,
                    meta={"payload_len": len(data), "payload_hash": _hash_stable(data[:256].hex())},
                )

            if op == "READ":
                data = self._read_data(ser, sreq, timeout_s=timeout_s)
                ok = True
                # If caller specified a condition (len/until) and got empty -> mark not ok (but do not raise)
                if (sreq.read_len is not None or sreq.read_until is not None) and not data:
                    ok = False
                return SerialResponse(
                    request_fingerprint=fp,
                    operation=op,
                    ok=ok,
                    bytes_read=len(data),
                    data=data,
                    meta={
                        "read_len": sreq.read_len,
                        "read_until": _shape_value(sreq.read_until),
                        "empty": not data,
                    },
                )

            if op == "EXCHANGE":
                # write then read
                outb = _coerce_bytes(sreq.data, encoding=sreq.encoding)
                if len(outb) > self._cfg.max_write_bytes:
                    raise ProtocolValidationError(
                        "write payload exceeds max_write_bytes",
                        details={"len": len(outb), "max_write_bytes": self._cfg.max_write_bytes},
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.exchange"),
                    )
                try:
                    n = int(ser.write(outb))
                    if hasattr(ser, "flush"):
                        ser.flush()
                except Exception as exc:  # noqa: BLE001
                    if (
                        serial is not None
                        and getattr(serial, "SerialTimeoutException", None)
                        and isinstance(exc, serial.SerialTimeoutException)
                    ):  # type: ignore[attr-defined]
                        raise ProtocolTimeoutError(
                            "serial exchange write timed out",
                            context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.exchange"),
                            code="write_timeout",
                            cause=exc,
                        ) from exc
                    raise ProtocolNetworkError(
                        "serial exchange write failed",
                        context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.exchange"),
                        code="write_failed",
                        cause=exc,
                    ) from exc

                data = self._read_data(ser, sreq, timeout_s=timeout_s)
                ok = True
                if (sreq.read_len is not None or sreq.read_until is not None) and not data:
                    ok = False

                return SerialResponse(
                    request_fingerprint=fp,
                    operation=op,
                    ok=ok,
                    bytes_written=n,
                    bytes_read=len(data),
                    data=data,
                    meta={
                        "tx_len": len(outb),
                        "tx_hash": _hash_stable(outb[:256].hex()),
                        "rx_len": len(data),
                        "rx_hash": _hash_stable(data[:256].hex()),
                        "read_len": sreq.read_len,
                        "read_until": _shape_value(sreq.read_until),
                        "empty": not data,
                    },
                )

            raise ProtocolUnsupportedError(
                "unsupported serial operation",
                details={"operation": redact_value(op)},
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.execute"),
                code="unsupported_operation",
            )

        finally:
            # Restore previous timeouts
            try:
                if prev_timeout is not None:
                    ser.timeout = prev_timeout
                if prev_write_timeout is not None:
                    ser.write_timeout = prev_write_timeout
            except Exception:
                pass

    def _read_data(self, ser: Any, sreq: SerialRequest, *, timeout_s: float) -> bytes:
        """
        Read bytes according to sreq.read_len or sreq.read_until or default.
        """
        max_read = int(self._cfg.max_read_bytes)

        # Determine terminator if provided
        terminator: bytes | None = None
        if sreq.read_until is not None:
            if isinstance(sreq.read_until, (bytes, bytearray)):
                terminator = bytes(sreq.read_until)
            else:
                terminator = str(sreq.read_until).encode(sreq.encoding, errors="strict")
            if not terminator:
                raise ProtocolValidationError(
                    "read_until cannot be empty",
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read"),
                )
            if len(terminator) > 64:
                raise ProtocolValidationError(
                    "read_until too long (conservative limit 64 bytes)",
                    details={"len": len(terminator), "max": 64},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read"),
                )

        if sreq.read_len is not None:
            rl = int(sreq.read_len)
            if rl > max_read:
                raise ProtocolValidationError(
                    "read_len exceeds max_read_bytes",
                    details={"read_len": rl, "max_read_bytes": max_read},
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read"),
                )
            try:
                data = bytes(ser.read(rl))
            except Exception as exc:  # noqa: BLE001
                raise ProtocolNetworkError(
                    "serial read failed",
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read"),
                    code="read_failed",
                    cause=exc,
                ) from exc
            return data

        if terminator is not None:
            # Prefer pyserial's read_until when available
            try:
                if hasattr(ser, "read_until"):
                    data = bytes(ser.read_until(terminator, size=max_read))
                else:
                    # Fallback: manual loop
                    data_b = bytearray()
                    deadline = time.time() + float(timeout_s)
                    while time.time() < deadline and len(data_b) < max_read:
                        chunk = ser.read(1)
                        if not chunk:
                            continue
                        data_b.extend(chunk)
                        if data_b.endswith(terminator):
                            break
                    data = bytes(data_b)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolNetworkError(
                    "serial read_until failed",
                    context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read_until"),
                    code="read_until_failed",
                    cause=exc,
                ) from exc

            if sreq.strip_terminator and data.endswith(terminator):
                return data[: -len(terminator)]
            return data

        # Default: read up to max_read once (may return empty on timeout)
        try:
            data = bytes(ser.read(max_read))
        except Exception as exc:  # noqa: BLE001
            raise ProtocolNetworkError(
                "serial read failed",
                context=ProtocolErrorContext(protocol_id=SERIAL_PROTOCOL_ID, operation="serial.read"),
                code="read_failed",
                cause=exc,
            ) from exc
        return data
