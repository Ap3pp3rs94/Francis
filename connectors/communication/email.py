"""
===============================================================================
Francis 2.0 — Communication Connectors (Email Utilities)
Path: connectors/communication/email.py
===============================================================================

ROLE IN THE SYSTEM
------------------
This module provides *provider-agnostic* email primitives and helpers used by
email-capable communication connectors (e.g., Gmail, Outlook/Microsoft Graph,
SMTP-like adapters).

It is intentionally provider-neutral:
  - No Gmail/Graph/SMTP SDK imports.
  - Standard library only (email.* utils) for parsing and MIME composition.

It provides:
  - Email channel constants + address helpers (parse/format/validate)
  - Safe header sanitization (prevent CR/LF injection)
  - A small email compose model (EmailSendOptions)
  - MIME builder: build_email_mime_bytes(outbound, options) -> bytes
  - Log-safe summaries / redaction-friendly utilities

SAFETY & OBSERVABILITY
----------------------
- Never log message bodies or attachment bytes.
- Never log raw email addresses by default (use redact_address from contract).
- Sanitizes headers to prevent injection (CR/LF stripping/validation).

NOTE
----
The provider connectors still decide:
  - How to send the MIME bytes (Gmail API, Graph sendMail, SMTP relay, etc.)
  - Whether to supply envelope recipients separately (some APIs ignore Bcc header)
  - Threading behavior / conversation id mapping

===============================================================================
"""

from __future__ import annotations

import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.policy import SMTP
from email.utils import formataddr, getaddresses, make_msgid, parseaddr
from typing import Any

from . import (
    CommAddress,
    CommAttachmentUpload,
    CommOutboundMessage,
    CommValidationError,
    redact_address,
    redact_mapping,
    redact_value,
)

__all__ = [
    "EMAIL_CHANNEL",
    "EmailSendOptions",
    "EmailComposeLimits",
    # Address helpers
    "email_address",
    "is_email_address",
    "parse_email_address",
    "parse_email_addresses",
    "format_email_addresses",
    "redacted_email",
    # Header + safety helpers
    "sanitize_header_value",
    "sanitize_header_name",
    # MIME composition
    "build_email_mime_bytes",
    "email_outbound_summary",
]


EMAIL_CHANNEL = "email"

# Pragmatic email address validation (not a full RFC 5322 parser).
# - avoids spaces
# - requires one "@"
# - basic domain structure
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# =============================================================================
# Compose options / limits
# =============================================================================


@dataclass(frozen=True, slots=True)
class EmailSendOptions:
    """
    Provider-agnostic email send options.

    These options map cleanly to common providers:
      - In-Reply-To / References for threading
      - Reply-To
      - Additional headers (sanitized)
      - Optional override for Message-ID generation

    IMPORTANT:
    - Do not put auth headers here.
    - Values are sanitized to prevent header injection.
    """

    reply_to: Sequence[CommAddress] = field(default_factory=tuple)
    in_reply_to: str | None = None  # RFC822 Message-ID of parent
    references: Sequence[str] = field(default_factory=tuple)  # list of Message-ID strings

    # Additional headers to include. Names/values sanitized.
    headers: Mapping[str, str] = field(default_factory=dict)

    # Optional explicit Message-ID. If None, build_email_mime_bytes will generate one.
    message_id: str | None = None

    # Some providers handle Bcc via envelope recipients rather than headers.
    include_bcc_header: bool = False

    # If set, overrides the Date header; otherwise uses now.
    date_ts: int | None = None


@dataclass(frozen=True, slots=True)
class EmailComposeLimits:
    """
    Lightweight guardrails for composition.

    These are not provider limits (Gmail/Graph have their own).
    They prevent accidental huge payloads or weird headers.
    """

    max_subject_len: int = 500
    max_header_value_len: int = 4000
    max_headers: int = 50
    max_attachment_bytes: int = 25 * 1024 * 1024  # 25MB (common-ish), provider may differ


# =============================================================================
# Address helpers
# =============================================================================


def email_address(
    address: str, *, display_name: str | None = None, meta: Mapping[str, Any] | None = None
) -> CommAddress:
    """
    Convenience: create a CommAddress for email channel.

    Raises CommValidationError if address is empty or unsafe.
    """
    addr = (address or "").strip()
    if not addr:
        raise CommValidationError("email address is required", details={"field": "address"})

    # Prevent header injection vectors inside addresses.
    if "\r" in addr or "\n" in addr:
        raise CommValidationError("email address contains illegal newline characters")

    # We allow non-ASCII in display_name; formataddr handles encoding at output time.
    return CommAddress(channel=EMAIL_CHANNEL, address=addr, display_name=display_name, meta=meta or {})


def is_email_address(address: str) -> bool:
    """
    Return True if a string looks like a reasonable email address.
    """
    a = (address or "").strip()
    if not a:
        return False
    if "\r" in a or "\n" in a:
        return False
    return bool(_EMAIL_RE.match(a))


def parse_email_address(raw: str) -> CommAddress:
    """
    Parse a single RFC 5322-ish mailbox string into a CommAddress.

    Examples:
      - 'Alice <alice@example.com>'
      - 'bob@example.com'
    """
    if raw is None:
        raise CommValidationError("raw address is required", details={"field": "raw"})

    s = str(raw).strip()
    if not s:
        raise CommValidationError("raw address is required", details={"field": "raw"})

    # Prevent header injection
    if "\r" in s or "\n" in s:
        raise CommValidationError("raw address contains illegal newline characters")

    name, addr = parseaddr(s)
    addr = (addr or "").strip()

    if not addr:
        raise CommValidationError("failed to parse email address", details={"raw": redact_value(s)})

    return email_address(addr, display_name=(name or None))


def parse_email_addresses(raw_list: str | Sequence[str]) -> list[CommAddress]:
    """
    Parse a list of addresses from:
      - a single RFC 5322 header value (comma-separated), or
      - a sequence of strings.

    Uses email.utils.getaddresses for robust splitting.
    """
    if raw_list is None:
        return []

    # Normalize to a list of strings for getaddresses
    if isinstance(raw_list, str):
        items = [raw_list]
    else:
        items = [str(x) for x in raw_list if x is not None]

    # Header injection guard
    for it in items:
        if "\r" in it or "\n" in it:
            raise CommValidationError("address list contains illegal newline characters")

    parsed = []
    for name, addr in getaddresses(items):
        addr = (addr or "").strip()
        if not addr:
            continue
        parsed.append(email_address(addr, display_name=(name or None)))

    return parsed


def format_email_addresses(addrs: Sequence[CommAddress]) -> str:
    """
    Format a list of CommAddress (email channel) into a header-safe string.

    NOTE: This produces a value for To/Cc/From headers, not for logging.
    """
    if not addrs:
        return ""

    parts: list[str] = []
    for a in addrs:
        if a.channel != EMAIL_CHANNEL:
            raise CommValidationError(
                "format_email_addresses expected email channel addresses",
                details={"channel": a.channel},
            )
        if "\r" in a.address or "\n" in a.address:
            raise CommValidationError("email address contains illegal newline characters")
        parts.append(formataddr((a.display_name or "", a.address)))
    return ", ".join(parts)


def redacted_email(addr: str | CommAddress | None) -> str:
    """
    Log-safe representation of an email address.

    - Uses deterministic hashing via redact_address from the communication contract.
    """
    if addr is None:
        return ""
    if isinstance(addr, CommAddress):
        return addr.redacted_dict().get("address") or ""
    return redact_address(str(addr))


# =============================================================================
# Header + safety helpers
# =============================================================================

_HEADER_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9\-]{0,78}[A-Za-z0-9]$")


def sanitize_header_name(name: str) -> str:
    """
    Validate/sanitize an email header name.

    - Disallows CR/LF and suspicious characters.
    - Enforces a conservative name pattern.
    """
    n = (name or "").strip()
    if not n:
        raise CommValidationError("header name is required")

    if "\r" in n or "\n" in n:
        raise CommValidationError("header name contains illegal newline characters")

    if not _HEADER_NAME_RE.match(n):
        raise CommValidationError(
            "header name has invalid format",
            details={"header": redact_value(n)},
        )
    return n


def sanitize_header_value(value: str, *, limits: EmailComposeLimits | None = None) -> str:
    """
    Sanitize an email header value.

    - Disallows CR/LF to prevent header injection.
    - Applies a conservative length cap.
    """
    lim = limits or EmailComposeLimits()
    v = "" if value is None else str(value)

    if "\r" in v or "\n" in v:
        raise CommValidationError("header value contains illegal newline characters")

    if len(v) > lim.max_header_value_len:
        v = v[: lim.max_header_value_len] + "…"
    return v


# =============================================================================
# MIME composition
# =============================================================================


def email_outbound_summary(outbound: CommOutboundMessage) -> dict[str, Any]:
    """
    Log-safe summary of an outbound email.

    - No bodies
    - No raw addresses
    - No attachment bytes
    """
    if outbound.channel != EMAIL_CHANNEL:
        raise CommValidationError("email_outbound_summary expects channel='email'")

    return {
        "channel": outbound.channel,
        "to": [a.redacted_dict() for a in (outbound.to or ())],
        "cc_count": len(outbound.cc or ()),
        "bcc_count": len(outbound.bcc or ()),
        "from": outbound.from_addr.redacted_dict() if outbound.from_addr else None,
        "subject_len": len(outbound.subject) if outbound.subject else 0,
        "text_len": len(outbound.text) if outbound.text else 0,
        "html_len": len(outbound.html) if outbound.html else 0,
        "attachment_count": len(outbound.attachments or ()),
        "client_message_id": outbound.client_message_id,
        "meta": redact_mapping(outbound.meta),
    }


def _split_content_type(ct: str | None) -> tuple[str, str]:
    if not ct:
        return "application", "octet-stream"
    c = ct.strip()
    if "/" not in c:
        return "application", "octet-stream"
    maintype, subtype = c.split("/", 1)
    maintype = maintype.strip() or "application"
    subtype = subtype.strip() or "octet-stream"
    return maintype, subtype


def build_email_mime_bytes(
    outbound: CommOutboundMessage,
    *,
    options: EmailSendOptions | None = None,
    limits: EmailComposeLimits | None = None,
) -> bytes:
    """
    Build RFC822 MIME bytes from a CommOutboundMessage.

    Provider connectors can pass these bytes to:
      - Gmail API: "raw" (base64url encoding done by provider layer)
      - Microsoft Graph: sendMail (often takes JSON; provider can still use MIME if desired)
      - SMTP relay: sendmail raw data

    IMPORTANT:
    - This function returns message bytes containing body and attachments.
    - Do not log the returned bytes.

    Notes:
    - Bcc header is excluded by default (privacy). Envelope recipients should still include Bcc.
    - If html exists, a multipart/alternative is created.
    """
    if outbound.channel != EMAIL_CHANNEL:
        raise CommValidationError(
            "build_email_mime_bytes expects outbound.channel='email'",
            details={"channel": outbound.channel},
        )

    opt = options or EmailSendOptions()
    lim = limits or EmailComposeLimits()

    msg = EmailMessage(policy=SMTP)

    # Date
    ts = int(opt.date_ts if opt.date_ts is not None else time.time())
    # EmailMessage will generate Date automatically on serialization in some policies,
    # but we set it explicitly for determinism.
    # RFC 2822 date formatting is handled by email library when setting via "Date" string,
    # but simplest is to let EmailMessage manage; setting raw string is acceptable.
    # We'll avoid extra formatting dependencies; provider can overwrite if needed.
    msg["Date"] = sanitize_header_value(time.strftime("%a, %d %b %Y %H:%M:%S +0000", time.gmtime(ts)), limits=lim)

    # Message-ID
    if opt.message_id:
        mid = sanitize_header_value(opt.message_id, limits=lim)
    else:
        # Use domain from From address if available; otherwise a local placeholder.
        dom = "francis.local"
        if outbound.from_addr and "@" in (outbound.from_addr.address or ""):
            dom = outbound.from_addr.address.split("@", 1)[1].strip() or dom
        mid = make_msgid(domain=dom)
    msg["Message-ID"] = mid

    # From / To / Cc / Bcc (optional)
    if outbound.from_addr:
        if outbound.from_addr.channel != EMAIL_CHANNEL:
            raise CommValidationError(
                "from_addr must be an email address",
                details={"channel": outbound.from_addr.channel},
            )
        msg["From"] = format_email_addresses([outbound.from_addr])

    if outbound.to:
        msg["To"] = format_email_addresses(list(outbound.to))
    else:
        # Some providers allow empty To when sending via "send as"; keep strict.
        raise CommValidationError("email outbound must have at least one recipient in 'to'")

    if outbound.cc:
        msg["Cc"] = format_email_addresses(list(outbound.cc))

    if opt.include_bcc_header and outbound.bcc:
        msg["Bcc"] = format_email_addresses(list(outbound.bcc))

    # Subject
    if outbound.subject is not None:
        subj = outbound.subject
        if len(subj) > lim.max_subject_len:
            subj = subj[: lim.max_subject_len] + "…"
        msg["Subject"] = sanitize_header_value(subj, limits=lim)

    # Reply-To / threading headers
    if opt.reply_to:
        msg["Reply-To"] = format_email_addresses(list(opt.reply_to))

    if opt.in_reply_to:
        msg["In-Reply-To"] = sanitize_header_value(opt.in_reply_to, limits=lim)

    if opt.references:
        # References header is a whitespace-separated list of Message-IDs
        refs = " ".join(sanitize_header_value(r, limits=lim) for r in opt.references if r)
        if refs:
            msg["References"] = refs

    # Additional headers (sanitized)
    if opt.headers:
        if len(opt.headers) > lim.max_headers:
            raise CommValidationError(
                "too many custom headers",
                details={"count": len(opt.headers), "max": lim.max_headers},
            )
        for k, v in opt.headers.items():
            hk = sanitize_header_name(k)
            hv = sanitize_header_value(v, limits=lim)
            # Avoid overriding core headers set above unless explicitly desired by caller.
            # If they want overrides, they can supply via provider layer or set earlier.
            if hk in msg:
                continue
            msg[hk] = hv

    # Body
    text = outbound.text or ""
    html = outbound.html

    if html:
        # multipart/alternative: text/plain then text/html
        msg.set_content(text)
        msg.add_alternative(html, subtype="html")
    else:
        msg.set_content(text)

    # Attachments
    total_attach_bytes = 0
    for att in outbound.attachments or ():
        if not isinstance(att, CommAttachmentUpload):
            raise CommValidationError("attachments must be CommAttachmentUpload objects")

        data = att.data
        if data is None:
            raise CommValidationError(
                "attachment upload missing data bytes",
                details={"filename": att.filename},
            )

        size = att.size_bytes if att.size_bytes is not None else len(data)
        total_attach_bytes += int(size)
        if total_attach_bytes > lim.max_attachment_bytes:
            raise CommValidationError(
                "attachments exceed compose limit",
                details={"total_bytes": total_attach_bytes, "max_bytes": lim.max_attachment_bytes},
            )

        maintype, subtype = _split_content_type(att.content_type)
        filename = (att.filename or "attachment").strip()

        if "\r" in filename or "\n" in filename:
            raise CommValidationError("attachment filename contains illegal newline characters")

        msg.add_attachment(
            data,
            maintype=maintype,
            subtype=subtype,
            filename=filename,
        )

    return msg.as_bytes()
