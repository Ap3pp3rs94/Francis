from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from francis_core.clock import utc_now_iso
from francis_core.workspace_fs import WorkspaceFS
from francis_forge.proposal_engine import propose


def execute(
    job: dict[str, Any],
    *,
    run_id: str,
    fs: WorkspaceFS,
) -> dict[str, Any]:
    action = str(job.get("action", "")).strip().lower()
    if action != "forge.propose":
        return {
            "ok": False,
            "run_id": run_id,
            "job_id": str(job.get("id", "")),
            "action": action,
            "error": f"unsupported forge worker action: {action}",
        }

    context = job.get("context", {})
    if not isinstance(context, dict):
        context = {}

    proposals = propose(context)
    ts = utc_now_iso()
    report_name = f"worker_forge_{ts.replace(':', '-').replace('.', '-')}_{str(uuid4())[:8]}.json"
    rel_path = Path("forge") / "reports" / report_name
    fs.write_text(
        str(rel_path).replace("\\", "/"),
        json.dumps(
            {
                "ts": ts,
                "run_id": run_id,
                "job_id": str(job.get("id", "")),
                "action": action,
                "context": context,
                "proposals": proposals,
            },
            ensure_ascii=False,
            indent=2,
        ),
    )

    return {
        "ok": True,
        "run_id": run_id,
        "job_id": str(job.get("id", "")),
        "action": action,
        "proposal_count": len(proposals),
        "report_path": str(rel_path).replace("\\", "/"),
    }
