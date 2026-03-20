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
