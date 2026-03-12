from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi.testclient import TestClient

from services.orchestrator.app.lens_operator import execute_lens_action
from services.orchestrator.app.swarm_store import (
    DEFAULT_LEASE_TTL_SECONDS,
    complete_delegation,
    fail_delegation,
    get_delegation,
    lease_delegation,
    list_delegations,
)

LOCAL_SWARM_ACTIONS: dict[str, set[str]] = {
    "planner": {"mission.tick"},
    "repo_operator": {"repo.status", "repo.diff", "repo.lint", "repo.tests"},
    "verifier": {"verify.receipts"},
}


def supports_swarm_execution(unit_id: str, action_kind: str) -> bool:
    normalized_unit = str(unit_id or "").strip().lower()
    normalized_action = str(action_kind or "").strip().lower()
    return normalized_action in LOCAL_SWARM_ACTIONS.get(normalized_unit, set())


def list_due_swarm_delegations(
    fs,
    *,
    target_unit_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return list_delegations(
        fs,
        statuses={"queued"},
        due_only=True,
        target_unit_id=target_unit_id,
        limit=limit,
    )


def _get_orchestrator_app():
    from apps.api.main import app as orchestrator_app

    return orchestrator_app


def _http_detail(exc: HTTPException) -> str:
    detail = exc.detail
    if isinstance(detail, dict):
        message = detail.get("message")
        if message:
            return str(message)
        return str(detail)
    return str(detail)


def _summarize_lens_execution(action_kind: str, payload: dict[str, Any]) -> str:
    execution = payload.get("execution", {}) if isinstance(payload.get("execution"), dict) else {}
    result = execution.get("result", {}) if isinstance(execution.get("result"), dict) else {}
    presentation = result.get("presentation", {}) if isinstance(result.get("presentation"), dict) else {}
    summary = str(presentation.get("summary", "")).strip() or str(result.get("summary", "")).strip()
    if summary:
        return summary
    return f"{action_kind} completed under Swarm control."


def _execute_receipt_verification(
    *,
    role: str,
    user: str,
    trace_id: str,
    delegation: dict[str, Any],
) -> dict[str, Any]:
    origin_run_id = str(delegation.get("run_id", "")).strip()
    headers = {
        "x-francis-role": str(role or "architect").strip().lower() or "architect",
        "x-francis-user": str(user or "swarm.verifier").strip() or "swarm.verifier",
        "x-trace-id": trace_id,
    }
    with TestClient(_get_orchestrator_app()) as client:
        if origin_run_id:
            response = client.get(f"/runs/{origin_run_id}", params={"limit": 25}, headers=headers)
        else:
            response = client.get("/receipts/latest", params={"limit": 25}, headers=headers)
    body = response.json() if response.headers.get("content-type", "").startswith("application/json") else {"detail": response.text}
    if response.status_code >= 400:
        raise HTTPException(status_code=response.status_code, detail=body.get("detail", body))
    summary = body.get("summary", {}) if isinstance(body.get("summary"), dict) else {}
    counts = summary.get("counts", {}) if isinstance(summary.get("counts"), dict) else {}
    fabric = summary.get("fabric", {}) if isinstance(summary.get("fabric"), dict) else {}
    ledger_count = int(counts.get("ledger", 0) or 0)
    decision_count = int(counts.get("decisions", 0) or 0)
    artifact_count = int(fabric.get("artifact_count", 0) or 0)
    result_summary = (
        f"Verifier checked {ledger_count} ledger receipt(s), "
        f"{decision_count} decision record(s), and {artifact_count} fabric artifact(s)."
    )
    return {
        "executor": "receipts.verify",
        "execution_run_id": origin_run_id or None,
        "execution_trace_id": trace_id,
        "result_summary": result_summary,
        "detail": body,
    }


def _execute_supported_delegation(
    *,
    role: str,
    user: str,
    trace_id: str,
    delegation: dict[str, Any],
) -> dict[str, Any]:
    unit_id = str(delegation.get("target_unit_id", "")).strip().lower()
    action_kind = str(delegation.get("action_kind", "")).strip().lower()
    action_args = delegation.get("action_args", {}) if isinstance(delegation.get("action_args"), dict) else {}

    if unit_id in {"planner", "repo_operator"} and action_kind in LOCAL_SWARM_ACTIONS.get(unit_id, set()):
        payload = execute_lens_action(
            kind=action_kind,
            args=action_args,
            dry_run=False,
            role=role,
            user=user,
            trace_id=trace_id,
        )
        execution = payload.get("execution", {}) if isinstance(payload.get("execution"), dict) else {}
        return {
            "executor": "lens",
            "execution_run_id": str(execution.get("run_id", "")).strip() or None,
            "execution_trace_id": str(execution.get("trace_id", "")).strip() or trace_id,
            "result_summary": _summarize_lens_execution(action_kind, payload),
            "detail": execution,
        }

    if unit_id == "verifier" and action_kind == "verify.receipts":
        return _execute_receipt_verification(role=role, user=user, trace_id=trace_id, delegation=delegation)

    raise ValueError(f"Swarm execution is not supported for unit={unit_id} action={action_kind}")


def execute_swarm_delegation(
    fs,
    *,
    repo_root,
    workspace_root,
    delegation_id: str,
    role: str,
    user: str,
    trace_id: str,
    lease_ttl_seconds: int = DEFAULT_LEASE_TTL_SECONDS,
) -> dict[str, Any]:
    delegation = get_delegation(fs, delegation_id)
    if delegation is None:
        raise LookupError(f"Delegation not found: {delegation_id}")

    status = str(delegation.get("status", "")).strip().lower()
    unit_id = str(delegation.get("target_unit_id", "")).strip().lower()
    leased = False
    working = delegation

    if status == "queued":
        leased_row = lease_delegation(
            fs,
            repo_root=repo_root,
            workspace_root=workspace_root,
            delegation_id=delegation_id,
            unit_id=unit_id,
            lease_owner=f"swarm:{unit_id}",
            lease_ttl_seconds=lease_ttl_seconds,
        )
        if leased_row is None:
            raise LookupError(f"Delegation not found: {delegation_id}")
        working = leased_row
        leased = True
    elif status != "leased":
        raise ValueError(f"Delegation {delegation_id} cannot execute from status {status or 'unknown'}")

    swarm_user = str(user or f"swarm.{unit_id}").strip() or f"swarm.{unit_id}"
    try:
        execution = _execute_supported_delegation(
            role=role,
            user=swarm_user,
            trace_id=trace_id,
            delegation=working,
        )
    except ValueError as exc:
        failed = fail_delegation(
            fs,
            repo_root=repo_root,
            workspace_root=workspace_root,
            delegation_id=delegation_id,
            failed_by_unit_id=unit_id,
            error=str(exc),
            retryable=False,
        )
        return {
            "status": "error",
            "leased": leased,
            "leased_delegation": working if leased else None,
            "delegation": failed,
            "error": str(exc),
            "retryable": False,
            "execution": None,
        }
    except HTTPException as exc:
        retryable = exc.status_code in {403, 409, 429} or exc.status_code >= 500
        failed = fail_delegation(
            fs,
            repo_root=repo_root,
            workspace_root=workspace_root,
            delegation_id=delegation_id,
            failed_by_unit_id=unit_id,
            error=_http_detail(exc),
            retryable=retryable,
            retry_backoff_seconds=0,
        )
        return {
            "status": "error",
            "leased": leased,
            "leased_delegation": working if leased else None,
            "delegation": failed,
            "error": _http_detail(exc),
            "retryable": retryable,
            "execution": {"status_code": exc.status_code, "detail": exc.detail},
        }
    except Exception as exc:
        failed = fail_delegation(
            fs,
            repo_root=repo_root,
            workspace_root=workspace_root,
            delegation_id=delegation_id,
            failed_by_unit_id=unit_id,
            error=str(exc),
            retryable=True,
            retry_backoff_seconds=0,
        )
        return {
            "status": "error",
            "leased": leased,
            "leased_delegation": working if leased else None,
            "delegation": failed,
            "error": str(exc),
            "retryable": True,
            "execution": None,
        }

    completed = complete_delegation(
        fs,
        repo_root=repo_root,
        workspace_root=workspace_root,
        delegation_id=delegation_id,
        completed_by_unit_id=unit_id,
        result_summary=str(execution.get("result_summary", "")).strip() or f"{working.get('action_kind', 'task')} completed.",
    )
    return {
        "status": "ok",
        "leased": leased,
        "leased_delegation": working if leased else None,
        "delegation": completed,
        "execution": execution,
        "retryable": False,
        "error": "",
    }


def run_swarm_cycle(
    fs,
    *,
    repo_root,
    workspace_root,
    role: str,
    user: str,
    trace_id: str,
    limit: int = 3,
    target_unit_id: str | None = None,
) -> dict[str, Any]:
    due_rows = list_due_swarm_delegations(fs, target_unit_id=target_unit_id, limit=limit)
    items: list[dict[str, Any]] = []
    completed_count = 0
    error_count = 0
    for row in due_rows:
        delegation_id = str(row.get("id", "")).strip()
        if not delegation_id:
            continue
        result = execute_swarm_delegation(
            fs,
            repo_root=repo_root,
            workspace_root=workspace_root,
            delegation_id=delegation_id,
            role=role,
            user=user,
            trace_id=trace_id,
        )
        items.append(result)
        if str(result.get("status", "")).strip().lower() == "ok":
            completed_count += 1
        else:
            error_count += 1
    return {
        "status": "ok",
        "processed_count": len(items),
        "completed_count": completed_count,
        "error_count": error_count,
        "items": items,
    }
