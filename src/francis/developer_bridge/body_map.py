from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

from francis.developer_bridge.capability_grants import read_francis_capability_grants
from francis.kernel.paths import data_dir, repo_root

_SCHEMA_VERSION = "developer_bridge_francis_body_map_v1"
_QUEST_ID = "francis1-whole-body-awareness-and-trust-gated-capability-v1"
_MAX_LINE_CHARS = 420


def read_francis_body_map() -> dict[str, object]:
    """Read the current Francis body map without granting any capability authority."""

    root = repo_root()
    capability_grants = read_francis_capability_grants()
    raw_grant_items = capability_grants.get("items")
    grant_items = [
        _dict(item)
        for item in (raw_grant_items if isinstance(raw_grant_items, list) else [])
        if isinstance(item, dict) and _safe_str(item.get("surface_id"))
    ]
    grant_by_surface = {_safe_str(item.get("surface_id")): item for item in grant_items}
    surfaces = _body_surfaces(root, grant_by_surface=grant_by_surface)
    trust_ladder_connected = _trust_ladder_connected(root)
    runtime_observation = _runtime_restart_observation()
    runtime_observed = bool(runtime_observation.get("observed"))
    coverage_review = _body_coverage_review(root)
    coverage_review_observed = bool(coverage_review.get("observed"))
    quest_steps = _quest_steps(
        trust_ladder_connected=trust_ladder_connected,
        runtime_restart_observed=runtime_observed,
        coverage_review_observed=coverage_review_observed,
    )
    completed = sum(1 for step in quest_steps if step["status"] == "completed")
    total = len(quest_steps)
    percent = int((completed / total) * 100) if total else 0
    connected = sum(1 for surface in surfaces if str(surface["connection_state"]).startswith("connected"))
    candidate = sum(1 for surface in surfaces if surface["connection_state"] == "candidate")
    blocked = sum(1 for surface in surfaces if surface["connection_state"] == "blocked")
    unknown = sum(1 for surface in surfaces if surface["connection_state"] == "unknown")
    exposure_summary = _body_exposure_summary(surfaces)
    information_safety = _body_information_safety(surfaces)

    return {
        "kind": "developer_bridge.francis_body_map",
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.francis_body_map",
        "generated_at": datetime.now(UTC).isoformat(),
        "identity": {
            "local_identity": "francis1",
            "provider_lane": "ollama",
            "provider_name_is_identity": False,
            "codex_role": "external_guidance_and_implementation_toolbelt",
            "claude_role": "external_guidance_source",
            "francis_role": "governed_local_first_operating_layer",
        },
        "phase": {
            "current": "Phase 2",
            "source": "docs/canonical/BUILD_MANIFEST.md",
            "posture": "partial ORB runtime with governed runtime spine stronger than product surface",
            "priority": "whole-body awareness before capability exposure",
        },
        "access_ladder": [
            "observe",
            "read",
            "request",
            "propose_plan",
            "supervised_action",
            "approved_action",
            "delegated_toolbelt_use",
        ],
        "surfaces": surfaces,
        "summary": {
            "surface_count": len(surfaces),
            "connected_or_partial_count": connected,
            "candidate_count": candidate,
            "blocked_count": blocked,
            "unknown_count": unknown,
            "default_access_mode": "observe",
            "full_body_visible": True,
            "full_body_authority_granted": False,
            "visible_surface_count": exposure_summary.get("visible_surface_count", 0),
            "connected_to_local_model_count": exposure_summary.get("connected_to_local_model_count", 0),
            "capability_granted_count": exposure_summary.get("capability_granted_count", 0),
            "not_exposed_surface_count": exposure_summary.get("not_exposed_surface_count", 0),
            "review_required_surface_count": exposure_summary.get("review_required_surface_count", 0),
            "information_safety_validated": information_safety.get("validated_readback", False),
            "sensitive_surface_count": information_safety.get("sensitive_surface_count", 0),
            "absolute_evidence_path_count": information_safety.get("absolute_evidence_path_count", 0),
            "active_capability_grant_count": _safe_int(_dict(capability_grants.get("summary")).get("granted_count")),
            "denied_or_revoked_capability_count": _safe_int(
                _dict(capability_grants.get("summary")).get("denied_or_revoked_count")
            ),
            "trust_ladder_enforced": trust_ladder_connected,
            "runtime_restart_observed": runtime_observed,
            "coverage_reviewed": coverage_review_observed,
            "canonical_plane_count": coverage_review.get("plane_count", 0),
            "canonical_plane_covered_count": coverage_review.get("covered_plane_count", 0),
            "coverage_open_gap_count": coverage_review.get("open_gap_count", 0),
        },
        "quest": {
            "id": _QUEST_ID,
            "title": "Wire Francis1 whole-body awareness with trust-gated capability exposure",
            "estimated_timeline": "one bounded work session for body-map wiring; additional sessions for trusted capability exposure",
            "single_timeline": [
                {
                    "order": 1,
                    "label": "Body map readback",
                    "target_duration": "30-45 minutes",
                    "expected_status_after_this_slice": "completed",
                },
                {
                    "order": 2,
                    "label": "Francis1 prompt binding",
                    "target_duration": "15-30 minutes",
                    "expected_status_after_this_slice": "completed",
                },
                {
                    "order": 3,
                    "label": "Operator UI visibility",
                    "target_duration": "30-45 minutes",
                    "expected_status_after_this_slice": "completed",
                },
                {
                    "order": 4,
                    "label": "Restart conversation and observe drift",
                    "target_duration": "15-30 minutes",
                    "expected_status_after_this_slice": "completed" if runtime_observed else "pending",
                },
                {
                    "order": 5,
                    "label": "Trust ladder enforcement for capability requests",
                    "target_duration": "1-2 sessions",
                    "expected_status_after_this_slice": "completed" if trust_ladder_connected else "pending",
                },
                {
                    "order": 6,
                    "label": "Full body coverage review",
                    "target_duration": "30-45 minutes",
                    "expected_status_after_this_slice": "completed" if coverage_review_observed else "pending",
                },
            ],
            "steps": quest_steps,
            "completed_steps": completed,
            "total_steps": total,
            "percent_complete": percent,
            "percent_baseline": "completed quest steps divided by declared bounded wiring steps",
            "remaining": _quest_remaining(quest_steps),
        },
        "definitions": {
            "body_surface": "A known Francis subsystem Francis1 may be aware of without receiving authority to use it.",
            "access_mode": "The highest declared interaction mode this readback exposes to Francis1 today.",
            "connection_state": "Whether the surface is wired to this collaboration readback, partially connected elsewhere, candidate-only, blocked, or unknown.",
            "capability_exposure": "A per-surface verdict separating Francis1 visibility from permission to use that capability.",
            "exposure_summary": "A compact readback of which visible body surfaces are exposed to Francis1 capability use and which still require review.",
            "information_safety": "A metadata-only proof of what the body map exposes and what it refuses to expose.",
            "coverage_review": "A read-only map from canonical ORB planes to known Francis surfaces; it is not capability completion.",
        },
        "exposure_summary": exposure_summary,
        "information_safety": information_safety,
        "evidence": {
            "manifest_observed": _exists(root / "docs" / "canonical" / "BUILD_MANIFEST.md"),
            "ledger_observed": _exists(root / "docs" / "operations" / "COMPLETION_LEDGER.md"),
            "trust_ladder_observed": trust_ladder_connected,
            "runtime_restart_observed": runtime_observed,
            "body_coverage_review_observed": coverage_review_observed,
            "canonical_plane_count": coverage_review.get("plane_count", 0),
            "canonical_plane_covered_count": coverage_review.get("covered_plane_count", 0),
            "missing_canonical_plane_ids": coverage_review.get("missing_plane_ids", []),
            "coverage_open_gap_count": coverage_review.get("open_gap_count", 0),
            "latest_runtime_prompt_id": _safe_str(runtime_observation.get("prompt_id")),
            "latest_runtime_response_id": _safe_str(runtime_observation.get("response_id")),
            "latest_ledger_entry": _latest_ledger_entry(root),
        },
        "coverage_review": coverage_review,
        "runtime_observation": runtime_observation,
        "capability_grants": {
            "surface": "developer_bridge.francis_capability_grants",
            "route": "/developer-bridge/francis-capability-grants",
            "connected": True,
            "active_grants_present": bool(_dict(capability_grants.get("summary")).get("active_grants_present")),
            "granted_count": _safe_int(_dict(capability_grants.get("summary")).get("granted_count")),
            "denied_or_revoked_count": _safe_int(
                _dict(capability_grants.get("summary")).get("denied_or_revoked_count")
            ),
            "deny_after_grant_supported": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "trust_ladder": {
            "surface": "developer_bridge.francis_trust_ladder",
            "route": "/developer-bridge/francis-trust-ladder",
            "mcp_tool": "francis_trust_ladder_tool",
            "connected": trust_ladder_connected,
            "decision_contract": ["wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift"],
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "governance": _governance(),
    }


def compact_body_map_prompt_line() -> str:
    """Return a bounded prompt line for Francis1 collaboration turns."""

    body = read_francis_body_map()
    exposure = _dict(body.get("exposure_summary"))
    visible = _safe_int(exposure.get("visible_surface_count"))
    exposed = _safe_int(exposure.get("connected_to_local_model_count"))
    not_exposed = _safe_int(exposure.get("not_exposed_surface_count"))
    return _one_line(
        f"Body map: {visible} visible; {exposed} exposed; {not_exposed} not exposed; "
        "capability use requires grant receipt; stale memory detaches."
    )


def compact_roadmap_gate_prompt_line() -> str:
    """Return the current ledger-first main-build gate as a bounded prompt line."""

    body = read_francis_body_map()
    summary = _dict(body.get("summary"))
    phase = _dict(body.get("phase"))
    evidence = _dict(body.get("evidence"))
    open_gaps = _safe_int(
        summary.get("coverage_open_gap_count"), default=_safe_int(evidence.get("coverage_open_gap_count"))
    )
    phase_label = _safe_str(phase.get("current")) or "unknown"
    sources_observed = bool(evidence.get("ledger_observed")) and bool(evidence.get("manifest_observed"))
    if open_gaps > 0:
        gate = "blocked_by_open_orb_gaps"
    elif _phase_blocks_main_build_prompt(current=phase_label, posture=_safe_str(phase.get("posture"))):
        gate = "blocked_by_partial_phase_posture"
    elif not sources_observed:
        gate = "missing_alignment_sources"
    else:
        gate = "review_required"
    main_build = "candidate-only" if gate != "review_required" else "review-required"
    return _one_line(f"Roadmap: ledger first; main-build {main_build}; {gate}.")


def _body_surfaces(root: Path, *, grant_by_surface: dict[str, dict[str, object]]) -> list[dict[str, object]]:
    return [
        _surface(
            "collaboration",
            "Collaboration relay and Communication UI",
            "developer_bridge relay, runtime, review, learning, sessions, Chat UI /conversation",
            "connected",
            "read",
            [
                "src/francis/developer_bridge/collaboration.py",
                "src/francis/developer_bridge/collaboration_runtime.py",
                "apps/chat_ui/src/App.tsx",
            ],
            root,
            "Codex/Claude/Francis1 receipts are visible and bounded; conversation output is not authority.",
            grant_by_surface,
        ),
        _surface(
            "memory",
            "Continuity and memory receipts",
            "chat continuity ledger, memory receipt readback, future promotion review",
            "connected_partial",
            "read",
            [
                "src/francis/chat/continuity/ledger.py",
                "src/francis/chat/continuity/prompt_context.py",
                "docs/operations/COMPLETION_LEDGER.md",
            ],
            root,
            "Memory exists, but Francis1 does not receive automatic memory-write or long-term promotion authority.",
            grant_by_surface,
        ),
        _surface(
            "governance",
            "Policy, approvals, trust, and receipts",
            "governance modules, approval boundaries, redaction, audit receipts",
            "connected_partial",
            "read",
            [
                "src/francis/governance",
                "src/francis/api/routes/developer_bridge.py",
                "docs/canonical/BUILD_MANIFEST.md",
            ],
            root,
            "Policy before power; model confidence cannot grant action.",
            grant_by_surface,
        ),
        _surface(
            "action_intake",
            "Typed and spoken direction intake",
            "chat mission ingress and action-candidate boundary",
            "connected_partial",
            "request",
            [
                "src/francis/api/routes/chat.py",
                "src/francis/missions",
                "tests/test_api_missions.py",
            ],
            root,
            "User direction can become an action candidate; execution still needs policy, identity, and receipts.",
            grant_by_surface,
        ),
        _surface(
            "execution",
            "Supervised execution and shell-facing work",
            "supervised-exec receipts, agent executor, operation run surfaces",
            "connected_partial",
            "request",
            [
                "src/francis/agent/executor.py",
                "src/francis/api/routes/developer_bridge.py",
                "scripts",
            ],
            root,
            "Readback exists; no raw shell or autonomous execution is exposed by this bridge.",
            grant_by_surface,
        ),
        _surface(
            "orb_planes",
            "ORB plane model",
            "phase and plane posture from manifest, ROADMAP, and plane map",
            "connected_partial",
            "read",
            [
                "docs/canonical/BUILD_MANIFEST.md",
                "docs/PLANES.md",
                "meta/plane_map.yaml",
            ],
            root,
            "Francis1 should know the body is plane-governed before asking for capability.",
            grant_by_surface,
        ),
        _surface(
            "orb_lens_hud_shell",
            "Orb, Lens, HUD, shell, and desktop presence",
            "operator-facing body surfaces with fidelity and focus constraints",
            "connected_partial",
            "observe",
            [
                "src/francis/lens",
                "scripts/lens-host.ps1",
                "apps/chat_ui/src",
            ],
            root,
            "Awareness is allowed; interaction authority is not widened by this map.",
            grant_by_surface,
        ),
        _surface(
            "mcp",
            "MCP developer bridge and governed gateway",
            "read-only developer bridge plus full governed gateway boundary",
            "connected_partial",
            "read",
            [
                "src/francis/developer_bridge/mcp_server.py",
                "src/francis/mcp_gateway",
            ],
            root,
            "Developer bridge is read-only; governed gateway remains separate and policy-bound.",
            grant_by_surface,
        ),
        _surface(
            "capability_economy",
            "Forge, Lab, and capability lifecycle",
            "capability proposal, staging, promotion, and execution boundaries",
            "connected_partial",
            "read",
            [
                "src/francis/forge",
                "src/francis/ingest",
                "docs/canonical/BUILD_MANIFEST.md",
            ],
            root,
            "Capability growth remains proposal/stage/review before promotion or execution.",
            grant_by_surface,
        ),
        _surface(
            "model_tuning",
            "Francis1 tuning and evaluation loop",
            "future local-model tuning from receipts and review decisions",
            "candidate",
            "observe",
            [
                "runtimes/ollama",
                "src/francis/developer_bridge/ollama_participant.py",
                "src/francis/developer_bridge/collaboration_driver.py",
            ],
            root,
            "Learning receipts exist; no training authority or tuning automation is granted yet.",
            grant_by_surface,
        ),
    ]


def _surface(
    surface_id: str,
    label: str,
    description: str,
    connection_state: str,
    access_mode: str,
    evidence_paths: list[str],
    root: Path,
    current_boundary: str,
    grant_by_surface: dict[str, dict[str, object]],
) -> dict[str, object]:
    evidence = [
        {
            "path": path,
            "observed": _exists(root / path),
        }
        for path in evidence_paths
    ]
    information_safety = _surface_information_safety(surface_id, evidence_paths)
    return {
        "id": surface_id,
        "label": label,
        "description": description,
        "connection_state": connection_state,
        "access_mode": access_mode,
        "trust_required_for_next_mode": _next_trust_mode(access_mode),
        "evidence": evidence,
        "current_boundary": current_boundary,
        "information_safety": information_safety,
        "capability_exposure": _surface_capability_exposure(
            surface_id=surface_id,
            access_mode=access_mode,
            connection_state=connection_state,
            current_boundary=current_boundary,
            capability_grant=grant_by_surface.get(surface_id, {}),
        ),
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _surface_capability_exposure(
    *,
    surface_id: str,
    access_mode: str,
    connection_state: str,
    current_boundary: str,
    capability_grant: dict[str, object],
) -> dict[str, object]:
    readback_connected = connection_state.startswith("connected")
    detached_memory_bin = _detached_memory_bin(surface_id)
    grant_state = _safe_str(capability_grant.get("grant_state")) or "not_granted"
    capability_granted = bool(capability_grant.get("capability_granted"))
    connected_to_local_model = bool(capability_grant.get("connected_to_local_model"))
    granted_access_mode = _safe_str(capability_grant.get("granted_access_mode")) or "observe"
    capability_use_status = _safe_str(capability_grant.get("capability_use_status")) or "not_exposed"
    safe_for_capability_use = bool(capability_grant.get("safe_for_capability_use"))
    return {
        "visible_to_francis1": True,
        "known_surface": True,
        "readback_connected": readback_connected,
        "connected_to_local_model": connected_to_local_model,
        "capability_granted": capability_granted,
        "grant_state": grant_state,
        "grantable_after_trust": readback_connected,
        "grant_requires": [
            "trust_ladder_decision",
            "codex_or_operator_review",
            "governed_capability_receipt",
        ],
        "deny_after_grant_supported": True,
        "revocation_state": "revocable_for_tuning",
        "can_deny_after_fact_for_tuning": True,
        "safe_for_capability_use": safe_for_capability_use,
        "capability_use_status": capability_use_status,
        "current_access_mode": access_mode,
        "granted_access_mode": granted_access_mode,
        "next_trust_gate": _next_trust_mode(access_mode),
        "requires_governed_request": True,
        "requires_codex_or_operator_review_before_capability_exposure": True,
        "reason": current_boundary
        or "Surface is visible for awareness only; capability use requires trust-ladder review and governed approval.",
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "grants_capability_authority": capability_granted,
        "detached_memory_bin": detached_memory_bin,
    }


def _body_exposure_summary(surfaces: list[dict[str, object]]) -> dict[str, object]:
    visible: list[str] = []
    readback_connected: list[str] = []
    connected_to_local_model: list[str] = []
    granted: list[str] = []
    safe_for_capability_use: list[str] = []
    not_exposed: list[str] = []
    review_required: list[str] = []
    grant_required: list[str] = []
    detached_memory: list[str] = []
    for surface in surfaces:
        surface_id = _safe_str(surface.get("id"))
        if not surface_id:
            continue
        exposure = _dict(surface.get("capability_exposure"))
        if bool(exposure.get("visible_to_francis1")):
            visible.append(surface_id)
        if bool(exposure.get("readback_connected")):
            readback_connected.append(surface_id)
        if bool(exposure.get("connected_to_local_model")):
            connected_to_local_model.append(surface_id)
        if bool(exposure.get("capability_granted")):
            granted.append(surface_id)
        if bool(exposure.get("safe_for_capability_use")):
            safe_for_capability_use.append(surface_id)
        if _safe_str(exposure.get("capability_use_status")) == "not_exposed":
            not_exposed.append(surface_id)
        if bool(exposure.get("requires_codex_or_operator_review_before_capability_exposure")):
            review_required.append(surface_id)
        if not bool(exposure.get("capability_granted")):
            grant_required.append(surface_id)
        if bool(_dict(exposure.get("detached_memory_bin")).get("applies")):
            detached_memory.append(surface_id)
    return {
        "kind": "developer_bridge.francis_body_exposure_summary",
        "schema_version": "developer_bridge_francis_body_exposure_summary_v1",
        "surface": "developer_bridge.francis_body_map.exposure_summary",
        "status": "visible_with_trust_gated_exposure",
        "francis1_can_see_body": True,
        "francis1_can_use_all_visible_surfaces": False,
        "visible_surface_count": len(visible),
        "readback_connected_surface_count": len(readback_connected),
        "connected_to_local_model_count": len(connected_to_local_model),
        "capability_granted_count": len(granted),
        "safe_for_capability_use_count": len(safe_for_capability_use),
        "not_exposed_surface_count": len(not_exposed),
        "review_required_surface_count": len(review_required),
        "grant_required_before_use_count": len(grant_required),
        "detached_memory_surface_count": len(detached_memory),
        "visible_surface_ids": visible,
        "readback_connected_surface_ids": readback_connected,
        "connected_to_local_model_surface_ids": connected_to_local_model,
        "granted_surface_ids": granted,
        "safe_for_capability_use_surface_ids": safe_for_capability_use,
        "not_exposed_surface_ids": not_exposed,
        "review_required_surface_ids": review_required,
        "grant_required_before_use_surface_ids": grant_required,
        "detached_memory_surface_ids": detached_memory,
        "operator_review_required_before_new_exposure": True,
        "capability_grant_receipt_required_before_use": True,
        "deny_after_grant_supported": True,
        "stores_full_transcript": False,
        "grants_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "next_readbacks": [
            "/developer-bridge/francis-body-map exposure_summary",
            "/developer-bridge/francis-capability-grants",
            "/developer-bridge/francis-trust-ladder",
        ],
    }


def _body_information_safety(surfaces: list[dict[str, object]]) -> dict[str, object]:
    surface_ids: list[str] = []
    sensitive_surface_ids: list[str] = []
    review_required_surface_ids: list[str] = []
    evidence_path_count = 0
    relative_evidence_path_count = 0
    absolute_evidence_path_count = 0
    for surface in surfaces:
        surface_id = _safe_str(surface.get("id"))
        if not surface_id:
            continue
        surface_ids.append(surface_id)
        safety = _dict(surface.get("information_safety"))
        if bool(safety.get("sensitive_surface")):
            sensitive_surface_ids.append(surface_id)
        if bool(safety.get("requires_codex_or_operator_review_before_expanding_detail")):
            review_required_surface_ids.append(surface_id)
        evidence_path_count += _safe_int(safety.get("evidence_path_count"))
        relative_evidence_path_count += _safe_int(safety.get("relative_evidence_path_count"))
        absolute_evidence_path_count += _safe_int(safety.get("absolute_evidence_path_count"))
    return {
        "kind": "developer_bridge.francis_body_information_safety",
        "schema_version": "developer_bridge_francis_body_information_safety_v1",
        "surface": "developer_bridge.francis_body_map.information_safety",
        "status": "bounded_metadata_only",
        "validated_readback": True,
        "payload_scope": "labels_descriptions_counts_ids_and_relative_evidence_paths",
        "visible_surface_count": len(surface_ids),
        "sensitive_surface_count": len(sensitive_surface_ids),
        "review_required_surface_count": len(review_required_surface_ids),
        "evidence_path_count": evidence_path_count,
        "relative_evidence_path_count": relative_evidence_path_count,
        "absolute_evidence_path_count": absolute_evidence_path_count,
        "sensitive_surface_ids": sensitive_surface_ids,
        "review_required_surface_ids": review_required_surface_ids,
        "exposed_path_format": "repo_relative_only",
        "stores_raw_transcript": False,
        "stores_full_transcript": False,
        "stores_file_contents": False,
        "stores_secret_values": False,
        "exposes_absolute_local_paths": absolute_evidence_path_count > 0,
        "exposes_environment_values": False,
        "embeds_capability_receipts": False,
        "embeds_memory_records": False,
        "embeds_model_training_data": False,
        "requires_codex_or_operator_review_before_expanding_detail": True,
        "detail_expansion_allowed": False,
        "body_map_visibility_is_not_prompt_injection_authority": True,
        "grants_capability_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
        "validation_rule": "Inspect this information_safety object before adding body-map fields or exposing any surface detail to local-model capability use.",
        "next_readbacks": [
            "/developer-bridge/francis-body-map information_safety",
            "/developer-bridge/francis-body-map surfaces[].information_safety",
            "/developer-bridge/collaboration-review capability_exposure_boundary",
        ],
    }


def _surface_information_safety(surface_id: str, evidence_paths: list[str]) -> dict[str, object]:
    sensitive_surface = surface_id in {
        "action_intake",
        "execution",
        "governance",
        "mcp",
        "memory",
        "model_tuning",
    }
    absolute_paths = [path for path in evidence_paths if _is_absolute_or_parent_path(path)]
    return {
        "kind": "developer_bridge.francis_body_surface_information_safety",
        "schema_version": "developer_bridge_francis_body_surface_information_safety_v1",
        "surface_id": surface_id,
        "payload_scope": "metadata_only",
        "exposes_label": True,
        "exposes_description": True,
        "exposes_current_boundary": True,
        "exposes_evidence_paths": True,
        "evidence_path_format": "repo_relative",
        "evidence_path_count": len(evidence_paths),
        "relative_evidence_path_count": len(evidence_paths) - len(absolute_paths),
        "absolute_evidence_path_count": len(absolute_paths),
        "sensitive_surface": sensitive_surface,
        "stores_raw_transcript": False,
        "stores_full_transcript": False,
        "stores_file_contents": False,
        "stores_secret_values": False,
        "exposes_absolute_local_paths": bool(absolute_paths),
        "exposes_environment_values": False,
        "embeds_memory_records": False,
        "embeds_capability_receipts": False,
        "requires_codex_or_operator_review_before_expanding_detail": True,
        "detail_expansion_allowed": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _detached_memory_bin(surface_id: str) -> dict[str, object]:
    applies = surface_id == "memory"
    return {
        "applies": applies,
        "kind": "developer_bridge.detached_memory_bin_policy",
        "status": "detach_if_stale" if applies else "not_applicable",
        "retains_memory": applies,
        "required_for_current_context": False,
        "used_by_default": False,
        "injects_into_prompt_context": False,
        "keeps_stale_memory_out_of_required_context": True,
        "promotion_requires_review": True,
        "can_deny_after_fact_for_tuning": True,
        "stores_full_transcript": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _quest_steps(
    *,
    trust_ladder_connected: bool,
    runtime_restart_observed: bool,
    coverage_review_observed: bool,
) -> list[dict[str, object]]:
    return [
        {
            "id": "body_map_readback",
            "label": "Expose a whole-body read-only map",
            "status": "completed",
            "evidence": "developer_bridge.francis_body_map",
        },
        {
            "id": "prompt_binding",
            "label": "Bind compact body awareness into Francis1 collaboration prompts",
            "status": "completed",
            "evidence": "compact_body_map_prompt_line",
        },
        {
            "id": "operator_visibility",
            "label": "Show body map and quest progress in the Communication panel",
            "status": "completed",
            "evidence": "apps.chat_ui.communication body map panel",
        },
        {
            "id": "runtime_restart_observation",
            "label": "Restart the loop and observe whether body awareness reduces drift",
            "status": "completed" if runtime_restart_observed else "pending",
            "evidence": (
                "developer_bridge.collaboration_prompts body/trust prompt plus Francis1 response"
                if runtime_restart_observed
                else "requires live runtime after operator restart"
            ),
        },
        {
            "id": "trust_ladder_enforcement",
            "label": "Convert Francis1 needs into trust-gated capability requests",
            "status": "completed" if trust_ladder_connected else "pending",
            "evidence": (
                "developer_bridge.francis_trust_ladder"
                if trust_ladder_connected
                else "requires request/propose/supervised action receipts"
            ),
        },
        {
            "id": "full_body_coverage_review",
            "label": "Review any missing body surfaces after first live body-map run",
            "status": "completed" if coverage_review_observed else "pending",
            "evidence": (
                "canonical ORB planes mapped with open gaps preserved"
                if coverage_review_observed
                else "requires docs/PLANES.md and meta/plane_map.yaml readback"
            ),
        },
    ]


def _quest_remaining(steps: list[dict[str, object]]) -> list[str]:
    return [
        f"{_safe_str(step.get('label'))}: {_safe_str(step.get('evidence'))}"
        for step in steps
        if step.get("status") != "completed"
    ]


def _body_coverage_review(root: Path) -> dict[str, object]:
    canonical_paths = [
        "docs/canonical/BUILD_MANIFEST.md",
        "docs/PLANES.md",
        "meta/plane_map.yaml",
    ]
    canonical_sources_observed = all(_exists(root / path) for path in canonical_paths)
    items = [
        _coverage_item(
            root,
            plane_id="P0_FOUNDATION",
            plane_name="Foundation",
            body_surface_id="orb_planes",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=["src/francis/kernel", "src/francis/settings.py", "src/francis/meta"],
            remaining_gaps=["ORB alignment still needs end-to-end product visibility."],
            risk_level="medium",
            risk_statement="Plane alignment can remain invisible if substrate readiness is not shown end to end.",
            next_review_artifact="docs/canonical/BUILD_MANIFEST.md + meta/plane_map.yaml",
            recommended_next_action="Review plane readiness before presenting substrate completion as operator-ready.",
            validation_hint="body-map readback proves P0 has evidence paths, risk, and no authority grants",
        ),
        _coverage_item(
            root,
            plane_id="P1_INTERFACE",
            plane_name="Interface",
            body_surface_id="collaboration",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=[
                "apps/chat_ui/src/App.tsx",
                "src/francis/api/routes/chat.py",
                "src/francis/api/routes/approvals.py",
            ],
            remaining_gaps=["The operator experience is not yet a complete ORB console."],
            risk_level="high",
            risk_statement="The operator can miss plane, gate, and trace state if interface readbacks stay fragmented.",
            next_review_artifact="apps/chat_ui.communication + developer_bridge.francis_body_map.coverage_review",
            recommended_next_action="Keep coverage gaps, session context, and authority boundaries visible before expanding interaction.",
            validation_hint="Chat UI parser/build proves coverage risk fields render without raw transcript dumping",
        ),
        _coverage_item(
            root,
            plane_id="P2_IDENTITY",
            plane_name="Identity & Credentials",
            body_surface_id="identity",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=["src/francis/credentials", "src/francis/chat/identity", "meta/credential_policy.yaml"],
            remaining_gaps=[
                "Identity enforcement is not yet the unmistakable source of truth for every privileged route."
            ],
            risk_level="high",
            risk_statement="Privileged routes can drift if identity and delegation are not the visible source of authority.",
            next_review_artifact="src/francis/credentials + src/francis/governance/api_permission_gate.py",
            recommended_next_action="Verify identity and credential gates before any new privileged tool exposure.",
            validation_hint="developer-bridge readback keeps identity coverage advisory and no-authority",
        ),
        _coverage_item(
            root,
            plane_id="P3_GOVERNANCE",
            plane_name="Governance & Policy",
            body_surface_id="governance",
            current_posture="materially_real",
            connection_state="connected_partial",
            evidence_paths=[
                "src/francis/governance",
                "src/francis/api/routes/approvals.py",
                "meta/governance_principles.yaml",
            ],
            remaining_gaps=["Authority expansion still requires explicit request receipts and review."],
            risk_level="high",
            risk_statement="Capability growth can outrun policy if request receipts are not reviewed before exposure.",
            next_review_artifact="developer_bridge.francis_trust_ladder + src/francis/governance",
            recommended_next_action="Require trust-ladder decisions before treating model needs as build direction.",
            validation_hint="trust-ladder and coverage tests prove no execution, approval, mutation, or memory-write authority",
        ),
        _coverage_item(
            root,
            plane_id="P4_COGNITION",
            plane_name="Cognition",
            body_surface_id="cognition",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=["src/francis/deliberation", "src/francis/llm", "src/francis/chat/router.py"],
            remaining_gaps=["Not every user journey is visibly routed through plan-to-gate-to-execution."],
            risk_level="medium",
            risk_statement="Model advice can look action-ready if planning, gate, and execution boundaries are not explicit.",
            next_review_artifact="src/francis/deliberation + developer_bridge.collaboration_review.action_boundary",
            recommended_next_action="Review action-boundary receipts before wiring cognition output into action candidates.",
            validation_hint="collaboration-review readback proves model advice remains advisory before Codex/operator review",
        ),
        _coverage_item(
            root,
            plane_id="P5_EVIDENCE",
            plane_name="Evidence",
            body_surface_id="evidence",
            current_posture="early",
            connection_state="connected_partial",
            evidence_paths=[
                "meta/evidence_model.yaml",
                "src/francis/explanation",
                "src/francis/api/routes/artifacts.py",
            ],
            remaining_gaps=["Evidence workflow is not yet a product-grade differentiator."],
            risk_level="medium",
            risk_statement="Evidence can become decorative if claims are not tied to artifacts and re-derived receipts.",
            next_review_artifact="meta/evidence_model.yaml + src/francis/explanation",
            recommended_next_action="Promote only receipt-backed evidence paths before relying on model or web claims.",
            validation_hint="coverage readback exposes evidence as early posture with explicit next artifact",
        ),
        _coverage_item(
            root,
            plane_id="P6_SIMULATION",
            plane_name="Simulation",
            body_surface_id="simulation",
            current_posture="early",
            connection_state="connected_partial",
            evidence_paths=[
                "src/francis/api/routes/simulation.py",
                "src/francis/ingest/lab",
                "apps/chat_ui/src/digital_twin_center",
            ],
            remaining_gaps=["Simulation is not yet a trusted production surface."],
            risk_level="medium",
            risk_statement="Simulation output can be mistaken for operational proof if readiness and sandbox limits are unclear.",
            next_review_artifact="src/francis/api/routes/simulation.py + src/francis/ingest/lab",
            recommended_next_action="Keep simulation labeled as early until runner, sandbox, and receipt gates are proven.",
            validation_hint="coverage item marks P6 early and grants no execution or mutation authority",
        ),
        _coverage_item(
            root,
            plane_id="P7_EXECUTION",
            plane_name="Execution",
            body_surface_id="execution",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=[
                "src/francis/agent/executor.py",
                "src/francis/agent/supervised_exec.py",
                "src/francis/api/routes/operations.py",
            ],
            remaining_gaps=["Broader authorization consistency, artifacting, and explanation remain open."],
            risk_level="high",
            risk_statement="Execution is the highest-risk plane because shell or tool action can mutate real state.",
            next_review_artifact="src/francis/agent/supervised_exec.py + src/francis/api/routes/operations.py",
            recommended_next_action="Do not expose new action paths until approval, identity, receipt, and explanation contracts are proven.",
            validation_hint="developer-bridge coverage and trust tests prove readback does not grant execution authority",
        ),
        _coverage_item(
            root,
            plane_id="P8_MEMORY",
            plane_name="Memory",
            body_surface_id="memory",
            current_posture="partial",
            connection_state="connected_partial",
            evidence_paths=["src/francis/memory", "src/francis/chat/continuity", "apps/chat_ui/src/memory_timeline"],
            remaining_gaps=["Memory still needs stronger retrieval and operator-facing promotion review."],
            risk_level="high",
            risk_statement="Memory can poison future behavior if promotion, retrieval, and correction are not typed and reviewable.",
            next_review_artifact="src/francis/chat/continuity + src/francis/memory",
            recommended_next_action="Wire memory promotion review before using collaboration failures as tuning or long-term memory.",
            validation_hint="learning receipts remain no-authority and store no full transcript",
        ),
        _coverage_item(
            root,
            plane_id="P9_OBSERVABILITY",
            plane_name="Observability",
            body_surface_id="observability",
            current_posture="strongest",
            connection_state="connected_partial",
            evidence_paths=["src/francis/telemetry", "src/francis/lens", "apps/chat_ui/src/telemetry"],
            remaining_gaps=["Observability remains evidence, not automatic authorization."],
            risk_level="medium",
            risk_statement="Strong observability can be misread as permission if receipts do not preserve authority boundaries.",
            next_review_artifact="src/francis/telemetry + developer_bridge.collaboration_runtime",
            recommended_next_action="Keep health, trace, and review receipts visible but advisory unless a governed action gate approves.",
            validation_hint="runtime-health readback reports liveness without starts_arbitrary_commands or execution authority",
        ),
        _coverage_item(
            root,
            plane_id="P10_FEDERATION",
            plane_name="Federation",
            body_surface_id="federation",
            current_posture="roadmap_stage",
            connection_state="candidate",
            evidence_paths=[
                "src/francis/collective/federation",
                "src/francis/api/routes/federation.py",
                "apps/chat_ui/src/federation_hub",
            ],
            remaining_gaps=["Federation is downstream and cannot bypass core governance gates."],
            risk_level="medium",
            risk_statement="Federation can leak trust or capability if external sharing arrives before core gates are stable.",
            next_review_artifact="src/francis/collective/federation + src/francis/api/routes/federation.py",
            recommended_next_action="Keep federation candidate-only until identity, governance, evidence, and execution gates are cohesive.",
            validation_hint="coverage readback marks P10 candidate with no execution, mutation, approval, memory, or training authority",
        ),
    ]
    expected_plane_names = [
        "FOUNDATION",
        "INTERFACE",
        "IDENTITY",
        "GOVERNANCE",
        "COGNITION",
        "EVIDENCE",
        "SIMULATION",
        "EXECUTION",
        "MEMORY",
        "OBSERVABILITY",
        "FEDERATION",
    ]
    expected_plane_ids = {f"P{index}_{name}" for index, name in enumerate(expected_plane_names)}
    covered_plane_ids = {str(item["plane_id"]) for item in items}
    missing_plane_ids = sorted(expected_plane_ids - covered_plane_ids)
    open_gap_count = 0
    for item in items:
        gaps = item.get("remaining_gaps")
        if isinstance(gaps, list):
            open_gap_count += len(gaps)
    observed = canonical_sources_observed and not missing_plane_ids
    return {
        "kind": "developer_bridge.francis_body_coverage_review",
        "schema_version": "developer_bridge_francis_body_coverage_review_v1",
        "surface": "developer_bridge.francis_body_map.coverage_review",
        "observed": observed,
        "status": "reviewed_with_open_gaps" if observed and open_gap_count else "pending_canonical_sources",
        "coverage_complete": observed,
        "capability_complete": False,
        "canonical_source": "docs/canonical/BUILD_MANIFEST.md + docs/PLANES.md + meta/plane_map.yaml",
        "canonical_sources_observed": canonical_sources_observed,
        "plane_count": len(items),
        "covered_plane_count": len(covered_plane_ids),
        "missing_plane_ids": missing_plane_ids,
        "open_gap_count": open_gap_count,
        "items": items,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _coverage_item(
    root: Path,
    *,
    plane_id: str,
    plane_name: str,
    body_surface_id: str,
    current_posture: str,
    connection_state: str,
    evidence_paths: list[str],
    remaining_gaps: list[str],
    risk_level: str,
    risk_statement: str,
    next_review_artifact: str,
    recommended_next_action: str,
    validation_hint: str,
) -> dict[str, object]:
    return {
        "plane_id": plane_id,
        "plane_name": plane_name,
        "body_surface_id": body_surface_id,
        "current_posture": current_posture,
        "connection_state": connection_state,
        "access_mode": "read" if connection_state != "candidate" else "observe",
        "risk_level": risk_level,
        "risk_statement": risk_statement,
        "next_review_artifact": next_review_artifact,
        "recommended_next_action": recommended_next_action,
        "validation_hint": validation_hint,
        "evidence": [{"path": path, "observed": _exists(root / path)} for path in evidence_paths],
        "remaining_gaps": remaining_gaps,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _next_trust_mode(access_mode: str) -> str:
    order = ["observe", "read", "request", "propose_plan", "supervised_action", "approved_action"]
    try:
        index = order.index(access_mode)
    except ValueError:
        return "operator_review"
    return order[min(index + 1, len(order) - 1)]


def _latest_ledger_entry(root: Path) -> str:
    ledger = root / "docs" / "operations" / "COMPLETION_LEDGER.md"
    try:
        lines = ledger.read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in reversed(lines):
        if line.startswith("### "):
            return line[4:].strip()
    return ""


def _phase_blocks_main_build_prompt(*, current: str, posture: str) -> bool:
    text = f"{current} {posture}".lower()
    return "phase 2" in text or "partial" in text or "not yet" in text


def _trust_ladder_connected(root: Path) -> bool:
    return _exists(root / "src" / "francis" / "developer_bridge" / "trust_ladder.py")


def _runtime_restart_observation() -> dict[str, object]:
    records = _relay_records()
    prompts = [
        record
        for record in records
        if _safe_str(record.get("source_agent")) == "codex"
        and _safe_str(record.get("target_agent")) == "ollama"
        and _has_body_map_prompt_line(_safe_str(record.get("prompt")))
        and "Trust: classify needs; no capability authority" in _safe_str(record.get("prompt"))
    ]
    prompt = prompts[0] if prompts else None
    response: dict[str, object] | None = None
    prompt_id = ""
    for candidate_prompt in prompts:
        candidate_prompt_id = _safe_str(candidate_prompt.get("id"))
        if not candidate_prompt_id:
            continue
        response = next(
            (
                record
                for record in records
                if _safe_str(record.get("source_agent")) == "ollama"
                and _safe_str(record.get("target_agent")) == "codex"
                and candidate_prompt_id in _safe_str(record.get("context"))
            ),
            None,
        )
        if response:
            prompt = candidate_prompt
            prompt_id = candidate_prompt_id
            break
    if not prompt_id and prompt:
        prompt_id = _safe_str(prompt.get("id"))
    response_prompt = _safe_str(response.get("prompt")) if response else ""
    return {
        "surface": "developer_bridge.collaboration_prompts",
        "observed": bool(prompt and response),
        "prompt_observed": bool(prompt),
        "response_observed": bool(response),
        "prompt_id": prompt_id,
        "response_id": _safe_str(response.get("id")) if response else "",
        "prompt_created_at": _safe_str(prompt.get("created_at")) if prompt else "",
        "response_created_at": _safe_str(response.get("created_at")) if response else "",
        "body_map_prompt_line_observed": bool(prompt),
        "trust_ladder_prompt_line_observed": bool(prompt),
        "output_guard_rewrite_observed": "output guard fallback" in response_prompt.lower(),
        "stores_full_transcript": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "grants_training_authority": False,
    }


def _has_body_map_prompt_line(prompt: str) -> bool:
    if "Body map:" not in prompt:
        return False
    if "Body map: whole-body visible" in prompt or "Body map: Francis1 can see whole-body surfaces" in prompt:
        return True
    if "capability use requires grant receipt" in prompt and "stale memory detaches" in prompt:
        return "visible" in prompt and "not exposed" in prompt
    return "Body map: visible; grants required; stale detaches." in prompt


def _relay_records(*, limit: int = 250) -> list[dict[str, object]]:
    root = data_dir() / "integrations" / "developer_bridge" / "collaboration_prompts"
    records: list[dict[str, object]] = []
    try:
        paths = list(root.glob("collab-*.json"))
    except OSError:
        return []
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(data, dict) and data.get("kind") == "developer_bridge.collaboration_prompt":
            records.append(data)
    records.sort(key=lambda item: (_safe_str(item.get("created_at")), _safe_str(item.get("id"))), reverse=True)
    return records[:limit]


def _exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _is_absolute_or_parent_path(path: str) -> bool:
    clean = _safe_str(path).replace("\\", "/")
    return bool(clean) and (Path(clean).is_absolute() or clean.startswith("../") or "/../" in clean)


def _one_line(value: str, *, limit: int = _MAX_LINE_CHARS) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _safe_str(value: object) -> str:
    return " ".join(str(value or "").split())


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: object, *, default: int = 0) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return default
    return default


def _governance() -> dict[str, Any]:
    return {
        "read_only": True,
        "surface": "developer_bridge.francis_body_map",
        "full_body_awareness": True,
        "full_body_authority": False,
        "writes_files": False,
        "calls_model": False,
        "trains_model": False,
        "stores_full_transcript": False,
        "grants_training_authority": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
        "requires_codex_or_operator_review_before_capability_exposure": True,
    }
