from __future__ import annotations

from typing import Any

from francis_llm import chat
from francis_presence.orb import build_orb_state
from services.hud.app.orb_authority import get_orb_authority_view
from services.hud.app.orb_perception import get_orb_perception_view
from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.voice.app.operator import build_operator_presence


def get_orb_view(
    *,
    max_actions: int = 8,
    snapshot: dict[str, Any] | None = None,
    actions: dict[str, Any] | None = None,
    voice: dict[str, Any] | None = None,
    include_perception_frame: bool = False,
) -> dict[str, object]:
    snapshot = snapshot if isinstance(snapshot, dict) else build_lens_snapshot()
    actions = actions if isinstance(actions, dict) else get_lens_actions(max_actions=max_actions)
    voice = voice if isinstance(voice, dict) else build_operator_presence(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot,
        actions_payload=actions,
    )
    orb = build_orb_state(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        snapshot=snapshot,
        actions_payload=actions,
        voice=voice,
    )
    orb["authority"] = get_orb_authority_view()
    orb["perception"] = get_orb_perception_view(include_frame_data=include_perception_frame)
    return orb


def build_orb_chat_reply(*, message: str, max_actions: int = 4) -> dict[str, Any]:
    snapshot = build_lens_snapshot()
    actions = get_lens_actions(max_actions=max_actions)
    voice = build_operator_presence(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot,
        actions_payload=actions,
    )
    orb = get_orb_view(
        max_actions=max_actions,
        snapshot=snapshot,
        actions=actions,
        voice=voice,
    )
    perception = get_orb_perception_view(include_frame_data=False)
    user_message = str(message or "").strip()
    if not user_message:
        raise ValueError("Orb chat message is required.")

    system_prompt = (
        "You are Francis speaking through the Orb. Respond briefly, concretely, and calmly. "
        "Stay grounded in the supplied Francis state. Do not invent visual facts that are not present. "
        "If perception is present, use it carefully as the current visible context. "
        "Keep responses short enough for a compact Orb chat surface."
    )
    context_block = {
        "mode": orb.get("mode"),
        "posture": orb.get("posture"),
        "summary": orb.get("summary"),
        "detail": orb.get("detail"),
        "authority": orb.get("authority"),
        "current_work": snapshot.get("current_work", {}),
        "objective": snapshot.get("objective", {}),
        "approvals": snapshot.get("approvals", {}),
        "runs": snapshot.get("runs", {}),
        "perception": {
            "state": perception.get("state"),
            "summary": perception.get("summary"),
            "detail_summary": perception.get("detail_summary"),
            "captured_at": perception.get("captured_at"),
            "display_id": perception.get("display_id"),
            "display": perception.get("display"),
            "cursor": perception.get("cursor"),
            "window": perception.get("window"),
            "freshness": perception.get("freshness"),
            "sensing": perception.get("sensing"),
            "cards": perception.get("cards"),
            "focus": {
                "width": perception.get("focus", {}).get("width"),
                "height": perception.get("focus", {}).get("height"),
                "has_image": bool(
                    perception.get("focus", {}).get("has_image")
                    or perception.get("focus", {}).get("data_url")
                ),
            },
            "frame": {
                "width": perception.get("frame", {}).get("width"),
                "height": perception.get("frame", {}).get("height"),
                "has_image": bool(
                    perception.get("frame", {}).get("has_image")
                    or perception.get("frame", {}).get("data_url")
                ),
            },
        },
    }

    content = ""
    try:
        response = chat(
            "orb.quick_chat.operator_loop",
            [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Orb context:\n{context_block}\n\n"
                        f"User message:\n{user_message}"
                    ),
                },
            ],
            timeout=45.0,
            options={"temperature": 0.2},
        )
        if isinstance(response, dict):
            message_payload = response.get("message", {})
            if isinstance(message_payload, dict):
                content = str(message_payload.get("content", "")).strip()
            elif response.get("response"):
                content = str(response.get("response", "")).strip()
    except Exception as exc:  # pragma: no cover - fallback is verified at the route layer
        content = (
            "Orb chat stayed local, but the model route did not answer cleanly. "
            f"Current mode is {orb.get('mode')}, posture is {orb.get('posture')}, and the visible context summary is: "
            f"{perception.get('summary') or orb.get('summary')}. Error: {exc}"
        )

    return {
        "status": "ok",
        "reply": content or "Orb chat is live, but no response text was returned.",
        "orb": {
            "mode": orb.get("mode"),
            "posture": orb.get("posture"),
            "summary": orb.get("summary"),
        },
        "perception": {
            "state": perception.get("state"),
            "summary": perception.get("summary"),
            "detail_summary": perception.get("detail_summary"),
            "captured_at": perception.get("captured_at"),
            "freshness": perception.get("freshness"),
            "window": perception.get("window"),
        },
    }
