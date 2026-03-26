from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.core.config import settings
from francis.core.run_context import ActorKind, RunContext
from francis.core.workspace_fs import WorkspaceFS

router = APIRouter(tags=["inbox"])
TERMINAL_MESSAGE_STATUSES = {"archived", "resolved", "acknowledged", "superseded"}

_workspace_root = Path(settings.workspace_root).resolve()
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class InboxPost(BaseModel):
    severity: str = Field(default="info")
    title: str
    body: str


def _new_ctx(reason: str) -> RunContext:
    return RunContext(
        run_id=uuid4(),
        actor_kind=ActorKind.SYSTEM,
        actor_name="francis",
        reason=reason,
    )


def _message_status(row: dict[str, Any]) -> str:
    return str(row.get("status", row.get("state", "open"))).strip().lower() or "open"


def _is_active_message(row: dict[str, Any]) -> bool:
    return _message_status(row) not in TERMINAL_MESSAGE_STATUSES


def _normalize_message_key(value: str | None) -> str:
    return str(value or "").strip().lower()


def _read_message_rows(ctx: RunContext) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(ctx, "inbox/messages.jsonl")
    except Exception:
        return []

    out: list[dict[str, Any]] = []
    for ln in raw.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            out.append(json.loads(ln))
        except Exception:
            continue
    return out


def _write_message_rows(ctx: RunContext, rows: list[dict[str, Any]]) -> None:
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows) if rows else ""
    _fs.write_text(ctx, "inbox/messages.jsonl", payload)


def _read_messages() -> list[dict[str, Any]]:
    return [row for row in _read_message_rows(_new_ctx("inbox.read")) if _is_active_message(row)]


def write_system_message(
    *,
    title: str,
    body: str,
    severity: str = "info",
    message_key: str | None = None,
    replace_existing: bool = False,
) -> dict:
    ts = _utc_now_iso()
    normalized_key = _normalize_message_key(message_key)
    entry = {
        "id": str(uuid4()),
        "ts": ts,
        "severity": severity,
        "title": title,
        "body": body,
        "source": "system",
        "status": "open",
    }
    if normalized_key:
        entry["message_key"] = normalized_key

    ctx = _new_ctx("inbox.write_system_message")
    rows = _read_message_rows(ctx)
    if replace_existing and normalized_key:
        matching_indexes = [
            index
            for index, row in enumerate(rows)
            if _is_active_message(row)
            and str(row.get("source", "")).strip().lower() == "system"
            and _normalize_message_key(str(row.get("message_key", ""))) == normalized_key
        ]
        if matching_indexes:
            canonical_index = matching_indexes[-1]
            canonical = dict(rows[canonical_index])
            canonical["ts"] = ts
            canonical["updated_at"] = ts
            canonical["severity"] = severity
            canonical["title"] = title
            canonical["body"] = body
            canonical["source"] = "system"
            canonical["status"] = "open"
            canonical["message_key"] = normalized_key
            rows[canonical_index] = canonical

            for duplicate_index in matching_indexes[:-1]:
                duplicate = dict(rows[duplicate_index])
                duplicate["status"] = "superseded"
                duplicate["state"] = "superseded"
                duplicate["updated_at"] = ts
                duplicate["archived_at"] = ts
                duplicate["superseded_by"] = canonical["id"]
                duplicate["archived_reason"] = "message_key_replaced"
                rows[duplicate_index] = duplicate

            _write_message_rows(ctx, rows)
            return canonical

    rows.append(entry)
    _write_message_rows(ctx, rows)
    return entry


@router.get("/inbox")
def inbox_list() -> list[dict[str, Any]]:
    return _read_messages()


@router.post("/inbox")
def inbox_write(payload: InboxPost) -> dict:
    entry = write_system_message(title=payload.title, body=payload.body, severity=payload.severity)
    return {"status": "ok", **entry}
