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


def _manifest(*, process_alive: bool, process_blocker: str) -> dict[str, Any]:
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
        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["route"] == "/lens/host"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "resident_host_process_missing"
        assert dependency["requirement_state"] == "missing"
        assert dependency["process_alive"] is False
        assert dependency["blocked_reason"] == "resident_host_process_missing"


def test_persistent_supervision_prerequisite_readback_distinguishes_unsupervised_process() -> None:
    manifest = _manifest(process_alive=True, process_blocker="resident_host_not_supervised")

    for body in (
        lens_host_persistent_supervision_plan(manifest=manifest),
        lens_host_persistent_supervision_enablement_preflight(manifest=manifest),
    ):
        assert body["missing_required_before_enable"] == REQUIRED_BEFORE_ENABLE
        dependency = _dependency_by_id(body)["resident_host_process"]
        assert dependency["route"] == "/lens/host"
        assert dependency["ready"] is False
        assert dependency["status"] == "blocked"
        assert dependency["blocker"] == "resident_host_process_not_supervised"
        assert dependency["requirement_state"] == "foreground_observed_not_supervised"
        assert dependency["process_alive"] is True
        assert dependency["blocked_reason"] == "resident_host_not_supervised"


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
