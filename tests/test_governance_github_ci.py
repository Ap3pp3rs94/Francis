from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def test_github_ci_delegation_receipt_gates_each_bounded_operation(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")

    from francis.governance import github_ci

    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout='{"ok": true}', stderr="")

    denied = github_ci.execute_github_ci_operation(
        actor="codex.builder",
        operation="run_list",
        payload={"branch": "main"},
        runner=runner,
    )
    assert denied["ok"] is False
    assert denied["status"] == "denied"
    assert denied["governance"]["reason"] == "operator_delegation_missing_or_inactive"
    assert calls == []

    delegation = github_ci.create_github_ci_operator_delegation_receipt()
    delegation_id = str(delegation["delegation_id"])
    receipt_path = data_root / "approvals" / "operator_delegation_receipts" / f"{delegation_id}.json"
    assert receipt_path.exists()
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["kind"] == "operator.delegation.receipt"
    assert receipt["delegating_actor"] == "Austin"
    assert receipt["receiving_actor"] == "codex.builder"
    assert receipt["granted_scope"] == [
        "github.workflow_run_monitor",
        "github.workflow_run_rerun",
        "github.workflow_dispatch_ci",
    ]
    assert receipt["expiry_policy"] == "ci_operations_until_explicit_revocation"
    assert receipt["governance"]["github_ci_operations"] is True
    assert receipt["governance"]["production_allowed"] is False
    assert receipt["governance"]["regulated_profile_allowed"] is False
    assert receipt["governance"]["subdelegation_allowed"] is False

    operations = [
        (
            "run_list",
            {"branch": "main", "limit": 5},
            ["gh", "run", "list", "--branch", "main", "--limit", "5"],
        ),
        (
            "run_view",
            {"run_id": "26611346358"},
            ["gh", "run", "view", "26611346358"],
        ),
        (
            "run_rerun_failed",
            {"run_id": "26611346358"},
            ["gh", "run", "rerun", "26611346358", "--failed"],
        ),
        (
            "workflow_dispatch_ci",
            {"workflow": "ci.yml", "ref": "main"},
            ["gh", "workflow", "run", "ci.yml", "--ref", "main"],
        ),
    ]

    for operation, payload, expected_prefix in operations:
        result = github_ci.execute_github_ci_operation(
            actor="codex.builder",
            operation=operation,
            payload=payload,
            reason=f"test_{operation}",
            runner=runner,
        )
        assert result["ok"] is True
        assert result["status"] == "completed"
        assert result["delegation_id"] == delegation_id
        assert result["authority"] == "delegated_operator"
        assert result["command"][: len(expected_prefix)] == expected_prefix
        op_receipt_path = Path(str(result["receipt_path"]))
        assert op_receipt_path.exists()
        op_receipt = json.loads(op_receipt_path.read_text(encoding="utf-8"))
        assert op_receipt["kind"] == "operator.delegated_github_ci.operation_receipt"
        assert op_receipt["actor"] == "codex.builder"
        assert op_receipt["delegation_id"] == delegation_id
        assert op_receipt["operation"] == operation
        assert op_receipt["authority"] == "delegated_operator"
        assert op_receipt["command"] == result["command"]
        assert op_receipt["shell"] is False
        assert op_receipt["governance"]["workflow_edits_allowed"] is False
        assert op_receipt["governance"]["release_publish_deploy_workflows_allowed"] is False
        assert op_receipt["governance"]["force_push_allowed"] is False

    assert len(calls) == len(operations)


def test_github_ci_delegation_blocks_production_and_non_ci_workflows(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "production")

    from francis.governance import github_ci

    github_ci.create_github_ci_operator_delegation_receipt()
    calls: list[list[str]] = []

    def runner(command: list[str], **_kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    denied_prod = github_ci.execute_github_ci_operation(
        actor="codex.builder",
        operation="run_view",
        payload={"run_id": "26611346358"},
        runner=runner,
    )
    assert denied_prod["ok"] is False
    assert denied_prod["governance"]["reason"] == "operator_delegation_missing_or_inactive"
    assert calls == []

    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "workstation")
    denied_release = github_ci.execute_github_ci_operation(
        actor="codex.builder",
        operation="workflow_dispatch_ci",
        payload={"workflow": "release.yml", "ref": "main"},
        runner=runner,
    )
    assert denied_release["ok"] is False
    assert denied_release["governance"]["reason"] == "github_ci_workflow_forbidden"
    assert calls == []
