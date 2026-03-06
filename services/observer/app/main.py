from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.clock import utc_now_iso
from francis_core.config import settings
from francis_core.workspace_fs import WorkspaceFS

from services.observer.app.anomaly.baselines import load_or_init
from services.observer.app.anomaly.detectors import detect
from services.observer.app.anomaly.scoring import score as score_anomalies
from services.observer.app.emitter import ObserverEmitter
from services.observer.app.probes import cpu, disk, memory, network, processes, repo, services


def collect_snapshot(*, workspace_root: Path, repo_root: Path) -> dict[str, Any]:
    return {
        "ts": utc_now_iso(),
        "disk": disk.collect(workspace_root),
        "cpu": cpu.collect(),
        "memory": memory.collect(),
        "network": network.collect(),
        "processes": processes.collect(),
        "repo": repo.collect(repo_root),
        "services": services.collect(repo_root),
    }


def run_cycle(*, run_id: str, repo_root: Path | None = None, workspace_root: Path | None = None) -> dict[str, Any]:
    resolved_repo = (repo_root or Path(__file__).resolve().parents[3]).resolve()
    resolved_workspace = (workspace_root or Path(settings.workspace_root)).resolve()

    fs = WorkspaceFS(
        roots=[resolved_workspace],
        journal_path=(resolved_workspace / "journals" / "fs.jsonl").resolve(),
    )
    baseline = load_or_init(fs)
    snapshot = collect_snapshot(workspace_root=resolved_workspace, repo_root=resolved_repo)
    anomalies = detect(snapshot, baseline)
    score = score_anomalies(anomalies)
    emitted = ObserverEmitter(resolved_workspace).emit_cycle(
        run_id=run_id,
        snapshot=snapshot,
        anomalies=anomalies,
        score=score,
    )
    return {
        "status": "ok",
        "run_id": run_id,
        "snapshot": snapshot,
        "baseline": baseline,
        "anomalies": anomalies,
        "score": score,
        "emitted": emitted,
    }
