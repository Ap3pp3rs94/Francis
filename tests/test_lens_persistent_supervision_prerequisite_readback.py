from __future__ import annotations

from typing import Any

from francis.lens.host_manifest import (
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_persistent_supervision_plan,
)


REQUIRED_BEFORE_ENABLE = [
    "resident_host_process",
    "tray_presence",
    "global_hotkey_binding",
    "overlay_window",
    "summon_binding",
]


def _manifest(
    *,
    process_alive: bool,
    process_blocker: str,
    activation_execution_readback: dict[str, Any] | None = None,
    supervisor_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "required_before_enable": REQUIRED_BEFORE_ENABLE,
        "declared_entrypoint": {"exists": True},
        "service_install": {
            "config_exists": True,
            "manager_exists": True,
            "service_name": "Francis-LensHost",
        },
        "service_plan": {"status": "blocked"},
        "service_readback": {"status": "not_checked_by_api"},
        "supervision_readiness": {
            "process_supervision_enabled": False,
            "persistent_supervision_enabled": False,
        },
        "process_readback": {
            "process_alive": process_alive,
            "blocked_reason": process_blocker,
        },
        "activation_execution_readback": activation_execution_readback or {},
        "supervisor_readback": supervisor_readback or {},
        "blocker_groups": {
            "process_readback": [process_blocker],
            "surface_dependencies": [
                "tray_host_missing",
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
        },
    }


def _dependency_by_id(body: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["id"]: item for item in body["enablement_dependency_readback"]}


def test_persistent_supervision_prerequisite_readback_reports_missing_process() -> None:
    manifest = _manifest(process_alive=False, process_blocker="resident_host_process_missing")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        assert body["first_missing_required_before_enable"] == "resident_host_process"
        handoff = body["first_missing_requirement_handoff"]
        assert handoff["id"] == "resident_host_process"
        assert handoff["family"] == "resident_host"
        assert handoff["route"] == "/lens/host"
        assert handoff["readiness_route"] == "/lens/host/runtime-loop/readiness"
        assert handoff["proof_script"] == "scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status"
        assert handoff["blocker"] == "resident_host_process_missing"
        assert handoff["requirement_state"] == "missing"
        assert handoff["next_step"] == "resolve_resident_host_process_before_persistent_supervision_enablement"
        assert handoff["next_smallest_truthful_gap"] == "resident_host_process_not_supervised"
        assert handoff["read_only_contract"] is True
        assert handoff["diagnostic_only"] is True
        assert handoff["would_execute"] is False
        assert handoff["would_mutate"] is False
        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["family"] == "resident_host"
        assert dependency["route"] == "/lens/host"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "resident_host_process_missing"
        assert dependency["requirement_state"] == "missing"
        assert dependency["process_alive"] is False
        assert dependency["blocked_reason"] == "resident_host_process_missing"


def test_persistent_supervision_prerequisite_readback_links_bounded_activation_receipt() -> None:
    manifest = _manifest(
        process_alive=False,
        process_blocker="resident_host_process_missing",
        activation_execution_readback={
            "status": "readback_ready",
            "route": "/lens/host/activation/executions",
            "execute_route": "/lens/host/activation/execute",
            "receipt_count": 1,
            "latest_receipt_id": "lhae_123_test",
            "latest_status": "bounded_foreground_launch_observed",
            "latest_runner_status": "launch_started",
            "latest_observed_process": True,
            "latest_observed_pid": 456,
            "bounded_activation_execution_observed": True,
            "resident_host_process_claimed": False,
            "resident_claim_authority": False,
        },
    )

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        assert body["first_missing_required_before_enable"] == "resident_host_process"
        assert body["first_missing_requirement_handoff"]["blocker"] == "resident_host_process_missing"
        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "resident_host_process_missing"
        assert dependency["requirement_state"] == "missing"
        assert dependency["process_alive"] is False
        assert dependency["activation_execution_route"] == "/lens/host/activation/executions"
        assert dependency["activation_execution_execute_route"] == "/lens/host/activation/execute"
        assert dependency["activation_execution_readback_status"] == "readback_ready"
        assert dependency["activation_execution_receipt_count"] == 1
        assert dependency["activation_execution_receipt_id"] == "lhae_123_test"
        assert dependency["activation_execution_status"] == "bounded_foreground_launch_observed"
        assert dependency["activation_execution_runner_status"] == "launch_started"
        assert dependency["activation_execution_observed_process"] is True
        assert dependency["activation_execution_observed_pid"] == 456
        assert dependency["bounded_activation_execution_observed"] is True
        assert dependency["activation_execution_evidence_only"] is True
        assert dependency["activation_execution_does_not_satisfy_resident_host_process"] is True
        assert dependency["resident_host_process_claimed"] is False
        assert dependency["resident_claim_allowed"] is False
        assert dependency["resident_claim_authority"] is False


def test_persistent_supervision_prerequisite_readback_distinguishes_unsupervised_process() -> None:
    manifest = _manifest(process_alive=True, process_blocker="resident_host_not_supervised")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        assert body["missing_required_before_enable"] == REQUIRED_BEFORE_ENABLE
        assert body["first_missing_required_before_enable"] == "resident_host_process"
        assert body["first_missing_requirement_handoff"]["blocker"] == "resident_host_process_not_supervised"
        assert body["first_missing_requirement_handoff"]["requirement_state"] == "foreground_observed_not_supervised"
        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["route"] == "/lens/host"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "resident_host_process_not_supervised"
        assert dependency["requirement_state"] == "foreground_observed_not_supervised"
        assert dependency["process_alive"] is True
        assert dependency["blocked_reason"] == "resident_host_not_supervised"


def test_persistent_supervision_prerequisite_readback_links_persistent_process_authority_review() -> None:
    manifest = _manifest(
        process_alive=False,
        process_blocker="resident_host_process_missing",
        supervisor_readback={
            "resident_runtime_candidate_supervised": True,
            "fresh_resident_runtime_candidate_supervised": True,
            "freshness_status": "fresh",
            "state_age_seconds": 3,
        },
    )

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        handoff = body["first_missing_requirement_handoff"]
        assert handoff["id"] == "resident_host_process"
        assert handoff["requirement_state"] == "resident_candidate_observed_not_persistent"
        assert handoff["blocker"] == "resident_supervision_not_persistent"
        assert (
            handoff["next_step"] == "resolve_resident_supervision_persistence_before_persistent_supervision_enablement"
        )
        assert handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        assert handoff["authority_required"] == "persistent_process_supervision_authority"
        assert handoff["authority_route"] == "/lens/host/supervision/authority"
        assert handoff["authority_request_route"] == "/lens/host/supervision/authority/request"
        assert handoff["authority_requests_route"] == "/lens/host/supervision/authority/requests"
        assert handoff["authority_readiness_route"] == "/lens/host/supervision/authority/readiness"
        assert handoff["authority_grants_route"] == "/lens/host/supervision/authority/grants"
        assert handoff["authority_denials_route"] == "/lens/host/supervision/authority/denials"
        assert handoff["approval_action"] == "lens.host.supervision_authority"
        assert handoff["read_only_contract"] is True
        assert handoff["diagnostic_only"] is True
        assert handoff["would_execute"] is False
        assert handoff["would_mutate"] is False

        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["blocker"] == "resident_supervision_not_persistent"
        assert dependency["requirement_state"] == "resident_candidate_observed_not_persistent"
        assert dependency["fresh_resident_runtime_candidate_supervised"] is True
        assert dependency["resident_runtime_candidate_supervised"] is True
        assert dependency["resident_supervised_runtime"] is False


def test_persistent_supervision_prerequisite_readback_reports_tray_presence_gate() -> None:
    manifest = _manifest(process_alive=False, process_blocker="resident_host_process_missing")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        dependency = _dependency_by_id(body)["tray_presence"]
        assert dependency["route"] == "/lens/tray"
        assert dependency["readiness_route"] == "/lens/tray/readiness"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "tray_host_missing"
        assert dependency["requirement_state"] == "tray_host_disabled"
        assert dependency["blocked_reason"] == "lens_tray_presence_not_implemented"
        assert dependency["config_path"] == "config/runtime/lens/tray.json"
        assert dependency["config_exists"] is True
        assert dependency["presence_name"] == "Francis Lens Tray Presence"
        assert dependency["tray_scope"] == "user_session"
        assert dependency["tray_host_enabled"] is False
        assert dependency["tray_icon_enabled"] is False
        assert dependency["startup_register"] is False
        assert dependency["tray_registration_authority"] is False
        assert dependency["tray_icon_authority"] is False
        assert dependency["notification_authority"] is False
        assert dependency["family_blockers"] == [
            "lens_tray_presence_not_implemented",
            "tray_host_disabled",
            "tray_icon_disabled",
            "tray_startup_registration_disabled",
            "tray_registration_authority_not_granted",
            "tray_icon_authority_not_granted",
            "notification_authority_not_granted",
        ]


def test_persistent_supervision_prerequisite_readback_reports_global_hotkey_gate() -> None:
    manifest = _manifest(process_alive=False, process_blocker="resident_host_process_missing")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        dependency = _dependency_by_id(body)["global_hotkey_binding"]
        assert dependency["route"] == "/lens/summon"
        assert dependency["readiness_route"] == "/lens/summon/readiness"
        assert dependency["preflight_script"] == "scripts/lens-summon-preflight.ps1 -Mode Status"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "global_hotkey_binding_missing"
        assert dependency["requirement_state"] == "binding_disabled"
        assert dependency["blocked_reason"] == "global_hotkey_binding_disabled"
        assert dependency["config_path"] == "config/runtime/lens/summon.json"
        assert dependency["config_exists"] is True
        assert dependency["global_hotkey"] == "Ctrl+Alt+Space"
        assert dependency["binding_scope"] == "global"
        assert dependency["palette_route"] == "/lens/status"
        assert dependency["binding_enabled"] is False
        assert dependency["register_hotkey"] is False
        assert dependency["startup_register"] is False
        assert dependency["hotkey_registration_authority"] is False
        assert dependency["summon_authority"] is False
        assert dependency["family_blockers"] == [
            "global_hotkey_binding_disabled",
            "global_hotkey_registration_disabled",
            "hotkey_registration_authority_not_granted",
        ]


def test_persistent_supervision_prerequisite_readback_reports_overlay_window_gate() -> None:
    manifest = _manifest(process_alive=False, process_blocker="resident_host_process_missing")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        dependency = _dependency_by_id(body)["overlay_window"]
        assert dependency["route"] == "/lens/overlay"
        assert dependency["readiness_route"] == "/lens/overlay/readiness"
        assert dependency["preflight_script"] == "scripts/lens-overlay-preflight.ps1 -Mode Status"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "overlay_window_missing"
        assert dependency["requirement_state"] == "window_disabled"
        assert dependency["blocked_reason"] == "lens_overlay_window_not_implemented"
        assert dependency["config_path"] == "config/runtime/lens/overlay.json"
        assert dependency["config_exists"] is True
        assert dependency["overlay_name"] == "Francis Lens Overlay"
        assert dependency["overlay_scope"] == "user_session"
        assert dependency["status_route"] == "/lens/status"
        assert dependency["host_route"] == "/lens/host"
        assert dependency["required_before_enable"] == [
            "resident_host_process",
            "tray_presence",
            "overlay_window",
            "always_on_top_policy",
            "global_hotkey_binding",
            "summon_binding",
        ]
        assert dependency["overlay_enabled"] is False
        assert dependency["window_enabled"] is False
        assert dependency["always_on_top"] is False
        assert dependency["dock_supported"] is False
        assert dependency["focus_supported"] is False
        assert dependency["click_through_supported"] is False
        assert dependency["capture_supported"] is False
        assert dependency["overlay_control_authority"] is False
        assert dependency["window_management_authority"] is False
        assert dependency["local_process_launch_authority"] is False
        assert dependency["capture_authority"] is False
        assert dependency["summon_authority"] is False
        assert dependency["tray_registration_authority"] is False
        assert dependency["family_blockers"] == [
            "lens_overlay_window_not_implemented",
            "overlay_window_disabled",
            "always_on_top_disabled",
            "overlay_dock_not_supported",
            "overlay_focus_not_supported",
            "overlay_click_through_not_supported",
            "overlay_control_authority_not_granted",
            "window_management_authority_not_granted",
            "local_process_launch_authority_not_granted",
            "capture_authority_not_granted",
            "summon_authority_not_granted",
            "tray_registration_authority_not_granted",
        ]


def test_persistent_supervision_prerequisite_readback_reports_summon_binding_gate() -> None:
    manifest = _manifest(process_alive=False, process_blocker="resident_host_process_missing")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        dependency = _dependency_by_id(body)["summon_binding"]
        assert dependency["route"] == "/lens/summon"
        assert dependency["readiness_route"] == "/lens/summon/readiness"
        assert dependency["preflight_script"] == "scripts/lens-summon-preflight.ps1 -Mode Status"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "summon_binding_missing"
        assert dependency["requirement_state"] == "not_implemented"
        assert dependency["blocked_reason"] == "lens_summon_binding_not_implemented"
        assert dependency["config_path"] == "config/runtime/lens/summon.json"
        assert dependency["config_exists"] is True
        assert dependency["summon_name"] == "Francis Lens Summon"
        assert dependency["acceptance_criterion"] == "summon_anywhere"
        assert dependency["next_smallest_truthful_gap"] == "summon_anywhere_blockers"
        assert dependency["global_hotkey"] == "Ctrl+Alt+Space"
        assert dependency["binding_scope"] == "global"
        assert dependency["palette_route"] == "/lens/status"
        assert dependency["required_before_enable"] == [
            "resident_host_process",
            "tray_presence",
            "overlay_window",
            "global_hotkey_binding",
            "summon_binding",
        ]
        assert dependency["host_preflight"] == "scripts/lens-host-preflight.ps1"
        assert dependency["host_preflight_exists"] is True
        assert dependency["host_status_runner"] == "scripts/lens-host.ps1"
        assert dependency["host_status_runner_exists"] is True
        assert dependency["launch_target"] == "lens_host"
        assert dependency["launch_mode"] == "Foreground"
        assert dependency["summon_enabled"] is False
        assert dependency["binding_enabled"] is False
        assert dependency["register_hotkey"] is False
        assert dependency["startup_register"] is False
        assert dependency["overlay_required"] is True
        assert dependency["tray_required"] is True
        assert dependency["summon_authority"] is False
        assert dependency["hotkey_registration_authority"] is False
        assert dependency["overlay_control_authority"] is False
        assert dependency["local_process_launch_authority"] is False
        assert dependency["family_blockers"] == [
            "lens_summon_binding_not_implemented",
            "summon_authority_not_granted",
        ]
        assert dependency["host_dependency_blockers"] == [
            "local_process_launch_authority_not_granted",
        ]
        assert dependency["surface_dependency_blockers"] == [
            "overlay_window_missing",
            "tray_host_missing",
        ]
        assert dependency["authority_blockers"] == [
            "summon_authority_not_granted",
            "local_process_launch_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
        ]
