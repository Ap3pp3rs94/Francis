from __future__ import annotations

import json
import os
import secrets
import subprocess
import time
from pathlib import Path
from typing import Any

from francis.governance import approvals
from francis.kernel.paths import data_dir, repo_root


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _artifact_dir(run_id: str) -> Path:
    return data_dir() / "artifacts" / "supervised_exec" / run_id


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def _find_approval(approval_id: str) -> tuple[str, dict[str, Any] | None]:
    approval_id = _safe_str(approval_id).strip()
    if not approval_id:
        return "missing", None

    candidates: list[tuple[str, Path]] = [
        ("pending", approvals.pending_dir() / f"{approval_id}.json"),
        ("approved", approvals.approved_dir() / f"{approval_id}.json"),
        ("rejected", approvals.rejected_dir() / f"{approval_id}.json"),
        ("emergency", approvals.emergency_dir() / f"{approval_id}.json"),
    ]
    for status, path in candidates:
        if path.exists():
            try:
                obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
                return status, obj if isinstance(obj, dict) else None
            except Exception:
                return "corrupt", None

    return "missing", None


def _new_run_id() -> str:
    return f"run_{time.strftime('%Y%m%d_%H%M%S', time.gmtime())}_{secrets.token_hex(4)}"


def _normalize_cwd(cwd_raw: str) -> str:
    cwd_raw = _safe_str(cwd_raw).strip()
    if not cwd_raw:
        return str(repo_root())
    try:
        p = Path(cwd_raw)
        if not p.is_absolute():
            p = repo_root() / p
        p = p.resolve()
        return str(p)
    except Exception:
        return str(repo_root())


def run_supervised_exec(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    """Capability implementation for `codex.supervised_exec`.

    Contract:
    - If no approval is provided, create an approval request and return `status=needs_approval`.
    - If an approval_id is provided:
      - approved: execute the command and return `ok=True`, `status=success`.
      - pending: return `status=needs_approval`.
      - rejected/emergency: return `ok=False`, `status=denied`.

    This is intentionally conservative: no approval => no execution.
    """
    user_command = _safe_str(inputs.get("user_command")).strip()
    if not user_command:
        return {"kind": "supervised_exec.result", "ok": False, "status": "invalid", "error": "missing_user_command"}

    cwd = _normalize_cwd(_safe_str(inputs.get("cwd")))
    timeout_sec = int(inputs.get("timeout_sec") or 300)
    timeout_sec = max(1, min(timeout_sec, 24 * 3600))

    expected_artifacts = inputs.get("expected_artifacts")
    if not isinstance(expected_artifacts, list):
        expected_artifacts = []
    prechecks = inputs.get("prechecks")
    if not isinstance(prechecks, list):
        prechecks = []

    approval_id = _safe_str(inputs.get("approval_id")).strip()

    # 1) No approval_id => create an approval request.
    if not approval_id:
        req = approvals.request(
            action="codex.supervised_exec",
            reason="supervised_exec_requested",
            payload={
                "objective": _safe_str(objective),
                "user_command": user_command,
                "cwd": cwd,
                "timeout_sec": timeout_sec,
                "expected_artifacts": expected_artifacts,
                "prechecks": prechecks,
            },
        )
        approval_id = _safe_str(req.get("id")).strip() or _new_run_id()
        art = _artifact_dir(approval_id)
        _write_json(
            art / "request.json",
            {
                "kind": "supervised_exec.request",
                "approval": req,
                "objective": objective,
            },
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
        }

    # 2) approval_id provided => inspect status and proceed accordingly.
    status, record = _find_approval(approval_id)
    art = _artifact_dir(approval_id)
    if status in ("missing", "corrupt"):
        _write_json(
            art / "error.json",
            {"kind": "supervised_exec.error", "approval_id": approval_id, "status": status, "objective": objective},
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": "approval_not_found",
        }

    if status == "pending":
        _write_json(
            art / "pending.json",
            {"kind": "supervised_exec.pending", "approval": record, "objective": objective},
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
        }

    if status in ("rejected", "emergency"):
        _write_json(
            art / "denied.json",
            {"kind": "supervised_exec.denied", "approval": record, "objective": objective},
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "denied",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": f"approval_{status}",
        }

    if status != "approved":
        _write_json(
            art / "error.json",
            {"kind": "supervised_exec.error", "approval_id": approval_id, "status": status, "objective": objective},
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "denied",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": f"unknown_approval_status:{status}",
        }

    # 3) Approved => execute.
    art.mkdir(parents=True, exist_ok=True)
    _write_json(
        art / "plan.json",
        {
            "kind": "supervised_exec.plan",
            "approval_id": approval_id,
            "objective": objective,
            "user_command": user_command,
            "cwd": cwd,
            "timeout_sec": timeout_sec,
            "expected_artifacts": expected_artifacts,
            "prechecks": prechecks,
            "approval_record": record,
        },
    )

    t0 = time.time()
    try:
        # We execute the exact user-provided command string; on Windows this needs `shell=True`
        # to support built-ins like `echo`.
        proc = subprocess.run(
            user_command,
            shell=True,
            cwd=cwd,
            timeout=timeout_sec,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        dt = time.time() - t0
        (art / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
        (art / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
        _write_json(
            art / "result.json",
            {
                "kind": "supervised_exec.run_result",
                "approval_id": approval_id,
                "objective": objective,
                "cmd": user_command,
                "cwd": cwd,
                "timeout_sec": timeout_sec,
                "elapsed_sec": dt,
                "exit_code": int(proc.returncode),
            },
        )
        return {
            "kind": "supervised_exec.result",
            "ok": proc.returncode == 0,
            "status": "success" if proc.returncode == 0 else "error",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "exit_code": int(proc.returncode),
        }
    except subprocess.TimeoutExpired:
        dt = time.time() - t0
        _write_json(
            art / "result.json",
            {
                "kind": "supervised_exec.run_result",
                "approval_id": approval_id,
                "objective": objective,
                "cmd": user_command,
                "cwd": cwd,
                "timeout_sec": timeout_sec,
                "elapsed_sec": dt,
                "exit_code": None,
                "error": "timeout",
            },
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "timeout",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": "timeout",
        }
