from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

from francis.world_state.presence import build_grounded_presence_snapshot


def _schema() -> dict[str, object]:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "schemas" / "grounded_presence_snapshot.schema.json").read_text(encoding="utf-8"))


def test_grounded_presence_snapshot_validates_and_preserves_authority_boundary() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={
            "headline": "Review the blocked mission before continuing.",
            "focus": [
                {
                    "id": "mission_1",
                    "objective": "Recover the governed mission.",
                    "title": "Blocked mission",
                    "summary": "The latest operation needs review.",
                    "status": "blocked",
                    "next_step": "Inspect the result receipt.",
                    "recommended_action": "review_result",
                    "current_task": {
                        "mission_id": "mission_1",
                        "operation_id": "operation_1",
                        "operation_plane": "P7_EXECUTION",
                        "reason": "The operation is waiting for operator review.",
                        "next_step": "Inspect the result receipt.",
                        "gate": "operator_review",
                        "approval_id": "approval_1",
                        "approval_status": "pending",
                        "trace_id": "trace_1",
                        "run_id": "run_1",
                        "artifact_dir": "data/artifacts/run_1",
                    },
                }
            ],
            "memory_receipts": [
                {
                    "receipt_id": "receipt_1",
                    "mission_id": "mission_1",
                    "operation_id": "operation_1",
                    "operation_status": "blocked",
                    "ts": 1783598390.0,
                }
            ],
            "generated_at": 1783598395.0,
        },
        operator={
            "available": True,
            "observed_at": 1783598396.0,
            "control_mode": {"id": "assist"},
            "backlog": {"pending_approvals": 1},
        },
        orb={
            "available": True,
            "observed_at": 1783598397.0,
            "state": {
                "semantic_state": "blocked",
                "render_state": "handback",
                "activity_intensity": {"level": "idle"},
                "incident_pressure": {"level": "warning"},
                "handback_state": {"state": "operator_action_required"},
            },
        },
        generated_at="2026-07-09T12:00:00+00:00",
    )

    errors = list(Draft202012Validator(_schema()).iter_errors(snapshot))

    assert errors == []
    assert snapshot["stage"]["status"] == "ready"
    assert snapshot["intent"]["request_only"] is True
    assert snapshot["intent"]["operation_id"] == "operation_1"
    assert snapshot["intent"]["grants_execution_authority"] is False
    assert snapshot["evidence"]["receipt_linkage_ready"] is True
    assert snapshot["evidence"]["correlation"]["receipt_ids"] == ["receipt_1"]
    assert snapshot["freshness"]["status"] == "observed"
    assert snapshot["voice"]["status"] == "unknown"
    assert snapshot["voice"]["listening"] is None
    assert snapshot["visual_state"]["approval_required"] is True
    assert snapshot["presence"]["return_to_context"]["next_step"] == "Inspect the result receipt."
    assert snapshot["unreal_adapter"]["technology_selection_status"] == "operator_confirmation_required"
    assert snapshot["authority"]["grants_execution_authority"] is False
    assert snapshot["authority"]["grants_approval_authority"] is False


def test_grounded_presence_blocks_actionable_briefing_without_receipt() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={
            "headline": "An action needs review.",
            "focus": [{"title": "Action", "recommended_action": "review_result"}],
            "generated_at": 1783598395.0,
        },
        operator={"available": True, "observed_at": 1783598396.0},
        orb={"available": True, "observed_at": 1783598397.0, "state": {}},
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["stage"]["status"] == "blocked"
    assert "action_receipt_linkage" in snapshot["blockers"]
    assert snapshot["evidence"]["receipt_linkage_required"] is True
    assert snapshot["evidence"]["receipt_linkage_ready"] is False


def test_grounded_presence_projects_confirmed_unreal_selection_without_runtime_claim() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={},
        operator={"available": False},
        orb={"available": False},
        unreal_selection={"status": "operator_selection_confirmed", "valid": True},
        generated_at="2026-07-10T12:00:00+00:00",
    )

    unreal = snapshot["unreal_adapter"]
    assert unreal["status"] == "operator_selection_confirmed_runtime_not_observed"
    assert unreal["technology_selection_status"] == "operator_confirmed"
    assert unreal["project_selection_status"] == "operator_confirmed"
    assert unreal["runtime_observed"] is False
    assert unreal["accepts_authority"] is False
    assert "unreal_runtime_not_observed" in snapshot["limitations"]
    assert "unreal_project_not_configured" not in snapshot["limitations"]


def test_grounded_presence_projects_only_fresh_observed_unreal_runtime() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={},
        operator={"available": False},
        orb={"available": False},
        unreal_selection={"status": "operator_selection_confirmed", "valid": True},
        unreal_runtime={"status": "runtime_observed", "observed": True},
        generated_at="2026-07-10T12:00:00+00:00",
    )

    assert snapshot["unreal_adapter"]["status"] == "runtime_observed"
    assert snapshot["unreal_adapter"]["runtime_observed"] is True
    assert "unreal_runtime_not_observed" not in snapshot["limitations"]


def test_grounded_presence_does_not_accept_unrelated_receipt() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={
            "headline": "An action needs review.",
            "focus": [{"id": "mission_1", "title": "Action", "recommended_action": "review_result"}],
            "memory_receipts": [{"receipt_id": "receipt_other", "mission_id": "mission_2"}],
            "generated_at": 1783598395.0,
        },
        operator={"available": True, "observed_at": 1783598396.0},
        orb={"available": True, "observed_at": 1783598397.0, "state": {}},
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["stage"]["status"] == "blocked"
    assert snapshot["evidence"]["references"] == []


def test_grounded_presence_does_not_invent_empty_state() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={},
        operator={"available": False},
        orb={"available": False},
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["stage"]["status"] == "blocked"
    assert snapshot["presence"]["truthful"] is True
    assert snapshot["presence"]["headline"] == ""
    assert snapshot["presence"]["state"] == "unknown"
    assert snapshot["voice"]["listening"] is None
    assert snapshot["visual_state"]["execution_state"] == "unknown"
    assert "no_fabricated_state" in snapshot["blockers"]


def test_grounded_presence_blocks_stale_continuity_instead_of_claiming_grounding() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={
            "headline": "This readback is too old to present as current.",
            "generated_at": 1783598000.0,
        },
        operator={"available": False},
        orb={"available": False},
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["stage"]["status"] == "blocked"
    assert snapshot["freshness"]["status"] == "stale"
    assert snapshot["freshness"]["sources"]["continuity_briefing"]["stale"] is True
    assert snapshot["presence"]["return_to_context"]["fresh"] is False
    assert "local_evidence_grounded" in snapshot["blockers"]


def test_grounded_presence_observes_voice_only_when_voice_readback_exists() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={"headline": "Voice state is source-backed.", "generated_at": 1783598395.0},
        operator={"available": True, "observed_at": 1783598396.0},
        orb={
            "available": True,
            "observed_at": 1783598397.0,
            "state": {
                "voice": {
                    "listening": True,
                    "speaking": False,
                    "provider": "local_voice",
                }
            },
        },
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["voice"] == {
        "status": "observed",
        "listening": True,
        "speaking": False,
        "provider": "local_voice",
        "source": "orb.state.voice",
        "reason": "observed_voice_readback",
    }


def test_grounded_presence_observes_voice_identity_without_inventing_activity() -> None:
    snapshot = build_grounded_presence_snapshot(
        briefing={"headline": "Voice identity is source-backed.", "generated_at": 1783598395.0},
        operator={"available": True, "observed_at": 1783598396.0},
        orb={
            "available": True,
            "observed_at": 1783598397.0,
            "state": {},
            "voice": {
                "runtime_provider": "ElevenLabs",
                "identity_status": "input_output_contract_split",
                "listening": None,
                "speaking": None,
            },
        },
        generated_at="2026-07-09T12:00:00+00:00",
    )

    assert snapshot["voice"] == {
        "status": "observed",
        "listening": None,
        "speaking": None,
        "provider": "ElevenLabs",
        "source": "orb.voice",
        "reason": "voice_identity_observed_activity_state_unknown",
    }
    assert "voice_identity_observed_activity_state_unknown" in snapshot["limitations"]
    assert "voice_identity_readback_not_ready" in snapshot["limitations"]
    assert "voice_state_is_unknown_without_observed_voice_readback" not in snapshot["limitations"]
