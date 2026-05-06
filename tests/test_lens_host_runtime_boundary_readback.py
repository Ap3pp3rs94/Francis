from __future__ import annotations

from francis.lens.host_manifest import lens_host_runtime_boundary


def test_lens_host_runtime_boundary_surfaces_bounded_launch_proof_handoff() -> None:
    body = lens_host_runtime_boundary(
        manifest={
            "declared_entrypoint": {"exists": True},
            "status_command": {"executable": True},
            "candidate_command": {"executable": True},
            "foreground_session": {
                "supported": True,
                "runtime_state_write": True,
                "max_seconds": 30,
            },
            "process_readback": {"process_alive": False},
            "blocker_groups": {
                "runtime": ["lens_host_runtime_not_implemented"],
                "surface_dependencies": [
                    "tray_host_missing",
                    "global_hotkey_binding_missing",
                    "overlay_window_missing",
                    "summon_binding_missing",
                ],
            },
        }
    )

    assert body["kind"] == "lens.host.runtime_boundary"
    assert body["status"] == "blocked"
    assert body["bounded_launch_proof_available"] is True
    assert body["bounded_launch_proof_script"] == "scripts/lens-host-launch-proof.ps1 -Mode Status"
    assert "scripts/lens-host.ps1 -Mode Launch" in body["evidence"]
    assert "scripts/lens-host-launch-proof.ps1 -Mode Status" in body["evidence"]

    proof_handoff = body["boundaries"]["bounded_launch_proof"]
    assert proof_handoff == {
        "status": "available",
        "ready": True,
        "scope": "readback_to_existing_bounded_diagnostic_launch_proof",
        "proof_script": "scripts/lens-host-launch-proof.ps1 -Mode Status",
        "host_script": "scripts/lens-host.ps1 -Mode Launch",
        "resident_runtime": False,
        "would_launch_from_api": False,
        "would_launch_from_status_route": False,
        "authority_granted": False,
        "product_execution_authority": False,
        "api_local_process_launch_authority": False,
        "resident_claim_allowed": False,
    }
    assert body["governance"]["execution_authority"] is False
    assert body["governance"]["local_process_launch_authority"] is False
    assert body["governance"]["diagnostic_launch_authority"] is False
    assert body["governance"]["resident_claim_authority"] is False
    assert body["next_smallest_truthful_gap"] == "resident_host_runtime_implementation_plan"
