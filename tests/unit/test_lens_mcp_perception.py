"""Lens <-> MCP read-only perception bridge: the body reaches the nervous system.

These assert the governance contract: read-only tools are perceivable and leave a
receipt; mutating/approval tools are refused AT THE BRIDGE (no second path around a
gate, and the mutating tool is never invoked); nothing claims residency; and the
API surface is permission-gated.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from francis.api.app import create_app
from francis.lens import (
    lens_mcp_perception_contract,
    lens_mcp_perception_receipts,
    lens_observe_overlay_region,
    lens_perceive_via_mcp,
)
from francis.lens.mcp_perception import _receipt_root

pytestmark = pytest.mark.unit

_ACTOR = "test.lens.mcp"


def test_contract_lists_only_read_only_tools_and_claims_not_resident(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    out = lens_mcp_perception_contract()
    assert out["ok"] is True
    names = {t["name"] for t in out["perceivable_tools"]}
    # Senses are present...
    assert "francis.health" in names
    assert "francis.repo.status" in names
    # ...mutating / approval tools are NOT perceivable.
    assert "francis.command.propose" not in names
    assert "francis.input.execute_approved" not in names
    assert "francis.takeover.start_approved" not in names
    assert out["overlay_observation"]["route"] == "/lens/mcp/observe"
    assert out["overlay_observation"]["uses_existing_overlay"] is True
    assert out["overlay_observation"]["creates_overlay"] is False
    assert out["overlay_observation"]["requires_overlay_coordinate_model"] is True
    assert out["overlay_observation"]["spatial_contract_schema_version"] == 1
    assert out["overlay_observation"]["reports_requested_region"] is True
    assert out["overlay_observation"]["reports_mapped_overlay_region"] is True
    assert out["overlay_observation"]["reports_actual_inspected_observed_and_captured_regions"] is True
    assert out["overlay_observation"]["reports_region_basis_readback"] is True
    assert out["overlay_observation"]["reports_region_comparison_readback"] is True
    assert out["overlay_observation"]["reports_confidence_breakdown"] is True
    assert out["overlay_observation"]["reports_replay_manifest"] is True
    assert out["overlay_observation"]["screenshots"] is False
    assert out["overlay_observation"]["pixels"] is False
    assert out["governance"]["resident"] is False
    assert out["governance"]["grants_execution_authority"] is False


def test_perceive_read_only_tool_succeeds_and_writes_receipt(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    out = lens_perceive_via_mcp("francis.health", {}, actor=_ACTOR)
    assert out["status"] == "perceived"
    assert out["ok"] is True
    assert out["mcp_result"]["tool"] == "francis.health"
    assert out["governance"]["resident"] is False
    # A receipt was written as auditable evidence.
    assert out["receipt"]["decision"] == "perceived"
    assert list(_receipt_root().glob("*.json")), "no perception receipt written"
    rb = lens_mcp_perception_receipts()
    assert rb["count"] >= 1
    assert any(r.get("tool") == "francis.health" for r in rb["receipts"])


def test_perceive_refuses_mutating_tool_at_bridge_without_invoking_it(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "gw"))
    out = lens_perceive_via_mcp(
        "francis.command.propose",
        {"actor": _ACTOR, "kind": "git_status", "objective": "should never run"},
        actor=_ACTOR,
    )
    assert out["ok"] is False
    assert out["status"] == "refused"
    assert out["error"] == "tool_not_read_only_perceivable"
    # The mutating tool was never invoked: no proposal artifact exists.
    proposals = tmp_path / "gw" / "proposals"
    assert not proposals.exists() or not list(proposals.glob("*.json"))
    # The refusal itself is receipted.
    assert out["receipt"]["decision"] == "refused"


def test_perceive_unknown_tool_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    out = lens_perceive_via_mcp("francis.does.not.exist", {}, actor=_ACTOR)
    assert out["ok"] is False
    assert out["status"] == "refused"
    assert out["error"] == "unknown_tool"


def test_overlay_observation_refuses_without_overlay_coordinate_model(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    out = lens_observe_overlay_region(
        {"space": "desktop", "x": 10, "y": 20, "width": 80, "height": 60},
        actor=_ACTOR,
    )

    assert out["ok"] is False
    assert out["status"] == "blocked"
    assert out["surface"] == "lens.overlay.observation"
    assert out["overlay_context"]["source"] == "missing"
    assert out["mapped_overlay_region"]["reason"] == "overlay_context_missing"
    boundary = out["mapped_overlay_region"]["coordinate_boundary"]
    assert boundary["status"] == "unavailable"
    assert boundary["reason"] == "overlay_context_missing"
    assert boundary["bounds_checked"] is False
    assert boundary["within_overlay_bounds"] is False
    transform = out["mapped_overlay_region"]["coordinate_transform"]
    assert transform["status"] == "unavailable"
    assert transform["reason"] == "overlay_context_missing"
    assert transform["source_space"] == "desktop"
    assert transform["target_space"] == "desktop_logical_pixels"
    assert transform["transform_applied"] is False
    assert transform["confidence"] == 0.0
    assert transform["confidence_basis"] == "coordinate_transform_unavailable"
    assert out["observation_source"]["status"] == "not_called"
    assert out["actual_observed_region"]["requested_region"] == out["requested_region"]
    assert out["actual_observed_region"]["mapped_overlay_region_status"] == "blocked"
    assert out["actual_observed_region"]["coordinate_boundary"] == boundary
    assert out["actual_observed_region"]["coordinate_transform"] == transform
    assert out["actual_observed_region"]["actual_observation_region"] == {}
    assert out["actual_observed_region"]["observation_adapter"] == "none"
    assert out["actual_observed_region"]["screenshots"] is False
    assert out["actual_observed_region"]["pixels"] is False
    assert out["actual_observed_region"]["confidence"] == 0.0
    assert out["actual_observed_region"]["unknowns"] == out["unknown_information"]
    assert "overlay_context_missing" in out["actual_observed_region"]["limitations"]
    assert out["actual_captured_region"]["requested_region"] == out["requested_region"]
    assert out["actual_captured_region"]["mapped_overlay_region_status"] == "blocked"
    assert out["actual_captured_region"]["coordinate_boundary"] == boundary
    assert out["actual_captured_region"]["coordinate_transform"] == transform
    assert out["actual_captured_region"]["confidence"] == 0.0
    assert out["actual_captured_region"]["confidence_basis"] == "capture_not_performed"
    assert out["actual_captured_region"]["unknowns"] == out["unknown_information"]
    assert "capture_adapter_unavailable" in out["actual_captured_region"]["limitations"]
    structured = out["structured_observation_receipt"]
    assert structured["status"] == "blocked"
    assert structured["requested_region"] == out["requested_region"]
    assert structured["mapped_overlay_region"] == out["mapped_overlay_region"]
    assert structured["actual_inspected_region"] == {}
    assert structured["source"]["status"] == "not_called"
    assert structured["unknowns"] == out["unknown_information"]
    assert structured["failure_or_refusal_reason"] == "overlay_context_missing"
    spatial = out["spatial_contract"]
    assert spatial == structured["spatial_contract"]
    assert spatial["contract"] == "lens_overlay_spatial_metadata_v1"
    assert spatial["status"] == "blocked"
    assert spatial["coordinate_space"] == "desktop_logical_pixels"
    assert spatial["mapped_overlay_region_status"] == "blocked"
    assert spatial["actual_inspected_region_status"] == "not_inspected"
    assert spatial["actual_observed_region_status"] == "not_observed"
    assert spatial["actual_captured_region_status"] == "not_captured"
    assert spatial["coordinate_boundary_status"] == "unavailable"
    assert spatial["coordinate_transform_status"] == "unavailable"
    assert spatial["bounds_checked"] is False
    assert spatial["source"]["status"] == "not_called"
    assert spatial["region_presence"] == {
        "requested_region": True,
        "mapped_region": False,
        "actual_inspection_region": False,
        "actual_observation_region": False,
        "actual_capture_region": False,
    }
    assert spatial["confidence"] == 0.0
    assert spatial["confidence_basis"] == "capture_not_performed"
    assert spatial["capture_performed"] is False
    assert spatial["unsupported_perception"]["screenshots"] is False
    assert spatial["unsupported_perception"]["pixels"] is False
    assert "requested_region" in spatial["replay_keys"]
    assert spatial["failure_or_refusal_reason"] == "overlay_context_missing"
    assert "pixel_content" in out["unknown_information"]
    assert out["receipt"]["decision"] == "refused"
    assert out["receipt"]["structured_observation_receipt"] == structured
    assert out["receipt"]["spatial_contract"] == spatial
    assert out["receipt"]["requested_region"]["space"] == "desktop"
    assert out["governance"]["uses_existing_overlay"] is True
    assert out["governance"]["creates_overlay"] is False
    assert out["governance"]["creates_lens_app"] is False


def test_overlay_observation_uses_existing_overlay_bounds_and_screen_readback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))

    out = lens_observe_overlay_region(
        {"space": "desktop", "label": "test target", "x": 10, "y": 20, "width": 80, "height": 60},
        {
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "coordinate_space": "desktop_logical_pixels",
            "bounds": {"x": 0, "y": 0, "width": 500, "height": 400},
        },
        actor=_ACTOR,
        observation_source="francis.screen.session",
        correlation_id="corr-observe-test",
        mission_id="mission-observe-test",
    )

    assert out["ok"] is True
    assert out["status"] == "observed"
    assert out["overlay_context"]["source"] == "caller_supplied_overlay_context"
    assert out["overlay_context"]["coordinate_model"]["status"] == "available"
    assert out["mapped_overlay_region"]["status"] == "mapped"
    assert out["mapped_overlay_region"]["within_overlay_bounds"] is True
    boundary = out["mapped_overlay_region"]["coordinate_boundary"]
    assert boundary["status"] == "within_bounds"
    assert boundary["bounds_checked"] is True
    assert boundary["within_overlay_bounds"] is True
    assert boundary["clipped_by_overlay"] is False
    assert boundary["outside_edges"] == []
    assert boundary["coordinate_space"] == "desktop_logical_pixels"
    assert boundary["overlay_edges"] == {"left": 0.0, "top": 0.0, "right": 500.0, "bottom": 400.0}
    assert boundary["requested_edges"] == {"left": 10.0, "top": 20.0, "right": 90.0, "bottom": 80.0}
    assert boundary["intersection_region"] == out["mapped_overlay_region"]["region"]
    transform = out["mapped_overlay_region"]["coordinate_transform"]
    assert transform["status"] == "mapped"
    assert transform["reason"] == ""
    assert transform["source_space"] == "desktop"
    assert transform["target_space"] == "desktop_logical_pixels"
    assert transform["mapped_region_space"] == "desktop_logical_pixels"
    assert transform["transform"] == "identity_desktop_logical"
    assert transform["transform_applied"] is True
    assert transform["requested_to_mapped_delta"] == {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    assert transform["overlay_origin"] == {
        "space": "desktop_logical_pixels",
        "x": 0.0,
        "y": 0.0,
        "source": "overlay_coordinate_model.bounds",
    }
    assert transform["overlay_local_region"] == {
        "space": "overlay_local_logical_pixels",
        "x": 10.0,
        "y": 20.0,
        "width": 80.0,
        "height": 60.0,
    }
    assert transform["intersection_overlay_local_region"] == transform["overlay_local_region"]
    assert transform["bounds_checked"] is True
    assert transform["within_overlay_bounds"] is True
    assert transform["clipped_by_overlay"] is False
    assert transform["confidence"] == 1.0
    assert transform["confidence_basis"] == "declared_overlay_coordinate_model_not_visual_perception"
    assert "visual_registration_unsupported" in transform["limitations"]
    assert out["actual_inspected_region"]["status"] == "inspected_metadata_only"
    assert out["actual_inspected_region"]["requested_region"] == out["requested_region"]
    assert out["actual_inspected_region"]["mapped_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_inspected_region"]["mapped_overlay_region_status"] == "mapped"
    assert out["actual_inspected_region"]["coordinate_boundary"] == boundary
    assert out["actual_inspected_region"]["coordinate_transform"] == transform
    assert out["actual_inspected_region"]["actual_inspection_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_inspected_region"]["source"] == "francis.screen.session"
    assert out["actual_inspected_region"]["confidence"] == out["confidence"]
    assert out["actual_inspected_region"]["confidence_basis"] == "mcp_metadata_readback_not_visual_perception"
    assert out["actual_inspected_region"]["unknowns"] == out["unknown_information"]
    assert out["actual_inspected_region"]["limitations"] == out["limitations"]
    assert out["actual_inspected_region"]["screenshots"] is False
    assert out["actual_inspected_region"]["pixels"] is False
    assert out["actual_observed_region"]["status"] == "observed_metadata_only"
    assert out["actual_observed_region"]["requested_region"] == out["requested_region"]
    assert out["actual_observed_region"]["mapped_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_observed_region"]["mapped_overlay_region_status"] == "mapped"
    assert out["actual_observed_region"]["coordinate_boundary"] == boundary
    assert out["actual_observed_region"]["coordinate_transform"] == transform
    assert out["actual_observed_region"]["region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_observed_region"]["actual_observation_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_observed_region"]["observation_adapter"] == "mcp_metadata_readback"
    assert out["actual_observed_region"]["capture"] == "not_performed"
    assert out["actual_observed_region"]["screenshots"] is False
    assert out["actual_observed_region"]["pixels"] is False
    assert out["actual_observed_region"]["ocr"] is False
    assert out["actual_observed_region"]["confidence"] == out["confidence"]
    assert out["actual_observed_region"]["confidence_basis"] == "mcp_metadata_readback_not_visual_perception"
    assert out["actual_observed_region"]["unknowns"] == out["unknown_information"]
    assert out["actual_observed_region"]["limitations"] == out["limitations"]
    assert out["actual_captured_region"]["status"] == "not_captured"
    assert out["actual_captured_region"]["requested_region"] == out["requested_region"]
    assert out["actual_captured_region"]["region"] == {}
    assert out["actual_captured_region"]["actual_capture_region"] == {}
    assert out["actual_captured_region"]["mapped_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_captured_region"]["mapped_overlay_region_status"] == "mapped"
    assert out["actual_captured_region"]["coordinate_boundary"] == boundary
    assert out["actual_captured_region"]["coordinate_transform"] == transform
    assert out["actual_captured_region"]["capture_adapter"] == "unavailable"
    assert out["actual_captured_region"]["screenshots"] is False
    assert out["actual_captured_region"]["pixels"] is False
    assert out["actual_captured_region"]["confidence"] == 0.0
    assert out["actual_captured_region"]["unknowns"] == out["unknown_information"]
    assert "capture_adapter_unavailable" in out["actual_captured_region"]["limitations"]
    assert out["observation_source"]["tool"] == "francis.screen.session"
    assert out["observation_source"]["live_simulated_fixture_or_replay"] == "live"
    assert out["evidence_reference"]["status"] == "metadata_readback"
    assert out["evidence_reference"]["content_included"] is False
    structured = out["structured_observation_receipt"]
    assert structured["kind"] == "francis.lens.overlay.structured_observation_receipt"
    assert structured["schema_version"] == 1
    assert structured["status"] == "observed"
    assert structured["source"]["name"] == "francis.screen.session"
    assert structured["source"]["live_simulated_fixture_or_replay"] == "live"
    assert structured["actual_observed_region"] == out["actual_observed_region"]
    assert structured["actual_captured_region"] == out["actual_captured_region"]
    assert structured["evidence_reference"] == out["evidence_reference"]
    assert structured["inferred_information"] == out["inferred_information"]
    assert structured["confidence"] == out["confidence"]
    spatial = out["spatial_contract"]
    assert spatial == structured["spatial_contract"]
    assert spatial["schema_version"] == 1
    assert spatial["status"] == "observed"
    assert spatial["coordinate_space"] == "desktop_logical_pixels"
    assert spatial["mapped_overlay_region_status"] == "mapped"
    assert spatial["actual_inspected_region_status"] == "inspected_metadata_only"
    assert spatial["actual_observed_region_status"] == "observed_metadata_only"
    assert spatial["actual_captured_region_status"] == "not_captured"
    assert spatial["coordinate_boundary_status"] == "within_bounds"
    assert spatial["coordinate_transform_status"] == "mapped"
    assert spatial["bounds_checked"] is True
    assert spatial["within_overlay_bounds"] is True
    assert spatial["clipped_by_overlay"] is False
    assert spatial["source"]["name"] == "francis.screen.session"
    assert spatial["source"]["status"] == "ready"
    assert spatial["source"]["read_only"] is True
    assert spatial["evidence_reference_status"] == "metadata_readback"
    assert spatial["evidence_content_included"] is False
    assert spatial["region_presence"] == {
        "requested_region": True,
        "mapped_region": True,
        "actual_inspection_region": True,
        "actual_observation_region": True,
        "actual_capture_region": False,
    }
    assert spatial["region_truth"] == {
        "requested_region_present": True,
        "mapped_region_present": True,
        "actual_inspection_region_present": True,
        "actual_observation_region_present": True,
        "actual_capture_region_present": False,
        "actual_inspection_region_matches_mapped_region": True,
        "actual_observed_region_matches_mapped_region": True,
        "actual_captured_region_matches_mapped_region": False,
        "mapped_region_observed_metadata_only": True,
        "mapped_region_captured": False,
        "actual_capture_region_absent_reason": "capture_adapter_unavailable",
        "source_called": True,
        "metadata_readback_only": True,
        "capture_performed": False,
        "unsupported_perception_claimed": False,
        "unsupported_perception": spatial["unsupported_perception"],
    }
    assert spatial["region_basis"] == {
        "requested_region": {
            "present": True,
            "status": "bounded",
            "space": "desktop",
            "basis": "caller_supplied_request",
        },
        "mapped_overlay_region": {
            "present": True,
            "status": "mapped",
            "space": "desktop_logical_pixels",
            "basis": "declared_overlay_coordinate_model",
            "coordinate_boundary_status": "within_bounds",
            "coordinate_transform_status": "mapped",
            "bounds_checked": True,
            "within_overlay_bounds": True,
            "clipped_by_overlay": False,
        },
        "actual_inspected_region": {
            "present": True,
            "status": "inspected_metadata_only",
            "space": "desktop_logical_pixels",
            "source": "francis.screen.session",
            "basis": "mcp_metadata",
            "confidence": 0.35,
            "confidence_basis": "mcp_metadata_readback_not_visual_perception",
        },
        "actual_observed_region": {
            "present": True,
            "status": "observed_metadata_only",
            "space": "desktop_logical_pixels",
            "source": "francis.screen.session",
            "basis": "mcp_metadata",
            "observation_adapter": "mcp_metadata_readback",
            "metadata_only": True,
            "confidence": 0.35,
            "confidence_basis": "mcp_metadata_readback_not_visual_perception",
        },
        "actual_captured_region": {
            "present": False,
            "status": "not_captured",
            "space": "",
            "source": "none",
            "basis": "not_performed",
            "capture_adapter": "unavailable",
            "capture_performed": False,
            "confidence": 0.0,
            "confidence_basis": "capture_not_performed",
            "absent_reason": "capture_adapter_unavailable",
        },
    }
    comparison = spatial["region_comparison"]
    assert comparison["schema_version"] == 1
    assert comparison["comparison_scope"] == "requested_mapped_actual_regions"
    assert comparison["comparison_basis"] == "coordinate_and_metadata_only_not_visual_perception"
    assert comparison["summary"] == {
        "requested_geometry_matches_mapped_region": True,
        "actual_inspected_region_matches_mapped_region": True,
        "actual_observed_region_matches_mapped_region": True,
        "actual_captured_region_matches_mapped_region": False,
        "mapped_region_observed_metadata_only": True,
        "mapped_region_captured": False,
        "capture_performed": False,
        "unsupported_perception_claimed": False,
    }
    assert comparison["rows"]["requested_region"]["present"] is True
    assert comparison["rows"]["requested_region"]["geometry"] == {"x": 10.0, "y": 20.0, "width": 80.0, "height": 60.0}
    assert comparison["rows"]["requested_region"]["geometry_matches_mapped_region"] is True
    assert comparison["rows"]["requested_region"]["exact_region_matches_mapped_region"] is False
    assert (
        comparison["rows"]["requested_region"]["confidence_basis"]
        == "operator_supplied_geometry_unverified_by_visual_perception"
    )
    assert comparison["rows"]["mapped_overlay_region"]["present"] is True
    assert comparison["rows"]["mapped_overlay_region"]["exact_region_matches_mapped_region"] is True
    assert comparison["rows"]["mapped_overlay_region"]["confidence"] == 1.0
    assert (
        comparison["rows"]["mapped_overlay_region"]["confidence_basis"]
        == "declared_overlay_coordinate_model_not_visual_perception"
    )
    assert comparison["rows"]["actual_inspected_region"]["present"] is True
    assert comparison["rows"]["actual_inspected_region"]["source"] == "francis.screen.session"
    assert comparison["rows"]["actual_inspected_region"]["basis"] == "mcp_metadata"
    assert comparison["rows"]["actual_inspected_region"]["metadata_only"] is True
    assert comparison["rows"]["actual_inspected_region"]["geometry_matches_mapped_region"] is True
    assert comparison["rows"]["actual_inspected_region"]["unknowns"] == out["unknown_information"]
    assert comparison["rows"]["actual_inspected_region"]["limitations"] == out["limitations"]
    assert comparison["rows"]["actual_observed_region"]["present"] is True
    assert comparison["rows"]["actual_observed_region"]["basis"] == "mcp_metadata"
    assert comparison["rows"]["actual_observed_region"]["metadata_only"] is True
    assert comparison["rows"]["actual_observed_region"]["geometry_matches_mapped_region"] is True
    assert comparison["rows"]["actual_captured_region"]["present"] is False
    assert comparison["rows"]["actual_captured_region"]["capture_performed"] is False
    assert comparison["rows"]["actual_captured_region"]["geometry_matches_mapped_region"] is False
    assert "capture_adapter_unavailable" in comparison["rows"]["actual_captured_region"]["limitations"]
    assert comparison["unsupported_perception"] == spatial["unsupported_perception"]
    assert comparison["unknowns"] == out["unknown_information"]
    assert comparison["limitations"] == out["limitations"]
    assert spatial["confidence"] == out["confidence"]
    assert spatial["confidence_basis"] == "mcp_metadata_readback_not_visual_perception"
    assert spatial["confidence_breakdown"] == {
        "overall": {"confidence": 0.35, "basis": "mcp_metadata_readback_not_visual_perception"},
        "coordinate_transform": {
            "status": "mapped",
            "confidence": 1.0,
            "basis": "declared_overlay_coordinate_model_not_visual_perception",
        },
        "metadata_readback": {
            "status": "observed_metadata_only",
            "confidence": 0.35,
            "basis": "mcp_metadata_readback_not_visual_perception",
        },
        "capture": {
            "status": "not_captured",
            "confidence": 0.0,
            "basis": "capture_not_performed",
            "performed": False,
        },
        "visual_perception": {
            "supported": False,
            "confidence": 0.0,
            "basis": "visual_perception_unsupported",
        },
    }
    assert spatial["capture_performed"] is False
    assert spatial["unsupported_perception"] == {
        "screenshots": False,
        "pixels": False,
        "ocr": False,
        "accessibility_tree": False,
        "visual_similarity": False,
    }
    assert spatial["unknowns"] == out["unknown_information"]
    assert spatial["limitations"] == out["limitations"]
    assert spatial["failure_or_refusal_reason"] == ""
    assert "actual_captured_region" in spatial["replay_keys"]
    replay = spatial["replay_manifest"]
    assert replay == structured["replay_manifest"] == out["replay_manifest"]
    assert replay["contract"] == "lens_overlay_spatial_metadata_replay_v1"
    assert replay["replay_scope"] == "coordinate_and_metadata_only"
    assert replay["metadata_replayable"] is True
    assert replay["visual_replayable"] is False
    assert replay["source_mode"] == "live_readback"
    assert replay["source_status"] == "ready"
    assert replay["region_presence"] == spatial["region_presence"]
    assert replay["region_truth"] == spatial["region_truth"]
    assert replay["region_basis"] == spatial["region_basis"]
    assert replay["region_comparison"] == spatial["region_comparison"]
    assert replay["unsupported_perception"] == spatial["unsupported_perception"]
    assert replay["confidence_basis"] == spatial["confidence_basis"]
    assert replay["confidence_breakdown"] == spatial["confidence_breakdown"]
    assert replay["evidence_content_included"] is False
    assert replay["capture_performed"] is False
    assert "screenshot_pixels" in structured["unknowns"]
    assert "metadata_only_screen_session_readback" in structured["limitations"]
    assert "pixel_capture_unsupported" in structured["limitations"]
    assert "ocr_unsupported" in structured["limitations"]
    assert structured["limitations"] == out["limitations"]
    assert structured["governance"]["grants_execution_authority"] is False
    assert out["confidence"] == 0.35
    assert "screenshot_pixels" in out["unknown_information"]
    assert out["receipt"]["decision"] == "observed"
    assert out["receipt"]["structured_observation_receipt"] == structured
    assert out["receipt"]["actual_observed_region"] == out["actual_observed_region"]
    assert out["receipt"]["actual_captured_region"] == out["actual_captured_region"]
    assert out["receipt"]["limitations"] == out["limitations"]
    assert out["receipt"]["spatial_contract"] == spatial
    assert out["receipt"]["replay_manifest"] == replay
    assert out["receipt"]["correlation_id"] == "corr-observe-test"
    assert out["receipt"]["mission_id"] == "mission-observe-test"


def test_overlay_observation_blocks_out_of_bounds_region_without_screen_readback(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    def fail_if_called(*_args, **_kwargs):  # pragma: no cover - exercised only on regression
        raise AssertionError("out-of-bounds overlay observation must not call MCP readback")

    monkeypatch.setattr("francis.lens.mcp_perception._mcp_run_tool", fail_if_called)

    out = lens_observe_overlay_region(
        {"space": "desktop", "label": "outside", "x": 490, "y": 20, "width": 20, "height": 60},
        {
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "coordinate_space": "desktop_logical_pixels",
            "bounds": {"x": 0, "y": 0, "width": 500, "height": 400},
        },
        actor=_ACTOR,
        observation_source="francis.screen.session",
    )

    assert out["ok"] is False
    assert out["status"] == "blocked"
    assert out["mapped_overlay_region"]["status"] == "blocked"
    assert out["mapped_overlay_region"]["reason"] == "requested_region_outside_overlay_bounds"
    assert out["mapped_overlay_region"]["region"] == {
        "space": "desktop_logical_pixels",
        "x": 490.0,
        "y": 20.0,
        "width": 20.0,
        "height": 60.0,
    }
    boundary = out["mapped_overlay_region"]["coordinate_boundary"]
    assert boundary["status"] == "outside_bounds"
    assert boundary["bounds_checked"] is True
    assert boundary["within_overlay_bounds"] is False
    assert boundary["clipped_by_overlay"] is True
    assert boundary["outside_edges"] == ["right"]
    assert boundary["overlay_edges"] == {"left": 0.0, "top": 0.0, "right": 500.0, "bottom": 400.0}
    assert boundary["requested_edges"] == {"left": 490.0, "top": 20.0, "right": 510.0, "bottom": 80.0}
    assert boundary["intersection_region"] == {
        "space": "desktop_logical_pixels",
        "x": 490.0,
        "y": 20.0,
        "width": 10.0,
        "height": 60.0,
    }
    transform = out["mapped_overlay_region"]["coordinate_transform"]
    assert transform["status"] == "blocked_after_mapping"
    assert transform["reason"] == "requested_region_outside_overlay_bounds"
    assert transform["transform"] == "identity_desktop_logical"
    assert transform["transform_applied"] is True
    assert transform["requested_to_mapped_delta"] == {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    assert transform["overlay_local_region"] == {
        "space": "overlay_local_logical_pixels",
        "x": 490.0,
        "y": 20.0,
        "width": 20.0,
        "height": 60.0,
    }
    assert transform["intersection_overlay_local_region"] == {
        "space": "overlay_local_logical_pixels",
        "x": 490.0,
        "y": 20.0,
        "width": 10.0,
        "height": 60.0,
    }
    assert transform["within_overlay_bounds"] is False
    assert transform["clipped_by_overlay"] is True
    assert transform["confidence"] == 1.0
    assert transform["confidence_basis"] == "declared_overlay_coordinate_model_not_visual_perception"
    assert "capture_adapter_unavailable" in transform["limitations"]
    assert out["observation_source"]["status"] == "not_called"
    assert out["actual_observed_region"]["status"] == "not_observed"
    assert out["actual_observed_region"]["requested_region"] == out["requested_region"]
    assert out["actual_observed_region"]["mapped_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_observed_region"]["mapped_overlay_region_status"] == "blocked"
    assert out["actual_observed_region"]["coordinate_boundary"] == boundary
    assert out["actual_observed_region"]["coordinate_transform"] == transform
    assert out["actual_observed_region"]["region"] == {}
    assert out["actual_observed_region"]["actual_observation_region"] == {}
    assert out["actual_observed_region"]["observation_adapter"] == "none"
    assert out["actual_observed_region"]["reason"] == "requested_region_outside_overlay_bounds"
    assert out["actual_observed_region"]["confidence"] == 0.0
    assert out["actual_observed_region"]["unknowns"] == out["unknown_information"]
    assert out["actual_captured_region"]["status"] == "not_captured"
    assert out["actual_captured_region"]["requested_region"] == out["requested_region"]
    assert out["actual_captured_region"]["region"] == {}
    assert out["actual_captured_region"]["mapped_region"] == out["mapped_overlay_region"]["region"]
    assert out["actual_captured_region"]["mapped_overlay_region_status"] == "blocked"
    assert out["actual_captured_region"]["coordinate_boundary"] == boundary
    assert out["actual_captured_region"]["coordinate_transform"] == transform
    assert out["actual_captured_region"]["screenshots"] is False
    assert out["actual_captured_region"]["pixels"] is False
    assert out["actual_captured_region"]["ocr"] is False
    assert out["actual_captured_region"]["confidence"] == 0.0
    assert out["actual_captured_region"]["unknowns"] == out["unknown_information"]
    assert "requested_region_outside_overlay_bounds" in out["actual_captured_region"]["limitations"]
    assert "requested_region_outside_overlay_bounds" in out["limitations"]
    assert "pixel_capture_unsupported" in out["limitations"]
    structured = out["structured_observation_receipt"]
    assert structured["status"] == "blocked"
    assert structured["actual_observed_region"] == out["actual_observed_region"]
    assert structured["actual_captured_region"] == out["actual_captured_region"]
    assert structured["limitations"] == out["limitations"]
    spatial = out["spatial_contract"]
    assert spatial == structured["spatial_contract"]
    assert spatial["status"] == "blocked"
    assert spatial["mapped_overlay_region_status"] == "blocked"
    assert spatial["actual_observed_region_status"] == "not_observed"
    assert spatial["coordinate_boundary_status"] == "outside_bounds"
    assert spatial["coordinate_transform_status"] == "blocked_after_mapping"
    assert spatial["bounds_checked"] is True
    assert spatial["within_overlay_bounds"] is False
    assert spatial["clipped_by_overlay"] is True
    assert spatial["source"]["status"] == "not_called"
    assert spatial["region_presence"]["mapped_region"] is True
    assert spatial["region_presence"]["actual_observation_region"] is False
    assert spatial["region_truth"]["requested_region_present"] is True
    assert spatial["region_truth"]["mapped_region_present"] is True
    assert spatial["region_truth"]["actual_observation_region_present"] is False
    assert spatial["region_truth"]["actual_capture_region_present"] is False
    assert spatial["region_truth"]["actual_observed_region_matches_mapped_region"] is False
    assert spatial["region_truth"]["actual_captured_region_matches_mapped_region"] is False
    assert spatial["region_truth"]["mapped_region_observed_metadata_only"] is False
    assert spatial["region_truth"]["mapped_region_captured"] is False
    assert spatial["region_truth"]["actual_capture_region_absent_reason"] == "requested_region_outside_overlay_bounds"
    assert spatial["region_truth"]["source_called"] is False
    assert spatial["region_truth"]["metadata_readback_only"] is False
    assert spatial["region_truth"]["unsupported_perception_claimed"] is False
    assert spatial["region_basis"]["mapped_overlay_region"] == {
        "present": True,
        "status": "blocked",
        "space": "desktop_logical_pixels",
        "basis": "declared_overlay_coordinate_model",
        "coordinate_boundary_status": "outside_bounds",
        "coordinate_transform_status": "blocked_after_mapping",
        "bounds_checked": True,
        "within_overlay_bounds": False,
        "clipped_by_overlay": True,
    }
    assert spatial["region_basis"]["actual_observed_region"] == {
        "present": False,
        "status": "not_observed",
        "space": "",
        "source": "none",
        "basis": "not_performed",
        "observation_adapter": "none",
        "metadata_only": False,
        "confidence": 0.0,
        "confidence_basis": "observation_not_performed",
    }
    assert spatial["region_basis"]["actual_captured_region"]["present"] is False
    assert (
        spatial["region_basis"]["actual_captured_region"]["absent_reason"] == "requested_region_outside_overlay_bounds"
    )
    comparison = spatial["region_comparison"]
    assert comparison["summary"] == {
        "requested_geometry_matches_mapped_region": True,
        "actual_inspected_region_matches_mapped_region": False,
        "actual_observed_region_matches_mapped_region": False,
        "actual_captured_region_matches_mapped_region": False,
        "mapped_region_observed_metadata_only": False,
        "mapped_region_captured": False,
        "capture_performed": False,
        "unsupported_perception_claimed": False,
    }
    assert comparison["rows"]["mapped_overlay_region"]["status"] == "blocked"
    assert comparison["rows"]["mapped_overlay_region"]["geometry_matches_mapped_region"] is True
    assert comparison["rows"]["actual_inspected_region"]["present"] is False
    assert comparison["rows"]["actual_inspected_region"]["basis"] == "not_performed"
    assert comparison["rows"]["actual_observed_region"]["status"] == "not_observed"
    assert comparison["rows"]["actual_observed_region"]["present"] is False
    assert comparison["rows"]["actual_observed_region"]["source"] == "none"
    assert comparison["rows"]["actual_captured_region"]["present"] is False
    assert comparison["rows"]["actual_captured_region"]["capture_performed"] is False
    assert "requested_region_outside_overlay_bounds" in comparison["rows"]["actual_captured_region"]["limitations"]
    assert comparison["unsupported_perception"] == spatial["unsupported_perception"]
    assert spatial["confidence"] == 0.0
    assert spatial["confidence_breakdown"]["coordinate_transform"] == {
        "status": "blocked_after_mapping",
        "confidence": 1.0,
        "basis": "declared_overlay_coordinate_model_not_visual_perception",
    }
    assert spatial["confidence_breakdown"]["metadata_readback"]["confidence"] == 0.0
    assert spatial["confidence_breakdown"]["capture"]["performed"] is False
    assert spatial["confidence_breakdown"]["visual_perception"]["supported"] is False
    assert spatial["capture_performed"] is False
    assert spatial["failure_or_refusal_reason"] == "requested_region_outside_overlay_bounds"
    replay = spatial["replay_manifest"]
    assert replay == structured["replay_manifest"] == out["replay_manifest"]
    assert replay["source_status"] == "not_called"
    assert replay["mapped_overlay_region_status"] == "blocked"
    assert replay["actual_observed_region_status"] == "not_observed"
    assert replay["actual_captured_region_status"] == "not_captured"
    assert replay["metadata_replayable"] is True
    assert replay["visual_replayable"] is False
    assert replay["region_presence"] == spatial["region_presence"]
    assert replay["region_truth"] == spatial["region_truth"]
    assert replay["region_basis"] == spatial["region_basis"]
    assert replay["region_comparison"] == spatial["region_comparison"]
    assert replay["confidence_breakdown"] == spatial["confidence_breakdown"]
    assert replay["failure_or_refusal_reason"] == "requested_region_outside_overlay_bounds"
    assert out["receipt"]["actual_observed_region"] == out["actual_observed_region"]
    assert out["receipt"]["actual_captured_region"] == out["actual_captured_region"]
    assert out["receipt"]["limitations"] == out["limitations"]
    assert out["receipt"]["spatial_contract"] == spatial
    assert out["receipt"]["replay_manifest"] == replay


def test_overlay_observation_reports_overlay_local_transform_for_offset_bounds(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_MCP_GATEWAY_STATE_DIR", str(tmp_path / "mcp"))

    out = lens_observe_overlay_region(
        {"space": "desktop", "label": "offset target", "x": 130, "y": 240, "width": 20, "height": 30},
        {
            "overlay_name": "Francis Lens Overlay",
            "overlay_scope": "user_session",
            "coordinate_space": "desktop_logical_pixels",
            "bounds": {"x": 100, "y": 200, "width": 300, "height": 250},
        },
        actor=_ACTOR,
        observation_source="francis.screen.session",
    )

    assert out["ok"] is True
    transform = out["mapped_overlay_region"]["coordinate_transform"]
    assert transform["status"] == "mapped"
    assert transform["overlay_origin"] == {
        "space": "desktop_logical_pixels",
        "x": 100.0,
        "y": 200.0,
        "source": "overlay_coordinate_model.bounds",
    }
    assert transform["overlay_local_region"] == {
        "space": "overlay_local_logical_pixels",
        "x": 30.0,
        "y": 40.0,
        "width": 20.0,
        "height": 30.0,
    }
    assert transform["intersection_overlay_local_region"] == transform["overlay_local_region"]
    assert transform["requested_to_mapped_delta"] == {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0}
    assert transform["confidence_basis"] == "declared_overlay_coordinate_model_not_visual_perception"


def test_overlay_observation_refuses_non_screen_observation_sources(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    out = lens_observe_overlay_region(
        {"space": "desktop", "x": 10, "y": 20, "width": 80, "height": 60},
        {
            "coordinate_space": "desktop_logical_pixels",
            "bounds": {"x": 0, "y": 0, "width": 500, "height": 400},
        },
        actor=_ACTOR,
        observation_source="francis.command.propose",
    )

    assert out["ok"] is False
    assert out["status"] == "refused"
    assert out["failure_or_refusal_reason"] == "unsupported_overlay_observation_source"
    assert out["actual_observed_region"]["requested_region"] == out["requested_region"]
    assert out["actual_observed_region"]["mapped_overlay_region_status"] == "mapped"
    assert out["actual_observed_region"]["actual_observation_region"] == {}
    assert out["actual_observed_region"]["observation_adapter"] == "none"
    assert out["actual_observed_region"]["confidence"] == 0.0
    assert out["actual_captured_region"]["requested_region"] == out["requested_region"]
    assert out["actual_captured_region"]["mapped_overlay_region_status"] == "mapped"
    assert out["actual_captured_region"]["confidence_basis"] == "capture_not_performed"
    assert "unsupported_overlay_observation_source" in out["actual_captured_region"]["limitations"]
    assert out["receipt"]["decision"] == "refused"


# --------------------------------------------------------------------------- #
# API surface (permission-gated)
# --------------------------------------------------------------------------- #
def test_api_perceive_requires_scope(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())

    denied = client.post("/lens/mcp/perceive", json={"tool": "francis.health", "actor": "intruder.no.scope"})
    body = denied.json()
    assert body["ok"] is False
    assert body["error"] == "api_permission_denied"

    allowed = client.post("/lens/mcp/perceive", json={"tool": "francis.health", "actor": _ACTOR})
    ok_body = allowed.json()
    assert ok_body["status"] == "perceived"
    assert ok_body["governance"]["resident"] is False


def test_api_contract_requires_scope(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())
    denied = client.get("/lens/mcp/contract", params={"actor": "intruder.no.scope"})
    assert denied.json()["error"] == "api_permission_denied"
    allowed = client.get("/lens/mcp/contract", params={"actor": _ACTOR})
    assert allowed.json()["ok"] is True


def test_api_observe_requires_scope_and_overlay_context(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    client = TestClient(create_app())
    payload = {
        "actor": _ACTOR,
        "requested_region": {"space": "desktop", "x": 10, "y": 20, "width": 80, "height": 60},
        "overlay_context": {
            "coordinate_space": "desktop_logical_pixels",
            "bounds": {"x": 0, "y": 0, "width": 500, "height": 400},
        },
    }

    denied = client.post("/lens/mcp/observe", json={**payload, "actor": "intruder.no.scope"})
    assert denied.json()["error"] == "api_permission_denied"

    allowed = client.post("/lens/mcp/observe", json=payload)
    body = allowed.json()
    assert body["status"] == "observed"
    assert body["mapped_overlay_region"]["status"] == "mapped"
    assert body["actual_captured_region"]["mapped_overlay_region_status"] == "mapped"
    assert body["actual_captured_region"]["coordinate_transform"]["status"] == "mapped"
    assert body["spatial_contract"]["coordinate_boundary_status"] == "within_bounds"
    assert body["spatial_contract"]["actual_captured_region_status"] == "not_captured"
    assert body["spatial_contract"]["capture_performed"] is False
    assert body["governance"]["uses_existing_overlay"] is True

    receipts = client.get("/lens/mcp/receipts", params={"actor": _ACTOR, "limit": 1}).json()
    receipt = receipts["receipts"][0]
    assert receipt["decision"] == "observed"
    assert receipt["spatial_contract"] == body["spatial_contract"]
    assert receipt["actual_captured_region"]["mapped_overlay_region_status"] == "mapped"
    assert receipt["actual_captured_region"]["coordinate_boundary"]["status"] == "within_bounds"
    assert receipt["actual_captured_region"]["coordinate_transform"]["status"] == "mapped"
    assert receipt["actual_captured_region"]["confidence"] == 0.0
    assert receipt["actual_observed_region"]["actual_observation_region"] == body["mapped_overlay_region"]["region"]
    assert receipt["actual_observed_region"]["coordinate_transform"]["status"] == "mapped"
    assert receipt["actual_inspected_region"]["actual_inspection_region"] == body["mapped_overlay_region"]["region"]
    assert receipt["actual_inspected_region"]["confidence_basis"] == "mcp_metadata_readback_not_visual_perception"
    assert "capture_adapter_unavailable" in receipt["actual_captured_region"]["limitations"]
    assert body["spatial_contract"]["region_truth"]["mapped_region_observed_metadata_only"] is True
    assert body["spatial_contract"]["region_truth"]["mapped_region_captured"] is False
    assert body["spatial_contract"]["region_basis"]["requested_region"]["basis"] == "caller_supplied_request"
    assert (
        body["spatial_contract"]["region_basis"]["mapped_overlay_region"]["basis"]
        == "declared_overlay_coordinate_model"
    )
    assert body["spatial_contract"]["region_basis"]["actual_observed_region"]["metadata_only"] is True
    assert body["spatial_contract"]["region_comparison"]["summary"]["mapped_region_observed_metadata_only"] is True
    assert body["spatial_contract"]["region_comparison"]["summary"]["mapped_region_captured"] is False
    assert (
        body["spatial_contract"]["region_comparison"]["rows"]["actual_captured_region"]["confidence_basis"]
        == "capture_not_performed"
    )
    assert body["spatial_contract"]["confidence_breakdown"]["visual_perception"]["supported"] is False
    assert receipt["spatial_contract"]["region_truth"] == body["spatial_contract"]["region_truth"]
    assert receipt["spatial_contract"]["region_basis"] == body["spatial_contract"]["region_basis"]
    assert receipt["spatial_contract"]["region_comparison"] == body["spatial_contract"]["region_comparison"]
    assert receipt["spatial_contract"]["confidence_breakdown"] == body["spatial_contract"]["confidence_breakdown"]
    assert body["replay_manifest"] == body["spatial_contract"]["replay_manifest"]
    assert receipt["replay_manifest"] == body["replay_manifest"]
    assert receipt["replay_manifest"]["metadata_replayable"] is True
    assert receipt["replay_manifest"]["visual_replayable"] is False
