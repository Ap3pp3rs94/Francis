from __future__ import annotations

from francis.lens.host_runtime_plan import lens_host_runtime_implementation_plan


def test_lens_host_runtime_plan_consumes_bounded_launch_proof_handoff() -> None:
    body = lens_host_runtime_implementation_plan(
        manifest={
            "declared_entrypoint": {"exists": True},
            "status_command": {"executable": True},
            "candidate_command": {"executable": True},
            "foreground_session": {
                "supported": True,
                "runtime_state_write": True,
                "max_seconds": 30,
            },
            "process_readback": {
                "readback_ready": True,
                "process_alive": False,
                "runtime_state_path": "data/runtime/lens-host/status.json",
            },
            "blocker_groups": {
                "runtime": ["lens_host_runtime_not_implemented"],
                "surface_dependencies": [
                    "tray_host_missing",
                    "global_hotkey_binding_missing",
                    "overlay_window_missing",
                    "summon_binding_missing",
                ],
            },
            "service_install": {
                "config_exists": True,
                "manager_exists": True,
                "config_path": "config/runtime/services/lens-host.json",
            },
        }
    )

    assert body["kind"] == "lens.host.runtime_implementation_plan"
    assert body["status"] == "blocked"
    assert body["bounded_launch_proof_available"] is True
    assert body["bounded_launch_proof_script"] == "scripts/lens-host-launch-proof.ps1 -Mode Status"
    assert "scripts/lens-host.ps1 -Mode Launch" in body["evidence"]
    assert "scripts/lens-host-launch-proof.ps1 -Mode Status" in body["evidence"]
    assert body["plan"]["would_launch_process"] is False

    proof_handoff = body["bounded_launch_proof"]
    assert proof_handoff["status"] == "available"
    assert proof_handoff["ready"] is True
    assert proof_handoff["proof_script"] == "scripts/lens-host-launch-proof.ps1 -Mode Status"
    assert proof_handoff["host_script"] == "scripts/lens-host.ps1 -Mode Launch"
    assert proof_handoff["would_launch_from_api"] is False
    assert proof_handoff["would_launch_from_status_route"] is False
    assert proof_handoff["product_execution_authority"] is False
    assert proof_handoff["api_local_process_launch_authority"] is False
    assert proof_handoff["resident_claim_allowed"] is False

    governance = body["governance"]
    assert governance["read_only_contract"] is True
    assert governance["execution_authority"] is False
    assert governance["local_process_launch_authority"] is False
    assert governance["diagnostic_launch_authority"] is False
    assert governance["process_supervision_authority"] is False
    assert governance["resident_claim_authority"] is False
