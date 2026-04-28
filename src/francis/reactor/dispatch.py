from __future__ import annotations

import json
import re
from typing import Any

from francis.forge import analyze_proposal_quality
from francis.governance import approvals
from francis.governance.api_permission_gate import ApiPermissionGate
from francis.governance.redaction import redact_governed_value
from francis.kernel.paths import data_dir
from francis.missions import runtime as mission_runtime
from francis.operations import runtime as operations_runtime
from francis.world_state.operator_mode import snapshot as operator_mode_snapshot

_MISSIONS_WRITE_SCOPE = "missions.write"
_OPERATIONS_RUN_SCOPE = "operations.run"
_SAFE_RECORD_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,191}$")
_CLASSIFICATION_SOURCES = frozenset({"federated_handoff", "observer_anomaly", "schedule_window", "telemetry_event"})
SUPPORTED_ACTIONS = ("classify", "mission_tick", "operation_run", "proposal_review", "resume")
BOUNDARY_ACTIONS = ("dispatch", "execute", "mutate", "plugin_run")


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _redacted_dict(value: dict[str, Any]) -> dict[str, Any]:
    redacted = redact_governed_value(value)
    return redacted if isinstance(redacted, dict) else {}


def _as_str_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        return [text] if text else []
    if isinstance(value, (list, tuple, set)):
        return [text for item in value if (text := _safe_str(item).strip())]
    text = _safe_str(value).strip()
    return [text] if text else []


def _safe_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _scope_permission(actor: str, scope: str) -> tuple[bool, dict[str, Any]]:
    decision = ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[scope],
        route="/reactor/events/dispatch_attempt",
        method="POST",
    )
    return decision.allowed, {"reason": decision.reason, "evidence": decision.evidence}


def _operation_run_permission(actor: str) -> tuple[bool, dict[str, Any]]:
    return _scope_permission(actor, _OPERATIONS_RUN_SCOPE)


def _mission_write_permission(actor: str) -> tuple[bool, dict[str, Any]]:
    return _scope_permission(actor, _MISSIONS_WRITE_SCOPE)


def _posture_block(action_label: str) -> str:
    try:
        operator_state = operator_mode_snapshot()
    except Exception as exc:
        return f"Execution is blocked until operator posture can be verified: {exc}"

    if not bool(operator_state.get("ok")):
        return "Execution is blocked until operator posture can be verified."

    control_mode = _as_dict(operator_state.get("control_mode"))
    posture = _as_dict(operator_state.get("posture"))
    control_mode_id = _safe_str(control_mode.get("id")).strip().lower()
    control_writes = _safe_str(control_mode.get("writes")).strip().lower()
    posture_writes = _safe_str(posture.get("writes")).strip().lower()

    if control_mode_id == "observe" or control_writes == "blocked":
        return f"Observe mode keeps execution read-only. Switch posture before {action_label}."
    if posture_writes == "blocked":
        return f"Current operator posture blocks writes. Adjust the environment before {action_label}."
    return ""


def _operation_identity(result: dict[str, Any]) -> dict[str, Any]:
    operation = _as_dict(result.get("operation"))
    output = _as_dict(operation.get("output"))
    memory_receipt = _as_dict(result.get("memory_receipt")) or _as_dict(operation.get("latest_memory_receipt"))
    return {
        "operation_id": _safe_str(operation.get("id") or operation.get("operation_id")).strip(),
        "operation_status": _safe_str(result.get("status") or operation.get("status")).strip(),
        "trace_id": _safe_str(operation.get("trace_id") or output.get("trace_id")).strip(),
        "run_id": _safe_str(operation.get("run_id") or output.get("run_id")).strip(),
        "memory_receipt_id": _safe_str(memory_receipt.get("receipt_id") or memory_receipt.get("id")).strip(),
        "memory_write": bool(memory_receipt),
    }


def _mission_queue_identity(result: dict[str, Any]) -> dict[str, Any]:
    raw_results = result.get("results")
    results = raw_results if isinstance(raw_results, list) else []
    mission_ids: list[str] = []
    operation_ids: list[str] = []
    trace_ids: list[str] = []
    run_ids: list[str] = []
    memory_receipt_ids: list[str] = []
    memory_write = False
    for item in results[:10]:
        entry = _as_dict(item)
        mission_id = _safe_str(entry.get("mission_id")).strip()
        if mission_id:
            mission_ids.append(mission_id)
        operation_id = _safe_str(entry.get("operation_id")).strip()
        if operation_id:
            operation_ids.append(operation_id)
        trace_id = _safe_str(entry.get("trace_id")).strip()
        if trace_id:
            trace_ids.append(trace_id)
        run_id = _safe_str(entry.get("run_id")).strip()
        if run_id:
            run_ids.append(run_id)
        memory_receipt = _as_dict(entry.get("memory_receipt"))
        memory_receipt_id = _safe_str(memory_receipt.get("receipt_id") or memory_receipt.get("id")).strip()
        if memory_receipt_id:
            memory_receipt_ids.append(memory_receipt_id)
        if memory_receipt:
            memory_write = True
    return {
        "mission_ids": mission_ids,
        "operation_ids": operation_ids,
        "trace_ids": trace_ids,
        "run_ids": run_ids,
        "memory_receipt_ids": memory_receipt_ids,
        "memory_write": memory_write,
    }


def _proposal_id_from_trigger(trigger: dict[str, Any]) -> str:
    metadata = _as_dict(trigger.get("metadata"))
    for value in (
        metadata.get("proposal_id"),
        metadata.get("forge_proposal_id"),
        metadata.get("id"),
        trigger.get("proposal_id"),
        trigger.get("forge_proposal_id"),
    ):
        proposal_id = _safe_str(value).strip()
        if proposal_id:
            return proposal_id
    return ""


def _proposal_artifact(proposal_id: str) -> tuple[dict[str, Any], str]:
    cleaned = _safe_str(proposal_id).strip()
    if not cleaned or not _SAFE_RECORD_ID_RE.match(cleaned):
        return {}, ""
    root = (data_dir() / "artifacts" / "plugins" / "proposals").resolve()
    path = (root / f"{cleaned}.json").resolve(strict=False)
    try:
        path.relative_to(root)
    except ValueError:
        return {}, ""
    if not path.exists() or not path.is_file():
        return {}, str(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}, str(path)
    return (raw if isinstance(raw, dict) else {}), str(path)


def _approval_record_status(approval_id: str) -> str:
    cleaned = _safe_str(approval_id).strip()
    if not cleaned:
        return ""
    candidates = (
        ("pending", approvals.pending_dir()),
        ("approved", approvals.approved_dir()),
        ("rejected", approvals.rejected_dir()),
        ("emergency", approvals.emergency_dir()),
    )
    for status, folder in candidates:
        path = folder / f"{cleaned}.json"
        if not path.exists() or not path.is_file():
            continue
        try:
            json.loads(path.read_text(encoding="utf-8", errors="replace"))
        except Exception:
            return "corrupt"
        return status
    return "missing"


def _approval_id_from_trigger(trigger: dict[str, Any]) -> str:
    metadata = _as_dict(trigger.get("metadata"))
    for value in (trigger.get("approval_id"), metadata.get("approval_id"), metadata.get("id")):
        approval_id = _safe_str(value).strip()
        if approval_id:
            return approval_id
    return ""


def _target_event_id_from_trigger(trigger: dict[str, Any]) -> str:
    metadata = _as_dict(trigger.get("metadata"))
    for value in (
        metadata.get("reactor_event_id"),
        metadata.get("target_event_id"),
        metadata.get("event_id"),
        metadata.get("source_event_id"),
    ):
        target_event_id = _safe_str(value).strip()
        if target_event_id:
            return target_event_id
    return ""


def _plugin_id_from_trigger(trigger: dict[str, Any]) -> str:
    metadata = _as_dict(trigger.get("metadata"))
    for value in (
        metadata.get("plugin_id"),
        metadata.get("capability_id"),
        metadata.get("id"),
        trigger.get("plugin_id"),
        trigger.get("capability_id"),
    ):
        plugin_id = _safe_str(value).strip()
        if plugin_id:
            return plugin_id
    return ""


def _plugin_run_boundary_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    plugin_id = _plugin_id_from_trigger(trigger)
    outcome = "plugin_run_dispatch_not_enabled" if plugin_id else "plugin_id_required"
    next_step = (
        "implement_governed_plugin_run_dispatch_before_execution"
        if plugin_id
        else "link_plugin_id_before_reactor_plugin_run_dispatch"
    )
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": outcome,
            "route": "plugin_run",
            "gate": "reactor_plugin_run_boundary",
            "stable_state": outcome,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "plugin_id": plugin_id,
            "trigger_source": _safe_str(trigger.get("source")).strip().lower(),
            "trigger_type": _safe_str(trigger.get("type")).strip().lower(),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "plugin_execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "readback_only": True,
            "governance": {
                "gate": "reactor_plugin_run_boundary",
                "execution_authority": False,
                "dispatch_authority": False,
                "plugin_run_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "readback_only": True,
            },
        }
    )


def _execute_boundary_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": "execute_dispatch_not_enabled",
            "route": "execute",
            "gate": "reactor_execute_boundary",
            "stable_state": "execute_dispatch_not_enabled",
            "next_step": "implement_governed_execute_dispatch_before_execution",
            "actor": actor,
            "reason": reason,
            "trigger_source": _safe_str(trigger.get("source")).strip().lower(),
            "trigger_type": _safe_str(trigger.get("type")).strip().lower(),
            "trigger_summary": _safe_str(trigger.get("summary")).strip(),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "readback_only": True,
            "governance": {
                "gate": "reactor_execute_boundary",
                "execution_authority": False,
                "dispatch_authority": False,
                "execute_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "readback_only": True,
            },
        }
    )


def _dispatch_boundary_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": "dispatch_action_not_enabled",
            "route": "dispatch",
            "gate": "reactor_dispatch_boundary",
            "stable_state": "dispatch_action_not_enabled",
            "next_step": "implement_governed_dispatch_action_before_execution",
            "actor": actor,
            "reason": reason,
            "trigger_source": _safe_str(trigger.get("source")).strip().lower(),
            "trigger_type": _safe_str(trigger.get("type")).strip().lower(),
            "trigger_summary": _safe_str(trigger.get("summary")).strip(),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "readback_only": True,
            "governance": {
                "gate": "reactor_dispatch_boundary",
                "execution_authority": False,
                "dispatch_authority": False,
                "dispatch_action_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "readback_only": True,
            },
        }
    )


def _mutate_boundary_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": "mutate_dispatch_not_enabled",
            "route": "mutate",
            "gate": "reactor_mutate_boundary",
            "stable_state": "mutate_dispatch_not_enabled",
            "next_step": "implement_governed_mutate_dispatch_before_execution",
            "actor": actor,
            "reason": reason,
            "trigger_source": _safe_str(trigger.get("source")).strip().lower(),
            "trigger_type": _safe_str(trigger.get("type")).strip().lower(),
            "trigger_summary": _safe_str(trigger.get("summary")).strip(),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "readback_only": True,
            "governance": {
                "gate": "reactor_mutate_boundary",
                "execution_authority": False,
                "dispatch_authority": False,
                "mutate_authority": False,
                "approval_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "readback_only": True,
            },
        }
    )


def _classification_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    classification: dict[str, Any],
    bounds: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    source = _safe_str(trigger.get("source")).strip().lower()
    trigger_type = _safe_str(trigger.get("type")).strip().lower() or source
    outcome = f"{source}_classified" if source else "trigger_classified"
    next_step = f"review_classified_{source}_before_followup" if source else "review_classification_before_followup"
    metadata = _as_dict(trigger.get("metadata"))
    metadata_keys = sorted(key for key in (_safe_str(key).strip() for key in metadata) if key)
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "completed",
            "outcome": outcome,
            "route": "classification",
            "gate": "reactor_dispatch_engine",
            "stable_state": "classification_recorded",
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "trigger_source": source,
            "trigger_type": trigger_type,
            "trigger_summary": _safe_str(trigger.get("summary")).strip(),
            "mode": _safe_str(classification.get("mode")).strip(),
            "risk_tier": _safe_str(classification.get("risk_tier")).strip(),
            "approval_required": bool(classification.get("approval_required")),
            "dispatch_allowed": bool(classification.get("dispatch_allowed")),
            "max_actions": _safe_int(bounds.get("max_actions"), default=1, minimum=0, maximum=50),
            "max_runtime_seconds": _safe_int(bounds.get("max_runtime_seconds"), default=60, minimum=1, maximum=86_400),
            "max_retries": _safe_int(bounds.get("max_retries"), default=0, minimum=0, maximum=10),
            "stop_conditions": _as_str_list(bounds.get("stop_conditions")),
            "metadata_keys": metadata_keys,
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "dispatch_applied": True,
            "verified": True,
            "completion_claim_allowed": True,
            "memory_write": False,
            "readback_only": True,
            "governance": {
                "gate": "reactor_dispatch_engine",
                "execution_authority": False,
                "dispatch_authority": True,
                "approval_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "classification_authority": True,
                "readback_only": True,
            },
        }
    )


def _approval_resume_receipt(
    *,
    event_id: str,
    trigger: dict[str, Any],
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    approval_id = _approval_id_from_trigger(trigger)
    approval_status = _approval_record_status(approval_id)
    target_event_id = _target_event_id_from_trigger(trigger)
    operation_id = _safe_str(trigger.get("operation_id") or _as_dict(trigger.get("metadata")).get("operation_id"))
    approval_allows_dispatch = approval_status == "approved"
    outcome = f"approval_resume_{approval_status or 'unknown'}"
    next_step = (
        "record_dispatch_attempt_on_approved_reactor_event"
        if approval_allows_dispatch
        else "review_approval_decision_before_reactor_dispatch"
    )
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "completed",
            "outcome": outcome,
            "route": "approval_resume",
            "gate": "reactor_dispatch_engine",
            "stable_state": "approval_resume_recorded",
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "approval_id": approval_id,
            "approval_status": approval_status,
            "approval_allows_dispatch": approval_allows_dispatch,
            "target_event_id": target_event_id,
            "operation_id": _safe_str(operation_id).strip(),
            "trigger_source": _safe_str(trigger.get("source")).strip().lower(),
            "trigger_type": _safe_str(trigger.get("type")).strip().lower(),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": False,
            "dispatch_applied": True,
            "verified": True,
            "completion_claim_allowed": True,
            "memory_write": False,
            "readback_only": True,
            "approval_decision_applied": False,
            "governance": {
                "gate": "reactor_dispatch_engine",
                "execution_authority": False,
                "dispatch_authority": True,
                "approval_authority": False,
                "approval_decision_authority": False,
                "memory_write": False,
                "authority_source": "reactor.write",
                "resume_authority": True,
                "readback_only": True,
            },
        }
    )


def _blocked_receipt(
    *,
    event_id: str,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
    gate: str,
    outcome: str,
    next_step: str,
    route: str = "operation_run",
    operation_id: str = "",
    permission: dict[str, Any] | None = None,
    message: str = "",
) -> dict[str, Any]:
    return _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "blocked",
            "outcome": outcome,
            "route": route,
            "gate": gate,
            "stable_state": outcome,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "operation_id": operation_id,
            "attempt_count": attempt_count,
            "ts": ts,
            "message": message,
            "permission": permission or {},
            "execution_started": False,
            "dispatch_applied": False,
            "verified": False,
            "completion_claim_allowed": False,
            "memory_write": False,
            "governance": {
                "gate": gate,
                "execution_authority": False,
                "dispatch_authority": False,
                "approval_authority": False,
                "memory_write": False,
            },
        }
    )


def dispatch_event(
    event: dict[str, Any],
    *,
    actor: str,
    reason: str,
    attempt_count: int,
    ts: int,
) -> dict[str, Any]:
    """Run bounded Reactor dispatch engine paths.

    Supported actions are explicitly bounded and permission checked. Unsupported
    action classes deliberately fall back to the existing non-executing
    dispatch-attempt path.
    """

    classification = _as_dict(event.get("classification"))
    action_class = _safe_str(classification.get("action_class")).strip().lower()
    event_id = _safe_str(event.get("event_id") or event.get("id")).strip()
    trigger = _as_dict(event.get("trigger"))
    bounds = _as_dict(event.get("bounds"))

    if action_class == "dispatch":
        receipt = _dispatch_boundary_receipt(
            event_id=event_id,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "dispatch_action_not_enabled",
            "stable_state": "dispatch_action_not_enabled",
            "next_step": "implement_governed_dispatch_action_before_execution",
            "receipt": receipt,
        }

    if action_class == "execute":
        receipt = _execute_boundary_receipt(
            event_id=event_id,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "execute_dispatch_not_enabled",
            "stable_state": "execute_dispatch_not_enabled",
            "next_step": "implement_governed_execute_dispatch_before_execution",
            "receipt": receipt,
        }

    if action_class == "mutate":
        receipt = _mutate_boundary_receipt(
            event_id=event_id,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "mutate_dispatch_not_enabled",
            "stable_state": "mutate_dispatch_not_enabled",
            "next_step": "implement_governed_mutate_dispatch_before_execution",
            "receipt": receipt,
        }

    if action_class == "plugin_run":
        receipt = _plugin_run_boundary_receipt(
            event_id=event_id,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        outcome = _safe_str(receipt.get("outcome")).strip() or "plugin_run_dispatch_not_enabled"
        next_step = _safe_str(receipt.get("next_step")).strip() or "implement_governed_plugin_run_dispatch"
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": outcome,
            "stable_state": outcome,
            "next_step": next_step,
            "receipt": receipt,
        }

    if action_class not in SUPPORTED_ACTIONS:
        return {"handled": False}

    if action_class == "classify":
        source = _safe_str(trigger.get("source")).strip().lower()
        if source not in _CLASSIFICATION_SOURCES:
            return {"handled": False}
        receipt = _classification_receipt(
            event_id=event_id,
            trigger=trigger,
            classification=classification,
            bounds=bounds,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        return {
            "handled": True,
            "applied": True,
            "blocked": False,
            "status": "dispatch_completed",
            "outcome": receipt.get("outcome"),
            "stable_state": "classification_recorded",
            "next_step": receipt.get("next_step"),
            "receipt": receipt,
        }

    if action_class == "proposal_review":
        proposal_id = _proposal_id_from_trigger(trigger)
        if not proposal_id:
            receipt = _blocked_receipt(
                event_id=event_id,
                actor=actor,
                reason=reason,
                attempt_count=attempt_count,
                ts=ts,
                gate="reactor_proposal_review_requires_proposal_id",
                outcome="proposal_id_required",
                next_step="link_proposal_id_before_reactor_dispatch",
                route="proposal_review",
            )
            return {
                "handled": True,
                "applied": False,
                "blocked": True,
                "status": "dispatch_blocked",
                "outcome": "proposal_id_required",
                "stable_state": "proposal_id_required",
                "next_step": "link_proposal_id_before_reactor_dispatch",
                "receipt": receipt,
            }

        proposal, proposal_path = _proposal_artifact(proposal_id)
        if not proposal:
            receipt = _blocked_receipt(
                event_id=event_id,
                actor=actor,
                reason=reason,
                attempt_count=attempt_count,
                ts=ts,
                gate="reactor_proposal_review_requires_existing_artifact",
                outcome="proposal_artifact_not_found",
                next_step="create_or_link_existing_forge_proposal_before_reactor_dispatch",
                route="proposal_review",
                message=proposal_path,
            )
            return {
                "handled": True,
                "applied": False,
                "blocked": True,
                "status": "dispatch_blocked",
                "outcome": "proposal_artifact_not_found",
                "stable_state": "proposal_artifact_not_found",
                "next_step": "create_or_link_existing_forge_proposal_before_reactor_dispatch",
                "receipt": receipt,
            }

        analysis = analyze_proposal_quality(proposal)
        evidence = _as_dict(analysis.get("evidence"))
        ready = bool(analysis.get("ready"))
        outcome = "proposal_review_ready" if ready else "proposal_review_blocked"
        next_step = "eligible_for_operator_review_decision" if ready else "review_missing_proposal_quality_requirements"
        receipt = _redacted_dict(
            {
                "kind": "reactor.dispatch.execution.receipt",
                "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
                "event_id": event_id,
                "status": "completed",
                "outcome": outcome,
                "route": "proposal_review",
                "gate": "reactor_dispatch_engine",
                "stable_state": "proposal_review_inspected",
                "next_step": next_step,
                "actor": actor,
                "reason": reason,
                "proposal_id": proposal_id,
                "plugin_id": _safe_str(proposal.get("plugin_id") or analysis.get("plugin_id")).strip(),
                "proposal_status": _safe_str(proposal.get("status") or analysis.get("status")).strip(),
                "proposal_artifact_path": proposal_path,
                "quality_ready": ready,
                "missing_requirements": _as_str_list(analysis.get("missing_requirements")),
                "review_status": _safe_str(evidence.get("review_status")).strip(),
                "review_receipt_id": _safe_str(evidence.get("review_receipt_id")).strip(),
                "validation_receipt_id": _safe_str(evidence.get("validation_receipt_id")).strip(),
                "validation_receipt_path": _safe_str(evidence.get("validation_receipt_path")).strip(),
                "proposal_quality_analysis": analysis,
                "attempt_count": attempt_count,
                "ts": ts,
                "execution_started": False,
                "dispatch_applied": True,
                "verified": True,
                "completion_claim_allowed": True,
                "memory_write": False,
                "readback_only": True,
                "proposal_decision_applied": False,
                "promotion_applied": False,
                "governance": {
                    "gate": "reactor_dispatch_engine",
                    "execution_authority": False,
                    "dispatch_authority": True,
                    "approval_authority": False,
                    "promotion_authority": False,
                    "memory_write": False,
                    "authority_source": "reactor.write",
                    "readback_only": True,
                },
            }
        )
        return {
            "handled": True,
            "applied": True,
            "blocked": False,
            "status": "dispatch_completed",
            "outcome": outcome,
            "stable_state": "proposal_review_inspected",
            "next_step": next_step,
            "receipt": receipt,
            "proposal_quality_analysis": analysis,
        }

    if action_class == "resume":
        if _safe_str(trigger.get("source")).strip().lower() != "approval_decision":
            return {"handled": False}
        approval_id = _approval_id_from_trigger(trigger)
        approval_status = _approval_record_status(approval_id)
        if not approval_id or approval_status not in {"approved", "rejected", "emergency"}:
            receipt = _blocked_receipt(
                event_id=event_id,
                actor=actor,
                reason=reason,
                attempt_count=attempt_count,
                ts=ts,
                gate="reactor_resume_requires_terminal_approval",
                outcome=f"approval_{approval_status or 'id_required'}",
                next_step="wait_for_terminal_approval_decision_before_reactor_resume",
                route="approval_resume",
                message=approval_id,
            )
            return {
                "handled": True,
                "applied": False,
                "blocked": True,
                "status": "dispatch_blocked",
                "outcome": f"approval_{approval_status or 'id_required'}",
                "stable_state": f"approval_{approval_status or 'id_required'}",
                "next_step": "wait_for_terminal_approval_decision_before_reactor_resume",
                "receipt": receipt,
            }

        receipt = _approval_resume_receipt(
            event_id=event_id,
            trigger=trigger,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
        )
        return {
            "handled": True,
            "applied": True,
            "blocked": False,
            "status": "dispatch_completed",
            "outcome": receipt.get("outcome"),
            "stable_state": "approval_resume_recorded",
            "next_step": receipt.get("next_step"),
            "receipt": receipt,
        }

    if action_class == "mission_tick":
        allowed, permission = _mission_write_permission(actor)
        if not allowed:
            receipt = _blocked_receipt(
                event_id=event_id,
                actor=actor,
                reason=reason,
                attempt_count=attempt_count,
                ts=ts,
                gate="missions_write_permission_gate",
                outcome="mission_tick_permission_denied",
                next_step="configure_missions_write_scope_before_reactor_dispatch",
                route="mission_tick",
                permission=permission,
            )
            return {
                "handled": True,
                "applied": False,
                "blocked": True,
                "status": "dispatch_blocked",
                "outcome": "mission_tick_permission_denied",
                "stable_state": "mission_tick_permission_denied",
                "next_step": "configure_missions_write_scope_before_reactor_dispatch",
                "receipt": receipt,
            }

        posture_block = _posture_block("reactor mission queue dispatch")
        if posture_block:
            receipt = _blocked_receipt(
                event_id=event_id,
                actor=actor,
                reason=reason,
                attempt_count=attempt_count,
                ts=ts,
                gate="operator_posture",
                outcome="operator_posture_blocks_execution",
                next_step="switch_operator_posture_before_reactor_dispatch",
                route="mission_tick",
                message=posture_block,
            )
            return {
                "handled": True,
                "applied": False,
                "blocked": True,
                "status": "dispatch_blocked",
                "outcome": "operator_posture_blocks_execution",
                "stable_state": "operator_posture_blocks_execution",
                "next_step": "switch_operator_posture_before_reactor_dispatch",
                "receipt": receipt,
            }

        mission_queue_limit = _safe_int(bounds.get("max_actions"), default=1, minimum=1, maximum=50)
        result = mission_runtime.run_queue_once(
            limit=mission_queue_limit,
            actor=actor or "reactor.dispatch",
            note=reason or "reactor_mission_tick",
        )
        result_data = result if isinstance(result, dict) else {"ok": False, "error": "unexpected_mission_tick_result"}
        identity = _mission_queue_identity(result_data)
        ok = bool(result_data.get("ok"))
        status = "dispatch_completed" if ok else "dispatch_failed"
        outcome = "mission_tick_succeeded" if ok else "mission_tick_failed"
        stable_state = "dispatch_succeeded" if ok else "dispatch_failed"
        raw_errors = result_data.get("errors")
        mission_queue_errors = raw_errors if isinstance(raw_errors, list) else []
        next_step = (
            "return_to_stable_state_with_mission_queue_receipts"
            if ok
            else "review_failed_mission_tick_before_retry_or_deadletter"
        )
        receipt = _redacted_dict(
            {
                "kind": "reactor.dispatch.execution.receipt",
                "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
                "event_id": event_id,
                "status": "completed" if ok else "failed",
                "outcome": outcome,
                "route": "mission_tick",
                "gate": "reactor_dispatch_engine",
                "stable_state": stable_state,
                "next_step": next_step,
                "actor": actor,
                "reason": reason,
                "mission_queue_limit": mission_queue_limit,
                "mission_queue_total": _safe_int(result_data.get("total"), default=0, minimum=0, maximum=10_000),
                "mission_queue_processed": _safe_int(
                    result_data.get("processed"), default=0, minimum=0, maximum=10_000
                ),
                "mission_queue_applied": _safe_int(result_data.get("applied"), default=0, minimum=0, maximum=10_000),
                "mission_queue_advanced": _safe_int(result_data.get("advanced"), default=0, minimum=0, maximum=10_000),
                "mission_queue_error_count": len(mission_queue_errors),
                "mission_queue_counts": _as_dict(result_data.get("counts")),
                "mission_ids": identity.get("mission_ids"),
                "operation_ids": identity.get("operation_ids"),
                "trace_ids": identity.get("trace_ids"),
                "run_ids": identity.get("run_ids"),
                "memory_receipt_ids": identity.get("memory_receipt_ids"),
                "attempt_count": attempt_count,
                "ts": ts,
                "execution_started": True,
                "dispatch_applied": True,
                "verified": ok,
                "completion_claim_allowed": ok,
                "memory_write": identity.get("memory_write"),
                "governance": {
                    "gate": "reactor_dispatch_engine",
                    "execution_authority": True,
                    "dispatch_authority": True,
                    "approval_authority": False,
                    "memory_write": bool(identity.get("memory_write")),
                    "authority_source": "missions.write",
                },
            }
        )
        return {
            "handled": True,
            "applied": True,
            "blocked": False,
            "status": status,
            "outcome": outcome,
            "stable_state": stable_state,
            "next_step": next_step,
            "receipt": receipt,
            "mission_queue_result": result_data,
        }

    operation_id = _safe_str(trigger.get("operation_id")).strip()
    if not operation_id:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="reactor_operation_run_requires_operation_id",
            outcome="operation_id_required",
            next_step="link_operation_id_before_reactor_dispatch",
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operation_id_required",
            "stable_state": "operation_id_required",
            "next_step": "link_operation_id_before_reactor_dispatch",
            "receipt": receipt,
        }

    allowed, permission = _operation_run_permission(actor)
    if not allowed:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="operations_run_permission_gate",
            outcome="operation_run_permission_denied",
            next_step="configure_operations_run_scope_before_reactor_dispatch",
            operation_id=operation_id,
            permission=permission,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operation_run_permission_denied",
            "stable_state": "operation_run_permission_denied",
            "next_step": "configure_operations_run_scope_before_reactor_dispatch",
            "receipt": receipt,
        }

    posture_block = _posture_block("reactor operation dispatch")
    if posture_block:
        receipt = _blocked_receipt(
            event_id=event_id,
            actor=actor,
            reason=reason,
            attempt_count=attempt_count,
            ts=ts,
            gate="operator_posture",
            outcome="operator_posture_blocks_execution",
            next_step="switch_operator_posture_before_reactor_dispatch",
            operation_id=operation_id,
            message=posture_block,
        )
        return {
            "handled": True,
            "applied": False,
            "blocked": True,
            "status": "dispatch_blocked",
            "outcome": "operator_posture_blocks_execution",
            "stable_state": "operator_posture_blocks_execution",
            "next_step": "switch_operator_posture_before_reactor_dispatch",
            "receipt": receipt,
        }

    result = operations_runtime.run_operation(
        operation_id,
        worker_id=f"reactor.dispatch.{actor or 'system'}",
        advance_action="reactor_dispatch",
    )
    result_data = result if isinstance(result, dict) else {"ok": False, "error": "unexpected_operation_result"}
    identity = _operation_identity(result_data)
    ok = bool(result_data.get("ok"))
    operation_status = identity.get("operation_status") or "unknown"
    status = "dispatch_completed" if ok else "dispatch_failed"
    outcome = "operation_succeeded" if ok else f"operation_{operation_status or 'failed'}"
    stable_state = "dispatch_succeeded" if ok else "dispatch_failed"
    next_step = (
        "return_to_stable_state_with_operation_receipts" if ok else "review_failed_operation_before_retry_or_deadletter"
    )
    receipt = _redacted_dict(
        {
            "kind": "reactor.dispatch.execution.receipt",
            "receipt_id": f"{event_id}_dispatch_execution_{attempt_count}",
            "event_id": event_id,
            "status": "completed" if ok else "failed",
            "outcome": outcome,
            "route": "operation_run",
            "gate": "reactor_dispatch_engine",
            "stable_state": stable_state,
            "next_step": next_step,
            "actor": actor,
            "reason": reason,
            "operation_id": operation_id,
            "operation_status": operation_status,
            "trace_id": identity.get("trace_id"),
            "run_id": identity.get("run_id"),
            "memory_receipt_id": identity.get("memory_receipt_id"),
            "attempt_count": attempt_count,
            "ts": ts,
            "execution_started": True,
            "dispatch_applied": True,
            "verified": ok,
            "completion_claim_allowed": ok,
            "memory_write": identity.get("memory_write"),
            "governance": {
                "gate": "reactor_dispatch_engine",
                "execution_authority": True,
                "dispatch_authority": True,
                "approval_authority": False,
                "memory_write": bool(identity.get("memory_write")),
                "authority_source": "operations.run",
            },
        }
    )
    return {
        "handled": True,
        "applied": True,
        "blocked": False,
        "status": status,
        "outcome": outcome,
        "stable_state": stable_state,
        "next_step": next_step,
        "receipt": receipt,
        "operation_result": result_data,
    }
