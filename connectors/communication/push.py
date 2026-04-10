"""
===============================================================================
Francis 2.0 — Communication Connectors (Push Utilities)
Path: connectors/communication/push.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *provider-agnostic* push-notification primitives and helpers
used by push-capable communication connectors (e.g., Firebase Cloud Messaging,
Apple Push Notification Service via a gateway, Web Push, etc.).

It is intentionally provider-neutral:
  - No FCM/APNs/WebPush SDK imports.
  - Standard library only (json, time) for payload composition.

It provides:
  - PUSH channel constant + target helpers (CommAddress with channel="push")
  - Safety: input validation + header/data sanitization (prevents CR/LF injection)
  - A small push compose model (PushSendOptions)
  - A payload builder: build_push_payload(outbound, options) -> dict
      * returns a payload that excludes recipient tokens by default (safer logging)
  - Log-safe summaries (lengths, counts, hashed targets)

SAFETY & OBSERVABILITY
----------------------
- Never log device tokens / endpoints. Use redact_address() (deterministic hash).
- Never log payload bodies by default; summaries only expose lengths.
- Sanitizes fields to prevent newline injection in headers/keys.

NOTE
----
Provider connectors still decide:
  - How to address recipients (token vs topic vs device endpoint)
  - How to map "options" into provider-specific fields
  - How to send (HTTP v1, legacy APIs, APNs binary, Web Push VAPID, etc.)

===============================================================================
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from . import (
    CommAddress,
    CommOutboundMessage,
    CommValidationError,
    redact_address,
    redact_mapping,
    redact_value,
)

__all__ = [
    "PUSH_CHANNEL",
    "PushSendOptions",
    "PushComposeLimits",
    # Target helpers
    "push_target",
    "is_push_target",
    "redacted_push_target",
    # Data sanitization
    "sanitize_push_key",
    "sanitize_push_value",
    "normalize_push_data",
    # Payload composition
    "build_push_payload",
    "push_outbound_summary",
    "push_payload_summary",
]

PUSH_CHANNEL = "push"

# Conservative key pattern for "data" payloads (works across most push systems)
# - keep it simple: alnum, dot, dash, underscore
# - 1..64 chars
_PUSH_KEY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._\-]{0,63}$")

# Conservative "priority" values (connector can map/override)
_ALLOWED_PRIORITIES = {"normal", "high"}


# =============================================================================
# Compose options / limits
# =============================================================================


@dataclass(frozen=True, slots=True)
class PushSendOptions:
    """
    Provider-agnostic push send options.

    These map cleanly to common providers:
      - ttl_s -> time-to-live / expiration
      - priority -> delivery priority
      - collapse_key -> collapse / coalesce key
      - topic -> topic routing (if supported by provider)
      - sound/badge -> mobile presentation hints (if supported)
      - click_action -> deep link / action hint
      - image_url -> rich notification hint (provider-dependent)

    IMPORTANT:
    - Do NOT put secrets (server keys, bearer tokens) here.
    - headers are optional and MUST be sanitized; still avoid auth headers.
    """

    ttl_s: int | None = None
    priority: str | None = None  # "normal" | "high" (best-effort)
    collapse_key: str | None = None
    topic: str | None = None

    sound: str | None = None
    badge: int | None = None

    click_action: str | None = None
    image_url: str | None = None

    # Additional headers/options; connector decides whether/how to use.
    headers: Mapping[str, str] = field(default_factory=dict)

    # Provider may support "dry run" test sends (e.g., FCM validate_only)
    dry_run: bool = False

    # Optional client-side id for correlation/idempotency
    message_id: str | None = None

    # Optional custom data payload (merged with outbound.meta["data"] if present)
    data: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class PushComposeLimits:
    """
    Lightweight guardrails for composition.

    These are not provider limits (FCM/APNs/WebPush differ).
    They prevent accidental huge payloads or unsafe fields.
    """

    max_title_len: int = 200
    max_body_len: int = 2000

    max_data_keys: int = 50
    max_key_len: int = 64
    max_value_len: int = 2048

    # Conservative total JSON size guardrail (bytes).
    # Historically many push payloads were ~4KB (APNs legacy) and some are larger now.
    # We choose a conservative default; provider can override at connector level.
    max_json_bytes: int = 4096

    # Avoid huge fan-out in one call at the utility layer.
    # Connectors can still implement batch sending; this just guards composition misuse.
    max_targets: int = 500


# =============================================================================
# Target helpers
# =============================================================================


def push_target(
    token_or_endpoint: str,
    *,
    display_name: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> CommAddress:
    """
    Convenience: create a CommAddress for push channel.

    token_or_endpoint may be:
      - device token
      - installation id
      - web push endpoint url
      - provider-specific registration id

    Raises CommValidationError if empty or contains CR/LF (injection guard).
    """
    t = (token_or_endpoint or "").strip()
    if not t:
        raise CommValidationError("push target is required", details={"field": "token_or_endpoint"})
    if "\r" in t or "\n" in t:
        raise CommValidationError("push target contains illegal newline characters")
    return CommAddress(channel=PUSH_CHANNEL, address=t, display_name=display_name, meta=meta or {})


def is_push_target(token_or_endpoint: str) -> bool:
    """
    Return True if a string looks like a plausible push target.

    This is intentionally permissive; providers vary greatly.
    """
    t = (token_or_endpoint or "").strip()
    if not t:
        return False
    if "\r" in t or "\n" in t:
        return False
    # Heuristic: ensure it's not absurdly short.
    return len(t) >= 8


def redacted_push_target(target: str | CommAddress | None) -> str:
    """
    Log-safe representation of a push target.
    Uses deterministic hashing via redact_address().

    IMPORTANT: Never log raw device tokens/endpoints.
    """
    if target is None:
        return ""
    if isinstance(target, CommAddress):
        if target.channel != PUSH_CHANNEL:
            return ""
        return target.redacted_dict().get("address") or ""
    return redact_address(str(target))


# =============================================================================
# Data sanitization
# =============================================================================


def sanitize_push_key(key: str, *, limits: PushComposeLimits | None = None) -> str:
    """
    Validate/sanitize a push data key.

    - Disallows CR/LF.
    - Enforces conservative pattern + length.
    """
    lim = limits or PushComposeLimits()
    k = (key or "").strip()
    if not k:
        raise CommValidationError("push data key is required")
    if "\r" in k or "\n" in k:
        raise CommValidationError("push data key contains illegal newline characters")
    if len(k) > lim.max_key_len:
        raise CommValidationError(
            "push data key too long",
            details={"key": redact_value(k), "max_key_len": lim.max_key_len},
        )
    if not _PUSH_KEY_RE.match(k):
        raise CommValidationError(
            "push data key has invalid format",
            details={"key": redact_value(k), "expected": _PUSH_KEY_RE.pattern},
        )
    return k


def sanitize_push_value(value: Any, *, limits: PushComposeLimits | None = None) -> str:
    """
    Sanitize a push data value.

    - Converts to string. For dict/list, JSON-encodes.
    - Disallows CR/LF to avoid header-ish injection and log weirdness.
    - Caps length.
    """
    lim = limits or PushComposeLimits()

    if value is None:
        s = ""
    elif isinstance(value, (dict, list)):
        # Compact encoding; ensures stable, readable payloads.
        s = json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    else:
        s = str(value)

    if "\r" in s or "\n" in s:
        raise CommValidationError("push data value contains illegal newline characters")

    if len(s) > lim.max_value_len:
        s = s[: lim.max_value_len] + "…"
    return s


def normalize_push_data(
    data: Mapping[str, Any] | None,
    *,
    limits: PushComposeLimits | None = None,
) -> dict[str, str]:
    """
    Normalize a data payload into dict[str, str] with conservative validation.

    Many providers require data values to be strings.
    """
    lim = limits or PushComposeLimits()
    if not data:
        return {}

    if len(data) > lim.max_data_keys:
        raise CommValidationError(
            "too many push data keys",
            details={"count": len(data), "max": lim.max_data_keys},
        )

    out: dict[str, str] = {}
    for k, v in data.items():
        kk = sanitize_push_key(str(k), limits=lim)
        out[kk] = sanitize_push_value(v, limits=lim)
    return out


# =============================================================================
# Payload composition
# =============================================================================


def push_outbound_summary(outbound: CommOutboundMessage) -> dict[str, Any]:
    """
    Log-safe summary of an outbound push message.

    - No bodies
    - No raw targets
    """
    if outbound.channel != PUSH_CHANNEL:
        raise CommValidationError("push_outbound_summary expects channel='push'")

    return {
        "channel": outbound.channel,
        "to": [a.redacted_dict() for a in (outbound.to or ())],
        "to_count": len(outbound.to or ()),
        "from": outbound.from_addr.redacted_dict() if outbound.from_addr else None,
        "title_len": len(outbound.subject) if outbound.subject else 0,
        "body_len": len(outbound.text) if outbound.text else 0,
        "html_len": len(outbound.html) if outbound.html else 0,
        "attachment_count": len(outbound.attachments or ()),
        "client_message_id": outbound.client_message_id,
        "meta": redact_mapping(outbound.meta),
    }


def push_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Log-safe summary of a push payload dict.

    It exposes only lengths/counts and safe option values.
    """
    notif = payload.get("notification") if isinstance(payload, dict) else None
    data = payload.get("data") if isinstance(payload, dict) else None
    opts = payload.get("options") if isinstance(payload, dict) else None

    title = ""
    body = ""
    if isinstance(notif, dict):
        title = str(notif.get("title") or "")
        body = str(notif.get("body") or "")

    data_keys = []
    if isinstance(data, dict):
        data_keys = list(data.keys())

    safe_opts: dict[str, Any] = {}
    if isinstance(opts, dict):
        # Keep only a small safe subset
        for k in (
            "ttl_s",
            "priority",
            "collapse_key",
            "topic",
            "sound",
            "badge",
            "click_action",
            "image_url",
            "dry_run",
        ):
            if k in opts:
                safe_opts[k] = opts.get(k)

    return {
        "title_len": len(title),
        "body_len": len(body),
        "data_key_count": len(data_keys),
        "options": redact_mapping(safe_opts),
    }


def build_push_payload(
    outbound: CommOutboundMessage,
    *,
    options: PushSendOptions | None = None,
    limits: PushComposeLimits | None = None,
    include_targets: bool = False,
) -> dict[str, Any]:
    """
    Build a provider-agnostic push payload dict from a CommOutboundMessage.

    IMPORTANT:
    - By default, this payload does NOT include recipient tokens/endpoints.
      This is deliberate for safety/observability. Connectors should apply
      recipient addressing separately.

    Field mapping (convention):
      - outbound.subject -> notification.title
      - outbound.text    -> notification.body
      - outbound.meta.get("data") + options.data -> data (validated)  (strings)
      - options -> options (ttl_s, priority, collapse_key, ...)

    Args:
      include_targets:
        - If True, includes a "targets" list of raw target strings.
        - This is NOT recommended unless you have strict log discipline.

    Raises:
      CommValidationError on invalid/suspicious inputs or size over limits.
    """
    if outbound.channel != PUSH_CHANNEL:
        raise CommValidationError(
            "build_push_payload expects outbound.channel='push'",
            details={"channel": outbound.channel},
        )

    opt = options or PushSendOptions()
    lim = limits or PushComposeLimits()

    # Validate recipients (but don't embed them unless include_targets=True)
    to = list(outbound.to or ())
    if not to:
        raise CommValidationError("push outbound must have at least one recipient in 'to'")

    if len(to) > lim.max_targets:
        raise CommValidationError(
            "too many push targets for one compose call",
            details={"count": len(to), "max": lim.max_targets},
        )

    for a in to:
        if a.channel != PUSH_CHANNEL:
            raise CommValidationError(
                "push outbound recipients must have channel='push'",
                details={"channel": a.channel},
            )
        if "\r" in a.address or "\n" in a.address:
            raise CommValidationError("push target contains illegal newline characters")

    # Title/body
    title = outbound.subject or ""
    body = outbound.text or ""

    if "\r" in title or "\n" in title:
        raise CommValidationError("push title contains illegal newline characters")
    if "\r" in body or "\n" in body:
        raise CommValidationError("push body contains illegal newline characters")

    if len(title) > lim.max_title_len:
        title = title[: lim.max_title_len] + "…"
    if len(body) > lim.max_body_len:
        body = body[: lim.max_body_len] + "…"

    # Attachments are not supported at this layer
    if outbound.attachments:
        raise CommValidationError(
            "push payload composition does not support attachments",
            details={"attachment_count": len(outbound.attachments)},
        )

    # Merge data sources
    outbound_data_raw = {}
    if isinstance(outbound.meta, dict):
        maybe = outbound.meta.get("data")
        if isinstance(maybe, dict):
            outbound_data_raw = maybe

    merged_data: dict[str, Any] = {}
    merged_data.update(outbound_data_raw)
    merged_data.update(opt.data or {})

    data_norm = normalize_push_data(merged_data, limits=lim)

    # Options validation
    priority = (opt.priority or "").strip().lower() if opt.priority else None
    if priority and priority not in _ALLOWED_PRIORITIES:
        raise CommValidationError(
            "invalid push priority",
            details={"priority": redact_value(priority), "allowed": sorted(_ALLOWED_PRIORITIES)},
        )

    ttl_s = opt.ttl_s
    if ttl_s is not None:
        try:
            ttl_s = int(ttl_s)
        except Exception as exc:  # noqa: BLE001
            raise CommValidationError("ttl_s must be an integer") from exc
        if ttl_s < 0:
            raise CommValidationError("ttl_s cannot be negative", details={"ttl_s": ttl_s})

    # Headers: sanitize to prevent newline injection (connectors may ignore)
    headers_clean: dict[str, str] = {}
    if opt.headers:
        for k, v in opt.headers.items():
            kk = (str(k) or "").strip()
            vv = "" if v is None else str(v)
            if not kk:
                continue
            if "\r" in kk or "\n" in kk or "\r" in vv or "\n" in vv:
                raise CommValidationError("push headers contain illegal newline characters")
            # Length guardrails (re-use push value limits)
            if len(kk) > lim.max_key_len:
                raise CommValidationError("push header name too long", details={"header": redact_value(kk)})
            if len(vv) > lim.max_value_len:
                vv = vv[: lim.max_value_len] + "…"
            headers_clean[kk] = vv

    payload: dict[str, Any] = {
        "notification": {
            # Some providers allow data-only; omit empty notification object later.
            "title": title,
            "body": body,
        },
        "data": data_norm,
        "options": {
            "ttl_s": ttl_s,
            "priority": priority,
            "collapse_key": opt.collapse_key,
            "topic": opt.topic,
            "sound": opt.sound,
            "badge": opt.badge,
            "click_action": opt.click_action,
            "image_url": opt.image_url,
            "headers": headers_clean,  # connector decides usage
            "dry_run": bool(opt.dry_run),
        },
        "client_message_id": outbound.client_message_id or opt.message_id,
        "ts": int(time.time()),
    }

    # Remove empty notification if both title/body empty (data-only message)
    notif = payload.get("notification")
    if isinstance(notif, dict):
        if not (notif.get("title") or notif.get("body")):
            payload.pop("notification", None)

    # If still nothing meaningful, reject
    if "notification" not in payload and not data_norm:
        raise CommValidationError("push message must include a title/body or a non-empty data payload")

    if include_targets:
        # WARNING: includes raw targets; do not log this payload.
        payload["targets"] = [a.address for a in to]

    # Total payload size guardrail
    try:
        encoded = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise CommValidationError("failed to JSON-encode push payload") from exc

    if len(encoded) > lim.max_json_bytes:
        raise CommValidationError(
            "push payload exceeds size limit",
            details={"json_bytes": len(encoded), "max_json_bytes": lim.max_json_bytes},
        )

    return payload
