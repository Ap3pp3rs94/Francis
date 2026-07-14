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


def _allow_orb_arrival(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_arrival(*, pointer_state: dict[str, object], timeout_seconds: float | None = None) -> dict[str, object]:
        return {
            "ok": True,
            "status": "orb_virtual_pointer_applied",
            "receipt_id": "orb-virtual-pointer-test",
            "receipt_path": "data/runtime/lens-overlay/orb-position-commands/orb-virtual-pointer-test.json",
            "pointer_updated_at": pointer_state.get("updated_at", ""),
            "orb_virtual_pointer_applied": True,
            "native_renderer_move_applied": True,
            "travelled_to_target": True,
            "contact_visual_applied": True,
            "timeout_ms": 2500,
        }

    monkeypatch.setattr(orb_operator_module, "_await_orb_arrival_readback", fake_arrival)


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
    _allow_orb_arrival(monkeypatch)

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
    _allow_orb_arrival(monkeypatch)

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
    _allow_orb_arrival(monkeypatch)

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


def test_orb_pointer_carry_records_semantic_target_without_desktop_bridge(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    bridge_calls: list[dict[str, object]] = []

    def fake_bridge(**kwargs: object) -> dict[str, object]:
        bridge_calls.append(kwargs)
        return {"ok": False, "status": "unexpected_bridge_call"}

    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "orb_carry_desktop_icon",
                "x": 68,
                "y": 232,
                "metadata": {
                    "semantic_target_id": "icon-a",
                    "semantic_target_kind": "file_icon",
                    "stable_identity_digest": "digest-a",
                    "desktop_position_index": 4,
                    "carry_phase": "carry_001",
                },
            },
        }
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert result["backend"]["input_kind"] == "orb.carry"
    assert result["backend"]["result"]["desktop_bridge"] == {}
    assert result["backend"]["result"]["desktop_action_sent"] is False
    assert result["backend"]["result"]["desktop_effect_performed"] is False
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False
    assert result["governance"]["physical_input_performed"] is False
    assert bridge_calls == []
    pointer_state = result["backend"]["result"]["pointer_state"]
    assert pointer_state["x"] == 68
    assert pointer_state["y"] == 232
    assert pointer_state["carrying"] is True
    assert pointer_state["carry_state"]["carry_state"] == "carrying"
    assert pointer_state["carry_state"]["held_target"] == {
        "semantic_target_id": "icon-a",
        "semantic_target_kind": "file_icon",
        "stable_identity_digest": "digest-a",
        "desktop_position_index": 4,
    }
    assert pointer_state["last_action"]["status"] == "virtual_pointer_carry_recorded"
    assert pointer_state["last_action"]["gesture"]["kind"] == "carry"
    assert pointer_state["last_action"]["gesture"]["semantic_target_id"] == "icon-a"


def test_orb_pointer_carry_release_clears_held_target(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _envs(tmp_path, monkeypatch)

    result = submit_orb_intent(
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "orb_carry_desktop_icon",
                "x": 64,
                "y": 48,
                "metadata": {
                    "semantic_target_id": "icon-a",
                    "semantic_target_kind": "file_icon",
                    "stable_identity_digest": "digest-a",
                    "desktop_position_index": 4,
                    "carry_phase": "destination_center",
                },
            },
        }
    )

    pointer_state = result["backend"]["result"]["pointer_state"]
    assert result["ok"] is True
    assert pointer_state["carrying"] is False
    assert pointer_state["carry_state"]["carry_state"] == "released"
    assert pointer_state["carry_state"]["held_target"] == {}
    assert pointer_state["last_action"]["status"] == "virtual_pointer_carry_released"
    assert pointer_state["last_action"]["gesture"]["carry_state"] == "released"


def test_orb_pointer_drag_propagates_user_mouse_bridge_truth(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _envs(tmp_path, monkeypatch)
    _allow_orb_arrival(monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")

    def fake_bridge(**kwargs):
        assert kwargs["input_kind"] == "mouse.drag"
        return {
            "ok": True,
            "status": "desktop_action_sent",
            "receipt_id": "orb_desktop_bridge_user_mouse",
            "receipt_path": str(tmp_path / "bridge-user-mouse.json"),
            "desktop_action_sent": True,
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": False,
            "uses_user_os_cursor": True,
            "user_mouse_taken": True,
            "physical_input_performed": True,
        }

    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

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
    assert result["backend"]["result"]["desktop_action_sent"] is True
    assert result["backend"]["result"]["desktop_effect_performed"] is True
    assert result["backend"]["result"]["physical_input_performed"] is True
    assert result["backend"]["result"]["user_os_cursor_moved"] is True
    assert result["backend"]["result"]["user_mouse_taken"] is True
    assert result["governance"]["uses_user_os_cursor"] is True
    assert result["governance"]["user_mouse_taken"] is True
    assert result["governance"]["physical_input_performed"] is True


def test_orb_pointer_drag_preserves_desktop_shell_target_requirement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    _allow_orb_arrival(monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    calls: list[dict[str, object]] = []

    def fake_bridge(**kwargs):
        calls.append(kwargs)
        payload = kwargs["payload"]
        assert isinstance(payload, dict)
        assert payload["desktop_shell_target_required"] is True
        assert payload["semantic_target_id"] == "desktop-icon-a"
        assert payload["desktop_position_index"] == 4
        assert payload["stable_identity_digest"] == "digest-a"
        return {
            "ok": True,
            "status": "desktop_action_sent",
            "receipt_id": "orb_desktop_bridge_desktop_shell",
            "receipt_path": str(tmp_path / "bridge-desktop-shell.json"),
            "desktop_action_sent": True,
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": False,
            "uses_user_os_cursor": True,
            "user_mouse_taken": True,
            "physical_input_performed": True,
            "desktop_shell_target_required": True,
        }

    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "mouse_drag",
                "x": 74,
                "y": 152,
                "target_x": 266,
                "target_y": 152,
                "button": "left",
                "metadata": {
                    "desktop_shell_target_required": True,
                    "semantic_target_id": "desktop-icon-a",
                    "desktop_position_index": 4,
                    "stable_identity_digest": "digest-a",
                },
            },
        }
    )

    assert result["ok"] is True
    assert result["intent"]["metadata"]["desktop_shell_target_required"] is True
    assert result["resolved_target"]["desktop_shell_target_required"] is True
    assert result["resolved_target"]["semantic_target_id"] == "desktop-icon-a"
    assert result["backend"]["result"]["desktop_effect_performed"] is True
    assert len(calls) == 1


def test_orb_pointer_click_with_desktop_bridge_records_action_without_user_mouse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    _allow_orb_arrival(monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")

    def fake_bridge(**kwargs):
        assert kwargs["input_kind"] == "mouse.click"
        assert kwargs["payload"]["x"] == 10
        assert kwargs["payload"]["y"] == 20
        assert kwargs["payload"]["expected_target_title"] == "Approved Safe Target"
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
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "click",
                "x": 10,
                "y": 20,
                "button": "left",
                "clicks": 1,
                "metadata": {"expected_target_title": "Approved Safe Target"},
            },
        }
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
    assert result["resolved_target"]["expected_target_title_present"] is True


def test_orb_pointer_click_waits_for_arrival_before_bridge_fire(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    events: list[str] = []

    def fake_arrival(*, pointer_state: dict[str, object], timeout_seconds: float | None = None) -> dict[str, object]:
        assert pointer_state["last_action"]["requires_orb_arrival_readback"] is True
        assert Path(tmp_path / "orb_operator" / "virtual_pointer_state.json").exists()
        events.append("arrival")
        return {
            "ok": True,
            "status": "orb_virtual_pointer_applied",
            "receipt_id": "orb-virtual-pointer-test",
            "receipt_path": "data/runtime/lens-overlay/orb-position-commands/orb-virtual-pointer-test.json",
            "orb_virtual_pointer_applied": True,
            "native_renderer_move_applied": True,
            "travelled_to_target": True,
            "contact_visual_applied": True,
        }

    def fake_bridge(**kwargs: object) -> dict[str, object]:
        events.append("bridge")
        assert kwargs["input_kind"] == "mouse.click"
        payload = kwargs["payload"]
        assert isinstance(payload, dict)
        assert payload["orb_arrival_satisfied"] is True
        assert payload["orb_arrival_receipt_id"] == "orb-virtual-pointer-test"
        return {
            "ok": True,
            "status": "desktop_action_sent",
            "receipt_id": "orb_desktop_bridge_after_arrival",
            "receipt_path": str(tmp_path / "bridge-after-arrival.json"),
            "desktop_action_sent": True,
            "desktop_effect_performed": True,
            "desktop_effect_confirmed": False,
            "uses_user_os_cursor": False,
            "user_mouse_taken": False,
            "physical_input_performed": False,
        }

    monkeypatch.setattr(orb_operator_module, "_await_orb_arrival_readback", fake_arrival)
    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is True
    assert result["status"] == "complete"
    assert events == ["arrival", "bridge"]
    assert result["backend"]["result"]["orb_arrival_satisfied"] is True
    assert result["backend"]["result"]["bridge_fired_after_arrival"] is True
    assert result["backend"]["result"]["action_fired_without_orb_arrival"] is False
    assert result["governance"]["bridge_fired_after_arrival"] is True


def test_orb_pointer_click_timeout_blocks_before_bridge_fire(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _envs(tmp_path, monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    bridge_calls: list[dict[str, object]] = []

    def fake_arrival(*, pointer_state: dict[str, object], timeout_seconds: float | None = None) -> dict[str, object]:
        return {
            "ok": False,
            "status": "blocked_orb_arrival_timeout",
            "receipt_id": "orb-virtual-pointer-timeout",
            "receipt_path": "data/runtime/lens-overlay/orb-position-commands/orb-virtual-pointer-timeout.json",
            "orb_virtual_pointer_applied": False,
            "native_renderer_move_applied": False,
            "timeout_ms": 50,
        }

    def fake_bridge(**kwargs: object) -> dict[str, object]:
        bridge_calls.append(kwargs)
        return {"ok": True, "status": "unexpected_bridge_call"}

    monkeypatch.setattr(orb_operator_module, "_await_orb_arrival_readback", fake_arrival)
    monkeypatch.setattr(orb_operator_module, "perform_orb_desktop_action", fake_bridge)

    result = submit_orb_intent(
        {"mode": "orb_pointer", "intent": {"kind": "click", "x": 10, "y": 20, "button": "left", "clicks": 1}}
    )

    assert result["ok"] is False
    assert result["status"] == "blocked_orb_arrival_timeout"
    assert result["feedback_state"] == "blocked"
    assert bridge_calls == []
    assert result["backend"]["result"]["desktop_action_sent"] is False
    assert result["backend"]["result"]["orb_arrival_satisfied"] is False
    assert result["backend"]["result"]["unembodied_action_blocked"] is True
    assert result["governance"]["unembodied_action_blocked"] is True


def test_orb_arrival_wait_treats_travel_started_receipt_as_progress(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    receipts = [
        {
            "ok": True,
            "status": "orb_move_place_travel_started",
            "travel_duration_ms": 2200,
            "runtime_overlay_position_changed": False,
            "native_renderer_move_applied": False,
        },
        {
            "ok": True,
            "status": "orb_virtual_pointer_applied",
            "runtime_overlay_position_changed": True,
            "native_renderer_move_applied": True,
            "native_renderer_move_status": "native_renderer_position_posted",
            "travelled_to_target": True,
        },
    ]
    read_count = 0

    def fake_read_json_object(path: Path) -> dict[str, object]:
        nonlocal read_count
        index = min(read_count, len(receipts) - 1)
        read_count += 1
        return receipts[index]

    monkeypatch.setattr(orb_operator_module, "_read_json_object", fake_read_json_object)
    monkeypatch.setattr(orb_operator_module.time, "sleep", lambda seconds: None)

    result = orb_operator_module._await_orb_arrival_readback(
        pointer_state={"updated_at": "2026-07-13T00:00:00+00:00"},
        timeout_seconds=0.5,
    )

    assert result["ok"] is True
    assert result["status"] == "orb_virtual_pointer_applied"
    assert result["progress_receipt_observed"] is True
    assert read_count == 2


def test_orb_arrival_wait_reads_powershell_utf8_bom_receipt(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _envs(tmp_path, monkeypatch)
    updated_at = "2026-07-13T00:00:00+00:00"
    receipt_path = orb_operator_module._orb_virtual_pointer_receipt_path(updated_at)
    receipt_path.parent.mkdir(parents=True)
    receipt_path.write_text(
        """{
  "ok": true,
  "status": "orb_virtual_pointer_applied",
  "runtime_overlay_position_changed": true,
  "native_renderer_move_applied": true,
  "native_renderer_move_status": "native_renderer_position_posted",
  "travelled_to_target": true
}
""",
        encoding="utf-8-sig",
    )

    result = orb_operator_module._await_orb_arrival_readback(
        pointer_state={"updated_at": updated_at},
        timeout_seconds=0.5,
    )

    assert result["ok"] is True
    assert result["status"] == "orb_virtual_pointer_applied"
    assert result["native_renderer_move_applied"] is True


def test_orb_pointer_click_with_desktop_bridge_propagates_confirmed_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _envs(tmp_path, monkeypatch)
    _allow_orb_arrival(monkeypatch)
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
    _allow_orb_arrival(monkeypatch)

    result = submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "type_text", "text": "visible label"}})

    receipt_path = Path(result["backend"]["result"]["desktop_bridge_receipt_path"])
    receipt_text = receipt_path.read_text(encoding="utf-8")
    assert result["status"] == "visible_only"
    assert result["backend"]["input_kind"] == "keyboard.type"
    assert "visible label" not in receipt_text
    assert "text_sha256" in receipt_text
    assert result["governance"]["uses_user_os_cursor"] is False
    assert result["governance"]["user_mouse_taken"] is False


def test_orb_pointer_type_carries_expected_target_title_to_bridge(tmp_path: Path, monkeypatch) -> None:
    _envs(tmp_path, monkeypatch)
    _allow_orb_arrival(monkeypatch)
    monkeypatch.setenv("FRANCIS_ORB_DESKTOP_BRIDGE_ENABLE", "1")
    submit_orb_intent({"mode": "orb_pointer", "intent": {"kind": "mouse.move", "x": 120, "y": 140}})

    def fake_bridge(**kwargs):
        assert kwargs["input_kind"] == "keyboard.type"
        assert kwargs["payload"]["x"] == 120
        assert kwargs["payload"]["y"] == 140
        assert kwargs["payload"]["expected_target_title"] == "Approved Safe Target"
        return {
            "ok": True,
            "status": "desktop_action_confirmed",
            "receipt_id": "orb_desktop_bridge_expected_target",
            "receipt_path": str(tmp_path / "bridge-expected-target.json"),
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
        {
            "mode": "orb_pointer",
            "intent": {
                "kind": "type_text",
                "text": "bounded effect",
                "metadata": {"expected_target_title": "Approved Safe Target"},
            },
        }
    )

    assert result["ok"] is True, result
    assert result["status"] == "complete"
    assert result["resolved_target"]["expected_target_title_present"] is True
    assert "expected_target_title_sha256" in result["resolved_target"]
    assert result["governance"]["physical_input_performed"] is False


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


def test_latest_orb_operator_state_can_read_without_creating_state_dirs(tmp_path: Path, monkeypatch) -> None:
    state_root = tmp_path / "orb_operator"
    monkeypatch.setenv("FRANCIS_ORB_OPERATOR_STATE_DIR", str(state_root))

    state = latest_orb_operator_state(create_dirs=False)

    assert state["read_only"] is True
    assert state["feedback_state"] == "idle"
    assert state["virtual_pointer"]["available"] is False
    assert state["grants_execution_authority"] is False
    assert not state_root.exists()


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
