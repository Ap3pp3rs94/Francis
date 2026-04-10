"""
===============================================================================
Francis 2.0 — SaaS Connectors (GitLab)
Path: connectors/saas/gitlab.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a GitLab SaaS connector on top of the provider-agnostic
contract in connectors/saas/__init__.py.

Design goals:
  - Safe-by-default observability:
      * never logs tokens
      * never logs raw response bodies
      * summaries include hashes/lengths only
  - Deterministic, synchronous behavior using ONLY the Python standard library:
      * http.client + ssl for HTTP/HTTPS
  - Clear error taxonomy mapping to SaaS-layer errors:
      * auth vs permission vs rate limit vs not found vs validation vs unavailable
  - Retry semantics:
      * retries only for idempotent operations by default (GET/HEAD/OPTIONS)
      * retries only for retryable failures (network/unavailable/rate-limit)

NOTES
-----
- This connector is a foundation layer:
    * health_check()
    * REST request helpers (request_json, request_bytes)
    * GraphQL helper (optional; GitLab supports /api/graphql on most installs)
    * pagination helper (GitLab uses X-Next-Page header)
    * a few convenience helpers (get_current_user, get_project, create_issue)
- It is NOT a full GitLab SDK.

AUTH
----
Token resolution order:
  1) GitlabConfig.token (explicit)
  2) Environment variable GitlabConfig.token_env (default: GITLAB_TOKEN)

Auth header modes:
  - "private-token" (default):  PRIVATE-TOKEN: <token>
  - "bearer":                Authorization: Bearer <token>

No secrets should ever be hardcoded into repo files.

===============================================================================
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import ssl
import time
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit

from . import (
    SaasAuthError,
    SaasBackoffPolicy,
    SaasConflictError,
    SaasConnector,
    SaasConnectorInfo,
    SaasError,
    SaasErrorContext,
    SaasHealth,
    SaasIdentity,
    SaasNetworkError,
    SaasNotFoundError,
    SaasPermissionError,
    SaasRateLimitError,
    SaasUnavailableError,
    SaasValidationError,
    compute_backoff_s,
    normalize_provider_id,
    redact_mapping,
    redact_url,
    redact_value,
)

__all__ = [
    "GITLAB_PROVIDER_ID",
    "DEFAULT_GITLAB_API_BASE_URL",
    "GitlabConfig",
    "GitlabHttpResponse",
    "GitlabConnector",
    # Pagination helpers
    "parse_gitlab_pagination_headers",
]


GITLAB_PROVIDER_ID = "gitlab"
DEFAULT_GITLAB_API_BASE_URL = "https://gitlab.com/api/v4"


# =============================================================================
# Small log-safe hashing/shapes (never log token or raw body)
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
# Config + response model
# =============================================================================


@dataclass(frozen=True, slots=True)
class GitlabConfig:
    """
    GitLab connector configuration.

    base_url:
      - GitLab.com REST:       https://gitlab.com/api/v4
      - Self-managed REST:     https://gitlab.example.com/api/v4

    GraphQL endpoint:
      - Usually:               https://<host>/api/graphql
      - This connector derives the GraphQL URL by stripping a trailing "/api/v4"
        from base_url path (if present) and appending "/api/graphql".

    token:
      - Personal access token / project access token / OAuth token
      - optional for public endpoints (most GitLab endpoints are auth-required)

    auth_mode:
      - "private-token" (default): PRIVATE-TOKEN: <token>
      - "bearer": Authorization: Bearer <token>

    Safety:
      - token is never logged
    """

    base_url: str = DEFAULT_GITLAB_API_BASE_URL

    token: str | None = None
    token_env: str = "GITLAB_TOKEN"
    auth_mode: str = "private-token"  # "private-token" | "bearer"

    user_agent: str = "Francis/2.0 (connectors.saas.gitlab)"

    timeout_s: float = 15.0
    verify_tls: bool = True
    ca_file: str | None = None

    # Conservative limits
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    # Retry policy (applies only for idempotent requests)
    backoff_policy: SaasBackoffPolicy = field(default_factory=SaasBackoffPolicy)

    # Extra headers (safe defaults; do not place secrets here)
    default_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": self.timeout_s},
                context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.config.validate"),
            )
        am = (self.auth_mode or "").strip().lower()
        if am not in ("private-token", "bearer"):
            raise SaasValidationError(
                "auth_mode must be 'private-token' or 'bearer'",
                details={"auth_mode": redact_value(am)},
                context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class GitlabHttpResponse:
    """
    Low-level HTTP response wrapper.

    SAFETY:
      - body is stored, but the connector never logs it directly.
      - use summary() for log-safe details.
    """

    method: str
    url: str
    status: int
    reason: str
    headers: Mapping[str, str]
    body: bytes = field(repr=False)

    request_id: str | None = None
    trace_id: str | None = None
    rate_limit: Mapping[str, Any] = field(default_factory=dict)
    pagination: Mapping[str, Any] = field(default_factory=dict)

    def ok(self) -> bool:
        return 200 <= int(self.status) <= 299

    def text(self, encoding: str = "utf-8", *, errors: str = "replace") -> str:
        return (self.body or b"").decode(encoding, errors=errors)

    def json(self) -> Any:
        if not self.body:
            return None
        try:
            return json.loads(self.body.decode("utf-8", errors="strict"))
        except Exception as exc:  # noqa: BLE001
            raise SaasError(
                "failed to decode JSON response",
                context=SaasErrorContext(
                    provider_id=GITLAB_PROVIDER_ID,
                    operation="gitlab.response.json",
                    http_status=self.status,
                    request_id=self.request_id,
                    endpoint=redact_url(self.url),
                    details={
                        "body_len": len(self.body or b""),
                        "body_hash": _hash_stable((self.body or b"")[:256].hex()),
                    },
                ),
                code="json_decode_error",
                cause=exc,
            ) from exc

    def summary(self) -> dict[str, Any]:
        b = self.body or b""
        return {
            "method": self.method,
            "url": redact_url(self.url),
            "status": int(self.status),
            "reason": redact_value(self.reason),
            "request_id": redact_value(self.request_id) if self.request_id else None,
            "trace_id": redact_value(self.trace_id) if self.trace_id else None,
            "headers": redact_mapping(self.headers),
            "body_len": len(b),
            "body_hash": _hash_stable(b[:256].hex()),
            "rate_limit": dict(self.rate_limit) if self.rate_limit else {},
            "pagination": dict(self.pagination) if self.pagination else {},
        }


# =============================================================================
# Pagination / rate-limit header parsing
# =============================================================================


def parse_gitlab_pagination_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    GitLab pagination headers:
      - X-Page
      - X-Next-Page
      - X-Prev-Page
      - X-Per-Page
      - X-Total
      - X-Total-Pages
      - Link (sometimes present, but GitLab primarily uses X-Next-Page)

    Returns a dict with numeric values when parseable.
    """

    def _get(name: str) -> str | None:
        return headers.get(name) or headers.get(name.lower())

    def _as_int(v: str | None) -> int | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            return None

    out: dict[str, Any] = {}
    for k in ("X-Page", "X-Next-Page", "X-Prev-Page", "X-Per-Page", "X-Total", "X-Total-Pages"):
        iv = _as_int(_get(k))
        if iv is not None:
            out[k.lower().replace("-", "_")] = iv

    link = _get("Link")
    if link:
        out["link_present"] = True
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    GitLab rate limit headers vary by deployment. We parse common variants:

      - RateLimit-Limit / RateLimit-Remaining / RateLimit-Reset
      - X-RateLimit-Limit / X-RateLimit-Remaining / X-RateLimit-Reset
      - Retry-After

    Returns numbers when parseable.
    """

    def _get(name: str) -> str | None:
        return headers.get(name) or headers.get(name.lower())

    def _as_int(v: str | None) -> int | None:
        if v is None:
            return None
        s = str(v).strip()
        if not s:
            return None
        try:
            return int(s)
        except Exception:
            return None

    out: dict[str, Any] = {}
    for prefix in ("RateLimit", "X-RateLimit"):
        lim = _as_int(_get(f"{prefix}-Limit"))
        rem = _as_int(_get(f"{prefix}-Remaining"))
        rst = _as_int(_get(f"{prefix}-Reset"))
        if lim is not None:
            out["limit"] = lim
        if rem is not None:
            out["remaining"] = rem
        if rst is not None:
            out["reset"] = rst

    ra = _as_int(_get("Retry-After"))
    if ra is not None:
        out["retry_after_s"] = ra
    return out


# =============================================================================
# Internal URL + header helpers
# =============================================================================


@dataclass(frozen=True, slots=True)
class _BaseUrl:
    scheme: str
    host: str
    port: int
    path_prefix: str
    canonical: str
    graphql_canonical: str


def _normalize_base_url(base_url: str) -> _BaseUrl:
    raw = (base_url or "").strip()
    if not raw:
        raise SaasValidationError(
            "base_url is required",
            details={"field": "base_url"},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.base_url"),
        )

    p = urlsplit(raw)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.base_url"),
        )
    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.base_url"),
        )

    path_prefix = (p.path or "").rstrip("/")
    canonical_netloc = (
        f"{host}:{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else host
    )
    canonical = urlunsplit((scheme, canonical_netloc, path_prefix, "", ""))

    # Derive graphql base by stripping trailing "/api/v4" if present, then "/api/graphql"
    root_prefix = path_prefix
    if root_prefix.endswith("/api/v4"):
        root_prefix = root_prefix[: -len("/api/v4")]
    graphql_path = (root_prefix.rstrip("/") + "/api/graphql") if root_prefix else "/api/graphql"
    graphql_canonical = urlunsplit((scheme, canonical_netloc, graphql_path, "", ""))

    return _BaseUrl(
        scheme=scheme,
        host=host,
        port=port,
        path_prefix=path_prefix,
        canonical=canonical,
        graphql_canonical=graphql_canonical,
    )


def _safe_header_copy(h: Mapping[str, str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    if not h:
        return out
    for k, v in h.items():
        kk = ("" if k is None else str(k)).strip()
        if not kk:
            continue
        vv = "" if v is None else str(v)
        # Block header injection
        if "\r" in kk or "\n" in kk or "\x00" in kk:
            raise SaasValidationError(
                "header name contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.headers"),
            )
        out[kk] = vv
    return out


def _coerce_json_bytes(obj: Any) -> bytes:
    try:
        return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise SaasValidationError(
            "failed to encode JSON body",
            details={"json_body_shape": _shape_value(obj)},
            context=SaasErrorContext(provider_id=GITLAB_PROVIDER_ID, operation="gitlab.json_encode"),
            cause=exc,
        ) from exc


def _extract_message_from_body(resp: GitlabHttpResponse) -> str | None:
    """
    Best-effort extraction of a concise message from GitLab error payloads.
    Never returns raw full bodies; only a short string if present.
    """
    try:
        data = resp.json()
    except Exception:
        return None

    # Common GitLab patterns:
    # - {"message": "..."} or {"error": "..."} or {"error_description": "..."}
    if isinstance(data, Mapping):
        for key in ("message", "error_description", "error"):
            v = data.get(key)
            if isinstance(v, str) and v.strip():
                return v.strip()

        # Sometimes "message" can be an object
        msg = data.get("message")
        if isinstance(msg, Mapping):
            # keep it short: join keys only
            try:
                keys = list(msg.keys())[:10]
                return f"message: {', '.join(str(k) for k in keys)}"
            except Exception:
                return None

    # Sometimes it's an array of errors
    if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
        if data:
            first = data[0]
            if isinstance(first, str) and first.strip():
                return first.strip()
            if isinstance(first, Mapping):
                m = first.get("message")
                if isinstance(m, str) and m.strip():
                    return m.strip()

    return None


# =============================================================================
# Connector
# =============================================================================


class GitlabConnector(SaasConnector):
    """
    GitLab SaaS connector.

    Exposes:
      - info(), health_check()
      - request_* helpers
      - graphql() helper
      - pagination helper
      - a few convenience REST methods
    """

    def __init__(self, config: GitlabConfig | None = None) -> None:
        cfg = config or GitlabConfig()
        pid = normalize_provider_id(GITLAB_PROVIDER_ID)
        object.__setattr__(self, "_provider_id", pid)
        object.__setattr__(self, "_cfg", cfg)
        object.__setattr__(self, "_base", _normalize_base_url(cfg.base_url))

        tok = cfg.token
        if not tok:
            tok = (os.environ.get(cfg.token_env) or "").strip() or None
        object.__setattr__(self, "_token", tok)

        # Prebuild SSL context (only for https)
        ctx: ssl.SSLContext | None = None
        if self._base.scheme == "https":
            if cfg.verify_tls:
                ctx = ssl.create_default_context(cafile=cfg.ca_file)
            else:
                ctx = ssl._create_unverified_context()  # noqa: SLF001
        object.__setattr__(self, "_ssl_context", ctx)

    # ---- contract -----------------------------------------------------------

    def info(self) -> SaasConnectorInfo:
        return SaasConnectorInfo(
            provider_id=self._provider_id,
            name="GitLab Connector",
            version=None,
            description="GitLab REST/GraphQL connector (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest",
                "graphql",
                "pagination_x_next_page",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical),
                "graphql_url": redact_url(self._base.graphql_canonical),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "has_token": bool(self._token),
                "auth_mode": self._cfg.auth_mode,
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If token present: GET /user (validates auth)
          - Else: GET /version (connectivity check; may be public on many installs)

        If /version is not accessible, we still treat connection failures as unhealthy.
        """
        op = "gitlab.health_check"
        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)

        try:
            if self._token:
                data = self.request_json("GET", "/user", operation=op, timeout_s=tmo, idempotent=True)
                username = None
                try:
                    if isinstance(data, Mapping):
                        username = data.get("username") or data.get("name")
                except Exception:
                    username = None
                return SaasHealth(
                    ok=True,
                    degraded=False,
                    message="ok",
                    details={
                        "base_url": redact_url(self._base.canonical),
                        "auth": "ok",
                        "user_hash": _hash_stable(str(username or "")) if username else None,
                    },
                )

            data = self.request_json("GET", "/version", operation=op, timeout_s=tmo, idempotent=True)
            version = None
            try:
                if isinstance(data, Mapping):
                    version = data.get("version")
            except Exception:
                version = None
            return SaasHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "none",
                    "version_hash": _hash_stable(str(version or "")) if version else None,
                },
            )

        except SaasRateLimitError as exc:
            return SaasHealth(
                ok=False,
                degraded=True,
                message="rate_limited",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "error": redact_value(str(exc)),
                    "context": exc.redacted_context(),
                    "retry_after_s": getattr(exc, "retry_after_s", None),
                },
            )
        except SaasError as exc:
            return SaasHealth(
                ok=False,
                degraded=False,
                message="failed",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "error": redact_value(str(exc)),
                    "context": exc.redacted_context(),
                },
            )

    # ---- public helpers -----------------------------------------------------

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        json_body: Any | None = None,
        timeout_s: float | None = None,
        idempotent: bool | None = None,
        operation: str | None = None,
    ) -> GitlabHttpResponse:
        """
        Perform a GitLab REST request and return a low-level GitlabHttpResponse.

        Retries:
          - only if idempotent is True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "gitlab.request"),
            )

        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        pth = (path or "").strip()
        if not pth.startswith("/"):
            pth = "/" + pth

        # Encode query params
        query = ""
        if params:
            clean: dict[str, Any] = {str(k): v for k, v in params.items() if v is not None}
            query = urlencode(clean, doseq=True)

        full_path = self._base.path_prefix + pth
        url = urlunsplit((self._base.scheme, self._base.host, full_path, query, ""))

        # Headers
        hdrs: dict[str, str] = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/json")

        # Auth (never log)
        if self._token:
            if self._cfg.auth_mode.strip().lower() == "bearer":
                hdrs.setdefault("Authorization", f"Bearer {self._token}")
            else:
                hdrs.setdefault("PRIVATE-TOKEN", self._token)

        # Encode body
        send_body: bytes | None
        if json_body is not None:
            send_body = _coerce_json_bytes(json_body)
            hdrs.setdefault("Content-Type", "application/json; charset=utf-8")
        else:
            send_body = body

        if send_body is not None:
            hdrs.setdefault("Content-Length", str(len(send_body)))

        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)
        if tmo <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": tmo},
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "gitlab.request"),
            )

        policy = self._cfg.backoff_policy
        max_attempts = int(policy.max_attempts)
        attempt = 0

        while True:
            try:
                resp = self._send_once(
                    method=m,
                    full_path=full_path,
                    query=query,
                    url=url,
                    headers=hdrs,
                    body=send_body,
                    timeout_s=tmo,
                    operation=operation,
                )

                if resp.ok():
                    return resp

                self._raise_for_status(resp, operation=operation or "gitlab.request")
                return resp

            except SaasError as exc:
                if bool(idempotent) and getattr(exc, "retryable", False):
                    attempt += 1
                    if attempt > max_attempts:
                        raise

                    delay = compute_backoff_s(policy, attempt=attempt)

                    ra = getattr(exc, "retry_after_s", None)
                    if isinstance(ra, (int, float)) and ra is not None:
                        delay = max(delay, float(ra))

                    delay = min(float(policy.max_s), float(delay))
                    time.sleep(delay)
                    continue

                raise

    def request_json(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        json_body: Any | None = None,
        timeout_s: float | None = None,
        idempotent: bool | None = None,
        operation: str | None = None,
    ) -> Any:
        """
        Perform a REST request and decode JSON.

        Returns:
          - decoded JSON object
          - None for empty body / 204
        """
        resp = self.request_bytes(
            method,
            path,
            params=params,
            headers=headers,
            body=body,
            json_body=json_body,
            timeout_s=timeout_s,
            idempotent=idempotent,
            operation=operation,
        )
        if resp.status == 204 or not resp.body:
            return None
        return resp.json()

    def graphql(
        self,
        query: str,
        *,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
        timeout_s: float | None = None,
        idempotent: bool = True,
        operation: str | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Perform a GitLab GraphQL request.

        Endpoint:
          - derived from base_url -> /api/graphql

        Note:
          - GraphQL errors are commonly in {"errors": [...]}
        """
        if not (query or "").strip():
            raise SaasValidationError(
                "graphql query is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "gitlab.graphql"),
            )

        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        if operation_name is not None:
            payload["operationName"] = str(operation_name)

        # Build URL for GraphQL: same host/port, but path at graphql_canonical
        # We'll call _send_once with a computed full_path rather than relying on request_bytes.
        gql_url = urlsplit(self._base.graphql_canonical)
        gql_path = (gql_url.path or "/api/graphql").rstrip("/") or "/api/graphql"

        # For GraphQL we use POST, JSON body
        hdrs: dict[str, str] = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/json")
        hdrs.setdefault("Content-Type", "application/json; charset=utf-8")

        if self._token:
            if self._cfg.auth_mode.strip().lower() == "bearer":
                hdrs.setdefault("Authorization", f"Bearer {self._token}")
            else:
                hdrs.setdefault("PRIVATE-TOKEN", self._token)

        body_bytes = _coerce_json_bytes(payload)
        hdrs["Content-Length"] = str(len(body_bytes))

        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)
        if tmo <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": tmo},
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "gitlab.graphql"),
            )

        op = operation or "gitlab.graphql"
        resp = self._send_once(
            method="POST",
            full_path=gql_path,
            query="",
            url=self._base.graphql_canonical,
            headers=hdrs,
            body=body_bytes,
            timeout_s=tmo,
            operation=op,
        )

        if not resp.ok():
            self._raise_for_status(resp, operation=op)

        data = resp.json()
        if isinstance(data, Mapping) and data.get("errors"):
            errs = data.get("errors")
            msg_hashes: list[str] = []
            try:
                if isinstance(errs, Sequence):
                    for e in errs[:10]:
                        if isinstance(e, Mapping):
                            msg = e.get("message")
                            if isinstance(msg, str) and msg:
                                msg_hashes.append(_hash_stable(msg))
            except Exception:
                pass

            raise SaasError(
                "graphql returned errors",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=op,
                    endpoint=self._base.graphql_canonical,
                    details={"errors_shape": _shape_value(errs), "message_hashes": msg_hashes},
                ),
                code="graphql_error",
            )

        return data

    # ---- convenience methods -----------------------------------------------

    def get_current_user(self) -> Mapping[str, Any]:
        """
        GET /user (requires token).
        """
        if not self._token:
            raise SaasAuthError(
                "gitlab token required for /user",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.get_current_user"),
                code="token_required",
            )
        data = self.request_json("GET", "/user", operation="gitlab.get_current_user", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected /user response type",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation="gitlab.get_current_user",
                    details={"type": type(data).__name__},
                ),
                code="unexpected_response",
            )
        return data

    def get_project(self, project: str | int) -> Mapping[str, Any]:
        """
        GET /projects/:id

        project can be:
          - numeric project id
          - "group/subgroup/name" (will be URL-encoded as group%2Fsubgroup%2Fname)
        """
        if project is None:
            raise SaasValidationError(
                "project is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.get_project"),
            )
        pid = str(project).strip()
        if not pid:
            raise SaasValidationError(
                "project is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.get_project"),
            )

        # Encode if it looks like a path
        if "/" in pid:
            pid_enc = quote(pid, safe="")
        else:
            pid_enc = pid

        data = self.request_json("GET", f"/projects/{pid_enc}", operation="gitlab.get_project", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected project response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.get_project"),
                code="unexpected_response",
            )
        return data

    def create_issue(
        self,
        project: str | int,
        *,
        title: str,
        description: str | None = None,
        labels: Sequence[str] | None = None,
        assignee_ids: Sequence[int] | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /projects/:id/issues

        NOTE: Not idempotent by default (no automatic retries).
        """
        if not self._token:
            raise SaasAuthError(
                "gitlab token required to create issues",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.create_issue"),
                code="token_required",
            )

        pid = str(project).strip()
        if not pid:
            raise SaasValidationError(
                "project is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.create_issue"),
            )
        if "/" in pid:
            pid_enc = quote(pid, safe="")
        else:
            pid_enc = pid

        t = (title or "").strip()
        if not t:
            raise SaasValidationError(
                "title is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.create_issue"),
            )

        payload: dict[str, Any] = {"title": t}
        if description is not None:
            payload["description"] = str(description)
        if labels is not None:
            payload["labels"] = ",".join(str(x) for x in labels if str(x).strip())
        if assignee_ids is not None:
            payload["assignee_ids"] = [int(x) for x in assignee_ids]

        data = self.request_json(
            "POST",
            f"/projects/{pid_enc}/issues",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="gitlab.create_issue",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected create_issue response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="gitlab.create_issue"),
                code="unexpected_response",
            )
        return data

    def iter_paginated(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        operation: str | None = None,
        max_pages: int = 50,
        per_page: int | None = None,
    ) -> Iterable[Any]:
        """
        Iterate through a GitLab paginated endpoint following X-Next-Page.

        - Assumes each page returns a JSON array.
        - Uses GET (idempotent).

        Tip:
          - set per_page (<=100 on most GitLab installs) to reduce round-trips.
        """
        op = operation or "gitlab.iter_paginated"
        page = 1
        pages = 0

        base_params: dict[str, Any] = dict(params or {})
        if per_page is not None:
            base_params.setdefault("per_page", int(per_page))

        while True:
            pages += 1
            if pages > max_pages:
                break

            q = dict(base_params)
            q["page"] = page

            resp = self.request_bytes(
                "GET",
                path,
                params=q,
                headers=headers,
                timeout_s=timeout_s,
                idempotent=True,
                operation=op,
            )
            data = resp.json()

            if isinstance(data, Sequence) and not isinstance(data, (str, bytes, bytearray)):
                for item in data:
                    yield item
            else:
                yield data
                break

            next_page = None
            try:
                np = resp.pagination.get("x_next_page")  # parsed lower_key form
                if isinstance(np, int) and np > 0:
                    next_page = np
            except Exception:
                next_page = None

            # If parsing didn’t capture it, try raw header lookup.
            if next_page is None:
                raw_np = resp.headers.get("X-Next-Page") or resp.headers.get("x-next-page") or ""
                raw_np = str(raw_np).strip()
                if raw_np:
                    try:
                        next_page = int(raw_np)
                    except Exception:
                        next_page = None

            if not next_page:
                break
            page = next_page

    # ---- internals ----------------------------------------------------------

    def _send_once(
        self,
        *,
        method: str,
        full_path: str,
        query: str,
        url: str,
        headers: Mapping[str, str],
        body: bytes | None,
        timeout_s: float,
        operation: str | None,
    ) -> GitlabHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError / SaasUnavailableError.
        """
        op = operation or "gitlab.request"
        conn: http.client.HTTPConnection | None = None
        try:
            if self._base.scheme == "https":
                conn = http.client.HTTPSConnection(
                    self._base.host,
                    self._base.port,
                    timeout=float(timeout_s),
                    context=self._ssl_context,
                )
            else:
                conn = http.client.HTTPConnection(
                    self._base.host,
                    self._base.port,
                    timeout=float(timeout_s),
                )

            path_with_query = full_path + (f"?{query}" if query else "")
            conn.request(method, path_with_query, body=body, headers=dict(headers))

            resp = conn.getresponse()
            status = int(resp.status)
            reason = str(resp.reason or "")

            raw = resp.read(int(self._cfg.max_response_bytes) + 1)
            if len(raw) > int(self._cfg.max_response_bytes):
                raise SaasError(
                    "response exceeded max_response_bytes",
                    context=SaasErrorContext(
                        provider_id=self._provider_id,
                        operation=op,
                        http_status=status,
                        endpoint=self._base.canonical,
                        details={
                            "url": redact_url(url),
                            "max_response_bytes": int(self._cfg.max_response_bytes),
                        },
                    ),
                    code="response_too_large",
                )

            hdr_map: dict[str, str] = {}
            for k, v in resp.getheaders():
                if k is None:
                    continue
                hdr_map[str(k)] = "" if v is None else str(v)

            request_id = hdr_map.get("X-Request-Id") or hdr_map.get("x-request-id")
            trace_id = hdr_map.get("X-GitLab-Trace-Id") or hdr_map.get("x-gitlab-trace-id")

            rate = _parse_rate_limit_headers(hdr_map)
            pagination = parse_gitlab_pagination_headers(hdr_map)

            return GitlabHttpResponse(
                method=method,
                url=url,
                status=status,
                reason=reason,
                headers=hdr_map,
                body=raw,
                request_id=request_id,
                trace_id=trace_id,
                rate_limit=rate,
                pagination=pagination,
            )

        except ssl.SSLError as exc:
            raise SaasNetworkError(
                "TLS error contacting GitLab endpoint",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=op,
                    endpoint=self._base.canonical,
                    details={"url": redact_url(url)},
                ),
                code="tls_error",
                cause=exc,
            ) from exc

        except (OSError, http.client.HTTPException) as exc:
            raise SaasNetworkError(
                "network error contacting GitLab endpoint",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=op,
                    endpoint=self._base.canonical,
                    details={"url": redact_url(url)},
                ),
                code="network_error",
                cause=exc,
            ) from exc

        finally:
            try:
                if conn is not None:
                    conn.close()
            except Exception:
                pass

    def _raise_for_status(self, resp: GitlabHttpResponse, *, operation: str) -> None:
        """
        Map HTTP status to SaaS-layer errors.

        IMPORTANT: Do not attach raw body. Only attach safe summaries.
        """
        status = int(resp.status)
        msg = _extract_message_from_body(resp)

        retry_after = None
        if resp.rate_limit:
            retry_after = resp.rate_limit.get("retry_after_s")
            # Some deployments provide reset as epoch seconds.
            reset = resp.rate_limit.get("reset")
            if retry_after is None and isinstance(reset, (int, float)):
                delta = float(reset) - float(time.time())
                if delta > 0:
                    retry_after = delta

        ctx = SaasErrorContext(
            provider_id=self._provider_id,
            operation=operation,
            request_id=resp.request_id,
            http_status=status,
            endpoint=self._base.canonical,
            details={
                "method": resp.method,
                "url": redact_url(resp.url),
                "rate_limit": dict(resp.rate_limit) if resp.rate_limit else {},
                "pagination": dict(resp.pagination) if resp.pagination else {},
                "trace_id": redact_value(resp.trace_id) if resp.trace_id else None,
                "body_len": len(resp.body or b""),
                "body_hash": _hash_stable((resp.body or b"")[:256].hex()),
            },
        )

        if status == 401:
            raise SaasAuthError(msg or "unauthorized", context=ctx, code="http_401")

        if status == 403:
            # GitLab generally uses 403 for permission; rate-limits usually 429.
            raise SaasPermissionError(msg or "forbidden", context=ctx, code="http_403")

        if status == 404:
            raise SaasNotFoundError(msg or "not found", context=ctx, code="http_404")

        if status == 409:
            raise SaasConflictError(msg or "conflict", context=ctx, code="http_409")

        if status in (400, 422):
            raise SaasValidationError(msg or "validation failed", context=ctx, code=f"http_{status}")

        if status == 429:
            ra_s: float | None = float(retry_after) if isinstance(retry_after, (int, float)) else None
            raise SaasRateLimitError(
                msg or "too many requests",
                context=ctx,
                code="http_429",
                retry_after_s=ra_s,
            )

        if 500 <= status <= 599:
            raise SaasUnavailableError(msg or "service unavailable", context=ctx, code=f"http_{status}")

        raise SaasError(msg or f"http error {status}", context=ctx, code=f"http_{status}")
