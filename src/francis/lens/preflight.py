from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.lens.errors import lens_error_code
from francis.kernel.paths import data_dir, repo_root
from francis.lens.host_manifest import _process_alive_readback, lens_host_launch_manifest


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        parsed = str(value)
    except Exception:
        return default
    return parsed if parsed.strip() else default


def _int_value(value: Any) -> int:
    if isinstance(value, bool):
        return 0
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _runtime_file_exists(relative_path: str) -> bool:
    try:
        return (repo_root() / Path(relative_path)).is_file()
    except OSError:
        return False


def _runtime_state_exists() -> bool:
    runtime_root = data_dir() / "runtime" / "lens-host"
    try:
        return (runtime_root / "status.json").is_file() or (runtime_root / "lens-host.pid").is_file()
    except OSError:
        return False


def _read_config(relative_path: str) -> tuple[dict[str, Any], bool, str]:
    path = repo_root() / Path(relative_path)
    try:
        if not path.is_file():
            return {}, False, ""
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, True, lens_error_code(exc, code="lens_config_read_error", surface=relative_path)
    return (payload if isinstance(payload, dict) else {}), True, "" if isinstance(payload, dict) else "not_json_object"


def _json_dict_from_path(path: Path) -> dict[str, Any]:
    try:
        if not path.is_file():
            return {}
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _pid_from_file(path: Path) -> int:
    try:
        raw = path.read_text(encoding="utf-8-sig").strip()
    except OSError:
        return 0
    try:
        parsed = int(raw)
    except ValueError:
        return 0
    return max(parsed, 0)


def _path_exists(path: Path) -> bool:
    try:
        return path.is_file()
    except OSError:
        return False


def _tray_runtime_readback() -> dict[str, Any]:
    runtime_root = data_dir() / "runtime" / "lens-tray"
    state_file = runtime_root / "status.json"
    pid_file = runtime_root / "lens-tray.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = _safe_str(state_payload.get("kind"))
    state_status = _safe_str(state_payload.get("status"))
    state_pid = _int_value(state_payload.get("pid"))
    state_claims_running_tray = (
        state_kind == "lens.tray.runtime_state"
        and state_status == "tray_running"
        and state_pid > 0
        and state_pid == pid
    )
    if state_claims_running_tray:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.tray.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "tray_running":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_running"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_mismatch"
    tray_icon_visible = process_alive and _bool(state_payload.get("tray_icon_visible"))
    requirement_state = (
        "running"
        if tray_icon_visible
        else "process_running_no_icon_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    blocker = (
        "" if tray_icon_visible else "tray_icon_not_observed" if process_alive else "tray_presence_runtime_missing"
    )
    return {
        "ready": tray_icon_visible,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "tray_icon_visible": tray_icon_visible,
        "pid": pid,
        "pid_present": pid_present,
        "status_path": "data/runtime/lens-tray/status.json",
        "pid_path": "data/runtime/lens-tray/lens-tray.pid",
        "runtime_state_exists": state_exists,
        "runtime_status": state_status,
        "runtime_status_kind": state_kind,
        "runtime_status_pid": state_pid,
        "runtime_status_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "runtime_state_updated_at": _safe_str(state_payload.get("updated_at")),
        "requirement_state": requirement_state,
        "blocker": blocker,
    }


def _tray_runtime_gate_readback(readback: dict[str, Any]) -> dict[str, Any]:
    return {
        "ready": bool(readback.get("ready")),
        "process_alive": bool(readback.get("process_alive")),
        "process_alive_check": _safe_str(readback.get("process_alive_check")),
        "tray_icon_visible": bool(readback.get("tray_icon_visible")),
        "pid": _int_value(readback.get("pid")),
        "pid_present": bool(readback.get("pid_present")),
        "status_path": _safe_str(
            readback.get("status_path") or readback.get("runtime_state_path"),
            "data/runtime/lens-tray/status.json",
        ),
        "pid_path": _safe_str(readback.get("pid_path"), "data/runtime/lens-tray/lens-tray.pid"),
        "runtime_state_exists": bool(readback.get("runtime_state_exists") or readback.get("state_exists")),
        "runtime_status": _safe_str(readback.get("runtime_status") or readback.get("state_status")),
        "runtime_status_kind": _safe_str(readback.get("runtime_status_kind") or readback.get("state_kind")),
        "runtime_status_pid": _int_value(readback.get("runtime_status_pid") or readback.get("state_pid")),
        "runtime_status_pid_matches_pid_file": bool(
            readback.get("runtime_status_pid_matches_pid_file") or readback.get("state_pid_matches_pid_file")
        ),
        "runtime_state_updated_at": _safe_str(
            readback.get("runtime_state_updated_at") or readback.get("state_updated_at")
        ),
        "requirement_state": _safe_str(readback.get("requirement_state"), "missing"),
        "blocker": _safe_str(readback.get("blocker")),
    }


def _hotkey_runtime_readback(
    *,
    global_hotkey: str,
    binding_scope: str,
    config_source: str = "canonical_config",
) -> dict[str, Any]:
    runtime_root = data_dir() / "runtime" / "lens-hotkey"
    state_file = runtime_root / "status.json"
    pid_file = runtime_root / "lens-hotkey.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = _safe_str(state_payload.get("kind"))
    state_status = _safe_str(state_payload.get("status"))
    state_pid = _int_value(state_payload.get("pid"))
    state_claims_bound_hotkey = (
        state_kind == "lens.hotkey.runtime_state"
        and state_status == "hotkey_bound"
        and state_pid > 0
        and state_pid == pid
        and _bool(state_payload.get("hotkey_bound"))
        and _safe_str(state_payload.get("global_hotkey")) == global_hotkey
        and _safe_str(state_payload.get("binding_scope")) == binding_scope
    )
    if state_claims_bound_hotkey:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.hotkey.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "hotkey_bound":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_bound"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_or_binding_mismatch"
    ready = process_alive and state_claims_bound_hotkey
    requirement_state = (
        "bound"
        if ready
        else "process_running_no_bound_hotkey_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    return {
        "ready": ready,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "hotkey_bound": ready,
        "pid": pid,
        "pid_present": pid_present,
        "status_path": "data/runtime/lens-hotkey/status.json",
        "pid_path": "data/runtime/lens-hotkey/lens-hotkey.pid",
        "config_source": config_source,
        "config_override_path": "data/runtime/lens-hotkey/os-binding-summon-override.json"
        if config_source == "runtime_override"
        else "",
        "runtime_state_exists": state_exists,
        "runtime_status": state_status,
        "runtime_status_kind": state_kind,
        "runtime_status_pid": state_pid,
        "runtime_status_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "runtime_state_updated_at": _safe_str(state_payload.get("updated_at")),
        "global_hotkey": _safe_str(state_payload.get("global_hotkey")),
        "expected_global_hotkey": global_hotkey,
        "binding_scope": _safe_str(state_payload.get("binding_scope")),
        "expected_binding_scope": binding_scope,
        "launch_on_hotkey": _bool(state_payload.get("launch_on_hotkey")),
        "summon_runner": _safe_str(state_payload.get("summon_runner")),
        "press_count": _int_value(state_payload.get("press_count")),
        "requirement_state": requirement_state,
        "blocker": "" if ready else "global_hotkey_binding_runtime_missing",
    }


def _hotkey_runtime_override_config() -> dict[str, Any]:
    path = data_dir() / "runtime" / "lens-hotkey" / "os-binding-summon-override.json"
    return _json_dict_from_path(path) if _path_exists(path) else {}


def _overlay_runtime_readback(*, overlay_name: str, overlay_scope: str) -> dict[str, Any]:
    runtime_root = data_dir() / "runtime" / "lens-overlay"
    state_file = runtime_root / "status.json"
    pid_file = runtime_root / "lens-overlay.pid"
    state_exists = _path_exists(state_file)
    pid_present = _path_exists(pid_file)
    pid = _pid_from_file(pid_file) if pid_present else 0
    state_payload = _json_dict_from_path(state_file) if state_exists else {}
    state_kind = _safe_str(state_payload.get("kind"))
    state_status = _safe_str(state_payload.get("status"))
    state_pid = _int_value(state_payload.get("pid"))
    state_claims_running_overlay = (
        state_kind == "lens.overlay.runtime_state"
        and state_status == "overlay_running"
        and state_pid > 0
        and state_pid == pid
        and _safe_str(state_payload.get("overlay_name")) == overlay_name
        and _safe_str(state_payload.get("overlay_scope")) == overlay_scope
    )
    if state_claims_running_overlay:
        process_alive, process_alive_check = _process_alive_readback(pid)
    elif not pid_present:
        process_alive, process_alive_check = False, "not_attempted_no_pid_file"
    elif not state_exists:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_missing"
    elif state_kind != "lens.overlay.runtime_state":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_kind_mismatch"
    elif state_status != "overlay_running":
        process_alive, process_alive_check = False, "not_attempted_runtime_state_not_running"
    else:
        process_alive, process_alive_check = False, "not_attempted_runtime_state_pid_or_identity_mismatch"
    overlay_window_visible = process_alive and _bool(state_payload.get("overlay_window_visible"))
    always_on_top = overlay_window_visible and _bool(state_payload.get("always_on_top"))
    ready = overlay_window_visible and always_on_top
    requirement_state = (
        "visible"
        if ready
        else "process_running_no_visible_overlay_claim"
        if process_alive
        else "stale_or_unverified"
        if state_exists or pid_present
        else "missing"
    )
    blocker = "" if ready else "overlay_window_not_observed" if process_alive else "overlay_window_runtime_missing"
    return {
        "ready": ready,
        "process_alive": process_alive,
        "process_alive_check": process_alive_check,
        "overlay_window_visible": overlay_window_visible,
        "always_on_top": always_on_top,
        "pid": pid,
        "pid_present": pid_present,
        "status_path": "data/runtime/lens-overlay/status.json",
        "pid_path": "data/runtime/lens-overlay/lens-overlay.pid",
        "runtime_state_exists": state_exists,
        "runtime_status": state_status,
        "runtime_status_kind": state_kind,
        "runtime_status_pid": state_pid,
        "runtime_status_pid_matches_pid_file": state_pid > 0 and pid > 0 and state_pid == pid,
        "runtime_state_updated_at": _safe_str(state_payload.get("updated_at")),
        "overlay_name": _safe_str(state_payload.get("overlay_name")),
        "expected_overlay_name": overlay_name,
        "overlay_scope": _safe_str(state_payload.get("overlay_scope")),
        "expected_overlay_scope": overlay_scope,
        "requirement_state": requirement_state,
        "blocker": blocker,
    }


def _config_status(*, exists: bool, error: str) -> str:
    if exists and not error:
        return "present_disabled"
    if exists:
        return "invalid"
    return "missing"


def _check(check_id: str, status: str, reason: str, evidence: str = "") -> dict[str, Any]:
    return {
        "id": check_id,
        "status": status,
        "reason": reason,
        "evidence": evidence,
    }


def _dict_value(payload: dict[str, Any], key: str) -> dict[str, Any]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _blockers(payload: dict[str, Any]) -> list[str]:
    value = payload.get("blockers")
    return _string_list(value)


def _select_blockers(blockers: list[str], *candidates: str) -> list[str]:
    return [candidate for candidate in candidates if candidate in blockers]


def _authority_blockers(blockers: list[str]) -> list[str]:
    return [
        blocker
        for blocker in blockers
        if blocker.endswith("_authority_not_granted") or blocker.endswith("_authority_false")
    ]


def _dedupe(values: list[str]) -> list[str]:
    deduped: list[str] = []
    for value in values:
        item = _safe_str(value).strip()
        if item and item not in deduped:
            deduped.append(item)
    return deduped


def _summon_blocker_family_readback(blocker_groups: dict[str, list[str]]) -> list[dict[str, Any]]:
    routes = {
        "resident_host": "/lens/host",
        "tray_presence": "/lens/tray",
        "overlay_window": "/lens/overlay",
        "global_hotkey_binding": "/lens/summon",
        "summon_binding": "/lens/summon",
        "summon_anywhere": "/lens/summon",
        "authority": "/lens/preflight",
    }
    labels = {
        "resident_host": "Resident host",
        "tray_presence": "Tray presence",
        "overlay_window": "Overlay window",
        "global_hotkey_binding": "Global hotkey binding",
        "summon_binding": "Summon binding",
        "summon_anywhere": "Summon anywhere runtime",
        "authority": "Authority boundary",
    }
    authority_required = {
        "resident_host": "resident_runtime_execution_authority",
        "tray_presence": "tray_registration_authority",
        "overlay_window": "overlay_control_authority",
        "global_hotkey_binding": "hotkey_registration_authority",
        "summon_binding": "summon_authority",
        "summon_anywhere": "summon_anywhere_runtime_proof",
        "authority": "operator_approved_authority",
    }
    return [
        {
            "id": family,
            "label": labels[family],
            "status": "blocked" if blockers else "ready",
            "ready": not blockers,
            "route": routes[family],
            "authority_required": authority_required[family],
            "blockers": blockers,
        }
        for family, blockers in blocker_groups.items()
    ]


def _summon_blocker_family_handoffs(blocker_family_readback: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metadata_by_family = {
        "resident_host": {
            "label": "Resident host",
            "proof_script": "scripts/lens-summon-resident-host-blocker-proof.ps1 -Mode Status",
            "route": "/lens/host",
            "readiness_route": "/lens/host/runtime-loop/readiness",
            "next_step": "run_resident_host_blocker_proof",
            "next_smallest_truthful_gap": "resident_host_runtime_blocker_boundary",
            "authority_required": "resident_runtime_execution_authority",
        },
        "tray_presence": {
            "label": "Tray presence",
            "proof_script": "scripts/lens-summon-tray-presence-blocker-proof.ps1 -Mode Status",
            "route": "/lens/tray",
            "readiness_route": "/lens/tray/readiness",
            "next_step": "run_tray_presence_blocker_proof",
            "next_smallest_truthful_gap": "summon_overlay_window_blocker_boundary",
            "authority_required": "tray_registration_authority",
        },
        "overlay_window": {
            "label": "Overlay window",
            "proof_script": "scripts/lens-summon-overlay-window-blocker-proof.ps1 -Mode Status",
            "route": "/lens/overlay",
            "readiness_route": "/lens/overlay/readiness",
            "next_step": "run_overlay_window_blocker_proof",
            "next_smallest_truthful_gap": "summon_global_hotkey_binding_blocker_boundary",
            "authority_required": "overlay_control_authority",
        },
        "global_hotkey_binding": {
            "label": "Global hotkey binding",
            "proof_script": "scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status",
            "route": "/lens/summon",
            "readiness_route": "/lens/summon/readiness",
            "next_step": "run_global_hotkey_binding_blocker_proof",
            "next_smallest_truthful_gap": "summon_binding_blocker_boundary",
            "authority_required": "hotkey_registration_authority",
        },
        "summon_binding": {
            "label": "Summon binding",
            "proof_script": "scripts/lens-summon-binding-blocker-proof.ps1 -Mode Status",
            "route": "/lens/summon",
            "readiness_route": "/lens/summon/readiness",
            "next_step": "run_summon_binding_blocker_proof",
            "next_smallest_truthful_gap": "summon_authority_blocker_boundary",
            "authority_required": "summon_authority",
        },
        "summon_anywhere": {
            "label": "Summon anywhere runtime",
            "proof_script": "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
            "route": "/lens/summon",
            "readiness_route": "/lens/summon/readiness",
            "next_step": "prove_os_level_summon_anywhere_runtime_before_stage6_closure",
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "authority_required": "summon_anywhere_runtime_proof",
        },
        "authority": {
            "label": "Summon authority",
            "proof_script": "scripts/lens-summon-authority-blocker-proof.ps1 -Mode Status",
            "route": "/lens/summon",
            "readiness_route": "/lens/summon/readiness",
            "next_step": "run_summon_authority_blocker_proof",
            "next_smallest_truthful_gap": "stage6_lens_completion_audit",
            "authority_required": "summon_hotkey_overlay_and_process_authority",
        },
    }
    handoffs: list[dict[str, Any]] = []
    for family_readback in blocker_family_readback:
        family = _safe_str(family_readback.get("id")).strip()
        blockers = _string_list(family_readback.get("blockers"))
        metadata = metadata_by_family.get(family)
        if not metadata or not blockers:
            continue
        handoffs.append(
            {
                "id": family,
                "label": metadata["label"],
                "status": "blocked",
                "blockers": blockers,
                "proof_script": metadata["proof_script"],
                "route": metadata["route"],
                "readiness_route": metadata["readiness_route"],
                "next_step": metadata["next_step"],
                "next_smallest_truthful_gap": metadata["next_smallest_truthful_gap"],
                "authority_required": metadata["authority_required"],
                "authority_granted": False,
                "read_only_contract": True,
                "diagnostic_only": True,
                "would_execute": False,
                "would_mutate": False,
            }
        )
    return handoffs


def _summon_anywhere_family_chain_completion_audit_handoff(
    *,
    blocked_families: list[str],
    first_blocker_family_handoff: dict[str, Any],
) -> dict[str, Any]:
    if not blocked_families or not first_blocker_family_handoff:
        return {}
    return {
        "next_step": "consume_summon_anywhere_family_chain_proof_before_stage6_closure",
        "proof_script": "scripts/lens-summon-anywhere-family-chain-proof.ps1 -Mode Status",
        "previous_next_smallest_truthful_gap": "summon_anywhere_blockers",
        "next_smallest_truthful_gap": "stage6_lens_completion_audit",
        "blocked_families": blocked_families,
        "authority_required": _safe_str(
            first_blocker_family_handoff.get("authority_required"),
            "summon_hotkey_overlay_and_process_authority",
        ),
        "authority_granted": False,
        "read_only_contract": True,
        "diagnostic_only": True,
        "would_execute": False,
        "would_mutate": False,
    }


def _base_governance(**extra: bool) -> dict[str, bool]:
    governance = {
        "read_only_contract": True,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "new_sensing_authority": False,
        "local_process_launch_authority": False,
        "mutation_authority_granted": False,
    }
    governance.update(extra)
    return governance


def _host_preflight(host_manifest: dict[str, Any]) -> dict[str, Any]:
    blockers = [str(item) for item in host_manifest.get("blockers", []) if item]
    blocker_groups = _dict_value(host_manifest, "blocker_groups")
    service_plan = _dict_value(host_manifest, "service_plan")
    process_readback = _dict_value(host_manifest, "process_readback")
    supervision = _dict_value(host_manifest, "supervision_readiness")
    ready = not blockers and bool(supervision.get("ready"))
    return {
        "ok": True,
        "kind": "lens.host.api_preflight",
        "status": "ready" if ready else "blocked",
        "mode": "status",
        "ready": ready,
        "route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "service_plan_status": _safe_str(service_plan.get("status"), "missing"),
        "process_readback_status": _safe_str(process_readback.get("status"), "missing"),
        "supervision_status": _safe_str(supervision.get("status"), "missing"),
        "checks": [
            _check(
                "launch_manifest",
                _safe_str(host_manifest.get("contract_status"), "missing"),
                "host launch manifest API readback is mounted",
                "/lens/host/manifest",
            ),
            _check(
                "service_plan",
                _safe_str(service_plan.get("status"), "missing"),
                "service plan API projection is available",
                "config/runtime/services/lens-host.json",
            ),
            _check(
                "process_readback",
                _safe_str(process_readback.get("status"), "missing"),
                "foreground process readback is available without launch authority",
                "data/runtime/lens-host",
            ),
            _check(
                "supervision_readiness",
                _safe_str(supervision.get("status"), "missing"),
                "resident supervision readiness remains governed",
                "process_supervision_enabled",
            ),
        ],
        "blockers": blockers,
        "blocker_groups": blocker_groups,
        "governance": _base_governance(
            service_install_authority=False,
            service_control_authority=False,
            wrapper_write_authority=False,
        ),
        "message": "Lens host API preflight is read-only; resident host runtime remains blocked.",
    }


def _summon_preflight() -> dict[str, Any]:
    config_path = "config/runtime/lens/summon.json"
    payload, exists, error = _read_config(config_path)
    hotkey_override = _hotkey_runtime_override_config()
    effective_payload = {**payload, **hotkey_override} if hotkey_override else payload
    summon_name = _safe_str(effective_payload.get("summon_name"), "Francis Lens Summon")
    global_hotkey = _safe_str(effective_payload.get("global_hotkey"))
    binding_scope = _safe_str(effective_payload.get("binding_scope"), "global")
    palette_route = _safe_str(effective_payload.get("palette_route"), "/lens/status")
    host_preflight = _safe_str(effective_payload.get("host_preflight"), "scripts/lens-host-preflight.ps1")
    host_status_runner = _safe_str(effective_payload.get("host_status_runner"), "scripts/lens-host.ps1")
    summon_runner = _safe_str(effective_payload.get("summon_runner"), "scripts/lens-summon.ps1")
    local_palette_launcher = _safe_str(
        effective_payload.get("local_palette_launcher"),
        "scripts/lens-command-palette.ps1 -Mode LocalOpen",
    )
    blocked_reason = _safe_str(
        effective_payload.get("blocked_reason"), "lens_summon_binding_disabled_pending_authority"
    )
    enabled = _bool(effective_payload.get("enabled"))
    binding_enabled = _bool(effective_payload.get("binding_enabled"))
    register_hotkey = _bool(effective_payload.get("register_hotkey"))
    startup_register = _bool(effective_payload.get("startup_register"))
    overlay_required = _bool(effective_payload.get("overlay_required"), True)
    tray_required = _bool(effective_payload.get("tray_required"), True)
    summon_authority = _bool(effective_payload.get("summon_authority"))
    hotkey_registration_authority = _bool(effective_payload.get("hotkey_registration_authority"))
    overlay_control_authority = _bool(effective_payload.get("overlay_control_authority"))
    local_process_launch_authority = _bool(effective_payload.get("local_process_launch_authority"))
    required_before_enable = _string_list(effective_payload.get("required_before_enable"))
    host_preflight_exists = _runtime_file_exists(host_preflight)
    host_status_runner_exists = _runtime_file_exists(host_status_runner)
    summon_runner_exists = _runtime_file_exists(summon_runner)
    hotkey_runtime = _hotkey_runtime_readback(
        global_hotkey=global_hotkey,
        binding_scope=binding_scope,
        config_source="runtime_override" if hotkey_override else "canonical_config",
    )
    hotkey_runtime_ready = bool(hotkey_runtime.get("ready"))
    blockers: list[str] = []
    if blocked_reason:
        blockers.append(blocked_reason)
    if not exists:
        blockers.append("lens_summon_config_missing")
    if error:
        blockers.append("lens_summon_config_invalid")
    if not global_hotkey:
        blockers.append("global_hotkey_not_declared")
    if not summon_runner_exists:
        blockers.append("lens_summon_runner_missing")
    if not binding_enabled:
        blockers.append("global_hotkey_binding_disabled")
    if not register_hotkey:
        blockers.append("global_hotkey_registration_disabled")
    if not host_preflight_exists:
        blockers.append("lens_host_lifecycle_preflight_missing")
    if not host_status_runner_exists:
        blockers.append("lens_host_status_runner_missing")
    if overlay_required:
        blockers.append("overlay_window_missing")
    if tray_required:
        blockers.append("tray_host_missing")
    if not summon_authority:
        blockers.append("summon_authority_not_granted")
    if not hotkey_registration_authority:
        blockers.append("hotkey_registration_authority_not_granted")
    if not overlay_control_authority:
        blockers.append("overlay_control_authority_not_granted")
    if not local_process_launch_authority:
        blockers.append("local_process_launch_authority_not_granted")
    ready = not blockers
    blocker_groups = {
        "config": _select_blockers(blockers, "lens_summon_config_missing", "lens_summon_config_invalid"),
        "global_hotkey_binding": _select_blockers(
            blockers,
            "global_hotkey_not_declared",
            "global_hotkey_binding_disabled",
            "global_hotkey_registration_disabled",
            "hotkey_registration_authority_not_granted",
        ),
        "summon_binding": _select_blockers(
            blockers,
            "lens_summon_binding_not_implemented",
            "lens_summon_binding_disabled_pending_authority",
            "lens_summon_runner_missing",
            "summon_authority_not_granted",
        ),
        "host_dependency": _select_blockers(
            blockers,
            "lens_host_lifecycle_preflight_missing",
            "lens_host_status_runner_missing",
            "local_process_launch_authority_not_granted",
        ),
        "surface_dependencies": _select_blockers(blockers, "tray_host_missing", "overlay_window_missing"),
        "authority": _authority_blockers(blockers),
    }
    return {
        "ok": True,
        "kind": "lens.summon.api_preflight",
        "status": "ready" if ready else "blocked",
        "mode": "status",
        "ready": ready,
        "summon_name": summon_name,
        "config_path": config_path,
        "config_exists": exists,
        "acceptance_criterion": "summon_anywhere",
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "required_before_enable": required_before_enable,
        "global_hotkey": global_hotkey,
        "binding_scope": binding_scope,
        "palette_route": palette_route,
        "checks": [
            _check(
                "summon_config",
                _config_status(exists=exists, error=error),
                error or ("disabled summon config is present" if exists else "summon config is missing"),
                config_path,
            ),
            _check(
                "summon_runner",
                "present" if summon_runner_exists else "missing",
                "local summon launcher is present" if summon_runner_exists else "local summon launcher is missing",
                summon_runner,
            ),
            _check(
                "hotkey_declared",
                "declared" if global_hotkey else "missing",
                "global hotkey intent is declared but not bound"
                if global_hotkey
                else "global hotkey intent is missing",
                global_hotkey,
            ),
            _check(
                "binding_enabled",
                "enabled" if binding_enabled else "disabled",
                "global binding remains disabled until resident Lens host exists",
                binding_scope,
            ),
            _check(
                "register_hotkey",
                "would_register" if register_hotkey else "disabled",
                "hotkey registration remains disabled",
                "register_hotkey",
            ),
            _check(
                "hotkey_runtime",
                "bound"
                if hotkey_runtime_ready
                else "stale_or_unverified"
                if hotkey_runtime.get("runtime_state_exists") or hotkey_runtime.get("pid_present")
                else "missing",
                "global hotkey runtime reports a live bound hotkey"
                if hotkey_runtime_ready
                else "global hotkey runtime is not live",
                "data/runtime/lens-hotkey/status.json",
            ),
            _check(
                "host_preflight",
                "present" if host_preflight_exists else "missing",
                "host lifecycle preflight is present"
                if host_preflight_exists
                else "host lifecycle preflight is missing",
                host_preflight,
            ),
            _check(
                "hotkey_registration_authority",
                "allowed" if hotkey_registration_authority else "blocked",
                "hotkey registration authority is not granted",
                "hotkey_registration_authority",
            ),
        ],
        "blockers": blockers,
        "blocker_groups": blocker_groups,
        "hotkey_runtime_readback": hotkey_runtime,
        "binding": {
            "enabled": enabled,
            "binding_enabled": binding_enabled,
            "register_hotkey": register_hotkey,
            "startup_register": startup_register,
            "host_preflight": host_preflight,
            "host_status_runner": host_status_runner,
            "summon_runner": summon_runner,
            "summon_runner_present": summon_runner_exists,
            "local_palette_launcher": local_palette_launcher,
            "local_binding_target_ready": summon_runner_exists,
            "global_hotkey_runtime_bound": hotkey_runtime_ready,
            "hotkey_runtime_requirement_state": _safe_str(hotkey_runtime.get("requirement_state"), "missing"),
        },
        "governance": {
            **_base_governance(hotkey_registration_authority=False),
            "hotkey_runtime_readback": True,
            "summon_runner_readback": True,
        },
        "message": (
            "Lens summon API preflight is read-only; local launcher readback is present but global hotkey "
            "binding and summon authority remain blocked."
        ),
    }


def _tray_preflight() -> dict[str, Any]:
    config_path = "config/runtime/lens/tray.json"
    payload, exists, error = _read_config(config_path)
    presence_name = _safe_str(payload.get("presence_name"), "Francis Lens Tray Presence")
    tray_scope = _safe_str(payload.get("tray_scope"), "user_session")
    status_route = _safe_str(payload.get("status_route"), "/lens/host")
    lens_status_route = _safe_str(payload.get("lens_status_route"), "/lens/status")
    host_preflight = _safe_str(payload.get("host_preflight"), "scripts/lens-host-preflight.ps1")
    host_status_runner = _safe_str(payload.get("host_status_runner"), "scripts/lens-host.ps1")
    tray_runner = _safe_str(payload.get("tray_runner"), "scripts/lens-tray-presence.ps1")
    runtime_state_path = _safe_str(payload.get("runtime_state_path"), "data/runtime/lens-tray/status.json")
    pid_path = _safe_str(payload.get("pid_path"), "data/runtime/lens-tray/lens-tray.pid")
    summon_preflight = _safe_str(payload.get("summon_preflight"), "scripts/lens-summon-preflight.ps1")
    summon_config = _safe_str(payload.get("summon_config"), "config/runtime/lens/summon.json")
    blocked_reason = _safe_str(payload.get("blocked_reason"), "lens_tray_presence_disabled_pending_authority")
    enabled = _bool(payload.get("enabled"))
    tray_host_enabled = _bool(payload.get("tray_host_enabled"))
    tray_icon_enabled = _bool(payload.get("tray_icon_enabled"))
    startup_register = _bool(payload.get("startup_register"))
    notification_supported = _bool(payload.get("notification_supported"))
    tray_registration_authority = _bool(payload.get("tray_registration_authority"))
    tray_icon_authority = _bool(payload.get("tray_icon_authority"))
    notification_authority = _bool(payload.get("notification_authority"))
    overlay_control_authority = _bool(payload.get("overlay_control_authority"))
    local_process_launch_authority = _bool(payload.get("local_process_launch_authority"))
    service_control_authority = _bool(payload.get("service_control_authority"))
    summon_authority = _bool(payload.get("summon_authority"))
    required_before_enable = _string_list(payload.get("required_before_enable"))
    host_preflight_exists = _runtime_file_exists(host_preflight)
    host_status_runner_exists = _runtime_file_exists(host_status_runner)
    tray_runner_exists = _runtime_file_exists(tray_runner)
    summon_preflight_exists = _runtime_file_exists(summon_preflight)
    summon_config_exists = _runtime_file_exists(summon_config)
    tray_runtime = _tray_runtime_readback()
    tray_runtime_ready = bool(tray_runtime.get("ready"))
    runtime_state_exists = _runtime_state_exists()
    blockers: list[str] = []
    if blocked_reason:
        blockers.append(blocked_reason)
    if not exists:
        blockers.append("lens_tray_config_missing")
    if error:
        blockers.append("lens_tray_config_invalid")
    if not tray_host_enabled:
        blockers.append("tray_host_disabled")
    if not tray_icon_enabled:
        blockers.append("tray_icon_disabled")
    if not startup_register:
        blockers.append("tray_startup_registration_disabled")
    if not host_preflight_exists:
        blockers.append("lens_host_lifecycle_preflight_missing")
    if not host_status_runner_exists:
        blockers.append("lens_host_status_runner_missing")
    if (enabled or tray_host_enabled or tray_icon_enabled) and not tray_runner_exists:
        blockers.append("lens_tray_runner_missing")
    if tray_host_enabled and tray_icon_enabled and not tray_runtime_ready:
        blockers.append(_safe_str(tray_runtime.get("blocker"), "tray_presence_runtime_missing"))
    if not summon_preflight_exists:
        blockers.append("lens_summon_preflight_missing")
    if not summon_config_exists:
        blockers.append("lens_summon_config_missing")
    if not runtime_state_exists:
        blockers.append("resident_host_process_missing")
    if not tray_registration_authority:
        blockers.append("tray_registration_authority_not_granted")
    if not tray_icon_authority:
        blockers.append("tray_icon_authority_not_granted")
    if not notification_authority:
        blockers.append("notification_authority_not_granted")
    if not overlay_control_authority:
        blockers.append("overlay_control_authority_not_granted")
    if not local_process_launch_authority:
        blockers.append("local_process_launch_authority_not_granted")
    if not service_control_authority:
        blockers.append("service_control_authority_not_granted")
    if not summon_authority:
        blockers.append("summon_authority_not_granted")
    ready = not blockers
    return {
        "ok": True,
        "kind": "lens.tray.api_preflight",
        "status": "ready" if ready else "blocked",
        "mode": "status",
        "ready": ready,
        "presence_name": presence_name,
        "config_path": config_path,
        "config_exists": exists,
        "required_before_enable": required_before_enable,
        "tray_scope": tray_scope,
        "status_route": status_route,
        "lens_status_route": lens_status_route,
        "checks": [
            _check(
                "tray_config",
                _config_status(exists=exists, error=error),
                error or ("disabled tray presence config is present" if exists else "tray presence config is missing"),
                config_path,
            ),
            _check(
                "tray_host_enabled",
                "enabled" if tray_host_enabled else "disabled",
                "tray host remains disabled until resident host exists",
                tray_scope,
            ),
            _check(
                "tray_icon_enabled",
                "enabled" if tray_icon_enabled else "disabled",
                "tray icon remains disabled until tray host authority exists",
                "tray_icon_enabled",
            ),
            _check(
                "host_preflight",
                "present" if host_preflight_exists else "missing",
                "host lifecycle preflight is present"
                if host_preflight_exists
                else "host lifecycle preflight is missing",
                host_preflight,
            ),
            _check(
                "tray_runner",
                "present" if tray_runner_exists else "missing",
                "tray presence runner is present" if tray_runner_exists else "tray presence runner is missing",
                tray_runner,
            ),
            _check(
                "tray_runtime",
                "running"
                if tray_runtime_ready
                else "stale_or_unverified"
                if tray_runtime.get("runtime_state_exists") or tray_runtime.get("pid_present")
                else "missing",
                "tray runtime state reports a live tray icon" if tray_runtime_ready else "tray runtime is not live",
                runtime_state_path,
            ),
            _check(
                "summon_preflight",
                "present" if summon_preflight_exists else "missing",
                "summon preflight is present" if summon_preflight_exists else "summon preflight is missing",
                summon_preflight,
            ),
            _check(
                "tray_registration_authority",
                "allowed" if tray_registration_authority else "blocked",
                "tray registration authority is not granted",
                "tray_registration_authority",
            ),
        ],
        "blockers": blockers,
        "tray": {
            "enabled": enabled,
            "tray_host_enabled": tray_host_enabled,
            "tray_icon_enabled": tray_icon_enabled,
            "startup_register": startup_register,
            "notification_supported": notification_supported,
            "host_preflight": host_preflight,
            "host_status_runner": host_status_runner,
            "tray_runner": tray_runner,
            "runtime_state_path": runtime_state_path,
            "pid_path": pid_path,
            "summon_preflight": summon_preflight,
            "summon_config": summon_config,
        },
        "tray_runtime": tray_runtime,
        "governance": _base_governance(
            service_control_authority=False,
            tray_registration_authority=False,
            tray_icon_authority=False,
            notification_authority=False,
        ),
        "message": "Lens tray API preflight is read-only; tray registration and presence remain blocked.",
    }


def _overlay_preflight() -> dict[str, Any]:
    config_path = "config/runtime/lens/overlay.json"
    payload, exists, error = _read_config(config_path)
    overlay_name = _safe_str(payload.get("overlay_name"), "Francis Lens Overlay")
    overlay_scope = _safe_str(payload.get("overlay_scope"), "user_session")
    status_route = _safe_str(payload.get("status_route"), "/lens/status")
    host_route = _safe_str(payload.get("host_route"), "/lens/host")
    host_preflight = _safe_str(payload.get("host_preflight"), "scripts/lens-host-preflight.ps1")
    host_status_runner = _safe_str(payload.get("host_status_runner"), "scripts/lens-host.ps1")
    overlay_runner = _safe_str(payload.get("overlay_runner"), "scripts/lens-overlay-window.ps1")
    summon_preflight = _safe_str(payload.get("summon_preflight"), "scripts/lens-summon-preflight.ps1")
    tray_preflight = _safe_str(payload.get("tray_preflight"), "scripts/lens-tray-preflight.ps1")
    blocked_reason = _safe_str(payload.get("blocked_reason"), "lens_overlay_window_not_implemented")
    enabled = _bool(payload.get("enabled"))
    window_enabled = _bool(payload.get("window_enabled"))
    always_on_top = _bool(payload.get("always_on_top"))
    dock_supported = _bool(payload.get("dock_supported"))
    focus_supported = _bool(payload.get("focus_supported"))
    click_through_supported = _bool(payload.get("click_through_supported"))
    capture_supported = _bool(payload.get("capture_supported"))
    overlay_control_authority = _bool(payload.get("overlay_control_authority"))
    window_management_authority = _bool(payload.get("window_management_authority"))
    local_process_launch_authority = _bool(payload.get("local_process_launch_authority"))
    capture_authority = _bool(payload.get("capture_authority"))
    summon_authority = _bool(payload.get("summon_authority"))
    tray_registration_authority = _bool(payload.get("tray_registration_authority"))
    required_before_enable = _string_list(payload.get("required_before_enable"))
    host_preflight_exists = _runtime_file_exists(host_preflight)
    host_status_runner_exists = _runtime_file_exists(host_status_runner)
    overlay_runner_exists = _runtime_file_exists(overlay_runner)
    summon_preflight_exists = _runtime_file_exists(summon_preflight)
    tray_preflight_exists = _runtime_file_exists(tray_preflight)
    runtime_state_exists = _runtime_state_exists()
    overlay_runtime = _overlay_runtime_readback(overlay_name=overlay_name, overlay_scope=overlay_scope)
    overlay_runtime_ready = bool(overlay_runtime.get("ready"))
    blockers: list[str] = []
    if blocked_reason and not overlay_runtime_ready:
        blockers.append(blocked_reason)
    if not exists:
        blockers.append("lens_overlay_config_missing")
    if error:
        blockers.append("lens_overlay_config_invalid")
    if not window_enabled:
        blockers.append("overlay_window_disabled")
    if not always_on_top:
        blockers.append("always_on_top_disabled")
    if not dock_supported:
        blockers.append("overlay_dock_not_supported")
    if not focus_supported:
        blockers.append("overlay_focus_not_supported")
    if not click_through_supported:
        blockers.append("overlay_click_through_not_supported")
    if not host_preflight_exists:
        blockers.append("lens_host_lifecycle_preflight_missing")
    if not host_status_runner_exists:
        blockers.append("lens_host_status_runner_missing")
    if not overlay_runner_exists:
        blockers.append("lens_overlay_runner_missing")
    if not summon_preflight_exists:
        blockers.append("lens_summon_preflight_missing")
    if not tray_preflight_exists:
        blockers.append("lens_tray_preflight_missing")
    if window_enabled and not overlay_runtime_ready:
        blockers.append("overlay_window_runtime_missing")
    if not runtime_state_exists:
        blockers.append("resident_host_process_missing")
    if not overlay_control_authority:
        blockers.append("overlay_control_authority_not_granted")
    if not window_management_authority:
        blockers.append("window_management_authority_not_granted")
    if not local_process_launch_authority:
        blockers.append("local_process_launch_authority_not_granted")
    if not capture_authority:
        blockers.append("capture_authority_not_granted")
    if not summon_authority:
        blockers.append("summon_authority_not_granted")
    if not tray_registration_authority:
        blockers.append("tray_registration_authority_not_granted")
    ready = not blockers
    return {
        "ok": True,
        "kind": "lens.overlay.api_preflight",
        "status": "ready" if ready else "blocked",
        "mode": "status",
        "ready": ready,
        "overlay_name": overlay_name,
        "config_path": config_path,
        "config_exists": exists,
        "required_before_enable": required_before_enable,
        "overlay_scope": overlay_scope,
        "status_route": status_route,
        "host_route": host_route,
        "checks": [
            _check(
                "overlay_config",
                _config_status(exists=exists, error=error),
                error or ("disabled overlay config is present" if exists else "overlay config is missing"),
                config_path,
            ),
            _check(
                "window_enabled",
                "enabled" if window_enabled else "disabled",
                "overlay window remains disabled until resident host exists",
                overlay_scope,
            ),
            _check(
                "always_on_top",
                "enabled" if always_on_top else "disabled",
                "always-on-top behavior remains disabled",
                "always_on_top",
            ),
            _check(
                "host_preflight",
                "present" if host_preflight_exists else "missing",
                "host lifecycle preflight is present"
                if host_preflight_exists
                else "host lifecycle preflight is missing",
                host_preflight,
            ),
            _check(
                "tray_preflight",
                "present" if tray_preflight_exists else "missing",
                "tray preflight is present" if tray_preflight_exists else "tray preflight is missing",
                tray_preflight,
            ),
            _check(
                "overlay_runner",
                "present" if overlay_runner_exists else "missing",
                "overlay window runtime runner is present"
                if overlay_runner_exists
                else "overlay window runtime runner is missing",
                overlay_runner,
            ),
            _check(
                "overlay_runtime",
                _safe_str(overlay_runtime.get("requirement_state"), "missing"),
                "overlay window runtime is live and topmost"
                if overlay_runtime_ready
                else "overlay window runtime is not live",
                "data/runtime/lens-overlay",
            ),
            _check(
                "overlay_control_authority",
                "allowed" if overlay_control_authority else "blocked",
                "overlay control authority is not granted",
                "overlay_control_authority",
            ),
        ],
        "blockers": blockers,
        "overlay": {
            "enabled": enabled,
            "window_enabled": window_enabled,
            "always_on_top": always_on_top,
            "dock_supported": dock_supported,
            "focus_supported": focus_supported,
            "click_through_supported": click_through_supported,
            "capture_supported": capture_supported,
            "host_preflight": host_preflight,
            "host_status_runner": host_status_runner,
            "overlay_runner": overlay_runner,
            "summon_preflight": summon_preflight,
            "tray_preflight": tray_preflight,
        },
        "overlay_runtime": overlay_runtime,
        "governance": _base_governance(
            window_management_authority=False,
            tray_registration_authority=False,
        ),
        "message": "Lens overlay API preflight is read-only; overlay window and focus actions remain blocked.",
    }


def lens_preflight() -> dict[str, Any]:
    host_manifest = lens_host_launch_manifest()
    host = _host_preflight(host_manifest)
    summon = _summon_preflight()
    tray = _tray_preflight()
    overlay = _overlay_preflight()
    surfaces = {
        "host": host,
        "summon": summon,
        "tray": tray,
        "overlay": overlay,
    }
    blockers = sorted({blocker for surface in surfaces.values() for blocker in surface["blockers"]})
    ready = not blockers
    return {
        "ok": True,
        "kind": "lens.preflight",
        "status": "ready" if ready else "blocked",
        "ready": ready,
        "read_only": True,
        "route": "/lens/preflight",
        "status_route": "/lens/status",
        "host_route": "/lens/host",
        "surfaces": surfaces,
        "summary": {
            "surface_total": len(surfaces),
            "ready_total": sum(1 for surface in surfaces.values() if bool(surface.get("ready"))),
            "blocked_total": sum(1 for surface in surfaces.values() if not bool(surface.get("ready"))),
            "blocker_total": len(blockers),
        },
        "blockers": blockers,
        "governance": _base_governance(
            service_install_authority=False,
            service_control_authority=False,
            wrapper_write_authority=False,
            window_management_authority=False,
            tray_registration_authority=False,
            tray_icon_authority=False,
            notification_authority=False,
            hotkey_registration_authority=False,
        ),
        "message": "Lens preflight API is read-only; host, summon, tray, and overlay lifecycle actions remain blocked.",
    }


def lens_summon_enablement_gate(*, preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    lens_preflight_payload = preflight if isinstance(preflight, dict) else lens_preflight()
    surfaces = _dict_value(lens_preflight_payload, "surfaces")
    host = _dict_value(surfaces, "host")
    summon = _dict_value(surfaces, "summon")
    tray = _dict_value(surfaces, "tray")
    overlay = _dict_value(surfaces, "overlay")
    blocker_set = {
        *_blockers(host),
        *_blockers(summon),
        *_blockers(tray),
        *_blockers(overlay),
    }
    blockers = sorted(blocker_set)
    launch_manifest = lens_host_launch_manifest()
    supervisor_readback = _dict_value(launch_manifest, "supervisor_readback")
    resident_host_runtime_ready = bool(supervisor_readback.get("resident_supervised_runtime"))
    tray_runtime = _dict_value(launch_manifest, "tray_runtime_readback")
    tray_runtime_ready = bool(tray_runtime.get("ready"))
    hotkey_runtime = _dict_value(launch_manifest, "hotkey_runtime_readback") or _dict_value(
        summon,
        "hotkey_runtime_readback",
    )
    hotkey_runtime_ready = bool(hotkey_runtime.get("ready"))
    hotkey_launch_on_press = hotkey_runtime_ready and bool(hotkey_runtime.get("launch_on_hotkey"))
    overlay_runtime = _dict_value(launch_manifest, "overlay_runtime_readback") or _dict_value(
        overlay,
        "overlay_runtime",
    )
    overlay_runtime_ready = bool(overlay_runtime.get("ready"))
    summon_runtime = _dict_value(launch_manifest, "summon_runtime_readback")
    summon_runtime_ready = bool(summon_runtime.get("ready"))
    summon_anywhere_runtime_ready = (
        summon_runtime_ready
        and hotkey_launch_on_press
        and resident_host_runtime_ready
        and tray_runtime_ready
        and overlay_runtime_ready
        and bool(summon_runtime.get("summon_anywhere"))
        and bool(summon_runtime.get("os_level_summon"))
    )
    if hotkey_runtime_ready:
        blockers = [blocker for blocker in blockers if blocker != "global_hotkey_binding_missing"]
    if overlay_runtime_ready:
        blockers = [
            blocker
            for blocker in blockers
            if blocker not in {"lens_overlay_window_not_implemented", "overlay_window_missing"}
        ]
    if summon_runtime_ready:
        blockers = [
            blocker
            for blocker in blockers
            if blocker
            not in {
                "lens_summon_binding_disabled_pending_authority",
                "summon_authority_not_granted",
                "summon_binding_missing",
            }
        ]
        if not summon_anywhere_runtime_ready:
            blockers.append("summon_anywhere_runtime_readback")
    if summon_anywhere_runtime_ready:
        blockers = [
            blocker
            for blocker in blockers
            if blocker
            not in {
                "always_on_top_disabled",
                "capture_authority_not_granted",
                "global_hotkey_binding_disabled",
                "global_hotkey_registration_disabled",
                "hotkey_registration_authority_not_granted",
                "lens_host_persistent_supervision_prerequisites_pending",
                "lens_tray_presence_disabled_pending_authority",
                "local_process_launch_authority_not_granted",
                "notification_authority_not_granted",
                "overlay_click_through_not_supported",
                "overlay_control_authority_not_granted",
                "overlay_dock_not_supported",
                "overlay_focus_not_supported",
                "overlay_window_disabled",
                "service_control_authority_not_granted",
                "summon_anywhere_runtime_readback",
                "tray_host_disabled",
                "tray_host_missing",
                "tray_icon_authority_not_granted",
                "tray_icon_disabled",
                "tray_registration_authority_not_granted",
                "tray_startup_registration_disabled",
                "window_management_authority_not_granted",
            }
        ]
    summon_ready = bool(summon.get("ready")) or summon_runtime_ready
    resident_host_ready = bool(host.get("ready")) or (summon_anywhere_runtime_ready and resident_host_runtime_ready)
    tray_ready = bool(tray.get("ready")) or (summon_anywhere_runtime_ready and tray_runtime_ready)
    overlay_ready = bool(overlay.get("ready")) or (summon_anywhere_runtime_ready and overlay_runtime_ready)
    ready = summon_anywhere_runtime_ready and resident_host_ready and tray_ready and overlay_ready
    blocker_groups = {
        "resident_host": _select_blockers(
            blockers,
            "resident_host_process_missing",
            "lens_host_runtime_not_implemented",
            "lens_host_persistent_supervision_prerequisites_pending",
            "lens_host_service_config_missing",
            "lens_host_entrypoint_missing",
            "lens_host_lifecycle_preflight_missing",
            "lens_host_status_runner_missing",
            "local_process_launch_authority_not_granted",
        ),
        "tray_presence": _select_blockers(
            blockers,
            "lens_tray_presence_not_implemented",
            "lens_tray_presence_disabled_pending_authority",
            "tray_host_missing",
            "tray_host_disabled",
            "tray_icon_disabled",
            "tray_registration_authority_not_granted",
        ),
        "overlay_window": _select_blockers(
            blockers,
            "lens_overlay_window_not_implemented",
            "overlay_window_missing",
            "overlay_window_runtime_missing",
            "overlay_window_disabled",
            "overlay_control_authority_not_granted",
        ),
        "global_hotkey_binding": _select_blockers(
            blockers,
            "global_hotkey_not_declared",
            "global_hotkey_binding_missing",
            "global_hotkey_binding_disabled",
            "global_hotkey_registration_disabled",
            "hotkey_registration_authority_not_granted",
        ),
        "summon_binding": _select_blockers(
            blockers,
            "lens_summon_binding_not_implemented",
            "lens_summon_binding_disabled_pending_authority",
            "summon_binding_missing",
            "summon_authority_not_granted",
        ),
        "authority": _authority_blockers(blockers),
    }
    if summon_runtime_ready and not summon_anywhere_runtime_ready:
        blocker_groups["summon_anywhere"] = _select_blockers(blockers, "summon_anywhere_runtime_readback")
    blocker_family_readback = _summon_blocker_family_readback(blocker_groups)
    blocked_families = [_safe_str(item.get("id")).strip() for item in blocker_family_readback if not item["ready"]]
    first_blocker_family = blocked_families[0] if blocked_families else ""
    blocked_family_handoffs = _summon_blocker_family_handoffs(blocker_family_readback)
    first_blocker_family_handoff = blocked_family_handoffs[0] if blocked_family_handoffs else {}
    family_chain_completion_audit_handoff = _summon_anywhere_family_chain_completion_audit_handoff(
        blocked_families=blocked_families,
        first_blocker_family_handoff=first_blocker_family_handoff,
    )
    return {
        "ok": True,
        "kind": "lens.summon.enablement_gate",
        "status": "ready_for_operator_review" if ready else "blocked",
        "route": "/lens/summon",
        "preflight_route": "/lens/preflight",
        "status_route": "/lens/status",
        "host_route": "/lens/host",
        "ready": ready,
        "summon_anywhere": ready,
        "acceptance_criterion": "summon_anywhere",
        "next_smallest_truthful_gap": "summon_anywhere_blockers",
        "first_blocker_family": first_blocker_family,
        "blocked_families": blocked_families,
        "first_blocker_family_handoff_observed": bool(first_blocker_family_handoff),
        "first_blocker_family_handoff": first_blocker_family_handoff,
        "blocked_family_handoffs": blocked_family_handoffs,
        "summon_anywhere_family_chain_completion_audit_handoff_observed": bool(family_chain_completion_audit_handoff),
        "summon_anywhere_family_chain_completion_audit_handoff": family_chain_completion_audit_handoff,
        "operator_surface_readback_ready": True,
        "summon_binding_ready": summon_ready,
        "summon_runtime_ready": summon_runtime_ready,
        "summon_anywhere_runtime_ready": summon_anywhere_runtime_ready,
        "summon_runtime_bounded_handoff_ready": bool(summon_runtime.get("bounded_handoff_ready")),
        "summon_runtime_local_open_ready": bool(summon_runtime.get("local_open_ready")),
        "summon_runtime_readback": summon_runtime,
        "resident_host_ready": resident_host_ready,
        "tray_ready": tray_ready,
        "overlay_ready": overlay_ready,
        "global_hotkey": _safe_str(summon.get("global_hotkey")),
        "binding_scope": _safe_str(summon.get("binding_scope"), "global"),
        "palette_route": _safe_str(summon.get("palette_route"), "/lens/status"),
        "required_before_enable": _string_list(summon.get("required_before_enable")),
        "global_hotkey_runtime_ready": hotkey_runtime_ready,
        "hotkey_launch_on_press": hotkey_launch_on_press,
        "hotkey_runtime_readback": hotkey_runtime,
        "overlay_runtime_ready": overlay_runtime_ready,
        "overlay_runtime_readback": overlay_runtime,
        "blockers": blockers,
        "blocker_groups": blocker_groups,
        "blocker_family_readback": blocker_family_readback,
        "summon_preflight": summon,
        "surface_dependencies": {
            "host": {
                "status": _safe_str(host.get("status"), "missing"),
                "ready": resident_host_ready,
                "route": _safe_str(host.get("route"), "/lens/host"),
                "blockers": _blockers(host),
            },
            "tray": {
                "status": _safe_str(tray.get("status"), "missing"),
                "ready": tray_ready,
                "blockers": _blockers(tray),
            },
            "overlay": {
                "status": _safe_str(overlay.get("status"), "missing"),
                "ready": overlay_ready,
                "blockers": _blockers(overlay),
            },
        },
        "governance": _base_governance(
            hotkey_registration_authority=False,
            tray_registration_authority=False,
            overlay_control_authority=False,
            first_blocker_family_handoff_readback=bool(first_blocker_family_handoff),
            summon_anywhere_family_chain_completion_audit_handoff_readback=bool(family_chain_completion_audit_handoff),
        ),
        "message": "Lens summon enablement is read-only; global hotkey binding and summon-anywhere remain blocked.",
    }


def _os_binding_requirement(
    requirement_id: str,
    *,
    label: str,
    ready: bool,
    blockers: list[str],
    route: str,
    required_before_enable: list[str] | None = None,
    authority_granted: bool = False,
    authority_required: str = "",
    active_grant_receipt_id: str = "",
) -> dict[str, Any]:
    return {
        "id": requirement_id,
        "label": label,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "route": route,
        "blockers": blockers,
        "required_before_enable": required_before_enable or [],
        "authority_required": authority_required,
        "authority_granted": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
    }


def _os_binding_plan_step(
    step_id: str,
    *,
    label: str,
    ready: bool,
    blockers: list[str],
    route: str,
    authority_required: str = "",
    authority_granted: bool = False,
    active_grant_receipt_id: str = "",
    source: str = "",
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "route": route,
        "source": source,
        "blockers": [] if ready else _dedupe(blockers),
        "authority_required": authority_required,
        "authority_granted": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
        "would_open_palette": False,
        "would_register_hotkey": False,
        "would_summon": False,
        "would_launch_process": False,
        "would_register_tray": False,
        "would_open_overlay": False,
        "would_write_memory": False,
        "would_decide_approval": False,
    }


def _os_binding_authority_request_summary(readback: dict[str, Any] | None) -> dict[str, Any]:
    payload = readback if isinstance(readback, dict) else {}
    latest = _dict_value(payload, "latest")
    governance = _dict_value(payload, "governance")
    readback_ready = (
        _safe_str(payload.get("kind")).strip() == "lens.os_binding.command_palette_binding_authority.request_readback"
    )
    return {
        "kind": _safe_str(
            payload.get("kind"),
            "lens.os_binding.command_palette_binding_authority.request_readback",
        ),
        "status": _safe_str(payload.get("status"), "missing"),
        "readback_ready": readback_ready,
        "route": _safe_str(payload.get("route"), "/lens/os-binding/authority/requests"),
        "authority_route": _safe_str(payload.get("authority_route"), "/lens/os-binding/authority"),
        "request_route": _safe_str(payload.get("request_route"), "/lens/os-binding/authority/request"),
        "grants_route": _safe_str(payload.get("grants_route"), "/lens/os-binding/authority/grants"),
        "readiness_route": _safe_str(payload.get("readiness_route"), "/lens/os-binding/readiness"),
        "plan_route": _safe_str(payload.get("plan_route"), "/lens/os-binding/plan"),
        "active_grant_receipt_id": _safe_str(payload.get("active_grant_receipt_id")).strip(),
        "authority_required": _safe_str(
            payload.get("authority_required"),
            "os_level_command_palette_binding_authority",
        ),
        "pending_count": _int_value(payload.get("pending_count")),
        "approved_count": _int_value(payload.get("approved_count")),
        "rejected_count": _int_value(payload.get("rejected_count")),
        "emergency_count": _int_value(payload.get("emergency_count")),
        "total_count": _int_value(payload.get("total_count")),
        "latest_approval_id": _safe_str(latest.get("id")).strip(),
        "latest_status": _safe_str(latest.get("status")).strip(),
        "authority_granted": bool(payload.get("authority_granted")),
        "os_level_command_palette_binding_authority": bool(payload.get("os_level_command_palette_binding_authority")),
        "os_level_command_palette": bool(payload.get("os_level_command_palette")),
        "summon_anywhere": bool(payload.get("summon_anywhere")),
        "opens_palette": bool(payload.get("opens_palette")),
        "registers_hotkey": bool(payload.get("registers_hotkey")),
        "launches_process": bool(payload.get("launches_process")),
        "controls_overlay": bool(payload.get("controls_overlay")),
        "governance": {
            "read_only_contract": bool(governance.get("read_only_contract")),
            "approval_request_write": bool(governance.get("approval_request_write")),
            "execution_authority": bool(governance.get("execution_authority")),
            "approval_decision_authority": bool(governance.get("approval_decision_authority")),
            "memory_write": bool(governance.get("memory_write")),
            "resident_claim_authority": bool(governance.get("resident_claim_authority")),
        },
    }


def _os_binding_command_palette_contract(
    *,
    blockers: list[str],
    authority_granted: bool,
    active_grant_receipt_id: str,
    os_level_command_palette: bool = False,
    summon_anywhere: bool = False,
) -> dict[str, Any]:
    ready = bool(os_level_command_palette)
    return {
        "kind": "lens.os_binding.command_palette_contract",
        "status": "ready" if ready else "blocked",
        "readback_ready": True,
        "route": "/lens/status",
        "source": "lens.command_palette.shell_bridge",
        "source_route": "/lens/status",
        "bridge_script": "scripts/lens-command-palette.ps1",
        "proof_script": "scripts/lens-command-palette-os-binding-proof.ps1",
        "local_surface": "chat_ui.command_palette",
        "availability": "os_runtime" if ready else "chat_ui_only",
        "url_entrypoint_ready": True,
        "url_entrypoint_route": "/?francis_lens=command_palette",
        "authority_required": "os_level_command_palette_binding_authority",
        "authority_granted": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
        "os_level_command_palette": ready,
        "summon_anywhere": bool(summon_anywhere) and ready,
        "would_open_palette": False,
        "would_register_hotkey": False,
        "would_summon": False,
        "would_launch_process": False,
        "would_write_memory": False,
        "blockers": _dedupe(blockers),
        "governance": {
            "read_only_contract": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "memory_write": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
        },
    }


def lens_os_binding_implementation_plan(
    *,
    preflight: dict[str, Any] | None = None,
    summon_gate: dict[str, Any] | None = None,
    authority_request_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lens_preflight_payload = preflight if isinstance(preflight, dict) else lens_preflight()
    summon_gate_payload = (
        summon_gate if isinstance(summon_gate, dict) else lens_summon_enablement_gate(preflight=lens_preflight_payload)
    )
    authority_request_summary = _os_binding_authority_request_summary(authority_request_readback)
    authority_granted = bool(authority_request_summary.get("authority_granted"))
    active_grant_receipt_id = _safe_str(authority_request_summary.get("active_grant_receipt_id")).strip()
    blocker_groups = _dict_value(summon_gate_payload, "blocker_groups")
    required_before_enable = _string_list(summon_gate_payload.get("required_before_enable"))
    os_level_command_palette_ready = bool(summon_gate_payload.get("global_hotkey_runtime_ready")) and bool(
        summon_gate_payload.get("summon_anywhere")
    )
    palette_blockers = [] if os_level_command_palette_ready else ["os_level_command_palette_missing"]
    if not bool(summon_gate_payload.get("summon_anywhere")):
        palette_blockers.append("summon_anywhere_missing")
    palette_blockers.extend(_string_list(blocker_groups.get("global_hotkey_binding")))
    grouped_blockers = {
        "palette_binding": _dedupe(palette_blockers),
        "global_hotkey_binding": _string_list(blocker_groups.get("global_hotkey_binding")),
        "summon_binding": _string_list(blocker_groups.get("summon_binding")),
        "resident_host": _string_list(blocker_groups.get("resident_host")),
        "tray_presence": _string_list(blocker_groups.get("tray_presence")),
        "overlay_window": _string_list(blocker_groups.get("overlay_window")),
        "authority": _string_list(blocker_groups.get("authority")),
    }
    command_palette_contract = _os_binding_command_palette_contract(
        blockers=grouped_blockers["palette_binding"],
        authority_granted=authority_granted,
        active_grant_receipt_id=active_grant_receipt_id,
        os_level_command_palette=os_level_command_palette_ready,
        summon_anywhere=bool(summon_gate_payload.get("summon_anywhere")),
    )
    palette_step = _os_binding_plan_step(
        "os_level_command_palette_contract",
        label="OS-level command palette contract",
        ready=os_level_command_palette_ready,
        route="/lens/status",
        source="lens.command_palette.shell_bridge",
        authority_required="os_level_command_palette_binding_authority",
        authority_granted=authority_granted,
        active_grant_receipt_id=active_grant_receipt_id,
        blockers=grouped_blockers["palette_binding"],
    )
    palette_step.update(
        {
            "readback_ready": bool(command_palette_contract.get("readback_ready")),
            "source_route": _safe_str(command_palette_contract.get("source_route"), "/lens/status"),
            "bridge_script": _safe_str(command_palette_contract.get("bridge_script")),
            "proof_script": _safe_str(command_palette_contract.get("proof_script")),
            "local_surface": _safe_str(command_palette_contract.get("local_surface")),
            "availability": _safe_str(command_palette_contract.get("availability")),
        }
    )
    steps = [
        palette_step,
        _os_binding_plan_step(
            "global_hotkey_binding_contract",
            label="Global hotkey binding contract",
            ready=not grouped_blockers["global_hotkey_binding"],
            route="/lens/summon",
            authority_required="hotkey_registration_authority",
            blockers=grouped_blockers["global_hotkey_binding"],
        ),
        _os_binding_plan_step(
            "summon_binding_contract",
            label="Summon binding contract",
            ready=not grouped_blockers["summon_binding"],
            route="/lens/summon",
            authority_required="summon_authority",
            blockers=grouped_blockers["summon_binding"],
        ),
        _os_binding_plan_step(
            "resident_host_dependency",
            label="Resident host dependency",
            ready=bool(summon_gate_payload.get("resident_host_ready")),
            route="/lens/host",
            authority_required="resident_runtime_execution_authority",
            blockers=grouped_blockers["resident_host"],
        ),
        _os_binding_plan_step(
            "tray_presence_dependency",
            label="Tray presence dependency",
            ready=bool(summon_gate_payload.get("tray_ready")),
            route="/lens/tray",
            authority_required="tray_registration_authority",
            blockers=grouped_blockers["tray_presence"],
        ),
        _os_binding_plan_step(
            "overlay_window_dependency",
            label="Overlay window dependency",
            ready=bool(summon_gate_payload.get("overlay_ready")),
            route="/lens/overlay",
            authority_required="overlay_control_authority",
            blockers=grouped_blockers["overlay_window"],
        ),
        _os_binding_plan_step(
            "authority_boundary",
            label="Authority boundary",
            ready=not grouped_blockers["authority"],
            route="/lens/preflight",
            blockers=grouped_blockers["authority"],
        ),
    ]
    blocked_steps = [_safe_str(step.get("id")) for step in steps if not bool(step.get("ready"))]
    blockers = _dedupe([blocker for blockers in grouped_blockers.values() for blocker in blockers])
    ready = not blocked_steps and bool(summon_gate_payload.get("ready")) and os_level_command_palette_ready
    return {
        "ok": True,
        "kind": "lens.os_binding.implementation_plan",
        "status": "ready_for_operator_review" if ready else "blocked",
        "route": "/lens/os-binding/plan",
        "readiness_route": "/lens/os-binding/readiness",
        "execute_route": "/lens/os-binding/execute",
        "denials_route": "/lens/os-binding/denials",
        "status_route": "/lens/status",
        "preflight_route": "/lens/preflight",
        "summon_route": "/lens/summon",
        "tray_route": "/lens/tray",
        "overlay_route": "/lens/overlay",
        "host_route": "/lens/host",
        "plan_available": True,
        "implementation_ready": ready,
        "execution_ready": False,
        "os_binding_ready": ready,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
        "authority_grant_consumed": authority_granted or os_level_command_palette_ready,
        "os_level_command_palette": os_level_command_palette_ready,
        "summon_anywhere": bool(summon_gate_payload.get("summon_anywhere")) and os_level_command_palette_ready,
        "acceptance_criterion": "summon_anywhere",
        "next_smallest_truthful_gap": "stage6_lens_completion_audit" if ready else "os_level_command_palette_binding",
        "required_before_enable": required_before_enable,
        "requirements_total": len(steps),
        "requirements_ready_total": len(steps) - len(blocked_steps),
        "requirements_blocked_total": len(blocked_steps),
        "blocked_requirements": blocked_steps,
        "blockers": blockers,
        "blocker_groups": grouped_blockers,
        "authority_request_readback": authority_request_summary,
        "command_palette_contract": command_palette_contract,
        "plan": {
            "status": "ready_for_operator_review" if ready else "blocked",
            "steps": steps,
            "would_open_palette": False,
            "would_register_hotkey": False,
            "would_summon": False,
            "would_launch_process": False,
            "would_supervise_process": False,
            "would_register_tray": False,
            "would_open_overlay": False,
            "would_write_memory": False,
            "would_write_receipt": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
        },
        "source_readbacks": {
            "summon_gate_status": _safe_str(summon_gate_payload.get("status"), "blocked"),
            "summon_gate_route": _safe_str(summon_gate_payload.get("route"), "/lens/summon"),
            "summon_gate_next_smallest_truthful_gap": _safe_str(
                summon_gate_payload.get("next_smallest_truthful_gap"),
                "summon_anywhere_blockers",
            ),
            "authority_request_readback_status": _safe_str(authority_request_summary.get("status"), "missing"),
            "active_grant_receipt_id": active_grant_receipt_id,
            "authority_granted": authority_granted,
            "execution_denial_route": "/lens/os-binding/execute",
            "execution_denials_route": "/lens/os-binding/denials",
            "command_palette_contract_status": _safe_str(command_palette_contract.get("status"), "blocked"),
            "command_palette_contract_route": _safe_str(command_palette_contract.get("route"), "/lens/status"),
            "command_palette_contract_readback_ready": bool(command_palette_contract.get("readback_ready")),
            "command_palette_contract_bridge_script": _safe_str(command_palette_contract.get("bridge_script")),
        },
        "evidence": [
            "/lens/os-binding/plan",
            "/lens/os-binding/readiness",
            "/lens/os-binding/execute",
            "/lens/os-binding/denials",
            "/lens/status",
            "/lens/summon",
            "/lens/tray",
            "/lens/overlay",
            "/lens/host",
        ],
        "governance": _base_governance(
            service_control_authority=False,
            process_supervision_authority=False,
            resident_claim_authority=False,
            hotkey_registration_authority=False,
            tray_registration_authority=False,
            tray_icon_authority=False,
            notification_authority=False,
            window_management_authority=False,
        ),
        "message": (
            "Lens OS-binding implementation plan is read-only; it names the OS-level command palette, "
            "global hotkey, summon, tray, overlay, resident host, and authority prerequisites without "
            "opening a palette, registering hotkeys, launching processes, or claiming resident status."
        ),
    }


def lens_os_binding_readiness(
    *,
    preflight: dict[str, Any] | None = None,
    authority_request_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lens_preflight_payload = preflight if isinstance(preflight, dict) else lens_preflight()
    summon_gate = lens_summon_enablement_gate(preflight=lens_preflight_payload)
    implementation_plan = lens_os_binding_implementation_plan(
        preflight=lens_preflight_payload,
        summon_gate=summon_gate,
        authority_request_readback=authority_request_readback,
    )
    command_palette_contract = _dict_value(implementation_plan, "command_palette_contract")
    authority_request_summary = _os_binding_authority_request_summary(authority_request_readback)
    authority_granted = bool(authority_request_summary.get("authority_granted"))
    active_grant_receipt_id = _safe_str(authority_request_summary.get("active_grant_receipt_id")).strip()
    blocker_groups = _dict_value(summon_gate, "blocker_groups")
    summon_preflight = _dict_value(_dict_value(lens_preflight_payload, "surfaces"), "summon")
    overlay_preflight = _dict_value(_dict_value(lens_preflight_payload, "surfaces"), "overlay")
    hotkey_runtime = _dict_value(summon_preflight, "hotkey_runtime_readback")
    hotkey_runtime_ready = bool(hotkey_runtime.get("ready"))
    overlay_runtime = _dict_value(overlay_preflight, "overlay_runtime")
    overlay_runtime_ready = bool(overlay_runtime.get("ready"))
    required_before_enable = _string_list(summon_gate.get("required_before_enable"))
    os_level_command_palette_ready = bool(implementation_plan.get("os_level_command_palette")) or (
        bool(hotkey_runtime_ready) and bool(summon_gate.get("summon_anywhere"))
    )
    palette_blockers = [] if os_level_command_palette_ready else ["os_level_command_palette_missing"]
    if not bool(summon_gate.get("summon_anywhere")):
        palette_blockers.append("summon_anywhere_missing")
    palette_blockers.extend(_string_list(blocker_groups.get("global_hotkey_binding")))
    grouped_blockers = {
        "palette_binding": _dedupe(palette_blockers),
        "global_hotkey_binding": _string_list(blocker_groups.get("global_hotkey_binding")),
        "summon_binding": _string_list(blocker_groups.get("summon_binding")),
        "resident_host": _string_list(blocker_groups.get("resident_host")),
        "tray_presence": _string_list(blocker_groups.get("tray_presence")),
        "overlay_window": _string_list(blocker_groups.get("overlay_window")),
        "authority": _string_list(blocker_groups.get("authority")),
    }
    requirements = [
        _os_binding_requirement(
            "authority_request_readback",
            label="Authority request readback",
            ready=bool(authority_request_summary.get("readback_ready")),
            blockers=[]
            if bool(authority_request_summary.get("readback_ready"))
            else ["os_binding_authority_request_readback_missing"],
            route="/lens/os-binding/authority/requests",
            authority_required="os_level_command_palette_binding_authority",
            authority_granted=authority_granted,
            active_grant_receipt_id=active_grant_receipt_id,
        ),
        _os_binding_requirement(
            "os_level_command_palette",
            label="OS-level command palette binding",
            ready=os_level_command_palette_ready,
            blockers=grouped_blockers["palette_binding"],
            route="/lens/os-binding/plan",
            required_before_enable=["global_hotkey_binding", "summon_binding"],
            authority_required="os_level_command_palette_binding_authority",
            authority_granted=authority_granted,
            active_grant_receipt_id=active_grant_receipt_id,
        ),
        _os_binding_requirement(
            "global_hotkey_binding",
            label="Global hotkey binding",
            ready=not grouped_blockers["global_hotkey_binding"],
            blockers=grouped_blockers["global_hotkey_binding"],
            route="/lens/summon",
            required_before_enable=required_before_enable,
        ),
        _os_binding_requirement(
            "summon_binding",
            label="Summon binding",
            ready=not grouped_blockers["summon_binding"],
            blockers=grouped_blockers["summon_binding"],
            route="/lens/summon",
            required_before_enable=required_before_enable,
        ),
        _os_binding_requirement(
            "resident_host",
            label="Resident host",
            ready=bool(summon_gate.get("resident_host_ready")),
            blockers=grouped_blockers["resident_host"],
            route="/lens/host",
        ),
        _os_binding_requirement(
            "tray_presence",
            label="Tray presence",
            ready=bool(summon_gate.get("tray_ready")),
            blockers=grouped_blockers["tray_presence"],
            route="/lens/tray",
        ),
        _os_binding_requirement(
            "overlay_window",
            label="Overlay window",
            ready=bool(summon_gate.get("overlay_ready")),
            blockers=grouped_blockers["overlay_window"],
            route="/lens/overlay",
        ),
        _os_binding_requirement(
            "authority_boundary",
            label="Authority boundary",
            ready=not grouped_blockers["authority"],
            blockers=grouped_blockers["authority"],
            route="/lens/preflight",
        ),
    ]
    for requirement in requirements:
        if _safe_str(requirement.get("id")).strip() == "global_hotkey_binding":
            requirement.update(
                {
                    "runtime_ready": hotkey_runtime_ready,
                    "runtime_requirement_state": _safe_str(hotkey_runtime.get("requirement_state"), "missing"),
                    "runtime_blocker": _safe_str(hotkey_runtime.get("blocker")),
                    "hotkey_runtime_readback": hotkey_runtime,
                }
            )
        if _safe_str(requirement.get("id")).strip() == "overlay_window":
            requirement.update(
                {
                    "runtime_ready": overlay_runtime_ready,
                    "runtime_requirement_state": _safe_str(overlay_runtime.get("requirement_state"), "missing"),
                    "runtime_blocker": _safe_str(overlay_runtime.get("blocker")),
                    "overlay_runtime_readback": overlay_runtime,
                }
            )
        if _safe_str(requirement.get("id")).strip() == "os_level_command_palette":
            requirement.update(
                {
                    "readback_ready": bool(command_palette_contract.get("readback_ready")),
                    "source": _safe_str(command_palette_contract.get("source")),
                    "source_route": _safe_str(command_palette_contract.get("source_route"), "/lens/status"),
                    "bridge_script": _safe_str(command_palette_contract.get("bridge_script")),
                    "proof_script": _safe_str(command_palette_contract.get("proof_script")),
                    "local_surface": _safe_str(command_palette_contract.get("local_surface")),
                    "availability": _safe_str(command_palette_contract.get("availability")),
                }
            )
    blocked_requirements = [_safe_str(item.get("id")).strip() for item in requirements if not bool(item.get("ready"))]
    first_blocker_family = next(
        (family for family, blockers in grouped_blockers.items() if blockers),
        "",
    )
    ready = not blocked_requirements and bool(summon_gate.get("ready"))
    return {
        "ok": True,
        "kind": "lens.os_binding.readiness",
        "status": "ready_for_operator_review" if ready else "blocked",
        "audit_status": "complete",
        "route": "/lens/os-binding/readiness",
        "plan_route": "/lens/os-binding/plan",
        "status_route": "/lens/status",
        "preflight_route": "/lens/preflight",
        "authority_route": "/lens/os-binding/authority",
        "authority_request_route": "/lens/os-binding/authority/request",
        "authority_requests_route": "/lens/os-binding/authority/requests",
        "execute_route": "/lens/os-binding/execute",
        "denials_route": "/lens/os-binding/denials",
        "summon_route": "/lens/summon",
        "tray_route": "/lens/tray",
        "overlay_route": "/lens/overlay",
        "host_route": "/lens/host",
        "ready": ready,
        "os_binding_ready": ready,
        "authority_granted": authority_granted,
        "os_level_command_palette_binding_authority": authority_granted,
        "active_grant_receipt_id": active_grant_receipt_id,
        "authority_grant_consumed": authority_granted or os_level_command_palette_ready,
        "os_level_command_palette": os_level_command_palette_ready,
        "summon_anywhere": bool(summon_gate.get("summon_anywhere")) and os_level_command_palette_ready and ready,
        "acceptance_criterion": "summon_anywhere",
        "next_smallest_truthful_gap": "os_level_command_palette_binding",
        "first_blocker_family": first_blocker_family,
        "required_before_enable": required_before_enable,
        "requirements": requirements,
        "requirements_total": len(requirements),
        "requirements_ready_total": len(requirements) - len(blocked_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "blocked_requirements": blocked_requirements,
        "blockers": _dedupe([blocker for blockers in grouped_blockers.values() for blocker in blockers]),
        "blocker_groups": grouped_blockers,
        "authority_request_readback": authority_request_summary,
        "command_palette_contract": command_palette_contract,
        "implementation_plan": {
            "kind": _safe_str(implementation_plan.get("kind"), "lens.os_binding.implementation_plan"),
            "route": _safe_str(implementation_plan.get("route"), "/lens/os-binding/plan"),
            "status": _safe_str(implementation_plan.get("status"), "blocked"),
            "plan_available": bool(implementation_plan.get("plan_available")),
            "implementation_ready": bool(implementation_plan.get("implementation_ready")),
            "authority_granted": bool(implementation_plan.get("authority_granted")),
            "os_level_command_palette_binding_authority": bool(
                implementation_plan.get("os_level_command_palette_binding_authority")
            ),
            "active_grant_receipt_id": _safe_str(implementation_plan.get("active_grant_receipt_id")).strip(),
            "authority_grant_consumed": bool(implementation_plan.get("authority_grant_consumed")),
            "blocked_requirements": _string_list(implementation_plan.get("blocked_requirements")),
            "next_smallest_truthful_gap": _safe_str(
                implementation_plan.get("next_smallest_truthful_gap"),
                "os_level_command_palette_binding",
            ),
            "command_palette_contract": command_palette_contract,
            "governance": _dict_value(implementation_plan, "governance"),
        },
        "summon_enablement_gate": {
            "route": _safe_str(summon_gate.get("route"), "/lens/summon"),
            "status": _safe_str(summon_gate.get("status"), "blocked"),
            "ready": bool(summon_gate.get("ready")),
            "summon_anywhere": bool(summon_gate.get("summon_anywhere")),
            "next_smallest_truthful_gap": _safe_str(
                summon_gate.get("next_smallest_truthful_gap"),
                "summon_anywhere_blockers",
            ),
            "first_blocker_family": _safe_str(summon_gate.get("first_blocker_family")).strip(),
            "blocked_families": _string_list(summon_gate.get("blocked_families")),
            "global_hotkey_runtime_ready": bool(summon_gate.get("global_hotkey_runtime_ready")),
            "hotkey_runtime_readback": _dict_value(summon_gate, "hotkey_runtime_readback"),
            "overlay_runtime_ready": bool(summon_gate.get("overlay_runtime_ready")),
            "overlay_runtime_readback": _dict_value(summon_gate, "overlay_runtime_readback"),
        },
        "governance": _base_governance(
            service_control_authority=False,
            process_supervision_authority=False,
            resident_claim_authority=False,
            hotkey_registration_authority=False,
            tray_registration_authority=False,
            tray_icon_authority=False,
            notification_authority=False,
            window_management_authority=False,
        ),
        "message": (
            "Lens OS-binding readiness is read-only; OS-level palette binding, global hotkey, "
            "tray, overlay, and summon-anywhere remain blocked."
        ),
    }


def lens_tray_enablement_gate(
    *,
    preflight: dict[str, Any] | None = None,
    tray_runtime_readback: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lens_preflight_payload = preflight if isinstance(preflight, dict) else lens_preflight()
    surfaces = _dict_value(lens_preflight_payload, "surfaces")
    host = _dict_value(surfaces, "host")
    summon = _dict_value(surfaces, "summon")
    tray = _dict_value(surfaces, "tray")
    overlay = _dict_value(surfaces, "overlay")
    tray_binding = _dict_value(tray, "tray")
    tray_runtime = _tray_runtime_gate_readback(
        tray_runtime_readback if isinstance(tray_runtime_readback, dict) else _dict_value(tray, "tray_runtime")
    )
    blocker_set = {
        *_blockers(host),
        *_blockers(summon),
        *_blockers(tray),
        *_blockers(overlay),
    }
    tray_ready = bool(tray.get("ready"))
    tray_runtime_ready = bool(tray_runtime.get("ready"))
    resident_host_ready = bool(host.get("ready"))
    summon_ready = bool(summon.get("ready"))
    overlay_ready = bool(overlay.get("ready"))
    ready = tray_ready and resident_host_ready and summon_ready and overlay_ready
    return {
        "ok": True,
        "kind": "lens.tray.enablement_gate",
        "status": "ready_for_operator_review" if ready else "blocked",
        "route": "/lens/tray",
        "preflight_route": "/lens/preflight",
        "status_route": "/lens/status",
        "host_route": "/lens/host",
        "ready": ready,
        "tray_presence": ready,
        "tray_presence_observed": tray_runtime_ready,
        "tray_presence_source": "live_runtime_readback" if tray_runtime_ready else "not_observed",
        "tray_preflight_ready": tray_ready,
        "tray_runtime_ready": tray_runtime_ready,
        "tray_runtime_readback": tray_runtime,
        "tray_runtime_requirement_state": _safe_str(tray_runtime.get("requirement_state"), "missing"),
        "tray_runtime_blocker": _safe_str(tray_runtime.get("blocker")),
        "tray_runtime_process_alive": bool(tray_runtime.get("process_alive")),
        "tray_runtime_icon_visible": bool(tray_runtime.get("tray_icon_visible")),
        "tray_runtime_pid": _int_value(tray_runtime.get("pid")),
        "resident_host_ready": resident_host_ready,
        "summon_binding_ready": summon_ready,
        "overlay_ready": overlay_ready,
        "tray_host_enabled": bool(tray_binding.get("tray_host_enabled")),
        "tray_icon_enabled": bool(tray_binding.get("tray_icon_enabled")),
        "notification_supported": bool(tray_binding.get("notification_supported")),
        "presence_name": _safe_str(tray.get("presence_name"), "Francis Lens Tray Presence"),
        "tray_scope": _safe_str(tray.get("tray_scope"), "user_session"),
        "required_before_enable": _string_list(tray.get("required_before_enable")),
        "blockers": sorted(blocker_set),
        "tray_preflight": tray,
        "surface_dependencies": {
            "host": {
                "status": _safe_str(host.get("status"), "missing"),
                "ready": resident_host_ready,
                "route": _safe_str(host.get("route"), "/lens/host"),
                "blockers": _blockers(host),
            },
            "summon": {
                "status": _safe_str(summon.get("status"), "missing"),
                "ready": summon_ready,
                "route": "/lens/summon",
                "blockers": _blockers(summon),
            },
            "overlay": {
                "status": _safe_str(overlay.get("status"), "missing"),
                "ready": overlay_ready,
                "blockers": _blockers(overlay),
            },
        },
        "governance": _base_governance(
            service_control_authority=False,
            tray_registration_authority=False,
            tray_icon_authority=False,
            notification_authority=False,
            hotkey_registration_authority=False,
        ),
        "message": "Lens tray enablement is read-only; tray registration, tray icon, and user-session presence remain blocked.",
    }


def lens_overlay_enablement_gate(*, preflight: dict[str, Any] | None = None) -> dict[str, Any]:
    lens_preflight_payload = preflight if isinstance(preflight, dict) else lens_preflight()
    surfaces = _dict_value(lens_preflight_payload, "surfaces")
    host = _dict_value(surfaces, "host")
    summon = _dict_value(surfaces, "summon")
    tray = _dict_value(surfaces, "tray")
    overlay = _dict_value(surfaces, "overlay")
    overlay_binding = _dict_value(overlay, "overlay")
    blocker_set = {
        *_blockers(host),
        *_blockers(summon),
        *_blockers(tray),
        *_blockers(overlay),
    }
    overlay_ready = bool(overlay.get("ready"))
    resident_host_ready = bool(host.get("ready"))
    summon_ready = bool(summon.get("ready"))
    tray_ready = bool(tray.get("ready"))
    ready = overlay_ready and resident_host_ready and summon_ready and tray_ready
    return {
        "ok": True,
        "kind": "lens.overlay.enablement_gate",
        "status": "ready_for_operator_review" if ready else "blocked",
        "route": "/lens/overlay",
        "preflight_route": "/lens/preflight",
        "status_route": "/lens/status",
        "host_route": "/lens/host",
        "ready": ready,
        "overlay_window": ready,
        "overlay_preflight_ready": overlay_ready,
        "resident_host_ready": resident_host_ready,
        "summon_binding_ready": summon_ready,
        "tray_presence_ready": tray_ready,
        "overlay_enabled": bool(overlay_binding.get("enabled")),
        "window_enabled": bool(overlay_binding.get("window_enabled")),
        "always_on_top": bool(overlay_binding.get("always_on_top")),
        "dock_supported": bool(overlay_binding.get("dock_supported")),
        "focus_supported": bool(overlay_binding.get("focus_supported")),
        "click_through_supported": bool(overlay_binding.get("click_through_supported")),
        "capture_supported": bool(overlay_binding.get("capture_supported")),
        "overlay_name": _safe_str(overlay.get("overlay_name"), "Francis Lens Overlay"),
        "overlay_scope": _safe_str(overlay.get("overlay_scope"), "user_session"),
        "required_before_enable": _string_list(overlay.get("required_before_enable")),
        "blockers": sorted(blocker_set),
        "overlay_preflight": overlay,
        "surface_dependencies": {
            "host": {
                "status": _safe_str(host.get("status"), "missing"),
                "ready": resident_host_ready,
                "route": _safe_str(host.get("route"), "/lens/host"),
                "blockers": _blockers(host),
            },
            "summon": {
                "status": _safe_str(summon.get("status"), "missing"),
                "ready": summon_ready,
                "route": "/lens/summon",
                "blockers": _blockers(summon),
            },
            "tray": {
                "status": _safe_str(tray.get("status"), "missing"),
                "ready": tray_ready,
                "route": "/lens/tray",
                "blockers": _blockers(tray),
            },
        },
        "governance": _base_governance(
            window_management_authority=False,
            service_control_authority=False,
            tray_registration_authority=False,
            hotkey_registration_authority=False,
        ),
        "message": "Lens overlay enablement is read-only; overlay window, focus, and control actions remain blocked.",
    }
