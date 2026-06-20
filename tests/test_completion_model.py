from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.completion_model import COMPLETION_MODEL_STATUS_KIND, completion_model_status_snapshot


def test_completion_model_snapshot_is_read_only_and_loop_guarded() -> None:
    payload = completion_model_status_snapshot()

    assert payload["ok"] is True
    assert payload["kind"] == COMPLETION_MODEL_STATUS_KIND
    assert payload["status"] == "ready"
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_execution_authority"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["current_phase"] == "Phase 2"
    assert payload["latest_ledger_entry"]["found"] is True
    assert payload["latest_ledger_entry"]["has_remaining_truthful_gap"] is True
    assert payload["stage17_status"]["found"] is True
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["read_only_contract"] is True
    assert payload["stage17_status"]["writes_repo"] is False
    assert payload["stage17_status"]["writes_data"] is False
    assert payload["stage17_status"]["grants_execution_authority"] is False
    assert payload["stage17_status"]["grants_mutation_authority"] is False
    assert payload["continue_loop_guard"]["status"] == "ready"
    assert payload["completion_percentage_model"]["movement_allowed_by_this_readback"] is False
    assert payload["routes"]["status"] == "/completion-model/status"
    assert payload["next_continue_decision"]["status"] == "bounded_slice_required"
    assert payload["next_continue_decision"]["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert payload["next_continue_decision"]["stage17_gap_preferred"] is True
    selected_gap_contract = payload["next_continue_decision"]["selected_gap_contract"]
    assert selected_gap_contract["kind"] == "francis.completion_model.selected_gap_contract"
    assert selected_gap_contract["status"] == "selected"
    assert selected_gap_contract["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert selected_gap_contract["selection_basis"] == "latest_open_stage17_remaining_gap"
    assert selected_gap_contract["selected_gap_is_stage17"] is True
    assert selected_gap_contract["read_only_selection"] is True
    assert selected_gap_contract["writes_repo"] is False
    assert selected_gap_contract["writes_data"] is False
    assert selected_gap_contract["grants_execution_authority"] is False
    assert selected_gap_contract["grants_mutation_authority"] is False
    assert selected_gap_contract["apply_authority_granted"] is False
    assert selected_gap_contract["proposal_evidence_apply_authority"] is False
    assert selected_gap_contract["proposal_review_authority"] is False
    assert selected_gap_contract["promotion_authority"] is False
    assert selected_gap_contract["capability_execution_authority"] is False
    assert selected_gap_contract["selected_gap_is_proposal_evidence_reference"] is False
    assert selected_gap_contract["proposal_evidence_refs_verified"] is False
    assert selected_gap_contract["proposal_review_receipts_verified"] is False
    assert selected_gap_contract["validation_receipts_verified"] is False
    assert selected_gap_contract["proposal_evidence_reference_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_queue_count_evidence"] is False
    assert selected_gap_contract["global_queue_count_recomputed"] is False
    assert selected_gap_contract["queue_count_authority_granted"] is False
    assert selected_gap_contract["stage17_readback_authority_denied"] is True
    assert selected_gap_contract["future_stage17_apply_requires"] == [
        "existing_governed_route",
        "dry_run_confirmation",
        "bounded_scope",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_queue_count_claim_requires"] == [
        "route_readback_or_apply_response",
        "projection_scope",
        "global_counts_included_flag",
        "before_after_counts",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_proposal_evidence_claim_requires"] == [
        "existing_governed_route",
        "proposal_artifact_ref",
        "proposal_review_receipt_ref",
        "validation_receipt_or_quality_evidence_ref",
        "bounded_plugin_id_scope",
        "focused_validation",
    ]
    checklist = {item["id"]: item for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["stage17_lane_gap_preserved"]["status"] == "ready"
    assert checklist["stage17_lane_gap_preserved"]["evidence"]
    assert checklist["dirty_worktree_preservation_guard"]["status"] == "enforced"
    assert checklist["material_ledger_update_guard"]["status"] == "enforced"
    assert checklist["stage17_readback_apply_boundary_guard"]["status"] == "enforced"
    assert checklist["stage17_queue_count_evidence_guard"]["status"] == "enforced"
    assert "global_counts_included" in checklist["stage17_queue_count_evidence_guard"]["evidence"]
    assert checklist["stage17_proposal_evidence_reference_guard"]["status"] == "enforced"
    assert "proposal-review receipt" in checklist["stage17_proposal_evidence_reference_guard"]["evidence"]


def test_completion_model_snapshot_blocks_when_sources_are_missing(tmp_path: Path) -> None:
    payload = completion_model_status_snapshot(
        ledger_path=tmp_path / "missing-ledger.md",
        build_manifest_path=tmp_path / "missing-build-manifest.md",
    )

    assert payload["ok"] is False
    assert payload["status"] == "blocked"
    assert payload["continue_loop_guard"]["status"] == "blocked"
    assert payload["continue_loop_guard"]["blocked_count"] == 3
    assert payload["next_continue_decision"]["selected_gap_source"] == "completion_model_sources"
    assert payload["next_continue_decision"]["next_smallest_truthful_gap"] == "restore_completion_model_sources"
    selected_gap_contract = payload["next_continue_decision"]["selected_gap_contract"]
    assert selected_gap_contract["status"] == "blocked"
    assert selected_gap_contract["selected_gap_source"] == "completion_model_sources"
    assert selected_gap_contract["selection_basis"] == "restore_completion_model_sources"
    assert selected_gap_contract["read_only_selection"] is True
    assert selected_gap_contract["apply_authority_granted"] is False
    checklist = {item["id"]: item["status"] for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["ledger_read"] == "blocked"
    assert checklist["build_manifest_read"] == "blocked"
    assert checklist["latest_validated_slice_identified"] == "blocked"
    assert checklist["stage17_lane_gap_preserved"] == "not_applicable"
    assert checklist["dirty_worktree_preservation_guard"] == "enforced"
    assert checklist["percentage_movement_guard"] == "enforced"
    assert checklist["material_ledger_update_guard"] == "enforced"
    assert checklist["stage17_readback_apply_boundary_guard"] == "enforced"
    assert checklist["stage17_queue_count_evidence_guard"] == "enforced"
    assert checklist["stage17_proposal_evidence_reference_guard"] == "enforced"


def test_completion_model_snapshot_reads_wrapped_roadmap_area(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "### 2026-06-19 - Wrapped ledger slice",
                "",
                "Roadmap area: Stage 6 / Lens MVP, Orb embodiment,",
                "voice-to-substrate routing, overlay command receipts,",
                "and P9 observability.",
                "",
                "Remaining truthful gap:",
                "",
                "- Keep going.",
                "",
                "## 6. Update rule",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["roadmap_area"] == (
        "Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate routing, "
        "overlay command receipts, and P9 observability."
    )


def test_completion_model_snapshot_keeps_stage17_gap_when_latest_entry_is_other_lane(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.",
                "",
                "### 2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52",
                "",
                "Roadmap area: Stage 17 / Capability Economy, operator-supplied proposal",
                "evidence and proposal-review queue reduction.",
                "",
                "Remaining truthful gap:",
                "",
                "- Stage 17 remains open. Continue the selected-scope queue.",
                "",
                "### 2026-06-19 - Manual acoustic Orb proof becomes an enforceable monitor gate",
                "",
                "Roadmap area: Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate",
                "routing, overlay command receipts, and P9 observability.",
                "",
                "Remaining truthful gap:",
                "",
                "- A real operator-spoken proof is still needed.",
                "- Stage 17 remains open, but this entry is not the Stage 17 lane.",
                "",
                "### 2026-06-19 - Completion model preserves Stage 17 readback across lane drift",
                "",
                "Roadmap area: Stage 17-adjacent Capability Economy, completion-model",
                "truth, and P9 observability readback.",
                "",
                "Remaining truthful gap:",
                "",
                "- Stage 17 remains open, but this is readback support work.",
                "",
                "## 6. Update rule",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["title"] == (
        "2026-06-19 - Completion model preserves Stage 17 readback across lane drift"
    )
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["readback_scope"] == "latest_stage17_ledger_entry"
    assert payload["stage17_status"]["latest_ledger_entry"]["title"] == (
        "2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52"
    )
    assert payload["stage17_status"]["latest_ledger_entry"]["roadmap_area"] == (
        "Stage 17 / Capability Economy, operator-supplied proposal evidence and proposal-review queue reduction."
    )
    assert payload["stage17_status"]["next_smallest_truthful_gap"] == (
        "select_from_latest_stage17_remaining_truthful_gap"
    )
    assert payload["next_continue_decision"]["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert payload["next_continue_decision"]["selected_ledger_title"] == (
        "2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52"
    )
    assert payload["next_continue_decision"]["selected_roadmap_area"] == (
        "Stage 17 / Capability Economy, operator-supplied proposal evidence and proposal-review queue reduction."
    )
    assert payload["next_continue_decision"]["stage17_gap_preferred"] is True
    assert payload["next_continue_decision"]["next_smallest_truthful_gap"] == (
        "- Stage 17 remains open. Continue the selected-scope queue."
    )
    assert payload["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_stage17"] is True
    assert (
        payload["next_continue_decision"]["selected_gap_contract"]["selection_basis"]
        == "latest_open_stage17_remaining_gap"
    )
    checklist = {item["id"]: item for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["stage17_lane_gap_preserved"]["status"] == "ready"
    assert checklist["stage17_lane_gap_preserved"]["evidence"] == (
        "2026-06-19 - Stage 17 selected-scope proposal evidence/review chunk 52"
    )
    assert checklist["stage17_readback_apply_boundary_guard"]["status"] == "enforced"
    assert checklist["stage17_queue_count_evidence_guard"]["status"] == "enforced"
    assert checklist["stage17_proposal_evidence_reference_guard"]["status"] == "enforced"
    selected_gap_contract = payload["next_continue_decision"]["selected_gap_contract"]
    assert selected_gap_contract["selected_gap_is_proposal_evidence_reference"] is False
    assert selected_gap_contract["proposal_evidence_refs_verified"] is False
    assert selected_gap_contract["proposal_review_receipts_verified"] is False
    assert selected_gap_contract["validation_receipts_verified"] is False
    assert selected_gap_contract["proposal_evidence_reference_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_queue_count_evidence"] is False
    assert selected_gap_contract["global_queue_count_recomputed"] is False
    assert selected_gap_contract["queue_count_authority_granted"] is False
    assert selected_gap_contract["future_stage17_queue_count_claim_requires"] == [
        "route_readback_or_apply_response",
        "projection_scope",
        "global_counts_included_flag",
        "before_after_counts",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_proposal_evidence_claim_requires"] == [
        "existing_governed_route",
        "proposal_artifact_ref",
        "proposal_review_receipt_ref",
        "validation_receipt_or_quality_evidence_ref",
        "bounded_plugin_id_scope",
        "focused_validation",
    ]


def test_completion_model_status_route_is_mounted_and_read_only() -> None:
    client = TestClient(create_app())

    response = client.get("/completion-model/status")

    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == COMPLETION_MODEL_STATUS_KIND
    assert body["status"] == "ready"
    assert body["read_only_contract"] is True
    assert body["writes_repo"] is False
    assert body["writes_data"] is False
    assert body["grants_execution_authority"] is False
    assert body["grants_mutation_authority"] is False
    assert body["stage17_status"]["read_only_contract"] is True
    assert body["stage17_status"]["writes_repo"] is False
    assert body["stage17_status"]["writes_data"] is False
    assert body["stage17_status"]["grants_execution_authority"] is False
    assert body["stage17_status"]["grants_mutation_authority"] is False
    assert body["completion_percentage_model"]["movement_allowed_by_this_readback"] is False
    assert body["next_continue_decision"]["selected_gap_contract"]["read_only_selection"] is True
    assert body["next_continue_decision"]["selected_gap_contract"]["apply_authority_granted"] is False
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_proposal_evidence_reference"] is False
    )
    assert body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_queue_count_evidence"] is False
