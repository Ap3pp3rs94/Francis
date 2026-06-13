"""Francis Lab v0 runtime: safe, opt-in, sandboxed capability rebuild + run.

This module is the FIRST place in the ingest/lab chain that can actually execute
repository code. Everything upstream of it is deliberately non-executing
(see ``service.py`` and ``CODE_BORN_CAPABILITY_INGESTION.md``). To keep that
boundary honest, this module follows three hard rules:

1. Real execution happens only inside a Docker sandbox, only when an explicit
   opt-in is given, only for capability candidates proven safe + non-destructive,
   and only when a consumed exact-action approval exists upstream. If any of
   those is missing, the run is SIMULATED (a Francis-owned no-op), never a real
   repository command.
2. A simulated run produces no real evidence, so the validator can never return
   ``VALID`` for it and promotion to ``validated`` is refused.
3. Every run produces a receipt. No receipt means the run did not happen.

The module is intentionally pure and side-effect-light: the only side effect is
invoking the injected ``CommandRunner`` (which defaults to ``subprocess``).
Artifact/receipt persistence is handled by the calling ``IngestService`` so this
layer stays trivially testable offline without Docker.
"""

from __future__ import annotations

import re
import subprocess
import time
import uuid
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from ..shared.models import CapabilityCandidate, RepoMap

# --- execution modes ---------------------------------------------------------
EXECUTION_MODE_REAL = "real"
EXECUTION_MODE_SIMULATED = "simulated"

# --- deterministic validation verdicts --------------------------------------
VALIDATION_VALID = "VALID"
VALIDATION_INVALID = "INVALID"
VALIDATION_PARTIAL = "PARTIAL"

# --- capability promotion ladder (never skip a state) -----------------------
PROMOTION_STATES: tuple[str, ...] = ("discovered", "drafted", "runnable", "validated", "registered")

# --- sandbox defaults (conservative, default-deny) --------------------------
DEFAULT_TIMEOUT_SECONDS = 120
DEFAULT_MEMORY = "512m"
DEFAULT_PIDS_LIMIT = 256
DEFAULT_CPUS = "1.0"
DEFAULT_SCRATCH_SIZE = "256m"
DEFAULT_NETWORK = "none"
_OUTPUT_SUMMARY_MAX = 4000

# Risk signals that make a candidate ineligible for Lab execution outright.
BLOCKED_RISK_SIGNAL_IDS: frozenset[str] = frozenset(
    {
        "destructive_command_hint",
        "credential_like_file_present",
        "package_postinstall_script",
        "package_preinstall_script",
        "deploy_script_present",
        "migration_script_present",
        "network_command_hint",
    }
)


@dataclass(frozen=True)
class CommandResult:
    """Outcome of invoking a single host command (docker, etc.)."""

    argv: list[str]
    exit_code: int | None
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    duration_ms: int = 0
    error: str = ""

    @property
    def ok(self) -> bool:
        return self.error == "" and self.exit_code == 0 and not self.timed_out


CommandRunner = Callable[[Sequence[str], float], CommandResult]


def _summarize(text: str) -> str:
    clean = text or ""
    if len(clean) <= _OUTPUT_SUMMARY_MAX:
        return clean
    head = clean[: _OUTPUT_SUMMARY_MAX // 2]
    tail = clean[-_OUTPUT_SUMMARY_MAX // 2 :]
    return f"{head}\n...[{len(clean) - _OUTPUT_SUMMARY_MAX} chars truncated]...\n{tail}"


def default_command_runner(argv: Sequence[str], timeout: float) -> CommandResult:
    """Real subprocess runner. Never auto-pulls; only invokes what it is given."""

    args = [str(item) for item in argv]
    started = time.monotonic()
    try:
        proc = subprocess.run(  # noqa: S603 - argv is fully controlled, no shell
            args,
            capture_output=True,
            text=True,
            timeout=max(1.0, float(timeout)),
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        duration = int((time.monotonic() - started) * 1000)
        return CommandResult(
            argv=args,
            exit_code=None,
            stdout=_summarize(exc.stdout or "" if isinstance(exc.stdout, str) else ""),
            stderr=_summarize(exc.stderr or "" if isinstance(exc.stderr, str) else ""),
            timed_out=True,
            duration_ms=duration,
            error="command_timed_out",
        )
    except FileNotFoundError as exc:
        return CommandResult(argv=args, exit_code=None, error=f"executable_not_found:{exc}")
    except Exception as exc:  # pragma: no cover - defensive
        return CommandResult(argv=args, exit_code=None, error=f"command_invocation_failed:{exc}")
    duration = int((time.monotonic() - started) * 1000)
    return CommandResult(
        argv=args,
        exit_code=proc.returncode,
        stdout=_summarize(proc.stdout or ""),
        stderr=_summarize(proc.stderr or ""),
        duration_ms=duration,
    )


# --- docker detection (fail closed) -----------------------------------------
@dataclass(frozen=True)
class DockerStatus:
    available: bool
    server_version: str = ""
    reason: str = ""
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_docker(run: CommandRunner | None = None) -> DockerStatus:
    """Probe whether a live Docker daemon is reachable. Pure read; never mutates."""

    runner = run or default_command_runner
    result = runner(["docker", "version", "--format", "{{.Server.Version}}"], 10.0)
    if result.error:
        return DockerStatus(available=False, reason="docker_cli_unavailable", detail=result.error)
    if result.timed_out:
        return DockerStatus(available=False, reason="docker_version_timed_out")
    if result.exit_code != 0:
        return DockerStatus(
            available=False,
            reason="docker_daemon_unreachable",
            detail=_summarize(result.stderr).strip(),
        )
    return DockerStatus(available=True, server_version=result.stdout.strip())


def image_present_locally(image: str, run: CommandRunner | None = None) -> bool:
    """True only if the pinned image already exists locally. Never pulls."""

    clean = (image or "").strip()
    if not clean:
        return False
    runner = run or default_command_runner
    result = runner(["docker", "image", "inspect", clean], 10.0)
    return result.exit_code == 0 and not result.error and not result.timed_out


# --- safety gate -------------------------------------------------------------
@dataclass(frozen=True)
class SafetyVerdict:
    safe: bool
    blockers: list[str] = field(default_factory=list)
    blocked_risk_signals: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def candidate_lab_safety(candidate: CapabilityCandidate, repo_map: RepoMap) -> SafetyVerdict:
    """A candidate may enter Lab execution only if non-destructive and low/medium risk.

    Writing inside the sandbox scratch dir is allowed (``write`` permission is not a
    blocker); destructive intent, network need, high risk, or any blocked risk
    signal is.
    """

    blockers: list[str] = []
    perms = candidate.permissions_required
    if getattr(perms, "destructive", False):
        blockers.append("candidate_requires_destructive_permission")
    if getattr(perms, "network", False):
        blockers.append("candidate_requires_network_access")
    if (candidate.risk_level or "").strip().lower() == "high":
        blockers.append("candidate_risk_level_high")

    risk_ids = {str(getattr(signal, "id", "")).strip() for signal in repo_map.risk_signals}
    blocked_signals = sorted(rid for rid in risk_ids if rid in BLOCKED_RISK_SIGNAL_IDS)
    blockers.extend(f"blocked_risk_signal:{rid}" for rid in blocked_signals)

    return SafetyVerdict(safe=not blockers, blockers=blockers, blocked_risk_signals=blocked_signals)


# --- rebuild planning --------------------------------------------------------
@dataclass(frozen=True)
class RebuildPlan:
    """A detected (never user-authored) command projected into an in-sandbox script."""

    candidate_id: str
    candidate_name: str
    detected_commands: list[str]
    container_script: str
    inspect_first: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CapabilityRebuilder:
    """Derives a safe, inspect-first in-container script from the repo map.

    It never invents commands and never blindly runs arbitrary repo scripts: it
    uses only the validation commands the repo adapter already detected for this
    candidate. The script copies the read-only source into the writable scratch
    workdir before running, so the host source mount stays read-only.
    """

    def plan(self, candidate: CapabilityCandidate, repo_map: RepoMap) -> RebuildPlan:
        detected = [str(cmd).strip() for cmd in (candidate.suggested_validation or []) if str(cmd).strip()]
        if not detected:
            detected = [
                str(item.get("command")).strip()
                for item in repo_map.suggested_validation_commands
                if str(item.get("command") or "").strip()
            ]
        # Inspect first: list the tree, then run detected commands (if any).
        steps = ["set -e", "cp -a /src/. /work/ 2>/dev/null || true", "cd /work", "ls -la"]
        steps.extend(detected)
        script = " && ".join(steps)
        return RebuildPlan(
            candidate_id=candidate.id,
            candidate_name=candidate.name,
            detected_commands=detected,
            container_script=script,
        )


# --- sandbox execution -------------------------------------------------------
@dataclass(frozen=True)
class SandboxPlan:
    image: str
    container_name: str
    source_path: str
    script: str
    network: str = DEFAULT_NETWORK
    memory: str = DEFAULT_MEMORY
    pids_limit: int = DEFAULT_PIDS_LIMIT
    cpus: str = DEFAULT_CPUS
    scratch_size: str = DEFAULT_SCRATCH_SIZE
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS


def safe_container_name(name: str) -> str:
    """Coerce a name to Docker's allowed set: ``[a-zA-Z0-9][a-zA-Z0-9_.-]*``.

    Run ids derive from an ISO timestamp whose timezone offset contains ``+``,
    which Docker rejects in ``--name``; this keeps the container name valid.
    """

    cleaned = re.sub(r"[^a-zA-Z0-9_.-]", "_", str(name)).lstrip("_.-")
    if not cleaned:
        return "francis_lab_run"
    if not cleaned[0].isalnum():
        cleaned = f"x{cleaned}"
    return cleaned[:120]


def build_run_argv(plan: SandboxPlan) -> list[str]:
    """Assemble the locked-down ``docker run`` argv.

    Network is disabled, the root filesystem and the source mount are read-only,
    capabilities are dropped, privilege escalation is blocked, and the only
    writable surface is a size-limited tmpfs scratch at ``/work``.
    """

    return [
        "docker",
        "run",
        "--rm",
        "--name",
        safe_container_name(plan.container_name),
        "--network",
        plan.network,
        "--read-only",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--pids-limit",
        str(plan.pids_limit),
        "--memory",
        plan.memory,
        "--cpus",
        str(plan.cpus),
        "-v",
        f"{plan.source_path}:/src:ro",
        "--tmpfs",
        f"/work:rw,exec,size={plan.scratch_size},nodev,nosuid",
        "-w",
        "/work",
        "--env",
        "HOME=/work",
        plan.image,
        "/bin/sh",
        "-lc",
        plan.script,
    ]


@dataclass(frozen=True)
class RunOutcome:
    execution_mode: str
    sandbox_id: str
    argv: list[str]
    exit_code: int | None
    stdout_summary: str
    stderr_summary: str
    timed_out: bool
    duration_ms: int
    commands_run: list[str]
    network_accessed: bool
    wrote_to_repo: bool
    repo_code_executed: bool
    failure_reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SandboxExecutor:
    """Runs a rebuild plan, choosing REAL (Docker) or SIMULATED based on the gate."""

    def __init__(self, run: CommandRunner | None = None) -> None:
        self._run = run or default_command_runner

    def simulate(self, plan: SandboxPlan, *, reason: str) -> RunOutcome:
        """Francis-owned no-op standing in for the real command. Runs nothing."""

        return RunOutcome(
            execution_mode=EXECUTION_MODE_SIMULATED,
            sandbox_id=f"sim_{uuid.uuid4().hex[:12]}",
            argv=build_run_argv(plan),
            exit_code=None,
            stdout_summary="",
            stderr_summary="",
            timed_out=False,
            duration_ms=0,
            commands_run=[],
            network_accessed=False,
            wrote_to_repo=False,
            repo_code_executed=False,
            failure_reason=reason,
        )

    def run_real(self, plan: SandboxPlan, *, detected_commands: list[str]) -> RunOutcome:
        """Execute the sandboxed container. Fails closed if the image is absent."""

        # Normalize the container name once so argv, kill target, and sandbox_id agree.
        plan = replace(plan, container_name=safe_container_name(plan.container_name))
        if not image_present_locally(plan.image, self._run):
            return RunOutcome(
                execution_mode=EXECUTION_MODE_SIMULATED,
                sandbox_id=f"sim_{uuid.uuid4().hex[:12]}",
                argv=build_run_argv(plan),
                exit_code=None,
                stdout_summary="",
                stderr_summary="",
                timed_out=False,
                duration_ms=0,
                commands_run=[],
                network_accessed=False,
                wrote_to_repo=False,
                repo_code_executed=False,
                failure_reason="pinned_image_not_present_locally_refused_to_pull",
            )
        argv = build_run_argv(plan)
        result = self._run(argv, float(plan.timeout_seconds))
        if result.timed_out:
            # Best-effort kill; --rm cleans the container up.
            self._run(["docker", "kill", plan.container_name], 10.0)
        return RunOutcome(
            execution_mode=EXECUTION_MODE_REAL,
            sandbox_id=plan.container_name,
            argv=argv,
            exit_code=result.exit_code,
            stdout_summary=result.stdout,
            stderr_summary=result.stderr,
            timed_out=result.timed_out,
            duration_ms=result.duration_ms,
            commands_run=list(detected_commands),
            network_accessed=False,
            wrote_to_repo=False,
            repo_code_executed=True,
            failure_reason=result.error or ("" if result.exit_code == 0 else "container_command_nonzero_exit"),
        )


# --- deterministic validation -----------------------------------------------
def validate_run(outcome: RunOutcome) -> str:
    """Deterministic verdict. Simulated evidence can never be VALID."""

    if outcome.execution_mode != EXECUTION_MODE_REAL:
        return VALIDATION_PARTIAL
    if outcome.timed_out or outcome.exit_code is None or outcome.exit_code != 0:
        return VALIDATION_INVALID
    return VALIDATION_VALID


# --- promotion ---------------------------------------------------------------
@dataclass(frozen=True)
class PromotionDecision:
    from_status: str
    to_status: str
    promoted: bool
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def decide_promotion(current_status: str, outcome: RunOutcome, validation_status: str) -> PromotionDecision:
    """Advance at most one rung; never skip states; never promote without real+valid evidence.

    PHASE 3 contract: a capability may only advance when it was executed in a real
    sandbox, deterministic validation passed, and no network violation occurred.
    Simulated or INVALID runs never promote. Advancement stops at ``validated`` —
    moving to ``registered`` is a separate governance decision, not an automatic
    consequence of one passing run.
    """

    current = (current_status or "").strip().lower()
    if current not in PROMOTION_STATES:
        return PromotionDecision(
            from_status=current,
            to_status=current,
            promoted=False,
            reason="status_not_on_promotion_ladder",
        )
    if outcome.execution_mode != EXECUTION_MODE_REAL:
        return PromotionDecision(
            from_status=current,
            to_status=current,
            promoted=False,
            reason="simulated_run_has_no_execution_evidence",
        )
    if validation_status != VALIDATION_VALID:
        return PromotionDecision(
            from_status=current,
            to_status=current,
            promoted=False,
            reason="real_run_not_valid",
        )
    if outcome.network_accessed:
        return PromotionDecision(
            from_status=current,
            to_status=current,
            promoted=False,
            reason="network_violation_blocks_promotion",
        )
    # Real + VALID + no network: advance exactly one rung, capped at validated.
    idx = PROMOTION_STATES.index(current)
    target_idx = min(idx + 1, PROMOTION_STATES.index("validated"))
    to_status = PROMOTION_STATES[target_idx]
    return PromotionDecision(
        from_status=current,
        to_status=to_status,
        promoted=to_status != current,
        reason="real_valid_sandbox_run_with_receipt",
    )


# --- run receipt (distinct from the synthetic/no-op receipt) ----------------
@dataclass(frozen=True)
class LabExecutionRunReceipt:
    """Receipt for a Lab rebuild/run attempt. Required for every run."""

    lab_run_id: str
    operation: str
    source_id: str
    candidate_id: str
    candidate_name: str
    approval_id: str
    sandbox_id: str
    execution_mode: str
    image: str
    commands_run: list[str]
    container_argv: list[str]
    exit_code: int | None
    stdout_summary: str
    stderr_summary: str
    timed_out: bool
    duration_ms: int
    validation_status: str
    promotion_from: str
    promotion_to: str
    promoted: bool
    failure_reason: str
    created_at: str
    actor: str = "francis/system"
    schema_version: int = 1
    # Truth booleans (mirror the chain's honesty contract).
    executed: bool = False
    repo_code_executed: bool = False
    network_accessed: bool = False
    wrote_to_repo: bool = False
    execution_authority: bool = False
    approval_consumed: bool = False
    opt_in: bool = False
    warnings: list[str] = field(default_factory=list)
    artifacts_generated: list[str] = field(default_factory=list)
    receipts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Any) -> "LabExecutionRunReceipt | None":
        if not isinstance(value, dict):
            return None
        run_id = str(value.get("lab_run_id") or "").strip()
        source_id = str(value.get("source_id") or "").strip()
        candidate_id = str(value.get("candidate_id") or "").strip()
        if not run_id or not source_id or not candidate_id:
            return None
        raw_exit = value.get("exit_code")
        try:
            exit_code = None if raw_exit is None else int(raw_exit)
        except (TypeError, ValueError):
            exit_code = None
        return cls(
            lab_run_id=run_id,
            operation=str(value.get("operation") or "lab.execution.run").strip(),
            source_id=source_id,
            candidate_id=candidate_id,
            candidate_name=str(value.get("candidate_name") or "").strip(),
            approval_id=str(value.get("approval_id") or "").strip(),
            sandbox_id=str(value.get("sandbox_id") or "").strip(),
            execution_mode=str(value.get("execution_mode") or EXECUTION_MODE_SIMULATED).strip(),
            image=str(value.get("image") or "").strip(),
            commands_run=[str(c) for c in value.get("commands_run") or [] if str(c).strip()],
            container_argv=[str(c) for c in value.get("container_argv") or []],
            exit_code=exit_code,
            stdout_summary=str(value.get("stdout_summary") or ""),
            stderr_summary=str(value.get("stderr_summary") or ""),
            timed_out=bool(value.get("timed_out", False)),
            duration_ms=int(value.get("duration_ms") or 0),
            validation_status=str(value.get("validation_status") or VALIDATION_PARTIAL).strip(),
            promotion_from=str(value.get("promotion_from") or "").strip(),
            promotion_to=str(value.get("promotion_to") or "").strip(),
            promoted=bool(value.get("promoted", False)),
            failure_reason=str(value.get("failure_reason") or "").strip(),
            created_at=str(value.get("created_at") or "").strip(),
            actor=str(value.get("actor") or "francis/system").strip(),
            schema_version=int(value.get("schema_version") or 1),
            executed=bool(value.get("executed", False)),
            repo_code_executed=bool(value.get("repo_code_executed", False)),
            network_accessed=bool(value.get("network_accessed", False)),
            wrote_to_repo=bool(value.get("wrote_to_repo", False)),
            execution_authority=bool(value.get("execution_authority", False)),
            approval_consumed=bool(value.get("approval_consumed", False)),
            opt_in=bool(value.get("opt_in", False)),
            warnings=[str(w) for w in value.get("warnings") or []],
            artifacts_generated=[str(a) for a in value.get("artifacts_generated") or []],
            receipts=[str(r) for r in value.get("receipts") or []],
        )


__all__ = [
    "EXECUTION_MODE_REAL",
    "EXECUTION_MODE_SIMULATED",
    "VALIDATION_VALID",
    "VALIDATION_INVALID",
    "VALIDATION_PARTIAL",
    "PROMOTION_STATES",
    "BLOCKED_RISK_SIGNAL_IDS",
    "CommandResult",
    "CommandRunner",
    "DockerStatus",
    "SafetyVerdict",
    "RebuildPlan",
    "CapabilityRebuilder",
    "SandboxPlan",
    "RunOutcome",
    "SandboxExecutor",
    "PromotionDecision",
    "LabExecutionRunReceipt",
    "default_command_runner",
    "detect_docker",
    "image_present_locally",
    "candidate_lab_safety",
    "build_run_argv",
    "validate_run",
    "decide_promotion",
]
