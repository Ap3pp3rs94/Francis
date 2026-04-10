"""
===============================================================================
Francis 2.0 — Communication Connectors (SMS Utilities)
Path: connectors/communication/sms.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *provider-agnostic* SMS primitives and helpers used by
SMS-capable communication connectors (e.g., Twilio, AWS SNS SMS, Vonage, Telnyx,
MessageBird, etc.).

It is intentionally provider-neutral:
  - No Twilio/Vonage/etc SDK imports.
  - Standard library only.

It provides:
  - SMS channel constants + phone/target helpers (normalize/validate)
  - Safety: input validation (CR/LF injection guards where relevant)
  - SMS encoding + segmentation helpers (GSM-7 vs UCS-2; concatenated segment sizing)
  - A small SMS compose model (SmsSendOptions)
  - A payload builder: build_sms_payload(outbound, options) -> dict
      * returns a payload that excludes raw phone numbers by default (safer logging)
  - Log-safe summaries (lengths, counts, hashed targets)

SAFETY & OBSERVABILITY
----------------------
- Never log phone numbers. Use redact_address() (deterministic hash).
- Never log message bodies by default; summaries only expose lengths/segment counts.
- Rejects unsupported fields for SMS (attachments, html, cc/bcc).

IMPORTANT NOTES
---------------
- This file does NOT attempt full international phone parsing.
  It prefers E.164 normalization (+15551234567).
- If you need locale-specific parsing, do that in a provider connector or a higher layer
  with an explicit dependency (e.g., phonenumbers library) behind governance control.

===============================================================================
"""

from __future__ import annotations

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
    "SMS_CHANNEL",
    "SmsSendOptions",
    "SmsComposeLimits",
    "SmsSegmentInfo",
    # Target helpers
    "sms_target",
    "is_sms_target",
    "normalize_e164",
    "is_e164",
    "redacted_sms_target",
    # Encoding + segmentation
    "sms_encoding",
    "gsm7_septet_len",
    "ucs2_units_len",
    "sms_segment_info",
    "split_sms_segments",
    # Payload composition + summaries
    "build_sms_payload",
    "sms_outbound_summary",
    "sms_payload_summary",
]


SMS_CHANNEL = "sms"

# E.164: "+" + country code + national number; max 15 digits total.
_E164_RE = re.compile(r"^\+[1-9]\d{7,14}$")

# Short code (provider-dependent; common 3-6 digits)
_SHORTCODE_RE = re.compile(r"^\d{3,8}$")

# Alphanumeric sender IDs (provider/country dependent; often 3-11 chars)
# We keep this conservative and ASCII-only.
_SENDER_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _\-]{1,13}[A-Za-z0-9]$")


# =============================================================================
# Compose options / limits
# =============================================================================


@dataclass(frozen=True, slots=True)
class SmsSendOptions:
    """
    Provider-agnostic SMS send options.

    These map cleanly to common SMS providers:
      - sender_id: alphanumeric sender ID (where supported)
      - from_number: explicit from phone number (E.164)
      - validity_period_s: TTL for undelivered messages (provider support varies)
      - delivery_report: request a delivery receipt (provider support varies)
      - force_unicode: force UCS-2 encoding (some providers auto-detect)
      - metadata: correlation/idempotency hints (connector-defined)

    IMPORTANT:
    - Do NOT put credentials or auth headers here.
    - sender_id and from_number are identifiers (not secrets) but can be PII
      depending on org policy; avoid logging raw values.
    """

    sender_id: str | None = None
    from_number: str | None = None

    validity_period_s: int | None = None
    delivery_report: bool | None = None

    force_unicode: bool = False

    # Optional provider-neutral correlation hint (safe string)
    message_id: str | None = None

    # Connector-defined metadata (safe for logs after redaction)
    meta: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class SmsComposeLimits:
    """
    Lightweight guardrails for SMS composition.

    These are not hard provider limits (providers/countries vary).
    They prevent accidental abuse (e.g., sending huge multi-part messages).
    """

    max_body_chars: int = 4000
    max_segments: int = 10

    # Some providers treat newlines as valid; we allow them in the body.
    # Control characters are generally risky; we can reject NUL.
    disallow_nul: bool = True

    # Allow short codes for 'to' addresses (opt-in for safety).
    allow_short_codes: bool = True

    # Allow alphanumeric sender IDs (opt-in; country/provider dependent).
    allow_sender_id: bool = True


@dataclass(frozen=True, slots=True)
class SmsSegmentInfo:
    """
    Computed encoding + segmentation info for an SMS body.

    encoding:
      - "gsm7" or "ucs2"
    units:
      - for gsm7: septets (including escape sequences for extended chars)
      - for ucs2: UTF-16 code units (BMP=1, astral/emoji=2)
    """

    encoding: str
    segments: int
    per_segment_units: int
    total_units: int
    concatenated: bool


# =============================================================================
# Target helpers
# =============================================================================


def normalize_e164(raw: str, *, default_country_code: str | None = None) -> str:
    """
    Normalize a phone number into E.164 format if possible.

    Supported inputs:
      - "+15551234567" (already E.164)
      - "0015551234567" (converted to +15551234567)
      - "(555) 123-4567" with default_country_code="1" -> +15551234567

    Notes:
      - This is intentionally minimal. It does NOT implement full national rules.
      - If default_country_code is omitted and input is not already E.164-ish,
        we raise a validation error to avoid silently producing wrong numbers.
    """
    if raw is None:
        raise CommValidationError("phone number is required", details={"field": "raw"})

    s = str(raw).strip()
    if not s:
        raise CommValidationError("phone number is required", details={"field": "raw"})

    # Injection guard (phone numbers should not contain newlines)
    if "\r" in s or "\n" in s:
        raise CommValidationError("phone number contains illegal newline characters")

    # Convert 00 prefix to +
    if s.startswith("00"):
        s = "+" + s[2:]

    # Already E.164
    if _E164_RE.match(s):
        return s

    # Remove common separators
    digits = re.sub(r"[^\d]", "", s)

    if not digits:
        raise CommValidationError("phone number has no digits", details={"raw": redact_value(s)})

    # If the original had a leading "+", keep it; otherwise use default_country_code.
    if s.startswith("+"):
        cand = "+" + digits
    else:
        if not default_country_code:
            raise CommValidationError(
                "phone number must be E.164 unless default_country_code is provided",
                details={"raw": redact_value(s)},
            )
        cc = re.sub(r"[^\d]", "", str(default_country_code))
        if not cc or cc.startswith("0"):
            raise CommValidationError(
                "default_country_code must be digits without leading zero",
                details={"default_country_code": redact_value(str(default_country_code))},
            )
        cand = "+" + cc + digits

    if not _E164_RE.match(cand):
        raise CommValidationError(
            "phone number could not be normalized to E.164",
            details={"raw": redact_value(s), "candidate": redact_value(cand)},
        )
    return cand


def is_e164(number: str) -> bool:
    """Return True if number matches a conservative E.164 pattern."""
    if not number:
        return False
    n = str(number).strip()
    if "\r" in n or "\n" in n:
        return False
    return bool(_E164_RE.match(n))


def sms_target(
    number_or_shortcode: str,
    *,
    default_country_code: str | None = None,
    allow_short_code: bool = True,
    display_name: str | None = None,
    meta: Mapping[str, Any] | None = None,
) -> CommAddress:
    """
    Convenience: create a CommAddress for SMS channel.

    Accepts:
      - E.164 number: +15551234567
      - short code: 12345 (if allow_short_code=True)
      - local/national number with default_country_code -> normalized to E.164

    IMPORTANT: Avoid logging raw numbers; use redacted_sms_target().
    """
    raw = (number_or_shortcode or "").strip()
    if not raw:
        raise CommValidationError("sms target is required", details={"field": "number_or_shortcode"})
    if "\r" in raw or "\n" in raw:
        raise CommValidationError("sms target contains illegal newline characters")

    # Short code?
    if allow_short_code and _SHORTCODE_RE.match(raw):
        return CommAddress(channel=SMS_CHANNEL, address=raw, display_name=display_name, meta=meta or {})

    # Otherwise normalize to E.164
    norm = normalize_e164(raw, default_country_code=default_country_code)
    return CommAddress(channel=SMS_CHANNEL, address=norm, display_name=display_name, meta=meta or {})


def is_sms_target(value: str, *, allow_short_code: bool = True) -> bool:
    """
    Return True if a string looks like an SMS target:
      - E.164, or
      - short code (if allowed)
    """
    if not value:
        return False
    s = str(value).strip()
    if "\r" in s or "\n" in s:
        return False
    if is_e164(s):
        return True
    if allow_short_code and _SHORTCODE_RE.match(s):
        return True
    return False


def redacted_sms_target(target: str | CommAddress | None) -> str:
    """
    Log-safe representation of an SMS target.

    IMPORTANT: Never log raw phone numbers/short codes.
    """
    if target is None:
        return ""
    if isinstance(target, CommAddress):
        if target.channel != SMS_CHANNEL:
            return ""
        return target.redacted_dict().get("address") or ""
    return redact_address(str(target))


def _validate_sender_id(sender_id: str, *, limits: SmsComposeLimits) -> str:
    s = (sender_id or "").strip()
    if not s:
        raise CommValidationError("sender_id is empty")
    if "\r" in s or "\n" in s:
        raise CommValidationError("sender_id contains illegal newline characters")
    if not limits.allow_sender_id:
        raise CommValidationError("sender_id not allowed by compose limits")
    if not _SENDER_ID_RE.match(s):
        raise CommValidationError(
            "sender_id has invalid format",
            details={"sender_id": redact_value(s), "expected": _SENDER_ID_RE.pattern},
        )
    return s


# =============================================================================
# Encoding + segmentation (GSM-7 vs UCS-2)
# =============================================================================
# GSM 03.38 basic + extension detection (approximate, but practical).
# - Basic charset (common subset)
# - Extended chars require escape, count as 2 septets.
_GSM7_BASIC = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ"
    "ÆæßÉ !\"#¤%&'()*+,-./"
    "0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

_GSM7_EXT = set("^{}\\[~]|€")  # counts as 2 septets per character


def gsm7_septet_len(text: str) -> int | None:
    """
    Return septet length of text if representable in GSM-7, else None.

    Extended table chars count as 2 septets.
    """
    if text is None:
        return 0
    total = 0
    for ch in str(text):
        if ch in _GSM7_BASIC:
            total += 1
        elif ch in _GSM7_EXT:
            total += 2
        else:
            return None
    return total


def ucs2_units_len(text: str) -> int:
    """
    Return the number of UCS-2/UTF-16 code units needed for the text.

    - BMP chars -> 1 unit
    - Astral chars (e.g., emoji) -> 2 units (surrogate pair)
    """
    if text is None:
        return 0
    total = 0
    for ch in str(text):
        total += 2 if ord(ch) > 0xFFFF else 1
    return total


def sms_encoding(text: str, *, force_unicode: bool = False) -> str:
    """
    Determine encoding: "gsm7" or "ucs2".

    - If force_unicode=True, always returns "ucs2".
    - Otherwise uses GSM-7 if representable; else UCS-2.
    """
    if force_unicode:
        return "ucs2"
    return "gsm7" if gsm7_septet_len(text) is not None else "ucs2"


def sms_segment_info(text: str, *, force_unicode: bool = False) -> SmsSegmentInfo:
    """
    Compute segmentation info for a message body.
    """
    enc = sms_encoding(text, force_unicode=force_unicode)
    if enc == "gsm7":
        units = gsm7_septet_len(text) or 0
        single = 160
        concat = 153
    else:
        units = ucs2_units_len(text)
        single = 70
        concat = 67

    if units <= single:
        return SmsSegmentInfo(
            encoding=enc,
            segments=1,
            per_segment_units=single,
            total_units=units,
            concatenated=False,
        )

    # Concatenated SMS uses a UDH header reducing payload per segment.
    segs = (units + concat - 1) // concat
    return SmsSegmentInfo(
        encoding=enc,
        segments=int(segs),
        per_segment_units=concat,
        total_units=units,
        concatenated=True,
    )


def split_sms_segments(
    text: str,
    *,
    force_unicode: bool = False,
    limits: SmsComposeLimits | None = None,
) -> list[str]:
    """
    Split text into SMS segments according to encoding rules.

    - GSM-7: 160 septets single, 153 per segment concatenated
    - UCS-2: 70 units single, 67 per segment concatenated

    This returns the actual segment strings (safe to send, but DO NOT log).
    """
    lim = limits or SmsComposeLimits()

    body = "" if text is None else str(text)

    if lim.disallow_nul and "\x00" in body:
        raise CommValidationError("sms body contains NUL characters")

    if len(body) > lim.max_body_chars:
        # We cap chars (not units) as a general guardrail.
        body = body[: lim.max_body_chars] + "…"

    info = sms_segment_info(body, force_unicode=force_unicode)

    if info.segments > lim.max_segments:
        raise CommValidationError(
            "sms message exceeds segment limit",
            details={
                "segments": info.segments,
                "max_segments": lim.max_segments,
                "encoding": info.encoding,
                "total_units": info.total_units,
            },
        )

    # If one segment, no need to split.
    if info.segments <= 1:
        return [body]

    per = info.per_segment_units

    segments: list[str] = []
    cur: list[str] = []

    if info.encoding == "gsm7":
        cur_units = 0
        for ch in body:
            # GSM-7 safe because encoding chosen based on representability
            add = 1 if ch in _GSM7_BASIC else 2  # extended chars count as 2 septets
            if cur_units + add > per and cur:
                segments.append("".join(cur))
                cur = [ch]
                cur_units = add
            else:
                cur.append(ch)
                cur_units += add
        if cur:
            segments.append("".join(cur))
    else:
        cur_units = 0
        for ch in body:
            add = 2 if ord(ch) > 0xFFFF else 1
            if cur_units + add > per and cur:
                segments.append("".join(cur))
                cur = [ch]
                cur_units = add
            else:
                cur.append(ch)
                cur_units += add
        if cur:
            segments.append("".join(cur))

    # Defensive: ensure we didn't exceed segment limits due to weird edge cases
    if len(segments) > lim.max_segments:
        raise CommValidationError(
            "sms segmentation exceeded segment limit",
            details={"segments": len(segments), "max_segments": lim.max_segments},
        )

    return segments


# =============================================================================
# Payload composition + summaries
# =============================================================================


def sms_outbound_summary(outbound: CommOutboundMessage, *, force_unicode: bool = False) -> dict[str, Any]:
    """
    Log-safe summary of an outbound SMS message.

    - No raw phone numbers
    - No body content
    - Includes segmentation info (counts/encoding)
    """
    if outbound.channel != SMS_CHANNEL:
        raise CommValidationError("sms_outbound_summary expects channel='sms'")

    if outbound.html:
        raise CommValidationError("sms outbound does not support html body")
    if outbound.attachments:
        raise CommValidationError("sms outbound does not support attachments")
    if outbound.cc or outbound.bcc:
        raise CommValidationError("sms outbound does not support cc/bcc")

    body = outbound.text or ""
    seg = sms_segment_info(body, force_unicode=force_unicode)

    return {
        "channel": outbound.channel,
        "to_count": len(outbound.to or ()),
        "to": [a.redacted_dict() for a in (outbound.to or ())],
        "from": outbound.from_addr.redacted_dict() if outbound.from_addr else None,
        "subject_len": len(outbound.subject) if outbound.subject else 0,  # not typically used for SMS
        "body_len_chars": len(body),
        "encoding": seg.encoding,
        "segments": seg.segments,
        "client_message_id": outbound.client_message_id,
        "meta": redact_mapping(outbound.meta),
    }


def sms_payload_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    """
    Log-safe summary of a payload dict from build_sms_payload().

    Exposes only counts/lengths and redacted targets.
    """
    if not isinstance(payload, dict):
        return {}

    opts = payload.get("options")
    to_list = payload.get("to_redacted") or []
    body_len = int(payload.get("body_len_chars") or 0)
    segments = payload.get("segments") or None
    encoding = payload.get("encoding") or None

    safe_opts: dict[str, Any] = {}
    if isinstance(opts, dict):
        for k in ("validity_period_s", "delivery_report", "force_unicode"):
            if k in opts:
                safe_opts[k] = opts.get(k)

    return {
        "to_count": len(to_list) if isinstance(to_list, list) else 0,
        "body_len_chars": body_len,
        "encoding": encoding,
        "segments": segments,
        "options": redact_mapping(safe_opts),
    }


def build_sms_payload(
    outbound: CommOutboundMessage,
    *,
    options: SmsSendOptions | None = None,
    limits: SmsComposeLimits | None = None,
    default_country_code: str | None = None,
    include_targets: bool = False,
) -> dict[str, Any]:
    """
    Build a provider-agnostic SMS payload dict from a CommOutboundMessage.

    IMPORTANT:
    - By default, this payload does NOT include raw phone numbers.
      This is deliberate for safety/observability. Connectors should apply
      recipient addressing separately (or set include_targets=True and ensure
      strict no-logging discipline).

    Conventions:
      - outbound.text -> SMS body
      - outbound.to -> recipients (CommAddress channel="sms")
      - outbound.from_addr (optional) or options.from_number/sender_id (optional)
      - options.force_unicode influences encoding/segmentation

    Unsupported for SMS:
      - outbound.html
      - outbound.attachments
      - outbound.cc/bcc

    Args:
      default_country_code:
        Used only when normalizing non-E.164 inputs in addresses (if any).
      include_targets:
        If True, includes raw targets in the payload as "to". NOT recommended unless you
        guarantee payload will never be logged.

    Returns:
      dict suitable for a provider connector to map into its API.

    Raises:
      CommValidationError for invalid inputs or unsafe payloads.
    """
    lim = limits or SmsComposeLimits()
    opt = options or SmsSendOptions()

    if outbound.channel != SMS_CHANNEL:
        raise CommValidationError(
            "build_sms_payload expects outbound.channel='sms'",
            details={"channel": outbound.channel},
        )

    if outbound.html:
        raise CommValidationError("sms outbound does not support html body")
    if outbound.attachments:
        raise CommValidationError("sms outbound does not support attachments")
    if outbound.cc or outbound.bcc:
        raise CommValidationError("sms outbound does not support cc/bcc")

    # Recipients
    to_raw = list(outbound.to or ())
    if not to_raw:
        raise CommValidationError("sms outbound must have at least one recipient in 'to'")

    # Normalize/validate recipients (E.164 or short code depending on limits)
    to_norm: list[str] = []
    to_red: list[str] = []

    for a in to_raw:
        if a.channel != SMS_CHANNEL:
            raise CommValidationError(
                "sms outbound recipients must have channel='sms'",
                details={"channel": a.channel},
            )
        addr = (a.address or "").strip()
        if "\r" in addr or "\n" in addr:
            raise CommValidationError("sms target contains illegal newline characters")

        if _SHORTCODE_RE.match(addr):
            if not lim.allow_short_codes:
                raise CommValidationError(
                    "short codes are not allowed by compose limits",
                    details={"target": redacted_sms_target(a)},
                )
            to_norm.append(addr)
        else:
            to_norm.append(normalize_e164(addr, default_country_code=default_country_code))

        to_red.append(redacted_sms_target(a))

    # From selection:
    # Priority:
    #   1) options.sender_id (if provided)
    #   2) options.from_number (if provided)
    #   3) outbound.from_addr (if provided)
    sender_id = None
    from_number = None

    if opt.sender_id:
        sender_id = _validate_sender_id(opt.sender_id, limits=lim)

    if opt.from_number:
        from_number = normalize_e164(opt.from_number, default_country_code=default_country_code)

    if outbound.from_addr:
        if outbound.from_addr.channel != SMS_CHANNEL:
            raise CommValidationError(
                "sms from_addr must have channel='sms'",
                details={"channel": outbound.from_addr.channel},
            )
        # If outbound.from_addr looks like a sender id, allow only if explicitly permitted
        fa = (outbound.from_addr.address or "").strip()
        if _SHORTCODE_RE.match(fa):
            # From short codes are provider-dependent; treat as "from_number" and let connector decide.
            if not lim.allow_short_codes:
                raise CommValidationError("from short code not allowed by compose limits")
            from_number = from_number or fa
        elif is_e164(fa) or fa.startswith("00") or any(ch.isdigit() for ch in fa):
            from_number = from_number or normalize_e164(fa, default_country_code=default_country_code)
        else:
            # Possibly alphanumeric sender ID
            if sender_id is None:
                sender_id = _validate_sender_id(fa, limits=lim)

    # Body
    body = outbound.text or ""
    if lim.disallow_nul and "\x00" in body:
        raise CommValidationError("sms body contains NUL characters")

    # Segment
    seg = sms_segment_info(body, force_unicode=bool(opt.force_unicode))
    parts = split_sms_segments(body, force_unicode=bool(opt.force_unicode), limits=lim)

    # Validity/delivery options
    validity_period_s = opt.validity_period_s
    if validity_period_s is not None:
        try:
            validity_period_s = int(validity_period_s)
        except Exception as exc:  # noqa: BLE001
            raise CommValidationError("validity_period_s must be an integer") from exc
        if validity_period_s < 0:
            raise CommValidationError(
                "validity_period_s cannot be negative",
                details={"validity_period_s": validity_period_s},
            )

    payload: dict[str, Any] = {
        # Targets are excluded by default; include_targets=True to embed raw values.
        "to_redacted": list(to_red),
        "to_count": len(to_norm),
        "from_redacted": redact_address(from_number)
        if from_number
        else (redact_value(sender_id) if sender_id else None),
        "body_len_chars": len(body),
        "encoding": seg.encoding,
        "segments": seg.segments,
        "parts_count": len(parts),
        "options": {
            "sender_id": redact_value(sender_id) if sender_id else None,
            "from_number": redact_address(from_number) if from_number else None,
            "validity_period_s": validity_period_s,
            "delivery_report": opt.delivery_report,
            "force_unicode": bool(opt.force_unicode),
            "meta": redact_mapping(opt.meta),
            "message_id": opt.message_id,
        },
        "client_message_id": outbound.client_message_id or opt.message_id,
        "ts": int(time.time()),
    }

    if include_targets:
        # WARNING: includes raw targets and body parts; do not log this payload.
        payload["to"] = list(to_norm)
        if sender_id:
            payload["sender_id"] = sender_id
        if from_number:
            payload["from_number"] = from_number
        payload["parts"] = list(parts)
        payload["body"] = body

    return payload
