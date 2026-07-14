from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        pytest.skip("PowerShell is not available")
    return executable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _client(monkeypatch, tmp_path: Path):
    repo_root = tmp_path / "api-repo"
    data_root = tmp_path / "data"
    repo_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("FRANCIS_ROOT", str(repo_root))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(data_root))
    monkeypatch.setenv("FRANCIS_ENV_PROFILE", "dev")
    monkeypatch.setenv("FRANCIS_RUN_MODE", "api")

    from fastapi.testclient import TestClient

    from francis.api.app import create_app

    return TestClient(create_app()), data_root


def _approved_enablement(client) -> dict[str, object]:  # type: ignore[no-untyped-def]
    capture_request = client.post(
        "/lens/perception/authority/request",
        json={"actor": "test.system.write", "reason": "request host worker capture authority"},
    ).json()
    capture_approval_id = capture_request["approval_id"]
    assert (
        client.post(
            "/approvals/decision",
            json={
                "id": capture_approval_id,
                "action": "approve",
                "actor": "test.approvals.decision",
                "comment": "approve host worker capture authority",
            },
        ).json()["status"]
        == "approved"
    )
    capture_grant = client.post(
        "/lens/perception/authority",
        json={
            "actor": "test.system.write",
            "approval_id": capture_approval_id,
            "reason": "grant host worker capture authority",
            "lease_seconds": 120,
        },
    ).json()
    authority_receipt_id = capture_grant["receipt"]["receipt_id"]

    execution_request = client.post(
        "/lens/perception/execution/request",
        json={
            "actor": "test.system.write",
            "authority_receipt_id": authority_receipt_id,
            "reason": "request host-owned perception worker execution",
        },
    ).json()
    execution_approval_id = execution_request["approval_id"]
    assert (
        client.post(
            "/approvals/decision",
            json={
                "id": execution_approval_id,
                "action": "approve",
                "actor": "test.approvals.decision",
                "comment": "approve host-owned perception worker execution",
            },
        ).json()["status"]
        == "approved"
    )
    enabled = client.post(
        "/lens/perception/execution/enable",
        json={
            "actor": "test.system.write",
            "approval_id": execution_approval_id,
            "authority_receipt_id": authority_receipt_id,
            "reason": "enable host-owned perception worker handoff",
        },
    ).json()
    assert enabled["status"] == "enabled_for_host_consumption"
    return enabled


def _run_resident_host(data_root: Path, *, run_seconds: int) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["FRANCIS_DATA_DIR"] = str(data_root)
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host.ps1"),
            "-Mode",
            "Resident",
            "-RunSeconds",
            str(run_seconds),
        ],
        cwd=_repo_root(),
        env=environment,
        check=False,
        text=True,
        capture_output=True,
        timeout=45,
    )


def test_resident_host_passes_and_restores_game_observer_runtime_config() -> None:
    script = (_repo_root() / "scripts" / "lens-host.ps1").read_text(encoding="utf-8-sig")

    assert "$GameObserverConfigPath = if ([string]::IsNullOrWhiteSpace($PreviousGameObserverConfig))" in script
    assert "[System.IO.Path]::Combine($RepoRoot, 'config', 'runtime', 'lens', 'game-observer.json')" in script
    assert "$env:FRANCIS_LENS_GAME_OBSERVER_CONFIG_PATH = $GameObserverConfigPath" in script
    assert "Remove-Item Env:\\FRANCIS_LENS_GAME_OBSERVER_CONFIG_PATH -ErrorAction SilentlyContinue" in script


def test_resident_host_consumes_approved_handoff_but_worker_blocks_before_capture_without_supervisor(
    monkeypatch,
    tmp_path: Path,
) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    enabled = _approved_enablement(client)

    result = _run_resident_host(data_root, run_seconds=12)

    assert result.returncode == 0, result.stderr
    host_output = json.loads(result.stdout)
    worker = host_output["process_readback"]["perception_worker"]
    assert worker["enablement_status"] == "ready_for_host_consumption"
    assert worker["enablement_receipt_id"] == enabled["enablement_receipt_id"]
    assert worker["process_alive"] is False
    assert worker["result_status"] == "blocked"
    assert worker["exit_code"] == 2
    assert isinstance(worker["process_exit_code"], int)
    assert host_output["governance"]["local_process_launch_authority"] is True
    assert host_output["governance"]["perception_worker_launch_authority"] is True
    assert host_output["governance"]["mutation_authority_granted"] is True

    worker_state_path = data_root / "runtime" / "lens-perception" / "status.json"
    worker_state = json.loads(worker_state_path.read_text(encoding="utf-8"))
    assert worker_state["state"] == "blocked"
    assert worker_state["capture"]["desktop"]["active"] is False
    assert worker_state["capture"]["keyboard_content_captured"] is False
    assert worker_state["capture"]["user_mouse_captured"] is False
    assert "lens_perception_supervisor_state_unavailable" in worker_state["blockers"]
    assert not (data_root / "runtime" / "lens-perception" / "frames").exists()

    host_state = json.loads((data_root / "runtime" / "lens-host" / "status.json").read_text(encoding="utf-8-sig"))
    assert host_state["status"] == "resident_stopped"
    assert worker_state["supervision"]["parent_process_id"] == host_state["pid"]
    assert worker_state["pid"] == worker["pid"]
    assert host_state["governance"]["local_process_launch_authority"] is True
    assert host_state["governance"]["perception_worker_launch_authority"] is True
    assert host_state["governance"]["mutation_authority_granted"] is True


def test_resident_host_refuses_overbroad_enablement_without_launching_worker(monkeypatch, tmp_path: Path) -> None:
    client, data_root = _client(monkeypatch, tmp_path)
    _approved_enablement(client)
    enablement_path = data_root / "runtime" / "lens-perception" / "execution" / "enablement.json"
    enablement = json.loads(enablement_path.read_text(encoding="utf-8"))
    enablement["keyboard_capture_authority"] = True
    enablement_path.write_text(json.dumps(enablement), encoding="utf-8")

    result = _run_resident_host(data_root, run_seconds=1)

    assert result.returncode == 0, result.stderr
    host_output = json.loads(result.stdout)
    worker = host_output["process_readback"]["perception_worker"]
    assert worker["status"] == "blocked"
    assert worker["process_alive"] is False
    assert "lens_perception_execution_enablement_overbroad" in worker["blockers"]
    assert not (data_root / "runtime" / "lens-perception" / "status.json").exists()
    assert not (data_root / "runtime" / "lens-perception" / "frames").exists()
