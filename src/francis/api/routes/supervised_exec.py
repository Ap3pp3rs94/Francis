from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from francis.agent.supervised_exec import run_supervised_exec
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate

router = APIRouter()

_SUPERVISED_EXEC_SCOPE = "codex.supervised_exec"


class SupervisedExecIn(BaseModel):
    objective: str = ""
    user_command: str
    cwd: str | None = None
    timeout_sec: int = 300
    expected_artifacts: list[str] = Field(default_factory=list)
    prechecks: list[str] = Field(default_factory=list)
    approval_id: str | None = None
    actor: str | None = None


def _permission_denied(decision: ApiPermissionDecision) -> dict[str, object]:
    return {
        "kind": "supervised_exec.result",
        "ok": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "reason": decision.reason,
            "next_step": "configure_actor_scope_or_use_governed_operation_flow",
            "evidence": decision.evidence,
        },
    }


@router.get("/supervised-exec/info")
def info() -> dict[str, object]:
    return {"ok": True, "feature": "supervised_exec", "status": "online"}


@router.post("/supervised-exec/run")
def run(payload: SupervisedExecIn) -> dict[str, object]:
    try:
        permission = ApiPermissionGate.from_env().check(
            actor_id=payload.actor,
            required_scopes=[_SUPERVISED_EXEC_SCOPE],
            route="/operations/supervised-exec/run",
            method="POST",
        )
        if not permission.allowed:
            return _permission_denied(permission)

        objective = payload.objective.strip() or "supervised_exec"
        inputs = {
            "user_command": payload.user_command,
            "cwd": payload.cwd,
            "timeout_sec": payload.timeout_sec,
            "expected_artifacts": payload.expected_artifacts,
            "prechecks": payload.prechecks,
            "approval_id": payload.approval_id,
        }
        return run_supervised_exec(inputs, objective)
    except Exception as exc:
        return {"kind": "supervised_exec.result", "ok": False, "status": "error", "error": str(exc)}
