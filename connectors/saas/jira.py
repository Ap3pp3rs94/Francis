"""
===============================================================================
Francis 2.0 — SaaS Connectors (Jira)
Path: connectors/saas/jira.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a Jira SaaS connector on top of the provider-agnostic
contract in connectors/saas/__init__.py.

Supports Jira Cloud and Jira Server/Data Center style REST APIs via stdlib
http.client + ssl.

Design goals:
  - Safe-by-default observability:
      * never logs tokens/passwords
      * never logs raw response bodies
      * summaries use hashes/lengths only
  - Deterministic, synchronous behavior using only stdlib
  - Clear error taxonomy mapping to SaaS-layer errors:
      * auth vs permission vs rate limit vs not found vs validation vs unavailable
  - Retry semantics:
      * retries only for idempotent methods by default (GET/HEAD/OPTIONS)
      * retries only for retryable failures (network/unavailable/rate-limit)

AUTH
----
Token resolution order:
  1) JiraConfig.token (explicit)
  2) Environment variable JiraConfig.token_env (default: JIRA_API_TOKEN)

Username/email resolution order (for basic auth):
  1) JiraConfig.username (explicit)
  2) Environment variable JiraConfig.username_env (default: JIRA_EMAIL)

Supported auth modes:
  - "basic" (default for Jira Cloud): Authorization: Basic base64(username:token)
  - "bearer": Authorization: Bearer <token>

NOTES
-----
- This is a foundation connector:
    * health_check()
    * REST request helpers (request_json, request_bytes)
    * pagination helper for JQL search
    * a few convenience helpers (get_myself, get_issue, search_jql, create_issue)
- It is NOT a full Jira SDK.

===============================================================================
"""

from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import re
import ssl
import time
from collections.abc import Iterable, Mapping, MutableMapping, Sequence
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
    SaasUnsupportedError,
    SaasValidationError,
    compute_backoff_s,
    normalize_provider_id,
    redact_mapping,
    redact_url,
    redact_value,
)

__all__ = [
    "JIRA_PROVIDER_ID",
    "DEFAULT_JIRA_API_VERSION",
    "JiraConfig",
    "JiraHttpResponse",
    "JiraConnector",
    "make_adf_description",
]


JIRA_PROVIDER_ID = "jira"
DEFAULT_JIRA_API_VERSION = 3  # Jira Cloud commonly uses /rest/api/3 (Server/DC often uses /rest/api/2)

# Common Jira/Atlassian correlation headers
_REQUEST_ID_KEYS = (
    "x-arequestid",
    "x-request-id",
    "x-trace-id",
    "x-correlation-id",
)


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
# Minimal Atlassian Document Format helper (Jira Cloud v3 description)
# =============================================================================


def make_adf_description(text: str) -> Mapping[str, Any]:
    """
    Build a minimal Atlassian Document Format (ADF) document with one paragraph.

    Jira Cloud API v3 uses ADF for fields like "description". This helper avoids
    forcing callers to handcraft ADF for simple text.

    If you already have an ADF dict, pass it directly to create_issue(..., description_adf=...).
    """
    t = "" if text is None else str(text)
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": t}],
            }
        ],
    }


# =============================================================================
# Config + response model
# =============================================================================


@dataclass(frozen=True, slots=True)
class JiraConfig:
    """
    Jira connector configuration.

    base_url examples:
      - Jira Cloud:           https://your-domain.atlassian.net
      - Server/Data Center:   https://jira.example.com
      - with path prefix:     https://jira.example.com/jira

    If base_url already ends with /rest/api/<n>, we treat that as the API prefix.
    Otherwise, we append /rest/api/<api_version>.

    auth_mode:
      - "basic"  : Authorization: Basic base64(username:token)
      - "bearer" : Authorization: Bearer <token>

    Safety:
      - token is never logged
      - username is not secret, but still treated carefully in logs
    """

    base_url: str

    api_version: int = DEFAULT_JIRA_API_VERSION

    # Auth
    auth_mode: str = "basic"  # "basic" | "bearer"
    username: str | None = None
    username_env: str = "JIRA_EMAIL"

    token: str | None = None
    token_env: str = "JIRA_API_TOKEN"

    user_agent: str = "Francis/2.0 (connectors.saas.jira)"

    timeout_s: float = 20.0
    verify_tls: bool = True
    ca_file: str | None = None

    # Conservative limits
    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    # Retry policy (idempotent only)
    backoff_policy: SaasBackoffPolicy = field(default_factory=SaasBackoffPolicy)

    # Extra headers (safe defaults; do not place secrets here)
    default_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not (self.base_url or "").strip():
            raise SaasValidationError(
                "base_url is required",
                details={"field": "base_url"},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.config.validate"),
            )
        if self.timeout_s <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": self.timeout_s},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.config.validate"),
            )
        am = (self.auth_mode or "").strip().lower()
        if am not in ("basic", "bearer"):
            raise SaasValidationError(
                "auth_mode must be 'basic' or 'bearer'",
                details={"auth_mode": redact_value(am)},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.config.validate"),
            )
        if int(self.api_version) <= 0:
            raise SaasValidationError(
                "api_version must be a positive integer",
                details={"api_version": self.api_version},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class JiraHttpResponse:
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
                    provider_id=JIRA_PROVIDER_ID,
                    operation="jira.response.json",
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
            "headers": redact_mapping(self.headers),
            "body_len": len(b),
            "body_hash": _hash_stable(b[:256].hex()),
            "rate_limit": dict(self.rate_limit) if self.rate_limit else {},
        }


# =============================================================================
# URL + header helpers
# =============================================================================


@dataclass(frozen=True, slots=True)
class _BaseUrl:
    scheme: str
    host: str
    port: int

    root_prefix: str  # path prefix without /rest/api/<n>
    api_prefix: str  # full prefix including /rest/api/<n>

    canonical_root: str
    canonical_api: str


_REST_API_SUFFIX_RE = re.compile(r"(?P<prefix>.*)/rest/api/(?P<ver>\d+)$")


def _normalize_base_url(base_url: str, api_version: int) -> _BaseUrl:
    raw = (base_url or "").strip()
    p = urlsplit(raw)

    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.base_url"),
        )

    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.base_url"),
        )

    path = (p.path or "").rstrip("/")
    m = _REST_API_SUFFIX_RE.match(path)
    if m:
        root_prefix = (m.group("prefix") or "").rstrip("/")
        api_prefix = path  # already includes /rest/api/<ver>
    else:
        root_prefix = path
        api_prefix = (path.rstrip("/") + f"/rest/api/{int(api_version)}") if path else f"/rest/api/{int(api_version)}"

    canonical_netloc = (
        f"{host}:{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else host
    )
    canonical_root = urlunsplit((scheme, canonical_netloc, root_prefix, "", ""))
    canonical_api = urlunsplit((scheme, canonical_netloc, api_prefix, "", ""))

    return _BaseUrl(
        scheme=scheme,
        host=host,
        port=port,
        root_prefix=root_prefix,
        api_prefix=api_prefix,
        canonical_root=canonical_root,
        canonical_api=canonical_api,
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
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.headers"),
            )
        out[kk] = vv
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    Jira/Atlassian rate limit signals vary; parse what we can.

    Common:
      - Retry-After
      - X-RateLimit-Remaining / X-RateLimit-Limit / X-RateLimit-Reset
      - RateLimit-Remaining / RateLimit-Limit / RateLimit-Reset
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

    for prefix in ("X-RateLimit", "RateLimit"):
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


def _extract_request_id(headers: Mapping[str, str]) -> str | None:
    for k in _REQUEST_ID_KEYS:
        v = headers.get(k) or headers.get(k.upper()) or headers.get(k.title())
        if v:
            s = str(v).strip()
            if s:
                return s
    return None


def _extract_message_from_body(resp: JiraHttpResponse) -> str | None:
    """
    Best-effort extraction of a concise error message from Jira error payloads.
    Never returns the full body.
    """
    try:
        data = resp.json()
    except Exception:
        return None

    # Common Jira patterns:
    # - {"errorMessages":["..."], "errors":{...}}
    # - {"message":"..."}
    if isinstance(data, Mapping):
        em = data.get("errorMessages")
        if isinstance(em, Sequence) and not isinstance(em, (str, bytes, bytearray)) and em:
            first = em[0]
            if isinstance(first, str) and first.strip():
                return first.strip()

        msg = data.get("message")
        if isinstance(msg, str) and msg.strip():
            return msg.strip()

        # If "errors" is a dict, return keys summary only
        errs = data.get("errors")
        if isinstance(errs, Mapping) and errs:
            keys = list(errs.keys())[:10]
            return f"errors: {', '.join(str(k) for k in keys)}"

    return None


# =============================================================================
# Connector
# =============================================================================


class JiraConnector(SaasConnector):
    """
    Jira SaaS connector.

    Exposes:
      - info(), health_check()
      - request_* helpers (REST)
      - search pagination helpers
      - convenience methods
    """

    def __init__(self, config: JiraConfig) -> None:
        if config is None:
            raise SaasValidationError(
                "config is required",
                context=SaasErrorContext(provider_id=JIRA_PROVIDER_ID, operation="jira.init"),
            )

        pid = normalize_provider_id(JIRA_PROVIDER_ID)
        object.__setattr__(self, "_provider_id", pid)
        object.__setattr__(self, "_cfg", config)
        object.__setattr__(self, "_base", _normalize_base_url(config.base_url, int(config.api_version)))

        # Resolve secrets from env if not provided
        tok = config.token or (os.environ.get(config.token_env) or "").strip() or None
        usr = config.username or (os.environ.get(config.username_env) or "").strip() or None
        object.__setattr__(self, "_token", tok)
        object.__setattr__(self, "_username", usr)

        # Prebuild SSL context
        ctx: ssl.SSLContext | None = None
        if self._base.scheme == "https":
            if config.verify_tls:
                ctx = ssl.create_default_context(cafile=config.ca_file)
            else:
                ctx = ssl._create_unverified_context()  # noqa: SLF001
        object.__setattr__(self, "_ssl_context", ctx)

    # ---- contract -----------------------------------------------------------

    def info(self) -> SaasConnectorInfo:
        return SaasConnectorInfo(
            provider_id=self._provider_id,
            name="Jira Connector",
            version=None,
            description="Jira REST connector (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest",
                "jql_search",
                "pagination",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical_root),
                "api_base": redact_url(self._base.canonical_api),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "auth_mode": self._cfg.auth_mode,
                "has_token": bool(self._token),
                "has_username": bool(self._username),
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If token present: GET /myself  (validates auth)
          - Else:            GET /serverInfo (connectivity check; may be allowed on some installs)
        """
        op = "jira.health_check"
        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)

        try:
            if self._token:
                data = self.request_json("GET", "/myself", operation=op, timeout_s=tmo, idempotent=True)
                acct = None
                try:
                    if isinstance(data, Mapping):
                        acct = data.get("accountId") or data.get("name") or data.get("emailAddress")
                except Exception:
                    acct = None
                return SaasHealth(
                    ok=True,
                    degraded=False,
                    message="ok",
                    details={
                        "api_base": redact_url(self._base.canonical_api),
                        "auth": "ok",
                        "account_hash": _hash_stable(str(acct or "")) if acct else None,
                    },
                )

            data = self.request_json("GET", "/serverInfo", operation=op, timeout_s=tmo, idempotent=True)
            ver = None
            try:
                if isinstance(data, Mapping):
                    ver = data.get("version")
            except Exception:
                ver = None
            return SaasHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "api_base": redact_url(self._base.canonical_api),
                    "auth": "none",
                    "version_hash": _hash_stable(str(ver or "")) if ver else None,
                },
            )

        except SaasRateLimitError as exc:
            return SaasHealth(
                ok=False,
                degraded=True,
                message="rate_limited",
                details={
                    "api_base": redact_url(self._base.canonical_api),
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
                    "api_base": redact_url(self._base.canonical_api),
                    "error": redact_value(str(exc)),
                    "context": exc.redacted_context(),
                },
            )

    # ---- public REST helpers ------------------------------------------------

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
    ) -> JiraHttpResponse:
        """
        Perform a Jira REST request and return a low-level JiraHttpResponse.

        The path is relative to the Jira REST API prefix:
          e.g. "/issue/ABC-1" -> "{api_prefix}/issue/ABC-1"

        Retries:
          - only if idempotent is True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "jira.request"),
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

        # Build full path under API prefix
        full_path = self._base.api_prefix.rstrip("/") + pth
        url = urlunsplit((self._base.scheme, self._base.host, full_path, query, ""))

        # Headers (safe)
        hdrs: dict[str, str] = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/json")

        # Auth (never log token)
        self._apply_auth_headers(hdrs, operation=operation or "jira.request")

        # Encode body
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
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "jira.request"),
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
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "jira.request"),
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

                self._raise_for_status(resp, operation=operation or "jira.request")
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

    # ---- convenience methods -----------------------------------------------

    def get_myself(self) -> Mapping[str, Any]:
        """
        GET /myself (requires auth on most installs).
        """
        if not self._token:
            raise SaasAuthError(
                "jira token required for /myself",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.get_myself"),
                code="token_required",
            )
        data = self.request_json("GET", "/myself", operation="jira.get_myself", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected /myself response type",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation="jira.get_myself",
                    details={"type": type(data).__name__},
                ),
                code="unexpected_response",
            )
        return data

    def get_issue(self, issue_key: str, *, fields: Sequence[str] | None = None) -> Mapping[str, Any]:
        """
        GET /issue/{issueKey}
        """
        k = (issue_key or "").strip()
        if not k:
            raise SaasValidationError(
                "issue_key is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.get_issue"),
            )

        params: dict[str, Any] = {}
        if fields:
            params["fields"] = ",".join(str(f).strip() for f in fields if str(f).strip())

        data = self.request_json(
            "GET",
            f"/issue/{quote(k, safe='')}",
            params=params,
            operation="jira.get_issue",
            idempotent=True,
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected issue response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.get_issue"),
                code="unexpected_response",
            )
        return data

    def search_jql(
        self,
        jql: str,
        *,
        fields: Sequence[str] | None = None,
        start_at: int = 0,
        max_results: int = 50,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /search

        Jira supports GET /search with query params too, but POST is safer for long JQL.
        """
        q = (jql or "").strip()
        if not q:
            raise SaasValidationError(
                "jql is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.search_jql"),
            )

        payload: dict[str, Any] = {
            "jql": q,
            "startAt": int(start_at),
            "maxResults": int(max_results),
        }
        if fields:
            payload["fields"] = [str(f).strip() for f in fields if str(f).strip()]

        data = self.request_json(
            "POST",
            "/search",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=True,  # safe to retry; search is read-only
            operation="jira.search_jql",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected search response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.search_jql"),
                code="unexpected_response",
            )
        return data

    def iter_search_issues(
        self,
        jql: str,
        *,
        fields: Sequence[str] | None = None,
        page_size: int = 50,
        max_pages: int = 100,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate issues for a JQL query using Jira pagination (startAt/maxResults/total).

        Yields each issue (dict) from the "issues" array.
        """
        start_at = 0
        pages = 0

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            data = self.search_jql(
                jql,
                fields=fields,
                start_at=start_at,
                max_results=int(page_size),
                timeout_s=timeout_s,
            )

            issues = data.get("issues") if isinstance(data, Mapping) else None
            if not isinstance(issues, Sequence) or isinstance(issues, (str, bytes, bytearray)):
                break

            for it in issues:
                if isinstance(it, Mapping):
                    yield it

            # Pagination fields
            try:
                total = int(data.get("total", 0))
                maxr = int(data.get("maxResults", page_size))
                start = int(data.get("startAt", start_at))
            except Exception:
                break

            start_at = start + maxr
            if start_at >= total:
                break
            if not issues:
                break

    def create_issue(
        self,
        *,
        project_key: str,
        summary: str,
        issue_type: str = "Task",
        description: str | None = None,
        description_adf: Mapping[str, Any] | None = None,
        fields: Mapping[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /issue

        - Not idempotent (no automatic retries).
        - For Jira API v3, description should be ADF. If description_adf is not provided
          and description is a string, we auto-wrap into a minimal ADF document.

        Parameters:
          - project_key: e.g. "ENG"
          - summary: short summary
          - issue_type: e.g. "Task", "Bug", "Story"
          - fields: additional Jira fields merged into payload
        """
        if not self._token:
            raise SaasAuthError(
                "jira token required to create issues",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.create_issue"),
                code="token_required",
            )

        pk = (project_key or "").strip()
        sm = (summary or "").strip()
        it = (issue_type or "").strip()
        if not pk or not sm or not it:
            raise SaasValidationError(
                "project_key, summary, and issue_type are required",
                details={
                    "project_key": redact_value(pk),
                    "summary_len": len(sm),
                    "issue_type": redact_value(it),
                },
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.create_issue"),
            )

        payload_fields: dict[str, Any] = {
            "project": {"key": pk},
            "summary": sm,
            "issuetype": {"name": it},
        }

        # Description handling
        if description_adf is not None:
            payload_fields["description"] = dict(description_adf)
        elif description is not None:
            # Jira Cloud v3 commonly expects ADF; v2 expects string.
            # If our configured API prefix ends with /rest/api/3, use ADF; otherwise send string.
            if self._base.api_prefix.endswith("/rest/api/3"):
                payload_fields["description"] = make_adf_description(description)
            else:
                payload_fields["description"] = str(description)

        # Merge extra fields
        if fields:
            # Caller can override defaults if needed.
            for k, v in fields.items():
                payload_fields[str(k)] = v

        payload = {"fields": payload_fields}

        data = self.request_json(
            "POST",
            "/issue",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="jira.create_issue",
        )

        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected create_issue response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="jira.create_issue"),
                code="unexpected_response",
            )
        return data

    # ---- internals ----------------------------------------------------------

    def _apply_auth_headers(self, hdrs: MutableMapping[str, str], *, operation: str) -> None:
        """
        Apply authentication headers based on config.

        SAFETY: never logs token content.
        """
        am = (self._cfg.auth_mode or "").strip().lower()
        tok = self._token

        if not tok:
            # No auth; allow for public endpoints / serverInfo on some installs.
            return

        if am == "bearer":
            hdrs.setdefault("Authorization", f"Bearer {tok}")
            return

        if am == "basic":
            usr = self._username
            if not usr:
                raise SaasAuthError(
                    "jira username/email required for basic auth",
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation),
                    code="username_required",
                )
            token_bytes = f"{usr}:{tok}".encode("utf-8", errors="strict")
            b64 = base64.b64encode(token_bytes).decode("ascii")
            hdrs.setdefault("Authorization", f"Basic {b64}")
            return

        raise SaasUnsupportedError(
            "unsupported auth_mode",
            context=SaasErrorContext(provider_id=self._provider_id, operation=operation, details={"auth_mode": am}),
            code="unsupported_auth_mode",
        )

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
    ) -> JiraHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError.
        """
        op = operation or "jira.request"
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
                        endpoint=self._base.canonical_api,
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

            rid = _extract_request_id({k.lower(): v for k, v in hdr_map.items()})
            rate = _parse_rate_limit_headers({k.lower(): v for k, v in hdr_map.items()})

            return JiraHttpResponse(
                method=method,
                url=url,
                status=status,
                reason=reason,
                headers=hdr_map,
                body=raw,
                request_id=rid,
                rate_limit=rate,
            )

        except ssl.SSLError as exc:
            raise SaasNetworkError(
                "TLS error contacting Jira endpoint",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=op,
                    endpoint=self._base.canonical_api,
                    details={"url": redact_url(url)},
                ),
                code="tls_error",
                cause=exc,
            ) from exc

        except (OSError, http.client.HTTPException) as exc:
            raise SaasNetworkError(
                "network error contacting Jira endpoint",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation=op,
                    endpoint=self._base.canonical_api,
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

    def _raise_for_status(self, resp: JiraHttpResponse, *, operation: str) -> None:
        """
        Map HTTP status to SaaS-layer errors.

        IMPORTANT: do not attach raw body. Only attach safe summaries.
        """
        status = int(resp.status)
        msg = _extract_message_from_body(resp)

        retry_after = None
        if resp.rate_limit:
            retry_after = resp.rate_limit.get("retry_after_s")
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
            endpoint=self._base.canonical_api,
            details={
                "method": resp.method,
                "url": redact_url(resp.url),
                "rate_limit": dict(resp.rate_limit) if resp.rate_limit else {},
                "body_len": len(resp.body or b""),
                "body_hash": _hash_stable((resp.body or b"")[:256].hex()),
            },
        )

        if status == 401:
            raise SaasAuthError(msg or "unauthorized", context=ctx, code="http_401")

        if status == 403:
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
