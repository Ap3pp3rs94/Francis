from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterable, Iterator

WORKSPACE_ROOT = Path(__file__).resolve().parents[2] / "workspace"

MISSION_RUNTIME_PATHS = (
    "missions/missions.json",
    "missions/history.jsonl",
    "queue/jobs.jsonl",
    "queue/deadletter.jsonl",
    "queue/worker_cycle_gate.json",
    "runs/run_ledger.jsonl",
    "runs/last_run.json",
    "runs/last_worker_run.json",
    "approvals/requests.jsonl",
    "journals/decisions.jsonl",
)

AUTONOMY_RUNTIME_PATHS = MISSION_RUNTIME_PATHS + (
    "autonomy/action_budget_state.json",
    "autonomy/events.jsonl",
    "autonomy/dispatch_history.jsonl",
    "autonomy/tick_history.jsonl",
    "autonomy/last_dispatch.json",
    "autonomy/last_tick.json",
    "autonomy/deadletter.jsonl",
    "incidents/incidents.jsonl",
)


def _stash(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _restore(path: Path, content: str | None) -> None:
    if content is None:
        if path.exists():
            path.unlink()
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


@contextmanager
def isolated_workspace_files(rel_paths: Iterable[str]) -> Iterator[None]:
    paths = [(WORKSPACE_ROOT / rel_path) for rel_path in rel_paths]
    snapshots = {path: _stash(path) for path in paths}
    try:
        yield
    finally:
        for path, content in snapshots.items():
            _restore(path, content)
