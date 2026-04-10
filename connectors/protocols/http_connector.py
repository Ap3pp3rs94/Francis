"""
===============================================================================
Francis 2.0 — Protocol Connectors (HTTP/HTTPS Connector)
Path: connectors/protocols/http_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a synchronous HTTP/HTTPS ProtocolConnector using ONLY the
Python standard library (urllib).

It provides:
  - HttpProtocolConnector implementing ProtocolConnector:
      * info()
      * health_check()
      * request()  (supports operation parsing like "GET /path" or "POST https://...")

  - Safe-by-default behaviors:
      * Never logs raw request/response bodies
      * Header redaction helpers are applied in summaries/stats
      * Limits response body size (configurable)
      * Defaults Accept-Encoding to "identity" to avoid compressed payload surprises
      * Optional JSON decoding ("auto" by Content-Type)

  - Minimal retry handling:
      * Retries only for idempotent requests
      * Retries only for retryable statuses (429/408/5xx gateway-ish) and network/timeouts
      * Uses ProtocolBackoffPolicy + compute_backoff_s() for backoff
      * Honors Retry-After (seconds) for 429 when present

This module intentionally does NOT:
  - Provide async support
  - Provide HTTP/2
  - Provide cookie jar/session persistence
  - Provide connection pooling beyond urllib defaults
  - Implement any authentication schemes (Bearer, OAuth, etc.) beyond passing headers

===============================================================================
"""

from __future__ import annotations

import json
import socket
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Mapping, MutableMapping
from dataclasses import dataclass, field
from typing import Any

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
    ProtocolValidationError,
    compute_backoff_s,
    redact_mapping,
    redact_uri,
    redact_value,
)

__all__ = [
    "HTTP_PROTOCOL_ID",
    "HTTPS_PROTOCOL_ID",
    "HttpConnectorConfig",
    "HttpProtocolConnector",
    "normalize_http_method",
    "parse_http_operation",
    "join_base_url",
]


HTTP_PROTOCOL_ID = "http"
HTTPS_PROTOCOL_ID = "https"

# Retryable HTTP status codes (common practice)
_RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}


# =============================================================================
# Helpers: operation parsing + URL building
# =============================================================================

_HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "HEAD",
    "OPTIONS",
}


def normalize_http_method(method: str) -> str:
    m = (method or "").strip().upper()
    if not m:
        raise ProtocolValidationError(
            "http method is required",
            details={"field": "method"},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_method"),
        )
    if m not in _HTTP_METHODS:
        raise ProtocolValidationError(
            "unsupported http method",
            details={"method": redact_value(m), "allowed": sorted(_HTTP_METHODS)},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_method"),
        )
    return m


def parse_http_operation(operation: str) -> tuple[str, str | None]:
    """
    Parse ProtocolRequest.operation into (method, url_or_path?).

    Supported patterns:
      - "GET"                    -> method=GET, url_or_path=None
      - "GET /v1/items"          -> method=GET, url_or_path="/v1/items"
      - "POST https://x/y"       -> method=POST, url_or_path="https://x/y"
    """
    op = (operation or "").strip()
    if not op:
        raise ProtocolValidationError(
            "operation is required (expected HTTP method)",
            details={"field": "operation"},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.parse_operation"),
        )
    if "\x00" in op or "\r" in op or "\n" in op:
        raise ProtocolValidationError(
            "operation contains illegal control characters",
            details={"operation": redact_value(op)},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.parse_operation"),
        )

    parts = op.split(None, 1)
    method = normalize_http_method(parts[0])
    url_or_path = parts[1].strip() if len(parts) > 1 else None
    return method, (url_or_path if url_or_path else None)


def _is_absolute_http_url(s: str) -> bool:
    try:
        p = urllib.parse.urlsplit(s)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False


def join_base_url(base_url: str, url_or_path: str) -> str:
    """
    Join a base URL with a relative path (or return absolute URL unchanged).

    - If url_or_path is absolute (http/https), return it.
    - If url_or_path starts with "/", it replaces the base path.
    - If url_or_path is relative (no leading "/"), it is appended to base path.
    - If url_or_path includes a query string, it's respected.
    """
    if _is_absolute_http_url(url_or_path):
        return url_or_path

    base = (base_url or "").strip()
    if not _is_absolute_http_url(base):
        raise ProtocolValidationError(
            "base_url must be absolute http(s) url",
            details={"base_url": redact_value(base)},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.join_base_url"),
        )

    # Split relative piece (may include query)
    rel_parts = urllib.parse.urlsplit(url_or_path)
    rel_path = rel_parts.path or ""
    rel_query = rel_parts.query or ""

    b = urllib.parse.urlsplit(base)
    base_path = b.path or "/"

    if rel_path.startswith("/"):
        new_path = rel_path
    else:
        # Append to base directory
        if not base_path.endswith("/"):
            base_dir = base_path.rsplit("/", 1)[0] + "/"
        else:
            base_dir = base_path
        new_path = urllib.parse.urljoin(base_dir, rel_path)

    # Prefer relative query if provided; otherwise keep base query.
    new_query = rel_query if rel_query else (b.query or "")

    return urllib.parse.urlunsplit((b.scheme, b.netloc, new_path, new_query, ""))


def _normalize_url(url: str) -> str:
    """
    Validate URL is http/https and strip CRLF/NUL.

    NOTE: We do NOT strip query here; callers may need it. Logs must use redact_uri().
    """
    s = (url or "").strip()
    if not s:
        raise ProtocolValidationError(
            "url is required",
            details={"field": "url"},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_url"),
        )
    if "\x00" in s or "\r" in s or "\n" in s:
        raise ProtocolValidationError(
            "url contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_url"),
        )
    try:
        p = urllib.parse.urlsplit(s)
    except Exception as exc:  # noqa: BLE001
        raise ProtocolValidationError(
            "url is invalid",
            details={"url": redact_value(s)},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_url"),
            cause=exc,
        ) from exc
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ProtocolValidationError(
            "url must be absolute http(s)",
            details={"url": redact_value(s)},
            context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.normalize_url"),
        )
    return s


def _validate_headers(headers: Mapping[str, str] | None) -> dict[str, str]:
    """
    Validate headers contain no control characters.
    """
    if not headers:
        return {}

    out: dict[str, str] = {}
    for k, v in headers.items():
        kk = ("" if k is None else str(k)).strip()
        if not kk:
            raise ProtocolValidationError(
                "header name cannot be empty",
                context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.validate_headers"),
            )
        vv = "" if v is None else str(v)

        # Prevent header injection
        if "\r" in kk or "\n" in kk or "\x00" in kk:
            raise ProtocolValidationError(
                "header name contains illegal control characters",
                details={"header": redact_value(kk)},
                context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.validate_headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise ProtocolValidationError(
                "header value contains illegal control characters",
                details={"header": redact_value(kk)},
                context=ProtocolErrorContext(protocol_id=HTTP_PROTOCOL_ID, operation="http.validate_headers"),
            )

        out[kk] = vv
    return out


# =============================================================================
# Config
# =============================================================================


@dataclass(frozen=True, slots=True)
class HttpConnectorConfig:
    """
    Configuration for HttpProtocolConnector.
    """

    protocol_id: str = HTTPS_PROTOCOL_ID  # register separately as "http" or "https"
    user_agent: str = "Francis/2.0 (stdlib urllib)"
    default_headers: Mapping[str, str] = field(default_factory=dict)

    # Response limits
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    # JSON decoding:
    #   - "auto": decode only when Content-Type indicates json
    #   - True: always attempt JSON decode when body exists
    #   - False: never decode (return bytes)
    decode_json: str | bool = "auto"

    # Default timeout for urlopen (seconds) if none provided
    default_timeout_s: float = 30.0

    # Retry policy (applies ONLY if request.idempotent is True)
    backoff_policy: ProtocolBackoffPolicy = field(default_factory=ProtocolBackoffPolicy)

    # TLS verification (applies to https)
    verify_tls: bool = True
    ca_file: str | None = None  # optional custom CA bundle path (use with verify_tls=True)


# =============================================================================
# HTTP Connector
# =============================================================================


class HttpProtocolConnector:
    """
    Synchronous HTTP/HTTPS connector using Python stdlib urllib.

    This class can be instantiated with protocol_id="http" or "https".
    It can still send to both schemes, but registry lookups should match the id.
    """

    def __init__(self, config: HttpConnectorConfig | None = None) -> None:
        self._cfg = config or HttpConnectorConfig()
        self._protocol_id = (self._cfg.protocol_id or HTTPS_PROTOCOL_ID).strip().lower()

        # Prepare SSL context (only used for https requests)
        self._ssl_context: ssl.SSLContext | None = None
        try:
            if self._cfg.verify_tls:
                self._ssl_context = ssl.create_default_context(cafile=self._cfg.ca_file)
            else:
                # Insecure; allowed for controlled internal usage only.
                self._ssl_context = ssl._create_unverified_context()  # noqa: SLF001
        except Exception:
            # If SSL context creation fails, keep None and let urllib default handle it.
            self._ssl_context = None

        # Normalize defaults safely
        self._default_headers = _validate_headers(dict(self._cfg.default_headers) if self._cfg.default_headers else {})

        if self._cfg.max_response_bytes <= 0:
            raise ProtocolValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self._cfg.max_response_bytes},
                context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.config.validate"),
            )

        if self._cfg.default_timeout_s <= 0:
            raise ProtocolValidationError(
                "default_timeout_s must be > 0",
                details={"default_timeout_s": self._cfg.default_timeout_s},
                context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.config.validate"),
            )

    # -------------------------------------------------------------------------
    # ProtocolConnector interface
    # -------------------------------------------------------------------------

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=self._protocol_id,
            name="HTTP Connector",
            version=None,
            description="Synchronous HTTP/HTTPS connector using stdlib urllib.",
            capabilities=("request", "health_check", "json_auto_decode", "idempotent_retry"),
            meta={
                "max_response_bytes": self._cfg.max_response_bytes,
                "decode_json": self._cfg.decode_json,
                "default_timeout_s": self._cfg.default_timeout_s,
                "verify_tls": bool(self._cfg.verify_tls),
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
        Lightweight health check.

        - If endpoint is provided, performs a HEAD request to endpoint.uri/address.
        - If no endpoint provided, returns ok=True but degraded=True (generic connector).
        """
        if endpoint is None or not (endpoint.uri or endpoint.address):
            return ProtocolHealth(
                ok=True,
                degraded=True,
                message="no endpoint provided (generic http connector)",
                details={"protocol_id": self._protocol_id},
            )

        url = _normalize_url(endpoint.uri or endpoint.address)
        try:
            req = ProtocolRequest(
                protocol_id=self._protocol_id,
                operation="HEAD",
                endpoint=ProtocolEndpoint(protocol_id=self._protocol_id, address=url, uri=url),
                headers={},
                payload=None,
                idempotent=True,
                expect_response=True,
                timeout_s=timeout_s,
                meta={"health_check": True},
            )
            resp = self.request(req, identity=identity, timeout_s=timeout_s)
            return ProtocolHealth(
                ok=bool(resp.ok),
                degraded=False if resp.ok else True,
                message="ok" if resp.ok else "failed",
                details={
                    "url": redact_uri(url),
                    "status_code": resp.status_code,
                    "stats": redact_mapping(resp.stats),
                },
            )
        except Exception as exc:  # noqa: BLE001
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={"url": redact_uri(url), "error": redact_value(str(exc))},
            )

    def request(
        self,
        req: ProtocolRequest,
        *,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolResponse:
        """
        Execute an HTTP request.

        Behavior:
          - Returns ProtocolResponse always for HTTP status outcomes (including 4xx/5xx).
          - Raises ProtocolTimeoutError / ProtocolNetworkError for transport failures.
          - Retries only if req.idempotent is True.

        URL resolution precedence:
          1) operation may include method + absolute URL/path
          2) req.endpoint.uri/address used as base or full URL
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.request"),
            )

        method, url_or_path = parse_http_operation(req.operation)

        base_url = None
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            base_url = (req.endpoint.uri or req.endpoint.address).strip()

        if url_or_path:
            if _is_absolute_http_url(url_or_path):
                url = _normalize_url(url_or_path)
            else:
                if not base_url:
                    raise ProtocolValidationError(
                        "relative path provided in operation but no endpoint base url provided",
                        details={"operation": redact_value(req.operation)},
                        context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.request"),
                    )
                url = _normalize_url(join_base_url(base_url, url_or_path))
        else:
            if not base_url:
                raise ProtocolValidationError(
                    "no url provided (endpoint required when operation has no url/path)",
                    details={"operation": redact_value(req.operation)},
                    context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.request"),
                )
            url = _normalize_url(base_url)

        # Merge headers: connector defaults -> request headers
        headers: dict[str, str] = {}
        headers.update(self._default_headers)
        headers.update(_validate_headers(dict(req.headers) if req.headers else {}))

        # Safe defaults
        headers.setdefault("User-Agent", self._cfg.user_agent)
        headers.setdefault("Accept", "*/*")
        # Avoid automatic compression to keep response decoding predictable.
        headers.setdefault("Accept-Encoding", "identity")

        # Prepare body
        body_bytes, content_type = self._prepare_body(req.payload, headers=headers)

        # Some methods typically shouldn't send bodies; we don't enforce, but it's up to caller.
        timeout = float(
            timeout_s
            if timeout_s is not None
            else (req.timeout_s if req.timeout_s is not None else self._cfg.default_timeout_s)
        )
        if timeout <= 0:
            raise ProtocolValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": timeout},
                context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.request"),
            )

        # Retry loop (idempotent only)
        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        idempotent = bool(req.idempotent)

        attempt = 0

        while True:
            try:
                resp = self._send_once(
                    method=method,
                    url=url,
                    headers=headers,
                    body=body_bytes,
                    timeout_s=timeout,
                    decode_json=self._cfg.decode_json,
                    max_response_bytes=self._cfg.max_response_bytes,
                )

                if resp.ok:
                    return resp

                # Retry if eligible
                if idempotent and self._should_retry_status(resp.status_code):
                    attempt += 1
                    if attempt > max_attempts:
                        return resp
                    delay = self._retry_delay_s(resp.headers, policy=policy, attempt=attempt)
                    time.sleep(delay)
                    continue

                return resp

            except (ProtocolTimeoutError, ProtocolNetworkError):
                # Retry transport errors only if idempotent
                if idempotent:
                    attempt += 1
                    if attempt > max_attempts:
                        raise
                    delay = compute_backoff_s(policy, attempt=attempt)
                    time.sleep(delay)
                    continue
                raise

    # -------------------------------------------------------------------------
    # Internals
    # -------------------------------------------------------------------------

    def _prepare_body(self, payload: Any, *, headers: MutableMapping[str, str]) -> tuple[bytes | None, str | None]:
        """
        Convert payload to bytes for urllib.

        Rules:
          - None => None
          - bytes/bytearray => bytes
          - str => utf-8 bytes
          - Mapping/list => JSON bytes (sets Content-Type if missing)
          - other => try JSON serialization, else error
        """
        if payload is None:
            return None, None

        if isinstance(payload, (bytes, bytearray)):
            b = bytes(payload)
            if "Content-Type" not in headers and "content-type" not in {k.lower() for k in headers.keys()}:
                headers.setdefault("Content-Type", "application/octet-stream")
            return b, headers.get("Content-Type")

        if isinstance(payload, str):
            b = payload.encode("utf-8")
            if "Content-Type" not in headers and "content-type" not in {k.lower() for k in headers.keys()}:
                headers.setdefault("Content-Type", "text/plain; charset=utf-8")
            return b, headers.get("Content-Type")

        # JSON-ish payloads
        if isinstance(payload, (Mapping, list, tuple)):
            try:
                s = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolSerializationError(
                    "failed to JSON-encode request payload",
                    context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.prepare_body"),
                    code="json_encode_error",
                    cause=exc,
                ) from exc
            b = s.encode("utf-8")
            if "Content-Type" not in headers and "content-type" not in {k.lower() for k in headers.keys()}:
                headers.setdefault("Content-Type", "application/json; charset=utf-8")
            return b, headers.get("Content-Type")

        # Fallback: try to serialize as JSON
        try:
            s = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=False)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolSerializationError(
                "unsupported request payload type (not bytes/str/mapping/sequence/json-serializable)",
                context=ProtocolErrorContext(
                    protocol_id=self._protocol_id,
                    operation="http.prepare_body",
                    details={"payload_type": type(payload).__name__},
                ),
                code="unsupported_payload",
                cause=exc,
            ) from exc
        b = s.encode("utf-8")
        if "Content-Type" not in headers and "content-type" not in {k.lower() for k in headers.keys()}:
            headers.setdefault("Content-Type", "application/json; charset=utf-8")
        return b, headers.get("Content-Type")

    def _send_once(
        self,
        *,
        method: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_s: float,
        decode_json: str | bool,
        max_response_bytes: int,
    ) -> ProtocolResponse:
        """
        Send a single HTTP request attempt.

        Returns ProtocolResponse for all HTTP statuses.
        Raises ProtocolTimeoutError / ProtocolNetworkError for transport failures.
        Raises ProtocolSerializationError for JSON decode failures when enabled.
        """
        start_ns = time.time_ns()

        # urllib expects headers as dict-like; method supported in Request
        ureq = urllib.request.Request(url=url, data=body, method=method, headers=dict(headers))

        # Select SSL context only for https URLs
        scheme = urllib.parse.urlsplit(url).scheme.lower()
        ctx = self._ssl_context if scheme == "https" else None

        try:
            with urllib.request.urlopen(ureq, timeout=timeout_s, context=ctx) as resp:
                status = int(getattr(resp, "status", resp.getcode()))
                resp_headers = self._headers_to_dict(resp.headers)
                raw_body, truncated = self._read_limited(resp, max_bytes=max_response_bytes)
                payload = self._decode_response_payload(raw_body, resp_headers, decode_json=decode_json)

                duration_ms = (time.time_ns() - start_ns) / 1_000_000.0
                ok = status < 400

                return ProtocolResponse(
                    protocol_id=self._protocol_id,
                    ok=ok,
                    status_code=status,
                    headers=resp_headers,
                    payload=payload,
                    stats=redact_mapping(
                        {
                            "method": method,
                            "url": redact_uri(url),
                            "duration_ms": round(duration_ms, 3),
                            "bytes_read": len(raw_body),
                            "truncated": bool(truncated),
                        }
                    ),
                    ts=int(time.time()),
                    meta={},
                )

        except urllib.error.HTTPError as he:
            # HTTPError is a valid response with status+body.
            status = int(getattr(he, "code", 0) or 0)
            resp_headers = self._headers_to_dict(getattr(he, "headers", None))
            try:
                raw_body, truncated = self._read_limited(he, max_bytes=max_response_bytes)
            except Exception:
                raw_body, truncated = b"", False

            # Decode JSON optionally even for 4xx/5xx (useful for API error payloads).
            payload = self._decode_response_payload(raw_body, resp_headers, decode_json=decode_json)

            duration_ms = (time.time_ns() - start_ns) / 1_000_000.0
            ok = status < 400

            return ProtocolResponse(
                protocol_id=self._protocol_id,
                ok=ok,
                status_code=status,
                headers=resp_headers,
                payload=payload,
                stats=redact_mapping(
                    {
                        "method": method,
                        "url": redact_uri(url),
                        "duration_ms": round(duration_ms, 3),
                        "bytes_read": len(raw_body),
                        "truncated": bool(truncated),
                        "http_error": True,
                    }
                ),
                ts=int(time.time()),
                meta={},
            )

        except urllib.error.URLError as ue:
            # URLError wraps many network issues
            reason = getattr(ue, "reason", None)
            if isinstance(reason, socket.timeout) or "timed out" in str(reason).lower():
                raise ProtocolTimeoutError(
                    "http request timed out",
                    context=ProtocolErrorContext(
                        protocol_id=self._protocol_id,
                        operation="http.urlopen",
                        details={"url": redact_uri(url), "method": method},
                    ),
                    code="timeout",
                    cause=ue,
                ) from ue

            raise ProtocolNetworkError(
                "http network error",
                context=ProtocolErrorContext(
                    protocol_id=self._protocol_id,
                    operation="http.urlopen",
                    details={
                        "url": redact_uri(url),
                        "method": method,
                        "reason": redact_value(str(reason)),
                    },
                ),
                code="network_error",
                cause=ue,
            ) from ue

        except TimeoutError as se:
            raise ProtocolTimeoutError(
                "http request timed out",
                context=ProtocolErrorContext(
                    protocol_id=self._protocol_id,
                    operation="http.urlopen",
                    details={"url": redact_uri(url), "method": method},
                ),
                code="timeout",
                cause=se,
            ) from se

        except ssl.SSLError as ssle:
            raise ProtocolNetworkError(
                "tls/ssl error",
                context=ProtocolErrorContext(
                    protocol_id=self._protocol_id,
                    operation="http.tls",
                    details={"url": redact_uri(url), "method": method},
                ),
                code="ssl_error",
                cause=ssle,
            ) from ssle

    def _headers_to_dict(self, headers_obj: Any) -> dict[str, str]:
        """
        Convert urllib headers to a plain dict[str,str].
        """
        if not headers_obj:
            return {}
        out: dict[str, str] = {}
        try:
            # email.message.Message provides items()
            for k, v in headers_obj.items():
                out[str(k)] = str(v)
        except Exception:
            # Fallback best-effort
            try:
                out = dict(headers_obj)  # type: ignore[arg-type]
            except Exception:
                out = {}
        return out

    def _read_limited(self, fp: Any, *, max_bytes: int) -> tuple[bytes, bool]:
        """
        Read up to max_bytes (+1 sentinel) from a file-like response.

        Returns: (bytes, truncated)
        """
        if max_bytes <= 0:
            return b"", False
        try:
            data = fp.read(max_bytes + 1)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolNetworkError(
                "failed to read http response body",
                context=ProtocolErrorContext(protocol_id=self._protocol_id, operation="http.read_body"),
                code="read_error",
                cause=exc,
            ) from exc

        if data is None:
            return b"", False
        b = bytes(data)
        if len(b) > max_bytes:
            return b[:max_bytes], True
        return b, False

    def _decode_response_payload(self, body: bytes, headers: Mapping[str, str], *, decode_json: str | bool) -> Any:
        """
        Decode response payload:
          - decode_json=False -> return bytes
          - decode_json=True  -> always attempt JSON decode if body exists
          - decode_json="auto" -> decode if Content-Type indicates json
        """
        if not body:
            return None

        mode = decode_json
        if mode == "auto":
            ct = ""
            for k, v in (headers or {}).items():
                if str(k).lower() == "content-type":
                    ct = str(v).lower()
                    break
            wants_json = ("application/json" in ct) or ("+json" in ct)
            if not wants_json:
                return body
            mode = True

        if mode is False:
            return body

        # Attempt JSON decode (strict UTF-8 decode)
        try:
            text = body.decode("utf-8")
            return json.loads(text)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolSerializationError(
                "failed to decode JSON response",
                context=ProtocolErrorContext(
                    protocol_id=self._protocol_id,
                    operation="http.decode_json",
                    details={"content_type": redact_value(str(headers.get("Content-Type", "")))},
                ),
                code="json_decode_error",
                cause=exc,
            ) from exc

    def _should_retry_status(self, status_code: int | None) -> bool:
        try:
            sc = int(status_code) if status_code is not None else 0
        except Exception:
            return False
        return sc in _RETRYABLE_STATUS

    def _retry_delay_s(self, headers: Mapping[str, str], *, policy: ProtocolBackoffPolicy, attempt: int) -> float:
        """
        Compute retry delay:
          - If Retry-After present and parseable for 429, prefer it (bounded).
          - Else use exponential backoff policy.
        """
        # Retry-After is meaningful for 429 (and sometimes 503); use it if safe.
        ra = None
        for k, v in (headers or {}).items():
            if str(k).lower() == "retry-after":
                ra = str(v).strip()
                break
        if ra:
            try:
                sec = int(float(ra))
                if sec >= 0:
                    # Bound by policy.max_s to avoid huge sleeps from untrusted headers
                    return float(min(sec, policy.max_s))
            except Exception:
                pass
        return compute_backoff_s(policy, attempt=attempt)
