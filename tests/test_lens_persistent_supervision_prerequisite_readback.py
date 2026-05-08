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
