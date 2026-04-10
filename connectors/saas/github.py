"""
===============================================================================
Francis 2.0 — SaaS Connectors (GitHub)
Path: connectors/saas/github.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a GitHub SaaS connector on top of the provider-agnostic
contract in connectors/saas/__init__.py.

Design goals:
  - Safe-by-default observability:
      * never logs tokens
      * never logs raw response bodies
      * summaries include hashes/lengths only
  - Deterministic, synchronous behavior using only the Python standard library:
      * http.client + ssl for HTTPS
  - Clear error taxonomy mapping to SaaS-layer errors:
      * auth vs permission vs rate limit vs not found vs validation vs unavailable
  - Retry semantics:
      * retries only for idempotent operations by default (GET/HEAD/OPTIONS)
      * retries only for retryable failures (network/unavailable/rate-limit)

NOTES
-----
- This is intentionally a small “foundation” connector:
    * health_check()
    * REST request helpers (request_json, request_bytes)
    * GraphQL helper
    * a few convenience helpers (get_user, get_repo, create_issue)
- It does NOT implement a full GitHub SDK. Keep higher-level behaviors in
  service layers above connectors.

AUTH
----
- Token is optional (for public endpoints).
- Token resolution order:
    1) GithubConfig.token (explicit)
    2) Environment variable GithubConfig.token_env (default: GITHUB_TOKEN)

No secrets should ever be hardcoded into repo files.

===============================================================================
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import http.client
import json
import os
import ssl
import time
import hashlib
from urllib.parse import urlencode, urlsplit, urlunsplit

from . import (
    SaasBackoffPolicy,
    SaasConnector,
    SaasConnectorInfo,
    SaasError,
    SaasErrorContext,
    SaasHealth,
    SaasIdentity,
    SaasValidationError,
    SaasAuthError,
    SaasPermissionError,
    SaasNotFoundError,
    SaasConflictError,
    SaasRateLimitError,
    SaasUnavailableError,
    SaasNetworkError,
    compute_backoff_s,
    normalize_provider_id,
    redact_url,
    redact_value,
)

__all__ = [
    "GITHUB_PROVIDER_ID",
    "DEFAULT_GITHUB_API_BASE_URL",
    "GithubConfig",
    "GithubHttpResponse",
    "GithubConnector",
    # Helpers
    "parse_github_link_header",
]


GITHUB_PROVIDER_ID = "github"
DEFAULT_GITHUB_API_BASE_URL = "https://api.github.com"


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
class GithubConfig:
    """
    GitHub connector configuration.

    base_url:
      - GitHub.com REST:      https://api.github.com
      - GitHub Enterprise:    https://github.company.com/api/v3
      - (GraphQL is /graphql relative to base_url root for github.com; for GHE it is typically /api/graphql
         but many deployments also support /graphql. We handle both with a fallback strategy.)

    token:
      - Personal access token / fine-grained token / GitHub App installation token
      - optional for public endpoints

    Safety:
      - token is never logged
    """

    base_url: str = DEFAULT_GITHUB_API_BASE_URL

    token: str | None = None
    token_env: str = "GITHUB_TOKEN"

    user_agent: str = "Francis/2.0 (connectors.saas.github)"
    api_version: str | None = "2022-11-28"  # GitHub API version header (recommended)

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
                context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class GithubHttpResponse:
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
                    provider_id=GITHUB_PROVIDER_ID,
                    operation="github.response.json",
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
            "status": self.status,
            "ok": self.ok,
            "url": self.url_redacted,
            "method": self.method,
            "request_id": self.request_id,
            "body_len": len(b),
            "body_sha256": _hash_stable(b),
            "rate_limit": dict(self.rate_limit) if self.rate_limit else {},
        }


def parse_github_link_header(link_header: str | None) -> dict[str, str]:
    """
    Parse GitHub-style Link header:
      <https://api.github.com/...>; rel="next", <...>; rel="last"

    Returns:
      { "next": "https://...", "last": "https://...", ... }
    """
    if not link_header:
        return {}
    out: dict[str, str] = {}
    parts = [p.strip() for p in link_header.split(",") if p.strip()]
    for part in parts:
        if ";" not in part:
            continue
        url_part, *params = [x.strip() for x in part.split(";") if x.strip()]
        if not (url_part.startswith("<") and url_part.endswith(">")):
            continue
        url = url_part[1:-1].strip()
        rel = None
        for prm in params:
            if prm.lower().startswith("rel="):
                val = prm.split("=", 1)[1].strip().strip('"').strip("'")
                rel = val
                break
        if rel:
            out[rel] = url
    return out


# =============================================================================
# Connector
# =============================================================================


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
            context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.base_url"),
        )
    p = urlsplit(raw)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.base_url"),
        )
    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.base_url"),
        )

    # Remove trailing slash for prefix logic
    path_prefix = (p.path or "").rstrip("/")
    canonical = urlunsplit(
        (
            scheme,
            f"{host}:{port}" if (scheme == "http" and port != 80) or (scheme == "https" and port != 443) else host,
            path_prefix,
            "",
            "",
        )
    )
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
                context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=GITHUB_PROVIDER_ID, operation="github.headers"),
            )
        out[kk] = vv
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    GitHub rate limit headers (when present):
      - X-RateLimit-Limit
      - X-RateLimit-Remaining
      - X-RateLimit-Reset (epoch seconds)
      - X-RateLimit-Used
      - Retry-After (seconds)  [sometimes for abuse/secondary rate limits]
    """

    def _get_int(name: str) -> int | None:
        v = headers.get(name) or headers.get(name.lower())
        if v is None:
            return None
        try:
            return int(str(v).strip())
        except Exception:
            return None

    out: dict[str, Any] = {}
    limit = _get_int("X-RateLimit-Limit")
    remaining = _get_int("X-RateLimit-Remaining")
    reset = _get_int("X-RateLimit-Reset")
    used = _get_int("X-RateLimit-Used")
    retry_after = _get_int("Retry-After")

    if limit is not None:
        out["limit"] = limit
    if remaining is not None:
        out["remaining"] = remaining
    if reset is not None:
        out["reset"] = reset
    if used is not None:
        out["used"] = used
    if retry_after is not None:
        out["retry_after_s"] = retry_after
    return out


class GithubConnector(SaasConnector):
    """
    GitHub SaaS connector.

    Exposes:
      - info(), health_check()
      - request_* helpers
      - a few common convenience API methods
    """

    def __init__(self, config: GithubConfig | None = None) -> None:
        cfg = config or GithubConfig()
        pid = normalize_provider_id(GITHUB_PROVIDER_ID)
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
            name="GitHub Connector",
            version=None,
            description="GitHub REST/GraphQL connector (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest",
                "graphql",
                "pagination",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "has_token": bool(self._token),
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If token is present: GET /user (validates auth)
          - Else: GET /rate_limit (public endpoint) to validate connectivity
        """
        op = "github.health_check"
        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)
        try:
            if self._token:
                data = self.request_json("GET", "/user", operation=op, timeout_s=tmo, idempotent=True)
                login = None
                try:
                    if isinstance(data, Mapping):
                        login = data.get("login")
                except Exception:
                    login = None
                return SaasHealth(
                    ok=True,
                    degraded=False,
                    message="ok",
                    details={
                        "base_url": redact_url(self._base.canonical),
                        "auth": "ok",
                        "user_login_hash": _hash_stable(str(login or "")) if login else None,
                    },
                )

            data = self.request_json("GET", "/rate_limit", operation=op, timeout_s=tmo, idempotent=True)
            # If reachable, ok. If remaining=0, degraded.
            core = None
            remaining = None
            try:
                if isinstance(data, Mapping):
                    resources = data.get("resources")
                    if isinstance(resources, Mapping):
                        core = resources.get("core")
                        if isinstance(core, Mapping):
                            remaining = core.get("remaining")
            except Exception:
                remaining = None
            degraded = remaining == 0
            return SaasHealth(
                ok=True,
                degraded=bool(degraded),
                message="ok" if not degraded else "rate_limited",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "none",
                    "remaining": remaining,
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
    ) -> GithubHttpResponse:
        """
        Perform a GitHub REST request and return a low-level GithubHttpResponse.

        Retries:
          - only if idempotent is True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "github.request"),
            )

        # Default idempotency by method if not provided.
        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        p = (path or "").strip()
        if not p.startswith("/"):
            p = "/" + p

        # Encode query params
        query = ""
        if params:
            # Remove None values (common)
            clean: dict[str, Any] = {str(k): v for k, v in params.items() if v is not None}
            query = urlencode(clean, doseq=True)
        full_path = self._base.path_prefix + p
        url = urlunsplit((self._base.scheme, self._base.host, full_path, query, ""))

        # Build headers
        hdrs = {}
        hdrs.update(_safe_header_copy(self._cfg.default_headers))
        hdrs.update(_safe_header_copy(headers))
        hdrs.setdefault("User-Agent", self._cfg.user_agent)
        hdrs.setdefault("Accept", "application/vnd.github+json")
        if self._cfg.api_version:
            hdrs.setdefault("X-GitHub-Api-Version", self._cfg.api_version)

        # Auth header (never logged)
        if self._token:
            hdrs.setdefault("Authorization", f"Bearer {self._token}")

        # Encode body
        send_body: bytes | None = None
        if json_body is not None:
            try:
                send_body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode(
                    "utf-8"
                )
            except Exception as exc:  # noqa: BLE001
                raise SaasValidationError(
                    "failed to encode json_body",
                    details={"json_body_shape": _shape_value(json_body)},
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "github.request"),
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
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "github.request"),
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

                # Map response codes to typed errors
                if resp.ok():
                    return resp

                self._raise_for_status(resp, operation=operation or "github.request")

                # If _raise_for_status didn't raise, return anyway.
                return resp

            except SaasError as exc:
                # Only retry if explicitly idempotent and the error is retryable.
                if bool(idempotent) and getattr(exc, "retryable", False):
                    attempt += 1
                    if attempt > max_attempts:
                        raise

                    delay = compute_backoff_s(policy, attempt=attempt)

                    # If rate limit indicates a retry-after, prefer it (but don’t sleep forever).
                    ra = getattr(exc, "retry_after_s", None)
                    if isinstance(ra, (int, float)) and ra is not None:
                        delay = max(delay, float(ra))

                    # Clamp delay to policy.max_s
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
        Perform a request and decode JSON.

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
    ) -> Any:
        """
        Perform a GitHub GraphQL request.

        Endpoint behavior:
          - GitHub.com: POST /graphql
          - Some GHE:    POST /api/graphql
        We try /graphql first (relative to base_url path prefix), and if 404, fallback
        to /api/graphql (only once).
        """
        if not (query or "").strip():
            raise SaasValidationError(
                "graphql query is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "github.graphql"),
            )

        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        if operation_name is not None:
            payload["operationName"] = str(operation_name)

        op = operation or "github.graphql"

        # Attempt 1: /graphql
        try:
            data = self.request_json(
                "POST",
                "/graphql",
                json_body=payload,
                timeout_s=timeout_s,
                idempotent=idempotent,
                operation=op,
            )
        except SaasNotFoundError:
            # Attempt 2: /api/graphql (common on some enterprise installs)
            data = self.request_json(
                "POST",
                "/api/graphql",
                json_body=payload,
                timeout_s=timeout_s,
                idempotent=idempotent,
                operation=op,
            )

        # GraphQL layer errors are inside the JSON payload.
        if isinstance(data, Mapping) and data.get("errors"):
            # Avoid dumping full errors; include shape + message hashes only.
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
                    endpoint=self._base.canonical,
                    details={"errors_shape": _shape_value(errs), "message_hashes": msg_hashes},
                ),
                code="graphql_error",
            )

        return data

    # ---- common convenience methods ----------------------------------------

    def get_authenticated_user(self) -> Mapping[str, Any]:
        """
        GET /user (requires token).
        """
        if not self._token:
            raise SaasAuthError(
                "github token required for /user",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.get_authenticated_user"),
                code="token_required",
            )
        data = self.request_json("GET", "/user", operation="github.get_authenticated_user", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected /user response type",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation="github.get_authenticated_user",
                    details={"type": type(data).__name__},
                ),
                code="unexpected_response",
            )
        return data

    def get_user(self, username: str) -> Mapping[str, Any]:
        """
        GET /users/{username}
        """
        u = (username or "").strip()
        if not u:
            raise SaasValidationError(
                "username is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.get_user"),
            )
        data = self.request_json("GET", f"/users/{u}", operation="github.get_user", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected user response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.get_user"),
                code="unexpected_response",
            )
        return data

    def get_repo(self, owner: str, repo: str) -> Mapping[str, Any]:
        """
        GET /repos/{owner}/{repo}
        """
        o = (owner or "").strip()
        r = (repo or "").strip()
        if not o or not r:
            raise SaasValidationError(
                "owner and repo are required",
                details={"owner": redact_value(o), "repo": redact_value(r)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.get_repo"),
            )
        data = self.request_json("GET", f"/repos/{o}/{r}", operation="github.get_repo", idempotent=True)
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected repo response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.get_repo"),
                code="unexpected_response",
            )
        return data

    def create_issue(
        self,
        owner: str,
        repo: str,
        *,
        title: str,
        body: str | None = None,
        labels: Sequence[str] | None = None,
        assignees: Sequence[str] | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /repos/{owner}/{repo}/issues

        NOTE: Not idempotent by default (no automatic retries).
        """
        if not self._token:
            raise SaasAuthError(
                "github token required to create issues",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.create_issue"),
                code="token_required",
            )
        o = (owner or "").strip()
        r = (repo or "").strip()
        t = (title or "").strip()
        if not o or not r or not t:
            raise SaasValidationError(
                "owner, repo, and title are required",
                details={"owner": redact_value(o), "repo": redact_value(r), "title_len": len(t)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.create_issue"),
            )

        payload: dict[str, Any] = {"title": t}
        if body is not None:
            payload["body"] = str(body)
        if labels is not None:
            payload["labels"] = [str(x) for x in labels]
        if assignees is not None:
            payload["assignees"] = [str(x) for x in assignees]

        data = self.request_json(
            "POST",
            f"/repos/{o}/{r}/issues",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,  # important
            operation="github.create_issue",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected create_issue response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="github.create_issue"),
                code="unexpected_response",
            )
        return data

    # ---- pagination helper --------------------------------------------------

    def iter_paginated(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        timeout_s: float | None = None,
        operation: str | None = None,
        max_pages: int = 50,
    ) -> Iterable[Any]:
        """
        Iterate through GitHub paginated endpoints by following Link: rel="next".

        - Assumes each page returns a JSON array.
        - Idempotent by nature (GET).
        """
        op = operation or "github.iter_paginated"
        current_path = path
        current_params = dict(params or {})
        pages = 0

        while True:
            pages += 1
            if pages > max_pages:
                break

            resp = self.request_bytes(
                method,
                current_path,
                params=current_params,
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
                # If not list, yield once and stop.
                yield data
                break

            link = resp.headers.get("Link") or resp.headers.get("link")
            links = parse_github_link_header(link)
            nxt = links.get("next")
            if not nxt:
                break

            # Convert absolute next URL into a path+query relative to our base.
            try:
                p = urlsplit(nxt)
                current_path = p.path
                current_params = {k: v[0] if len(v) == 1 else v for k, v in ({} if not p.query else dict())}  # reset
                # Parse query properly:
                if p.query:
                    # lightweight parse without importing parse_qs (keep deps minimal)
                    qd: dict[str, list[str]] = {}
                    for part in p.query.split("&"):
                        if not part:
                            continue
                        if "=" in part:
                            k, v = part.split("=", 1)
                        else:
                            k, v = part, ""
                        k = k.replace("+", " ")
                        v = v.replace("+", " ")
                        qd.setdefault(k, []).append(v)
                    # keep doseq behavior by storing lists when needed
                    cp: dict[str, Any] = {}
                    for k, vals in qd.items():
                        cp[k] = vals[0] if len(vals) == 1 else vals
                    current_params = cp
            except Exception:
                break

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
    ) -> GithubHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError / SaasUnavailableError.
        """
        op = operation or "github.request"
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

            # Normalize headers into simple dict[str,str]
            hdr_map: dict[str, str] = {}
            for k, v in resp.getheaders():
                if k is None:
                    continue
                kk = str(k)
                vv = "" if v is None else str(v)
                hdr_map[kk] = vv

            request_id = (
                hdr_map.get("x-github-request-id")
                or hdr_map.get("X-GitHub-Request-Id")
                or hdr_map.get("X-GitHub-Request-ID")
            )
            rate = _parse_rate_limit_headers(hdr_map)

            return GithubHttpResponse(
                method=method,
                url=url,
                status=status,
                reason=reason,
                headers=hdr_map,
                body=raw,
                request_id=request_id,
                rate_limit=rate,
            )

        except (ssl.SSLError,) as exc:
            raise SaasNetworkError(
                "TLS error contacting GitHub endpoint",
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
            # Treat as retryable network error
            raise SaasNetworkError(
                "network error contacting GitHub endpoint",
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

    def _raise_for_status(self, resp: GithubHttpResponse, *, operation: str) -> None:
        """
        Map HTTP status to SaaS-layer errors.

        IMPORTANT: Do not attach raw body. Only attach safe summaries.
        """
        status = int(resp.status)
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
                # body summary only:
                "body_len": len(resp.body or b""),
                "body_hash": None,  # TODO: compute stable hash
            },
        )

        # Try to extract a small "message" field from JSON (still safe-ish) but never dump entire payload.
        msg = None
        try:
            j = resp.json()
            if isinstance(j, Mapping):
                m = j.get("message")
                if isinstance(m, str) and m.strip():
                    msg = m.strip()
        except Exception:
            msg = None

        # Rate limit detection:
        remaining = None
        reset = None
        retry_after = None
        if resp.rate_limit:
            remaining = resp.rate_limit.get("remaining")
            reset = resp.rate_limit.get("reset")
            retry_after = resp.rate_limit.get("retry_after_s")

        # 401 Unauthorized
        if status == 401:
            raise SaasAuthError(
                msg or "unauthorized",
                context=ctx,
                code="http_401",
            )

        # 403 Forbidden (could be permission OR rate limit OR abuse limit)
        if status == 403:
            # If remaining is 0, treat as rate-limited.
            if remaining == 0 or (isinstance(msg, str) and "rate limit" in msg.lower()):
                ra_s: float | None = None
                if isinstance(retry_after, (int, float)):
                    ra_s = float(retry_after)
                elif isinstance(reset, (int, float)):
                    # reset is epoch seconds
                    now = time.time()
                    delta = float(reset) - float(now)
                    if delta > 0:
                        # Don’t force long sleeps here; we pass hint to caller.
                        ra_s = delta
                raise SaasRateLimitError(
                    msg or "rate limited",
                    context=ctx,
                    code="http_403_rate_limit",
                    retry_after_s=ra_s,
                )

            # Abuse/secondary rate limit sometimes returns Retry-After too.
            if isinstance(retry_after, (int, float)) and retry_after:
                raise SaasRateLimitError(
                    msg or "rate limited",
                    context=ctx,
                    code="http_403_secondary_rate_limit",
                    retry_after_s=float(retry_after),
                )

            raise SaasPermissionError(
                msg or "forbidden",
                context=ctx,
                code="http_403",
            )

        # 404
        if status == 404:
            raise SaasNotFoundError(
                msg or "not found",
                context=ctx,
                code="http_404",
            )

        # 409 conflict
        if status == 409:
            raise SaasConflictError(
                msg or "conflict",
                context=ctx,
                code="http_409",
            )

        # 422 validation
        if status == 422:
            raise SaasValidationError(
                msg or "validation failed",
                context=ctx,
                code="http_422",
            )

        # 429 too many requests
        if status == 429:
            ra_s2: float | None = None
            if isinstance(retry_after, (int, float)):
                ra_s2 = float(retry_after)
            raise SaasRateLimitError(
                msg or "too many requests",
                context=ctx,
                code="http_429",
                retry_after_s=ra_s2,
            )

        # 5xx -> unavailable
        if 500 <= status <= 599:
            raise SaasUnavailableError(
                msg or "service unavailable",
                context=ctx,
                code=f"http_{status}",
            )

        # Other 4xx -> generic error
        raise SaasError(
            msg or f"http error {status}",
            context=ctx,
            code=f"http_{status}",
        )
