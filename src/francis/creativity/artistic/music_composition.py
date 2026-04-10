from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["MusicPrompt", "MusicComposer"]


@dataclass(frozen=True)
class MusicPrompt:
    mood: str
    tempo_bpm: int = 100
    metadata: dict[str, Any] = field(default_factory=dict)


class MusicComposer:
    def compose(self, prompt: MusicPrompt) -> dict[str, Any]:
        if not isinstance(prompt, MusicPrompt):
            logger.warning("compose expected MusicPrompt")
            return {}
        mood = prompt.mood.strip() if isinstance(prompt.mood, str) else ""
        tempo = max(40, min(200, int(prompt.tempo_bpm)))
        if not mood:
            return {}
        return {"mood": mood, "tempo_bpm": tempo, "structure": ["intro", "theme", "outro"]}
