"""
===============================================================================
Francis 2.0 — SaaS Connectors (Notion)
Path: connectors/saas/notion.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module implements a Notion SaaS connector on top of the provider-agnostic
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
- This is a foundation connector:
    * health_check()
    * REST request helpers (request_json, request_bytes)
    * pagination helpers (has_more/next_cursor)
    * a few convenience helpers:
        - get_user_me
        - get_page
        - query_database / iter_query_database
        - search / iter_search
        - create_page (non-idempotent)
        - append_block_children (non-idempotent)

AUTH
----
Token resolution order:
  1) NotionConfig.token (explicit)
  2) Environment variable NotionConfig.token_env (default: NOTION_TOKEN)

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
    "NOTION_PROVIDER_ID",
    "DEFAULT_NOTION_API_BASE_URL",
    "DEFAULT_NOTION_VERSION",
    "NotionConfig",
    "NotionHttpResponse",
    "NotionConnector",
    # Convenience
    "notion_page_id_normalize",
]


NOTION_PROVIDER_ID = "notion"
DEFAULT_NOTION_API_BASE_URL = "https://api.notion.com/v1"
DEFAULT_NOTION_VERSION = "2022-06-28"


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
class NotionConfig:
    """
    Notion connector configuration.

    base_url:
      - Notion Cloud: https://api.notion.com/v1

    notion_version:
      - Required Notion header: "Notion-Version: YYYY-MM-DD"

    token:
      - Notion integration secret token
      - optional for a few public-ish endpoints, but most require auth

    Safety:
      - token is never logged
    """

    base_url: str = DEFAULT_NOTION_API_BASE_URL
    notion_version: str = DEFAULT_NOTION_VERSION

    token: str | None = field(default=None, repr=False)
    token_env: str = "NOTION_TOKEN"

    user_agent: str = "Francis/2.0 (connectors.saas.notion)"

    timeout_s: float = 20.0
    verify_tls: bool = True
    ca_file: str | None = None

    max_response_bytes: int = 10 * 1024 * 1024  # 10MB

    backoff_policy: SaasBackoffPolicy = field(default_factory=SaasBackoffPolicy)
    default_headers: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.timeout_s <= 0:
            raise SaasValidationError(
                "timeout_s must be > 0",
                details={"timeout_s": self.timeout_s},
                context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.config.validate"),
            )
        if self.max_response_bytes <= 0:
            raise SaasValidationError(
                "max_response_bytes must be > 0",
                details={"max_response_bytes": self.max_response_bytes},
                context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.config.validate"),
            )
        if not (self.notion_version or "").strip():
            raise SaasValidationError(
                "notion_version is required",
                details={"field": "notion_version"},
                context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.config.validate"),
            )


@dataclass(frozen=True, slots=True)
class NotionHttpResponse:
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
                    provider_id=NOTION_PROVIDER_ID,
                    operation="notion.response.json",
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


def notion_page_id_normalize(page_id: str) -> str:
    """
    Normalize a Notion UUID-ish id string.

    Notion accepts IDs with or without dashes. We return a dashless lowercase id
    when possible.

    This function is intentionally lenient and does not guarantee the id exists.
    """
    s = (page_id or "").strip().lower()
    if not s:
        raise SaasValidationError(
            "id is required",
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.id.normalize"),
        )
    s = s.replace("-", "")
    return s


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
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.base_url"),
        )

    p = urlsplit(raw)
    scheme = (p.scheme or "").lower()
    if scheme not in ("https", "http"):
        raise SaasValidationError(
            "base_url must be http or https",
            details={"scheme": redact_value(scheme)},
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.base_url"),
        )
    if not p.netloc:
        raise SaasValidationError(
            "base_url missing host",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.base_url"),
        )

    host = p.hostname or ""
    if not host:
        raise SaasValidationError(
            "base_url missing hostname",
            details={"base_url": redact_value(raw)},
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.base_url"),
        )

    port = int(p.port or (443 if scheme == "https" else 80))
    if not (1 <= port <= 65535):
        raise SaasValidationError(
            "base_url port out of range (1..65535)",
            details={"port": port},
            context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.base_url"),
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
                context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.headers"),
            )
        if "\r" in vv or "\n" in vv or "\x00" in vv:
            raise SaasValidationError(
                "header value contains illegal characters",
                details={"header": redact_value(kk)},
                context=SaasErrorContext(provider_id=NOTION_PROVIDER_ID, operation="notion.headers"),
            )
        out[kk] = vv
    return out


def _parse_rate_limit_headers(headers: Mapping[str, str]) -> dict[str, Any]:
    """
    Notion commonly uses:
      - Retry-After (seconds) on 429
    Some infra may include RateLimit-*; we parse common variants opportunistically.
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


def _extract_message_from_body(resp: NotionHttpResponse) -> tuple[str | None, str | None]:
    """
    Best-effort extraction of (message, notion_error_code) from Notion error payloads.

    Notion error payloads often look like:
      {
        "object": "error",
        "status": 401,
        "code": "unauthorized",
        "message": "..."
      }
    """
    try:
        data = resp.json()
    except Exception:
        return None, None

    if isinstance(data, Mapping):
        msg = data.get("message")
        code = data.get("code")
        if isinstance(msg, str) and msg.strip():
            msg_out = msg.strip()
        else:
            msg_out = None
        code_out = str(code).strip() if isinstance(code, str) and str(code).strip() else None
        return msg_out, code_out

    return None, None


# =============================================================================
# Connector
# =============================================================================


class NotionConnector(SaasConnector):
    """
    Notion SaaS connector (stdlib http.client).

    Exposes:
      - info(), health_check()
      - request_bytes(), request_json()
      - query/search pagination helpers
      - common convenience methods
    """

    def __init__(self, config: NotionConfig | None = None) -> None:
        cfg = config or NotionConfig()
        pid = normalize_provider_id(NOTION_PROVIDER_ID)
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
            name="Notion Connector",
            version=None,
            description="Notion REST connector (stdlib http.client).",
            capabilities=(
                "health_check",
                "rest",
                "pagination_cursor",
                "idempotent_retry",
            ),
            meta={
                "base_url": redact_url(self._base.canonical),
                "tls": self._base.scheme == "https",
                "verify_tls": bool(self._cfg.verify_tls),
                "has_token": bool(self._token),
                "notion_version": redact_value(self._cfg.notion_version),
            },
        )

    def health_check(self, *, identity: SaasIdentity | None = None, timeout_s: float | None = None) -> SaasHealth:
        """
        Health check strategy:
          - If token is present: GET /users/me (validates auth + connectivity)
          - Else: try GET /users/me anyway; likely returns 401 but confirms reachability
        """
        op = "notion.health_check"
        tmo = float(timeout_s if timeout_s is not None else self._cfg.timeout_s)

        try:
            data = self.request_json("GET", "/users/me", operation=op, timeout_s=tmo, idempotent=True)
            # If token missing, Notion will likely have raised SaasAuthError already.
            bot_id = None
            try:
                if isinstance(data, Mapping):
                    bot_id = data.get("id")
            except Exception:
                bot_id = None

            return SaasHealth(
                ok=True,
                degraded=False,
                message="ok",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "auth": "ok" if self._token else "none",
                    "bot_id_hash": _hash_stable(str(bot_id or "")) if bot_id else None,
                },
            )

        except SaasAuthError as exc:
            # Treat as reachable but unauthenticated when token is missing.
            if not self._token:
                return SaasHealth(
                    ok=True,
                    degraded=True,
                    message="unauthenticated",
                    details={
                        "base_url": redact_url(self._base.canonical),
                        "auth": "none",
                        "error": redact_value(str(exc)),
                        "context": exc.redacted_context(),
                    },
                )
            return SaasHealth(
                ok=False,
                degraded=False,
                message="unauthorized",
                details={
                    "base_url": redact_url(self._base.canonical),
                    "error": redact_value(str(exc)),
                    "context": exc.redacted_context(),
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
        timeout_s: float | None = None,
        idempotent: bool | None = None,
        operation: str | None = None,
    ) -> NotionHttpResponse:
        """
        Perform a Notion REST request and return a low-level NotionHttpResponse.

        Retries:
          - only if idempotent is True (default for GET/HEAD/OPTIONS)
          - only for retryable failures (network/unavailable/rate-limit)
        """
        m = (method or "").strip().upper()
        if not m:
            raise SaasValidationError(
                "HTTP method is required",
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "notion.request"),
            )

        if idempotent is None:
            idempotent = m in ("GET", "HEAD", "OPTIONS")

        pth = (path or "").strip()
        if not pth.startswith("/"):
            pth = "/" + pth

        # Query params
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
        hdrs.setdefault("Notion-Version", self._cfg.notion_version)

        # Auth (never log token)
        if self._token:
            hdrs.setdefault("Authorization", f"Bearer {self._token}")

        # Body
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
                    context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "notion.request"),
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
                context=SaasErrorContext(provider_id=self._provider_id, operation=operation or "notion.request"),
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

                self._raise_for_status(resp, operation=operation or "notion.request")
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

    # ---- convenience methods ------------------------------------------------

    def get_user_me(self, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /users/me (requires token).
        """
        if not self._token:
            raise SaasAuthError(
                "notion token required for /users/me",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.get_user_me"),
                code="token_required",
            )

        data = self.request_json(
            "GET", "/users/me", timeout_s=timeout_s, idempotent=True, operation="notion.get_user_me"
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected /users/me response type",
                context=SaasErrorContext(
                    provider_id=self._provider_id,
                    operation="notion.get_user_me",
                    details={"type": type(data).__name__},
                ),
                code="unexpected_response",
            )
        return data

    def get_page(self, page_id: str, *, timeout_s: float | None = None) -> Mapping[str, Any]:
        """
        GET /pages/{page_id}
        """
        pid = notion_page_id_normalize(page_id)
        data = self.request_json(
            "GET",
            f"/pages/{quote(pid, safe='')}",
            timeout_s=timeout_s,
            idempotent=True,
            operation="notion.get_page",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected page response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.get_page"),
                code="unexpected_response",
            )
        return data

    def query_database(
        self,
        database_id: str,
        *,
        filter: Mapping[str, Any] | None = None,
        sorts: Sequence[Mapping[str, Any]] | None = None,
        start_cursor: str | None = None,
        page_size: int | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /databases/{database_id}/query

        This is read-only (safe to retry) even though it is POST.
        """
        did = notion_page_id_normalize(database_id)
        payload: dict[str, Any] = {}
        if filter is not None:
            payload["filter"] = dict(filter)
        if sorts is not None:
            payload["sorts"] = [dict(s) for s in sorts]
        if start_cursor is not None:
            payload["start_cursor"] = str(start_cursor)
        if page_size is not None:
            payload["page_size"] = int(page_size)

        data = self.request_json(
            "POST",
            f"/databases/{quote(did, safe='')}/query",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=True,
            operation="notion.query_database",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected query_database response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.query_database"),
                code="unexpected_response",
            )
        return data

    def iter_query_database(
        self,
        database_id: str,
        *,
        filter: Mapping[str, Any] | None = None,
        sorts: Sequence[Mapping[str, Any]] | None = None,
        page_size: int = 100,
        max_pages: int = 200,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate results from POST /databases/{id}/query using has_more/next_cursor.

        Yields each result object from "results".
        """
        cursor: str | None = None
        pages = 0

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            data = self.query_database(
                database_id,
                filter=filter,
                sorts=sorts,
                start_cursor=cursor,
                page_size=int(page_size),
                timeout_s=timeout_s,
            )

            results = data.get("results") if isinstance(data, Mapping) else None
            if isinstance(results, Sequence) and not isinstance(results, (str, bytes, bytearray)):
                for item in results:
                    if isinstance(item, Mapping):
                        yield item

            has_more = bool(data.get("has_more")) if isinstance(data, Mapping) else False
            cursor = str(data.get("next_cursor")) if isinstance(data, Mapping) and data.get("next_cursor") else None
            if not has_more or not cursor:
                break

    def search(
        self,
        *,
        query: str | None = None,
        filter: Mapping[str, Any] | None = None,
        sort: Mapping[str, Any] | None = None,
        start_cursor: str | None = None,
        page_size: int | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /search

        Read-only (safe to retry) even though it is POST.
        """
        payload: dict[str, Any] = {}
        if query is not None:
            payload["query"] = str(query)
        if filter is not None:
            payload["filter"] = dict(filter)
        if sort is not None:
            payload["sort"] = dict(sort)
        if start_cursor is not None:
            payload["start_cursor"] = str(start_cursor)
        if page_size is not None:
            payload["page_size"] = int(page_size)

        data = self.request_json(
            "POST",
            "/search",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=True,
            operation="notion.search",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected search response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.search"),
                code="unexpected_response",
            )
        return data

    def iter_search(
        self,
        *,
        query: str | None = None,
        filter: Mapping[str, Any] | None = None,
        sort: Mapping[str, Any] | None = None,
        page_size: int = 100,
        max_pages: int = 200,
        timeout_s: float | None = None,
    ) -> Iterable[Mapping[str, Any]]:
        """
        Iterate results from POST /search using has_more/next_cursor.
        """
        cursor: str | None = None
        pages = 0

        while True:
            pages += 1
            if pages > int(max_pages):
                break

            data = self.search(
                query=query,
                filter=filter,
                sort=sort,
                start_cursor=cursor,
                page_size=int(page_size),
                timeout_s=timeout_s,
            )

            results = data.get("results") if isinstance(data, Mapping) else None
            if isinstance(results, Sequence) and not isinstance(results, (str, bytes, bytearray)):
                for item in results:
                    if isinstance(item, Mapping):
                        yield item

            has_more = bool(data.get("has_more")) if isinstance(data, Mapping) else False
            cursor = str(data.get("next_cursor")) if isinstance(data, Mapping) and data.get("next_cursor") else None
            if not has_more or not cursor:
                break

    def create_page(
        self,
        *,
        parent: Mapping[str, Any],
        properties: Mapping[str, Any],
        children: Sequence[Mapping[str, Any]] | None = None,
        icon: Mapping[str, Any] | None = None,
        cover: Mapping[str, Any] | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        POST /pages

        Non-idempotent (no automatic retries).
        """
        if not self._token:
            raise SaasAuthError(
                "notion token required to create pages",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.create_page"),
                code="token_required",
            )

        if not isinstance(parent, Mapping) or not parent:
            raise SaasValidationError(
                "parent is required and must be a mapping",
                details={"parent_shape": _shape_value(parent)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.create_page"),
            )
        if not isinstance(properties, Mapping) or not properties:
            raise SaasValidationError(
                "properties is required and must be a mapping",
                details={"properties_shape": _shape_value(properties)},
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.create_page"),
            )

        payload: dict[str, Any] = {
            "parent": dict(parent),
            "properties": dict(properties),
        }
        if children is not None:
            payload["children"] = [dict(c) for c in children]
        if icon is not None:
            payload["icon"] = dict(icon)
        if cover is not None:
            payload["cover"] = dict(cover)

        data = self.request_json(
            "POST",
            "/pages",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="notion.create_page",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected create_page response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.create_page"),
                code="unexpected_response",
            )
        return data

    def append_block_children(
        self,
        block_id: str,
        *,
        children: Sequence[Mapping[str, Any]],
        after: str | None = None,
        timeout_s: float | None = None,
    ) -> Mapping[str, Any]:
        """
        PATCH /blocks/{block_id}/children

        Non-idempotent (no automatic retries).
        """
        if not self._token:
            raise SaasAuthError(
                "notion token required to append block children",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.append_block_children"),
                code="token_required",
            )

        bid = notion_page_id_normalize(block_id)
        if not children:
            raise SaasValidationError(
                "children is required and cannot be empty",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.append_block_children"),
            )

        payload: dict[str, Any] = {"children": [dict(c) for c in children]}
        if after is not None:
            payload["after"] = str(after)

        data = self.request_json(
            "PATCH",
            f"/blocks/{quote(bid, safe='')}/children",
            json_body=payload,
            timeout_s=timeout_s,
            idempotent=False,
            operation="notion.append_block_children",
        )
        if not isinstance(data, Mapping):
            raise SaasError(
                "unexpected append_block_children response type",
                context=SaasErrorContext(provider_id=self._provider_id, operation="notion.append_block_children"),
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
    ) -> NotionHttpResponse:
        """
        Perform a single HTTP request with stdlib http.client.
        Converts transport errors to SaasNetworkError.
        """
        op = operation or "notion.request"
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

            # Notion/infra request id
            request_id = hdr_map.get("x-request-id") or hdr_map.get("X-Request-Id") or hdr_map.get("X-Request-ID")

            rate = _parse_rate_limit_headers({k.lower(): v for k, v in hdr_map.items()})

            return NotionHttpResponse(
                method=method,
                url=url,
                status=status,
                reason=reason,
                headers=hdr_map,
                body=raw,
                request_id=request_id,
                rate_limit=rate,
            )

        except ssl.SSLError as exc:
            raise SaasNetworkError(
                "TLS error contacting Notion endpoint",
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
                "network error contacting Notion endpoint",
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

    def _raise_for_status(self, resp: NotionHttpResponse, *, operation: str) -> None:
        """
        Map HTTP status to SaaS-layer errors.

        IMPORTANT: do not attach raw body. Only attach safe summaries.
        """
        status = int(resp.status)
        msg, notion_code = _extract_message_from_body(resp)

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
            endpoint=self._base.canonical,
            details={
                "method": resp.method,
                "url": redact_url(resp.url),
                "notion_code": notion_code,
                "rate_limit": dict(resp.rate_limit) if resp.rate_limit else {},
                "body_len": len(resp.body or b""),
                "body_hash": _hash_stable((resp.body or b"")[:256].hex()),
            },
        )

        if status == 401:
            raise SaasAuthError(msg or "unauthorized", context=ctx, code=notion_code or "http_401")

        if status == 403:
            raise SaasPermissionError(msg or "forbidden", context=ctx, code=notion_code or "http_403")

        if status == 404:
            raise SaasNotFoundError(msg or "not found", context=ctx, code=notion_code or "http_404")

        if status == 409:
            raise SaasConflictError(msg or "conflict", context=ctx, code=notion_code or "http_409")

        if status in (400, 422):
            raise SaasValidationError(msg or "validation failed", context=ctx, code=notion_code or f"http_{status}")

        if status == 429:
            ra_s: float | None = float(retry_after) if isinstance(retry_after, (int, float)) else None
            raise SaasRateLimitError(
                msg or "too many requests",
                context=ctx,
                code=notion_code or "http_429",
                retry_after_s=ra_s,
            )

        if 500 <= status <= 599:
            raise SaasUnavailableError(msg or "service unavailable", context=ctx, code=notion_code or f"http_{status}")

        raise SaasError(msg or f"http error {status}", context=ctx, code=notion_code or f"http_{status}")
