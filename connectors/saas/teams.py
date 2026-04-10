"""
===============================================================================
Francis 2.0 — SaaS Connectors (Microsoft Teams via Microsoft Graph)
Path: connectors/saas/teams.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a Microsoft Teams SaaS connector on top of the provider-
agnostic contract in connectors/saas/__init__.py.

Microsoft Teams operations are exposed through the Microsoft Graph API, so this
connector is effectively a Graph REST connector with Teams-focused conveniences.

Design goals:
  - Safe-by-default observability:
      * never logs tokens
      * never logs raw response bodies
      * structured context includes only lengths/hashes + redacted URLs
  - Deterministic, synchronous behavior using only Python stdlib:
      * http.client + ssl for HTTPS
  - Clear error taxonomy mapping to SaaS-layer errors:
      * auth vs permission vs rate limit vs not found vs validation vs unavailable
  - Retry semantics:
      * retries only for idempotent operations by default (GET/HEAD/OPTIONS)
      * retries only for retryable failures (network/unavailable/rate-limit)

AUTH
----
Token resolution order:
  1) TeamsConfig.token (explicit)
  2) Environment variable TeamsConfig.token_env (default: MS_GRAPH_TOKEN)

This connector does NOT implement OAuth flows. It assumes an access token is
provided by Francis credential governance (preferred), environment variables,
or local developer tooling.

NOTES
-----
- This is a foundation connector:
    * health_check() with pragmatic fallback ("/me" then "/organization")
    * request helpers (request_json, request_bytes)
    * Graph pagination helper (@odata.nextLink)
    * Teams conveniences:
        - list_joined_teams (delegated)
        - list_team_channels
        - post_channel_message
        - list_channel_messages (paged)
- It is NOT a full Teams SDK.

===============================================================================
"""

from __future__ import annotations

import hashlib
import http.client
import json
import os
import ssl
import time
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

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
    SaasUnsupportedError,
    SaasValidationError,
    compute_backoff_s,
    normalize_provider_id,
    redact_mapping,
    redact_url,
    redact_value,
)

__all__ = [
    "TEAMS_PROVIDER_ID",
    "DEFAULT_GRAPH_BASE_URL",
    "TeamsConfig",
    "TeamsHttpResponse",
    "TeamsConnector",
    # Helpers
    "extract_odata_next_link",
]


TEAMS_PROVIDER_ID = "teams"
DEFAULT_GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"


# =============================================================================
# Log-safe hashing / shapes (never log token or raw body)
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
class TeamsConfig:
    """
    Teams connector configuration (Microsoft Graph).

    base_url:
      - Graph v1.0: https://graph.microsoft.com/v1.0
      - Graph beta: https://graph.microsoft.com/beta

    token:
      - OAuth access token for Microsoft Graph.

    Safety:
      - token is never logged
    """

    base_url: str = DEFAULT_GRAPH_BASE_URL

    token: str | None = field(default=None, repr=False)
    token_env: str = "MS_GRAPH_TOKEN"

    user_agent: str = "Francis/2.0 (connectors.saas.teams)"

    timeout_s: float = 20.0
    verify_tls: bool = True
    ca_file: str | None = None

    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    backoff_policy: SaasBackoffPolicy = field(default_factory=SaasBackoffPolicy)
    default_headers: Mapping[str, str] = field(default_factory=dict)

    # Graph can optionally return a request id header; we also send a client-request-id for correlation.
    send_client_request_id: bool = True

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": self.timeout_s},
                context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class TeamsHttpResponse:
    """
    Low-level HTTP response wrapper.

    SAFETY:
      - body is stored, but never logged directly.
      - use summary() for log-safe details.
    """

    method: str
    url: str
    status: int
    reason: str
    headers: Mapping[str, str]
    body: bytes = field(repr=False)

    request_id: str | None = None
    client_request_id: str | None = None
    rate_limit: Mapping[str, Any] = field(default_factory=dict)

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
                    provider_id=TEAMS_PROVIDER_ID,
                    operation="teams.response.json",
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
            "client_request_id": redact_value(self.client_request_id) if self.client_request_id else None,
            "headers": redact_mapping(self.headers),
            "body_len": len(b),
            "body_hash": _hash_stable(b[:256].hex()),
            "rate_limit": dict(self.rate_limit) if self.rate_limit else {},
        }


# =============================================================================
# Helpers
# =============================================================================


def extract_odata_next_link(payload: Mapping[str, Any] | None) -> str | None:
    """
    Microsoft Graph pagination:
      - payload.get("@odata.nextLink")

    Returns a stripped nextLink string or None.
    """
    if not payload:
        return None
    try:
        v = payload.get("@odata.nextLink")
        if isinstance(v, str):
            v = v.strip()
            return v or None
    except Exception:
        return None
    return None


@dataclass(frozen=True, slots=True)
class _BaseUrl:
    scheme: str
    host: str
    port: int
    path_prefix: str
    canonical: str


def _normalize_base_url(base_url: str) -> _BaseUrl:
    raw = (base_url or "").strip()
    if not raw:
        raise SaasValidationError(
            "base_url is required",
            details={"field": "base_url"},
            context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.base_url"),
        )

    p = urlsplit(raw)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.base_url"),
        )
    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.base_url"),
        )

    path_prefix = (p.path or "").rstrip("/")
    canonical_netloc = (
        f"{host}:{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else host
    )
    canonical = urlunsplit((scheme, canonical_netloc, path_prefix, "", ""))
    return _BaseUrl(scheme=scheme, host=host, port=port, path_prefix=path_prefix, canonical=canonical)


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
                context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=TEAMS_PROVIDER_ID, operation="teams.headers"),
            )
        out[kk] = vv
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    Microsoft Graph rate limiting:
      - 429 Too Many Requests with Retry-After header (seconds)
    Also parse RateLimit-* variants opportunistically.
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
    ra = _as_int(_get("Retry-After"))
    if ra is not None:
        out["retry_after_s"] = ra

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

    return out


def _extract_graph_error(resp: TeamsHttpResponse) -> tuple[str | None, str | None, str | None]:
    """
    Best-effort extraction of (message, code, request_id) from Graph error payload.

    Graph often returns:
      {
        "error": {
          "code": "InvalidAuthenticationToken",
          "message": "Access token has expired.",
          "innerError": { "date": "...", "request-id": "...", "client-request-id": "..." }
        }
      }
    """
    try:
        data = resp.json()
    except Exception:
        return None, None, None

    if not isinstance(data, Mapping):
        return None, None, None

    err = data.get("error")
    if not isinstance(err, Mapping):
        return None, None, None

    msg = err.get("message")
    code = err.get("code")
    inner = err.get("innerError")
    rid = None
    if isinstance(inner, Mapping):
        rid = inner.get("request-id") or inner.get("requestId") or inner.get("request_id")

    msg_s = msg.strip() if isinstance(msg, str) and msg.strip() else None
    code_s = code.strip() if isinstance(code, str) and code.strip() else None
    rid_s = str(rid).strip() if isinstance(rid, str) and str(rid).strip() else None
    return msg_s, code_s, rid_s


# =============================================================================
# Connector
# =============================================================================


class TeamsConnector(SaasConnector):
    """
    Microsoft Teams connector implemented on Microsoft Graph.

    Exposes:
      - info(), health_check()
      - request helpers:
          request_json, request_bytes, request_url_json (absolute nextLink)
      - pagination helpers for @odata.nextLink
      - Teams convenience methods:
          get_me
          list_joined_teams
          list_team_channels
          post_channel_message
          list_channel_messages / iter_channel_messages
    """

    def __init__(self, config: TeamsConfig | None = None) -> None:
        cfg = config or TeamsConfig()
        pid = normalize_provider_id(TEAMS_PROVIDER_ID)
        object.__setattr__(self, "_provider_id", pid)
        object.__setattr__(self, "_cfg", cfg)
        object.__setattr__(self, "_base", _normalize_base_url(cfg.base_url))

        tok = cfg.token
        if not tok:
            tok = (os.environ.get(cfg.token_env) or "").strip() or None
        object.__setattr__(self, "_token", tok)

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
            name="Microsoft Teams Connector",
            version=None,
            description="Microsoft Teams via Microsoft Graph (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest_graph",
                "odata_pagination",
                "teams_channels",
                "teams_messages",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "has_token": bool(self._token),
                "token_env": self._cfg.token_env,
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If no token: degraded/unauthenticated (Graph requires auth for almost everything)
          - If token present:
              1) Try GET /me (delegated tokens)
              2) If forbidden, try GET /organization?$top=1 (often works for app tokens with perms)
        """
        if not self._token:
            return SaasHealth(
                ok=True,
                degraded=True,
                message="unauthenticated",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "none",
                    "note": "No token configured; most Graph endpoints will fail.",
                },
            )

        op = "teams.health_check"
        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)

        try:
            data = self.request_json("GET", "/me", timeout_s=tmo, idempotent=True, operation=op)
            # /me returns a user object for delegated tokens
            upn_hash = None
            try:
                if isinstance(data, Mapping):
                    upn = data.get("userPrincipalName") or data.get("mail") or data.get("id")
                    if upn:
                        upn_hash = _hash_stable(str(upn))
            except Exception:
                upn_hash = None

            return SaasHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "ok",
                    "mode": "delegated_me",
                    "principal_hash": upn_hash,
                },
            )

        except SaasPermissionError:
            # Fall back for app-only tokens
            try:
                data2 = self.request_json(
                    "GET",
                    "/organization",
                    params={"$top": 1},
                    timeout_s=tmo,
                    idempotent=True,
                    operation=op,
                )
                org_hash = None
                try:
                    if isinstance(data2, Mapping):
                        vals = data2.get("value")
                        if isinstance(vals, Sequence) and not isinstance(vals, (str, bytes, bytearray)) and vals:
                            first = vals[0]
                            if isinstance(first, Mapping):
                                org_hash = _hash_stable(str(first.get("id") or first.get("displayName") or ""))
                except Exception:
                    org_hash = None

                return SaasHealth(
                    ok=True,
                    degraded=False,
                    message="ok",
                    details={
                        "base_url": redact_url(self._base.canonical),
                        "auth": "ok",
                        "mode": "app_organization",
                        "org_hash": org_hash,
                    },
                )
            except SaasError as exc2:
                return SaasHealth(
                    ok=False,
                    degraded=False,
                    message="failed",
                    details={
                        "base_url": redact_url(self._base.canonical),
                        "error": redact_value(str(exc2)),
                        "context": exc2.redacted_context(),
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

    # ---- public request helpers --------------------------------------------

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
    ) -> TeamsHttpResponse:
        """
        Perform a Microsoft Graph request relative to base_url.

        Retries:
          - only if idempotent True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request"),
            )

        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        pth = (path or "").strip()
        if not pth:
            raise SaasValidationError(
                "path is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request"),
            )
        if not pth.startswith("/"):
            pth = "/" + pth

        query = ""
        if params:
            clean: dict[str, Any] = {str(k): v for k, v in params.items() if v is not None}
            query = urlencode(clean, doseq=True)

        full_path = self._base.path_prefix + pth
        url = urlunsplit((self._base.scheme, self._base.host, full_path, query, ""))

        hdrs: dict[str, str] = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/json")

        # Auth (never log token)
        if self._token:
            hdrs.setdefault("Authorization", f"Bearer {self._token}")

        # Correlation header (safe)
        client_req_id: str | None = None
        if self._cfg.send_client_request_id:
            client_req_id = str(uuid.uuid4())
            hdrs.setdefault("client-request-id", client_req_id)
            hdrs.setdefault("return-client-request-id", "true")

        send_body: bytes | None
        if json_body is not None:
            try:
                send_body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode(
                    "utf-8"
                )
            except Exception as exc:  # noqa: BLE001
                raise SaasValidationError(
                    "failed to encode json_body",
                    details={"json_body_shape": _shape_value(json_body)},
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request"),
                    cause=exc,
                ) from exc
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
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request"),
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
                    client_request_id=client_req_id,
                )

                if resp.ok():
                    return resp

                self._raise_for_status(resp, operation=operation or "teams.request")
                return resp  # should not happen

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

    def request_url_json(
        self,
        method: str,
        absolute_url: str,
        *,
        headers: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        idempotent: bool | None = None,
        operation: str | None = None,
    ) -> Any:
        """
        Request an *absolute* URL (used for @odata.nextLink).

        Safety: only allows same host as configured base_url to avoid SSRF-style surprises.
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request_url"),
            )

        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        raw = (absolute_url or "").strip()
        if not raw:
            raise SaasValidationError(
                "absolute_url is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request_url"),
            )

        p = urlsplit(raw)
        if not p.scheme or not p.netloc:
            raise SaasValidationError(
                "absolute_url must be a full URL",
                details={"absolute_url": redact_url(raw)},
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "teams.request_url"),
            )

        # Host allow-list: same as configured host
        if (p.hostname or "").lower() != self._base.host.lower():
            raise SaasUnsupportedError(
                "absolute_url host does not match configured Graph host",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=operation or "teams.request_url",
                    details={
                        "host": redact_value(p.hostname or ""),
                        "expected": redact_value(self._base.host),
                    },
                ),
                code="absolute_url_host_mismatch",
            )

        full_path = p.path or "/"
        query = p.query or ""
        url = urlunsplit((p.scheme, p.netloc, p.path, p.query, ""))

        hdrs: dict[str, str] = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/json")
        if self._token:
            hdrs.setdefault("Authorization", f"Bearer {self._token}")

        client_req_id: str | None = None
        if self._cfg.send_client_request_id:
            client_req_id = str(uuid.uuid4())
            hdrs.setdefault("client-request-id", client_req_id)
            hdrs.setdefault("return-client-request-id", "true")

        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)

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
                    body=None,
                    timeout_s=tmo,
                    operation=operation or "teams.request_url",
                    client_request_id=client_req_id,
                )
                if resp.ok():
                    if resp.status == 204 or not resp.body:
                        return None
                    return resp.json()
                self._raise_for_status(resp, operation=operation or "teams.request_url")
                return None
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

    # ---- Teams convenience methods -----------------------------------------

    def get_me(self, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /me  (delegated token)
        """
        data = self.request_json("GET", "/me", timeout_s=timeout_s, idempotent=True, operation="teams.get_me")
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected /me response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.get_me"),
                code="unexpected_response",
            )
        return data

    def list_joined_teams(self, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /me/joinedTeams  (delegated token)
        Returns raw payload: {"value":[...], ...}
        """
        data = self.request_json(
            "GET",
            "/me/joinedTeams",
            timeout_s=timeout_s,
            idempotent=True,
            operation="teams.list_joined_teams",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected joinedTeams response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.list_joined_teams"),
                code="unexpected_response",
            )
        return data

    def list_team_channels(self, team_id: str, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /teams/{team-id}/channels
        """
        tid = (team_id or "").strip()
        if not tid:
            raise SaasValidationError(
                "team_id is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.list_team_channels"),
            )
        data = self.request_json(
            "GET",
            f"/teams/{tid}/channels",
            timeout_s=timeout_s,
            idempotent=True,
            operation="teams.list_team_channels",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected channels response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.list_team_channels"),
                code="unexpected_response",
            )
        return data

    def post_channel_message(
        self,
        team_id: str,
        channel_id: str,
        *,
        content: str,
        content_type: str = "html",  # "html" or "text" in Graph
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /teams/{team-id}/channels/{channel-id}/messages

        Non-idempotent (no automatic retries).
        """
        tid = (team_id or "").strip()
        cid = (channel_id or "").strip()
        if not tid or not cid:
            raise SaasValidationError(
                "team_id and channel_id are required",
                details={"team_id": redact_value(tid), "channel_id": redact_value(cid)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.post_channel_message"),
            )
        ct = (content_type or "html").strip().lower()
        if ct not in ("html", "text"):
            raise SaasValidationError(
                "content_type must be 'html' or 'text'",
                details={"content_type": redact_value(ct)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.post_channel_message"),
            )
        msg = (content or "").strip()
        if not msg:
            raise SaasValidationError(
                "content is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.post_channel_message"),
            )

        payload = {"body": {"contentType": ct, "content": msg}}

        data = self.request_json(
            "POST",
            f"/teams/{tid}/channels/{cid}/messages",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="teams.post_channel_message",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected post message response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.post_channel_message"),
                code="unexpected_response",
            )
        return data

    def list_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        *,
        top: int = 50,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        GET /teams/{team-id}/channels/{channel-id}/messages?$top=N

        Returns raw payload, including possible @odata.nextLink.
        """
        tid = (team_id or "").strip()
        cid = (channel_id or "").strip()
        if not tid or not cid:
            raise SaasValidationError(
                "team_id and channel_id are required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.list_channel_messages"),
            )

        data = self.request_json(
            "GET",
            f"/teams/{tid}/channels/{cid}/messages",
            params={"$top": int(top)},
            timeout_s=timeout_s,
            idempotent=True,
            operation="teams.list_channel_messages",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected list messages response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="teams.list_channel_messages"),
                code="unexpected_response",
            )
        return data

    def iter_channel_messages(
        self,
        team_id: str,
        channel_id: str,
        *,
        top: int = 50,
        max_pages: int = 50,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate messages using Graph @odata.nextLink.

        Yields each message dict from "value".
        """
        pages = 0
        payload = self.list_channel_messages(team_id, channel_id, top=top, timeout_s=timeout_s)

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            vals = payload.get("value") if isinstance(payload, Mapping) else None
            if isinstance(vals, Sequence) and not isinstance(vals, (str, bytes, bytearray)):
                for item in vals:
                    if isinstance(item, Mapping):
                        yield item

            nxt = extract_odata_next_link(payload)
            if not nxt:
                break

            next_payload = self.request_url_json(
                "GET",
                nxt,
                timeout_s=timeout_s,
                idempotent=True,
                operation="teams.iter_channel_messages.next",
            )
            if not isinstance(next_payload, Mapping):
                break
            payload = next_payload

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
        client_request_id: str | None,
    ) -> TeamsHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError.
        """
        op = operation or "teams.request"
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

            # Graph request id headers can vary; commonly "request-id"
            request_id = (
                hdr_map.get("request-id")
                or hdr_map.get("Request-Id")
                or hdr_map.get("x-ms-request-id")
                or hdr_map.get("X-Ms-Request-Id")
            )

            rate = _parse_rate_limit_headers({k.lower(): v for k, v in hdr_map.items()})

            return TeamsHttpResponse(
                method=method,
                url=url,
                status=status,
                reason=reason,
                headers=hdr_map,
                body=raw,
                request_id=request_id,
                client_request_id=client_request_id,
                rate_limit=rate,
            )

        except ssl.SSLError as exc:
            raise SaasNetworkError(
                "TLS error contacting Microsoft Graph",
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
                "network error contacting Microsoft Graph",
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

    def _raise_for_status(self, resp: TeamsHttpResponse, *, operation: str) -> None:
        """
        Map HTTP status to SaaS-layer errors.

        IMPORTANT: do not attach raw body. Only attach safe summaries.
        """
        status = int(resp.status)
        msg, graph_code, inner_rid = _extract_graph_error(resp)

        # Prefer inner error request-id if header missing
        request_id = resp.request_id or inner_rid

        retry_after = None
        if resp.rate_limit:
            retry_after = resp.rate_limit.get("retry_after_s")

        ctx = SaasErrorContext(
            provider_id=self._provider_id,
            operation=operation,
            request_id=request_id,
            http_status=status,
            endpoint=self._base.canonical,
            details={
                "method": resp.method,
                "url": redact_url(resp.url),
                "graph_code": graph_code,
                "client_request_id": resp.client_request_id,
                "rate_limit": dict(resp.rate_limit) if resp.rate_limit else {},
                "body_len": len(resp.body or b""),
                "body_hash": _hash_stable((resp.body or b"")[:256].hex()),
            },
        )

        # 401 Unauthorized
        if status == 401:
            raise SaasAuthError(msg or "unauthorized", context=ctx, code=graph_code or "http_401")

        # 403 Forbidden
        if status == 403:
            raise SaasPermissionError(msg or "forbidden", context=ctx, code=graph_code or "http_403")

        # 404 Not found
        if status == 404:
            raise SaasNotFoundError(msg or "not found", context=ctx, code=graph_code or "http_404")

        # 409 Conflict
        if status == 409:
            raise SaasConflictError(msg or "conflict", context=ctx, code=graph_code or "http_409")

        # 400/422 Validation-ish
        if status in (400, 422):
            raise SaasValidationError(msg or "validation failed", context=ctx, code=graph_code or f"http_{status}")

        # 429 Too many requests
        if status == 429:
            ra_s: float | None = float(retry_after) if isinstance(retry_after, (int, float)) else None
            raise SaasRateLimitError(
                msg or "rate limited",
                context=ctx,
                code=graph_code or "http_429",
                retry_after_s=ra_s,
            )

        # 5xx
        if 500 <= status <= 599:
            raise SaasUnavailableError(msg or "service unavailable", context=ctx, code=graph_code or f"http_{status}")

        # Default
        raise SaasError(msg or f"http error {status}", context=ctx, code=graph_code or f"http_{status}")
