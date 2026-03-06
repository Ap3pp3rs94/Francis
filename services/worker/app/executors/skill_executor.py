from __future__ import annotations

from pathlib import Path
from typing import Any

from francis_core.workspace_fs import WorkspaceFS
from francis_skills.contracts import SkillCall
from francis_skills.executor import SkillExecutor


def execute(
    job: dict[str, Any],
    *,
    run_id: str,
    fs: WorkspaceFS,
    repo_root: Path,
) -> dict[str, Any]:
    skill_name = str(job.get("skill", "")).strip()
    if not skill_name:
        return {
            "ok": False,
            "run_id": run_id,
            "job_id": str(job.get("id", "")),
            "action": str(job.get("action", "")),
            "error": "missing skill name",
        }
    args = job.get("args", {})
    if not isinstance(args, dict):
        args = {}

    executor = SkillExecutor.with_defaults(fs=fs, repo_root=repo_root)
    result = executor.execute(SkillCall(name=skill_name, args=args))
    return {
        "ok": result.ok,
        "run_id": run_id,
        "job_id": str(job.get("id", "")),
        "action": str(job.get("action", "")),
        "skill": skill_name,
        "result": result.to_dict(),
        "error": result.error,
    }
