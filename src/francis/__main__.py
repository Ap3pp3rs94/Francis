from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from pathlib import Path
from typing import Any

from francis.kernel.paths import repo_root

logger = logging.getLogger(__name__)
DEFAULT_TIMEOUT_SEC = 300


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s", stream=sys.stderr)


def _sanitize_decision_field(value: Any, default: str) -> str:
    if value is None:
        return default
    text = str(value).strip()
    if not text:
        return default
    text = text.replace('"', "'")
    lines = text.splitlines()
    text = " ".join(line.strip() for line in lines if line.strip())
    return text or default


def _print_decision_line(task: dict[str, Any] | None, *, reason_override: str | None = None) -> None:
    verdict = "DENY"
    reason = reason_override or "denied"
    artifact = ""
    if task:
        result = task.get("result") or {}
        ok = bool(result.get("ok"))
        verdict = "ALLOW" if task.get("status") == "complete" and ok else "DENY"
        if not reason_override:
            reason = (
                task.get("status_reason")
                or (result.get("data") or {}).get("status")
                or ("success" if verdict == "ALLOW" else "denied")
            )
        data = result.get("data")
        if isinstance(data, dict):
            artifact = data.get("run_id") or data.get("artifact_dir") or (data.get("plan") or {}).get("id", "")
        if not artifact:
            artifact = task.get("task_id") or ""
    reason = _sanitize_decision_field(reason, "unknown")
    artifact = _sanitize_decision_field(artifact, "")
    print(f'DECISION: {verdict} reason="{reason}" artifact="{artifact}"', file=sys.stderr)


def _run(cmd: list[str]) -> int:
    logger.info("Running: %s", " ".join(cmd))
    try:
        return int(subprocess.run(cmd).returncode)
    except OSError as exc:
        logger.error("Command failed: %s", exc)
        return 1


def _existing_paths(root: Path) -> list[Path]:
    candidates = [root / "src", root / "connectors", root / "specializations", root / "tools"]
    return [path for path in candidates if path.exists()]


def cmd_healthcheck() -> int:
    """Run compile and tests if available."""
    py = sys.executable
    repo = repo_root()
    paths = _existing_paths(repo)

    if paths:
        rc = _run([py, "-m", "compileall", "-q", *map(str, paths)])
        if rc != 0:
            return rc
    else:
        logger.warning("No compile paths found under %s", repo)

    try:
        import pytest  # noqa: F401
    except ImportError:
        logger.warning("pytest not installed; skipping tests")
        return 0

    rc = _run([py, "-m", "pytest", "-q"])
    if rc != 0:
        return rc

    compilefails = len(list(repo.rglob("*.bak_compilefail_*")))
    stubs = len(list(repo.rglob("*.bak_stub_*")))
    logger.info("Backups: compilefail=%s stub=%s", compilefails, stubs)
    return 0


def cmd_supervised_exec(args: argparse.Namespace) -> int:
    from francis.agent.delegation import DelegationRequest, create_delegation
    from francis.agent.executor import execute_task

    user_command = args.user_command
    if isinstance(user_command, list):
        if user_command and user_command[0] == "--":
            user_command = user_command[1:]
        user_command = " ".join([str(item) for item in user_command]).strip()
    if not isinstance(user_command, str) or not user_command:
        logger.error("Missing --cmd")
        return 2

    cmd_hash = hashlib.sha256(user_command.encode("utf-8", errors="ignore")).hexdigest()[:12]
    inputs: dict[str, object] = {
        "user_command": user_command,
        "cwd": args.cwd,
        "timeout_sec": args.timeout_sec,
        "expected_artifacts": args.expected_artifact,
        "prechecks": args.precheck,
    }
    if args.approval_id:
        inputs["approval_id"] = args.approval_id

    record, err = create_delegation(
        DelegationRequest(
            requester_id="cli",
            capability="codex.supervised_exec",
            objective=f"supervised_exec:{cmd_hash}",
            inputs={k: v for k, v in inputs.items() if v is not None},
            priority=5,
            ttl_sec=args.ttl_sec,
        )
    )
    if not record:
        logger.error("Create failed: %s", err)
        _print_decision_line(None, reason_override=err or "create_failed")
        return 1

    task = execute_task(task_id=record.task_id, worker_id="supervised_exec")
    print(json.dumps(task, indent=2, ensure_ascii=False, default=str))
    _print_decision_line(task)
    if bool(getattr(args, "print_summary", False)):
        _print_supervised_exec_summary(task)
    if task.get("status") == "complete":
        return 0
    if task.get("result", {}).get("data", {}).get("status") == "needs_approval":
        return 2
    return 1


def _print_supervised_exec_summary(task: dict[str, Any] | None) -> None:
    """Emit a brief human-readable summary to stderr (stdout remains JSON)."""
    if not isinstance(task, dict):
        return

    result = task.get("result") or {}
    ok = bool(result.get("ok"))
    status = _sanitize_decision_field(task.get("status"), "unknown")
    reason = _sanitize_decision_field(task.get("status_reason"), "")
    task_id = _sanitize_decision_field(task.get("task_id"), "")

    data = result.get("data")
    approval_id = ""
    trace_id = ""
    run_id = ""
    artifact_dir = ""
    if isinstance(data, dict):
        approval_id = _sanitize_decision_field(data.get("approval_id"), "")
        trace_id = _sanitize_decision_field(data.get("trace_id") or data.get("traceId"), "")
        run_id = _sanitize_decision_field(data.get("run_id"), "")
        artifact_dir = _sanitize_decision_field(data.get("artifact_dir"), "")

    print(f"SUMMARY: task_id={task_id or '-'} status={status} ok={ok}", file=sys.stderr)
    if reason:
        print(f"SUMMARY: reason={reason}", file=sys.stderr)
    if approval_id:
        print(f"SUMMARY: approval_id={approval_id}", file=sys.stderr)
    if trace_id:
        print(f"SUMMARY: trace_id={trace_id}", file=sys.stderr)
    if run_id:
        print(f"SUMMARY: run_id={run_id}", file=sys.stderr)
    if artifact_dir:
        print(f"SUMMARY: artifact_dir={artifact_dir}", file=sys.stderr)


def cmd_doctor(_args: argparse.Namespace) -> int:
    from francis.cli import doctor

    return int(doctor())


def cmd_api(args: argparse.Namespace) -> int:
    from francis.cli import api

    return int(api(host=args.host, port=args.port))


def cmd_daemon(_args: argparse.Namespace) -> int:
    from francis.cli import daemon

    return int(daemon())


def cmd_stage3_readiness_proof(args: argparse.Namespace) -> int:
    from francis.missions.readiness_proof import run_stage3_readiness_proof

    result = run_stage3_readiness_proof(
        actor=args.actor,
        confirm=bool(args.confirm),
        force=bool(args.force),
        deadletter_reason=args.deadletter_reason,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    if result.get("ok") is True:
        return 0
    if result.get("error") == "confirmation_required":
        return 2
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="francis", description="FRANCIS - autonomous digital colleague")
    parser.add_argument("-v", "--verbose", action="store_true", help="Verbose logging")

    sub = parser.add_subparsers(dest="cmd", required=False)
    sub.add_parser("healthcheck", help="Compile + run unit tests")

    p_doctor = sub.add_parser("doctor", help="Lightweight health report")
    p_doctor.set_defaults(fn=cmd_doctor)

    p_api = sub.add_parser("api", help="Run the API server (requires web dependencies)")
    p_api.add_argument("--host", default="127.0.0.1")
    p_api.add_argument("--port", type=int, default=8000)
    p_api.set_defaults(fn=cmd_api)

    p_daemon = sub.add_parser("daemon", help="Run the daemon loop")
    p_daemon.set_defaults(fn=cmd_daemon)

    p_stage3 = sub.add_parser(
        "stage3-readiness-proof",
        help="Create bounded proof missions and report Stage 3 readiness",
    )
    p_stage3.add_argument("--actor", default="operator.stage3.readiness")
    p_stage3.add_argument(
        "--confirm",
        action="store_true",
        help="Required; creates proof missions in the configured Francis data directory.",
    )
    p_stage3.add_argument(
        "--force",
        action="store_true",
        help="Create fresh proof missions even when Stage 3 readiness is already satisfied.",
    )
    p_stage3.add_argument("--deadletter-reason", default="stage3_readiness_proof_deadletter")
    p_stage3.set_defaults(fn=cmd_stage3_readiness_proof)

    p_supervised = sub.add_parser("supervised-exec", help="Run a supervised command execution plan")
    p_supervised.add_argument(
        "--cmd",
        required=True,
        type=str,
        dest="user_command",
        help="Exact user-provided command to execute",
    )
    p_supervised.add_argument("--cwd", default="", help="Working directory (default: repo root)")
    p_supervised.add_argument("--timeout-sec", type=int, default=DEFAULT_TIMEOUT_SEC)
    p_supervised.add_argument("--ttl-sec", type=int, default=3600)
    p_supervised.add_argument("--approval-id", default="")
    p_supervised.add_argument("--expected-artifact", action="append", default=None)
    p_supervised.add_argument("--precheck", action="append", default=None)
    p_supervised.add_argument(
        "--print-summary",
        action="store_true",
        help="Emit a brief human-readable summary to stderr (stdout remains JSON).",
    )
    p_supervised.set_defaults(fn=cmd_supervised_exec)

    args = parser.parse_args(argv)
    _configure_logging(args.verbose)

    if getattr(args, "fn", None) is not None:
        return int(args.fn(args))

    if args.cmd == "healthcheck":
        return cmd_healthcheck()

    logger.info("FRANCIS CLI is online (minimal mode).")
    logger.info("Try: python -m francis doctor")
    logger.info("Try: python -m francis healthcheck")
    logger.info("API: python -m francis api")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
