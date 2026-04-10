from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

__all__ = ["PlaybookStep", "Playbook", "load_playbook"]


@dataclass(frozen=True)
class PlaybookStep:
    step_id: str
    action: str
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Playbook:
    name: str
    steps: list[PlaybookStep]
    source_path: str


def load_playbook(path: str) -> Playbook | None:
    p = Path(path)
    if not p.exists():
        logger.error("Playbook not found: %s", p)
        return None

    try:
        raw = p.read_text(encoding="utf-8", errors="replace")
        data = _parse_data(raw, p.suffix.lower())
        if not isinstance(data, dict):
            logger.error("Playbook must be an object: %s", p)
            return None
        name = str(data.get("name") or p.stem)
        steps_raw = data.get("steps") or []
        if not isinstance(steps_raw, list):
            logger.error("Playbook steps must be a list: %s", p)
            return None
        steps: list[PlaybookStep] = []
        for idx, step in enumerate(steps_raw, start=1):
            if not isinstance(step, dict):
                continue
            steps.append(
                PlaybookStep(
                    step_id=str(step.get("id") or f"step_{idx}"),
                    action=str(step.get("action") or "noop"),
                    params=dict(step.get("params") or {}),
                )
            )
        return Playbook(name=name, steps=steps, source_path=str(p))
    except Exception as exc:
        logger.error("Failed to load playbook %s: %s", p, exc)
        return None


def _parse_data(raw: str, suffix: str) -> dict[str, Any] | None:
    if suffix in {".json", ""}:
        try:
            return json.loads(raw)
        except Exception:
            return None
    if suffix in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except Exception:
            logger.error("PyYAML not installed; cannot parse %s", suffix)
            return None
        return yaml.safe_load(raw)
    return None
