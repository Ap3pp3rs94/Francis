from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from francis.api.app import create_app

DEFAULT_ACTOR = "operator.stage3.readiness"
DEFAULT_DEADLETTER_REASON = "stage3_readiness_proof_deadletter"


def _response_body(response: Any) -> dict[str, Any]:
    try:
        body = response.json()
    except Exception:
        return {"raw": getattr(response, "text", "")}
    return body if isinstance(body, dict) else {"body": body}


def _readiness_from_briefing(client: TestClient) -> dict[str, Any]:
    response = client.get("/continuity/briefing")
    body = _response_body(response)
    raw_briefing = body.get("briefing")
    if not isinstance(raw_briefing, dict):
        return {}
    readiness = raw_briefing.get("readiness")
    if not isinstance(readiness, dict):
        return {}
    return dict(readiness)


def _is_ready(readiness: dict[str, Any]) -> bool:
    blocked = readiness.get("blocked_criteria_ids")
    attention = readiness.get("attention_criteria_ids")
    review = readiness.get("review_criteria_ids")
    return (
        readiness.get("status") == "ready"
        and readiness.get("satisfied") == readiness.get("total")
        and blocked == []
        and attention == []
        and review == []
    )


def _failed_result(
    *,
    stage: str,
    response: Any,
    initial_readiness: dict[str, Any],
    proof_missions: dict[str, str],
) -> dict[str, Any]:
    body = _response_body(response)
    return {
        "ok": False,
        "stage": stage,
        "status_code": getattr(response, "status_code", None),
        "error": str(body.get("error") or body.get("message") or "stage_failed"),
        "body": body,
        "initial_readiness": initial_readiness,
        "proof_missions": proof_missions,
    }


def _post_json(client: TestClient, path: str, payload: dict[str, Any]) -> Any:
    return client.post(path, json=payload)


def run_stage3_readiness_proof(
    *,
    actor: str = DEFAULT_ACTOR,
    confirm: bool = False,
    force: bool = False,
    deadletter_reason: str = DEFAULT_DEADLETTER_REASON,
) -> dict[str, Any]:
    """Exercise the Stage 3 mission readiness path through public API routes.

    This intentionally mutates the configured Francis data directory by creating
    bounded proof missions. The caller must opt in with ``confirm=True`` and the
    supplied actor must already have ``missions.write`` in
    ``FRANCIS_API_ACTOR_SCOPES``.
    """

    if not confirm:
        return {
            "ok": False,
            "error": "confirmation_required",
            "message": "Run with --confirm to create Stage 3 proof missions in the configured data directory.",
        }

    cleaned_actor = str(actor or "").strip() or DEFAULT_ACTOR
    cleaned_deadletter_reason = str(deadletter_reason or "").strip() or DEFAULT_DEADLETTER_REASON
    client = TestClient(create_app())
    initial_readiness = _readiness_from_briefing(client)
    if _is_ready(initial_readiness) and not force:
        return {
            "ok": True,
            "status": "already_ready",
            "message": "Stage 3 mission readiness is already satisfied for the configured data directory.",
            "readiness": initial_readiness,
            "proof_missions": {},
        }

    proof_missions: dict[str, str] = {}
    completed = _post_json(
        client,
        "/missions/create",
        {
            "objective": "Complete Stage 3 readiness proof mission",
            "summary": "Exercise tick, completion, history, memory, and reconstruction readiness.",
            "next_step": "Advance this proof mission through the governed mission runtime.",
            "requester_id": cleaned_actor,
            "actor": cleaned_actor,
            "meta": {"purpose": "stage3_readiness_proof"},
        },
    )
    completed_body = _response_body(completed)
    if completed.status_code != 200 or not completed_body.get("ok"):
        return _failed_result(
            stage="create_completed_mission",
            response=completed,
            initial_readiness=initial_readiness,
            proof_missions=proof_missions,
        )
    completed_id = str(completed_body.get("mission_id") or "").strip()
    proof_missions["completed"] = completed_id

    first_advance = _post_json(
        client,
        f"/missions/{completed_id}/advance",
        {"actor": cleaned_actor, "worker_id": cleaned_actor, "note": "stage3_readiness_proof_create_operation"},
    )
    first_body = _response_body(first_advance)
    if first_advance.status_code != 200 or not first_body.get("ok"):
        return _failed_result(
            stage="advance_create_operation",
            response=first_advance,
            initial_readiness=initial_readiness,
            proof_missions=proof_missions,
        )

    second_advance = _post_json(
        client,
        f"/missions/{completed_id}/advance",
        {"actor": cleaned_actor, "worker_id": cleaned_actor, "note": "stage3_readiness_proof_run_operation"},
    )
    second_body = _response_body(second_advance)
    if second_advance.status_code != 200 or not second_body.get("ok"):
        return _failed_result(
            stage="advance_run_operation",
            response=second_advance,
            initial_readiness=initial_readiness,
            proof_missions=proof_missions,
        )

    deadletter = _post_json(
        client,
        "/missions/create",
        {
            "objective": "Deadletter Stage 3 readiness proof mission",
            "summary": "Exercise clean deadletter evidence for Stage 3 readiness.",
            "next_step": "Deadletter this proof mission with an explicit review reason.",
            "requester_id": cleaned_actor,
            "actor": cleaned_actor,
            "meta": {"purpose": "stage3_readiness_proof"},
        },
    )
    deadletter_body = _response_body(deadletter)
    if deadletter.status_code != 200 or not deadletter_body.get("ok"):
        return _failed_result(
            stage="create_deadletter_mission",
            response=deadletter,
            initial_readiness=initial_readiness,
            proof_missions=proof_missions,
        )
    deadletter_id = str(deadletter_body.get("mission_id") or "").strip()
    proof_missions["deadlettered"] = deadletter_id

    reviewed_deadletter = _post_json(
        client,
        f"/missions/{deadletter_id}/deadletter",
        {
            "reason": cleaned_deadletter_reason,
            "actor": cleaned_actor,
            "note": "stage3_readiness_proof_deadletter_review",
        },
    )
    reviewed_body = _response_body(reviewed_deadletter)
    if reviewed_deadletter.status_code != 200 or not reviewed_body.get("ok"):
        return _failed_result(
            stage="deadletter_review",
            response=reviewed_deadletter,
            initial_readiness=initial_readiness,
            proof_missions=proof_missions,
        )

    final_readiness = _readiness_from_briefing(client)
    return {
        "ok": _is_ready(final_readiness),
        "status": final_readiness.get("status") or "unknown",
        "message": (
            "Stage 3 mission readiness proof satisfied all criteria."
            if _is_ready(final_readiness)
            else "Stage 3 mission readiness proof ran but criteria remain unresolved."
        ),
        "initial_readiness": initial_readiness,
        "readiness": final_readiness,
        "proof_missions": proof_missions,
    }
