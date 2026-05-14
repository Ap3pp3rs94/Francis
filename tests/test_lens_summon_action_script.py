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


def _run_action(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon-action.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=30,
    )


def test_lens_summon_action_status_consumes_preflight_without_execution(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    proc = _run_action("-Mode", "Status", "-DataDir", str(data_dir))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.action"
    assert payload["status"] == "blocked"
    assert payload["mode"] == "status"
    assert payload["preflight"]["kind"] == "lens.summon.preflight"
    assert payload["preflight_ready"] is False
    assert payload["execution_attempted"] is False
    assert payload["handoff_attempted"] is False
    assert payload["hotkey_binding_attempted"] is False
    assert payload["launch_attempted"] is False
    assert payload["bounded_handoff"]["status"] == "not_requested"
    assert payload["governance"]["read_only_contract"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False


@pytest.mark.parametrize(
    ("mode", "expected_error", "attempt_field"),
    [
        ("Bind", "lens_summon_action_blocked_by_preflight", "hotkey_binding_attempted"),
        ("Launch", "lens_summon_action_blocked_by_preflight", "launch_attempted"),
    ],
)
def test_lens_summon_action_refuses_blocked_handoff_without_side_effects(
    tmp_path: Path,
    mode: str,
    expected_error: str,
    attempt_field: str,
) -> None:
    data_dir = tmp_path / "data"
    proc = _run_action("-Mode", mode, "-DataDir", str(data_dir))

    assert proc.returncode == 2
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon.action"
    assert payload["status"] == "blocked_by_preflight"
    assert payload["mode"] == mode.lower()
    assert payload["error"] == expected_error
    assert payload["preflight_exit_code"] == 2
    assert payload["preflight_ready"] is False
    assert payload["preflight"]["kind"] == "lens.summon.preflight"
    assert payload["action_gate"]["action"] == mode.lower()
    assert payload["action_gate"]["status"] == "blocked"
    assert payload["action_gate"]["execution_handoff"] == f"scripts/lens-summon-action.ps1 -Mode {mode}"
    assert payload["execution_attempted"] is False
    assert payload["handoff_attempted"] is False
    assert payload["hotkey_binding_attempted"] is False
    assert payload["launch_attempted"] is False
    assert payload[attempt_field] is False
    assert payload["bounded_handoff"]["status"] == "not_requested"
    assert payload["bounded_handoff"]["payload"] is None
    assert payload["governance"]["action_request_gated"] is True
    assert payload["governance"]["execution_authority"] is False
    assert payload["governance"]["approval_decision_authority"] is False
    assert payload["governance"]["memory_write"] is False
    assert payload["governance"]["hotkey_registration_authority"] is False
    assert payload["governance"]["summon_authority"] is False
    assert payload["governance"]["mutation_authority_granted"] is False
    assert not (data_dir / "runtime" / "lens-hotkey" / "status.json").exists()
