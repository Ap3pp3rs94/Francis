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


def _run_proof(*args: str, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    run_env = os.environ.copy()
    if env:
        run_env.update(env)

    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-host-runtime-loop-readiness-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=60,
        env=run_env,
    )


def test_lens_host_runtime_loop_readiness_proof_consumes_authority_handoff(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    proc = _run_proof("-Mode", "Status", "-DataDir", str(data_root))

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.host.runtime_loop_readiness.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["mode"] == "status"
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "system_resident_presence"
    assert payload["previous_next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
    assert payload["runtime_loop_next_smallest_truthful_gap"] == (
        "resident_host_supervision_authority_readiness_blockers"
    )
    assert payload["next_smallest_truthful_gap"] == "host_supervision_authority_exact_approval_request"
    assert payload["runtime_loop_readiness_observed"] is True
    assert payload["runtime_loop_first_blocker_consumed"] is True
    assert payload["host_supervision_authority_readiness_observed"] is True
    assert payload["host_supervision_authority_first_blocker_observed"] is True
    assert payload["side_effects_denied"] is True
    assert payload["first_blocked_requirement"] == "resident_loop_process_supervision"
    assert payload["host_supervision_authority_first_blocked_requirement"] == ("exact_supervision_authority_approval")

    first_handoff = payload["first_blocked_requirement_handoff"]
    assert first_handoff["id"] == "resident_loop_process_supervision"
    assert first_handoff["route"] == "/lens/host/supervision"
    assert first_handoff["readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert first_handoff["request_route"] == "/lens/host/supervision/authority/request"
    assert first_handoff["requests_route"] == "/lens/host/supervision/authority/requests"
    assert first_handoff["grant_route"] == "/lens/host/supervision/authority"
    assert first_handoff["authority_required"] == "process_supervision_authority"
    assert first_handoff["authority_granted"] is False
    assert first_handoff["would_execute"] is False
    assert first_handoff["would_mutate"] is False
    assert "resident_host_process_missing" in first_handoff["blockers"]
    assert "process_supervision_authority_not_granted" in first_handoff["blockers"]
    assert "process_restart_authority_not_granted" in first_handoff["blockers"]

    authority_handoff = payload["host_supervision_authority_first_blocked_requirement_handoff"]
    assert authority_handoff["id"] == "exact_supervision_authority_approval"
    assert authority_handoff["route"] == "/lens/host/supervision/authority/requests"
    assert authority_handoff["readiness_route"] == "/lens/host/supervision/authority/readiness"
    assert authority_handoff["request_route"] == "/lens/host/supervision/authority/request"
    assert authority_handoff["requests_route"] == "/lens/host/supervision/authority/requests"
    assert authority_handoff["grant_route"] == "/lens/host/supervision/authority"
    assert authority_handoff["approval_action"] == "lens.host.supervision_authority"
    assert authority_handoff["next_step"] == "create_or_select_exact_approved_host_supervision_authority_request"
    assert authority_handoff["authority_required"] == "operator_approval"
    assert authority_handoff["authority_granted"] is False
    assert authority_handoff["would_execute"] is False
    assert authority_handoff["would_mutate"] is False
    assert authority_handoff["blockers"] == ["approval_id_required"]

    assert payload["blocked_requirements"] == [
        "resident_loop_process_supervision",
        "resident_loop_service_lifecycle",
        "resident_loop_surface_presence",
        "resident_loop_receipt_emission",
        "resident_loop_claim_checkpoint",
    ]
    assert payload["host_supervision_authority_blocked_requirements"][0] == ("exact_supervision_authority_approval")
    assert "resident_runtime_loop_not_implemented" in payload["blockers"]
    assert "resident_runtime_loop_not_supervised" in payload["blockers"]
    assert "approval_id_required" in payload["host_supervision_authority_blockers"]
    assert "process_supervision_authority_not_granted" in payload["host_supervision_authority_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["runtime_loop_readiness_audit"]["status"] == "readiness_observed"
    assert checks["runtime_loop_first_blocker"]["status"] == "host_supervision_authority_handoff_ready"
    assert checks["host_supervision_authority_readiness"]["status"] == "readiness_observed"
    assert checks["host_supervision_authority_first_blocker"]["status"] == ("exact_approval_request_handoff_ready")
    assert checks["side_effects_denied"]["status"] == "readback_only"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["source_readbacks"] == {
        "runtime_loop_readiness_status": "blocked",
        "runtime_loop_first_blocker": "resident_loop_process_supervision",
        "supervision_authority_readiness_status": "blocked",
        "supervision_authority_first_blocker": "exact_supervision_authority_approval",
    }
    assert "scripts/lens-host-runtime-loop-readiness-proof.ps1 -Mode Status" in payload["evidence"]
    assert "/lens/host/runtime-loop/readiness" in payload["evidence"]
    assert "/lens/host/supervision/authority/readiness" in payload["evidence"]

    assert payload["governance"] == {
        "diagnostic_only": True,
        "read_only_contract": True,
        "uses_runtime_loop_readiness_readback": True,
        "uses_supervision_authority_readiness_readback": True,
        "approval_request_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
