from __future__ import annotations

from francis.api.errors import api_error_code, log_api_exception
import json
from typing import Any, cast
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from francis.api.routes._operator_posture import posture_write_guard
from francis.api.websocket import ConnectionManager
from francis.chat.continuity.ledger import append
from francis.chat.router import handle, parse_mission_ingress
from francis.governance.api_permission_gate import ApiPermissionDecision, ApiPermissionGate
from francis.governance.redaction import redact_secret_text
from francis.missions import runtime as mission_runtime
from francis.missions import store as mission_store
from francis.missions.store import MissionCreateRequest
from francis.telemetry.context import TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE, telemetry_context_snapshot

router = APIRouter()
manager = ConnectionManager()
_CHAT_MISSION_ACTOR = "chat.send"
_CHAT_WRITE_SCOPE = "chat.write"
_MISSION_WRITE_SCOPE = "missions.write"


@router.get("/health")
def health() -> dict[str, object]:
    return {"ok": True, "service": "chat"}


class ChatIn(BaseModel):
    message: str
    use_llm: bool = False
    actor: str | None = None
    request_actor: str | None = None
    api_actor: str | None = None


def _safe_dict(value: object) -> dict[str, object]:
    return cast(dict[str, object], value) if isinstance(value, dict) else {}


def _safe_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float, str, bytes, bytearray)):
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return 0


def _chat_text_from_wire(raw: str) -> str:
    if not isinstance(raw, str):
        return str(raw)

    stripped = raw.strip()
    if not stripped:
        return ""

    try:
        decoded = json.loads(stripped)
    except Exception:
        return raw
    if not isinstance(decoded, dict):
        return raw

    message = decoded.get("message") if isinstance(decoded.get("message"), dict) else decoded
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, str):
        return content
    return raw


def _mission_ingress_ws_event(payload: dict[str, object]) -> str:
    reply = str(payload.get("reply") or "")
    meta = {
        key: payload[key]
        for key in (
            "ok",
            "mode",
            "status",
            "error",
            "mission_id",
            "mission",
            "operation_id",
            "operation",
            "advance",
            "queue_item",
            "loop_state",
            "current_task",
            "receipt_summary",
            "memory_receipt_count",
            "latest_memory_receipt",
            "governance",
        )
        if key in payload
    }
    return json.dumps(
        {
            "type": "message",
            "message": {
                "role": "assistant",
                "content": reply,
                "meta": meta,
            },
        },
        ensure_ascii=True,
    )


def _compact_mission_ingress_meta(
    *,
    record: mission_store.MissionRecord,
    loop_state: dict[str, object],
    current_task: dict[str, object],
    receipt_summary: dict[str, object],
) -> dict[str, object]:
    handoff = _safe_dict(loop_state.get("handoff"))
    meta: dict[str, object] = {
        "mode": "mission_ingress",
        "status": record.status.value,
        "mission_id": record.mission_id,
        "ingress_plane": "P1_INTERFACE",
        "active_stage": str(loop_state.get("active_stage") or "").strip(),
        "handoff_stage": str(handoff.get("stage") or "").strip(),
        "handoff_action": str(handoff.get("action") or "").strip(),
        "handoff_gate": str(handoff.get("gate") or "").strip(),
        "handoff_approval_id": str(handoff.get("approval_id") or "").strip(),
        "handoff_approval_status": str(handoff.get("approval_status") or "").strip(),
        "handoff_operation_id": str(handoff.get("operation_id") or "").strip(),
        "handoff_trace_id": str(handoff.get("trace_id") or "").strip(),
        "handoff_run_id": str(handoff.get("run_id") or "").strip(),
        "handoff_artifact_dir": str(handoff.get("artifact_dir") or "").strip(),
        "handoff_next_step": str(handoff.get("next_step") or "").strip(),
        "current_task_source": str(current_task.get("source") or "").strip(),
        "current_task_approval_id": str(current_task.get("approval_id") or "").strip(),
        "current_task_approval_status": str(current_task.get("approval_status") or "").strip(),
        "current_task_previous_approval_id": str(current_task.get("previous_approval_id") or "").strip(),
        "current_task_previous_approval_status": str(current_task.get("previous_approval_status") or "").strip(),
        "current_task_operation_id": str(current_task.get("operation_id") or "").strip(),
        "current_task_operation_name": str(current_task.get("operation_name") or "").strip(),
        "current_task_operation_plane": str(current_task.get("operation_plane") or "").strip(),
        "current_task_gate": str(current_task.get("gate") or "").strip(),
        "current_task_trace_id": str(current_task.get("trace_id") or "").strip(),
        "current_task_run_id": str(current_task.get("run_id") or "").strip(),
        "current_task_artifact_dir": str(current_task.get("artifact_dir") or "").strip(),
        "current_task_advance_action": str(current_task.get("advance_action") or "").strip(),
        "current_task_next_step": str(current_task.get("next_step") or "").strip(),
        "linked_operation_count": _safe_int(receipt_summary.get("linked_operation_count") or 0),
        "run_ledger_count": _safe_int(receipt_summary.get("run_ledger_count") or 0),
        "memory_receipt_count": _safe_int(receipt_summary.get("memory_receipt_count") or 0),
    }
    return {key: value for key, value in meta.items() if value not in {"", None}}


def _mission_write_permission(actor: object, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_MISSION_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _chat_actor(payload: ChatIn) -> str:
    actor = (payload.request_actor or payload.api_actor or payload.actor or "").strip()
    return actor or "api.chat"


def _chat_write_permission(actor: object, *, route: str, method: str) -> ApiPermissionDecision:
    return ApiPermissionGate.from_env().check(
        actor_id=actor,
        required_scopes=[_CHAT_WRITE_SCOPE],
        route=route,
        method=method,
    )


def _chat_feedback_memory_assistance_context(telemetry_context: dict[str, Any]) -> dict[str, Any]:
    context = dict(telemetry_context)
    try:
        from francis.api.routes.telemetry import context_feedback_memory_assistance_chat_context_readback

        readback = context_feedback_memory_assistance_chat_context_readback(limit=20)
    except Exception as exc:
        log_api_exception(exc, route="chat.feedback_memory_assistance_context")
        context["feedback_memory_assistance_prompt_integration"] = {
            "status": "unavailable",
            "applies_to_chat_now": False,
            "line_count": 0,
            "reason": api_error_code(),
            "writes_memory": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
        }
        return context

    chat_context = _safe_dict(readback.get("chat_context"))
    raw_lines_value = chat_context.get("lines")
    raw_lines = raw_lines_value if isinstance(raw_lines_value, list) else []
    assistance_lines = [
        redact_secret_text(str(line).strip()).replace("\r", " ").replace("\n", " ").strip()
        for line in raw_lines[:2]
        if str(line).strip()
    ]
    existing_lines_value = context.get("prompt_lines")
    existing_lines = existing_lines_value if isinstance(existing_lines_value, list) else []
    prompt_lines = [
        redact_secret_text(str(line).strip()).replace("\r", " ").replace("\n", " ").strip()
        for line in existing_lines
        if str(line).strip()
    ]
    for line in assistance_lines:
        if line and line not in prompt_lines:
            prompt_lines.append(line)

    context["prompt_lines"] = prompt_lines
    context["max_prompt_lines"] = min(len(prompt_lines), 7)
    feedback_target: dict[str, object] = {}
    if assistance_lines:
        feedback_context_id = f"tel_ctx_feedback_memory_assistance_chat_{uuid.uuid4().hex[:16]}"
        feedback_target = {
            "feedback_route": "/telemetry/context/feedback",
            "required_scope": TELEMETRY_CONTEXT_FEEDBACK_WRITE_SCOPE,
            "actor": "chat_ui.system",
            "context_id": feedback_context_id,
            "message_id": feedback_context_id,
            "surface": "chat",
            "reply_mode": "feedback_memory_assistance_prompt_context",
            "source_ids": ["feedback_memory_assistance", "telemetry_context"],
            "tags": ["stage7", "feedback_memory_assistance", "chat_prompt_context"],
            "ratings": ["useful", "not_useful", "neutral"],
            "records_operator_feedback": True,
            "writes_memory": False,
            "calls_model": False,
            "selects_tools": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        }
    context["feedback_memory_assistance_prompt_integration"] = {
        "status": "applied" if assistance_lines else "empty",
        "source_route": "/telemetry/context/feedback/memory-assistance-chat-context-readback",
        "target": chat_context.get("target") or "telemetry_context.prompt_lines",
        "line_count": len(assistance_lines),
        "max_context_lines": _safe_int(chat_context.get("max_context_lines") or 2),
        "applies_to_chat_now": bool(assistance_lines),
        "telemetry_is_untrusted_input": True,
        "redacted_context_lines": True,
        "reads_memory": bool(readback.get("reads_memory", True)),
        "writes_memory": False,
        "calls_model": False,
        "mutates_prompt": True,
        "selects_tools": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "feedback_target": feedback_target,
        "next_smallest_truthful_gap": "stage7_context_feedback_memory_assistance_operator_feedback_loop_e2e_sample",
    }
    return context


def _permission_denied(
    decision: ApiPermissionDecision,
    *,
    next_step: str = "configure_actor_scope_before_declaring_chat_missions",
    reply: str = "Mission declaration denied by permission gate.",
) -> dict[str, object]:
    governance = {
        "gate": "permission_gate",
        "reason": decision.reason,
        "next_step": next_step,
        "evidence": decision.evidence,
    }
    return {
        "ok": False,
        "mode": "chat",
        "status": "denied",
        "error": "api_permission_denied",
        "governance": governance,
        "reply": reply,
    }


def _posture_block_governance(blocked_reason: str) -> dict[str, object]:
    reason = "operator_posture_unverified"
    next_step = "verify_operator_posture_before_declaring_chat_missions"
    handoff_action = "verify_operator_posture"
    if "Observe mode keeps Francis read-only." in blocked_reason:
        reason = "observe_mode"
        next_step = "switch_operator_posture_before_declaring_chat_missions"
        handoff_action = "switch_operator_posture"
    elif "Current operator posture blocks writes." in blocked_reason:
        reason = "writes_blocked"
        next_step = "adjust_environment_posture_before_declaring_chat_missions"
        handoff_action = "adjust_environment_posture"
    return {
        "gate": "operator_posture",
        "reason": reason,
        "next_step": next_step,
        "handoff_action": handoff_action,
    }


def _compact_mission_gate_meta(
    *,
    status: str,
    error: str = "",
    governance: dict[str, object] | None = None,
    handoff_action: str = "",
) -> dict[str, object]:
    governance_obj = governance if isinstance(governance, dict) else {}
    gate = str(governance_obj.get("gate") or "").strip()
    reason = str(governance_obj.get("reason") or "").strip()
    next_step = str(governance_obj.get("next_step") or "").strip()

    meta: dict[str, object] = {
        "mode": "mission_ingress",
        "status": status,
        "ingress_plane": "P1_INTERFACE",
        "active_stage": "gate",
        "handoff_stage": "gate",
    }
    if error:
        meta["error"] = error
    if handoff_action:
        meta["handoff_action"] = handoff_action
    if gate:
        meta["handoff_gate"] = gate
        meta["governance_gate"] = gate
    if reason:
        meta["governance_reason"] = reason
    if next_step:
        meta["handoff_next_step"] = next_step
        meta["governance_next_step"] = next_step
    evidence = governance_obj.get("evidence")
    if isinstance(evidence, dict):
        meta["governance_evidence"] = evidence
    return meta


def _compact_mission_advance_result(outcome: dict[str, object]) -> dict[str, object]:
    compact: dict[str, object] = {}
    for key in ("ok", "applied"):
        if key in outcome:
            compact[key] = bool(outcome.get(key))
    for key in (
        "action",
        "status",
        "message",
        "operation_id",
        "approval_id",
        "gate",
        "next_step",
        "trace_id",
        "run_id",
        "artifact_dir",
    ):
        text = str(outcome.get(key) or "").strip()
        if text:
            compact[key] = text
    return compact


def _mission_ingress_reply(
    payload: ChatIn, *, route: str = "/chat/send", method: str = "POST"
) -> dict[str, object] | None:
    intent = parse_mission_ingress(payload.message)
    if intent is None:
        return None

    objective = redact_secret_text(intent.objective.strip())
    append("user", f"/mission {objective}".strip(), {"mode": "mission_ingress", "redacted": True})
    if not objective:
        reply = "Mission declaration needs an objective after /mission."
        append("assistant", reply, {"mode": "mission_ingress", "status": "rejected"})
        return {
            "ok": False,
            "mode": "mission_ingress",
            "status": "rejected",
            "error": "objective_required",
            "reply": reply,
        }

    blocked_reason = posture_write_guard("declaring a mission from chat")
    if blocked_reason:
        reply = f"Mission declaration blocked: {blocked_reason}"
        governance = _posture_block_governance(blocked_reason)
        append(
            "assistant",
            reply,
            _compact_mission_gate_meta(
                status="blocked",
                error=blocked_reason,
                governance=governance,
                handoff_action=str(governance.get("handoff_action") or ""),
            ),
        )
        return {
            "ok": False,
            "mode": "mission_ingress",
            "status": "blocked",
            "error": blocked_reason,
            "governance": {key: value for key, value in governance.items() if key != "handoff_action"},
            "reply": reply,
        }

    permission = _mission_write_permission(_CHAT_MISSION_ACTOR, route=route, method=method)
    if not permission.allowed:
        denied = _permission_denied(
            permission,
            next_step="configure_actor_scope_before_declaring_chat_missions",
            reply="Mission declaration denied by permission gate.",
        )
        denied["mode"] = "mission_ingress"
        append(
            "assistant",
            str(denied["reply"]),
            _compact_mission_gate_meta(
                status="denied",
                error="api_permission_denied",
                governance=_safe_dict(denied.get("governance")),
                handoff_action="configure_actor_scope",
            ),
        )
        return denied

    record, err = mission_store.create_mission(
        MissionCreateRequest(
            objective=objective,
            summary="Mission declared from chat ingress.",
            next_step="Declare or advance the first bounded operation for this mission.",
            requester_id=_CHAT_MISSION_ACTOR,
            owner_id=_CHAT_MISSION_ACTOR,
            status=mission_store.MissionStatus.QUEUED,
            meta={"source": _CHAT_MISSION_ACTOR, "ingress_plane": "P1_INTERFACE"},
        )
    )
    if not record:
        error = err or "mission_create_failed"
        reply = f"Mission declaration failed: {error}"
        append("assistant", reply, {"mode": "mission_ingress", "status": "failed"})
        return {"ok": False, "mode": "mission_ingress", "status": "failed", "error": error, "reply": reply}

    advance_result = mission_runtime.advance_mission(
        record.mission_id,
        actor=_CHAT_MISSION_ACTOR,
        note="chat_mission_ingress_first_operation",
        worker_id=_CHAT_MISSION_ACTOR,
    )
    projected_record = advance_result.get("mission_record")
    if not isinstance(projected_record, mission_store.MissionRecord):
        projected_record = record

    from francis.api.routes import missions as mission_routes

    detail = mission_routes._mission_detail_projection(projected_record)
    queue_item = _safe_dict(detail.get("queue_item"))
    loop_state = _safe_dict(detail.get("loop_state"))
    current_task = _safe_dict(detail.get("current_task"))
    receipt_summary = _safe_dict(detail.get("receipt_summary"))
    handoff = _safe_dict(loop_state.get("handoff"))
    action = str(handoff.get("action") or "link_operation").strip()
    advance = _compact_mission_advance_result(advance_result)
    operation_id = str(advance.get("operation_id") or "").strip()
    if bool(advance.get("applied")) and operation_id:
        reply = (
            f"Mission {projected_record.mission_id} declared. First operation {operation_id} queued. Next: {action}."
        )
    elif advance_result.get("ok") is False:
        error = str(advance_result.get("error") or advance_result.get("message") or "operation_link_failed").strip()
        reply = f"Mission {projected_record.mission_id} declared, but first operation link failed: {error}"
    else:
        reply = f"Mission {projected_record.mission_id} declared. Next: {action}."
    append(
        "assistant",
        reply,
        _compact_mission_ingress_meta(
            record=projected_record,
            loop_state=loop_state,
            current_task=current_task,
            receipt_summary=receipt_summary,
        ),
    )

    response: dict[str, Any] = {
        "ok": bool(advance_result.get("ok", True)),
        "mode": "mission_ingress",
        "status": projected_record.status.value,
        "reply": reply,
        "mission_id": projected_record.mission_id,
        "mission": mission_routes._serialize_mission(projected_record, queue_item),
        "advance": advance,
    }
    if operation_id:
        response["operation_id"] = operation_id
    operation = advance_result.get("operation")
    if isinstance(operation, dict):
        response["operation"] = operation
    if advance_result.get("error"):
        response["error"] = str(advance_result.get("error") or "").strip()
    response.update(detail)
    return response


@router.post("/send")
def send(payload: ChatIn) -> dict[str, object]:
    try:
        mission_reply = _mission_ingress_reply(payload, route="/chat/send", method="POST")
        if mission_reply is not None:
            return mission_reply
        actor = _chat_actor(payload)
        permission = _chat_write_permission(actor, route="/chat/send", method="POST")
        if not permission.allowed:
            return _permission_denied(
                permission,
                next_step="configure_actor_scope_before_writing_chat_ledger",
                reply="Chat request denied by permission gate.",
            )
        telemetry_context = _chat_feedback_memory_assistance_context(telemetry_context_snapshot(surface="chat"))
        return {
            "reply": handle(
                payload.message,
                use_llm=payload.use_llm,
                telemetry_context=telemetry_context,
                api_actor=actor,
            ),
            "telemetry_context": telemetry_context,
        }
    except Exception as exc:
        log_api_exception(exc, route="chat.send")
        return {"reply": "", "error": api_error_code()}


@router.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            raw_msg = await websocket.receive_text()
            msg = _chat_text_from_wire(raw_msg)
            mission_reply = _mission_ingress_reply(
                ChatIn(message=msg, use_llm=False), route="/chat/ws", method="WEBSOCKET"
            )
            if mission_reply is not None:
                await websocket.send_text(_mission_ingress_ws_event(mission_reply))
                continue
            reply = handle(msg, use_llm=False)
            await websocket.send_text(reply)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
