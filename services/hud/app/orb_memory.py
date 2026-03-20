from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_llm import chat
from services.hud.app.state import get_workspace_root

DEFAULT_ORB_CONVERSATION_ID = "primary"
SESSION_DIR = "orb/chat/sessions"
LONG_TERM_PATH = "orb/chat/long_term_memory.json"
LOG_PATH = "logs/francis.log.jsonl"
DECISIONS_PATH = "journals/decisions.jsonl"


def _build_fs(workspace_root: Path | None = None) -> WorkspaceFS:
    root = (workspace_root or get_workspace_root()).resolve()
    return WorkspaceFS(
        roots=[root],
        journal_path=(root / "journals" / "fs.jsonl").resolve(),
    )


def _build_ledger(fs: WorkspaceFS) -> RunLedger:
    return RunLedger(fs, rel_path="runs/run_ledger.jsonl")


def _safe_conversation_id(value: object) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", str(value or "").strip())
    cleaned = cleaned.strip("-._")
    return cleaned or DEFAULT_ORB_CONVERSATION_ID


def _session_rel_path(conversation_id: str) -> str:
    return f"{SESSION_DIR}/{_safe_conversation_id(conversation_id)}.json"


def _read_json(fs: WorkspaceFS, rel_path: str, default: Any) -> Any:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default


def _write_json(fs: WorkspaceFS, rel_path: str, payload: Any) -> None:
    fs.write_text(rel_path, json.dumps(payload, ensure_ascii=False, indent=2))


def _default_session(conversation_id: str) -> dict[str, Any]:
    now = utc_now_iso()
    return {
        "conversation_id": _safe_conversation_id(conversation_id),
        "created_at": now,
        "updated_at": now,
        "messages": [],
        "thought_ids": [],
        "message_count": 0,
    }


def _normalize_message(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    role = str(row.get("role", "")).strip().lower()
    if role not in {"system", "user", "assistant"}:
        return None
    content = str(row.get("content", "")).strip()
    if not content:
        return None
    return {
        "id": str(row.get("id", "")).strip() or str(uuid4()),
        "role": role,
        "content": content,
        "kind": str(row.get("kind", "chat")).strip().lower() or "chat",
        "ts": str(row.get("ts", "")).strip() or utc_now_iso(),
        "metadata": row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {},
    }


def load_orb_chat_session(
    conversation_id: str = DEFAULT_ORB_CONVERSATION_ID,
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    fs = _build_fs(workspace_root)
    safe_id = _safe_conversation_id(conversation_id)
    payload = _read_json(fs, _session_rel_path(safe_id), _default_session(safe_id))
    if not isinstance(payload, dict):
        return _default_session(safe_id)
    session = _default_session(safe_id)
    session.update(payload)
    session["conversation_id"] = safe_id
    session["messages"] = [
        normalized
        for normalized in (_normalize_message(row) for row in payload.get("messages", []))
        if normalized is not None
    ][-120:]
    session["thought_ids"] = [
        str(value).strip()
        for value in payload.get("thought_ids", [])
        if str(value).strip()
    ][-40:]
    session["message_count"] = len(session["messages"])
    return session


def save_orb_chat_session(
    session: dict[str, Any],
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    fs = _build_fs(workspace_root)
    safe_id = _safe_conversation_id(session.get("conversation_id", DEFAULT_ORB_CONVERSATION_ID))
    normalized = _default_session(safe_id)
    normalized.update(session if isinstance(session, dict) else {})
    normalized["conversation_id"] = safe_id
    normalized["messages"] = [
        normalized_row
        for normalized_row in (_normalize_message(row) for row in normalized.get("messages", []))
        if normalized_row is not None
    ][-120:]
    normalized["thought_ids"] = [
        str(value).strip()
        for value in normalized.get("thought_ids", [])
        if str(value).strip()
    ][-40:]
    normalized["updated_at"] = utc_now_iso()
    normalized["message_count"] = len(normalized["messages"])
    _write_json(fs, _session_rel_path(safe_id), normalized)
    return normalized


def append_orb_chat_turn(
    *,
    conversation_id: str,
    role: str,
    content: str,
    kind: str = "chat",
    metadata: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    session = load_orb_chat_session(conversation_id, workspace_root=workspace_root)
    normalized = _normalize_message(
        {
            "role": role,
            "content": content,
            "kind": kind,
            "metadata": metadata or {},
        }
    )
    if normalized is None:
        raise ValueError("Orb chat turn requires a valid role and content.")
    session["messages"].append(normalized)
    return save_orb_chat_session(session, workspace_root=workspace_root)


def append_orb_turn(
    *,
    conversation_id: str,
    role: str,
    content: str,
    kind: str = "chat",
    source: str = "orb.chat",
    metadata: dict[str, Any] | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    merged_metadata = {"source": str(source or "orb.chat").strip() or "orb.chat"}
    if isinstance(metadata, dict):
        merged_metadata.update(metadata)
    return append_orb_chat_turn(
        conversation_id=conversation_id,
        role=role,
        content=content,
        kind=kind,
        metadata=merged_metadata,
        workspace_root=workspace_root,
    )


def remember_orb_chat_thought(
    *,
    conversation_id: str,
    thought_id: str,
    content: str,
    detail: str = "",
    source: str = "orb.interjection",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    normalized_id = str(thought_id or "").strip()
    text = str(content or "").strip()
    if not normalized_id:
        raise ValueError("thought_id is required.")
    if not text:
        raise ValueError("Thought content is required.")
    session = load_orb_chat_session(conversation_id, workspace_root=workspace_root)
    known_ids = set(session.get("thought_ids", []))
    if normalized_id in known_ids:
        return build_orb_chat_history(conversation_id=conversation_id, workspace_root=workspace_root)
    session["thought_ids"].append(normalized_id)
    session["messages"].append(
        {
            "id": str(uuid4()),
            "role": "assistant",
            "content": text,
            "kind": "thought",
            "ts": utc_now_iso(),
            "metadata": {
                "thought_id": normalized_id,
                "source": str(source or "orb.interjection").strip() or "orb.interjection",
                "detail": str(detail or "").strip(),
            },
        }
    )
    save_orb_chat_session(session, workspace_root=workspace_root)
    return build_orb_chat_history(conversation_id=conversation_id, workspace_root=workspace_root)


def remember_orb_thought(
    *,
    conversation_id: str,
    thought_id: str,
    content: str,
    detail: str = "",
    source: str = "orb.interjection",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    return remember_orb_chat_thought(
        conversation_id=conversation_id,
        thought_id=thought_id,
        content=content,
        detail=detail,
        source=source,
        workspace_root=workspace_root,
    )


def _default_long_term_memory() -> dict[str, Any]:
    return {
        "summary": "",
        "user_preferences": [],
        "operator_context": [],
        "open_threads": [],
        "last_updated_at": "",
        "last_summarized_message_count": 0,
    }


def load_orb_long_term_memory(*, workspace_root: Path | None = None) -> dict[str, Any]:
    fs = _build_fs(workspace_root)
    payload = _read_json(fs, LONG_TERM_PATH, _default_long_term_memory())
    if not isinstance(payload, dict):
        return _default_long_term_memory()
    memory = _default_long_term_memory()
    memory.update(payload)
    for key in ("user_preferences", "operator_context", "open_threads"):
        memory[key] = [
            str(value).strip()
            for value in memory.get(key, [])
            if str(value).strip()
        ][:8]
    memory["summary"] = str(memory.get("summary", "")).strip()
    memory["last_updated_at"] = str(memory.get("last_updated_at", "")).strip()
    memory["last_summarized_message_count"] = max(
        0,
        int(memory.get("last_summarized_message_count", 0) or 0),
    )
    return memory


def save_orb_long_term_memory(
    payload: dict[str, Any],
    *,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    fs = _build_fs(workspace_root)
    memory = _default_long_term_memory()
    memory.update(payload if isinstance(payload, dict) else {})
    memory["summary"] = str(memory.get("summary", "")).strip()
    for key in ("user_preferences", "operator_context", "open_threads"):
        memory[key] = [
            str(value).strip()
            for value in memory.get(key, [])
            if str(value).strip()
        ][:8]
    memory["last_updated_at"] = utc_now_iso()
    memory["last_summarized_message_count"] = max(
        0,
        int(memory.get("last_summarized_message_count", 0) or 0),
    )
    _write_json(fs, LONG_TERM_PATH, memory)
    return memory


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except Exception:
        start = text.find("{")
        end = text.rfind("}")
        if start < 0 or end <= start:
            return {}
        try:
            payload = json.loads(text[start : end + 1])
        except Exception:
            return {}
    return payload if isinstance(payload, dict) else {}


def refresh_orb_long_term_memory(
    *,
    conversation_id: str,
    snapshot: dict[str, Any],
    perception: dict[str, Any],
    workspace_root: Path | None = None,
    force: bool = False,
) -> dict[str, Any]:
    session = load_orb_chat_session(conversation_id, workspace_root=workspace_root)
    memory = load_orb_long_term_memory(workspace_root=workspace_root)
    message_count = len(session.get("messages", []))
    if message_count < 4:
        return memory
    if not force and message_count - int(memory.get("last_summarized_message_count", 0) or 0) < 4:
        return memory

    transcript = [
        {"role": row.get("role"), "content": row.get("content"), "kind": row.get("kind")}
        for row in session.get("messages", [])[-18:]
        if isinstance(row, dict)
    ]
    system_prompt = (
        "You maintain Francis's long-term Orb conversation memory. "
        "Return JSON only with keys summary, user_preferences, operator_context, and open_threads. "
        "Keep everything local-first, concrete, and short. "
        "Do not store transient chatter. "
        "Capture only durable user preferences, recurring operator context, and unfinished threads."
    )
    response_text = ""
    try:
        response = chat(
            "orb.long_term_memory.synthesis",
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "existing_memory": memory,
                            "recent_transcript": transcript,
                            "snapshot": {
                                "control": snapshot.get("control", {}),
                                "objective": snapshot.get("objective", {}),
                                "current_work": snapshot.get("current_work", {}),
                                "runs": snapshot.get("runs", {}),
                            },
                            "perception": {
                                "summary": perception.get("summary"),
                                "detail_summary": perception.get("detail_summary"),
                                "window": perception.get("window"),
                            },
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            timeout=60.0,
            options={"temperature": 0.1},
        )
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                response_text = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                response_text = str(response.get("response", "")).strip()
    except Exception:
        response_text = ""

    extracted = _extract_json_object(response_text)
    if not extracted:
        summary_lines = [
            str(memory.get("summary", "")).strip(),
            *(str(row.get("content", "")).strip() for row in transcript[-4:]),
        ]
        fallback_summary = " ".join(line for line in summary_lines if line).strip()
        extracted = {
            "summary": fallback_summary[:900],
            "user_preferences": memory.get("user_preferences", []),
            "operator_context": memory.get("operator_context", []),
            "open_threads": memory.get("open_threads", []),
        }

    return save_orb_long_term_memory(
        {
            **memory,
            "summary": str(extracted.get("summary", "")).strip() or str(memory.get("summary", "")).strip(),
            "user_preferences": extracted.get("user_preferences", memory.get("user_preferences", [])),
            "operator_context": extracted.get("operator_context", memory.get("operator_context", [])),
            "open_threads": extracted.get("open_threads", memory.get("open_threads", [])),
            "last_summarized_message_count": message_count,
        },
        workspace_root=workspace_root,
    )


def build_orb_chat_history(
    conversation_id: str = DEFAULT_ORB_CONVERSATION_ID,
    *,
    limit: int = 24,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    session = load_orb_chat_session(conversation_id, workspace_root=workspace_root)
    memory = load_orb_long_term_memory(workspace_root=workspace_root)
    messages = session.get("messages", [])[-max(1, limit) :]
    return {
        "status": "ok",
        "conversation_id": session["conversation_id"],
        "messages": messages,
        "recent_turns": messages,
        "short_term_memory": {
            "message_count": len(session.get("messages", [])),
            "window_count": len(messages),
        },
        "thought_ids": session.get("thought_ids", []),
        "long_term_memory": memory,
    }


def get_orb_chat_history(
    *,
    conversation_id: str = DEFAULT_ORB_CONVERSATION_ID,
    limit: int = 24,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    return build_orb_chat_history(conversation_id=conversation_id, limit=limit, workspace_root=workspace_root)


def _build_execution_cards(*, plan: dict[str, Any], result: dict[str, Any]) -> list[dict[str, str]]:
    steps = plan.get("steps", []) if isinstance(plan.get("steps"), list) else []
    return [
        {
            "label": "Execution",
            "value": str(result.get("status", "unknown")).strip() or "unknown",
            "tone": "high" if str(result.get("status", "")).strip().lower() == "failed" else "medium",
        },
        {
            "label": "Plan",
            "value": str(plan.get("title", "")).strip() or str(plan.get("summary", "")).strip() or "Orb desktop plan",
            "tone": "medium",
        },
        {
            "label": "Steps",
            "value": str(len(steps)),
            "tone": "low",
        },
        {
            "label": "Mode",
            "value": str(plan.get("mode_requirement", "")).strip() or "pilot",
            "tone": "low",
        },
    ]


def record_orb_chat_execution_receipt(
    *,
    conversation_id: str,
    plan: dict[str, Any],
    execution: dict[str, Any] | None = None,
    result: dict[str, Any] | None = None,
    user_message: str = "",
    assistant_reply: str = "",
    actor: str = "electron.orb",
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    execution_payload = execution if isinstance(execution, dict) else result if isinstance(result, dict) else {}
    fs = _build_fs(workspace_root)
    ledger = _build_ledger(fs)
    conversation = build_orb_chat_history(conversation_id=conversation_id, workspace_root=workspace_root)
    if not user_message:
        for row in reversed(conversation.get("messages", [])):
            if isinstance(row, dict) and str(row.get("role", "")).strip().lower() == "user":
                user_message = str(row.get("content", "")).strip()
                if user_message:
                    break
    run_id = str(execution_payload.get("run_id", "")).strip() or f"orb-chat:{uuid4()}"
    trace_id = str(execution_payload.get("trace_id", "")).strip() or run_id
    raw_status = str(execution_payload.get("status", "completed")).strip().lower() or "completed"
    status = "completed" if raw_status == "ok" else raw_status
    plan_title = str(plan.get("title", "")).strip() or str(plan.get("summary", "")).strip() or "Orb desktop plan"
    step_count = len(plan.get("steps", [])) if isinstance(plan.get("steps"), list) else 0
    summary_text = (
        f"{plan_title} {status} through the Orb shell."
        if status != "failed"
        else f"{plan_title} failed during Orb shell execution."
    )
    detail_payload = {
        "conversation_id": _safe_conversation_id(conversation_id),
        "user_message": str(user_message or "").strip(),
        "assistant_reply": str(assistant_reply or "").strip(),
        "plan": plan if isinstance(plan, dict) else {},
        "result": execution_payload,
    }
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": f"orb.chat.execution.{status}",
        "actor": str(actor or "electron.orb").strip() or "electron.orb",
        "summary": {
            "action_kind": "orb.chat.execution",
            "summary_text": summary_text,
            "conversation_id": _safe_conversation_id(conversation_id),
            "step_count": step_count,
            "status": status,
            "presentation_cards": _build_execution_cards(plan=plan, result=execution_payload),
        },
        "detail": detail_payload,
    }
    fs.append_jsonl(LOG_PATH, receipt)
    fs.append_jsonl(DECISIONS_PATH, receipt)
    ledger.append(run_id=run_id, kind=receipt["kind"], summary=receipt["summary"])
    append_orb_turn(
        conversation_id=conversation_id,
        role="assistant",
        kind="receipt",
        content=summary_text,
        metadata={
            "run_id": run_id,
            "trace_id": trace_id,
            "status": status,
            "step_count": step_count,
        },
        workspace_root=workspace_root,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": trace_id,
        "receipt": receipt,
        "history": build_orb_chat_history(conversation_id=conversation_id, workspace_root=workspace_root),
    }
