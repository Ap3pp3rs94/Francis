from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from powershell_script_runner import run_powershell_script


def _powershell() -> str:
    exe = shutil.which("powershell") or shutil.which("pwsh")
    if not exe:
        pytest.skip("PowerShell is not available")
    return exe


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _run_completion_model(*args: str) -> subprocess.CompletedProcess[str]:
    return run_powershell_script(
        _powershell(),
        _repo_root() / "scripts" / "francis-completion-model.ps1",
        args,
        cwd=_repo_root(),
        timeout_seconds=30,
    )


def test_francis_completion_model_status_projects_ledger_backed_loop_guard() -> None:
    result = _run_completion_model("-Mode", "Status")

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["ok"] is True
    assert payload["kind"] == "francis.completion_model.status"
    assert payload["status"] == "ready"
    assert payload["read_only_contract"] is True
    assert payload["writes_repo"] is False
    assert payload["writes_data"] is False
    assert payload["grants_execution_authority"] is False
    assert payload["grants_mutation_authority"] is False
    assert payload["source_documents"]["completion_ledger"] == "docs/operations/COMPLETION_LEDGER.md"
    assert payload["source_documents"]["build_manifest"] == "docs/canonical/BUILD_MANIFEST.md"
    assert payload["current_phase"] == "Phase 2"
    assert payload["latest_ledger_entry"]["found"] is True
    assert payload["stage17_status"]["found"] is True
    assert payload["stage17_status"]["status"] == "open"
    assert payload["stage17_status"]["read_only_contract"] is True
    assert payload["stage17_status"]["writes_repo"] is False
    assert payload["stage17_status"]["writes_data"] is False
    assert payload["stage17_status"]["grants_execution_authority"] is False
    assert payload["stage17_status"]["grants_mutation_authority"] is False
    assert payload["continue_loop_guard"]["status"] == "ready"
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

    checklist_ids = {item["id"] for item in payload["continue_loop_guard"]["checklist"]}
    assert "ledger_read" in checklist_ids
    assert "build_manifest_read" in checklist_ids
    assert "latest_validated_slice_identified" in checklist_ids
    assert "remaining_gap_named" in checklist_ids
    assert "stage17_lane_gap_preserved" in checklist_ids
    assert "dirty_worktree_preservation_guard" in checklist_ids
    assert "percentage_movement_guard" in checklist_ids
    assert "single_bounded_slice_guard" in checklist_ids
    assert "material_ledger_update_guard" in checklist_ids
    assert "stage17_readback_apply_boundary_guard" in checklist_ids
    assert "stage17_queue_count_evidence_guard" in checklist_ids
    assert "stage17_projection_timing_evidence_guard" in checklist_ids
    assert "stage17_proposal_evidence_reference_guard" in checklist_ids
    assert "stage17_publication_evidence_guard" in checklist_ids
    assert "stage17_worker_readback_evidence_guard" in checklist_ids
    assert "stage17_worker_publication_handoff_guard" in checklist_ids
    assert "stage17_worker_execution_liveness_guard" in checklist_ids
    checklist = {item["id"]: item for item in payload["continue_loop_guard"]["checklist"]}
    assert checklist["stage17_lane_gap_preserved"]["status"] == "ready"
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


def test_francis_completion_model_percentages_are_evidence_gated_not_invented() -> None:
    payload = json.loads(_run_completion_model("-Mode", "Status").stdout)
    percentage_model = payload["completion_percentage_model"]

    assert percentage_model["status"] == "evidence_gated"
    assert percentage_model["numeric_baseline_declared_here"] is False
    assert percentage_model["overall_project_percent"] is None
    assert percentage_model["current_build_phase_percent"] is None
    assert percentage_model["current_task_percent"] is None
    assert percentage_model["movement_allowed_by_this_readback"] is False
    assert "known_baseline_source" in percentage_model["required_to_move"]
    assert "validated_repo_evidence" in percentage_model["required_to_move"]
    assert "ledger_backed_gate_or_milestone_change" in percentage_model["required_to_move"]
    assert "explicit_remaining_blockers" in percentage_model["required_to_move"]


def test_francis_completion_model_reports_stage17_artifact_reconstruction_evidence(tmp_path: Path) -> None:
    receipt_root = tmp_path / "artifact_reconstructions"
    receipt_root.mkdir()
    receipt_path = receipt_root / "stage17_artifact_reconstruction_batch_test_receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "actor": "stage17.operator",
                "after_global_remediation_queue_count": 16,
                "after_proposal_lineage_reconstruction_required_count": 79,
                "after_remediation_queue_count": 16,
                "after_validation_receipt_reconstruction_required_count": 79,
                "before_global_remediation_queue_count": 17,
                "before_proposal_lineage_reconstruction_required_count": 83,
                "before_remediation_queue_count": 17,
                "before_validation_receipt_reconstruction_required_count": 83,
                "candidate_reduction_count": 1,
                "contract": "stage17_capability_pack_artifact_reconstruction_receipt_v1",
                "dry_run_confirmation": {"fingerprint_matched": True},
                "global_counts_included": True,
                "governance": {
                    "approval_authority": False,
                    "execution_authority": False,
                    "memory_write": False,
                    "promotion_authority": False,
                    "writes_batch_reconstruction_receipt": True,
                },
                "kind": "plugin.capability_pack.artifact_reconstruction.receipt",
                "proposal_lineage_write_count": 4,
                "projection_scope": "full_library",
                "queue_count_contract": "stage17_capability_pack_artifact_reconstruction_batch_queue_evidence_v1",
                "receipt_id": "stage17_artifact_reconstruction_batch_test_receipt",
                "recorded_capability_count": 4,
                "recorded_pack_count": 1,
                "route": "/plugins/capabilities/packs/quality/evidence/remediation/reconstruct",
                "selected_reconstruction_pack_ids": ["legacy.generated.capabilityoperatorreviewdecisionplugin"],
                "selection_strategy": "smallest_full_pack_first",
                "status": "recorded",
                "validation_receipt_write_count": 4,
            }
        ),
        encoding="utf-8",
    )

    result = _run_completion_model(
        "-Mode",
        "Status",
        "-ArtifactReconstructionReceiptRootPath",
        str(receipt_root),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    evidence = payload["stage17_artifact_reconstruction_evidence"]
    assert evidence["found"] is True
    assert evidence["status"] == "ready"
    assert evidence["read_only_contract"] is True
    assert evidence["writes_repo"] is False
    assert evidence["writes_data"] is False
    assert evidence["clean_json"] is True
    assert evidence["receipt_id"] == "stage17_artifact_reconstruction_batch_test_receipt"
    assert evidence["contract"] == "stage17_capability_pack_artifact_reconstruction_receipt_v1"
    assert evidence["durable_receipt_contract_verified"] is True
    assert evidence["queue_count_contract_verified"] is True
    assert evidence["selection_strategy"] == "smallest_full_pack_first"
    assert evidence["projection_scope"] == "full_library"
    assert evidence["global_counts_included"] is True
    assert evidence["before_global_remediation_queue_count"] == 17
    assert evidence["after_global_remediation_queue_count"] == 16
    assert evidence["before_remediation_queue_count"] == 17
    assert evidence["after_remediation_queue_count"] == 16
    assert evidence["before_validation_receipt_reconstruction_required_count"] == 83
    assert evidence["after_validation_receipt_reconstruction_required_count"] == 79
    assert evidence["before_proposal_lineage_reconstruction_required_count"] == 83
    assert evidence["after_proposal_lineage_reconstruction_required_count"] == 79
    assert evidence["candidate_reduction_count"] == 1
    assert evidence["validation_receipt_write_count"] == 4
    assert evidence["proposal_lineage_write_count"] == 4
    assert evidence["recorded_pack_count"] == 1
    assert evidence["recorded_capability_count"] == 4
    assert evidence["dry_run_fingerprint_matched"] is True
    assert evidence["writes_batch_reconstruction_receipt"] is True
    assert evidence["approval_authority"] is False
    assert evidence["promotion_authority"] is False
    assert evidence["execution_authority"] is False
    assert evidence["memory_write"] is False
    assert evidence["selected_reconstruction_pack_ids"] == ["legacy.generated.capabilityoperatorreviewdecisionplugin"]


def test_francis_completion_model_script_reads_wrapped_roadmap_area(tmp_path: Path) -> None:
    ledger = tmp_path / "ledger.md"
    ledger.write_text(
        "\n".join(
            [
                "# Ledger",
                "",
                "### 2026-06-19 - Wrapped script ledger slice",
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

    result = _run_completion_model(
        "-Mode",
        "Status",
        "-LedgerPath",
        str(ledger),
        "-BuildManifestPath",
        str(manifest),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["latest_ledger_entry"]["roadmap_area"] == (
        "Stage 6 / Lens MVP, Orb embodiment, voice-to-substrate routing, "
        "overlay command receipts, and P9 observability."
    )


def test_francis_completion_model_script_keeps_stage17_gap_when_latest_entry_is_other_lane(
    tmp_path: Path,
) -> None:
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

    result = _run_completion_model(
        "-Mode",
        "Status",
        "-LedgerPath",
        str(ledger),
        "-BuildManifestPath",
        str(manifest),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
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
    assert checklist["stage17_publication_evidence_guard"]["status"] == "enforced"
    assert checklist["stage17_worker_readback_evidence_guard"]["status"] == "enforced"
    assert checklist["stage17_worker_publication_handoff_guard"]["status"] == "enforced"
    assert checklist["stage17_worker_execution_liveness_guard"]["status"] == "enforced"
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


def test_francis_completion_model_script_is_status_only() -> None:
    script = (_repo_root() / "scripts" / "francis-completion-model.ps1").read_text(encoding="utf-8")

    assert "[ValidateSet('Status')]" in script
    assert "read_only_contract = $true" in script
    assert "writes_repo = $false" in script
    assert "writes_data = $false" in script
    assert "grants_execution_authority = $false" in script
    assert "grants_mutation_authority = $false" in script
    assert "apply_authority_granted = $false" in script
    assert "proposal_review_authority = $false" in script
    assert "capability_execution_authority = $false" in script
    assert "selected_gap_is_proposal_evidence_reference = $false" in script
    assert "proposal_evidence_reference_authority_granted = $false" in script
    assert "selected_gap_is_queue_count_evidence = $false" in script
    assert "queue_count_authority_granted = $false" in script
    assert "selected_gap_is_projection_timing_evidence = $false" in script
    assert "projection_timing_authority_granted = $false" in script
    assert "selected_gap_is_publication_evidence = $false" in script
    assert "publication_authority_granted = $false" in script
    assert "selected_gap_is_worker_readback_evidence = $false" in script
    assert "worker_readback_authority_granted = $false" in script
    assert "selected_gap_is_worker_publication_handoff_evidence = $false" in script
    assert "worker_publication_handoff_authority_granted = $false" in script
    assert "selected_gap_is_worker_execution_liveness_evidence = $false" in script
    assert "worker_execution_readback_authority_granted = $false" in script
    assert "Set-Content" not in script
    assert "Out-File" not in script
    assert "Add-Content" not in script
