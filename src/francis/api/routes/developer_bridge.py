from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError
import json
from threading import Lock
from time import monotonic

from fastapi import APIRouter, Query
from fastapi import Response
from pydantic import BaseModel

from francis.developer_bridge.agents import collaboration_agents_status, set_collaboration_agent_enabled
from francis.developer_bridge.body_map import read_francis_body_map
from francis.developer_bridge.capability_grants import read_francis_capability_grants, set_francis_capability_grant
from francis.developer_bridge.collaboration import read_collaboration_sessions, read_collaboration_transcript
from francis.developer_bridge.collaboration_driver import read_collaboration_learning_events
from francis.developer_bridge.collaboration_review import read_collaboration_review
from francis.developer_bridge.collaboration_runtime import read_collaboration_runtime_health
from francis.developer_bridge.substrate_readiness import read_collaboration_substrate_readiness
from francis.developer_bridge.trust_ladder import read_francis_trust_ladder
from francis.developer_bridge.repo_tools import (
    DeveloperBridgeError,
    git_diff_summary,
    read_completion_ledger,
    read_repo_file,
    read_supervised_exec_receipt,
    repo_status,
    search_repo,
)
from francis.kernel.paths import data_dir

router = APIRouter()
_READBACK_CACHE_TTL_SECONDS = 3.0
_READBACK_REFRESH_TIMEOUT_SECONDS = 2.0
_READBACK_LOCK = Lock()
_READBACK_CACHE: dict[str, tuple[float, dict[str, object]]] = {}
_READBACK_IN_FLIGHT: dict[str, Future[dict[str, object]]] = {}
_READBACK_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="francis-readback")


class CollaborationAgentToggleIn(BaseModel):
    agent: str
    enabled: bool
    actor: str = "chat_ui.system"
    reason: str = ""


class FrancisCapabilityGrantIn(BaseModel):
    surface_id: str
    decision: str
    requested_access_mode: str = "read"
    actor: str = "chat_ui.system"
    reason: str = ""
    source_review_item_id: str = ""


def _call_read_only(func, *args, **kwargs) -> dict[str, object]:  # type: ignore[no-untyped-def]
    try:
        return func(*args, **kwargs)
    except DeveloperBridgeError as exc:
        return exc.to_dict()


def _read_only_json_response(func, *args, **kwargs) -> Response:  # type: ignore[no-untyped-def]
    payload = _call_read_only(func, *args, **kwargs)
    return _json_response(payload)


def _json_response(payload: dict[str, object]) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str),
        media_type="application/json",
    )


def _cache_key(kind: str, kwargs: dict[str, object]) -> str:
    return json.dumps(
        {"kind": kind, "data_dir": str(data_dir()), "kwargs": kwargs},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _cache_key_kind(key: str) -> str:
    try:
        raw = json.loads(key)
    except json.JSONDecodeError:
        return ""
    if not isinstance(raw, dict):
        return ""
    return str(raw.get("kind") or "")


def _invalidate_readback_cache(*kinds: str) -> None:
    kind_set = {kind for kind in kinds if kind}
    if not kind_set:
        return
    with _READBACK_LOCK:
        for key in list(_READBACK_CACHE):
            if _cache_key_kind(key) in kind_set:
                _READBACK_CACHE.pop(key, None)
        for key in list(_READBACK_IN_FLIGHT):
            if _cache_key_kind(key) in kind_set:
                _READBACK_IN_FLIGHT.pop(key, None)


def _copy_payload(payload: dict[str, object]) -> dict[str, object]:
    return json.loads(json.dumps(payload, ensure_ascii=False, default=str))


def _with_cache_status(payload: dict[str, object], *, status: str, age_seconds: float | None) -> dict[str, object]:
    copied = _copy_payload(payload)
    copied["readback_cache"] = {
        "status": status,
        "age_ms": int(age_seconds * 1000) if age_seconds is not None else None,
        "ttl_ms": int(_READBACK_CACHE_TTL_SECONDS * 1000),
        "serves_full_transcript_store": False,
    }
    return copied


def _empty_readback_payload(empty_payload, kwargs: dict[str, object]) -> dict[str, object]:  # type: ignore[no-untyped-def]
    try:
        return empty_payload(**kwargs)
    except Exception as exc:  # pragma: no cover - defensive boundary
        return _readback_error_payload("developer_bridge.readback_empty_payload", exc)


def _readback_error_payload(kind: str, error: BaseException) -> dict[str, object]:
    return {
        "kind": kind,
        "ok": False,
        "mode": "read_only",
        "error": str(error),
        "governance": {
            "executes_prompt": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _store_readback_future_result(kind: str, key: str, future: Future[dict[str, object]]) -> None:
    try:
        payload = future.result()
    except Exception as exc:  # pragma: no cover - defensive boundary
        payload = _readback_error_payload(kind, exc)
    with _READBACK_LOCK:
        if _READBACK_IN_FLIGHT.get(key) is not future:
            return
        _READBACK_IN_FLIGHT.pop(key, None)
        _READBACK_CACHE[key] = (monotonic(), payload)


def _cached_read_only_json_response(
    kind: str,
    func,
    _empty_payload,
    **kwargs,
) -> Response:  # type: ignore[no-untyped-def]
    key = _cache_key(kind, kwargs)
    now = monotonic()
    with _READBACK_LOCK:
        cached = _READBACK_CACHE.get(key)
        if cached is not None and now - cached[0] <= _READBACK_CACHE_TTL_SECONDS:
            return _json_response(_with_cache_status(cached[1], status="hit", age_seconds=now - cached[0]))
        in_flight = _READBACK_IN_FLIGHT.get(key)
        if in_flight is not None:
            if cached is not None:
                return _json_response(
                    _with_cache_status(cached[1], status="stale_refreshing", age_seconds=now - cached[0])
                )
            return _json_response(
                _with_cache_status(_empty_readback_payload(_empty_payload, kwargs), status="warming", age_seconds=None)
            )

        future = _READBACK_EXECUTOR.submit(_call_read_only, func, **kwargs)
        _READBACK_IN_FLIGHT[key] = future

        def store_done(
            done: Future[dict[str, object]],
            *,
            done_kind: str = kind,
            done_key: str = key,
        ) -> None:
            _store_readback_future_result(done_kind, done_key, done)

        future.add_done_callback(store_done)

    try:
        payload = future.result(timeout=_READBACK_REFRESH_TIMEOUT_SECONDS)
    except TimeoutError:
        with _READBACK_LOCK:
            cached = _READBACK_CACHE.get(key)
            if cached is not None:
                return _json_response(
                    _with_cache_status(cached[1], status="stale_refreshing", age_seconds=monotonic() - cached[0])
                )
        return _json_response(
            _with_cache_status(_empty_readback_payload(_empty_payload, kwargs), status="warming", age_seconds=None)
        )
    except Exception as exc:  # pragma: no cover - defensive boundary
        payload = _readback_error_payload(kind, exc)
    with _READBACK_LOCK:
        _READBACK_IN_FLIGHT.pop(key, None)
        _READBACK_CACHE[key] = (monotonic(), payload)
    return _json_response(_with_cache_status(payload, status="refreshed", age_seconds=0.0))


def _empty_transcript_payload(
    *,
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = 20,
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_transcript",
        "ok": True,
        "mode": "read_only",
        "relay_root": "integrations/developer_bridge/collaboration_prompts",
        "items": [],
        "count": 0,
        "truncated": False,
        "filters": {
            "agent": agent,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "status": status,
            "limit": limit,
        },
        "governance": {
            "executes_prompt": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
        },
    }


def _empty_sessions_payload(
    *,
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = 10,
    item_limit: int = 50,
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_sessions",
        "schema_version": "developer_bridge_collaboration_sessions_v1",
        "ok": True,
        "mode": "read_only",
        "relay_root": "integrations/developer_bridge/collaboration_prompts",
        "items": [],
        "count": 0,
        "truncated": False,
        "filters": {
            "agent": agent,
            "source_agent": source_agent,
            "target_agent": target_agent,
            "status": status,
            "limit": limit,
            "item_limit": item_limit,
        },
        "definitions": {
            "session": "Messages grouped by timestamp gap from bounded relay receipts.",
            "latest_preview": "A short bounded preview from the latest receipt, not a full transcript store.",
        },
        "governance": {
            "executes_prompt": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "stores_full_transcript": False,
            "calls_model": False,
            "trains_model": False,
            "grants_memory_write_authority": False,
        },
    }


def _empty_review_payload(
    *,
    limit: int = 10,
    session_id: str = "",
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_review",
        "schema_version": "developer_bridge_collaboration_review_v1",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_review",
        "items": [],
        "count": 0,
        "filters": {
            "limit": limit,
            "session_id": session_id,
        },
        "definitions": {
            "concrete_repo_surface": (
                "The bounded code, API, UI, receipt, or docs surface Codex must inspect before implementation."
            ),
            "review_artifact": (
                "The typed receipt or candidate record Codex/operator reviews before any repo change, memory "
                "promotion, or action-readiness claim."
            ),
            "surface_verification": (
                "Read-only statement of whether the review projection found an existing Francis surface to inspect, "
                "or whether the item still needs repo-truth review before build or wiring work."
            ),
            "build_direction_gate": (
                "Read-only gate stating whether the review item can be used as build direction or must remain "
                "blocked until typed review records the required evidence."
            ),
        },
        "governance": {
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
        },
    }


def _empty_learning_payload(
    *,
    limit: int = 10,
    failure_type: str = "",
    term: str = "",
    session_id: str = "",
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_learning_events",
        "schema_version": "developer_bridge_collaboration_learning_v1",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_driver.learning_events",
        "items": [],
        "count": 0,
        "truncated": False,
        "filters": {
            "limit": limit,
            "failure_type": failure_type,
            "term": term,
            "session_id": session_id,
        },
        "definitions": {
            "learning_event": "A bounded receipt for repeated collaboration drift, loops, or local-model failure patterns.",
            "failure_type": "The classified failure or drift class recorded by the collaboration driver.",
            "repeated_terms": "Stable drift markers counted across recent relay notes; not raw transcript text.",
            "recent_turns": "Receipt identifiers and matched markers used as evidence without storing full messages.",
        },
        "governance": {
            "read_only": True,
            "reads_collaboration_learning_events": True,
            "writes_files": False,
            "stores_full_transcript": False,
            "calls_model": False,
            "trains_model": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_model_authority": False,
        },
    }


def _empty_runtime_health_payload() -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_runtime_health",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_runtime",
        "status": "unknown",
        "desired_count": 0,
        "helper_count": 0,
        "helpers": [],
        "supervisor": {
            "state_observed": False,
            "state_path": "integrations/developer_bridge/collaboration_runtime/state.json",
            "generated_at": "",
            "age_seconds": None,
        },
        "collaboration_loop": {
            "state_observed": False,
            "state_path": "integrations/developer_bridge/collaboration_driver/state.json",
            "turn_count": 0,
            "recurrence_state": "unknown",
            "waiting_for_ollama": False,
            "last_codex_prompt_id": "",
            "last_ollama_prompt_id": "",
            "last_note_id": "",
            "last_insight_id": "",
            "last_learning_event_id": "",
            "next_prompt_after": "",
            "turn_gap_remaining_seconds": 0.0,
            "latest_turn": {},
        },
        "participants": {
            "enabled_count": 0,
            "total_count": 0,
            "items": [],
        },
        "governance": {
            "read_only": True,
            "reads_runtime_state": True,
            "reads_driver_state": True,
            "starts_bounded_local_helpers": False,
            "starts_arbitrary_commands": False,
            "executes_prompt": False,
            "calls_model": False,
            "trains_model": False,
            "stores_full_transcript": False,
            "grants_model_execution_authority": False,
            "grants_repo_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
        },
    }


def _empty_substrate_readiness_payload() -> dict[str, object]:
    return {
        "kind": "developer_bridge.collaboration_substrate_readiness",
        "schema_version": "developer_bridge_collaboration_substrate_readiness_v1",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.collaboration_substrate_readiness",
        "generated_at": "",
        "status": "warming",
        "required_alignment_sources": [
            "docs/operations/COMPLETION_LEDGER.md",
            "docs/canonical/BUILD_MANIFEST.md",
        ],
        "summary": {
            "collaboration_substrate_wired": False,
            "bounded_wiring_percent_complete": 0,
            "main_build_prompt_allowed": False,
            "main_build_prompt_gate": "requires_alignment_review",
            "coverage_open_gap_count": 0,
            "trust_ladder_enforced": False,
            "runtime_healthy": False,
            "learning_receipts_bounded": False,
            "no_authority_granted": True,
        },
        "checklist": [],
        "blocking_items": [],
        "next_action": (
            "Read the completion ledger and build manifest before treating collaboration output as build direction."
        ),
        "definitions": {
            "collaboration_substrate_wired": (
                "The relay, body map, trust ladder, runtime health, and no-authority guard are visible."
            ),
            "main_build_prompt_allowed": ("Whether this readback allows unsupervised main Francis build prompting."),
            "blocking_items": "Checklist items that block main-build prompting.",
        },
        "source_readbacks": {
            "body_map": "developer_bridge.francis_body_map",
            "runtime_health": "developer_bridge.collaboration_runtime_health",
            "trust_ladder": "developer_bridge.francis_trust_ladder",
            "learning": "developer_bridge.collaboration_driver.learning_events",
        },
        "governance": {
            "read_only": True,
            "derived_from_readbacks": True,
            "executes_prompt": False,
            "calls_model": False,
            "trains_model": False,
            "stores_full_transcript": False,
            "writes_memory": False,
            "writes_files": False,
            "starts_processes": False,
            "grants_model_execution_authority": False,
            "grants_repo_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }


def _empty_body_map_payload() -> dict[str, object]:
    return {
        "kind": "developer_bridge.francis_body_map",
        "schema_version": "developer_bridge_francis_body_map_v1",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.francis_body_map",
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
            "posture": "unknown",
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
        "surfaces": [],
        "summary": {
            "surface_count": 0,
            "connected_or_partial_count": 0,
            "candidate_count": 0,
            "blocked_count": 0,
            "unknown_count": 0,
            "default_access_mode": "observe",
            "full_body_visible": True,
            "full_body_authority_granted": False,
            "visible_surface_count": 0,
            "connected_to_local_model_count": 0,
            "capability_granted_count": 0,
            "not_exposed_surface_count": 0,
            "review_required_surface_count": 0,
            "active_capability_grant_count": 0,
            "denied_or_revoked_capability_count": 0,
            "trust_ladder_enforced": False,
            "runtime_restart_observed": False,
            "coverage_reviewed": False,
            "canonical_plane_count": 0,
            "canonical_plane_covered_count": 0,
            "coverage_open_gap_count": 0,
        },
        "quest": {
            "id": "francis1-whole-body-awareness-and-trust-gated-capability-v1",
            "title": "Wire Francis1 whole-body awareness with trust-gated capability exposure",
            "estimated_timeline": "warming",
            "single_timeline": [],
            "steps": [],
            "completed_steps": 0,
            "total_steps": 0,
            "percent_complete": 0,
            "percent_baseline": "completed quest steps divided by declared bounded wiring steps",
            "remaining": [],
        },
        "definitions": {
            "body_surface": "A known Francis subsystem Francis1 may be aware of without receiving authority to use it.",
            "access_mode": "The highest declared interaction mode this readback exposes to Francis1 today.",
            "connection_state": "Whether the surface is wired, partial, candidate-only, blocked, or unknown.",
            "capability_exposure": "A per-surface verdict separating Francis1 visibility from permission to use that capability.",
            "exposure_summary": "A compact readback of visible, exposed, and review-required body surfaces.",
            "coverage_review": "A read-only map from canonical ORB planes to known Francis surfaces; it is not capability completion.",
        },
        "exposure_summary": {
            "kind": "developer_bridge.francis_body_exposure_summary",
            "schema_version": "developer_bridge_francis_body_exposure_summary_v1",
            "surface": "developer_bridge.francis_body_map.exposure_summary",
            "status": "warming",
            "francis1_can_see_body": True,
            "francis1_can_use_all_visible_surfaces": False,
            "visible_surface_count": 0,
            "readback_connected_surface_count": 0,
            "connected_to_local_model_count": 0,
            "capability_granted_count": 0,
            "safe_for_capability_use_count": 0,
            "not_exposed_surface_count": 0,
            "review_required_surface_count": 0,
            "grant_required_before_use_count": 0,
            "detached_memory_surface_count": 0,
            "visible_surface_ids": [],
            "readback_connected_surface_ids": [],
            "connected_to_local_model_surface_ids": [],
            "granted_surface_ids": [],
            "safe_for_capability_use_surface_ids": [],
            "not_exposed_surface_ids": [],
            "review_required_surface_ids": [],
            "grant_required_before_use_surface_ids": [],
            "detached_memory_surface_ids": [],
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
            "next_readbacks": [],
        },
        "evidence": {
            "manifest_observed": False,
            "ledger_observed": False,
            "trust_ladder_observed": False,
            "runtime_restart_observed": False,
            "body_coverage_review_observed": False,
            "canonical_plane_count": 0,
            "canonical_plane_covered_count": 0,
            "missing_canonical_plane_ids": [],
            "coverage_open_gap_count": 0,
            "latest_runtime_prompt_id": "",
            "latest_runtime_response_id": "",
            "latest_ledger_entry": "",
        },
        "coverage_review": {
            "kind": "developer_bridge.francis_body_coverage_review",
            "schema_version": "developer_bridge_francis_body_coverage_review_v1",
            "surface": "developer_bridge.francis_body_map.coverage_review",
            "observed": False,
            "status": "warming",
            "coverage_complete": False,
            "capability_complete": False,
            "canonical_source": "docs/canonical/BUILD_MANIFEST.md + docs/PLANES.md + meta/plane_map.yaml",
            "canonical_sources_observed": False,
            "plane_count": 0,
            "covered_plane_count": 0,
            "missing_plane_ids": [],
            "open_gap_count": 0,
            "items": [],
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "runtime_observation": {
            "surface": "developer_bridge.collaboration_prompts",
            "observed": False,
            "prompt_observed": False,
            "response_observed": False,
            "prompt_id": "",
            "response_id": "",
            "output_guard_rewrite_observed": False,
            "stores_full_transcript": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "capability_grants": {
            "surface": "developer_bridge.francis_capability_grants",
            "route": "/developer-bridge/francis-capability-grants",
            "connected": False,
            "active_grants_present": False,
            "granted_count": 0,
            "denied_or_revoked_count": 0,
            "deny_after_grant_supported": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "governance": {
            "read_only": True,
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
        },
    }


def _empty_trust_ladder_payload(
    *,
    limit: int = 10,
    session_id: str = "",
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.francis_trust_ladder",
        "schema_version": "developer_bridge_francis_trust_ladder_v1",
        "ok": True,
        "mode": "read_only",
        "surface": "developer_bridge.francis_trust_ladder",
        "items": [],
        "count": 0,
        "summary": {
            "allowed_decisions": ["wire_existing", "build_missing", "tune_prompt_guard", "reject_as_drift"],
            "decision_counts": {
                "wire_existing": 0,
                "build_missing": 0,
                "tune_prompt_guard": 0,
                "reject_as_drift": 0,
            },
            "request_count": 0,
            "requests_with_existing_surface": 0,
            "requests_requiring_build_or_wiring_review": 0,
            "requests_requiring_prompt_guard": 0,
            "requests_rejected_as_drift": 0,
            "grants_any_authority": False,
        },
        "filters": {
            "limit": limit,
            "session_id": session_id,
        },
        "definitions": {
            "wire_existing": "A concrete Francis surface already exists; typed review is still required.",
            "build_missing": "The cited surface is not verified; repo-truth review is required before a minimal build.",
            "tune_prompt_guard": "The need is mostly model drift or repeated prompt failure.",
            "reject_as_drift": "The need is too generic, invented, conflicted, or unsafe to become build direction.",
        },
        "governance": {
            "read_only": True,
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
        },
    }


def _empty_capability_grants_payload(
    *,
    surface_id: str = "",
) -> dict[str, object]:
    return {
        "kind": "developer_bridge.francis_capability_grants",
        "schema_version": "developer_bridge_francis_capability_grants_v1",
        "ok": True,
        "mode": "readback_and_operator_receipts",
        "surface": "developer_bridge.francis_capability_grants",
        "state_path": "integrations/developer_bridge/capability_grants/state.json",
        "known_surfaces": [],
        "allowed_decisions": ["grant", "deny", "revoke"],
        "allowed_access_modes": ["observe", "read", "request", "propose_plan"],
        "items": [],
        "count": 0,
        "summary": {
            "surface_count": 0,
            "granted_count": 0,
            "denied_or_revoked_count": 0,
            "active_grants_present": False,
            "deny_after_grant_supported": True,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
        "receipts": [],
        "filters": {"surface_id": surface_id},
        "definitions": {
            "grant": "Permit a named low-risk Francis body surface to be exposed as local-model capability context.",
            "deny": "Keep or place the surface outside local-model capability use.",
            "revoke": "Remove a prior grant while retaining the bounded decision receipt for tuning review.",
        },
        "governance": {
            "read_only": True,
            "writes_capability_grant_state": False,
            "writes_bounded_receipt": False,
            "executes_prompt": False,
            "calls_model": False,
            "trains_model": False,
            "client_can_be_operator_console": True,
            "client_is_automatic_execution_authority": False,
            "requires_operator_review": True,
            "grants_capability_authority": False,
            "grants_execution_authority": False,
            "grants_mutation_authority": False,
            "grants_approval_authority": False,
            "grants_memory_write_authority": False,
            "grants_training_authority": False,
        },
    }


@router.get("/status")
def status() -> dict[str, object]:
    return _call_read_only(repo_status)


@router.get("/read-file")
def read_file(
    path: str = Query(..., min_length=1),
    max_bytes: int = Query(256_000, ge=1, le=256_000),
) -> dict[str, object]:
    return _call_read_only(read_repo_file, path, max_bytes=max_bytes)


@router.get("/search")
def search(
    query: str = Query(..., min_length=1),
    max_results: int = Query(20, ge=1, le=100),
) -> dict[str, object]:
    return _call_read_only(search_repo, query, max_results=max_results)


@router.get("/git-diff-summary")
def diff_summary() -> dict[str, object]:
    return _call_read_only(git_diff_summary)


@router.get("/completion-ledger")
def completion_ledger(max_bytes: int = Query(256_000, ge=1, le=256_000)) -> dict[str, object]:
    return _call_read_only(read_completion_ledger, max_bytes=max_bytes)


@router.get("/supervised-exec-receipt")
def supervised_exec_receipt(
    run_id: str = Query(..., min_length=1),
    filename: str = Query("result.json", min_length=1),
    max_bytes: int = Query(256_000, ge=1, le=256_000),
) -> dict[str, object]:
    return _call_read_only(read_supervised_exec_receipt, run_id, filename=filename, max_bytes=max_bytes)


def collaboration_transcript(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    return _read_only_json_response(
        read_collaboration_transcript,
        agent=agent,
        source_agent=source_agent,
        target_agent=target_agent,
        status=status,
        limit=limit,
    )


def collaboration_review(
    limit: int = Query(10, ge=1, le=50),
    session_id: str = "",
) -> Response:
    return _read_only_json_response(read_collaboration_review, limit=limit, session_id=session_id)


def collaboration_learning(
    limit: int = Query(10, ge=1, le=50),
    failure_type: str = "",
    term: str = "",
    session_id: str = "",
) -> Response:
    return _read_only_json_response(
        read_collaboration_learning_events,
        limit=limit,
        failure_type=failure_type,
        term=term,
        session_id=session_id,
    )


def collaboration_runtime_health() -> Response:
    return _read_only_json_response(read_collaboration_runtime_health)


def collaboration_sessions(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = Query(10, ge=1, le=20),
    item_limit: int = Query(50, ge=1, le=50),
) -> Response:
    return _read_only_json_response(
        read_collaboration_sessions,
        agent=agent,
        source_agent=source_agent,
        target_agent=target_agent,
        status=status,
        limit=limit,
        item_limit=item_limit,
    )


def collaboration_agents() -> Response:
    return _read_only_json_response(collaboration_agents_status)


def francis_body_map() -> Response:
    return _read_only_json_response(read_francis_body_map)


def francis_trust_ladder(
    limit: int = Query(10, ge=1, le=50),
    session_id: str = "",
) -> Response:
    return _read_only_json_response(read_francis_trust_ladder, limit=limit, session_id=session_id)


@router.get("/collaboration-transcript")
def collaboration_transcript_route(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = Query(20, ge=1, le=50),
) -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_transcript",
        read_collaboration_transcript,
        _empty_transcript_payload,
        agent=agent,
        source_agent=source_agent,
        target_agent=target_agent,
        status=status,
        limit=limit,
    )


@router.get("/collaboration-review")
def collaboration_review_route(
    limit: int = Query(10, ge=1, le=50),
    session_id: str = "",
) -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_review",
        read_collaboration_review,
        _empty_review_payload,
        limit=limit,
        session_id=session_id,
    )


@router.get("/collaboration-learning")
def collaboration_learning_route(
    limit: int = Query(10, ge=1, le=50),
    failure_type: str = "",
    term: str = "",
    session_id: str = "",
) -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_learning_events",
        read_collaboration_learning_events,
        _empty_learning_payload,
        limit=limit,
        failure_type=failure_type,
        term=term,
        session_id=session_id,
    )


@router.get("/collaboration-runtime-health")
def collaboration_runtime_health_route() -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_runtime_health",
        read_collaboration_runtime_health,
        _empty_runtime_health_payload,
    )


@router.get("/collaboration-substrate-readiness")
def collaboration_substrate_readiness_route() -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_substrate_readiness",
        read_collaboration_substrate_readiness,
        _empty_substrate_readiness_payload,
    )


@router.get("/francis-body-map")
def francis_body_map_route() -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.francis_body_map",
        read_francis_body_map,
        _empty_body_map_payload,
    )


@router.get("/francis-trust-ladder")
def francis_trust_ladder_route(
    limit: int = Query(10, ge=1, le=50),
    session_id: str = "",
) -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.francis_trust_ladder",
        read_francis_trust_ladder,
        _empty_trust_ladder_payload,
        limit=limit,
        session_id=session_id,
    )


@router.get("/francis-capability-grants")
def francis_capability_grants_route(surface_id: str = "") -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.francis_capability_grants",
        read_francis_capability_grants,
        _empty_capability_grants_payload,
        surface_id=surface_id,
    )


@router.get("/collaboration-sessions")
def collaboration_sessions_route(
    agent: str = "",
    source_agent: str = "",
    target_agent: str = "",
    status: str = "",
    limit: int = Query(10, ge=1, le=20),
    item_limit: int = Query(50, ge=1, le=50),
) -> Response:
    return _cached_read_only_json_response(
        "developer_bridge.collaboration_sessions",
        read_collaboration_sessions,
        _empty_sessions_payload,
        agent=agent,
        source_agent=source_agent,
        target_agent=target_agent,
        status=status,
        limit=limit,
        item_limit=item_limit,
    )


@router.get("/collaboration-agents")
async def collaboration_agents_route() -> Response:
    return collaboration_agents()


@router.post("/collaboration-agents/toggle")
def collaboration_agent_toggle(payload: CollaborationAgentToggleIn) -> dict[str, object]:
    return _call_read_only(
        set_collaboration_agent_enabled,
        payload.agent,
        payload.enabled,
        actor=payload.actor,
        reason=payload.reason,
    )


@router.post("/francis-capability-grants")
def francis_capability_grant(payload: FrancisCapabilityGrantIn) -> dict[str, object]:
    result = _call_read_only(
        set_francis_capability_grant,
        payload.surface_id,
        payload.decision,
        requested_access_mode=payload.requested_access_mode,
        actor=payload.actor,
        reason=payload.reason,
        source_review_item_id=payload.source_review_item_id,
    )
    if result.get("ok") is True:
        _invalidate_readback_cache(
            "developer_bridge.francis_capability_grants",
            "developer_bridge.francis_body_map",
            "developer_bridge.collaboration_substrate_readiness",
        )
    return result
