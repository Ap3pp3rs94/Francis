from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

from francis.governance.approval_projection import approval_projection_fields
from francis.governance.approvals import list_requests, request as create_approval_request
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_governed_display_value, redact_secret_text
from francis.kernel.paths import data_dir
from francis.lens.host_manifest import (
    lens_host_launch_manifest,
    lens_host_persistent_supervision_enablement_preflight,
    lens_host_supervision_authority_preflight,
    lens_host_supervision_gate,
)
from francis.lens.preflight import (
    lens_overlay_enablement_gate,
    lens_preflight,
    lens_summon_enablement_gate,
    lens_tray_enablement_gate,
)
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

LENS_HOST_ACTIVATION_ACTION = "lens.host.foreground_activation"
LENS_HOST_ACTIVATION_ROUTE = "/lens/host/activation/request"
LENS_HOST_ACTIVATION_READBACK_ROUTE = "/lens/host/activation"
LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE = "/lens/host/activation/preflight"
LENS_HOST_ACTIVATION_PLAN_ROUTE = "/lens/host/activation/plan"
LENS_HOST_ACTIVATION_EXECUTE_ROUTE = "/lens/host/activation/execute"
LENS_HOST_ACTIVATION_DENIALS_ROUTE = "/lens/host/activation/denials"
LENS_HOST_SUPERVISION_AUTHORITY_ROUTE = "/lens/host/supervision/authority"
LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE = "/lens/host/supervision/authority/denials"
LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE = "/lens/host/supervision/authority/grants"
LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE = "/lens/host/supervision/authority/readiness"
LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION = "lens.host.supervision_authority"
LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE = "/lens/host/supervision/authority/request"
LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE = "/lens/host/supervision/authority/requests"
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE = "/lens/host/persistent-supervision/enablement"
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION = (
    "lens.host.persistent_supervision_enablement_authority"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE = "/lens/host/persistent-supervision/enablement/authority"
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE = (
    "/lens/host/persistent-supervision/enablement/authority/request"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/authority/requests"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/authority/grants"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/authority/readiness"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION = (
    "lens.host.persistent_supervision_enablement_execution_authority"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE = "/lens/host/persistent-supervision/enablement/execution"
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE = (
    "/lens/host/persistent-supervision/enablement/execution/request"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/execution/requests"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE = (
    "/lens/host/persistent-supervision/enablement/execution/authority"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/execution/authority/grants"
)
LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE = (
    "/lens/host/persistent-supervision/enablement/execution/readiness"
)
LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE = "/lens/resident-runtime/preflight"
LENS_RESIDENT_RUNTIME_POLICY_ROUTE = "/lens/resident-runtime/policy"
LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE = "/lens/resident-runtime/authority-grant"
LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_READINESS_ROUTE = "/lens/resident-runtime/authority-grant/readiness"
LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE = "/lens/resident-runtime/authority-grant/denials"
LENS_RESIDENT_RUNTIME_PLAN_ROUTE = "/lens/resident-runtime/plan"
LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE = "/lens/resident-runtime/execute"
LENS_RESIDENT_RUNTIME_DENIALS_ROUTE = "/lens/resident-runtime/denials"
LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE = "/lens/resident-surface/activation"
LENS_HOST_ACTIVATION_SCOPE = "system.write"

_DEFAULT_REASON = "request Lens host foreground activation"
_DEFAULT_MODE = "foreground_status_session"
_ALLOWED_MODES = {_DEFAULT_MODE}
_APPROVAL_STATUSES = ("pending", "approved", "rejected", "emergency")
_HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS = 60 * 60
_HOST_SUPERVISION_AUTHORITY_MIN_LEASE_SECONDS = 60
_HOST_SUPERVISION_AUTHORITY_MAX_LEASE_SECONDS = 24 * 60 * 60


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _str_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_safe_str(item).strip() for item in value if _safe_str(item).strip()]
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    return []


def _dedupe_strs(values: list[Any]) -> list[str]:
    return sorted({_safe_str(item).strip() for item in values if _safe_str(item).strip()})


def _safe_limit(value: Any, *, default: int = 5) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(1, min(50, parsed))


def _safe_host_supervision_authority_lease_seconds(value: Any) -> int:
    if isinstance(value, bool):
        return _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS
    return max(
        _HOST_SUPERVISION_AUTHORITY_MIN_LEASE_SECONDS,
        min(_HOST_SUPERVISION_AUTHORITY_MAX_LEASE_SECONDS, parsed),
    )


def _record_ts(value: Any) -> float:
    if isinstance(value, bool):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _now_s() -> int:
    return int(time.time())


def _filtered_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if value not in ("", {}, [], None)}


def _display(record: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_display_value(record)
    return redacted if isinstance(redacted, dict) else {}


def _activation_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "host_activation_denials"


def _resident_runtime_authority_grant_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "resident_runtime_authority_grant_denials"


def _resident_runtime_activation_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "resident_runtime_activation_denials"


def _host_supervision_authority_denial_receipt_root() -> Path:
    return data_dir() / "lens" / "host_supervision_authority_denials"


def _host_supervision_authority_grant_receipt_root() -> Path:
    return data_dir() / "lens" / "host_supervision_authority_grants"


def _persistent_supervision_enablement_authority_grant_receipt_root() -> Path:
    return data_dir() / "lens" / "pse_authority_grants"


def _persistent_supervision_enablement_execution_authority_grant_receipt_root() -> Path:
    return data_dir() / "lens" / "pse_execution_authority_grants"


def _activation_denial_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lad_{ts}_{digest}"


def _resident_runtime_authority_grant_denial_receipt_id(
    *,
    approval_id: str,
    actor: str,
    route: str,
    ts: int,
) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lragd_{ts}_{digest}"


def _resident_runtime_activation_denial_receipt_id(
    *,
    approval_id: str,
    actor: str,
    route: str,
    ts: int,
) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lrad_{ts}_{digest}"


def _host_supervision_authority_denial_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lhsad_{ts}_{digest}"


def _host_supervision_authority_grant_receipt_id(*, approval_id: str, actor: str, route: str, ts: int) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lhsag_{ts}_{digest}"


def _persistent_supervision_enablement_authority_grant_receipt_id(
    *,
    approval_id: str,
    actor: str,
    route: str,
    ts: int,
) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lpseag_{ts}_{digest}"


def _persistent_supervision_enablement_execution_authority_grant_receipt_id(
    *,
    approval_id: str,
    actor: str,
    route: str,
    ts: int,
) -> str:
    seed = f"{approval_id}:{actor}:{route}:{time.time_ns()}"
    digest = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:12]
    return f"lpseeag_{ts}_{digest}"


def _activation_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _activation_denial_receipt_root() / f"{cleaned}.json"


def _resident_runtime_authority_grant_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _resident_runtime_authority_grant_denial_receipt_root() / f"{cleaned}.json"


def _resident_runtime_activation_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _resident_runtime_activation_denial_receipt_root() / f"{cleaned}.json"


def _host_supervision_authority_denial_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _host_supervision_authority_denial_receipt_root() / f"{cleaned}.json"


def _host_supervision_authority_grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _host_supervision_authority_grant_receipt_root() / f"{cleaned}.json"


def _persistent_supervision_enablement_authority_grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _persistent_supervision_enablement_authority_grant_receipt_root() / f"{cleaned}.json"


def _persistent_supervision_enablement_execution_authority_grant_receipt_path(receipt_id: Any) -> Path | None:
    cleaned = _safe_str(receipt_id).strip()
    if not cleaned or "/" in cleaned or "\\" in cleaned or ".." in cleaned:
        return None
    return _persistent_supervision_enablement_execution_authority_grant_receipt_root() / f"{cleaned}.json"


def _atomic_write_json(path: Path, obj: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _activation_mode(value: Any) -> str:
    mode = _safe_str(value).strip().lower()
    return mode if mode in _ALLOWED_MODES else _DEFAULT_MODE


def _activation_governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_host_activation_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_ACTIVATION_ACTION,
        "approval_request_write": approval_request_write,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "denials_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "read_only_contract": read_only_contract,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "runtime_mutation_authority_granted": False,
        "next_step": "operator_decides_pending_lens_host_activation_request",
    }


def _supervision_authority_governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_host_supervision_authority_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION,
        "approval_request_write": approval_request_write,
        "request_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "preflight_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grant_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "denials_route": LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
        "readiness_route": LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
        "read_only_contract": read_only_contract,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "resident_claim_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": False,
        "next_step": "operator_decides_pending_lens_host_supervision_authority_request",
    }


def _persistent_supervision_enablement_authority_governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_host_persistent_supervision_enablement_authority_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        "approval_request_write": approval_request_write,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "read_only_contract": read_only_contract,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": False,
        "next_step": "operator_decides_pending_lens_host_persistent_supervision_enablement_authority_request",
    }


def _persistent_supervision_enablement_execution_governance(
    *,
    route: str,
    approval_request_write: bool = True,
    read_only_contract: bool = False,
) -> dict[str, Any]:
    return {
        "gate": "lens_host_persistent_supervision_enablement_execution_request",
        "route": route,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "approval_action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        "approval_request_write": approval_request_write,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "host_supervision_authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "host_supervision_authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "read_only_contract": read_only_contract,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "memory_write": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "hotkey_registration_authority": False,
        "tray_registration_authority": False,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": False,
        "next_step": "operator_decides_pending_persistent_supervision_execution_authority_request",
    }


def lens_host_activation_request_contract() -> dict[str, Any]:
    return {
        "status": "approval_request_ready",
        "route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "denials_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "method": "POST",
        "action": LENS_HOST_ACTIVATION_ACTION,
        "mode": _DEFAULT_MODE,
        "creates_approval_request": True,
        "launches_process": False,
        "installs_service": False,
        "starts_service": False,
        "registers_hotkey": False,
        "controls_overlay": False,
        "governance": _activation_governance(route=LENS_HOST_ACTIVATION_ROUTE),
    }


def lens_host_supervision_authority_request_contract() -> dict[str, Any]:
    return {
        "status": "approval_request_ready",
        "route": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "preflight_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grant_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "denials_route": LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
        "readiness_route": LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
        "method": "POST",
        "action": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION,
        "creates_approval_request": True,
        "grants_authority": False,
        "supervises_process": False,
        "restarts_process": False,
        "installs_service": False,
        "starts_service": False,
        "claims_resident": False,
        "governance": _supervision_authority_governance(route=LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE),
    }


def lens_host_persistent_supervision_enablement_authority_request_contract() -> dict[str, Any]:
    return {
        "status": "approval_request_ready",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "method": "POST",
        "action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        "creates_approval_request": True,
        "grants_authority": False,
        "updates_service_config": False,
        "enables_process_supervision": False,
        "enables_persistent_supervision": False,
        "supervises_process": False,
        "restarts_process": False,
        "installs_service": False,
        "starts_service": False,
        "writes_receipt": False,
        "writes_memory": False,
        "claims_resident": False,
        "governance": _persistent_supervision_enablement_authority_governance(
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE
        ),
    }


def lens_host_persistent_supervision_enablement_execution_request_contract() -> dict[str, Any]:
    return {
        "status": "approval_request_ready",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "host_supervision_authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "host_supervision_authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "method": "POST",
        "action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        "creates_approval_request": True,
        "requires_active_enablement_authority_grant": True,
        "grants_authority": False,
        "updates_service_config": False,
        "enables_process_supervision": False,
        "enables_persistent_supervision": False,
        "supervises_process": False,
        "restarts_process": False,
        "installs_service": False,
        "starts_service": False,
        "writes_receipt": False,
        "writes_memory": False,
        "claims_resident": False,
        "governance": _persistent_supervision_enablement_execution_governance(
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE
        ),
    }


def _permission(actor: Any, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[LENS_HOST_ACTIVATION_SCOPE],
        route=route,
        method=method,
    )


def _permission_readiness(actor: Any, *, route: str, method: str) -> dict[str, Any]:
    decision = _permission(actor, route=route, method=method)
    return {
        "ready": decision.allowed,
        "allowed": decision.allowed,
        "reason": decision.reason,
        "required_scope": LENS_HOST_ACTIVATION_SCOPE,
        "evidence": decision.evidence,
    }


def _permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "route": route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_requesting_lens_host_activation",
            "evidence": decision.evidence,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "service_control_authority": False,
        },
    }


def _supervision_authority_permission_denied(decision: ApiPermissionDecision, *, route: str) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "governance": {
            "gate": "permission_gate",
            "route": route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_requesting_lens_host_supervision_authority",
            "evidence": decision.evidence,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "resident_claim_authority": False,
        },
    }


def _persistent_supervision_enablement_authority_permission_denied(
    decision: ApiPermissionDecision, *, route: str
) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "authority_granted": False,
        "persistent_supervision_enablement_allowed": False,
        "governance": {
            "gate": "permission_gate",
            "route": route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "reason": decision.reason,
            "next_step": (
                "configure_actor_scope_before_requesting_lens_host_persistent_supervision_enablement_authority"
            ),
            "evidence": decision.evidence,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
        },
    }


def _persistent_supervision_enablement_execution_permission_denied(
    decision: ApiPermissionDecision, *, route: str
) -> dict[str, Any]:
    return {
        "ok": False,
        "applied": False,
        "executed": False,
        "approval_requested": False,
        "status": "denied",
        "error": "api_permission_denied",
        "authority_granted": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "governance": {
            "gate": "permission_gate",
            "route": route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "reason": decision.reason,
            "next_step": "configure_actor_scope_before_requesting_persistent_supervision_execution_authority",
            "evidence": decision.evidence,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": False,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
        },
    }


def _approval_item(record: dict[str, Any]) -> dict[str, Any]:
    item = dict(record) if isinstance(record, dict) else {}
    redacted = redact_governed_display_value(item)
    out = redacted if isinstance(redacted, dict) else {}
    out.update(approval_projection_fields(item))
    return out


def _activation_approval_items(
    *, limit: int
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    all_items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict) and _safe_str(item.get("action")).strip() == LENS_HOST_ACTIVATION_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
        all_items.extend(items)
    all_items.sort(
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return by_status, all_items[:limit], counts


def _supervision_authority_approval_items(
    *, limit: int
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    all_items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict)
            and _safe_str(item.get("action")).strip() == LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
        all_items.extend(items)
    all_items.sort(
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return by_status, all_items[:limit], counts


def _persistent_supervision_enablement_authority_approval_items(
    *, limit: int
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    all_items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict)
            and _safe_str(item.get("action")).strip()
            == LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
        all_items.extend(items)
    all_items.sort(
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return by_status, all_items[:limit], counts


def _persistent_supervision_enablement_execution_approval_items(
    *, limit: int
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, int]]:
    by_status: dict[str, list[dict[str, Any]]] = {}
    counts: dict[str, int] = {}
    all_items: list[dict[str, Any]] = []
    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        items = [
            _approval_item(item)
            for item in records
            if isinstance(item, dict)
            and _safe_str(item.get("action")).strip()
            == LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION
        ]
        items.sort(
            key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
            reverse=True,
        )
        counts[status] = len(items)
        by_status[status] = items[:limit]
        all_items.extend(items)
    all_items.sort(
        key=lambda item: (_record_ts(item.get("decided_ts") or item.get("ts")), _safe_str(item.get("id"))),
        reverse=True,
    )
    return by_status, all_items[:limit], counts


def _supervision_authority_approval_by_id(approval_id: Any) -> tuple[dict[str, Any] | None, str]:
    requested_id = _safe_str(approval_id).strip()
    if not requested_id:
        return None, "missing"

    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if _safe_str(record.get("id")).strip() != requested_id:
                continue
            if _safe_str(record.get("action")).strip() != LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION:
                return None, "wrong_action"
            return _approval_item(record), status
    return None, "not_found"


def _persistent_supervision_enablement_authority_approval_by_id(
    approval_id: Any,
) -> tuple[dict[str, Any] | None, str]:
    requested_id = _safe_str(approval_id).strip()
    if not requested_id:
        return None, "missing"

    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if _safe_str(record.get("id")).strip() != requested_id:
                continue
            if (
                _safe_str(record.get("action")).strip()
                != LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION
            ):
                return None, "wrong_action"
            return _approval_item(record), status
    return None, "not_found"


def _persistent_supervision_enablement_execution_approval_by_id(
    approval_id: Any,
) -> tuple[dict[str, Any] | None, str]:
    requested_id = _safe_str(approval_id).strip()
    if not requested_id:
        return None, "missing"

    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if _safe_str(record.get("id")).strip() != requested_id:
                continue
            if (
                _safe_str(record.get("action")).strip()
                != LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION
            ):
                return None, "wrong_action"
            return _approval_item(record), status
    return None, "not_found"


def _activation_approval_by_id(approval_id: Any) -> tuple[dict[str, Any] | None, str]:
    requested_id = _safe_str(approval_id).strip()
    if not requested_id:
        return None, "missing"

    for status in _APPROVAL_STATUSES:
        try:
            records = list_requests(status=status, limit=5000)
        except Exception:
            records = []
        for record in records:
            if not isinstance(record, dict):
                continue
            if _safe_str(record.get("id")).strip() != requested_id:
                continue
            if _safe_str(record.get("action")).strip() != LENS_HOST_ACTIVATION_ACTION:
                return None, "wrong_action"
            return _approval_item(record), status
    return None, "not_found"


def _activation_readback_status(counts: dict[str, int]) -> tuple[str, str]:
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_lens_host_activation_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_execution", "operator_review_emergency_activation_decision"
    if counts.get("approved", 0) > 0:
        return "approved_no_execution", "approved_activation_requires_separate_execution_slice"
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_lens_host_activation_again"
    return "none", "request_lens_host_activation_before_runtime_start"


def lens_host_activation_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _activation_approval_items(limit=safe_limit)
    total = sum(counts.values())
    status, next_step = _activation_readback_status(counts)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.host.activation.readback",
        "status": status,
        "route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_HOST_ACTIVATION_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_READBACK_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_readback",
            "read_only_contract": True,
            "next_step": next_step,
        },
    }


def _supervision_authority_readback_status(
    counts: dict[str, int],
    *,
    authority_granted: bool = False,
) -> tuple[str, str]:
    if authority_granted:
        return "authority_granted", "review_persistent_supervision_enablement_before_execution"
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_lens_host_supervision_authority_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_authority", "operator_review_emergency_supervision_authority_decision"
    if counts.get("approved", 0) > 0:
        return "approved_no_authority", "approved_request_requires_separate_supervision_authority_grant_slice"
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_lens_host_supervision_authority_again"
    return "none", "request_lens_host_supervision_authority_before_grant"


def _persistent_supervision_enablement_authority_readback_status(
    counts: dict[str, int],
) -> tuple[str, str]:
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_lens_host_persistent_supervision_enablement_authority_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_authority", "operator_review_emergency_persistent_supervision_enablement_decision"
    if counts.get("approved", 0) > 0:
        return (
            "approved_no_authority",
            "approved_request_requires_separate_persistent_supervision_enablement_grant_slice",
        )
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_persistent_supervision_enablement_authority_again"
    return "none", "request_persistent_supervision_enablement_authority_before_grant"


def _persistent_supervision_enablement_execution_readback_status(
    counts: dict[str, int],
) -> tuple[str, str]:
    if counts.get("pending", 0) > 0:
        return "pending_review", "operator_decide_pending_persistent_supervision_execution_authority_request"
    if counts.get("emergency", 0) > 0:
        return "emergency_reviewed_no_authority", "operator_review_emergency_persistent_supervision_execution_decision"
    if counts.get("approved", 0) > 0:
        return (
            "approved_no_authority",
            "approved_request_requires_separate_service_config_write_execution_grant_slice",
        )
    if counts.get("rejected", 0) > 0:
        return "rejected", "operator_may_request_persistent_supervision_execution_authority_again"
    return "none", "request_persistent_supervision_execution_authority_after_enablement_authority_grant"


def lens_host_supervision_authority_request_readback(*, limit: int = 5) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _supervision_authority_approval_items(limit=safe_limit)
    total = sum(counts.values())
    active_grants = lens_host_supervision_authority_grant_receipts(limit=1, active_only=True)
    active_grant = _as_dict(active_grants.get("active_latest"))
    authority_granted = bool(active_grant)
    status, next_step = _supervision_authority_readback_status(counts, authority_granted=authority_granted)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.host.supervision_authority.request_readback",
        "status": status,
        "route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "request_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
        "grant_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "readiness_route": LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
        "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "decision_route": "/approvals/decision",
        "approval_action": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "authority_granted": authority_granted,
        "resident_claim_allowed": False,
        "governance": {
            **_supervision_authority_governance(
                route=LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_supervision_authority_request_readback",
            "read_only_contract": True,
            "next_step": next_step,
        },
    }


def lens_host_persistent_supervision_enablement_authority_request_readback(
    *,
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _persistent_supervision_enablement_authority_approval_items(limit=safe_limit)
    total = sum(counts.values())
    status, next_step = _persistent_supervision_enablement_authority_readback_status(counts)
    latest = latest_items[0] if latest_items else None
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_authority.request_readback",
        "status": status,
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "authority_granted": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "governance": {
            **_persistent_supervision_enablement_authority_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_authority_request_readback",
            "read_only_contract": True,
            "next_step": next_step,
        },
    }


def lens_host_persistent_supervision_enablement_execution_request_readback(
    *,
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    by_status, latest_items, counts = _persistent_supervision_enablement_execution_approval_items(limit=safe_limit)
    total = sum(counts.values())
    status, next_step = _persistent_supervision_enablement_execution_readback_status(counts)
    latest = latest_items[0] if latest_items else None
    grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    active_grant_id = _safe_str(active_grant.get("receipt_id")).strip()
    execution_grants = lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_execution_grant = _as_dict(execution_grants.get("active_latest"))
    active_execution_grant_id = _safe_str(active_execution_grant.get("receipt_id")).strip()
    execution_authority_granted = bool(active_execution_grant)
    if execution_authority_granted:
        status = "authority_granted"
        next_step = "review_resident_claim_boundary_before_persistent_supervision_execution"
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_execution.request_readback",
        "status": status,
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "active_enablement_authority_grant_receipt_id": active_grant_id,
        "active_execution_authority_grant_receipt_id": active_execution_grant_id,
        "decision_route": "/approvals/decision",
        "approval_action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        "pending_count": counts.get("pending", 0),
        "approved_count": counts.get("approved", 0),
        "rejected_count": counts.get("rejected", 0),
        "emergency_count": counts.get("emergency", 0),
        "total_count": total,
        "latest": latest,
        "items": latest_items,
        "by_status": by_status,
        "authority_granted": execution_authority_granted,
        "service_config_write_authority": execution_authority_granted,
        "persistent_supervision_execution_authority": execution_authority_granted,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "governance": {
            **_persistent_supervision_enablement_execution_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_execution_request_readback",
            "read_only_contract": True,
            "persistent_supervision_enablement_authority": bool(active_grant),
            "service_config_write_authority": execution_authority_granted,
            "persistent_supervision_execution_authority": execution_authority_granted,
            "next_step": next_step,
        },
    }


def _operator_posture_readiness() -> dict[str, Any]:
    try:
        state = operator_mode_snapshot()
    except Exception as exc:
        return {
            "ready": False,
            "status": "unavailable",
            "reason": _safe_str(exc),
            "control_mode": {},
            "posture": {},
        }

    if not bool(state.get("ok")):
        return {
            "ready": False,
            "status": "unavailable",
            "reason": _safe_str(state.get("error") or "operator_mode_unavailable"),
            "control_mode": {},
            "posture": {},
        }

    control_mode = _as_dict(state.get("control_mode"))
    posture = _as_dict(state.get("posture"))
    control_mode_id = _safe_str(control_mode.get("id")).strip().lower()
    control_writes = _safe_str(control_mode.get("writes")).strip().lower()
    posture_writes = _safe_str(posture.get("writes")).strip().lower()
    blocked_reason = ""
    if control_mode_id == "observe" or control_writes == "blocked":
        blocked_reason = "observe_mode_blocks_activation"
    elif posture_writes == "blocked":
        blocked_reason = "operator_posture_blocks_activation"

    return {
        "ready": not blocked_reason,
        "status": "ready" if not blocked_reason else "blocked",
        "reason": blocked_reason,
        "control_mode": {
            "id": control_mode_id,
            "writes": control_writes,
            "implementation_status": _safe_str(control_mode.get("implementation_status")).strip(),
        },
        "posture": {
            "writes": posture_writes,
            "governance_mode": _safe_str(posture.get("governance_mode")).strip(),
            "trust_posture": _safe_str(posture.get("trust_posture")).strip(),
        },
    }


def _activation_preflight_status(blockers: list[str]) -> tuple[str, str]:
    if not blockers:
        return "ready_for_execution_slice", "implement_separate_lens_host_execution_slice"
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "blocked", "remove_lens_host_activation_blockers_before_execution"


def lens_host_activation_execution_preflight(*, approval_id: Any = "", actor: Any = "") -> dict[str, Any]:
    requested_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _activation_approval_by_id(requested_id)
    approval_status = _safe_str(_as_dict(approval).get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(actor, route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE, method="GET")
    posture = _operator_posture_readiness()
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    candidate_command = _as_dict(manifest.get("candidate_command"))
    foreground_session = _as_dict(manifest.get("foreground_session"))
    process_readback = _as_dict(manifest.get("process_readback"))
    service_plan = _as_dict(manifest.get("service_plan"))

    blockers: list[str] = []
    if not requested_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("activation_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("activation_approval_wrong_action")
    elif not approval_ready:
        blockers.append("activation_approval_not_approved")

    if not bool(permission.get("ready")):
        blockers.append("system_write_scope_not_ready")
    if not bool(posture.get("ready")):
        blockers.append("operator_posture_not_ready")
    if not bool(candidate_command.get("executable")):
        blockers.append("lens_host_foreground_command_unavailable")
    if not bool(foreground_session.get("supported")):
        blockers.append("foreground_session_not_supported")
    if bool(process_readback.get("process_alive")):
        blockers.append("lens_host_process_already_observed")
    if _safe_str(preflight.get("status")).strip() != "ready":
        blockers.append("lens_preflight_blocked")
    blockers.extend(_str_list(preflight.get("blockers")))
    blockers.append("local_process_launch_authority_not_granted")

    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _activation_preflight_status(deduped_blockers)
    return {
        "ok": True,
        "kind": "lens.host.activation.execution_preflight",
        "status": status,
        "ready": not deduped_blockers,
        "route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "approval_id": requested_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": approval,
        },
        "permission": permission,
        "operator_posture": posture,
        "host": {
            "candidate_command": candidate_command,
            "foreground_session": foreground_session,
            "process_readback": {
                "status": _safe_str(process_readback.get("status")),
                "process_alive": bool(process_readback.get("process_alive")),
                "pid_present": bool(process_readback.get("pid_present")),
                "supervision_enabled": bool(process_readback.get("supervision_enabled")),
            },
            "service_plan": {
                "status": _safe_str(service_plan.get("status")),
                "ready": bool(service_plan.get("ready")),
                "blocked_by": _as_list(service_plan.get("blocked_by")),
            },
            "preflight": {
                "status": _safe_str(preflight.get("status")),
                "ready": bool(preflight.get("ready")),
                "blockers": _as_list(preflight.get("blockers")),
            },
        },
        "blockers": deduped_blockers,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_execution_preflight",
            "next_step": next_step,
        },
    }


def _step_status(blockers: list[str], blocker_ids: set[str]) -> str:
    return "blocked" if blocker_ids.intersection(blockers) else "ready"


def _plan_step(
    step_id: str,
    *,
    label: str,
    status: str,
    source: str,
    authority_required: str = "",
    authority_granted: bool = False,
) -> dict[str, Any]:
    return {
        "id": step_id,
        "label": label,
        "status": status,
        "source": source,
        "authority_required": authority_required,
        "authority_granted": authority_granted,
    }


def _activation_execution_plan_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "blocked", "implement_lens_host_execution_authority_in_separate_slice"


def lens_host_activation_execution_plan(*, approval_id: Any = "", actor: Any = "") -> dict[str, Any]:
    preflight = lens_host_activation_execution_preflight(approval_id=approval_id, actor=actor)
    blockers = _str_list(preflight.get("blockers"))
    host = _as_dict(preflight.get("host"))
    candidate_command = _as_dict(host.get("candidate_command"))
    foreground_session = _as_dict(host.get("foreground_session"))
    process_readback = _as_dict(host.get("process_readback"))
    service_plan = _as_dict(host.get("service_plan"))
    status, next_step = _activation_execution_plan_status(blockers)
    steps = [
        _plan_step(
            "verify_exact_approval",
            label="Verify exact Lens host activation approval",
            status=_step_status(
                blockers,
                {
                    "approval_id_required",
                    "activation_approval_not_found",
                    "activation_approval_wrong_action",
                    "activation_approval_not_approved",
                },
            ),
            source=LENS_HOST_ACTIVATION_READBACK_ROUTE,
        ),
        _plan_step(
            "verify_actor_scope",
            label="Verify actor has system.write for Lens activation",
            status=_step_status(blockers, {"system_write_scope_not_ready"}),
            source=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        ),
        _plan_step(
            "verify_operator_posture",
            label="Verify operator posture allows writes",
            status=_step_status(blockers, {"operator_posture_not_ready"}),
            source="operator_mode_snapshot",
        ),
        _plan_step(
            "verify_host_command",
            label="Verify bounded foreground Lens host command",
            status=_step_status(
                blockers,
                {
                    "lens_host_foreground_command_unavailable",
                    "foreground_session_not_supported",
                    "lens_preflight_blocked",
                },
            ),
            source="/lens/host/manifest",
        ),
        _plan_step(
            "verify_no_existing_host_process",
            label="Verify no Lens host process is already observed",
            status=_step_status(blockers, {"lens_host_process_already_observed"}),
            source="/lens/host/manifest",
        ),
        _plan_step(
            "launch_foreground_status_session",
            label="Launch bounded foreground Lens host status session",
            status="blocked",
            source="future_execution_slice",
            authority_required="local_process_launch",
            authority_granted=False,
        ),
        _plan_step(
            "record_activation_receipt",
            label="Record activation receipt after launch",
            status="blocked",
            source="future_receipt_slice",
            authority_required="receipt_write",
            authority_granted=False,
        ),
    ]
    return {
        "ok": True,
        "kind": "lens.host.activation.execution_plan",
        "status": status,
        "plan_available": True,
        "execution_ready": False,
        "route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "approval_id": _safe_str(preflight.get("approval_id")).strip(),
        "actor": _redact_free_text(actor),
        "preflight": preflight,
        "plan": {
            "mode": _DEFAULT_MODE,
            "launch_kind": "foreground_status_session",
            "steps": steps,
            "candidate_command": candidate_command,
            "foreground_session": foreground_session,
            "process_readback": process_readback,
            "service_plan": service_plan,
            "would_launch_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_write_memory": False,
            "would_decide_approval": False,
        },
        "blockers": blockers,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_PLAN_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_execution_plan",
            "read_only_contract": True,
            "plan_readback_only": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "receipt_write_authority": False,
            "next_step": next_step,
        },
    }


def _execution_denial_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_host_activation"
    return "denied_no_execution_authority", "implement_lens_host_execution_authority_in_separate_slice"


def _activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_HOST_ACTIVATION_EXECUTE_ROUTE
    receipt_id = _activation_denial_receipt_id(approval_id=approval_id, actor=actor, route=route, ts=ts)
    preflight = _as_dict(denial.get("preflight"))
    approval = _as_dict(preflight.get("approval"))
    permission = _as_dict(denial.get("permission"))
    plan = _as_dict(denial.get("plan"))
    plan_body = _as_dict(plan.get("plan"))
    return _filtered_record(
        {
            "kind": "lens.host.activation.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "execution": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "would_launch_process": bool(plan_body.get("would_launch_process")),
                "would_install_service": bool(plan_body.get("would_install_service")),
                "would_start_service": bool(plan_body.get("would_start_service")),
                "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
                "would_open_overlay": bool(plan_body.get("would_open_overlay")),
                "would_write_memory": bool(plan_body.get("would_write_memory")),
                "would_decide_approval": bool(plan_body.get("would_decide_approval")),
            },
            "denial": _as_dict(denial.get("denial")),
            "governance": {
                "gate": "lens_host_activation_denial_receipt",
                "denial_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "activation_authority": False,
                "local_process_launch_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "hotkey_registration_authority": False,
                "memory_write": False,
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
            },
        }
    )


def _record_activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _activation_denial_receipt(denial)
    path = _activation_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _read_activation_denial_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _matches_filter(item: dict[str, Any], *, approval_id: str, status: str) -> bool:
    if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
        return False
    if status and _safe_str(item.get("status")).strip() != status:
        return False
    return True


def _list_activation_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _activation_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_activation_denial_receipt(path)
        if not item:
            continue
        if not _matches_filter(item, approval_id=approval_id, status=status):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def lens_host_activation_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_activation_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.host.activation.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_ACTIVATION_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_activation_denial_receipts_readback",
            "read_only_contract": True,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "next_step": "review_denial_receipts_before_adding_execution_authority",
        },
    }


def _resident_runtime_activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE
    receipt_id = _resident_runtime_activation_denial_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(denial.get("permission"))
    plan = _as_dict(denial.get("plan"))
    approval = _as_dict(plan.get("approval"))
    plan_body = _as_dict(plan.get("plan"))
    runtime_denial = _as_dict(denial.get("denial"))
    return _filtered_record(
        {
            "kind": "lens.resident_runtime.activation.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("selected_status") or approval.get("status")).strip(),
                "approved": bool(approval.get("selected_approved") or approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "runtime": {
                "plan_available": bool(plan.get("plan_available")),
                "runtime_ready": bool(plan.get("runtime_ready")),
                "resident_claim_allowed": bool(plan.get("resident_claim_allowed")),
                "execution_ready": False,
            },
            "execution": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "would_launch_process": bool(plan_body.get("would_launch_process")),
                "would_supervise_process": bool(plan_body.get("would_supervise_process")),
                "would_restart_process": bool(plan_body.get("would_restart_process")),
                "would_install_service": bool(plan_body.get("would_install_service")),
                "would_start_service": bool(plan_body.get("would_start_service")),
                "would_register_tray": bool(plan_body.get("would_register_tray")),
                "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
                "would_open_overlay": bool(plan_body.get("would_open_overlay")),
                "would_write_memory": bool(plan_body.get("would_write_memory")),
                "would_write_receipt": bool(plan_body.get("would_write_receipt")),
                "would_decide_approval": bool(plan_body.get("would_decide_approval")),
                "would_claim_resident": bool(plan_body.get("would_claim_resident")),
            },
            "denial": runtime_denial,
            "governance": {
                "gate": "lens_resident_runtime_activation_denial_receipt",
                "denial_boundary": True,
                "resident_runtime_boundary": True,
                "activation_authority": False,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "window_management_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
                "runtime_mutation_authority_granted": False,
                "authority_granted": False,
            },
        }
    )


def _record_resident_runtime_activation_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _resident_runtime_activation_denial_receipt(denial)
    path = _resident_runtime_activation_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _read_resident_runtime_activation_denial_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _list_resident_runtime_activation_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _resident_runtime_activation_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_resident_runtime_activation_denial_receipt(path)
        if not item:
            continue
        if not _matches_filter(item, approval_id=approval_id, status=status):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def lens_resident_runtime_activation_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_resident_runtime_activation_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.resident_runtime.activation.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_RESIDENT_RUNTIME_DENIALS_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_activation_denial_receipts_readback",
            "read_only_contract": True,
            "resident_runtime_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "next_step": "review_runtime_denial_receipts_before_adding_resident_runtime_authority",
        },
    }


def _resident_runtime_authority_grant_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE
    receipt_id = _resident_runtime_authority_grant_denial_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(denial.get("permission"))
    preflight = _as_dict(denial.get("preflight"))
    policy = _as_dict(denial.get("policy"))
    approval = _as_dict(policy.get("approval"))
    grant_denial = _as_dict(denial.get("grant_denial"))
    return _filtered_record(
        {
            "kind": "lens.resident_runtime.execution_authority_grant.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "policy": {
                "policy_contract_ready": bool(policy.get("policy_contract_ready")),
                "execution_policy_ready": bool(policy.get("execution_policy_ready")),
                "grant_ready": bool(policy.get("grant_ready")),
                "authority_grant_ready": bool(policy.get("authority_grant_ready")),
                "runtime_ready": bool(policy.get("runtime_ready")),
                "resident_claim_allowed": bool(policy.get("resident_claim_allowed")),
            },
            "preflight": {
                "ready": bool(preflight.get("ready")),
                "grant_ready": bool(preflight.get("grant_ready")),
                "authority_grant_ready": bool(preflight.get("authority_grant_ready")),
                "runtime_ready": bool(preflight.get("runtime_ready")),
                "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
            },
            "authority_grant": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "authority_granted": bool(denial.get("authority_granted")),
                "boundary_ready": bool(denial.get("boundary_ready")),
                "grant_ready": bool(denial.get("grant_ready")),
                "authority_grant_ready": bool(denial.get("authority_grant_ready")),
                "runtime_ready": bool(denial.get("runtime_ready")),
                "resident_claim_allowed": bool(denial.get("resident_claim_allowed")),
            },
            "grant_denial": grant_denial,
            "governance": {
                "gate": "lens_resident_runtime_execution_authority_grant_denial_receipt",
                "authority_grant_boundary": True,
                "denial_boundary": True,
                "resident_runtime_boundary": True,
                "activation_authority": False,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "window_management_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
                "runtime_mutation_authority_granted": False,
                "authority_granted": False,
            },
        }
    )


def _record_resident_runtime_authority_grant_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _resident_runtime_authority_grant_denial_receipt(denial)
    path = _resident_runtime_authority_grant_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _read_resident_runtime_authority_grant_denial_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _list_resident_runtime_authority_grant_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _resident_runtime_authority_grant_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_resident_runtime_authority_grant_denial_receipt(path)
        if not item:
            continue
        if not _matches_filter(item, approval_id=approval_id, status=status):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def lens_resident_runtime_authority_grant_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_resident_runtime_authority_grant_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.resident_runtime.execution_authority_grant.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE,
        "authority_grant_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_execution_authority_grant_denial_receipts_readback",
            "read_only_contract": True,
            "authority_grant_boundary": True,
            "resident_runtime_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "service_control_authority": False,
            "hotkey_registration_authority": False,
            "tray_registration_authority": False,
            "overlay_control_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "next_step": "review_authority_grant_denial_receipts_before_adding_resident_runtime_authority",
        },
    }


def _readiness_requirement(
    requirement_id: str,
    *,
    label: str,
    route: str,
    ready: bool,
    status: Any = "",
    blockers: Any = None,
    authority_required: str = "",
    authority_granted: bool = False,
) -> dict[str, Any]:
    return _filtered_record(
        {
            "id": requirement_id,
            "label": label,
            "route": route,
            "status": _safe_str(status).strip() or ("ready" if ready else "blocked"),
            "ready": ready,
            "blockers": _str_list(blockers),
            "authority_required": authority_required,
            "authority_granted": authority_granted,
        }
    )


def lens_resident_runtime_authority_grant_readiness_audit(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    runtime_preflight = lens_resident_runtime_activation_preflight(approval_id=safe_approval_id, actor=actor)
    runtime_policy = lens_resident_runtime_execution_policy_contract(approval_id=safe_approval_id, actor=actor)
    runtime_authority_grant = deny_lens_resident_runtime_execution_authority_grant(
        approval_id=safe_approval_id,
        actor=actor,
        reason="audit Lens resident runtime authority grant readiness",
        route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        method="POST",
        record_receipt=False,
    )
    denial_receipts = lens_resident_runtime_authority_grant_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
    )
    runtime_plan = lens_resident_runtime_activation_plan(approval_id=safe_approval_id, actor=actor)
    runtime_denial = deny_lens_resident_runtime_activation_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="audit Lens resident runtime execution boundary",
        route=LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        method="POST",
    )
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    supervision_gate = lens_host_supervision_gate(manifest=manifest)
    supervision_authority_preflight = lens_host_supervision_authority_preflight(manifest=manifest)
    supervision_authority_denial = deny_lens_host_supervision_authority_grant(
        actor=actor,
        reason="audit Lens host supervision authority boundary",
        route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        method="POST",
    )
    summon_gate = lens_summon_enablement_gate(preflight=preflight)
    tray_gate = lens_tray_enablement_gate(preflight=preflight)
    overlay_gate = lens_overlay_enablement_gate(preflight=preflight)
    approval = _as_dict(runtime_preflight.get("approval"))
    permission = _as_dict(runtime_preflight.get("permission"))
    posture = _as_dict(runtime_preflight.get("operator_posture"))
    grant_boundary_observed = (
        bool(runtime_authority_grant.get("boundary_ready"))
        and not bool(runtime_authority_grant.get("applied"))
        and not bool(runtime_authority_grant.get("executed"))
        and not bool(runtime_authority_grant.get("authority_granted"))
    )
    denial_receipt_readback_ready = _safe_str(denial_receipts.get("status")).strip() in {"empty", "readback_ready"}
    runtime_execution_boundary_observed = not bool(runtime_denial.get("applied")) and not bool(
        runtime_denial.get("executed")
    )
    supervision_authority_boundary_observed = (
        bool(supervision_authority_denial.get("boundary_ready"))
        and not bool(supervision_authority_denial.get("applied"))
        and not bool(supervision_authority_denial.get("executed"))
        and not bool(supervision_authority_denial.get("authority_granted"))
    )
    blockers = _dedupe_strs(
        [
            *_str_list(runtime_preflight.get("blockers")),
            *_str_list(runtime_policy.get("blockers")),
            *_str_list(runtime_authority_grant.get("blockers")),
            *_str_list(runtime_plan.get("blockers")),
            *_str_list(runtime_denial.get("blockers")),
            *_str_list(supervision_gate.get("blockers")),
            *_str_list(supervision_authority_preflight.get("blockers")),
            *_str_list(supervision_authority_denial.get("blockers")),
            *_str_list(summon_gate.get("blockers")),
            *_str_list(tray_gate.get("blockers")),
            *_str_list(overlay_gate.get("blockers")),
        ]
    )
    requirements = [
        _readiness_requirement(
            "exact_activation_approval",
            label="Exact approved Lens activation request",
            route=LENS_HOST_ACTIVATION_READBACK_ROUTE,
            ready=bool(approval.get("approved")),
            status="ready" if bool(approval.get("approved")) else "blocked",
            blockers=[
                item
                for item in blockers
                if item
                in {
                    "approval_id_required",
                    "activation_approval_not_found",
                    "activation_approval_wrong_action",
                    "activation_approval_not_approved",
                }
            ],
            authority_required="operator_approval",
            authority_granted=bool(approval.get("approved")),
        ),
        _readiness_requirement(
            "actor_scope",
            label="Actor has resident runtime write-review scope",
            route=LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
            ready=bool(permission.get("ready")),
            status="ready" if bool(permission.get("ready")) else "blocked",
            blockers=["system_write_scope_not_ready"] if "system_write_scope_not_ready" in blockers else [],
            authority_required=LENS_HOST_ACTIVATION_SCOPE,
            authority_granted=bool(permission.get("ready")),
        ),
        _readiness_requirement(
            "operator_posture",
            label="Operator posture allows write review",
            route="operator_mode_snapshot",
            ready=bool(posture.get("ready")),
            status="ready" if bool(posture.get("ready")) else "blocked",
            blockers=["operator_posture_not_ready"] if "operator_posture_not_ready" in blockers else [],
        ),
        _readiness_requirement(
            "execution_policy_contract",
            label="Resident runtime execution policy contract",
            route=LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
            ready=bool(runtime_policy.get("policy_contract_ready")),
            status=runtime_policy.get("status"),
        ),
        _readiness_requirement(
            "authority_grant_denial_boundary",
            label="Authority grant denial boundary is observed",
            route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
            ready=grant_boundary_observed,
            status=runtime_authority_grant.get("status"),
            blockers=runtime_authority_grant.get("blockers"),
            authority_required="resident_runtime_execution_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "authority_grant_denial_receipts",
            label="Authority grant denial receipt readback",
            route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE,
            ready=denial_receipt_readback_ready,
            status=denial_receipts.get("status"),
        ),
        _readiness_requirement(
            "resident_supervision_gate",
            label="Resident supervision and service gates",
            route="/lens/host/supervision",
            ready=bool(supervision_gate.get("ready")),
            status=supervision_gate.get("status"),
            blockers=supervision_gate.get("blockers"),
            authority_required="process_supervision_and_service_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "resident_host_supervision_authority_preflight",
            label="Resident host supervision authority preflight",
            route="/lens/host/supervision/authority",
            ready=bool(supervision_authority_preflight.get("ready")),
            status=supervision_authority_preflight.get("status"),
            blockers=supervision_authority_preflight.get("blockers"),
            authority_required="process_supervision_and_service_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "resident_host_supervision_authority_denial_boundary",
            label="Resident host supervision authority denial boundary",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=supervision_authority_boundary_observed,
            status=supervision_authority_denial.get("status"),
            blockers=supervision_authority_denial.get("blockers"),
            authority_required="process_supervision_and_service_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "summon_gate",
            label="Summon and hotkey gate",
            route="/lens/summon",
            ready=bool(summon_gate.get("ready")),
            status=summon_gate.get("status"),
            blockers=summon_gate.get("blockers"),
            authority_required="summon_and_hotkey_registration",
            authority_granted=False,
        ),
        _readiness_requirement(
            "tray_gate",
            label="Tray presence gate",
            route="/lens/tray",
            ready=bool(tray_gate.get("ready")),
            status=tray_gate.get("status"),
            blockers=tray_gate.get("blockers"),
            authority_required="tray_registration",
            authority_granted=False,
        ),
        _readiness_requirement(
            "overlay_gate",
            label="Overlay window gate",
            route="/lens/overlay",
            ready=bool(overlay_gate.get("ready")),
            status=overlay_gate.get("status"),
            blockers=overlay_gate.get("blockers"),
            authority_required="overlay_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "runtime_activation_plan",
            label="Resident runtime activation plan",
            route=LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
            ready=bool(runtime_plan.get("runtime_ready")),
            status=runtime_plan.get("status"),
            blockers=runtime_plan.get("blockers"),
            authority_required="resident_runtime_execution_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "runtime_execution_denial_boundary",
            label="Runtime execution denial boundary is observed",
            route=LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
            ready=runtime_execution_boundary_observed,
            status=runtime_denial.get("status"),
            blockers=runtime_denial.get("blockers"),
            authority_required="resident_runtime_execution_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "authority_grant_implementation",
            label="Explicit supervised authority grant implementation",
            route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
            ready="resident_runtime_authority_grant_not_implemented" not in blockers,
            status=(
                "ready" if "resident_runtime_authority_grant_not_implemented" not in blockers else "not_implemented"
            ),
            blockers=(
                ["resident_runtime_authority_grant_not_implemented"]
                if "resident_runtime_authority_grant_not_implemented" in blockers
                else []
            ),
            authority_required="resident_runtime_execution_authority",
            authority_granted=False,
        ),
    ]
    blocked_requirements = [item for item in requirements if not bool(item.get("ready"))]
    ready_requirements = [item for item in requirements if bool(item.get("ready"))]
    ready = not blocked_requirements and not blockers
    return {
        "ok": True,
        "kind": "lens.resident_runtime.execution_authority_grant.readiness_audit",
        "status": "ready" if ready else "blocked",
        "audit_status": "complete",
        "route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_READINESS_ROUTE,
        "preflight_route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
        "policy_route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
        "authority_grant_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        "denials_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "ready": ready,
        "grant_ready": ready,
        "authority_grant_ready": ready,
        "runtime_ready": bool(runtime_plan.get("runtime_ready")) and ready,
        "resident_claim_allowed": bool(runtime_plan.get("resident_claim_allowed")) and ready,
        "boundary_observed": grant_boundary_observed,
        "denial_receipt_readback_ready": denial_receipt_readback_ready,
        "receipt_count": int(denial_receipts.get("total") or 0),
        "latest_receipt_id": _safe_str(_as_dict(denial_receipts.get("latest")).get("receipt_id")).strip(),
        "requirements_total": len(requirements),
        "requirements_ready_total": len(ready_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "requirements": requirements,
        "blocked_requirements": [item.get("id") for item in blocked_requirements],
        "blockers": blockers,
        "source_readbacks": {
            "preflight_status": _safe_str(runtime_preflight.get("status")).strip(),
            "policy_status": _safe_str(runtime_policy.get("status")).strip(),
            "authority_grant_status": _safe_str(runtime_authority_grant.get("status")).strip(),
            "denial_receipts_status": _safe_str(denial_receipts.get("status")).strip(),
            "plan_status": _safe_str(runtime_plan.get("status")).strip(),
            "execute_status": _safe_str(runtime_denial.get("status")).strip(),
            "supervision_status": _safe_str(supervision_gate.get("status")).strip(),
            "supervision_authority_preflight_status": _safe_str(supervision_authority_preflight.get("status")).strip(),
            "supervision_authority_denial_status": _safe_str(supervision_authority_denial.get("status")).strip(),
            "summon_status": _safe_str(summon_gate.get("status")).strip(),
            "tray_status": _safe_str(tray_gate.get("status")).strip(),
            "overlay_status": _safe_str(overlay_gate.get("status")).strip(),
        },
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_READINESS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_execution_authority_grant_readiness_audit",
            "read_only_contract": True,
            "audit_only": True,
            "authority_grant_boundary": True,
            "resident_runtime_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "runtime_mutation_authority_granted": False,
            "authority_granted": False,
            "next_step": "resolve_resident_runtime_authority_grant_readiness_blockers_before_implementation",
        },
    }


def lens_host_supervision_authority_readiness_audit(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    manifest = lens_host_launch_manifest()
    supervision_gate = lens_host_supervision_gate(manifest=manifest)
    preflight = lens_host_supervision_authority_preflight(manifest=manifest)
    authority_grant = grant_lens_host_supervision_authority(
        approval_id=safe_approval_id,
        actor=actor,
        reason="audit Lens host supervision authority readiness",
        route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        method="POST",
        record_receipt=False,
    )
    denial_receipts = lens_host_supervision_authority_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
    )
    grant_receipts = lens_host_supervision_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
    )
    active_grant = _as_dict(grant_receipts.get("active_latest"))
    authority_granted = bool(active_grant)
    approval = _as_dict(authority_grant.get("approval"))
    permission = _as_dict(authority_grant.get("permission"))
    boundary_observed = authority_granted or (
        bool(authority_grant.get("boundary_ready"))
        and not bool(authority_grant.get("applied"))
        and not bool(authority_grant.get("executed"))
        and not bool(authority_grant.get("authority_granted"))
    )
    denial_receipt_readback_ready = _safe_str(denial_receipts.get("status")).strip() in {
        "empty",
        "readback_ready",
    }
    grant_receipt_readback_ready = _safe_str(grant_receipts.get("status")).strip() in {
        "empty",
        "readback_ready",
    }
    blockers = _dedupe_strs(
        [
            *_str_list(supervision_gate.get("blockers")),
            *_str_list(preflight.get("blockers")),
            *_str_list(authority_grant.get("blockers")),
        ]
    )
    authority_blocker_names = {
        "process_supervision_authority_not_granted",
        "process_restart_authority_not_granted",
        "service_install_authority_not_granted",
        "service_control_authority_not_granted",
        "resident_host_supervision_authority_not_granted",
        "receipt_write_authority_not_granted",
        "resident_claim_authority_not_granted",
    }
    if authority_granted:
        blockers = [item for item in blockers if item not in authority_blocker_names]
    requirements = [
        _readiness_requirement(
            "exact_supervision_authority_approval",
            label="Exact approved host supervision authority request",
            route=LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
            ready=bool(approval.get("approved")),
            status="ready" if bool(approval.get("approved")) else "blocked",
            blockers=[
                item
                for item in blockers
                if item
                in {
                    "approval_id_required",
                    "supervision_authority_approval_not_found",
                    "supervision_authority_approval_wrong_action",
                    "supervision_authority_approval_not_approved",
                }
            ],
            authority_required="operator_approval",
            authority_granted=bool(approval.get("approved")),
        ),
        _readiness_requirement(
            "actor_scope",
            label="Actor has host supervision write-review scope",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=bool(permission.get("ready")),
            status="ready" if bool(permission.get("ready")) else "blocked",
            blockers=["system_write_scope_not_ready"] if "system_write_scope_not_ready" in blockers else [],
            authority_required=LENS_HOST_ACTIVATION_SCOPE,
            authority_granted=bool(permission.get("ready")),
        ),
        _readiness_requirement(
            "resident_supervision_gate",
            label="Resident host supervision gate",
            route="/lens/host/supervision",
            ready=bool(supervision_gate.get("ready")),
            status=supervision_gate.get("status"),
            blockers=supervision_gate.get("blockers"),
            authority_required="process_supervision_and_service_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "host_supervision_authority_preflight",
            label="Host supervision authority preflight contract",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=bool(preflight.get("preflight_ready")),
            status="ready" if bool(preflight.get("preflight_ready")) else preflight.get("status"),
            blockers=[],
            authority_required="process_supervision_and_service_control",
            authority_granted=False,
        ),
        _readiness_requirement(
            "host_supervision_authority_denial_boundary",
            label="Host supervision authority denial boundary is observed",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=boundary_observed,
            status=authority_grant.get("status"),
            blockers=authority_grant.get("blockers"),
            authority_required="process_supervision_and_service_control",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "host_supervision_authority_denial_receipts",
            label="Host supervision authority denial receipt readback",
            route=LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
            ready=denial_receipt_readback_ready,
            status=denial_receipts.get("status"),
        ),
        _readiness_requirement(
            "host_supervision_authority_grant_receipts",
            label="Host supervision authority grant receipt readback",
            route=LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
            ready=grant_receipt_readback_ready,
            status=grant_receipts.get("status"),
            authority_required="process_supervision_and_service_control",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "process_supervision_authority",
            label="Process supervision authority",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=authority_granted and "process_supervision_authority_not_granted" not in blockers,
            status="ready"
            if authority_granted and "process_supervision_authority_not_granted" not in blockers
            else "blocked",
            blockers=(
                ["process_supervision_authority_not_granted"]
                if not authority_granted or "process_supervision_authority_not_granted" in blockers
                else []
            ),
            authority_required="process_supervision_authority",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "process_restart_authority",
            label="Process restart authority",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=authority_granted and "process_restart_authority_not_granted" not in blockers,
            status="ready"
            if authority_granted and "process_restart_authority_not_granted" not in blockers
            else "blocked",
            blockers=(
                ["process_restart_authority_not_granted"]
                if not authority_granted or "process_restart_authority_not_granted" in blockers
                else []
            ),
            authority_required="process_restart_authority",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "service_install_authority",
            label="Service install authority",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=authority_granted and "service_install_authority_not_granted" not in blockers,
            status="ready"
            if authority_granted and "service_install_authority_not_granted" not in blockers
            else "blocked",
            blockers=(
                ["service_install_authority_not_granted"]
                if not authority_granted or "service_install_authority_not_granted" in blockers
                else []
            ),
            authority_required="service_install_authority",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "service_control_authority",
            label="Service control authority",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=authority_granted and "service_control_authority_not_granted" not in blockers,
            status="ready"
            if authority_granted and "service_control_authority_not_granted" not in blockers
            else "blocked",
            blockers=(
                ["service_control_authority_not_granted"]
                if not authority_granted or "service_control_authority_not_granted" in blockers
                else []
            ),
            authority_required="service_control_authority",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "resident_claim_authority",
            label="Resident claim authority",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=authority_granted and "resident_claim_authority_not_granted" not in blockers,
            status="ready"
            if authority_granted and "resident_claim_authority_not_granted" not in blockers
            else "blocked",
            blockers=(
                ["resident_claim_authority_not_granted"]
                if not authority_granted or "resident_claim_authority_not_granted" in blockers
                else []
            ),
            authority_required="resident_claim_authority",
            authority_granted=authority_granted,
        ),
        _readiness_requirement(
            "authority_grant_implementation",
            label="Explicit host supervision authority grant implementation",
            route=LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
            ready=True,
            status="ready",
            blockers=[],
            authority_required="process_supervision_and_service_control",
            authority_granted=authority_granted,
        ),
    ]
    blocked_requirements = [item for item in requirements if not bool(item.get("ready"))]
    ready_requirements = [item for item in requirements if bool(item.get("ready"))]
    ready = not blocked_requirements and not blockers
    return {
        "ok": True,
        "kind": "lens.host.supervision_authority.readiness_audit",
        "status": "ready" if ready else "blocked",
        "audit_status": "complete",
        "route": LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "preflight_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "denials_route": LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
        "grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "requests_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "request_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "supervision_route": "/lens/host/supervision",
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "ready": ready,
        "preflight_ready": bool(preflight.get("preflight_ready")),
        "authority_ready": authority_granted and bool(preflight.get("preflight_ready")),
        "supervision_ready": bool(preflight.get("supervision_ready")) and ready,
        "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")) and ready,
        "boundary_observed": boundary_observed,
        "denial_receipt_readback_ready": denial_receipt_readback_ready,
        "grant_receipt_readback_ready": grant_receipt_readback_ready,
        "receipt_count": int(denial_receipts.get("total") or 0),
        "latest_receipt_id": _safe_str(_as_dict(denial_receipts.get("latest")).get("receipt_id")).strip(),
        "grant_receipt_count": int(grant_receipts.get("total") or 0),
        "latest_grant_receipt_id": _safe_str(_as_dict(grant_receipts.get("latest")).get("receipt_id")).strip(),
        "active_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "requirements_total": len(requirements),
        "requirements_ready_total": len(ready_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "requirements": requirements,
        "blocked_requirements": [item.get("id") for item in blocked_requirements],
        "blockers": blockers,
        "source_readbacks": {
            "supervision_gate_status": _safe_str(supervision_gate.get("status")).strip(),
            "preflight_status": _safe_str(preflight.get("status")).strip(),
            "approval_status": _safe_str(approval.get("status")).strip(),
            "authority_grant_status": _safe_str(authority_grant.get("status")).strip(),
            "denial_receipts_status": _safe_str(denial_receipts.get("status")).strip(),
            "grant_receipts_status": _safe_str(grant_receipts.get("status")).strip(),
        },
        "governance": {
            **_supervision_authority_governance(
                route=LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_supervision_authority_readiness_audit",
            "read_only_contract": True,
            "audit_only": True,
            "preflight_only": True,
            "authority_grant_boundary": True,
            "resident_host_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": authority_granted,
            "process_restart_authority": authority_granted,
            "service_install_authority": authority_granted,
            "service_control_authority": authority_granted,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": authority_granted,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": authority_granted,
            "mutation_authority_granted": False,
            "authority_granted": authority_granted,
            "next_step": "resolve_host_supervision_authority_readiness_blockers_before_implementation",
        },
    }


def lens_host_persistent_supervision_enablement_authority_readiness_audit(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    preflight = lens_host_persistent_supervision_enablement_preflight()
    denial = deny_lens_host_persistent_supervision_enablement(
        actor=actor,
        reason="audit Lens persistent supervision enablement authority readiness",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        method="POST",
    )
    authority_grant = grant_lens_host_persistent_supervision_enablement_authority(
        approval_id=safe_approval_id,
        actor=actor,
        reason="audit Lens persistent supervision enablement authority grant readiness",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        method="POST",
        record_receipt=False,
    )
    grant_receipts = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
    )
    active_grant = _as_dict(grant_receipts.get("active_latest"))
    enablement_authority_granted = bool(active_grant)
    requests = lens_host_persistent_supervision_enablement_authority_request_readback(limit=safe_limit)
    approval, approval_lookup_status = _persistent_supervision_enablement_authority_approval_by_id(safe_approval_id)
    approval = _as_dict(approval)
    approval_status = _safe_str(approval.get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(
        actor,
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        method="POST",
    )
    boundary_observed = (
        bool(denial.get("boundary_ready"))
        and not bool(denial.get("applied"))
        and not bool(denial.get("executed"))
        and not bool(denial.get("authority_granted"))
        and not bool(denial.get("service_config_updated"))
    )
    grant_boundary_observed = enablement_authority_granted or (
        bool(authority_grant.get("boundary_ready"))
        and not bool(authority_grant.get("applied"))
        and not bool(authority_grant.get("executed"))
        and not bool(authority_grant.get("authority_granted"))
    )
    request_readback_ready = _safe_str(requests.get("kind")).strip() == (
        "lens.host.persistent_supervision_enablement_authority.request_readback"
    )
    grant_receipt_readback_ready = _safe_str(grant_receipts.get("status")).strip() in {
        "empty",
        "readback_ready",
    }
    blockers = _dedupe_strs(
        [
            *_str_list(preflight.get("blockers")),
            *_str_list(denial.get("blockers")),
            *_str_list(authority_grant.get("blockers")),
        ]
    )
    if enablement_authority_granted:
        blockers = [
            item
            for item in blockers
            if item
            not in {
                "persistent_supervision_enablement_authority_not_granted",
                "receipt_write_authority_not_granted",
            }
        ]
    if approval_lookup_status == "missing":
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("persistent_supervision_enablement_authority_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("persistent_supervision_enablement_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("persistent_supervision_enablement_authority_approval_not_approved")
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    blockers = _dedupe_strs(blockers)
    approval_blockers = [
        item
        for item in blockers
        if item
        in {
            "approval_id_required",
            "persistent_supervision_enablement_authority_approval_not_found",
            "persistent_supervision_enablement_authority_approval_wrong_action",
            "persistent_supervision_enablement_authority_approval_not_approved",
        }
    ]
    requirements = [
        _readiness_requirement(
            "exact_persistent_supervision_enablement_authority_approval",
            label="Exact approved persistent supervision enablement authority request",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
            ready=approval_ready,
            status="ready" if approval_ready else "blocked",
            blockers=approval_blockers,
            authority_required="operator_approval",
            authority_granted=approval_ready,
        ),
        _readiness_requirement(
            "actor_scope",
            label="Actor has persistent supervision enablement write-review scope",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
            ready=bool(permission.get("ready")),
            status="ready" if bool(permission.get("ready")) else "blocked",
            blockers=["system_write_scope_not_ready"] if "system_write_scope_not_ready" in blockers else [],
            authority_required=LENS_HOST_ACTIVATION_SCOPE,
            authority_granted=bool(permission.get("ready")),
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_preflight",
            label="Persistent supervision enablement preflight contract",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
            ready=bool(preflight.get("preflight_ready")),
            status="ready" if bool(preflight.get("preflight_ready")) else preflight.get("status"),
            blockers=[],
        ),
        _readiness_requirement(
            "active_host_supervision_authority_grant",
            label="Active host supervision authority grant",
            route=LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
            ready=bool(preflight.get("authority_grant_active")),
            status="ready" if bool(preflight.get("authority_grant_active")) else "blocked",
            blockers=(
                ["host_supervision_authority_grant_not_active"]
                if "host_supervision_authority_grant_not_active" in blockers
                else []
            ),
            authority_required="host_supervision_authority",
            authority_granted=bool(preflight.get("authority_grant_active")),
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_denial_boundary",
            label="Persistent supervision enablement denial boundary is observed",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
            ready=boundary_observed,
            status=denial.get("status"),
            blockers=denial.get("blockers"),
            authority_required="service_config_write_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_authority_request_readback",
            label="Persistent supervision enablement authority request readback",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
            ready=request_readback_ready,
            status=requests.get("status"),
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_authority_grant_boundary",
            label="Persistent supervision enablement authority grant boundary",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
            ready=grant_boundary_observed,
            status=authority_grant.get("status"),
            blockers=authority_grant.get("blockers"),
            authority_required="persistent_supervision_enablement_authority",
            authority_granted=enablement_authority_granted,
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_authority_grant_receipts",
            label="Persistent supervision enablement authority grant receipt readback",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
            ready=grant_receipt_readback_ready,
            status=grant_receipts.get("status"),
            authority_required="persistent_supervision_enablement_authority",
            authority_granted=enablement_authority_granted,
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_authority",
            label="Persistent supervision enablement authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
            ready=enablement_authority_granted,
            status="ready" if enablement_authority_granted else "blocked",
            blockers=(
                ["persistent_supervision_enablement_authority_not_granted"] if not enablement_authority_granted else []
            ),
            authority_required="persistent_supervision_enablement_authority",
            authority_granted=enablement_authority_granted,
        ),
        _readiness_requirement(
            "service_config_write_authority",
            label="Service config write authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
            ready=False,
            status="blocked",
            blockers=["service_config_write_authority_not_granted"],
            authority_required="service_config_write_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "persistent_supervision_execution_authority",
            label="Persistent supervision execution authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
            ready=False,
            status="blocked",
            blockers=["persistent_supervision_execution_authority_not_granted"],
            authority_required="persistent_supervision_execution_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "receipt_write_authority",
            label="Persistent supervision receipt write authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
            ready=False,
            status="blocked",
            blockers=["receipt_write_authority_not_granted"],
            authority_required="receipt_write_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "resident_claim_authority",
            label="Resident claim authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
            ready=False,
            status="blocked",
            blockers=["resident_claim_authority_not_granted"],
            authority_required="resident_claim_authority",
            authority_granted=False,
        ),
    ]
    blocked_requirements = [item for item in requirements if not bool(item.get("ready"))]
    ready_requirements = [item for item in requirements if bool(item.get("ready"))]
    ready = False
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_authority.readiness_audit",
        "status": "blocked",
        "audit_status": "complete",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "host_supervision_authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "ready": ready,
        "preflight_ready": bool(preflight.get("preflight_ready")),
        "approval_ready": approval_ready,
        "request_readback_ready": request_readback_ready,
        "boundary_observed": boundary_observed,
        "grant_boundary_observed": grant_boundary_observed,
        "grant_receipt_readback_ready": grant_receipt_readback_ready,
        "authority_grant_active": bool(preflight.get("authority_grant_active")),
        "active_grant_receipt_id": _safe_str(preflight.get("active_grant_receipt_id")).strip(),
        "enablement_authority_granted": enablement_authority_granted,
        "active_enablement_authority_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "enablement_ready": False,
        "persistent_supervision_enablement_allowed": False,
        "persistent_supervision_ready": False,
        "service_config_updated": False,
        "resident_claim_allowed": False,
        "authority_granted": enablement_authority_granted,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "grant_receipt_count": int(grant_receipts.get("total") or 0),
        "latest_grant_receipt_id": _safe_str(_as_dict(grant_receipts.get("latest")).get("receipt_id")).strip(),
        "requirements_total": len(requirements),
        "requirements_ready_total": len(ready_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "requirements": requirements,
        "blocked_requirements": [item.get("id") for item in blocked_requirements],
        "blockers": blockers,
        "source_readbacks": {
            "preflight_status": _safe_str(preflight.get("status")).strip(),
            "denial_status": _safe_str(denial.get("status")).strip(),
            "authority_grant_status": _safe_str(authority_grant.get("status")).strip(),
            "request_readback_status": _safe_str(requests.get("status")).strip(),
            "grant_receipts_status": _safe_str(grant_receipts.get("status")).strip(),
            "approval_lookup_status": approval_lookup_status,
            "approval_status": approval_status,
            "permission_status": _safe_str(permission.get("reason")).strip(),
        },
        "governance": {
            **_persistent_supervision_enablement_authority_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_authority_readiness_audit",
            "read_only_contract": True,
            "audit_only": True,
            "preflight_only": True,
            "authority_request_boundary": True,
            "authority_grant_boundary": True,
            "persistent_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": enablement_authority_granted,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": enablement_authority_granted,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
            "authority_granted": enablement_authority_granted,
            "next_step": (
                "resolve_persistent_supervision_enablement_authority_readiness_blockers_before_grant_boundary"
                if not enablement_authority_granted
                else "review_service_config_write_boundary_before_persistent_supervision_enablement"
            ),
        },
    }


def lens_host_persistent_supervision_enablement_execution_readiness_audit(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    denial = deny_lens_host_persistent_supervision_enablement_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="audit Lens persistent supervision execution denial boundary",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        method="POST",
    )
    requests = lens_host_persistent_supervision_enablement_execution_request_readback(limit=safe_limit)
    grant_receipts = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_grant = _as_dict(grant_receipts.get("active_latest"))
    enablement_authority_granted = bool(active_grant)
    execution_grant_receipts = lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(
        limit=safe_limit,
        active_only=True,
    )
    active_execution_grant = _as_dict(execution_grant_receipts.get("active_latest"))
    execution_authority_granted = bool(active_execution_grant)
    approval, approval_lookup_status = _persistent_supervision_enablement_execution_approval_by_id(safe_approval_id)
    approval = _as_dict(approval)
    approval_status = _safe_str(approval.get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(
        actor,
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        method="POST",
    )
    boundary_observed = (
        bool(denial.get("boundary_ready"))
        and not bool(denial.get("applied"))
        and not bool(denial.get("executed"))
        and not bool(denial.get("service_config_updated"))
    )
    request_readback_ready = _safe_str(requests.get("kind")).strip() == (
        "lens.host.persistent_supervision_enablement_execution.request_readback"
    )
    blockers = _dedupe_strs([*_str_list(denial.get("blockers"))])
    if not enablement_authority_granted:
        blockers.append("persistent_supervision_enablement_authority_not_granted")
    else:
        blockers = [
            item
            for item in blockers
            if item
            not in {
                "persistent_supervision_enablement_authority_not_granted",
                "receipt_write_authority_not_granted",
            }
        ]
        if not execution_authority_granted:
            blockers.append("receipt_write_authority_not_granted")
    if execution_authority_granted:
        blockers = [
            item
            for item in blockers
            if item
            not in {
                "service_config_write_authority_not_granted",
                "persistent_supervision_execution_authority_not_granted",
                "receipt_write_authority_not_granted",
            }
        ]
    if approval_lookup_status == "missing":
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("persistent_supervision_enablement_execution_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("persistent_supervision_enablement_execution_approval_wrong_action")
    elif not approval_ready:
        blockers.append("persistent_supervision_enablement_execution_approval_not_approved")
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    blockers = _dedupe_strs(blockers)
    approval_blockers = [
        item
        for item in blockers
        if item
        in {
            "approval_id_required",
            "persistent_supervision_enablement_execution_approval_not_found",
            "persistent_supervision_enablement_execution_approval_wrong_action",
            "persistent_supervision_enablement_execution_approval_not_approved",
        }
    ]
    requirements = [
        _readiness_requirement(
            "exact_persistent_supervision_enablement_execution_approval",
            label="Exact approved persistent supervision execution authority request",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
            ready=approval_ready,
            status="ready" if approval_ready else "blocked",
            blockers=approval_blockers,
            authority_required="operator_approval",
            authority_granted=approval_ready,
        ),
        _readiness_requirement(
            "actor_scope",
            label="Actor has persistent supervision execution write-review scope",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
            ready=bool(permission.get("ready")),
            status="ready" if bool(permission.get("ready")) else "blocked",
            blockers=["system_write_scope_not_ready"] if "system_write_scope_not_ready" in blockers else [],
            authority_required=LENS_HOST_ACTIVATION_SCOPE,
            authority_granted=bool(permission.get("ready")),
        ),
        _readiness_requirement(
            "active_persistent_supervision_enablement_authority_grant",
            label="Active persistent supervision enablement authority grant",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
            ready=enablement_authority_granted,
            status="ready" if enablement_authority_granted else "blocked",
            blockers=(
                ["persistent_supervision_enablement_authority_not_granted"]
                if "persistent_supervision_enablement_authority_not_granted" in blockers
                else []
            ),
            authority_required="persistent_supervision_enablement_authority",
            authority_granted=enablement_authority_granted,
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_execution_request_readback",
            label="Persistent supervision execution authority request readback",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
            ready=request_readback_ready,
            status=requests.get("status"),
        ),
        _readiness_requirement(
            "persistent_supervision_enablement_execution_denial_boundary",
            label="Persistent supervision execution denial boundary is observed",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
            ready=boundary_observed,
            status=denial.get("status"),
            blockers=denial.get("blockers"),
            authority_required="service_config_write_authority",
            authority_granted=False,
        ),
        _readiness_requirement(
            "service_config_write_authority",
            label="Service config write authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
            ready=execution_authority_granted,
            status="ready" if execution_authority_granted else "blocked",
            blockers=(["service_config_write_authority_not_granted"] if not execution_authority_granted else []),
            authority_required="service_config_write_authority",
            authority_granted=execution_authority_granted,
        ),
        _readiness_requirement(
            "persistent_supervision_execution_authority",
            label="Persistent supervision execution authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
            ready=execution_authority_granted,
            status="ready" if execution_authority_granted else "blocked",
            blockers=(
                ["persistent_supervision_execution_authority_not_granted"] if not execution_authority_granted else []
            ),
            authority_required="persistent_supervision_execution_authority",
            authority_granted=execution_authority_granted,
        ),
        _readiness_requirement(
            "receipt_write_authority",
            label="Persistent supervision execution receipt write authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
            ready=execution_authority_granted,
            status="ready" if execution_authority_granted else "blocked",
            blockers=(["receipt_write_authority_not_granted"] if not execution_authority_granted else []),
            authority_required="receipt_write_authority",
            authority_granted=execution_authority_granted,
        ),
        _readiness_requirement(
            "resident_claim_authority",
            label="Resident claim authority",
            route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
            ready=False,
            status="blocked",
            blockers=["resident_claim_authority_not_granted"],
            authority_required="resident_claim_authority",
            authority_granted=False,
        ),
    ]
    blocked_requirements = [item for item in requirements if not bool(item.get("ready"))]
    ready_requirements = [item for item in requirements if bool(item.get("ready"))]
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_execution.readiness_audit",
        "status": "blocked",
        "audit_status": "complete",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "ready": False,
        "approval_ready": approval_ready,
        "request_readback_ready": request_readback_ready,
        "boundary_observed": boundary_observed,
        "enablement_authority_granted": enablement_authority_granted,
        "active_enablement_authority_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "execution_authority_granted": execution_authority_granted,
        "active_execution_authority_grant_receipt_id": _safe_str(active_execution_grant.get("receipt_id")).strip(),
        "persistent_supervision_enablement_allowed": False,
        "persistent_supervision_ready": False,
        "service_config_updated": False,
        "resident_claim_allowed": False,
        "authority_granted": execution_authority_granted,
        "service_config_write_authority": execution_authority_granted,
        "persistent_supervision_execution_authority": execution_authority_granted,
        "receipt_write_authority": execution_authority_granted,
        "execution_authority_grant_receipt_count": int(execution_grant_receipts.get("total") or 0),
        "latest_execution_authority_grant_receipt_id": _safe_str(
            _as_dict(execution_grant_receipts.get("latest")).get("receipt_id")
        ).strip(),
        "requirements_total": len(requirements),
        "requirements_ready_total": len(ready_requirements),
        "requirements_blocked_total": len(blocked_requirements),
        "requirements": requirements,
        "blocked_requirements": [item.get("id") for item in blocked_requirements],
        "blockers": blockers,
        "source_readbacks": {
            "execution_denial_status": _safe_str(denial.get("status")).strip(),
            "request_readback_status": _safe_str(requests.get("status")).strip(),
            "enablement_authority_grant_status": _safe_str(grant_receipts.get("status")).strip(),
            "execution_authority_grant_status": _safe_str(execution_grant_receipts.get("status")).strip(),
            "approval_lookup_status": approval_lookup_status,
            "approval_status": approval_status,
            "permission_status": _safe_str(permission.get("reason")).strip(),
        },
        "governance": {
            **_persistent_supervision_enablement_execution_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_execution_readiness_audit",
            "read_only_contract": True,
            "audit_only": True,
            "preflight_only": True,
            "authority_request_boundary": True,
            "persistent_supervision_boundary": True,
            "persistent_supervision_enablement_authority": enablement_authority_granted,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "service_config_write_authority": execution_authority_granted,
            "persistent_supervision_execution_authority": execution_authority_granted,
            "tray_registration_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": execution_authority_granted,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
            "authority_granted": execution_authority_granted,
            "next_step": "review_service_config_write_boundary_before_persistent_supervision_execution",
        },
    }


def _surface_component(
    component_id: str,
    *,
    label: str,
    route: str,
    status: Any,
    ready: Any,
    blockers: Any = None,
    required_before_enable: Any = None,
) -> dict[str, Any]:
    return {
        "id": component_id,
        "label": label,
        "route": route,
        "status": _safe_str(status).strip() or "missing",
        "ready": bool(ready),
        "blockers": _str_list(blockers),
        "required_before_enable": _str_list(required_before_enable),
    }


def _resident_runtime_preflight_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_resident_runtime_grant"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_resident_runtime_grant"
    return "blocked", "implement_resident_runtime_execution_authority_grant_boundary"


def _resident_surface_runtime_blockers_from_manifest(manifest: dict[str, Any]) -> list[str]:
    process_readback = _as_dict(manifest.get("process_readback"))
    process_alive = bool(process_readback.get("process_alive"))
    state_status = _safe_str(process_readback.get("state_status")).strip()
    if process_alive and state_status == "foreground_running":
        return ["resident_surface_runtime_not_supervised", "resident_surface_not_resident"]
    return ["resident_surface_runtime_missing"]


def lens_resident_runtime_activation_preflight(
    *,
    approval_id: Any = "",
    actor: Any = "",
) -> dict[str, Any]:
    safe_approval_id = _safe_str(approval_id).strip()
    host_preflight = lens_host_activation_execution_preflight(approval_id=safe_approval_id, actor=actor)
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    supervision_gate = lens_host_supervision_gate(manifest=manifest)
    summon_gate = lens_summon_enablement_gate(preflight=preflight)
    tray_gate = lens_tray_enablement_gate(preflight=preflight)
    overlay_gate = lens_overlay_enablement_gate(preflight=preflight)
    blockers = _dedupe_strs(
        [
            *_str_list(host_preflight.get("blockers")),
            *_str_list(supervision_gate.get("blockers")),
            *_str_list(summon_gate.get("blockers")),
            *_str_list(tray_gate.get("blockers")),
            *_str_list(overlay_gate.get("blockers")),
            "resident_runtime_authority_grant_not_implemented",
            "resident_runtime_execution_authority_not_granted",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
            "service_install_authority_not_granted",
            "service_control_authority_not_granted",
            "tray_registration_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
            "resident_activation_receipt_write_authority_not_granted",
            "resident_claim_authority_not_granted",
            *_resident_surface_runtime_blockers_from_manifest(manifest),
        ]
    )
    status, next_step = _resident_runtime_preflight_status(blockers)
    approval = _as_dict(host_preflight.get("approval"))
    permission = _as_dict(host_preflight.get("permission"))
    posture = _as_dict(host_preflight.get("operator_posture"))
    return {
        "ok": True,
        "kind": "lens.resident_runtime.activation_preflight",
        "status": status,
        "ready": False,
        "grant_ready": False,
        "authority_grant_ready": False,
        "runtime_ready": False,
        "resident_claim_allowed": False,
        "route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
        "policy_route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "surface_route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "host_activation_preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "approval": {
            "required": True,
            "found": bool(approval.get("found")),
            "status": _safe_str(approval.get("status")).strip(),
            "approved": bool(approval.get("approved")),
            "item": _as_dict(approval.get("item")),
        },
        "permission": permission,
        "operator_posture": posture,
        "source_readbacks": {
            "host_activation_preflight": {
                "route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
                "status": _safe_str(host_preflight.get("status")).strip(),
                "ready": bool(host_preflight.get("ready")),
            },
            "supervision_gate": {
                "route": "/lens/host/supervision",
                "status": _safe_str(supervision_gate.get("status")).strip(),
                "ready": bool(supervision_gate.get("ready")),
            },
            "summon_gate": {
                "route": "/lens/summon",
                "status": _safe_str(summon_gate.get("status")).strip(),
                "ready": bool(summon_gate.get("ready")),
            },
            "tray_gate": {
                "route": "/lens/tray",
                "status": _safe_str(tray_gate.get("status")).strip(),
                "ready": bool(tray_gate.get("ready")),
            },
            "overlay_gate": {
                "route": "/lens/overlay",
                "status": _safe_str(overlay_gate.get("status")).strip(),
                "ready": bool(overlay_gate.get("ready")),
            },
        },
        "requirements": [
            _plan_step(
                "verify_exact_approval",
                label="Verify exact approved Lens activation request",
                status=_step_status(
                    blockers,
                    {
                        "approval_id_required",
                        "activation_approval_not_found",
                        "activation_approval_wrong_action",
                        "activation_approval_not_approved",
                    },
                ),
                source=LENS_HOST_ACTIVATION_READBACK_ROUTE,
            ),
            _plan_step(
                "verify_actor_scope",
                label="Verify actor has system.write for resident runtime grant review",
                status=_step_status(blockers, {"system_write_scope_not_ready"}),
                source=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            ),
            _plan_step(
                "verify_operator_posture",
                label="Verify operator posture allows runtime grant review",
                status=_step_status(blockers, {"operator_posture_not_ready"}),
                source="operator_mode_snapshot",
            ),
            _plan_step(
                "verify_resident_supervision_gate",
                label="Verify resident process supervision and service gates",
                status="ready" if bool(supervision_gate.get("ready")) else "blocked",
                source="/lens/host/supervision",
            ),
            _plan_step(
                "verify_summon_tray_overlay_gates",
                label="Verify summon, tray, and overlay enablement gates",
                status=(
                    "ready"
                    if bool(summon_gate.get("ready"))
                    and bool(tray_gate.get("ready"))
                    and bool(overlay_gate.get("ready"))
                    else "blocked"
                ),
                source="/lens/preflight",
            ),
            _plan_step(
                "define_runtime_execution_policy_contract",
                label="Define explicit resident runtime execution policy contract",
                status="ready",
                source=LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
                authority_required="resident_runtime_execution_policy",
                authority_granted=False,
            ),
        ],
        "blockers": blockers,
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_activation_preflight",
            "read_only_contract": True,
            "preflight_only": True,
            "authority_grant_preflight": True,
            "activation_authority": False,
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
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "window_management_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": next_step,
        },
    }


def lens_resident_runtime_execution_policy_contract(
    *,
    approval_id: Any = "",
    actor: Any = "",
) -> dict[str, Any]:
    safe_approval_id = _safe_str(approval_id).strip()
    runtime_preflight = lens_resident_runtime_activation_preflight(approval_id=safe_approval_id, actor=actor)
    source_readbacks = _as_dict(runtime_preflight.get("source_readbacks"))
    blockers = _dedupe_strs(
        [
            *_str_list(runtime_preflight.get("blockers")),
            "resident_runtime_execution_authority_not_granted",
            "resident_runtime_authority_grant_not_implemented",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
            "service_install_authority_not_granted",
            "service_control_authority_not_granted",
            "tray_registration_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
            "resident_activation_receipt_write_authority_not_granted",
            "resident_claim_authority_not_granted",
        ]
    )
    return {
        "ok": True,
        "kind": "lens.resident_runtime.execution_policy_contract",
        "status": "readback_ready",
        "policy_id": "lens.resident_runtime.execution_policy.v1",
        "policy_contract_ready": True,
        "execution_policy_ready": True,
        "ready": True,
        "grant_ready": False,
        "authority_grant_ready": False,
        "runtime_ready": False,
        "resident_claim_allowed": False,
        "route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
        "preflight_route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
        "authority_grant_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "surface_route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "approval": _as_dict(runtime_preflight.get("approval")),
        "permission": _as_dict(runtime_preflight.get("permission")),
        "operator_posture": _as_dict(runtime_preflight.get("operator_posture")),
        "source_readbacks": {
            "resident_runtime_preflight": {
                "route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
                "status": _safe_str(runtime_preflight.get("status")).strip(),
                "grant_ready": bool(runtime_preflight.get("grant_ready")),
            },
            "host_activation_preflight": _as_dict(source_readbacks.get("host_activation_preflight")),
            "supervision_gate": _as_dict(source_readbacks.get("supervision_gate")),
            "summon_gate": _as_dict(source_readbacks.get("summon_gate")),
            "tray_gate": _as_dict(source_readbacks.get("tray_gate")),
            "overlay_gate": _as_dict(source_readbacks.get("overlay_gate")),
        },
        "policy": {
            "default_effect": "deny",
            "grant_model": "future_explicit_runtime_authority_grant",
            "required_approval_action": LENS_HOST_ACTIVATION_ACTION,
            "required_actor_scope": LENS_HOST_ACTIVATION_SCOPE,
            "required_operator_posture": "writes_not_blocked",
            "required_runtime_mode": "supervised_resident_host_with_tray_hotkey_overlay",
            "required_readbacks": [
                LENS_HOST_ACTIVATION_READBACK_ROUTE,
                LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
                "/lens/host/supervision",
                "/lens/summon",
                "/lens/tray",
                "/lens/overlay",
                LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
                LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
            ],
            "required_denials_before_grant": [
                "local_process_launch_authority_not_granted",
                "process_supervision_authority_not_granted",
                "service_control_authority_not_granted",
                "tray_registration_authority_not_granted",
                "hotkey_registration_authority_not_granted",
                "overlay_control_authority_not_granted",
                "resident_claim_authority_not_granted",
            ],
            "must_not_execute_until_granted": [
                "launch_process",
                "supervise_process",
                "restart_process",
                "install_service",
                "start_service",
                "control_service",
                "register_tray",
                "register_hotkey",
                "open_overlay",
                "capture_screen",
                "write_memory",
                "claim_resident",
            ],
        },
        "requirements": [
            _plan_step(
                "verify_exact_approval",
                label="Verify exact approved Lens activation request",
                status=_step_status(
                    blockers,
                    {
                        "approval_id_required",
                        "activation_approval_not_found",
                        "activation_approval_wrong_action",
                        "activation_approval_not_approved",
                    },
                ),
                source=LENS_HOST_ACTIVATION_READBACK_ROUTE,
            ),
            _plan_step(
                "verify_actor_scope",
                label="Verify actor has system.write for resident runtime grant review",
                status=_step_status(blockers, {"system_write_scope_not_ready"}),
                source=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            ),
            _plan_step(
                "verify_operator_posture",
                label="Verify operator posture allows runtime grant review",
                status=_step_status(blockers, {"operator_posture_not_ready"}),
                source="operator_mode_snapshot",
            ),
            _plan_step(
                "verify_resident_supervision_gate",
                label="Verify process supervision, restart, and service gates remain explicit",
                status="blocked",
                source="/lens/host/supervision",
                authority_required="process_supervision_and_service_control",
                authority_granted=False,
            ),
            _plan_step(
                "verify_summon_tray_overlay_gates",
                label="Verify summon, tray, hotkey, and overlay gates remain explicit",
                status="blocked",
                source="/lens/preflight",
                authority_required="tray_hotkey_overlay_control",
                authority_granted=False,
            ),
            _plan_step(
                "define_future_authority_grant_boundary",
                label="Observe runtime authority grant boundary",
                status="ready",
                source=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
                authority_required="resident_runtime_execution_authority",
                authority_granted=False,
            ),
        ],
        "blockers": blockers,
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_execution_policy_contract",
            "read_only_contract": True,
            "policy_contract": True,
            "preflight_only": True,
            "activation_authority": False,
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
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "window_management_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": "implement_resident_runtime_execution_authority_grant_boundary",
        },
    }


def _host_supervision_authority_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(denial.get("approval_id")).strip()
    actor = _safe_str(denial.get("actor")).strip()
    route = _safe_str(denial.get("route")).strip() or LENS_HOST_SUPERVISION_AUTHORITY_ROUTE
    receipt_id = _host_supervision_authority_denial_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(denial.get("permission"))
    preflight = _as_dict(denial.get("preflight"))
    approval = _as_dict(denial.get("approval"))
    denial_body = _as_dict(denial.get("denial"))
    return _filtered_record(
        {
            "kind": "lens.host.supervision_authority.denial.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(denial.get("status")).strip(),
            "route": route,
            "method": _safe_str(denial.get("method")).strip() or "POST",
            "source_kind": _safe_str(denial.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(denial.get("reason")).strip(),
            "created_ts": ts,
            "blockers": _str_list(denial.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "preflight": {
                "ready": bool(preflight.get("ready")),
                "preflight_ready": bool(preflight.get("preflight_ready")),
                "authority_ready": bool(preflight.get("authority_ready")),
                "supervision_ready": bool(preflight.get("supervision_ready")),
                "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
                "requirements_total": int(preflight.get("requirements_total") or 0),
                "requirements_blocked_total": int(preflight.get("requirements_blocked_total") or 0),
                "blocked_requirements": _str_list(preflight.get("blocked_requirements")),
            },
            "authority_boundary": {
                "applied": bool(denial.get("applied")),
                "executed": bool(denial.get("executed")),
                "authority_granted": bool(denial.get("authority_granted")),
                "boundary_ready": bool(denial.get("boundary_ready")),
                "ready": bool(denial.get("ready")),
                "supervision_ready": bool(denial.get("supervision_ready")),
                "authority_ready": bool(denial.get("authority_ready")),
                "resident_claim_allowed": bool(denial.get("resident_claim_allowed")),
            },
            "denial": denial_body,
            "governance": {
                "gate": "lens_host_supervision_authority_denial_receipt",
                "authority_grant_boundary": True,
                "denial_boundary": True,
                "resident_host_supervision_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": True,
                "receipt_write_authority": False,
                "mutation_authority_granted": False,
                "authority_granted": False,
            },
        }
    )


def _host_supervision_authority_grant_receipt(grant: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(grant.get("approval_id")).strip()
    actor = _safe_str(grant.get("actor")).strip()
    route = _safe_str(grant.get("route")).strip() or LENS_HOST_SUPERVISION_AUTHORITY_ROUTE
    receipt_id = _host_supervision_authority_grant_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(grant.get("permission"))
    preflight = _as_dict(grant.get("preflight"))
    approval = _as_dict(grant.get("approval"))
    grant_body = _as_dict(grant.get("grant"))
    lease_seconds = _safe_host_supervision_authority_lease_seconds(grant_body.get("lease_seconds"))
    expires_ts = ts + lease_seconds
    authorities = _as_dict(grant_body.get("authorities"))
    return _filtered_record(
        {
            "kind": "lens.host.supervision_authority.grant.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(grant.get("status")).strip(),
            "route": route,
            "method": _safe_str(grant.get("method")).strip() or "POST",
            "source_kind": _safe_str(grant.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(grant.get("reason")).strip(),
            "created_ts": ts,
            "expires_ts": expires_ts,
            "lease": {
                "active": True,
                "lease_seconds": lease_seconds,
                "created_ts": ts,
                "expires_ts": expires_ts,
            },
            "blockers": _str_list(grant.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "preflight": {
                "ready": bool(preflight.get("ready")),
                "preflight_ready": bool(preflight.get("preflight_ready")),
                "authority_ready": bool(preflight.get("authority_ready")),
                "supervision_ready": bool(preflight.get("supervision_ready")),
                "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
                "requirements_total": int(preflight.get("requirements_total") or 0),
                "requirements_blocked_total": int(preflight.get("requirements_blocked_total") or 0),
                "blocked_requirements": _str_list(preflight.get("blocked_requirements")),
            },
            "authority_boundary": {
                "applied": True,
                "executed": False,
                "authority_granted": True,
                "boundary_ready": True,
                "ready": True,
                "supervision_ready": False,
                "authority_ready": True,
                "resident_claim_allowed": False,
            },
            "authorities": {
                "process_supervision_authority": bool(authorities.get("process_supervision_authority")),
                "process_restart_authority": bool(authorities.get("process_restart_authority")),
                "service_install_authority": bool(authorities.get("service_install_authority")),
                "service_control_authority": bool(authorities.get("service_control_authority")),
                "receipt_write_authority": bool(authorities.get("receipt_write_authority")),
                "resident_claim_authority": bool(authorities.get("resident_claim_authority")),
            },
            "grant": grant_body,
            "governance": {
                "gate": "lens_host_supervision_authority_grant_receipt",
                "authority_grant_boundary": True,
                "resident_host_supervision_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": True,
                "process_restart_authority": True,
                "service_install_authority": True,
                "service_control_authority": True,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": True,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": True,
                "mutation_authority_granted": False,
                "authority_granted": True,
            },
        }
    )


def _persistent_supervision_enablement_authority_grant_receipt(grant: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(grant.get("approval_id")).strip()
    actor = _safe_str(grant.get("actor")).strip()
    route = _safe_str(grant.get("route")).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE
    receipt_id = _persistent_supervision_enablement_authority_grant_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(grant.get("permission"))
    preflight = _as_dict(grant.get("preflight"))
    approval = _as_dict(grant.get("approval"))
    host_authority = _as_dict(grant.get("host_supervision_authority"))
    grant_body = _as_dict(grant.get("grant"))
    lease_seconds = _safe_host_supervision_authority_lease_seconds(grant_body.get("lease_seconds"))
    expires_ts = ts + lease_seconds
    authorities = _as_dict(grant_body.get("authorities"))
    return _filtered_record(
        {
            "kind": "lens.host.persistent_supervision_enablement_authority.grant.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(grant.get("status")).strip(),
            "route": route,
            "method": _safe_str(grant.get("method")).strip() or "POST",
            "source_kind": _safe_str(grant.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(grant.get("reason")).strip(),
            "created_ts": ts,
            "expires_ts": expires_ts,
            "lease": {
                "active": True,
                "lease_seconds": lease_seconds,
                "created_ts": ts,
                "expires_ts": expires_ts,
            },
            "blockers": _str_list(grant.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "host_supervision_authority": {
                "active": bool(host_authority.get("active")),
                "receipt_id": _safe_str(host_authority.get("receipt_id")).strip(),
                "route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
            },
            "preflight": {
                "ready": bool(preflight.get("ready")),
                "preflight_ready": bool(preflight.get("preflight_ready")),
                "enablement_ready": bool(preflight.get("enablement_ready")),
                "authority_grant_active": bool(preflight.get("authority_grant_active")),
                "persistent_supervision_ready": bool(preflight.get("persistent_supervision_ready")),
                "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
                "requirements_total": int(preflight.get("requirements_total") or 0),
                "requirements_blocked_total": int(preflight.get("requirements_blocked_total") or 0),
                "blocked_requirements": _str_list(preflight.get("blocked_requirements")),
            },
            "authority_boundary": {
                "applied": True,
                "executed": False,
                "authority_granted": True,
                "boundary_ready": True,
                "ready": True,
                "enablement_ready": False,
                "persistent_supervision_ready": False,
                "service_config_updated": False,
                "resident_claim_allowed": False,
            },
            "authorities": {
                "persistent_supervision_enablement_authority": bool(
                    authorities.get("persistent_supervision_enablement_authority")
                ),
                "service_config_write_authority": bool(authorities.get("service_config_write_authority")),
                "persistent_supervision_execution_authority": bool(
                    authorities.get("persistent_supervision_execution_authority")
                ),
                "receipt_write_authority": bool(authorities.get("receipt_write_authority")),
                "resident_claim_authority": bool(authorities.get("resident_claim_authority")),
            },
            "grant": grant_body,
            "governance": {
                "gate": "lens_host_persistent_supervision_enablement_authority_grant_receipt",
                "authority_grant_boundary": True,
                "persistent_supervision_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": True,
                "service_config_write_authority": False,
                "persistent_supervision_execution_authority": False,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": True,
                "mutation_authority_granted": False,
                "authority_granted": True,
            },
        }
    )


def _persistent_supervision_enablement_execution_authority_grant_receipt(grant: dict[str, Any]) -> dict[str, Any]:
    ts = _now_s()
    approval_id = _safe_str(grant.get("approval_id")).strip()
    actor = _safe_str(grant.get("actor")).strip()
    route = (
        _safe_str(grant.get("route")).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE
    )
    receipt_id = _persistent_supervision_enablement_execution_authority_grant_receipt_id(
        approval_id=approval_id,
        actor=actor,
        route=route,
        ts=ts,
    )
    permission = _as_dict(grant.get("permission"))
    approval = _as_dict(grant.get("approval"))
    enablement_authority = _as_dict(grant.get("enablement_authority"))
    boundary = _as_dict(grant.get("execution_boundary"))
    grant_body = _as_dict(grant.get("grant"))
    lease_seconds = _safe_host_supervision_authority_lease_seconds(grant_body.get("lease_seconds"))
    expires_ts = ts + lease_seconds
    authorities = _as_dict(grant_body.get("authorities"))
    return _filtered_record(
        {
            "kind": "lens.host.persistent_supervision_enablement_execution_authority.grant.receipt",
            "receipt_id": receipt_id,
            "id": receipt_id,
            "status": _safe_str(grant.get("status")).strip(),
            "route": route,
            "method": _safe_str(grant.get("method")).strip() or "POST",
            "source_kind": _safe_str(grant.get("kind")).strip(),
            "source_route": route,
            "approval_id": approval_id,
            "actor": actor,
            "reason": _safe_str(grant.get("reason")).strip(),
            "created_ts": ts,
            "expires_ts": expires_ts,
            "lease": {
                "active": True,
                "lease_seconds": lease_seconds,
                "created_ts": ts,
                "expires_ts": expires_ts,
            },
            "blockers": _str_list(grant.get("blockers")),
            "approval": {
                "required": bool(approval.get("required")),
                "found": bool(approval.get("found")),
                "status": _safe_str(approval.get("status")).strip(),
                "approved": bool(approval.get("approved")),
            },
            "permission": {
                "ready": bool(permission.get("ready")),
                "allowed": bool(permission.get("allowed")),
                "reason": _safe_str(permission.get("reason")).strip(),
                "required_scope": _safe_str(permission.get("required_scope")).strip(),
            },
            "enablement_authority": {
                "active": bool(enablement_authority.get("active")),
                "receipt_id": _safe_str(enablement_authority.get("receipt_id")).strip(),
                "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
            },
            "execution_boundary": {
                "status": _safe_str(boundary.get("status")).strip(),
                "boundary_ready": bool(boundary.get("boundary_ready")),
                "applied": bool(boundary.get("applied")),
                "executed": bool(boundary.get("executed")),
                "service_config_updated": bool(boundary.get("service_config_updated")),
                "persistent_supervision_enablement_allowed": bool(
                    boundary.get("persistent_supervision_enablement_allowed")
                ),
                "resident_claim_allowed": bool(boundary.get("resident_claim_allowed")),
            },
            "authority_boundary": {
                "applied": True,
                "executed": False,
                "authority_granted": True,
                "boundary_ready": True,
                "ready": True,
                "service_config_write_authority": True,
                "persistent_supervision_execution_authority": True,
                "persistent_supervision_enablement_allowed": False,
                "persistent_supervision_ready": False,
                "service_config_updated": False,
                "resident_claim_allowed": False,
            },
            "authorities": {
                "service_config_write_authority": bool(authorities.get("service_config_write_authority")),
                "persistent_supervision_execution_authority": bool(
                    authorities.get("persistent_supervision_execution_authority")
                ),
                "receipt_write_authority": bool(authorities.get("receipt_write_authority")),
                "resident_claim_authority": bool(authorities.get("resident_claim_authority")),
            },
            "grant": grant_body,
            "governance": {
                "gate": "lens_host_persistent_supervision_enablement_execution_authority_grant_receipt",
                "authority_grant_boundary": True,
                "persistent_supervision_boundary": True,
                "execution_authority": False,
                "approval_decision_authority": False,
                "local_process_launch_authority": False,
                "process_supervision_authority": False,
                "process_restart_authority": False,
                "service_install_authority": False,
                "service_control_authority": False,
                "persistent_supervision_enablement_authority": True,
                "service_config_write_authority": True,
                "persistent_supervision_execution_authority": True,
                "tray_registration_authority": False,
                "hotkey_registration_authority": False,
                "overlay_control_authority": False,
                "summon_authority": False,
                "capture_authority": False,
                "memory_write": False,
                "resident_claim_authority": False,
                "denial_receipt_write_authority": False,
                "receipt_write_authority": True,
                "mutation_authority_granted": False,
                "authority_granted": True,
            },
        }
    )


def _record_host_supervision_authority_denial_receipt(denial: dict[str, Any]) -> dict[str, Any]:
    receipt = _host_supervision_authority_denial_receipt(denial)
    path = _host_supervision_authority_denial_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _record_host_supervision_authority_grant_receipt(grant: dict[str, Any]) -> dict[str, Any]:
    receipt = _host_supervision_authority_grant_receipt(grant)
    path = _host_supervision_authority_grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _record_persistent_supervision_enablement_authority_grant_receipt(grant: dict[str, Any]) -> dict[str, Any]:
    receipt = _persistent_supervision_enablement_authority_grant_receipt(grant)
    path = _persistent_supervision_enablement_authority_grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _record_persistent_supervision_enablement_execution_authority_grant_receipt(
    grant: dict[str, Any],
) -> dict[str, Any]:
    receipt = _persistent_supervision_enablement_execution_authority_grant_receipt(grant)
    path = _persistent_supervision_enablement_execution_authority_grant_receipt_path(receipt.get("receipt_id"))
    if path is None:
        return {}
    receipt["path"] = str(path)
    display = _display(receipt)
    _atomic_write_json(path, display)
    return display


def _read_host_supervision_authority_denial_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _read_host_supervision_authority_grant_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _read_persistent_supervision_enablement_authority_grant_receipt(path: Path) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _read_persistent_supervision_enablement_execution_authority_grant_receipt(
    path: Path,
) -> dict[str, Any] | None:
    raw = _read_json(path)
    return _display(raw) if raw is not None else None


def _list_host_supervision_authority_denial_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
) -> tuple[list[dict[str, Any]], int]:
    root = _host_supervision_authority_denial_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    for path in root.glob("*.json"):
        item = _read_host_supervision_authority_denial_receipt(path)
        if not item:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def _host_supervision_authority_grant_active(item: dict[str, Any], *, now: int | None = None) -> bool:
    lease = _as_dict(item.get("lease"))
    expires_ts = _record_ts(lease.get("expires_ts") or item.get("expires_ts"))
    if expires_ts <= 0:
        return False
    check_ts = _now_s() if now is None else now
    return (
        _safe_str(item.get("kind")).strip() == "lens.host.supervision_authority.grant.receipt"
        and _safe_str(item.get("status")).strip() == "authority_granted"
        and bool(_as_dict(item.get("authority_boundary")).get("authority_granted"))
        and bool(lease.get("active"))
        and expires_ts > check_ts
    )


def _list_host_supervision_authority_grant_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    root = _host_supervision_authority_grant_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    now = _now_s()
    for path in root.glob("*.json"):
        item = _read_host_supervision_authority_grant_receipt(path)
        if not item:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        if active_only and not _host_supervision_authority_grant_active(item, now=now):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def _persistent_supervision_enablement_authority_grant_active(item: dict[str, Any], *, now: int | None = None) -> bool:
    lease = _as_dict(item.get("lease"))
    expires_ts = _record_ts(lease.get("expires_ts") or item.get("expires_ts"))
    if expires_ts <= 0:
        return False
    check_ts = _now_s() if now is None else now
    authorities = _as_dict(item.get("authorities"))
    return (
        _safe_str(item.get("kind")).strip() == "lens.host.persistent_supervision_enablement_authority.grant.receipt"
        and _safe_str(item.get("status")).strip() == "authority_granted"
        and bool(_as_dict(item.get("authority_boundary")).get("authority_granted"))
        and bool(authorities.get("persistent_supervision_enablement_authority"))
        and bool(lease.get("active"))
        and expires_ts > check_ts
    )


def _list_persistent_supervision_enablement_authority_grant_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    root = _persistent_supervision_enablement_authority_grant_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    now = _now_s()
    for path in root.glob("*.json"):
        item = _read_persistent_supervision_enablement_authority_grant_receipt(path)
        if not item:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        if active_only and not _persistent_supervision_enablement_authority_grant_active(item, now=now):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def _persistent_supervision_enablement_execution_authority_grant_active(
    item: dict[str, Any],
    *,
    now: int | None = None,
) -> bool:
    lease = _as_dict(item.get("lease"))
    expires_ts = _record_ts(lease.get("expires_ts") or item.get("expires_ts"))
    if expires_ts <= 0:
        return False
    check_ts = _now_s() if now is None else now
    authorities = _as_dict(item.get("authorities"))
    return (
        _safe_str(item.get("kind")).strip()
        == "lens.host.persistent_supervision_enablement_execution_authority.grant.receipt"
        and _safe_str(item.get("status")).strip() == "authority_granted"
        and bool(_as_dict(item.get("authority_boundary")).get("authority_granted"))
        and bool(authorities.get("service_config_write_authority"))
        and bool(authorities.get("persistent_supervision_execution_authority"))
        and bool(lease.get("active"))
        and expires_ts > check_ts
    )


def _list_persistent_supervision_enablement_execution_authority_grant_receipts(
    *,
    limit: int,
    approval_id: str = "",
    status: str = "",
    active_only: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    root = _persistent_supervision_enablement_execution_authority_grant_receipt_root()
    if not root.exists():
        return [], 0
    items: list[dict[str, Any]] = []
    now = _now_s()
    for path in root.glob("*.json"):
        item = _read_persistent_supervision_enablement_execution_authority_grant_receipt(path)
        if not item:
            continue
        if approval_id and _safe_str(item.get("approval_id")).strip() != approval_id:
            continue
        if status and _safe_str(item.get("status")).strip() != status:
            continue
        if active_only and not _persistent_supervision_enablement_execution_authority_grant_active(item, now=now):
            continue
        items.append(item)
    items.sort(
        key=lambda item: (_record_ts(item.get("created_ts")), _safe_str(item.get("receipt_id"))),
        reverse=True,
    )
    return items[:limit], len(items)


def lens_host_supervision_authority_denial_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_host_supervision_authority_denial_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
    )
    latest = items[0] if items else None
    return {
        "ok": True,
        "kind": "lens.host.supervision_authority.denial_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "total": total,
        "latest": latest,
        "items": items,
        "governance": {
            **_activation_governance(
                route=LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_supervision_authority_denial_receipts_readback",
            "read_only_contract": True,
            "authority_grant_boundary": True,
            "resident_host_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": "review_host_supervision_authority_denial_receipts_before_granting_supervision",
        },
    }


def lens_host_supervision_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_host_supervision_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
        active_only=active_only,
    )
    latest = items[0] if items else None
    active_latest = next((item for item in items if _host_supervision_authority_grant_active(item)), None)
    return {
        "ok": True,
        "kind": "lens.host.supervision_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "active_only": active_only,
        "total": total,
        "latest": latest,
        "active_latest": active_latest,
        "authority_granted": bool(active_latest),
        "items": items,
        "governance": {
            **_supervision_authority_governance(
                route=LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_supervision_authority_grant_receipts_readback",
            "read_only_contract": True,
            "authority_grant_boundary": True,
            "resident_host_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": "review_host_supervision_authority_grants_before_enabling_persistent_supervision",
        },
    }


def lens_host_persistent_supervision_enablement_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_persistent_supervision_enablement_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
        active_only=active_only,
    )
    latest = items[0] if items else None
    active_latest = next(
        (item for item in items if _persistent_supervision_enablement_authority_grant_active(item)),
        None,
    )
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "active_only": active_only,
        "total": total,
        "latest": latest,
        "active_latest": active_latest,
        "authority_granted": bool(active_latest),
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "items": items,
        "governance": {
            **_persistent_supervision_enablement_authority_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_authority_grant_receipts_readback",
            "read_only_contract": True,
            "authority_grant_boundary": True,
            "persistent_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": bool(active_latest),
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": "review_persistent_supervision_enablement_authority_grants_before_config_write_boundary",
        },
    }


def lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(
    *,
    limit: int = 5,
    approval_id: Any = "",
    status: Any = "",
    active_only: bool = False,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    safe_status = _safe_str(status).strip()
    items, total = _list_persistent_supervision_enablement_execution_authority_grant_receipts(
        limit=safe_limit,
        approval_id=safe_approval_id,
        status=safe_status,
        active_only=active_only,
    )
    latest = items[0] if items else None
    active_latest = next(
        (item for item in items if _persistent_supervision_enablement_execution_authority_grant_active(item)),
        None,
    )
    authority_granted = bool(active_latest)
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_execution_authority.grant_receipts",
        "status": "readback_ready" if items else "empty",
        "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "limit": safe_limit,
        "approval_id": safe_approval_id,
        "filter_status": safe_status,
        "active_only": active_only,
        "total": total,
        "latest": latest,
        "active_latest": active_latest,
        "authority_granted": authority_granted,
        "service_config_write_authority": authority_granted,
        "persistent_supervision_execution_authority": authority_granted,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "items": items,
        "governance": {
            **_persistent_supervision_enablement_execution_governance(
                route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_host_persistent_supervision_enablement_execution_authority_grant_receipts_readback",
            "read_only_contract": True,
            "authority_grant_boundary": True,
            "persistent_supervision_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": authority_granted,
            "service_config_write_authority": authority_granted,
            "persistent_supervision_execution_authority": authority_granted,
            "memory_write": False,
            "resident_claim_authority": False,
            "denial_receipt_write_authority": False,
            "receipt_write_authority": False,
            "mutation_authority_granted": False,
            "next_step": "review_resident_claim_boundary_before_persistent_supervision_execution",
        },
    }


def _resident_runtime_authority_grant_boundary_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_resident_runtime_grant"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_resident_runtime_grant"
    return (
        "denied_no_authority_grant",
        "review_authority_grant_denial_receipts_before_adding_resident_runtime_authority",
    )


def deny_lens_resident_runtime_execution_authority_grant(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens resident runtime execution authority grant",
    route: str = LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE
    permission = _permission_readiness(actor, route=safe_route, method=method)
    runtime_preflight = lens_resident_runtime_activation_preflight(approval_id=approval_id, actor=actor)
    runtime_policy = lens_resident_runtime_execution_policy_contract(approval_id=approval_id, actor=actor)
    blockers = _str_list(runtime_policy.get("blockers"))
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    blockers.extend(
        [
            "resident_runtime_authority_grant_not_implemented",
            "resident_runtime_execution_authority_not_granted",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
            "service_install_authority_not_granted",
            "service_control_authority_not_granted",
            "tray_registration_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
            "resident_activation_receipt_write_authority_not_granted",
            "resident_claim_authority_not_granted",
        ]
    )
    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _resident_runtime_authority_grant_boundary_status(deduped_blockers)
    safe_approval_id = _safe_str(runtime_policy.get("approval_id")).strip()
    grant_denial: dict[str, Any] = {
        "reason": "resident_runtime_authority_grant_not_implemented",
        "message": (
            "Lens resident runtime execution authority is denied until an explicit supervised grant "
            "implementation and receipt path exist."
        ),
        "would_grant_execution_authority": False,
        "would_grant_local_process_launch_authority": False,
        "would_grant_process_supervision_authority": False,
        "would_grant_process_restart_authority": False,
        "would_grant_service_install_authority": False,
        "would_grant_service_control_authority": False,
        "would_grant_tray_registration_authority": False,
        "would_grant_hotkey_registration_authority": False,
        "would_grant_overlay_control_authority": False,
        "would_grant_capture_authority": False,
        "would_grant_receipt_write_authority": False,
        "would_grant_memory_write": False,
        "would_grant_resident_claim": False,
        "denial_receipt_written": False,
    }
    governance: dict[str, Any] = {
        **_activation_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": "lens_resident_runtime_execution_authority_grant_boundary",
        "authority_grant_boundary": True,
        "denial_boundary": True,
        "resident_runtime_boundary": True,
        "activation_authority": False,
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
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "memory_write": False,
        "receipt_write_authority": False,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": False,
        "runtime_mutation_authority_granted": False,
        "authority_granted": False,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "applied": False,
        "executed": False,
        "authority_granted": False,
        "grant_ready": False,
        "authority_grant_ready": False,
        "runtime_ready": False,
        "resident_claim_allowed": False,
        "boundary_ready": True,
        "kind": "lens.resident_runtime.execution_authority_grant.denial",
        "status": status,
        "route": safe_route,
        "method": method,
        "preflight_route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
        "policy_route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "surface_route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_DENIALS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "permission": permission,
        "preflight": runtime_preflight,
        "policy": runtime_policy,
        "blockers": deduped_blockers,
        "grant_denial": grant_denial,
        "governance": governance,
    }
    if record_receipt and bool(permission.get("ready")) and status == "denied_no_authority_grant":
        receipt = _record_resident_runtime_authority_grant_denial_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            grant_denial["denial_receipt_written"] = True
            governance["denial_receipt_write_authority"] = True
    elif record_receipt:
        governance["denial_receipt_write_blocker"] = "resident_runtime_authority_grant_not_ready"
    return response


def _host_supervision_authority_boundary_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_host_supervision_authority_request"
    if (
        "supervision_authority_approval_not_found" in blockers
        or "supervision_authority_approval_wrong_action" in blockers
    ):
        return "blocked", "select_matching_lens_host_supervision_authority_request"
    if "supervision_authority_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_supervision_authority_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_host_supervision_authority_boundary"
    return (
        "authority_granted",
        "review_persistent_supervision_enablement_before_execution",
    )


def grant_lens_host_supervision_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens host supervision authority grant",
    route: str = LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_SUPERVISION_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _supervision_authority_approval_by_id(safe_approval_id)
    approval_status = _safe_str(_as_dict(approval).get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(actor, route=safe_route, method=method)
    preflight = lens_host_supervision_authority_preflight()
    preflight_blockers = _str_list(preflight.get("blockers"))
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("supervision_authority_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("supervision_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("supervision_authority_approval_not_approved")
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    grant_ready = approval_ready and bool(permission.get("ready"))
    if not grant_ready:
        blockers.extend(preflight_blockers)
        blockers.extend(
            [
                "process_supervision_authority_not_granted",
                "process_restart_authority_not_granted",
                "service_install_authority_not_granted",
                "service_control_authority_not_granted",
                "resident_host_supervision_authority_not_granted",
                "receipt_write_authority_not_granted",
                "resident_claim_authority_not_granted",
            ]
        )
    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _host_supervision_authority_boundary_status(deduped_blockers)
    active_authorities = grant_ready and not deduped_blockers
    safe_lease_seconds = _safe_host_supervision_authority_lease_seconds(lease_seconds)
    grant = {
        "reason": "approved_supervision_authority_lease",
        "message": (
            "Approved host supervision authority is leased for future persistent-supervision review; "
            "this does not start, install, supervise, restart, write memory, or claim a resident host."
        ),
        "lease_seconds": safe_lease_seconds,
        "authorities": {
            "process_supervision_authority": active_authorities,
            "process_restart_authority": active_authorities,
            "service_install_authority": active_authorities,
            "service_control_authority": active_authorities,
            "receipt_write_authority": active_authorities,
            "resident_claim_authority": active_authorities,
        },
        "would_grant_process_supervision_authority": active_authorities,
        "would_grant_process_restart_authority": active_authorities,
        "would_grant_service_install_authority": active_authorities,
        "would_grant_service_control_authority": active_authorities,
        "would_grant_receipt_write_authority": active_authorities,
        "would_grant_resident_claim_authority": active_authorities,
        "would_grant_local_process_launch_authority": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_claim_resident": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "grant_receipt_written": False,
    }
    denial = {
        "reason": "host_supervision_authority_not_ready",
        "message": (
            "Lens resident host process supervision authority is denied until an exact approved "
            "host supervision authority request and system.write actor scope are present."
        ),
        "would_grant_process_supervision_authority": False,
        "would_grant_process_restart_authority": False,
        "would_grant_service_install_authority": False,
        "would_grant_service_control_authority": False,
        "would_grant_local_process_launch_authority": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_claim_resident": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "denial_receipt_written": False,
    }
    governance: dict[str, Any] = {
        **_supervision_authority_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": (
            "lens_host_supervision_authority_grant_boundary"
            if active_authorities
            else "lens_host_supervision_authority_denial_boundary"
        ),
        "authority_grant_boundary": True,
        "denial_boundary": not active_authorities,
        "resident_host_supervision_boundary": True,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": active_authorities,
        "process_restart_authority": active_authorities,
        "service_install_authority": active_authorities,
        "service_control_authority": active_authorities,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "memory_write": False,
        "receipt_write_authority": active_authorities,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": active_authorities,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": active_authorities,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.host.supervision_authority.grant" if active_authorities else "lens.host.supervision_authority.denial"
        ),
        "status": status,
        "route": safe_route,
        "method": method,
        "preflight_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "request_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "supervision_route": "/lens/host/supervision",
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": approval,
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": (
            LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE
            if active_authorities
            else LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE
        ),
        "receipt_written": False,
        "receipt": {},
        "applied": False,
        "executed": False,
        "authority_granted": active_authorities,
        "grant_ready": active_authorities,
        "boundary_ready": True,
        "ready": active_authorities,
        "supervision_ready": False,
        "authority_ready": active_authorities,
        "resident_claim_allowed": False,
        "permission": permission,
        "preflight": preflight,
        "blockers": deduped_blockers,
        "grant": grant,
        "denial": denial if not active_authorities else {},
        "governance": governance,
    }
    if record_receipt and active_authorities and status == "authority_granted":
        receipt = _record_host_supervision_authority_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
            grant["grant_receipt_written"] = True
    elif record_receipt:
        governance["grant_receipt_write_blocker"] = "host_supervision_authority_not_ready"
        governance["denial_receipt_write_blocker"] = "host_supervision_authority_not_ready"
    return response


def deny_lens_host_supervision_authority_grant(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens host supervision authority grant",
    route: str = LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    return grant_lens_host_supervision_authority(
        approval_id=approval_id,
        actor=actor,
        reason=reason,
        route=route,
        method=method,
        record_receipt=record_receipt,
        lease_seconds=lease_seconds,
    )


def _persistent_supervision_enablement_authority_boundary_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_persistent_supervision_enablement_authority_request"
    if (
        "persistent_supervision_enablement_authority_approval_not_found" in blockers
        or "persistent_supervision_enablement_authority_approval_wrong_action" in blockers
    ):
        return "blocked", "select_matching_persistent_supervision_enablement_authority_request"
    if "persistent_supervision_enablement_authority_approval_not_approved" in blockers:
        return "blocked", "approve_exact_persistent_supervision_enablement_authority_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_persistent_supervision_enablement_authority_boundary"
    if "host_supervision_authority_grant_not_active" in blockers:
        return "blocked", "grant_host_supervision_authority_before_persistent_supervision_enablement_authority"
    return (
        "authority_granted",
        "review_service_config_write_boundary_before_persistent_supervision_enablement",
    )


def grant_lens_host_persistent_supervision_enablement_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens persistent supervision enablement authority grant",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _persistent_supervision_enablement_authority_approval_by_id(safe_approval_id)
    approval_status = _safe_str(_as_dict(approval).get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(actor, route=safe_route, method=method)
    preflight = lens_host_persistent_supervision_enablement_preflight()
    host_grants = lens_host_supervision_authority_grant_receipts(limit=1, active_only=True)
    active_host_grant = _as_dict(host_grants.get("active_latest"))
    host_authority_active = bool(active_host_grant)
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("persistent_supervision_enablement_authority_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("persistent_supervision_enablement_authority_approval_wrong_action")
    elif not approval_ready:
        blockers.append("persistent_supervision_enablement_authority_approval_not_approved")
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    if not host_authority_active:
        blockers.append("host_supervision_authority_grant_not_active")
    grant_ready = approval_ready and bool(permission.get("ready")) and host_authority_active
    if not grant_ready:
        blockers.extend(_str_list(preflight.get("blockers")))
        blockers.extend(
            [
                "persistent_supervision_enablement_authority_not_granted",
                "service_config_write_authority_not_granted",
                "persistent_supervision_execution_authority_not_granted",
                "receipt_write_authority_not_granted",
                "resident_claim_authority_not_granted",
            ]
        )
    deduped_blockers = _dedupe_strs(blockers)
    status, next_step = _persistent_supervision_enablement_authority_boundary_status(deduped_blockers)
    active_authorities = grant_ready and not deduped_blockers
    safe_lease_seconds = _safe_host_supervision_authority_lease_seconds(lease_seconds)
    grant = {
        "reason": "approved_persistent_supervision_enablement_authority_lease",
        "message": (
            "Approved persistent supervision enablement authority is leased for future service-config "
            "review; this does not update config, enable supervision, install, start, supervise, restart, "
            "write memory, or claim a resident host."
        ),
        "lease_seconds": safe_lease_seconds,
        "authorities": {
            "persistent_supervision_enablement_authority": active_authorities,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": active_authorities,
            "resident_claim_authority": False,
        },
        "would_grant_persistent_supervision_enablement_authority": active_authorities,
        "would_grant_service_config_write_authority": False,
        "would_grant_persistent_supervision_execution_authority": False,
        "would_grant_receipt_write_authority": active_authorities,
        "would_grant_resident_claim_authority": False,
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "grant_receipt_written": False,
    }
    denial = {
        "reason": "persistent_supervision_enablement_authority_not_ready",
        "message": (
            "Lens persistent supervision enablement authority is denied until an exact approved request, "
            "system.write actor scope, and active host supervision authority grant are present."
        ),
        "would_grant_persistent_supervision_enablement_authority": False,
        "would_grant_service_config_write_authority": False,
        "would_grant_persistent_supervision_execution_authority": False,
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "denial_receipt_written": False,
    }
    governance: dict[str, Any] = {
        **_persistent_supervision_enablement_authority_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": (
            "lens_host_persistent_supervision_enablement_authority_grant_boundary"
            if active_authorities
            else "lens_host_persistent_supervision_enablement_authority_denial_boundary"
        ),
        "authority_grant_boundary": True,
        "denial_boundary": not active_authorities,
        "persistent_supervision_boundary": True,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": active_authorities,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "tray_registration_authority": False,
        "tray_icon_authority": False,
        "notification_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "window_management_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "memory_write": False,
        "receipt_write_authority": active_authorities,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": False,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": active_authorities,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.host.persistent_supervision_enablement_authority.grant"
            if active_authorities
            else "lens.host.persistent_supervision_enablement_authority.denial"
        ),
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "host_supervision_authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "host_supervision_authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": approval,
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "applied": False,
        "executed": False,
        "authority_granted": active_authorities,
        "grant_ready": active_authorities,
        "boundary_ready": True,
        "ready": active_authorities,
        "enablement_ready": False,
        "persistent_supervision_enablement_allowed": False,
        "persistent_supervision_ready": False,
        "service_config_updated": False,
        "resident_claim_allowed": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "permission": permission,
        "host_supervision_authority": {
            "active": host_authority_active,
            "receipt_id": _safe_str(active_host_grant.get("receipt_id")).strip(),
            "route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        },
        "preflight": preflight,
        "blockers": deduped_blockers,
        "grant": grant,
        "denial": denial if not active_authorities else {},
        "governance": governance,
    }
    if record_receipt and active_authorities and status == "authority_granted":
        receipt = _record_persistent_supervision_enablement_authority_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
            grant["grant_receipt_written"] = True
    elif record_receipt:
        governance["grant_receipt_write_blocker"] = "persistent_supervision_enablement_authority_not_ready"
        governance["denial_receipt_write_blocker"] = "persistent_supervision_enablement_authority_not_ready"
    return response


def _persistent_supervision_enablement_execution_authority_boundary_status(
    blockers: list[str],
) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_persistent_supervision_execution_authority_request"
    if (
        "persistent_supervision_enablement_execution_approval_not_found" in blockers
        or "persistent_supervision_enablement_execution_approval_wrong_action" in blockers
    ):
        return "blocked", "select_matching_persistent_supervision_execution_authority_request"
    if "persistent_supervision_enablement_execution_approval_not_approved" in blockers:
        return "blocked", "approve_exact_persistent_supervision_execution_authority_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_persistent_supervision_execution_authority_boundary"
    if "persistent_supervision_enablement_authority_not_granted" in blockers:
        return "blocked", "grant_persistent_supervision_enablement_authority_before_execution_authority"
    return (
        "authority_granted",
        "review_resident_claim_boundary_before_persistent_supervision_execution",
    )


def grant_lens_host_persistent_supervision_enablement_execution_authority(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens persistent supervision execution authority grant",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
    lease_seconds: Any = _HOST_SUPERVISION_AUTHORITY_DEFAULT_LEASE_SECONDS,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE
    safe_approval_id = _safe_str(approval_id).strip()
    approval, approval_lookup_status = _persistent_supervision_enablement_execution_approval_by_id(safe_approval_id)
    approval_status = _safe_str(_as_dict(approval).get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    permission = _permission_readiness(actor, route=safe_route, method=method)
    enablement_grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_enablement_grant = _as_dict(enablement_grants.get("active_latest"))
    enablement_authority_active = bool(active_enablement_grant)
    execution_boundary = deny_lens_host_persistent_supervision_enablement_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="snapshot Lens persistent supervision execution authority grant boundary",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        method="POST",
    )
    blockers: list[str] = []
    if not safe_approval_id:
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("persistent_supervision_enablement_execution_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("persistent_supervision_enablement_execution_approval_wrong_action")
    elif not approval_ready:
        blockers.append("persistent_supervision_enablement_execution_approval_not_approved")
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    if not enablement_authority_active:
        blockers.append("persistent_supervision_enablement_authority_not_granted")
    grant_ready = approval_ready and bool(permission.get("ready")) and enablement_authority_active
    if not grant_ready:
        blockers.extend(_str_list(execution_boundary.get("blockers")))
        blockers.extend(
            [
                "service_config_write_authority_not_granted",
                "persistent_supervision_execution_authority_not_granted",
                "receipt_write_authority_not_granted",
                "resident_claim_authority_not_granted",
            ]
        )
    deduped_blockers = _dedupe_strs(blockers)
    status, next_step = _persistent_supervision_enablement_execution_authority_boundary_status(deduped_blockers)
    active_authorities = grant_ready and not deduped_blockers
    safe_lease_seconds = _safe_host_supervision_authority_lease_seconds(lease_seconds)
    grant = {
        "reason": "approved_persistent_supervision_execution_authority_lease",
        "message": (
            "Approved persistent supervision execution authority is leased for future service-config "
            "review; this does not update config, enable supervision, install, start, supervise, restart, "
            "write memory, or claim a resident host."
        ),
        "lease_seconds": safe_lease_seconds,
        "authorities": {
            "service_config_write_authority": active_authorities,
            "persistent_supervision_execution_authority": active_authorities,
            "receipt_write_authority": active_authorities,
            "resident_claim_authority": False,
        },
        "would_grant_service_config_write_authority": active_authorities,
        "would_grant_persistent_supervision_execution_authority": active_authorities,
        "would_grant_receipt_write_authority": active_authorities,
        "would_grant_resident_claim_authority": False,
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "grant_receipt_written": False,
    }
    denial = {
        "reason": "persistent_supervision_execution_authority_not_ready",
        "message": (
            "Lens persistent supervision execution authority is denied until an exact approved request, "
            "system.write actor scope, and active persistent supervision enablement authority grant are present."
        ),
        "would_grant_service_config_write_authority": False,
        "would_grant_persistent_supervision_execution_authority": False,
        "would_grant_receipt_write_authority": False,
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "denial_receipt_written": False,
    }
    governance: dict[str, Any] = {
        **_persistent_supervision_enablement_execution_governance(
            route=safe_route,
            approval_request_write=False,
            read_only_contract=False,
        ),
        "gate": (
            "lens_host_persistent_supervision_enablement_execution_authority_grant_boundary"
            if active_authorities
            else "lens_host_persistent_supervision_enablement_execution_authority_denial_boundary"
        ),
        "authority_grant_boundary": True,
        "denial_boundary": not active_authorities,
        "persistent_supervision_boundary": True,
        "activation_authority": False,
        "execution_authority": False,
        "approval_decision_authority": False,
        "local_process_launch_authority": False,
        "process_supervision_authority": False,
        "process_restart_authority": False,
        "service_install_authority": False,
        "service_control_authority": False,
        "persistent_supervision_enablement_authority": enablement_authority_active,
        "service_config_write_authority": active_authorities,
        "persistent_supervision_execution_authority": active_authorities,
        "tray_registration_authority": False,
        "hotkey_registration_authority": False,
        "overlay_control_authority": False,
        "summon_authority": False,
        "capture_authority": False,
        "memory_write": False,
        "receipt_write_authority": active_authorities,
        "denial_receipt_write_authority": False,
        "resident_claim_authority": False,
        "runtime_mutation_authority_granted": False,
        "mutation_authority_granted": False,
        "authority_granted": active_authorities,
        "next_step": next_step,
    }
    response: dict[str, Any] = {
        "ok": True,
        "kind": (
            "lens.host.persistent_supervision_enablement_execution_authority.grant"
            if active_authorities
            else "lens.host.persistent_supervision_enablement_execution_authority.denial"
        ),
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "status": approval_status,
            "approved": approval_ready,
            "item": approval,
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "applied": False,
        "executed": False,
        "authority_granted": active_authorities,
        "grant_ready": active_authorities,
        "boundary_ready": True,
        "ready": active_authorities,
        "persistent_supervision_enablement_allowed": False,
        "persistent_supervision_ready": False,
        "service_config_updated": False,
        "resident_claim_allowed": False,
        "service_config_write_authority": active_authorities,
        "persistent_supervision_execution_authority": active_authorities,
        "receipt_write_authority": active_authorities,
        "permission": permission,
        "enablement_authority": {
            "active": enablement_authority_active,
            "receipt_id": _safe_str(active_enablement_grant.get("receipt_id")).strip(),
            "route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        },
        "execution_boundary": execution_boundary,
        "blockers": deduped_blockers,
        "grant": grant,
        "denial": denial if not active_authorities else {},
        "governance": governance,
    }
    if record_receipt and active_authorities and status == "authority_granted":
        receipt = _record_persistent_supervision_enablement_execution_authority_grant_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["applied"] = True
            grant["grant_receipt_written"] = True
    elif record_receipt:
        governance["grant_receipt_write_blocker"] = "persistent_supervision_execution_authority_not_ready"
        governance["denial_receipt_write_blocker"] = "persistent_supervision_execution_authority_not_ready"
    return response


def _persistent_supervision_enablement_boundary_status(blockers: list[str]) -> tuple[str, str]:
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_persistent_supervision_enablement"
    if "host_supervision_authority_grant_not_active" in blockers:
        return "blocked", "grant_host_supervision_authority_before_persistent_supervision_enablement"
    return (
        "denied_no_service_config_write_authority",
        "review_persistent_supervision_enablement_denial_before_config_write_authority",
    )


def deny_lens_host_persistent_supervision_enablement(
    *,
    actor: Any = "",
    reason: Any = "attempt Lens persistent supervision enablement",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE
    safe_method = _safe_str(method).strip() or "POST"
    permission = _permission_readiness(actor, route=safe_route, method=safe_method)
    preflight = lens_host_persistent_supervision_enablement_preflight()
    preflight_plan = _as_dict(preflight.get("plan"))
    enablement_authority_grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_enablement_authority_grant = _as_dict(enablement_authority_grants.get("active_latest"))
    enablement_authority_granted = bool(active_enablement_authority_grant)
    blockers = _str_list(preflight.get("blockers"))
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    if not enablement_authority_granted:
        blockers.append("persistent_supervision_enablement_authority_not_granted")
    blockers.extend(
        [
            "service_config_write_authority_not_granted",
            "persistent_supervision_execution_authority_not_granted",
        ]
    )
    deduped_blockers = _dedupe_strs(blockers)
    status, next_step = _persistent_supervision_enablement_boundary_status(deduped_blockers)
    denial = {
        "reason": (
            "host_supervision_authority_grant_not_active"
            if "host_supervision_authority_grant_not_active" in deduped_blockers
            else "service_config_write_authority_not_granted"
        ),
        "message": (
            "Persistent Lens host supervision enablement is denied until an explicit service-config "
            "write boundary exists; this route does not enable supervision or mutate resident runtime state."
        ),
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "denial_receipt_written": False,
    }
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement.denial",
        "status": status,
        "route": safe_route,
        "method": safe_method,
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "plan_route": "/lens/host/persistent-supervision",
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "applied": False,
        "executed": False,
        "boundary_ready": True,
        "ready": False,
        "enablement_ready": False,
        "persistent_supervision_ready": False,
        "resident_claim_allowed": False,
        "authority_granted": False,
        "persistent_supervision_enablement_authority_granted": enablement_authority_granted,
        "active_enablement_authority_grant_receipt_id": _safe_str(
            active_enablement_authority_grant.get("receipt_id")
        ).strip(),
        "authority_grant_active": bool(preflight.get("authority_grant_active")),
        "active_grant_receipt_id": _safe_str(preflight.get("active_grant_receipt_id")).strip(),
        "process_supervision_enabled": bool(preflight.get("process_supervision_enabled")),
        "persistent_supervision_enabled": bool(preflight.get("persistent_supervision_enabled")),
        "service_config_updated": False,
        "permission": permission,
        "preflight": preflight,
        "plan": {
            "mode": "persistent_supervision_enablement_denial",
            "service_name": _safe_str(preflight_plan.get("service_name")).strip(),
            "would_update_service_config": False,
            "would_enable_process_supervision": False,
            "would_enable_persistent_supervision": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_write_receipt": False,
            "would_write_memory": False,
            "would_claim_resident": False,
        },
        "blockers": deduped_blockers,
        "denial": denial,
        "governance": {
            "gate": "lens_host_persistent_supervision_enablement_denial_boundary",
            "route": safe_route,
            "required_scope": LENS_HOST_ACTIVATION_SCOPE,
            "denial_boundary": True,
            "persistent_supervision_boundary": True,
            "read_only_contract": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "persistent_supervision_enablement_authority": enablement_authority_granted,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
            "authority_granted": enablement_authority_granted,
            "next_step": next_step,
        },
    }


def _persistent_supervision_enablement_execution_boundary_status(
    blockers: list[str],
) -> tuple[str, str]:
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_persistent_supervision_execution_enablement"
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_persistent_supervision_execution_authority_request"
    if "persistent_supervision_enablement_execution_approval_not_found" in blockers:
        return "blocked", "request_persistent_supervision_execution_authority_before_execution_enablement"
    if "persistent_supervision_enablement_execution_approval_wrong_action" in blockers:
        return "blocked", "select_persistent_supervision_execution_authority_request"
    if "persistent_supervision_enablement_execution_approval_not_approved" in blockers:
        return "blocked", "operator_approve_persistent_supervision_execution_authority_before_enablement"
    if "persistent_supervision_enablement_authority_not_granted" in blockers:
        return "blocked", "grant_persistent_supervision_enablement_authority_before_execution_enablement"
    if (
        "service_config_write_authority_not_granted" in blockers
        or "persistent_supervision_execution_authority_not_granted" in blockers
    ):
        return (
            "denied_no_service_config_write_authority",
            "review_service_config_write_boundary_before_persistent_supervision_execution",
        )
    if "receipt_write_authority_not_granted" in blockers:
        return (
            "denied_no_receipt_write_authority",
            "review_receipt_write_boundary_before_persistent_supervision_execution",
        )
    if "resident_claim_authority_not_granted" in blockers:
        return (
            "denied_no_resident_claim_authority",
            "review_resident_claim_boundary_before_persistent_supervision_execution",
        )
    return (
        "denied_no_execution_authority",
        "review_persistent_supervision_execution_boundary_before_runtime_mutation",
    )


def deny_lens_host_persistent_supervision_enablement_execution(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens persistent supervision execution enablement",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE
    safe_method = _safe_str(method).strip() or "POST"
    safe_approval_id = _safe_str(approval_id).strip()
    permission = _permission_readiness(actor, route=safe_route, method=safe_method)
    enablement_denial = deny_lens_host_persistent_supervision_enablement(
        actor=actor,
        reason="snapshot Lens persistent supervision execution denial boundary",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        method="POST",
    )
    grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    enablement_authority_granted = bool(active_grant)
    execution_grants = lens_host_persistent_supervision_enablement_execution_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_execution_grant = _as_dict(execution_grants.get("active_latest"))
    execution_authority_granted = bool(active_execution_grant)
    approval, approval_lookup_status = _persistent_supervision_enablement_execution_approval_by_id(safe_approval_id)
    approval = _as_dict(approval)
    approval_status = _safe_str(approval.get("status")).strip() if approval else approval_lookup_status
    approval_ready = bool(approval) and approval_status == "approved"
    blockers = _dedupe_strs(
        [
            *_str_list(enablement_denial.get("blockers")),
            "service_config_write_authority_not_granted",
            "persistent_supervision_execution_authority_not_granted",
            "receipt_write_authority_not_granted",
            "resident_claim_authority_not_granted",
        ]
    )
    if enablement_authority_granted:
        blockers = [item for item in blockers if item != "persistent_supervision_enablement_authority_not_granted"]
    else:
        blockers.append("persistent_supervision_enablement_authority_not_granted")
    if execution_authority_granted:
        blockers = [
            item
            for item in blockers
            if item
            not in {
                "service_config_write_authority_not_granted",
                "persistent_supervision_execution_authority_not_granted",
                "receipt_write_authority_not_granted",
            }
        ]
    if approval_lookup_status == "missing":
        blockers.append("approval_id_required")
    elif approval_lookup_status == "not_found":
        blockers.append("persistent_supervision_enablement_execution_approval_not_found")
    elif approval_lookup_status == "wrong_action":
        blockers.append("persistent_supervision_enablement_execution_approval_wrong_action")
    elif not approval_ready:
        blockers.append("persistent_supervision_enablement_execution_approval_not_approved")
    if not bool(permission.get("ready")):
        blockers.append("system_write_scope_not_ready")
    blockers = _dedupe_strs(blockers)
    status, next_step = _persistent_supervision_enablement_execution_boundary_status(blockers)
    denial_reason = (
        "resident_claim_authority_not_granted"
        if execution_authority_granted
        else "service_config_write_authority_not_granted"
    )
    denial = {
        "reason": denial_reason,
        "message": (
            "Persistent Lens host supervision execution is denied until all service-config, execution, "
            "receipt, and resident-claim boundaries exist; this route does not enable supervision or "
            "mutate resident runtime state."
        ),
        "would_update_service_config": False,
        "would_enable_process_supervision": False,
        "would_enable_persistent_supervision": False,
        "would_install_service": False,
        "would_start_service": False,
        "would_supervise_process": False,
        "would_restart_process": False,
        "would_write_receipt": False,
        "would_write_memory": False,
        "would_claim_resident": False,
        "denial_receipt_written": False,
    }
    return {
        "ok": True,
        "kind": "lens.host.persistent_supervision_enablement_execution.denial",
        "status": status,
        "route": safe_route,
        "method": safe_method,
        "request_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
        "requests_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "approval_id": safe_approval_id,
        "approval": {
            "required": True,
            "found": bool(approval),
            "ready": approval_ready,
            "status": approval_status,
            "lookup_status": approval_lookup_status,
            "item": approval,
        },
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "applied": False,
        "executed": False,
        "boundary_ready": True,
        "ready": False,
        "authority_granted": execution_authority_granted,
        "persistent_supervision_enablement_authority_granted": enablement_authority_granted,
        "active_enablement_authority_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "active_execution_authority_grant_receipt_id": _safe_str(active_execution_grant.get("receipt_id")).strip(),
        "persistent_supervision_enablement_allowed": False,
        "persistent_supervision_ready": False,
        "service_config_updated": False,
        "resident_claim_allowed": False,
        "service_config_write_authority": execution_authority_granted,
        "persistent_supervision_execution_authority": execution_authority_granted,
        "receipt_write_authority": execution_authority_granted,
        "permission": permission,
        "enablement_denial": enablement_denial,
        "blockers": blockers,
        "denial": denial,
        "governance": {
            **_persistent_supervision_enablement_execution_governance(
                route=safe_route,
                approval_request_write=False,
            ),
            "gate": "lens_host_persistent_supervision_enablement_execution_denial_boundary",
            "denial_boundary": True,
            "persistent_supervision_boundary": True,
            "persistent_supervision_enablement_authority": enablement_authority_granted,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "process_supervision_authority": False,
            "process_restart_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "service_config_write_authority": execution_authority_granted,
            "persistent_supervision_execution_authority": execution_authority_granted,
            "receipt_write_authority": execution_authority_granted,
            "denial_receipt_write_authority": False,
            "memory_write": False,
            "resident_claim_authority": False,
            "mutation_authority_granted": False,
            "authority_granted": execution_authority_granted,
            "next_step": next_step,
        },
    }


def lens_resident_runtime_activation_plan(
    *,
    approval_id: Any = "",
    actor: Any = "",
) -> dict[str, Any]:
    safe_approval_id = _safe_str(approval_id).strip()
    runtime_preflight = lens_resident_runtime_activation_preflight(approval_id=safe_approval_id, actor=actor)
    runtime_policy = lens_resident_runtime_execution_policy_contract(approval_id=safe_approval_id, actor=actor)
    execution_plan = lens_host_activation_execution_plan(approval_id=safe_approval_id, actor=actor)
    plan_body = _as_dict(execution_plan.get("plan"))
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    supervision_gate = lens_host_supervision_gate(manifest=manifest)
    summon_gate = lens_summon_enablement_gate(preflight=preflight)
    tray_gate = lens_tray_enablement_gate(preflight=preflight)
    overlay_gate = lens_overlay_enablement_gate(preflight=preflight)
    blockers = _dedupe_strs(
        [
            *_str_list(execution_plan.get("blockers")),
            *_str_list(supervision_gate.get("blockers")),
            *_str_list(summon_gate.get("blockers")),
            *_str_list(tray_gate.get("blockers")),
            *_str_list(overlay_gate.get("blockers")),
            *_str_list(runtime_preflight.get("blockers")),
            *_str_list(runtime_policy.get("blockers")),
            "resident_runtime_execution_authority_not_granted",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
            "service_install_authority_not_granted",
            "service_control_authority_not_granted",
            "tray_registration_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
            *_resident_surface_runtime_blockers_from_manifest(manifest),
        ]
    )
    steps = [
        _plan_step(
            "verify_exact_host_activation_plan",
            label="Verify exact host activation plan and approval state",
            status="ready" if bool(execution_plan.get("plan_available")) else "blocked",
            source=LENS_HOST_ACTIVATION_PLAN_ROUTE,
        ),
        _plan_step(
            "verify_supervision_gate",
            label="Verify resident process supervision and service control gates",
            status="ready" if bool(supervision_gate.get("ready")) else "blocked",
            source="/lens/host/supervision",
        ),
        _plan_step(
            "verify_summon_gate",
            label="Verify summon-anywhere hotkey gate",
            status="ready" if bool(summon_gate.get("ready")) else "blocked",
            source="/lens/summon",
        ),
        _plan_step(
            "verify_tray_gate",
            label="Verify tray presence gate",
            status="ready" if bool(tray_gate.get("ready")) else "blocked",
            source="/lens/tray",
        ),
        _plan_step(
            "verify_overlay_gate",
            label="Verify overlay window gate",
            status="ready" if bool(overlay_gate.get("ready")) else "blocked",
            source="/lens/overlay",
        ),
        _plan_step(
            "activate_supervised_resident_host",
            label="Activate supervised resident host",
            status="blocked",
            source="future_resident_runtime_slice",
            authority_required="local_process_launch_and_process_supervision",
            authority_granted=False,
        ),
        _plan_step(
            "register_tray_hotkey_overlay",
            label="Register tray presence, global hotkey, and overlay window",
            status="blocked",
            source="future_resident_runtime_slice",
            authority_required="tray_hotkey_overlay_control",
            authority_granted=False,
        ),
        _plan_step(
            "record_resident_runtime_receipt",
            label="Record resident runtime activation receipt after activation",
            status="blocked",
            source="future_receipt_slice",
            authority_required="receipt_write",
            authority_granted=False,
        ),
    ]
    approval = _as_dict(_as_dict(execution_plan.get("preflight")).get("approval"))
    return {
        "ok": True,
        "kind": "lens.resident_runtime.activation_plan",
        "status": "blocked",
        "plan_available": True,
        "runtime_ready": False,
        "execution_ready": False,
        "resident_claim_allowed": False,
        "resident_surface_ready": False,
        "route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "preflight_route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
        "policy_route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
        "authority_grant_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        "execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        "surface_route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "host_activation_plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "host_activation_preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "host_activation_execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "approval": {
            "required": True,
            "selected_status": _safe_str(approval.get("status")).strip(),
            "selected_approved": bool(approval.get("approved")),
        },
        "source_readbacks": {
            "resident_runtime_preflight": {
                "route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
                "status": _safe_str(runtime_preflight.get("status")).strip(),
                "grant_ready": bool(runtime_preflight.get("grant_ready")),
            },
            "resident_runtime_policy": {
                "route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
                "status": _safe_str(runtime_policy.get("status")).strip(),
                "policy_contract_ready": bool(runtime_policy.get("policy_contract_ready")),
                "grant_ready": bool(runtime_policy.get("grant_ready")),
            },
            "host_activation_plan": {
                "route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
                "status": _safe_str(execution_plan.get("status")).strip(),
                "execution_ready": bool(execution_plan.get("execution_ready")),
            },
            "supervision_gate": {
                "route": "/lens/host/supervision",
                "status": _safe_str(supervision_gate.get("status")).strip(),
                "ready": bool(supervision_gate.get("ready")),
            },
            "summon_gate": {
                "route": "/lens/summon",
                "status": _safe_str(summon_gate.get("status")).strip(),
                "ready": bool(summon_gate.get("ready")),
            },
            "tray_gate": {
                "route": "/lens/tray",
                "status": _safe_str(tray_gate.get("status")).strip(),
                "ready": bool(tray_gate.get("ready")),
            },
            "overlay_gate": {
                "route": "/lens/overlay",
                "status": _safe_str(overlay_gate.get("status")).strip(),
                "ready": bool(overlay_gate.get("ready")),
            },
        },
        "preflight": runtime_preflight,
        "policy": runtime_policy,
        "plan": {
            "mode": "supervised_resident_host_with_tray_hotkey_overlay",
            "launch_kind": "resident_runtime_activation",
            "steps": steps,
            "candidate_command": _as_dict(plan_body.get("candidate_command")),
            "foreground_session": _as_dict(plan_body.get("foreground_session")),
            "process_readback": _as_dict(plan_body.get("process_readback")),
            "service_plan": _as_dict(plan_body.get("service_plan")),
            "would_launch_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_register_tray": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_capture_screen": False,
            "would_write_memory": False,
            "would_write_receipt": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
        },
        "blockers": blockers,
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_runtime_activation_plan",
            "read_only_contract": True,
            "plan_readback_only": True,
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
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "window_management_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "resident_claim_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": "implement_supervised_resident_runtime_authority_in_separate_slice",
        },
    }


def _resident_runtime_denial_status(blockers: list[str]) -> tuple[str, str]:
    if "approval_id_required" in blockers:
        return "blocked", "select_exact_approved_activation_request"
    if "activation_approval_not_found" in blockers or "activation_approval_wrong_action" in blockers:
        return "blocked", "select_matching_lens_host_activation_request"
    if "activation_approval_not_approved" in blockers:
        return "blocked", "approve_exact_lens_host_activation_request"
    if "system_write_scope_not_ready" in blockers:
        return "blocked", "configure_actor_scope_before_lens_resident_runtime_activation"
    if "operator_posture_not_ready" in blockers:
        return "blocked", "switch_operator_posture_before_lens_resident_runtime_activation"
    return "denied_no_resident_runtime_authority", "implement_lens_resident_runtime_authority_in_separate_slice"


def deny_lens_resident_runtime_activation_execution(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens resident runtime activation",
    route: str = LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE
    permission = _permission_readiness(actor, route=safe_route, method=method)
    plan = lens_resident_runtime_activation_plan(approval_id=approval_id, actor=actor)
    blockers = _str_list(plan.get("blockers"))
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    blockers.extend(
        [
            "resident_runtime_execution_authority_not_granted",
            "local_process_launch_authority_not_granted",
            "process_supervision_authority_not_granted",
            "process_restart_authority_not_granted",
            "service_install_authority_not_granted",
            "service_control_authority_not_granted",
            "tray_registration_authority_not_granted",
            "hotkey_registration_authority_not_granted",
            "overlay_control_authority_not_granted",
            "resident_claim_authority_not_granted",
            "resident_activation_receipt_write_authority_not_granted",
        ]
    )
    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _resident_runtime_denial_status(deduped_blockers)
    response: dict[str, Any] = {
        "ok": True,
        "applied": False,
        "executed": False,
        "kind": "lens.resident_runtime.activation.execution_denial",
        "status": status,
        "route": safe_route,
        "method": method,
        "plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
        "receipt_route": LENS_RESIDENT_RUNTIME_DENIALS_ROUTE,
        "surface_route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "host_activation_execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        "approval_id": _safe_str(plan.get("approval_id")).strip(),
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_written": False,
        "receipt": {},
        "permission": permission,
        "plan": plan,
        "blockers": deduped_blockers,
        "denial": {
            "reason": "resident_runtime_execution_authority_not_granted",
            "message": (
                "Lens resident runtime activation is blocked until explicit resident runtime execution authority "
                "exists."
            ),
            "would_launch_process": False,
            "would_supervise_process": False,
            "would_restart_process": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_tray": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "would_capture_screen": False,
            "would_write_memory": False,
            "would_write_receipt": False,
            "would_decide_approval": False,
            "would_claim_resident": False,
            "denial_receipt_written": False,
        },
        "governance": {
            **_activation_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_resident_runtime_activation_execution_denial",
            "execution_boundary": True,
            "denial_boundary": True,
            "resident_runtime_boundary": True,
            "activation_authority": False,
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
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "window_management_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "resident_claim_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": next_step,
        },
    }
    if record_receipt and bool(permission.get("ready")) and status == "denied_no_resident_runtime_authority":
        receipt = _record_resident_runtime_activation_denial_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["denial"]["denial_receipt_written"] = True
            response["governance"]["denial_receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["denial_receipt_write_blocker"] = "resident_runtime_execution_not_ready"

    return response


def lens_resident_surface_activation_boundary(
    *,
    approval_id: Any = "",
    actor: Any = "",
    limit: int = 5,
) -> dict[str, Any]:
    safe_limit = _safe_limit(limit)
    safe_approval_id = _safe_str(approval_id).strip()
    activation_state = lens_host_activation_readback(limit=safe_limit)
    execution_preflight = lens_host_activation_execution_preflight(approval_id=safe_approval_id, actor=actor)
    execution_plan = lens_host_activation_execution_plan(approval_id=safe_approval_id, actor=actor)
    runtime_preflight = lens_resident_runtime_activation_preflight(approval_id=safe_approval_id, actor=actor)
    runtime_policy = lens_resident_runtime_execution_policy_contract(approval_id=safe_approval_id, actor=actor)
    runtime_authority_grant = deny_lens_resident_runtime_execution_authority_grant(
        approval_id=safe_approval_id,
        actor=actor,
        reason="prove resident runtime authority grant boundary",
        route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
        method="POST",
    )
    runtime_plan = lens_resident_runtime_activation_plan(approval_id=safe_approval_id, actor=actor)
    runtime_denial = deny_lens_resident_runtime_activation_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="prove resident runtime activation boundary",
        route=LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
        method="POST",
    )
    execution_denial = deny_lens_host_activation_execution(
        approval_id=safe_approval_id,
        actor=actor,
        reason="prove resident surface activation boundary",
        route=LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
        method="POST",
        record_receipt=False,
    )
    preflight = lens_preflight()
    surfaces = _as_dict(preflight.get("surfaces"))
    host_surface = _as_dict(surfaces.get("host"))
    summon_surface = _as_dict(surfaces.get("summon"))
    tray_surface = _as_dict(surfaces.get("tray"))
    overlay_surface = _as_dict(surfaces.get("overlay"))
    plan_body = _as_dict(execution_plan.get("plan"))
    denial = _as_dict(execution_denial.get("denial"))
    approval = _as_dict(execution_preflight.get("approval"))
    blockers = _dedupe_strs(
        [
            *_str_list(preflight.get("blockers")),
            *_str_list(execution_plan.get("blockers")),
            *_str_list(runtime_preflight.get("blockers")),
            *_str_list(runtime_policy.get("blockers")),
            *_str_list(runtime_authority_grant.get("blockers")),
            *_str_list(runtime_plan.get("blockers")),
            *_str_list(runtime_denial.get("blockers")),
            *_str_list(execution_denial.get("blockers")),
            *_resident_surface_runtime_blockers_from_manifest(lens_host_launch_manifest()),
        ]
    )
    components = [
        _surface_component(
            "host_activation_preflight",
            label="Host activation preflight",
            route=LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            status=execution_preflight.get("status"),
            ready=execution_preflight.get("ready"),
            blockers=execution_preflight.get("blockers"),
        ),
        _surface_component(
            "host_activation_plan",
            label="Host activation execution plan",
            route=LENS_HOST_ACTIVATION_PLAN_ROUTE,
            status=execution_plan.get("status"),
            ready=execution_plan.get("execution_ready"),
            blockers=execution_plan.get("blockers"),
        ),
        _surface_component(
            "resident_runtime_preflight",
            label="Supervised resident runtime grant preflight",
            route=LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
            status=runtime_preflight.get("status"),
            ready=runtime_preflight.get("grant_ready"),
            blockers=runtime_preflight.get("blockers"),
        ),
        _surface_component(
            "resident_runtime_policy",
            label="Supervised resident runtime execution policy",
            route=LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
            status=runtime_policy.get("status"),
            ready=runtime_policy.get("policy_contract_ready"),
            blockers=runtime_policy.get("blockers"),
        ),
        _surface_component(
            "resident_runtime_authority_grant",
            label="Supervised resident runtime authority grant denial",
            route=LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
            status=runtime_authority_grant.get("status"),
            ready=runtime_authority_grant.get("authority_granted"),
            blockers=runtime_authority_grant.get("blockers"),
        ),
        _surface_component(
            "resident_runtime_plan",
            label="Supervised resident runtime activation plan",
            route=LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
            status=runtime_plan.get("status"),
            ready=runtime_plan.get("runtime_ready"),
            blockers=runtime_plan.get("blockers"),
        ),
        _surface_component(
            "resident_runtime_activation_denial",
            label="Supervised resident runtime activation denial",
            route=LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
            status=runtime_denial.get("status"),
            ready=runtime_denial.get("executed"),
            blockers=runtime_denial.get("blockers"),
        ),
        _surface_component(
            "host_activation_denial",
            label="Host activation execution denial",
            route=LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
            status=execution_denial.get("status"),
            ready=execution_denial.get("executed"),
            blockers=execution_denial.get("blockers"),
        ),
        _surface_component(
            "host_preflight",
            label="Resident host preflight",
            route="/lens/preflight",
            status=host_surface.get("status"),
            ready=host_surface.get("ready"),
            blockers=host_surface.get("blockers"),
            required_before_enable=host_surface.get("required_before_enable"),
        ),
        _surface_component(
            "summon_preflight",
            label="Summon hotkey preflight",
            route="/lens/preflight",
            status=summon_surface.get("status"),
            ready=summon_surface.get("ready"),
            blockers=summon_surface.get("blockers"),
            required_before_enable=summon_surface.get("required_before_enable"),
        ),
        _surface_component(
            "tray_preflight",
            label="Tray presence preflight",
            route="/lens/preflight",
            status=tray_surface.get("status"),
            ready=tray_surface.get("ready"),
            blockers=tray_surface.get("blockers"),
            required_before_enable=tray_surface.get("required_before_enable"),
        ),
        _surface_component(
            "overlay_preflight",
            label="Overlay window preflight",
            route="/lens/preflight",
            status=overlay_surface.get("status"),
            ready=overlay_surface.get("ready"),
            blockers=overlay_surface.get("blockers"),
            required_before_enable=overlay_surface.get("required_before_enable"),
        ),
    ]
    return {
        "ok": True,
        "kind": "lens.resident_surface.activation_boundary",
        "status": "blocked",
        "route": LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
        "approval_id": safe_approval_id,
        "actor": _redact_free_text(actor),
        "boundary_ready": True,
        "activation_ready": False,
        "resident_surface_ready": False,
        "ready_for_lens_resident_claim": False,
        "resident_claim_allowed": False,
        "execution_ready": False,
        "executed": False,
        "applied": False,
        "operator_experience_proof": False,
        "approval": {
            "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
            "status": _safe_str(activation_state.get("status")).strip(),
            "selected_status": _safe_str(approval.get("status")).strip(),
            "selected_approved": bool(approval.get("approved")),
            "pending_count": activation_state.get("pending_count", 0),
            "approved_count": activation_state.get("approved_count", 0),
        },
        "execution": {
            "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
            "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
            "runtime_preflight_route": LENS_RESIDENT_RUNTIME_PREFLIGHT_ROUTE,
            "runtime_policy_route": LENS_RESIDENT_RUNTIME_POLICY_ROUTE,
            "runtime_authority_grant_route": LENS_RESIDENT_RUNTIME_AUTHORITY_GRANT_ROUTE,
            "runtime_plan_route": LENS_RESIDENT_RUNTIME_PLAN_ROUTE,
            "runtime_execute_route": LENS_RESIDENT_RUNTIME_EXECUTE_ROUTE,
            "execute_route": LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
            "preflight_status": _safe_str(execution_preflight.get("status")).strip(),
            "plan_status": _safe_str(execution_plan.get("status")).strip(),
            "runtime_preflight_status": _safe_str(runtime_preflight.get("status")).strip(),
            "runtime_policy_status": _safe_str(runtime_policy.get("status")).strip(),
            "runtime_authority_grant_status": _safe_str(runtime_authority_grant.get("status")).strip(),
            "runtime_plan_status": _safe_str(runtime_plan.get("status")).strip(),
            "runtime_denial_status": _safe_str(runtime_denial.get("status")).strip(),
            "denial_status": _safe_str(execution_denial.get("status")).strip(),
            "would_launch_process": bool(plan_body.get("would_launch_process")),
            "would_install_service": bool(plan_body.get("would_install_service")),
            "would_start_service": bool(plan_body.get("would_start_service")),
            "would_supervise_process": bool(_as_dict(runtime_plan.get("plan")).get("would_supervise_process")),
            "would_restart_process": bool(_as_dict(runtime_plan.get("plan")).get("would_restart_process")),
            "would_register_tray": bool(_as_dict(runtime_plan.get("plan")).get("would_register_tray")),
            "would_register_hotkey": bool(plan_body.get("would_register_hotkey")),
            "would_open_overlay": bool(plan_body.get("would_open_overlay")),
            "would_capture_screen": bool(_as_dict(runtime_plan.get("plan")).get("would_capture_screen")),
            "would_write_memory": bool(plan_body.get("would_write_memory")),
            "would_write_receipt": bool(_as_dict(runtime_denial.get("denial")).get("would_write_receipt")),
            "would_decide_approval": bool(plan_body.get("would_decide_approval")),
            "would_claim_resident": bool(_as_dict(runtime_denial.get("denial")).get("would_claim_resident")),
            "runtime_denial_reason": _safe_str(_as_dict(runtime_denial.get("denial")).get("reason")).strip(),
            "denial_reason": _safe_str(denial.get("reason")).strip(),
        },
        "surface": {
            "preflight_route": "/lens/preflight",
            "status": _safe_str(preflight.get("status")).strip(),
            "ready": bool(preflight.get("ready")),
            "host_status": _safe_str(host_surface.get("status")).strip(),
            "summon_status": _safe_str(summon_surface.get("status")).strip(),
            "tray_status": _safe_str(tray_surface.get("status")).strip(),
            "overlay_status": _safe_str(overlay_surface.get("status")).strip(),
        },
        "resident_runtime_preflight": runtime_preflight,
        "resident_runtime_policy": runtime_policy,
        "resident_runtime_authority_grant": runtime_authority_grant,
        "resident_runtime_plan": runtime_plan,
        "resident_runtime_denial": runtime_denial,
        "components": components,
        "blockers": blockers,
        "next_smallest_truthful_gap": "review_authority_grant_denial_receipts_before_adding_resident_runtime_authority",
        "governance": {
            **_activation_governance(
                route=LENS_RESIDENT_SURFACE_ACTIVATION_ROUTE,
                approval_request_write=False,
                read_only_contract=True,
            ),
            "gate": "lens_resident_surface_activation_boundary",
            "boundary_only": True,
            "read_only_contract": True,
            "activation_authority": False,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "service_install_authority": False,
            "service_control_authority": False,
            "tray_registration_authority": False,
            "tray_icon_authority": False,
            "hotkey_registration_authority": False,
            "overlay_control_authority": False,
            "summon_authority": False,
            "capture_authority": False,
            "memory_write": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "runtime_mutation_authority_granted": False,
            "next_step": "implement_supervised_resident_runtime_authority_in_separate_slice",
        },
    }


def deny_lens_host_activation_execution(
    *,
    approval_id: Any = "",
    actor: Any = "",
    reason: Any = "attempt Lens host foreground activation",
    route: str = LENS_HOST_ACTIVATION_EXECUTE_ROUTE,
    method: str = "POST",
    record_receipt: bool = False,
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_ACTIVATION_EXECUTE_ROUTE
    permission = _permission_readiness(actor, route=safe_route, method=method)
    plan = lens_host_activation_execution_plan(approval_id=approval_id, actor=actor)
    preflight = _as_dict(plan.get("preflight"))
    blockers = _str_list(plan.get("blockers"))
    if not bool(permission.get("ready")) and "system_write_scope_not_ready" not in blockers:
        blockers.append("system_write_scope_not_ready")
    if "local_process_launch_authority_not_granted" not in blockers:
        blockers.append("local_process_launch_authority_not_granted")
    deduped_blockers = sorted({blocker for blocker in blockers if blocker})
    status, next_step = _execution_denial_status(deduped_blockers)
    response: dict[str, Any] = {
        "ok": True,
        "applied": False,
        "executed": False,
        "kind": "lens.host.activation.execution_denial",
        "status": status,
        "route": safe_route,
        "method": method,
        "request_route": LENS_HOST_ACTIVATION_ROUTE,
        "readback_route": LENS_HOST_ACTIVATION_READBACK_ROUTE,
        "preflight_route": LENS_HOST_ACTIVATION_PREFLIGHT_ROUTE,
        "plan_route": LENS_HOST_ACTIVATION_PLAN_ROUTE,
        "approval_id": _safe_str(plan.get("approval_id")).strip(),
        "actor": _redact_free_text(actor),
        "reason": _redact_free_text(reason),
        "receipt_route": LENS_HOST_ACTIVATION_DENIALS_ROUTE,
        "receipt_written": False,
        "receipt": {},
        "permission": permission,
        "preflight": preflight,
        "plan": plan,
        "blockers": deduped_blockers,
        "denial": {
            "reason": "local_process_launch_authority_not_granted",
            "message": "Lens host activation execution is blocked until explicit local process launch authority exists.",
            "would_launch_process": False,
            "would_write_receipt": False,
            "would_install_service": False,
            "would_start_service": False,
            "would_register_hotkey": False,
            "would_open_overlay": False,
            "denial_receipt_written": False,
        },
        "governance": {
            **_activation_governance(
                route=safe_route,
                approval_request_write=False,
                read_only_contract=False,
            ),
            "gate": "lens_host_activation_execution_denial",
            "execution_boundary": True,
            "denial_boundary": True,
            "execution_authority": False,
            "approval_decision_authority": False,
            "local_process_launch_authority": False,
            "receipt_write_authority": False,
            "denial_receipt_write_authority": False,
            "next_step": next_step,
        },
    }
    if record_receipt and bool(permission.get("ready")):
        receipt = _record_activation_denial_receipt(response)
        if receipt:
            response["receipt_written"] = True
            response["receipt"] = receipt
            response["denial"]["denial_receipt_written"] = True
            response["governance"]["denial_receipt_write_authority"] = True
    elif record_receipt:
        response["governance"]["denial_receipt_write_blocker"] = "system_write_scope_not_ready"
    return response


def _activation_payload(*, actor: Any, mode: str, route: str) -> dict[str, Any]:
    manifest = lens_host_launch_manifest()
    preflight = lens_preflight()
    service_plan = _as_dict(manifest.get("service_plan"))
    process_readback = _as_dict(manifest.get("process_readback"))
    governance = _activation_governance(route=route)
    return {
        "request_kind": "lens.host.activation.request",
        "mode": mode,
        "actor": _redact_free_text(actor),
        "route": route,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "preflight_route": "/lens/preflight",
        "candidate_command": _as_dict(manifest.get("candidate_command")),
        "foreground_session": _as_dict(manifest.get("foreground_session")),
        "service_plan": {
            "status": _safe_str(service_plan.get("status")),
            "ready": bool(service_plan.get("ready")),
            "planned_command": _safe_str(service_plan.get("planned_command")),
            "blocked_by": _as_list(service_plan.get("blocked_by")),
            "governance": _as_dict(service_plan.get("governance")),
        },
        "process_readback": {
            "status": _safe_str(process_readback.get("status")),
            "pid_present": bool(process_readback.get("pid_present")),
            "process_alive": bool(process_readback.get("process_alive")),
            "supervision_enabled": bool(process_readback.get("supervision_enabled")),
        },
        "preflight": {
            "status": _safe_str(preflight.get("status")),
            "ready": bool(preflight.get("ready")),
            "blockers": _as_list(preflight.get("blockers")),
        },
        "blockers": _as_list(manifest.get("blockers")),
        "governance": governance,
    }


def _supervision_authority_request_payload(*, actor: Any, route: str) -> dict[str, Any]:
    manifest = lens_host_launch_manifest()
    supervision_gate = lens_host_supervision_gate(manifest=manifest)
    preflight = lens_host_supervision_authority_preflight(manifest=manifest)
    governance = _supervision_authority_governance(route=route)
    return {
        "request_kind": "lens.host.supervision_authority.request",
        "actor": _redact_free_text(actor),
        "route": route,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "supervision_route": "/lens/host/supervision",
        "preflight_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "grant_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "readback_route": LENS_HOST_SUPERVISION_AUTHORITY_REQUESTS_ROUTE,
        "denials_route": LENS_HOST_SUPERVISION_AUTHORITY_DENIALS_ROUTE,
        "readiness_route": LENS_HOST_SUPERVISION_AUTHORITY_READINESS_ROUTE,
        "supervision_gate": {
            "status": _safe_str(supervision_gate.get("status")).strip(),
            "ready": bool(supervision_gate.get("ready")),
            "resident_host_process": bool(supervision_gate.get("resident_host_process")),
            "resident_host_supervised": bool(supervision_gate.get("resident_host_supervised")),
            "resident_claim_allowed": bool(supervision_gate.get("resident_claim_allowed")),
            "blockers": _as_list(supervision_gate.get("blockers")),
        },
        "preflight": {
            "status": _safe_str(preflight.get("status")).strip(),
            "ready": bool(preflight.get("ready")),
            "preflight_ready": bool(preflight.get("preflight_ready")),
            "authority_ready": bool(preflight.get("authority_ready")),
            "supervision_ready": bool(preflight.get("supervision_ready")),
            "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
            "blocked_requirements": _as_list(preflight.get("blocked_requirements")),
            "blockers": _as_list(preflight.get("blockers")),
        },
        "blockers": _as_list(preflight.get("blockers")),
        "governance": governance,
    }


def _persistent_supervision_enablement_authority_request_payload(*, actor: Any, route: str) -> dict[str, Any]:
    manifest = lens_host_launch_manifest()
    preflight = lens_host_persistent_supervision_enablement_preflight(manifest=manifest)
    denial = deny_lens_host_persistent_supervision_enablement(
        actor=actor,
        reason="snapshot Lens persistent supervision enablement authority request",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        method="POST",
    )
    governance = _persistent_supervision_enablement_authority_governance(route=route)
    return {
        "request_kind": "lens.host.persistent_supervision_enablement_authority.request",
        "actor": _redact_free_text(actor),
        "route": route,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "plan_route": "/lens/host/persistent-supervision",
        "preflight_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_READINESS_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "authority_route": LENS_HOST_SUPERVISION_AUTHORITY_ROUTE,
        "authority_grants_route": LENS_HOST_SUPERVISION_AUTHORITY_GRANTS_ROUTE,
        "preflight": {
            "status": _safe_str(preflight.get("status")).strip(),
            "ready": bool(preflight.get("ready")),
            "preflight_ready": bool(preflight.get("preflight_ready")),
            "enablement_ready": bool(preflight.get("enablement_ready")),
            "authority_grant_active": bool(preflight.get("authority_grant_active")),
            "active_grant_receipt_id": _safe_str(preflight.get("active_grant_receipt_id")).strip(),
            "persistent_supervision_ready": bool(preflight.get("persistent_supervision_ready")),
            "resident_claim_allowed": bool(preflight.get("resident_claim_allowed")),
            "blocked_requirements": _as_list(preflight.get("blocked_requirements")),
            "blockers": _as_list(preflight.get("blockers")),
        },
        "denial_boundary": {
            "status": _safe_str(denial.get("status")).strip(),
            "boundary_ready": bool(denial.get("boundary_ready")),
            "applied": bool(denial.get("applied")),
            "executed": bool(denial.get("executed")),
            "authority_granted": bool(denial.get("authority_granted")),
            "service_config_updated": bool(denial.get("service_config_updated")),
            "blockers": _as_list(denial.get("blockers")),
        },
        "blockers": _dedupe_strs([*_str_list(preflight.get("blockers")), *_str_list(denial.get("blockers"))]),
        "governance": governance,
    }


def _persistent_supervision_enablement_execution_request_payload(*, actor: Any, route: str) -> dict[str, Any]:
    grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    denial = deny_lens_host_persistent_supervision_enablement(
        actor=actor,
        reason="snapshot Lens persistent supervision execution authority request",
        route=LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        method="POST",
    )
    readiness = lens_host_persistent_supervision_enablement_execution_readiness_audit(actor=actor, limit=5)
    governance = _persistent_supervision_enablement_execution_governance(route=route)
    return {
        "request_kind": "lens.host.persistent_supervision_enablement_execution_authority.request",
        "actor": _redact_free_text(actor),
        "route": route,
        "host_route": "/lens/host",
        "manifest_route": "/lens/host/manifest",
        "enablement_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_ROUTE,
        "enablement_authority_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_ROUTE,
        "enablement_authority_grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_GRANTS_ROUTE,
        "active_enablement_authority_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "readback_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUESTS_ROUTE,
        "readiness_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_READINESS_ROUTE,
        "boundary_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_ROUTE,
        "grant_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_ROUTE,
        "grants_route": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_AUTHORITY_GRANTS_ROUTE,
        "denial_boundary": {
            "status": _safe_str(denial.get("status")).strip(),
            "boundary_ready": bool(denial.get("boundary_ready")),
            "applied": bool(denial.get("applied")),
            "executed": bool(denial.get("executed")),
            "authority_granted": bool(denial.get("authority_granted")),
            "service_config_updated": bool(denial.get("service_config_updated")),
            "persistent_supervision_enablement_authority_granted": bool(
                denial.get("persistent_supervision_enablement_authority_granted")
            ),
            "blockers": _as_list(denial.get("blockers")),
        },
        "readiness": {
            "status": _safe_str(readiness.get("status")).strip(),
            "ready": bool(readiness.get("ready")),
            "approval_ready": bool(readiness.get("approval_ready")),
            "request_readback_ready": bool(readiness.get("request_readback_ready")),
            "boundary_observed": bool(readiness.get("boundary_observed")),
            "enablement_authority_granted": bool(readiness.get("enablement_authority_granted")),
            "service_config_write_authority": bool(readiness.get("service_config_write_authority")),
            "persistent_supervision_execution_authority": bool(
                readiness.get("persistent_supervision_execution_authority")
            ),
            "blocked_requirements": _as_list(readiness.get("blocked_requirements")),
            "blockers": _as_list(readiness.get("blockers")),
        },
        "blockers": _dedupe_strs(
            [
                *_str_list(denial.get("blockers")),
                *_str_list(readiness.get("blockers")),
            ]
        ),
        "governance": governance,
    }


def request_lens_host_activation(
    *,
    actor: Any,
    reason: Any = _DEFAULT_REASON,
    mode: Any = _DEFAULT_MODE,
    route: str = LENS_HOST_ACTIVATION_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_ACTIVATION_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _permission_denied(permission, route=safe_route)

    safe_mode = _activation_mode(mode)
    request_reason = _redact_free_text(reason) or _DEFAULT_REASON
    activation = _activation_payload(actor=actor, mode=safe_mode, route=safe_route)
    approval = create_approval_request(LENS_HOST_ACTIVATION_ACTION, request_reason, activation)
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_HOST_ACTIVATION_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "activation": activation,
        "governance": {
            **_activation_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }


def request_lens_host_supervision_authority(
    *,
    actor: Any,
    reason: Any = "request Lens host supervision authority review",
    route: str = LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _supervision_authority_permission_denied(permission, route=safe_route)

    request_reason = _redact_free_text(reason) or "request Lens host supervision authority review"
    payload = _supervision_authority_request_payload(actor=actor, route=safe_route)
    approval = create_approval_request(LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION, request_reason, payload)
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_HOST_SUPERVISION_AUTHORITY_REQUEST_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "supervision_authority": payload,
        "authority_granted": False,
        "resident_claim_allowed": False,
        "governance": {
            **_supervision_authority_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }


def request_lens_host_persistent_supervision_enablement_authority(
    *,
    actor: Any,
    reason: Any = "request Lens persistent supervision enablement authority review",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _persistent_supervision_enablement_authority_permission_denied(permission, route=safe_route)

    request_reason = _redact_free_text(reason) or "request Lens persistent supervision enablement authority review"
    payload = _persistent_supervision_enablement_authority_request_payload(actor=actor, route=safe_route)
    approval = create_approval_request(
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        request_reason,
        payload,
    )
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_AUTHORITY_REQUEST_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "persistent_supervision_enablement_authority": payload,
        "authority_granted": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "governance": {
            **_persistent_supervision_enablement_authority_governance(route=safe_route),
            "permission": permission.evidence,
        },
    }


def request_lens_host_persistent_supervision_enablement_execution_authority(
    *,
    actor: Any,
    reason: Any = "request Lens persistent supervision execution authority review",
    route: str = LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE,
    method: str = "POST",
) -> dict[str, Any]:
    safe_route = _safe_str(route).strip() or LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ROUTE
    permission = _permission(actor, route=safe_route, method=method)
    if not permission.allowed:
        return _persistent_supervision_enablement_execution_permission_denied(permission, route=safe_route)

    grants = lens_host_persistent_supervision_enablement_authority_grant_receipts(
        limit=1,
        active_only=True,
    )
    active_grant = _as_dict(grants.get("active_latest"))
    payload = _persistent_supervision_enablement_execution_request_payload(actor=actor, route=safe_route)
    if not active_grant:
        return {
            "ok": True,
            "applied": False,
            "executed": False,
            "approval_requested": False,
            "status": "blocked",
            "action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
            "persistent_supervision_enablement_execution_authority": payload,
            "persistent_supervision_enablement_authority_granted": False,
            "authority_granted": False,
            "service_config_write_authority": False,
            "persistent_supervision_execution_authority": False,
            "persistent_supervision_enablement_allowed": False,
            "resident_claim_allowed": False,
            "blockers": _dedupe_strs(
                [
                    *_str_list(payload.get("blockers")),
                    "persistent_supervision_enablement_authority_not_granted",
                ]
            ),
            "governance": {
                **_persistent_supervision_enablement_execution_governance(route=safe_route),
                "approval_request_write": False,
                "persistent_supervision_enablement_authority": False,
                "permission": permission.evidence,
                "next_step": "grant_persistent_supervision_enablement_authority_before_execution_request",
            },
        }

    request_reason = _redact_free_text(reason) or "request Lens persistent supervision execution authority review"
    approval = create_approval_request(
        LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        request_reason,
        payload,
    )
    approval_item = _approval_item(approval)
    return {
        "ok": True,
        "applied": False,
        "executed": False,
        "approval_requested": True,
        "status": "approval_requested",
        "action": LENS_HOST_PERSISTENT_SUPERVISION_ENABLEMENT_EXECUTION_REQUEST_ACTION,
        "approval_id": _safe_str(approval_item.get("id")),
        "approval": approval_item,
        "persistent_supervision_enablement_execution_authority": payload,
        "persistent_supervision_enablement_authority_granted": True,
        "active_enablement_authority_grant_receipt_id": _safe_str(active_grant.get("receipt_id")).strip(),
        "authority_granted": False,
        "service_config_write_authority": False,
        "persistent_supervision_execution_authority": False,
        "persistent_supervision_enablement_allowed": False,
        "resident_claim_allowed": False,
        "governance": {
            **_persistent_supervision_enablement_execution_governance(route=safe_route),
            "persistent_supervision_enablement_authority": True,
            "permission": permission.evidence,
        },
    }
