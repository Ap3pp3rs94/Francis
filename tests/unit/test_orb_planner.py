from __future__ import annotations

import services.hud.app.orb_planner as orb_planner


def test_build_orb_chat_plan_falls_back_to_control_mode_answer_when_model_is_unavailable(monkeypatch) -> None:
    monkeypatch.setattr(orb_planner, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    payload = orb_planner.build_orb_chat_plan(
        message="What is Pilot mode?",
        orb_context={"summary": "Francis is ambient on the desktop."},
        perception={"summary": "Francis sees the active display."},
        snapshot={"control": {"mode": "assist"}},
        short_term_messages=[],
        long_term_memory={},
    )

    assert payload["intent"]["kind"] == "conversation.answer"
    assert payload["plan"] is None
    assert "takeover-on-command" in payload["reply"]


def test_build_orb_chat_plan_uses_perception_summary_for_visibility_questions(monkeypatch) -> None:
    monkeypatch.setattr(orb_planner, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    payload = orb_planner.build_orb_chat_plan(
        message="What do you see right now?",
        orb_context={"summary": "Francis is ambient on the desktop."},
        perception={"summary": "Francis sees the active display and the foreground editor window."},
        snapshot={"control": {"mode": "assist"}},
        short_term_messages=[],
        long_term_memory={},
    )

    assert payload["intent"]["kind"] == "conversation.answer"
    assert payload["plan"] is None
    assert payload["reply"] == "Francis sees the active display and the foreground editor window."


def test_build_orb_chat_plan_heuristically_opens_apps_through_the_start_button_path(monkeypatch) -> None:
    monkeypatch.setattr(orb_planner, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    payload = orb_planner.build_orb_chat_plan(
        message="open notepad",
        orb_context={"summary": "Francis is ambient on the desktop."},
        perception={"summary": "Francis sees the desktop."},
        snapshot={"control": {"mode": "pilot"}},
        short_term_messages=[],
        long_term_memory={},
    )

    assert payload["intent"]["kind"] == "desktop.action"
    assert payload["should_execute"] is True
    assert payload["plan"] is not None
    assert payload["plan"]["steps"][0]["kind"] == "mouse.click"
    assert payload["plan"]["steps"][0]["args"]["anchor"] == "start_button"
    assert payload["plan"]["steps"][0]["args"]["button"] == "left"
    assert payload["plan"]["steps"][1]["kind"] == "keyboard.type"
    assert payload["plan"]["steps"][2]["kind"] == "keyboard.key"


def test_build_orb_chat_plan_heuristically_maps_save_to_ctrl_s(monkeypatch) -> None:
    monkeypatch.setattr(orb_planner, "chat", lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))

    payload = orb_planner.build_orb_chat_plan(
        message="save",
        orb_context={"summary": "Francis is ambient on the desktop."},
        perception={"summary": "Francis sees the editor."},
        snapshot={"control": {"mode": "pilot"}},
        short_term_messages=[],
        long_term_memory={},
    )

    assert payload["intent"]["kind"] == "desktop.action"
    assert payload["plan"] is not None
    assert payload["plan"]["steps"] == [
        {
            "kind": "keyboard.shortcut",
            "args": {"keys": ["ctrl", "s"]},
            "reason": "Use the standard save shortcut on the active surface.",
            "interaction": "keyboard_navigation",
            "delay_ms": 180,
        }
    ]
