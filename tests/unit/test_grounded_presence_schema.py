from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from jsonschema.exceptions import ValidationError


SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas" / "grounded_presence_snapshot.schema.json"


def _validator() -> Draft202012Validator:
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _ready_core_snapshot() -> dict[str, Any]:
    return {
        "kind": "francis.grounded_presence.snapshot",
        "schema_version": "francis.grounded_presence.snapshot.v1",
        "schema_path": "schemas/grounded_presence_snapshot.schema.json",
        "generated_at": "2026-07-09T20:00:00Z",
        "stage": {
            "id": 1,
            "name": "Grounded Presence",
            "status": "ready",
            "criteria": {
                "no_fabricated_state": True,
                "local_evidence_grounded": True,
                "action_receipt_linkage": True,
                "calm_non_theatrical_tone": True,
                "return_to_context": True,
            },
        },
        "presence": {
            "state": "operator_action_required",
            "tone": "calm_operator",
            "tone_contract": {
                "id": "francis.grounded_presence.tone.v1",
                "style": "calm_operator",
                "theatricality_allowed": False,
                "claims_require_evidence": True,
                "missing_state_wording": "explicit_unknown",
            },
            "truthful": True,
            "headline": "Review the receipt-linked result before continuing.",
            "focus": {
                "source": "focus",
                "id": "mission_1",
                "objective": "Review the governed result.",
                "title": "Review governed result",
                "summary": "The operation is waiting for review.",
                "status": "blocked",
                "next_step": "Inspect the result receipt.",
                "recommended_action": "review_result",
                "updated_at": "2026-07-09T19:59:50Z",
            },
            "return_to_context": {
                "available": True,
                "source": "continuity_briefing",
                "focus_source": "focus",
                "fresh": True,
                "actionable": True,
                "objective": "Review the governed result.",
                "summary": "The operation is waiting for review.",
                "reason": "Operator review is required.",
                "next_step": "Inspect the result receipt.",
                "changed_since": "The operation entered review.",
                "governance_hold": {
                    "active": True,
                    "gate": "operator_review",
                    "approval_id": "approval_1",
                    "approval_status": "pending",
                    "reason": "Operator review is required.",
                },
                "last_meaningful_at": "2026-07-09T19:59:50Z",
                "reference_ids": ["receipt_1"],
            },
        },
        "intent": {
            "available": True,
            "request_only": True,
            "action": "review_result",
            "source": "focus.recommended_action",
            "target_kind": "operation",
            "target_id": "operation_1",
            "mission_id": "mission_1",
            "operation_id": "operation_1",
            "operation_plane": "P7_EXECUTION",
            "reason": "Operator review is required.",
            "next_step": "Inspect the result receipt.",
            "stage": "gate",
            "gate": "operator_review",
            "approval": {
                "id": "approval_1",
                "status": "pending",
            },
            "grants_execution_authority": False,
        },
        "evidence": {
            "status": "ready",
            "source_readbacks": {
                "continuity_briefing": True,
                "operator_surface": True,
                "orb_surface": True,
            },
            "correlation": {
                "status": "receipt_linked",
                "focus_id": "mission_1",
                "mission_id": "mission_1",
                "operation_id": "operation_1",
                "action": "review_result",
                "receipt_ids": ["receipt_1"],
            },
            "references": [
                {
                    "kind": "receipt",
                    "id": "receipt_1",
                    "source": "memory_receipts[0]",
                    "correlation_status": "correlated",
                    "mission_id": "mission_1",
                    "operation_id": "operation_1",
                    "status": "blocked",
                    "observed_at": "2026-07-09T19:59:50Z",
                }
            ],
            "receipt_linkage_required": True,
            "receipt_linkage_ready": True,
        },
        "freshness": {
            "status": "observed",
            "stale_after_seconds": 300,
            "sources": {
                "continuity_briefing": {
                    "available": True,
                    "status": "observed",
                    "observed_at": "2026-07-09T19:59:55Z",
                    "age_seconds": 5.0,
                    "stale": False,
                    "reason": "within_freshness_window",
                },
                "operator_surface": {
                    "available": True,
                    "status": "observed",
                    "observed_at": "2026-07-09T19:59:56Z",
                    "age_seconds": 4.0,
                    "stale": False,
                    "reason": "within_freshness_window",
                },
                "orb_surface": {
                    "available": True,
                    "status": "observed",
                    "observed_at": "2026-07-09T19:59:57Z",
                    "age_seconds": 3.0,
                    "stale": False,
                    "reason": "within_freshness_window",
                },
            },
        },
        "voice": {
            "status": "unknown",
            "listening": None,
            "speaking": None,
            "provider": "",
            "source": "",
            "reason": "voice_readback_not_available_in_orb_surface",
        },
        "visual_state": {
            "source_status": "observed",
            "mode": "assist",
            "semantic_state": "blocked",
            "render_state": "handback",
            "activity": "idle",
            "incident_pressure": "warning",
            "approval_required": True,
            "execution_state": "inactive",
            "handback_state": "operator_action_required",
            "panic_stop": {
                "status": "unknown",
                "ready": None,
                "source": "",
                "reason": "panic_stop_readback_not_available",
            },
        },
        "unreal_adapter": {
            "engine": "Unreal Engine",
            "engine_version": "5.8",
            "role": "governed_renderer_adapter",
            "status": "contract_defined_runtime_not_implemented",
            "technology_selection_status": "operator_confirmation_required",
            "project_selection_status": "operator_confirmation_required",
            "runtime_observed": False,
            "accepts_authority": False,
        },
        "authority": {
            "read_only": True,
            "render_only": True,
            "francis_core_authoritative": True,
            "grants_execution_authority": False,
            "grants_desktop_authority": False,
            "grants_network_authority": False,
            "grants_memory_write_authority": False,
            "grants_approval_authority": False,
        },
        "blockers": [],
        "limitations": [
            "unreal_technology_selection_pending_operator_confirmation",
            "unreal_project_selection_pending_operator_confirmation",
            "presence_projection_does_not_execute_actions",
        ],
    }


def _missing_evidence_snapshot() -> dict[str, Any]:
    snapshot = deepcopy(_ready_core_snapshot())
    snapshot["stage"].update(
        {
            "status": "blocked",
            "criteria": {
                "no_fabricated_state": False,
                "local_evidence_grounded": False,
                "action_receipt_linkage": True,
                "calm_non_theatrical_tone": True,
                "return_to_context": False,
            },
        }
    )
    snapshot["presence"].update(
        {
            "state": "quiet",
            "headline": "",
            "focus": {
                "source": "",
                "id": "",
                "objective": "",
                "title": "",
                "summary": "",
                "status": "",
                "next_step": "",
                "recommended_action": "",
                "updated_at": "",
            },
            "return_to_context": {
                "available": False,
                "source": "continuity_briefing",
                "focus_source": "",
                "fresh": False,
                "actionable": False,
                "objective": "",
                "summary": "",
                "reason": "",
                "next_step": "",
                "changed_since": "",
                "governance_hold": {
                    "active": False,
                    "gate": "",
                    "approval_id": "",
                    "approval_status": "",
                    "reason": "",
                },
                "last_meaningful_at": "",
                "reference_ids": [],
            },
        }
    )
    snapshot["intent"].update(
        {
            "available": False,
            "action": "",
            "source": "",
            "target_kind": "none",
            "target_id": "",
            "mission_id": "",
            "operation_id": "",
            "operation_plane": "",
            "reason": "",
            "next_step": "",
            "stage": "",
            "gate": "",
            "approval": {"id": "", "status": ""},
        }
    )
    snapshot["evidence"].update(
        {
            "status": "missing_evidence",
            "source_readbacks": {
                "continuity_briefing": False,
                "operator_surface": False,
                "orb_surface": False,
            },
            "correlation": {
                "status": "not_required",
                "focus_id": "",
                "mission_id": "",
                "operation_id": "",
                "action": "",
                "receipt_ids": [],
            },
            "references": [],
            "receipt_linkage_required": False,
            "receipt_linkage_ready": True,
        }
    )
    snapshot["freshness"].update(
        {
            "status": "missing_evidence",
            "sources": {
                source: {
                    "available": False,
                    "status": "missing_evidence",
                    "observed_at": None,
                    "age_seconds": None,
                    "stale": None,
                    "reason": "source_unavailable",
                }
                for source in ("continuity_briefing", "operator_surface", "orb_surface")
            },
        }
    )
    snapshot["visual_state"].update(
        {
            "source_status": "missing_evidence",
            "mode": "unknown",
            "semantic_state": "unknown",
            "render_state": "unknown",
            "activity": "unknown",
            "incident_pressure": "unknown",
            "approval_required": None,
            "execution_state": "unknown",
            "handback_state": "unknown",
        }
    )
    snapshot["blockers"] = ["no_fabricated_state", "local_evidence_grounded", "return_to_context"]
    return snapshot


def test_schema_validates_ready_francis_core_with_unreal_selection_pending() -> None:
    _validator().validate(_ready_core_snapshot())


def test_schema_validates_truthful_missing_evidence_status() -> None:
    _validator().validate(_missing_evidence_snapshot())


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("read_only", False),
        ("render_only", False),
        ("francis_core_authoritative", False),
        ("grants_execution_authority", True),
        ("grants_desktop_authority", True),
        ("grants_network_authority", True),
        ("grants_memory_write_authority", True),
        ("grants_approval_authority", True),
    ],
)
def test_schema_rejects_authority_drift(field: str, drifted_value: bool) -> None:
    snapshot = _ready_core_snapshot()
    snapshot["authority"][field] = drifted_value

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


@pytest.mark.parametrize(
    ("field", "drifted_value"),
    [
        ("engine_version", "5.7"),
        ("role", "autonomous_renderer"),
        ("technology_selection_status", "confirmed"),
        ("project_selection_status", "not_configured"),
        ("runtime_observed", True),
    ],
)
def test_schema_rejects_unreal_contract_drift(field: str, drifted_value: str | bool) -> None:
    snapshot = _ready_core_snapshot()
    snapshot["unreal_adapter"][field] = drifted_value

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_accepts_coherent_confirmed_selection_without_runtime_claim() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["unreal_adapter"].update(
        {
            "status": "operator_selection_confirmed_runtime_not_observed",
            "technology_selection_status": "operator_confirmed",
            "project_selection_status": "operator_confirmed",
        }
    )

    _validator().validate(snapshot)
    assert snapshot["unreal_adapter"]["runtime_observed"] is False
    assert snapshot["unreal_adapter"]["accepts_authority"] is False


def test_schema_accepts_runtime_observed_only_with_confirmed_selection() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["unreal_adapter"].update(
        {
            "status": "runtime_observed",
            "technology_selection_status": "operator_confirmed",
            "project_selection_status": "operator_confirmed",
            "runtime_observed": True,
        }
    )

    _validator().validate(snapshot)


def test_schema_rejects_fabricated_stage_readiness_without_evidence() -> None:
    snapshot = _missing_evidence_snapshot()
    snapshot["stage"]["status"] = "ready"

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_fabricated_evidence_readiness_without_readback() -> None:
    snapshot = _missing_evidence_snapshot()
    snapshot["evidence"]["status"] = "ready"

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_fabricated_unreal_runtime_readiness() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["unreal_adapter"]["status"] = "ready"
    snapshot["unreal_adapter"]["runtime_observed"] = True

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_ready_stage_with_stale_continuity() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["freshness"]["status"] = "stale"
    snapshot["freshness"]["sources"]["continuity_briefing"].update(
        {
            "status": "stale",
            "observed_at": "2026-07-09T19:50:00Z",
            "age_seconds": 600.0,
            "stale": True,
            "reason": "stale_after_threshold",
        }
    )

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_unknown_voice_state_encoded_as_false() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["voice"]["listening"] = False

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_intent_authority_drift() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["intent"]["grants_execution_authority"] = True

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)


def test_schema_rejects_unknown_snapshot_fields() -> None:
    snapshot = _ready_core_snapshot()
    snapshot["claimed_ready"] = True

    with pytest.raises(ValidationError):
        _validator().validate(snapshot)
