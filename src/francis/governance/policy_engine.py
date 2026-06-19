from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_value
from francis.kernel.paths import data_dir

DECISION_ALLOWED = "allowed"
DECISION_BLOCKED = "blocked"
DECISION_REQUIRES_OPERATOR = "requires_operator"

_READ_ONLY_MARKERS = (
    "status",
    "list",
    "read",
    "get",
    "inspect",
    "diff",
    "search",
    "show",
    "logs",
    "health",
    "probe",
)
_EXECUTION_AUTHORITIES = {"execute", "execution", "mutation", "write", "shell", "deploy", "database"}
_DESTRUCTIVE_SHELL_PATTERNS = (
    re.compile(r"\brm\s+(-[a-z]*r[a-z]*f|-rf|-fr)\b", re.IGNORECASE),
    re.compile(r"\bremove-item\b(?=.*\b-recurse\b)(?=.*\b-force\b)", re.IGNORECASE),
    re.compile(r"\brmdir\b(?=.*\s/s\b)", re.IGNORECASE),
    re.compile(r"\bdel\b(?=.*\s/s\b)(?=.*\s/q\b)", re.IGNORECASE),
    re.compile(r"\bformat\s+[a-z]:", re.IGNORECASE),
    re.compile(r"\breg\s+delete\b", re.IGNORECASE),
)
_GITHUB_DELETE_MARKERS = ("github_delete_repo", "delete_repo", "repo_delete", "repository_delete")
_GITHUB_OPERATOR_MARKERS = ("force_push", "push_force", "branch_delete", "delete_branch", "secret_change")
_DATABASE_DESTRUCTIVE_MARKERS = (
    "database_drop",
    "drop_database",
    "drop_table",
    "truncate_table",
    "database_delete",
    "delete_rows",
    "migration_apply",
)
_DEPLOY_PROD_MARKERS = (
    "deploy_production",
    "production_deploy",
    "restart_production",
    "service_restart",
    "environment_change",
)
_SECRET_MUTATION_MARKERS = ("secret_update", "secret_delete", "env_write", "credential_write", "api_key_rotate")


@dataclass(frozen=True)
class ToolCallPolicyRequest:
    actor: str
    surface: str
    tool_name: str
    arguments: dict[str, Any] | None = None
    requested_authority: str = "readback"
    reason: str = ""
    trace_id: str = ""


@dataclass(frozen=True)
class ToolCallPolicyDecision:
    ok: bool
    kind: str
    status: str
    decision: str
    policy_id: str
    reason: str
    actor: str
    surface: str
    tool_name: str
    normalized_action: str
    risk_class: str
    requested_authority: str
    trace_id: str
    arguments_redacted: dict[str, Any]
    receipt_written: bool
    receipt_id: str
    receipt_path: str
    grants_execution_authority: bool
    grants_mutation_authority: bool
    remote_egress: bool
    read_only_decision: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _clean_token(value: Any) -> str:
    return re.sub(r"\s+", " ", _safe_str(value).strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _flatten_argument_text(arguments: dict[str, Any]) -> str:
    try:
        payload = json.dumps(arguments, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        payload = _safe_str(arguments)
    return payload.lower()


def _first_text_argument(arguments: dict[str, Any]) -> str:
    for key in ("command", "cmd", "script", "argv", "args", "query", "operation"):
        value = arguments.get(key)
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            return " ".join(_safe_str(item) for item in value)
        return _safe_str(value)
    return _flatten_argument_text(arguments)


def _contains_any(value: str, markers: tuple[str, ...]) -> bool:
    normalized = value.lower()
    return any(marker in normalized for marker in markers)


def _looks_like_read_only(action: str, authority: str) -> bool:
    if authority in ("", "none", "read", "readback", "inspect"):
        return True
    return _contains_any(action, _READ_ONLY_MARKERS) and authority not in _EXECUTION_AUTHORITIES


def _classify_request(request: ToolCallPolicyRequest) -> tuple[str, str, str, str]:
    arguments = _as_dict(request.arguments)
    tool = _clean_token(request.tool_name).lower()
    command = _first_text_argument(arguments).lower()
    action = " ".join(part for part in (tool, command) if part).strip()
    authority = _clean_token(request.requested_authority).lower() or "readback"

    if _contains_any(action, _GITHUB_DELETE_MARKERS):
        return (
            DECISION_BLOCKED,
            "policy.github.repository_delete.block",
            "github_repository_delete",
            "repository deletion is blocked by default before execution",
        )
    if any(pattern.search(command) for pattern in _DESTRUCTIVE_SHELL_PATTERNS):
        return (
            DECISION_BLOCKED,
            "policy.shell.destructive_command.block",
            "destructive_shell",
            "destructive shell command is blocked by default before execution",
        )
    if _contains_any(action, _DATABASE_DESTRUCTIVE_MARKERS):
        return (
            DECISION_REQUIRES_OPERATOR,
            "policy.database.destructive_change.operator_required",
            "database_destructive",
            "database destructive change requires explicit operator review",
        )
    if _contains_any(action, _DEPLOY_PROD_MARKERS):
        return (
            DECISION_REQUIRES_OPERATOR,
            "policy.deploy.production_change.operator_required",
            "deploy_production",
            "production deploy or service/environment change requires explicit operator review",
        )
    if _contains_any(action, _GITHUB_OPERATOR_MARKERS):
        return (
            DECISION_REQUIRES_OPERATOR,
            "policy.github.high_impact_change.operator_required",
            "github_high_impact",
            "high-impact GitHub mutation requires explicit operator review",
        )
    if _contains_any(action, _SECRET_MUTATION_MARKERS):
        return (
            DECISION_REQUIRES_OPERATOR,
            "policy.secrets.mutation.operator_required",
            "secret_mutation",
            "secret or credential mutation requires explicit operator review",
        )
    if authority in _EXECUTION_AUTHORITIES and not _looks_like_read_only(action, authority):
        return (
            DECISION_REQUIRES_OPERATOR,
            "policy.unknown_mutating_tool.operator_required",
            "unknown_mutating_tool",
            "unknown mutating tool call requires explicit operator review",
        )

    return (
        DECISION_ALLOWED,
        "policy.readback_or_low_risk.allow",
        "readback_or_low_risk",
        "no destructive or operator-required marker matched",
    )


def evaluate_tool_call_policy(
    request: ToolCallPolicyRequest | dict[str, Any],
    *,
    write_receipt: bool = False,
    receipt_root: Path | None = None,
) -> ToolCallPolicyDecision:
    if isinstance(request, dict):
        request = ToolCallPolicyRequest(
            actor=_clean_token(request.get("actor")),
            surface=_clean_token(request.get("surface")),
            tool_name=_clean_token(request.get("tool_name")),
            arguments=_as_dict(request.get("arguments")),
            requested_authority=_clean_token(request.get("requested_authority") or "readback"),
            reason=_clean_token(request.get("reason")),
            trace_id=_clean_token(request.get("trace_id")),
        )

    arguments = _as_dict(request.arguments)
    decision, policy_id, risk_class, reason = _classify_request(request)
    normalized_action = _clean_token(request.tool_name).lower()
    arguments_redacted = redact_governed_value(arguments)
    payload = ToolCallPolicyDecision(
        ok=True,
        kind="francis.governance.tool_call_policy_decision",
        status="decision_ready",
        decision=decision,
        policy_id=policy_id,
        reason=reason,
        actor=_clean_token(request.actor),
        surface=_clean_token(request.surface),
        tool_name=_clean_token(request.tool_name),
        normalized_action=normalized_action,
        risk_class=risk_class,
        requested_authority=_clean_token(request.requested_authority) or "readback",
        trace_id=_clean_token(request.trace_id),
        arguments_redacted=arguments_redacted,
        receipt_written=False,
        receipt_id="",
        receipt_path="",
        grants_execution_authority=False,
        grants_mutation_authority=False,
        remote_egress=False,
        read_only_decision=True,
    )

    if not write_receipt:
        return payload
    receipt = write_tool_call_policy_receipt(payload, receipt_root=receipt_root)
    return ToolCallPolicyDecision(
        **{
            **payload.to_dict(),
            "receipt_written": True,
            "receipt_id": _safe_str(receipt.get("receipt_id")),
            "receipt_path": _safe_str(receipt.get("receipt_path")),
        }
    )


def write_tool_call_policy_receipt(
    decision: ToolCallPolicyDecision,
    *,
    receipt_root: Path | None = None,
) -> dict[str, str]:
    root = receipt_root if receipt_root is not None else data_dir() / "governance" / "tool_call_policy_receipts"
    root.mkdir(parents=True, exist_ok=True)
    receipt_payload = {
        "kind": "francis.governance.tool_call_policy.receipt",
        "created_at": _utc_now(),
        "decision": decision.to_dict(),
        "governance": {
            "local_first": True,
            "remote_egress": False,
            "execution_authority": False,
            "mutation_authority_granted": False,
            "decision_only": True,
        },
    }
    digest = hashlib.sha256(
        json.dumps(receipt_payload, sort_keys=True, default=str).encode("utf-8", errors="replace")
    ).hexdigest()[:16]
    receipt_id = f"tool-call-policy-{digest}"
    path = root / f"{receipt_id}.json"
    receipt_payload["receipt_id"] = receipt_id
    path.write_text(json.dumps(receipt_payload, indent=2, sort_keys=True, ensure_ascii=False), encoding="utf-8")
    return {"receipt_id": receipt_id, "receipt_path": str(path)}
