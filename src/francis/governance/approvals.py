from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir


def approvals_dir() -> Path:
    return data_dir() / "approvals"


def pending_dir() -> Path:
    return approvals_dir() / "pending"


def approved_dir() -> Path:
    return approvals_dir() / "approved"


def rejected_dir() -> Path:
    return approvals_dir() / "rejected"


def emergency_dir() -> Path:
    return approvals_dir() / "emergency"


# Backward-compatible constants (computed at import time).
PENDING = pending_dir()
APPROVED = approved_dir()
REJECTED = rejected_dir()
EMERGENCY = emergency_dir()


def request(action: str, reason: str, payload: dict[str, Any]) -> dict[str, Any]:
    req = {
        "id": str(uuid.uuid4()),
        "ts": time.time(),
        "action": action,
        "reason": reason,
        "payload": payload,
        "status": "pending",
    }
    folder = pending_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{req['id']}.json").write_text(
        json.dumps(req, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return req


def list_requests(status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
    folder = {
        "pending": pending_dir(),
        "approved": approved_dir(),
        "rejected": rejected_dir(),
        "emergency": emergency_dir(),
    }.get(status, pending_dir())
    if not folder.exists():
        return []
    out: list[dict[str, Any]] = []
    for p in sorted(folder.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]:
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def _decision_status(action: str) -> str:
    s = (action or "").strip().lower()
    if s in {"approve", "approved"}:
        return "approved"
    if s in {"reject", "rejected", "deny", "denied"}:
        return "rejected"
    if s in {"emergency", "escalate"}:
        return "emergency"
    return ""


def decide(approval_id: str, action: str, comment: str | None = None) -> dict[str, Any]:
    status = _decision_status(action)
    if not status:
        return {"ok": False, "status": "invalid", "error": "Unsupported decision action."}

    src = pending_dir() / f"{approval_id}.json"
    if not src.exists():
        return {"ok": False, "status": "missing", "error": "Approval not found in pending queue."}

    try:
        req = json.loads(src.read_text(encoding="utf-8"))
    except Exception:
        return {"ok": False, "status": "corrupt", "error": "Approval record is unreadable."}

    req["status"] = status
    req["decision"] = action
    if comment:
        req["comment"] = comment
    req["decided_ts"] = time.time()

    dest = {
        "approved": approved_dir(),
        "rejected": rejected_dir(),
        "emergency": emergency_dir(),
    }[status]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / f"{approval_id}.json").write_text(json.dumps(req, ensure_ascii=False, indent=2), encoding="utf-8")

    try:
        src.unlink()
    except Exception:
        pass

    return {"ok": True, "status": status, "item": req}
