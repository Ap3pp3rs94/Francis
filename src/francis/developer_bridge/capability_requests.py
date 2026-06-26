from __future__ import annotations

from francis.governance.redaction import redact_secret_text

from .capability_grants import (
    active_capability_grant,
    allowed_capability_access_modes,
    known_capability_surfaces,
)
from .trust_ladder import read_francis_trust_ladder

_KIND = "developer_bridge.francis_capability_requests"
_SCHEMA_VERSION = "developer_bridge_francis_capability_requests_v1"
_MAX_LIMIT = 50
_REQUEST_STATES = (
    "pending_operator_decision",
    "already_granted",
    "granted_different_mode",
    "requires_repo_truth_review",
    "requires_supervised_action_review",
    "blocked_until_prompt_or_drift_review",
)
_LOW_RISK_MODES = set(allowed_capability_access_modes())
_ESCALATED_MODES = {"supervised_action", "approved_action", "delegated_toolbelt_use"}

_SURFACE_HINTS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "collaboration",
        (
            "collaboration",
            "communication ui",
            "relay",
            "transcript",
            "session",
            "developer bridge collaboration",
            "apps chat ui",
        ),
    ),
    (
        "memory",
        (
            "memory",
            "continuity",
            "ledger",
            "long term",
            "short term",
            "stale memory",
            "detached memory",
        ),
    ),
    (
        "governance",
        (
            "governance",
            "policy",
            "approval",
            "trust",
            "redaction",
        ),
    ),
    (
        "action_intake",
        (
            "action intake",
            "action candidate",
            "typed",
            "spoken",
            "user direction",
            "mission ingress",
            "src francis api routes chat",
            "missions",
        ),
    ),
    (
        "execution",
        (
            "execution",
            "supervised",
            "shell",
            "executor",
            "supervised exec",
            "run command",
            "scripts",
        ),
    ),
    (
        "orb_planes",
        (
            "orb plane",
            "plane model",
            "build manifest",
            "roadmap",
            "meta plane map",
        ),
    ),
    (
        "orb_lens_hud_shell",
        (
            "orb",
            "lens",
            "hud",
            "shell",
            "desktop",
            "overlay",
        ),
    ),
    (
        "mcp",
        (
            "mcp",
            "developer bridge mcp",
            "model context protocol",
            "connector",
        ),
    ),
    (
        "capability_economy",
        (
            "capability economy",
            "capability pack",
            "plugin",
            "stage 17",
        ),
    ),
    (
        "model_tuning",
        (
            "model tuning",
            "prompt guard",
            "learning event",
            "ollama",
            "francis1",
            "local model",
        ),
    ),
)


def read_francis_capability_requests(
    *,
    limit: int = 10,
    session_id: str = "",
    surface_id: str = "",
    state: str = "",
) -> dict[str, object]:
    """Read Francis1 capability access requests without granting authority."""

    safe_limit = _bounded_int(limit, minimum=1, maximum=_MAX_LIMIT)
    clean_session_id = _bounded_text(session_id, limit=120)
    clean_surface_id = _optional_surface_id(surface_id)
    clean_state = _optional_state(state)
    trust = read_francis_trust_ladder(limit=safe_limit, session_id=clean_session_id)
    raw_items = trust.get("items")
    trust_items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
    requests = [_request_item(item) for item in trust_items]
    if clean_surface_id:
        requests = [item for item in requests if item.get("body_surface_id") == clean_surface_id]
    if clean_state:
        requests = [item for item in requests if item.get("request_state") == clean_state]
    requests = requests[:safe_limit]
    grantable = [item for item in requests if bool(item.get("grantable_now"))]
    blocked = [item for item in requests if bool(item.get("blocked"))]
    already_granted = [
        item for item in requests if item.get("request_state") in {"already_granted", "granted_different_mode"}
    ]
    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.francis_capability_requests",
        "items": requests,
        "count": len(requests),
        "summary": {
            "request_count": len(requests),
            "grantable_now_count": len(grantable),
            "blocked_count": len(blocked),
            "already_granted_count": len(already_granted),
            "known_surface_count": sum(1 for item in requests if bool(item.get("known_body_surface"))),
            "unknown_surface_count": sum(1 for item in requests if not bool(item.get("known_body_surface"))),
            "requires_operator_review_count": sum(1 for item in requests if bool(item.get("requires_operator_review"))),
            "stop_conditions_visible": True,
            "can_revoke_after_grant": True,
            "grants_capability_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "filters": {
            "limit": safe_limit,
            "session_id": clean_session_id,
            "surface_id": clean_surface_id,
            "state": clean_state,
        },
        "definitions": {
            "capability_request": (
                "A trust-ladder need projected into a body-surface access request; it is not permission."
            ),
            "grantable_now": (
                "The request names a known low-risk surface and mode, but still needs Codex or operator review."
            ),
            "blocked": "The request must not be granted until drift, repo-truth, or supervised-action review is complete.",
            "stop_conditions": "Operator-visible conditions that should trigger deny/revoke or participant pause.",
        },
        "operator_controls": {
            "grant_or_deny_route": "/developer-bridge/francis-capability-grants",
            "participant_toggle_route": "/developer-bridge/collaboration-agents/toggle",
            "request_readback_route": "/developer-bridge/francis-capability-requests",
            "client_can_be_operator_console": True,
            "client_is_automatic_execution_authority": False,
            "deny_after_grant_supported": True,
            "revoke_after_grant_supported": True,
        },
        "governance": _governance(),
    }


def compact_capability_request_prompt_line() -> str:
    """Return the compact prompt contract for access requests."""

    return _one_line("Access: ask surface+mode; request readback; no self-grant.")


def _request_item(item: dict[str, object]) -> dict[str, object]:
    requested_surface = _bounded_text(item.get("requested_surface"), limit=180)
    topic = _bounded_text(item.get("topic"), limit=260)
    need = _bounded_text(item.get("need_statement"), limit=320)
    decision = _bounded_text(item.get("decision"), limit=80)
    requested_mode = _bounded_text(item.get("requested_access_mode"), limit=80) or "observe"
    body_surface_id = _body_surface_for(requested_surface=requested_surface, topic=topic, need=need)
    current_grant = active_capability_grant(body_surface_id) if body_surface_id else _unknown_grant_record()
    grantable_mode = _grantable_access_mode(requested_mode)
    request_state = _request_state(
        decision=decision,
        requested_mode=requested_mode,
        body_surface_id=body_surface_id,
        current_grant=current_grant,
        grantable_mode=grantable_mode,
    )
    blocked = request_state in {
        "requires_repo_truth_review",
        "requires_supervised_action_review",
        "blocked_until_prompt_or_drift_review",
    }
    grantable_now = request_state == "pending_operator_decision"
    source_review_item_id = _bounded_text(item.get("source_review_item_id"), limit=180)
    grant_template = {
        "surface_id": body_surface_id,
        "decision": "grant",
        "requested_access_mode": grantable_mode,
        "actor": "operator_or_codex_after_review",
        "reason": "bounded reason required before exposing this surface to Francis1 capability use",
        "source_review_item_id": source_review_item_id,
    }
    deny_template = {
        "surface_id": body_surface_id,
        "decision": "deny",
        "requested_access_mode": grantable_mode,
        "actor": "operator_or_codex_after_review",
        "reason": "deny or keep detached while drift, repo-truth, or trust review remains open",
        "source_review_item_id": source_review_item_id,
    }
    return {
        "kind": "developer_bridge.francis_capability_request",
        "schema_version": _SCHEMA_VERSION,
        "id": f"capability-request-{_bounded_text(item.get('insight_id') or item.get('id'), limit=140)}",
        "source_trust_ladder_item_id": _bounded_text(item.get("id"), limit=180),
        "source_review_item_id": source_review_item_id,
        "insight_id": _bounded_text(item.get("insight_id"), limit=180),
        "created_at": _bounded_text(item.get("created_at"), limit=80),
        "session_id": _bounded_text(item.get("session_id"), limit=120),
        "turn": _safe_int(item.get("turn"), default=0),
        "topic": topic,
        "need_statement": need,
        "requested_surface": requested_surface,
        "body_surface_id": body_surface_id,
        "known_body_surface": bool(body_surface_id),
        "decision": decision,
        "decision_reason": _bounded_text(item.get("decision_reason"), limit=260),
        "requested_access_mode": requested_mode,
        "grantable_access_mode": grantable_mode,
        "current_access_mode": _bounded_text(item.get("current_access_mode"), limit=80),
        "current_grant": {
            "grant_state": _bounded_text(current_grant.get("grant_state"), limit=40),
            "capability_granted": bool(current_grant.get("capability_granted")),
            "connected_to_local_model": bool(current_grant.get("connected_to_local_model")),
            "granted_access_mode": _bounded_text(current_grant.get("granted_access_mode"), limit=40),
            "deny_after_grant_supported": bool(current_grant.get("deny_after_grant_supported")),
            "can_deny_after_fact_for_tuning": bool(current_grant.get("can_deny_after_fact_for_tuning")),
        },
        "request_state": request_state,
        "grantable_now": grantable_now,
        "blocked": blocked,
        "requires_operator_review": True,
        "requires_codex_review": True,
        "requires_repo_truth_review": request_state == "requires_repo_truth_review",
        "requires_supervised_action_review": request_state == "requires_supervised_action_review",
        "next_trust_gate": _next_trust_gate(item=item, request_state=request_state),
        "recommended_next_action": _recommended_next_action(item=item, request_state=request_state),
        "stop_conditions": _stop_conditions(request_state=request_state, requested_mode=requested_mode),
        "grant_payload_template": grant_template,
        "deny_payload_template": deny_template,
        "review_readbacks": [
            "/developer-bridge/francis-trust-ladder",
            "/developer-bridge/francis-capability-grants",
            "/developer-bridge/francis-body-map",
        ],
        "governance": _item_governance(),
    }


def _body_surface_for(*, requested_surface: str, topic: str, need: str) -> str:
    haystack = _surface_key(f"{requested_surface} {topic} {need}")
    known = set(known_capability_surfaces())
    if requested_surface in known:
        return requested_surface
    for surface_id, hints in _SURFACE_HINTS:
        if surface_id in known and any(hint in haystack for hint in hints):
            return surface_id
    return ""


def _grantable_access_mode(requested_mode: str) -> str:
    clean = _surface_key(requested_mode).replace(" ", "_")
    if clean in _LOW_RISK_MODES:
        return clean
    if clean in _ESCALATED_MODES:
        return "request"
    return "observe"


def _request_state(
    *,
    decision: str,
    requested_mode: str,
    body_surface_id: str,
    current_grant: dict[str, object],
    grantable_mode: str,
) -> str:
    if decision in {"reject_as_drift", "tune_prompt_guard"}:
        return "blocked_until_prompt_or_drift_review"
    clean_mode = _surface_key(requested_mode).replace(" ", "_")
    if clean_mode in _ESCALATED_MODES:
        return "requires_supervised_action_review"
    if not body_surface_id or decision == "build_missing":
        return "requires_repo_truth_review"
    if bool(current_grant.get("capability_granted")):
        granted_mode = _bounded_text(current_grant.get("granted_access_mode"), limit=40)
        if granted_mode == grantable_mode:
            return "already_granted"
        return "granted_different_mode"
    return "pending_operator_decision"


def _next_trust_gate(*, item: dict[str, object], request_state: str) -> str:
    if request_state == "pending_operator_decision":
        return "operator_or_codex_capability_grant_decision_receipt"
    if request_state in {"already_granted", "granted_different_mode"}:
        return "continue_monitoring_and_revoke_if_drift_appears"
    if request_state == "requires_supervised_action_review":
        return "policy_receipt_operator_approval_and_supervised_exec_receipt"
    if request_state == "requires_repo_truth_review":
        return "repo_truth_review_then_minimal_build_or_wiring_receipt"
    next_gate = _bounded_text(item.get("next_trust_gate"), limit=180)
    return next_gate or "prompt_guard_or_drift_review_receipt"


def _recommended_next_action(*, item: dict[str, object], request_state: str) -> str:
    if request_state == "pending_operator_decision":
        return "Review the trust-ladder item, then grant or deny through /developer-bridge/francis-capability-grants."
    if request_state == "already_granted":
        return "Keep observing; revoke the grant if drift or unsafe capability assumptions appear."
    if request_state == "granted_different_mode":
        return "Review whether the current grant mode is enough before widening exposure."
    if request_state == "requires_supervised_action_review":
        return "Do not grant as capability context; route through policy, operator approval, and supervised execution."
    if request_state == "requires_repo_truth_review":
        return "Inspect repo truth before creating or wiring any missing surface."
    return _bounded_text(item.get("recommended_next_action"), limit=320) or (
        "Treat this as prompt or drift evidence before any capability decision."
    )


def _stop_conditions(*, request_state: str, requested_mode: str) -> list[str]:
    conditions = [
        "model claims grant, execution, approval, memory-write, or training authority from this request",
        "request conflicts with the trust-ladder decision or current grant receipt",
        "operator revokes or denies the surface after tuning review",
    ]
    if request_state == "requires_supervised_action_review" or requested_mode in _ESCALATED_MODES:
        conditions.append("request asks for supervised or approved action without policy and approval receipts")
    if request_state == "blocked_until_prompt_or_drift_review":
        conditions.append("request is based on drift, prompt-loop, or rejected review evidence")
    if request_state == "requires_repo_truth_review":
        conditions.append("requested surface is missing or unverified in repo truth")
    return conditions[:6]


def _unknown_grant_record() -> dict[str, object]:
    return {
        "grant_state": "unknown_surface",
        "capability_granted": False,
        "connected_to_local_model": False,
        "granted_access_mode": "observe",
        "deny_after_grant_supported": True,
        "can_deny_after_fact_for_tuning": True,
    }


def _optional_surface_id(value: str) -> str:
    text = _surface_key(value).replace(" ", "_")
    if not text:
        return ""
    return text if text in set(known_capability_surfaces()) else ""


def _optional_state(value: str) -> str:
    text = _surface_key(value).replace(" ", "_")
    if not text:
        return ""
    return text if text in _REQUEST_STATES else ""


def _surface_key(value: object) -> str:
    text = str(value or "")
    for char in ("_", "-", ".", "+", "/", "\\"):
        text = text.replace(char, " ")
    return " ".join(text.lower().split())


def _bounded_text(value: object, *, limit: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()[: max(limit, 1)]


def _bounded_int(value: object, *, minimum: int, maximum: int) -> int:
    parsed = _safe_int(value, default=minimum)
    return max(minimum, min(parsed, maximum))


def _safe_int(value: object, *, default: int) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _one_line(value: str, *, limit: int = 220) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _governance() -> dict[str, object]:
    return {
        "read_only": True,
        "surface": "developer_bridge.francis_capability_requests",
        "derived_from": "developer_bridge.francis_trust_ladder",
        "reads_capability_grant_state": True,
        "writes_capability_grant_state": False,
        "writes_files": False,
        "writes_receipts": False,
        "stores_full_transcript": False,
        "calls_model": False,
        "trains_model": False,
        "client_can_be_operator_console": True,
        "client_is_automatic_execution_authority": False,
        "requires_operator_review_before_grant": True,
        "grants_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _item_governance() -> dict[str, object]:
    governance = _governance()
    governance["surface"] = "developer_bridge.francis_capability_requests.item"
    return governance
