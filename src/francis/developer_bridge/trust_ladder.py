from __future__ import annotations

from typing import Any

from francis.developer_bridge.collaboration_review import read_collaboration_review
from francis.governance.redaction import redact_secret_text

_KIND = "developer_bridge.francis_trust_ladder"
_SCHEMA_VERSION = "developer_bridge_francis_trust_ladder_v1"
_MAX_LIMIT = 50

_DECISIONS = ("wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift")
_ACCESS_ORDER = ("observe", "read", "request", "propose_plan", "supervised_action", "approved_action")


def read_francis_trust_ladder(*, limit: int = 10, session_id: str = "") -> dict[str, object]:
    """Project Francis1 collaboration needs into trust-gated, no-authority decisions."""

    safe_limit = _bounded_int(limit, minimum=1, maximum=_MAX_LIMIT)
    clean_session_id = _bounded_text(session_id, limit=120)
    review = read_collaboration_review(limit=safe_limit, session_id=clean_session_id)
    raw_items = review.get("items")
    review_items = [item for item in raw_items if isinstance(item, dict)] if isinstance(raw_items, list) else []
    decisions = [_trust_request(item) for item in review_items[:safe_limit]]
    counts = {decision: 0 for decision in _DECISIONS}
    for item in decisions:
        decision = str(item.get("decision") or "")
        if decision in counts:
            counts[decision] += 1

    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.francis_trust_ladder",
        "items": decisions,
        "count": len(decisions),
        "summary": {
            "allowed_decisions": list(_DECISIONS),
            "decision_counts": counts,
            "request_count": len(decisions),
            "requests_with_existing_surface": sum(
                1
                for item in decisions
                if bool(_safe_dict(item.get("surface_verification")).get("existing_surface_found"))
            ),
            "requests_requiring_build_or_wiring_review": sum(
                1
                for item in decisions
                if bool(_safe_dict(item.get("surface_verification")).get("requires_build_or_wiring_review"))
            ),
            "requests_requiring_prompt_guard": counts["tune_prompt_guard"],
            "requests_rejected_as_drift": counts["reject_as_drift"],
            "grants_any_authority": False,
        },
        "filters": {
            "limit": safe_limit,
            "session_id": clean_session_id,
        },
        "definitions": {
            "wire_existing": (
                "A concrete Francis surface already exists; Codex may inspect and wire it only after typed review."
            ),
            "build_missing": (
                "The cited surface is not verified; Codex must verify repo truth and build only the smallest missing path."
            ),
            "tune_prompt_guard": (
                "The need is mostly model drift or repeated prompt failure; tune guardrails before treating it as build work."
            ),
            "reject_as_drift": (
                "The need is too generic, invented, conflicted, or unsafe to become build direction without a clearer receipt."
            ),
        },
        "governance": _governance(),
    }


def compact_trust_ladder_prompt_line() -> str:
    """Return the compact Francis1 trust-ladder contract line."""

    return _one_line("Trust: classify needs; no capability authority.")


def _trust_request(review_item: dict[str, object]) -> dict[str, object]:
    surface_verification = _safe_dict(review_item.get("surface_verification"))
    quality = _safe_dict(review_item.get("quality_flags"))
    recommendation = _safe_dict(review_item.get("review_recommendation"))
    build_gate = _safe_dict(review_item.get("build_direction_gate"))
    action_boundary = _safe_dict(review_item.get("action_boundary"))
    source = _safe_dict(review_item.get("source"))
    surface = _bounded_text(review_item.get("concrete_repo_surface"), limit=180)
    decision = _decision_for(
        surface_verification=surface_verification,
        quality=quality,
        recommendation=recommendation,
        build_gate=build_gate,
    )
    current_mode = _current_access_mode(surface=surface, surface_verification=surface_verification)
    requested_mode = _requested_access_mode(
        decision=decision,
        surface=surface,
        topic=_bounded_text(review_item.get("topic"), limit=260),
        finding=_bounded_text(review_item.get("finding"), limit=360),
    )
    return {
        "kind": "developer_bridge.francis_trust_ladder_request",
        "schema_version": _SCHEMA_VERSION,
        "id": f"trust-{_bounded_text(review_item.get('insight_id') or review_item.get('id'), limit=160)}",
        "source_review_item_id": _bounded_text(review_item.get("id"), limit=180),
        "insight_id": _bounded_text(review_item.get("insight_id"), limit=180),
        "created_at": review_item.get("created_at", ""),
        "session_id": _bounded_text(review_item.get("session_id"), limit=120),
        "turn": review_item.get("turn", 0),
        "topic": _bounded_text(review_item.get("topic"), limit=260),
        "source": {
            "model_identity": _bounded_text(source.get("model_identity"), limit=80),
            "provider_lane": _bounded_text(source.get("provider_lane"), limit=80),
            "codex_prompt_id": _bounded_text(source.get("codex_prompt_id"), limit=140),
            "model_prompt_id": _bounded_text(source.get("ollama_prompt_id"), limit=140),
        },
        "need_statement": _need_statement(review_item),
        "requested_surface": surface,
        "source_artifact": _bounded_text(review_item.get("review_artifact"), limit=220),
        "surface_verification": surface_verification,
        "quality_flags": quality,
        "decision": decision,
        "decision_reason": _decision_reason(
            decision=decision,
            surface_verification=surface_verification,
            quality=quality,
            recommendation=recommendation,
            build_gate=build_gate,
        ),
        "current_access_mode": current_mode,
        "requested_access_mode": requested_mode,
        "next_trust_gate": _next_trust_gate(decision=decision, requested_access_mode=requested_mode),
        "recommended_next_action": _recommended_next_action(
            decision=decision,
            surface_verification=surface_verification,
            recommendation=recommendation,
        ),
        "classification_path": [
            "developer_bridge.collaboration_review.items",
            "surface_verification",
            "quality_flags",
            "review_recommendation",
            "build_direction_gate",
        ],
        "build_direction_gate": build_gate,
        "action_boundary": {
            "conversation_can_create_action_candidate": bool(
                action_boundary.get("conversation_can_create_action_candidate")
            ),
            "conversation_can_execute_action": False,
            "conversation_can_approve_action": False,
            "requires_codex_or_operator_review_before_implementation": True,
            "requires_repo_truth_review": True,
        },
        "governance": _item_governance(),
    }


def _decision_for(
    *,
    surface_verification: dict[str, object],
    quality: dict[str, object],
    recommendation: dict[str, object],
    build_gate: dict[str, object],
) -> str:
    if bool(build_gate.get("blocks_build_direction")) or bool(quality.get("invented_artifact_hint")):
        return "reject_as_drift"
    if str(recommendation.get("decision") or "") == "model_drift_needs_review" or bool(
        quality.get("loop_language_present")
    ):
        return "tune_prompt_guard"
    if bool(quality.get("generic_surface")):
        return "reject_as_drift"
    if bool(surface_verification.get("existing_surface_found")) and not bool(
        surface_verification.get("requires_build_or_wiring_review")
    ):
        return "wire_existing"
    return "build_missing"


def _need_statement(review_item: dict[str, object]) -> str:
    build_issue = _safe_dict(review_item.get("build_issue"))
    statement = _bounded_text(build_issue.get("statement"), limit=300)
    if statement:
        return statement
    finding = _bounded_text(review_item.get("finding"), limit=300)
    if finding:
        return finding
    return _bounded_text(review_item.get("topic"), limit=300)


def _current_access_mode(*, surface: str, surface_verification: dict[str, object]) -> str:
    surface_key = _surface_key(surface)
    if not bool(surface_verification.get("existing_surface_found")):
        return "observe"
    if "mission ingress" in surface_key or "action" in surface_key:
        return "request"
    return "read"


def _requested_access_mode(*, decision: str, surface: str, topic: str, finding: str) -> str:
    lower = _surface_key(f"{surface} {topic} {finding}")
    if decision in {"tune_prompt_guard", "reject_as_drift"}:
        return "observe"
    if "execute" in lower or "supervised" in lower or "shell" in lower:
        return "supervised_action"
    if decision == "build_missing":
        return "propose_plan"
    if "action" in lower or "spoken" in lower or "typed" in lower:
        return "request"
    return "read"


def _next_trust_gate(*, decision: str, requested_access_mode: str) -> str:
    if decision == "tune_prompt_guard":
        return "prompt_guard_or_model_tuning_review_receipt"
    if decision == "reject_as_drift":
        return "clearer_typed_receipt_before_build_direction"
    if requested_access_mode in {"supervised_action", "approved_action"}:
        return "policy_receipt_operator_approval_and_supervised_exec_receipt"
    if decision == "build_missing":
        return "repo_truth_review_then_minimal_build_receipt"
    return "codex_or_operator_review_before_wiring"


def _recommended_next_action(
    *,
    decision: str,
    surface_verification: dict[str, object],
    recommendation: dict[str, object],
) -> str:
    next_action = _bounded_text(recommendation.get("next_codex_action"), limit=320)
    surface_action = _bounded_text(surface_verification.get("next_codex_action"), limit=320)
    if decision == "reject_as_drift":
        return (
            "Do not build from this receipt; request or wait for a clearer typed surface and conflicting-source review."
        )
    if decision == "tune_prompt_guard":
        return next_action or "Tune the prompt/output guard and record a learning receipt before build work."
    if decision == "build_missing":
        return surface_action or "Verify repo truth, then build the smallest missing path with a focused test."
    return next_action or surface_action or "Inspect and wire the existing surface after typed review."


def _decision_reason(
    *,
    decision: str,
    surface_verification: dict[str, object],
    quality: dict[str, object],
    recommendation: dict[str, object],
    build_gate: dict[str, object],
) -> str:
    if decision == "reject_as_drift":
        if bool(build_gate.get("blocks_build_direction")):
            return "Build direction is blocked until typed review resolves conflicting sources."
        if bool(quality.get("invented_artifact_hint")):
            return "The receipt hints at an invented or unsupported artifact."
        return "The receipt is too generic to become build direction."
    if decision == "tune_prompt_guard":
        return "The receipt matches model drift or loop language and needs guard/tuning review first."
    if decision == "wire_existing":
        surface_kind = _bounded_text(surface_verification.get("surface_kind"), limit=80)
        return f"Surface verification found an existing Francis {surface_kind or 'surface'}."
    if str(recommendation.get("decision") or "") == "needs_codex_triage":
        return "No existing Francis surface has been verified; repo-truth triage is required."
    return "The cited surface is not verified and may need a smallest-missing-path build."


def _surface_key(value: str) -> str:
    text = str(value or "")
    for char in ("_", "-", ".", "+", "/", "\\"):
        text = text.replace(char, " ")
    return " ".join(text.lower().split())


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _bounded_text(value: object, *, limit: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()[: max(limit, 1)]


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))


def _one_line(value: str, *, limit: int = 420) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _governance() -> dict[str, object]:
    return {
        "read_only": True,
        "surface": "developer_bridge.francis_trust_ladder",
        "reads_collaboration_review_items": True,
        "writes_files": False,
        "stores_full_transcript": False,
        "calls_model": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "requires_codex_or_operator_review_before_capability_exposure": True,
    }


def _item_governance() -> dict[str, object]:
    governance = _governance()
    governance["surface"] = "developer_bridge.francis_trust_ladder.item"
    return governance
