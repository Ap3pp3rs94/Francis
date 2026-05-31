from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from francis.governance.redaction import redact_governed_value
from francis.kernel.paths import data_dir

STAGE7_TELEMETRY_STAGE = "Stage 7 / Telemetry MVP"
STAGE7_STATUS_KIND = "francis.stage7.telemetry.status"
_STAGE7_FEEDBACK_MEMORY_ASSISTANCE_LIVE_SAMPLE_GAP = (
    "stage7_context_feedback_memory_assistance_operator_feedback_loop_live_sample_run"
)
_STAGE7_LEDGER_CLOSURE_GAP = "stage7_ledger_closure"

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
    sources = [_apply_terminal_source_readback(source) for source in sources]
    sources = [_apply_git_source_readback(source) for source in sources]
    sources = [_apply_ide_diagnostics_source_readback(source) for source in sources]
    active_source_total = sum(1 for source in sources if source["active"])
    event_count = sum(_event_count(source) for source in sources)
    active = active_source_total > 0
    active_claim = "telemetry_posture_contract_only"
    if event_count > 0:
        active_claim = "explicit_telemetry_events_recorded"
    elif active:
        active_claim = "explicit_telemetry_readback_available"

    return {
        "ok": True,
        "kind": STAGE7_STATUS_KIND,
        "stage": STAGE7_TELEMETRY_STAGE,
        "status": "active" if active else "inactive",
        "active": active,
        "claim": active_claim,
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
            "status": _retention_status(active=active, event_count=event_count),
            "stores_raw_events": False,
            "event_count": event_count,
            "raw_terminal_retention": "none",
            "raw_ide_retention": "none",
        },
        "sensing": {
            "status": _sensing_status(active=active, event_count=event_count),
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
        "next_smallest_truthful_gap": _stage7_feedback_memory_assistance_next_gap(),
    }


def redact_telemetry_value(value: Any, *, key: str = "") -> Any:
    return redact_governed_value(value, key=key)


def _stage7_feedback_memory_assistance_next_gap() -> str:
    latest_receipt = _read_latest_stage7_closure_decision_receipt()
    if latest_receipt.get("decision") == "close_stage7" and latest_receipt.get("stage7_closed_by_receipt") is True:
        return _STAGE7_LEDGER_CLOSURE_GAP
    return _STAGE7_FEEDBACK_MEMORY_ASSISTANCE_LIVE_SAMPLE_GAP


def _read_latest_stage7_closure_decision_receipt() -> dict[str, Any]:
    path = data_dir() / "logs" / "telemetry" / "stage7_operator_stage_closure_decisions.jsonl"
    if not _safe_child_path(path, root=data_dir()) or not path.exists() or not path.is_file():
        return {}
    latest: dict[str, Any] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                latest = item
    except OSError:
        return {}
    return latest


def _safe_child_path(path: Path, *, root: Path) -> bool:
    try:
        resolved_path = path.resolve()
        resolved_root = root.resolve()
    except OSError:
        return False
    return resolved_path == resolved_root or resolved_root in resolved_path.parents


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


def _apply_terminal_source_readback(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("id") != "terminal":
        return source
    from francis.telemetry.terminal import terminal_source_snapshot

    readback = terminal_source_snapshot()
    updated = dict(source)
    updated["status"] = readback["status"]
    updated["active"] = readback["active"]
    updated["blocked_by"] = readback["blocked_by"]
    updated["signals"] = readback["signals"]
    updated["retention"] = readback["retention"]
    updated["scope"] = readback["scope"]
    updated["latest_event"] = readback["latest_event"]
    updated["routes"] = readback["routes"]
    return updated


def _apply_git_source_readback(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("id") != "git":
        return source
    from francis.telemetry.git import git_source_snapshot

    readback = git_source_snapshot()
    updated = dict(source)
    updated["status"] = readback["status"]
    updated["active"] = readback["active"]
    updated["blocked_by"] = readback["blocked_by"]
    updated["signals"] = readback["signals"]
    updated["retention"] = readback["retention"]
    updated["scope"] = readback["scope"]
    updated["latest_snapshot"] = readback["latest_snapshot"]
    updated["routes"] = readback["routes"]
    return updated


def _apply_ide_diagnostics_source_readback(source: dict[str, Any]) -> dict[str, Any]:
    if source.get("id") != "ide_diagnostics":
        return source
    from francis.telemetry.ide_diagnostics import ide_diagnostics_source_snapshot

    readback = ide_diagnostics_source_snapshot()
    updated = dict(source)
    updated["status"] = readback["status"]
    updated["active"] = readback["active"]
    updated["blocked_by"] = readback["blocked_by"]
    updated["signals"] = readback["signals"]
    updated["retention"] = readback["retention"]
    updated["scope"] = readback["scope"]
    updated["latest_diagnostic"] = readback["latest_diagnostic"]
    updated["routes"] = readback["routes"]
    return updated


def _event_count(source: dict[str, Any]) -> int:
    retention = source.get("retention")
    if not isinstance(retention, dict):
        return 0
    value = retention.get("event_count")
    if value is None:
        return 0
    try:
        return max(0, int(value))
    except Exception:
        return 0


def _retention_status(*, active: bool, event_count: int) -> str:
    if event_count > 0:
        return "bounded_redacted_events"
    if active:
        return "read_only_snapshot"
    return "none"


def _sensing_status(*, active: bool, event_count: int) -> str:
    if event_count > 0:
        return "explicit_events_recorded"
    if active:
        return "explicit_readback_available"
    return "inactive"


def _now_s() -> int:
    return int(time.time())
