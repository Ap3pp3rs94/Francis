from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import shutil
import tempfile
from typing import Iterable, Iterator

WORKSPACE_ROOT = Path(__file__).resolve().parents[2] / "workspace"

INBOX_RUNTIME_PATHS = (
    "inbox/messages.jsonl",
)

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

SECURITY_RUNTIME_PATHS = (
    "security/quarantine.jsonl",
    "incidents/incidents.jsonl",
    "logs/francis.log.jsonl",
    "journals/decisions.jsonl",
    "runs/run_ledger.jsonl",
    "apprenticeship/sessions.json",
)

TELEMETRY_RUNTIME_PATHS = (
    "telemetry/config.json",
    "telemetry/events.jsonl",
    "autonomy/events.jsonl",
)

LENS_USAGE_RUNTIME_PATHS = (
    "apprenticeship/sessions.json",
    "approvals/requests.jsonl",
    "forge/catalog.json",
    "journals/decisions.jsonl",
    "journals/fs.jsonl",
    "lens/repo_drilldown.json",
    "runs/run_ledger.jsonl",
    "telemetry/events.jsonl",
)

RECEIPTS_LENS_RUNTIME_PATHS = MISSION_RUNTIME_PATHS + (
    "autonomy/action_budget_state.json",
    "autonomy/events.jsonl",
    "autonomy/last_dispatch.json",
    "autonomy/last_tick.json",
    "autonomy/reactor_guardrail_state.json",
    "control/handback_exports/index.jsonl",
    "control/takeover.json",
    "control/takeover_activity.jsonl",
    "journals/fs.jsonl",
    "lens/repo_drilldown.json",
)

PORTABILITY_RUNTIME_PATHS = (
    "approvals/requests.jsonl",
    "control/handback_exports",
    "control/takeover.json",
    "federation/topology.json",
    "forge/catalog.json",
    "journals/decisions.jsonl",
    "journals/fs.jsonl",
    "logs/francis.log.jsonl",
    "managed_copies/deltas.jsonl",
    "managed_copies/registry.json",
    "missions/history.jsonl",
    "missions/missions.json",
    "portability",
    "runs/run_ledger.jsonl",
    "swarm/delegations.jsonl",
    "swarm/units.json",
    "telemetry/config.json",
)

SWARM_RUNTIME_PATHS = (
    "journals/decisions.jsonl",
    "journals/fs.jsonl",
    "logs/francis.log.jsonl",
    "runs/run_ledger.jsonl",
    "swarm/deadletter.jsonl",
    "swarm/delegations.jsonl",
    "swarm/units.json",
)

APPEND_ONLY_RUNTIME_PATHS = {
    "control/handback_exports/index.jsonl",
    "control/takeover_activity.jsonl",
    "journals/fs.jsonl",
    "logs/francis.log.jsonl",
    "runs/run_ledger.jsonl",
}


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


def _remove_path(path: Path) -> None:
    if path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


@contextmanager
def isolated_workspace_paths(rel_paths: Iterable[str]) -> Iterator[None]:
    paths = [(rel_path, WORKSPACE_ROOT / rel_path) for rel_path in rel_paths]
    with tempfile.TemporaryDirectory(prefix="francis-workspace-state-") as temp_dir:
        stash_root = Path(temp_dir)
        snapshots: list[dict[str, object]] = []
        for index, (rel_path, path) in enumerate(paths):
            if path.is_dir():
                stash_path = stash_root / str(index)
                shutil.copytree(path, stash_path)
                snapshots.append({"path": path, "kind": "dir", "stash_path": stash_path})
            elif path.exists():
                if rel_path in APPEND_ONLY_RUNTIME_PATHS:
                    snapshots.append({"path": path, "kind": "append_only_file", "size": path.stat().st_size})
                else:
                    stash_path = stash_root / str(index)
                    stash_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, stash_path)
                    snapshots.append({"path": path, "kind": "file", "stash_path": stash_path})
            else:
                snapshots.append({"path": path, "kind": "missing"})
        try:
            yield
        finally:
            for snapshot in snapshots:
                path = snapshot.get("path")
                kind = snapshot.get("kind")
                if not isinstance(path, Path) or not isinstance(kind, str):
                    continue
                if kind == "append_only_file":
                    original_size = int(snapshot.get("size", 0))
                    if not path.exists():
                        raise RuntimeError(f"append-only runtime file missing during restore: {path}")
                    current_size = path.stat().st_size
                    if current_size < original_size:
                        raise RuntimeError(
                            f"append-only runtime file shrank during isolated test run: {path} "
                            f"({current_size} < {original_size})"
                        )
                    with path.open("rb+") as handle:
                        handle.truncate(original_size)
                    continue

                _remove_path(path)
                stash_path = snapshot.get("stash_path")
                if kind == "dir" and isinstance(stash_path, Path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(stash_path, path)
                elif kind == "file" and isinstance(stash_path, Path):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(stash_path, path)


@contextmanager
def isolated_workspace_files(rel_paths: Iterable[str]) -> Iterator[None]:
    with isolated_workspace_paths(rel_paths):
        yield
