from __future__ import annotations

from francis_presence.orb import build_orb_state
from services.hud.app.orchestrator_bridge import get_lens_actions
from services.hud.app.state import build_lens_snapshot
from services.voice.app.operator import build_operator_presence


def get_orb_view(*, max_actions: int = 8) -> dict[str, object]:
    snapshot = build_lens_snapshot()
    actions = get_lens_actions(max_actions=max_actions)
    voice = build_operator_presence(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        max_actions=min(max_actions, 3),
        snapshot=snapshot,
        actions_payload=actions,
    )
    return build_orb_state(
        mode=str(snapshot.get("control", {}).get("mode", "assist")),
        snapshot=snapshot,
        actions_payload=actions,
        voice=voice,
    )
