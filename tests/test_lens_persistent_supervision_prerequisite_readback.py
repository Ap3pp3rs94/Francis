from __future__ import annotations

from typing import Any

import pytest

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
    surface_dependencies: list[str] | None = None,
    activation_execution_readback: dict[str, Any] | None = None,
    supervision_execution_readback: dict[str, Any] | None = None,
    supervisor_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    process_blockers = [process_blocker] if process_blocker else []
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
        "supervision_execution_readback": supervision_execution_readback or {},
        "supervisor_readback": supervisor_readback or {},
        "blocker_groups": {
            "process_readback": process_blockers,
            "surface_dependencies": surface_dependencies
            if surface_dependencies is not None
            else [
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
        assert handoff["authority_route"] == "/lens/host/activation/authority"
        assert handoff["authority_request_route"] == "/lens/host/activation/request"
        assert handoff["authority_readback_route"] == "/lens/host/activation"
        assert handoff["authority_preflight_route"] == "/lens/host/activation/preflight"
        assert handoff["authority_plan_route"] == "/lens/host/activation/plan"
        assert handoff["authority_execute_route"] == "/lens/host/activation/execute"
        assert handoff["authority_executions_route"] == "/lens/host/activation/executions"
        assert handoff["authority_grants_route"] == "/lens/host/activation/authority/grants"
        assert handoff["execution_denials_route"] == "/lens/host/activation/denials"
        assert handoff["approval_action"] == "lens.host.foreground_activation"
        assert handoff["authority_scope"] == "system.write"
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
        assert body["first_missing_requirement_handoff"]["proof_script"] == (
            "scripts/lens-resident-host-process-supervision-blocker-proof.ps1 -Mode Status"
        )
        assert body["first_missing_requirement_handoff"]["next_step"] == (
            "consume_resident_host_process_supervision_handoff_before_stage6_closure"
        )
        assert body["first_missing_requirement_handoff"]["authority_route"] == "/lens/host/activation/authority"
        assert body["first_missing_requirement_handoff"]["authority_request_route"] == "/lens/host/activation/request"
        assert body["first_missing_requirement_handoff"]["approval_action"] == "lens.host.foreground_activation"
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
        assert (
            handoff["proof_script"] == "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
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
        assert handoff["persistent_supervision_route"] == "/lens/host/persistent-supervision"
        assert handoff["persistent_supervision_enablement_route"] == "/lens/host/persistent-supervision/enablement"
        assert handoff["persistent_supervision_enablement_authority_route"] == (
            "/lens/host/persistent-supervision/enablement/authority"
        )
        assert handoff["persistent_supervision_enablement_authority_request_route"] == (
            "/lens/host/persistent-supervision/enablement/authority/request"
        )
        assert handoff["persistent_supervision_enablement_authority_requests_route"] == (
            "/lens/host/persistent-supervision/enablement/authority/requests"
        )
        assert handoff["persistent_supervision_enablement_authority_readiness_route"] == (
            "/lens/host/persistent-supervision/enablement/authority/readiness"
        )
        assert handoff["persistent_supervision_enablement_authority_grants_route"] == (
            "/lens/host/persistent-supervision/enablement/authority/grants"
        )
        assert handoff["persistent_supervision_enablement_execution_route"] == (
            "/lens/host/persistent-supervision/enablement/execution"
        )
        assert handoff["persistent_supervision_enablement_execution_request_route"] == (
            "/lens/host/persistent-supervision/enablement/execution/request"
        )
        assert handoff["persistent_supervision_enablement_execution_requests_route"] == (
            "/lens/host/persistent-supervision/enablement/execution/requests"
        )
        assert handoff["persistent_supervision_enablement_execution_readiness_route"] == (
            "/lens/host/persistent-supervision/enablement/execution/readiness"
        )
        assert handoff["persistent_supervision_enablement_execution_authority_route"] == (
            "/lens/host/persistent-supervision/enablement/execution/authority"
        )
        assert handoff["persistent_supervision_enablement_execution_authority_grants_route"] == (
            "/lens/host/persistent-supervision/enablement/execution/authority/grants"
        )
        assert handoff["persistent_supervision_enablement_executions_route"] == (
            "/lens/host/persistent-supervision/enablement/executions"
        )
        assert handoff["persistent_supervision_next_smallest_truthful_gap"] == (
            "persistent_supervision_authority_not_granted"
        )
        assert handoff["persistent_supervision_enablement_authority_action"] == (
            "lens.host.persistent_supervision_enablement_authority"
        )
        assert handoff["persistent_supervision_enablement_execution_action"] == (
            "lens.host.persistent_supervision_enablement_execution_authority"
        )
        assert handoff["persistent_supervision_authority_scope"] == "system.write"
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


def test_persistent_supervision_prerequisite_readback_preserves_supervision_receipt_after_freshness() -> None:
    manifest = _manifest(
        process_alive=False,
        process_blocker="resident_host_process_missing",
        supervisor_readback={
            "resident_runtime_candidate_supervised": True,
            "fresh_resident_runtime_candidate_supervised": False,
            "freshness_status": "stale",
            "state_age_seconds": 1200,
        },
        supervision_execution_readback={
            "status": "readback_ready",
            "route": "/lens/host/supervision/executions",
            "execute_route": "/lens/host/supervision/execute",
            "receipt_count": 1,
            "latest_receipt_id": "lhse_test_receipt",
            "latest_status": "resident_candidate_supervised_not_persistent",
            "latest_bounded_supervised_session": True,
            "latest_temporary_host_process_observed": True,
            "latest_resident_runtime_candidate_supervised": True,
            "latest_resident_supervised_runtime": False,
            "latest_next_smallest_truthful_gap": "resident_supervision_not_persistent",
            "resident_runtime_candidate_receipt_observed": True,
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
        assert handoff["next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        assert (
            handoff["proof_script"] == "scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status"
        )
        assert handoff["supervision_execution_receipt_observed"] is True
        assert handoff["supervision_execution_receipt_id"] == "lhse_test_receipt"
        assert handoff["fresh_resident_runtime_candidate_supervised"] is False
        assert handoff["resident_runtime_candidate_supervised"] is True

        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["requirement_state"] == "resident_candidate_observed_not_persistent"
        assert dependency["blocker"] == "resident_supervision_not_persistent"
        assert dependency["supervision_execution_receipt_observed"] is True
        assert dependency["supervision_execution_receipt_id"] == "lhse_test_receipt"
        assert dependency["supervision_execution_next_smallest_truthful_gap"] == "resident_supervision_not_persistent"
        assert dependency["fresh_resident_runtime_candidate_supervised"] is False
        assert dependency["resident_runtime_candidate_supervised"] is True


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


@pytest.mark.parametrize(
    (
        "requirement_id",
        "surface_dependencies",
        "expected_readback_route",
        "expected_readiness_route",
        "expected_proof_script",
        "expected_config_path",
        "expected_blocker",
        "expected_next_gap",
    ),
    [
        (
            "tray_presence",
            [
                "tray_host_missing",
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
            "/lens/tray",
            "/lens/tray/readiness",
            "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
            "config/runtime/lens/tray.json",
            "tray_host_missing",
            "summon_tray_presence_blocker_boundary",
        ),
        (
            "global_hotkey_binding",
            [
                "global_hotkey_binding_missing",
                "overlay_window_missing",
                "summon_binding_missing",
            ],
            "/lens/summon",
            "/lens/summon/readiness",
            "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
            "config/runtime/lens/summon.json",
            "global_hotkey_binding_missing",
            "os_level_command_palette_binding",
        ),
        (
            "overlay_window",
            [
                "overlay_window_missing",
                "summon_binding_missing",
            ],
            "/lens/overlay",
            "/lens/overlay/readiness",
            "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
            "config/runtime/lens/overlay.json",
            "overlay_window_missing",
            "summon_overlay_window_blocker_boundary",
        ),
        (
            "summon_binding",
            ["summon_binding_missing"],
            "/lens/summon",
            "/lens/summon/readiness",
            "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
            "config/runtime/lens/summon.json",
            "summon_binding_missing",
            "summon_anywhere_blockers",
        ),
    ],
)
def test_persistent_supervision_prerequisite_handoff_routes_remaining_family_gates(
    requirement_id: str,
    surface_dependencies: list[str],
    expected_readback_route: str,
    expected_readiness_route: str,
    expected_proof_script: str,
    expected_config_path: str,
    expected_blocker: str,
    expected_next_gap: str,
) -> None:
    manifest = _manifest(process_alive=True, process_blocker="", surface_dependencies=surface_dependencies)

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        handoff = body["first_missing_requirement_handoff"]
        assert body["first_missing_required_before_enable"] == requirement_id
        assert handoff["id"] == requirement_id
        assert handoff["route"] == expected_readback_route
        assert handoff["readback_route"] == expected_readback_route
        assert handoff["readiness_route"] == expected_readiness_route
        assert handoff["proof_script"] == expected_proof_script
        assert handoff["preflight_route"] == "/lens/preflight"
        assert handoff["config_path"] == expected_config_path
        assert handoff["blocker"] == expected_blocker
        assert handoff["next_smallest_truthful_gap"] == expected_next_gap
        assert handoff["family_blockers"]
        assert handoff["read_only_contract"] is True
        assert handoff["diagnostic_only"] is True
        assert handoff["would_execute"] is False
        assert handoff["would_mutate"] is False


def test_persistent_supervision_prerequisite_handoff_promotes_os_binding_review_for_hotkey() -> None:
    manifest = _manifest(
        process_alive=True,
        process_blocker="",
        surface_dependencies=[
            "global_hotkey_binding_missing",
            "overlay_window_missing",
            "summon_binding_missing",
        ],
    )

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        handoff = body["first_missing_requirement_handoff"]
        assert handoff["id"] == "global_hotkey_binding"
        assert handoff["os_binding_readiness_route"] == "/lens/os-binding/readiness"
        assert handoff["os_binding_plan_route"] == "/lens/os-binding/plan"
        assert handoff["os_binding_authority_route"] == "/lens/os-binding/authority"
        assert handoff["os_binding_authority_request_route"] == "/lens/os-binding/authority/request"
        assert handoff["os_binding_authority_requests_route"] == "/lens/os-binding/authority/requests"
        assert handoff["os_binding_authority_grants_route"] == "/lens/os-binding/authority/grants"
        assert handoff["os_binding_execution_readiness_route"] == "/lens/os-binding/execution/readiness"
        assert handoff["os_binding_execution_denials_route"] == "/lens/os-binding/denials"
        assert handoff["approval_action"] == "lens.os_binding.command_palette_binding_authority"
        assert handoff["authority_scope"] == "system.write"
        assert handoff["read_only_contract"] is True
        assert handoff["diagnostic_only"] is True
        assert handoff["would_execute"] is False
        assert handoff["would_mutate"] is False


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
