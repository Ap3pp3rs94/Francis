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
    proposals = (tmp_path / "gw" / "proposals")
    assert not proposals.exists() or not list(proposals.glob("*.json"))
    # The refusal itself is receipted.
    assert out["receipt"]["decision"] == "refused"


def test_perceive_unknown_tool_refused(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    out = lens_perceive_via_mcp("francis.does.not.exist", {}, actor=_ACTOR)
    assert out["ok"] is False
    assert out["status"] == "refused"
    assert out["error"] == "unknown_tool"


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
