from __future__ import annotations

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.api.mutation_authority_matrix import (
    MUTATING_METHODS,
    build_mutating_route_authority_matrix,
)


def _join_paths(prefix: str, path: str) -> str:
    if not prefix:
        return path
    if path == "/":
        return prefix
    return f"{prefix.rstrip('/')}/{path.lstrip('/')}"


def _iter_routes(routes: list[object], prefix: str = ""):
    for route in routes:
        original_router = getattr(route, "original_router", None)
        include_context = getattr(route, "include_context", None)
        if original_router is not None and include_context is not None:
            include_prefix = str(getattr(include_context, "prefix", "") or "")
            nested_prefix = _join_paths(prefix, include_prefix) if include_prefix else prefix
            yield from _iter_routes(getattr(original_router, "routes", []), nested_prefix)
            continue
        yield route


def _mutating_route_total() -> int:
    total = 0
    for route in _iter_routes(create_app().routes):
        if not isinstance(route, APIRoute):
            continue
        total += len([method for method in route.methods if method in MUTATING_METHODS])
    return total


def _entry_by_path(entries: list[dict[str, object]]) -> dict[str, dict[str, object]]:
    return {str(entry["path"]): entry for entry in entries}


def test_mutating_route_authority_matrix_covers_all_non_get_routes() -> None:
    matrix = build_mutating_route_authority_matrix(create_app().routes)

    assert matrix["ok"] is True
    assert matrix["status"] == "covered"
    assert matrix["missing"] == []
    assert matrix["missing_total"] == 0
    assert matrix["total"] == _mutating_route_total()
    assert matrix["summary"]["read_only_projection"] is True
    assert matrix["summary"]["write_behavior_changed"] is False

    required_fields = {
        "method",
        "path",
        "endpoint",
        "module",
        "family",
        "required_actor",
        "required_scope",
        "approval_requirement",
        "receipt_behavior",
        "denial_behavior",
        "governance_maturity",
    }
    for entry in matrix["entries"]:
        assert required_fields.issubset(entry)
        assert entry["method"] in MUTATING_METHODS
        for field in required_fields - {"method"}:
            assert str(entry[field]).strip()


def test_system_exposes_mutating_route_authority_matrix() -> None:
    client = TestClient(create_app())

    response = client.get("/system/mutating-route-authority-matrix")

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["kind"] == "francis.api.mutating_route_authority_matrix"
    assert body["total"] == _mutating_route_total()
    assert body["missing_total"] == 0

    entries = _entry_by_path(body["entries"])
    system_config = entries["/system/config/mutate"]
    assert system_config["family"] == "system"
    assert system_config["required_actor"] == "payload.actor"
    assert system_config["required_scope"] == "system.write"
    assert system_config["governance_maturity"] == "permission_gated"
    assert "permission_gate" in system_config["denial_behavior"]

    terminal = entries["/telemetry/terminal/events"]
    assert terminal["family"] == "telemetry_terminal"
    assert terminal["required_scope"] == "telemetry.terminal.write"
    assert terminal["governance_maturity"] == "permission_gated"

    feedback_memory = entries["/telemetry/context/feedback/memory-quality"]
    assert feedback_memory["family"] == "telemetry_context_feedback_memory_quality"
    assert feedback_memory["required_actor"] == "payload.actor"
    assert feedback_memory["required_scope"] == "memory.timeline.write"
    assert feedback_memory["governance_maturity"] == "permission_gated"
    assert "memory timeline" in feedback_memory["receipt_behavior"]
    assert "permission_gate" in feedback_memory["denial_behavior"]

    attachment = entries["/attachments/upload"]
    assert attachment["family"] == "attachments"
    assert attachment["required_actor"] == "multipart request_actor, actor, or api.attachments default"
    assert attachment["required_scope"] == "attachments.write"
    assert attachment["governance_maturity"] == "permission_gated"
    assert "permission_gate" in attachment["denial_behavior"]

    approval_request = entries["/approvals/request"]
    assert approval_request["family"] == "approval_request"
    assert approval_request["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert approval_request["required_scope"] == "approvals.request"
    assert approval_request["approval_requirement"] == (
        "creates pending approval after request-scope gate; does not decide it"
    )
    assert approval_request["governance_maturity"] == "permission_gated"
    assert "permission_gate" in approval_request["denial_behavior"]
    assert "lower authority than deciding" in approval_request["notes"]

    executor_closure = entries["/executor/substrate/stage-closure-decision"]
    assert executor_closure["family"] == "executor_substrate"
    assert executor_closure["required_actor"] == "payload.actor"
    assert executor_closure["required_scope"] == "executor.stage8.closure.write"
    assert executor_closure["governance_maturity"] == "permission_gated"
    assert "closure receipt" in executor_closure["denial_behavior"]
    assert "does not mutate runtime stage state" in executor_closure["notes"]

    takeover_control = entries["/takeover/control-transfer"]
    assert takeover_control["family"] == "takeover"
    assert takeover_control["required_actor"] == "payload.actor"
    assert takeover_control["required_scope"] == "takeover.control.write"
    assert takeover_control["governance_maturity"] == "permission_gated"
    assert "Stage 8 closure receipt" in takeover_control["approval_requirement"]
    assert "does not run tools" in takeover_control["notes"]

    takeover_panic = entries["/takeover/panic-stop"]
    assert takeover_panic["family"] == "takeover"
    assert takeover_panic["required_actor"] == "payload.actor"
    assert takeover_panic["required_scope"] == "takeover.panic.write"
    assert takeover_panic["governance_maturity"] == "permission_gated"
    assert "panic-stop receipt" in takeover_panic["receipt_behavior"]
    assert "control-transfer action-feed receipt" in takeover_panic["notes"]

    takeover_action = entries["/takeover/delegated-action"]
    assert takeover_action["family"] == "takeover"
    assert takeover_action["required_actor"] == "payload.actor"
    assert takeover_action["required_scope"] == "takeover.action.write"
    assert takeover_action["governance_maturity"] == "permission_gated"
    assert "control-transfer receipt" in takeover_action["approval_requirement"]
    assert "live-action receipt" in takeover_action["receipt_behavior"]
    assert "allowlisted executor operations" in takeover_action["notes"]

    takeover_closure = entries["/takeover/stage-closure-decision"]
    assert takeover_closure["family"] == "takeover"
    assert takeover_closure["required_actor"] == "payload.actor"
    assert takeover_closure["required_scope"] == "takeover.stage9.closure.write"
    assert takeover_closure["governance_maturity"] == "permission_gated"
    assert "completion review readiness" in takeover_closure["approval_requirement"]
    assert "stage closure decision receipt" in takeover_closure["receipt_behavior"]
    assert "does not mutate runtime stage state" in takeover_closure["notes"]

    takeover_handback = entries["/takeover/handback-summary"]
    assert takeover_handback["family"] == "takeover"
    assert takeover_handback["required_actor"] == "payload.actor"
    assert takeover_handback["required_scope"] == "takeover.handback.write"
    assert takeover_handback["governance_maturity"] == "permission_gated"
    assert "control-transfer receipt" in takeover_handback["approval_requirement"]
    assert "without executing work" in takeover_handback["notes"]

    away_progress = entries["/away/live-progress-sample"]
    assert away_progress["family"] == "away"
    assert away_progress["required_actor"] == "payload.actor"
    assert away_progress["required_scope"] == "away.progress.write"
    assert away_progress["governance_maturity"] == "permission_gated"
    assert "Stage 10 groundwork" in away_progress["approval_requirement"]
    assert "live-progress sample receipt" in away_progress["receipt_behavior"]
    assert "does not activate autonomy" in away_progress["notes"]

    apprenticeship_teaching = entries["/apprenticeship/teaching-session"]
    assert apprenticeship_teaching["family"] == "apprenticeship"
    assert apprenticeship_teaching["required_actor"] == "payload.actor"
    assert apprenticeship_teaching["required_scope"] == "apprenticeship.teaching_session.write"
    assert apprenticeship_teaching["governance_maturity"] == "permission_gated"
    assert "teaching-session receipt" in apprenticeship_teaching["receipt_behavior"]
    assert "permission_gate" in apprenticeship_teaching["denial_behavior"]
    assert "does not write memory" in apprenticeship_teaching["notes"]

    game_teaching_start = entries["/apprenticeship/game-teaching-session/start"]
    game_teaching_stop = entries["/apprenticeship/game-teaching-session/stop"]
    for game_teaching in (game_teaching_start, game_teaching_stop):
        assert game_teaching["family"] == "apprenticeship_game_teaching"
        assert game_teaching["required_actor"] == "payload.actor"
        assert game_teaching["required_scope"] == "apprenticeship.game_teaching_session.write"
        assert game_teaching["governance_maturity"] == "permission_gated_bounded_semantic_observation"
        assert "semantic episode receipt" in game_teaching["receipt_behavior"]
        assert "permission_gate" in game_teaching["denial_behavior"]
        assert "does not persist raw pixels" in game_teaching["notes"]
        assert "learn a policy" in game_teaching["notes"]

    game_episode_review = entries["/apprenticeship/game-teaching-episode/{episode_receipt_id}/review"]
    assert game_episode_review["family"] == "apprenticeship_game_episode_review"
    assert game_episode_review["required_actor"] == "payload.actor"
    assert game_episode_review["required_scope"] == "apprenticeship.game_teaching_episode_review.write"
    assert game_episode_review["governance_maturity"] == "permission_gated_semantic_replay_review"
    assert "source episode digest" in game_episode_review["receipt_behavior"]
    assert "permission_gate" in game_episode_review["denial_behavior"]
    assert "does not execute input" in game_episode_review["notes"]

    game_generalization = entries["/apprenticeship/game-teaching-episode/{episode_receipt_id}/generalization-proposal"]
    assert game_generalization["family"] == "apprenticeship_game_generalization"
    assert game_generalization["required_actor"] == "payload.actor"
    assert game_generalization["required_scope"] == "apprenticeship.game_teaching_generalization.write"
    assert game_generalization["governance_maturity"] == "permission_gated_generalization_proposal_only"
    assert "episode, review, and replay lineage" in game_generalization["receipt_behavior"]
    assert "permission_gate" in game_generalization["denial_behavior"]
    assert "does not infer player controls" in game_generalization["notes"]

    apprenticeship_replay = entries["/apprenticeship/replay-receipt"]
    assert apprenticeship_replay["family"] == "apprenticeship"
    assert apprenticeship_replay["required_actor"] == "payload.actor"
    assert apprenticeship_replay["required_scope"] == "apprenticeship.replay_receipt.write"
    assert apprenticeship_replay["governance_maturity"] == "permission_gated"
    assert "prior teaching-session receipt" in apprenticeship_replay["approval_requirement"]
    assert "replay/generalization review receipt" in apprenticeship_replay["receipt_behavior"]
    assert "permission_gate" in apprenticeship_replay["denial_behavior"]
    assert "does not execute replay" in apprenticeship_replay["notes"]

    apprenticeship_skillization = entries["/apprenticeship/skillization-artifact-receipt"]
    assert apprenticeship_skillization["family"] == "apprenticeship"
    assert apprenticeship_skillization["required_actor"] == "payload.actor"
    assert apprenticeship_skillization["required_scope"] == "apprenticeship.skillization_artifact.write"
    assert apprenticeship_skillization["governance_maturity"] == "permission_gated"
    assert "prior replay receipt" in apprenticeship_skillization["approval_requirement"]
    assert "skillization artifact review receipt" in apprenticeship_skillization["receipt_behavior"]
    assert "permission_gate" in apprenticeship_skillization["denial_behavior"]
    assert "does not write memory" in apprenticeship_skillization["notes"]

    apprenticeship_forge_handoff = entries["/apprenticeship/forge-handoff-receipt"]
    assert apprenticeship_forge_handoff["family"] == "apprenticeship"
    assert apprenticeship_forge_handoff["required_actor"] == "payload.actor"
    assert apprenticeship_forge_handoff["required_scope"] == "apprenticeship.forge_handoff.write"
    assert apprenticeship_forge_handoff["governance_maturity"] == "permission_gated"
    assert "prior skillization artifact receipt" in apprenticeship_forge_handoff["approval_requirement"]
    assert "Forge handoff review receipt" in apprenticeship_forge_handoff["receipt_behavior"]
    assert "permission_gate" in apprenticeship_forge_handoff["denial_behavior"]
    assert "does not write a Forge proposal" in apprenticeship_forge_handoff["notes"]

    apprenticeship_closure = entries["/apprenticeship/stage-closure-decision"]
    assert apprenticeship_closure["family"] == "apprenticeship"
    assert apprenticeship_closure["required_actor"] == "payload.actor"
    assert apprenticeship_closure["required_scope"] == "apprenticeship.stage11.closure.write"
    assert apprenticeship_closure["governance_maturity"] == "permission_gated"
    assert "completion review readiness" in apprenticeship_closure["approval_requirement"]
    assert "stage closure decision receipt" in apprenticeship_closure["receipt_behavior"]
    assert "permission_gate" in apprenticeship_closure["denial_behavior"]
    assert "does not mutate runtime stage state" in apprenticeship_closure["notes"]

    away_closure = entries["/away/stage-closure-decision"]
    assert away_closure["family"] == "away"
    assert away_closure["required_actor"] == "payload.actor"
    assert away_closure["required_scope"] == "away.stage10.closure.write"
    assert away_closure["governance_maturity"] == "permission_gated"
    assert "completion review readiness" in away_closure["approval_requirement"]
    assert "stage closure decision receipt" in away_closure["receipt_behavior"]
    assert "does not mutate runtime stage state" in away_closure["notes"]

    memory = entries["/memory/timeline/record"]
    assert memory["family"] == "memory_timeline"
    assert memory["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert memory["required_scope"] == "memory.timeline.write"
    assert memory["governance_maturity"] == "permission_gated"
    assert "permission_gate" in memory["denial_behavior"]

    explanation = entries["/explanations/record"]
    assert explanation["family"] == "explanation"
    assert explanation["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert explanation["required_scope"] == "explanation.write"
    assert explanation["governance_maturity"] == "permission_gated"
    assert "permission_gate" in explanation["denial_behavior"]

    web_learning = entries["/web_learning/request"]
    assert web_learning["family"] == "web_learning"
    assert web_learning["required_actor"] == "payload.request_actor, payload.api_actor, payload.actor, or api default"
    assert web_learning["required_scope"] == "web_learning.write"
    assert web_learning["governance_maturity"] == "permission_and_policy_gated"
    assert "permission_gate" in web_learning["denial_behavior"]

    federation = entries["/federation/instances/upsert"]
    assert federation["family"] == "federation"
    assert federation["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, or api.federation default"
    )
    assert federation["required_scope"] == "federation.write"
    assert federation["governance_maturity"] == "permission_gated"
    assert "permission_gate" in federation["denial_behavior"]

    federation_sleep_resume = entries["/federation/sleep-resume-confirmation"]
    assert federation_sleep_resume["family"] == "federation"
    assert federation_sleep_resume["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, or api.federation default"
    )
    assert federation_sleep_resume["required_scope"] == "federation.stage16.sleep_resume.confirmation.write"
    assert federation_sleep_resume["governance_maturity"] == "permission_gated"
    assert "confirmation receipt" in federation_sleep_resume["receipt_behavior"]
    assert "does not write evidence" in federation_sleep_resume["notes"]

    industrial = entries["/industrial/assets"]
    assert industrial["family"] == "industrial"
    assert industrial["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, payload.requested_by, or api.industrial default"
    )
    assert industrial["required_scope"] == "industrial.write"
    assert industrial["governance_maturity"] == "permission_and_policy_gated"
    assert "permission_gate" in industrial["denial_behavior"]
    assert "exact-action" in industrial["approval_requirement"]

    chat = entries["/chat/send"]
    assert chat["family"] == "chat"
    assert chat["required_actor"] == (
        "payload.request_actor, payload.api_actor, payload.actor, or api.chat default for generic chat; internal "
        "chat.send for /mission ingress"
    )
    assert chat["required_scope"] == "chat.write for generic chat; missions.write for /mission ingress"
    assert chat["governance_maturity"] == "permission_gated"
    assert "generic ledger write" in chat["denial_behavior"]
    assert "mission declaration authority" in chat["notes"]

    chatgpt_voice = entries["/chatgpt-voice/ingress"]
    assert chatgpt_voice["family"] == "chatgpt_voice_bridge"
    assert chatgpt_voice["required_actor"] == "payload.actor or chatgpt.voice default"
    assert "chatgpt.voice.bridge.write" in chatgpt_voice["required_scope"]
    assert "chat.write" in chatgpt_voice["required_scope"]
    assert chatgpt_voice["governance_maturity"] == "permission_gated"
    assert "transcript" in chatgpt_voice["approval_requirement"]
    assert "voice transcript ingress receipt" in chatgpt_voice["receipt_behavior"]
    assert "permission_gate" in chatgpt_voice["denial_behavior"]
    assert "no raw audio stream" in chatgpt_voice["notes"]

    chatgpt_voice_mcp_proof = entries["/chatgpt-voice/mcp-proof"]
    assert chatgpt_voice_mcp_proof["family"] == "chatgpt_voice_bridge"
    assert chatgpt_voice_mcp_proof["required_actor"] == "payload.actor or chatgpt.voice default"
    assert "chatgpt.voice.bridge.write" in chatgpt_voice_mcp_proof["required_scope"]
    assert "MCP proof route records connector evidence only" in chatgpt_voice_mcp_proof["approval_requirement"]
    assert "MCP connection proof receipt" in chatgpt_voice_mcp_proof["receipt_behavior"]
    assert "permission_gate" in chatgpt_voice_mcp_proof["denial_behavior"]
    assert "no execution or mutation authority" in chatgpt_voice_mcp_proof["notes"]

    ingest_acquire = entries["/ingest/acquire/start"]
    assert ingest_acquire["family"] == "ingest_acquire"
    assert ingest_acquire["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert ingest_acquire["required_scope"] == "ingest.acquire"
    assert ingest_acquire["governance_maturity"] == "permission_gated"
    assert "permission_gate" in ingest_acquire["denial_behavior"]

    ingest_forge = entries["/ingest/forge/synthesize"]
    assert ingest_forge["family"] == "ingest_forge"
    assert ingest_forge["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert ingest_forge["required_scope"] == "ingest.forge route-specific scope"
    assert ingest_forge["governance_maturity"] == "permission_gated"
    assert "does not promote capabilities" in ingest_forge["notes"]

    ingest_lab_run = entries["/ingest/lab/run"]
    assert ingest_lab_run["family"] == "ingest_lab"
    assert ingest_lab_run["required_scope"] == "ingest.lab.execute.run"
    assert ingest_lab_run["governance_maturity"] == "permission_and_policy_gated"
    assert "Lab execution" in ingest_lab_run["denial_behavior"]

    managed_copy = entries["/managed-copies/runtime-evidence-readback"]
    assert managed_copy["family"] == "managed_copies"
    assert managed_copy["required_actor"] == "payload.request_actor, payload.api_actor, or payload.actor"
    assert managed_copy["required_scope"] == "managed_copies route-specific write scope"
    assert managed_copy["governance_maturity"] == "permission_gated"
    assert "no-copy/no-delete" in managed_copy["notes"]

    safe_delta_export_preflight = entries["/managed-copies/safe-delta-export-preflight"]
    assert safe_delta_export_preflight["family"] == "managed_copies_safe_delta_export_preflight"
    assert safe_delta_export_preflight["required_scope"] == "managed_copies.safe_delta.export.preflight"
    assert safe_delta_export_preflight["governance_maturity"] == "permission_gated_dry_run_preflight"
    assert safe_delta_export_preflight["receipt_behavior"] == "none_dry_run_preflight_projection"
    assert "writes no receipt, artifact, manifest" in safe_delta_export_preflight["notes"]
    assert "grants no export, execution, or mutation authority" in safe_delta_export_preflight["notes"]

    export_request = entries["/managed-copies/safe-delta-export-authorization-request"]
    assert export_request["family"] == "managed_copies_safe_delta_export_authorization_request"
    assert export_request["required_scope"] == "managed_copies.safe_delta.export.authorization.request"
    assert export_request["receipt_behavior"] == "immutable pending export authorization-request receipt only"
    assert "Creates no approval, export, artifact" in export_request["notes"]

    export_decision = entries["/managed-copies/safe-delta-export-authorization-decision"]
    assert export_decision["family"] == "managed_copies_safe_delta_export_authorization_decision"
    assert export_decision["required_scope"] == "managed_copies.safe_delta.export.authorization.decide"
    assert "immutable approved or rejected" in export_decision["receipt_behavior"]

    artifact_plan = entries["/managed-copies/safe-delta-export-artifact-plan"]
    assert artifact_plan["family"] == "managed_copies_safe_delta_export_artifact_plan"
    assert artifact_plan["required_scope"] == "managed_copies.safe_delta.export.artifact.preflight"
    assert "writes no plan, receipt, artifact" in artifact_plan["receipt_behavior"]

    rogue_assessment = entries["/managed-copies/rogue-detection-assessment"]
    assert rogue_assessment["family"] == "managed_copies_rogue_detection_assessment"
    assert rogue_assessment["required_scope"] == "managed_copies.rogue_recovery.write"
    assert "Never declares rogue detection" in rogue_assessment["notes"]

    read_batch = entries["/operations/get_many"]
    assert read_batch["family"] == "operations_read_batch"
    assert read_batch["required_actor"] == "none"
    assert read_batch["required_scope"] == "none_read_only_batch_lookup"
    assert read_batch["receipt_behavior"] == "none_read_projection"
