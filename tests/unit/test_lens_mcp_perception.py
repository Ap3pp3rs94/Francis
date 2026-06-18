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
    assert out["observation_source"]["status"] == "not_called"
    assert "pixel_content" in out["unknown_information"]
    assert out["receipt"]["decision"] == "refused"
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
    assert out["actual_inspected_region"]["status"] == "inspected_metadata_only"
    assert out["actual_inspected_region"]["screenshots"] is False
    assert out["actual_inspected_region"]["pixels"] is False
    assert out["observation_source"]["tool"] == "francis.screen.session"
    assert out["observation_source"]["live_simulated_fixture_or_replay"] == "live"
    assert out["evidence_reference"]["status"] == "metadata_readback"
    assert out["evidence_reference"]["content_included"] is False
    assert out["confidence"] == 0.35
    assert "screenshot_pixels" in out["unknown_information"]
    assert out["receipt"]["decision"] == "observed"
    assert out["receipt"]["correlation_id"] == "corr-observe-test"
    assert out["receipt"]["mission_id"] == "mission-observe-test"


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
    assert body["governance"]["uses_existing_overlay"] is True
