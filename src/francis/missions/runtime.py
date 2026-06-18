from __future__ import annotations

import inspect
from typing import Any

from francis.governance.redaction import redact_secret_text
import francis.missions.store as mission_store
from francis.operations import runtime as operations_runtime


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _queue_run_error(errors: list[dict[str, object]]) -> str:
    if not errors:
        return ""
    first = errors[0]
    return _redact_free_text(first.get("error") or first.get("message")) or "mission_queue_run_failed"


def _redact_result_text(value: Any) -> str | None:
    text = _redact_free_text(value)
    return text or None


def _queue_run_error_record(mission_id: str, action: str, outcome: dict[str, object]) -> dict[str, object]:
    record: dict[str, object] = {
        "mission_id": mission_id,
        "error": _redact_free_text(outcome.get("error")) or "advance_failed",
    }
    fields = {
        "action": action,
        "status": outcome.get("status"),
        "operation_id": outcome.get("operation_id"),
        "approval_id": outcome.get("approval_id"),
        "previous_approval_id": outcome.get("previous_approval_id"),
        "approval_status": outcome.get("approval_status"),
        "gate": outcome.get("gate"),
        "next_step": outcome.get("next_step"),
        "trace_id": outcome.get("trace_id"),
        "run_id": outcome.get("run_id"),
        "artifact_dir": outcome.get("artifact_dir"),
        "operation_error": outcome.get("operation_error"),
        "result_message": outcome.get("result_message"),
        "recovery_next_step": outcome.get("recovery_next_step"),
        "message": outcome.get("message"),
    }
    for key, value in fields.items():
        text = _redact_free_text(value) if key in _FREE_TEXT_HANDOFF_FIELDS else _safe_str(value).strip()
        if text:
            record[key] = text
    return record


def _redact_free_text(value: Any) -> str:
    return redact_secret_text(_safe_str(value).strip())


_FREE_TEXT_HANDOFF_FIELDS = frozenset(
    {
        "message",
        "next_step",
        "operation_error",
        "result_message",
        "recovery_next_step",
    }
)


def _queue_run_request(actor: Any, note: Any, limit: int) -> dict[str, object]:
    return {
        "actor": _redact_free_text(actor) or "missions.runner",
        "note": _redact_free_text(note) or "mission_queue_run_once",
        "limit": max(1, int(limit)),
    }


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


_MISSION_PLAN_CONTEXT_KEYS = frozenset(
    {
        "claim_completed_painting",
        "execution_mode",
        "intent_kind",
        "lens_overlay_observation",
        "live_desktop_execution",
        "no_pasted_image",
        "operator_contract",
        "operator_primitives_required",
        "orb_embodiment",
        "sandbox_status",
        "truthful_limitations",
        "voice_turn_correlation",
    }
)
_MONA_LISA_INTENT_KIND = "mona_lisa_sandbox_painting"
_MONA_LISA_SANDBOX_ACTION = "sandbox.paint.mona_lisa"
_MONA_LISA_SANDBOX_CAPABILITY = "sandbox.canvas.paint_mona_lisa"
_MONA_LISA_CANVAS_SIZE = 512


def _mission_plan_context(meta: Any) -> dict[str, Any]:
    raw = _as_dict(meta)
    return {key: raw[key] for key in sorted(_MISSION_PLAN_CONTEXT_KEYS) if key in raw}


def _mona_lisa_sandbox_requested_region() -> dict[str, Any]:
    return {
        "coordinate_space": "sandbox.logical_pixels",
        "x": 0,
        "y": 0,
        "width": _MONA_LISA_CANVAS_SIZE,
        "height": _MONA_LISA_CANVAS_SIZE,
    }


def _mona_lisa_sandbox_operation_input(
    *,
    mission_id: str,
    plan_operation_id: str,
    mission_plan_context: dict[str, Any],
) -> dict[str, Any]:
    mission_meta = dict(mission_plan_context)
    mission_meta["mission_id"] = mission_id
    mission_meta["plan_operation_id"] = plan_operation_id
    mission_meta["sandbox_status"] = "queued_not_executed"
    mission_meta["claim_completed_painting"] = False

    lens_observation = dict(_as_dict(mission_meta.get("lens_overlay_observation")))
    requested_region = _as_dict(lens_observation.get("requested_region")) or _mona_lisa_sandbox_requested_region()
    lens_observation["requested_region"] = requested_region
    lens_observation.setdefault(
        "mapped_overlay_region",
        {
            **requested_region,
            "status": "mapped",
            "source": "sandbox_canvas_coordinate_model",
            "within_overlay_bounds": True,
            "screen_readback": False,
        },
    )
    lens_observation["status"] = "sandbox_operation_queued_not_observed"
    lens_observation["live_desktop_observation"] = False
    mission_meta["lens_overlay_observation"] = lens_observation

    return {
        "mission_id": mission_id,
        "plan_operation_id": plan_operation_id,
        "mission_meta": mission_meta,
        "operator_contract": _as_dict(mission_meta.get("operator_contract")),
        "lens_overlay_observation": lens_observation,
        "canvas": {"width": _MONA_LISA_CANVAS_SIZE, "height": _MONA_LISA_CANVAS_SIZE},
        "live_desktop_execution": False,
        "paste_image": False,
        "import_image": False,
    }


def _mona_lisa_sandbox_operation_meta(
    *,
    mission_id: str,
    plan_operation_id: str,
    mission_plan_context: dict[str, Any],
) -> dict[str, Any]:
    meta = dict(mission_plan_context)
    meta.update(
        {
            "mission_id": mission_id,
            "plan_operation_id": plan_operation_id,
            "intent_kind": _MONA_LISA_INTENT_KIND,
            "execution_mode": "sandbox_required",
            "sandbox_status": "queued_not_executed",
            "auto_enqueued_from_plan": True,
            "execution_deferred": True,
            "live_desktop_execution": False,
            "claim_completed_painting": False,
        }
    )
    return meta


def _create_mona_lisa_sandbox_operation(
    *,
    record: mission_store.MissionRecord,
    mission_plan_context: dict[str, Any],
    plan_operation_id: str,
    actor: str,
) -> dict[str, object]:
    if str(mission_plan_context.get("intent_kind") or "").strip() != _MONA_LISA_INTENT_KIND:
        return {}

    mission_id = record.mission_id
    created = operations_runtime.create_operation(
        action=_MONA_LISA_SANDBOX_ACTION,
        reason=f"mission.advance:{mission_id}:sandbox_canvas",
        actor=actor,
        mission_id=mission_id,
        idempotency_key=f"{mission_id}:mona_lisa_sandbox_canvas",
        objective=record.objective,
        input=_mona_lisa_sandbox_operation_input(
            mission_id=mission_id,
            plan_operation_id=plan_operation_id,
            mission_plan_context=mission_plan_context,
        ),
        meta=_mona_lisa_sandbox_operation_meta(
            mission_id=mission_id,
            plan_operation_id=plan_operation_id,
            mission_plan_context=mission_plan_context,
        ),
    )
    sandbox_operation_id = _safe_str(created.get("operation_id")).strip()
    if bool(created.get("ok")) and sandbox_operation_id:
        mission_store.record_linked_task_transition(
            mission_id,
            sandbox_operation_id,
            task_status="accepted",
            actor=actor,
            note="mona_lisa_sandbox_operation_queued",
        )
    return created


def _first_text(*values: Any) -> str:
    for value in values:
        text = _safe_str(value).strip()
        if text:
            return text
    return ""


def _operation_handoff(operation: Any) -> dict[str, object]:
    operation_record = _as_dict(operation)
    operation_meta = _as_dict(operation_record.get("meta"))
    operation_output = _as_dict(operation_record.get("output"))
    output_receipt = operation_output.get("receipt") if isinstance(operation_output.get("receipt"), dict) else {}
    output_sandbox = (
        operation_output.get("sandbox")
        if isinstance(operation_output.get("sandbox"), dict)
        else output_receipt.get("sandbox")
        if isinstance(output_receipt.get("sandbox"), dict)
        else {}
    )
    output_audit = output_receipt.get("audit_event") if isinstance(output_receipt.get("audit_event"), dict) else {}
    output_sandbox_audit = (
        output_sandbox.get("audit_event") if isinstance(output_sandbox.get("audit_event"), dict) else {}
    )
    operation_governance = _as_dict(operation_meta.get("governance"))
    output_governance = _as_dict(operation_output.get("governance"))
    receipt_governance = _as_dict(output_receipt.get("governance"))
    sandbox_governance = _as_dict(output_sandbox.get("governance"))
    audit_governance = _as_dict(output_audit.get("governance"))
    sandbox_audit_governance = _as_dict(output_sandbox_audit.get("governance"))
    governance = (
        operation_governance
        or output_governance
        or receipt_governance
        or sandbox_governance
        or audit_governance
        or sandbox_audit_governance
    )
    approval_id = _first_text(
        operation_meta.get("approval_id"),
        operation_output.get("approval_id"),
        output_receipt.get("approval_id"),
        output_sandbox.get("approval_id"),
        output_audit.get("approval_id"),
        output_sandbox_audit.get("approval_id"),
    )
    previous_approval_id = _first_text(
        operation_meta.get("previous_approval_id"),
        operation_meta.get("previousApprovalId"),
        operation_output.get("previous_approval_id"),
        operation_output.get("previousApprovalId"),
        output_receipt.get("previous_approval_id"),
        output_receipt.get("previousApprovalId"),
        output_sandbox.get("previous_approval_id"),
        output_sandbox.get("previousApprovalId"),
        output_audit.get("previous_approval_id"),
        output_audit.get("previousApprovalId"),
        output_sandbox_audit.get("previous_approval_id"),
        output_sandbox_audit.get("previousApprovalId"),
    )
    approval_status = _first_text(
        operation_meta.get("approval_status"),
        operation_meta.get("approvalStatus"),
        operation_output.get("approval_status"),
        operation_output.get("approvalStatus"),
        governance.get("approval_status"),
        governance.get("approvalStatus"),
        output_receipt.get("approval_status"),
        output_receipt.get("approvalStatus"),
        receipt_governance.get("approval_status"),
        receipt_governance.get("approvalStatus"),
        output_sandbox.get("approval_status"),
        output_sandbox.get("approvalStatus"),
        sandbox_governance.get("approval_status"),
        sandbox_governance.get("approvalStatus"),
        output_audit.get("approval_status"),
        output_audit.get("approvalStatus"),
        audit_governance.get("approval_status"),
        audit_governance.get("approvalStatus"),
        output_sandbox_audit.get("approval_status"),
        output_sandbox_audit.get("approvalStatus"),
        sandbox_audit_governance.get("approval_status"),
        sandbox_audit_governance.get("approvalStatus"),
    )
    gate = _safe_str(governance.get("gate")).strip()
    next_step = _redact_free_text(governance.get("next_step"))
    trace_id = (
        _safe_str(operation_record.get("trace_id")).strip()
        or _safe_str(operation_meta.get("trace_id")).strip()
        or _safe_str(operation_output.get("trace_id")).strip()
    )
    trace_id = (
        trace_id
        or _safe_str(operation_output.get("traceId")).strip()
        or _safe_str(output_receipt.get("trace_id")).strip()
        or _safe_str(output_sandbox.get("trace_id")).strip()
        or _safe_str(output_audit.get("trace_id")).strip()
        or _safe_str(output_sandbox_audit.get("trace_id")).strip()
    )
    run_id = (
        _safe_str(operation_record.get("run_id")).strip()
        or _safe_str(operation_meta.get("run_id")).strip()
        or _safe_str(operation_output.get("run_id")).strip()
        or _safe_str(operation_output.get("runId")).strip()
        or _safe_str(output_receipt.get("run_id")).strip()
        or _safe_str(output_sandbox.get("run_id")).strip()
        or _safe_str(output_audit.get("run_id")).strip()
        or _safe_str(output_sandbox_audit.get("run_id")).strip()
    )
    artifact_dir = (
        _safe_str(operation_record.get("artifact_dir")).strip()
        or _safe_str(operation_meta.get("artifact_dir")).strip()
        or _safe_str(operation_output.get("artifact_dir")).strip()
        or _safe_str(operation_output.get("artifact_path")).strip()
        or _safe_str(output_receipt.get("artifact_dir")).strip()
        or _safe_str(output_receipt.get("artifact_path")).strip()
        or _safe_str(output_sandbox.get("artifact_dir")).strip()
        or _safe_str(output_sandbox.get("artifact_path")).strip()
        or _safe_str(output_audit.get("artifact_dir")).strip()
        or _safe_str(output_sandbox_audit.get("artifact_dir")).strip()
    )
    message = _redact_free_text(operation_meta.get("result_message")) or _redact_free_text(
        operation_output.get("message")
    )
    handoff: dict[str, object] = {}
    if approval_id:
        handoff["approval_id"] = approval_id
    if previous_approval_id:
        handoff["previous_approval_id"] = previous_approval_id
    if approval_status:
        handoff["approval_status"] = approval_status
    if gate:
        handoff["gate"] = gate
    if next_step:
        handoff["next_step"] = next_step
    if trace_id:
        handoff["trace_id"] = trace_id
    if run_id:
        handoff["run_id"] = run_id
    if artifact_dir:
        handoff["artifact_dir"] = artifact_dir
    if message:
        handoff["operation_message"] = message
    return handoff


def _operation_receipt_identity(operation: Any) -> dict[str, str]:
    operation_record = _as_dict(operation)
    operation_meta = _as_dict(operation_record.get("meta"))
    return {
        "operation_name": _safe_str(operation_record.get("name")).strip(),
        "operation_plane": _safe_str(operation_meta.get("orb_plane")).strip(),
    }


def _memory_receipt_recovery_handoff(receipt: Any) -> dict[str, object]:
    receipt_payload = _as_dict(receipt)
    handoff: dict[str, object] = {}
    for key in ("operation_error", "result_message", "recovery_next_step"):
        value = _redact_free_text(receipt_payload.get(key))
        if value:
            handoff[key] = value
    return handoff


def _run_operation_for_advance(
    operation_id: str,
    *,
    worker_id: str,
    advance_action: str,
) -> dict[str, object]:
    run_operation = operations_runtime.run_operation
    try:
        parameters = inspect.signature(run_operation).parameters
    except (TypeError, ValueError):
        parameters = {}
    accepts_advance_action = "advance_action" in parameters or any(
        parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )
    if accepts_advance_action:
        return run_operation(operation_id, worker_id=worker_id, advance_action=advance_action)
    return run_operation(operation_id, worker_id=worker_id)


def advance_mission(
    mission_id: str,
    *,
    actor: str = "missions.runner",
    note: str = "mission_advance",
    worker_id: str = "missions.runner",
    record_operator_receipt: bool = True,
) -> dict[str, object]:
    record, _, tick_err = mission_store.tick_mission(
        mission_id,
        actor=actor,
        note="advance_preflight",
    )
    if not record and tick_err:
        return {"ok": False, "applied": False, "error": tick_err}

    record, queue_item, queue_err = mission_store.mission_queue_item(mission_id)
    if not record or not queue_item:
        return {"ok": False, "applied": False, "error": queue_err or "not_found"}

    action = _safe_str(queue_item.get("recommended_action")).strip() or "review_mission"
    action_target_id = _safe_str(queue_item.get("action_target_id")).strip()
    operator_hint = _redact_free_text(queue_item.get("operator_hint"))

    if action == "create_first_operation":
        constraints: dict[str, Any] = {
            "mission_id": mission_id,
            "summary": record.summary,
            "next_step": record.next_step,
        }
        mission_plan_context = _mission_plan_context(record.meta)
        if mission_plan_context:
            constraints["mission_meta"] = mission_plan_context

        created = operations_runtime.create_operation(
            action="plan.create",
            reason=f"mission.advance:{mission_id}",
            actor=actor,
            mission_id=mission_id,
            objective=record.objective,
            input={
                "goal": record.objective,
                "constraints": constraints,
            },
            meta=mission_plan_context,
        )
        operation_id = _safe_str(created.get("operation_id")).strip()
        operation_status = _safe_str(created.get("status")).strip()
        message = _redact_free_text(created.get("message")) or "operation_created"
        operation_identity = _operation_receipt_identity(created.get("operation"))
        receipt_operation_id = operation_id
        receipt_operation_status = operation_status
        sandbox_created: dict[str, object] = {}
        if bool(created.get("ok")) and operation_id:
            sandbox_created = _create_mona_lisa_sandbox_operation(
                record=record,
                mission_plan_context=mission_plan_context,
                plan_operation_id=operation_id,
                actor=actor,
            )
            if sandbox_created:
                sandbox_operation_id = _safe_str(sandbox_created.get("operation_id")).strip()
                sandbox_status = _safe_str(sandbox_created.get("status")).strip()
                sandbox_operation = sandbox_created.get("operation")
                if bool(sandbox_created.get("ok")) and sandbox_operation_id:
                    receipt_operation_id = sandbox_operation_id
                    receipt_operation_status = sandbox_status
                    operation_identity = _operation_receipt_identity(sandbox_operation)
                    message = "operation_created_and_sandbox_operation_queued"
                else:
                    message = (
                        _redact_free_text(sandbox_created.get("error"))
                        or _redact_free_text(sandbox_created.get("message"))
                        or "sandbox_operation_create_failed"
                    )
        advance_ok = bool(created.get("ok")) and (not sandbox_created or bool(sandbox_created.get("ok")))
        mission_store.tick_mission(mission_id, actor=actor, note="advance_post_create")
        if sandbox_created and bool(sandbox_created.get("ok")) and receipt_operation_id:
            _, transition_err = mission_store.record_linked_task_transition(
                mission_id,
                receipt_operation_id,
                task_status="accepted",
                actor=actor,
                note="mona_lisa_sandbox_operation_current_task",
            )
            if transition_err:
                advance_ok = False
                message = transition_err
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome="applied" if advance_ok else "error",
            actor=actor,
            note=note,
            operation_id=receipt_operation_id,
            **operation_identity,
            operation_status=receipt_operation_status,
            message=message,
            applied=advance_ok,
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        response: dict[str, object] = {
            "ok": advance_ok,
            "applied": advance_ok,
            "action": action,
            "mission_record": updated_record,
            "operation": created.get("operation"),
            "operation_id": operation_id or None,
            "status": operation_status or updated_record.status.value,
            "message": message,
            **_operation_handoff(created.get("operation")),
        }
        if sandbox_created:
            sandbox_operation_id = _safe_str(sandbox_created.get("operation_id")).strip()
            sandbox_operation = sandbox_created.get("operation")
            response["linked_operation_action"] = _MONA_LISA_SANDBOX_CAPABILITY
            response["linked_operation_id"] = sandbox_operation_id or None
            response["linked_operation_status"] = _safe_str(sandbox_created.get("status")).strip() or None
            response["linked_operation_queued"] = bool(sandbox_created.get("ok"))
            if isinstance(sandbox_operation, dict):
                response["linked_operation"] = sandbox_operation
            if sandbox_created.get("error"):
                response["linked_operation_error"] = _redact_free_text(sandbox_created.get("error"))
        return response

    if action == "run_linked_operation" and action_target_id:
        run_result = _run_operation_for_advance(
            action_target_id,
            worker_id=worker_id,
            advance_action=action,
        )
        mission_store.tick_mission(mission_id, actor=actor, note="advance_post_run")
        operation_status = _safe_str(run_result.get("status")).strip()
        message = _redact_free_text(run_result.get("message")) or "operation_run"
        operation_identity = _operation_receipt_identity(run_result.get("operation"))
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome=operation_status or ("applied" if bool(run_result.get("ok")) else "error"),
            actor=actor,
            note=note,
            operation_id=action_target_id,
            **operation_identity,
            operation_status=operation_status,
            message=message,
            applied=bool(run_result.get("ok")),
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        response: dict[str, object] = {
            "ok": bool(run_result.get("ok")),
            "applied": bool(run_result.get("ok")),
            "action": action,
            "mission_record": updated_record,
            "operation": run_result.get("operation"),
            "operation_id": action_target_id,
            "status": operation_status or updated_record.status.value,
            "message": message,
            **_operation_handoff(run_result.get("operation")),
        }
        memory_receipt = run_result.get("memory_receipt")
        if isinstance(memory_receipt, dict):
            response["memory_receipt"] = memory_receipt
            response.update(_memory_receipt_recovery_handoff(memory_receipt))
        return response

    if record_operator_receipt:
        updated_record, receipt_err = mission_store.record_advance_receipt(
            mission_id,
            action=action,
            outcome="requires_operator",
            actor=actor,
            note=note,
            operation_id=action_target_id,
            operation_status=_safe_str(queue_item.get("last_task_status")).strip(),
            message=operator_hint or "Mission cannot be advanced automatically from the current queue state.",
            applied=False,
        )
        if receipt_err:
            return {"ok": False, "applied": False, "error": receipt_err}
        if action in mission_store.RECOVERY_REVIEW_ACTIONS:
            recovery_record, recovery_err = mission_store.record_recovery_review_receipt(
                mission_id,
                action=action,
                outcome="requires_operator",
                actor=actor,
                note=note,
                target_id=action_target_id,
                message=operator_hint or "Mission requires operator intervention.",
                source_status=record.status.value,
            )
            if recovery_err:
                return {"ok": False, "applied": False, "error": recovery_err}
            if recovery_record is not None:
                updated_record = recovery_record
        return {
            "ok": True,
            "applied": False,
            "action": action,
            "mission_record": updated_record,
            "operation_id": action_target_id or None,
            "status": updated_record.status.value,
            "message": operator_hint or "Mission requires operator intervention.",
        }

    return {
        "ok": True,
        "applied": False,
        "action": action,
        "mission_record": record,
        "operation_id": action_target_id or None,
        "status": record.status.value,
        "message": operator_hint or "Mission requires operator intervention.",
    }


def run_queue_once(
    *,
    limit: int = 50,
    actor: str = "missions.runner",
    note: str = "mission_queue_run_once",
) -> dict[str, object]:
    safe_limit = max(1, int(limit))
    records, tick_applied, errors = mission_store.tick_all_missions(
        limit=max(safe_limit, 200),
        actor=actor,
        note=note,
    )
    initial_items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=False)

    results: list[dict[str, object]] = []
    advanced = 0
    for item in initial_items:
        mission_id = _safe_str(item.get("id")).strip()
        if not mission_id:
            continue
        action = _safe_str(item.get("recommended_action")).strip() or "review_mission"
        if action not in mission_store.AUTO_ADVANCE_ACTIONS:
            results.append(
                {
                    "mission_id": mission_id,
                    "ok": True,
                    "applied": False,
                    "action": action,
                    "status": _safe_str(item.get("status")).strip(),
                    "operation_id": _safe_str(item.get("action_target_id")).strip() or None,
                    "message": _redact_free_text(item.get("operator_hint"))
                    or "Mission requires operator intervention.",
                }
            )
            continue

        outcome = advance_mission(
            mission_id,
            actor=actor,
            note=note,
            worker_id=actor,
            record_operator_receipt=False,
        )
        result: dict[str, object] = {
            "mission_id": mission_id,
            "ok": bool(outcome.get("ok")),
            "applied": bool(outcome.get("applied")),
            "action": _safe_str(outcome.get("action")).strip() or action,
            "status": _safe_str(outcome.get("status")).strip(),
            "operation_id": _safe_str(outcome.get("operation_id")).strip() or None,
            "message": _redact_free_text(outcome.get("message")),
            "approval_id": _safe_str(outcome.get("approval_id")).strip() or None,
            "previous_approval_id": _safe_str(outcome.get("previous_approval_id")).strip() or None,
            "approval_status": _safe_str(outcome.get("approval_status")).strip() or None,
            "gate": _safe_str(outcome.get("gate")).strip() or None,
            "next_step": _redact_result_text(outcome.get("next_step")),
            "trace_id": _safe_str(outcome.get("trace_id")).strip() or None,
            "run_id": _safe_str(outcome.get("run_id")).strip() or None,
            "artifact_dir": _safe_str(outcome.get("artifact_dir")).strip() or None,
            "operation_error": _redact_result_text(outcome.get("operation_error")),
            "result_message": _redact_result_text(outcome.get("result_message")),
            "recovery_next_step": _redact_result_text(outcome.get("recovery_next_step")),
        }
        operation = outcome.get("operation")
        if isinstance(operation, dict):
            result["operation"] = operation
        memory_receipt = outcome.get("memory_receipt")
        if isinstance(memory_receipt, dict):
            result["memory_receipt"] = memory_receipt
        results.append(result)
        if bool(outcome.get("applied")):
            advanced += 1
        elif outcome.get("ok") is False:
            errors.append(_queue_run_error_record(mission_id, action, outcome))

    queue_items = mission_store.mission_queue_items(limit=safe_limit, include_terminal=False)
    failed_items = mission_store.failed_queue_items(limit=min(safe_limit, 20))
    deadletter_items = mission_store.deadletter_queue_items(limit=min(safe_limit, 20))
    counts = {
        "queued": 0,
        "active": 0,
        "blocked": 0,
        "failed": len(failed_items),
        "deadlettered": len(deadletter_items),
    }
    for item in queue_items:
        status = _safe_str(item.get("status")).strip().lower()
        if status in counts:
            counts[status] += 1

    status = "failed" if errors else "succeeded"
    response: dict[str, object] = {
        "ok": not errors,
        "items": queue_items,
        "failed": failed_items,
        "deadletter": deadletter_items,
        "total": len(queue_items),
        "applied": tick_applied + advanced,
        "advanced": advanced,
        "results": results,
        "processed": len(records),
        "errors": errors,
        "counts": counts,
        "status": status,
        "request": _queue_run_request(actor, note, safe_limit),
    }
    if errors:
        response["error"] = _queue_run_error(errors)
    return response
