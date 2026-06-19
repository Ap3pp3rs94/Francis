from __future__ import annotations

import json
from pathlib import Path


def test_tool_call_policy_blocks_destructive_shell_command() -> None:
    from francis.governance.policy_engine import DECISION_BLOCKED, evaluate_tool_call_policy

    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "mcp_gateway",
            "tool_name": "shell.run",
            "requested_authority": "execution",
            "arguments": {"command": "rm -rf /tmp/francis"},
            "trace_id": "trace-shell-block",
        }
    )

    assert decision.ok is True
    assert decision.decision == DECISION_BLOCKED
    assert decision.policy_id == "policy.shell.destructive_command.block"
    assert decision.risk_class == "destructive_shell"
    assert decision.grants_execution_authority is False
    assert decision.grants_mutation_authority is False
    assert decision.remote_egress is False
    assert decision.read_only_decision is True
    assert decision.receipt_written is False


def test_tool_call_policy_requires_operator_for_production_deploy() -> None:
    from francis.governance.policy_engine import DECISION_REQUIRES_OPERATOR, evaluate_tool_call_policy

    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "operator_overlay",
            "tool_name": "deploy_production",
            "requested_authority": "mutation",
            "arguments": {"service": "francis-api"},
        }
    )

    assert decision.decision == DECISION_REQUIRES_OPERATOR
    assert decision.policy_id == "policy.deploy.production_change.operator_required"
    assert decision.risk_class == "deploy_production"
    assert "operator review" in decision.reason
    assert decision.grants_execution_authority is False
    assert decision.grants_mutation_authority is False


def test_tool_call_policy_requires_operator_for_unknown_mutating_tool() -> None:
    from francis.governance.policy_engine import DECISION_REQUIRES_OPERATOR, evaluate_tool_call_policy

    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "connector",
            "tool_name": "custom_vendor_tool",
            "requested_authority": "write",
            "arguments": {"operation": "change account config"},
        }
    )

    assert decision.decision == DECISION_REQUIRES_OPERATOR
    assert decision.policy_id == "policy.unknown_mutating_tool.operator_required"
    assert decision.risk_class == "unknown_mutating_tool"
    assert decision.grants_execution_authority is False
    assert decision.grants_mutation_authority is False


def test_tool_call_policy_allows_readback_status() -> None:
    from francis.governance.policy_engine import DECISION_ALLOWED, evaluate_tool_call_policy

    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "lens",
            "tool_name": "git_status",
            "requested_authority": "readback",
            "arguments": {"path": "D:/Francis"},
        }
    )

    assert decision.decision == DECISION_ALLOWED
    assert decision.policy_id == "policy.readback_or_low_risk.allow"
    assert decision.risk_class == "readback_or_low_risk"
    assert decision.grants_execution_authority is False
    assert decision.grants_mutation_authority is False
    assert decision.remote_egress is False


def test_tool_call_policy_redacts_sensitive_arguments() -> None:
    from francis.governance.policy_engine import evaluate_tool_call_policy
    from francis.governance.redaction import REDACTED_SECRET

    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "mcp_gateway",
            "tool_name": "status_probe",
            "requested_authority": "readback",
            "arguments": {"api_key": "abc123def456", "command": "echo ok"},
        }
    )

    assert decision.arguments_redacted["api_key"] == REDACTED_SECRET
    assert decision.arguments_redacted["command"] == "echo ok"
    assert "abc123def456" not in json.dumps(decision.to_dict(), sort_keys=True)


def test_tool_call_policy_writes_local_receipt_without_authority(tmp_path: Path) -> None:
    from francis.governance.policy_engine import (
        DECISION_ALLOWED,
        evaluate_tool_call_policy,
        tool_call_policy_receipts_readback,
    )

    receipt_root = tmp_path / "receipts"
    decision = evaluate_tool_call_policy(
        {
            "actor": "codex.local",
            "surface": "lens",
            "tool_name": "read_status",
            "requested_authority": "readback",
            "arguments": {"scope": "voice_bridge"},
            "trace_id": "trace-readback-receipt",
        },
        write_receipt=True,
        receipt_root=receipt_root,
    )

    assert decision.decision == DECISION_ALLOWED
    assert decision.receipt_written is True
    assert decision.receipt_id.startswith("tool-call-policy-")
    receipt_path = Path(decision.receipt_path)
    assert receipt_path.exists()
    assert receipt_path.parent == receipt_root

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "francis.governance.tool_call_policy.receipt"
    assert receipt["receipt_id"] == decision.receipt_id
    assert receipt["decision"]["decision"] == DECISION_ALLOWED
    assert receipt["decision"]["grants_execution_authority"] is False
    assert receipt["decision"]["grants_mutation_authority"] is False
    assert receipt["governance"] == {
        "decision_only": True,
        "execution_authority": False,
        "local_first": True,
        "mutation_authority_granted": False,
        "remote_egress": False,
    }

    readback = tool_call_policy_receipts_readback(limit=5, receipt_root=receipt_root)
    assert readback["ok"] is True
    assert readback["status"] == "ready"
    assert readback["receipt_count"] == 1
    assert readback["items"][0]["receipt_id"] == decision.receipt_id
    assert readback["items"][0]["tool_name"] == "read_status"
    assert readback["items"][0]["grants_execution_authority"] is False

    single = tool_call_policy_receipts_readback(receipt_id=decision.receipt_id, receipt_root=receipt_root)
    assert single["ok"] is True
    assert single["receipt"]["decision"]["tool_name"] == "read_status"
    assert single["receipt"]["governance"]["decision_only"] is True

    missing = tool_call_policy_receipts_readback(receipt_id="missing", receipt_root=receipt_root)
    assert missing["ok"] is False
    assert missing["status"] == "not_found"
