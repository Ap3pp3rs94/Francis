from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(repo),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def test_operations_create_list_get_cancel(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "plan.create",
            "reason": "api_operations_test",
            "input": {"goal": "verify operations API"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    listed = client.get("/operations/list")
    assert listed.status_code == 200
    listed_body = listed.json()
    assert isinstance(listed_body.get("items"), list)
    assert any(str(item.get("id")) == operation_id for item in listed_body["items"])

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id

    cancelled = client.post(f"/operations/{operation_id}/cancel", json={"reason": "test_cancel"})
    assert cancelled.status_code == 200
    cancelled_body = cancelled.json()
    assert "status" in cancelled_body
    assert cancelled_body["status"] in {"queued", "running", "failed", "canceled", "succeeded", "unknown"}


def test_operations_run_executes_plan_create(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "run_now", "input": {"goal": "run immediately"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] in {"succeeded", "failed"}

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert str(fetched_body["operation"]["id"]) == operation_id
    assert fetched_body["operation"]["status"] in {"succeeded", "failed"}


def test_operations_run_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "observe_block", "input": {"goal": "stay queued in observe"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    set_control_mode("observe", reason="test_observe_block", actor="tests")

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["ok"] is False
    assert run_body["status"] == "queued"
    assert "Observe mode keeps execution read-only." in run_body["message"]

    fetched = client.get(f"/operations/{operation_id}")
    assert fetched.status_code == 200
    fetched_body = fetched.json()
    assert fetched_body["operation"]["status"] == "queued"


def test_operations_run_once_worker_route_completes_cleanly(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is True
    assert body["exit_code"] == 0


def test_operations_run_once_worker_route_is_blocked_in_observe_mode(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.world_state.operator_mode import set_control_mode

    set_control_mode("observe", reason="test_observe_worker_block", actor="tests")

    client = TestClient(create_app())

    run_once = client.post(
        "/operations/run-once",
        json={
            "queue": "default",
            "kind": "default",
            "concurrency": 1,
            "heartbeat_s": 0.1,
            "profile": "dev",
            "run_mode": "api",
            "log_level": "INFO",
        },
    )
    assert run_once.status_code == 200
    body = run_once.json()
    assert body["ok"] is False
    assert body["exit_code"] == 1
    assert body["status"] == "blocked"
    assert "Observe mode keeps execution read-only." in body["error"]


def test_operations_export_jsonl_contains_task(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={"action": "plan.create", "reason": "export_test", "input": {"goal": "export"}},
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    exported = client.get("/operations/export?format=jsonl")
    assert exported.status_code == 200
    assert operation_id in exported.text


def test_operations_plugin_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post("/plugins/build", json={"name": "Ops Plugin", "description": "operation plugin action"})
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "queue plugin run",
            "input": {"id": plugin_id, "action": "run", "input": "hello from operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert str(output["output"]) == "Plugin response: hello from operation"


def test_operations_tool_run_action_executes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    built = client.post("/plugins/build", json={"name": "Ops Tool Plugin", "description": "operation tool action"})
    assert built.status_code == 200
    plugin_id = str(built.json()["plugin_id"])

    tools = client.get(f"/plugins/tools/list?plugin_id={plugin_id}")
    assert tools.status_code == 200
    tools_body = tools.json()
    assert isinstance(tools_body.get("items"), list)
    assert tools_body["items"]
    tool_id = str(tools_body["items"][0]["id"])

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "plugin.tool.run" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "tool.run",
            "reason": "queue tool run",
            "input": {"id": tool_id, "input": "hello from tool operation"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    run_now = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.tool"})
    assert run_now.status_code == 200
    run_body = run_now.json()
    assert run_body["status"] == "succeeded"
    output = run_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["ok"] is True
    assert output["tool_id"] == tool_id
    assert str(output["output"]) == "Plugin response: hello from tool operation"


def test_operations_governance_holds_are_visible_and_rerunnable(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/risky",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Critical deployment action.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    blocked = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert blocked.status_code == 200
    blocked_body = blocked.json()
    assert blocked_body["ok"] is True
    assert blocked_body["status"] == "blocked"
    blocked_meta = blocked_body["operation"]["meta"]
    assert blocked_meta["orb_plane"] == "P3_GOVERNANCE"
    assert blocked_meta["governance"]["gate"] == "trust_gate"
    assert blocked_meta["governance"]["next_step"] == "raise_trust_or_reduce_risk"

    raised = client.post("/trust/set", json={"level": 6, "reason": "operations-governance-test"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == approval_id
    assert task_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "status_updated" in log_names
    assert "governance_hold" in log_names

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.governance"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"

    detail_executed = client.get(f"/operations/{operation_id}")
    assert detail_executed.status_code == 200
    detail_executed_body = detail_executed.json()
    governance_holds = [item for item in detail_executed_body["logs"] if item.get("name") == "governance_hold"]
    assert len(governance_holds) >= 2


def test_operations_plugin_run_refreshes_exact_action_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    installed = client.post(
        "/plugins/install",
        json={
            "source_kind": "registry",
            "source_ref": "acme/ops-governed",
            "capabilities": [
                {
                    "id": "acme.deploy",
                    "kind": "tool",
                    "name": "deploy",
                    "action": "deploy",
                    "description": "Deploy to a target environment.",
                    "meta": {"risk_tier": "critical", "required_trust": 5},
                }
            ],
        },
    )
    assert installed.status_code == 200
    installed_body = installed.json()
    assert installed_body["ok"] is True
    plugin_id = str(installed_body["plugin_id"])

    raised = client.post("/trust/set", json={"level": 6, "reason": "operations-plugin-refresh-test"})
    assert raised.status_code == 200
    assert raised.json()["ok"] is True

    created = client.post(
        "/operations/create",
        json={
            "action": "plugin.run",
            "reason": "governed deploy refresh",
            "input": {"id": plugin_id, "action": "deploy", "input": {"target": "prod"}},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["input"] = {"target": "staging"}
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["input"]["target"] == "staging"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.plugin_refresh"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "ok"
    assert output["meta"]["action"] == "deploy"


def test_operations_git_push_requires_approval_and_pushes_branch(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    remote_root = tmp_path / "remote.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(remote_root))
    _git(repo_root, "remote", "add", "origin", str(remote_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    status = client.get("/operations/status")
    assert status.status_code == 200
    capabilities = status.json().get("capabilities") or []
    assert "git.push" in capabilities

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    pending_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert pending_inputs["approval_id"] == approval_id
    assert pending_inputs["meta"]["approval_id"] == approval_id
    log_names = [str(item.get("name")) for item in detail_pending_body["logs"]]
    assert "governance_hold" in log_names

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["branch"] == "main"
    assert output["remote"] == "origin"
    assert output["exit_code"] == 0

    remote_branch = subprocess.run(
        ["git", "--git-dir", str(remote_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert remote_branch.returncode == 0
    assert remote_branch.stdout.strip()


def test_operations_git_push_refreshes_approval_when_remote_changes(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    repo_root = tmp_path / "repo"
    origin_root = tmp_path / "origin.git"
    mirror_root = tmp_path / "mirror.git"
    repo_root.mkdir()

    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))

    _git(repo_root, "init")
    _git(repo_root, "config", "user.name", "Francis Tests")
    _git(repo_root, "config", "user.email", "francis-tests@example.com")
    _git(repo_root, "checkout", "-b", "main")
    (repo_root / "README.md").write_text("initial\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-m", "Initial commit")
    _git(repo_root, "init", "--bare", str(origin_root))
    _git(repo_root, "init", "--bare", str(mirror_root))
    _git(repo_root, "remote", "add", "origin", str(origin_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "git.push",
            "reason": "push current branch",
            "input": {"cwd": str(repo_root), "remote": "origin"},
        },
    )
    assert created.status_code == 200
    operation_id = str(created.json()["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert pending.status_code == 200
    pending_body = pending.json()
    first_approval_id = str(pending_body["operation"]["meta"]["approval_id"])
    assert first_approval_id

    approved = client.post("/approvals/decision", json={"id": first_approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    _git(repo_root, "remote", "set-url", "origin", str(mirror_root))

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != first_approval_id
    assert mismatch_output["previous_approval_id"] == first_approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    art = Path(str(mismatch_output["artifact_dir"]))
    assert (art / "request.json").exists()
    assert (art / "mismatch.json").exists()
    assert not (art / "result.json").exists()

    mirror_branch_before = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_before.returncode != 0

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.git_push"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
    assert output["remote_url"] == str(mirror_root)

    mirror_branch_after = subprocess.run(
        ["git", "--git-dir", str(mirror_root), "rev-parse", "refs/heads/main"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    assert mirror_branch_after.returncode == 0
    assert mirror_branch_after.stdout.strip()


def test_operations_supervised_exec_refreshes_stale_approval(monkeypatch, tmp_path: Path) -> None:
    data_root = tmp_path / "francis_data"
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))

    from fastapi.testclient import TestClient

    from francis.api.app import create_app
    from francis.governance import approvals

    client = TestClient(create_app())

    created = client.post(
        "/operations/create",
        json={
            "action": "supervised_exec",
            "reason": "run approved command",
            "input": {"user_command": "echo approved", "cwd": str(tmp_path)},
        },
    )
    assert created.status_code == 200
    created_body = created.json()
    assert created_body["ok"] is True
    operation_id = str(created_body["operation_id"])

    pending = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert pending.status_code == 200
    pending_body = pending.json()
    assert pending_body["ok"] is True
    assert pending_body["status"] == "queued"
    pending_meta = pending_body["operation"]["meta"]
    assert pending_meta["orb_plane"] == "P3_GOVERNANCE"
    assert pending_meta["governance"]["gate"] == "approvals_gate"
    approval_id = str(pending_meta["approval_id"])
    assert approval_id

    approved = client.post("/approvals/decision", json={"id": approval_id, "action": "approve"})
    assert approved.status_code == 200
    assert approved.json()["ok"] is True

    record_path = data_root / "tasks" / operation_id / "record.json"
    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["inputs"]["user_command"] = "echo refreshed"
    record_path.write_text(json.dumps(record, indent=2), encoding="utf-8")

    mismatched = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert mismatched.status_code == 200
    mismatched_body = mismatched.json()
    assert mismatched_body["ok"] is True
    assert mismatched_body["status"] == "queued"
    mismatch_output = mismatched_body["operation"]["output"]
    assert isinstance(mismatch_output, dict)
    assert mismatch_output["status"] == "needs_approval"
    assert mismatch_output["error"] == "approval_payload_mismatch"
    refreshed_approval_id = str(mismatch_output["approval_id"])
    assert refreshed_approval_id
    assert refreshed_approval_id != approval_id
    assert mismatch_output["previous_approval_id"] == approval_id
    mismatch_meta = mismatched_body["operation"]["meta"]
    assert mismatch_meta["orb_plane"] == "P3_GOVERNANCE"
    assert mismatch_meta["governance"]["gate"] == "approvals_gate"
    assert mismatch_meta["approval_id"] == refreshed_approval_id

    detail_pending = client.get(f"/operations/{operation_id}")
    assert detail_pending.status_code == 200
    detail_pending_body = detail_pending.json()
    task_inputs = detail_pending_body["meta"]["task"]["inputs"]
    assert task_inputs["approval_id"] == refreshed_approval_id
    assert task_inputs["meta"]["approval_id"] == refreshed_approval_id
    assert task_inputs["user_command"] == "echo refreshed"
    governance_holds = [item for item in detail_pending_body["logs"] if item.get("name") == "governance_hold"]
    assert governance_holds
    last_hold = governance_holds[-1]["output"]
    assert last_hold["approval_id"] == refreshed_approval_id
    assert last_hold["gate"] == "approvals_gate"

    refreshed_art = Path(str(mismatch_output["artifact_dir"]))
    assert (refreshed_art / "request.json").exists()
    assert (refreshed_art / "mismatch.json").exists()
    assert not (refreshed_art / "result.json").exists()

    approved_refreshed = client.post("/approvals/decision", json={"id": refreshed_approval_id, "action": "approve"})
    assert approved_refreshed.status_code == 200
    assert approved_refreshed.json()["ok"] is True

    executed = client.post(f"/operations/{operation_id}/run", json={"worker_id": "test.operations.supervised_exec"})
    assert executed.status_code == 200
    executed_body = executed.json()
    assert executed_body["ok"] is True
    assert executed_body["status"] == "succeeded"
    output = executed_body["operation"]["output"]
    assert isinstance(output, dict)
    assert output["status"] == "success"
    assert output["approval_id"] == refreshed_approval_id
