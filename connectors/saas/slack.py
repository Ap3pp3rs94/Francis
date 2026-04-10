"""
===============================================================================
Francis 2.0 — SaaS Connectors (Slack)
Path: connectors/saas/slack.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a Slack SaaS connector on top of the provider-agnostic
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
  - Slack-specific correctness:
      * Slack often returns HTTP 200 with {"ok": false, "error": "..."}.
        We map those to typed SaasError subclasses.

NOTES
-----
- This is a foundation connector:
    * health_check() via auth.test
    * request helpers (request_json, request_bytes)
    * cursor pagination helpers (response_metadata.next_cursor)
    * a few common convenience methods (post_message, list_channels, list_users, etc.)
- It is NOT a full Slack SDK.

AUTH
----
Token resolution order:
  1) SlackConfig.token (explicit)
  2) Environment variable SlackConfig.token_env (default: SLACK_BOT_TOKEN)

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
    SaasValidationError,
    compute_backoff_s,
    normalize_provider_id,
    redact_mapping,
    redact_url,
    redact_value,
)

__all__ = [
    "SLACK_PROVIDER_ID",
    "DEFAULT_SLACK_API_BASE_URL",
    "SlackConfig",
    "SlackHttpResponse",
    "SlackConnector",
    # Helpers
    "extract_slack_next_cursor",
]


SLACK_PROVIDER_ID = "slack"
DEFAULT_SLACK_API_BASE_URL = "https://slack.com/api"


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
class SlackConfig:
    """
    Slack connector configuration.

    base_url:
      - Slack Web API: https://slack.com/api

    token:
      - Bot token (xoxb-...), user token (xoxp-...), etc.
      - Most endpoints require auth.

    body_format:
      - "json" (default): send POST bodies as JSON (application/json)
      - "form": send POST bodies as application/x-www-form-urlencoded

    Safety:
      - token is never logged
    """

    base_url: str = DEFAULT_SLACK_API_BASE_URL

    token: str | None = field(default=None, repr=False)
    token_env: str = "SLACK_BOT_TOKEN"

    user_agent: str = "Francis/2.0 (connectors.saas.slack)"

    timeout_s: float = 20.0
    verify_tls: bool = True
    ca_file: str | None = None

    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    # Retry policy (applies only for idempotent requests)
    backoff_policy: SaasBackoffPolicy = field(default_factory=SaasBackoffPolicy)

    # Extra headers (safe defaults; do not place secrets here)
    default_headers: Mapping[str, str] = field(default_factory=dict)

    # Slack Web API: typically JSON is supported for most modern methods
    body_format: str = "json"  # "json" | "form"

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": self.timeout_s},
                context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.config.validate"),
            )
        bf = (self.body_format or "").strip().lower()
        if bf not in ("json", "form"):
            raise SaasValidationError(
                "body_format must be 'json' or 'form'",
                details={"body_format": redact_value(bf)},
                context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class SlackHttpResponse:
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

    def ok_http(self) -> bool:
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
                    provider_id=SLACK_PROVIDER_ID,
                    operation="slack.response.json",
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
# Helpers
# =============================================================================


def extract_slack_next_cursor(payload: Mapping[str, Any] | None) -> str | None:
    """
    Slack cursor pagination:
      payload.get("response_metadata", {}).get("next_cursor")

    Returns a stripped cursor string or None.
    """
    if not payload:
        return None
    try:
        rm = payload.get("response_metadata")
        if isinstance(rm, Mapping):
            cur = rm.get("next_cursor")
            if isinstance(cur, str):
                cur = cur.strip()
                return cur or None
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
            context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.base_url"),
        )

    p = urlsplit(raw)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.base_url"),
        )
    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.base_url"),
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
                context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=SLACK_PROVIDER_ID, operation="slack.headers"),
            )
        out[kk] = vv
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    Slack rate limiting:
      - HTTP 429 with Retry-After header (seconds)
      - may include other rate headers (parse opportunistically)

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
    # Slack often includes: x-slack-req-id
    rid = headers.get("x-slack-req-id") or headers.get("X-Slack-Req-Id") or headers.get("X-Slack-Req-ID")
    if rid:
        s = str(rid).strip()
        return s or None
    return None


# =============================================================================
# Connector
# =============================================================================


class SlackConnector(SaasConnector):
    """
    Slack SaaS connector.

    Exposes:
      - info(), health_check()
      - request helpers:
          request_json, request_bytes
      - cursor pagination helpers
      - convenience methods:
          auth_test, post_message, list_channels, iter_channels, list_users, iter_users
    """

    def __init__(self, config: SlackConfig | None = None) -> None:
        cfg = config or SlackConfig()
        pid = normalize_provider_id(SLACK_PROVIDER_ID)
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
            name="Slack Connector",
            version=None,
            description="Slack Web API connector (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest",
                "cursor_pagination",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "has_token": bool(self._token),
                "body_format": self._cfg.body_format,
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If token present: call auth.test
          - If no token: report degraded/unauthenticated (Slack Web API is mostly auth-required)
        """
        if not self._token:
            return SaasHealth(
                ok=True,
                degraded=True,
                message="unauthenticated",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "none",
                    "note": "No token configured; most Slack endpoints will fail with not_authed.",
                },
            )

        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)
        try:
            data = self.auth_test(timeout_s=tmo)
            team = None
            user = None
            try:
                if isinstance(data, Mapping):
                    team = data.get("team")
                    user = data.get("user")
            except Exception:
                team = None
                user = None

            return SaasHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "ok",
                    "team_hash": _hash_stable(str(team or "")) if team else None,
                    "user_hash": _hash_stable(str(user or "")) if user else None,
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

    # ---- core request helpers ----------------------------------------------

    def request_bytes(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        body: bytes | None = None,
        json_body: Any | None = None,
        form_body: Mapping[str, Any] | None = None,
        timeout_s: float | None = None,
        idempotent: bool | None = None,
        operation: str | None = None,
    ) -> SlackHttpResponse:
        """
        Perform a Slack Web API request and return a SlackHttpResponse.

        - path is relative to base_url path prefix:
            "/auth.test" -> https://slack.com/api/auth.test
            "auth.test"  -> same

        For POST bodies you can provide:
          - json_body: dict (sent as application/json)
          - form_body: dict (sent as application/x-www-form-urlencoded)
          - body: raw bytes (sent as-is; caller should set Content-Type)

        Retries:
          - only if idempotent True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
            )

        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        pth = (path or "").strip()
        if not pth:
            raise SaasValidationError(
                "path is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
            )
        if not pth.startswith("/"):
            pth = "/" + pth

        # Query params (Slack uses query params for many GET endpoints)
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

        # Auth (never log token)
        if self._token:
            hdrs.setdefault("Authorization", f"Bearer {self._token}")

        # Encode body (Slack accepts JSON and form-encoded)
        send_body: bytes | None = None
        if json_body is not None and form_body is not None:
            raise SaasValidationError(
                "Provide only one of json_body or form_body",
                details={
                    "json_body_shape": _shape_value(json_body),
                    "form_body_shape": _shape_value(form_body),
                },
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
            )

        if json_body is not None:
            try:
                send_body = json.dumps(json_body, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode(
                    "utf-8"
                )
            except Exception as exc:  # noqa: BLE001
                raise SaasValidationError(
                    "failed to encode json_body",
                    details={"json_body_shape": _shape_value(json_body)},
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
                    cause=exc,
                ) from exc
            hdrs.setdefault("Content-Type", "application/json; charset=utf-8")
        elif form_body is not None:
            try:
                # Slack expects strings; urlencode handles sequences with doseq=True
                send_body = urlencode({str(k): v for k, v in form_body.items() if v is not None}, doseq=True).encode(
                    "utf-8"
                )
            except Exception as exc:  # noqa: BLE001
                raise SaasValidationError(
                    "failed to encode form_body",
                    details={"form_body_shape": _shape_value(form_body)},
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
                    cause=exc,
                ) from exc
            hdrs.setdefault("Content-Type", "application/x-www-form-urlencoded; charset=utf-8")
        else:
            send_body = body

        if send_body is not None:
            hdrs.setdefault("Content-Length", str(len(send_body)))

        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)
        if tmo <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": tmo},
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "slack.request"),
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

                # HTTP-level errors first
                if not resp.ok_http():
                    self._raise_for_http_status(resp, operation=operation or "slack.request")

                # Slack-level ok:false is still an error
                self._raise_for_slack_payload(resp, operation=operation or "slack.request")

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
        form_body: Mapping[str, Any] | None = None,
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
            form_body=form_body,
            timeout_s=timeout_s,
            idempotent=idempotent,
            operation=operation,
        )
        if resp.status == 204 or not resp.body:
            return None
        return resp.json()

    # ---- Slack API convenience methods -------------------------------------

    def auth_test(self, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /auth.test

        Validates the token and returns team/user context.
        """
        if not self._token:
            raise SaasAuthError(
                "slack token required for auth.test",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.auth_test"),
                code="token_required",
            )
        data = self.request_json("GET", "/auth.test", timeout_s=timeout_s, idempotent=True, operation="slack.auth_test")
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected auth.test response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.auth_test"),
                code="unexpected_response",
            )
        return data

    def post_message(
        self,
        *,
        channel: str,
        text: str | None = None,
        blocks: Sequence[Mapping[str, Any]] | None = None,
        thread_ts: str | None = None,
        mrkdwn: bool | None = None,
        unfurl_links: bool | None = None,
        unfurl_media: bool | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /chat.postMessage (non-idempotent; no automatic retries)

        Uses JSON by default unless config.body_format == "form".
        """
        if not self._token:
            raise SaasAuthError(
                "slack token required to post messages",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.post_message"),
                code="token_required",
            )

        ch = (channel or "").strip()
        if not ch:
            raise SaasValidationError(
                "channel is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.post_message"),
            )

        payload: dict[str, Any] = {"channel": ch}
        if text is not None:
            payload["text"] = str(text)
        if blocks is not None:
            payload["blocks"] = [dict(b) for b in blocks]
        if thread_ts is not None:
            payload["thread_ts"] = str(thread_ts)
        if mrkdwn is not None:
            payload["mrkdwn"] = bool(mrkdwn)
        if unfurl_links is not None:
            payload["unfurl_links"] = bool(unfurl_links)
        if unfurl_media is not None:
            payload["unfurl_media"] = bool(unfurl_media)

        if self._cfg.body_format.strip().lower() == "form":
            return self.request_json(
                "POST",
                "/chat.postMessage",
                form_body=payload,
                timeout_s=timeout_s,
                idempotent=False,
                operation="slack.post_message",
            )
        return self.request_json(
            "POST",
            "/chat.postMessage",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="slack.post_message",
        )

    def conversations_list(
        self,
        *,
        types: str | None = "public_channel,private_channel",
        limit: int = 200,
        cursor: str | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        GET /conversations.list (idempotent)

        Returns the raw response payload (includes channels + response_metadata).
        """
        params: dict[str, Any] = {"limit": int(limit)}
        if types:
            params["types"] = str(types)
        if cursor:
            params["cursor"] = str(cursor)

        data = self.request_json(
            "GET",
            "/conversations.list",
            params=params,
            timeout_s=timeout_s,
            idempotent=True,
            operation="slack.conversations_list",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected conversations.list response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.conversations_list"),
                code="unexpected_response",
            )
        return data

    def iter_channels(
        self,
        *,
        types: str | None = "public_channel,private_channel",
        limit: int = 200,
        max_pages: int = 50,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate channels using conversations.list cursor pagination.

        Yields each channel dict.
        """
        cursor: str | None = None
        pages = 0

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            payload = self.conversations_list(types=types, limit=limit, cursor=cursor, timeout_s=timeout_s)
            chans = payload.get("channels") if isinstance(payload, Mapping) else None
            if isinstance(chans, Sequence) and not isinstance(chans, (str, bytes, bytearray)):
                for ch in chans:
                    if isinstance(ch, Mapping):
                        yield ch

            cursor = extract_slack_next_cursor(payload)
            if not cursor:
                break

    def users_list(
        self,
        *,
        limit: int = 200,
        cursor: str | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        GET /users.list (idempotent)
        """
        params: dict[str, Any] = {"limit": int(limit)}
        if cursor:
            params["cursor"] = str(cursor)

        data = self.request_json(
            "GET",
            "/users.list",
            params=params,
            timeout_s=timeout_s,
            idempotent=True,
            operation="slack.users_list",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected users.list response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.users_list"),
                code="unexpected_response",
            )
        return data

    def iter_users(
        self,
        *,
        limit: int = 200,
        max_pages: int = 50,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate users using users.list cursor pagination.

        Yields each member dict.
        """
        cursor: str | None = None
        pages = 0

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            payload = self.users_list(limit=limit, cursor=cursor, timeout_s=timeout_s)
            members = payload.get("members") if isinstance(payload, Mapping) else None
            if isinstance(members, Sequence) and not isinstance(members, (str, bytes, bytearray)):
                for m in members:
                    if isinstance(m, Mapping):
                        yield m

            cursor = extract_slack_next_cursor(payload)
            if not cursor:
                break

    def users_info(self, user: str, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /users.info (idempotent)
        """
        u = (user or "").strip()
        if not u:
            raise SaasValidationError(
                "user is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.users_info"),
            )
        data = self.request_json(
            "GET",
            "/users.info",
            params={"user": u},
            timeout_s=timeout_s,
            idempotent=True,
            operation="slack.users_info",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected users.info response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="slack.users_info"),
                code="unexpected_response",
            )
        return data

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
    ) -> SlackHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError.
        """
        op = operation or "slack.request"
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

            rid = _extract_request_id({k.lower(): v for k, v in hdr_map.items()})
            rate = _parse_rate_limit_headers({k.lower(): v for k, v in hdr_map.items()})

            return SlackHttpResponse(
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
                "TLS error contacting Slack endpoint",
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
                "network error contacting Slack endpoint",
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

    def _base_ctx(self, resp: SlackHttpResponse, *, operation: str) -> SaasErrorContext:
        return SaasErrorContext(
            provider_id=self._provider_id,
            operation=operation,
            request_id=resp.request_id,
            http_status=int(resp.status),
            endpoint=self._base.canonical,
            details={
                "method": resp.method,
                "url": redact_url(resp.url),
                "rate_limit": dict(resp.rate_limit) if resp.rate_limit else {},
                "body_len": len(resp.body or b""),
                "body_hash": _hash_stable((resp.body or b"")[:256].hex()),
            },
        )

    def _raise_for_http_status(self, resp: SlackHttpResponse, *, operation: str) -> None:
        """
        Map non-2xx HTTP statuses.
        Slack uses 429 for rate limiting, and can use 5xx for outages.
        """
        status = int(resp.status)
        ctx = self._base_ctx(resp, operation=operation)

        retry_after = None
        if resp.rate_limit:
            retry_after = resp.rate_limit.get("retry_after_s")

        if status == 401:
            raise SaasAuthError("unauthorized", context=ctx, code="http_401")

        if status == 403:
            raise SaasPermissionError("forbidden", context=ctx, code="http_403")

        if status == 404:
            raise SaasNotFoundError("not found", context=ctx, code="http_404")

        if status == 409:
            raise SaasConflictError("conflict", context=ctx, code="http_409")

        if status == 429:
            ra_s: float | None = float(retry_after) if isinstance(retry_after, (int, float)) else None
            raise SaasRateLimitError(
                "rate limited",
                context=ctx,
                code="http_429",
                retry_after_s=ra_s,
            )

        if 500 <= status <= 599:
            raise SaasUnavailableError("service unavailable", context=ctx, code=f"http_{status}")

        # Other non-2xx
        raise SaasError(f"http error {status}", context=ctx, code=f"http_{status}")

    def _raise_for_slack_payload(self, resp: SlackHttpResponse, *, operation: str) -> None:
        """
        Slack often returns 200 OK with a JSON body like:
          {"ok": false, "error": "invalid_auth"}

        Convert Slack "error" codes into SaasError subclasses.
        """
        # If it isn't JSON, don’t attempt Slack ok/error mapping
        try:
            payload = resp.json()
        except Exception:
            return

        if not isinstance(payload, Mapping):
            return

        ok = payload.get("ok")
        if ok is True:
            return

        # Slack error pattern
        err = payload.get("error")
        err_code = str(err).strip().lower() if isinstance(err, str) else None

        ctx = self._base_ctx(resp, operation=operation)
        # Include safe hint about Slack error code + top-level fields count
        ctx = SaasErrorContext(
            provider_id=ctx.provider_id,
            operation=ctx.operation,
            request_id=ctx.request_id,
            http_status=ctx.http_status,
            endpoint=ctx.endpoint,
            details={
                **(ctx.details or {}),
                "slack_error": err_code,
                "payload_keys": len(payload),
            },
        )

        retry_after = None
        if resp.rate_limit:
            retry_after = resp.rate_limit.get("retry_after_s")

        # Map common Slack errors
        if err_code in (None, ""):
            raise SaasError("slack api returned ok=false", context=ctx, code="slack_ok_false")

        # Auth
        if err_code in (
            "not_authed",
            "invalid_auth",
            "token_revoked",
            "token_expired",
            "account_inactive",
            "invalid_token",
        ):
            raise SaasAuthError(err_code, context=ctx, code=f"slack_{err_code}")

        # Permission / scope
        if err_code in (
            "missing_scope",
            "not_allowed_token_type",
            "restricted_action",
            "action_not_allowed",
            "user_is_bot",
            "user_is_restricted",
            "user_is_ultra_restricted",
            "cannot_use_admin_endpoints",
        ):
            raise SaasPermissionError(err_code, context=ctx, code=f"slack_{err_code}")

        # Not found-ish
        if err_code in (
            "channel_not_found",
            "user_not_found",
            "file_not_found",
            "not_found",
            "unknown_method",
        ):
            raise SaasNotFoundError(err_code, context=ctx, code=f"slack_{err_code}")

        # Conflict-ish
        if err_code in (
            "name_taken",
            "already_in_channel",
            "already_reacted",
            "already_archived",
        ):
            raise SaasConflictError(err_code, context=ctx, code=f"slack_{err_code}")

        # Validation
        if err_code in (
            "invalid_arguments",
            "invalid_arg_name",
            "invalid_arg_value",
            "invalid_name",
            "invalid_channel",
            "invalid_user",
            "invalid_ts",
            "message_too_long",
            "no_text",
        ):
            raise SaasValidationError(err_code, context=ctx, code=f"slack_{err_code}")

        # Rate limiting (Slack sometimes returns ok:false error=rate_limited)
        if err_code in ("rate_limited",):
            ra_s: float | None = float(retry_after) if isinstance(retry_after, (int, float)) else None
            raise SaasRateLimitError(
                err_code,
                context=ctx,
                code="slack_rate_limited",
                retry_after_s=ra_s,
            )

        # Service issues
        if err_code in ("internal_error", "fatal_error", "service_unavailable", "server_error"):
            raise SaasUnavailableError(err_code, context=ctx, code=f"slack_{err_code}")

        # Default: generic SaasError (retryability unknown; keep non-retryable)
        raise SaasError(err_code, context=ctx, code=f"slack_{err_code}")
