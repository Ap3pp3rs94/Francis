from __future__ import annotations

import time
from typing import Any

from francis.governance.redaction import redact_governed_value

STAGE7_TELEMETRY_STAGE = "Stage 7 / Telemetry MVP"
STAGE7_STATUS_KIND = "francis.stage7.telemetry.status"

_CONNECTOR_AUTHORITY = {
    "telemetry_collection": False,
    "terminal_capture": False,
    "git_watch": False,
    "ide_diagnostics": False,
    "memory_write": False,
    "execution_authority": False,
    "approval_decision_authority": False,
    "mutation_authority_granted": False,
}

_SOURCE_DEFINITIONS = (
    {
        "id": "terminal",
        "label": "Terminal connector",
        "description": "Command outcomes and shell context, once explicitly scoped.",
        "authority_key": "terminal_capture",
        "blocked_by": ("connector_not_configured", "operator_scope_not_granted"),
        "expected_signals": ("command", "cwd", "exit_code", "duration_ms"),
    },
    {
        "id": "git",
        "label": "Git watcher",
        "description": "Repository state and file-change activity, once explicitly scoped.",
        "authority_key": "git_watch",
        "blocked_by": ("watcher_not_configured", "operator_scope_not_granted"),
        "expected_signals": ("branch", "dirty_state", "changed_paths", "remote_alignment"),
    },
    {
        "id": "ide_diagnostics",
        "label": "IDE diagnostics connector",
        "description": "Editor diagnostics and focused file context, once explicitly scoped.",
        "authority_key": "ide_diagnostics",
        "blocked_by": ("connector_not_configured", "operator_scope_not_granted"),
        "expected_signals": ("file", "diagnostic_code", "severity", "range"),
    },
)


def telemetry_status_snapshot() -> dict[str, Any]:
    """Return the Stage 7 telemetry posture without starting any sensing."""

    sources = [_inactive_source(definition) for definition in _SOURCE_DEFINITIONS]
    active_source_total = sum(1 for source in sources if source["active"])

    return {
        "ok": True,
        "kind": STAGE7_STATUS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "status": "inactive",
        "active": False,
        "claim": "telemetry_posture_contract_only",
        "ts": _now_s(),
        "source_total": len(sources),
        "active_source_total": active_source_total,
        "sources": sources,
        "redaction": {
            "status": "ready",
            "pipeline": "governed_value_redaction",
            "redact_before_storage": True,
            "redact_before_display": True,
            "stores_raw_secret_values": False,
        },
        "retention": {
            "status": "none",
            "stores_raw_events": False,
            "event_count": 0,
            "raw_terminal_retention": "none",
            "raw_ide_retention": "none",
        },
        "sensing": {
            "status": "inactive",
            "visible_indicator": True,
            "hidden_sensing": False,
            "active_source_total": active_source_total,
        },
        "governance": {
            "read_only_contract": True,
            "telemetry_collection": False,
            "requires_operator_scope": True,
            "requires_visible_indicator": True,
            "telemetry_is_untrusted_input": True,
            "grants_execution_authority": False,
            "grants_memory_write_authority": False,
        },
        "next_smallest_truthful_gap": "stage7_terminal_connector_scope_contract",
    }


def redact_telemetry_value(value: Any, *, key: str = "") -> Any:
    return redact_governed_value(value, key=key)


def _inactive_source(definition: dict[str, Any]) -> dict[str, Any]:
    authority = dict(_CONNECTOR_AUTHORITY)
    authority_key = str(definition["authority_key"])
    authority[authority_key] = False

    return {
        "id": definition["id"],
        "label": definition["label"],
        "description": definition["description"],
        "status": "not_connected",
        "active": False,
        "visible_indicator": True,
        "hidden_sensing": False,
        "scope": {
            "status": "not_granted",
            "allowed_paths": [],
            "allowed_processes": [],
            "denied_by_default": True,
        },
        "redaction": {
            "status": "ready",
            "redact_before_storage": True,
            "redact_before_display": True,
            "stores_raw_secret_values": False,
        },
        "retention": {
            "status": "none",
            "stores_raw_events": False,
            "event_count": 0,
        },
        "signals": [],
        "expected_signals": list(definition["expected_signals"]),
        "blocked_by": list(definition["blocked_by"]),
        "authority": authority,
    }


def _now_s() -> int:
    return int(time.time())
