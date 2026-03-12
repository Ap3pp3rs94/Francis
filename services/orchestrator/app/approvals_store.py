from __future__ import annotations

import json
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.approvals import requires_approval

APPROVAL_REQUESTS_PATH = "approvals/requests.jsonl"
DECISIONS_PATH = "journals/decisions.jsonl"
VALID_DECISIONS = {"approved", "rejected"}


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    rows: list[dict] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
        except Exception:
            continue
        if isinstance(parsed, dict):
            rows.append(parsed)
    return rows


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict) -> None:
    rows = _read_jsonl(fs, rel_path)
    rows.append(row)
    payload = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in rows)
    fs.write_text(rel_path, payload)


def _latest_decisions_map(fs: WorkspaceFS) -> dict[str, dict]:
    rows = _read_jsonl(fs, DECISIONS_PATH)
    latest: dict[str, dict] = {}
    for row in rows:
        if str(row.get("kind", "")).strip().lower() != "approval.decision":
            continue
        request_id = str(row.get("request_id", "")).strip()
        if not request_id:
            continue
        latest[request_id] = row
    return latest


def _materialize_status(request: dict, latest_decisions: dict[str, dict]) -> dict:
    out = dict(request)
    request_id = str(out.get("id", "")).strip()
    status = "pending"
    decision_event = None
    if request_id in latest_decisions:
        decision_event = latest_decisions[request_id]
        decision = str(decision_event.get("decision", "")).strip().lower()
        if decision in VALID_DECISIONS:
            status = decision
    out["status"] = status
    if decision_event is not None:
        out["decision_event"] = decision_event
    return out


def create_request(
    fs: WorkspaceFS,
    *,
    run_id: str,
    action: str,
    reason: str,
    requested_by: str,
    metadata: dict | None = None,
) -> dict:
    request = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "action": action,
        "reason": reason,
        "requested_by": requested_by,
        "metadata": metadata or {},
    }
    _append_jsonl(fs, APPROVAL_REQUESTS_PATH, request)
    request["status"] = "pending"
    return request


def list_requests(
    fs: WorkspaceFS,
    *,
    status: str | None = None,
    action: str | None = None,
    limit: int = 50,
) -> list[dict]:
    rows = _read_jsonl(fs, APPROVAL_REQUESTS_PATH)
    latest_decisions = _latest_decisions_map(fs)
    materialized = [_materialize_status(row, latest_decisions) for row in rows]

    filtered = materialized
    if status is not None:
        normalized = status.strip().lower()
        filtered = [row for row in filtered if str(row.get("status", "")).lower() == normalized]
    if action is not None:
        normalized_action = action.strip().lower()
        filtered = [row for row in filtered if str(row.get("action", "")).lower() == normalized_action]

    n = max(0, min(limit, 200))
    if n == 0:
        return []
    return filtered[-n:]


def get_request(fs: WorkspaceFS, approval_id: str) -> dict | None:
    rows = _read_jsonl(fs, APPROVAL_REQUESTS_PATH)
    latest_decisions = _latest_decisions_map(fs)
    for row in reversed(rows):
        if str(row.get("id", "")).strip() == approval_id:
            return _materialize_status(row, latest_decisions)
    return None


def add_decision(
    fs: WorkspaceFS,
    *,
    run_id: str,
    approval_id: str,
    decision: str,
    decided_by: str,
    note: str = "",
    metadata: dict | None = None,
) -> dict | None:
    request = get_request(fs, approval_id)
    if request is None:
        return None

    normalized_decision = decision.strip().lower()
    if normalized_decision == "approve":
        normalized_decision = "approved"
    if normalized_decision == "reject":
        normalized_decision = "rejected"
    if normalized_decision not in VALID_DECISIONS:
        raise ValueError(f"Invalid decision: {decision}")

    event = {
        "id": str(uuid4()),
        "ts": utc_now_iso(),
        "run_id": run_id,
        "kind": "approval.decision",
        "request_id": approval_id,
        "action": request.get("action"),
        "decision": normalized_decision,
        "decided_by": decided_by,
        "note": note,
    }
    normalized_metadata = metadata if isinstance(metadata, dict) else {}
    if normalized_metadata:
        event["metadata"] = normalized_metadata
        via_node = normalized_metadata.get("via_node")
        if isinstance(via_node, dict):
            event["via_node"] = via_node
    _append_jsonl(fs, DECISIONS_PATH, event)
    return event


def pending_count(fs: WorkspaceFS) -> int:
    return len(list_requests(fs, status="pending", limit=200))


def ensure_action_approved(
    fs: WorkspaceFS,
    *,
    run_id: str,
    action: str,
    requested_by: str,
    reason: str,
    approval_required: bool | None = None,
    approval_id: str | None = None,
    metadata: dict | None = None,
) -> tuple[bool, dict]:
    needs_approval = requires_approval(action) if approval_required is None else bool(approval_required)
    if not needs_approval:
        return (True, {"approval_required": False})

    if approval_id:
        existing = get_request(fs, approval_id.strip())
        if existing is None:
            return (
                False,
                {
                    "approval_required": True,
                    "approval_request_id": approval_id.strip(),
                    "reason": "approval request not found",
                },
            )
        if str(existing.get("action", "")).strip().lower() != action.strip().lower():
            return (
                False,
                {
                    "approval_required": True,
                    "approval_request_id": approval_id.strip(),
                    "reason": "approval action mismatch",
                },
            )
        if str(existing.get("status", "")).strip().lower() != "approved":
            return (
                False,
                {
                    "approval_required": True,
                    "approval_request_id": approval_id.strip(),
                    "reason": "approval not yet approved",
                },
            )
        return (True, {"approval_required": True, "approval_request_id": approval_id.strip(), "request": existing})

    created = create_request(
        fs,
        run_id=run_id,
        action=action,
        reason=reason,
        requested_by=requested_by,
        metadata=metadata,
    )
    return (
        False,
        {
            "approval_required": True,
            "approval_request_id": created["id"],
            "reason": "approval required",
        },
    )
