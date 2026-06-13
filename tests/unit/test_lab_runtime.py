"""Offline unit tests for Francis Lab v0 runtime core.

These tests never touch Docker or the network. A fake ``CommandRunner`` is
injected so we verify decision logic, sandbox argv assembly, receipt shape,
deterministic validation, simulated-promotion refusal, and concurrency safety
without a live daemon. This is the on-spec default today: Docker is stopped, so
the exercised path is simulation, and the real-Docker path is unit-tested with a
mocked daemon (see RISKS in the build report).
"""

from __future__ import annotations

import threading

import pytest

from francis.ingest.lab.lab_runtime import (
    EXECUTION_MODE_REAL,
    EXECUTION_MODE_SIMULATED,
    VALIDATION_INVALID,
    VALIDATION_PARTIAL,
    VALIDATION_VALID,
    CapabilityRebuilder,
    CommandResult,
    LabExecutionRunReceipt,
    SandboxExecutor,
    SandboxPlan,
    build_run_argv,
    candidate_lab_safety,
    decide_promotion,
    detect_docker,
    safe_container_name,
    validate_run,
)
from francis.ingest.shared.models import (
    CapabilityCandidate,
    RepoMap,
    RepoRiskSignal,
    SourcePermissionProfile,
)

pytestmark = pytest.mark.unit


# --- fixtures ----------------------------------------------------------------
def _candidate(*, status="drafted", risk="medium", destructive=False, network=False, validation=None):
    return CapabilityCandidate(
        id="cap_test",
        name="run_project_tests",
        source_id="src_test",
        source_type="repo",
        status=status,
        description="test candidate",
        permissions_required=SourcePermissionProfile(
            read=True, execute=True, network=network, write=True, destructive=destructive
        ),
        risk_level=risk,
        suggested_validation=validation if validation is not None else ["pytest -q"],
    )


def _repo_map(*, risk_ids=()):
    return RepoMap(
        source_id="src_test",
        repo_root="/repo",
        is_git_repo=True,
        risk_signals=[RepoRiskSignal(id=rid, severity="high", path="x", detail="d") for rid in risk_ids],
        suggested_validation_commands=[{"command": "pytest -q"}],
    )


def _fake_runner(responses):
    """Build a CommandRunner that returns queued CommandResults keyed by argv[1]/[0]."""

    calls = []

    def runner(argv, timeout):
        calls.append(list(argv))
        key = argv[1] if len(argv) > 1 else argv[0]
        resp = responses.get(key, CommandResult(argv=list(argv), exit_code=0, stdout="", stderr=""))
        return resp

    runner.calls = calls  # type: ignore[attr-defined]
    return runner


# --- docker detection --------------------------------------------------------
def test_detect_docker_daemon_down():
    runner = _fake_runner({"version": CommandResult(argv=[], exit_code=1, stderr="cannot connect")})
    status = detect_docker(runner)
    assert status.available is False
    assert status.reason == "docker_daemon_unreachable"


def test_detect_docker_available():
    runner = _fake_runner({"version": CommandResult(argv=[], exit_code=0, stdout="27.0.3\n")})
    status = detect_docker(runner)
    assert status.available is True
    assert status.server_version == "27.0.3"


# --- safety gate -------------------------------------------------------------
def test_safe_candidate_passes():
    verdict = candidate_lab_safety(_candidate(), _repo_map())
    assert verdict.safe is True
    assert verdict.blockers == []


def test_destructive_candidate_blocked():
    verdict = candidate_lab_safety(_candidate(destructive=True), _repo_map())
    assert verdict.safe is False
    assert "candidate_requires_destructive_permission" in verdict.blockers


def test_network_candidate_blocked():
    verdict = candidate_lab_safety(_candidate(network=True), _repo_map())
    assert verdict.safe is False
    assert "candidate_requires_network_access" in verdict.blockers


def test_high_risk_candidate_blocked():
    verdict = candidate_lab_safety(_candidate(risk="high"), _repo_map())
    assert verdict.safe is False
    assert "candidate_risk_level_high" in verdict.blockers


def test_blocked_risk_signal_blocks_candidate():
    verdict = candidate_lab_safety(_candidate(), _repo_map(risk_ids=("destructive_command_hint",)))
    assert verdict.safe is False
    assert any(b.startswith("blocked_risk_signal:") for b in verdict.blockers)


# --- sandbox argv assembly (the isolation contract) -------------------------
def test_run_argv_enforces_isolation():
    plan = SandboxPlan(
        image="francis-lab-base:pinned",
        container_name="lab_run_x",
        source_path="/host/repo",
        script="ls -la",
    )
    argv = build_run_argv(plan)
    joined = " ".join(argv)
    assert "--network none" in joined
    assert "--read-only" in joined
    assert "--cap-drop ALL" in joined
    assert "no-new-privileges" in joined
    assert "/host/repo:/src:ro" in joined  # source mounted read-only
    assert "--tmpfs" in joined and "/work:rw" in joined  # writable scratch separate from source
    assert "--pids-limit" in joined and "--memory" in joined and "--cpus" in joined


# --- docker-safe container name (regression: live run hit `+` from ISO tz) ---
def test_safe_container_name_strips_docker_invalid_chars():
    import re

    # The real-world trigger: ISO timestamp timezone offset contains '+'.
    assert safe_container_name("lab_run_20260611T012531+0000_abc") == "lab_run_20260611T012531_0000_abc"
    assert safe_container_name("a:b/c") == "a_b_c"
    assert safe_container_name("__x") == "x"  # leading separators trimmed
    assert safe_container_name("+++") == "francis_lab_run"  # empty after cleaning -> default
    for raw in ("lab+run", "x:y+z", "20260611T01:25:31+00:00"):
        assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", safe_container_name(raw))


def test_build_run_argv_emits_docker_safe_name():
    plan = SandboxPlan(
        image="francis-lab-base:pinned",
        container_name="lab_run_20260611T012531+0000_x",  # would make `docker run` exit 125
        source_path="/host/repo",
        script="ls",
    )
    argv = build_run_argv(plan)
    name = argv[argv.index("--name") + 1]
    assert "+" not in name
    import re

    assert re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]*", name)


def test_real_run_sanitizes_container_name_for_argv_and_kill():
    runner = _fake_runner(
        {"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=0, stdout="ok")}
    )
    executor = SandboxExecutor(runner)
    plan = SandboxPlan(image="present:tag", container_name="c+name:bad", source_path="/r", script="ls")
    outcome = executor.run_real(plan, detected_commands=[])
    # sandbox_id reflects the sanitized name, and the docker run --name is valid.
    assert "+" not in outcome.sandbox_id and ":" not in outcome.sandbox_id
    run_call = next(c for c in runner.calls if c[:2] == ["docker", "run"])
    name = run_call[run_call.index("--name") + 1]
    assert name == outcome.sandbox_id


# --- rebuild planning --------------------------------------------------------
def test_rebuilder_copies_source_into_scratch_first():
    plan = CapabilityRebuilder().plan(_candidate(validation=["pytest -q"]), _repo_map())
    assert "cp -a /src/. /work/" in plan.container_script
    assert "cd /work" in plan.container_script
    assert "pytest -q" in plan.container_script
    assert plan.detected_commands == ["pytest -q"]


# --- execution: simulated default -------------------------------------------
def test_simulate_runs_nothing():
    runner = _fake_runner({})
    executor = SandboxExecutor(runner)
    plan = SandboxPlan(image="img", container_name="c1", source_path="/r", script="pytest")
    outcome = executor.simulate(plan, reason="opt_in_absent")
    assert outcome.execution_mode == EXECUTION_MODE_SIMULATED
    assert outcome.repo_code_executed is False
    assert outcome.commands_run == []
    assert runner.calls == []  # nothing was executed
    assert outcome.failure_reason == "opt_in_absent"


# --- execution: real path fails closed without local image ------------------
def test_real_run_fails_closed_when_image_absent():
    runner = _fake_runner({"image": CommandResult(argv=[], exit_code=1)})  # inspect -> not found
    executor = SandboxExecutor(runner)
    plan = SandboxPlan(image="missing:tag", container_name="c2", source_path="/r", script="pytest")
    outcome = executor.run_real(plan, detected_commands=["pytest"])
    assert outcome.execution_mode == EXECUTION_MODE_SIMULATED
    assert outcome.failure_reason == "pinned_image_not_present_locally_refused_to_pull"
    # It must NOT have attempted `docker run`.
    assert all(call[:2] != ["docker", "run"] for call in runner.calls)


# --- execution: real path success -------------------------------------------
def test_real_run_success_captures_output():
    runner = _fake_runner(
        {
            "image": CommandResult(argv=[], exit_code=0),  # inspect -> present
            "run": CommandResult(argv=[], exit_code=0, stdout="3 passed", duration_ms=1200),
        }
    )
    executor = SandboxExecutor(runner)
    plan = SandboxPlan(image="present:tag", container_name="c3", source_path="/r", script="pytest")
    outcome = executor.run_real(plan, detected_commands=["pytest -q"])
    assert outcome.execution_mode == EXECUTION_MODE_REAL
    assert outcome.exit_code == 0
    assert outcome.repo_code_executed is True
    assert "3 passed" in outcome.stdout_summary
    assert outcome.commands_run == ["pytest -q"]


def test_real_run_timeout_kills_container():
    runner = _fake_runner(
        {
            "image": CommandResult(argv=[], exit_code=0),
            "run": CommandResult(argv=[], exit_code=None, timed_out=True, error="command_timed_out"),
        }
    )
    executor = SandboxExecutor(runner)
    plan = SandboxPlan(image="present:tag", container_name="c4", source_path="/r", script="sleep 999")
    outcome = executor.run_real(plan, detected_commands=["sleep 999"])
    assert outcome.timed_out is True
    # A docker kill must have been attempted for the named container.
    assert ["docker", "kill", "c4"] in runner.calls


# --- deterministic validation ------------------------------------------------
def test_validation_simulated_is_partial():
    runner = _fake_runner({})
    outcome = SandboxExecutor(runner).simulate(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), reason="sim"
    )
    assert validate_run(outcome) == VALIDATION_PARTIAL


def test_validation_real_zero_exit_is_valid():
    runner = _fake_runner({"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=0)})
    outcome = SandboxExecutor(runner).run_real(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), detected_commands=["x"]
    )
    assert validate_run(outcome) == VALIDATION_VALID


def test_validation_real_nonzero_is_invalid():
    runner = _fake_runner({"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=1)})
    outcome = SandboxExecutor(runner).run_real(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), detected_commands=["x"]
    )
    assert validate_run(outcome) == VALIDATION_INVALID


# --- promotion: never on simulated evidence ---------------------------------
def test_promotion_refused_on_simulated_evidence():
    runner = _fake_runner({})
    outcome = SandboxExecutor(runner).simulate(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), reason="sim"
    )
    decision = decide_promotion("drafted", outcome, validate_run(outcome))
    # Simulated evidence promotes nothing: status is unchanged, never validated.
    assert decision.promoted is False
    assert decision.to_status == "drafted"
    assert decision.reason == "simulated_run_has_no_execution_evidence"


def test_promotion_to_validated_only_on_real_valid():
    runner = _fake_runner({"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=0)})
    outcome = SandboxExecutor(runner).run_real(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), detected_commands=["x"]
    )
    decision = decide_promotion("runnable", outcome, validate_run(outcome))
    assert decision.to_status == "validated"
    assert decision.promoted is True


def test_promotion_real_invalid_stays_runnable():
    runner = _fake_runner({"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=2)})
    outcome = SandboxExecutor(runner).run_real(
        SandboxPlan(image="i", container_name="c", source_path="/r", script="x"), detected_commands=["x"]
    )
    decision = decide_promotion("runnable", outcome, validate_run(outcome))
    assert decision.to_status == "runnable"
    assert decision.promoted is False


# --- receipt round-trip ------------------------------------------------------
def test_run_receipt_round_trip():
    receipt = LabExecutionRunReceipt(
        lab_run_id="run_1",
        operation="lab.execution.run",
        source_id="src_test",
        candidate_id="cap_test",
        candidate_name="run_project_tests",
        approval_id="appr_1",
        sandbox_id="sim_abc",
        execution_mode=EXECUTION_MODE_SIMULATED,
        image="img",
        commands_run=[],
        container_argv=["docker", "run"],
        exit_code=None,
        stdout_summary="",
        stderr_summary="",
        timed_out=False,
        duration_ms=0,
        validation_status=VALIDATION_PARTIAL,
        promotion_from="drafted",
        promotion_to="runnable",
        promoted=True,
        failure_reason="sim",
        created_at="2026-06-10T00:00:00+00:00",
    )
    restored = LabExecutionRunReceipt.from_dict(receipt.to_dict())
    assert restored is not None
    assert restored.lab_run_id == "run_1"
    assert restored.execution_mode == EXECUTION_MODE_SIMULATED
    assert restored.execution_authority is False


# --- concurrency: parallel runs do not cross-contaminate state --------------
def test_parallel_runs_isolated_state():
    runner = _fake_runner(
        {"image": CommandResult(argv=[], exit_code=0), "run": CommandResult(argv=[], exit_code=0, stdout="ok")}
    )
    executor = SandboxExecutor(runner)
    results: dict[int, str] = {}
    errors: list[Exception] = []

    def worker(i):
        try:
            plan = SandboxPlan(image="present:tag", container_name=f"lab_{i}", source_path=f"/r{i}", script="pytest")
            outcome = executor.run_real(plan, detected_commands=[f"cmd{i}"])
            results[i] = outcome.sandbox_id
        except Exception as exc:  # pragma: no cover
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    # Each run kept its own sandbox id (container name); no shared mutable state.
    assert sorted(results.values()) == [f"lab_{i}" for i in range(8)]
