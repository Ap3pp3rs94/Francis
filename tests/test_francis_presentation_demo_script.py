from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "francis-presentation-demo.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_presentation_demo_can_include_one_visible_loop_proof_without_defaulting_live_authority() -> None:
    script = _script_text()

    assert "IncludeOneVisibleLoopProof" in script
    assert "UseFixtureOneVisibleLoopTarget" in script
    assert "OperatorApprovedOneVisibleLoopFixtureAction" in script
    assert "OperatorApprovedOneVisibleLoopSummonDecision" in script
    assert "$OneVisibleLoopArgs = @{" in script
    assert "@OneVisibleLoopArgs" in script
    assert "scripts\\francis-one-visible-loop-proof.ps1" in script
    assert "one_visible_loop_proof" in script
    assert "one_visible_loop_proof_blocked" in script
    assert "target_observer_status" in script
    assert "desktop_bridge_receipt_path" in script
    assert "receipt_trace_status_paths" in script
    assert "does not self-enable summon or default-enable the desktop bridge" in script
    assert "actual_chat_ui_render_verified" in script
    assert "actual_lens_ui_render_verified" in script
    assert "chat_lens_visibility_status" in script
    assert "receipt_trace_artifact_paths_present" in script
    assert "lens_status_contract_verified" in script
    assert "lens_status_test_contract_verified" in script
    assert "presentation_demo_contract_verified" in script
    assert "render_validation_required" in script
    assert "operator_decision_status" in script
    assert "operator_decision_question" in script
    assert "operator_decision_command" in script
    assert "operator_decision_authority_required" in script
    assert "operator_decision_self_granted" in script
