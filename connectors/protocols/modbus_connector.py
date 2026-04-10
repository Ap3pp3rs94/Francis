"""
===============================================================================
Francis 2.0 — Protocol Connectors (Modbus TCP Connector)
Path: connectors/protocols/modbus_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a synchronous Modbus TCP connector using ONLY the Python
standard library (socket). It fits into the provider-agnostic ProtocolConnector
contract in connectors/protocols/__init__.py.

Scope:
  - Modbus TCP (MBAP header, port 502 by default)
  - Common function codes:
      * 01 Read Coils
      * 02 Read Discrete Inputs
      * 03 Read Holding Registers
      * 04 Read Input Registers
      * 05 Write Single Coil
      * 06 Write Single Register
      * 0F Write Multiple Coils
      * 10 Write Multiple Registers
  - Safe-by-default observability:
      * never logs raw frames
      * never logs raw register/coil values (summaries only)
      * request/response fingerprinting

Out of scope (intentionally):
  - Modbus RTU framing (CRC) and serial port I/O (requires non-stdlib dependencies)
  - Streaming call types or long-lived subscriptions
  - Full device modeling / register maps / scaling / endianness interpretation
  - Async support

SAFETY & OBSERVABILITY NOTES
----------------------------
- Modbus values (registers/coils) can represent sensitive or safety-critical states.
  This connector never logs raw values; it only logs shapes + hashes.
- Default retry behavior:
    * retries only for idempotent operations (reads)
    * retries only on transport/timeouts and transient response issues
  Writes are NOT retried by default unless the caller explicitly marks the request
  idempotent (use with care).

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import socket
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit

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

__all__ = [
    "MODBUS_PROTOCOL_ID",
    "MODBUS_TCP_DEFAULT_PORT",
    "ModbusTcpConfig",
    "ModbusRequest",
    "ModbusResponse",
    "ModbusProtocolConnector",
    # Helpers
    "normalize_modbus_target",
    "normalize_unit_id",
    "normalize_address",
    "normalize_quantity",
    "modbus_request_summary",
    "modbus_response_summary",
]


MODBUS_PROTOCOL_ID = "modbus"
MODBUS_TCP_DEFAULT_PORT = 502

# Function codes
FC_READ_COILS = 0x01
FC_READ_DISCRETE_INPUTS = 0x02
FC_READ_HOLDING_REGISTERS = 0x03
FC_READ_INPUT_REGISTERS = 0x04
FC_WRITE_SINGLE_COIL = 0x05
FC_WRITE_SINGLE_REGISTER = 0x06
FC_WRITE_MULTIPLE_COILS = 0x0F
FC_WRITE_MULTIPLE_REGISTERS = 0x10

_READ_FUNCTIONS = {
    FC_READ_COILS,
    FC_READ_DISCRETE_INPUTS,
    FC_READ_HOLDING_REGISTERS,
    FC_READ_INPUT_REGISTERS,
}
_WRITE_FUNCTIONS = {
    FC_WRITE_SINGLE_COIL,
    FC_WRITE_SINGLE_REGISTER,
    FC_WRITE_MULTIPLE_COILS,
    FC_WRITE_MULTIPLE_REGISTERS,
}

# Conservative bounds (typical spec / common device limits)
_MAX_COILS_PER_READ = 2000
_MAX_REGS_PER_READ = 125
_MAX_REGS_PER_WRITE = 123  # typical for FC16 (bytes limit 246)
_MAX_COILS_PER_WRITE = 1968  # typical for FC15 (bytes limit 246*8)

# Retryable "device exception codes" are rare; most exception responses are not retryable.
# We'll treat any Modbus exception as non-retryable by default and return ok=False.


# =============================================================================
# Small log-safe hashing/shapes
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


def normalize_unit_id(unit_id: int | str | None) -> int:
    """
    Normalize Modbus unit id (0..255).
    """
    if unit_id is None:
        return 1
    try:
        u = int(unit_id)
    except Exception as exc:  # noqa: BLE001
        raise ProtocolValidationError(
            "unit_id must be an integer",
            details={"unit_id": redact_value(str(unit_id))},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_unit_id"),
            cause=exc,
        ) from exc
    if not (0 <= u <= 255):
        raise ProtocolValidationError(
            "unit_id out of range (0..255)",
            details={"unit_id": u},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_unit_id"),
        )
    return u


def normalize_address(address: int | str, *, one_based: bool = False) -> int:
    """
    Normalize a Modbus address (0..65535).

    If one_based=True, subtract 1 (common UI convention).
    """
    try:
        a = int(address)
    except Exception as exc:  # noqa: BLE001
        raise ProtocolValidationError(
            "address must be an integer",
            details={"address": redact_value(str(address))},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_address"),
            cause=exc,
        ) from exc

    if one_based:
        a = a - 1

    if not (0 <= a <= 0xFFFF):
        raise ProtocolValidationError(
            "address out of range (0..65535)",
            details={"address": a},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_address"),
        )
    return a


def normalize_quantity(quantity: int | str, *, max_allowed: int) -> int:
    try:
        q = int(quantity)
    except Exception as exc:  # noqa: BLE001
        raise ProtocolValidationError(
            "quantity must be an integer",
            details={"quantity": redact_value(str(quantity))},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_quantity"),
            cause=exc,
        ) from exc
    if q <= 0:
        raise ProtocolValidationError(
            "quantity must be > 0",
            details={"quantity": q},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_quantity"),
        )
    if q > max_allowed:
        raise ProtocolValidationError(
            "quantity exceeds conservative limit",
            details={"quantity": q, "max_allowed": max_allowed},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_quantity"),
        )
    return q


def normalize_modbus_target(target: str) -> tuple[str, int]:
    """
    Normalize a Modbus TCP target into (host, port).

    Accepts:
      - "host:port"
      - "host" (uses default port 502)
      - "modbus://host:port"
      - "tcp://host:port"   (treated as plain TCP target)
      - "modbus-tcp://host:port"

    Safety:
      - rejects userinfo
      - strips query/fragment
    """
    raw = (target or "").strip()
    if not raw:
        raise ProtocolValidationError(
            "modbus target is required",
            details={"field": "target"},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
        )
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "modbus target contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
        )

    if "://" in raw:
        p = urlsplit(raw)
        if p.username or p.password:
            raise ProtocolValidationError(
                "modbus target must not include userinfo",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
            )
        if p.scheme and p.scheme.lower() not in ("modbus", "modbus-tcp", "tcp"):
            raise ProtocolValidationError(
                "unsupported target scheme for modbus tcp",
                details={"scheme": redact_value(p.scheme)},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
            )
        host = p.hostname
        port = p.port or MODBUS_TCP_DEFAULT_PORT
        if not host:
            raise ProtocolValidationError(
                "modbus target missing host",
                details={"target": redact_value(raw)},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
            )
        return host, int(port)

    # host:port or host
    if ":" in raw:
        host, port_s = raw.rsplit(":", 1)
        host = host.strip()
        if not host:
            raise ProtocolValidationError(
                "modbus target missing host",
                details={"target": redact_value(raw)},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
            )
        try:
            port = int(port_s.strip())
        except Exception as exc:  # noqa: BLE001
            raise ProtocolValidationError(
                "invalid port",
                details={"port": redact_value(port_s)},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
                cause=exc,
            ) from exc
        if not (1 <= port <= 65535):
            raise ProtocolValidationError(
                "port out of range (1..65535)",
                details={"port": port},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.normalize_target"),
            )
        return host, port

    return raw, MODBUS_TCP_DEFAULT_PORT


# =============================================================================
# Modbus TCP config
# =============================================================================


@dataclass(frozen=True, slots=True)
class ModbusTcpConfig:
    """
    Configuration for ModbusProtocolConnector (TCP mode).
    """

    target: str
    default_unit_id: int = 1

    connect_timeout_s: float = 3.0
    read_timeout_s: float = 3.0

    # Optional persistent connection (single socket protected by a lock).
    # When False, the connector uses connect-per-request (simpler, safer).
    keep_connection: bool = False

    # Conservative frame limits
    max_adu_bytes: int = 260  # MBAP(7)+PDU(253) conservative
    max_pdu_bytes: int = 253  # Modbus TCP PDU max per spec

    # Retry policy (applies ONLY when request is idempotent)
    backoff_policy: ProtocolBackoffPolicy = field(default_factory=ProtocolBackoffPolicy)

    # Addressing option
    one_based_addresses: bool = False  # if True, subtract 1 from provided addresses


# =============================================================================
# Modbus request/response models
# =============================================================================


@dataclass(frozen=True, slots=True)
class ModbusRequest:
    """
    A Modbus request (Modbus TCP PDU builder).

    SAFETY:
      - values are suppressed from repr()
      - use modbus_request_summary() for log-safe logging
    """

    function_code: int
    unit_id: int = 1

    address: int | None = None
    quantity: int | None = None

    # For writes:
    #   - single coil/register: int|bool
    #   - multiple: Sequence[int] or Sequence[bool]
    values: Any = field(default=None, repr=False)

    timeout_s: float | None = None
    idempotent: bool | None = None  # if None, derived from function code

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        fc = int(self.function_code)
        if not (1 <= fc <= 127):
            raise ProtocolValidationError(
                "function_code out of range (1..127)",
                details={"function_code": fc},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request.validate"),
            )
        object.__setattr__(self, "function_code", fc)
        object.__setattr__(self, "unit_id", normalize_unit_id(self.unit_id))

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request.validate"),
                    cause=exc,
                ) from exc
            if ts <= 0:
                raise ProtocolValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

        if self.idempotent is None:
            object.__setattr__(self, "idempotent", bool(fc in _READ_FUNCTIONS))

    def fingerprint(self, *, salt: str = "francis") -> str:
        payload = {
            "fc": self.function_code,
            "unit": self.unit_id,
            "address": self.address,
            "quantity": self.quantity,
            "values_shape": _shape_value(self.values),
            "idempotent": bool(self.idempotent),
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return _hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return modbus_request_summary(self)


@dataclass(frozen=True, slots=True)
class ModbusResponse:
    """
    A Modbus response (decoded).

    SAFETY:
      - data is suppressed from repr()
      - summaries never include raw coil/register values
    """

    request_fingerprint: str
    unit_id: int
    function_code: int

    exception_code: int | None = None  # if response function has 0x80 bit set
    data: Any = field(default=None, repr=False)

    # Lightweight stats
    transaction_id: int | None = None
    duration_ms: float | None = None
    bytes_sent: int | None = None
    bytes_received: int | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        return self.exception_code is None

    def redacted_dict(self) -> dict[str, Any]:
        return modbus_response_summary(self)


def modbus_request_summary(req: ModbusRequest) -> dict[str, Any]:
    if not isinstance(req, ModbusRequest):
        return {"type": type(req).__name__}
    return {
        "function_code": req.function_code,
        "unit_id": req.unit_id,
        "address": req.address,
        "quantity": req.quantity,
        "idempotent": bool(req.idempotent),
        "timeout_s": req.timeout_s,
        "values_shape": _shape_value(req.values),
        "fingerprint": req.fingerprint(),
        "meta": redact_mapping(req.meta),
    }


def modbus_response_summary(resp: ModbusResponse) -> dict[str, Any]:
    if not isinstance(resp, ModbusResponse):
        return {"type": type(resp).__name__}
    return {
        "request_fingerprint": resp.request_fingerprint,
        "unit_id": resp.unit_id,
        "function_code": resp.function_code,
        "ok": bool(resp.ok()),
        "exception_code": resp.exception_code,
        "data_shape": _shape_value(resp.data),
        "transaction_id": resp.transaction_id,
        "duration_ms": resp.duration_ms,
        "bytes_sent": resp.bytes_sent,
        "bytes_received": resp.bytes_received,
        "meta": redact_mapping(resp.meta),
    }


# =============================================================================
# Modbus PDU encode/decode helpers
# =============================================================================


def _u16(n: int) -> bytes:
    return bytes([(n >> 8) & 0xFF, n & 0xFF])


def _from_u16(b: bytes, off: int = 0) -> int:
    return (b[off] << 8) | b[off + 1]


def _pack_bits(values: Sequence[bool]) -> bytes:
    """
    Pack booleans into Modbus coil/discrete bit order (LSB first).
    """
    out = bytearray()
    acc = 0
    bit = 0
    for v in values:
        if v:
            acc |= 1 << bit
        bit += 1
        if bit == 8:
            out.append(acc)
            acc = 0
            bit = 0
    if bit != 0:
        out.append(acc)
    return bytes(out)


def _unpack_bits(data: bytes, count: int) -> list[bool]:
    """
    Unpack Modbus coil/discrete bytes (LSB first) into list[bool] of length count.
    """
    out: list[bool] = []
    for byte in data:
        for bit in range(8):
            out.append(bool(byte & (1 << bit)))
            if len(out) >= count:
                return out
    return out[:count]


def _pack_registers(values: Sequence[int]) -> bytes:
    out = bytearray()
    for v in values:
        iv = int(v)
        if not (0 <= iv <= 0xFFFF):
            raise ProtocolValidationError(
                "register value out of range (0..65535)",
                details={"value": iv},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.pack_registers"),
            )
        out.extend(_u16(iv))
    return bytes(out)


def _unpack_registers(data: bytes, count: int) -> list[int]:
    need = count * 2
    if len(data) < need:
        raise ProtocolSerializationError(
            "not enough bytes for registers",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.unpack_registers"),
            code="short_register_payload",
        )
    out: list[int] = []
    for i in range(count):
        off = i * 2
        out.append(_from_u16(data, off))
    return out


def _build_pdu(req: ModbusRequest, *, one_based: bool = False) -> bytes:
    fc = req.function_code

    # Validate for function
    if fc in (FC_READ_COILS, FC_READ_DISCRETE_INPUTS):
        if req.address is None or req.quantity is None:
            raise ProtocolValidationError(
                "read coils/inputs requires address and quantity",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        qty = normalize_quantity(req.quantity, max_allowed=_MAX_COILS_PER_READ)
        return bytes([fc]) + _u16(addr) + _u16(qty)

    if fc in (FC_READ_HOLDING_REGISTERS, FC_READ_INPUT_REGISTERS):
        if req.address is None or req.quantity is None:
            raise ProtocolValidationError(
                "read registers requires address and quantity",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        qty = normalize_quantity(req.quantity, max_allowed=_MAX_REGS_PER_READ)
        return bytes([fc]) + _u16(addr) + _u16(qty)

    if fc == FC_WRITE_SINGLE_COIL:
        if req.address is None:
            raise ProtocolValidationError(
                "write single coil requires address",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        v = req.values
        if isinstance(v, bool):
            val = 0xFF00 if v else 0x0000
        else:
            # allow int-like 0/1
            try:
                iv = int(v)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "write single coil value must be bool or int",
                    details={"value_type": type(v).__name__},
                    context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
                    cause=exc,
                ) from exc
            val = 0xFF00 if iv else 0x0000
        return bytes([fc]) + _u16(addr) + _u16(val)

    if fc == FC_WRITE_SINGLE_REGISTER:
        if req.address is None:
            raise ProtocolValidationError(
                "write single register requires address",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        try:
            val = int(req.values)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolValidationError(
                "write single register value must be int",
                details={"value_type": type(req.values).__name__},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
                cause=exc,
            ) from exc
        if not (0 <= val <= 0xFFFF):
            raise ProtocolValidationError(
                "write single register value out of range (0..65535)",
                details={"value": val},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        return bytes([fc]) + _u16(addr) + _u16(val)

    if fc == FC_WRITE_MULTIPLE_COILS:
        if req.address is None:
            raise ProtocolValidationError(
                "write multiple coils requires address",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        vals = req.values
        if not isinstance(vals, Sequence) or isinstance(vals, (str, bytes, bytearray)):
            raise ProtocolValidationError(
                "write multiple coils values must be a sequence[bool]",
                details={"value_type": type(vals).__name__},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        bools = [bool(x) for x in vals]
        qty = normalize_quantity(len(bools), max_allowed=_MAX_COILS_PER_WRITE)
        packed = _pack_bits(bools)
        return bytes([fc]) + _u16(addr) + _u16(qty) + bytes([len(packed)]) + packed

    if fc == FC_WRITE_MULTIPLE_REGISTERS:
        if req.address is None:
            raise ProtocolValidationError(
                "write multiple registers requires address",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        addr = normalize_address(req.address, one_based=one_based)
        vals = req.values
        if not isinstance(vals, Sequence) or isinstance(vals, (str, bytes, bytearray)):
            raise ProtocolValidationError(
                "write multiple registers values must be a sequence[int]",
                details={"value_type": type(vals).__name__},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        regs = [int(x) for x in vals]
        qty = normalize_quantity(len(regs), max_allowed=_MAX_REGS_PER_WRITE)
        payload = _pack_registers(regs)
        return bytes([fc]) + _u16(addr) + _u16(qty) + bytes([len(payload)]) + payload

    # Unknown function: allow raw bytes in values (advanced users).
    if isinstance(req.values, (bytes, bytearray)):
        raw = bytes(req.values)
        if len(raw) > 252:
            raise ProtocolValidationError(
                "raw PDU payload too large",
                details={"payload_len": len(raw)},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
            )
        return bytes([fc]) + raw

    raise ProtocolUnsupportedError(
        "unsupported modbus function_code",
        details={"function_code": fc},
        context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_pdu"),
        code="unsupported_function",
    )


def _decode_pdu(req: ModbusRequest, pdu: bytes) -> ModbusResponse:
    """
    Decode a response PDU based on request function code.
    """
    if not pdu or len(pdu) < 1:
        raise ProtocolSerializationError(
            "empty response PDU",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
            code="empty_pdu",
        )

    fn = pdu[0]
    req_fn = req.function_code
    fp = req.fingerprint()

    # Exception response: function | 0x80, then 1 byte exception code
    if fn & 0x80:
        if len(pdu) < 2:
            raise ProtocolSerializationError(
                "short exception PDU",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_exception_pdu",
            )
        exc_code = int(pdu[1])
        return ModbusResponse(
            request_fingerprint=fp,
            unit_id=req.unit_id,
            function_code=req_fn,
            exception_code=exc_code,
            data=None,
            meta={"exception": True},
        )

    # Normal response: function must match request function (best-effort)
    # Some gateways might behave oddly; be strict.
    if fn != req_fn:
        raise ProtocolSerializationError(
            "function code mismatch",
            context=ProtocolErrorContext(
                protocol_id=MODBUS_PROTOCOL_ID,
                operation="modbus.decode_pdu",
                details={"expected": req_fn, "got": fn},
            ),
            code="function_mismatch",
        )

    # Reads
    if fn in (FC_READ_COILS, FC_READ_DISCRETE_INPUTS):
        if len(pdu) < 2:
            raise ProtocolSerializationError(
                "short read-bits response",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_read_bits",
            )
        byte_count = pdu[1]
        data = pdu[2:]
        if len(data) < byte_count:
            raise ProtocolSerializationError(
                "short read-bits payload",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_read_bits_payload",
            )
        qty = int(req.quantity or 0)
        bits = _unpack_bits(data[:byte_count], qty)
        # Do not log raw bits; returned to caller as data.
        return ModbusResponse(
            request_fingerprint=fp,
            unit_id=req.unit_id,
            function_code=req_fn,
            data=bits,
            meta={"byte_count": byte_count, "quantity": qty},
        )

    if fn in (FC_READ_HOLDING_REGISTERS, FC_READ_INPUT_REGISTERS):
        if len(pdu) < 2:
            raise ProtocolSerializationError(
                "short read-registers response",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_read_regs",
            )
        byte_count = pdu[1]
        data = pdu[2:]
        if len(data) < byte_count:
            raise ProtocolSerializationError(
                "short read-registers payload",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_read_regs_payload",
            )
        qty = int(req.quantity or 0)
        regs = _unpack_registers(data[:byte_count], qty)
        return ModbusResponse(
            request_fingerprint=fp,
            unit_id=req.unit_id,
            function_code=req_fn,
            data=regs,
            meta={"byte_count": byte_count, "quantity": qty},
        )

    # Writes confirmations
    if fn in (FC_WRITE_SINGLE_COIL, FC_WRITE_SINGLE_REGISTER):
        if len(pdu) < 5:
            raise ProtocolSerializationError(
                "short write-single response",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_write_single",
            )
        addr = _from_u16(pdu, 1)
        val = _from_u16(pdu, 3)
        return ModbusResponse(
            request_fingerprint=fp,
            unit_id=req.unit_id,
            function_code=req_fn,
            data={"address": addr, "value": val},
        )

    if fn in (FC_WRITE_MULTIPLE_COILS, FC_WRITE_MULTIPLE_REGISTERS):
        if len(pdu) < 5:
            raise ProtocolSerializationError(
                "short write-multiple response",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.decode_pdu"),
                code="short_write_multiple",
            )
        addr = _from_u16(pdu, 1)
        qty = _from_u16(pdu, 3)
        return ModbusResponse(
            request_fingerprint=fp,
            unit_id=req.unit_id,
            function_code=req_fn,
            data={"address": addr, "quantity": qty},
        )

    # Fallback: return raw trailing bytes (still suppressed from logs)
    return ModbusResponse(
        request_fingerprint=fp,
        unit_id=req.unit_id,
        function_code=req_fn,
        data=bytes(pdu[1:]),
        meta={"decoded": False},
    )


# =============================================================================
# Modbus TCP transport (socket)
# =============================================================================


class _TransactionId:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tid = 0

    def next(self) -> int:
        with self._lock:
            self._tid = (self._tid + 1) & 0xFFFF
            return self._tid


_TID = _TransactionId()


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """
    Receive exactly n bytes or raise ProtocolNetworkError.
    """
    buf = bytearray()
    while len(buf) < n:
        try:
            chunk = sock.recv(n - len(buf))
        except TimeoutError as exc:
            raise ProtocolTimeoutError(
                "modbus recv timed out",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.recv"),
                code="timeout",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ProtocolNetworkError(
                "modbus recv failed",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.recv"),
                code="recv_error",
                cause=exc,
            ) from exc
        if not chunk:
            raise ProtocolNetworkError(
                "modbus connection closed by peer",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.recv"),
                code="connection_closed",
            )
        buf.extend(chunk)
    return bytes(buf)


def _modbus_tcp_exchange(
    *,
    host: str,
    port: int,
    unit_id: int,
    pdu: bytes,
    timeout_s: float,
    connect_timeout_s: float,
    max_adu_bytes: int,
    keep_socket: socket.socket | None = None,
) -> tuple[int, int, bytes, int, int, socket.socket | None]:
    """
    Send one Modbus TCP ADU and receive response ADU.

    Returns:
      (transaction_id, unit_id_resp, pdu_resp, bytes_sent, bytes_received, socket_to_keep?)
    """
    tid = _TID.next()

    # MBAP header:
    #  - transaction id (2)
    #  - protocol id (2) = 0
    #  - length (2) = unit_id(1) + pdu_len
    #  - unit id (1)
    length = 1 + len(pdu)
    if length > 0xFFFF:
        raise ProtocolValidationError(
            "PDU too large",
            details={"pdu_len": len(pdu)},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_adu"),
        )
    adu = _u16(tid) + b"\x00\x00" + _u16(length) + bytes([unit_id]) + pdu
    if len(adu) > max_adu_bytes:
        raise ProtocolValidationError(
            "ADU exceeds configured max_adu_bytes",
            details={"adu_len": len(adu), "max_adu_bytes": max_adu_bytes},
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.build_adu"),
        )

    sock = keep_socket
    created = False

    if sock is None:
        created = True
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(connect_timeout_s)
            sock.connect((host, port))
            sock.settimeout(timeout_s)
        except TimeoutError as exc:
            raise ProtocolTimeoutError(
                "modbus connect timed out",
                context=ProtocolErrorContext(
                    protocol_id=MODBUS_PROTOCOL_ID,
                    operation="modbus.connect",
                    details={"host": host, "port": port},
                ),
                code="connect_timeout",
                cause=exc,
            ) from exc
        except OSError as exc:
            raise ProtocolNetworkError(
                "modbus connect failed",
                context=ProtocolErrorContext(
                    protocol_id=MODBUS_PROTOCOL_ID,
                    operation="modbus.connect",
                    details={"host": host, "port": port},
                ),
                code="connect_error",
                cause=exc,
            ) from exc

    assert sock is not None

    # Send
    try:
        sock.sendall(adu)
    except TimeoutError as exc:
        if created:
            try:
                sock.close()
            except Exception:
                pass
        raise ProtocolTimeoutError(
            "modbus send timed out",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.send"),
            code="send_timeout",
            cause=exc,
        ) from exc
    except OSError as exc:
        if created:
            try:
                sock.close()
            except Exception:
                pass
        raise ProtocolNetworkError(
            "modbus send failed",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.send"),
            code="send_error",
            cause=exc,
        ) from exc

    bytes_sent = len(adu)

    # Receive MBAP header: 7 bytes
    mbap = _recv_exact(sock, 7)
    bytes_received = len(mbap)

    tid_r = _from_u16(mbap, 0)
    proto = _from_u16(mbap, 2)
    length_r = _from_u16(mbap, 4)
    unit_r = mbap[6]

    if proto != 0:
        if created:
            try:
                sock.close()
            except Exception:
                pass
        raise ProtocolSerializationError(
            "invalid protocol id in MBAP",
            context=ProtocolErrorContext(
                protocol_id=MODBUS_PROTOCOL_ID,
                operation="modbus.recv_mbap",
                details={"protocol_id": proto},
            ),
            code="invalid_mbap_protocol",
        )

    # length includes unit id + PDU
    if length_r <= 1:
        if created:
            try:
                sock.close()
            except Exception:
                pass
        raise ProtocolSerializationError(
            "invalid MBAP length",
            context=ProtocolErrorContext(
                protocol_id=MODBUS_PROTOCOL_ID,
                operation="modbus.recv_mbap",
                details={"length": length_r},
            ),
            code="invalid_mbap_length",
        )

    remaining = length_r - 1  # we already consumed unit id byte in header
    if remaining > (max_adu_bytes - 7):
        if created:
            try:
                sock.close()
            except Exception:
                pass
        raise ProtocolSerializationError(
            "response ADU exceeds configured max_adu_bytes",
            context=ProtocolErrorContext(
                protocol_id=MODBUS_PROTOCOL_ID,
                operation="modbus.recv_mbap",
                details={"remaining": remaining, "max_adu_bytes": max_adu_bytes},
            ),
            code="response_too_large",
        )

    pdu_r = _recv_exact(sock, remaining)
    bytes_received += len(pdu_r)

    # Transaction id mismatch: possible if shared socket and out-of-sync
    if tid_r != tid:
        # If we created the socket (connect-per-request), mismatch is unexpected -> error.
        if created:
            try:
                sock.close()
            except Exception:
                pass
            raise ProtocolSerializationError(
                "transaction id mismatch",
                context=ProtocolErrorContext(
                    protocol_id=MODBUS_PROTOCOL_ID,
                    operation="modbus.recv_mbap",
                    details={"expected_tid": tid, "got_tid": tid_r},
                ),
                code="tid_mismatch",
            )
        # If persistent socket, it's unsafe to keep using it.
        try:
            sock.close()
        except Exception:
            pass
        return (tid, unit_r, pdu_r, bytes_sent, bytes_received, None)

    # Keep or close socket
    if created:
        try:
            sock.close()
        except Exception:
            pass
        return (tid, unit_r, pdu_r, bytes_sent, bytes_received, None)

    return (tid, unit_r, pdu_r, bytes_sent, bytes_received, sock)


# =============================================================================
# Connector
# =============================================================================


class ModbusProtocolConnector:
    """
    Modbus TCP ProtocolConnector (stdlib sockets).

    - If keep_connection=True, maintains a single TCP socket (thread-safe via lock).
      This is faster but less resilient to network quirks.
    - If keep_connection=False, uses connect-per-request (safer default).
    """

    def __init__(self, config: ModbusTcpConfig) -> None:
        self._cfg = config
        host, port = normalize_modbus_target(config.target)
        self._host = host
        self._port = port
        self._default_unit = normalize_unit_id(config.default_unit_id)

        if self._cfg.connect_timeout_s <= 0 or self._cfg.read_timeout_s <= 0:
            raise ProtocolValidationError(
                "timeouts must be > 0",
                details={
                    "connect_timeout_s": self._cfg.connect_timeout_s,
                    "read_timeout_s": self._cfg.read_timeout_s,
                },
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.config.validate"),
            )

        if self._cfg.max_adu_bytes < 64 or self._cfg.max_adu_bytes > 8192:
            raise ProtocolValidationError(
                "max_adu_bytes out of reasonable bounds",
                details={"max_adu_bytes": self._cfg.max_adu_bytes},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.config.validate"),
            )

        self._sock: socket.socket | None = None
        self._sock_lock = threading.RLock()

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=MODBUS_PROTOCOL_ID,
            name="Modbus TCP Connector",
            version=None,
            description="Synchronous Modbus TCP connector using stdlib sockets.",
            capabilities=(
                "request",
                "health_check",
                "read_coils",
                "read_discrete_inputs",
                "read_holding_registers",
                "read_input_registers",
                "write_single_coil",
                "write_single_register",
                "write_multiple_coils",
                "write_multiple_registers",
                "idempotent_retry",
            ),
            meta={
                "target": f"{self._host}:{self._port}",
                "keep_connection": bool(self._cfg.keep_connection),
                "one_based_addresses": bool(self._cfg.one_based_addresses),
                "max_adu_bytes": self._cfg.max_adu_bytes,
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
        Lightweight health check:
          - TCP connect + immediate close (no register read by default).
        """
        host, port = self._host, self._port
        if endpoint and (endpoint.uri or endpoint.address):
            try:
                host, port = normalize_modbus_target(endpoint.uri or endpoint.address)
            except Exception:
                # Keep defaults but report degraded
                return ProtocolHealth(
                    ok=False,
                    degraded=True,
                    message="invalid endpoint",
                    details={"endpoint": endpoint.redacted_dict()},
                )

        tmo = float(timeout_s if timeout_s is not None else self._cfg.connect_timeout_s)
        start = time.time()
        s: socket.socket | None = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(tmo)
            s.connect((host, port))
            return ProtocolHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "target": f"{host}:{port}",
                    "connect_ms": round((time.time() - start) * 1000.0, 3),
                },
            )
        except TimeoutError as exc:
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="timeout",
                details={"target": f"{host}:{port}", "error": redact_value(str(exc))},
            )
        except OSError as exc:
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={"target": f"{host}:{port}", "error": redact_value(str(exc))},
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
        Execute a Modbus request.

        Expects:
          - req.payload is ModbusRequest OR a mapping with fields:
              {"function_code": int, "unit_id": int?, "address": int?, "quantity": int?, "values": ...}
          - req.endpoint (optional) overrides connector target.

        Returns:
          - ProtocolResponse(protocol_id="modbus") whose payload is ModbusResponse.
          - Does NOT raise for Modbus exception responses; ok=False indicates exception.
          - Raises ProtocolTimeoutError / ProtocolNetworkError / ProtocolSerializationError for transport/parse failures.
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request"),
            )

        # Resolve target
        host, port = self._host, self._port
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            host, port = normalize_modbus_target(req.endpoint.uri or req.endpoint.address)

        # Coerce payload to ModbusRequest
        mb_req: ModbusRequest
        if isinstance(req.payload, ModbusRequest):
            mb_req = req.payload
        elif isinstance(req.payload, Mapping):
            fc = req.payload.get("function_code")
            if fc is None:
                raise ProtocolValidationError(
                    "modbus payload mapping requires function_code",
                    details={"keys": sorted(str(k) for k in req.payload.keys())},
                    context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request"),
                )
            mb_req = ModbusRequest(
                function_code=int(fc),
                unit_id=normalize_unit_id(req.payload.get("unit_id", self._default_unit)),
                address=req.payload.get("address"),
                quantity=req.payload.get("quantity"),
                values=req.payload.get("values"),
                timeout_s=req.payload.get("timeout_s"),
                idempotent=req.payload.get("idempotent"),
                meta={"from_mapping": True, "caller_meta": redact_mapping(req.meta)},
            )
        else:
            raise ProtocolValidationError(
                "modbus request payload must be ModbusRequest or mapping",
                details={"payload_type": type(req.payload).__name__},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request"),
            )

        # Override unit_id if provided via req.meta
        if isinstance(req.meta, Mapping) and "unit_id" in req.meta:
            mb_req = ModbusRequest(
                function_code=mb_req.function_code,
                unit_id=normalize_unit_id(req.meta.get("unit_id")),
                address=mb_req.address,
                quantity=mb_req.quantity,
                values=mb_req.values,
                timeout_s=mb_req.timeout_s,
                idempotent=mb_req.idempotent,
                meta=mb_req.meta,
            )

        # Determine timeouts
        read_tmo = float(
            timeout_s
            if timeout_s is not None
            else (mb_req.timeout_s if mb_req.timeout_s is not None else self._cfg.read_timeout_s)
        )
        if read_tmo <= 0:
            raise ProtocolValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": read_tmo},
                context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus.request"),
            )

        # Build PDU
        pdu = _build_pdu(mb_req, one_based=self._cfg.one_based_addresses)

        # Retry loop (idempotent only)
        idempotent = bool(req.idempotent) if req.idempotent is not None else bool(mb_req.idempotent)
        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        attempt = 0

        while True:
            start_ns = time.time_ns()
            sock_to_use: socket.socket | None = None

            if self._cfg.keep_connection:
                self._sock_lock.acquire()
                sock_to_use = self._sock

            try:
                tid, unit_r, pdu_r, bytes_sent, bytes_recv, sock_keep = _modbus_tcp_exchange(
                    host=host,
                    port=port,
                    unit_id=mb_req.unit_id,
                    pdu=pdu,
                    timeout_s=read_tmo,
                    connect_timeout_s=self._cfg.connect_timeout_s,
                    max_adu_bytes=self._cfg.max_adu_bytes,
                    keep_socket=sock_to_use,
                )

                if self._cfg.keep_connection:
                    # Update kept socket (may become None if unsafe)
                    self._sock = sock_keep

                duration_ms = (time.time_ns() - start_ns) / 1_000_000.0

                decoded = _decode_pdu(mb_req, pdu_r)
                decoded = ModbusResponse(
                    request_fingerprint=decoded.request_fingerprint,
                    unit_id=unit_r,
                    function_code=decoded.function_code,
                    exception_code=decoded.exception_code,
                    data=decoded.data,
                    transaction_id=tid,
                    duration_ms=round(duration_ms, 3),
                    bytes_sent=bytes_sent,
                    bytes_received=bytes_recv,
                    meta=decoded.meta,
                )

                ok = decoded.ok()
                status_code = 0 if ok else int(decoded.exception_code or 0)

                return ProtocolResponse(
                    protocol_id=MODBUS_PROTOCOL_ID,
                    ok=ok,
                    status_code=status_code,
                    headers={},  # Modbus has no headers; keep empty
                    payload=decoded,
                    stats=redact_mapping(
                        {
                            "target": f"{host}:{port}",
                            "transaction_id": tid,
                            "unit_id": unit_r,
                            "function_code": mb_req.function_code,
                            "idempotent": bool(idempotent),
                            "attempt": attempt,
                            "duration_ms": round(duration_ms, 3),
                            "bytes_sent": bytes_sent,
                            "bytes_received": bytes_recv,
                            "exception_code": decoded.exception_code,
                        }
                    ),
                    ts=int(time.time()),
                    meta=redact_mapping(req.meta),
                )

            except (ProtocolTimeoutError, ProtocolNetworkError, ProtocolSerializationError):
                # If persistent socket and we hit a transport/parse error, drop it.
                if self._cfg.keep_connection:
                    try:
                        if self._sock is not None:
                            self._sock.close()
                    except Exception:
                        pass
                    self._sock = None

                if idempotent:
                    attempt += 1
                    if attempt > max_attempts:
                        raise
                    time.sleep(compute_backoff_s(policy, attempt=attempt))
                    continue

                raise

            finally:
                if self._cfg.keep_connection:
                    try:
                        self._sock_lock.release()
                    except Exception:
                        pass

    # -------------------------------------------------------------------------
    # Convenience methods (return ModbusResponse)
    # -------------------------------------------------------------------------

    def _call(
        self,
        mb: ModbusRequest,
        *,
        timeout_s: float | None = None,
        identity: ProtocolIdentity | None = None,
    ) -> ModbusResponse:
        resp = self.request(
            ProtocolRequest(
                protocol_id=MODBUS_PROTOCOL_ID,
                operation="modbus",
                endpoint=ProtocolEndpoint(
                    protocol_id=MODBUS_PROTOCOL_ID,
                    address=f"{self._host}:{self._port}",
                    uri=f"modbus://{self._host}:{self._port}",
                ),
                headers={},
                payload=mb,
                idempotent=bool(mb.idempotent),
                expect_response=True,
                timeout_s=timeout_s if timeout_s is not None else mb.timeout_s,
                meta={},
            ),
            identity=identity,
            timeout_s=timeout_s,
        )
        if isinstance(resp.payload, ModbusResponse):
            return resp.payload
        raise ProtocolSerializationError(
            "unexpected modbus response payload type",
            context=ProtocolErrorContext(protocol_id=MODBUS_PROTOCOL_ID, operation="modbus._call"),
            code="unexpected_payload",
        )

    def read_holding_registers(
        self,
        address: int,
        quantity: int,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_READ_HOLDING_REGISTERS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            quantity=quantity,
            idempotent=True,
        )
        return self._call(mb, timeout_s=timeout_s)

    def read_input_registers(
        self,
        address: int,
        quantity: int,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_READ_INPUT_REGISTERS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            quantity=quantity,
            idempotent=True,
        )
        return self._call(mb, timeout_s=timeout_s)

    def read_coils(
        self,
        address: int,
        quantity: int,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_READ_COILS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            quantity=quantity,
            idempotent=True,
        )
        return self._call(mb, timeout_s=timeout_s)

    def read_discrete_inputs(
        self,
        address: int,
        quantity: int,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_READ_DISCRETE_INPUTS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            quantity=quantity,
            idempotent=True,
        )
        return self._call(mb, timeout_s=timeout_s)

    def write_single_coil(
        self,
        address: int,
        value: bool,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
        idempotent: bool = False,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_WRITE_SINGLE_COIL,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            values=bool(value),
            idempotent=bool(idempotent),
        )
        return self._call(mb, timeout_s=timeout_s)

    def write_single_register(
        self,
        address: int,
        value: int,
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
        idempotent: bool = False,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_WRITE_SINGLE_REGISTER,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            values=int(value),
            idempotent=bool(idempotent),
        )
        return self._call(mb, timeout_s=timeout_s)

    def write_multiple_registers(
        self,
        address: int,
        values: Sequence[int],
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
        idempotent: bool = False,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_WRITE_MULTIPLE_REGISTERS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            values=list(values),
            idempotent=bool(idempotent),
        )
        return self._call(mb, timeout_s=timeout_s)

    def write_multiple_coils(
        self,
        address: int,
        values: Sequence[bool],
        *,
        unit_id: int | None = None,
        timeout_s: float | None = None,
        idempotent: bool = False,
    ) -> ModbusResponse:
        mb = ModbusRequest(
            function_code=FC_WRITE_MULTIPLE_COILS,
            unit_id=unit_id if unit_id is not None else self._default_unit,
            address=address,
            values=[bool(v) for v in values],
            idempotent=bool(idempotent),
        )
        return self._call(mb, timeout_s=timeout_s)
