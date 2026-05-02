from __future__ import annotations

from typing import Any

from francis.lens.host_manifest import lens_host_launch_manifest, lens_host_runtime_boundary


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    return [str(value)]


def _ordered_unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        item = str(value or "").strip()
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _plan_step(
    step_id: str,
    *,
    label: str,
    ready: bool,
    blockers: list[str],
    route: str = "",
    authority_required: str = "",
    source: str = "",
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "route": route,
        "source": source,
        "blockers": [] if ready else _ordered_unique(blockers),
        "authority_required": authority_required,
        "authority_granted": False,
        "would_execute": False,
        "would_mutate": False,
    }


def lens_host_runtime_implementation_plan(
    *,
    manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    runtime_boundary = lens_host_runtime_boundary(manifest=launch_manifest)
    declared_entrypoint = _as_dict(launch_manifest.get("declared_entrypoint"))
    service_install = _as_dict(launch_manifest.get("service_install"))
    process_readback = _as_dict(runtime_boundary.get("process_readback"))
    blocker_groups = _as_dict(runtime_boundary.get("blocker_groups"))

    entrypoint_ready = bool(declared_entrypoint.get("exists"))
    diagnostic_runner_ready = bool(runtime_boundary.get("diagnostic_status_runner_ready"))
    bounded_foreground_ready = bool(runtime_boundary.get("bounded_foreground_session_available"))
    runtime_blockers = _as_str_list(blocker_groups.get("runtime")) or ["lens_host_runtime_not_implemented"]
    process_blockers = _as_str_list(blocker_groups.get("process_readback")) or [
        str(runtime_boundary.get("resident_host_process_blocker") or "resident_host_process_missing")
    ]
    surface_blockers = _as_str_list(blocker_groups.get("surface_dependencies"))
    service_config_ready = bool(service_install.get("config_exists"))
    service_manager_ready = bool(service_install.get("manager_exists"))

    steps = [
        _plan_step(
            "host_entrypoint_contract",
            label="Host entrypoint contract",
            ready=entrypoint_ready,
            route="/lens/host/manifest",
            source=str(declared_entrypoint.get("path") or ""),
            blockers=["lens_host_entrypoint_missing"],
        ),
        _plan_step(
            "diagnostic_status_boundary",
            label="Diagnostic status boundary",
            ready=diagnostic_runner_ready,
            route="/lens/host/runtime-boundary",
            source="scripts/lens-host.ps1 -Mode Status",
            blockers=["diagnostic_status_runner_missing"],
        ),
        _plan_step(
            "bounded_foreground_session_boundary",
            label="Bounded foreground session boundary",
            ready=bounded_foreground_ready,
            route="/lens/host/runtime-boundary",
            source="scripts/lens-host.ps1 -Mode Foreground",
            blockers=["bounded_foreground_session_missing"],
        ),
        _plan_step(
            "runtime_state_readback_contract",
            label="Runtime state readback contract",
            ready=bool(process_readback.get("readback_ready")),
            route="/lens/host/runtime-boundary",
            source=str(process_readback.get("runtime_state_path") or ""),
            blockers=["resident_host_runtime_state_readback_missing"],
        ),
        _plan_step(
            "resident_runtime_loop_contract",
            label="Resident runtime loop contract",
            ready=False,
            route="/lens/host/runtime-loop",
            authority_required="resident_runtime_execution_authority",
            blockers=runtime_blockers,
        ),
        _plan_step(
            "process_supervision_contract",
            label="Process supervision contract",
            ready=False,
            route="/lens/host/supervision",
            authority_required="process_supervision_authority",
            blockers=[
                *process_blockers,
                "process_supervision_authority_not_granted",
                "process_restart_authority_not_granted",
            ],
        ),
        _plan_step(
            "service_management_contract",
            label="Service management contract",
            ready=False,
            route="/lens/host/manifest",
            source=str(service_install.get("config_path") or ""),
            authority_required="service_install_and_control_authority",
            blockers=[
                *([] if service_config_ready else ["lens_host_service_config_missing"]),
                *([] if service_manager_ready else ["lens_host_service_manager_missing"]),
                "service_install_authority_not_granted",
                "service_control_authority_not_granted",
            ],
        ),
        _plan_step(
            "tray_presence_contract",
            label="Tray presence contract",
            ready=False,
            authority_required="tray_registration_authority",
            blockers=["tray_host_missing", "tray_registration_authority_not_granted"],
        ),
        _plan_step(
            "hotkey_summon_contract",
            label="Hotkey and summon contract",
            ready=False,
            authority_required="hotkey_registration_and_summon_authority",
            blockers=[
                "global_hotkey_binding_missing",
                "summon_binding_missing",
                "hotkey_registration_authority_not_granted",
                "summon_authority_not_granted",
            ],
        ),
        _plan_step(
            "overlay_window_contract",
            label="Overlay window contract",
            ready=False,
            authority_required="overlay_control_authority",
            blockers=["overlay_window_missing", "overlay_control_authority_not_granted"],
        ),
        _plan_step(
            "resident_claim_contract",
            label="Resident claim contract",
            ready=False,
            authority_required="resident_claim_authority",
            blockers=["resident_runtime_not_ready", "resident_claim_authority_not_granted"],
        ),
    ]

    ready_steps = [step for step in steps if bool(step.get("ready"))]
    blocked_steps = [str(step["id"]) for step in steps if not bool(step.get("ready"))]
    authority_blockers = [
        "resident_runtime_execution_authority_not_granted",
        "process_supervision_authority_not_granted",
        "process_restart_authority_not_granted",
        "service_install_authority_not_granted",
        "service_control_authority_not_granted",
        "tray_registration_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "summon_authority_not_granted",
        "resident_claim_authority_not_granted",
    ]
    blockers = _ordered_unique(
        [
            *runtime_blockers,
            *process_blockers,
            *surface_blockers,
            *authority_blockers,
        ]
    )

    return {
        "ok": True,
        "kind": "lens.host.runtime_implementation_plan",
        "status": "blocked",
        "route": "/lens/host/runtime-plan",
        "manifest_route": "/lens/host/manifest",
        "runtime_boundary_route": "/lens/host/runtime-boundary",
        "host_route": "/lens/host",
        "plan_available": True,
        "implementation_ready": False,
        "execution_ready": False,
        "resident_runtime_ready": False,
        "resident_claim_allowed": False,
        "foreground_process_observed": bool(runtime_boundary.get("foreground_process_observed")),
        "resident_host_process_state": str(runtime_boundary.get("resident_host_process_state") or ""),
        "resident_host_process_blocker": str(runtime_boundary.get("resident_host_process_blocker") or ""),
        "requirements_total": len(steps),
        "requirements_ready_total": len(ready_steps),
        "blocked_requirements": blocked_steps,
        "blockers": blockers,
        "blocker_groups": {
            "runtime": runtime_blockers,
            "process_readback": process_blockers,
            "surface_dependencies": surface_blockers,
            "authority": authority_blockers,
        },
        "plan": {
            "status": "blocked",
            "steps": steps,
            "would_launch_process": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_tray": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_claim_resident": False,
            "would_write_memory": False,
            "would_write_receipt": False,
            "would_decide_approval": False,
        },
        "runtime_boundary": runtime_boundary,
        "evidence": [
            "/lens/host/runtime-plan",
            "/lens/host/runtime-loop",
            "/lens/host/runtime-boundary",
            "/lens/host/manifest",
            "/lens/host/supervision",
        ],
        "governance": {
            "gate": "lens_host_runtime_implementation_plan",
            "read_only_contract": True,
            "plan_readback_only": True,
            "execution_authority": False,
            "resident_runtime_execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "diagnostic_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "mutation_authority_granted": False,
        },
        "next_smallest_truthful_gap": "resident_host_runtime_loop_execution_denial_boundary",
        "message": (
            "Lens can describe the resident-host runtime implementation path, but this contract does not "
            "launch, supervise, install, register, claim residency, approve, or write memory."
        ),
    }


def lens_host_runtime_loop_contract(
    *,
    manifest: dict[str, Any] | None = None,
    runtime_plan: dict[str, Any] | None = None,
) -> dict[str, Any]:
    launch_manifest = manifest if isinstance(manifest, dict) else lens_host_launch_manifest()
    implementation_plan = (
        runtime_plan
        if isinstance(runtime_plan, dict)
        else lens_host_runtime_implementation_plan(manifest=launch_manifest)
    )
    runtime_boundary = _as_dict(implementation_plan.get("runtime_boundary"))
    process_readback = _as_dict(runtime_boundary.get("process_readback"))
    foreground_session = _as_dict(runtime_boundary.get("foreground_session"))
    blocker_groups = _as_dict(implementation_plan.get("blocker_groups"))

    runtime_blockers = _as_str_list(blocker_groups.get("runtime")) or ["lens_host_runtime_not_implemented"]
    process_blockers = _as_str_list(blocker_groups.get("process_readback")) or [
        str(runtime_boundary.get("resident_host_process_blocker") or "resident_host_process_missing")
    ]
    surface_blockers = _as_str_list(blocker_groups.get("surface_dependencies"))
    authority_blockers = _as_str_list(blocker_groups.get("authority")) or [
        "resident_runtime_execution_authority_not_granted",
        "process_supervision_authority_not_granted",
        "process_restart_authority_not_granted",
        "service_install_authority_not_granted",
        "service_control_authority_not_granted",
        "tray_registration_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "overlay_control_authority_not_granted",
        "summon_authority_not_granted",
        "resident_claim_authority_not_granted",
    ]

    loop_requirements = [
        _plan_step(
            "diagnostic_status_tick",
            label="Diagnostic status tick",
            ready=bool(runtime_boundary.get("diagnostic_status_runner_ready")),
            route="/lens/host/runtime-boundary",
            source="scripts/lens-host.ps1 -Mode Status",
            blockers=["diagnostic_status_runner_missing"],
        ),
        _plan_step(
            "bounded_foreground_tick",
            label="Bounded foreground tick",
            ready=bool(runtime_boundary.get("bounded_foreground_session_available")),
            route="/lens/host/runtime-boundary",
            source="scripts/lens-host.ps1 -Mode Foreground",
            blockers=["bounded_foreground_session_missing"],
        ),
        _plan_step(
            "runtime_state_heartbeat_readback",
            label="Runtime state heartbeat readback",
            ready=bool(process_readback.get("readback_ready")),
            route="/lens/host/runtime-boundary",
            source=str(process_readback.get("runtime_state_path") or ""),
            blockers=["resident_host_runtime_state_readback_missing"],
        ),
        _plan_step(
            "resident_loop_process_supervision",
            label="Resident loop process supervision",
            ready=False,
            route="/lens/host/supervision",
            authority_required="process_supervision_authority",
            blockers=[
                *process_blockers,
                "process_supervision_authority_not_granted",
                "process_restart_authority_not_granted",
            ],
        ),
        _plan_step(
            "resident_loop_service_lifecycle",
            label="Resident loop service lifecycle",
            ready=False,
            route="/lens/host/persistent-supervision",
            authority_required="service_install_and_control_authority",
            blockers=[
                *runtime_blockers,
                "service_install_authority_not_granted",
                "service_control_authority_not_granted",
            ],
        ),
        _plan_step(
            "resident_loop_surface_presence",
            label="Resident loop surface presence",
            ready=False,
            route="/lens/preflight",
            authority_required="tray_hotkey_overlay_and_summon_authority",
            blockers=[
                *surface_blockers,
                "tray_registration_authority_not_granted",
                "hotkey_registration_authority_not_granted",
                "overlay_control_authority_not_granted",
                "summon_authority_not_granted",
            ],
        ),
        _plan_step(
            "resident_loop_receipt_emission",
            label="Resident loop receipt emission",
            ready=False,
            route="/lens/resident-runtime/execute",
            authority_required="receipt_write_authority",
            blockers=["resident_runtime_not_ready", "receipt_write_authority_not_granted"],
        ),
        _plan_step(
            "resident_loop_claim_checkpoint",
            label="Resident loop claim checkpoint",
            ready=False,
            route="/lens/host/runtime-loop",
            authority_required="resident_claim_authority",
            blockers=["resident_runtime_not_ready", "resident_claim_authority_not_granted"],
        ),
    ]

    ready_requirements = [item for item in loop_requirements if bool(item.get("ready"))]
    blocked_requirements = [str(item["id"]) for item in loop_requirements if not bool(item.get("ready"))]
    blockers = _ordered_unique(
        [
            *runtime_blockers,
            *process_blockers,
            *surface_blockers,
            *authority_blockers,
            "resident_runtime_loop_not_implemented",
            "resident_runtime_loop_not_supervised",
            "receipt_write_authority_not_granted",
        ]
    )

    return {
        "ok": True,
        "kind": "lens.host.runtime_loop_contract",
        "status": "blocked",
        "route": "/lens/host/runtime-loop",
        "runtime_plan_route": "/lens/host/runtime-plan",
        "runtime_boundary_route": "/lens/host/runtime-boundary",
        "host_route": "/lens/host",
        "supervision_route": "/lens/host/supervision",
        "resident_runtime_execute_route": "/lens/resident-runtime/execute",
        "execution_denial_route": "/lens/host/runtime-loop/execute",
        "contract_available": True,
        "loop_readback_ready": True,
        "loop_ready": False,
        "execution_ready": False,
        "resident_runtime_loop": False,
        "resident_runtime_ready": False,
        "resident_claim_allowed": False,
        "foreground_process_observed": bool(runtime_boundary.get("foreground_process_observed")),
        "foreground_session_available": bool(runtime_boundary.get("bounded_foreground_session_available")),
        "foreground_session_max_seconds": int(foreground_session.get("max_seconds") or 0),
        "resident_host_process_state": str(runtime_boundary.get("resident_host_process_state") or ""),
        "resident_host_process_blocker": str(runtime_boundary.get("resident_host_process_blocker") or ""),
        "requirements_total": len(loop_requirements),
        "requirements_ready_total": len(ready_requirements),
        "blocked_requirements": blocked_requirements,
        "blockers": blockers,
        "blocker_groups": {
            "runtime": runtime_blockers,
            "process_readback": process_blockers,
            "surface_dependencies": surface_blockers,
            "authority": authority_blockers,
            "loop": [
                "resident_runtime_loop_not_implemented",
                "resident_runtime_loop_not_supervised",
                "receipt_write_authority_not_granted",
            ],
        },
        "loop_contract": {
            "status": "blocked",
            "readback_ready": True,
            "requirements": loop_requirements,
            "would_start_loop": False,
            "would_launch_process": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_tray": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_claim_resident": False,
            "would_write_receipt": False,
            "would_write_memory": False,
            "would_decide_approval": False,
        },
        "runtime_plan": implementation_plan,
        "evidence": [
            "/lens/host/runtime-loop",
            "/lens/host/runtime-plan",
            "/lens/host/runtime-boundary",
            "/lens/host/supervision",
            "/lens/resident-runtime/execute",
        ],
        "governance": {
            "gate": "lens_host_runtime_loop_contract",
            "read_only_contract": True,
            "loop_contract_readback_only": True,
            "execution_authority": False,
            "resident_runtime_execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "diagnostic_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "mutation_authority_granted": False,
        },
        "next_smallest_truthful_gap": "resident_host_runtime_loop_execution_denial_boundary",
        "message": (
            "Lens can now read back the resident host runtime loop contract, but the loop is not implemented "
            "and this route does not start, supervise, restart, install, register, claim residency, approve, "
            "write receipts, or write memory."
        ),
    }


def _runtime_loop_execution_denial_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "denied_no_approval", "bind_runtime_loop_execution_to_exact_approval_before_any_loop_start"
    if "resident_runtime_execution_authority_not_granted" in blockers:
        return "denied_no_resident_runtime_authority", "grant_resident_runtime_execution_authority_before_loop_start"
    return "denied_no_resident_runtime_loop_boundary", "implement_supervised_resident_runtime_loop_boundary"


def deny_lens_host_runtime_loop_execution(
    *,
    actor: str | None = None,
    approval_id: str = "",
    reason: str = "attempt Lens host runtime loop execution",
    route: str = "/lens/host/runtime-loop/execute",
    method: str = "POST",
    manifest: dict[str, Any] | None = None,
    runtime_plan: dict[str, Any] | None = None,
    runtime_loop: dict[str, Any] | None = None,
) -> dict[str, Any]:
    loop_contract = (
        runtime_loop
        if isinstance(runtime_loop, dict)
        else lens_host_runtime_loop_contract(manifest=manifest, runtime_plan=runtime_plan)
    )
    approval_id_value = str(approval_id or "").strip()
    actor_value = str(actor or "").strip()
    blockers = _ordered_unique(
        [
            *([] if approval_id_value else ["approval_id_required"]),
            *_as_str_list(loop_contract.get("blockers")),
            "resident_runtime_loop_execution_not_authorized",
            "resident_runtime_loop_execution_boundary_not_implemented",
            "receipt_write_authority_not_granted",
            "resident_claim_authority_not_granted",
        ]
    )
    status, next_step = _runtime_loop_execution_denial_status(blockers)

    return {
        "ok": True,
        "kind": "lens.host.runtime_loop.execution_denial",
        "status": status,
        "route": route,
        "method": method.upper(),
        "runtime_loop_route": "/lens/host/runtime-loop",
        "runtime_plan_route": "/lens/host/runtime-plan",
        "runtime_boundary_route": "/lens/host/runtime-boundary",
        "supervision_route": "/lens/host/supervision",
        "approval_id": approval_id_value,
        "actor": actor_value,
        "reason": str(reason or "").strip(),
        "applied": False,
        "executed": False,
        "loop_started": False,
        "resident_runtime_loop": False,
        "resident_runtime_ready": False,
        "resident_claim_allowed": False,
        "foreground_process_observed": bool(loop_contract.get("foreground_process_observed")),
        "resident_host_process_state": str(loop_contract.get("resident_host_process_state") or ""),
        "resident_host_process_blocker": str(loop_contract.get("resident_host_process_blocker") or ""),
        "blockers": blockers,
        "denial": {
            "reason": status,
            "next_step": next_step,
            "would_start_loop": False,
            "would_launch_process": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_tray": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_claim_resident": False,
            "would_write_receipt": False,
            "would_write_memory": False,
            "would_decide_approval": False,
            "denial_receipt_written": False,
        },
        "proof": {
            "contract_status": str(loop_contract.get("status") or ""),
            "loop_readback_ready": bool(loop_contract.get("loop_readback_ready")),
            "loop_ready": bool(loop_contract.get("loop_ready")),
            "execution_ready": bool(loop_contract.get("execution_ready")),
            "resident_runtime_loop": bool(loop_contract.get("resident_runtime_loop")),
            "resident_runtime_ready": bool(loop_contract.get("resident_runtime_ready")),
            "resident_claim_allowed": bool(loop_contract.get("resident_claim_allowed")),
            "requirements_total": int(loop_contract.get("requirements_total") or 0),
            "requirements_ready_total": int(loop_contract.get("requirements_ready_total") or 0),
            "blocked_requirements": _as_str_list(loop_contract.get("blocked_requirements")),
        },
        "runtime_loop_contract": loop_contract,
        "receipt_written": False,
        "receipt_route": "",
        "receipt": {},
        "evidence": [
            "/lens/host/runtime-loop/execute",
            "/lens/host/runtime-loop",
            "/lens/host/runtime-plan",
            "/lens/host/runtime-boundary",
            "/lens/host/supervision",
        ],
        "governance": {
            "gate": "lens_host_runtime_loop_execution_denial_boundary",
            "execution_boundary": True,
            "denial_boundary": True,
            "read_only_contract": True,
            "execution_authority": False,
            "resident_runtime_execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "local_process_launch_authority": False,
            "diagnostic_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "mutation_authority_granted": False,
        },
        "next_smallest_truthful_gap": "resident_host_runtime_loop_denial_receipt_readback",
        "message": (
            "Lens can deny resident host runtime loop execution attempts, but this boundary does not start "
            "a loop, launch or supervise a process, control services or surfaces, claim residency, decide "
            "approvals, write receipts, or write memory."
        ),
    }
