"""Receipt-backed cross-organ handoff (takeover -> input).

Embodiment milestone #3: organs coordinate with auditable evidence. Concretely,
this makes a TAKEOVER-SESSION RECEIPT the authority that an INPUT action checks
before it may execute -- upgrading the input organ's dependency on takeover from
an ephemeral live-status snapshot to a receipt-backed binding that is bound to a
specific evidence artifact by digest and is auditable end to end.

Load-bearing, not cosmetic: `verify_input_handoff` is consumed by
`input_actuator.execute_approved_input_action` as an ADDITIONAL precondition
(strictly stricter -- the existing approval-phrase, ENABLE_REAL, and active-takeover
checks all still apply). Deleting the handoff receipt blocks the input execution.

Authority evidence = a non-read-only takeover-session `start` receipt (the operator
approved Francis to take control). A read-only session, a missing receipt, or the
wrong kind all DENY the binding. Nothing here grants execution authority itself.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.kernel.paths import data_dir
from francis.takeover_session.tools import takeover_session_receipts_readback

HANDOFF_SURFACE = "francis.handoff.v0"
_TAKEOVER_START_KIND = "francis.takeover_session.start"


def _now_s() -> int:
    return int(time.time())


def _safe_str(value: Any, default: str = "") -> str:
    return str(value if value is not None else default).strip()


def _receipt_root() -> Path:
    return data_dir() / "handoff" / "receipts"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, sort_keys=True, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _honesty() -> dict[str, Any]:
    return {
        "surface": HANDOFF_SURFACE,
        "read_only": False,
        "writes_receipt": True,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "raw_input": False,
        "raw_shell": False,
        "binds_input_to_takeover_receipt": True,
    }


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str).encode("utf-8", errors="ignore")).hexdigest()


def _valid_takeover_authority(receipt: dict[str, Any]) -> tuple[bool, str]:
    """A non-read-only takeover-session start receipt authorizes control transfer."""

    if _safe_str(receipt.get("kind")) != _TAKEOVER_START_KIND:
        return False, "takeover_receipt_not_a_session_start"
    raw_payload = receipt.get("payload")
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    if bool(payload.get("read_only_session")):
        return False, "takeover_session_read_only_no_control_transfer"
    return True, ""


def _write_receipt(payload: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    decision = _safe_str(payload.get("decision"))
    receipt_id = f"handoff-{decision}-{_digest(payload)[:16]}"
    receipt = {
        "kind": "francis.handoff.receipt",
        "receipt_id": receipt_id,
        "id": receipt_id,
        "created_ts": ts,
        "surface": HANDOFF_SURFACE,
        **payload,
        "governance": _honesty(),
    }
    path = _receipt_root() / f"{receipt_id}.json"
    _atomic_write_json(path, receipt)
    receipt["receipt_path"] = str(path)
    return receipt


def bind_input_to_takeover(
    input_proposal_id: str, takeover_receipt_id: str, *, actor: str = "unknown"
) -> dict[str, Any]:
    """Bind an input proposal to a takeover-session start receipt (the authority).

    Allows only when the takeover receipt exists and is a non-read-only session start.
    Writes a handoff receipt either way (allow with digest binding, or deny with reason).
    """

    clean_proposal = _safe_str(input_proposal_id)
    clean_receipt = _safe_str(takeover_receipt_id)
    if not clean_proposal or not clean_receipt:
        receipt = _write_receipt(
            {
                "decision": "deny",
                "input_proposal_id": clean_proposal,
                "takeover_receipt_id": clean_receipt,
                "reason": "input_proposal_id_and_takeover_receipt_id_required",
                "actor": _safe_str(actor, "unknown"),
            }
        )
        return {"ok": False, "status": "denied", "decision": "deny", "reason": receipt["reason"], "receipt": receipt}

    rb = takeover_session_receipts_readback({"receipt_id": clean_receipt})
    if not rb.get("ok") or not isinstance(rb.get("receipt"), dict):
        receipt = _write_receipt(
            {
                "decision": "deny",
                "input_proposal_id": clean_proposal,
                "takeover_receipt_id": clean_receipt,
                "reason": "takeover_receipt_not_found",
                "actor": _safe_str(actor, "unknown"),
            }
        )
        return {"ok": False, "status": "denied", "decision": "deny", "reason": receipt["reason"], "receipt": receipt}

    takeover_receipt = rb["receipt"]
    valid, reason = _valid_takeover_authority(takeover_receipt)
    if not valid:
        receipt = _write_receipt(
            {
                "decision": "deny",
                "input_proposal_id": clean_proposal,
                "takeover_receipt_id": clean_receipt,
                "reason": reason,
                "actor": _safe_str(actor, "unknown"),
            }
        )
        return {"ok": False, "status": "denied", "decision": "deny", "reason": reason, "receipt": receipt}

    raw_payload = takeover_receipt.get("payload")
    payload = raw_payload if isinstance(raw_payload, dict) else {}
    raw_stage9 = payload.get("stage9_result")
    stage9 = raw_stage9 if isinstance(raw_stage9, dict) else {}
    receipt = _write_receipt(
        {
            "decision": "allow",
            "input_proposal_id": clean_proposal,
            "takeover_receipt_id": clean_receipt,
            "takeover_receipt_digest": _digest(takeover_receipt),
            "takeover_session_id": _safe_str(stage9.get("session_id")),
            "control_transfer_active": bool(stage9.get("control_transfer_active")),
            "reason": "bound_to_takeover_session_start_receipt",
            "actor": _safe_str(actor, "unknown"),
        }
    )
    return {
        "ok": True,
        "status": "bound",
        "decision": "allow",
        "input_proposal_id": clean_proposal,
        "takeover_receipt_id": clean_receipt,
        "receipt": receipt,
    }


def _allow_bindings_for(input_proposal_id: str) -> list[dict[str, Any]]:
    root = _receipt_root()
    if not root.exists():
        return []
    out: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(rec, dict)
            and _safe_str(rec.get("decision")) == "allow"
            and _safe_str(rec.get("input_proposal_id")) == _safe_str(input_proposal_id)
        ):
            out.append(rec)
    return out


def verify_input_handoff(input_proposal_id: str) -> dict[str, Any]:
    """Consumed by the input gate: is there a valid allow-binding for this proposal?"""

    bindings = _allow_bindings_for(_safe_str(input_proposal_id))
    if not bindings:
        return {
            "authorized": False,
            "input_proposal_id": _safe_str(input_proposal_id),
            "reason": "no_takeover_handoff_binding",
        }
    newest = bindings[0]
    return {
        "authorized": True,
        "input_proposal_id": _safe_str(input_proposal_id),
        "takeover_receipt_id": _safe_str(newest.get("takeover_receipt_id")),
        "takeover_receipt_digest": _safe_str(newest.get("takeover_receipt_digest")),
        "handoff_receipt_id": _safe_str(newest.get("receipt_id")),
        "reason": "valid_takeover_handoff_binding",
    }


def handoff_receipts(limit: int = 10) -> dict[str, Any]:
    root = _receipt_root()
    safe_limit = max(1, min(int(limit or 10), 100))
    receipts: list[dict[str, Any]] = []
    if root.exists():
        for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:safe_limit]:
            try:
                receipts.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
    return {
        "ok": True,
        "status": "ready",
        "surface": HANDOFF_SURFACE,
        "count": len(receipts),
        "receipts": receipts,
        "governance": {"read_only": True, "grants_execution_authority": False},
    }


def handoff_audit(input_proposal_id: str = "", limit: int = 10) -> dict[str, Any]:
    """Read-only audit: verify one proposal's binding, or list the handoff trail."""

    if _safe_str(input_proposal_id):
        verification = verify_input_handoff(input_proposal_id)
        return {
            "ok": True,
            "status": "ready",
            "surface": HANDOFF_SURFACE,
            "verification": verification,
            "governance": {"read_only": True, "grants_execution_authority": False},
        }
    return handoff_receipts(limit=limit)


__all__ = [
    "HANDOFF_SURFACE",
    "bind_input_to_takeover",
    "verify_input_handoff",
    "handoff_receipts",
    "handoff_audit",
]
