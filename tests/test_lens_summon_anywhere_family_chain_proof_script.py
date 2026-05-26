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


def _run_proof(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            _powershell(),
            "-NoProfile",
            "-ExecutionPolicy",
            "Bypass",
            "-File",
            str(_repo_root() / "scripts" / "lens-summon-anywhere-family-chain-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
        timeout=780,
    )


def _write_summon_binding_runtime_readback(data_root: Path) -> None:
    runtime_root = data_root / "runtime" / "lens-summon"
    runtime_root.mkdir(parents=True, exist_ok=True)
    (runtime_root / "status.json").write_text(
        json.dumps(
            {
                "kind": "lens.summon.runtime_state",
                "status": "summon_binding_observed",
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "bounded_handoff_ready": True,
                "local_open_ready": True,
                "opened": False,
                "no_launch": True,
                "summon_anywhere": False,
                "os_level_summon": False,
                "updated_at": "2026-05-26T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def test_lens_summon_anywhere_family_chain_requires_child_authority_readbacks() -> None:
    script = (_repo_root() / "scripts" / "lens-summon-anywhere-family-chain-proof.ps1").read_text(encoding="utf-8")

    assert "summon_anywhere_blockers_first_family_handoff" in script
    assert "uses_summon_anywhere_family_handoff_contract" in script
    assert "final_authority_previous_contract_readback" in script
    assert (
        "[string](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_required' -Default '') "
        "-eq 'resident_runtime_execution_authority'"
    ) in script
    assert (
        "-not [bool](Get-PropertyValue -Payload $SummonFirstHandoff -Name 'authority_granted' -Default $true)" in script
    )
    assert "reuses_authority_previous_resident_host_bridge_readback" not in script
    assert "previous_global_hotkey_bridge" not in script
    assert "previous_resident_host_bridge" not in script
    assert "wraps_summon_resident_host_blocker_proof" not in script
    assert "New-ChildProofRunSummary -Name 'summon_resident_host_blocker'" not in script
    assert "recommended_handoff_source = $RecommendedHandoffSource" in script
    assert "summon_anywhere_family_chain_completion_audit_handoff" in script
    assert "scripts/lens-stage6-completion-audit.ps1 -Mode Status" in script
    assert "summon_binding_resolved_by_runtime_readback" in script
    assert "final_authority_runtime_readback_resolved" in script
    assert (
        "[string](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_required' -Default '') "
        "-eq 'summon_hotkey_overlay_and_process_authority'"
    ) in script
    assert (
        "-not [bool](Get-PropertyValue -Payload $AuthorityPayload -Name 'authority_granted' -Default $true)" in script
    )


def test_lens_summon_anywhere_family_chain_consumes_handoffs(tmp_path: Path) -> None:
    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(tmp_path / "data"),
        "-ChildProofTimeoutSeconds",
        "240",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_anywhere_family_chain.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["stage"] == "Stage 6 / Lens MVP"
    assert payload["stage_state"] == "active"
    assert payload["acceptance_criterion"] == "summon_anywhere"
    assert payload["summon_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert payload["recommended_handoff_source"] == "summon_anywhere_family_chain_completion_audit_handoff"
    assert payload["recommended_next_slice"] == (
        "run_stage6_lens_completion_audit_after_summon_anywhere_family_chain_readback"
    )
    assert payload["recommended_proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert payload["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert payload["authority_granted"] is False
    assert payload["family_chain_observed"] is True
    assert payload["resident_host_family_handoff_observed"] is True
    assert payload["final_summon_authority_handoff_observed"] is True
    assert payload["final_summon_authority_contract_readback_observed"] is True
    assert payload["final_summon_authority_runtime_readback_resolved"] is False
    assert payload["summon_binding_runtime_readback_observed"] is False
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["child_proof_timeout_seconds"] == 240
    assert payload["child_proof_timeouts"] == []
    child_proof_runs = {item["name"]: item for item in payload["child_proof_runs"]}
    assert set(child_proof_runs) == {
        "summon_anywhere_blockers",
        "summon_authority_blocker",
    }
    for run in child_proof_runs.values():
        assert run["timed_out"] is False
        assert run["timeout_seconds"] == 240
        assert isinstance(run["duration_ms"], int)
        assert run["duration_ms"] >= 0

    assert payload["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "summon_binding",
        "authority",
    ]
    assert [item["id"] for item in payload["blocked_family_handoffs"]] == payload["blocked_families"]
    assert payload["first_blocker_family"] == "resident_host"
    assert payload["first_blocker_family_handoff"]["next_smallest_truthful_gap"] == (
        "resident_host_runtime_blocker_boundary"
    )
    recommended_handoff = payload["recommended_handoff"]
    assert recommended_handoff["id"] == "stage6_lens_completion_audit"
    assert recommended_handoff["status"] == "audit_needed"
    assert recommended_handoff["previous_next_smallest_truthful_gap"] == "summon_anywhere_blockers"
    assert recommended_handoff["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert recommended_handoff["next_step"] == (
        "run_stage6_lens_completion_audit_after_summon_anywhere_family_chain_readback"
    )
    assert recommended_handoff["proof_script"] == "scripts/lens-stage6-completion-audit.ps1 -Mode Status"
    assert recommended_handoff["route"] == "/lens/status"
    assert recommended_handoff["readiness_route"] == "/lens/status"
    assert recommended_handoff["acceptance_criterion"] == "summon_anywhere"
    assert recommended_handoff["blocker"] == "summon_anywhere_blockers"
    assert recommended_handoff["requirement_state"] == "summon_anywhere_family_chain_consumed_without_authority"
    assert recommended_handoff["authority_required"] == "none_new_stage6_completion_audit"
    assert recommended_handoff["authority_granted"] is False
    assert recommended_handoff["read_only_contract"] is True
    assert recommended_handoff["diagnostic_only"] is True
    assert recommended_handoff["would_execute"] is False
    assert recommended_handoff["would_mutate"] is False
    assert recommended_handoff["would_register_hotkey"] is False
    assert recommended_handoff["would_control_overlay"] is False
    assert recommended_handoff["would_launch_process"] is False
    assert recommended_handoff["would_supervise_process"] is False
    assert recommended_handoff["would_claim_resident"] is False
    assert recommended_handoff["blocked_families"] == payload["blocked_families"]

    resident_host = payload["resident_host"]
    assert resident_host["handoff_source"] == "summon_anywhere_blockers_first_family_handoff"
    assert resident_host["id"] == "resident_host"
    assert resident_host["status"] == "blocked"
    assert resident_host["proof_script"] == "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status"
    assert resident_host["route"] == "/lens/host"
    assert resident_host["readiness_route"] == "/lens/host/runtime-loop/readiness"
    assert resident_host["next_step"] == "run_resident_host_blocker_proof"
    assert resident_host["next_smallest_truthful_gap"] == "resident_host_runtime_blocker_boundary"
    assert resident_host["authority_required"] == "resident_runtime_execution_authority"
    assert resident_host["authority_granted"] is False
    assert resident_host["read_only_contract"] is True
    assert resident_host["diagnostic_only"] is True
    assert resident_host["would_execute"] is False
    assert resident_host["would_mutate"] is False
    assert resident_host["blockers"] == ["local_process_launch_authority_not_granted"]

    final_authority = payload["final_authority"]
    assert final_authority["previous_summon_blocker_family"] == "summon_binding"
    assert final_authority["summon_authority_blocker_family"] == "authority"
    assert final_authority["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert final_authority["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert final_authority["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert final_authority["authority_granted"] is False
    assert final_authority["all_summon_blocker_families_consumed"] is True
    assert final_authority["previous_summon_binding_contract_observed"] is True
    assert final_authority["previous_summon_binding_contract_readback_observed"] is True
    assert final_authority["summon_binding_runtime_readback_observed"] is False
    assert final_authority["summon_binding_resolved_by_runtime_readback"] is False
    previous_binding = final_authority["previous_binding_handoff"]
    assert previous_binding["source"] == "summon_anywhere_blockers.blocked_family_handoffs"
    assert previous_binding["status"] == "contract_projected"
    assert previous_binding["contract_status"] == "blocked"
    assert previous_binding["proof_script"] == "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status"
    assert previous_binding["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_binding["summon_binding_blocker_family"] == "summon_binding"
    assert previous_binding["next_summon_blocker_family"] == "authority"
    assert previous_binding["next_smallest_truthful_gap"] == "summon_authority_blocker_boundary"
    assert previous_binding["authority_required"] == "summon_authority"
    assert previous_binding["authority_granted"] is False
    assert previous_binding["read_only_contract"] is True
    assert previous_binding["diagnostic_only"] is True
    assert previous_binding["would_execute"] is False
    assert previous_binding["would_mutate"] is False
    assert previous_binding["handoff_aligned"] is True
    assert previous_binding["side_effects_denied"] is True
    assert previous_binding["blockers"] == [
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
    ]
    assert final_authority["blockers"] == [
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted",
    ]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_anywhere_family_chain"]["status"] == "family_chain_projected"
    assert checks["resident_host_family_handoff"]["status"] == "resident_host_contract_ready"
    assert checks["final_summon_authority_handoff"]["status"] == "final_family_consumed"
    assert checks["final_summon_authority_contract_readback"]["status"] == ("final_contract_readback_observed")
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_summon_anywhere_blockers_proof": True,
        "wraps_summon_authority_blocker_proof": True,
        "uses_summon_anywhere_family_handoff_contract": True,
        "final_authority_previous_contract_readback": True,
        "final_authority_runtime_readback_resolved": False,
        "read_only_contract": True,
        "bounded_local_process_launch": False,
        "temporary_runtime_state_write": False,
        "product_execution_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }


def test_lens_summon_anywhere_family_chain_accepts_resolved_summon_binding_runtime_readback(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    _write_summon_binding_runtime_readback(data_root)

    proc = _run_proof(
        "-Mode",
        "Status",
        "-DataDir",
        str(data_root),
        "-ChildProofTimeoutSeconds",
        "240",
    )

    assert proc.returncode == 0, proc.stderr or proc.stdout
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.summon_anywhere_family_chain.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["blocked_families"] == [
        "resident_host",
        "tray_presence",
        "overlay_window",
        "global_hotkey_binding",
        "authority",
    ]
    assert "summon_binding" not in payload["blocked_families"]
    assert payload["family_chain_observed"] is True
    assert payload["final_summon_authority_handoff_observed"] is True
    assert payload["final_summon_authority_contract_readback_observed"] is True
    assert payload["final_summon_authority_runtime_readback_resolved"] is True
    assert payload["summon_binding_runtime_readback_observed"] is True
    assert payload["all_summon_blocker_families_consumed"] is True
    assert payload["handoff_aligned"] is True
    assert payload["side_effects_denied"] is True
    assert payload["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"

    final_authority = payload["final_authority"]
    assert final_authority["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert final_authority["summon_authority_blocker_family"] == "authority"
    assert final_authority["next_summon_blocker_family"] == "stage6_lens_completion_audit"
    assert final_authority["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert final_authority["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert final_authority["authority_granted"] is False
    assert final_authority["previous_summon_binding_contract_observed"] is True
    assert final_authority["previous_summon_binding_contract_readback_observed"] is True
    assert final_authority["summon_binding_runtime_readback_observed"] is True
    assert final_authority["summon_binding_resolved_by_runtime_readback"] is True

    previous_binding = final_authority["previous_binding_handoff"]
    assert previous_binding["source"] == "summon_anywhere_blockers.surface_runtime_readback_observed"
    assert previous_binding["status"] == "runtime_readback_resolved"
    assert previous_binding["contract_status"] == "resolved"
    assert previous_binding["proof_script"] == "scripts/lens-summon-anywhere-blockers-proof.ps1 -Mode Status"
    assert previous_binding["previous_summon_blocker_family"] == "global_hotkey_binding"
    assert previous_binding["summon_binding_blocker_family"] == "summon_binding"
    assert previous_binding["next_summon_blocker_family"] == "authority"
    assert previous_binding["next_smallest_truthful_gap"] == "stage6_lens_completion_audit"
    assert previous_binding["authority_required"] == "summon_hotkey_overlay_and_process_authority"
    assert previous_binding["authority_granted"] is False
    assert previous_binding["read_only_contract"] is True
    assert previous_binding["diagnostic_only"] is True
    assert previous_binding["would_execute"] is False
    assert previous_binding["would_mutate"] is False
    assert previous_binding["blockers"] == []
    assert "lens_summon_binding_disabled_pending_authority" in previous_binding["suppressed_blockers"]
    assert "summon_authority_not_granted" in previous_binding["suppressed_blockers"]

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["summon_anywhere_family_chain"]["status"] == "family_chain_projected"
    assert checks["final_summon_authority_handoff"]["status"] == "final_family_consumed"
    assert checks["final_summon_authority_contract_readback"]["status"] == "final_runtime_readback_resolved"
    assert checks["handoff_alignment"]["status"] == "handoff_aligned"
    assert checks["side_effects_denied"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    governance = payload["governance"]
    assert governance["final_authority_previous_contract_readback"] is True
    assert governance["final_authority_runtime_readback_resolved"] is True
    assert governance["execution_authority"] is False
    assert governance["summon_authority"] is False
    assert governance["mutation_authority_granted"] is False
