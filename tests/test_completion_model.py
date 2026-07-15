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
    assert payload["stage17_status"]["status"] == "closed"
    assert payload["stage17_status"]["stage17_closed_by_receipt"] is True
    assert payload["stage17_status"]["closure_receipt_id"] == ("stage17_capability_economy_closure_afd0fa32f7d1")
    assert payload["stage17_status"]["read_only_contract"] is True
    assert payload["stage17_status"]["writes_repo"] is False
    assert payload["stage17_status"]["writes_data"] is False
    assert payload["stage17_status"]["grants_execution_authority"] is False
    assert payload["stage17_status"]["grants_mutation_authority"] is False
    assert payload["continue_loop_guard"]["status"] == "ready"
    assert payload["completion_percentage_model"]["movement_allowed_by_this_readback"] is False
    assert payload["routes"]["status"] == "/completion-model/status"
    assert payload["active_workstream"] == {
        "found": True,
        "workstream": "Managed Copies Platform / Stage 18 groundwork.",
        "current_goal": (
            "a permission-gated safe-delta export authorization-request contract bound to a freshly "
            "validated export preflight and current live lineage/policy. It may create only a pending "
            "request receipt; it cannot approve or perform export. Production copy creation still requires "
            "real operator-supplied tenant and policy facts; those facts are not inferred or fabricated."
        ),
        "read_only_contract": True,
        "writes_repo": False,
        "writes_data": False,
        "grants_execution_authority": False,
        "grants_mutation_authority": False,
    }
    assert payload["next_continue_decision"]["status"] == "bounded_slice_required"
    assert payload["next_continue_decision"]["selected_gap_source"] == "active_workstream_current_goal"
    assert payload["next_continue_decision"]["active_workstream_preferred"] is True
    assert payload["next_continue_decision"]["stage17_gap_preferred"] is False
    selected_gap_contract = payload["next_continue_decision"]["selected_gap_contract"]
    assert selected_gap_contract["kind"] == "francis.completion_model.selected_gap_contract"
    assert selected_gap_contract["status"] == "selected"
    assert selected_gap_contract["selected_gap_source"] == "active_workstream_current_goal"
    assert selected_gap_contract["selection_basis"] == "active_workstream_current_goal"
    assert selected_gap_contract["selected_gap_is_stage17"] is False
    assert selected_gap_contract["selected_gap_is_active_workstream"] is True
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
    assert selected_gap_contract["selected_gap_is_projection_timing_evidence"] is False
    assert selected_gap_contract["projection_generated_at_verified"] is False
    assert selected_gap_contract["projection_is_fresh"] is False
    assert selected_gap_contract["projection_timing_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_publication_evidence"] is False
    assert selected_gap_contract["github_publication_verified"] is False
    assert selected_gap_contract["publication_marker_verified"] is False
    assert selected_gap_contract["publication_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_readback_evidence"] is False
    assert selected_gap_contract["worker_lane_readback_verified"] is False
    assert selected_gap_contract["worker_packet_verified"] is False
    assert selected_gap_contract["worker_readback_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_publication_handoff_evidence"] is False
    assert selected_gap_contract["worker_publication_handoff_verified"] is False
    assert selected_gap_contract["worker_publication_handoff_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_execution_liveness_evidence"] is False
    assert selected_gap_contract["worker_session_liveness_verified"] is False
    assert selected_gap_contract["worker_process_completion_verified"] is False
    assert selected_gap_contract["worker_execution_readback_authority_granted"] is False
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
    assert selected_gap_contract["future_stage17_projection_timing_claim_requires"] == [
        "route_readback_or_apply_response",
        "projection_generated_at_or_receipt_timestamp",
        "projection_scope",
        "bounded_plugin_id_scope_or_full_library_declaration",
        "global_counts_included_flag",
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
    assert selected_gap_contract["future_stage17_publication_claim_requires"] == [
        "pm_owned_publication_marker",
        "matching_prompt_sha256",
        "github_push_or_explicit_no_change_or_blocked_receipt",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_worker_readback_claim_requires"] == [
        "worker_lane_readback_path",
        "matching_prompt_sha256",
        "files_changed",
        "validation_run",
        "blockers_and_risks",
        "proposed_commit_scope",
        "next_recommended_prompt",
    ]
    assert selected_gap_contract["future_stage17_worker_publication_handoff_claim_requires"] == [
        "worker_lane_readback_path",
        "pm_owned_publication_marker",
        "matching_prompt_sha256",
        "github_push_or_explicit_no_change_or_blocked_receipt",
        "files_changed",
        "validation_run",
        "blockers_and_risks",
        "proposed_commit_scope",
        "next_recommended_prompt",
    ]
    assert selected_gap_contract["future_stage17_worker_execution_liveness_claim_requires"] == [
        "worker_session_path",
        "matching_prompt_sha256",
        "process_alive_or_exit_code",
        "worker_execution_completed_or_blocked_status",
        "lane_readback_path_or_last_message",
        "files_changed_or_no_change_scope",
        "validation_or_blocker_evidence",
    ]
    checklist = {item["id"]: item for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["stage17_lane_gap_preserved"]["status"] == "not_applicable"
    assert checklist["stage17_lane_gap_preserved"]["evidence"]
    assert checklist["dirty_worktree_preservation_guard"]["status"] == "enforced"
    assert checklist["material_ledger_update_guard"]["status"] == "enforced"
    assert checklist["stage17_readback_apply_boundary_guard"]["status"] == "enforced"
    assert checklist["stage17_queue_count_evidence_guard"]["status"] == "enforced"
    assert "global_counts_included" in checklist["stage17_queue_count_evidence_guard"]["evidence"]
    assert checklist["stage17_projection_timing_evidence_guard"]["status"] == "enforced"
    assert "generated_at or receipt timestamp" in checklist["stage17_projection_timing_evidence_guard"]["evidence"]
    assert checklist["stage17_proposal_evidence_reference_guard"]["status"] == "enforced"
    assert "proposal-review receipt" in checklist["stage17_proposal_evidence_reference_guard"]["evidence"]
    assert checklist["stage17_publication_evidence_guard"]["status"] == "enforced"
    assert "matching prompt hash" in checklist["stage17_publication_evidence_guard"]["evidence"]
    assert checklist["stage17_worker_readback_evidence_guard"]["status"] == "enforced"
    assert "worker packet claims" in checklist["stage17_worker_readback_evidence_guard"]["evidence"]
    assert checklist["stage17_worker_publication_handoff_guard"]["status"] == "enforced"
    assert "PM-owned publication marker" in checklist["stage17_worker_publication_handoff_guard"]["evidence"]
    assert checklist["stage17_worker_execution_liveness_guard"]["status"] == "enforced"
    assert "process liveness or exit code" in checklist["stage17_worker_execution_liveness_guard"]["evidence"]


def test_stage17_roadmap_steering_excludes_fr017_forearm_naming_collision() -> None:
    root = Path(__file__).resolve().parents[1]
    ledger = (root / "docs" / "operations" / "COMPLETION_LEDGER.md").read_text(encoding="utf-8")
    matrix = (root / "docs" / "operations" / "STAGE17_CLOSURE_MATRIX.md").read_text(encoding="utf-8")
    manifest = (root / "FR-017_Stage17_Package" / "FR-017-STAGE17-PACKAGE-MANIFEST.json").read_text(encoding="utf-8")

    assert "The current goal is a permission-gated safe-delta export authorization-request" in ledger
    assert "stage17_capability_economy_closure_afd0fa32f7d1" in ledger
    assert "The current goal is the FR-017 operator/physical evidence boundary" not in ledger
    assert "The remaining gates are the physically present" not in matrix
    assert "Explicitly permissioned closure-decision route" in matrix
    assert "excluded_collision" in manifest
    assert "Capability Economy records are not FR-017 forearm-cuff source material" in manifest


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
    assert checklist["stage17_projection_timing_evidence_guard"] == "enforced"
    assert checklist["stage17_proposal_evidence_reference_guard"] == "enforced"
    assert checklist["stage17_publication_evidence_guard"] == "enforced"
    assert checklist["stage17_worker_readback_evidence_guard"] == "enforced"
    assert checklist["stage17_worker_publication_handoff_guard"] == "enforced"
    assert checklist["stage17_worker_execution_liveness_guard"] == "enforced"


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


def test_completion_model_classifies_non_stage17_active_workstream(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        """# Ledger

Francis is in `Phase 2`.

Current active workstream: Lens / Stage 6 runtime repair.
The current goal is restore resident supervision without granting new authority.

### 2026-07-13 05:00Z - Runtime repair remains bounded

Remaining truthful gap:

- Restore resident supervision.
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["next_continue_decision"]["selected_gap_source"] == "active_workstream_current_goal"
    assert payload["next_continue_decision"]["active_workstream_preferred"] is True
    selected_gap_contract = payload["next_continue_decision"]["selected_gap_contract"]
    assert selected_gap_contract["selected_gap_is_active_workstream"] is True
    assert selected_gap_contract["selected_gap_is_stage17"] is False


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
    assert checklist["stage17_projection_timing_evidence_guard"]["status"] == "enforced"
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
    assert selected_gap_contract["selected_gap_is_projection_timing_evidence"] is False
    assert selected_gap_contract["projection_generated_at_verified"] is False
    assert selected_gap_contract["projection_is_fresh"] is False
    assert selected_gap_contract["projection_timing_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_publication_evidence"] is False
    assert selected_gap_contract["github_publication_verified"] is False
    assert selected_gap_contract["publication_marker_verified"] is False
    assert selected_gap_contract["publication_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_readback_evidence"] is False
    assert selected_gap_contract["worker_lane_readback_verified"] is False
    assert selected_gap_contract["worker_packet_verified"] is False
    assert selected_gap_contract["worker_readback_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_publication_handoff_evidence"] is False
    assert selected_gap_contract["worker_publication_handoff_verified"] is False
    assert selected_gap_contract["worker_publication_handoff_authority_granted"] is False
    assert selected_gap_contract["selected_gap_is_worker_execution_liveness_evidence"] is False
    assert selected_gap_contract["worker_session_liveness_verified"] is False
    assert selected_gap_contract["worker_process_completion_verified"] is False
    assert selected_gap_contract["worker_execution_readback_authority_granted"] is False
    assert selected_gap_contract["future_stage17_queue_count_claim_requires"] == [
        "route_readback_or_apply_response",
        "projection_scope",
        "global_counts_included_flag",
        "before_after_counts",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_projection_timing_claim_requires"] == [
        "route_readback_or_apply_response",
        "projection_generated_at_or_receipt_timestamp",
        "projection_scope",
        "bounded_plugin_id_scope_or_full_library_declaration",
        "global_counts_included_flag",
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
    assert selected_gap_contract["future_stage17_publication_claim_requires"] == [
        "pm_owned_publication_marker",
        "matching_prompt_sha256",
        "github_push_or_explicit_no_change_or_blocked_receipt",
        "focused_validation",
    ]
    assert selected_gap_contract["future_stage17_worker_readback_claim_requires"] == [
        "worker_lane_readback_path",
        "matching_prompt_sha256",
        "files_changed",
        "validation_run",
        "blockers_and_risks",
        "proposed_commit_scope",
        "next_recommended_prompt",
    ]
    assert selected_gap_contract["future_stage17_worker_publication_handoff_claim_requires"] == [
        "worker_lane_readback_path",
        "pm_owned_publication_marker",
        "matching_prompt_sha256",
        "github_push_or_explicit_no_change_or_blocked_receipt",
        "files_changed",
        "validation_run",
        "blockers_and_risks",
        "proposed_commit_scope",
        "next_recommended_prompt",
    ]
    assert selected_gap_contract["future_stage17_worker_execution_liveness_claim_requires"] == [
        "worker_session_path",
        "matching_prompt_sha256",
        "process_alive_or_exit_code",
        "worker_execution_completed_or_blocked_status",
        "lane_readback_path_or_last_message",
        "files_changed_or_no_change_scope",
        "validation_or_blocker_evidence",
    ]


def test_completion_model_selects_newest_timestamped_entry_from_newest_first_ledger(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        """# Ledger

## 2. Current build phase

Francis is in `Phase 2`.

### 2026-07-13 00:41Z - Stage 17 software posture broad-validated at final head

Remaining truthful gap:

- Stage 17 remains open until FR-017 physical evidence and the final governed decision are recorded.

### 2026-07-12 20:04Z - Stage 1 later-lane hardening

Remaining truthful gap:

- Stage 1 visual tuning remains optional.

### 2026-07-10 14:31Z - Stage 17 software criteria ready for closure review

Remaining truthful gap:

- Final-head GitHub CI must pass before broad validation.
""",
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["title"] == (
        "2026-07-13 00:41Z - Stage 17 software posture broad-validated at final head"
    )
    assert payload["stage17_status"]["latest_ledger_entry"]["title"] == (
        "2026-07-13 00:41Z - Stage 17 software posture broad-validated at final head"
    )
    assert "FR-017 physical evidence" in payload["stage17_status"]["latest_ledger_entry"]["remaining_truthful_gap"]
    assert (
        "Final-head GitHub CI must pass"
        not in payload["stage17_status"]["latest_ledger_entry"]["remaining_truthful_gap"]
    )


def test_completion_model_snapshot_uses_archive_when_main_ledger_is_compacted(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "Francis is in `Phase 2` per `docs/canonical/BUILD_MANIFEST.md`.",
                "",
                "### 2026-07-03 - Stage 6 current compact ledger entry",
                "",
                "Roadmap area: Stage 6 / Lens MVP and P9 observability.",
                "",
                "Remaining truthful gap:",
                "",
                "- Keep live Orb proof honest.",
                "",
                "## 6. Update rule",
            ]
        ),
        encoding="utf-8",
    )
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    archive_path = archive_dir / "COMPLETION_LEDGER_2026-06.md"
    archive_path.write_text(
        "\n".join(
            [
                "# FRANCIS - COMPLETION_LEDGER archive (2026-06)",
                "",
                "### 2026-06-20 - Stage 17 archived governed apply gap",
                "",
                "Roadmap area: Stage 17 / Capability Economy, archived proposal evidence.",
                "",
                "Remaining truthful gap:",
                "",
                "- Stage 17 remains open. Continue the archived governed apply queue.",
            ]
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.md"
    manifest.write_text("# Manifest (Phase 2)\n", encoding="utf-8")

    payload = completion_model_status_snapshot(
        ledger_path=ledger,
        ledger_archive_dir_path=archive_dir,
        build_manifest_path=manifest,
    )

    assert payload["latest_ledger_entry"]["title"] == "2026-07-03 - Stage 6 current compact ledger entry"
    assert payload["stage17_status"]["found"] is True
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["archive_fallback_used"] is True
    assert payload["stage17_status"]["latest_ledger_entry"]["title"] == (
        "2026-06-20 - Stage 17 archived governed apply gap"
    )
    assert payload["next_continue_decision"]["selected_gap_source"] == "stage17_latest_ledger_entry"
    assert payload["next_continue_decision"]["next_smallest_truthful_gap"] == (
        "- Stage 17 remains open. Continue the archived governed apply queue."
    )
    expected_archive_source = archive_path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    assert expected_archive_source in payload["stage17_status"]["archive_source_documents"]


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
    assert body["active_workstream"]["found"] is True
    assert body["next_continue_decision"]["selected_gap_source"] == "active_workstream_current_goal"
    assert body["next_continue_decision"]["selected_gap_contract"]["read_only_selection"] is True
    assert body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_stage17"] is False
    assert body["next_continue_decision"]["selected_gap_contract"]["apply_authority_granted"] is False
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_proposal_evidence_reference"] is False
    )
    assert body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_queue_count_evidence"] is False
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_projection_timing_evidence"] is False
    )
    assert body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_publication_evidence"] is False
    assert body["next_continue_decision"]["selected_gap_contract"]["publication_authority_granted"] is False
    assert body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_worker_readback_evidence"] is False
    assert body["next_continue_decision"]["selected_gap_contract"]["worker_readback_authority_granted"] is False
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_worker_publication_handoff_evidence"]
        is False
    )
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["worker_publication_handoff_authority_granted"] is False
    )
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["selected_gap_is_worker_execution_liveness_evidence"]
        is False
    )
    assert (
        body["next_continue_decision"]["selected_gap_contract"]["worker_execution_readback_authority_granted"] is False
    )
