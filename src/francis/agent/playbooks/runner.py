from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Callable

from .loader import Playbook, PlaybookStep, load_playbook

logger = logging.getLogger(__name__)

__all__ = ["PlaybookResult", "PlaybookRunner"]


@dataclass(frozen=True)
class PlaybookResult:
    name: str
    started_at: str
    finished_at: str
    ok: bool
    step_results: list[dict[str, Any]] = field(default_factory=list)


class PlaybookRunner:
    def __init__(self) -> None:
        self.handlers: dict[str, Callable[[PlaybookStep], dict[str, Any]]] = {
            "log": self._handle_log,
            "note": self._handle_note,
            "noop": self._handle_noop,
        }

    def run(self, playbook: Playbook) -> PlaybookResult:
        started = datetime.now(UTC).replace(microsecond=0).isoformat()
        step_results: list[dict[str, Any]] = []
        ok = True

        for step in playbook.steps:
            handler = self.handlers.get(step.action, self._handle_unknown)
            try:
                result = handler(step)
                step_results.append(result)
                if not result.get("ok", True):
                    ok = False
            except Exception as exc:
                ok = False
                step_results.append({"step_id": step.step_id, "action": step.action, "ok": False, "error": str(exc)})

        finished = datetime.now(UTC).replace(microsecond=0).isoformat()
        return PlaybookResult(
            name=playbook.name,
            started_at=started,
            finished_at=finished,
            ok=ok,
            step_results=step_results,
        )

    def _handle_log(self, step: PlaybookStep) -> dict[str, Any]:
        message = str(step.params.get("message", ""))
        logger.info("Playbook log: %s", message)
        return {"step_id": step.step_id, "action": step.action, "ok": True}

    def _handle_note(self, step: PlaybookStep) -> dict[str, Any]:
        note = str(step.params.get("text", ""))
        return {"step_id": step.step_id, "action": step.action, "ok": True, "note": note}

    def _handle_noop(self, step: PlaybookStep) -> dict[str, Any]:
        return {"step_id": step.step_id, "action": step.action, "ok": True}

    def _handle_unknown(self, step: PlaybookStep) -> dict[str, Any]:
        return {"step_id": step.step_id, "action": step.action, "ok": False, "error": "unknown_action"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="playbook_runner")
    parser.add_argument("path", help="Path to playbook (.json/.yaml)")
    args = parser.parse_args(argv)

    playbook = load_playbook(args.path)
    if not playbook:
        return 2

    runner = PlaybookRunner()
    result = runner.run(playbook)
    print(result)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
