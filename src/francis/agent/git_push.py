from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from francis.governance import approvals
from francis.kernel.paths import data_dir, repo_root


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value)
    except Exception:
        return ""


def _safe_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    text = _safe_str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "t", "yes", "y", "on"}


def _artifact_dir(run_id: str) -> Path:
    return data_dir() / "artifacts" / "git_push" / run_id


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
        if not path.exists():
            continue
        try:
            obj = json.loads(path.read_text(encoding="utf-8", errors="replace"))
            return status, obj if isinstance(obj, dict) else None
        except Exception:
            return "corrupt", None
    return "missing", None


def _normalize_cwd(cwd_raw: Any) -> Path:
    workspace_root = repo_root().resolve()
    text = _safe_str(cwd_raw).strip()
    if not text:
        return workspace_root
    candidate = Path(text)
    if not candidate.is_absolute():
        candidate = workspace_root / candidate
    try:
        resolved = candidate.resolve()
    except Exception:
        return workspace_root
    try:
        resolved.relative_to(workspace_root)
        return resolved
    except Exception:
        return workspace_root


def _git(args: list[str], *, cwd: Path, timeout_sec: int = 120) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=timeout_sec,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _git_text(args: list[str], *, cwd: Path, timeout_sec: int = 30) -> tuple[bool, str]:
    proc = _git(args, cwd=cwd, timeout_sec=timeout_sec)
    text = (proc.stdout or proc.stderr or "").strip()
    return proc.returncode == 0, text


def _approval_payload(
    *,
    objective: str,
    git_root: Path,
    remote: str,
    remote_url: str,
    branch: str,
    set_upstream: bool,
) -> dict[str, Any]:
    return {
        "objective": _safe_str(objective).strip(),
        "git_root": str(git_root),
        "remote": remote,
        "remote_url": remote_url,
        "branch": branch,
        "set_upstream": bool(set_upstream),
    }


def _request_approval(
    *,
    objective: str,
    request_payload: dict[str, Any],
    reason: str,
    previous_approval_id: str = "",
    previous_status: str = "",
    previous_record: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    req = approvals.request(
        action="git.push",
        reason=reason,
        payload=request_payload,
    )
    approval_id = _safe_str(req.get("id")).strip()
    art = _artifact_dir(approval_id)
    request_body: dict[str, Any] = {
        "kind": "git.push.request",
        "approval": req,
        "objective": objective,
        "request": request_payload,
    }
    if previous_approval_id:
        request_body["previous_approval_id"] = previous_approval_id
    if previous_status:
        request_body["previous_status"] = previous_status
    if isinstance(previous_record, dict):
        request_body["previous_approval"] = previous_record
    _write_json(art / "request.json", request_body)
    return approval_id, art


def _approval_matches_request(approval_record: dict[str, Any] | None, expected_payload: dict[str, Any]) -> bool:
    if not isinstance(approval_record, dict):
        return False

    approval_action = _safe_str(approval_record.get("action")).strip().lower()
    if approval_action and approval_action != "git.push":
        return False

    payload = approval_record.get("payload")
    if not isinstance(payload, dict):
        return False

    approved_payload = _approval_payload(
        objective=_safe_str(payload.get("objective")),
        git_root=Path(_safe_str(payload.get("git_root")) or expected_payload["git_root"]),
        remote=_safe_str(payload.get("remote")),
        remote_url=_safe_str(payload.get("remote_url")),
        branch=_safe_str(payload.get("branch")),
        set_upstream=bool(payload.get("set_upstream")),
    )
    return approved_payload == expected_payload


def run_git_push(inputs: dict[str, Any], objective: str) -> dict[str, Any]:
    git_exe = shutil.which("git")
    if not git_exe:
        return {"kind": "git.push.result", "ok": False, "status": "invalid", "error": "git_not_available"}

    cwd = _normalize_cwd(inputs.get("cwd"))
    remote = _safe_str(inputs.get("remote")).strip() or "origin"
    set_upstream = _safe_bool(inputs.get("set_upstream"), default=False)

    ok_root, git_root_text = _git_text(["rev-parse", "--show-toplevel"], cwd=cwd)
    if not ok_root or not git_root_text:
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "invalid",
            "error": "not_a_git_repository",
            "cwd": str(cwd),
        }
    git_root = Path(git_root_text).resolve()

    ok_branch, branch_text = _git_text(["rev-parse", "--abbrev-ref", "HEAD"], cwd=git_root)
    if not ok_branch or not branch_text:
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "invalid",
            "error": "branch_detection_failed",
            "git_root": str(git_root),
        }
    current_branch = branch_text.strip()
    if current_branch == "HEAD":
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "invalid",
            "error": "detached_head_not_supported",
            "git_root": str(git_root),
        }

    requested_branch = _safe_str(inputs.get("branch")).strip() or current_branch
    if requested_branch != current_branch:
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "invalid",
            "error": "branch_mismatch",
            "git_root": str(git_root),
            "branch": current_branch,
            "requested_branch": requested_branch,
        }

    ok_remote, remote_url = _git_text(["remote", "get-url", remote], cwd=git_root)
    if not ok_remote or not remote_url:
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "invalid",
            "error": "remote_not_found",
            "git_root": str(git_root),
            "remote": remote,
        }

    request_payload = _approval_payload(
        objective=objective,
        git_root=git_root,
        remote=remote,
        remote_url=remote_url,
        branch=current_branch,
        set_upstream=set_upstream,
    )
    approval_id = _safe_str(inputs.get("approval_id")).strip()

    if not approval_id:
        approval_id, art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="git_push_requested",
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "git_root": str(git_root),
            "remote": remote,
            "branch": current_branch,
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    status, record = _find_approval(approval_id)
    if status in {"missing", "corrupt"}:
        refreshed_approval_id, art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="git_push_requested",
            previous_approval_id=approval_id,
            previous_status=status,
            previous_record=record,
        )
        _write_json(
            art / "error.json",
            {
                "kind": "git.push.error",
                "approval_id": refreshed_approval_id,
                "previous_approval_id": approval_id,
                "status": status,
                "objective": objective,
            },
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": refreshed_approval_id,
            "run_id": refreshed_approval_id,
            "artifact_dir": str(art),
            "error": "approval_not_found",
            "previous_approval_id": approval_id,
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    art = _artifact_dir(approval_id)
    if status == "pending":
        _write_json(
            art / "pending.json",
            {"kind": "git.push.pending", "approval": record, "objective": objective},
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    if status in {"rejected", "emergency"}:
        _write_json(
            art / "denied.json",
            {"kind": "git.push.denied", "approval": record, "objective": objective},
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "denied",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": f"approval_{status}",
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    if status != "approved":
        _write_json(
            art / "error.json",
            {"kind": "git.push.error", "approval_id": approval_id, "status": status, "objective": objective},
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "denied",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "error": f"unknown_approval_status:{status}",
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    if not _approval_matches_request(record, request_payload):
        refreshed_approval_id, refreshed_art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="git_push_requested",
            previous_approval_id=approval_id,
            previous_status=status,
            previous_record=record,
        )
        _write_json(
            refreshed_art / "mismatch.json",
            {
                "kind": "git.push.mismatch",
                "approval_id": refreshed_approval_id,
                "previous_approval_id": approval_id,
                "objective": objective,
                "expected_payload": request_payload,
                "approval_record": record,
            },
        )
        _write_json(
            art / "mismatch.json",
            {
                "kind": "git.push.mismatch",
                "approval_id": approval_id,
                "objective": objective,
                "expected_payload": request_payload,
                "approval_record": record,
            },
        )
        return {
            "kind": "git.push.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": refreshed_approval_id,
            "run_id": refreshed_approval_id,
            "artifact_dir": str(refreshed_art),
            "error": "approval_payload_mismatch",
            "message": "Approval does not match this git push request.",
            "previous_approval_id": approval_id,
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    art.mkdir(parents=True, exist_ok=True)
    push_args = ["push"]
    if set_upstream:
        push_args.append("--set-upstream")
    push_args.extend([remote, current_branch])

    _write_json(
        art / "plan.json",
        {
            "kind": "git.push.plan",
            "approval_id": approval_id,
            "objective": objective,
            "git_root": str(git_root),
            "remote": remote,
            "remote_url": remote_url,
            "branch": current_branch,
            "set_upstream": set_upstream,
            "approval_record": record,
            "argv": ["git", *push_args],
        },
    )

    proc = _git(push_args, cwd=git_root, timeout_sec=120)
    (art / "stdout.txt").write_text(proc.stdout or "", encoding="utf-8")
    (art / "stderr.txt").write_text(proc.stderr or "", encoding="utf-8")
    _write_json(
        art / "result.json",
        {
            "kind": "git.push.run_result",
            "approval_id": approval_id,
            "objective": objective,
            "git_root": str(git_root),
            "remote": remote,
            "remote_url": remote_url,
            "branch": current_branch,
            "set_upstream": set_upstream,
            "exit_code": int(proc.returncode),
        },
    )
    return {
        "kind": "git.push.result",
        "ok": proc.returncode == 0,
        "status": "success" if proc.returncode == 0 else "error",
        "approval_id": approval_id,
        "run_id": approval_id,
        "artifact_dir": str(art),
        "git_root": str(git_root),
        "remote": remote,
        "remote_url": remote_url,
        "branch": current_branch,
        "set_upstream": set_upstream,
        "exit_code": int(proc.returncode),
    }
