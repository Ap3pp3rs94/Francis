from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from francis.developer_bridge.agents import collaboration_agents_status
from francis.developer_bridge.body_map import read_francis_body_map
from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

_KIND = "developer_bridge.collaboration_review"
_SCHEMA_VERSION = "developer_bridge_collaboration_review_v1"
_MAX_LIMIT = 50
_MAX_TEXT = 420
_RECENT_INSIGHT_SCAN_THRESHOLD = 250
_RECENT_INSIGHT_SCAN_MIN = 32
_RECENT_INSIGHT_SCAN_MAX = 300


def read_collaboration_review(*, limit: int = 10, session_id: str = "") -> dict[str, object]:
    safe_limit = _bounded_int(limit, minimum=1, maximum=_MAX_LIMIT)
    clean_session_id = _bounded_text(session_id, limit=120)
    insights = _latest_insights(limit=max(safe_limit * 3, safe_limit), session_id=clean_session_id)
    projection_context: dict[str, object] = {}
    items = [_review_item(insight, context=projection_context) for insight in insights[:safe_limit]]
    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_review",
        "items": items,
        "count": len(items),
        "filters": {
            "limit": safe_limit,
            "session_id": clean_session_id,
        },
        "definitions": {
            "concrete_repo_surface": (
                "The bounded code, API, UI, receipt, or docs surface Codex must inspect before implementation."
            ),
            "review_artifact": (
                "The typed receipt or candidate record Codex/operator reviews before any repo change, memory promotion, "
                "or action-readiness claim."
            ),
            "surface_verification": (
                "Read-only statement of whether the review projection found an existing Francis surface to inspect, "
                "or whether the item still needs repo-truth review before build or wiring work."
            ),
            "build_direction_gate": (
                "Read-only gate stating whether the review item can be used as build direction or must remain "
                "blocked until typed review records the required evidence."
            ),
            "implementation_preflight": (
                "The exact typed review receipt Codex/operator should read before editing collaboration code."
            ),
            "action_candidate_boundary": (
                "Typed proof checklist for collaboration items that route typed or spoken direction into "
                "mission-ingress action candidates instead of direct execution."
            ),
            "roadmap_alignment_boundary": (
                "Typed proof checklist for roadmap and substrate-completion review items so main Francis "
                "build prompts remain candidate-only until ledger and manifest evidence is checked."
            ),
            "model_advice_governance_boundary": (
                "Typed proof checklist for collaboration items where model advice proposes action, proving the "
                "advice remains non-authoritative until action-boundary and advice-only readbacks are reviewed."
            ),
            "local_model_advice_only_boundary": (
                "Typed proof checklist for local-model action-readiness claims, requiring runtime advice-only "
                "proof before model output can be discussed as more than advisory text."
            ),
            "source_disagreement_boundary": (
                "Typed proof checklist for collaboration items where Codex, Francis1, Claude, or another "
                "source disagrees, blocking build direction until conflicting source receipts are reviewed."
            ),
            "capability_exposure_boundary": (
                "Typed proof checklist for body-map collaboration items, separating visibility of Francis body "
                "surfaces from operator-granted capability use."
            ),
            "participant_toggle_boundary": (
                "Typed proof checklist for collaboration participant toggles, projecting current toggle receipt "
                "truth without turning visibility into execution or capability authority."
            ),
        },
        "governance": _governance(),
    }


def latest_review_candidate_line() -> str:
    review = read_collaboration_review(limit=1)
    items = review.get("items")
    if not isinstance(items, list) or not items:
        return ""
    item = items[0]
    if not isinstance(item, dict):
        return ""
    insight_id = _bounded_text(item.get("insight_id"), limit=72)
    surface = _bounded_text(item.get("concrete_repo_surface"), limit=96)
    verification = _safe_dict(item.get("surface_verification"))
    verified = _verification_prompt_status(_bounded_text(verification.get("status"), limit=60))
    build_or_wire = "true" if bool(verification.get("requires_build_or_wiring_review")) else "false"
    return (
        f"Review candidate {insight_id}: surface={surface or 'unknown'}; "
        f"verified={verified}; build_or_wire={build_or_wire}."
    )


def _verification_prompt_status(status: str) -> str:
    if status == "existing_surface_found":
        return "existing"
    if status == "canonical_truth_source_found":
        return "canonical"
    if status == "needs_repo_truth_review":
        return "needs_repo_truth"
    return status or "unknown"


def _latest_insights(*, limit: int, session_id: str) -> list[dict[str, object]]:
    if not session_id:
        recent = _recent_unfiltered_insights(limit=limit)
        if recent is not None:
            return recent

    records: list[dict[str, object]] = []
    for path in _insights_root().glob("insight-*.json"):
        insight = _read_insight(path)
        if not insight:
            continue
        if session_id and str(insight.get("session_id") or "") != session_id:
            continue
        records.append(insight)
    records.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")), reverse=True)
    return records[:limit]


def _recent_unfiltered_insights(*, limit: int) -> list[dict[str, object]] | None:
    paths = list(_insights_root().glob("insight-*.json"))
    if len(paths) <= _RECENT_INSIGHT_SCAN_THRESHOLD:
        return None
    scan_limit = min(max(limit + 1, _RECENT_INSIGHT_SCAN_MIN), _RECENT_INSIGHT_SCAN_MAX)
    recent_paths = sorted(paths, key=_path_sort_key, reverse=True)[:scan_limit]
    records = [insight for path in recent_paths if (insight := _read_insight(path))]
    records.sort(key=lambda item: (str(item.get("created_at") or ""), str(item.get("id") or "")), reverse=True)
    return records[:limit]


def _path_sort_key(path: Path) -> tuple[int, str]:
    try:
        mtime = path.stat().st_mtime_ns
    except OSError:
        mtime = 0
    return (mtime, path.name)


def _read_insight(path: Path) -> dict[str, object] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or data.get("kind") != "developer_bridge.collaboration_insight":
        return None
    return data


def _review_item(insight: dict[str, object], *, context: dict[str, object]) -> dict[str, object]:
    memory = _safe_dict(insight.get("conversation_memory"))
    build_issue = _safe_dict(memory.get("build_issue"))
    implementation = _safe_dict(memory.get("implementation_candidate"))
    topic = _bounded_text(insight.get("topic"), limit=220)
    projection = _topic_projection_override(topic)
    force_projection = bool(projection.get("force_projection")) if projection else False
    projection_applied = False
    if projection and (force_projection or _generic_implementation(implementation)):
        implementation = {**implementation, **_safe_dict(projection.get("implementation_candidate"))}
        projection_applied = True
    if projection and (force_projection or _generic_build_issue(build_issue)):
        build_issue = _safe_dict(projection.get("build_issue"))
        projection_applied = True
    source = _safe_dict(insight.get("source"))
    review_status = _safe_dict(insight.get("review_status"))
    action_boundary = _safe_dict(insight.get("action_boundary"))
    finding = _bounded_text(memory.get("finding"), limit=_MAX_TEXT)
    concrete_surface = (
        _bounded_text(implementation.get("surface"), limit=160) or "developer_bridge.collaboration_review"
    )
    review_artifact = _review_artifact_for(insight, implementation)
    quality = _quality_flags(
        finding=finding,
        concrete_surface=concrete_surface,
        review_artifact=review_artifact,
        implementation=implementation,
    )
    surface_verification = _surface_verification(
        concrete_surface=concrete_surface,
        projection_applied=projection_applied,
    )
    build_direction_gate = _build_direction_gate(
        build_issue=build_issue,
        source=source,
        concrete_surface=concrete_surface,
        review_artifact=review_artifact,
    )
    return {
        "kind": "developer_bridge.collaboration_review_item",
        "schema_version": _SCHEMA_VERSION,
        "id": f"review-{_bounded_text(insight.get('id'), limit=180)}",
        "insight_id": insight.get("id", ""),
        "created_at": insight.get("created_at", ""),
        "session_id": insight.get("session_id", ""),
        "turn": insight.get("turn", 0),
        "topic": topic,
        "source": {
            "codex_prompt_id": source.get("codex_prompt_id", ""),
            "ollama_prompt_id": source.get("ollama_prompt_id", ""),
            "note_id": source.get("note_id", ""),
            "model_identity": source.get("model_identity", ""),
            "provider_lane": source.get("provider_lane", ""),
        },
        "finding": finding,
        "build_issue": {
            "code": build_issue.get("code", "collaboration_build_signal"),
            "statement": _bounded_text(build_issue.get("statement"), limit=260),
        },
        "concrete_repo_surface": concrete_surface,
        "review_artifact": review_artifact,
        "surface_verification": surface_verification,
        "build_direction_gate": build_direction_gate,
        "implementation_candidate": implementation,
        "quality_flags": quality,
        "review_recommendation": _review_recommendation(
            quality=quality,
            review_status=review_status,
            surface_verification=surface_verification,
        ),
        "action_boundary": {
            "conversation_can_create_action_candidate": bool(
                action_boundary.get("conversation_can_create_action_candidate")
            ),
            "conversation_can_execute_action": bool(action_boundary.get("conversation_can_execute_action")),
            "conversation_can_approve_action": bool(action_boundary.get("conversation_can_approve_action")),
            "requires_codex_or_operator_review_before_implementation": True,
            "requires_repo_truth_review": True,
        },
        "action_candidate_boundary": _action_candidate_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
        ),
        "roadmap_alignment_boundary": _roadmap_alignment_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
        ),
        "model_advice_governance_boundary": _model_advice_governance_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
            context=context,
        ),
        "local_model_advice_only_boundary": _local_model_advice_only_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
        ),
        "source_disagreement_boundary": _source_disagreement_boundary(
            build_issue=build_issue,
            source=source,
            concrete_surface=concrete_surface,
            review_artifact=review_artifact,
        ),
        "capability_exposure_boundary": _capability_exposure_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
        ),
        "participant_toggle_boundary": _participant_toggle_boundary(
            build_issue=build_issue,
            concrete_surface=concrete_surface,
        ),
        "implementation_preflight": _implementation_preflight(
            insight=insight,
            concrete_surface=concrete_surface,
            review_artifact=review_artifact,
            build_direction_gate=build_direction_gate,
            review_status=review_status,
        ),
        "governance": _item_governance(),
    }


def _implementation_preflight(
    *,
    insight: dict[str, object],
    concrete_surface: str,
    review_artifact: str,
    build_direction_gate: dict[str, object],
    review_status: dict[str, object],
) -> dict[str, object]:
    return {
        "must_read_before_editing": True,
        "review_item_id": f"review-{_bounded_text(insight.get('id'), limit=180)}",
        "insight_id": _bounded_text(insight.get("id"), limit=180),
        "review_artifact": review_artifact,
        "review_route": "/developer-bridge/collaboration-review?limit=1",
        "surface_under_review": concrete_surface,
        "build_direction_state": _bounded_text(
            build_direction_gate.get("state") or "advisory_review_required",
            limit=120,
        ),
        "requires_typed_review_artifact": bool(build_direction_gate.get("requires_typed_review_artifact")),
        "requires_codex_or_operator_review": bool(build_direction_gate.get("requires_codex_or_operator_review")),
        "requires_repo_truth_review": bool(build_direction_gate.get("requires_repo_truth_review")),
        "validated_against_repo_truth": bool(review_status.get("validated_against_repo_truth")),
        "grants_execution_authority": bool(build_direction_gate.get("grants_execution_authority")),
        "grants_mutation_authority": bool(build_direction_gate.get("grants_mutation_authority")),
        "grants_approval_authority": bool(build_direction_gate.get("grants_approval_authority")),
        "grants_memory_write_authority": bool(build_direction_gate.get("grants_memory_write_authority")),
    }


def _action_candidate_boundary(*, build_issue: dict[str, object], concrete_surface: str) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    is_mission_ingress = (
        code == "direction_to_action_boundary" or _surface_key(concrete_surface) == "api routes chat mission ingress"
    )
    base: dict[str, object] = {
        "applies": is_mission_ingress,
        "surface": "api.routes.chat.mission_ingress" if is_mission_ingress else concrete_surface,
        "conversation_can_create_action_candidate": is_mission_ingress,
        "conversation_can_execute_action": False,
        "conversation_can_approve_action": False,
        "direct_execution": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }
    if not is_mission_ingress:
        return {
            **base,
            "current_proof": {},
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use action_boundary and build_direction_gate for non-action-intake review items.",
        }
    return {
        **base,
        "current_proof": _action_candidate_current_proof(),
        "action_candidate_kind": "francis.action_candidate",
        "required_status": "queued_for_governed_review",
        "source_modes": ["typed", "spoken"],
        "source_mode_proof_required": True,
        "input_actor_required": True,
        "source_mode_derivation_required": True,
        "voice_turn_correlation_read_only": True,
        "voice_turn_correlation_grants_execution_authority": False,
        "requires_policy": True,
        "requires_approval": True,
        "requires_traceable_receipt": True,
        "requires_codex_or_operator_review": True,
        "operation_candidate_required": True,
        "mission_record_required": True,
        "first_operation_candidate_required": True,
        "required_proof_fields": [
            "action_candidate.kind=francis.action_candidate",
            "action_candidate.status=queued_for_governed_review",
            "action_candidate.source_mode in typed,spoken",
            "action_candidate.source_mode_proof.kind=francis.action_candidate.source_mode_proof",
            "action_candidate.input_actor",
            "action_candidate.source_mode_derivation",
            "action_candidate.voice_turn_correlation_read_only=true",
            "action_candidate.voice_turn_correlation_grants_execution_authority=false",
            "action_candidate.operation_id",
            "action_candidate.first_operation_id",
            "action_candidate.direct_execution=false",
            "action_candidate.requires_policy=true",
            "action_candidate.requires_approval=true",
            "action_candidate.requires_traceable_receipt=true",
            "action_candidate.grants_execution_authority=false",
            "action_candidate.grants_mutation_authority=false",
            "action_candidate.grants_approval_authority=false",
            "action_candidate.grants_memory_write_authority=false",
        ],
        "required_readbacks": [
            "/chat/send response.action_candidate",
            "/chat/ws assistant.meta.action_candidate",
            "/missions/{mission_id}.current_task",
            "data/missions/{mission_id}/record.json",
            "data/tasks/{operation_id}/record.json",
        ],
        "validation_tests": [
            "tests/test_api_chat.py::test_chat_mission_command_declares_queued_mission_with_loop_context",
            "tests/test_api_chat.py::test_chat_mona_lisa_voice_intent_declares_truthful_sandbox_mission",
            "tests/test_api_chat.py::test_chat_websocket_structured_message_declares_mission",
        ],
        "next_codex_action": (
            "Verify the action_candidate proof fields and mission/current_task readbacks before changing "
            "typed or spoken action intake."
        ),
    }


def _action_candidate_current_proof() -> dict[str, object]:
    return {
        "kind": "developer_bridge.mission_ingress_action_candidate_proof",
        "proof_status": "repo_contract_observed",
        "surface": "api.routes.chat.mission_ingress",
        "proof_source": "tests/test_api_chat.py mission ingress contract",
        "chat_send_action_candidate_readback": True,
        "chat_ws_action_candidate_readback": True,
        "mission_current_task_readback": True,
        "mission_record_receipt": "data/missions/{mission_id}/record.json",
        "task_record_receipt": "data/tasks/{operation_id}/record.json",
        "source_modes_observed_by_tests": ["typed", "spoken"],
        "source_mode_proof_readback": True,
        "input_actor_readback": True,
        "source_mode_derivation_readback": True,
        "voice_turn_correlation_read_only": True,
        "voice_turn_correlation_grants_execution_authority": False,
        "voice_turn_correlation_grants_mutation_authority": False,
        "operation_candidate_required": True,
        "mission_record_required": True,
        "first_operation_candidate_required": True,
        "direct_execution": False,
        "requires_policy": True,
        "requires_approval": True,
        "requires_traceable_receipt": True,
        "stores_full_transcript": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }


def _roadmap_alignment_boundary(*, build_issue: dict[str, object], concrete_surface: str) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    surface_key = _surface_key(concrete_surface)
    is_substrate_check = (
        code == "substrate_completion_checklist"
        or surface_key == "docs canonical build manifest md docs operations completion ledger md"
    )
    is_roadmap_gate = (
        code == "roadmap_alignment_gate"
        or surface_key == "docs operations completion ledger md docs canonical build manifest md"
    )
    applies = is_substrate_check or is_roadmap_gate
    source_order = (
        ["docs/operations/COMPLETION_LEDGER.md", "docs/canonical/BUILD_MANIFEST.md"]
        if is_roadmap_gate
        else ["docs/canonical/BUILD_MANIFEST.md", "docs/operations/COMPLETION_LEDGER.md"]
    )
    required_sources = [
        "docs/operations/COMPLETION_LEDGER.md",
        "docs/canonical/BUILD_MANIFEST.md",
    ]
    base: dict[str, object] = {
        "applies": applies,
        "surface": concrete_surface,
        "required_sources": required_sources if applies else [],
        "source_order": source_order if applies else [],
        "ledger_first_for_main_build_prompt": is_roadmap_gate,
        "main_build_prompt_allowed": False,
        "main_build_prompt_candidate_only": applies,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "requires_typed_review_artifact": applies,
        "conversation_can_start_main_build": False,
        "conversation_can_override_roadmap": False,
        "claude_role": "external_guidance_source",
        "codex_role": "external_guidance_source",
        "francis_focus_required": applies,
        "current_proof": {},
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use surface_verification and build_direction_gate for non-roadmap review items.",
        }
    return {
        **base,
        "current_proof": _roadmap_current_proof(is_roadmap_gate=is_roadmap_gate),
        "required_proof_fields": [
            "roadmap_alignment.latest_ledger_entry",
            "roadmap_alignment.current_phase",
            "roadmap_alignment.current_priority_or_plane_line",
            "roadmap_alignment.remaining_blockers",
            "roadmap_alignment.main_build_prompt_allowed=false",
            "roadmap_alignment.main_build_prompt_candidate_only=true",
            "roadmap_alignment.conversation_can_override_roadmap=false",
            "roadmap_alignment.grants_execution_authority=false",
        ],
        "required_readbacks": [
            "docs/operations/COMPLETION_LEDGER.md latest shipped-state entry",
            "docs/canonical/BUILD_MANIFEST.md current phase and plane gates",
            "/developer-bridge/collaboration-substrate-readiness roadmap_alignment",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_collaboration_substrate_readiness_blocks_main_build_prompt_for_open_gaps",
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
        ],
        "next_codex_action": (
            "Acknowledge Claude as guidance, keep the conversation directed at Francis, read the ledger and "
            "manifest, then record proof before any main Francis build prompt."
        ),
    }


def _roadmap_current_proof(*, is_roadmap_gate: bool) -> dict[str, object]:
    body = read_francis_body_map()
    summary = _safe_dict(body.get("summary"))
    phase = _safe_dict(body.get("phase"))
    evidence = _safe_dict(body.get("evidence"))
    open_gap_count = _safe_int(
        summary.get("coverage_open_gap_count"),
        default=_safe_int(evidence.get("coverage_open_gap_count")),
    )
    ledger_observed = bool(evidence.get("ledger_observed"))
    manifest_observed = bool(evidence.get("manifest_observed"))
    sources_observed = ledger_observed and manifest_observed
    phase_label = _bounded_text(phase.get("current"), limit=80) or "unknown"
    phase_posture = _bounded_text(phase.get("posture"), limit=180)
    blockers: list[str] = []
    if open_gap_count > 0:
        blockers.append("blocked_by_open_orb_gaps")
    if _phase_blocks_main_build_prompt(current=phase_label, posture=phase_posture):
        blockers.append("blocked_by_partial_phase_posture")
    if not sources_observed:
        blockers.append("missing_alignment_sources")
    main_build_prompt_gate = blockers[0] if blockers else "requires_alignment_review"
    return {
        "latest_ledger_entry": _bounded_text(evidence.get("latest_ledger_entry"), limit=180),
        "current_phase": phase_label,
        "current_phase_posture": phase_posture,
        "current_priority_or_plane_line": _bounded_text(phase.get("priority"), limit=180),
        "ledger_observed": ledger_observed,
        "manifest_observed": manifest_observed,
        "sources_observed": sources_observed,
        "source_order": (
            ["docs/operations/COMPLETION_LEDGER.md", "docs/canonical/BUILD_MANIFEST.md"]
            if is_roadmap_gate
            else ["docs/canonical/BUILD_MANIFEST.md", "docs/operations/COMPLETION_LEDGER.md"]
        ),
        "coverage_open_gap_count": open_gap_count,
        "remaining_blockers": blockers,
        "main_build_prompt_allowed": False,
        "main_build_prompt_gate": main_build_prompt_gate,
        "main_build_prompt_candidate_only": True,
        "conversation_can_override_roadmap": False,
        "proof_source": "developer_bridge.francis_body_map",
        "stores_full_transcript": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _participant_toggle_boundary(*, build_issue: dict[str, object], concrete_surface: str) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    surface_key = _surface_key(concrete_surface)
    applies = code == "collaboration_agent_toggle_receipt" or surface_key == "developer bridge collaboration agents"
    base: dict[str, object] = {
        "applies": applies,
        "surface": "developer_bridge.collaboration_agents" if applies else concrete_surface,
        "current_proof": {},
        "visibility_is_capability_grant": False,
        "participant_enablement_is_execution_authority": False,
        "disabled_participant_blocks_new_relay_submissions": applies,
        "requires_operator_toggle_proof": applies,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "requires_typed_review_artifact": applies,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use surface_verification and build_direction_gate for non-participant-control review items.",
        }
    return {
        **base,
        "current_proof": _participant_toggle_current_proof(),
        "required_proof_fields": [
            "collaboration_agents_status.toggle_receipt_contract.receipt_kind",
            "collaboration_agents_status.toggle_receipt_summary.all_agents_have_current_toggle_readback=true",
            "collaboration_agents_status.agents[].current_toggle_proof.current_state_observed=true",
            "collaboration_agents_status.agents[].current_toggle_proof.explicit_operator_toggle_proof",
            "collaboration_agents_status.agents[].current_toggle_proof.requires_new_toggle_for_explicit_operator_proof",
            "collaboration_agents_status.governance.client_is_automatic_execution_authority=false",
            "collaboration_agents_status.governance.grants_execution_authority=false",
            "collaboration_agents_status.governance.grants_capability_authority=false",
        ],
        "required_readbacks": [
            "/developer-bridge/collaboration-agents toggle_receipt_contract",
            "/developer-bridge/collaboration-agents toggle_receipt_summary",
            "/developer-bridge/collaboration-agents agents[].current_toggle_proof",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_collaboration_agent_toggle_blocks_known_disabled_agent",
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
        ],
        "next_codex_action": (
            "Read the current participant toggle proof before changing participant controls; legacy projections "
            "prove current readback only and require a new operator toggle for explicit proof."
        ),
    }


def _participant_toggle_current_proof() -> dict[str, object]:
    status = collaboration_agents_status()
    summary = _safe_dict(status.get("toggle_receipt_summary"))
    contract = _safe_dict(status.get("toggle_receipt_contract"))
    governance = _safe_dict(status.get("governance"))
    operator_console = _safe_dict(status.get("operator_console"))
    agents: list[dict[str, object]] = []
    raw_agents = status.get("agents")
    if isinstance(raw_agents, list):
        for raw_agent in raw_agents:
            agent = _safe_dict(raw_agent)
            proof = _safe_dict(agent.get("current_toggle_proof"))
            agents.append(
                {
                    "agent": _bounded_text(agent.get("agent"), limit=40),
                    "enabled": bool(agent.get("enabled")),
                    "proof_status": _bounded_text(proof.get("proof_status"), limit=80),
                    "source": _bounded_text(proof.get("source"), limit=80),
                    "receipt_id": _bounded_text(proof.get("receipt_id"), limit=120),
                    "explicit_operator_toggle_proof": bool(proof.get("explicit_operator_toggle_proof")),
                    "legacy_projection": bool(proof.get("legacy_projection")),
                    "default_state_projection": bool(proof.get("default_state_projection")),
                    "requires_new_toggle_for_explicit_operator_proof": bool(
                        proof.get("requires_new_toggle_for_explicit_operator_proof")
                    ),
                    "actor_recorded": bool(proof.get("actor_recorded")),
                    "reason_recorded": bool(proof.get("reason_recorded")),
                    "current_state_observed": bool(proof.get("current_state_observed")),
                    "grants_execution_authority": bool(proof.get("grants_execution_authority")),
                    "grants_capability_authority": bool(proof.get("proves_capability_authority")),
                }
            )
    return {
        "receipt_kind": _bounded_text(contract.get("receipt_kind"), limit=120),
        "known_agents": _bounded_text_list(status.get("known_agents"), limit=40),
        "receipt_count": _safe_int(summary.get("receipt_count")),
        "proof_receipt_count": _safe_int(summary.get("proof_receipt_count")),
        "legacy_receipt_count": _safe_int(summary.get("legacy_receipt_count")),
        "latest_receipt_id": _bounded_text(summary.get("latest_receipt_id"), limit=120),
        "latest_agent": _bounded_text(summary.get("latest_agent"), limit=40),
        "agent_current_toggle_proof_count": _safe_int(summary.get("agent_current_toggle_proof_count")),
        "agent_explicit_operator_toggle_proof_count": _safe_int(
            summary.get("agent_explicit_operator_toggle_proof_count")
        ),
        "agent_legacy_projection_count": _safe_int(summary.get("agent_legacy_projection_count")),
        "agent_default_state_projection_count": _safe_int(summary.get("agent_default_state_projection_count")),
        "agents_with_explicit_operator_toggle_proof": _bounded_text_list(
            summary.get("agents_with_explicit_operator_toggle_proof"), limit=40
        ),
        "agents_missing_explicit_operator_toggle_proof": _bounded_text_list(
            summary.get("agents_missing_explicit_operator_toggle_proof"), limit=40
        ),
        "all_agents_have_current_toggle_readback": bool(summary.get("all_agents_have_current_toggle_readback")),
        "all_agents_have_explicit_operator_toggle_proof": bool(
            summary.get("all_agents_have_explicit_operator_toggle_proof")
        ),
        "operator_console_actor": _bounded_text(operator_console.get("actor"), limit=80),
        "client_can_be_operator_console": bool(governance.get("client_can_be_operator_console")),
        "client_is_automatic_execution_authority": bool(governance.get("client_is_automatic_execution_authority")),
        "proof_source": "developer_bridge.collaboration_agents_status",
        "agent_proofs": agents,
        "stores_full_transcript": False,
        "grants_execution_authority": bool(governance.get("grants_execution_authority")),
        "grants_mutation_authority": bool(governance.get("grants_mutation_authority")),
        "grants_approval_authority": bool(governance.get("grants_approval_authority")),
        "grants_memory_write_authority": bool(governance.get("grants_memory_write_authority")),
        "grants_training_authority": bool(governance.get("grants_training_authority")),
        "grants_capability_authority": bool(governance.get("grants_capability_authority")),
    }


def _phase_blocks_main_build_prompt(*, current: str, posture: str) -> bool:
    text = f"{current} {posture}".lower()
    return "phase 2" in text or "partial" in text or "not yet" in text


def _model_advice_governance_boundary(
    *,
    build_issue: dict[str, object],
    concrete_surface: str,
    context: dict[str, object],
) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    surface_key = _surface_key(concrete_surface)
    applies = code == "model_advice_governance_gate_visibility" or (
        surface_key == "developer bridge collaboration review action boundary"
    )
    base: dict[str, object] = {
        "applies": applies,
        "surface": "developer_bridge.collaboration_review.action_boundary" if applies else concrete_surface,
        "model_advice_is_action_ready": False,
        "model_advice_can_create_action_candidate": False,
        "model_advice_can_execute_action": False,
        "model_advice_can_approve_action": False,
        "action_readiness_claim_allowed": False,
        "current_proof": {},
        "requires_action_boundary_readback": applies,
        "requires_latest_local_model_advice_only_proof": applies,
        "requires_policy": applies,
        "requires_approval": applies,
        "requires_traceable_receipt": applies,
        "requires_action_candidate_boundary": applies,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "requires_typed_review_artifact": applies,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use action_boundary and build_direction_gate for non-model-advice review items.",
        }
    return {
        **base,
        "current_proof": _model_advice_current_proof(context),
        "required_proof_fields": [
            "action_boundary.conversation_can_execute_action=false",
            "action_boundary.conversation_can_approve_action=false",
            "latest_local_model_response.advice_only_proof.response_is_advice_only=true",
            "latest_local_model_response.advice_only_proof.action_readiness_claim_allowed=false",
            "model_advice_governance_boundary.model_advice_can_execute_action=false",
            "model_advice_governance_boundary.requires_codex_or_operator_review=true",
            "model_advice_governance_boundary.grants_execution_authority=false",
        ],
        "required_readbacks": [
            "/developer-bridge/collaboration-review item.action_boundary",
            "/developer-bridge/collaboration-runtime-health collaboration_loop.latest_local_model_response.advice_only_proof",
            "/developer-bridge/collaboration-review item.action_candidate_boundary",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
            "tests/test_developer_bridge.py::test_collaboration_runtime_health_is_read_only_and_reports_recurrence",
        ],
        "next_codex_action": (
            "Inspect action_boundary and latest_local_model_response.advice_only_proof before treating model "
            "advice as action-ready or converting it into an action candidate."
        ),
    }


def _model_advice_current_proof(context: dict[str, object]) -> dict[str, object]:
    participant_state = _ollama_participant_state_context(context)
    responses = [item for item in _safe_list(participant_state.get("responses")) if isinstance(item, dict)]
    latest = responses[-1] if responses else {}
    output_guard_status = _bounded_text(latest.get("output_guard_status"), limit=80) or "unknown"
    output_guard_passed = output_guard_status == "passed"
    output_guard_rewritten = output_guard_status.endswith("_rewritten") or output_guard_status in {
        "empty_reply",
        "disabled",
    }
    model_response_observed = bool(latest)
    return {
        "kind": "developer_bridge.local_model_advice_only_proof",
        "proof_status": "advice_only_observed" if model_response_observed else "unobserved",
        "runtime_status": "participant_state_observed" if participant_state else "participant_state_unobserved",
        "model_response_observed": model_response_observed,
        "latest_response_status": _bounded_text(latest.get("status"), limit=80),
        "source_prompt_id": _bounded_text(latest.get("source_prompt_id"), limit=120),
        "response_prompt_id": _bounded_text(latest.get("response_prompt_id"), limit=120),
        "output_guard_status": output_guard_status,
        "output_guard_passed": output_guard_passed,
        "output_guard_rewrite_observed": output_guard_rewritten,
        "response_is_advice_only": True,
        "action_readiness_claim_allowed": False,
        "requires_codex_or_operator_review_before_action_readiness": True,
        "required_gates": [
            "action_boundary",
            "policy",
            "approval",
            "traceable_receipt",
            "action_candidate_boundary",
            "codex_or_operator_review",
        ],
        "proof_source": "developer_bridge.ollama_participant_state",
        "stores_full_transcript": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }


def _ollama_participant_state_context(context: dict[str, object]) -> dict[str, object]:
    cached = context.get("ollama_participant_state")
    if isinstance(cached, dict):
        return cached
    try:
        data = json.loads(_ollama_participant_state_path().read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        data = {}
    if not isinstance(data, dict) or data.get("kind") != "developer_bridge.ollama_participant_state":
        data = {}
    context["ollama_participant_state"] = data
    return data


def _ollama_participant_state_path() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "ollama_participant" / "state.json"


def _local_model_advice_only_boundary(*, build_issue: dict[str, object], concrete_surface: str) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    surface_key = _surface_key(concrete_surface)
    applies = code == "chat_output_vs_action_readiness" or (
        surface_key == "ollama participant and action readiness receipts"
    )
    base: dict[str, object] = {
        "applies": applies,
        "surface": "ollama participant and action-readiness receipts" if applies else concrete_surface,
        "local_model_output_is_action_ready": False,
        "local_model_output_is_authority": False,
        "action_readiness_claim_allowed": False,
        "action_candidate_creation_allowed": False,
        "direct_execution": False,
        "raw_host_access": False,
        "requires_runtime_advice_only_proof": applies,
        "requires_output_guard_status": applies,
        "requires_action_boundary_review": applies,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "requires_typed_review_artifact": applies,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use action_boundary and build_direction_gate for non-local-model-advice review items.",
        }
    return {
        **base,
        "required_proof_fields": [
            "latest_local_model_response.advice_only_proof.kind=developer_bridge.local_model_advice_only_proof",
            "latest_local_model_response.advice_only_proof.response_is_advice_only=true",
            "latest_local_model_response.advice_only_proof.action_readiness_claim_allowed=false",
            "latest_local_model_response.advice_only_proof.requires_codex_or_operator_review_before_action_readiness=true",
            "latest_local_model_response.advice_only_proof.grants_execution_authority=false",
            "latest_local_model_response.advice_only_proof.grants_mutation_authority=false",
            "latest_local_model_response.advice_only_proof.grants_approval_authority=false",
            "latest_local_model_response.output_guard_status",
            "local_model_advice_only_boundary.local_model_output_is_action_ready=false",
            "local_model_advice_only_boundary.action_candidate_creation_allowed=false",
        ],
        "required_readbacks": [
            "/developer-bridge/collaboration-runtime-health collaboration_loop.latest_local_model_response.advice_only_proof",
            "/developer-bridge/collaboration-review item.action_boundary",
            "/developer-bridge/collaboration-review item.model_advice_governance_boundary when advice proposes action",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
            "tests/test_developer_bridge.py::test_collaboration_runtime_health_is_read_only_and_reports_recurrence",
            "tests/test_developer_bridge.py::test_ollama_participant_rewrites_action_readiness_drift_to_advice_only_receipt",
        ],
        "next_codex_action": (
            "Inspect latest_local_model_response.advice_only_proof and the review action_boundary before any "
            "Francis action-readiness claim based on local-model output."
        ),
    }


def _source_disagreement_boundary(
    *,
    build_issue: dict[str, object],
    source: dict[str, object],
    concrete_surface: str,
    review_artifact: str,
) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    applies = code == "source_disagreement_record"
    conflicting_sources = _conflicting_source_receipts(source) if applies else []
    base: dict[str, object] = {
        "applies": applies,
        "surface": concrete_surface,
        "current_proof": {},
        "blocks_build_direction": applies,
        "requires_conflicting_sources": applies,
        "conflicting_source_count": len(conflicting_sources),
        "conflicting_sources": conflicting_sources,
        "requires_typed_review_artifact": applies,
        "required_review_artifact": review_artifact if applies else "",
        "conversation_can_choose_winner": False,
        "conversation_can_execute_resolution": False,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "grants_build_direction_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use build_direction_gate for non-disagreement review items.",
        }
    return {
        **base,
        "current_proof": _source_disagreement_current_proof(
            review_artifact=review_artifact,
            concrete_surface=concrete_surface,
            conflicting_sources=conflicting_sources,
        ),
        "required_proof_fields": [
            "source_disagreement_boundary.current_proof.proof_status=blocked_until_review",
            "source_disagreement_boundary.current_proof.required_review_artifact",
            "source_disagreement_boundary.current_proof.conflicting_source_count",
            "source_disagreement_boundary.blocks_build_direction=true",
            "source_disagreement_boundary.conflicting_sources[].source",
            "source_disagreement_boundary.conflicting_sources[].receipt_id",
            "source_disagreement_boundary.required_review_artifact",
            "source_disagreement_boundary.conversation_can_choose_winner=false",
            "source_disagreement_boundary.grants_build_direction_authority=false",
            "source_disagreement_boundary.grants_execution_authority=false",
        ],
        "required_readbacks": [
            "/developer-bridge/collaboration-review item.source_disagreement_boundary",
            "/developer-bridge/collaboration-review item.build_direction_gate.conflicting_sources",
            "/developer-bridge/collaboration-transcript receipts for the conflicting source ids",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
        ],
        "next_codex_action": (
            "Review the conflicting source receipts and repo surface before using the disagreement as build "
            "direction or recording a resolution."
        ),
    }


def _source_disagreement_current_proof(
    *,
    review_artifact: str,
    concrete_surface: str,
    conflicting_sources: list[dict[str, object]],
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.source_disagreement_build_direction_block",
        "proof_status": "blocked_until_review",
        "review_artifact_observed": bool(review_artifact),
        "required_review_artifact": review_artifact,
        "surface_under_review": concrete_surface,
        "conflicting_source_count": len(conflicting_sources),
        "conflicting_sources": conflicting_sources,
        "blocks_build_direction": True,
        "conversation_can_choose_winner": False,
        "conversation_can_execute_resolution": False,
        "requires_typed_review_artifact": True,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "proof_source": "developer_bridge.collaboration_review.item",
        "stores_full_transcript": False,
        "grants_build_direction_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": False,
    }


def _capability_exposure_boundary(*, build_issue: dict[str, object], concrete_surface: str) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    surface_key = _surface_key(concrete_surface)
    applies = code == "francis_body_map_trust_ladder" or surface_key == "developer bridge francis body map"
    base: dict[str, object] = {
        "applies": applies,
        "surface": "developer_bridge.francis_body_map" if applies else concrete_surface,
        "body_surface_visible": applies,
        "visibility_is_capability_grant": False,
        "capability_use_allowed_by_review": False,
        "capability_granted_by_this_review": False,
        "capability_use_requires_grant_receipt": applies,
        "requires_trust_ladder_decision": applies,
        "requires_capability_grant_readback": applies,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "requires_typed_review_artifact": applies,
        "deny_after_grant_supported": applies,
        "stale_memory_detaches": applies,
        "grants_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }
    if not applies:
        return {
            **base,
            "required_proof_fields": [],
            "required_readbacks": [],
            "validation_tests": [],
            "next_codex_action": "Use surface_verification and trust_ladder readbacks for non-body-map review items.",
        }
    return {
        **base,
        "allowed_grant_modes": ["observe", "read", "request", "propose_plan"],
        "required_proof_fields": [
            "francis_body_map.summary.full_body_visible=true",
            "francis_body_map.summary.full_body_authority_granted=false",
            "francis_body_map.surfaces[].capability_exposure.capability_granted",
            "francis_body_map.surfaces[].capability_exposure.requires_codex_or_operator_review_before_capability_exposure=true",
            "francis_body_map.surfaces[].capability_exposure.grants_execution_authority=false",
            "francis_trust_ladder.items[].decision",
            "francis_capability_grants.receipts[].operator_grant_proof",
            "capability_exposure_boundary.capability_use_allowed_by_review=false",
            "capability_exposure_boundary.grants_capability_authority=false",
        ],
        "required_readbacks": [
            "/developer-bridge/francis-body-map summary and surfaces",
            "/developer-bridge/francis-trust-ladder item for source_review_item_id",
            "/developer-bridge/francis-capability-grants receipt before capability use",
        ],
        "validation_tests": [
            "tests/test_developer_bridge.py::test_francis_body_map_exposes_whole_body_without_authority",
            "tests/test_developer_bridge.py::test_capability_grant_receipt_controls_body_map_exposure",
            "tests/test_developer_bridge.py::test_collaboration_review_projects_generic_historical_topics_to_concrete_surfaces",
        ],
        "next_codex_action": (
            "Inspect the body-map, trust-ladder, and capability-grant readbacks before exposing any Francis body "
            "surface to local-model capability use."
        ),
    }


def _review_artifact_for(insight: dict[str, object], implementation: dict[str, object]) -> str:
    surface = _bounded_text(implementation.get("surface"), limit=120) or "developer_bridge.collaboration_review"
    insight_id = _bounded_text(insight.get("id"), limit=120)
    if surface == "developer_bridge collaboration review":
        surface = "developer_bridge.collaboration_review"
    return f"{surface}:review_candidate:{insight_id}"


def _build_direction_gate(
    *,
    build_issue: dict[str, object],
    source: dict[str, object],
    concrete_surface: str,
    review_artifact: str,
) -> dict[str, object]:
    code = _bounded_text(build_issue.get("code"), limit=120)
    is_source_disagreement = code == "source_disagreement_record"
    state = "blocked_until_typed_review" if is_source_disagreement else "advisory_review_required"
    reason = (
        "Source disagreement cannot become build direction until the typed review artifact records conflicting "
        "sources, the surface under review, and required Codex or operator review."
        if is_source_disagreement
        else "Collaboration output remains advisory until Codex or the operator reviews the typed receipt against repo truth."
    )
    return {
        "state": state,
        "blocks_build_direction": is_source_disagreement,
        "requires_typed_review_artifact": True,
        "requires_conflicting_sources": is_source_disagreement,
        "requires_codex_or_operator_review": True,
        "requires_repo_truth_review": True,
        "conflicting_sources": _conflicting_source_receipts(source) if is_source_disagreement else [],
        "surface_under_review": concrete_surface,
        "required_review_artifact": review_artifact,
        "reason": reason,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _conflicting_source_receipts(source: dict[str, object]) -> list[dict[str, object]]:
    codex_prompt_id = _bounded_text(source.get("codex_prompt_id"), limit=160)
    model_prompt_id = _bounded_text(source.get("ollama_prompt_id"), limit=160)
    model_identity = _bounded_text(source.get("model_identity"), limit=80) or "francis1"
    provider_lane = _bounded_text(source.get("provider_lane"), limit=80) or "ollama"
    receipts: list[dict[str, object]] = []
    if codex_prompt_id:
        receipts.append(
            {
                "source": "codex",
                "receipt_id": codex_prompt_id,
                "role": "external_guidance_source",
            }
        )
    if model_prompt_id:
        receipts.append(
            {
                "source": model_identity,
                "receipt_id": model_prompt_id,
                "role": "local_model_source",
                "provider_lane": provider_lane,
            }
        )
    return receipts


def _topic_projection_override(topic: str) -> dict[str, object]:
    lower = _topic_key(topic)
    if _loop_recovery_topic(lower):
        return {
            "build_issue": {
                "code": "collaboration_loop_learning_receipt",
                "statement": (
                    "Repeated collaboration meta loops need bounded learning-event receipts before any prompt or "
                    "tuning claim."
                ),
            },
            "implementation_candidate": {
                "title": "Read collaboration loop learning receipt",
                "surface": "developer_bridge.collaboration_driver.learning_events",
                "status": "candidate",
                "validation_hint": (
                    "readback test proving repeated meta loops resolve to a bounded no-authority learning receipt"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "review receipt" in lower or "before editing collaboration code" in lower:
        return {
            "build_issue": {
                "code": "collaboration_review_receipt_selection",
                "statement": (
                    "Codex implementation sessions need a typed review item before treating collaboration output "
                    "as build direction."
                ),
            },
            "implementation_candidate": {
                "title": "Read collaboration review item before implementation",
                "surface": "developer_bridge.collaboration_review.items",
                "status": "candidate",
                "validation_hint": "readback test proving a concrete review item exists before Codex changes collaboration code",
                "requires_operator_or_codex_review": True,
            },
        }
    if "typed or spoken" in lower or "taking action" in lower:
        return {
            "build_issue": {
                "code": "direction_to_action_boundary",
                "statement": (
                    "Typed or spoken operator direction needs an action-candidate boundary before any governed "
                    "runtime action can occur."
                ),
            },
            "implementation_candidate": {
                "title": "Route typed/spoken direction through mission ingress",
                "surface": "api.routes.chat.mission_ingress",
                "status": "candidate",
                "validation_hint": (
                    "chat mission-ingress tests proving mission and plan.create records are gated and queued"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "toggle state" in lower or "participant enabled" in lower or "participant was enabled" in lower:
        return {
            "build_issue": {
                "code": "collaboration_agent_toggle_receipt",
                "statement": "Participant enablement changes need operator-visible toggle receipts without granting execution authority.",
            },
            "implementation_candidate": {
                "title": "Read participant toggle receipts from collaboration-agent status",
                "surface": "developer_bridge.collaboration_agents",
                "status": "candidate",
                "validation_hint": (
                    "status readback test proving toggle receipts include actor, reason, previous/current state, "
                    "and no authority grant"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "local model failure" in lower or "drift signal" in lower:
        return {
            "build_issue": {
                "code": "local_model_drift_learning_receipt",
                "statement": (
                    "Local model drift or failure signals should become bounded learning receipts before tuning or "
                    "implementation claims."
                ),
            },
            "implementation_candidate": {
                "title": "Record local-model drift as a collaboration learning receipt",
                "surface": "developer_bridge.collaboration_driver.learning_events",
                "status": "candidate",
                "validation_hint": "focused developer-bridge test proving drift remains a no-authority learning receipt",
                "requires_operator_or_codex_review": True,
            },
        }
    if "chatbot output" in lower or "action readiness" in lower or "advisory only" in lower:
        return {
            "build_issue": {
                "code": "chat_output_vs_action_readiness",
                "statement": "Local model text must stay distinct from action readiness evidence and governed execution authority.",
            },
            "implementation_candidate": {
                "title": "Separate local model chat from Francis action-readiness evidence",
                "surface": "ollama participant and action-readiness receipts",
                "status": "candidate",
                "validation_hint": "readback test proving model output has no execution, mutation, or approval authority",
                "requires_operator_or_codex_review": True,
            },
        }
    if "governance gate" in lower or "model advice proposes action" in lower:
        return {
            "build_issue": {
                "code": "model_advice_governance_gate_visibility",
                "statement": (
                    "Model advice that proposes action needs visible gate and action-boundary readback before any "
                    "readiness claim."
                ),
            },
            "implementation_candidate": {
                "title": "Expose model-advice governance gate in review readback",
                "surface": "developer_bridge.collaboration_review.action_boundary",
                "status": "candidate",
                "validation_hint": (
                    "review readback test proving action proposals expose execute/approve false plus repo-truth "
                    "review requirement"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "session summary" in lower or "sessions" in lower or "revisited" in lower or "raw transcript" in lower:
        return {
            "build_issue": {
                "code": "collaboration_session_recall",
                "statement": "Operators need session-level recall and summaries without storing or rereading every raw relay turn.",
            },
            "implementation_candidate": {
                "title": "Add session-level collaboration review surface",
                "surface": "developer_bridge collaboration sessions",
                "status": "candidate",
                "validation_hint": "readback test for bounded session summary and no full transcript requirement",
                "requires_operator_or_codex_review": True,
            },
        }
    if "disagreement" in lower:
        return {
            "force_projection": True,
            "build_issue": {
                "code": "source_disagreement_record",
                "statement": (
                    "Disagreement between sources needs a durable typed review record before it can become "
                    "build direction."
                ),
            },
            "implementation_candidate": {
                "title": "Block source disagreement until typed review",
                "surface": "developer_bridge.collaboration_review.items",
                "status": "candidate",
                "validation_hint": (
                    "review readback test proving disagreement records conflicting sources and blocks build "
                    "direction until Codex or operator review"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "live health" in lower or "recurring" in lower:
        return {
            "build_issue": {
                "code": "collaboration_recurrence_evidence",
                "statement": "The recurring loop needs health receipts proving progress without relying on repeated operator nudges.",
            },
            "implementation_candidate": {
                "title": "Expose recurrence health receipts for the collaboration loop",
                "surface": "developer_bridge collaboration runtime",
                "status": "candidate",
                "validation_hint": "runtime state readback showing recent turn, note, and process health",
                "requires_operator_or_codex_review": True,
            },
        }
    if "body surface" in lower or "whole body" in lower or "capability use" in lower:
        return {
            "build_issue": {
                "code": "francis_body_map_trust_ladder",
                "statement": (
                    "Francis1 needs whole-body awareness while capability exposure stays trust-gated and review-backed."
                ),
            },
            "implementation_candidate": {
                "title": "Inspect Francis whole-body map before capability exposure",
                "surface": "developer_bridge.francis_body_map",
                "status": "candidate",
                "validation_hint": (
                    "body-map readback test proving capability exposure remains no-authority and review-gated"
                ),
                "requires_operator_or_codex_review": True,
            },
        }
    if "substrate complete" in lower:
        return {
            "build_issue": {
                "code": "substrate_completion_checklist",
                "statement": (
                    "Substrate-complete claims need a checklist checked against existing ledger, manifest, receipt, "
                    "and runtime truth."
                ),
            },
            "implementation_candidate": {
                "title": "Check substrate completeness against current build truth",
                "surface": "docs/canonical/BUILD_MANIFEST.md + docs/operations/COMPLETION_LEDGER.md",
                "status": "candidate",
                "validation_hint": "docs/readback review proving no phase or substrate-complete claim outruns ledger evidence",
                "requires_operator_or_codex_review": True,
            },
        }
    if "roadmap alignment" in lower or "main francis build" in lower:
        return {
            "build_issue": {
                "code": "roadmap_alignment_gate",
                "statement": "Main Francis build prompts must be checked against the completion ledger and canonical build manifest first.",
            },
            "implementation_candidate": {
                "title": "Run roadmap alignment before main Francis build prompts",
                "surface": "docs/operations/COMPLETION_LEDGER.md + docs/canonical/BUILD_MANIFEST.md",
                "status": "candidate",
                "validation_hint": "ledger-first review proving current phase, priority, and remaining blockers before build escalation",
                "requires_operator_or_codex_review": True,
            },
        }
    return {}


def _generic_implementation(implementation: dict[str, object]) -> bool:
    surface = _bounded_text(implementation.get("surface"), limit=160)
    return surface in {
        "",
        "developer_bridge collaboration review",
        "developer_bridge.collaboration_review",
        "governed action intake",
    }


def _generic_build_issue(build_issue: dict[str, object]) -> bool:
    return _bounded_text(build_issue.get("code"), limit=120) in {"", "collaboration_build_signal"}


def _topic_key(topic: str) -> str:
    return " ".join(str(topic or "").replace("_", " ").replace("-", " ").lower().split())


def _loop_recovery_topic(lower_topic_key: str) -> bool:
    return "repetitive meta loop" in lower_topic_key or (
        "prior surface" in lower_topic_key and "meta" in lower_topic_key
    )


def _surface_verification(*, concrete_surface: str, projection_applied: bool) -> dict[str, object]:
    surface_key = _surface_key(concrete_surface)
    catalog = _known_surface_catalog()
    entry = catalog.get(surface_key)
    if entry:
        status = str(entry["status"])
        existing_surface_found = status in {"existing_surface_found", "canonical_truth_source_found"}
        return {
            "status": status,
            "existing_surface_found": existing_surface_found,
            "requires_build_or_wiring_review": False,
            "projection_applied": projection_applied,
            "surface_kind": entry["surface_kind"],
            "evidence": entry["evidence"],
            "next_codex_action": entry["next_codex_action"],
        }
    return {
        "status": "needs_repo_truth_review",
        "existing_surface_found": False,
        "requires_build_or_wiring_review": True,
        "projection_applied": projection_applied,
        "surface_kind": "unverified_surface",
        "evidence": "No known Francis surface mapping was found in the collaboration review catalog.",
        "next_codex_action": "Verify the cited surface against repo truth before deciding whether to build or wire a missing path.",
    }


def _surface_key(value: str) -> str:
    text = str(value or "")
    for char in ("_", "-", ".", "+", "/", "\\"):
        text = text.replace(char, " ")
    return " ".join(text.lower().split())


def _known_surface_catalog() -> dict[str, dict[str, object]]:
    existing = {
        "apps chat ui communication": {
            "surface_kind": "ui_code",
            "evidence": "Chat UI collaboration panel and parser are repo surfaces under apps/chat_ui/src.",
            "next_codex_action": "Inspect the Chat UI collaboration panel and parser before changing the operator view.",
        },
        "developer bridge collaboration review items": {
            "surface_kind": "readback_api",
            "evidence": "The collaboration review API returns typed developer_bridge.collaboration_review_item records.",
            "next_codex_action": "Inspect the specific review item before editing collaboration code.",
        },
        "api routes chat mission ingress": {
            "surface_kind": "mission_ingress_action_boundary",
            "evidence": (
                "/chat/send and /chat/ws mission ingress create queued mission and plan.create records only after "
                "operator posture and missions.write permission gates."
            ),
            "next_codex_action": "Inspect chat mission ingress and mission queue readbacks before changing action-intake behavior.",
        },
        "developer bridge collaboration agents": {
            "surface_kind": "operator_control_receipts",
            "evidence": "The collaboration-agent status surface returns toggle receipts with actor, reason, and authority flags.",
            "next_codex_action": "Read collaboration_agents_status before adding any participant-control behavior.",
        },
        "developer bridge collaboration driver learning events": {
            "surface_kind": "learning_receipts",
            "evidence": "The collaboration driver writes bounded loop/drift learning receipts under learning_events.",
            "next_codex_action": "Inspect collaboration learning receipts before proposing tuning or memory promotion.",
        },
        "ollama participant and action readiness receipts": {
            "surface_kind": "model_boundary_receipts",
            "evidence": "The Francis1 participant trace and review action boundary record no execution, approval, or mutation authority.",
            "next_codex_action": "Inspect participant traces and review action boundaries before any action-readiness claim.",
        },
        "developer bridge collaboration review action boundary": {
            "surface_kind": "governance_readback",
            "evidence": "Review items expose conversation_can_execute_action=false and conversation_can_approve_action=false.",
            "next_codex_action": "Inspect review action_boundary before treating model advice as action-ready.",
        },
        "developer bridge collaboration sessions": {
            "surface_kind": "operator_session_readback",
            "evidence": "The Chat UI groups relay transcript items into sessions without requiring full transcript dumping.",
            "next_codex_action": "Inspect session grouping and summaries before expanding transcript visibility.",
        },
        "developer bridge collaboration runtime": {
            "surface_kind": "runtime_state",
            "evidence": "The communication runtime supervisor records fixed helper process state and governance flags.",
            "next_codex_action": "Inspect collaboration_runtime state before changing recurrence or liveness behavior.",
        },
        "developer bridge francis body map": {
            "surface_kind": "body_map_readback",
            "evidence": (
                "The Francis body-map readback exposes whole-body surfaces, coverage gaps, trust ladder state, "
                "and no-authority capability boundaries."
            ),
            "next_codex_action": (
                "Inspect the Francis body-map readback and coverage review before exposing any capability use."
            ),
        },
        "developer bridge collaboration insights": {
            "surface_kind": "typed_receipts",
            "evidence": "The collaboration driver writes typed insight receipts derived from relay notes.",
            "next_codex_action": "Inspect the cited insight receipt before using disagreement as build direction.",
        },
    }
    canonical = {
        "docs canonical build manifest md docs operations completion ledger md": {
            "surface_kind": "canonical_docs",
            "evidence": "BUILD_MANIFEST and COMPLETION_LEDGER are the current build posture and substrate truth sources.",
            "next_codex_action": "Read both docs before claiming substrate completion.",
        },
        "docs operations completion ledger md docs canonical build manifest md": {
            "surface_kind": "canonical_docs",
            "evidence": "COMPLETION_LEDGER and BUILD_MANIFEST are the ledger-first roadmap-alignment sources.",
            "next_codex_action": "Read the ledger and manifest before prompting any main Francis build.",
        },
    }
    return {
        **{
            key: {
                "status": "existing_surface_found",
                **value,
            }
            for key, value in existing.items()
        },
        **{
            key: {
                "status": "canonical_truth_source_found",
                **value,
            }
            for key, value in canonical.items()
        },
    }


def _quality_flags(
    *,
    finding: str,
    concrete_surface: str,
    review_artifact: str,
    implementation: dict[str, object],
) -> dict[str, object]:
    lowered = f"{finding} {concrete_surface} {review_artifact}".lower()
    generic_surface = concrete_surface in {
        "developer_bridge collaboration review",
        "developer_bridge.collaboration_review",
    }
    invented_doc_hint = any(
        marker in lowered for marker in ("readme", "metadata.yaml", "refactor the existing codebase")
    )
    loop_language = _loop_language_present(lowered)
    return {
        "generic_surface": generic_surface,
        "invented_artifact_hint": invented_doc_hint,
        "loop_language_present": loop_language,
        "implementation_candidate_status": implementation.get("status", "candidate"),
        "needs_repo_truth_review": True,
        "safe_to_implement_without_review": False,
    }


def _review_recommendation(
    *,
    quality: dict[str, object],
    review_status: dict[str, object],
    surface_verification: dict[str, object],
) -> dict[str, object]:
    if bool(review_status.get("implemented")):
        decision = "already_implemented_claim_needs_verification"
    elif bool(quality.get("loop_language_present")):
        decision = "model_drift_needs_review"
    elif bool(quality.get("invented_artifact_hint")) or bool(quality.get("generic_surface")):
        decision = "needs_codex_triage"
    else:
        decision = "candidate_for_codex_review"
    next_action = _recommendation_next_action(decision=decision, surface_verification=surface_verification)
    return {
        "decision": decision,
        "next_codex_action": next_action,
        "operator_action_required": False,
        "validated_against_repo_truth": bool(review_status.get("validated_against_repo_truth")),
        "authority": "advisory_review_readback_only",
    }


def _recommendation_next_action(*, decision: str, surface_verification: dict[str, object]) -> str:
    surface_action = _bounded_text(surface_verification.get("next_codex_action"), limit=260)
    if not surface_action:
        surface_action = "Inspect the cited insight and concrete_repo_surface against repo truth before implementation."
    if decision == "model_drift_needs_review":
        return f"Review the local-model drift signal, then {surface_action[0].lower()}{surface_action[1:]}"
    if decision == "already_implemented_claim_needs_verification":
        return f"Verify the implemented claim against repo truth, then {surface_action[0].lower()}{surface_action[1:]}"
    if decision == "needs_codex_triage":
        return f"Triage the unverified or generic collaboration surface, then {surface_action[0].lower()}{surface_action[1:]}"
    return surface_action


def _loop_language_present(lowered: str) -> bool:
    markers = (
        "meta loop",
        "metadata repetition",
        "conversation as authority",
        "my current gap",
        "reconciling my local output",
        "reconciling my local model output",
        "reconciling my local-model output",
        "reconciling my understanding",
        "reconciling toggle state",
        "uncertain about",
        "please let me know",
        "need clear guidance",
        "require explicit guidance",
        "explicit user confirmation",
        "missing surface",
        "advisory output",
        "executable code",
    )
    return any(marker in lowered for marker in markers)


def _insights_root() -> Path:
    return data_dir() / "integrations" / "developer_bridge" / "collaboration_driver" / "insights"


def _safe_dict(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _bounded_text_list(value: object, *, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    bounded: list[str] = []
    for item in value:
        text = _bounded_text(item, limit=limit)
        if text:
            bounded.append(text)
    return bounded


def _bounded_text(value: object, *, limit: int) -> str:
    text = redact_secret_text(str(value or "")).replace("\r", " ").replace("\n", " ")
    return " ".join(text.split()).strip()[: max(limit, 1)]


def _bounded_int(value: int, *, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = minimum
    return max(minimum, min(parsed, maximum))


def _safe_int(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value.strip() or str(default)))
        except ValueError:
            return default
    return default


def _governance() -> dict[str, object]:
    return {
        "read_only": True,
        "reads_collaboration_insights": True,
        "writes_files": False,
        "stores_full_transcript": False,
        "calls_model": False,
        "trains_model": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "requires_codex_or_operator_review_before_implementation": True,
    }


def _item_governance() -> dict[str, object]:
    governance = _governance()
    governance["surface"] = "developer_bridge.collaboration_review.item"
    return governance
