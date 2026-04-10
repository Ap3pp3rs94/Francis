"""
===============================================================================
Francis 2.0 — Protocol Connectors (GraphQL Connector)
Path: connectors/protocols/graphql_connector.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a *GraphQL-over-HTTP* connector as a thin adapter on top of
the generic protocol contract in connectors/protocols/__init__.py.

Key idea:
  - GraphQL is not a transport; it's a query language typically delivered over HTTP.
  - We avoid embedding a concrete HTTP client dependency here.
  - Instead, this connector delegates actual network transport to a registered
    "http" or "https" ProtocolConnector (implementation lives elsewhere).

Provides:
  - Stable GraphQL request/response types (safe-by-default: no query text in logs)
  - A GraphQLProtocolConnector implementing ProtocolConnector:
      * info()
      * health_check()
      * request()  -> returns ProtocolResponse whose payload is GraphQLResponse
      * execute()/query()/mutate() convenience methods (optionally raise on errors)
  - Observability helpers:
      * query fingerprinting (hash + length)
      * variables summaries (types/len/hash; never raw values)
      * GraphQL error summaries (count + extension codes; never raw messages)

Safety rules:
  - Never log raw query text.
  - Never log raw variable values.
  - Normalize endpoints to strip userinfo/query/fragment to avoid accidental secrets in URLs.

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
    ProtocolSerializationError,
    ProtocolUnavailableError,
    ProtocolValidationError,
    get_protocol_connector,
    redact_mapping,
    redact_value,
)

__all__ = [
    "GRAPHQL_PROTOCOL_ID",
    "GraphQLOperationType",
    "GraphQLRequest",
    "GraphQLResponse",
    "GraphQLProtocolConnector",
    "normalize_graphql_endpoint_url",
    "detect_graphql_operation_type",
    "graphql_request_summary",
    "graphql_response_summary",
]


GRAPHQL_PROTOCOL_ID = "graphql"

GraphQLOperationType = str  # "query" | "mutation" | "subscription"


# =============================================================================
# Small hashing + summaries (safe for logs)
# =============================================================================


def _hash_stable(value: str, *, salt: str = "francis") -> str:
    v = (value or "").encode("utf-8", errors="ignore")
    s = (salt or "").encode("utf-8", errors="ignore")
    return hashlib.sha256(s + b":" + v).hexdigest()[:12]


def _shape_value(v: Any) -> dict[str, Any]:
    """
    Summarize a value without returning it.
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
        return {"type": "bytes", "len": len(b), "hash": _hash_stable(b[:256].hex())}
    if isinstance(v, Mapping):
        return {"type": "object", "keys": len(v)}
    if isinstance(v, Sequence) and not isinstance(v, (str, bytes, bytearray)):
        return {"type": "array", "len": len(v)}
    # fallback
    try:
        s = str(v)
    except Exception:
        s = type(v).__name__
    return {"type": type(v).__name__, "hash": _hash_stable(s)}


def _summarize_variables(variables: Mapping[str, Any] | None, *, max_keys: int = 50) -> dict[str, Any]:
    """
    Log-safe summary of GraphQL variables.

    - Keys are preserved (keep your variable names clean).
    - Values are represented by type/len/hash only.
    """
    if not variables:
        return {"count": 0, "items": {}}
    if not isinstance(variables, Mapping):
        return {"count": 1, "items": {"<non_mapping>": {"type": type(variables).__name__}}}

    keys = sorted(str(k) for k in variables.keys())
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
            items[kk] = _shape_value(variables.get(k))
        except Exception:
            items[kk] = {"type": "error"}

    if truncated:
        items["…"] = {"truncated": True}

    return {"count": len(variables), "items": items}


def _summarize_graphql_errors(errors: Any, *, max_items: int = 20) -> dict[str, Any]:
    """
    Log-safe summary of GraphQL errors.

    GraphQL errors commonly include:
      - message (may contain sensitive text)
      - path, locations (generally safe)
      - extensions.code (useful for triage)

    We do NOT return raw messages; we hash them.
    """
    if not errors:
        return {"count": 0, "codes": [], "message_hashes": []}
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes, bytearray)):
        return {"count": 1, "codes": [], "message_hashes": []}

    codes: set[str] = set()
    msg_hashes: list[str] = []
    n = len(errors)
    sample_n = min(n, max_items)

    for i in range(sample_n):
        try:
            e = errors[i]  # type: ignore[index]
            if isinstance(e, Mapping):
                msg = "" if e.get("message") is None else str(e.get("message"))
                if msg:
                    msg_hashes.append(_hash_stable(msg))
                ext = e.get("extensions")
                if isinstance(ext, Mapping):
                    c = ext.get("code")
                    if c is not None:
                        codes.add(str(c))
        except Exception:
            continue

    return {
        "count": n,
        "sampled": sample_n,
        "codes": sorted(codes)[:50],
        "message_hashes": msg_hashes[:max_items],
    }


# =============================================================================
# Endpoint normalization (strip secrets from URL forms)
# =============================================================================


def normalize_graphql_endpoint_url(endpoint_url: str) -> str:
    """
    Normalize a GraphQL endpoint URL into a safe form:

    - Requires http or https scheme
    - Removes userinfo (username:password@)
    - Drops query params and fragments
    - Preserves host, port, and path

    This intentionally prevents "token in URL" patterns from sneaking into logs.
    """
    raw = (endpoint_url or "").strip()
    if not raw:
        raise ProtocolValidationError(
            "graphql endpoint_url is required",
            details={"field": "endpoint_url"},
            context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.normalize_endpoint"),
        )
    if "\x00" in raw or "\r" in raw or "\n" in raw:
        raise ProtocolValidationError(
            "graphql endpoint_url contains illegal control characters",
            context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.normalize_endpoint"),
        )

    parts = urlsplit(raw)
    scheme = (parts.scheme or "").lower()
    if scheme not in ("http", "https"):
        raise ProtocolValidationError(
            "graphql endpoint_url must be http(s)",
            details={"scheme": redact_value(scheme)},
            context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.normalize_endpoint"),
        )

    host = parts.hostname
    if not host:
        raise ProtocolValidationError(
            "graphql endpoint_url missing host",
            details={"endpoint_url": redact_value(raw)},
            context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.normalize_endpoint"),
        )

    netloc = host
    if parts.port:
        netloc = f"{host}:{parts.port}"

    path = parts.path or "/"
    # Strip query + fragment
    safe = urlunsplit((scheme, netloc, path, "", ""))
    return safe


# =============================================================================
# GraphQL request/response types
# =============================================================================

_GQL_COMMENT_RE = re.compile(r"^\s*#.*?$", re.MULTILINE)


def detect_graphql_operation_type(query_text: str) -> GraphQLOperationType:
    """
    Best-effort detection of GraphQL operation type from query text.

    Rules:
      - Strips leading comments (# ...) and whitespace
      - Looks for leading keyword: query|mutation|subscription
      - Defaults to "query"

    Not a security boundary; used for idempotency hints.
    """
    q = "" if query_text is None else str(query_text)
    q = _GQL_COMMENT_RE.sub("", q).lstrip()
    if not q:
        return "query"
    m = re.match(r"^(query|mutation|subscription)\b", q, flags=re.IGNORECASE)
    if not m:
        return "query"
    return m.group(1).lower()


@dataclass(frozen=True, slots=True)
class GraphQLRequest:
    """
    GraphQL request model.

    SAFETY:
      - query text and variables are suppressed from repr()
      - use redacted_dict()/graphql_request_summary() for log-safe views
    """

    query: str = field(repr=False)
    variables: Mapping[str, Any] = field(default_factory=dict, repr=False)
    operation_name: str | None = None
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    # Derived hint (query/mutation/subscription)
    operation_type: GraphQLOperationType = field(default="query")

    # Connector hints
    timeout_s: float | None = None
    meta: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        q = "" if self.query is None else str(self.query)
        if "\x00" in q:
            raise ProtocolValidationError(
                "graphql query contains NUL",
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request.validate"),
            )
        if len(q) > 2_000_000:
            raise ProtocolValidationError(
                "graphql query too large",
                details={"query_len": len(q), "max": 2_000_000},
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request.validate"),
            )
        object.__setattr__(self, "query", q)

        ot = detect_graphql_operation_type(q)
        object.__setattr__(self, "operation_type", ot)

        if self.timeout_s is not None:
            try:
                ts = float(self.timeout_s)
            except Exception as exc:  # noqa: BLE001
                raise ProtocolValidationError(
                    "timeout_s must be numeric",
                    details={"timeout_s": redact_value(str(self.timeout_s))},
                    context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request.validate"),
                ) from exc
            if ts <= 0:
                raise ProtocolValidationError(
                    "timeout_s must be > 0",
                    details={"timeout_s": ts},
                    context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request.validate"),
                )
            object.__setattr__(self, "timeout_s", ts)

    def is_idempotent(self) -> bool:
        # Queries are typically idempotent; mutations not.
        return self.operation_type != "mutation"

    def fingerprint(self, *, salt: str = "francis") -> str:
        payload = {
            "query_hash": _hash_stable(self.query, salt=salt),
            "query_len": len(self.query),
            "operation_name": self.operation_name or "",
            "operation_type": self.operation_type,
            "variables": _summarize_variables(self.variables),
            "extensions_shape": _shape_value(self.extensions),
        }
        s = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return _hash_stable(s, salt=salt)

    def to_http_json(self) -> dict[str, Any]:
        body: dict[str, Any] = {"query": self.query}
        if self.variables:
            body["variables"] = self.variables
        if self.operation_name:
            body["operationName"] = self.operation_name
        if self.extensions:
            body["extensions"] = self.extensions
        return body

    def redacted_dict(self) -> dict[str, Any]:
        return graphql_request_summary(self)


@dataclass(frozen=True, slots=True)
class GraphQLResponse:
    """
    GraphQL response model.

    SAFETY:
      - data/errors are suppressed from repr()
      - redacted_dict() summarizes only shapes + error codes/hashes
    """

    request_fingerprint: str
    status_code: int | None = None

    data: Any = field(default=None, repr=False)
    errors: Sequence[Mapping[str, Any]] = field(default_factory=tuple, repr=False)
    extensions: Mapping[str, Any] = field(default_factory=dict, repr=False)

    meta: Mapping[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        # Consider "ok" only if no GraphQL errors exist.
        return not self.errors

    def redacted_dict(self) -> dict[str, Any]:
        return graphql_response_summary(self)


def graphql_request_summary(req: GraphQLRequest, *, salt: str = "francis") -> dict[str, Any]:
    """
    Log-safe summary for GraphQLRequest (no raw query/vars).
    """
    if not isinstance(req, GraphQLRequest):
        raise ProtocolValidationError(
            "graphql_request_summary expects GraphQLRequest",
            details={"type": type(req).__name__},
            context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request.summary"),
        )
    return {
        "operation_type": req.operation_type,
        "operation_name": req.operation_name,
        "query_len": len(req.query or ""),
        "query_hash": _hash_stable(req.query or "", salt=salt),
        "fingerprint": req.fingerprint(salt=salt),
        "variables": _summarize_variables(req.variables),
        "extensions_shape": _shape_value(req.extensions),
        "timeout_s": req.timeout_s,
        "meta": redact_mapping(req.meta),
    }


def graphql_response_summary(resp: GraphQLResponse) -> dict[str, Any]:
    """
    Log-safe summary for GraphQLResponse (no raw data/errors).
    """
    if not isinstance(resp, GraphQLResponse):
        return {"type": type(resp).__name__}
    return {
        "request_fingerprint": resp.request_fingerprint,
        "status_code": resp.status_code,
        "ok": bool(resp.ok()),
        "data_shape": _shape_value(resp.data),
        "errors": _summarize_graphql_errors(resp.errors),
        "extensions_shape": _shape_value(resp.extensions),
        "meta": redact_mapping(resp.meta),
    }


# =============================================================================
# GraphQL connector (delegates transport to http/https ProtocolConnector)
# =============================================================================


def _coerce_json_payload(payload: Any) -> Any:
    """
    Coerce payload into Python objects if it's JSON text/bytes.
    """
    if payload is None:
        return None
    if isinstance(payload, (bytes, bytearray)):
        try:
            return json.loads(bytes(payload).decode("utf-8", errors="strict"))
        except Exception as exc:  # noqa: BLE001
            raise ProtocolSerializationError(
                "failed to decode JSON response payload (bytes)",
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.parse_response"),
                code="json_decode_error",
                cause=exc,
            ) from exc
    if isinstance(payload, str):
        try:
            return json.loads(payload)
        except Exception as exc:  # noqa: BLE001
            raise ProtocolSerializationError(
                "failed to decode JSON response payload (str)",
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.parse_response"),
                code="json_decode_error",
                cause=exc,
            ) from exc
    return payload


def _extract_graphql_fields(obj: Any) -> tuple[Any, Sequence[Mapping[str, Any]], Mapping[str, Any]]:
    """
    Extract (data, errors, extensions) from a decoded GraphQL response object.
    """
    if not isinstance(obj, Mapping):
        return (None, tuple(), {})
    data = obj.get("data")
    errors = obj.get("errors")
    ext = obj.get("extensions")
    if not isinstance(errors, Sequence) or isinstance(errors, (str, bytes, bytearray)):
        errors_list: Sequence[Mapping[str, Any]] = tuple()
    else:
        # keep only mappings; ignore non-mapping garbage
        tmp: list[Mapping[str, Any]] = []
        for e in errors:
            if isinstance(e, Mapping):
                tmp.append(e)
        errors_list = tuple(tmp)
    extensions = ext if isinstance(ext, Mapping) else {}
    return (data, errors_list, extensions)


def _map_http_status_to_error(
    status_code: int | None,
    *,
    endpoint: ProtocolEndpoint | None,
    operation: str,
    details: Mapping[str, Any] | None = None,
) -> ProtocolError:
    """
    Map an HTTP-like status code into a ProtocolError subclass.

    This is used only by execute(..., raise_on_errors=True) convenience wrappers.
    """
    ctx = ProtocolErrorContext(
        protocol_id=GRAPHQL_PROTOCOL_ID,
        operation=operation,
        endpoint=endpoint,
        details=details or {},
    )
    sc = status_code

    if sc == 401:
        return ProtocolAuthError("unauthorized", context=ctx, code="http_401")
    if sc == 403:
        return ProtocolPermissionError("forbidden", context=ctx, code="http_403")
    if sc == 404:
        return ProtocolNotFoundError("not found", context=ctx, code="http_404")
    if sc == 429:
        return ProtocolRateLimitError("rate limited", context=ctx, code="http_429")
    if sc is not None and 500 <= sc <= 599:
        return ProtocolUnavailableError("upstream unavailable", context=ctx, code=f"http_{sc}")
    if sc is not None and sc >= 400:
        return ProtocolError("http error", context=ctx, code=f"http_{sc}")
    return ProtocolError("request failed", context=ctx, code="request_failed")


class GraphQLProtocolConnector:
    """
    GraphQL over HTTP adapter.

    Transport dependency:
      - Requires an underlying ProtocolConnector registered as "http" or "https"
        (or another protocol_id you provide).
    """

    def __init__(
        self,
        *,
        endpoint_url: str,
        http_protocol_id: str | None = None,
        default_headers: Mapping[str, str] | None = None,
        backoff_policy: ProtocolBackoffPolicy | None = None,
        name: str = "GraphQL Connector",
        version: str | None = None,
    ) -> None:
        self._endpoint_url = normalize_graphql_endpoint_url(endpoint_url)

        # Derive protocol id from endpoint scheme if not provided.
        if http_protocol_id is None:
            scheme = urlsplit(self._endpoint_url).scheme.lower()
            http_protocol_id = scheme  # "http" or "https"
        self._http_protocol_id = http_protocol_id.strip().lower()

        self._default_headers = dict(default_headers) if default_headers else {}
        self._backoff_policy = backoff_policy or ProtocolBackoffPolicy()
        self._name = name
        self._version = version

    @property
    def endpoint_url(self) -> str:
        return self._endpoint_url

    @property
    def http_protocol_id(self) -> str:
        return self._http_protocol_id

    def _http(self) -> ProtocolConnector:
        try:
            return get_protocol_connector(self._http_protocol_id)
        except ProtocolNotFoundError as exc:
            raise ProtocolNotFoundError(
                f"GraphQL connector requires an underlying '{self._http_protocol_id}' protocol connector",
                context=ProtocolErrorContext(
                    protocol_id=GRAPHQL_PROTOCOL_ID,
                    operation="graphql.resolve_http_connector",
                    details={"http_protocol_id": self._http_protocol_id},
                ),
                code="http_connector_not_registered",
                cause=exc,
            ) from exc

    # -------------------------------------------------------------------------
    # ProtocolConnector interface
    # -------------------------------------------------------------------------

    def info(self) -> ProtocolConnectorInfo:
        return ProtocolConnectorInfo(
            protocol_id=GRAPHQL_PROTOCOL_ID,
            name=self._name,
            version=self._version,
            description="GraphQL-over-HTTP adapter (delegates transport to http/https ProtocolConnector).",
            capabilities=("request", "execute", "query", "mutate", "health_check"),
            meta={"http_protocol_id": self._http_protocol_id, "endpoint_url": self._endpoint_url},
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
          - attempts query { __typename } (common, low-cost)
        """
        try:
            gql = GraphQLRequest(query="query { __typename }", variables={})
            resp = self.execute(
                gql,
                endpoint_url=(endpoint.uri if endpoint and endpoint.uri else None),
                identity=identity,
                timeout_s=timeout_s,
                raise_on_errors=False,
            )
            # If transport ok but graphql errors, mark degraded.
            degraded = bool(resp.payload and isinstance(resp.payload, GraphQLResponse) and not resp.payload.ok())
            ok = bool(resp.ok) and not degraded
            msg = "ok" if ok else ("degraded" if degraded else "failed")
            details = {
                "endpoint_url": self._endpoint_url,
                "http_protocol_id": self._http_protocol_id,
                "graphql": resp.payload.redacted_dict() if isinstance(resp.payload, GraphQLResponse) else {},
            }
            return ProtocolHealth(ok=ok, degraded=degraded, message=msg, details=details)
        except Exception as exc:  # noqa: BLE001
            return ProtocolHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={"endpoint_url": self._endpoint_url, "error": redact_value(str(exc))},
            )

    def request(
        self,
        req: ProtocolRequest,
        *,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
    ) -> ProtocolResponse:
        """
        Execute a GraphQL request.

        Expects:
          - req.payload to be GraphQLRequest OR a dict containing at least {"query": "..."}.
        Returns:
          - ProtocolResponse(protocol_id="graphql") whose payload is GraphQLResponse.
        """
        if req is None:
            raise ProtocolValidationError(
                "request is required",
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request"),
            )

        # Determine endpoint URL (normalized and safe).
        endpoint_url = self._endpoint_url
        if req.endpoint and (req.endpoint.uri or req.endpoint.address):
            endpoint_url = normalize_graphql_endpoint_url(req.endpoint.uri or req.endpoint.address)

        # Coerce payload to GraphQLRequest
        gql_req: GraphQLRequest
        if isinstance(req.payload, GraphQLRequest):
            gql_req = req.payload
        elif isinstance(req.payload, Mapping) and "query" in req.payload:
            gql_req = GraphQLRequest(
                query=str(req.payload.get("query") or ""),
                variables=req.payload.get("variables") if isinstance(req.payload.get("variables"), Mapping) else {},
                operation_name=req.payload.get("operationName") if req.payload.get("operationName") else None,
                extensions=req.payload.get("extensions") if isinstance(req.payload.get("extensions"), Mapping) else {},
            )
        else:
            raise ProtocolValidationError(
                "graphql request payload must be GraphQLRequest or mapping with 'query'",
                details={"payload_type": type(req.payload).__name__},
                context=ProtocolErrorContext(protocol_id=GRAPHQL_PROTOCOL_ID, operation="graphql.request"),
            )

        # Build HTTP request envelope
        headers: dict[str, str] = {}
        headers.update(self._default_headers)
        headers.update(dict(req.headers) if req.headers else {})
        headers.setdefault("Content-Type", "application/json")
        headers.setdefault("Accept", "application/json")

        http_endpoint = ProtocolEndpoint(
            protocol_id=self._http_protocol_id,
            address=endpoint_url,
            uri=endpoint_url,
            meta={"protocol": "graphql", "normalized": True},
        )

        # GraphQL queries are typically POST to the endpoint URL.
        # Operation string is intentionally generic; the HTTP connector can interpret.
        http_req = ProtocolRequest(
            protocol_id=self._http_protocol_id,
            operation="POST",
            endpoint=http_endpoint,
            headers=headers,
            payload=gql_req.to_http_json(),
            idempotent=req.idempotent if req.idempotent is not None else gql_req.is_idempotent(),
            expect_response=True,
            timeout_s=timeout_s if timeout_s is not None else (req.timeout_s or gql_req.timeout_s),
            meta={
                "graphql": gql_req.redacted_dict(),
                "caller_meta": redact_mapping(req.meta),
            },
        )

        http_resp = self._http().request(http_req, identity=identity, timeout_s=http_req.timeout_s)

        decoded = _coerce_json_payload(http_resp.payload)
        data, errors, extensions = _extract_graphql_fields(decoded)

        gql_resp = GraphQLResponse(
            request_fingerprint=gql_req.fingerprint(),
            status_code=http_resp.status_code,
            data=data,
            errors=errors,
            extensions=extensions,
            meta={
                "http_protocol_id": self._http_protocol_id,
                "endpoint_url": endpoint_url,
                "graphql_errors_count": len(errors or ()),
                "graphql_error_summary": _summarize_graphql_errors(errors),
            },
        )

        # Define success as: HTTP ok AND no GraphQL errors.
        ok = bool(http_resp.ok) and gql_resp.ok()

        # Return as ProtocolResponse for consistent upstream handling.
        return ProtocolResponse(
            protocol_id=GRAPHQL_PROTOCOL_ID,
            ok=ok,
            status_code=http_resp.status_code,
            headers=http_resp.headers,
            payload=gql_resp,
            stats=redact_mapping(
                {
                    "http_ok": bool(http_resp.ok),
                    "graphql_ok": bool(gql_resp.ok()),
                    "graphql_operation_type": gql_req.operation_type,
                    "graphql_operation_name": gql_req.operation_name,
                    "graphql_request_fingerprint": gql_req.fingerprint(),
                    "graphql_errors_count": len(errors or ()),
                }
            ),
            ts=http_resp.ts,
            meta=redact_mapping(req.meta),
        )

    # -------------------------------------------------------------------------
    # Convenience helpers (not part of base ProtocolConnector)
    # -------------------------------------------------------------------------

    def execute(
        self,
        gql: GraphQLRequest,
        *,
        endpoint_url: str | None = None,
        headers: Mapping[str, str] | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
        raise_on_errors: bool = True,
    ) -> ProtocolResponse:
        """
        Execute a GraphQLRequest directly.

        If raise_on_errors=True, raises ProtocolError subclasses for:
          - HTTP status failures (401/403/429/5xx/etc)
          - GraphQL response 'errors' non-empty
          - JSON parsing failures
        """
        ep = ProtocolEndpoint(
            protocol_id=GRAPHQL_PROTOCOL_ID,
            address=(endpoint_url or self._endpoint_url),
            uri=(endpoint_url or self._endpoint_url),
        )
        req = ProtocolRequest(
            protocol_id=GRAPHQL_PROTOCOL_ID,
            operation="execute",
            endpoint=ep,
            headers=dict(headers) if headers else {},
            payload=gql,
            idempotent=gql.is_idempotent(),
            expect_response=True,
            timeout_s=timeout_s if timeout_s is not None else gql.timeout_s,
            meta={},
        )

        resp = self.request(req, identity=identity, timeout_s=req.timeout_s)

        if not raise_on_errors:
            return resp

        # If HTTP failed, map to a ProtocolError.
        if resp.status_code is not None and resp.status_code >= 400:
            raise _map_http_status_to_error(
                resp.status_code,
                endpoint=ep,
                operation="graphql.execute",
                details={"graphql": gql.redacted_dict()},
            )

        # If GraphQL errors present, raise a ProtocolError.
        payload = resp.payload
        if isinstance(payload, GraphQLResponse) and payload.errors:
            raise ProtocolError(
                "graphql returned errors",
                context=ProtocolErrorContext(
                    protocol_id=GRAPHQL_PROTOCOL_ID,
                    operation="graphql.execute",
                    endpoint=ep,
                    details={
                        "graphql_request": gql.redacted_dict(),
                        "graphql_error_summary": _summarize_graphql_errors(payload.errors),
                    },
                ),
                code="graphql_errors",
            )

        if not resp.ok:
            # Unknown failure mode
            raise ProtocolError(
                "graphql request failed",
                context=ProtocolErrorContext(
                    protocol_id=GRAPHQL_PROTOCOL_ID,
                    operation="graphql.execute",
                    endpoint=ep,
                    details={"graphql_request": gql.redacted_dict()},
                ),
                code="graphql_failed",
            )

        return resp

    def query(
        self,
        query: str,
        *,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
        endpoint_url: str | None = None,
        headers: Mapping[str, str] | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
        raise_on_errors: bool = True,
    ) -> ProtocolResponse:
        gql = GraphQLRequest(
            query=query,
            variables=dict(variables) if variables else {},
            operation_name=operation_name,
        )
        return self.execute(
            gql,
            endpoint_url=endpoint_url,
            headers=headers,
            identity=identity,
            timeout_s=timeout_s,
            raise_on_errors=raise_on_errors,
        )

    def mutate(
        self,
        mutation: str,
        *,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
        endpoint_url: str | None = None,
        headers: Mapping[str, str] | None = None,
        identity: ProtocolIdentity | None = None,
        timeout_s: float | None = None,
        raise_on_errors: bool = True,
    ) -> ProtocolResponse:
        gql = GraphQLRequest(
            query=mutation,
            variables=dict(variables) if variables else {},
            operation_name=operation_name,
        )
        # For governance/idempotency hints, force operation_type detection to see "mutation"
        # (it already detects, but keeping explicit intent by naming method mutate).
        return self.execute(
            gql,
            endpoint_url=endpoint_url,
            headers=headers,
            identity=identity,
            timeout_s=timeout_s,
            raise_on_errors=raise_on_errors,
        )
