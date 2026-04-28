from __future__ import annotations

from typing import Any

LOCAL_OUTBOX_ADAPTER = "local_outbox"
SUPPORTED_EXTERNAL_ESCALATION_ADAPTERS = frozenset({LOCAL_OUTBOX_ADAPTER})


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
