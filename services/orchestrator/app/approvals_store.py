from __future__ import annotations

from dataclasses import dataclass
import json
import threading
from typing import Any, Iterable
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_policy.approvals import requires_approval

APPROVAL_REQUESTS_PATH = "approvals/requests.jsonl"
DECISIONS_PATH = "journals/decisions.jsonl"
VALID_DECISIONS = {"approved", "rejected"}
_APPROVAL_SNAPSHOT_CACHE_LOCK = threading.Lock()
_APPROVAL_SNAPSHOT_CACHE: dict[
    str,
    tuple[tuple[str, str], ApprovalSnapshot],
] = {}


@dataclass(frozen=True, slots=True)
class ApprovalSnapshot:
    approvals: tuple[dict[str, Any], ...]
    approvals_by_id: dict[str, dict[str, Any]]
    approvals_by_action: dict[str, tuple[dict[str, Any], ...]]
    pending_count: int


def _parse_jsonl_text(raw: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
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


def _read_jsonl(fs: WorkspaceFS, rel_path: str) -> list[dict[str, Any]]:
    try:
        raw = fs.read_text(rel_path)
    except Exception:
        return []
    return _parse_jsonl_text(raw)


def _read_workspace_text(fs: WorkspaceFS, rel_path: str) -> str:
    path = (fs.roots[0] / rel_path).resolve()
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _append_jsonl(fs: WorkspaceFS, rel_path: str, row: dict[str, Any]) -> None:
    fs.append_jsonl(rel_path, row)


def _latest_decisions_map_rows(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for row in rows:
        if str(row.get("kind", "")).strip().lower() != "approval.decision":
            continue
        request_id = str(row.get("request_id", "")).strip()
        if not request_id:
            continue
        latest[request_id] = row
    return latest


def _materialize_status(
    request: dict[str, Any],
    latest_decisions: dict[str, dict[str, Any]],
) -> dict[str, Any]:
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


def _materialize_requests_rows(
    request_rows: list[dict[str, Any]],
    decision_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    latest_decisions = _latest_decisions_map_rows(decision_rows)
    return [_materialize_status(row, latest_decisions) for row in request_rows]


def _materialize_requests(fs: WorkspaceFS) -> list[dict[str, Any]]:
    rows = _read_jsonl(fs, APPROVAL_REQUESTS_PATH)
    decision_rows = _read_jsonl(fs, DECISIONS_PATH)
    latest_decisions = _latest_decisions_map_rows(decision_rows)
    return [_materialize_status(row, latest_decisions) for row in rows]


def _normalize_action(action: str | None) -> str | None:
    normalized = str(action or "").strip().lower()
    return normalized or None


def _normalize_status(status: str | None) -> str | None:
    normalized = str(status or "").strip().lower()
    return normalized or None


def load_approval_snapshot(fs: WorkspaceFS) -> ApprovalSnapshot:
    workspace_root = fs.roots[0]
    cache_key = str(workspace_root)
    raw_texts = (
        _read_workspace_text(fs, APPROVAL_REQUESTS_PATH),
        _read_workspace_text(fs, DECISIONS_PATH),
    )
    with _APPROVAL_SNAPSHOT_CACHE_LOCK:
        cached = _APPROVAL_SNAPSHOT_CACHE.get(cache_key)
        if cached is not None and cached[0] == raw_texts:
            return cached[1]
    approvals = _materialize_requests_rows(
        _parse_jsonl_text(raw_texts[0]),
        _parse_jsonl_text(raw_texts[1]),
    )
    approvals_by_id: dict[str, dict[str, Any]] = {}
    approvals_by_action_lists: dict[str, list[dict[str, Any]]] = {}
    pending_count_value = 0
    normalized_rows: list[dict[str, Any]] = []
    for row in approvals:
        normalized = dict(row)
        normalized_rows.append(normalized)
        approval_id = str(normalized.get("id", "")).strip()
        if approval_id:
            approvals_by_id[approval_id] = normalized
        action_key = _normalize_action(str(normalized.get("action", "")))
        if action_key:
            approvals_by_action_lists.setdefault(action_key, []).append(normalized)
        if _normalize_status(str(normalized.get("status", ""))) == "pending":
            pending_count_value += 1
    approvals_by_action = {key: tuple(value) for key, value in approvals_by_action_lists.items()}
    snapshot = ApprovalSnapshot(
        approvals=tuple(normalized_rows),
        approvals_by_id=approvals_by_id,
        approvals_by_action=approvals_by_action,
        pending_count=pending_count_value,
    )
    with _APPROVAL_SNAPSHOT_CACHE_LOCK:
        _APPROVAL_SNAPSHOT_CACHE[cache_key] = (raw_texts, snapshot)
    return snapshot


def find_latest_request_by_metadata(
    fs: WorkspaceFS,
    *,
    action: str | None = None,
    metadata_keys: Iterable[str],
    metadata_value: str,
    status: str | None = None,
    snapshot: ApprovalSnapshot | None = None,
    case_insensitive: bool = False,
) -> dict[str, Any] | None:
    approval_snapshot = snapshot if isinstance(snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    normalized_action = _normalize_action(action)
    normalized_status = _normalize_status(status)
    normalized_value = str(metadata_value).strip()
    if case_insensitive:
        normalized_value = normalized_value.lower()
    keys = [str(key).strip() for key in metadata_keys if str(key).strip()]
    if not keys or not normalized_value:
        return None
    rows = (
        approval_snapshot.approvals_by_action.get(normalized_action, ())
        if normalized_action is not None
        else approval_snapshot.approvals
    )
    for row in reversed(rows):
        if normalized_status is not None and _normalize_status(str(row.get("status", ""))) != normalized_status:
            continue
        metadata = row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {}
        if any(
            (
                str(metadata.get(key, "")).strip().lower()
                if case_insensitive
                else str(metadata.get(key, "")).strip()
            )
            == normalized_value
            for key in keys
        ):
            return dict(row)
    return None


def create_request(
    fs: WorkspaceFS,
    *,
    run_id: str,
    action: str,
    reason: str,
    requested_by: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
    snapshot: ApprovalSnapshot | None = None,
) -> list[dict[str, Any]]:
    n = max(0, min(limit, 200))
    if n == 0:
        return []
    approval_snapshot = snapshot if isinstance(snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    normalized_status = _normalize_status(status)
    normalized_action = _normalize_action(action)
    rows = (
        approval_snapshot.approvals_by_action.get(normalized_action, ())
        if normalized_action is not None
        else approval_snapshot.approvals
    )
    selected: list[dict[str, Any]] = []
    for row in reversed(rows):
        if normalized_status is not None and _normalize_status(str(row.get("status", ""))) != normalized_status:
            continue
        selected.append(dict(row))
        if len(selected) >= n:
            break
    selected.reverse()
    return selected


def get_request(
    fs: WorkspaceFS,
    approval_id: str,
    *,
    snapshot: ApprovalSnapshot | None = None,
) -> dict[str, Any] | None:
    approval_snapshot = snapshot if isinstance(snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    row = approval_snapshot.approvals_by_id.get(str(approval_id).strip())
    return dict(row) if isinstance(row, dict) else None


def add_decision(
    fs: WorkspaceFS,
    *,
    run_id: str,
    approval_id: str,
    decision: str,
    decided_by: str,
    note: str = "",
    metadata: dict[str, Any] | None = None,
    snapshot: ApprovalSnapshot | None = None,
) -> dict[str, Any] | None:
    request = get_request(fs, approval_id, snapshot=snapshot)
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


def pending_count(fs: WorkspaceFS, *, snapshot: ApprovalSnapshot | None = None) -> int:
    approval_snapshot = snapshot if isinstance(snapshot, ApprovalSnapshot) else load_approval_snapshot(fs)
    return approval_snapshot.pending_count


def ensure_action_approved(
    fs: WorkspaceFS,
    *,
    run_id: str,
    action: str,
    requested_by: str,
    reason: str,
    approval_required: bool | None = None,
    approval_id: str | None = None,
    metadata: dict[str, Any] | None = None,
    snapshot: ApprovalSnapshot | None = None,
) -> tuple[bool, dict]:
    needs_approval = requires_approval(action) if approval_required is None else bool(approval_required)
    if not needs_approval:
        return (True, {"approval_required": False})

    if approval_id:
        existing = get_request(fs, approval_id.strip(), snapshot=snapshot)
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
