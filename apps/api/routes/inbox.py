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


def _read_messages() -> list[dict[str, Any]]:
    ctx = RunContext(
        run_id=uuid4(),
        actor_kind=ActorKind.SYSTEM,
        actor_name="francis",
        reason="inbox.read",
    )
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


def write_system_message(*, title: str, body: str, severity: str = "info") -> dict:
    entry = {
        "id": str(uuid4()),
        "ts": _utc_now_iso(),
        "severity": severity,
        "title": title,
        "body": body,
        "source": "system",
    }

    ctx = RunContext(
        run_id=uuid4(),
        actor_kind=ActorKind.SYSTEM,
        actor_name="francis",
        reason="inbox.write_system_message",
    )

    try:
        existing = _fs.read_text(ctx, "inbox/messages.jsonl")
    except Exception:
        existing = ""

    if existing and not existing.endswith("\n"):
        existing += "\n"
    payload = existing + json.dumps(entry, ensure_ascii=False) + "\n"
    _fs.write_text(ctx, "inbox/messages.jsonl", payload)
    return entry


@router.get("/inbox")
def inbox_list() -> list[dict[str, Any]]:
    return _read_messages()


@router.post("/inbox")
def inbox_write(payload: InboxPost) -> dict:
    entry = write_system_message(title=payload.title, body=payload.body, severity=payload.severity)
    return {"status": "ok", **entry}

