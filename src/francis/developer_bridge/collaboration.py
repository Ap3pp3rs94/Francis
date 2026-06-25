from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any
from uuid import uuid4

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

from .agents import enforce_collaboration_agents_enabled
from .collaboration_review import read_collaboration_review
from .repo_tools import DeveloperBridgeError

_AGENT_RE = re.compile(r"^[a-z][a-z0-9_.-]{0,63}$")
_MAX_PROMPT_CHARS = 8_000
_MAX_OBJECTIVE_CHARS = 512
_MAX_CONTEXT_CHARS = 4_000
_MAX_LIMIT = 50
_MAX_SESSION_LIMIT = 20
_SESSION_GAP_SECONDS = 30 * 60
_PREVIEW_MAX_CHARS = 220
_PROMPT_CACHE_TTL_SECONDS = 1.0
_RECENT_PROMPT_SCAN_THRESHOLD = 250
_RECENT_PROMPT_SCAN_MIN = 64
_RECENT_PROMPT_SCAN_MAX = 500
_KNOWN_STATUSES = frozenset({"queued", "acknowledged", "delivered", "blocked", "closed"})
_PROMPT_CACHE_LOCK = Lock()
_prompt_cache_root: Path | None = None
_prompt_cache_deadline = 0.0
_prompt_cache_records: list[dict[str, object]] | None = None


def submit_collaboration_prompt(
    source_agent: str,
    target_agent: str,
    prompt: str,
    objective: str = "",
    context: str = "",
) -> dict[str, object]:
    """Append a bounded prompt envelope for another Francis-connected agent."""

    source = _agent_id(source_agent, field="source_agent")
    target = _agent_id(target_agent, field="target_agent")
    if source == target:
        raise DeveloperBridgeError("same_agent_denied", "source_agent and target_agent must be different")
    enforce_collaboration_agents_enabled(source, target)

    clean_prompt = _bounded_text(prompt, max_chars=_MAX_PROMPT_CHARS, field="prompt")
    clean_objective = _bounded_optional_text(objective, max_chars=_MAX_OBJECTIVE_CHARS)
    clean_context = _bounded_optional_text(context, max_chars=_MAX_CONTEXT_CHARS)

    created_at = _utc_now()
    prompt_id = _prompt_id(created_at, source, target, clean_prompt)
    redacted_objective = redact_secret_text(clean_objective)
    redacted_prompt = redact_secret_text(clean_prompt)
    redacted_context = redact_secret_text(clean_context)
    record: dict[str, Any] = {
        "kind": "developer_bridge.collaboration_prompt",
        "id": prompt_id,
        "created_at": created_at,
        "updated_at": created_at,
        "status": "queued",
        "source_agent": source,
        "target_agent": target,
        "objective": redacted_objective,
        "prompt": redacted_prompt,
        "context": redacted_context,
        "chat_handoff": _chat_handoff(
            prompt_id=prompt_id,
            source_agent=source,
            target_agent=target,
            objective=redacted_objective,
            prompt=redacted_prompt,
            context=redacted_context,
        ),
        "limits": {
            "prompt_max_chars": _MAX_PROMPT_CHARS,
            "objective_max_chars": _MAX_OBJECTIVE_CHARS,
            "context_max_chars": _MAX_CONTEXT_CHARS,
        },
        "governance": _governance(write=True),
    }
    path = _prompt_path(prompt_id)
    _atomic_write_json(path, record)
    _invalidate_prompt_cache()

    return {
        "kind": "developer_bridge.collaboration_prompt_submit",
        "ok": True,
        "prompt_id": prompt_id,
        "path": _display_path(path),
        "record": record,
        "chat_handoff": record["chat_handoff"],
        "governance": _governance(write=True),
    }


def list_collaboration_prompts(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "queued",
    limit: int = 20,
) -> dict[str, object]:
    """Read bounded prompt envelopes for Francis-connected agents."""

    clean_agent = _optional_agent_id(agent, field="agent")
    clean_source = _optional_agent_id(source_agent, field="source_agent")
    clean_target = _optional_agent_id(target_agent, field="target_agent")
    clean_status = _clean_status(status, default="queued")
    clean_limit = _bounded_int(limit, minimum=1, maximum=_MAX_LIMIT)

    filtered = _filtered_prompts(
        agent=clean_agent,
        source_agent=clean_source,
        target_agent=clean_target,
        status=clean_status,
        limit=clean_limit,
    )

    return {
        "kind": "developer_bridge.collaboration_prompt_list",
        "ok": True,
        "mode": "read_only",
        "items": filtered.items,
        "count": len(filtered.items),
        "truncated": filtered.truncated,
        "filters": {
            "agent": clean_agent,
            "source_agent": clean_source,
            "target_agent": clean_target,
            "status": clean_status,
            "limit": clean_limit,
        },
        "governance": _governance(write=False),
    }


def read_collaboration_transcript(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = 20,
) -> dict[str, object]:
    """Read the local collaboration relay as an operator-visible transcript."""

    clean_agent = _optional_agent_id(agent, field="agent")
    clean_source = _optional_agent_id(source_agent, field="source_agent")
    clean_target = _optional_agent_id(target_agent, field="target_agent")
    clean_status = _clean_status(status, default="")
    clean_limit = _bounded_int(limit, minimum=1, maximum=_MAX_LIMIT)
    filtered = _filtered_prompts(
        agent=clean_agent,
        source_agent=clean_source,
        target_agent=clean_target,
        status=clean_status,
        limit=clean_limit,
    )

    return {
        "kind": "developer_bridge.collaboration_transcript",
        "ok": True,
        "mode": "read_only",
        "relay_root": _display_path(_relay_root()),
        "items": [_transcript_item(record) for record in filtered.items],
        "count": len(filtered.items),
        "truncated": filtered.truncated,
        "filters": {
            "agent": clean_agent,
            "source_agent": clean_source,
            "target_agent": clean_target,
            "status": clean_status,
            "limit": clean_limit,
        },
        "governance": _governance(write=False),
    }


def read_collaboration_sessions(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = 10,
    item_limit: int = 50,
) -> dict[str, object]:
    """Read bounded collaboration session summaries without requiring raw transcript text."""

    clean_agent = _optional_agent_id(agent, field="agent")
    clean_source = _optional_agent_id(source_agent, field="source_agent")
    clean_target = _optional_agent_id(target_agent, field="target_agent")
    clean_status = _clean_status(status, default="")
    clean_limit = _bounded_int(limit, minimum=1, maximum=_MAX_SESSION_LIMIT)
    clean_item_limit = _bounded_int(item_limit, minimum=1, maximum=_MAX_LIMIT)
    filtered = _filtered_prompts(
        agent=clean_agent,
        source_agent=clean_source,
        target_agent=clean_target,
        status=clean_status,
        limit=clean_item_limit,
    )
    review_readback = read_collaboration_review(limit=min(clean_item_limit, _MAX_LIMIT))
    review_items = [item for item in _list(review_readback.get("items")) if isinstance(item, dict)]
    sessions = _session_summaries(filtered.items, review_items=review_items)
    limited_sessions = sessions[:clean_limit]

    return {
        "kind": "developer_bridge.collaboration_sessions",
        "schema_version": "developer_bridge_collaboration_sessions_v1",
        "ok": True,
        "mode": "read_only",
        "relay_root": _display_path(_relay_root()),
        "items": limited_sessions,
        "count": len(limited_sessions),
        "truncated": filtered.truncated or len(sessions) > clean_limit,
        "filters": {
            "agent": clean_agent,
            "source_agent": clean_source,
            "target_agent": clean_target,
            "status": clean_status,
            "limit": clean_limit,
            "item_limit": clean_item_limit,
        },
        "definitions": {
            "session": "Messages grouped by timestamp gap from bounded relay receipts.",
            "latest_preview": "A short bounded preview from the latest receipt, not a full transcript store.",
            "latest_review_gate": (
                "The latest typed review gate matched to a session relay receipt, without loading raw transcript text."
            ),
        },
        "governance": {
            **_governance(write=False),
            "surface": "developer_bridge.collaboration_sessions",
            "stores_full_transcript": False,
            "calls_model": False,
            "trains_model": False,
            "grants_memory_write_authority": False,
        },
    }


class _FilteredPrompts:
    def __init__(self, items: list[dict[str, object]], truncated: bool) -> None:
        self.items = items
        self.truncated = truncated


def _relay_root() -> Path:
    root = data_dir() / "integrations" / "developer_bridge" / "collaboration_prompts"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _prompt_path(prompt_id: str) -> Path:
    if not re.fullmatch(r"collab-[0-9a-f]{16}-[0-9a-f]{12}", prompt_id):
        raise DeveloperBridgeError("prompt_id_denied", "prompt_id is not a relay-issued identifier")
    return _relay_root() / f"{prompt_id}.json"


def _read_prompt(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "developer_bridge.collaboration_prompt":
        return None
    return _with_chat_handoff(data)


def _invalidate_prompt_cache() -> None:
    global _prompt_cache_deadline
    global _prompt_cache_records
    global _prompt_cache_root
    with _PROMPT_CACHE_LOCK:
        _prompt_cache_root = None
        _prompt_cache_deadline = 0.0
        _prompt_cache_records = None


def _with_chat_handoff(record: dict[str, object]) -> dict[str, object]:
    if isinstance(record.get("chat_handoff"), dict):
        return record
    updated = dict(record)
    updated["chat_handoff"] = _chat_handoff(
        prompt_id=str(record.get("id") or ""),
        source_agent=str(record.get("source_agent") or ""),
        target_agent=str(record.get("target_agent") or ""),
        objective=str(record.get("objective") or ""),
        prompt=str(record.get("prompt") or ""),
        context=str(record.get("context") or ""),
    )
    return updated


def _filtered_prompts(
    *,
    agent: str,
    source_agent: str,
    target_agent: str,
    status: str,
    limit: int,
) -> _FilteredPrompts:
    if not agent and not source_agent and not target_agent and not status:
        recent = _recent_unfiltered_prompts(limit=limit)
        if recent is not None:
            return recent

    matches: list[dict[str, object]] = []
    for record in _sorted_prompts():
        if status and str(record.get("status") or "").lower() != status:
            continue
        if agent and agent not in {record.get("source_agent"), record.get("target_agent")}:
            continue
        if source_agent and record.get("source_agent") != source_agent:
            continue
        if target_agent and record.get("target_agent") != target_agent:
            continue
        matches.append(record)
        if len(matches) > limit:
            return _FilteredPrompts(items=matches[:limit], truncated=True)
    return _FilteredPrompts(items=matches, truncated=False)


def _recent_unfiltered_prompts(*, limit: int) -> _FilteredPrompts | None:
    root = _relay_root()
    paths = list(root.glob("*.json"))
    if len(paths) <= _RECENT_PROMPT_SCAN_THRESHOLD:
        return None
    scan_limit = min(max(limit + 1, _RECENT_PROMPT_SCAN_MIN), _RECENT_PROMPT_SCAN_MAX)
    recent_paths = sorted(paths, key=_path_sort_key, reverse=True)[:scan_limit]
    records: list[dict[str, object]] = []
    for path in recent_paths:
        record = _read_prompt(path)
        if record:
            records.append(record)
    sorted_records = sorted(records, key=_sort_key, reverse=True)
    return _FilteredPrompts(items=sorted_records[:limit], truncated=len(paths) > limit)


def _path_sort_key(path: Path) -> tuple[int, str]:
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (mtime, path.name)


def _sorted_prompts() -> list[dict[str, object]]:
    global _prompt_cache_deadline
    global _prompt_cache_records
    global _prompt_cache_root
    root = _relay_root()
    now = monotonic()
    with _PROMPT_CACHE_LOCK:
        if _prompt_cache_root == root and _prompt_cache_records is not None and now < _prompt_cache_deadline:
            return [dict(record) for record in _prompt_cache_records]

    records: list[dict[str, object]] = []
    for path in root.glob("*.json"):
        record = _read_prompt(path)
        if record:
            records.append(record)
    sorted_records = sorted(records, key=_sort_key, reverse=True)
    with _PROMPT_CACHE_LOCK:
        _prompt_cache_root = root
        _prompt_cache_records = sorted_records
        _prompt_cache_deadline = monotonic() + _PROMPT_CACHE_TTL_SECONDS
    return [dict(record) for record in sorted_records]


def _sort_key(record: dict[str, object]) -> tuple[str, str]:
    return (str(record.get("created_at") or ""), str(record.get("id") or ""))


def _session_summaries(
    records: list[dict[str, object]],
    *,
    review_items: list[dict[str, object]] | None = None,
) -> list[dict[str, object]]:
    chronological = [record for record in reversed(records) if not _is_auto_ack_record(record)]
    sessions: list[list[dict[str, object]]] = []
    for record in chronological:
        timestamp = _record_timestamp(record)
        previous = sessions[-1][-1] if sessions and sessions[-1] else None
        previous_timestamp = _record_timestamp(previous) if previous else 0.0
        if not sessions or (timestamp and previous_timestamp and timestamp - previous_timestamp > _SESSION_GAP_SECONDS):
            sessions.append([record])
        else:
            sessions[-1].append(record)
    return [
        _session_summary(index, records, review_items=review_items or [])
        for index, records in enumerate(reversed(sessions), start=1)
    ]


def _session_summary(
    index: int,
    records: list[dict[str, object]],
    *,
    review_items: list[dict[str, object]],
) -> dict[str, object]:
    latest = records[-1] if records else {}
    started_at = str(records[0].get("created_at") or "") if records else ""
    ended_at = str(latest.get("created_at") or "")
    participants = sorted(
        {str(record.get("source_agent") or "") for record in records if str(record.get("source_agent") or "")}
        | {str(record.get("target_agent") or "") for record in records if str(record.get("target_agent") or "")}
    )
    direction_counts: dict[str, int] = {}
    for record in records:
        source = str(record.get("source_agent") or "")
        target = str(record.get("target_agent") or "")
        direction = f"{source}->{target}" if source and target else "unknown"
        direction_counts[direction] = direction_counts.get(direction, 0) + 1
    return {
        "id": f"session-{started_at or index}",
        "started_at": started_at,
        "ended_at": ended_at,
        "message_count": len(records),
        "participants": participants,
        "direction_counts": direction_counts,
        "latest_item_id": latest.get("id", ""),
        "latest_direction": _record_direction(latest),
        "latest_objective": latest.get("objective", ""),
        "latest_preview": _preview_text(str(latest.get("prompt") or "")),
        "latest_review_gate": _latest_session_review_gate(records, review_items),
    }


def _latest_session_review_gate(
    records: list[dict[str, object]],
    review_items: list[dict[str, object]],
) -> dict[str, object]:
    prompt_ids = {str(record.get("id") or "") for record in records if str(record.get("id") or "")}
    for item in review_items:
        source = _dict(item.get("source"))
        source_prompt_ids = {
            str(source.get("codex_prompt_id") or ""),
            str(source.get("ollama_prompt_id") or ""),
        }
        if not prompt_ids.intersection(source_prompt_ids):
            continue
        build_issue = _dict(item.get("build_issue"))
        build_gate = _dict(item.get("build_direction_gate"))
        recommendation = _dict(item.get("review_recommendation"))
        return {
            "observed": True,
            "review_item_id": _bounded_optional_text(str(item.get("id") or ""), max_chars=160),
            "insight_id": _bounded_optional_text(str(item.get("insight_id") or ""), max_chars=160),
            "turn": _int(item.get("turn")),
            "topic": _preview_text(str(item.get("topic") or "")),
            "build_issue_code": _bounded_optional_text(str(build_issue.get("code") or ""), max_chars=120),
            "surface": _bounded_optional_text(
                str(build_gate.get("surface_under_review") or item.get("concrete_repo_surface") or ""),
                max_chars=220,
            ),
            "required_review_artifact": _bounded_optional_text(
                str(build_gate.get("required_review_artifact") or item.get("review_artifact") or ""),
                max_chars=260,
            ),
            "build_direction_state": _bounded_optional_text(
                str(build_gate.get("state") or "advisory_review_required"),
                max_chars=120,
            ),
            "blocks_build_direction": bool(build_gate.get("blocks_build_direction")),
            "requires_codex_or_operator_review": bool(build_gate.get("requires_codex_or_operator_review")),
            "requires_repo_truth_review": bool(build_gate.get("requires_repo_truth_review")),
            "next_codex_action": _preview_text(str(recommendation.get("next_codex_action") or "")),
            "grants_execution_authority": bool(build_gate.get("grants_execution_authority")),
            "grants_mutation_authority": bool(build_gate.get("grants_mutation_authority")),
            "grants_approval_authority": bool(build_gate.get("grants_approval_authority")),
            "grants_memory_write_authority": bool(build_gate.get("grants_memory_write_authority")),
            "stores_full_transcript": False,
        }
    return {
        "observed": False,
        "stores_full_transcript": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _record_direction(record: dict[str, object]) -> str:
    source = str(record.get("source_agent") or "")
    target = str(record.get("target_agent") or "")
    return f"{source}->{target}" if source and target else ""


def _is_auto_ack_record(record: dict[str, object]) -> bool:
    objective = str(record.get("objective") or "").lower()
    context = str(record.get("context") or "").lower()
    prompt = str(record.get("prompt") or "").lower()
    return (
        objective.startswith("auto-ack ") or "no_response_requested=true" in context or prompt.startswith("auto-ack ")
    )


def _record_timestamp(record: dict[str, object] | None) -> float:
    if not record:
        return 0.0
    created_at = str(record.get("created_at") or "")
    if not created_at:
        return 0.0
    try:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _preview_text(value: str) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= _PREVIEW_MAX_CHARS:
        return text
    return f"{text[: _PREVIEW_MAX_CHARS - 3]}..."


def _transcript_item(record: dict[str, object]) -> dict[str, object]:
    source = str(record.get("source_agent") or "")
    target = str(record.get("target_agent") or "")
    return {
        "id": record.get("id"),
        "created_at": record.get("created_at"),
        "updated_at": record.get("updated_at"),
        "status": record.get("status"),
        "source_agent": source,
        "target_agent": target,
        "direction": f"{source}->{target}" if source and target else "",
        "objective": record.get("objective"),
        "prompt": record.get("prompt"),
        "context": record.get("context"),
        "chat_handoff": record.get("chat_handoff")
        or _chat_handoff(
            prompt_id=str(record.get("id") or ""),
            source_agent=source,
            target_agent=target,
            objective=str(record.get("objective") or ""),
            prompt=str(record.get("prompt") or ""),
            context=str(record.get("context") or ""),
        ),
        "governance": record.get("governance"),
    }


def _agent_id(value: str, *, field: str) -> str:
    text = _bounded_text(value, max_chars=64, field=field).lower()
    if not _AGENT_RE.fullmatch(text):
        raise DeveloperBridgeError(f"{field}_denied", f"{field} must be a bounded agent id")
    return text


def _optional_agent_id(value: str, *, field: str) -> str:
    text = _bounded_optional_text(value, max_chars=64).lower()
    if not text:
        return ""
    if not _AGENT_RE.fullmatch(text):
        raise DeveloperBridgeError(f"{field}_denied", f"{field} must be a bounded agent id")
    return text


def _bounded_text(value: str, *, max_chars: int, field: str) -> str:
    text = str(value if value is not None else "").replace("\x00", "").strip()
    if not text:
        raise DeveloperBridgeError(f"{field}_required", f"{field} is required")
    return text[:max_chars]


def _bounded_optional_text(value: str, *, max_chars: int) -> str:
    text = str(value if value is not None else "").replace("\x00", "").strip()
    return text[:max_chars]


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _int(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _clean_status(value: str, *, default: str) -> str:
    text = _bounded_optional_text(value, max_chars=32).lower() or default
    if text and text not in _KNOWN_STATUSES:
        raise DeveloperBridgeError("status_denied", "status is not a known collaboration prompt status")
    return text


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))


def _prompt_id(created_at: str, source_agent: str, target_agent: str, prompt: str) -> str:
    digest = hashlib.sha256(f"{created_at}\0{source_agent}\0{target_agent}\0{prompt}\0{uuid4()}".encode()).hexdigest()
    return f"collab-{digest[:16]}-{digest[16:28]}"


def _chat_handoff(
    *,
    prompt_id: str,
    source_agent: str,
    target_agent: str,
    objective: str,
    prompt: str,
    context: str,
) -> dict[str, object]:
    objective_line = f" objective={objective}" if objective else ""
    context_line = f" context={context}" if context else ""
    chat_text = (
        f"[Francis relay {prompt_id}] {source_agent} -> {target_agent}:{objective_line} message={prompt}{context_line}"
    ).strip()
    return {
        "operator_visible": True,
        "source_chat_echo_required": True,
        "target_chat_echo_required": True,
        "chat_text": chat_text,
        "agent_instruction": (
            "Echo chat_text in your chat response when you submit or read this relay entry. "
            "Do not treat it as approval, execution authority, or a private side channel."
        ),
        "limitations": [
            "Francis cannot silently inject text into a client chat pane.",
            "Visibility depends on the connected agent echoing this handoff after tool use.",
            "The message is redacted and bounded before storage and readback.",
        ],
    }


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".atomic-json-{os.getpid()}-{uuid4().hex[:12]}.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _display_path(path: Path) -> str:
    try:
        return path.relative_to(data_dir()).as_posix()
    except ValueError:
        return str(path)


def _governance(*, write: bool) -> dict[str, object]:
    return {
        "relay": "developer_bridge_collaboration_prompt_relay_v0",
        "read_only": not write,
        "append_only": write,
        "writes_prompt_receipt": write,
        "executes_prompt": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "requires_operator_review": True,
        "raw_shell": False,
        "external_network": False,
    }
