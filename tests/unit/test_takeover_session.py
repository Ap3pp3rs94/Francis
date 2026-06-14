from __future__ import annotations

from pathlib import Path

from francis.input_actuator.tools import execute_approved_input_action, propose_input_action
from francis.takeover_session.tools import (
    propose_takeover_session,
    start_approved_takeover_session,
    takeover_status_snapshot,
)


def test_takeover_status_is_read_only_without_raw_authority(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))

    result = takeover_status_snapshot()

    assert result["ok"] is True
    assert result["governance"]["read_only"] is True
    assert result["governance"]["raw_input"] is False
    assert result["governance"]["raw_shell"] is False
    assert result["governance"]["takeover_never_implicit"] is True
    assert result["control_transfer_active"] is False


def test_takeover_proposal_requires_manual_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))

    result = propose_takeover_session(
        {"actor": "test", "reason": "start pilot safely", "mode": "pilot", "duration_sec": 120}
    )

    assert result["ok"] is True
    assert result["status"] == "approval_required"
    assert result["approval_phrase"].startswith("APPROVE TAKEOVER ")
    assert result["governance"]["starts_session"] is False
    assert result["governance"]["raw_input"] is False


def test_takeover_start_refuses_without_exact_approval(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))
    proposal = propose_takeover_session({"actor": "test", "reason": "start pilot safely", "mode": "pilot"})

    denied = start_approved_takeover_session(
        {"proposal_id": proposal["proposal_id"], "approval_phrase": "APPROVE wrong"}
    )

    assert denied["ok"] is False
    assert denied["status"] == "approval_required"
    assert denied["governance"]["starts_session"] is False
    assert denied["governance"]["raw_input"] is False


def test_takeover_start_is_stage8_gated_without_closure_receipt(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    proposal = propose_takeover_session({"actor": "test", "reason": "start pilot safely", "mode": "pilot"})

    result = start_approved_takeover_session(
        {"proposal_id": proposal["proposal_id"], "approval_phrase": proposal["approval_phrase"]}
    )

    assert result["ok"] is False
    assert result["status"] == "awaiting_stage8_closure_receipt"
    assert result["control_transfer_active"] is False
    assert result["governance"]["raw_input"] is False
    assert result["stage9_result"]["writes_receipt"] is False


def test_input_real_env_still_blocks_without_active_takeover(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover_session"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", "1")

    proposal = propose_input_action(
        {
            "actor": "test",
            "objective": "blocked physical move without takeover",
            "kind": "mouse.move",
            "payload": {"x": 10, "y": 20},
        }
    )

    result = execute_approved_input_action(
        {"proposal_id": proposal["data"]["proposal_id"], "approval_phrase": proposal["data"]["approval_phrase"]}
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_active_takeover_required"
    assert result["governance"]["moves_mouse"] is False
    assert result["governance"]["raw_mcp_input_authority"] is False
