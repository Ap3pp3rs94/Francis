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
            str(_repo_root() / "scripts" / "lens-resident-runtime-hotkey-summon-boundary-proof.ps1"),
            *args,
        ],
        cwd=_repo_root(),
        check=False,
        text=True,
        capture_output=True,
    )


def test_lens_resident_runtime_hotkey_summon_boundary_accepts_cached_authority_blockers() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-runtime-hotkey-summon-boundary-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$CachedAuthorityBlockersProofPath = ''" in script
    assert "Read-CachedJsonScriptResult -Path $CachedAuthorityBlockersProofPath" in script
    assert "cached_authority_blockers_proof" in script


def test_lens_resident_runtime_hotkey_summon_boundary_accepts_cached_tray_presence() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-runtime-hotkey-summon-boundary-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$CachedTrayPresenceBoundaryProofPath = ''" in script
    assert "Read-CachedJsonScriptResult -Path $CachedTrayPresenceBoundaryProofPath" in script
    assert "cached_tray_presence_boundary_proof" in script


def test_lens_resident_runtime_hotkey_summon_boundary_accepts_cached_summon_preflight() -> None:
    script = (_repo_root() / "scripts" / "lens-resident-runtime-hotkey-summon-boundary-proof.ps1").read_text(
        encoding="utf-8"
    )

    assert "[string]$CachedSummonPreflightProofPath = ''" in script
    assert "Read-CachedJsonScriptResult -Path $CachedSummonPreflightProofPath" in script
    assert "cached_summon_preflight" in script


def test_lens_resident_runtime_hotkey_summon_boundary_uses_cached_summon_preflight(tmp_path: Path) -> None:
    summon_preflight_cache = tmp_path / "summon-preflight.json"
    summon_preflight_cache.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "lens.summon.preflight",
                "status": "blocked",
                "ready": False,
                "summon_name": "Francis Lens Summon",
                "config_path": "config/runtime/lens/summon.json",
                "global_hotkey": "Ctrl+Alt+Space",
                "binding_scope": "global",
                "palette_route": "/lens/status",
                "required_before_enable": ["operator_authority"],
                "blockers": [
                    "global_hotkey_binding_disabled",
                    "global_hotkey_registration_disabled",
                    "summon_authority_not_granted",
                    "hotkey_registration_authority_not_granted",
                ],
                "governance": {
                    "read_only_contract": True,
                    "summon_authority": False,
                    "hotkey_registration_authority": False,
                    "local_process_launch_authority": False,
                    "overlay_control_authority": False,
                },
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", "-CachedSummonPreflightProofPath", str(summon_preflight_cache))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["cached_summon_preflight"] is True
    assert payload["summon_preflight_observed"] is True
    assert payload["summon_preflight"]["global_hotkey"] == "Ctrl+Alt+Space"


def test_lens_resident_runtime_hotkey_summon_boundary_uses_cached_tray_presence(tmp_path: Path) -> None:
    tray_presence_cache = tmp_path / "tray-presence-boundary.json"
    tray_presence_cache.write_text(
        json.dumps(
            {
                "ok": True,
                "kind": "lens.resident_runtime.tray_presence_boundary.proof",
                "status": "proof_passed",
                "authority_family": "tray_presence",
                "next_authority_family": "hotkey_summon",
                "tray_presence_boundary_observed": True,
                "previous_service_control_family_observed": True,
                "tray_preflight_observed": True,
                "authority_blockers_proof_observed": True,
                "side_effects_denied": True,
                "third_authority_family_consumed": True,
                "next_smallest_truthful_gap": "resident_runtime_hotkey_summon_authority_boundary",
            }
        ),
        encoding="utf-8",
    )

    proc = _run_proof("-Mode", "Status", "-CachedTrayPresenceBoundaryProofPath", str(tray_presence_cache))

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["cached_tray_presence_boundary_proof"] is True
    assert payload["previous_tray_presence_family_observed"] is True
    assert payload["summon_preflight_observed"] is True
    assert payload["summon_preflight_binding_blockers_observed"] is True
    assert payload["hotkey_summon_boundary_observed"] is True


def test_lens_resident_runtime_hotkey_summon_boundary_is_readback_only() -> None:
    proc = _run_proof("-Mode", "Status")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert payload["kind"] == "lens.resident_runtime.hotkey_summon_boundary.proof"
    assert payload["status"] == "proof_passed"
    assert payload["ok"] is True
    assert payload["authority_family"] == "hotkey_summon"
    assert payload["previous_authority_family"] == "tray_presence"
    assert payload["next_authority_family"] == "overlay_window"
    assert payload["authority_required"] == "hotkey_registration_and_summon_authority"
    assert payload["authority_granted"] is False
    assert payload["hotkey_summon_boundary_observed"] is True
    assert payload["previous_tray_presence_family_observed"] is True
    assert payload["summon_preflight_observed"] is True
    assert payload["authority_blockers_proof_observed"] is True
    assert payload["cached_tray_presence_boundary_proof"] is False
    assert payload["cached_summon_preflight"] is False
    assert payload["side_effects_denied"] is True
    assert payload["fourth_authority_family_consumed"] is True
    assert payload["resident_runtime_execution_authority"] is True
    assert payload["local_process_launch_authority"] is False
    assert payload["process_supervision_authority"] is False
    assert payload["process_restart_authority"] is False
    assert payload["service_install_authority"] is False
    assert payload["service_control_authority"] is False
    assert payload["tray_registration_authority"] is False
    assert payload["tray_icon_authority"] is False
    assert payload["notification_authority"] is False
    assert payload["summon_authority"] is False
    assert payload["hotkey_registration_authority"] is False
    assert payload["overlay_control_authority"] is False
    assert payload["resident_claim_authority"] is False
    assert payload["would_launch_process"] is False
    assert payload["would_supervise_process"] is False
    assert payload["would_restart_process"] is False
    assert payload["would_install_service"] is False
    assert payload["would_start_service"] is False
    assert payload["would_register_tray"] is False
    assert payload["would_register_hotkey"] is False
    assert payload["would_open_overlay"] is False
    assert payload["would_write_memory"] is False
    assert payload["would_claim_resident"] is False

    hotkey_summon = payload["hotkey_summon"]
    assert hotkey_summon["status"] == "blocked"
    assert hotkey_summon["ready"] is False
    assert hotkey_summon["authority_granted"] is False
    assert hotkey_summon["would_execute"] is False
    assert hotkey_summon["route"] == "/lens/summon"
    assert "/lens/summon" in hotkey_summon["evidence"]
    assert hotkey_summon["required_before"] == ["resident_claim"]
    assert "global_hotkey_binding_disabled" in hotkey_summon["blockers"]
    assert "global_hotkey_registration_disabled" in hotkey_summon["blockers"]
    assert "hotkey_registration_authority_not_granted" in hotkey_summon["blockers"]
    assert "summon_authority_not_granted" in hotkey_summon["blockers"]
    assert payload["blockers"] == hotkey_summon["blockers"]

    summon_preflight = payload["summon_preflight"]
    assert summon_preflight["status"] == "blocked"
    assert summon_preflight["ready"] is False
    assert summon_preflight["summon_name"] == "Francis Lens Summon"
    assert summon_preflight["config_path"] == "config/runtime/lens/summon.json"
    assert summon_preflight["global_hotkey"] == "Ctrl+Alt+Space"
    assert summon_preflight["binding_scope"] == "global"
    assert summon_preflight["palette_route"] == "/lens/status"
    assert "global_hotkey_binding_disabled" in summon_preflight["blockers"]
    assert "global_hotkey_registration_disabled" in summon_preflight["blockers"]
    assert "lens_summon_binding_disabled_pending_authority" in summon_preflight["blockers"]
    assert payload["summon_preflight_binding_blockers_observed"] is True

    assert payload["remaining_authority_families"] == [
        "process_supervision",
        "service_control",
        "tray_presence",
        "hotkey_summon",
        "overlay_window",
        "resident_claim",
    ]
    assert payload["remaining_authority_families_after_this_boundary"] == [
        "overlay_window",
        "resident_claim",
    ]
    assert payload["next_smallest_truthful_gap"] == "resident_runtime_overlay_window_authority_boundary"

    checks = {item["id"]: item for item in payload["checks"]}
    assert checks["resident_runtime_authority_blockers_proof"]["status"] == "proof_observed"
    assert checks["previous_tray_presence_family"]["status"] == "blocked"
    assert checks["summon_preflight_readback"]["status"] == "blocked_readback_ready"
    assert checks["hotkey_summon_family"]["status"] == "blocked"
    assert checks["hotkey_summon_side_effects_denied"]["status"] == "denied_no_hotkey_summon"
    assert checks["authority_boundary"]["status"] == "diagnostic_bounded"
    assert all(item["passed"] for item in payload["checks"])

    assert payload["governance"] == {
        "diagnostic_only": True,
        "wraps_existing_authority_blockers_proof": True,
        "tray_presence_boundary_readback": True,
        "summon_preflight_readback": True,
        "approval_request_write": True,
        "resident_runtime_execution_authority": True,
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
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "resident_claim_authority": False,
        "mutation_authority_granted": False,
    }
