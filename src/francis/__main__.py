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


def cmd_communication(args: argparse.Namespace) -> int:
    from francis.developer_bridge.collaboration_log import main as collaboration_log_main

    relay_args: list[str] = ["--limit", str(args.limit), "--poll-seconds", str(args.poll_seconds)]
    for attr, flag in (
        ("agent", "--agent"),
        ("source_agent", "--source-agent"),
        ("target_agent", "--target-agent"),
        ("status", "--status"),
    ):
        value = str(getattr(args, attr, "") or "")
        if value:
            relay_args.extend([flag, value])
    if bool(getattr(args, "json", False)):
        relay_args.append("--json")
    if bool(getattr(args, "brief", False)):
        relay_args.append("--brief")
    if bool(getattr(args, "hide_auto_acks", False)):
        relay_args.append("--hide-auto-acks")
    if bool(getattr(args, "watch", False)):
        relay_args.append("--watch")
    if bool(getattr(args, "new_only", False)):
        relay_args.append("--new-only")
    return int(collaboration_log_main(relay_args))


def cmd_communication_runtime(args: argparse.Namespace) -> int:
    from francis.developer_bridge.collaboration_runtime import main as collaboration_runtime_main

    runtime_args: list[str] = ["--poll-seconds", str(args.poll_seconds)]
    if bool(getattr(args, "watch", False)):
        runtime_args.append("--watch")
    if bool(getattr(args, "quiet", False)):
        runtime_args.append("--quiet")
    return int(collaboration_runtime_main(runtime_args))


def cmd_overnight_explore(args: argparse.Namespace) -> int:
    from francis.exploration.overnight import main as overnight_main

    explorer_args: list[str] = [
        "--duration-hours",
        str(args.duration_hours),
        "--interval-minutes",
        str(args.interval_minutes),
        "--max-findings",
        str(args.max_findings),
        "--max-scan-files",
        str(args.max_scan_files),
        "--actor",
        str(args.actor),
    ]
    if str(args.repo_root or ""):
        explorer_args.extend(["--repo-root", str(args.repo_root)])
    if str(args.data_dir or ""):
        explorer_args.extend(["--data-dir", str(args.data_dir)])
    if bool(getattr(args, "once", False)):
        explorer_args.append("--once")
    if bool(getattr(args, "status", False)):
        explorer_args.append("--status")
    if bool(getattr(args, "stop", False)):
        explorer_args.append("--stop")
    if bool(getattr(args, "clear_stop_flag", False)):
        explorer_args.append("--clear-stop-flag")
    return int(overnight_main(explorer_args))


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


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))


def cmd_ingest_add(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().add_source(args.path, actor=args.actor)
    except Exception as exc:
        logger.error("Ingest add failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_repo_inspect(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().inspect_repo(args.path_or_source, actor=args.actor)
    except Exception as exc:
        logger.error("Repo inspect failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_capability_candidates(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().extract_candidates(args.source_or_path, actor=args.actor)
    except Exception as exc:
        logger.error("Capability candidate extraction failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def _read_proposal_text(args: argparse.Namespace) -> str:
    """Read the full proposal text from --proposal-file (digest-gated downstream)."""
    path = getattr(args, "proposal_file", "") or ""
    if not path:
        return ""
    try:
        from pathlib import Path

        return Path(path).read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        logger.error("Could not read proposal file %s: %s", path, exc)
        return ""


def cmd_forge_synthesize(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().synthesize_capability(
            args.source_or_path, getattr(args, "candidate", "") or "", actor=args.actor
        )
    except Exception as exc:
        logger.error("Forge synthesize failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_forge_continue(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().continue_synthesis_after_approval(args.run_id, actor=args.actor)
    except Exception as exc:
        logger.error("Forge continue failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_forge_review(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().review_builder_proposal(
            args.source_or_path, args.builder_run_id, _read_proposal_text(args), actor=args.actor
        )
    except Exception as exc:
        logger.error("Forge review failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_forge_dryrun(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().dryrun_forge_apply(
            args.source_or_path, args.builder_run_id, args.approval_id, _read_proposal_text(args), actor=args.actor
        )
    except Exception as exc:
        logger.error("Forge dry-run failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_forge_bind(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().bind_synthesized_source(args.source_or_path, args.builder_run_id, actor=args.actor)
    except Exception as exc:
        logger.error("Forge bind failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_acquire(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().acquire_source_candidate(
            args.source_or_path,
            getattr(args, "candidate", "") or "",
            opt_in=bool(getattr(args, "opt_in", False)),
            actor=args.actor,
            lab_image=getattr(args, "lab_image", "") or "",
        )
    except Exception as exc:
        logger.error("Acquire failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_acquire_continue(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().continue_acquisition_after_approval(args.run_id, actor=args.actor)
    except Exception as exc:
        logger.error("Acquire continue failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_plan(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().plan_lab(args.source_or_path, args.candidate, actor=args.actor)
    except Exception as exc:
        logger.error("Lab plan failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_run(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().run_lab_capability(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            opt_in=bool(args.opt_in),
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab run failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_prepare(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().prepare_lab_workspace(args.source_or_path, args.candidate, actor=args.actor)
    except Exception as exc:
        logger.error("Lab workspace prepare failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_preflight(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_execution(args.source_or_path, args.candidate, actor=args.actor)
    except Exception as exc:
        logger.error("Lab execution preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_request_approval(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().request_lab_execution_approval(
            args.source_or_path,
            args.candidate,
            actor=args.actor,
            reason=args.reason,
        )
    except Exception as exc:
        logger.error("Lab approval request failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_approval_consumption_preflight(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_approval_consumption(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab approval consumption preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_readiness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_readiness(
            args.source_or_path,
            args.candidate,
            approval_id=args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner readiness preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_binding(
            args.source_or_path,
            args.candidate,
            approval_id=args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner binding preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_enforcement(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_enforcement(
            args.source_or_path,
            args.candidate,
            approval_id=args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner enforcement preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_approval_consumption_handoff(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_approval_consumption_handoff(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab approval consumption handoff preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_execution_receipt_sink_reservation(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_execution_receipt_sink_reservation(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab execution receipt sink reservation failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_command_allowlist_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner command allowlist binding failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_command_allowlist_declaration(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_declaration(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner command allowlist declaration failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_command_allowlist_enforcement(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_command_allowlist_enforcement(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner command allowlist enforcement preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_runner_sandbox_readiness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_runner_sandbox_readiness(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab runner sandbox readiness preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_contract(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_contract(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider contract preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider binding preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_selection(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_selection(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider selection preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_verifier(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_verifier(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider verifier preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_harness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_harness(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe harness preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_runner_readiness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_readiness(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe runner readiness failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_runner_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe runner binding preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_runner_enforcement(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_enforcement(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe runner enforcement preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_execution_receipt_write_readiness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_execution_receipt_write_readiness(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab execution receipt write readiness preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_execution_receipt_prewrite_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_execution_receipt_prewrite_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab execution receipt prewrite binding preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_execution_receipt_writer_preflight(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_execution_receipt_writer(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab execution receipt writer preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_synthetic_execution_receipt_prewrite(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().prewrite_lab_synthetic_execution_receipt(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab synthetic execution receipt prewrite failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_synthetic_execution_receipt_finalize(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().finalize_lab_synthetic_execution_receipt(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab synthetic execution receipt finalize failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_approval_consume_synthetic_noop(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().consume_lab_approval_for_synthetic_execution_receipt(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab synthetic no-op approval consumption failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_noop_runner_envelope(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().run_lab_noop_runner_envelope(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab no-op runner envelope failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_noop_runner_transcript(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().capture_lab_noop_runner_transcript(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab no-op runner transcript failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_noop_runner_identity_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().bind_lab_noop_runner_identity(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab no-op runner identity binding failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_source_mount_readiness(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_source_mount_readiness(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab source mount readiness failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_source_mount_contract(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_source_mount_contract(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab source mount contract failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_run_boundary_preflight(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_run_boundary(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab run-boundary preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_execution_boundary(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_execution_boundary(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe execution boundary failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_refuse(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().refuse_lab_sandbox_provider_runtime_probe(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
            reason=args.reason,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe refusal failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_request_approval(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().request_lab_sandbox_provider_runtime_probe_approval(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
            reason=args.reason,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe approval request failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_consume_approval(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().consume_lab_sandbox_provider_runtime_probe_approval(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe approval consumption failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_invocation_boundary(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_invocation_boundary(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe invocation boundary failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe runner pre-execution boundary failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandbox_provider_runtime_probe_runner_control_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandbox_provider_runtime_probe_runner_control_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandbox provider runtime probe runner control binding failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandboxed_rebuild_run_test_boundary(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_boundary(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandboxed rebuild/run/test boundary failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandboxed_rebuild_run_test_request_approval(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().request_lab_sandboxed_rebuild_run_test_approval(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
            reason=args.reason,
        )
    except Exception as exc:
        logger.error("Lab sandboxed rebuild/run/test approval request failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandboxed_rebuild_run_test_consume_approval(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().consume_lab_sandboxed_rebuild_run_test_approval(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandboxed rebuild/run/test approval consumption failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandboxed_rebuild_run_test_runner_binding(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_runner_binding(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            provider_kind=args.provider_kind,
            provider_reference=args.provider_reference,
            provider_policy_manifest=args.provider_policy_manifest,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandboxed rebuild/run/test runner binding preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_sandboxed_rebuild_run_test_sandbox_policy(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().preflight_lab_sandboxed_rebuild_run_test_sandbox_policy(
            args.source_or_path,
            args.candidate,
            args.approval_id,
            actor=args.actor,
        )
    except Exception as exc:
        logger.error("Lab sandboxed rebuild/run/test sandbox policy preflight failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


def cmd_lab_execute(args: argparse.Namespace) -> int:
    from francis.ingest import IngestService

    try:
        result = IngestService().refuse_lab_execution(
            args.source_or_path,
            args.candidate,
            actor=args.actor,
            reason=args.reason,
        )
    except Exception as exc:
        logger.error("Lab execution boundary failed: %s", exc)
        result = {"ok": False, "status": "failed", "error": str(exc)}
    _print_json(result)
    return 0 if result.get("ok") is True else 1


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

    p_communication = sub.add_parser(
        "communication",
        aliases=["Communication"],
        help="Read or follow the developer bridge collaboration relay transcript",
    )
    p_communication.add_argument("--agent", default="", help="Filter to relay entries involving this agent.")
    p_communication.add_argument("--source-agent", default="", help="Filter to relay entries from this agent.")
    p_communication.add_argument("--target-agent", default="", help="Filter to relay entries for this agent.")
    p_communication.add_argument(
        "--status",
        default="",
        choices=["", "queued", "acknowledged", "delivered", "blocked", "closed"],
        help="Filter by relay status. Empty means all statuses.",
    )
    p_communication.add_argument(
        "--limit", type=int, default=20, help="Maximum relay entries to display, capped at 50."
    )
    p_communication.add_argument("--json", action="store_true", help="Print the bounded transcript payload as JSON.")
    p_communication.add_argument("--brief", action="store_true", help="Print only the operator-facing messages.")
    p_communication.add_argument(
        "--hide-auto-acks", action="store_true", help="Hide generic Codex auto-ack relay entries."
    )
    p_communication.add_argument("--watch", action="store_true", help="Poll and print the transcript repeatedly.")
    p_communication.add_argument(
        "--new-only",
        action="store_true",
        help="With --watch, print only relay entries created after the watcher starts.",
    )
    p_communication.add_argument("--poll-seconds", type=float, default=15.0, help="Polling interval for --watch.")
    p_communication.set_defaults(fn=cmd_communication)

    p_communication_runtime = sub.add_parser(
        "communication-runtime",
        aliases=["CommunicationRuntime"],
        help="Keep the bounded developer bridge Codex/Ollama collaboration helpers alive",
    )
    p_communication_runtime.add_argument(
        "--watch",
        action="store_true",
        help="Continuously ensure the Codex/Ollama collaboration helpers are alive.",
    )
    p_communication_runtime.add_argument(
        "--poll-seconds", type=float, default=10.0, help="Supervisor polling interval for --watch."
    )
    p_communication_runtime.add_argument(
        "--quiet", action="store_true", help="Write supervisor receipts without printing each check."
    )
    p_communication_runtime.set_defaults(fn=cmd_communication_runtime)

    p_overnight = sub.add_parser(
        "overnight-explore",
        help="Run the bounded read-only overnight substrate explorer",
    )
    p_overnight.add_argument("--repo-root", default="", help="Repo root to explore. Defaults to detected Francis root.")
    p_overnight.add_argument("--data-dir", default="", help="Data root for explorer receipts.")
    p_overnight.add_argument("--actor", default="francis.overnight_explorer", help="Actor recorded in receipts.")
    p_overnight.add_argument("--duration-hours", type=float, default=8.0)
    p_overnight.add_argument("--interval-minutes", type=float, default=20.0)
    p_overnight.add_argument("--max-findings", type=int, default=40)
    p_overnight.add_argument("--max-scan-files", type=int, default=900)
    p_overnight.add_argument("--once", action="store_true", help="Run one read-only cycle and exit.")
    p_overnight.add_argument("--status", action="store_true", help="Print latest explorer status.")
    p_overnight.add_argument("--stop", action="store_true", help="Request a running explorer to stop.")
    p_overnight.add_argument("--clear-stop-flag", action="store_true", help="Remove a stale stop flag before running.")
    p_overnight.set_defaults(fn=cmd_overnight_explore)

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

    p_ingest = sub.add_parser("ingest", help="Source ingestion and source-registry operations")
    ingest_sub = p_ingest.add_subparsers(dest="ingest_cmd", required=True)
    p_ingest_add = ingest_sub.add_parser("add", help="Add a local file, folder, or repo source")
    p_ingest_add.add_argument("path", help="Local source path to inspect without executing")
    p_ingest_add.add_argument("--actor", default="francis/system", help="Actor recorded in ingest receipts")
    p_ingest_add.set_defaults(fn=cmd_ingest_add)

    p_repo = sub.add_parser("repo", help="Read-only repository inspection")
    repo_sub = p_repo.add_subparsers(dest="repo_cmd", required=True)
    p_repo_inspect = repo_sub.add_parser("inspect", help="Inspect a local repo path or source id")
    p_repo_inspect.add_argument("path_or_source", help="Local repo path or source id")
    p_repo_inspect.add_argument("--actor", default="francis/system", help="Actor recorded in ingest receipts")
    p_repo_inspect.set_defaults(fn=cmd_repo_inspect)

    p_capability = sub.add_parser("capability", help="Capability candidate operations")
    capability_sub = p_capability.add_subparsers(dest="capability_cmd", required=True)
    p_capability_candidates = capability_sub.add_parser(
        "candidates",
        help="Draft capability candidates from an indexed repo source or local repo path",
    )
    p_capability_candidates.add_argument("source_or_path", help="Source id or local repo path")
    p_capability_candidates.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_capability_candidates.set_defaults(fn=cmd_capability_candidates)

    p_acquire = sub.add_parser("acquire", help="Drive the governed ingest acquisition corridor (Lab)")
    acquire_sub = p_acquire.add_subparsers(dest="acquire_cmd", required=True)
    p_acquire_start = acquire_sub.add_parser("start", help="Push a candidate to the first Lab approval gate")
    p_acquire_start.add_argument("source_or_path", help="Source id or local repo path")
    p_acquire_start.add_argument("--candidate", default="", help="Candidate id or name (default: inspect)")
    p_acquire_start.add_argument("--opt-in", dest="opt_in", action="store_true", help="Operator opt-in for real Lab")
    p_acquire_start.add_argument("--lab-image", dest="lab_image", default="", help="Pinned Lab image override")
    p_acquire_start.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_acquire_start.set_defaults(fn=cmd_acquire)
    p_acquire_continue = acquire_sub.add_parser("continue", help="Resume a paused acquisition after approval")
    p_acquire_continue.add_argument("run_id", help="Acquisition run id")
    p_acquire_continue.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_acquire_continue.set_defaults(fn=cmd_acquire_continue)

    p_forge = sub.add_parser("forge", help="Governed Forge synthesis corridor (review/apply-to-scratch, non-applying)")
    forge_sub = p_forge.add_subparsers(dest="forge_cmd", required=True)
    p_forge_synth = forge_sub.add_parser(
        "synthesize", help="Push a candidate through native synthesis to the apply gate"
    )
    p_forge_synth.add_argument("source_or_path", help="Source id or local repo path")
    p_forge_synth.add_argument("--candidate", default="", help="Candidate id or name (default: inspect)")
    p_forge_synth.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_forge_synth.set_defaults(fn=cmd_forge_synthesize)
    p_forge_continue = forge_sub.add_parser("continue", help="Resume a paused synthesis after the apply approval")
    p_forge_continue.add_argument("run_id", help="Synthesis run id")
    p_forge_continue.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_forge_continue.set_defaults(fn=cmd_forge_continue)
    p_forge_review = forge_sub.add_parser("review", help="Digest-gated review of a builder proposal (non-applying)")
    p_forge_review.add_argument("source_or_path", help="Source id or local repo path")
    p_forge_review.add_argument("builder_run_id", help="Builder run id")
    p_forge_review.add_argument(
        "--proposal-file", dest="proposal_file", default="", help="File with full proposal text"
    )
    p_forge_review.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_forge_review.set_defaults(fn=cmd_forge_review)
    p_forge_dryrun = forge_sub.add_parser("dryrun", help="Apply an approved proposal to an isolated scratch copy")
    p_forge_dryrun.add_argument("source_or_path", help="Source id or local repo path")
    p_forge_dryrun.add_argument("builder_run_id", help="Builder run id")
    p_forge_dryrun.add_argument("approval_id", help="Consumed francis.forge.apply approval id")
    p_forge_dryrun.add_argument(
        "--proposal-file", dest="proposal_file", default="", help="File with full proposal text"
    )
    p_forge_dryrun.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_forge_dryrun.set_defaults(fn=cmd_forge_dryrun)
    p_forge_bind = forge_sub.add_parser("bind", help="Register the synthesized scratch tree as a new ingest source")
    p_forge_bind.add_argument("source_or_path", help="Origin source id or local repo path")
    p_forge_bind.add_argument("builder_run_id", help="Builder run id")
    p_forge_bind.add_argument("--actor", default="francis/system", help="Actor recorded in receipts")
    p_forge_bind.set_defaults(fn=cmd_forge_bind)

    p_lab = sub.add_parser("lab", help="Francis Lab planning and execution-boundary operations")
    lab_sub = p_lab.add_subparsers(dest="lab_cmd", required=True)
    p_lab_plan = lab_sub.add_parser(
        "plan",
        help="Create a non-executing lab plan for a capability candidate",
    )
    p_lab_plan.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_plan.add_argument("candidate", help="Capability candidate id or name")
    p_lab_plan.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_plan.set_defaults(fn=cmd_lab_plan)

    p_lab_prepare = lab_sub.add_parser(
        "prepare",
        help="Prepare a non-executing Francis-owned lab workspace for a candidate",
    )
    p_lab_prepare.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_prepare.add_argument("candidate", help="Capability candidate id or name")
    p_lab_prepare.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_prepare.set_defaults(fn=cmd_lab_prepare)

    p_lab_preflight = lab_sub.add_parser(
        "preflight",
        help="Create a non-executing lab execution readiness preflight for a candidate",
    )
    p_lab_preflight.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_preflight.add_argument("candidate", help="Capability candidate id or name")
    p_lab_preflight.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_preflight.set_defaults(fn=cmd_lab_preflight)

    p_lab_request_approval = lab_sub.add_parser(
        "request-approval",
        help="Create a pending exact-action approval request for a lab candidate without execution",
    )
    p_lab_request_approval.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_request_approval.add_argument("candidate", help="Capability candidate id or name")
    p_lab_request_approval.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_request_approval.add_argument("--reason", default="francis_lab_execution_requested")
    p_lab_request_approval.set_defaults(fn=cmd_lab_request_approval)

    p_lab_approval_consumption_preflight = lab_sub.add_parser(
        "approval-consumption-preflight",
        help="Check an approval id against an exact lab action without consuming or executing",
    )
    p_lab_approval_consumption_preflight.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_approval_consumption_preflight.add_argument("candidate", help="Capability candidate id or name")
    p_lab_approval_consumption_preflight.add_argument("approval_id", help="Approval id to check")
    p_lab_approval_consumption_preflight.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_approval_consumption_preflight.set_defaults(fn=cmd_lab_approval_consumption_preflight)

    p_lab_runner_readiness = lab_sub.add_parser(
        "runner-readiness",
        help="Project governed Lab runner controls without executing repository code",
    )
    p_lab_runner_readiness.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_readiness.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_readiness.add_argument("--approval-id", default="", help="Optional exact-action approval id to check")
    p_lab_runner_readiness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_readiness.set_defaults(fn=cmd_lab_runner_readiness)

    p_lab_runner_binding = lab_sub.add_parser(
        "runner-binding",
        help="Project Lab runner binding and execution-receipt sink contracts without executing",
    )
    p_lab_runner_binding.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_binding.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_binding.add_argument("--approval-id", default="", help="Optional exact-action approval id to check")
    p_lab_runner_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_binding.set_defaults(fn=cmd_lab_runner_binding)

    p_lab_runner_enforcement = lab_sub.add_parser(
        "runner-enforcement",
        help="Verify Lab runner enforcement controls without executing repository code",
    )
    p_lab_runner_enforcement.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_enforcement.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_enforcement.add_argument(
        "--approval-id", default="", help="Optional exact-action approval id to check"
    )
    p_lab_runner_enforcement.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_enforcement.set_defaults(fn=cmd_lab_runner_enforcement)

    p_lab_approval_consumption_handoff = lab_sub.add_parser(
        "approval-consumption-handoff",
        help="Create a no-execution approval-consumption handoff after runner enforcement checks",
    )
    p_lab_approval_consumption_handoff.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_approval_consumption_handoff.add_argument("candidate", help="Capability candidate id or name")
    p_lab_approval_consumption_handoff.add_argument("approval_id", help="Approval id to bind to the handoff")
    p_lab_approval_consumption_handoff.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_approval_consumption_handoff.set_defaults(fn=cmd_lab_approval_consumption_handoff)

    p_lab_execution_receipt_sink_reservation = lab_sub.add_parser(
        "execution-receipt-sink-reservation",
        help="Reserve a future execution-receipt sink record without writing execution receipts",
    )
    p_lab_execution_receipt_sink_reservation.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_execution_receipt_sink_reservation.add_argument("candidate", help="Capability candidate id or name")
    p_lab_execution_receipt_sink_reservation.add_argument("approval_id", help="Approval id to bind to the reservation")
    p_lab_execution_receipt_sink_reservation.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_execution_receipt_sink_reservation.set_defaults(fn=cmd_lab_execution_receipt_sink_reservation)

    p_lab_runner_command_allowlist_binding = lab_sub.add_parser(
        "runner-command-allowlist-binding",
        help="Bind projected lab commands to missing allowlist controls without executing",
    )
    p_lab_runner_command_allowlist_binding.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_command_allowlist_binding.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_command_allowlist_binding.add_argument("approval_id", help="Approval id to bind to the command plan")
    p_lab_runner_command_allowlist_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_command_allowlist_binding.set_defaults(fn=cmd_lab_runner_command_allowlist_binding)

    p_lab_runner_command_allowlist_declaration = lab_sub.add_parser(
        "runner-command-allowlist-declaration",
        help="Declare exact-action lab command allowlist entries without binding or executing",
    )
    p_lab_runner_command_allowlist_declaration.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_command_allowlist_declaration.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_command_allowlist_declaration.add_argument(
        "approval_id",
        help="Approval id to bind to the command allowlist declaration",
    )
    p_lab_runner_command_allowlist_declaration.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_command_allowlist_declaration.set_defaults(fn=cmd_lab_runner_command_allowlist_declaration)

    p_lab_runner_command_allowlist_enforcement = lab_sub.add_parser(
        "runner-command-allowlist-enforcement",
        help="Check declared lab command allowlist entries against missing live enforcement controls",
    )
    p_lab_runner_command_allowlist_enforcement.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_command_allowlist_enforcement.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_command_allowlist_enforcement.add_argument(
        "approval_id",
        help="Approval id to bind to the command allowlist enforcement preflight",
    )
    p_lab_runner_command_allowlist_enforcement.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_command_allowlist_enforcement.set_defaults(fn=cmd_lab_runner_command_allowlist_enforcement)

    p_lab_runner_sandbox_readiness = lab_sub.add_parser(
        "runner-sandbox-readiness",
        help="Check Lab sandbox readiness controls without binding a runner or executing",
    )
    p_lab_runner_sandbox_readiness.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_runner_sandbox_readiness.add_argument("candidate", help="Capability candidate id or name")
    p_lab_runner_sandbox_readiness.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox readiness preflight",
    )
    p_lab_runner_sandbox_readiness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_runner_sandbox_readiness.set_defaults(fn=cmd_lab_runner_sandbox_readiness)

    p_lab_sandbox_provider_contract = lab_sub.add_parser(
        "sandbox-provider-contract",
        help="Declare missing Lab sandbox provider controls without binding a provider or executing",
    )
    p_lab_sandbox_provider_contract.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_contract.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_contract.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider contract preflight",
    )
    p_lab_sandbox_provider_contract.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_contract.set_defaults(fn=cmd_lab_sandbox_provider_contract)

    p_lab_sandbox_provider_binding = lab_sub.add_parser(
        "sandbox-provider-binding",
        help="Check Lab sandbox provider binding controls without binding a provider or executing",
    )
    p_lab_sandbox_provider_binding.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_binding.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_binding.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider binding preflight",
    )
    p_lab_sandbox_provider_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_binding.set_defaults(fn=cmd_lab_sandbox_provider_binding)

    p_lab_sandbox_provider_selection = lab_sub.add_parser(
        "sandbox-provider-selection",
        help="Record Lab sandbox provider selection/reference metadata without executing or binding a provider",
    )
    p_lab_sandbox_provider_selection.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_selection.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_selection.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider selection preflight",
    )
    p_lab_sandbox_provider_selection.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox selection",
    )
    p_lab_sandbox_provider_selection.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to inspect as metadata only",
    )
    p_lab_sandbox_provider_selection.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind by metadata only",
    )
    p_lab_sandbox_provider_selection.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_selection.set_defaults(fn=cmd_lab_sandbox_provider_selection)

    p_lab_sandbox_provider_verifier = lab_sub.add_parser(
        "sandbox-provider-verifier",
        help="Capture static Lab sandbox provider verifier evidence without executing or binding a provider",
    )
    p_lab_sandbox_provider_verifier.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_verifier.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_verifier.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider verifier preflight",
    )
    p_lab_sandbox_provider_verifier.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox verification",
    )
    p_lab_sandbox_provider_verifier.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to inspect as metadata only",
    )
    p_lab_sandbox_provider_verifier.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind by metadata only",
    )
    p_lab_sandbox_provider_verifier.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_verifier.set_defaults(fn=cmd_lab_sandbox_provider_verifier)

    p_lab_sandbox_provider_runtime_probe = lab_sub.add_parser(
        "sandbox-provider-runtime-probe",
        help="Declare Lab sandbox provider runtime probe controls without executing or binding a provider",
    )
    p_lab_sandbox_provider_runtime_probe.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_runtime_probe.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_runtime_probe.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider runtime probe preflight",
    )
    p_lab_sandbox_provider_runtime_probe.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to bind through static verifier evidence",
    )
    p_lab_sandbox_provider_runtime_probe.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind through static verifier evidence",
    )
    p_lab_sandbox_provider_runtime_probe.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe.set_defaults(fn=cmd_lab_sandbox_provider_runtime_probe)

    p_lab_sandbox_provider_runtime_probe_harness = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-harness",
        help="Declare Lab sandbox provider runtime probe harness controls without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_harness.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_sandbox_provider_runtime_probe_harness.add_argument("candidate", help="Capability candidate id or name")
    p_lab_sandbox_provider_runtime_probe_harness.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider runtime probe harness preflight",
    )
    p_lab_sandbox_provider_runtime_probe_harness.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe_harness.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to bind through runtime probe preflight evidence",
    )
    p_lab_sandbox_provider_runtime_probe_harness.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind through runtime probe preflight evidence",
    )
    p_lab_sandbox_provider_runtime_probe_harness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_harness.set_defaults(fn=cmd_lab_sandbox_provider_runtime_probe_harness)

    p_lab_sandbox_provider_runtime_probe_runner_readiness = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-runner-readiness",
        help="Declare Lab sandbox provider runtime probe runner readiness without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider runtime probe runner readiness record",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to bind through runtime probe harness evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind through runtime probe harness evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_runner_readiness.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_runner_readiness
    )

    p_lab_sandbox_provider_runtime_probe_runner_binding = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-runner-binding",
        help="Preflight Lab sandbox provider runtime probe runner binding without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider runtime probe runner binding preflight",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to bind through runtime probe runner readiness evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind through runtime probe runner readiness evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_runner_binding.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_runner_binding
    )

    p_lab_sandbox_provider_runtime_probe_runner_enforcement = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-runner-enforcement",
        help="Preflight Lab sandbox provider runtime probe runner enforcement without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "approval_id",
        help="Approval id to bind to the sandbox provider runtime probe runner enforcement preflight",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "--provider-kind",
        default="",
        help="Requested provider kind token to record for future sandbox runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "--provider-reference",
        default="",
        help="Local provider reference path/name to bind through runtime probe runner binding evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to bind through runtime probe runner binding evidence",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_runner_enforcement.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_runner_enforcement
    )

    p_lab_execution_receipt_write_readiness = lab_sub.add_parser(
        "execution-receipt-write-readiness",
        help="Check execution receipt prewrite/final-write readiness without writing execution receipts",
    )
    p_lab_execution_receipt_write_readiness.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_execution_receipt_write_readiness.add_argument("candidate", help="Capability candidate id or name")
    p_lab_execution_receipt_write_readiness.add_argument(
        "approval_id",
        help="Approval id to bind to the receipt write readiness preflight",
    )
    p_lab_execution_receipt_write_readiness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_execution_receipt_write_readiness.set_defaults(fn=cmd_lab_execution_receipt_write_readiness)

    p_lab_execution_receipt_prewrite_binding = lab_sub.add_parser(
        "execution-receipt-prewrite-binding",
        help="Bind execution receipt schema/prewrite contracts without writing execution receipts",
    )
    p_lab_execution_receipt_prewrite_binding.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_execution_receipt_prewrite_binding.add_argument("candidate", help="Capability candidate id or name")
    p_lab_execution_receipt_prewrite_binding.add_argument(
        "approval_id",
        help="Approval id to bind to the receipt prewrite contract",
    )
    p_lab_execution_receipt_prewrite_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_execution_receipt_prewrite_binding.set_defaults(fn=cmd_lab_execution_receipt_prewrite_binding)

    p_lab_execution_receipt_writer_preflight = lab_sub.add_parser(
        "execution-receipt-writer-preflight",
        help="Declare execution receipt writer boundaries without writing execution receipts",
    )
    p_lab_execution_receipt_writer_preflight.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_execution_receipt_writer_preflight.add_argument("candidate", help="Capability candidate id or name")
    p_lab_execution_receipt_writer_preflight.add_argument(
        "approval_id",
        help="Approval id to bind to the receipt writer preflight",
    )
    p_lab_execution_receipt_writer_preflight.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_execution_receipt_writer_preflight.set_defaults(fn=cmd_lab_execution_receipt_writer_preflight)

    p_lab_synthetic_execution_receipt_prewrite = lab_sub.add_parser(
        "synthetic-execution-receipt-prewrite",
        help="Prewrite a synthetic no-op execution receipt without running repository code",
    )
    p_lab_synthetic_execution_receipt_prewrite.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_synthetic_execution_receipt_prewrite.add_argument("candidate", help="Capability candidate id or name")
    p_lab_synthetic_execution_receipt_prewrite.add_argument(
        "approval_id",
        help="Approval id to bind to the synthetic receipt write",
    )
    p_lab_synthetic_execution_receipt_prewrite.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_synthetic_execution_receipt_prewrite.set_defaults(fn=cmd_lab_synthetic_execution_receipt_prewrite)

    p_lab_synthetic_execution_receipt_finalize = lab_sub.add_parser(
        "synthetic-execution-receipt-finalize",
        help="Finalize a synthetic no-op execution receipt without running repository code",
    )
    p_lab_synthetic_execution_receipt_finalize.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_synthetic_execution_receipt_finalize.add_argument("candidate", help="Capability candidate id or name")
    p_lab_synthetic_execution_receipt_finalize.add_argument(
        "approval_id",
        help="Approval id to bind to the synthetic receipt finalization",
    )
    p_lab_synthetic_execution_receipt_finalize.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_synthetic_execution_receipt_finalize.set_defaults(fn=cmd_lab_synthetic_execution_receipt_finalize)

    p_lab_approval_consume_synthetic_noop = lab_sub.add_parser(
        "approval-consume-synthetic-noop",
        help="Consume an exact-action approval for a finalized synthetic no-op receipt without execution",
    )
    p_lab_approval_consume_synthetic_noop.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_approval_consume_synthetic_noop.add_argument("candidate", help="Capability candidate id or name")
    p_lab_approval_consume_synthetic_noop.add_argument(
        "approval_id",
        help="Approval id to consume for the synthetic no-op receipt",
    )
    p_lab_approval_consume_synthetic_noop.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_approval_consume_synthetic_noop.set_defaults(fn=cmd_lab_approval_consume_synthetic_noop)

    p_lab_noop_runner_envelope = lab_sub.add_parser(
        "noop-runner-envelope",
        help="Complete a built-in no-op Lab runner envelope without running repository code",
    )
    p_lab_noop_runner_envelope.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_noop_runner_envelope.add_argument("candidate", help="Capability candidate id or name")
    p_lab_noop_runner_envelope.add_argument(
        "approval_id",
        help="Consumed approval id to bind to the no-op runner envelope",
    )
    p_lab_noop_runner_envelope.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_noop_runner_envelope.set_defaults(fn=cmd_lab_noop_runner_envelope)

    p_lab_noop_runner_transcript = lab_sub.add_parser(
        "noop-runner-transcript",
        help="Record empty stdout/stderr metadata for a built-in no-op Lab runner envelope",
    )
    p_lab_noop_runner_transcript.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_noop_runner_transcript.add_argument("candidate", help="Capability candidate id or name")
    p_lab_noop_runner_transcript.add_argument(
        "approval_id",
        help="Consumed approval id bound to the no-op runner envelope",
    )
    p_lab_noop_runner_transcript.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_noop_runner_transcript.set_defaults(fn=cmd_lab_noop_runner_transcript)

    p_lab_noop_runner_identity_binding = lab_sub.add_parser(
        "noop-runner-identity-binding",
        help="Bind the Francis-owned built-in no-op runner identity without live runner execution",
    )
    p_lab_noop_runner_identity_binding.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_noop_runner_identity_binding.add_argument("candidate", help="Capability candidate id or name")
    p_lab_noop_runner_identity_binding.add_argument(
        "approval_id",
        help="Consumed approval id bound to the no-op runner proof chain",
    )
    p_lab_noop_runner_identity_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_noop_runner_identity_binding.set_defaults(fn=cmd_lab_noop_runner_identity_binding)

    p_lab_source_mount_readiness = lab_sub.add_parser(
        "source-mount-readiness",
        help="Record read-only source reference readiness without binding a source mount or executing",
    )
    p_lab_source_mount_readiness.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_source_mount_readiness.add_argument("candidate", help="Capability candidate id or name")
    p_lab_source_mount_readiness.add_argument(
        "approval_id",
        help="Consumed approval id bound to the no-op runner identity proof chain",
    )
    p_lab_source_mount_readiness.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_source_mount_readiness.set_defaults(fn=cmd_lab_source_mount_readiness)

    p_lab_source_mount_contract = lab_sub.add_parser(
        "source-mount-contract",
        help="Record the future read-only source mount contract without binding a live mount or executing",
    )
    p_lab_source_mount_contract.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_source_mount_contract.add_argument("candidate", help="Capability candidate id or name")
    p_lab_source_mount_contract.add_argument(
        "approval_id",
        help="Consumed approval id bound to the source-mount readiness proof chain",
    )
    p_lab_source_mount_contract.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_source_mount_contract.set_defaults(fn=cmd_lab_source_mount_contract)

    p_lab_run_boundary_preflight = lab_sub.add_parser(
        "run-boundary-preflight",
        help="Aggregate guarded Lab run controls without executing repository commands",
    )
    p_lab_run_boundary_preflight.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_run_boundary_preflight.add_argument("candidate", help="Capability candidate id or name")
    p_lab_run_boundary_preflight.add_argument(
        "approval_id",
        help="Approval id to evaluate against the future governed run boundary",
    )
    p_lab_run_boundary_preflight.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_run_boundary_preflight.set_defaults(fn=cmd_lab_run_boundary_preflight)

    p_lab_sandbox_provider_runtime_probe_execution_boundary = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-execution-boundary",
        help="Preflight the provider runtime-probe execution boundary without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_execution_boundary.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_execution_boundary.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_execution_boundary.add_argument(
        "approval_id",
        help="Approval id to evaluate against the future provider runtime-probe execution boundary",
    )
    p_lab_sandbox_provider_runtime_probe_execution_boundary.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_execution_boundary.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_execution_boundary
    )

    p_lab_sandbox_provider_runtime_probe_refuse = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-refuse",
        help="Refuse provider runtime probing and write a receipt until governed probe execution exists",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.add_argument(
        "approval_id",
        help="Approval id evaluated against the provider runtime-probe execution boundary",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.add_argument(
        "--reason",
        default="sandbox_provider_runtime_probe_not_available",
        help="Receipt reason for refusing provider runtime probing",
    )
    p_lab_sandbox_provider_runtime_probe_refuse.set_defaults(fn=cmd_lab_sandbox_provider_runtime_probe_refuse)

    p_lab_sandbox_provider_runtime_probe_request_approval = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-request-approval",
        help="Request approval for future provider runtime probing without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.add_argument(
        "approval_id",
        help="Upstream exact-action approval id evaluated against the provider runtime-probe boundary",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.add_argument(
        "--reason",
        default="sandbox_provider_runtime_probe_requested",
        help="Reason recorded in the pending provider probe approval request",
    )
    p_lab_sandbox_provider_runtime_probe_request_approval.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_request_approval
    )

    p_lab_sandbox_provider_runtime_probe_consume_approval = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-consume-approval",
        help="Consume an approved provider runtime-probe approval without probing or executing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_consume_approval.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_consume_approval.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_consume_approval.add_argument(
        "approval_id",
        help="Approved provider runtime-probe approval id to consume",
    )
    p_lab_sandbox_provider_runtime_probe_consume_approval.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_consume_approval.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_consume_approval
    )

    p_lab_sandbox_provider_runtime_probe_invocation_boundary = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-invocation-boundary",
        help="Preflight the consumed provider-probe approval invocation boundary without probing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_invocation_boundary.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_invocation_boundary.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_invocation_boundary.add_argument(
        "approval_id",
        help="Consumed provider runtime-probe approval id to bind to the invocation boundary",
    )
    p_lab_sandbox_provider_runtime_probe_invocation_boundary.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_invocation_boundary.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_invocation_boundary
    )

    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-runner-pre-execution-boundary",
        help="Preflight future provider-probe runner controls without probing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary.add_argument(
        "approval_id",
        help="Consumed provider runtime-probe approval id with a recorded invocation boundary",
    )
    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_runner_pre_execution_boundary
    )

    p_lab_sandbox_provider_runtime_probe_runner_control_binding = lab_sub.add_parser(
        "sandbox-provider-runtime-probe-runner-control-binding",
        help="Record future provider-probe runner control bindings without probing a provider",
    )
    p_lab_sandbox_provider_runtime_probe_runner_control_binding.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandbox_provider_runtime_probe_runner_control_binding.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandbox_provider_runtime_probe_runner_control_binding.add_argument(
        "approval_id",
        help="Consumed provider runtime-probe approval id with a recorded runner pre-execution boundary",
    )
    p_lab_sandbox_provider_runtime_probe_runner_control_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandbox_provider_runtime_probe_runner_control_binding.set_defaults(
        fn=cmd_lab_sandbox_provider_runtime_probe_runner_control_binding
    )

    p_lab_sandboxed_rebuild_run_test_boundary = lab_sub.add_parser(
        "sandboxed-rebuild-run-test-boundary",
        help="Record the future sandboxed rebuild/run/test boundary without executing repo code",
    )
    p_lab_sandboxed_rebuild_run_test_boundary.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandboxed_rebuild_run_test_boundary.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandboxed_rebuild_run_test_boundary.add_argument(
        "approval_id",
        help="Provider runtime-probe approval id with a recorded runner control binding",
    )
    p_lab_sandboxed_rebuild_run_test_boundary.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandboxed_rebuild_run_test_boundary.set_defaults(fn=cmd_lab_sandboxed_rebuild_run_test_boundary)

    p_lab_sandboxed_rebuild_run_test_request_approval = lab_sub.add_parser(
        "sandboxed-rebuild-run-test-request-approval",
        help="Request approval for future sandboxed rebuild/run/test without executing repo code",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.add_argument(
        "approval_id",
        help="Provider runtime-probe approval id with a recorded sandboxed rebuild/run/test boundary",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.add_argument(
        "--reason",
        default="sandboxed_rebuild_run_test_requested",
        help="Reason recorded in the pending sandboxed rebuild/run/test approval request",
    )
    p_lab_sandboxed_rebuild_run_test_request_approval.set_defaults(
        fn=cmd_lab_sandboxed_rebuild_run_test_request_approval
    )

    p_lab_sandboxed_rebuild_run_test_consume_approval = lab_sub.add_parser(
        "sandboxed-rebuild-run-test-consume-approval",
        help="Consume an approved sandboxed rebuild/run/test approval without executing repo code",
    )
    p_lab_sandboxed_rebuild_run_test_consume_approval.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandboxed_rebuild_run_test_consume_approval.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandboxed_rebuild_run_test_consume_approval.add_argument(
        "approval_id",
        help="Approved sandboxed rebuild/run/test approval id to consume",
    )
    p_lab_sandboxed_rebuild_run_test_consume_approval.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandboxed_rebuild_run_test_consume_approval.set_defaults(
        fn=cmd_lab_sandboxed_rebuild_run_test_consume_approval
    )

    p_lab_sandboxed_rebuild_run_test_runner_binding = lab_sub.add_parser(
        "sandboxed-rebuild-run-test-runner-binding",
        help="Record static sandbox runner binding evidence without executing repo code",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "approval_id",
        help="Consumed sandboxed rebuild/run/test approval id",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "--provider-kind",
        default="local_process_sandbox",
        help="Requested local sandbox provider kind",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "--provider-reference",
        default="",
        help="Local sandbox provider file, directory, or name to record as metadata only",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "--provider-policy-manifest",
        default="",
        help="Local provider policy manifest path to record as metadata only",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandboxed_rebuild_run_test_runner_binding.set_defaults(fn=cmd_lab_sandboxed_rebuild_run_test_runner_binding)

    p_lab_sandboxed_rebuild_run_test_sandbox_policy = lab_sub.add_parser(
        "sandboxed-rebuild-run-test-sandbox-policy",
        help="Record conservative sandbox policy evidence without executing repo code",
    )
    p_lab_sandboxed_rebuild_run_test_sandbox_policy.add_argument(
        "source_or_path",
        help="Source id or local repo path",
    )
    p_lab_sandboxed_rebuild_run_test_sandbox_policy.add_argument(
        "candidate",
        help="Capability candidate id or name",
    )
    p_lab_sandboxed_rebuild_run_test_sandbox_policy.add_argument(
        "approval_id",
        help="Consumed sandboxed rebuild/run/test approval id with runner-binding evidence",
    )
    p_lab_sandboxed_rebuild_run_test_sandbox_policy.add_argument(
        "--actor",
        default="francis/system",
        help="Actor recorded in lab receipts",
    )
    p_lab_sandboxed_rebuild_run_test_sandbox_policy.set_defaults(fn=cmd_lab_sandboxed_rebuild_run_test_sandbox_policy)

    p_lab_execute = lab_sub.add_parser(
        "execute",
        help="Refuse lab execution and write a receipt until the governed runner exists",
    )
    p_lab_execute.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_execute.add_argument("candidate", help="Capability candidate id or name")
    p_lab_execute.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_execute.add_argument("--reason", default="francis_lab_execution_not_available")
    p_lab_execute.set_defaults(fn=cmd_lab_execute)

    p_lab_run = lab_sub.add_parser(
        "run",
        help="Francis Lab v0: attempt a safe, opt-in, sandboxed rebuild/run of a capability",
    )
    p_lab_run.add_argument("source_or_path", help="Source id or local repo path")
    p_lab_run.add_argument("candidate", help="Capability candidate id or name")
    p_lab_run.add_argument(
        "approval_id",
        help="Consumed sandboxed rebuild/run/test approval id (authority evidence)",
    )
    p_lab_run.add_argument(
        "--opt-in",
        action="store_true",
        dest="opt_in",
        help="Explicit operator opt-in to attempt REAL sandboxed execution (requires live Docker)",
    )
    p_lab_run.add_argument("--actor", default="francis/system", help="Actor recorded in lab receipts")
    p_lab_run.set_defaults(fn=cmd_lab_run)

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
