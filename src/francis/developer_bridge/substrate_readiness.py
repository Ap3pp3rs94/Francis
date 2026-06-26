from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from francis.developer_bridge.body_map import read_francis_body_map
from francis.developer_bridge.collaboration_driver import (
    read_collaboration_exploration,
    read_collaboration_learning_events,
)
from francis.developer_bridge.collaboration_runtime import read_collaboration_runtime_health
from francis.developer_bridge.trust_ladder import read_francis_trust_ladder

_KIND = "developer_bridge.collaboration_substrate_readiness"
_SCHEMA_VERSION = "developer_bridge_collaboration_substrate_readiness_v1"
_ALIGNMENT_SOURCES = [
    "docs/operations/COMPLETION_LEDGER.md",
    "docs/canonical/BUILD_MANIFEST.md",
]
_PROMPT_CHECK_ID = "collaboration_substrate_readiness.roadmap_alignment"
_PROMPT_CHECK_READBACK = "/developer-bridge/collaboration-substrate-readiness roadmap_alignment"


def read_collaboration_substrate_readiness() -> dict[str, object]:
    """Read whether the collaboration substrate is safe to use as build direction."""

    body = read_francis_body_map()
    runtime = read_collaboration_runtime_health()
    trust = read_francis_trust_ladder(limit=10)
    learning = read_collaboration_learning_events(limit=3)
    exploration = read_collaboration_exploration(limit=3)

    body_summary = _dict(body.get("summary"))
    body_phase = _dict(body.get("phase"))
    body_quest = _dict(body.get("quest"))
    body_evidence = _dict(body.get("evidence"))
    coverage_review = _dict(body.get("coverage_review"))
    runtime_loop = _dict(runtime.get("collaboration_loop"))
    runtime_learning_signal = _dict(runtime_loop.get("current_learning_signal"))
    trust_summary = _dict(trust.get("summary"))
    learning_items = [item for item in _list(learning.get("items")) if isinstance(item, dict)]
    exploration_items = [item for item in _list(exploration.get("items")) if isinstance(item, dict)]

    coverage_open_gap_count = _int(
        body_summary.get("coverage_open_gap_count"),
        default=_int(coverage_review.get("open_gap_count")),
    )
    open_orb_gaps = _open_orb_gaps(coverage_review)
    bounded_wiring_percent = _int(body_quest.get("percent_complete"))
    runtime_healthy = _str(runtime.get("status")) == "healthy"
    trust_ladder_enforced = bool(body_summary.get("trust_ladder_enforced")) and not bool(
        trust_summary.get("grants_any_authority")
    )
    phase_blocks_main_build_prompt = _phase_blocks_main_build_prompt(
        current=_str(body_phase.get("current")),
        posture=_str(body_phase.get("posture")),
    )
    no_authority_granted = _no_authority_granted(
        body=body,
        runtime=runtime,
        trust=trust,
        learning=learning,
        learning_items=learning_items,
        exploration=exploration,
        exploration_items=exploration_items,
    )
    learning_bounded = _learning_bounded(runtime_learning_signal=runtime_learning_signal, learning_items=learning_items)

    checklist = [
        _check(
            "ledger_observed",
            "Completion ledger observed",
            bool(body_evidence.get("ledger_observed")),
            evidence=_str(body_evidence.get("latest_ledger_entry")) or "docs/operations/COMPLETION_LEDGER.md",
            detail="Read the shipped posture before treating conversation output as build direction.",
        ),
        _check(
            "manifest_observed",
            "Canonical build manifest observed",
            bool(body_evidence.get("manifest_observed")),
            evidence=_str(body_phase.get("source")) or "docs/canonical/BUILD_MANIFEST.md",
            detail="Read the Phase 2 ORB build posture before prompting main Francis build work.",
        ),
        _check(
            "body_map_visible",
            "Francis1 body map visible without authority",
            bool(body_summary.get("full_body_visible")) and not bool(body_summary.get("full_body_authority_granted")),
            evidence=f"{_int(body_summary.get('surface_count'))} surfaces; authority=false",
            detail="Whole-body awareness is read-only and does not grant capability use.",
        ),
        _check(
            "trust_ladder_enforced",
            "Trust ladder enforced",
            trust_ladder_enforced,
            evidence=f"{_int(trust_summary.get('request_count'))} recent requests classified",
            detail="Capability needs stay observe/read/request/propose-gated until reviewed.",
        ),
        _check(
            "runtime_health_observed",
            "Collaboration runtime healthy",
            runtime_healthy,
            failure_status="warning",
            evidence=f"status={_str(runtime.get('status'), default='unknown')}; turns={_int(runtime_loop.get('turn_count'))}",
            detail="The recurring conversation can be watched, but health is not build authority.",
        ),
        _check(
            "learning_receipts_bounded",
            "Learning receipts bounded",
            learning_bounded,
            failure_status="warning",
            evidence=f"{len(learning_items)} learning receipts; stores_full_transcript=false; training=false",
            detail="Model drift receipts are review inputs, not automatic memory or training authority.",
        ),
        _check(
            "exploration_receipts_bounded",
            "Exploration receipts bounded",
            _exploration_bounded(exploration=exploration, exploration_items=exploration_items),
            failure_status="warning",
            evidence=f"{len(exploration_items)} exploration receipts; access request only; execution=false",
            detail="Francis1 can surface walls and next probes while Codex stays the guide and validator.",
        ),
        _check(
            "coverage_gaps_reviewed",
            "Open ORB coverage gaps reviewed",
            coverage_open_gap_count == 0,
            failure_status="blocked",
            evidence=f"{coverage_open_gap_count} open gaps",
            detail="Open coverage gaps block any unsupervised main Francis build prompt.",
            blocks_main_build_prompt=True,
        ),
        _check(
            "phase_posture_reviewed",
            "Phase posture still blocks main-build prompting",
            not phase_blocks_main_build_prompt,
            failure_status="blocked",
            evidence=f"{_str(body_phase.get('current'), default='unknown')}: {_str(body_phase.get('posture'), default='unknown')}",
            detail="Phase 2 partial posture requires Codex/operator review before main build prompting.",
            blocks_main_build_prompt=True,
        ),
    ]

    blocking_items = [item for item in checklist if item["blocks_main_build_prompt"] and item["status"] != "passed"]
    collaboration_substrate_wired = (
        bounded_wiring_percent >= 100
        and bool(body_summary.get("full_body_visible"))
        and trust_ladder_enforced
        and runtime_healthy
        and no_authority_granted
    )
    main_build_prompt_allowed = collaboration_substrate_wired and not blocking_items
    main_build_prompt_gate = "none" if main_build_prompt_allowed else _main_build_prompt_gate(blocking_items)
    status = _status_for(
        collaboration_substrate_wired=collaboration_substrate_wired,
        main_build_prompt_allowed=main_build_prompt_allowed,
        blocking_items=blocking_items,
    )

    return {
        "kind": _KIND,
        "schema_version": _SCHEMA_VERSION,
        "ok": True,
        "mode": "read_only",
        "surface": _KIND,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "required_alignment_sources": list(_ALIGNMENT_SOURCES),
        "collaboration_substrate_wired": collaboration_substrate_wired,
        "bounded_wiring_percent_complete": bounded_wiring_percent,
        "main_build_prompt_allowed": main_build_prompt_allowed,
        "main_build_prompt_gate": main_build_prompt_gate,
        "coverage_open_gap_count": coverage_open_gap_count,
        "open_orb_gap_plane_ids": [_str(item.get("plane_id")) for item in open_orb_gaps],
        "trust_ladder_enforced": trust_ladder_enforced,
        "runtime_healthy": runtime_healthy,
        "learning_receipts_bounded": learning_bounded,
        "no_authority_granted": no_authority_granted,
        "summary": {
            "collaboration_substrate_wired": collaboration_substrate_wired,
            "bounded_wiring_percent_complete": bounded_wiring_percent,
            "main_build_prompt_allowed": main_build_prompt_allowed,
            "main_build_prompt_gate": main_build_prompt_gate,
            "coverage_open_gap_count": coverage_open_gap_count,
            "open_orb_gap_plane_ids": [_str(item.get("plane_id")) for item in open_orb_gaps],
            "trust_ladder_enforced": trust_ladder_enforced,
            "runtime_healthy": runtime_healthy,
            "learning_receipts_bounded": learning_bounded,
            "no_authority_granted": no_authority_granted,
        },
        "roadmap_alignment": _roadmap_alignment(
            ledger_observed=bool(body_evidence.get("ledger_observed")),
            manifest_observed=bool(body_evidence.get("manifest_observed")),
            main_build_prompt_allowed=main_build_prompt_allowed,
            main_build_prompt_gate=main_build_prompt_gate,
            blocking_items=blocking_items,
            open_orb_gaps=open_orb_gaps,
        ),
        "checklist": checklist,
        "blocking_items": [item["id"] for item in blocking_items],
        "open_orb_gaps": open_orb_gaps,
        "next_action": (
            "Read the completion ledger and build manifest, review open ORB gaps, and keep any main Francis "
            "build prompt candidate-only until Codex/operator review clears the gap."
        ),
        "definitions": {
            "collaboration_substrate_wired": (
                "The Codex/Francis1 relay, body map, trust ladder, runtime health, and no-authority guard are visible."
            ),
            "main_build_prompt_allowed": (
                "Whether this readback allows the collaboration loop to prompt unsupervised main Francis build work."
            ),
            "blocking_items": "Checklist items that block main-build prompting even when the relay wiring is complete.",
            "roadmap_alignment": (
                "Ledger-first readback proving whether a main Francis build prompt must remain candidate-only."
            ),
            "open_orb_gaps": (
                "Bounded per-plane ORB coverage gaps derived from the Francis body-map coverage review; "
                "these are review inputs, not authority grants."
            ),
        },
        "source_readbacks": {
            "body_map": "developer_bridge.francis_body_map",
            "runtime_health": "developer_bridge.collaboration_runtime_health",
            "trust_ladder": "developer_bridge.francis_trust_ladder",
            "learning": "developer_bridge.collaboration_driver.learning_events",
            "exploration": "developer_bridge.collaboration_driver.explorations",
            "roadmap_alignment": _PROMPT_CHECK_READBACK,
        },
        "governance": _governance(),
    }


def _check(
    id_: str,
    label: str,
    passed: bool,
    *,
    evidence: str,
    detail: str,
    failure_status: str = "missing",
    blocks_main_build_prompt: bool = False,
) -> dict[str, object]:
    return {
        "id": id_,
        "label": label,
        "status": "passed" if passed else failure_status,
        "evidence": evidence,
        "detail": detail,
        "blocks_main_build_prompt": blocks_main_build_prompt,
    }


def _status_for(
    *,
    collaboration_substrate_wired: bool,
    main_build_prompt_allowed: bool,
    blocking_items: list[dict[str, object]],
) -> str:
    if main_build_prompt_allowed:
        return "main_build_prompt_allowed"
    if blocking_items:
        return "blocked"
    if collaboration_substrate_wired:
        return "ready_for_review"
    return "needs_wiring"


def _main_build_prompt_gate(blocking_items: list[dict[str, object]]) -> str:
    ids = {_str(item.get("id")) for item in blocking_items}
    if "coverage_gaps_reviewed" in ids:
        return "blocked_by_open_orb_gaps"
    if "phase_posture_reviewed" in ids:
        return "blocked_by_partial_phase_posture"
    return "requires_alignment_review"


def _roadmap_alignment(
    *,
    ledger_observed: bool,
    manifest_observed: bool,
    main_build_prompt_allowed: bool,
    main_build_prompt_gate: str,
    blocking_items: list[dict[str, object]],
    open_orb_gaps: list[dict[str, object]],
) -> dict[str, object]:
    sources_observed = ledger_observed and manifest_observed
    if main_build_prompt_allowed:
        status = "aligned_for_main_build_prompt"
    elif not sources_observed:
        status = "missing_alignment_sources"
    else:
        status = "blocked_candidate_only"
    return {
        "status": status,
        "required_sources": list(_ALIGNMENT_SOURCES),
        "source_order": list(_ALIGNMENT_SOURCES),
        "prompt_check_id": _PROMPT_CHECK_ID,
        "prompt_check_readback": _PROMPT_CHECK_READBACK,
        "prompt_check_required": True,
        "ledger_first": True,
        "ledger_observed": ledger_observed,
        "manifest_observed": manifest_observed,
        "sources_observed": sources_observed,
        "main_build_prompt_allowed": main_build_prompt_allowed,
        "main_build_prompt_gate": main_build_prompt_gate,
        "candidate_only_until_review": not main_build_prompt_allowed,
        "blocks_main_build_prompt": bool(blocking_items),
        "blocking_items": [_str(item.get("id")) for item in blocking_items if _str(item.get("id"))],
        "open_orb_gap_count": len(open_orb_gaps),
        "open_orb_gap_plane_ids": [_str(item.get("plane_id")) for item in open_orb_gaps if _str(item.get("plane_id"))],
        "next_check": (
            f"Run {_PROMPT_CHECK_ID}: read docs/operations/COMPLETION_LEDGER.md first, compare it against "
            "docs/canonical/BUILD_MANIFEST.md, confirm phase posture and ORB blockers, and keep any main "
            "Francis build prompt candidate-only unless the gate is clear."
        ),
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
        "grants_approval_authority": False,
        "grants_memory_write_authority": False,
    }


def _open_orb_gaps(coverage_review: dict[str, object]) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []
    for raw_item in _list(coverage_review.get("items")):
        item = _dict(raw_item)
        remaining_gaps = [_str(value) for value in _list(item.get("remaining_gaps")) if _str(value)]
        if not remaining_gaps:
            continue
        gaps.append(
            {
                "plane_id": _str(item.get("plane_id")),
                "plane_name": _str(item.get("plane_name")),
                "body_surface_id": _str(item.get("body_surface_id")),
                "current_posture": _str(item.get("current_posture")),
                "risk_level": _str(item.get("risk_level")),
                "risk_statement": _str(item.get("risk_statement")),
                "remaining_gaps": remaining_gaps[:4],
                "next_review_artifact": _str(item.get("next_review_artifact")),
                "recommended_next_action": _str(item.get("recommended_next_action")),
                "blocks_main_build_prompt": True,
                "grants_execution_authority": False,
                "grants_mutation_authority": False,
                "grants_approval_authority": False,
                "grants_memory_write_authority": False,
                "grants_training_authority": False,
            }
        )
    return gaps[:12]


def _phase_blocks_main_build_prompt(*, current: str, posture: str) -> bool:
    text = f"{current} {posture}".lower()
    return "phase 2" in text or "partial" in text or "not yet" in text


def _learning_bounded(
    *,
    runtime_learning_signal: dict[str, object],
    learning_items: list[dict[str, object]],
) -> bool:
    if runtime_learning_signal and not _record_has_no_authority(runtime_learning_signal):
        return False
    for item in learning_items:
        writer_governance = _dict(item.get("writer_governance"))
        if writer_governance and not _record_has_no_authority(writer_governance):
            return False
        if bool(writer_governance.get("stores_full_transcript")):
            return False
    return True


def _exploration_bounded(
    *,
    exploration: dict[str, object],
    exploration_items: list[dict[str, object]],
) -> bool:
    if not _record_has_no_authority(_dict(exploration.get("governance"))):
        return False
    for item in exploration_items:
        if not _record_has_no_authority(_dict(item.get("governance"))):
            return False
        if not _record_has_no_authority(_dict(item.get("access_boundary"))):
            return False
    return True


def _no_authority_granted(
    *,
    body: dict[str, object],
    runtime: dict[str, object],
    trust: dict[str, object],
    learning: dict[str, object],
    learning_items: list[dict[str, object]],
    exploration: dict[str, object],
    exploration_items: list[dict[str, object]],
) -> bool:
    body_summary = _dict(body.get("summary"))
    if bool(body_summary.get("full_body_authority_granted")):
        return False
    if not _record_has_no_authority(_dict(body.get("governance"))):
        return False
    if not _record_has_no_authority(_dict(runtime.get("governance"))):
        return False
    if bool(_dict(trust.get("summary")).get("grants_any_authority")):
        return False
    if not _record_has_no_authority(_dict(trust.get("governance"))):
        return False
    if not _record_has_no_authority(_dict(learning.get("governance"))):
        return False
    return _learning_bounded(
        runtime_learning_signal=_dict(_dict(runtime.get("collaboration_loop")).get("current_learning_signal")),
        learning_items=learning_items,
    ) and _exploration_bounded(exploration=exploration, exploration_items=exploration_items)


def _record_has_no_authority(record: dict[str, object]) -> bool:
    deny_keys = (
        "executes_prompt",
        "calls_model",
        "trains_model",
        "stores_full_transcript",
        "grants_any_authority",
        "grants_execution_authority",
        "grants_mutation_authority",
        "grants_approval_authority",
        "grants_memory_write_authority",
        "grants_training_authority",
        "grants_model_authority",
        "grants_model_execution_authority",
        "grants_repo_mutation_authority",
        "grants_capability_authority",
    )
    return not any(bool(record.get(key)) for key in deny_keys)


def _governance() -> dict[str, object]:
    return {
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
    }


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []


def _str(value: object, *, default: str = "") -> str:
    if value is None:
        return default
    text = str(value)
    return text if text else default


def _int(value: object, *, default: int = 0) -> int:
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
