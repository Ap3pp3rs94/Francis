"""Receipt-backed cross-organ handoff (takeover -> input), embodiment milestone #3.

The load-bearing test is the A/B: the SAME approved input proposal is BLOCKED
without a handoff binding and proceeds (safe dry-run) with one. If removing the
binding did not change the execute outcome, the handoff would be ceremony.
"""

from __future__ import annotations

import pytest

from francis.handoff import bind_input_to_takeover, verify_input_handoff
from francis.input_actuator.tools import execute_approved_input_action, propose_input_action
from francis.lens import lens_perceive_via_mcp
from francis.mcp_gateway.tools import list_tools, run_tool
from francis.takeover_session.tools import propose_takeover_session, start_approved_takeover_session

pytestmark = pytest.mark.unit


def _envs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", raising=False)


def _takeover_start_receipt_id(mode: str = "pilot") -> str:
    prop = propose_takeover_session({"actor": "op", "mode": mode, "reason": "r", "duration_sec": 120})
    started = start_approved_takeover_session(
        {"proposal_id": prop["proposal_id"], "approval_phrase": prop["approval_phrase"]}
    )
    return started["receipt_id"]


def _input_proposal() -> tuple[str, str]:
    p = propose_input_action(
        {"actor": "op", "objective": "move", "kind": "mouse.move", "payload": {"x": 1, "y": 2}}
    )
    return p["data"]["proposal_id"], p["data"]["approval_phrase"]


def test_bind_allows_with_pilot_takeover_receipt(tmp_path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    rid = _takeover_start_receipt_id("pilot")
    pid, _ = _input_proposal()
    out = bind_input_to_takeover(pid, rid, actor="op")
    assert out["ok"] is True and out["decision"] == "allow"
    assert out["receipt"]["takeover_receipt_digest"]
    v = verify_input_handoff(pid)
    assert v["authorized"] is True
    assert v["takeover_receipt_id"] == rid


def test_bind_denies_missing_takeover_receipt(tmp_path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    pid, _ = _input_proposal()
    out = bind_input_to_takeover(pid, "does-not-exist", actor="op")
    assert out["ok"] is False and out["decision"] == "deny"
    assert out["reason"] == "takeover_receipt_not_found"
    assert verify_input_handoff(pid)["authorized"] is False


def test_bind_denies_read_only_takeover_session(tmp_path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    rid = _takeover_start_receipt_id("read_only")
    pid, _ = _input_proposal()
    out = bind_input_to_takeover(pid, rid, actor="op")
    assert out["decision"] == "deny"
    assert out["reason"] == "takeover_session_read_only_no_control_transfer"


def test_AB_input_blocked_without_handoff_then_allowed_with(tmp_path, monkeypatch) -> None:
    """The discriminator: same proposal, handoff is the only thing that changes."""
    _envs(tmp_path, monkeypatch)
    pid, phrase = _input_proposal()

    # A) No handoff binding -> execution BLOCKED (the gate consumes the handoff).
    blocked = execute_approved_input_action({"proposal_id": pid, "approval_phrase": phrase})
    assert blocked["ok"] is False
    assert blocked["status"] == "blocked_handoff_evidence_missing"
    assert blocked["governance"]["moves_mouse"] is False

    # B) Bind to a real takeover start receipt -> SAME proposal now executes (safe dry-run).
    rid = _takeover_start_receipt_id("pilot")
    bind_input_to_takeover(pid, rid, actor="op")
    allowed = execute_approved_input_action({"proposal_id": pid, "approval_phrase": phrase})
    assert allowed["ok"] is True
    assert allowed["status"] == "dry_run"
    assert allowed["governance"]["moves_mouse"] is False  # no pixel moved (ENABLE_REAL off)


def test_handoff_audit_mcp_tool_is_read_only_and_perceivable(tmp_path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    assert "francis.handoff.audit" in {t["name"] for t in list_tools()}
    res = run_tool("francis.handoff.audit", {})
    assert res["governance"]["read_only"] is True
    # Perceivable through the Lens<->MCP read-only bridge (ties in Orb/Lens + MCP).
    out = lens_perceive_via_mcp("francis.handoff.audit", {}, actor="op")
    assert out["status"] == "perceived"
    assert out["ok"] is True
