"""Governed desktop organization contracts for Orb-mediated action.

This module intentionally does not execute mouse, shell, filesystem, UIA, or
window mutations. It defines the first fail-closed gate for desktop
organization so future actuators cannot bypass Lens semantics, plan approval,
or reversibility evidence.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Callable

from francis.governance.redaction import redact_secret_text
from francis.kernel.paths import data_dir

LENS_DESKTOP_ICON_SEMANTICS_KIND = "lens.orb.desktop_organization.semantic_targets"
LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND = "lens.orb.desktop_organization.position_evidence"
LENS_DESKTOP_ORGANIZATION_REVERSAL_EVIDENCE_KIND = "lens.orb.desktop_organization.reversal_evidence"
LENS_DESKTOP_ORGANIZATION_SCOPE = "lens.orb.desktop_organization"
LENS_DESKTOP_ORGANIZATION_PLAN_KIND = "lens.orb.desktop_organization.plan"
LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND = "lens.orb.desktop_organization.orb_sequence"
LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_RUN_KIND = "lens.orb.desktop_organization.orb_sequence.run"
LENS_DESKTOP_ORGANIZATION_ORB_ITEM_ACTUATION_KIND = "lens.orb.desktop_organization.orb_sequence.item_actuation"
LENS_DESKTOP_ORGANIZATION_EXECUTION_KIND = "lens.orb.desktop_organization.execution_preflight"
LENS_DESKTOP_ORGANIZATION_ROUTE = "/lens/orb/desktop-organization"
LENS_DESKTOP_ORGANIZATION_EXECUTE_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_EXECUTE_ENABLE"
LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENABLE"
LENS_DESKTOP_ORGANIZATION_CURSOR_CAPABILITY_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_CURSOR_ENABLE"
LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENABLE"

_ICON_TARGET_KINDS = frozenset({"desktop_icon", "file_icon", "folder_icon", "shortcut_icon"})
_MAX_TARGETS = 80
_DEFAULT_ICON_WIDTH = 96
_DEFAULT_ICON_HEIGHT = 96
_DEFAULT_GRID_GAP = 16
_CARRY_FRAME_COUNT = 6
_DESKTOP_ROOT_ENV = "FRANCIS_LENS_DESKTOP_SEMANTIC_ROOTS"
_DESKTOP_ORGANIZATION_EXCLUDED_LABELS_ENV = "FRANCIS_LENS_DESKTOP_ORGANIZATION_EXCLUDED_LABELS"
_GAME_TARGET_ID_ENV = "FRANCIS_LENS_GAME_TARGET_ID"
_GAME_TARGET_PROCESSES_ENV = "FRANCIS_LENS_GAME_TARGET_PROCESSES"
_POSITION_EVIDENCE_RELATIVE_PATH = "runtime/lens-perception/desktop-icon-position-evidence.json"
_POSITION_EVIDENCE_SOURCES = frozenset(
    {
        "uia_shell_desktop_snapshot",
        "shell_desktop_listview_snapshot",
        "lens_desktop_icon_position_fixture",
    }
)


def lens_desktop_icon_semantic_targets(
    *,
    limit: Any = _MAX_TARGETS,
    roots: Any = None,
) -> dict[str, Any]:
    """Return a bounded semantic inventory of desktop icons.

    This reads directory metadata only from desktop roots. It does not read file
    contents, expose raw paths, capture pixels, call UI Automation, or execute
    input. Screen rectangles remain unavailable until a later Lens semantic
    watcher maps shell/UIA positions.
    """

    safe_limit = _safe_int(limit, default=_MAX_TARGETS, lower=1, upper=_MAX_TARGETS)
    desktop_roots = _desktop_roots(roots)
    sources: list[dict[str, Any]] = []
    targets: list[dict[str, Any]] = []
    blockers: list[str] = []

    for source_index, root in enumerate(desktop_roots):
        source_scope = _desktop_source_scope(root, source_index)
        source = {
            "scope": source_scope,
            "exists": root.exists(),
            "readable": False,
            "raw_path_stored": False,
            "file_contents_read": False,
        }
        if not root.exists():
            sources.append(source)
            continue
        if not root.is_dir():
            source["status"] = "not_directory"
            sources.append(source)
            blockers.append("desktop_semantic_root_not_directory")
            continue
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            source["status"] = "unreadable"
            sources.append(source)
            blockers.append("desktop_semantic_root_unreadable")
            continue

        source["readable"] = True
        source["status"] = "readable"
        source["candidate_count"] = len(children)
        sources.append(source)
        for child in children:
            if len(targets) >= safe_limit:
                blockers.append("desktop_semantic_target_limit_reached")
                break
            target = _desktop_child_target(child, source_scope=source_scope)
            if target:
                targets.append(target)

    if not targets:
        blockers.append("desktop_semantic_targets_missing")

    organization_blockers = [
        "desktop_icon_screen_rect_mapping_not_ready",
        "desktop_reversibility_evidence_not_captured",
        "desktop_plan_approval_required",
    ]
    return {
        "kind": LENS_DESKTOP_ICON_SEMANTICS_KIND,
        "status": "ready" if targets else "blocked",
        "ready": bool(targets),
        "semantic_target_count": len(targets),
        "semantic_targets": targets,
        "sources": sources,
        "blockers": _dedupe(blockers),
        "organization_ready": False,
        "organization_blockers": organization_blockers,
        "governance": _semantic_governance(),
    }


def lens_desktop_icon_position_evidence(
    *,
    limit: Any = _MAX_TARGETS,
    roots: Any = None,
    semantic_readback: dict[str, Any] | None = None,
    position_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge semantic desktop targets with bounded screen-rectangle evidence."""

    semantic = semantic_readback or lens_desktop_icon_semantic_targets(limit=limit, roots=roots)
    targets = _target_items(semantic.get("semantic_targets"))
    evidence = position_evidence if position_evidence is not None else _read_position_evidence()
    evidence_targets = _target_items(evidence.get("targets"))
    blockers = _string_items(semantic.get("blockers"))
    source = _safe_text(evidence.get("source"), limit=120)
    evidence_id = _safe_text(evidence.get("evidence_id"), limit=160)
    if not evidence:
        blockers.append("desktop_icon_position_evidence_missing")
    if evidence and evidence.get("kind") != LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND:
        blockers.append("desktop_icon_position_evidence_kind_invalid")
    if evidence and source not in _POSITION_EVIDENCE_SOURCES:
        blockers.append("desktop_icon_position_evidence_source_invalid")
    if evidence and not evidence_id:
        blockers.append("desktop_icon_position_evidence_id_required")

    evidence_by_id: dict[str, dict[str, Any]] = {}
    for item in evidence_targets:
        target_id = _safe_text(item.get("target_id"), limit=120)
        if target_id:
            evidence_by_id[target_id] = {**item, "source": source, "evidence_id": evidence_id}

    mapped_targets: list[dict[str, Any]] = []
    mapped_count = 0
    for target in targets:
        target_id = _safe_text(target.get("target_id"), limit=120)
        match = evidence_by_id.get(target_id, {})
        mapped, target_blockers = _mapped_position_target(target, match)
        mapped_targets.append(mapped)
        blockers.extend(target_blockers)
        if mapped.get("screen_rect_available") is True:
            mapped_count += 1

    known_target_ids = {_safe_text(target.get("target_id"), limit=120) for target in targets}
    for item in evidence_targets:
        evidence_target_id = _safe_text(item.get("target_id"), limit=120)
        if evidence_target_id and evidence_target_id not in known_target_ids:
            blockers.append("desktop_icon_position_evidence_target_mismatch")

    all_targets_mapped = bool(targets) and mapped_count == len(targets)
    organization_blockers = [
        "desktop_reversibility_evidence_not_captured",
        "desktop_plan_approval_required",
    ]
    if not all_targets_mapped:
        organization_blockers.insert(0, "desktop_icon_screen_rect_mapping_not_ready")

    return {
        "kind": LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND,
        "status": "ready" if all_targets_mapped and not _blocking_evidence_errors(blockers) else "blocked",
        "ready": all_targets_mapped and not _blocking_evidence_errors(blockers),
        "position_evidence_ready": all_targets_mapped and not _blocking_evidence_errors(blockers),
        "evidence_id": evidence_id,
        "evidence_source": source,
        "semantic_target_count": len(targets),
        "mapped_target_count": mapped_count,
        "semantic_targets": mapped_targets,
        "blockers": _dedupe(blockers),
        "organization_ready": False,
        "organization_blockers": organization_blockers,
        "governance": _position_governance(),
    }


def propose_desktop_organization_plan(
    *,
    actor: Any,
    objective: Any,
    targets: Any,
    workspace: Any,
    max_steps: Any = 40,
) -> dict[str, Any]:
    """Create a bounded, non-mutating organization plan from semantic targets."""

    safe_actor = _safe_text(actor, limit=120) or "unknown"
    safe_objective = _redacted_text(objective, limit=240) or "organize desktop"
    safe_max_steps = _safe_int(max_steps, default=40, lower=1, upper=_MAX_TARGETS)
    workspace_bounds, workspace_blockers = _workspace_bounds(workspace)
    semantic_targets, target_blockers = _semantic_icon_targets(targets)
    blockers = [*workspace_blockers, *target_blockers]

    if not semantic_targets:
        blockers.append("lens_semantic_target_mapping_required")
    if len(semantic_targets) > safe_max_steps:
        blockers.append("desktop_organization_step_budget_exceeded")

    blockers = _dedupe(blockers)
    if blockers:
        return _plan_response(
            actor=safe_actor,
            objective=safe_objective,
            status="denied",
            ok=False,
            blockers=blockers,
            workspace=workspace_bounds,
            targets=semantic_targets,
            plan={},
        )

    ordered_targets = sorted(
        semantic_targets,
        key=lambda item: (
            str(item.get("target_kind")),
            str(item.get("label_summary")).casefold(),
            str(item.get("target_id")),
        ),
    )
    steps = _layout_steps(ordered_targets, workspace_bounds)
    plan_id = f"desktop-org-plan-{_digest({'objective': safe_objective, 'steps': steps})}"
    plan = {
        "kind": LENS_DESKTOP_ORGANIZATION_PLAN_KIND,
        "plan_id": plan_id,
        "status": "plan_proposed",
        "objective_summary": safe_objective,
        "target_count": len(ordered_targets),
        "step_count": len(steps),
        "steps": steps,
        "requires_plan_level_approval": True,
        "requires_pre_state": True,
        "requires_reversibility_evidence": True,
        "preview_only": True,
        "execution_authority": False,
        "desktop_effect_performed": False,
    }
    return _plan_response(
        actor=safe_actor,
        objective=safe_objective,
        status="plan_proposed",
        ok=True,
        blockers=[],
        workspace=workspace_bounds,
        targets=ordered_targets,
        plan=plan,
    )


def preflight_desktop_organization_execution(
    *,
    actor: Any,
    plan: Any,
    approval: Any,
    reversal_evidence: Any,
) -> dict[str, Any]:
    """Evaluate whether a desktop organization plan is allowed to reach an actuator.

    Passing the contract gates still does not execute anything in this slice. A
    future actuator must be added separately and keep this preflight in front of
    all physical input.
    """

    safe_actor = _safe_text(actor, limit=120) or "unknown"
    safe_plan = _as_dict(plan)
    safe_approval = _as_dict(approval)
    safe_reversal = _as_dict(reversal_evidence)
    blockers: list[str] = []

    plan_id = _safe_text(safe_plan.get("plan_id"), limit=160)
    steps = _plan_steps(safe_plan)
    if safe_plan.get("kind") != LENS_DESKTOP_ORGANIZATION_PLAN_KIND or safe_plan.get("status") != "plan_proposed":
        blockers.append("approved_desktop_organization_plan_required")
    if not plan_id:
        blockers.append("approved_plan_id_required")
    if not steps:
        blockers.append("approved_plan_steps_required")

    target_ids = _plan_target_ids(steps)
    approval_ok, approval_blockers, approval_summary = _approval_summary(
        approval=safe_approval,
        plan_id=plan_id,
        target_ids=target_ids,
        step_count=len(steps),
    )
    reversal_ok, reversal_blockers, reversal_summary = _reversal_summary(
        reversal=safe_reversal,
        target_ids=target_ids,
    )
    blockers.extend(approval_blockers)
    blockers.extend(reversal_blockers)
    blockers = _dedupe(blockers)

    base = {
        "kind": LENS_DESKTOP_ORGANIZATION_EXECUTION_KIND,
        "actor": safe_actor,
        "plan_id": plan_id,
        "status": "denied" if blockers else "blocked_actuator_not_implemented",
        "ok": False,
        "allowed_to_execute": False,
        "blockers": blockers or ["desktop_reorganization_actuator_not_implemented"],
        "plan_approval_valid": approval_ok,
        "reversal_evidence_valid": reversal_ok,
        "approval": approval_summary,
        "reversal_evidence": reversal_summary,
        "step_count": len(steps),
        "semantic_target_ids": sorted(target_ids),
        "execution_attempted": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "desktop_effect_confirmed": False,
        "receipt_written": False,
        "governance": _governance(
            extra={
                "plan_approval_gate": approval_ok,
                "reversibility_gate": reversal_ok,
                "lens_semantic_target_gate": bool(target_ids),
            }
        ),
    }
    if not blockers:
        base["contract_gates_satisfied"] = True
        base["execution_ready_for_future_actuator"] = True
    else:
        base["contract_gates_satisfied"] = False
        base["execution_ready_for_future_actuator"] = False
    return base


def create_desktop_organization_reversal_evidence(
    *,
    actor: Any,
    plan: Any,
    position_readback: Any,
) -> dict[str, Any]:
    """Create bounded reversible pre-state evidence for a desktop organization plan."""

    safe_actor = _safe_text(actor, limit=120) or "unknown"
    safe_plan = _as_dict(plan)
    safe_position = _as_dict(position_readback)
    blockers: list[str] = []
    plan_id = _safe_text(safe_plan.get("plan_id"), limit=160)
    steps = _plan_steps(safe_plan)
    position_targets = {
        _safe_text(target.get("target_id"), limit=120): target
        for target in _target_items(safe_position.get("semantic_targets"))
        if _safe_text(target.get("target_id"), limit=120)
    }

    if safe_plan.get("kind") != LENS_DESKTOP_ORGANIZATION_PLAN_KIND or safe_plan.get("status") != "plan_proposed":
        blockers.append("desktop_organization_plan_required")
    if not plan_id:
        blockers.append("approved_plan_id_required")
    if not steps:
        blockers.append("approved_plan_steps_required")
    if safe_position.get("position_evidence_ready") is not True:
        blockers.append("desktop_icon_position_evidence_ready_required")

    pre_state_targets: list[dict[str, Any]] = []
    for step in steps:
        semantic_target = _as_dict(step.get("semantic_target"))
        target_id = _safe_text(semantic_target.get("target_id"), limit=120)
        target_digest = _safe_text(semantic_target.get("stable_identity_digest"), limit=64)
        positioned = position_targets.get(target_id, {})
        positioned_digest = _safe_text(positioned.get("stable_identity_digest"), limit=64)
        rect, rect_blockers = _rect(positioned.get("current_rect"))
        if not target_id:
            blockers.append("desktop_reversal_target_id_required")
            continue
        if not positioned:
            blockers.append("desktop_reversal_position_target_missing")
            continue
        if target_digest != positioned_digest:
            blockers.append("desktop_reversal_position_identity_mismatch")
            continue
        if rect_blockers:
            blockers.extend(rect_blockers)
            continue
        pre_state_targets.append(
            {
                "target_id": target_id,
                "stable_identity_digest": target_digest,
                "pre_rect": rect,
                "reversal_hint": {
                    "action": "restore_desktop_icon_position",
                    "target_rect": rect,
                },
            }
        )

    target_ids = [target["target_id"] for target in pre_state_targets]
    all_targets_captured = bool(steps) and len(pre_state_targets) == len(steps)
    capturable = all_targets_captured and not blockers
    reversible = capturable
    evidence_id = f"desktop-org-reversal-{_digest({'plan_id': plan_id, 'targets': pre_state_targets})}"
    return {
        "kind": LENS_DESKTOP_ORGANIZATION_REVERSAL_EVIDENCE_KIND,
        "status": "ready" if reversible else "denied",
        "ok": reversible,
        "actor": safe_actor,
        "plan_id": plan_id,
        "evidence_id": evidence_id if pre_state_targets else "",
        "capturable": capturable,
        "reversible": reversible,
        "semantic_target_ids": target_ids,
        "target_count": len(pre_state_targets),
        "pre_state": {
            "kind": "lens.orb.desktop_organization.pre_state",
            "targets": pre_state_targets,
            "raw_paths_stored": False,
            "raw_labels_stored": False,
            "file_contents_read": False,
        },
        "blockers": _dedupe(blockers),
        "governance": {
            "api_permission_gate": True,
            "read_only_contract": True,
            "pre_state_capture": True,
            "reversibility_evidence": True,
            "input_execution_authority": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "filesystem_write": False,
            "shell": False,
            "subprocess": False,
            "network_client": False,
            "daemon": False,
        },
    }


def create_desktop_organization_orb_sequence(
    *,
    actor: Any,
    plan: Any,
    approval: Any,
    reversal_evidence: Any,
) -> dict[str, Any]:
    """Create a visible Orb-only sequence for a reversible desktop plan.

    This does not execute the sequence. It converts approved semantic plan
    steps into one visible Orb drag intent per target so a future actuator can
    consume them sequentially without batch desktop mutation.
    """

    preflight = preflight_desktop_organization_execution(
        actor=actor,
        plan=plan,
        approval=approval,
        reversal_evidence=reversal_evidence,
    )
    safe_actor = _safe_text(actor, limit=120) or "unknown"
    safe_plan = _as_dict(plan)
    plan_id = _safe_text(safe_plan.get("plan_id"), limit=160)
    base_governance = _governance(
        extra={
            "orb_bound_single_action_actuator": True,
            "visible_orb_body_required": True,
            "one_desktop_target_per_sequence_item": True,
            "batch_desktop_mutation": False,
            "raw_coordinate_drag_authority": False,
            "coordinates_are_semantic_plan_derived": True,
            "sequence_generation_only": True,
        }
    )
    if preflight.get("contract_gates_satisfied") is not True:
        return {
            "kind": LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND,
            "status": "denied",
            "ok": False,
            "actor": safe_actor,
            "plan_id": plan_id,
            "preflight": preflight,
            "blockers": _string_items(preflight.get("blockers")),
            "sequence_items": [],
            "sequence_item_count": 0,
            "sequence_ready_for_orb_actuator": False,
            "execution_attempted": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
            "governance": base_governance,
        }

    sequence_items: list[dict[str, Any]] = []
    blockers: list[str] = []
    for index, step in enumerate(_plan_steps(safe_plan), start=1):
        item, item_blockers = _orb_sequence_item(
            step=step,
            index=index,
            plan_id=plan_id,
        )
        blockers.extend(item_blockers)
        if item:
            sequence_items.append(item)

    blockers = _dedupe(blockers)
    if blockers:
        return {
            "kind": LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND,
            "status": "denied",
            "ok": False,
            "actor": safe_actor,
            "plan_id": plan_id,
            "preflight": preflight,
            "blockers": blockers,
            "sequence_items": [],
            "sequence_item_count": 0,
            "sequence_ready_for_orb_actuator": False,
            "execution_attempted": False,
            "physical_input_performed": False,
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
            "governance": base_governance,
        }

    sequence_id = f"desktop-org-orb-seq-{_digest({'plan_id': plan_id, 'items': sequence_items})}"
    return {
        "kind": LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND,
        "status": "orb_sequence_ready",
        "ok": True,
        "actor": safe_actor,
        "plan_id": plan_id,
        "sequence_id": sequence_id,
        "preflight": preflight,
        "blockers": [],
        "sequence_items": sequence_items,
        "sequence_item_count": len(sequence_items),
        "sequence_ready_for_orb_actuator": True,
        "requires_visible_orb_pointer": True,
        "requires_sequential_consumption": True,
        "requires_separate_orb_actuator_gate": True,
        "allowed_to_execute": False,
        "execution_authority": False,
        "execution_attempted": False,
        "physical_input_performed": False,
        "uses_user_os_cursor": False,
        "desktop_effect_performed": False,
        "desktop_effect_confirmed": False,
        "governance": base_governance,
    }


def execute_desktop_organization_plan(
    *,
    actor: Any,
    plan: Any,
    approval: Any,
    reversal_evidence: Any,
    move_backend: Any = None,
) -> dict[str, Any]:
    """Execute an approved, reversible desktop organization plan if enabled."""

    preflight = preflight_desktop_organization_execution(
        actor=actor,
        plan=plan,
        approval=approval,
        reversal_evidence=reversal_evidence,
    )
    if preflight.get("contract_gates_satisfied") is not True:
        return {
            **preflight,
            "kind": "lens.orb.desktop_organization.execution",
            "status": "denied",
            "preflight": preflight,
            "execution_attempted": False,
            "execution_gate": "contract_preflight",
        }

    orb_sequence = create_desktop_organization_orb_sequence(
        actor=actor,
        plan=plan,
        approval=approval,
        reversal_evidence=reversal_evidence,
    )
    blockers = ["desktop_organization_orb_actuator_required"]
    if move_backend is not None:
        blockers.insert(0, "desktop_organization_arbitrary_move_backend_rejected")

    return {
        **preflight,
        "kind": "lens.orb.desktop_organization.execution",
        "status": "blocked_orb_actuator_required",
        "preflight": preflight,
        "blockers": blockers,
        "orb_sequence": orb_sequence,
        "execution_attempted": False,
        "execution_gate": "orb_bound_single_action_actuator",
        "allowed_to_execute": False,
    }


def run_desktop_organization_orb_sequence(
    *,
    actor: Any,
    orb_sequence: Any,
    submitter: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Trace a desktop organization sequence through the visible Orb pointer only.

    Each sequence item is consumed independently as source-center and
    destination-center Orb moves. This intentionally does not click, drag, or
    mutate desktop icons.
    """

    safe_actor = _safe_text(actor, limit=120) or "unknown"
    sequence = _as_dict(orb_sequence)
    sequence_id = _safe_text(sequence.get("sequence_id"), limit=160)
    plan_id = _safe_text(sequence.get("plan_id"), limit=160)
    items = _sequence_items(sequence.get("sequence_items"))
    blockers: list[str] = []
    if sequence.get("kind") != LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND:
        blockers.append("desktop_organization_orb_sequence_kind_required")
    if sequence.get("status") != "orb_sequence_ready" or sequence.get("sequence_ready_for_orb_actuator") is not True:
        blockers.append("desktop_organization_orb_sequence_ready_required")
    if not sequence_id:
        blockers.append("desktop_organization_orb_sequence_id_required")
    if not items:
        blockers.append("desktop_organization_orb_sequence_items_required")
    if blockers:
        return _orb_sequence_run_response(
            actor=safe_actor,
            plan_id=plan_id,
            sequence_id=sequence_id,
            status="denied",
            ok=False,
            blockers=blockers,
            consumed=[],
        )

    if submitter is None:
        from francis.input_actuator.orb_operator import submit_orb_intent

        submitter = submit_orb_intent

    consumed: list[dict[str, Any]] = []
    for item in items:
        item_result, item_blockers = _run_orb_sequence_item(
            actor=safe_actor,
            sequence_id=sequence_id,
            plan_id=plan_id,
            item=item,
            submitter=submitter,
        )
        consumed.append(item_result)
        blockers.extend(item_blockers)
        if item_blockers:
            break

    blockers = _dedupe(blockers)
    status = "orb_visible_sequence_complete" if not blockers and len(consumed) == len(items) else "blocked"
    return _orb_sequence_run_response(
        actor=safe_actor,
        plan_id=plan_id,
        sequence_id=sequence_id,
        status=status,
        ok=status == "orb_visible_sequence_complete",
        blockers=blockers,
        consumed=consumed,
    )


def actuate_desktop_organization_orb_sequence_item(
    *,
    actor: Any,
    orb_sequence: Any,
    sequence_item_id: Any = "",
    order: Any = None,
    post_position_readback: Any = None,
    post_position_readback_provider: Callable[[], dict[str, Any]] | None = None,
    submitter: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    position_adapter: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Attempt one Orb-owned cursor desktop move with readback confirmation."""

    safe_actor = _safe_text(actor, limit=120) or "unknown"
    sequence = _as_dict(orb_sequence)
    sequence_id = _safe_text(sequence.get("sequence_id"), limit=160)
    plan_id = _safe_text(sequence.get("plan_id"), limit=160)
    items = _sequence_items(sequence.get("sequence_items"))
    selected, select_blockers = _select_sequence_item(
        items,
        sequence_item_id=_safe_text(sequence_item_id, limit=120),
        order=order,
    )
    post_readback = _as_dict(post_position_readback)
    blockers: list[str] = []
    if sequence.get("kind") != LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND:
        blockers.append("desktop_organization_orb_sequence_kind_required")
    if sequence.get("status") != "orb_sequence_ready" or sequence.get("sequence_ready_for_orb_actuator") is not True:
        blockers.append("desktop_organization_orb_sequence_ready_required")
    if not sequence_id:
        blockers.append("desktop_organization_orb_sequence_id_required")
    blockers.extend(select_blockers)
    if os.getenv(LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV, "").strip() != "1":
        blockers.append("desktop_organization_orb_actuation_env_gate_required")
    if _orb_item_requires_shell_adapter(selected) and not _desktop_shell_adapter_enabled():
        blockers.append("desktop_organization_shell_adapter_env_gate_required")
    if post_readback.get("position_evidence_ready") is not True and post_position_readback_provider is None:
        blockers.append("desktop_organization_post_action_position_readback_required")
    if blockers:
        return _orb_item_actuation_response(
            actor=safe_actor,
            plan_id=plan_id,
            sequence_id=sequence_id,
            item=selected,
            status="denied",
            ok=False,
            blockers=blockers,
            visual_result={},
            position_adapter_result={},
            post_position_readback=post_readback,
        )

    if submitter is None:
        from francis.input_actuator.orb_operator import submit_orb_intent

        submitter = submit_orb_intent

    intent = _as_dict(selected.get("orb_intent"))
    if _safe_text(intent.get("kind"), limit=80) != "orb_carry_desktop_icon":
        return _orb_item_actuation_response(
            actor=safe_actor,
            plan_id=plan_id,
            sequence_id=sequence_id,
            item=selected,
            status="denied",
            ok=False,
            blockers=["desktop_organization_orb_item_carry_intent_required"],
            visual_result={},
            position_adapter_result={},
            post_position_readback=post_readback,
        )

    if position_adapter is None:
        from francis.lens.desktop_icon_positions import apply_desktop_icon_position_item

        position_adapter = apply_desktop_icon_position_item

    visual_result, position_adapter_result, actuation_blockers = _run_orb_carry_sequence_item(
        actor=safe_actor,
        sequence_id=sequence_id,
        plan_id=plan_id,
        item=selected,
        submitter=submitter,
        position_adapter=position_adapter,
    )
    blockers = _dedupe(actuation_blockers)
    if (
        not blockers
        and post_readback.get("position_evidence_ready") is not True
        and post_position_readback_provider is not None
    ):
        post_readback = _as_dict(post_position_readback_provider())
    readback_ok, readback_blockers, readback_summary = _post_action_readback_summary(
        item=selected,
        post_position_readback=post_readback,
    )
    blockers = _dedupe([*blockers, *readback_blockers])
    status = "desktop_item_actuation_confirmed" if not blockers and readback_ok else "blocked"
    return _orb_item_actuation_response(
        actor=safe_actor,
        plan_id=plan_id,
        sequence_id=sequence_id,
        item=selected,
        status=status,
        ok=status == "desktop_item_actuation_confirmed",
        blockers=blockers,
        visual_result=visual_result,
        position_adapter_result=position_adapter_result,
        post_position_readback=post_readback,
        readback_summary=readback_summary,
    )


def _plan_response(
    *,
    actor: str,
    objective: str,
    status: str,
    ok: bool,
    blockers: list[str],
    workspace: dict[str, int],
    targets: list[dict[str, Any]],
    plan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "kind": LENS_DESKTOP_ORGANIZATION_PLAN_KIND,
        "actor": actor,
        "status": status,
        "ok": ok,
        "objective_summary": objective,
        "blockers": blockers,
        "workspace": workspace,
        "semantic_target_count": len(targets),
        "semantic_targets": targets,
        "plan": plan,
        "requires_lens_semantics": True,
        "requires_plan_level_approval": True,
        "requires_pre_state": True,
        "requires_reversibility_evidence": True,
        "execution_authority": False,
        "preview_only": True,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "governance": _governance(),
    }


def _orb_sequence_item(
    *,
    step: dict[str, Any],
    index: int,
    plan_id: str,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    step_id = _safe_text(step.get("step_id"), limit=120) or f"desktop-org-step-{index:03d}"
    semantic_target = _as_dict(step.get("semantic_target"))
    target_id = _safe_text(semantic_target.get("target_id"), limit=120)
    target_kind = _safe_text(semantic_target.get("target_kind"), limit=64)
    target_digest = _safe_text(semantic_target.get("stable_identity_digest"), limit=64)
    desktop_position_index = _safe_int(
        semantic_target.get("desktop_position_index"),
        default=-1,
        lower=-1,
        upper=_MAX_TARGETS,
    )
    from_rect, from_blockers = _rect(step.get("from_rect"))
    to_rect, to_blockers = _rect(step.get("to_rect"))
    blockers.extend(from_blockers)
    blockers.extend(to_blockers)
    if not plan_id:
        blockers.append("desktop_organization_plan_id_required")
    if not target_id:
        blockers.append("desktop_organization_orb_sequence_target_id_required")
    if target_kind not in _ICON_TARGET_KINDS:
        blockers.append("desktop_organization_orb_sequence_target_kind_invalid")
    if not target_digest:
        blockers.append("desktop_organization_orb_sequence_target_identity_required")
    if blockers:
        return {}, _dedupe(blockers)

    source_center = _desktop_icon_grab_point(from_rect)
    destination_center = _desktop_icon_grab_point(to_rect)
    metadata = {
        "desktop_organization_plan_id": plan_id,
        "desktop_organization_step_id": step_id,
        "semantic_target_id": target_id,
        "semantic_target_kind": target_kind,
        "stable_identity_digest": target_digest,
        "desktop_position_index": desktop_position_index,
        "requires_visible_orb_body": True,
        "single_action_only": True,
        "batch_desktop_mutation": False,
        "desktop_shell_target_required": True,
    }
    return (
        {
            "sequence_item_id": f"desktop-org-orb-item-{index:03d}",
            "order": index,
            "plan_step_id": step_id,
            "action": "orb_pointer_drag_desktop_icon",
            "semantic_target": {
                "target_id": target_id,
                "target_kind": target_kind,
                "stable_identity_digest": target_digest,
                "desktop_position_index": desktop_position_index,
            },
            "from_rect": from_rect,
            "to_rect": to_rect,
            "from_center": source_center,
            "to_center": destination_center,
            "orb_intent": {
                "kind": "orb_carry_desktop_icon",
                "metadata": metadata,
            },
            "requires_visible_orb_pointer": True,
            "requires_single_action_consumption": True,
            "execution_attempted": False,
            "physical_input_performed": False,
            "uses_user_os_cursor": False,
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
        },
        [],
    )


def _run_orb_sequence_item(
    *,
    actor: str,
    sequence_id: str,
    plan_id: str,
    item: dict[str, Any],
    submitter: Callable[[dict[str, Any]], dict[str, Any]],
) -> tuple[dict[str, Any], list[str]]:
    item_id = _safe_text(item.get("sequence_item_id"), limit=120)
    order = _safe_int(item.get("order"), default=0, lower=0, upper=_MAX_TARGETS)
    target = _as_dict(item.get("semantic_target"))
    target_id = _safe_text(target.get("target_id"), limit=120)
    from_center, from_blockers = _point(item.get("from_center"))
    to_center, to_blockers = _point(item.get("to_center"))
    blockers = [*from_blockers, *to_blockers]
    if not item_id:
        blockers.append("desktop_organization_orb_sequence_item_id_required")
    if not target_id:
        blockers.append("desktop_organization_orb_sequence_item_target_required")
    if blockers:
        return (
            {
                "sequence_item_id": item_id,
                "order": order,
                "semantic_target_id": target_id,
                "status": "denied",
                "blockers": _dedupe(blockers),
                "source_move": {},
                "destination_move": {},
                "desktop_effect_performed": False,
                "physical_input_performed": False,
                "uses_user_os_cursor": False,
            },
            blockers,
        )

    source_intent = _orb_move_intent(
        x=from_center["x"],
        y=from_center["y"],
        sequence_id=sequence_id,
        plan_id=plan_id,
        item_id=item_id,
        target_id=target_id,
        phase="source_center",
    )
    destination_intent = _orb_move_intent(
        x=to_center["x"],
        y=to_center["y"],
        sequence_id=sequence_id,
        plan_id=plan_id,
        item_id=item_id,
        target_id=target_id,
        phase="destination_center",
    )
    source_result = submitter(_orb_submit_payload(actor=actor, sequence_id=sequence_id, intent=source_intent))
    source_blockers = _orb_run_result_blockers(source_result)
    destination_result: dict[str, Any] = {}
    destination_blockers: list[str] = []
    if not source_blockers:
        destination_result = submitter(
            _orb_submit_payload(actor=actor, sequence_id=sequence_id, intent=destination_intent)
        )
        destination_blockers = _orb_run_result_blockers(destination_result)

    blockers = _dedupe([*source_blockers, *destination_blockers])
    return (
        {
            "sequence_item_id": item_id,
            "order": order,
            "semantic_target_id": target_id,
            "status": "visible_orb_item_complete" if not blockers else "blocked",
            "blockers": blockers,
            "source_move": _orb_run_move_summary(source_result),
            "destination_move": _orb_run_move_summary(destination_result),
            "desktop_effect_performed": False,
            "desktop_effect_confirmed": False,
            "physical_input_performed": False,
            "uses_user_os_cursor": False,
        },
        blockers,
    )


def _run_orb_carry_sequence_item(
    *,
    actor: str,
    sequence_id: str,
    plan_id: str,
    item: dict[str, Any],
    submitter: Callable[[dict[str, Any]], dict[str, Any]],
    position_adapter: Callable[..., dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    item_id = _safe_text(item.get("sequence_item_id"), limit=120)
    order = _safe_int(item.get("order"), default=0, lower=0, upper=_MAX_TARGETS)
    target = _as_dict(item.get("semantic_target"))
    target_id = _safe_text(target.get("target_id"), limit=120)
    desktop_position_index = _safe_int(
        target.get("desktop_position_index"),
        default=-1,
        lower=-1,
        upper=_MAX_TARGETS,
    )
    from_rect, from_blockers = _rect(item.get("from_rect"))
    to_rect, to_blockers = _rect(item.get("to_rect"))
    from_center, from_center_blockers = _point(item.get("from_center"))
    blockers = [*from_blockers, *to_blockers, *from_center_blockers]
    if not item_id:
        blockers.append("desktop_organization_orb_sequence_item_id_required")
    if not target_id:
        blockers.append("desktop_organization_orb_sequence_item_target_required")
    if desktop_position_index < 0:
        blockers.append("desktop_organization_shell_adapter_index_required")
    if blockers:
        return (
            _orb_carry_visual_result(
                item_id=item_id,
                order=order,
                target_id=target_id,
                status="denied",
                blockers=blockers,
                source_result={},
                carry_frames=[],
            ),
            {},
            _dedupe(blockers),
        )

    source_intent = _orb_carry_intent(
        x=from_center["x"],
        y=from_center["y"],
        sequence_id=sequence_id,
        plan_id=plan_id,
        item_id=item_id,
        target=target,
        phase="source_center",
    )
    source_result = submitter(_orb_submit_payload(actor=actor, sequence_id=sequence_id, intent=source_intent))
    blockers = _orb_run_result_blockers(source_result)
    carry_frames: list[dict[str, Any]] = []
    final_adapter_result: dict[str, Any] = {}
    if not blockers:
        for frame in _orb_carry_frames(from_rect=from_rect, to_rect=to_rect):
            move_intent = _orb_carry_intent(
                x=frame["point"]["x"],
                y=frame["point"]["y"],
                sequence_id=sequence_id,
                plan_id=plan_id,
                item_id=item_id,
                target=target,
                phase=frame["phase"],
            )
            move_result = submitter(_orb_submit_payload(actor=actor, sequence_id=sequence_id, intent=move_intent))
            move_blockers = _orb_run_result_blockers(move_result)
            adapter_result: dict[str, Any] = {}
            adapter_blockers: list[str] = []
            if not move_blockers:
                adapter_result = position_adapter(
                    target_id=target_id,
                    desktop_position_index=desktop_position_index,
                    to_rect=frame["rect"],
                )
                adapter_blockers = _position_adapter_blockers(adapter_result)
                final_adapter_result = adapter_result
            frame_blockers = _dedupe([*move_blockers, *adapter_blockers])
            carry_frames.append(
                {
                    "phase": frame["phase"],
                    "rect": frame["rect"],
                    "move": _orb_run_move_summary(move_result),
                    "shell_adapter_status": _safe_text(adapter_result.get("status"), limit=80),
                    "shell_adapter_blockers": _string_items(adapter_result.get("blockers")),
                    "blockers": frame_blockers,
                }
            )
            blockers.extend(frame_blockers)
            if frame_blockers:
                break

    blockers = _dedupe(blockers)
    return (
        _orb_carry_visual_result(
            item_id=item_id,
            order=order,
            target_id=target_id,
            status="visible_orb_carry_complete"
            if not blockers and len(carry_frames) == _CARRY_FRAME_COUNT
            else "blocked",
            blockers=blockers,
            source_result=source_result,
            carry_frames=carry_frames,
        ),
        final_adapter_result,
        blockers,
    )


def _orb_carry_visual_result(
    *,
    item_id: str,
    order: int,
    target_id: str,
    status: str,
    blockers: list[str],
    source_result: dict[str, Any],
    carry_frames: list[dict[str, Any]],
) -> dict[str, Any]:
    destination_frame = carry_frames[-1] if carry_frames else {}
    return {
        "sequence_item_id": item_id,
        "order": order,
        "semantic_target_id": target_id,
        "status": status,
        "blockers": _dedupe(blockers),
        "source_move": _orb_run_move_summary(source_result),
        "carry_moves": carry_frames,
        "carry_frame_count": len(carry_frames),
        "destination_move": _as_dict(destination_frame.get("move")),
        "desktop_effect_performed": False,
        "desktop_effect_confirmed": False,
        "physical_input_performed": False,
        "uses_user_os_cursor": False,
    }


def _orb_carry_frames(*, from_rect: dict[str, int], to_rect: dict[str, int]) -> list[dict[str, Any]]:
    frames: list[dict[str, Any]] = []
    for index in range(1, _CARRY_FRAME_COUNT + 1):
        ratio = index / _CARRY_FRAME_COUNT
        rect = {
            "left": round(from_rect["left"] + ((to_rect["left"] - from_rect["left"]) * ratio)),
            "top": round(from_rect["top"] + ((to_rect["top"] - from_rect["top"]) * ratio)),
            "width": to_rect["width"],
            "height": to_rect["height"],
        }
        frames.append(
            {
                "phase": "destination_center" if index == _CARRY_FRAME_COUNT else f"carry_{index:03d}",
                "rect": rect,
                "point": _desktop_icon_grab_point(rect),
            }
        )
    return frames


def _orb_sequence_run_response(
    *,
    actor: str,
    plan_id: str,
    sequence_id: str,
    status: str,
    ok: bool,
    blockers: list[str],
    consumed: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "kind": LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_RUN_KIND,
        "status": status,
        "ok": ok,
        "actor": actor,
        "plan_id": plan_id,
        "sequence_id": sequence_id,
        "blockers": _dedupe(blockers),
        "consumed_item_count": len(consumed),
        "consumed_items": consumed,
        "execution_attempted": bool(consumed),
        "orb_pointer_state_written": bool(consumed) and ok,
        "operator_receipts_written": bool(consumed),
        "desktop_effect_performed": False,
        "desktop_effect_confirmed": False,
        "physical_input_performed": False,
        "uses_user_os_cursor": False,
        "governance": _governance(
            extra={
                "api_permission_gate": True,
                "orb_bound_single_action_actuator": True,
                "visible_orb_body_required": True,
                "one_desktop_target_per_sequence_item": True,
                "batch_desktop_mutation": False,
                "raw_coordinate_drag_authority": False,
                "coordinates_are_semantic_plan_derived": True,
                "sequence_generation_only": False,
                "visible_orb_sequence_run": True,
                "orb_pointer_state_write": bool(consumed),
                "operator_receipts_written": bool(consumed),
            }
        ),
    }


def _orb_item_actuation_response(
    *,
    actor: str,
    plan_id: str,
    sequence_id: str,
    item: dict[str, Any],
    status: str,
    ok: bool,
    blockers: list[str],
    visual_result: dict[str, Any],
    position_adapter_result: dict[str, Any],
    post_position_readback: dict[str, Any],
    readback_summary: dict[str, Any] | None = None,
    fallback_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    target = _as_dict(item.get("semantic_target"))
    source_move = _as_dict(visual_result.get("source_move"))
    raw_carry_moves = visual_result.get("carry_moves")
    carry_moves = (
        [frame for frame in raw_carry_moves if isinstance(frame, dict)] if isinstance(raw_carry_moves, list) else []
    )
    destination_move = _as_dict(visual_result.get("destination_move"))
    adapter = _as_dict(position_adapter_result)
    adapter_governance = _as_dict(adapter.get("governance"))
    fallback = fallback_result or {}
    desktop_effect_performed = bool(
        adapter.get("desktop_effect_performed")
        or adapter_governance.get("desktop_effect_performed")
        or fallback.get("desktop_effect_performed")
    )
    physical_input_performed = bool(
        adapter.get("physical_input_performed") or adapter_governance.get("physical_input_performed")
    )
    uses_user_os_cursor = bool(adapter.get("uses_user_os_cursor") or adapter_governance.get("uses_user_os_cursor"))
    shell_adapter_required = _orb_item_requires_shell_adapter(item)
    shell_adapter_enabled = _desktop_shell_adapter_enabled()
    operator_receipt_ids = _dedupe(
        [
            _safe_text(source_move.get("operator_receipt_id"), limit=160),
            *[_safe_text(_as_dict(frame.get("move")).get("operator_receipt_id"), limit=160) for frame in carry_moves],
        ]
    )
    return {
        "kind": LENS_DESKTOP_ORGANIZATION_ORB_ITEM_ACTUATION_KIND,
        "status": status,
        "ok": ok,
        "actor": actor,
        "plan_id": plan_id,
        "sequence_id": sequence_id,
        "sequence_item_id": _safe_text(item.get("sequence_item_id"), limit=120),
        "order": _safe_int(item.get("order"), default=0, lower=0, upper=_MAX_TARGETS),
        "semantic_target_id": _safe_text(target.get("target_id"), limit=120),
        "blockers": _dedupe(blockers),
        "submit_status": _safe_text(visual_result.get("status"), limit=80),
        "operator_receipt_id": operator_receipt_ids[-1] if operator_receipt_ids else "",
        "operator_receipt_ids": operator_receipt_ids,
        "source_move": source_move,
        "carry_moves": carry_moves,
        "carry_frame_count": len(carry_moves),
        "destination_move": destination_move,
        "visual_orb_cursor_used": bool(visual_result),
        "shell_adapter_status": _safe_text(adapter.get("status"), limit=80),
        "shell_adapter_blockers": _string_items(adapter.get("blockers")),
        "fallback_used": bool(fallback),
        "fallback_status": _safe_text(fallback.get("status"), limit=80),
        "fallback_blockers": _string_items(fallback.get("blockers")),
        "readback": readback_summary or {},
        "post_position_readback_ready": post_position_readback.get("position_evidence_ready") is True,
        "execution_attempted": bool(visual_result or position_adapter_result),
        "desktop_effect_performed": desktop_effect_performed,
        "desktop_effect_confirmed": ok,
        "physical_input_performed": physical_input_performed,
        "uses_user_os_cursor": uses_user_os_cursor,
        "governance": _governance(
            extra={
                "api_permission_gate": True,
                "orb_bound_single_action_actuator": True,
                "visible_orb_body_required": True,
                "one_desktop_target_per_sequence_item": True,
                "batch_desktop_mutation": False,
                "raw_coordinate_drag_authority": False,
                "coordinates_are_semantic_plan_derived": True,
                "sequence_generation_only": False,
                "visible_orb_sequence_run": False,
                "single_item_actuation": True,
                "single_target_carry_frames": len(carry_moves),
                "single_item_position_fallback_used": bool(fallback),
                "post_action_readback_required": True,
                "execution_gate": LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV,
                "shell_adapter_gate": LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV,
                "desktop_shell_adapter_required": shell_adapter_required,
                "desktop_shell_adapter_enabled": shell_adapter_enabled,
                "francis_own_cursor": True,
                "visible_orb_cursor_used": bool(visual_result),
                "desktop_effect_performed": desktop_effect_performed,
                "physical_input_performed": physical_input_performed,
                "uses_user_os_cursor": uses_user_os_cursor,
            }
        ),
    }


def _orb_item_requires_shell_adapter(item: dict[str, Any]) -> bool:
    intent = _as_dict(item.get("orb_intent"))
    metadata = _as_dict(intent.get("metadata"))
    return metadata.get("desktop_shell_target_required") is True


def _desktop_shell_adapter_enabled() -> bool:
    return os.getenv(LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV, "").strip() == "1"


def _orb_move_intent(
    *,
    x: int,
    y: int,
    sequence_id: str,
    plan_id: str,
    item_id: str,
    target_id: str,
    phase: str,
) -> dict[str, Any]:
    return {
        "kind": "move_to",
        "x": x,
        "y": y,
        "metadata": {
            "desktop_organization_sequence_id": sequence_id,
            "desktop_organization_plan_id": plan_id,
            "desktop_organization_sequence_item_id": item_id,
            "semantic_target_id": target_id,
            "visible_orb_phase": phase,
            "desktop_effect_allowed": False,
            "batch_desktop_mutation": False,
        },
    }


def _orb_carry_intent(
    *,
    x: int,
    y: int,
    sequence_id: str,
    plan_id: str,
    item_id: str,
    target: dict[str, Any],
    phase: str,
) -> dict[str, Any]:
    target_id = _safe_text(target.get("target_id"), limit=120)
    return {
        "kind": "orb_carry_desktop_icon",
        "x": x,
        "y": y,
        "metadata": {
            "desktop_organization_sequence_id": sequence_id,
            "desktop_organization_plan_id": plan_id,
            "desktop_organization_sequence_item_id": item_id,
            "semantic_target_id": target_id,
            "semantic_target_kind": _safe_text(target.get("target_kind"), limit=64),
            "stable_identity_digest": _safe_text(target.get("stable_identity_digest"), limit=64),
            "desktop_position_index": _safe_int(
                target.get("desktop_position_index"),
                default=-1,
                lower=-1,
                upper=_MAX_TARGETS,
            ),
            "visible_orb_phase": phase,
            "carry_phase": phase,
            "desktop_effect_allowed": False,
            "batch_desktop_mutation": False,
            "desktop_shell_target_required": True,
            "francis_owned_cursor": True,
        },
    }


def _select_sequence_item(
    items: list[dict[str, Any]],
    *,
    sequence_item_id: str,
    order: Any,
) -> tuple[dict[str, Any], list[str]]:
    if not items:
        return {}, ["desktop_organization_orb_sequence_items_required"]
    safe_order = _safe_int(order, default=0, lower=0, upper=_MAX_TARGETS)
    if not sequence_item_id and not safe_order and len(items) != 1:
        return {}, ["desktop_organization_single_sequence_item_selector_required"]
    matches = []
    for item in items:
        item_id = _safe_text(item.get("sequence_item_id"), limit=120)
        item_order = _safe_int(item.get("order"), default=0, lower=0, upper=_MAX_TARGETS)
        if sequence_item_id and item_id == sequence_item_id:
            matches.append(item)
        elif safe_order and item_order == safe_order:
            matches.append(item)
    if not sequence_item_id and not safe_order and len(items) == 1:
        matches.append(items[0])
    if not matches:
        return {}, ["desktop_organization_orb_sequence_item_not_found"]
    if len(matches) > 1:
        return {}, ["desktop_organization_orb_sequence_item_selector_ambiguous"]
    return matches[0], []


def _position_adapter_blockers(result: dict[str, Any]) -> list[str]:
    if not result:
        return ["desktop_organization_shell_adapter_result_required"]
    blockers: list[str] = []
    governance = _as_dict(result.get("governance"))
    if result.get("ok") is not True:
        blockers.append("desktop_organization_shell_adapter_failed")
    if _safe_text(result.get("status"), limit=80) != "applied":
        blockers.append("desktop_organization_shell_adapter_not_applied")
    if result.get("desktop_effect_performed") is not True and governance.get("desktop_effect_performed") is not True:
        blockers.append("desktop_organization_shell_adapter_desktop_effect_not_performed")
    if result.get("uses_user_os_cursor") is True or governance.get("uses_user_os_cursor") is True:
        blockers.append("desktop_organization_shell_adapter_user_cursor_rejected")
    if result.get("physical_input_performed") is True or governance.get("physical_input_performed") is True:
        blockers.append("desktop_organization_shell_adapter_physical_input_rejected")
    blockers.extend(_string_items(result.get("blockers")))
    return _dedupe(blockers)


def _post_action_readback_summary(
    *,
    item: dict[str, Any],
    post_position_readback: dict[str, Any],
) -> tuple[bool, list[str], dict[str, Any]]:
    target = _as_dict(item.get("semantic_target"))
    target_id = _safe_text(target.get("target_id"), limit=120)
    expected_rect, expected_blockers = _rect(item.get("to_rect"))
    blockers = list(expected_blockers)
    if post_position_readback.get("position_evidence_ready") is not True:
        blockers.append("desktop_organization_post_action_position_readback_required")
    matched = {}
    for candidate in _target_items(post_position_readback.get("semantic_targets")):
        if _safe_text(candidate.get("target_id"), limit=120) == target_id:
            matched = candidate
            break
    if not matched:
        blockers.append("desktop_organization_post_action_target_readback_missing")
        return False, _dedupe(blockers), {"target_id": target_id, "confirmed": False}

    actual_rect, actual_blockers = _rect(matched.get("current_rect"))
    blockers.extend(actual_blockers)
    position_confirmed = _rect_near(expected_rect, actual_rect)
    if not position_confirmed:
        blockers.append("desktop_organization_post_action_position_mismatch")
    return (
        not blockers,
        _dedupe(blockers),
        {
            "target_id": target_id,
            "confirmed": position_confirmed and not blockers,
            "expected_rect": expected_rect,
            "actual_rect": actual_rect,
            "tolerance_px": 8,
        },
    )


def _rect_near(expected: dict[str, int], actual: dict[str, int]) -> bool:
    return abs(expected["left"] - actual["left"]) <= 8 and abs(expected["top"] - actual["top"]) <= 8


def _orb_submit_payload(*, actor: str, sequence_id: str, intent: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "orb_pointer",
        "actor": actor,
        "objective": "trace desktop organization sequence through the visible Orb pointer",
        "mission_id": sequence_id,
        "session_id": f"{sequence_id}-{_safe_text(intent.get('metadata', {}).get('visible_orb_phase'), limit=40)}",
        "intent": intent,
    }


def _orb_run_result_blockers(result: dict[str, Any]) -> list[str]:
    if not result:
        return ["orb_pointer_move_result_required"]
    blockers: list[str] = []
    governance = _as_dict(result.get("governance"))
    backend = _as_dict(result.get("backend"))
    backend_result = _as_dict(backend.get("result"))
    if result.get("ok") is not True:
        blockers.append("orb_pointer_move_failed")
    if governance.get("virtual_pointer_only") is not True:
        blockers.append("orb_pointer_virtual_only_required")
    if governance.get("uses_user_os_cursor") is True or governance.get("user_mouse_taken") is True:
        blockers.append("orb_pointer_user_cursor_control_rejected")
    if governance.get("physical_input_performed") is True or backend_result.get("physical_input_performed") is True:
        blockers.append("orb_pointer_physical_input_rejected")
    if governance.get("desktop_effect_performed") is True or backend_result.get("desktop_effect_performed") is True:
        blockers.append("orb_pointer_desktop_effect_rejected")
    intent_kind = _safe_text(_as_dict(result.get("intent")).get("kind"), limit=80)
    if intent_kind not in {"move_to", "orb_carry_desktop_icon"}:
        blockers.append("orb_pointer_move_or_carry_only_required")
    return _dedupe(blockers)


def _orb_run_move_summary(result: dict[str, Any]) -> dict[str, Any]:
    if not result:
        return {}
    backend = _as_dict(result.get("backend"))
    backend_result = _as_dict(backend.get("result"))
    pointer = _as_dict(backend_result.get("pointer_state"))
    return {
        "ok": result.get("ok") is True,
        "status": _safe_text(result.get("status"), limit=80),
        "feedback_state": _safe_text(result.get("feedback_state"), limit=80),
        "operator_receipt_id": _safe_text(result.get("operator_receipt_id"), limit=160),
        "x": _safe_int(pointer.get("x"), default=0, lower=-100_000, upper=100_000),
        "y": _safe_int(pointer.get("y"), default=0, lower=-100_000, upper=100_000),
        "desktop_effect_performed": False,
        "physical_input_performed": False,
        "uses_user_os_cursor": False,
    }


def _sequence_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = [_as_dict(item) for item in value if isinstance(item, dict)]
    return sorted(items, key=lambda item: _safe_int(item.get("order"), default=0, lower=0, upper=_MAX_TARGETS))


def _rect_center(rect: dict[str, int]) -> dict[str, int]:
    return {
        "x": rect["left"] + (rect["width"] // 2),
        "y": rect["top"] + (rect["height"] // 2),
    }


def _desktop_icon_grab_point(rect: dict[str, int]) -> dict[str, int]:
    return {
        "x": rect["left"] + (rect["width"] // 2),
        "y": rect["top"] + min(32, max(1, rect["height"] // 2)),
    }


def _point(value: Any) -> tuple[dict[str, int], list[str]]:
    item = _as_dict(value)
    x = _safe_int(item.get("x"), default=0, lower=-100_000, upper=100_000)
    y = _safe_int(item.get("y"), default=0, lower=-100_000, upper=100_000)
    blockers = []
    if "x" not in item or "y" not in item:
        blockers.append("orb_sequence_point_required")
    return {"x": x, "y": y}, blockers


def _semantic_icon_targets(value: Any) -> tuple[list[dict[str, Any]], list[str]]:
    if not isinstance(value, list):
        return [], ["semantic_target_list_required"]
    if len(value) > _MAX_TARGETS:
        return [], ["semantic_target_count_exceeds_limit"]

    targets: list[dict[str, Any]] = []
    blockers: list[str] = []
    for raw in value:
        item = _as_dict(raw)
        kind = _safe_text(item.get("kind") or item.get("target_kind"), limit=64)
        target_id = _safe_text(item.get("target_id") or item.get("id"), limit=120)
        semantic_source = _safe_text(item.get("semantic_source"), limit=120)
        stable_identity = _safe_text(item.get("stable_identity") or item.get("semantic_identity"), limit=300)
        stable_identity_digest = _safe_text(item.get("stable_identity_digest"), limit=64)
        label_summary = _redacted_text(item.get("label") or item.get("name") or item.get("label_summary"), limit=80)
        rect, rect_blockers = _rect(item.get("current_rect") or item.get("rect"))
        blockers.extend(rect_blockers)

        if any(key in item for key in ("x", "y", "from_x", "from_y", "target_x", "target_y")) and not kind:
            blockers.append("coordinate_only_target_rejected")
        if kind not in _ICON_TARGET_KINDS:
            blockers.append("unsupported_or_unknown_desktop_target")
            continue
        if not target_id or not semantic_source or not (stable_identity or stable_identity_digest):
            blockers.append("lens_semantic_target_mapping_required")
            continue
        if _desktop_organization_target_excluded(target_id=target_id, label_summary=label_summary):
            blockers.append("desktop_organization_game_target_isolated")
            continue
        if rect_blockers:
            continue

        targets.append(
            {
                "target_id": target_id,
                "target_kind": kind,
                "label_summary": label_summary,
                "semantic_source": semantic_source,
                "stable_identity_digest": stable_identity_digest or _digest({"stable_identity": stable_identity}),
                "current_rect": rect,
                "desktop_position_index": _safe_int(
                    item.get("desktop_position_index"),
                    default=-1,
                    lower=-1,
                    upper=_MAX_TARGETS,
                ),
            }
        )
    return targets, _dedupe(blockers)


def _desktop_organization_target_excluded(*, target_id: str, label_summary: str) -> bool:
    excluded = _desktop_organization_excluded_labels()
    if not excluded:
        return False
    return _normalized_target_label(label_summary) in excluded or _normalized_target_label(target_id) in excluded


def _desktop_organization_excluded_labels() -> set[str]:
    labels: set[str] = set()
    labels.update(_split_label_config(os.getenv(_DESKTOP_ORGANIZATION_EXCLUDED_LABELS_ENV, "")))
    labels.update(_split_label_config(os.getenv(_GAME_TARGET_ID_ENV, "")))
    for process_name in _split_label_config(os.getenv(_GAME_TARGET_PROCESSES_ENV, "")):
        stem = process_name.rsplit("\\", 1)[-1].rsplit("/", 1)[-1]
        if stem.casefold().endswith(".exe"):
            stem = stem[:-4]
        labels.add(_normalized_target_label(stem))
    return {label for label in labels if label}


def _split_label_config(value: Any) -> set[str]:
    text = _safe_text(value, limit=1000)
    if not text:
        return set()
    normalized = text.replace(";", ",")
    return {_normalized_target_label(item) for item in normalized.split(",") if _normalized_target_label(item)}


def _normalized_target_label(value: Any) -> str:
    return _safe_text(value, limit=160).casefold()


def _desktop_roots(value: Any) -> list[Path]:
    raw_items: list[Any]
    if value is None:
        configured = os.getenv(_DESKTOP_ROOT_ENV, "").strip()
        raw_items = configured.split(os.pathsep) if configured else []
        if not raw_items:
            raw_items = [Path.home() / "Desktop"]
            public_root = os.getenv("PUBLIC", "").strip()
            if public_root:
                raw_items.append(Path(public_root) / "Desktop")
    elif isinstance(value, (list, tuple)):
        raw_items = list(value)
    else:
        raw_items = [value]

    roots: list[Path] = []
    for raw in raw_items:
        text = _safe_text(raw, limit=1000)
        if not text:
            continue
        try:
            root = Path(text).expanduser().resolve()
        except OSError:
            continue
        if root not in roots:
            roots.append(root)
    return roots[:4]


def _desktop_source_scope(root: Path, index: int) -> str:
    home_desktop = (Path.home() / "Desktop").resolve()
    if root == home_desktop:
        return "user_desktop"
    public_root = os.getenv("PUBLIC", "").strip()
    if public_root and root == (Path(public_root) / "Desktop").resolve():
        return "public_desktop"
    return f"configured_desktop_{index + 1}"


def _desktop_child_target(path: Path, *, source_scope: str) -> dict[str, Any]:
    if path.name.casefold() == "desktop.ini":
        return {}
    try:
        if path.is_symlink():
            return {}
        is_dir = path.is_dir()
        is_file = path.is_file()
    except OSError:
        return {}
    if not is_dir and not is_file:
        return {}

    suffix = path.suffix.lower()[:24]
    if is_dir:
        target_kind = "folder_icon"
    elif suffix == ".lnk":
        target_kind = "shortcut_icon"
    else:
        target_kind = "file_icon"
    label = path.stem if suffix else path.name
    stable_identity = f"{source_scope}:{path.name}"
    return {
        "target_id": f"desktop-icon-{_digest({'source_scope': source_scope, 'name': path.name})}",
        "target_kind": target_kind,
        "label_summary": _redacted_text(label, limit=80),
        "extension_summary": suffix,
        "semantic_source": "desktop_directory_metadata",
        "source_scope": source_scope,
        "stable_identity_digest": _digest({"stable_identity": stable_identity}),
        "screen_rect_available": False,
        "current_rect": {},
        "raw_path_stored": False,
        "file_contents_read": False,
        "organization_ready": False,
        "blockers": ["desktop_icon_screen_rect_mapping_not_ready"],
    }


def _read_position_evidence() -> dict[str, Any]:
    path = data_dir() / _POSITION_EVIDENCE_RELATIVE_PATH
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig", errors="replace"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _target_items(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _mapped_position_target(target: dict[str, Any], evidence: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    target_id = _safe_text(target.get("target_id"), limit=120)
    stable_digest = _safe_text(target.get("stable_identity_digest"), limit=64)
    evidence_digest = _safe_text(evidence.get("stable_identity_digest"), limit=64)
    rect, rect_blockers = _rect(evidence.get("current_rect") or evidence.get("screen_rect"))
    mapped = dict(target)
    if not evidence:
        blockers.append("desktop_icon_position_evidence_missing_for_target")
    elif evidence_digest != stable_digest:
        blockers.append("desktop_icon_position_evidence_identity_mismatch")
    elif rect_blockers:
        blockers.extend(rect_blockers)
    else:
        mapped["screen_rect_available"] = True
        mapped["current_rect"] = rect
        mapped["position_evidence_id"] = _safe_text(evidence.get("evidence_id"), limit=160)
        mapped["position_evidence_source"] = _safe_text(evidence.get("source"), limit=120)
        mapped["desktop_position_index"] = _safe_int(
            evidence.get("desktop_position_index"),
            default=-1,
            lower=-1,
            upper=_MAX_TARGETS,
        )
        mapped["organization_ready"] = False
        mapped["blockers"] = []
        return mapped, []

    mapped["screen_rect_available"] = False
    mapped["current_rect"] = {}
    mapped["organization_ready"] = False
    mapped["blockers"] = _dedupe([*(_string_items(target.get("blockers"))), *blockers])
    if target_id:
        mapped["target_id"] = target_id
    return mapped, blockers


def _blocking_evidence_errors(blockers: list[str]) -> bool:
    blocking = {
        "desktop_icon_position_evidence_missing",
        "desktop_icon_position_evidence_kind_invalid",
        "desktop_icon_position_evidence_source_invalid",
        "desktop_icon_position_evidence_id_required",
        "desktop_icon_position_evidence_missing_for_target",
        "desktop_icon_position_evidence_identity_mismatch",
        "desktop_icon_position_evidence_target_mismatch",
        "target_current_rect_required",
    }
    return any(item in blocking for item in blockers)


def _layout_steps(targets: list[dict[str, Any]], workspace: dict[str, int]) -> list[dict[str, Any]]:
    left = workspace["left"] + _DEFAULT_GRID_GAP
    top = workspace["top"] + _DEFAULT_GRID_GAP
    width = max(_DEFAULT_ICON_WIDTH, workspace["width"] - (_DEFAULT_GRID_GAP * 2))
    column_stride = _DEFAULT_ICON_WIDTH + _DEFAULT_GRID_GAP
    row_stride = _DEFAULT_ICON_HEIGHT + _DEFAULT_GRID_GAP
    columns = max(1, width // column_stride)
    steps: list[dict[str, Any]] = []
    for index, target in enumerate(targets):
        column = index % columns
        row = index // columns
        destination = {
            "left": left + column * column_stride,
            "top": top + row * row_stride,
            "width": _DEFAULT_ICON_WIDTH,
            "height": _DEFAULT_ICON_HEIGHT,
        }
        steps.append(
            {
                "step_id": f"desktop-org-step-{index + 1:03d}",
                "action": "move_desktop_icon",
                "semantic_target": target,
                "from_rect": target["current_rect"],
                "to_rect": destination,
                "requires_pre_state": True,
                "requires_reversibility_evidence": True,
                "physical_input_performed": False,
            }
        )
    return steps


def _approval_summary(
    *,
    approval: dict[str, Any],
    plan_id: str,
    target_ids: set[str],
    step_count: int,
) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    approval_id = _safe_text(approval.get("approval_id") or approval.get("id"), limit=160)
    approved_plan_id = _safe_text(approval.get("approved_plan_id") or approval.get("plan_id"), limit=160)
    approved_targets = _string_set(approval.get("semantic_target_ids") or approval.get("target_ids"))
    approval_scopes = _string_set(approval.get("scopes") or approval.get("scope"))
    max_step_count = _safe_int(approval.get("max_step_count"), default=0, lower=0, upper=_MAX_TARGETS)

    if approval.get("approved") is not True:
        blockers.append("plan_level_approval_required")
    if not approval_id:
        blockers.append("approval_id_required")
    if approved_plan_id != plan_id:
        blockers.append("plan_approval_plan_id_mismatch")
    if LENS_DESKTOP_ORGANIZATION_SCOPE not in approval_scopes:
        blockers.append("desktop_organization_approval_scope_required")
    if step_count < 1 or max_step_count < step_count:
        blockers.append("desktop_organization_step_approval_scope_exceeded")
    if not approved_targets or not target_ids.issubset(approved_targets):
        blockers.append("desktop_organization_target_approval_scope_mismatch")
    if approval.get("reversibility_required") is not True:
        blockers.append("desktop_organization_reversibility_approval_required")

    ok = not blockers
    return (
        ok,
        _dedupe(blockers),
        {
            "approval_id": approval_id,
            "approved": approval.get("approved") is True,
            "approved_plan_id": approved_plan_id,
            "approved_target_count": len(approved_targets),
            "max_step_count": max_step_count,
            "scope_valid": LENS_DESKTOP_ORGANIZATION_SCOPE in approval_scopes,
            "valid": ok,
        },
    )


def _reversal_summary(
    *,
    reversal: dict[str, Any],
    target_ids: set[str],
) -> tuple[bool, list[str], dict[str, Any]]:
    blockers: list[str] = []
    evidence_id = _safe_text(reversal.get("evidence_id") or reversal.get("pre_state_id"), limit=160)
    evidence_targets = _string_set(reversal.get("semantic_target_ids") or reversal.get("target_ids"))
    capturable = reversal.get("capturable") is True
    reversible = reversal.get("reversible") is True

    if not reversal:
        blockers.extend(["pre_state_required", "reversibility_evidence_required"])
    if not evidence_id:
        blockers.append("reversal_evidence_id_required")
    if not capturable:
        blockers.append("desktop_pre_state_not_capturable")
    if not reversible:
        blockers.append("desktop_state_not_reversible")
    if not evidence_targets or not target_ids.issubset(evidence_targets):
        blockers.append("reversal_evidence_target_set_mismatch")

    ok = not blockers
    return (
        ok,
        _dedupe(blockers),
        {
            "evidence_id": evidence_id,
            "capturable": capturable,
            "reversible": reversible,
            "target_count": len(evidence_targets),
            "valid": ok,
        },
    )


def _workspace_bounds(value: Any) -> tuple[dict[str, int], list[str]]:
    item = _as_dict(value)
    left = _safe_int(item.get("left"), default=0, lower=-100_000, upper=100_000)
    top = _safe_int(item.get("top"), default=0, lower=-100_000, upper=100_000)
    width = _safe_int(item.get("width"), default=0, lower=0, upper=100_000)
    height = _safe_int(item.get("height"), default=0, lower=0, upper=100_000)
    blockers = []
    if width < _DEFAULT_ICON_WIDTH or height < _DEFAULT_ICON_HEIGHT:
        blockers.append("workspace_bounds_required")
    return {"left": left, "top": top, "width": width, "height": height}, blockers


def _rect(value: Any) -> tuple[dict[str, int], list[str]]:
    item = _as_dict(value)
    left = _safe_int(item.get("left"), default=0, lower=-100_000, upper=100_000)
    top = _safe_int(item.get("top"), default=0, lower=-100_000, upper=100_000)
    width = _safe_int(item.get("width"), default=0, lower=0, upper=100_000)
    height = _safe_int(item.get("height"), default=0, lower=0, upper=100_000)
    if (not width or not height) and "right" in item and "bottom" in item:
        right = _safe_int(item.get("right"), default=left, lower=-100_000, upper=100_000)
        bottom = _safe_int(item.get("bottom"), default=top, lower=-100_000, upper=100_000)
        width = max(0, right - left)
        height = max(0, bottom - top)
    blockers = []
    if width <= 0 or height <= 0:
        blockers.append("target_current_rect_required")
    return {"left": left, "top": top, "width": width, "height": height}, blockers


def _plan_steps(plan: dict[str, Any]) -> list[dict[str, Any]]:
    steps = plan.get("steps")
    if not isinstance(steps, list):
        return []
    return [_as_dict(step) for step in steps if isinstance(step, dict)]


def _plan_target_ids(steps: list[dict[str, Any]]) -> set[str]:
    target_ids: set[str] = set()
    for step in steps:
        target = _as_dict(step.get("semantic_target"))
        target_id = _safe_text(target.get("target_id"), limit=120)
        if target_id:
            target_ids.add(target_id)
    return target_ids


def _governance(*, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    governance: dict[str, Any] = {
        "api_permission_gate": True,
        "lens_semantic_target_mapping_required": True,
        "plan_level_approval_required": True,
        "pre_state_required": True,
        "reversibility_evidence_required": True,
        "coordinate_only_drag_authority": False,
        "uses_user_os_cursor": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "shell": False,
        "subprocess": False,
        "network_client": False,
        "gpu_execution": False,
        "daemon": False,
        "filesystem_write": False,
        "memory_write": False,
        "model_training": False,
    }
    if extra:
        governance.update(extra)
    return governance


def _semantic_governance() -> dict[str, Any]:
    return {
        "api_permission_gate": True,
        "read_only_contract": True,
        "desktop_directory_metadata_only": True,
        "raw_paths_stored": False,
        "file_contents_read": False,
        "pixel_capture": False,
        "ocr": False,
        "uia": False,
        "uses_user_os_cursor": False,
        "input_execution_authority": False,
        "physical_input_performed": False,
        "desktop_effect_performed": False,
        "filesystem_write": False,
        "shell": False,
        "subprocess": False,
        "network_client": False,
        "daemon": False,
        "memory_write": False,
    }


def _position_governance() -> dict[str, Any]:
    governance = _semantic_governance()
    governance.update(
        {
            "position_evidence_readback": True,
            "position_evidence_path": _POSITION_EVIDENCE_RELATIVE_PATH,
            "raw_paths_stored": False,
            "file_contents_read": False,
            "input_execution_authority": False,
            "desktop_effect_performed": False,
            "filesystem_write": False,
        }
    )
    return governance


def _safe_text(value: Any, *, limit: int) -> str:
    if value is None:
        return ""
    try:
        text = str(value).strip()
    except Exception:
        return ""
    return text[:limit]


def _redacted_text(value: Any, *, limit: int) -> str:
    return redact_secret_text(_safe_text(value, limit=limit))[:limit]


def _safe_int(value: Any, *, default: int, lower: int, upper: int) -> int:
    if isinstance(value, bool):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(lower, min(parsed, upper))


def _string_set(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value.strip()} if value.strip() else set()
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {_safe_text(item, limit=160) for item in value if _safe_text(item, limit=160)}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string_items(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [_safe_text(item, limit=160) for item in value if _safe_text(item, limit=160)]


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str, allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:16]


__all__ = [
    "LENS_DESKTOP_ICON_SEMANTICS_KIND",
    "LENS_DESKTOP_ICON_POSITION_EVIDENCE_KIND",
    "LENS_DESKTOP_ORGANIZATION_EXECUTION_KIND",
    "LENS_DESKTOP_ORGANIZATION_EXECUTE_ENV",
    "LENS_DESKTOP_ORGANIZATION_CURSOR_CAPABILITY_ENV",
    "LENS_DESKTOP_ORGANIZATION_ORB_ACTUATE_ENV",
    "LENS_DESKTOP_ORGANIZATION_ORB_ITEM_ACTUATION_KIND",
    "LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_KIND",
    "LENS_DESKTOP_ORGANIZATION_ORB_SEQUENCE_RUN_KIND",
    "LENS_DESKTOP_ORGANIZATION_PLAN_KIND",
    "LENS_DESKTOP_ORGANIZATION_REVERSAL_EVIDENCE_KIND",
    "LENS_DESKTOP_ORGANIZATION_ROUTE",
    "LENS_DESKTOP_ORGANIZATION_SHELL_ADAPTER_ENV",
    "LENS_DESKTOP_ORGANIZATION_SCOPE",
    "actuate_desktop_organization_orb_sequence_item",
    "create_desktop_organization_orb_sequence",
    "create_desktop_organization_reversal_evidence",
    "execute_desktop_organization_plan",
    "lens_desktop_icon_position_evidence",
    "lens_desktop_icon_semantic_targets",
    "preflight_desktop_organization_execution",
    "propose_desktop_organization_plan",
    "run_desktop_organization_orb_sequence",
]
