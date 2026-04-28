from __future__ import annotations

from typing import Any

LOCAL_OUTBOX_ADAPTER = "local_outbox"
SUPPORTED_EXTERNAL_ESCALATION_ADAPTERS = frozenset({LOCAL_OUTBOX_ADAPTER})
SUPPORTED_EXTERNAL_DELIVERY_SENDERS: frozenset[str] = frozenset()


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def normalize_external_escalation_adapter(value: Any) -> str:
    return _safe_str(value).strip().lower().replace("-", "_")


def external_escalation_adapter_preflight(
    adapter: Any,
    *,
    channel: Any = "",
    target: Any = "",
) -> dict[str, Any]:
    adapter_key = normalize_external_escalation_adapter(adapter)
    channel_key = _safe_str(channel).strip()
    target_key = _safe_str(target).strip()
    adapter_declared = bool(adapter_key)
    adapter_supported = adapter_key in SUPPORTED_EXTERNAL_ESCALATION_ADAPTERS

    if not adapter_declared:
        return {
            "external_adapter": "",
            "external_adapter_declared": False,
            "external_adapter_known": False,
            "external_adapter_configured": False,
            "external_adapter_status": "not_configured",
            "external_delivery_mode": "none",
            "external_delivery_ready": False,
            "external_delivery_queued": False,
            "external_delivery_started": False,
            "external_delivery_blocker": "external_adapter_required",
            "missing_requirements": ["external_adapter"],
            "next_step": "declare_external_escalation_adapter_or_request_recovery",
        }

    if not adapter_supported:
        return {
            "external_adapter": adapter_key,
            "external_adapter_declared": True,
            "external_adapter_known": False,
            "external_adapter_configured": False,
            "external_adapter_status": "not_configured",
            "external_delivery_mode": "unsupported",
            "external_delivery_ready": False,
            "external_delivery_queued": False,
            "external_delivery_started": False,
            "external_delivery_blocker": "unsupported_external_adapter",
            "missing_requirements": ["supported_external_adapter"],
            "next_step": "configure_external_escalation_adapter_before_delivery",
        }

    missing = []
    if not channel_key:
        missing.append("external_channel")
    if not target_key:
        missing.append("external_target")

    return {
        "external_adapter": adapter_key,
        "external_adapter_declared": True,
        "external_adapter_known": True,
        "external_adapter_configured": True,
        "external_adapter_status": "configured",
        "external_delivery_mode": LOCAL_OUTBOX_ADAPTER,
        "external_delivery_ready": not missing,
        "external_delivery_queued": False,
        "external_delivery_started": False,
        "external_delivery_blocker": "" if not missing else "external_delivery_metadata_required",
        "missing_requirements": missing,
        "next_step": (
            "queue_local_outbox_external_escalation_delivery"
            if not missing
            else "provide_external_channel_and_target_before_delivery_queue"
        ),
    }


def external_delivery_sender_preflight(
    sender_adapter: Any,
    *,
    channel: Any = "",
    target: Any = "",
    processor_completed: Any = False,
) -> dict[str, Any]:
    sender_key = normalize_external_escalation_adapter(sender_adapter)
    channel_key = _safe_str(channel).strip()
    target_key = _safe_str(target).strip()
    processor_ready = bool(processor_completed)

    missing_requirements: list[str] = []
    if not processor_ready:
        missing_requirements.append("local_outbox_processor_completion")
    if not sender_key:
        missing_requirements.append("external_sender_adapter")
    if not channel_key:
        missing_requirements.append("external_sender_channel")
    if not target_key:
        missing_requirements.append("external_sender_target")

    sender_supported = sender_key in SUPPORTED_EXTERNAL_DELIVERY_SENDERS
    if sender_key and not sender_supported:
        missing_requirements.append("supported_external_sender_adapter")

    if not sender_key:
        blocker = "external_sender_adapter_required"
        status = "not_configured"
    elif not sender_supported:
        blocker = "unsupported_external_sender_adapter"
        status = "unsupported"
    elif missing_requirements:
        blocker = "external_sender_metadata_required"
        status = "not_ready"
    else:
        blocker = ""
        status = "ready"

    ready = status == "ready"
    return {
        "external_sender_adapter": sender_key,
        "external_sender_declared": bool(sender_key),
        "external_sender_known": sender_supported,
        "external_sender_configured": ready,
        "external_sender_status": status,
        "external_sender_ready": ready,
        "external_sender_blocker": blocker,
        "missing_requirements": missing_requirements,
        "external_sender_channel": channel_key,
        "external_sender_target": target_key,
        "external_delivery_started": False,
        "external_message_sent": False,
        "external_network_send": False,
        "next_step": (
            "execute_explicit_external_delivery_sender"
            if ready
            else "configure_explicit_external_delivery_sender_before_marking_sent"
        ),
    }
