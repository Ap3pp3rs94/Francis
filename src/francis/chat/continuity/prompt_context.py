from __future__ import annotations

import re
from typing import Any

from francis.chat.continuity.ledger import tail
from francis.governance.redaction import redact_secret_text

__all__ = ["continuity_prompt_context_readback"]

_KIND = "francis.chat.continuity.prompt_context_readback"
_SOURCE_ID = "conversation_ledger"
_MAX_SCAN_LIMIT = 120
_MAX_CONTEXT_LINES = 4
_MAX_LINE_CHARS = 260
_MAX_QUERY_CHARS = 512
_TOKEN_RE = re.compile(r"[a-z0-9_]{3,}", re.IGNORECASE)
_STOPWORDS = {
    "about",
    "again",
    "also",
    "and",
    "are",
    "can",
    "could",
    "did",
    "does",
    "for",
    "from",
    "have",
    "how",
    "into",
    "just",
    "know",
    "like",
    "me",
    "need",
    "now",
    "our",
    "please",
    "should",
    "that",
    "the",
    "this",
    "was",
    "what",
    "when",
    "where",
    "with",
    "you",
    "your",
}


def continuity_prompt_context_readback(
    *,
    query: Any,
    limit: int = 80,
    max_lines: int = 3,
) -> dict[str, Any]:
    """Return bounded, redacted conversation-ledger context for chat prompts."""
    safe_limit = _bounded_int(limit, default=80, minimum=1, maximum=_MAX_SCAN_LIMIT)
    safe_max_lines = _bounded_int(max_lines, default=3, minimum=1, maximum=_MAX_CONTEXT_LINES)
    query_text = _bounded_line(query, max_chars=_MAX_QUERY_CHARS)
    query_tokens = _tokens(query_text)
    entries = tail(limit=safe_limit)
    current_query = _normalize_for_compare(query_text)

    candidates: list[tuple[int, int, str]] = []
    recent_candidates: list[tuple[int, str]] = []
    for position, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        role = _role(entry.get("role"))
        content = _bounded_line(entry.get("content"), max_chars=_MAX_LINE_CHARS)
        if not content or _normalize_for_compare(content) == current_query:
            continue

        line = _context_line(kind="recent", role=role, content=content)
        recent_candidates.append((position, line))
        score = _score(content, query_tokens)
        if score > 0:
            candidates.append((score, position, _context_line(kind="relevant", role=role, content=content)))

    lines: list[str] = []
    seen: set[str] = set()
    for _score_value, _position, line in sorted(candidates, key=lambda item: (-item[0], -item[1])):
        if line in seen:
            continue
        lines.append(line)
        seen.add(line)
        if len(lines) >= safe_max_lines:
            break

    if len(lines) < safe_max_lines:
        for _position, line in sorted(recent_candidates, key=lambda item: -item[0]):
            if line in seen:
                continue
            lines.append(line)
            seen.add(line)
            if len(lines) >= safe_max_lines:
                break

    status = "context_ready" if lines else "empty"
    return {
        "ok": True,
        "kind": _KIND,
        "plane": "P8_MEMORY",
        "source_id": _SOURCE_ID,
        "status": status,
        "ledger_entry_count": len(entries),
        "query_token_count": len(query_tokens),
        "matched_entry_count": len(candidates),
        "line_count": len(lines),
        "limit": safe_limit,
        "max_context_lines": safe_max_lines,
        "chat_context": {
            "target": "telemetry_context.prompt_lines",
            "line_count": len(lines),
            "max_context_lines": safe_max_lines,
            "lines": lines,
            "source": "data/conversations/ledger/ledger.jsonl",
            "visible_header_required": True,
            "continuity_context_is_untrusted_input": True,
        },
        "reads_memory": True,
        "writes_memory": False,
        "calls_model": False,
        "mutates_prompt": False,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "readback_only": True,
            "uses_conversation_ledger": True,
            "redacts_context_lines": True,
            "bounded_line_count": True,
            "bounded_line_chars": _MAX_LINE_CHARS,
            "does_not_write_memory": True,
            "does_not_call_model": True,
            "does_not_select_tools": True,
            "grants_memory_write_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _bounded_line(value: Any, *, max_chars: int) -> str:
    text = redact_secret_text(_safe_str(value)).replace("\r", " ").replace("\n", " ")
    text = " ".join(text.split()).strip()
    if not text:
        return ""
    return text[: max(1, max_chars)]


def _role(value: Any) -> str:
    role = re.sub(r"[^a-z0-9_.-]+", "", _safe_str(value).strip().lower())
    return role[:32] or "unknown"


def _tokens(value: str) -> set[str]:
    tokens: set[str] = set()
    for match in _TOKEN_RE.findall(value.lower()):
        if match in _STOPWORDS:
            continue
        tokens.add(match)
    return tokens


def _score(content: str, query_tokens: set[str]) -> int:
    if not query_tokens:
        return 0
    content_tokens = _tokens(content)
    if not content_tokens:
        return 0
    return len(query_tokens.intersection(content_tokens))


def _context_line(*, kind: str, role: str, content: str) -> str:
    return _bounded_line(f"continuity.ledger.{kind}[{role}]: {content}", max_chars=_MAX_LINE_CHARS)


def _normalize_for_compare(value: str) -> str:
    return " ".join(value.lower().split())
