from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _mapping(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _int(value: object) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def load_takeover_state(workspace_root: Path) -> dict[str, Any]:
    raw = _read_json(workspace_root / "control" / "takeover.json", {})
    if not isinstance(raw, Mapping):
        raw = {}

    status = _text(raw.get("status")) or "idle"
    handback = {
        "summary": _text(raw.get("handback_summary")),
        "reason": _text(raw.get("handback_reason")),
        "verification": _mapping(raw.get("handback_verification")),
        "fabric_posture": _mapping(raw.get("handback_fabric_posture")),
        "pending_approvals": _int(raw.get("handback_pending_approvals")),
        "run_id": _text(raw.get("handback_run_id")),
        "trace_id": _text(raw.get("handback_trace_id")),
        "handed_back_at": raw.get("handed_back_at"),
    }
    handback_available = any(
        [
            handback["summary"],
            handback["run_id"],
            handback["trace_id"],
            handback["handed_back_at"],
        ]
    )

    return {
        "status": status,
        "active": status == "active",
        "pending_confirmation": status == "requested",
        "session_id": _text(raw.get("session_id")),
        "last_session_id": _text(raw.get("last_session_id")),
        "objective": _text(raw.get("objective")),
        "requested_at": raw.get("requested_at"),
        "confirmed_at": raw.get("confirmed_at"),
        "handed_back_at": handback["handed_back_at"],
        "handback_available": handback_available,
        "handback": handback,
    }


def summarize_takeover_handback(
    takeover_state: Mapping[str, Any] | None,
    *,
    evidence_scope: str,
    run_id: str | None = None,
    trace_id: str | None = None,
) -> dict[str, Any]:
    takeover = takeover_state if isinstance(takeover_state, Mapping) else {}
    handback = takeover.get("handback", {})
    handback = handback if isinstance(handback, Mapping) else {}

    available = bool(takeover.get("handback_available"))
    handback_run_id = _text(handback.get("run_id"))
    handback_trace_id = _text(handback.get("trace_id"))
    normalized_run_id = _text(run_id)
    normalized_trace_id = _text(trace_id)

    scope_match = evidence_scope == "workspace"
    if normalized_run_id and handback_run_id and normalized_run_id == handback_run_id:
        scope_match = True
    if normalized_trace_id and handback_trace_id and normalized_trace_id == handback_trace_id:
        scope_match = True

    summary = {
        "available": available,
        "scope_match": scope_match,
        "status": _text(takeover.get("status")) or "idle",
        "evidence_scope": evidence_scope,
    }
    if not available:
        return summary
    if evidence_scope != "workspace" and not scope_match:
        summary["reason"] = "Latest handback belongs to a different run or trace."
        return summary

    fabric_posture = _mapping(handback.get("fabric_posture"))
    summary.update(
        {
            "handed_back_at": handback.get("handed_back_at"),
            "summary": _text(handback.get("summary")),
            "reason": _text(handback.get("reason")),
            "verification": _mapping(handback.get("verification")),
            "pending_approvals": _int(handback.get("pending_approvals")),
            "run_id": handback_run_id,
            "trace_id": handback_trace_id,
            "trust": _text(fabric_posture.get("trust")) or "Uncertain",
            "fabric_posture": fabric_posture,
        }
    )
    return summary
