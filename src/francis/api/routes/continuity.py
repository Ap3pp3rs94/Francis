from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Query

from francis.api.errors import api_error_message
from francis.chat.continuity.ledger import tail
from francis.chat.continuity.prompt_context import continuity_prompt_context_readback
from francis.lens.host_manifest import lens_overlay_runtime_readback
from francis.unreal_presence_intents import PRESENCE_INTENT_RECEIPT_SCHEMA_VERSION
from francis.unreal_presence_receipts import (
    PRESENCE_DELIVERY_ATTEMPT_SCHEMA_VERSION,
    PRESENCE_DELIVERY_JOURNAL_SCHEMA_VERSION,
    PRESENCE_DELIVERY_RECEIPT_SCHEMA_VERSION,
)
from francis.unreal_presence_runtime import (
    UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_VERSION,
    unreal_presence_runtime_readback,
)
from francis.unreal_presence_selection import (
    UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION,
    unreal_presence_selection_readback,
)
from francis.unreal_presence_wire import (
    PRESENCE_DELIVERY_ACK_SCHEMA_VERSION,
    PRESENCE_IPC_MESSAGE_SCHEMA_VERSION,
)
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot
from francis.world_state.orb import snapshot as orb_status_snapshot
from francis.world_state.presence import (
    GROUNDED_PRESENCE_SCHEMA_VERSION,
    build_grounded_presence_snapshot,
)
from francis.world_state.presence_intent import GROUNDED_PRESENCE_INTENT_SCHEMA_VERSION
from francis.world_state.presence_transport import GROUNDED_PRESENCE_TRANSPORT_SCHEMA_VERSION
from francis.world_state.snapshot import (
    mission_continuity_snapshot,
    observer_incident_snapshot,
    observer_readiness,
    observer_scan_history,
    observer_summary,
)

router = APIRouter()


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _without_internal_fields(value: dict[str, Any], *fields: str) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in fields}


def _operator_payload(*, continuity: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        if continuity is None:
            return operator_mode_snapshot()
        return operator_mode_snapshot(continuity=continuity)
    except Exception as exc:
        return {"ok": False, "error": api_error_message(exc)}


def _operator_surface(*, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _operator_payload() if payload is None else payload

    if not bool(payload.get("ok")):
        return {
            "available": False,
            "error": str(payload.get("error") or "operator_mode_unavailable"),
        }

    return {
        "available": True,
        "observed_at": float(payload.get("generated_at") or 0.0),
        "control_mode": _as_dict(payload.get("control_mode")),
        "focus": _as_dict(payload.get("focus")),
        "posture": _as_dict(payload.get("posture")),
        "backlog": _as_dict(payload.get("backlog")),
    }


def _orb_surface(*, operator_report: dict[str, Any] | None = None) -> dict[str, Any]:
    if operator_report is not None and not bool(operator_report.get("ok")):
        return {
            "available": False,
            "error": str(operator_report.get("error") or "operator_mode_unavailable"),
        }
    try:
        payload = (
            orb_status_snapshot(operator_report=operator_report)
            if operator_report is not None
            else orb_status_snapshot()
        )
    except Exception as exc:
        return {"available": False, "error": api_error_message(exc)}

    if not bool(payload.get("ok")):
        return {
            "available": False,
            "error": str(payload.get("error") or "orb_status_unavailable"),
        }

    return {
        "available": True,
        "observed_at": float(payload.get("generated_at") or 0.0),
        "state": _as_dict(payload.get("state")),
        "voice": _orb_voice_surface(),
    }


def _orb_voice_surface() -> dict[str, Any]:
    try:
        overlay = lens_overlay_runtime_readback()
    except Exception:
        return {}
    voice = _as_dict(overlay.get("voice"))
    overlay_voice = _as_dict(overlay.get("overlay_voice"))
    readiness = _as_dict(overlay.get("voice_provider_readiness"))
    if not bool(overlay.get("ready")) or not bool(overlay.get("process_alive")):
        return {}
    selected_provider = str(readiness.get("selected_provider") or "").strip()
    output_provider = str(
        overlay_voice.get("voice_provider") or voice.get("voice_provider") or selected_provider or ""
    ).strip()
    provider = output_provider or selected_provider
    selected_voice = str(overlay_voice.get("selected_voice") or voice.get("selected_voice") or "").strip()
    if not provider and not selected_voice:
        return {}
    blockers: list[str] = []
    if selected_provider and output_provider and selected_provider != output_provider:
        blockers.append("orb_voice_output_provider_readiness_mismatch")
    if selected_provider and readiness.get("active_provider_configured") is False:
        blockers.append("orb_voice_selected_provider_unconfigured")
    identity_status = "ready" if provider and not blockers else "not_ready"
    listening = bool(overlay_voice.get("wake_listening")) if "wake_listening" in overlay_voice else None
    activity_status = str(overlay_voice.get("status") or voice.get("status") or "").strip().lower()
    if activity_status == "speaking":
        speaking: bool | None = True
    elif activity_status in {"idle", "listening", "not_listening", "ready", "spoken", "wake_acknowledged"}:
        speaking = False
    else:
        speaking = None
    return {
        "provider": provider,
        "selected_voice": selected_voice,
        "identity_status": identity_status,
        "input_provider": str(voice.get("voice_provider") or "").strip(),
        "output_provider": output_provider,
        "listening": listening,
        "speaking": speaking,
        "blockers": blockers,
        "source": "lens.host_manifest.overlay_runtime_readback",
    }


def _observer_briefing() -> dict[str, Any]:
    try:
        payload = observer_incident_snapshot()
        recent_scans = observer_scan_history(limit=3)
        summary = observer_summary(payload)
    except Exception as exc:
        return {
            "headline": "Observer summary unavailable.",
            "counts": {"active": 0},
            "focus": [],
            "recent_scans": [],
            "error": api_error_message(exc),
        }

    return {
        "headline": summary["headline"],
        "counts": summary["counts"],
        "focus": summary["focus"],
        "probes": summary["probe_statuses"],
        "anomaly": summary["anomaly"],
        "observed_at": float(payload.get("generated_at") or 0.0),
        "recent_scans": recent_scans,
        "readiness": observer_readiness(payload, recent_scans=recent_scans),
    }


@router.get("/ledger")
def ledger(limit: int = 200) -> dict[str, object]:
    try:
        return {"entries": tail(limit=limit)}
    except Exception as exc:
        return {"entries": [], "error": api_error_message(exc)}


@router.get("/prompt-context")
@router.get("/prompt_context")
def prompt_context(
    query: str = "",
    limit: int = Query(80, ge=1, le=120),
    max_lines: int = Query(3, ge=1, le=4),
) -> dict[str, object]:
    try:
        readback = continuity_prompt_context_readback(query=query, limit=limit, max_lines=max_lines)
        return {
            **readback,
            "route": "/continuity/prompt-context",
            "alias_routes": ["/continuity/prompt_context"],
            "subsystem": "continuity_prompt_context",
            "operator_visible": True,
            "chat_prompt_route": "/chat/send",
        }
    except Exception as exc:
        return {
            "ok": False,
            "kind": "francis.chat.continuity.prompt_context_readback",
            "subsystem": "continuity_prompt_context",
            "status": "error",
            "error": api_error_message(exc),
            "chat_context": {
                "target": "telemetry_context.prompt_lines",
                "line_count": 0,
                "max_context_lines": max(1, min(int(max_lines or 3), 4)),
                "lines": [],
                "visible_header_required": True,
                "continuity_context_is_untrusted_input": True,
            },
            "reads_memory": False,
            "writes_memory": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }


@router.get("/briefing")
@router.get("/shift_briefing")
@router.get("/shift-briefing")
def briefing(
    recent_limit: int = 5,
    queue_limit: int = 3,
    deadletter_limit: int = 2,
    activity_log_limit: int = 20,
) -> dict[str, object]:
    try:
        continuity = mission_continuity_snapshot(
            recent_limit=max(1, min(recent_limit, 20)),
            queue_limit=max(1, min(queue_limit, 10)),
            deadletter_limit=max(1, min(deadletter_limit, 10)),
            activity_log_limit=max(1, min(activity_log_limit, 100)),
        )
        generated_at = time.time()
        briefing_payload = {
            **_as_dict(continuity.get("mission_briefing")),
            "observer": _observer_briefing(),
        }
        operator_payload = _operator_payload(continuity=continuity)
        operator = _operator_surface(payload=operator_payload)
        orb = _orb_surface(operator_report=operator_payload)
        unreal_selection = unreal_presence_selection_readback()
        unreal_runtime = unreal_presence_runtime_readback(selection=unreal_selection)
        return {
            "ok": True,
            "subsystem": "continuity_briefing",
            "generated_at": generated_at,
            "briefing": briefing_payload,
            "mission_status_counts": _as_dict(continuity.get("mission_status_counts")),
            "recent_missions": [item for item in _as_list(continuity.get("recent_missions")) if isinstance(item, dict)],
            "operator": _without_internal_fields(operator, "observed_at", "backlog"),
            "orb": _without_internal_fields(orb, "observed_at"),
            "presence": build_grounded_presence_snapshot(
                briefing={**briefing_payload, "generated_at": generated_at},
                operator=operator,
                orb=orb,
                unreal_selection=unreal_selection,
                unreal_runtime=unreal_runtime,
            ),
        }
    except Exception as exc:
        unreal_selection = unreal_presence_selection_readback()
        return {
            "ok": False,
            "subsystem": "continuity_briefing",
            "error": api_error_message(exc),
            "briefing": {},
            "mission_status_counts": {},
            "recent_missions": [],
            "operator": {"available": False},
            "orb": {"available": False},
            "presence": build_grounded_presence_snapshot(
                briefing={},
                operator={"available": False},
                orb={"available": False},
                unreal_selection=unreal_selection,
                unreal_runtime=unreal_presence_runtime_readback(selection=unreal_selection),
            ),
        }


@router.get("/presence")
@router.get("/grounded-presence")
def presence() -> dict[str, object]:
    payload = briefing()
    snapshot = payload.get("presence") if isinstance(payload.get("presence"), dict) else {}
    return {
        "ok": bool(payload.get("ok")),
        "subsystem": "grounded_presence",
        "route": "/continuity/presence",
        "alias_routes": ["/continuity/grounded-presence"],
        "presence": snapshot,
    }


@router.get("/presence/unreal-selection")
@router.get("/grounded-presence/unreal-selection")
def presence_unreal_selection() -> dict[str, object]:
    return unreal_presence_selection_readback()


@router.get("/presence/unreal-runtime")
@router.get("/grounded-presence/unreal-runtime")
def presence_unreal_runtime() -> dict[str, object]:
    selection = unreal_presence_selection_readback()
    return unreal_presence_runtime_readback(selection=selection)


@router.get("/presence/contracts")
@router.get("/grounded-presence/contracts")
def presence_contracts() -> dict[str, object]:
    selection = unreal_presence_selection_readback()
    selection_confirmed = bool(selection.get("valid"))
    runtime = unreal_presence_runtime_readback(selection=selection)
    runtime_observed = bool(runtime.get("observed"))
    return {
        "ok": True,
        "kind": "francis.grounded_presence.contract_status",
        "status": (
            "contracts_implemented_runtime_observed"
            if runtime_observed
            else "contracts_implemented_operator_selection_confirmed_runtime_not_observed"
            if selection_confirmed
            else "contracts_implemented_runtime_not_configured"
        ),
        "routes": {
            "presence": "/continuity/presence",
            "presence_alias": "/continuity/grounded-presence",
            "contracts": "/continuity/presence/contracts",
            "unreal_selection": "/continuity/presence/unreal-selection",
            "unreal_runtime": "/continuity/presence/unreal-runtime",
        },
        "contracts": {
            "snapshot": GROUNDED_PRESENCE_SCHEMA_VERSION,
            "unreal_selection": UNREAL_PRESENCE_SELECTION_SCHEMA_VERSION,
            "unreal_runtime_status": UNREAL_PRESENCE_RUNTIME_STATUS_SCHEMA_VERSION,
            "transport_envelope": GROUNDED_PRESENCE_TRANSPORT_SCHEMA_VERSION,
            "delivery_receipt": PRESENCE_DELIVERY_RECEIPT_SCHEMA_VERSION,
            "delivery_journal": PRESENCE_DELIVERY_JOURNAL_SCHEMA_VERSION,
            "delivery_attempt": PRESENCE_DELIVERY_ATTEMPT_SCHEMA_VERSION,
            "ipc_message": PRESENCE_IPC_MESSAGE_SCHEMA_VERSION,
            "delivery_ack": PRESENCE_DELIVERY_ACK_SCHEMA_VERSION,
            "intent_event": GROUNDED_PRESENCE_INTENT_SCHEMA_VERSION,
            "intent_receipt": PRESENCE_INTENT_RECEIPT_SCHEMA_VERSION,
        },
        "transport": {
            "core_to_unreal": "windows_named_pipe_implemented_not_active",
            "unreal_to_core": "windows_named_pipe_receipt_only_not_active",
            "local_only": True,
            "network_allowed": False,
            "application_authentication_status": "hmac_sha256_environment_loader_implemented_unreal_injection_required",
            "cross_process_writer_lock": "windows_named_mutex",
            "delivery_acknowledgement": "signed_ack_with_durable_consumer_dedup_required",
        },
        "unreal": {
            "engine": "Unreal Engine",
            "engine_version": "5.8",
            "selection_status": selection.get("status"),
            "selection_configured": selection.get("configured"),
            "selection_id": selection.get("selection_id"),
            "project_selection_status": selection.get("project_selection_status"),
            "technology_selection_status": selection.get("technology_selection_status"),
            "runtime_status": runtime.get("status"),
            "runtime_configured": bool(_as_dict(_as_dict(runtime.get("runtime")).get("transport")).get("configured")),
            "runtime_observed": runtime_observed,
        },
        "intent_routing": {
            "receipt_only": True,
            "dispatch_supported": False,
            "mutation_supported": False,
        },
        "recovery": {
            "stale_snapshot_posture": "blocked_until_fresh_core_projection",
            "outbound_replay_posture": "durable_delivery_receipt_sequence_watermark",
            "inbound_replay_posture": "durable_accepted_intent_receipt_sequence_watermark",
            "receipt_failure_posture": "pre_send_attempt_plus_authenticated_ack_journal_recovery",
            "crash_window_posture": "exact_envelope_authenticated_reconciliation_after_restart",
        },
        "authority": {
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
    }
