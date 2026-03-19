from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_brain.ledger import RunLedger
from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

QUEUE_PATH = "orb/authority_queue.jsonl"
STATE_PATH = "orb/authority_state.json"
LOG_PATH = "logs/francis.log.jsonl"
DECISIONS_PATH = "journals/decisions.jsonl"
SUPPORTED_COMMAND_KINDS = {
    "mouse.move",
    "mouse.click",
    "keyboard.type",
    "keyboard.key",
    "keyboard.shortcut",
}
SUPPORTED_COMPLETE_STATUSES = {"completed", "failed", "released", "canceled"}
AUTHORITY_STATE_VALUES = {"human_active", "idle_armed", "francis_authority", "handback"}

_workspace_root = Path(settings.workspace_root).resolve()
_repo_root = _workspace_root.parent
_fs = WorkspaceFS(
    roots=[_workspace_root],
    journal_path=(_workspace_root / "journals" / "fs.jsonl").resolve(),
)
_ledger = RunLedger(_fs, rel_path="runs/run_ledger.jsonl")


def _read_json(rel_path: str, default: Any) -> Any:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return default
    try:
        return json.loads(raw)
    except Exception:
        return default



def _write_json(rel_path: str, value: Any) -> None:
    _fs.write_text(rel_path, json.dumps(value, ensure_ascii=False, indent=2))



def _read_jsonl(rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = _fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict[str, Any]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows



def _write_jsonl(rel_path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        _fs.write_text(rel_path, "")
        return
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    _fs.write_text(rel_path, payload)



def _append_jsonl(rel_path: str, row: dict[str, Any]) -> None:
    rows = _read_jsonl(rel_path)
    rows.append(row)
    _write_jsonl(rel_path, rows)



def _default_state() -> dict[str, Any]:
    return {
        "surface": "orb_authority",
        "state": "human_active",
        "eligible": False,
        "live": False,
        "idle_seconds": 0.0,
        "idle_threshold_seconds": 30.0,
        "claimed_command_id": "",
        "reason": "",
        "updated_at": "",
        "actor": "",
        "last_human_return_at": "",
        "last_human_return_reason": "",
        "last_release_at": "",
        "last_release_reason": "",
    }



def _load_state() -> dict[str, Any]:
    state = _read_json(STATE_PATH, _default_state())
    if not isinstance(state, dict):
        return _default_state()
    merged = _default_state()
    merged.update(state)
    merged["state"] = str(merged.get("state", "human_active")).strip().lower() or "human_active"
    if merged["state"] not in AUTHORITY_STATE_VALUES:
        merged["state"] = "human_active"
    merged["eligible"] = bool(merged.get("eligible", False))
    merged["live"] = bool(merged.get("live", False))
    merged["idle_seconds"] = max(0.0, float(merged.get("idle_seconds", 0.0) or 0.0))
    merged["idle_threshold_seconds"] = max(1.0, float(merged.get("idle_threshold_seconds", 30.0) or 30.0))
    merged["claimed_command_id"] = str(merged.get("claimed_command_id", "")).strip()
    merged["reason"] = str(merged.get("reason", "")).strip()
    merged["actor"] = str(merged.get("actor", "")).strip()
    return merged



def _save_state(state: dict[str, Any]) -> dict[str, Any]:
    normalized = _default_state()
    normalized.update(state)
    normalized["state"] = str(normalized.get("state", "human_active")).strip().lower() or "human_active"
    if normalized["state"] not in AUTHORITY_STATE_VALUES:
        normalized["state"] = "human_active"
    normalized["eligible"] = bool(normalized.get("eligible", False))
    normalized["live"] = bool(normalized.get("live", False))
    normalized["idle_seconds"] = round(max(0.0, float(normalized.get("idle_seconds", 0.0) or 0.0)), 3)
    normalized["idle_threshold_seconds"] = round(max(1.0, float(normalized.get("idle_threshold_seconds", 30.0) or 30.0)), 3)
    normalized["claimed_command_id"] = str(normalized.get("claimed_command_id", "")).strip()
    normalized["reason"] = str(normalized.get("reason", "")).strip()
    normalized["actor"] = str(normalized.get("actor", "")).strip()
    normalized["updated_at"] = str(normalized.get("updated_at") or utc_now_iso())
    _write_json(STATE_PATH, normalized)
    return normalized



def _compact_command(row: dict[str, Any]) -> dict[str, Any]:
    args = row.get("args") if isinstance(row.get("args"), dict) else {}
    return {
        "id": str(row.get("id", "")).strip(),
        "run_id": str(row.get("run_id", "")).strip(),
        "trace_id": str(row.get("trace_id", "")).strip(),
        "ts": str(row.get("ts", "")).strip(),
        "kind": str(row.get("kind", "")).strip(),
        "status": str(row.get("status", "")).strip().lower(),
        "reason": str(row.get("reason", "")).strip(),
        "actor": str(row.get("actor", "")).strip(),
        "user": str(row.get("user", "")).strip(),
        "args": args,
        "claimed_at": str(row.get("claimed_at", "")).strip(),
        "claimed_by": str(row.get("claimed_by", "")).strip(),
        "completed_at": str(row.get("completed_at", "")).strip(),
        "detail": str(row.get("detail", "")).strip(),
    }



def _command_summary(row: dict[str, Any]) -> str:
    kind = str(row.get("kind", "command")).strip() or "command"
    reason = str(row.get("reason", "")).strip()
    status = str(row.get("status", "queued")).strip().lower() or "queued"
    if reason:
        return f"{kind} is {status}. {reason}".strip()
    return f"{kind} is {status}."



def _record_receipt(*, run_id: str, trace_id: str, kind: str, summary: dict[str, Any], detail: str, actor: str) -> dict[str, Any]:
    receipt = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": trace_id,
        "kind": kind,
        "actor": actor,
        "summary": summary,
        "detail": detail,
    }
    _append_jsonl(LOG_PATH, receipt)
    _append_jsonl(DECISIONS_PATH, receipt)
    _ledger.append(run_id=run_id, kind=kind, summary={"trace_id": trace_id, **summary})
    return receipt



def get_orb_authority_view(*, recent_limit: int = 8) -> dict[str, Any]:
    rows = _read_jsonl(QUEUE_PATH)
    state = _load_state()
    pending = [_compact_command(row) for row in rows if str(row.get("status", "")).strip().lower() == "queued"]
    claimed = [_compact_command(row) for row in rows if str(row.get("status", "")).strip().lower() == "claimed"]
    recent = [_compact_command(row) for row in rows if str(row.get("status", "")).strip().lower() != "queued"]
    recent = list(reversed(recent[-max(1, recent_limit) :]))

    if state["live"]:
        summary = "Francis authority is live. The Orb may execute queued input commands until human return or panic stop."
        severity = "high"
    elif state["eligible"] and state["idle_seconds"] > 0:
        remaining = max(0.0, state["idle_threshold_seconds"] - state["idle_seconds"])
        summary = f"Away authority is armed. {remaining:.1f} seconds of collective inactivity remain before Francis may take control."
        severity = "medium"
    elif pending:
        summary = f"{len(pending)} queued Orb authority command(s) are waiting for lawful Away control."
        severity = "medium"
    else:
        summary = "No Orb authority commands are waiting. Human control remains primary."
        severity = "low"

    return {
        "surface": "orb_authority",
        "summary": summary,
        "severity": severity,
        "state": state,
        "pending_count": len(pending),
        "claimed_count": len(claimed),
        "pending": pending,
        "claimed": claimed,
        "recent": recent,
    }



def queue_orb_authority_command(*, kind: str, args: dict[str, Any] | None = None, reason: str = "", actor: str = "hud.orb", user: str = "hud.operator", trace_id: str | None = None) -> dict[str, Any]:
    normalized_kind = str(kind or "").strip().lower()
    if normalized_kind not in SUPPORTED_COMMAND_KINDS:
        raise ValueError(f"Unsupported Orb authority command: {kind}")
    normalized_args = args if isinstance(args, dict) else {}
    run_id = f"orb-authority:{uuid4()}"
    effective_trace_id = str(trace_id or run_id).strip() or run_id
    row = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "trace_id": effective_trace_id,
        "kind": normalized_kind,
        "args": normalized_args,
        "reason": str(reason or "").strip() or f"Execute {normalized_kind} through the Orb authority channel.",
        "actor": str(actor or "hud.orb").strip() or "hud.orb",
        "user": str(user or "hud.operator").strip() or "hud.operator",
        "status": "queued",
        "claimed_at": "",
        "claimed_by": "",
        "completed_at": "",
        "detail": "",
        "result": None,
    }
    _append_jsonl(QUEUE_PATH, row)
    receipt = _record_receipt(
        run_id=run_id,
        trace_id=effective_trace_id,
        kind="orb.authority.command.queued",
        summary={
            "command_id": row["id"],
            "command_kind": normalized_kind,
            "status": "queued",
            "actor": row["actor"],
        },
        detail=_command_summary(row),
        actor=row["actor"],
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "trace_id": effective_trace_id,
        "receipt_id": receipt["id"],
        "command": _compact_command(row),
        "authority": get_orb_authority_view(),
    }



def record_orb_authority_state(*, state: str, eligible: bool, live: bool, idle_seconds: float, threshold_seconds: float, claimed_command_id: str = "", reason: str = "", actor: str = "electron.orb") -> dict[str, Any]:
    normalized_state = str(state or "human_active").strip().lower() or "human_active"
    if normalized_state not in AUTHORITY_STATE_VALUES:
        raise ValueError(f"Unsupported Orb authority state: {state}")
    existing = _load_state()
    updated = {
        **existing,
        "state": normalized_state,
        "eligible": bool(eligible),
        "live": bool(live),
        "idle_seconds": idle_seconds,
        "idle_threshold_seconds": threshold_seconds,
        "claimed_command_id": str(claimed_command_id or "").strip(),
        "reason": str(reason or "").strip(),
        "actor": str(actor or "electron.orb").strip() or "electron.orb",
    }
    if normalized_state == "handback":
        updated["last_human_return_at"] = utc_now_iso()
        updated["last_human_return_reason"] = updated["reason"]
        updated["last_release_at"] = updated["last_human_return_at"]
        updated["last_release_reason"] = updated["reason"]
    elif not live and updated["reason"]:
        updated["last_release_at"] = utc_now_iso()
        updated["last_release_reason"] = updated["reason"]
    saved = _save_state(updated)
    return get_orb_authority_view() | {"state": saved}



def claim_next_orb_authority_command(*, authority_live: bool, idle_seconds: float, threshold_seconds: float, actor: str = "electron.orb") -> dict[str, Any]:
    if not authority_live:
        record_orb_authority_state(
            state="idle_armed" if idle_seconds > 0 else "human_active",
            eligible=True,
            live=False,
            idle_seconds=idle_seconds,
            threshold_seconds=threshold_seconds,
            actor=actor,
            reason="Authority gate is not live yet.",
        )
        return {
            "status": "idle",
            "command": None,
            "authority": get_orb_authority_view(),
        }

    rows = _read_jsonl(QUEUE_PATH)
    for index, row in enumerate(rows):
        if str(row.get("status", "")).strip().lower() != "queued":
            continue
        rows[index] = {
            **row,
            "status": "claimed",
            "claimed_at": utc_now_iso(),
            "claimed_by": str(actor or "electron.orb").strip() or "electron.orb",
            "detail": "Claimed by the Orb shell for local execution.",
        }
        _write_jsonl(QUEUE_PATH, rows)
        command = rows[index]
        record_orb_authority_state(
            state="francis_authority",
            eligible=True,
            live=True,
            idle_seconds=idle_seconds,
            threshold_seconds=threshold_seconds,
            claimed_command_id=str(command.get("id", "")).strip(),
            actor=actor,
            reason="Francis authority is live in Away mode.",
        )
        receipt = _record_receipt(
            run_id=str(command.get("run_id", "")).strip() or f"orb-authority:{uuid4()}",
            trace_id=str(command.get("trace_id", "")).strip() or str(command.get("run_id", "")).strip() or str(uuid4()),
            kind="orb.authority.command.claimed",
            summary={
                "command_id": str(command.get("id", "")).strip(),
                "command_kind": str(command.get("kind", "")).strip(),
                "status": "claimed",
                "actor": actor,
            },
            detail=_command_summary(command),
            actor=actor,
        )
        return {
            "status": "ok",
            "receipt_id": receipt["id"],
            "command": _compact_command(command),
            "authority": get_orb_authority_view(),
        }

    record_orb_authority_state(
        state="francis_authority",
        eligible=True,
        live=True,
        idle_seconds=idle_seconds,
        threshold_seconds=threshold_seconds,
        actor=actor,
        reason="Authority is live, but no queued Orb command is waiting.",
    )
    return {
        "status": "empty",
        "command": None,
        "authority": get_orb_authority_view(),
    }



def complete_orb_authority_command(*, command_id: str, status: str, detail: str = "", result: dict[str, Any] | None = None, actor: str = "electron.orb", human_returned: bool = False) -> dict[str, Any]:
    normalized_id = str(command_id or "").strip()
    normalized_status = str(status or "").strip().lower()
    if not normalized_id:
        raise ValueError("command_id is required")
    if normalized_status not in SUPPORTED_COMPLETE_STATUSES:
        raise ValueError(f"Unsupported Orb authority completion status: {status}")

    rows = _read_jsonl(QUEUE_PATH)
    for index, row in enumerate(rows):
        if str(row.get("id", "")).strip() != normalized_id:
            continue
        rows[index] = {
            **row,
            "status": normalized_status,
            "completed_at": utc_now_iso(),
            "detail": str(detail or "").strip() or _command_summary({**row, "status": normalized_status}),
            "result": result if isinstance(result, dict) else None,
        }
        _write_jsonl(QUEUE_PATH, rows)
        command = rows[index]
        state_reason = rows[index]["detail"]
        record_orb_authority_state(
            state="handback" if human_returned or normalized_status == "released" else "human_active" if normalized_status == "canceled" else "idle_armed",
            eligible=True,
            live=False,
            idle_seconds=0.0,
            threshold_seconds=30.0,
            claimed_command_id="",
            actor=actor,
            reason=state_reason,
        )
        receipt = _record_receipt(
            run_id=str(command.get("run_id", "")).strip() or f"orb-authority:{uuid4()}",
            trace_id=str(command.get("trace_id", "")).strip() or str(command.get("run_id", "")).strip() or str(uuid4()),
            kind=f"orb.authority.command.{normalized_status}",
            summary={
                "command_id": normalized_id,
                "command_kind": str(command.get("kind", "")).strip(),
                "status": normalized_status,
                "actor": actor,
                "human_returned": bool(human_returned),
            },
            detail=state_reason,
            actor=actor,
        )
        return {
            "status": "ok",
            "receipt_id": receipt["id"],
            "command": _compact_command(command),
            "authority": get_orb_authority_view(),
        }

    raise ValueError(f"Unknown Orb authority command: {normalized_id}")



def cancel_orb_authority_queue(*, reason: str, actor: str = "electron.orb") -> dict[str, Any]:
    rows = _read_jsonl(QUEUE_PATH)
    changed = 0
    now = utc_now_iso()
    updated_rows: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status", "")).strip().lower()
        if status in {"queued", "claimed"}:
            changed += 1
            updated_rows.append(
                {
                    **row,
                    "status": "canceled",
                    "completed_at": now,
                    "detail": str(reason or "Orb authority queue was canceled.").strip() or "Orb authority queue was canceled.",
                }
            )
        else:
            updated_rows.append(row)
    _write_jsonl(QUEUE_PATH, updated_rows)
    saved = _save_state(
        {
            **_load_state(),
            "state": "human_active",
            "live": False,
            "claimed_command_id": "",
            "reason": str(reason or "").strip() or "Orb authority queue was canceled.",
            "last_release_at": now,
            "last_release_reason": str(reason or "").strip() or "Orb authority queue was canceled.",
            "actor": actor,
        }
    )
    run_id = f"orb-authority:{uuid4()}"
    trace_id = run_id
    receipt = _record_receipt(
        run_id=run_id,
        trace_id=trace_id,
        kind="orb.authority.queue.canceled",
        summary={"canceled_count": changed, "actor": actor},
        detail=str(reason or "Orb authority queue was canceled.").strip() or "Orb authority queue was canceled.",
        actor=actor,
    )
    return {
        "status": "ok",
        "receipt_id": receipt["id"],
        "canceled_count": changed,
        "authority": get_orb_authority_view() | {"state": saved},
    }
