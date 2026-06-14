from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root
from francis.takeover import takeover_status_snapshot as stage9_takeover_status_snapshot

TAKEOVER_SESSION_SURFACE = "takeover_session_binding_v0"
_ALLOWED_MODES = {"read_only", "pilot", "takeover"}
_MAX_DURATION_SEC = 3600
_MIN_DURATION_SEC = 60


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _now_s() -> int:
    return int(time.time())


def _state_root() -> Path:
    override = os.environ.get("FRANCIS_TAKEOVER_SESSION_STATE_DIR")
    root = Path(override) if override else repo_root() / ".francis" / "takeover_session"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _proposal_dir() -> Path:
    path = _state_root() / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _receipt_dir() -> Path:
    path = _state_root() / "receipts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _clean_text(value: Any, default: str = "") -> str:
    text = str(value if value is not None else default).strip()
    return " ".join(part.strip() for part in text.splitlines() if part.strip())


def _safe_mode(value: Any) -> str:
    mode = _clean_text(value, "pilot").lower()
    if mode not in _ALLOWED_MODES:
        return "pilot"
    return mode


def _duration(value: Any) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 900
    return max(_MIN_DURATION_SEC, min(parsed, _MAX_DURATION_SEC))


def _proposal_path(proposal_id: str) -> Path:
    return _proposal_dir() / f"{proposal_id}.json"


def _receipt_path(receipt_id: str) -> Path:
    return _receipt_dir() / f"{receipt_id}.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")


def _write_receipt(kind: str, payload: dict[str, Any]) -> dict[str, Any]:
    receipt_id = f"takeover_session_{kind}_{uuid.uuid4().hex[:12]}"
    receipt = {
        "ok": True,
        "kind": f"francis.takeover_session.{kind}",
        "receipt_id": receipt_id,
        "surface": TAKEOVER_SESSION_SURFACE,
        "created_at": _utc_now(),
        "payload": payload,
        "governance": {
            "raw_input": False,
            "raw_shell": False,
            "screenshots": False,
            "pixels": False,
            "manual_approval_required_for_start": kind == "start",
            "receipt_written": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }
    path = _receipt_path(receipt_id)
    _write_json(path, receipt)
    return {"receipt_id": receipt_id, "receipt_path": str(path), "receipt": receipt}


def _session_from_stage9() -> dict[str, Any]:
    try:
        stage9 = stage9_takeover_status_snapshot(limit=5)
    except Exception as exc:  # pragma: no cover - defensive readback fallback
        return {
            "available": False,
            "status": "unavailable",
            "error": type(exc).__name__,
            "control_transfer_active": False,
            "active_session_id": "",
        }
    return {
        "available": bool(stage9.get("ok")),
        "status": _clean_text(stage9.get("status"), "unknown"),
        "control_transfer_active": bool(stage9.get("control_transfer_active")),
        "active_session_id": _clean_text(stage9.get("active_session_id")),
        "panic_stop_ready": bool(stage9.get("panic_stop_ready")),
        "handback_required": bool(stage9.get("handback_required")),
        "stage8_closed_by_receipt": bool(stage9.get("stage8_closed_by_receipt")),
        "stage8_latest_receipt_id": _clean_text(stage9.get("stage8_latest_receipt_id")),
        "next_smallest_truthful_gap": _clean_text(stage9.get("next_smallest_truthful_gap")),
    }


def takeover_status_snapshot(*, limit: int = 10) -> dict[str, Any]:
    stage9 = _session_from_stage9()
    active = bool(stage9.get("control_transfer_active"))
    return {
        "ok": True,
        "status": "active" if active else "ready",
        "surface": TAKEOVER_SESSION_SURFACE,
        "created_at": _utc_now(),
        "control_transfer_active": active,
        "active_session_id": _clean_text(stage9.get("active_session_id")),
        "mode": "pilot" if active else "read_only",
        "stage9": stage9,
        "panic_stop_ready": bool(stage9.get("panic_stop_ready")),
        "handback_required": bool(stage9.get("handback_required")),
        "recent_receipts": _recent_receipts(limit=limit),
        "governance": {
            "read_only": True,
            "takeover_never_implicit": True,
            "start_requires_manual_approval": True,
            "end_is_revocation_surface": True,
            "raw_input": False,
            "raw_shell": False,
            "screenshots": False,
            "pixels": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def propose_takeover_session(args: dict[str, Any]) -> dict[str, Any]:
    actor = _clean_text(args.get("actor"), "unknown")[:240]
    reason = _clean_text(args.get("reason"), "operator_requested_takeover_session")[:500]
    mode = _safe_mode(args.get("mode"))
    duration_sec = _duration(args.get("duration_sec"))
    scope = _clean_text(args.get("scope"), "bounded operator session")[:500]
    mission_id = _clean_text(args.get("mission_id"))[:160]
    now = _now_s()
    proposal = {
        "proposal_id": "",
        "surface": TAKEOVER_SESSION_SURFACE,
        "actor": actor,
        "reason": reason,
        "mode": mode,
        "duration_sec": duration_sec,
        "scope": scope,
        "mission_id": mission_id,
        "created_at": _utc_now(),
        "expires_at_ts": now + duration_sec,
        "requires_manual_approval": True,
        "approval_consumes_no_raw_input_authority": True,
    }
    proposal_id = hashlib.sha256(json.dumps(proposal, sort_keys=True, default=str).encode("utf-8")).hexdigest()[:16]
    proposal["proposal_id"] = proposal_id
    _write_json(_proposal_path(proposal_id), proposal)
    return {
        "ok": True,
        "status": "approval_required",
        "surface": TAKEOVER_SESSION_SURFACE,
        "proposal_id": proposal_id,
        "proposal_path": str(_proposal_path(proposal_id)),
        "approval_phrase": f"APPROVE TAKEOVER {proposal_id}",
        "requested_mode": mode,
        "duration_sec": duration_sec,
        "governance": {
            "read_only": False,
            "writes_proposal": True,
            "starts_session": False,
            "manual_approval_required": True,
            "raw_input": False,
            "raw_shell": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def start_approved_takeover_session(args: dict[str, Any]) -> dict[str, Any]:
    proposal_id = _clean_text(args.get("proposal_id"))
    approval_phrase = _clean_text(args.get("approval_phrase"))
    if not proposal_id:
        return _approval_required("", "proposal_id is required")
    expected = f"APPROVE TAKEOVER {proposal_id}"
    if approval_phrase != expected:
        return _approval_required(proposal_id, "approval phrase missing or incorrect")
    path = _proposal_path(proposal_id)
    if not path.exists():
        return {
            "ok": False,
            "status": "not_found",
            "surface": TAKEOVER_SESSION_SURFACE,
            "proposal_id": proposal_id,
            "error": "takeover session proposal not found",
            "governance": {"read_only": False, "starts_session": False, "raw_input": False, "raw_shell": False},
        }
    proposal = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(proposal, dict):
        return {
            "ok": False,
            "status": "malformed_proposal",
            "surface": TAKEOVER_SESSION_SURFACE,
            "proposal_id": proposal_id,
            "error": "takeover session proposal is malformed",
            "governance": {"read_only": False, "starts_session": False, "raw_input": False, "raw_shell": False},
        }

    if _safe_mode(proposal.get("mode")) == "read_only":
        receipt = _write_receipt("start", {"proposal": _public_proposal(proposal), "read_only_session": True})
        return {
            "ok": True,
            "status": "read_only_session_recorded",
            "surface": TAKEOVER_SESSION_SURFACE,
            "proposal_id": proposal_id,
            "session_id": "",
            "receipt_id": receipt["receipt_id"],
            "receipt_path": receipt["receipt_path"],
            "control_transfer_active": False,
            "governance": {
                "read_only": False,
                "writes_receipt": True,
                "starts_physical_input_session": False,
                "raw_input": False,
                "raw_shell": False,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
            },
        }

    from francis.takeover import record_takeover_control_transfer

    result = record_takeover_control_transfer(
        actor=proposal.get("actor", "mcp-client"),
        reason=proposal.get("reason", "approved_takeover_session"),
        scope=proposal.get("scope", "bounded operator session"),
        mission_id=proposal.get("mission_id", ""),
    )
    receipt = _write_receipt("start", {"proposal": _public_proposal(proposal), "stage9_result": result})
    return {
        "ok": bool(result.get("receipt_id")),
        "status": "active" if result.get("receipt_id") else _clean_text(result.get("status"), "blocked"),
        "surface": TAKEOVER_SESSION_SURFACE,
        "proposal_id": proposal_id,
        "session_id": _clean_text(result.get("session_id")),
        "receipt_id": receipt["receipt_id"],
        "receipt_path": receipt["receipt_path"],
        "stage9_receipt_id": _clean_text(result.get("receipt_id")),
        "control_transfer_active": bool(result.get("control_transfer_active")),
        "stage9_result": result,
        "governance": {
            "read_only": False,
            "writes_receipt": True,
            "manual_approval_consumed": True,
            "raw_input": False,
            "raw_shell": False,
            "starts_processes": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def end_takeover_session(args: dict[str, Any]) -> dict[str, Any]:
    actor = _clean_text(args.get("actor"), "mcp-client")[:240]
    reason = _clean_text(args.get("reason"), "operator_end_takeover_session")[:500]
    summary = _clean_text(args.get("summary"), "Takeover/Pilot session ended by operator request.")[:800]
    validation = _clean_text(args.get("validation_outcome"), "not_run")[:500]

    from francis.takeover import record_takeover_handback_summary

    result = record_takeover_handback_summary(
        actor=actor,
        reason=reason,
        summary=summary,
        validation_outcome=validation,
        remaining_uncertainty=_clean_text(args.get("remaining_uncertainty"), "")[:500],
        next_recommendation=_clean_text(args.get("next_recommendation"), "")[:500],
    )
    receipt = _write_receipt("end", {"stage9_result": result})
    return {
        "ok": bool(result.get("receipt_id")),
        "status": "ended" if result.get("receipt_id") else _clean_text(result.get("status"), "blocked"),
        "surface": TAKEOVER_SESSION_SURFACE,
        "session_id": _clean_text(result.get("session_id")),
        "receipt_id": receipt["receipt_id"],
        "receipt_path": receipt["receipt_path"],
        "stage9_receipt_id": _clean_text(result.get("receipt_id")),
        "control_transfer_active": False,
        "stage9_result": result,
        "governance": {
            "read_only": False,
            "writes_receipt": True,
            "revocation_surface": True,
            "raw_input": False,
            "raw_shell": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def takeover_session_receipts_readback(args: dict[str, Any]) -> dict[str, Any]:
    receipt_id = _clean_text(args.get("receipt_id"))
    if not receipt_id:
        return {
            "ok": True,
            "status": "ready",
            "surface": TAKEOVER_SESSION_SURFACE,
            "receipts": _recent_receipts(limit=20),
            "governance": {"read_only": True, "raw_input": False, "raw_shell": False},
        }
    path = _receipt_path(receipt_id)
    if not path.exists():
        return {
            "ok": False,
            "status": "not_found",
            "surface": TAKEOVER_SESSION_SURFACE,
            "receipt_id": receipt_id,
            "error": "takeover session receipt not found",
            "governance": {"read_only": True, "raw_input": False, "raw_shell": False},
        }
    return {
        "ok": True,
        "status": "ready",
        "surface": TAKEOVER_SESSION_SURFACE,
        "receipt": json.loads(path.read_text(encoding="utf-8")),
        "governance": {"read_only": True, "raw_input": False, "raw_shell": False},
    }


def _approval_required(proposal_id: str, error: str) -> dict[str, Any]:
    expected = f"APPROVE TAKEOVER {proposal_id}" if proposal_id else "APPROVE TAKEOVER <proposal_id>"
    return {
        "ok": False,
        "status": "approval_required",
        "surface": TAKEOVER_SESSION_SURFACE,
        "proposal_id": proposal_id,
        "expected_approval_phrase": expected,
        "error": error,
        "governance": {
            "read_only": False,
            "starts_session": False,
            "manual_approval_required": True,
            "raw_input": False,
            "raw_shell": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _public_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    return {
        "proposal_id": _clean_text(proposal.get("proposal_id")),
        "actor": _clean_text(proposal.get("actor"))[:240],
        "reason": _clean_text(proposal.get("reason"))[:500],
        "mode": _safe_mode(proposal.get("mode")),
        "duration_sec": _duration(proposal.get("duration_sec")),
        "mission_id": _clean_text(proposal.get("mission_id"))[:160],
        "created_at": _clean_text(proposal.get("created_at")),
    }


def _recent_receipts(*, limit: int) -> list[str]:
    receipts = sorted(_receipt_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)[:limit]
    return [item.stem for item in receipts]
