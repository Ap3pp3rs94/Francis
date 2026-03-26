param(
    [switch]$SkipRuntimeStaging
)

$ErrorActionPreference = "Stop"

$steps = @(
    @{ Name = "ruff"; Command = @("ruff", "check", ".") },
    @{ Name = "unit-hardening"; Command = @("pytest", "-q", "tests/unit/test_mission_queue_repair.py", "tests/unit/test_runtime_hygiene.py", "tests/unit/test_observer_emitter.py", "tests/unit/test_observer_baselines.py") },
    @{ Name = "presence-hardening"; Command = @("pytest", "-q", "tests/unit/test_presence_state.py", "tests/test_presence_state_grounding.py") },
    @{ Name = "inbox-telemetry-hardening"; Command = @("pytest", "-q", "tests/integration/test_inbox_pipeline.py", "tests/integration/test_telemetry_pipeline.py") },
    @{ Name = "observer-integration"; Command = @("pytest", "-q", "tests/integration/test_observer_emits_events.py") },
    @{ Name = "security-hardening"; Command = @("pytest", "-q", "tests/integration/test_security_quarantine.py", "tests/redteam/test_prompt_injection.py", "tests/redteam/test_fs_escape_attempts.py") },
    @{ Name = "mission-smoke"; Command = @("pytest", "-q", "tests/integration/test_mission_tick.py", "-k", "create_mission_persists_and_queues or tick_advances_mission_and_history or failed_tick_goes_to_deadletter or tick_idempotency_replays_without_double_advance") },
    @{ Name = "worker-smoke"; Command = @("pytest", "-q", "tests/integration/test_worker_cycle.py", "-k", "worker_cycle_processes_mission_queue or worker_cycle_action_timeout_can_escalate_to_deadletter") },
    @{ Name = "overlay-test"; Command = @("npm", "run", "overlay:test") }
)

if (-not $SkipRuntimeStaging) {
    $steps += @{ Name = "overlay-runtime"; Command = @("npm", "run", "overlay:prepare-runtime") }
}

foreach ($step in $steps) {
    Write-Host ("==> " + $step.Name)
    Write-Host ("Running: " + ($step.Command -join " "))
    & $step.Command[0] @($step.Command[1..($step.Command.Length - 1)])
    if ($LASTEXITCODE -ne 0) {
        exit $LASTEXITCODE
    }
}
