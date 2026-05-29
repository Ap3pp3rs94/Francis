from __future__ import annotations

import json
import os
import re
import secrets
import shlex
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from francis.governance import approvals
from francis.governance.redaction import (
    redact_governed_display_value,
    redact_secret_text,
    seal_governed_approval_value,
)
from francis.kernel.paths import data_dir, repo_root

_SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,191}$")
_FORBIDDEN_COMMAND_TOKENS = (
    "\x00",
    "\n",
    "\r",
    "&&",
    "||",
    ";",
    "|",
    "<",
    ">",
    "`",
    "$(",
)
_ALLOWED_EXECUTABLES = {
    "echo",
    "mypy",
    "mypy.exe",
    "node",
    "node.exe",
    "npm",
    "npm.cmd",
    "npx",
    "npx.cmd",
    "py",
    "py.exe",
    "pytest",
    "pytest.exe",
    "python",
    "python.exe",
    "pwsh",
    "pwsh.exe",
    "ruff",
    "ruff.exe",
    "uv",
    "uv.exe",
}


def _safe_str(v: Any) -> str:
    if v is None:
        return ""
    try:
        return str(v)
    except Exception:
        return ""


def _real_path(value: str | Path) -> Path:
    return Path(os.path.realpath(os.fspath(value)))


def _path_is_under(root: Path, candidate: Path) -> bool:
    root = _real_path(root)
    candidate = _real_path(candidate)
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _safe_identifier(value: Any, *, fallback: str = "") -> str:
    text = _safe_str(value).strip()
    if _SAFE_ID_RE.fullmatch(text):
        return text
    return fallback


def _artifact_root() -> Path:
    return _real_path(data_dir() / "artifacts" / "supervised_exec")


def _artifact_dir(run_id: str) -> Path:
    root = _artifact_root()
    safe_run_id = _safe_identifier(run_id, fallback="invalid_run_id")
    candidate = _real_path(root / safe_run_id)
    if not _path_is_under(root, candidate):
        raise ValueError("artifact_path_outside_allowed_root")
    return candidate


def _artifact_path(path: Path) -> Path:
    root = _artifact_root()
    candidate = _real_path(path)
    if not _path_is_under(root, candidate):
        raise ValueError("artifact_path_outside_allowed_root")
    return candidate


def _ensure_artifact_dir(path: Path) -> Path:
    target = _artifact_path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def _display_safe_json_text(obj: Any) -> str:
    redacted = redact_governed_display_value(obj)
    return json.dumps(redacted, ensure_ascii=False, indent=2, default=str)


def _write_json(path: Path, obj: Any) -> None:
    target = _artifact_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(_display_safe_json_text(obj), encoding="utf-8")


def _write_redacted_text(path: Path, value: str) -> None:
    target = _artifact_path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(redact_secret_text(value or ""), encoding="utf-8")


def _find_approval(approval_id: str) -> tuple[str, dict[str, Any] | None]:
    approval_id = _safe_identifier(approval_id)
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


def _normalize_timeout_sec(value: Any) -> int:
    try:
        timeout_sec = int(value or 300)
    except Exception:
        timeout_sec = 300
    return max(1, min(timeout_sec, 24 * 3600))


def _normalize_cwd(cwd_raw: str) -> str:
    cwd_raw = _safe_str(cwd_raw).strip()
    if not cwd_raw:
        return str(_real_path(repo_root()))
    try:
        p = Path(cwd_raw)
        if not p.is_absolute():
            p = repo_root() / p
        p = _real_path(p)
        return str(p)
    except Exception:
        return str(_real_path(repo_root()))


def _allowed_cwd_roots() -> list[Path]:
    roots = [_real_path(repo_root()), _real_path(data_dir()).parent]
    unique: dict[str, Path] = {}
    for root in roots:
        unique[str(root).casefold()] = root
    return list(unique.values())


def _validated_cwd(cwd_raw: Any) -> tuple[str, str]:
    cwd = _real_path(_normalize_cwd(_safe_str(cwd_raw)))
    for root in _allowed_cwd_roots():
        if _path_is_under(root, cwd) or cwd == root:
            return str(cwd), ""
    return str(_real_path(repo_root())), "cwd_outside_allowed_root"


def _parse_command_args(user_command: str) -> tuple[list[str], str]:
    command = _safe_str(user_command).strip()
    if not command:
        return [], "missing_user_command"
    if any(token in command for token in _FORBIDDEN_COMMAND_TOKENS):
        return [], "unsupported_shell_syntax"
    try:
        args = shlex.split(command, posix=os.name != "nt")
    except ValueError:
        return [], "invalid_command_syntax"
    if not args:
        return [], "missing_user_command"

    executable = Path(args[0]).name.lower()
    if executable not in _ALLOWED_EXECUTABLES:
        return [], "unsupported_command"

    if executable == "echo":
        return [
            sys.executable,
            "-c",
            "import sys; print(' '.join(sys.argv[1:]))",
            *args[1:],
        ], ""

    return args, ""


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _safe_str(item).strip()
        if text:
            out.append(text)
    return out


def _approval_payload(
    *,
    objective: str,
    user_command: str,
    cwd: str,
    timeout_sec: int,
    expected_artifacts: list[str],
    prechecks: list[str],
) -> dict[str, Any]:
    return {
        "objective": _safe_str(objective),
        "user_command": _safe_str(user_command),
        "cwd": _normalize_cwd(cwd),
        "timeout_sec": _normalize_timeout_sec(timeout_sec),
        "expected_artifacts": _normalize_string_list(expected_artifacts),
        "prechecks": _normalize_string_list(prechecks),
    }


def _approval_contract_payload(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": seal_governed_approval_value(payload.get("objective"), key="objective"),
        "user_command": seal_governed_approval_value(payload.get("user_command"), key="user_command"),
        "cwd": seal_governed_approval_value(payload.get("cwd"), key="cwd"),
        "timeout_sec": _normalize_timeout_sec(payload.get("timeout_sec")),
        "expected_artifacts": seal_governed_approval_value(
            _normalize_string_list(payload.get("expected_artifacts")),
            key="expected_artifacts",
        ),
        "prechecks": seal_governed_approval_value(_normalize_string_list(payload.get("prechecks")), key="prechecks"),
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
        action="codex.supervised_exec",
        reason=reason,
        payload=request_payload,
    )
    approval_id = _safe_str(req.get("id")).strip() or _new_run_id()
    art = _artifact_dir(approval_id)
    request_body: dict[str, Any] = {
        "kind": "supervised_exec.request",
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
    if approval_action and approval_action != "codex.supervised_exec":
        return False

    payload = approval_record.get("payload")
    if not isinstance(payload, dict):
        return False

    return payload == expected_payload


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

    cwd, cwd_error = _validated_cwd(inputs.get("cwd"))
    if cwd_error:
        return {"kind": "supervised_exec.result", "ok": False, "status": "invalid", "error": cwd_error}
    command_args, command_error = _parse_command_args(user_command)
    if command_error:
        return {"kind": "supervised_exec.result", "ok": False, "status": "invalid", "error": command_error}
    timeout_sec = _normalize_timeout_sec(inputs.get("timeout_sec"))
    expected_artifacts = _normalize_string_list(inputs.get("expected_artifacts"))
    prechecks = _normalize_string_list(inputs.get("prechecks"))
    raw_request_payload = _approval_payload(
        objective=_safe_str(objective),
        user_command=user_command,
        cwd=cwd,
        timeout_sec=timeout_sec,
        expected_artifacts=expected_artifacts,
        prechecks=prechecks,
    )
    request_payload = _approval_contract_payload(raw_request_payload)

    approval_id = _safe_identifier(inputs.get("approval_id"))
    if _safe_str(inputs.get("approval_id")).strip() and not approval_id:
        return {"kind": "supervised_exec.result", "ok": False, "status": "invalid", "error": "invalid_approval_id"}

    # 1) No approval_id => create an approval request.
    if not approval_id:
        approval_id, art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="supervised_exec_requested",
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    # 2) approval_id provided => inspect status and proceed accordingly.
    status, record = _find_approval(approval_id)
    if status in ("missing", "corrupt"):
        refreshed_approval_id, art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="supervised_exec_requested",
            previous_approval_id=approval_id,
            previous_status=status,
            previous_record=record,
        )
        _write_json(
            art / "error.json",
            {
                "kind": "supervised_exec.error",
                "approval_id": refreshed_approval_id,
                "previous_approval_id": approval_id,
                "status": status,
                "objective": objective,
            },
        )
        return {
            "kind": "supervised_exec.result",
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
            {"kind": "supervised_exec.pending", "approval": record, "objective": objective},
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": approval_id,
            "run_id": approval_id,
            "artifact_dir": str(art),
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
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
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
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
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    if not _approval_matches_request(record, request_payload):
        refreshed_approval_id, refreshed_art = _request_approval(
            objective=objective,
            request_payload=request_payload,
            reason="supervised_exec_requested",
            previous_approval_id=approval_id,
            previous_status=status,
            previous_record=record,
        )
        _write_json(
            refreshed_art / "mismatch.json",
            {
                "kind": "supervised_exec.mismatch",
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
                "kind": "supervised_exec.mismatch",
                "approval_id": approval_id,
                "objective": objective,
                "expected_payload": request_payload,
                "approval_record": record,
            },
        )
        return {
            "kind": "supervised_exec.result",
            "ok": False,
            "status": "needs_approval",
            "approval_id": refreshed_approval_id,
            "run_id": refreshed_approval_id,
            "artifact_dir": str(refreshed_art),
            "error": "approval_payload_mismatch",
            "message": "Approval does not match this supervised execution request.",
            "previous_approval_id": approval_id,
            "governance": {"gate": "approvals_gate", "next_step": "approve_exact_action"},
        }

    # 3) Approved => execute.
    _ensure_artifact_dir(art)
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
        proc = subprocess.run(
            command_args,
            shell=False,
            cwd=cwd,
            timeout=timeout_sec,
            capture_output=True,
            text=True,
            env=os.environ.copy(),
        )
        dt = time.time() - t0
        _write_redacted_text(art / "stdout.txt", proc.stdout or "")
        _write_redacted_text(art / "stderr.txt", proc.stderr or "")
        _write_json(
            art / "result.json",
            {
                "kind": "supervised_exec.run_result",
                "approval_id": approval_id,
                "objective": objective,
                "cmd": user_command,
                "argv": command_args,
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
