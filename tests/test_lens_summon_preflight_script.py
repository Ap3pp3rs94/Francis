from __future__ import annotations

import json
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
    assert "lens_summon_binding_not_implemented" in dependencies["summon_binding"]["blockers"]
    resident_process = payload["resident_host_process_readback"]
    assert resident_process["process_alive"] is False
    assert resident_process["requirement_state"] in {"missing", "stale_or_unverified"}
    assert resident_process["blocker"] == "resident_host_process_missing"
    assert payload["binding"]["binding_enabled"] is False
    assert "global_hotkey_binding_disabled" in payload["blockers"]
    assert "summon_authority_not_granted" in payload["blockers"]
    blocker_groups = payload["blocker_groups"]
    assert blocker_groups["global_hotkey_binding"] == [
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "hotkey_registration_authority_not_granted",
    ]
    assert blocker_groups["summon_binding"] == [
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
    ]
    assert blocker_groups["surface_dependencies"] == [
        "tray_host_missing",
        "overlay_window_missing",
    ]
    assert "local_process_launch_authority_not_granted" in blocker_groups["host_dependency"]
    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_config"]["status"] == "present_disabled"
    assert checks["hotkey_declared"]["status"] == "declared"
    assert checks["binding_enabled"]["status"] == "disabled"
    assert checks["register_hotkey"]["status"] == "disabled"
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


def test_lens_summon_preflight_refuses_bind_actions() -> None:
    proc = _run_preflight("-Mode", "Bind")

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.preflight"
    assert payload["status"] == "refused"
    assert payload["ok"] is False
    assert payload["error"] == "lens_summon_action_not_authorized"
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
