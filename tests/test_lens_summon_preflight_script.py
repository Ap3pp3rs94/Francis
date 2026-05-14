from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_preflight(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon-preflight.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_summon_preflight_reports_disabled_hotkey_without_authority() -> None:
    proc = _run_preflight("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    expected_required_before_enable = [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert payload["kind"] == "lens.summon.preflight"
    assert payload["status"] == "blocked"
    assert payload["ready"] is False
    assert payload["global_hotkey"] == "Ctrl+Alt+Space"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["required_before_enable"] == expected_required_before_enable
    assert payload["missing_required_before_enable"] == expected_required_before_enable
    assert payload["required_before_enable_ready"] is False
    assert payload["first_missing_required_before_enable"] == "resident_host_process"
    first_handoff = payload["first_missing_requirement_handoff"]
    assert first_handoff["id"] == "resident_host_process"
    assert first_handoff["family"] == "resident_host"
    assert first_handoff["blocker"] == "resident_host_process_missing"
    assert first_handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    assert list(dependencies) == expected_required_before_enable
    assert dependencies["resident_host_process"]["blockers"] == ["resident_host_process_missing"]
    assert dependencies["tray_presence"]["blockers"] == ["tray_host_missing"]
    assert dependencies["overlay_window"]["blockers"] == ["overlay_window_missing"]
    assert "global_hotkey_binding_disabled" in dependencies["global_hotkey_binding"]["blockers"]
    assert "lens_summon_binding_disabled_pending_authority" in dependencies["summon_binding"]["blockers"]
    resident_process = payload["resident_host_process_readback"]
    assert resident_process["process_alive"] is False
    assert resident_process["requirement_state"] in {"missing", "stale_or_unverified"}
    assert resident_process["blocker"] == "resident_host_process_missing"
    assert payload["binding"]["binding_enabled"] is False
    assert payload["binding"]["summon_runner"] == "scripts/lens-summon.ps1"
    assert payload["binding"]["summon_runner_present"] is True
    assert payload["binding"]["local_binding_target_ready"] is True
    assert payload["binding"]["global_hotkey_runtime_bound"] is False
    assert payload["hotkey_runtime_readback"]["ready"] is False
    assert payload["hotkey_runtime_readback"]["requirement_state"] == "missing"
    assert "global_hotkey_binding_disabled" in payload["blockers"]
    assert "summon_authority_not_granted" in payload["blockers"]
    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]
    assert blocker_groups["surface_dependencies"] == [
        "tray_host_missing",
        "overlay_window_missing",
    ]
    assert "local_process_launch_authority_not_granted" in blocker_groups["host_dependency"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_config"]["status"] == "present_disabled"
    assert checks["summon_runner"]["status"] == "present"
    assert checks["hotkey_declared"]["status"] == "declared"
    assert checks["binding_enabled"]["status"] == "disabled"
    assert checks["register_hotkey"]["status"] == "disabled"
    assert checks["hotkey_runtime"]["status"] == "missing"
    assert checks["host_preflight"]["status"] == "present"
    assert checks["hotkey_registration_authority"]["status"] == "blocked"
    assert payload["governance"] == {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "hotkey_registration_authority": False,
        "hotkey_runtime_readback": True,
        "summon_runner_readback": True,
        "required_before_enable_readback": True,
        "resident_host_process_readback": True,
        "mutation_authority_granted": False,
    }


def test_lens_summon_preflight_rejects_stale_resident_host_process_state(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-host"
    runtime_dir.mkdir(parents=True)
    status_path = runtime_dir / "status.json"
    pid_path = runtime_dir / "lens-host.pid"
    status_path.write_text(
        json.dumps(
            {
                "kind": "lens.host.runtime_state",
                "status": "resident_running",
                "pid": 999999,
            }
        ),
        encoding="utf-8",
    )
    pid_path.write_text("888888", encoding="utf-8")

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert Path(payload["data_root"]).resolve() == data_dir.resolve()
    resident_process = payload["resident_host_process_readback"]
    assert resident_process["process_alive"] is False
    assert resident_process["pid"] == 888888
    assert resident_process["runtime_status_pid"] == 999999
    assert resident_process["runtime_status_pid_matches_pid_file"] is False
    assert resident_process["requirement_state"] == "stale_or_unverified"
    assert resident_process["blocker"] == "resident_host_process_missing"
    assert Path(resident_process["status_path"]).resolve() == status_path.resolve()
    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    assert dependencies["resident_host_process"]["ready"] is False
    assert dependencies["resident_host_process"]["blockers"] == ["resident_host_process_missing"]
    assert payload["first_missing_requirement_handoff"]["id"] == "resident_host_process"


def test_lens_summon_preflight_consumes_live_hotkey_runtime_readback(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    runtime_dir = data_dir / "runtime" / "lens-hotkey"
    runtime_dir.mkdir(parents=True)
    pid = os.getpid()
    (runtime_dir / "lens-hotkey.pid").write_text(str(pid), encoding="utf-8")
    (runtime_dir / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.hotkey.runtime_state",
                "status": "hotkey_bound",
                "pid": pid,
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "hotkey_bound": True,
                "launch_on_hotkey": False,
                "summon_runner": "scripts/lens-summon.ps1",
                "press_count": 0,
            }
        ),
        encoding="utf-8",
    )

    proc = _run_preflight("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    hotkey_runtime = payload["hotkey_runtime_readback"]
    assert hotkey_runtime["ready"] is True
    assert hotkey_runtime["hotkey_bound"] is True
    assert hotkey_runtime["requirement_state"] == "bound"
    assert hotkey_runtime["blocker"] == ""
    assert payload["binding"]["global_hotkey_runtime_bound"] is True
    assert payload["binding"]["hotkey_runtime_requirement_state"] == "bound"
    dependencies = {item["id"]: item for item in payload["enablement_dependency_readback"]}
    hotkey_dependency = dependencies["global_hotkey_binding"]
    assert hotkey_dependency["runtime_ready"] is True
    assert hotkey_dependency["runtime_requirement_state"] == "bound"
    assert hotkey_dependency["runtime_blocker"] == ""
    assert hotkey_dependency["ready"] is False
    assert "global_hotkey_binding_disabled" in hotkey_dependency["blockers"]
    assert "hotkey_registration_authority_not_granted" in hotkey_dependency["blockers"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["hotkey_runtime"]["status"] == "bound"
    assert payload["ready"] is False
    assert payload["governance"]["hotkey_runtime_readback"] is True
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False


def test_lens_summon_preflight_refuses_bind_actions() -> None:
    proc = _run_preflight("-Mode", "Bind")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.preflight"
    assert payload["status"] == "blocked"
    assert payload["ok"] is False
    assert payload["error"] == "lens_summon_bind_blocked_by_preflight"
    assert payload["binding_execution_attempted"] is False
    assert payload["launch_execution_attempted"] is False
    action_gate = payload["action_gate"]
    assert action_gate["action"] == "bind"
    assert action_gate["status"] == "blocked"
    assert action_gate["policy_gate"] == "lens_summon_preflight"
    assert action_gate["execution_handoff"] == "scripts/lens-summon-action.ps1 -Mode Bind"
    assert action_gate["bounded_runtime_handoff"] == "scripts/lens-hotkey-binding.ps1 -Mode Start"
    assert action_gate["required_before_enable_ready"] is False
    assert action_gate["missing_required_before_enable"] == [
        "resident_host_process",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
    ]
    assert action_gate["first_missing_required_before_enable"] == "resident_host_process"
    assert action_gate["first_missing_requirement_handoff"]["id"] == "resident_host_process"
    assert action_gate["first_missing_requirement_handoff"]["blocker"] == "resident_host_process_missing"
    assert action_gate["required_authorities"] == [
        "summon_authority",
        "hotkey_registration_authority",
        "overlay_control_authority",
        "local_process_launch_authority",
    ]
    assert action_gate["missing_authorities"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]
    assert action_gate["binding_execution_attempted"] is False
    assert action_gate["launch_execution_attempted"] is False
    assert action_gate["would_register_hotkey"] is False
    assert action_gate["would_summon"] is False
    assert action_gate["would_launch_process"] is False
    assert action_gate["would_open_overlay"] is False
    assert action_gate["would_write_memory"] is False
    assert action_gate["would_decide_approval"] is False
    assert action_gate["mutation_authority_granted"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["action_request_gated"] is True
    assert payload["governance"]["summon_action_authorized"] is False
