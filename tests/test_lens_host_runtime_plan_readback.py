from __future__ import annotations

from francis.lens.host_runtime_plan import (
    lens_host_runtime_implementation_plan,
    lens_host_runtime_loop_contract,
    lens_host_runtime_loop_readiness_audit,
)


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


def test_lens_host_runtime_loop_readback_consumes_supervision_authority_grant() -> None:
    manifest = {
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
            "process_alive": True,
            "runtime_state_path": "data/runtime/lens-host/status.json",
        },
        "blocker_groups": {
            "runtime": ["lens_host_runtime_not_implemented"],
            "process_readback": ["resident_host_process_not_supervised"],
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
        "supervision_readiness": {
            "authority_grant_active": True,
            "authority_grant": {
                "receipt_id": "lhsag_test",
                "kind": "lens.host.supervision_authority.grant.receipt",
                "status": "authority_granted",
            },
            "process_supervision_authority": True,
            "process_restart_authority": True,
            "service_install_authority": True,
            "service_control_authority": True,
            "receipt_write_authority": True,
            "resident_claim_authority": True,
        },
    }

    plan = lens_host_runtime_implementation_plan(manifest=manifest)
    plan_steps = {item["id"]: item for item in plan["plan"]["steps"]}

    assert plan["authority_grant_active"] is True
    assert plan["active_supervision_authority_grant_receipt_id"] == "lhsag_test"
    assert plan["authority_readback"]["process_supervision_authority"] is True
    assert plan["authority_readback"]["does_not_start_loop"] is True
    assert plan["authority_readback"]["does_not_satisfy_resident_runtime_loop"] is True
    assert "process_supervision_authority_not_granted" not in plan["blockers"]
    assert "process_restart_authority_not_granted" not in plan["blockers"]
    assert "service_install_authority_not_granted" not in plan["blockers"]
    assert "service_control_authority_not_granted" not in plan["blockers"]
    assert "resident_claim_authority_not_granted" not in plan["blockers"]
    assert "resident_runtime_execution_authority_not_granted" in plan["blockers"]

    supervision_step = plan_steps["process_supervision_contract"]
    assert supervision_step["ready"] is False
    assert supervision_step["authority_granted"] is True
    assert "resident_host_process_not_supervised" in supervision_step["blockers"]
    assert "process_supervision_authority_not_granted" not in supervision_step["blockers"]
    assert "process_restart_authority_not_granted" not in supervision_step["blockers"]

    loop = lens_host_runtime_loop_contract(manifest=manifest, runtime_plan=plan)
    loop_requirements = {item["id"]: item for item in loop["loop_contract"]["requirements"]}
    loop_supervision = loop_requirements["resident_loop_process_supervision"]

    assert loop["authority_grant_active"] is True
    assert loop["active_supervision_authority_grant_receipt_id"] == "lhsag_test"
    assert loop_supervision["ready"] is False
    assert loop_supervision["authority_granted"] is True
    assert "resident_host_process_not_supervised" in loop_supervision["blockers"]
    assert "process_supervision_authority_not_granted" not in loop_supervision["blockers"]
    assert "process_restart_authority_not_granted" not in loop_supervision["blockers"]
    assert "resident_runtime_loop_not_implemented" in loop["blockers"]
    assert loop["loop_ready"] is False
    assert loop["resident_runtime_loop"] is False
    assert loop["governance"]["execution_authority"] is False
    assert loop["governance"]["process_supervision_authority"] is False
    assert loop["governance"]["resident_claim_authority"] is False

    audit = lens_host_runtime_loop_readiness_audit(manifest=manifest, runtime_plan=plan, runtime_loop=loop)
    audit_requirements = {item["id"]: item for item in audit["requirements"]}

    assert audit["authority_grant_active"] is True
    assert audit["active_supervision_authority_grant_receipt_id"] == "lhsag_test"
    assert audit["first_blocked_requirement"] == "resident_loop_process_supervision"
    assert audit["first_blocked_requirement_handoff"]["authority_granted"] is True
    assert audit_requirements["resident_loop_process_supervision"]["authority_granted"] is True
    assert "process_supervision_authority_not_granted" not in audit["blockers"]
    assert audit["ready"] is False
    assert audit["resident_runtime_loop"] is False
