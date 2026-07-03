from __future__ import annotations

from pathlib import Path

import pytest

from francis.input_actuator import orb_operator as orb_operator_module
from francis.input_actuator.orb_operator import (
    DesktopInputBackend,
    OrbIntent,
    latest_orb_operator_state,
    submit_orb_intent,
    submit_orb_sequence,
)
from francis.input_actuator.tools import propose_input_action
from francis.world_state import orb as orb_world_state

pytestmark = pytest.mark.unit


def _envs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRANCIS_ORB_OPERATOR_STATE_DIR", str(tmp_path / "orb_operator"))
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_STATE_DIR", str(tmp_path / "input"))
    monkeypatch.setenv("FRANCIS_TAKEOVER_SESSION_STATE_DIR", str(tmp_path / "takeover"))
    monkeypatch.setenv("FRANCIS_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", raising=False)
    monkeypatch.delenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", raising=False)
    monkeypatch.delenv("FRANCIS_ORB_DESKTOP_BRIDGE_BACKEND", raising=False)


def test_orb_intent_public_contract_redacts_typed_text() -> None:
    intent = OrbIntent.type_text("hello Francis")
    public = intent.public_dict()

    assert public["kind"] == "type_text"
    assert public["text_length"] == len("hello Francis")
    assert "text_sha256" in public
    assert "hello Francis" not in str(public)


def test_desktop_input_backend_dry_run_mouse_move_writes_proposal(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = DesktopInputBackend(mode="dry_run", actor="test", objective="aim").mouse_move(10, 20)

    assert result.ok is True
    assert result.status == "dry_run_proposed"
    assert result.performed is False
    assert result.dry_run is True
    assert result.proposal_id
    assert result.governance["manual_approval_required_for_execution"] is True
    assert (tmp_path / "input" / "proposals" / f"{result.proposal_id}.json").exists()


def test_orb_move_dry_run_records_operator_receipt(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "dry_run", "intent": {"kind": "move_to", "x": 101, "y": 202}})

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["feedback_state"] == "moving"
    assert result["backend"]["performed"] is False
    assert result["backend"]["result"]["input_execution_attempted"] is False
    assert Path(result["operator_receipt_path"]).exists()


def test_orb_pointer_move_updates_virtual_pointer_without_user_mouse(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "move_to", "x": 101, "y": 202}})

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["backend"]["backend"] == "francis.orb_virtual_pointer"
    assert result["backend"]["performed"] is False
    assert result["backend"]["dry_run"] is False
    assert result["backend"]["result"]["input_execution_attempted"] is False
    assert result["backend"]["result"]["virtual_pointer_updated"] is True
    assert result["backend"]["result"]["physical_input_performed"] is False
    assert result["backend"]["result"]["user_mouse_taken"] is False
    assert result["governance"]["virtual_pointer_only"] is True
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False
    assert result["governance"]["physical_input_performed"] is False
    assert not (tmp_path / "input" / "proposals").exists()
    pointer_path = tmp_path / "orb_operator" / "virtual_pointer_state.json"
    assert pointer_path.exists()
    pointer_text = pointer_path.read_text(encoding="utf-8")
    assert '"x": 101' in pointer_text
    assert '"y": 202' in pointer_text


def test_orb_click_dry_run_records_mouse_action_without_live_input(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent(
        {"mode": "dry_run", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["feedback_state"] == "clicking"
    assert result["backend"]["input_kind"] == "mouse.click"
    assert result["backend"]["performed"] is False
    assert result["governance"]["live_input_performed"] is False


def test_orb_pointer_click_records_virtual_event_without_desktop_click(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "visible_only"
    assert result["backend"]["input_kind"] == "mouse.click"
    assert result["backend"]["performed"] is False
    assert result["backend"]["result"]["desktop_effect_performed"] is False
    assert result["backend"]["result"]["desktop_action_sent"] is False
    assert result["backend"]["result"]["desktop_bridge_status"] == "blocked_bridge_disabled"
    assert Path(result["backend"]["result"]["desktop_bridge_receipt_path"]).exists()
    assert result["backend"]["result"]["requires_app_bridge_for_desktop_effect"] is True
    assert result["governance"]["virtual_pointer_only"] is True
    assert result["governance"]["live_input_performed"] is False
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_pointer_right_click_records_virtual_event_without_user_mouse(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "right", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "visible_only"
    assert result["backend"]["input_kind"] == "mouse.click"
    assert result["backend"]["result"]["pointer_state"]["last_action"]["status"] == (
        "virtual_pointer_right_click_recorded"
    )
    assert result["backend"]["result"]["pointer_state"]["last_action"]["public_action"]["button"] == "right"
    assert result["backend"]["result"]["desktop_effect_performed"] is False
    assert result["governance"]["virtual_pointer_only"] is True
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_pointer_drag_records_virtual_path_without_user_mouse(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent(
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "mouse_drag",
                "x": 10,
                "y": 20,
                "target_x": 60,
                "target_y": 80,
                "button": "left",
            },
        }
    )

    assert result["ok"] is True
    assert result["status"] == "visible_only"
    assert result["resolved_target"]["target_x"] == 60
    assert result["resolved_target"]["target_y"] == 80
    assert result["backend"]["input_kind"] == "mouse.drag"
    pointer_state = result["backend"]["result"]["pointer_state"]
    assert pointer_state["x"] == 60
    assert pointer_state["y"] == 80
    assert pointer_state["last_action"]["status"] == "virtual_pointer_drag_recorded"
    assert pointer_state["last_action"]["gesture"]["kind"] == "drag"
    assert pointer_state["last_action"]["gesture"]["start"] == {"x": 10, "y": 20}
    assert pointer_state["last_action"]["gesture"]["end"] == {"x": 60, "y": 80}
    assert result["backend"]["result"]["desktop_effect_performed"] is False
    assert result["governance"]["virtual_pointer_only"] is True
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_pointer_click_with_desktop_bridge_records_action_without_user_mouse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")

    def fake_bridge(**kwargs):
        assert kwargs["input_kind"] == "mouse.click"
        assert kwargs["payload"]["x"] == 10
        assert kwargs["payload"]["y"] == 20
        return {
            "ok": True,
            "status": "desktop_action_sent",
            "receipt_id": "orb_desktop_bridge_test",
            "receipt_path": str(tmp_path / "bridge.json"),
            "desktop_action_sent": True,
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": False,
            "uses_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
        }

    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["backend"]["result"]["desktop_action_sent"] is True
    assert result["backend"]["result"]["desktop_effect_performed"] is True
    assert result["governance"]["desktop_action_sent"] is True
    assert result["governance"]["desktop_effect_performed"] is True
    assert result["governance"]["desktop_effect_confirmed"] is False
    assert result["governance"]["physical_input_performed"] is False
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_pointer_click_with_desktop_bridge_propagates_confirmed_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")

    def fake_bridge(**kwargs):
        assert kwargs["input_kind"] == "mouse.click"
        return {
            "ok": True,
            "status": "desktop_action_confirmed",
            "receipt_id": "orb_desktop_bridge_confirmed",
            "receipt_path": str(tmp_path / "bridge-confirmed.json"),
            "desktop_action_sent": True,
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": True,
            "target_observer_status": "confirmed_target_state_changed",
            "uses_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
        }

    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["backend"]["result"]["desktop_effect_confirmed"] is True
    assert result["governance"]["desktop_action_sent"] is True
    assert result["governance"]["desktop_effect_performed"] is True
    assert result["governance"]["desktop_effect_confirmed"] is True
    assert result["governance"]["physical_input_performed"] is False


def test_orb_keyboard_type_dry_run_receipt_redacts_text(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "dry_run", "intent": {"kind": "type_text", "text": "visible label"}})
    receipt_text = Path(result["operator_receipt_path"]).read_text(encoding="utf-8")

    assert result["ok"] is True
    assert result["feedback_state"] == "typing"
    assert result["backend"]["input_kind"] == "keyboard.type"
    assert "visible label" not in receipt_text
    assert "text_sha256" in receipt_text


def test_orb_pointer_type_bridge_receipt_redacts_text(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "type_text", "text": "visible label"}})

    receipt_path = Path(result["backend"]["result"]["desktop_bridge_receipt_path"])
    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert result["status"] == "visible_only"
    assert result["backend"]["input_kind"] == "keyboard.type"
    assert "visible label" not in receipt_text
    assert "text_sha256" in receipt_text
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_key_press_dry_run_uses_keyboard_hotkey(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "dry_run", "intent": {"kind": "key_press", "key": "enter"}})

    assert result["ok"] is True
    assert result["status"] == "dry_run"
    assert result["backend"]["input_kind"] == "keyboard.hotkey"
    assert result["backend"]["performed"] is False


def test_guarded_live_without_approval_blocks_and_writes_rejection_receipt(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_INPUT_ACTUATOR_ENABLE_REAL", "1")

    result = submit_orb_intent({"mode": "guarded_live", "intent": {"kind": "click", "x": 10, "y": 20}})

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["feedback_state"] == "blocked"
    assert result["backend"]["performed"] is False
    assert result["backend"]["status"] == "approval_required"
    assert result["governance"]["live_input_performed"] is False
    assert Path(result["operator_receipt_path"]).exists()


def test_guarded_live_rejects_mismatched_input_proposal_before_execution(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    proposal = propose_input_action(
        {
            "actor": "test",
            "objective": "move",
            "kind": "mouse.move",
            "payload": {"x": 1, "y": 2},
        }
    )

    result = submit_orb_intent(
        {
            "mode": "guarded_live",
            "proposal_id": proposal["data"]["proposal_id"],
            "approval_phrase": proposal["data"]["approval_phrase"],
            "intent": {"kind": "click", "x": 1, "y": 2},
        }
    )

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["backend"]["error"] == "input_proposal_kind_mismatch"
    assert result["backend"]["performed"] is False
    assert result["backend"].get("input_receipt_id") is None


def test_unsupported_focus_window_is_governance_rejection_with_receipt(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent({"mode": "dry_run", "intent": {"kind": "focus_window", "window_ref": "notepad"}})

    assert result["ok"] is False
    assert result["status"] == "blocked"
    assert result["governance"]["unsupported_reason"] == "focus_window_backend_not_declared"
    assert Path(result["operator_receipt_path"]).exists()


def test_orb_sequence_dry_run_move_click_type_prints_receipt_paths(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_sequence(
        {
            "mode": "dry_run",
            "intents": [
                {"kind": "move_to", "x": 1, "y": 2},
                {"kind": "click", "x": 1, "y": 2},
                {"kind": "type_text", "text": "operator dry run"},
            ],
        }
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert len(result["receipt_paths"]) == 3
    assert all(Path(path).exists() for path in result["receipt_paths"])


def test_latest_orb_operator_state_is_read_only_feedback(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    submit_orb_intent({"mode": "dry_run", "intent": {"kind": "move_to", "x": 3, "y": 4}})

    state = latest_orb_operator_state()
    bridged = orb_world_state._orb_operator_input_state()

    assert state["feedback_state"] == "moving"
    assert state["read_only"] is True
    assert state["grants_execution_authority"] is False
    assert bridged["feedback_state"] == "moving"
    assert bridged["grants_execution_authority"] is False


def test_latest_orb_operator_state_surfaces_virtual_pointer(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "move_to", "x": 33, "y": 44}})

    state = latest_orb_operator_state()
    bridged = orb_world_state._orb_operator_input_state()

    assert state["virtual_pointer"]["available"] is True
    assert state["virtual_pointer"]["x"] == 33
    assert state["virtual_pointer"]["y"] == 44
    assert state["virtual_pointer"]["controls_user_os_cursor"] is False
    assert state["user_mouse_taken"] is False
    assert bridged["virtual_pointer"]["x"] == 33
    assert bridged["virtual_pointer"]["user_mouse_taken"] is False
