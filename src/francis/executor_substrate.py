from __future__ import annotations

from typing import Any

from francis.telemetry.status import telemetry_status_snapshot

STAGE8_EXECUTOR_SUBSTRATE_STAGE = "Stage 8 / Executor Substrate"
EXECUTOR_SUBSTRATE_STATUS_KIND = "francis.stage8.executor_substrate.status"

_STAGE7_LEDGER_CLOSURE_GAP = "stage7_ledger_closure"
_STAGE8_TOOLBELT_ALLOWLIST_GAP = "stage8_executor_toolbelt_allowlist_review"


def executor_substrate_status_snapshot() -> dict[str, Any]:
    telemetry = telemetry_status_snapshot()
    stage7_closed = telemetry.get("next_smallest_truthful_gap") == _STAGE7_LEDGER_CLOSURE_GAP
    deliverables = _deliverables(stage7_closed=stage7_closed)
    ready_count = sum(1 for item in deliverables if item["ready"])
    return {
        "ok": True,
        "kind": EXECUTOR_SUBSTRATE_STATUS_KIND,
        "stage": STAGE8_EXECUTOR_SUBSTRATE_STAGE,
        "status": "substrate_contract_ready" if stage7_closed else "awaiting_stage7_ledger_closure",
        "source_id": "executor_substrate",
        "target": "safe_bounded_execution",
        "stage7_closed_by_receipt": stage7_closed,
        "stage7_next_smallest_truthful_gap": telemetry.get("next_smallest_truthful_gap", ""),
        "deliverables": deliverables,
        "ready_count": ready_count,
        "required_count": len(deliverables),
        "stage8_done_ready": False,
        "read_only": True,
        "writes_tasks": False,
        "writes_receipts": False,
        "writes_memory": False,
        "runs_tools": False,
        "runs_shell": False,
        "runs_git": False,
        "starts_processes": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "governance": {
            "read_only": True,
            "stage8_posture_contract": True,
            "requires_stage7_ledger_closure": True,
            "uses_stage7_telemetry_receipt_readback": True,
            "does_not_execute": True,
            "does_not_write_tasks": True,
            "does_not_write_receipts": True,
            "does_not_write_memory": True,
            "does_not_grant_authority": True,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
        "next_smallest_truthful_gap": (_STAGE8_TOOLBELT_ALLOWLIST_GAP if stage7_closed else _STAGE7_LEDGER_CLOSURE_GAP),
    }


def _deliverables(*, stage7_closed: bool) -> list[dict[str, Any]]:
    return [
        {
            "id": "stage7_ledger_closure_backstop",
            "label": "Stage 7 closure backstop",
            "ready": stage7_closed,
            "evidence": {
                "required_gap": _STAGE7_LEDGER_CLOSURE_GAP,
                "source_route": "/telemetry/status",
            },
        },
        {
            "id": "execution_toolbelt_inventory",
            "label": "Execution toolbelt inventory",
            "ready": True,
            "evidence": {
                "source": "src/francis/agent/executor.py",
                "known_capabilities": [
                    "chat.summarize",
                    "plan.create",
                    "plan.revise",
                    "plugin.run",
                    "plugin.tool.run",
                    "codex.supervised_exec",
                    "git.push",
                ],
            },
        },
        {
            "id": "allowlist_policy_filters",
            "label": "Allowlist and policy filters",
            "ready": True,
            "evidence": {
                "executor_allowlist": "CAPABILITY_ALLOWLIST",
                "supervised_exec_allowed_executables": "src/francis/agent/supervised_exec.py",
                "api_permission_gate": "src/francis/governance/api_permission_gate.py",
                "mutation_authority_matrix": "src/francis/api/mutation_authority_matrix.py",
            },
        },
        {
            "id": "branch_first_workflows",
            "label": "Branch-first workflows",
            "ready": False,
            "evidence": {
                "current_surface": "git.push approval-gated capability exists",
                "missing": "branch-first workflow readback and enforcement review",
            },
        },
        {
            "id": "leases_and_idempotency",
            "label": "Leases and idempotency",
            "ready": False,
            "evidence": {
                "current_surface": "task lock files exist",
                "missing": "lease/idempotency receipt readback and retry contract",
            },
        },
        {
            "id": "verification_hooks",
            "label": "Verification hooks",
            "ready": False,
            "evidence": {
                "current_surface": "operation traces and artifacts exist",
                "missing": "executor-level verification hook contract",
            },
        },
    ]
