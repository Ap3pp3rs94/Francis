from __future__ import annotations

import os
import re
import subprocess
import time
import uuid
from collections.abc import Callable, Sequence
from pathlib import PurePath
from typing import Any

from francis.governance import approvals
from francis.governance.redaction import redact_secret_text

GITHUB_CI_DELEGATION_SCOPES = (
    "github.workflow_run_monitor",
    "github.workflow_run_rerun",
    "github.workflow_dispatch_ci",
)
GITHUB_CI_DELEGATION_REASON = "austin_delegates_github_ci_operations"
GITHUB_CI_DELEGATION_EXPIRY_POLICY = "ci_operations_until_explicit_revocation"
GITHUB_CI_OPERATION_RECEIPT_KIND = "operator.delegated_github_ci.operation_receipt"

_SAFE_BRANCH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,191}$")
_SAFE_WORKFLOW_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,191}$")
_SAFE_RUN_ID_RE = re.compile(r"^[0-9]{1,32}$")
_DISALLOWED_WORKFLOW_MARKERS = ("deploy", "deployment", "publish", "release")
_CI_WORKFLOW_MARKERS = ("ci", "test", "check")

_DEFAULT_RUN_JSON_FIELDS = (
    "databaseId",
    "headSha",
    "status",
    "conclusion",
    "workflowName",
    "displayTitle",
    "createdAt",
    "url",
)
_DEFAULT_VIEW_JSON_FIELDS = (
    "databaseId",
    "headSha",
    "status",
    "conclusion",
    "workflowName",
    "displayTitle",
    "createdAt",
    "updatedAt",
    "jobs",
    "url",
)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _current_env_profile() -> str:
    return _safe_str(os.getenv("FRANCIS_ENV_PROFILE")).strip().lower()


def _receipt_dir() -> Any:
    return approvals.approvals_dir() / "github_ci_operation_receipts"


def _write_receipt(payload: dict[str, Any]) -> str:
    receipt_id = _safe_str(payload.get("receipt_id")).strip()
    path = _receipt_dir() / f"{receipt_id}.json"
    approvals._write_json(path, payload)  # noqa: SLF001 - approval receipts share this local writer.
    return str(path)


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return min(max(parsed, minimum), maximum)


def _safe_branch(value: Any) -> str:
    branch = _safe_str(value).strip() or "main"
    if not _SAFE_BRANCH_RE.fullmatch(branch) or ".." in branch or branch.startswith(("-", "/", ".")):
        raise ValueError("github_ci_branch_not_allowed")
    return branch


def _safe_run_id(value: Any) -> str:
    run_id = _safe_str(value).strip()
    if not _SAFE_RUN_ID_RE.fullmatch(run_id):
        raise ValueError("github_ci_run_id_not_allowed")
    return run_id


def _safe_workflow(value: Any) -> str:
    workflow = _safe_str(value).strip()
    normalized = workflow.replace("\\", "/")
    if not workflow or not _SAFE_WORKFLOW_RE.fullmatch(normalized):
        raise ValueError("github_ci_workflow_not_allowed")
    if ".." in PurePath(normalized).parts or normalized.startswith(("-", "/", ".")):
        raise ValueError("github_ci_workflow_not_allowed")
    lowered = normalized.lower()
    if any(marker in lowered for marker in _DISALLOWED_WORKFLOW_MARKERS):
        raise ValueError("github_ci_workflow_forbidden")
    if not any(marker in lowered for marker in _CI_WORKFLOW_MARKERS):
        raise ValueError("github_ci_workflow_must_be_ci_only")
    return normalized


def _csv_fields(fields: Sequence[str]) -> str:
    return ",".join(field for field in fields if field)


def create_github_ci_operator_delegation_receipt(
    *,
    delegating_actor: str = "Austin",
    receiving_actor: str = approvals.BUILDER_APPROVAL_ACTOR,
    delegation_id: str | None = None,
) -> dict[str, Any]:
    return approvals.create_operator_delegation_receipt(
        delegating_actor=delegating_actor,
        receiving_actor=receiving_actor,
        granted_scope=list(GITHUB_CI_DELEGATION_SCOPES),
        reason=GITHUB_CI_DELEGATION_REASON,
        expiry_policy=GITHUB_CI_DELEGATION_EXPIRY_POLICY,
        delegation_id=delegation_id,
        governance_overrides={
            "operator_decision_record": True,
            "delegated_operator_authority": True,
            "github_ci_operations": True,
            "workflow_run_monitor": True,
            "workflow_run_rerun": True,
            "workflow_dispatch_ci": True,
            "subdelegation_allowed": False,
            "production_allowed": False,
            "regulated_profile_allowed": False,
            "workflow_edits_allowed": False,
            "release_publish_deploy_workflows_allowed": False,
            "cancel_foreign_runs_allowed": False,
            "force_push_allowed": False,
            "branch_protection_mutation_allowed": False,
        },
    )


def _operation_scope(operation: str) -> str:
    if operation in {"run_list", "run_view"}:
        return "github.workflow_run_monitor"
    if operation == "run_rerun_failed":
        return "github.workflow_run_rerun"
    if operation == "workflow_dispatch_ci":
        return "github.workflow_dispatch_ci"
    return ""


def _build_command(operation: str, payload: dict[str, Any]) -> list[str]:
    if operation == "run_list":
        branch = _safe_branch(payload.get("branch"))
        limit = _bounded_int(payload.get("limit"), default=5, minimum=1, maximum=50)
        return [
            "gh",
            "run",
            "list",
            "--branch",
            branch,
            "--limit",
            str(limit),
            "--json",
            _csv_fields(_DEFAULT_RUN_JSON_FIELDS),
        ]
    if operation == "run_view":
        run_id = _safe_run_id(payload.get("run_id"))
        return ["gh", "run", "view", run_id, "--json", _csv_fields(_DEFAULT_VIEW_JSON_FIELDS)]
    if operation == "run_rerun_failed":
        run_id = _safe_run_id(payload.get("run_id"))
        return ["gh", "run", "rerun", run_id, "--failed"]
    if operation == "workflow_dispatch_ci":
        workflow = _safe_workflow(payload.get("workflow"))
        ref = _safe_branch(payload.get("ref"))
        return ["gh", "workflow", "run", workflow, "--ref", ref]
    raise ValueError("github_ci_operation_not_allowed")


def _denied(reason: str, *, profile: str, operation: str = "") -> dict[str, Any]:
    return {
        "ok": False,
        "status": "denied",
        "error": "github_ci_operation_denied",
        "operation": operation,
        "governance": {
            "gate": "github_ci_operator_delegation",
            "reason": reason,
            "actor": approvals.BUILDER_APPROVAL_ACTOR,
            "env_profile": profile,
            "required_delegation_scope": list(GITHUB_CI_DELEGATION_SCOPES),
            "authority_granted": False,
            "production_allowed": False,
            "regulated_profile_allowed": False,
            "subdelegation_allowed": False,
        },
    }


def execute_github_ci_operation(
    *,
    actor: str,
    operation: str,
    payload: dict[str, Any] | None = None,
    reason: str = "github_ci_operation",
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    timeout_sec: int = 120,
) -> dict[str, Any]:
    clean_actor = _safe_str(actor).strip()
    clean_operation = _safe_str(operation).strip()
    profile = _current_env_profile()
    if clean_actor != approvals.BUILDER_APPROVAL_ACTOR:
        return _denied("actor_not_builder", profile=profile, operation=clean_operation)

    required_scope = _operation_scope(clean_operation)
    if not required_scope:
        return _denied("operation_not_allowed", profile=profile, operation=clean_operation)

    delegation = approvals.active_operator_delegation_for(
        receiving_actor=clean_actor,
        required_scopes=[required_scope],
        profile=profile,
    )
    if delegation is None:
        return _denied("operator_delegation_missing_or_inactive", profile=profile, operation=clean_operation)

    try:
        command = _build_command(clean_operation, payload or {})
    except ValueError as exc:
        return _denied(_safe_str(exc), profile=profile, operation=clean_operation)

    started = time.time()
    completed = runner(
        command,
        shell=False,
        capture_output=True,
        text=True,
        timeout=_bounded_int(timeout_sec, default=120, minimum=5, maximum=600),
    )
    finished = time.time()
    receipt_id = f"ghci_{uuid.uuid4().hex[:16]}"
    delegation_id = _safe_str(delegation.get("delegation_id")).strip()
    receipt = {
        "kind": GITHUB_CI_OPERATION_RECEIPT_KIND,
        "receipt_id": receipt_id,
        "actor": clean_actor,
        "delegation_id": delegation_id,
        "delegating_actor": approvals._redact_free_text(delegation.get("delegating_actor")),  # noqa: SLF001
        "receiving_actor": clean_actor,
        "authority": approvals.DELEGATED_OPERATOR_AUTHORITY,
        "operation": clean_operation,
        "decision": "approved",
        "reason": approvals._redact_free_text(reason),  # noqa: SLF001
        "ts": started,
        "completed_ts": finished,
        "env_profile": profile,
        "command": command,
        "shell": False,
        "exit_code": int(completed.returncode),
        "stdout_preview": redact_secret_text(_safe_str(completed.stdout))[:2000],
        "stderr_preview": redact_secret_text(_safe_str(completed.stderr))[:2000],
        "governance": {
            "operator_delegation_required": True,
            "operator_decision_recorded": True,
            "delegation_id": delegation_id,
            "required_scope": [required_scope],
            "allowed_scope": list(GITHUB_CI_DELEGATION_SCOPES),
            "allowed_operations": [
                "run_list",
                "run_view",
                "run_rerun_failed",
                "workflow_dispatch_ci",
            ],
            "dev_or_workstation_only": True,
            "production_allowed": False,
            "regulated_profile_allowed": False,
            "subdelegation_allowed": False,
            "workflow_edits_allowed": False,
            "release_publish_deploy_workflows_allowed": False,
            "cancel_foreign_runs_allowed": False,
            "force_push_allowed": False,
            "branch_protection_mutation_allowed": False,
        },
    }
    receipt_path = _write_receipt(receipt)
    receipt["receipt_path"] = receipt_path
    _write_receipt(receipt)
    return {
        "ok": completed.returncode == 0,
        "status": "completed" if completed.returncode == 0 else "failed",
        "kind": "operator.delegated_github_ci.operation_result",
        "operation": clean_operation,
        "actor": clean_actor,
        "delegation_id": delegation_id,
        "authority": approvals.DELEGATED_OPERATOR_AUTHORITY,
        "command": command,
        "exit_code": int(completed.returncode),
        "receipt_id": receipt_id,
        "receipt_path": receipt_path,
    }
