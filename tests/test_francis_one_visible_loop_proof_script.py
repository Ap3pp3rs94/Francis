from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "francis-one-visible-loop-proof.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_one_visible_loop_proof_preserves_operator_authority_boundaries() -> None:
    script = _script_text()

    assert "francis.one_visible_loop.proof" in script
    assert "OperatorApprovedSummonDecision" in script
    assert "OperatorApprovedFixtureAction" in script
    assert "does_not_self_enable_summon" in script
    assert "does_not_default_enable_desktop_bridge" in script
    assert "approve_summon_enable_and_live_safe_target_bridge_proof" in script
    assert "first_missing_required_before_enable" in script
    assert "hotkey_runtime_readback" in script
    assert "tray_runtime_readback" in script
    assert "overlay_runtime_readback" in script
    assert "operator_decision_queue" in script
    assert "approve_resident_host_process_supervision_authority_request" in script
    assert "Austin: approve the governed process-supervision authority path" in script
    assert "script_would_grant_authority" in script
    assert "script_would_execute" in script
    assert "self_granted" in script
    assert "scripts/lens-host-supervisor.ps1 -Mode Status" in script
    assert "lens-canonical-summon-runtime-proof.ps1" in script
    assert "_canonical_summon_runtime_observed" in script
    assert "canonical_live_summon_runtime_readback" in script
    assert "canonical_summon_authority_already_evidenced" in script
    assert "summon_authority_evidence_observed" in script
    assert "one_visible_loop_safe_target_effect_and_render_proof" in script
    assert "configure_and_approve_live_safe_target_bridge_proof" in script
    assert "perform_browser_or_live_chat_lens_ui_proof" in script
    assert "and actual_render_verified" in script
    assert '"physical_input_used": False' in script
    assert "actual_chat_ui_render_verified" in script
    assert "actual_lens_ui_render_verified" in script
    assert "ui_contract_visible_render_unverified" in script
    assert "receipt_trace_artifact_paths_present" in script
    assert "lens_status_contract_verified" in script
    assert "lens_status_test_contract_verified" in script
    assert "presentation_demo_contract_verified" in script
    assert "browser_or_live_chat_lens_ui_proof" in script
    assert "fixture_safe_target_is_not_live_desktop_completion" in script
    assert 'payload.get("status") == "overlay_running"' in script
    assert 'encoding="utf-8-sig"' in script
    assert "yyyyMMdd_HHmmssfff" in script


def test_one_visible_loop_proof_exercises_confirmed_effect_with_fixture_safe_target() -> None:
    script = _script_text()

    assert "UseFixtureSafeTarget" in script
    assert "UseLiveSafeTarget" in script
    assert "LiveSafeTargetApprovalId" in script
    assert "ConfirmLiveSafeTargetAction" in script
    assert 'LIVE_SAFE_TARGET_ACTION = "lens.orb_desktop_bridge.live_safe_target"' in script
    assert "live_safe_target_approval_invalid_or_expired" in script
    assert '"delegated_operator_approval": approval.get("decision_kind") == "delegated_operator_approval"' in script
    assert "_start_live_safe_target" in script
    assert "_find_live_safe_target" in script
    assert 'if "edit" in str(win32gui.GetClassName(hwnd)).strip().casefold()' in script
    assert "[System.Drawing.Point]::new(80, 80)" in script
    assert "[System.Drawing.Size]::new(520, 240)" in script
    assert '"error_detail": str(exc)[:240]' in script
    assert 'os.environ["FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE"] = "1"' in script
    assert 'os.environ["FRANCIS_ORB_OPERATOR_STATE_DIR"] = str(_repo_root() / ".francis" / "orb_operator")' in script
    assert '"kind": "mouse.move"' in script
    assert '"kind": "keyboard.type"' in script
    assert '"metadata": {"expected_target_title": LIVE_SAFE_TARGET_TITLE}' in script
    assert '"proof_mode": "live_operator_approved_safe_target"' in script
    assert '"safe_target_process_stopped"' in script
    assert '"physical_input_performed": False' in script
    assert '"uses_user_os_cursor": False' in script
    assert "Francis One Visible Loop Safe Target" in script
    assert 'os.environ["FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE"] = "1"' in script
    assert '"mode": "orb_pointer"' in script
    assert '"kind": "keyboard.type"' in script
    assert "desktop_effect_confirmed" in script
    assert "target_observer_status" in script
    assert 'desktop_bridge.get("target_observer_status")' in script
    assert 'desktop_bridge.get("receipt_path")' in script
    assert "operator_receipt_path" in script
    assert "desktop_bridge_receipt_path" in script
    assert "uses_user_os_cursor" in script
    assert "user_mouse_taken" in script
    assert "physical_input_performed" in script
