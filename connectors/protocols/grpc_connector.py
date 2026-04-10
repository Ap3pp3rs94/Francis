"""
===============================================================================
Francis 2.0 — Protocol Connectors (gRPC Connector)
Path: connectors/protocols/grpc_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides a *gRPC adapter layer* that standardizes how Francis represents
and logs gRPC calls, WITHOUT importing grpcio or any provider SDKs.

Key idea:
  - gRPC is a transport/protocol that typically requires grpcio (or equivalent).
  - To keep this layer dependency-free and deterministic, we delegate the actual
    network/codec work to a registered ProtocolConnector (protocol_id="grpc").
  - This module focuses on:
      * stable types for gRPC method refs / call envelopes / response envelopes
      * safe logging: no raw protobuf bytes, no sensitive metadata values in logs
      * status code mapping to Francis ProtocolError taxonomy

This module:
  - Defines GraphQL-like typed wrappers for gRPC:
      * GrpcMethodRef, GrpcCall, GrpcResponse
  - Provides GrpcProtocolConnector implementing ProtocolConnector:
      * info(), health_check(), request()
      * plus convenience helpers (unary_unary(), call()) with optional raise_on_errors

It intentionally does NOT:
  - Implement grpc channels/stubs, reflection, protobuf encoding/decoding
  - Depend on grpcio
  - Store any secrets, tokens, or credentials

EXPECTED UNDERLYING TRANSPORT CONNECTOR
---------------------------------------
A "grpc" ProtocolConnector (implemented elsewhere) should interpret a ProtocolRequest as:
  - req.operation: gRPC method full name, e.g. "/pkg.Service/Method"
  - req.endpoint.address / req.endpoint.uri: gRPC target, e.g. "host:port" or "dns:///host:port"
  - req.headers: metadata (string metadata only in this contract)
  - req.payload: request message (bytes or mapping/dict) OR a structured dict
  - req.meta: may include call_type hints

The underlying transport connector returns ProtocolResponse where:
  - status_code: gRPC status code (OK=0, etc) if available
  - payload: response message (bytes or mapping/dict) OR a structured dict
  - headers/trailers (optional): may be returned in headers/meta/stats (connector-defined)

SAFETY & OBSERVABILITY
----------------------
- Never log raw request/response message bodies.
- Never log raw metadata values (summarize by key + hash/len only; redact known secret keys).
- Provide fingerprints for correlation.

===============================================================================
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from . import (
    ProtocolAuthError,
    ProtocolBackoffPolicy,
    ProtocolConnector,
    ProtocolConnectorInfo,
    ProtocolEndpoint,
    ProtocolError,
    ProtocolErrorContext,
    ProtocolHealth,
    ProtocolIdentity,
    ProtocolNotFoundError,
    ProtocolPermissionError,
    ProtocolRateLimitError,
    ProtocolRequest,
    ProtocolResponse,
    ProtocolTimeoutError,
    ProtocolUnavailableError,
    ProtocolUnsupportedError,
    ProtocolValidationError,
    get_protocol_connector,
    redact_mapping,
    redact_value,
)

__all__ = [
    "GRPC_PROTOCOL_ID",
    "GrpcCallType",
    "GrpcMethodRef",
    "GrpcCall",
    "GrpcResponse",
    "GrpcProtocolConnector",
    "normalize_grpc_target",
    "normalize_grpc_method",
    "normalize_grpc_metadata",
    "grpc_call_summary",
    "grpc_response_summary",
    "grpc_status_name",
    "is_retryable_grpc_status",
]


GRPC_PROTOCOL_ID = "grpc"
GrpcCallType = str  # "unary_unary" | "unary_stream" | "stream_unary" | "stream_stream"


# =============================================================================
# gRPC status codes (standard)
# =============================================================================

_GRPC_STATUS_NAMES: dict[int, str] = {
    0: "OK",
    1: "CANCELLED",
    2: "UNKNOWN",
    3: "INVALID_ARGUMENT",
    4: "DEADLINE_EXCEEDED",
    5: "NOT_FOUND",
    6: "ALREADY_EXISTS",
    7: "PERMISSION_DENIED",
    8: "RESOURCE_EXHAUSTED",
    9: "FAILED_PRECONDITION",
    10: "ABORTED",
    11: "OUT_OF_RANGE",
    12: "UNIMPLEMENTED",
    13: "INTERNAL",
    14: "UNAVAILABLE",
    15: "DATA_LOSS",
    16: "UNAUTHENTICATED",
}


def grpc_status_name(code: int | None) -> str:
    if code is None:
        return "UNKNOWN"
    try:
        c = int(code)
    except Exception:
        return "UNKNOWN"
    return _GRPC_STATUS_NAMES.get(c, f"CODE_{c}")


def is_retryable_grpc_status(code: int | None) -> bool:
    """
    Best-effort classification of retryable gRPC statuses.

    Not a security boundary. Callers/governance decide if retries are allowed.
    """
    try:
        c = int(code) if code is not None else None
    except Exception:
        c = None

    # Common retryable statuses:
    # - UNAVAILABLE (14)
    # - DEADLINE_EXCEEDED (4)
    # - RESOURCE_EXHAUSTED (8)  (often backoff helps)
    # - ABORTED (10)            (transaction abort; may retry)
    # - INTERNAL (13)           (sometimes transient)
    return c in (4, 8, 10, 13, 14)


# =============================================================================
# Safe hashing + summaries
# =============================================================================


def _hash_stable(value: str, *, salt: str = "francis") -> str:
    v = (value or "").encode("utf-8", errors="ignore")
    s = (salt or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(s + b":" + v).hexdigest()[:12]


def _shape_value(v: Any) -> dict[str, Any]:
    """
    Summarize a value without returning it (log-safe).
    """
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
        # Hash a prefix only for cost control
        return {"type": "bytes", "len": len(b), "hash": _hash_stable(b[:256].hex())}
    if isinstance(v, Mapping):
        return {"type": "object", "keys": len(v)}
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {"type": "array", "len": len(v)}
    try:
        s = str(v)
    except Exception:
        s = type(v).__name__
    return {
        "type": type(v).__name__,
        "hash": _hash_stable(s),
        "len": len(s) if isinstance(s, str) else None,
    }


def _summarize_metadata(md: Mapping[str, str] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Log-safe summary of gRPC metadata.

    - Keys preserved (normalized to lowercase in normalize_grpc_metadata()).
    - Values represented by len + hash, not raw strings.
    - Also passes through redact_mapping() so common secret keys are redacted if logged elsewhere.
    """
    if not md:
        return {"count": 0, "items": {}}
    if not isinstance(md, Mapping):
        return {"count": 1, "items": {"<non_mapping>": {"type": type(md).__name__}}}

    keys = sorted(str(k) for k in md.keys())
    truncated = False
    if len(keys) > max_keys:
        keys = keys[:max_keys]
        truncated = True

    items: dict[str, Any] = {}
    for k in keys:
        kk = k
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            kk = "<invalid_key>"
        try:
            v = "" if md.get(k) is None else str(md.get(k))
            items[kk] = {"len": len(v), "hash": _hash_stable(v)}
        except Exception:
            items[kk] = {"type": "error"}

    if truncated:
        items["…"] = {"truncated": True}

    return {"count": len(md), "items": items}


# =============================================================================
# Target / method / metadata normalization (conservative)
# =============================================================================

# Method full name formats we accept:
#   /package.Service/Method
#   package.Service/Method
#   Service/Method
_GRPC_METHOD_RE = re.compile(r"^/?[A-Za-z0-9_.]+/[A-Za-z0-9_]+$")

# Metadata key rules (string metadata only here):
#   - lowercase ASCII letters/digits/hyphen/underscore/dot (conservative)
#   - disallow "-bin" keys (binary metadata) in this string-only layer
_GRPC_MD_KEY_RE = re.compile(r"^[a-z0-9][a-z0-9_\-\.]{0,62}[a-z0-9]$")


def normalize_grpc_method(method: str) -> str:
    """
    Normalize and validate a gRPC method name.

    Returns a canonical full method name with a leading "/".
    """
    m = (method or "").strip()
    if not m:
        raise ProtocolValidationError(
            "grpc method is required",
            details={"field": "method"},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_method"),
        )
    if "\x00" in m or "\r" in m or "\n" in m:
        raise ProtocolValidationError(
            "grpc method contains illegal control characters",
            details={"method": redact_value(m)},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_method"),
        )
    if not _GRPC_METHOD_RE.match(m):
        raise ProtocolValidationError(
            "grpc method has invalid format",
            details={"method": redact_value(m), "expected": _GRPC_METHOD_RE.pattern},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_method"),
        )
    return m if m.startswith("/") else f"/{m}"


def normalize_grpc_metadata(metadata: Mapping[str, str] | None) -> dict[str, str]:
    """
    Normalize gRPC metadata keys and validate shape.

    Notes:
      - This contract supports string metadata only.
      - Binary metadata keys ending in "-bin" are rejected here (transport connector may support them separately).
    """
    if not metadata:
        return {}

    if not isinstance(metadata, Mapping):
        raise ProtocolValidationError(
            "grpc metadata must be a mapping",
            details={"type": type(metadata).__name__},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
        )

    out: dict[str, str] = {}
    for k, v in metadata.items():
        kk = ("" if k is None else str(k)).strip().lower()
        if not kk:
            raise ProtocolValidationError(
                "grpc metadata key cannot be empty",
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
            )
        if "\x00" in kk or "\r" in kk or "\n" in kk:
            raise ProtocolValidationError(
                "grpc metadata key contains illegal control characters",
                details={"key": redact_value(kk)},
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
            )
        if kk.endswith("-bin"):
            raise ProtocolValidationError(
                "grpc binary metadata keys (*-bin) are not supported by this string-only layer",
                details={"key": kk},
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
            )
        if not _GRPC_MD_KEY_RE.match(kk):
            raise ProtocolValidationError(
                "grpc metadata key has invalid format (conservative rule)",
                details={"key": redact_value(kk), "expected": _GRPC_MD_KEY_RE.pattern},
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
            )
        vv = "" if v is None else str(v)
        if "\x00" in vv or "\r" in vv or "\n" in vv:
            raise ProtocolValidationError(
                "grpc metadata value contains illegal control characters",
                details={"key": kk},
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_metadata"),
            )
        # NOTE: do not redact here; redaction is for logs. Keep exact value in memory.
        out[kk] = vv
    return out


def normalize_grpc_target(target: str) -> tuple[str, bool]:
    """
    Normalize a gRPC target string and infer TLS.

    Accepts:
      - "host:port"
      - "dns:///host:port"
      - "unix:///path"
      - "grpc://host:port"
      - "grpcs://host:port"
      - "https://host:port" (treated as TLS)

    Returns:
      (normalized_target, tls)

    Safety:
      - strips query and fragment if URL-form is used
      - rejects userinfo (username:password@)
    """
    raw = (target or "").strip()
    if not raw:
        raise ProtocolValidationError(
            "grpc target is required",
            details={"field": "target"},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_target"),
        )
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "grpc target contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_target"),
        )

    # Common gRPC resolver forms that are not normal URLs.
    if raw.startswith("dns:///") or raw.startswith("unix:///"):
        return (raw, False)

    if "://" not in raw:
        # Treat as host:port (or similar). TLS cannot be inferred here -> False.
        return (raw, False)

    parts = urlsplit(raw)
    scheme = (parts.scheme or "").lower()
    if parts.username or parts.password:
        raise ProtocolValidationError(
            "grpc target must not include userinfo",
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_target"),
        )

    tls = scheme in ("grpcs", "https")
    host = parts.hostname
    if not host:
        raise ProtocolValidationError(
            "grpc target missing host",
            details={"target": redact_value(raw)},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_target"),
        )
    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"

    # gRPC targets typically do not use path; if present, ignore it (except unix/dns handled above).
    normalized = urlunsplit(("dns", netloc, "", "", "")) if scheme == "dns" else netloc

    # Drop query/fragment by construction.
    return (normalized, tls)


# =============================================================================
# gRPC typed wrappers
# =============================================================================


@dataclass(frozen=True, slots=True)
class GrpcMethodRef:
    """
    Reference to a gRPC method.
    """

    full_method: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "full_method", normalize_grpc_method(self.full_method))

    @staticmethod
    def from_parts(service: str, method: str, *, package: str | None = None) -> GrpcMethodRef:
        svc = (service or "").strip()
        mtd = (method or "").strip()
        pkg = (package or "").strip()
        if pkg:
            fm = f"/{pkg}.{svc}/{mtd}"
        else:
            fm = f"/{svc}/{mtd}"
        return GrpcMethodRef(full_method=fm)

    def canonical(self) -> str:
        return self.full_method


_ALLOWED_CALL_TYPES = {"unary_unary", "unary_stream", "stream_unary", "stream_stream"}


def _normalize_call_type(call_type: str | None) -> GrpcCallType:
    ct = (call_type or "unary_unary").strip().lower()
    if ct not in _ALLOWED_CALL_TYPES:
        raise ProtocolValidationError(
            "unsupported grpc call_type",
            details={"call_type": redact_value(ct), "allowed": sorted(_ALLOWED_CALL_TYPES)},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.normalize_call_type"),
        )
    return ct


@dataclass(frozen=True, slots=True)
class GrpcCall:
    """
    gRPC call envelope.

    SAFETY:
      - message is suppressed from repr()
      - use grpc_call_summary() for log-safe details

    message may be:
      - bytes (serialized protobuf)
      - dict/mapping (pre-decoded or JSON-like request object)
      - any object the underlying transport connector understands
    """

    method: GrpcMethodRef
    call_type: GrpcCallType = "unary_unary"

    message: Any = field(default=None, repr=False)
    metadata: Mapping[str, str] = field(default_factory=dict, repr=False)

    # Hints
    timeout_s: float | None = None
    idempotent: bool | None = None

    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        ct = _normalize_call_type(self.call_type)
        object.__setattr__(self, "call_type", ct)

        md = normalize_grpc_metadata(self.metadata)
        object.__setattr__(self, "metadata", md)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.call.validate"),
                    cause=exc,
                ) from exc
            if ts <= 0:
                raise ProtocolValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.call.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

        # This connector layer cannot support streaming via ProtocolConnector.request().
        if ct != "unary_unary":
            raise ProtocolUnsupportedError(
                "streaming gRPC call types are not supported by this connector (requires streaming interface)",
                context=ProtocolErrorContext(
                    protocol_id=GRPC_PROTOCOL_ID,
                    operation="grpc.call.validate",
                    details={"call_type": ct},
                ),
                code="streaming_not_supported",
            )

    def fingerprint(self, *, salt: str = "francis") -> str:
        payload = {
            "method": self.method.canonical(),
            "call_type": self.call_type,
            "message_shape": _shape_value(self.message),
            "metadata": _summarize_metadata(self.metadata),
            "timeout_s": self.timeout_s,
            "idempotent": bool(self.idempotent) if self.idempotent is not None else None,
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return _hash_stable(s, salt=salt)

    def redacted_dict(self) -> dict[str, Any]:
        return grpc_call_summary(self)


@dataclass(frozen=True, slots=True)
class GrpcResponse:
    """
    gRPC response envelope.

    SAFETY:
      - message is suppressed from repr()
      - summaries do not include raw message bytes or decoded values
    """

    request_fingerprint: str
    status_code: int | None = None

    message: Any = field(default=None, repr=False)
    initial_metadata: Mapping[str, str] = field(default_factory=dict, repr=False)
    trailing_metadata: Mapping[str, str] = field(default_factory=dict, repr=False)

    stats: Mapping[str, Any] = field(default_factory=dict)
    meta: Mapping[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        try:
            return int(self.status_code or 0) == 0
        except Exception:
            return False

    def redacted_dict(self) -> dict[str, Any]:
        return grpc_response_summary(self)


def grpc_call_summary(call: GrpcCall) -> dict[str, Any]:
    """
    Log-safe summary for GrpcCall.
    """
    if not isinstance(call, GrpcCall):
        raise ProtocolValidationError(
            "grpc_call_summary expects GrpcCall",
            details={"type": type(call).__name__},
            context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.call.summary"),
        )
    return {
        "method": call.method.canonical(),
        "call_type": call.call_type,
        "fingerprint": call.fingerprint(),
        "message_shape": _shape_value(call.message),
        "metadata": _summarize_metadata(call.metadata),
        "timeout_s": call.timeout_s,
        "idempotent": call.idempotent,
        "meta": redact_mapping(call.meta),
    }


def grpc_response_summary(resp: GrpcResponse) -> dict[str, Any]:
    """
    Log-safe summary for GrpcResponse.
    """
    if not isinstance(resp, GrpcResponse):
        return {"type": type(resp).__name__}
    return {
        "request_fingerprint": resp.request_fingerprint,
        "status_code": resp.status_code,
        "status_name": grpc_status_name(resp.status_code),
        "ok": bool(resp.ok()),
        "message_shape": _shape_value(resp.message),
        "initial_metadata": _summarize_metadata(resp.initial_metadata),
        "trailing_metadata": _summarize_metadata(resp.trailing_metadata),
        "stats": redact_mapping(resp.stats),
        "meta": redact_mapping(resp.meta),
    }


# =============================================================================
# Error mapping helpers (used by raise_on_errors wrappers)
# =============================================================================


def _map_grpc_status_to_error(
    code: int | None,
    *,
    endpoint: ProtocolEndpoint | None,
    method: str,
    details: Mapping[str, Any] | None = None,
) -> ProtocolError:
    """
    Map gRPC status codes into Francis ProtocolError subclasses.
    """
    ctx = ProtocolErrorContext(
        protocol_id=GRPC_PROTOCOL_ID,
        operation=method,
        endpoint=endpoint,
        details=details or {},
    )

    try:
        c = int(code) if code is not None else 2  # UNKNOWN
    except Exception:
        c = 2

    if c == 0:
        return ProtocolError("ok", context=ctx, code="grpc_ok")

    if c == 16:
        return ProtocolAuthError("unauthenticated", context=ctx, code="grpc_unauthenticated")
    if c == 7:
        return ProtocolPermissionError("permission denied", context=ctx, code="grpc_permission_denied")
    if c == 5:
        return ProtocolNotFoundError("not found", context=ctx, code="grpc_not_found")
    if c == 6:
        return ProtocolError("already exists", context=ctx, code="grpc_already_exists")  # conflict-ish
    if c == 3 or c == 11:
        return ProtocolValidationError("invalid argument", context=ctx, code="grpc_invalid_argument")
    if c == 4:
        return ProtocolTimeoutError("deadline exceeded", context=ctx, code="grpc_deadline_exceeded")
    if c == 8:
        return ProtocolRateLimitError("resource exhausted", context=ctx, code="grpc_resource_exhausted")
    if c == 12:
        return ProtocolUnsupportedError("unimplemented", context=ctx, code="grpc_unimplemented")
    if c == 14:
        return ProtocolUnavailableError("unavailable", context=ctx, code="grpc_unavailable")

    # Default: generic error, retryable hint encoded in error type choice
    if is_retryable_grpc_status(c):
        return ProtocolUnavailableError("grpc transient error", context=ctx, code=f"grpc_{c}")
    return ProtocolError("grpc error", context=ctx, code=f"grpc_{c}")


# =============================================================================
# gRPC connector (delegates transport to registered "grpc" ProtocolConnector)
# =============================================================================


class GrpcProtocolConnector:
    """
    Typed gRPC adapter.

    Delegates actual transport/codec to an underlying ProtocolConnector registered under:
      - protocol_id="grpc"  (default)

    This adapter:
      - standardizes safe logging
      - provides a typed request/response envelope
      - provides convenience unary_unary wrappers
    """

    def __init__(
        self,
        *,
        target: str,
        grpc_protocol_id: str = GRPC_PROTOCOL_ID,
        default_metadata: Mapping[str, str] | None = None,
        backoff_policy: ProtocolBackoffPolicy | None = None,
        name: str = "gRPC Connector",
        version: str | None = None,
    ) -> None:
        normalized_target, tls = normalize_grpc_target(target)
        self._target = normalized_target
        self._tls = tls

        self._grpc_protocol_id = (grpc_protocol_id or GRPC_PROTOCOL_ID).strip().lower()
        self._default_metadata = normalize_grpc_metadata(default_metadata or {})
        self._backoff_policy = backoff_policy or ProtocolBackoffPolicy()
        self._name = name
        self._version = version

    @property
    def target(self) -> str:
        return self._target

    @property
    def tls(self) -> bool:
        return self._tls

    def _grpc(self) -> ProtocolConnector:
        try:
            return get_protocol_connector(self._grpc_protocol_id)
        except ProtocolNotFoundError as exc:
            raise ProtocolNotFoundError(
                f"gRPC adapter requires an underlying '{self._grpc_protocol_id}' protocol connector",
                context=ProtocolErrorContext(
                    protocol_id=GRPC_PROTOCOL_ID,
                    operation="grpc.resolve_transport",
                    details={"grpc_protocol_id": self._grpc_protocol_id},
                ),
                code="grpc_transport_not_registered",
                cause=exc,
            ) from exc

    # -------------------------------------------------------------------------
    # ProtocolConnector interface
    # -------------------------------------------------------------------------

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=GRPC_PROTOCOL_ID,
            name=self._name,
            version=self._version,
            description="Typed gRPC adapter (delegates transport/codec to registered 'grpc' ProtocolConnector).",
            capabilities=("request", "unary_unary", "health_check"),
            meta={
                "grpc_protocol_id": self._grpc_protocol_id,
                "target": self._target,
                "tls": self._tls,
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
        Health check is delegated to the underlying gRPC transport connector.

        The underlying connector can implement:
          - channel connectivity probes
          - gRPC Health Checking Protocol
          - reflection, etc.
        """
        ep = endpoint or ProtocolEndpoint(
            protocol_id=self._grpc_protocol_id,
            address=self._target,
            uri=f"{'grpcs' if self._tls else 'grpc'}://{self._target}",
            meta={"tls": self._tls},
        )
        h = self._grpc().health_check(endpoint=ep, identity=identity, timeout_s=timeout_s)
        # Enrich details without leaking secrets
        details = dict(h.details or {})
        details.update({"target": self._target, "tls": self._tls, "grpc_protocol_id": self._grpc_protocol_id})
        return ProtocolHealth(ok=h.ok, degraded=h.degraded, ts=h.ts, message=h.message, details=details)

    def request(
        self,
        req: ProtocolRequest,
        *,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolResponse:
        """
        Execute a gRPC request via the underlying transport connector.

        Interprets:
          - req.operation as the gRPC method ("/pkg.Service/Method")
          - req.payload as either:
              * GrpcCall, or
              * request message object/bytes/dict
        Returns:
          - ProtocolResponse(protocol_id="grpc") whose payload is GrpcResponse
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=GRPC_PROTOCOL_ID, operation="grpc.request"),
            )

        # Determine endpoint/target
        target = self._target
        tls = self._tls
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            t, t_tls = normalize_grpc_target(req.endpoint.uri or req.endpoint.address)
            target, tls = t, t_tls

        endpoint = ProtocolEndpoint(
            protocol_id=self._grpc_protocol_id,
            address=target,
            uri=f"{'grpcs' if tls else 'grpc'}://{target}",
            meta={"tls": tls, "adapter": "grpc_connector"},
        )

        # Coerce to GrpcCall
        if isinstance(req.payload, GrpcCall):
            call = req.payload
            method = call.method.canonical()
        else:
            method = normalize_grpc_method(req.operation)
            call = GrpcCall(
                method=GrpcMethodRef(full_method=method),
                call_type=_normalize_call_type(req.meta.get("call_type") if isinstance(req.meta, Mapping) else None),
                message=req.payload,
                metadata={},  # merged below
                timeout_s=req.timeout_s,
                idempotent=req.idempotent,
                meta={"caller_meta": redact_mapping(req.meta)},
            )

        # Merge metadata: defaults + request headers + call metadata
        merged_md: dict[str, str] = {}
        merged_md.update(self._default_metadata)
        merged_md.update(normalize_grpc_metadata(dict(req.headers) if req.headers else {}))
        merged_md.update(normalize_grpc_metadata(call.metadata))

        # Build underlying transport request
        transport_req = ProtocolRequest(
            protocol_id=self._grpc_protocol_id,
            operation=method,
            endpoint=endpoint,
            headers=merged_md,
            payload={
                "call_type": call.call_type,
                "message": call.message,
                # metadata also provided in headers; include shape-only hints for some transports
                "metadata_keys": sorted(merged_md.keys()),
            },
            idempotent=bool(call.idempotent) if call.idempotent is not None else bool(req.idempotent),
            expect_response=True,
            timeout_s=timeout_s if timeout_s is not None else (call.timeout_s or req.timeout_s),
            meta={
                "grpc": call.redacted_dict(),
                "adapter": "grpc_connector",
            },
        )

        transport_resp = self._grpc().request(transport_req, identity=identity, timeout_s=transport_req.timeout_s)

        # Try to interpret status code:
        status_code = transport_resp.status_code
        if status_code is None:
            # Best-effort: if transport ok, assume OK, else UNKNOWN
            status_code = 0 if transport_resp.ok else 2

        # Extract potential metadata if transport provided it (connector-defined)
        initial_md: Mapping[str, str] = {}
        trailing_md: Mapping[str, str] = {}
        try:
            if isinstance(transport_resp.meta, Mapping):
                im = transport_resp.meta.get("initial_metadata")
                tm = transport_resp.meta.get("trailing_metadata")
                if isinstance(im, Mapping):
                    initial_md = {str(k): str(v) for k, v in im.items()}
                if isinstance(tm, Mapping):
                    trailing_md = {str(k): str(v) for k, v in tm.items()}
        except Exception:
            initial_md = {}
            trailing_md = {}

        grpc_resp = GrpcResponse(
            request_fingerprint=call.fingerprint(),
            status_code=int(status_code),
            message=transport_resp.payload,
            initial_metadata=normalize_grpc_metadata(initial_md),
            trailing_metadata=normalize_grpc_metadata(trailing_md),
            stats=redact_mapping(
                {
                    "transport_protocol_id": self._grpc_protocol_id,
                    "transport_ok": bool(transport_resp.ok),
                    "grpc_status": int(status_code),
                    "grpc_status_name": grpc_status_name(int(status_code)),
                    "retryable_status": bool(is_retryable_grpc_status(int(status_code))),
                }
            ),
            meta=redact_mapping(
                {
                    "target": target,
                    "tls": tls,
                    "method": method,
                    "call_fingerprint": call.fingerprint(),
                }
            ),
        )

        ok = bool(grpc_resp.ok())

        return ProtocolResponse(
            protocol_id=GRPC_PROTOCOL_ID,
            ok=ok,
            status_code=int(status_code),
            headers=transport_resp.headers,
            payload=grpc_resp,
            stats=redact_mapping(
                {
                    "grpc_ok": bool(ok),
                    "grpc_status_name": grpc_status_name(int(status_code)),
                    "grpc_method": method,
                    "grpc_request_fingerprint": call.fingerprint(),
                }
            ),
            ts=transport_resp.ts,
            meta=redact_mapping(req.meta),
        )

    # -------------------------------------------------------------------------
    # Convenience helpers
    # -------------------------------------------------------------------------

    def unary_unary(
        self,
        method: str,
        message: Any,
        *,
        metadata: Mapping[str, str] | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
        raise_on_errors: bool = True,
    ) -> ProtocolResponse:
        """
        Convenience unary-unary call.

        If raise_on_errors=True, converts non-OK gRPC statuses to ProtocolError subclasses.
        """
        call = GrpcCall(
            method=GrpcMethodRef(full_method=method),
            call_type="unary_unary",
            message=message,
            metadata=metadata or {},
            timeout_s=timeout_s,
            idempotent=True,  # default safe hint
        )
        req = ProtocolRequest(
            protocol_id=GRPC_PROTOCOL_ID,
            operation=call.method.canonical(),
            endpoint=ProtocolEndpoint(
                protocol_id=GRPC_PROTOCOL_ID,
                address=self._target,
                uri=f"{'grpcs' if self._tls else 'grpc'}://{self._target}",
            ),
            headers=call.metadata,
            payload=call,
            idempotent=True,
            expect_response=True,
            timeout_s=timeout_s,
            meta={},
        )
        resp = self.request(req, identity=identity, timeout_s=timeout_s)

        if not raise_on_errors:
            return resp

        payload = resp.payload
        if isinstance(payload, GrpcResponse) and not payload.ok():
            raise _map_grpc_status_to_error(
                payload.status_code,
                endpoint=req.endpoint,
                method=call.method.canonical(),
                details={
                    "grpc_call": call.redacted_dict(),
                    "grpc_response": payload.redacted_dict(),
                },
            )

        if not resp.ok:
            # Fallback unknown failure
            raise ProtocolError(
                "grpc call failed",
                context=ProtocolErrorContext(
                    protocol_id=GRPC_PROTOCOL_ID,
                    operation=call.method.canonical(),
                    endpoint=req.endpoint,
                    details={"grpc_call": call.redacted_dict()},
                ),
                code="grpc_failed",
            )

        return resp
