from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir
from francis.telemetry.audit import record as audit_record

STAGE17_CAPABILITY_ECONOMY_STAGE = "Stage 17 / Capability Economy"
STAGE17_CLOSURE_DECISION_KIND = "francis.stage17.capability_economy.operator_stage_closure_decision_receipt"
STAGE17_CLOSURE_DECISIONS_KIND = "francis.stage17.capability_economy.operator_stage_closure_decision_receipts"
STAGE17_CLOSURE_WRITE_SCOPE = "plugins.stage17.closure.write"
STAGE17_CLOSURE_DECISION_GAP = "stage17_operator_stage_closure_decision"

_ALLOWED_CLOSURE_DECISIONS = {
    "close_stage17",
    "do_not_close_stage17",
    "needs_more_evidence",
}


def read_stage17_operator_stage_closure_decisions(*, limit: int = 20) -> list[dict[str, Any]]:
    return _read_jsonl_tail(_stage17_closure_decision_path(), limit=_safe_limit(limit))


def stage17_operator_stage_closure_decision_readback(*, limit: int = 20) -> dict[str, Any]:
    items = read_stage17_operator_stage_closure_decisions(limit=limit)
    latest_receipt = items[-1] if items else {}
    latest_receipt_valid = _valid_stage17_closure_receipt(latest_receipt)
    stage17_closed_by_receipt = latest_receipt_valid and bool(latest_receipt.get("stage17_closed_by_receipt"))
    return {
        "ok": True,
        "kind": STAGE17_CLOSURE_DECISIONS_KIND,
        "stage": STAGE17_CAPABILITY_ECONOMY_STAGE,
        "source_id": "capability_economy",
        "status": "closed" if stage17_closed_by_receipt else "ready" if latest_receipt else "empty",
        "items": items,
        "count": len(items),
        "latest_receipt": latest_receipt,
        "latest_receipt_id": _safe_text(latest_receipt.get("receipt_id")),
        "latest_decision": _safe_text(latest_receipt.get("decision")),
        "latest_authority": _safe_text(latest_receipt.get("authority")),
        "latest_delegation_id": _safe_text(latest_receipt.get("delegation_id")),
        "latest_recorded_ts": _safe_int(latest_receipt.get("recorded_ts")),
        "latest_review_fingerprint": _safe_text(latest_receipt.get("review_fingerprint")),
        "latest_receipt_valid": latest_receipt_valid,
        "receipt_readback_ready": bool(latest_receipt),
        "stage17_closed_by_receipt": stage17_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "reads_receipts": True,
        "writes_receipts": False,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "stage_closure_decision_receipt_readback": True,
            "validates_receipt_contract": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_write_receipts": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage17_ledger_closure" if stage17_closed_by_receipt else STAGE17_CLOSURE_DECISION_GAP
        ),
    }


def record_stage17_operator_stage_closure_decision(
    *,
    actor: Any,
    reason: Any,
    decision: Any,
    review: dict[str, Any],
    notes: Any = "",
    authority: Any = "operator",
    delegation_id: Any = "",
    delegated_operator: bool = False,
) -> dict[str, Any]:
    safe_decision = _safe_closure_decision(decision)
    closure_ready = bool(review.get("stage17_completion_review_ready"))
    safe_authority = _safe_text(authority) or "operator"
    safe_delegation_id = _safe_text(delegation_id)
    delegated_operator_approval = (
        delegated_operator and safe_authority == "delegated_operator" and bool(safe_delegation_id)
    )
    authority_ready = safe_authority == "operator" or delegated_operator_approval
    stage17_closed_by_receipt = safe_decision == "close_stage17" and closure_ready and authority_ready
    review_evidence = _review_evidence_snapshot(review)
    review_fingerprint = hashlib.sha256(
        json.dumps(review_evidence, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    receipt_id = f"stage17_capability_economy_closure_{uuid.uuid4().hex[:12]}"
    payload = {
        "ok": True,
        "kind": STAGE17_CLOSURE_DECISION_KIND,
        "receipt_id": receipt_id,
        "stage": STAGE17_CAPABILITY_ECONOMY_STAGE,
        "source_id": "capability_economy",
        "capture_mode": "explicit_operator_stage_closure_decision",
        "target": "stage17_capability_economy",
        "actor": _redacted_text(actor)[:240],
        "reason": _redacted_text(reason)[:500],
        "decision": safe_decision,
        "notes": _redacted_text(notes)[:500],
        "authority": safe_authority,
        "delegation_id": safe_delegation_id,
        "delegated_operator_approval": delegated_operator_approval,
        "review_status": _safe_text(review.get("status")),
        "completion_review_ready": closure_ready,
        "criteria_ready_count": _safe_int(review.get("criteria_ready_count")),
        "criteria_required_count": _safe_int(review.get("criteria_required_count")),
        "review_fingerprint": review_fingerprint,
        "review_evidence": review_evidence,
        "stage17_closed_by_receipt": stage17_closed_by_receipt,
        "marks_runtime_stage_state": False,
        "recorded_ts": int(time.time()),
        "writes_receipt": True,
        "writes_tasks": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "permission_scope": STAGE17_CLOSURE_WRITE_SCOPE,
            "explicit_operator_decision": True,
            "stage_closure_decision": True,
            "authority": safe_authority,
            "delegation_id": safe_delegation_id,
            "delegated_operator_authority": delegated_operator_approval,
            "completion_review_ready": closure_ready,
            "canonical_criteria_only": True,
            "does_not_mutate_runtime_stage_state": True,
            "does_not_promote_capabilities": True,
            "does_not_enable_capabilities": True,
            "does_not_execute_capabilities": True,
            "does_not_start_stage18_runtime": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (
            "stage17_ledger_closure" if stage17_closed_by_receipt else STAGE17_CLOSURE_DECISION_GAP
        ),
    }
    _append_jsonl(_stage17_closure_decision_path(), payload)
    audit_record(
        "capability_economy.stage17_closure_decision_recorded",
        actor=payload["actor"],
        reason=payload["reason"],
        receipt_id=receipt_id,
        decision=safe_decision,
        authority=safe_authority,
        delegation_id=safe_delegation_id,
        review_fingerprint=review_fingerprint,
        stage17_closed_by_receipt=stage17_closed_by_receipt,
    )
    return payload


def _review_evidence_snapshot(review: dict[str, Any]) -> dict[str, Any]:
    raw_matrix = review.get("closure_matrix")
    matrix: dict[str, Any] = raw_matrix if isinstance(raw_matrix, dict) else {}
    raw_criteria = matrix.get("criteria")
    criteria: list[Any] = raw_criteria if isinstance(raw_criteria, list) else []
    raw_source_readbacks = matrix.get("source_readbacks")
    source_readbacks: dict[str, Any] = raw_source_readbacks if isinstance(raw_source_readbacks, dict) else {}
    return {
        "contract": "stage17_capability_economy_closure_review_evidence_v1",
        "matrix_kind": _safe_text(matrix.get("kind")),
        "matrix_status": _safe_text(matrix.get("status")),
        "all_criteria_ready": bool(matrix.get("all_criteria_ready")),
        "criteria": [
            {
                "id": _safe_text(item.get("id")),
                "status": _safe_text(item.get("status")),
                "blockers": _safe_text_list(item.get("blockers")),
            }
            for item in criteria
            if isinstance(item, dict)
        ],
        "source_readbacks": source_readbacks,
    }


def _valid_stage17_closure_receipt(receipt: dict[str, Any]) -> bool:
    raw_governance = receipt.get("governance")
    governance: dict[str, Any] = raw_governance if isinstance(raw_governance, dict) else {}
    fingerprint = _safe_text(receipt.get("review_fingerprint"))
    authority = _safe_text(receipt.get("authority"))
    delegation_id = _safe_text(receipt.get("delegation_id"))
    delegated_operator_approval = bool(receipt.get("delegated_operator_approval"))
    authority_valid = authority == "operator" or (
        authority == "delegated_operator" and delegated_operator_approval and bool(delegation_id)
    )
    return (
        _safe_text(receipt.get("kind")) == STAGE17_CLOSURE_DECISION_KIND
        and bool(_safe_text(receipt.get("receipt_id")))
        and bool(_safe_text(receipt.get("actor")))
        and _safe_text(receipt.get("decision")) == "close_stage17"
        and bool(receipt.get("completion_review_ready"))
        and bool(receipt.get("stage17_closed_by_receipt"))
        and authority_valid
        and len(fingerprint) == 64
        and all(character in "0123456789abcdef" for character in fingerprint)
        and _safe_int(receipt.get("recorded_ts")) > 0
        and _safe_text(governance.get("permission_scope")) == STAGE17_CLOSURE_WRITE_SCOPE
        and bool(governance.get("explicit_operator_decision"))
        and bool(governance.get("stage_closure_decision"))
        and bool(governance.get("canonical_criteria_only"))
        and _safe_text(governance.get("authority")) == authority
        and _safe_text(governance.get("delegation_id")) == delegation_id
        and bool(governance.get("delegated_operator_authority")) == delegated_operator_approval
        and not bool(governance.get("grants_execution_authority"))
        and not bool(governance.get("grants_mutation_authority"))
    )


def _safe_closure_decision(value: Any) -> str:
    text = _safe_text(value)
    return text if text in _ALLOWED_CLOSURE_DECISIONS else "needs_more_evidence"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _safe_text_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item) for item in value if _safe_text(item)]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _safe_limit(value: Any) -> int:
    return min(max(_safe_int(value) or 20, 1), 100)


def _redacted_text(value: Any) -> str:
    return redact_secret_text(_safe_text(value))


def _stage17_closure_decision_path() -> Path:
    return data_dir() / "logs" / "plugins" / "stage17_operator_stage_closure_decisions.jsonl"


def _read_jsonl_tail(path: Path, *, limit: int) -> list[dict[str, Any]]:
    if not path.exists() or not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]:
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(item, dict):
            rows.append(item)
    return rows


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n")
