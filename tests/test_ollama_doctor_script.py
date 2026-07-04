from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ollama-doctor.ps1"


def _script_text() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_ollama_doctor_bounds_external_cli_commands() -> None:
    script = _script_text()

    assert "[Parameter()][int]$CommandTimeoutSec = 12" in script
    assert "[string[]]$CommandArgs = @()" in script
    assert '$argLine = ($CommandArgs -join " ")' in script
    assert "[int]$TimeoutSec = 12" in script
    assert "$boundedTimeoutMs = [Math]::Max(1, $TimeoutSec) * 1000" in script
    assert "$completed = $p.WaitForExit($boundedTimeoutMs)" in script
    assert "Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue" in script
    assert "command timed out after TimeoutSec=$TimeoutSec" in script
    assert "ExitCode   = $(if ($completed) { $p.ExitCode } else { 124 })" in script
    assert "TimedOut   = -not $completed" in script


def test_ollama_doctor_passes_cli_timeout_to_bounded_probes() -> None:
    script = _script_text()

    assert (
        'Invoke-CommandSafe -Exe $nvsmi.Source -CommandArgs @("-L") -MaxLines 40 -TimeoutSec $CommandTimeoutSec'
        in script
    )
    assert (
        'Invoke-CommandSafe -Exe $ollamaExe -CommandArgs @("version") -MaxLines 20 -TimeoutSec $CommandTimeoutSec'
        in script
    )
    assert (
        'Invoke-CommandSafe -Exe $ollamaExe -CommandArgs @("list") -MaxLines 200 -TimeoutSec $CommandTimeoutSec'
        in script
    )
    assert (
        'Invoke-CommandSafe -Exe $ollamaExe -CommandArgs @("ps") -MaxLines 200 -TimeoutSec $CommandTimeoutSec' in script
    )
    assert "CommandTimeoutSec      = $CommandTimeoutSec" in script


def test_ollama_doctor_counts_probe_results_as_arrays_under_strict_mode() -> None:
    script = _script_text()

    assert '$proc = @(Get-Process -Name "ollama" -ErrorAction SilentlyContinue)' in script
    assert "$services = @(Find-OllamaService)" in script
    assert "$listen = @(Get-ListeningPortInfo -Port 11434)" in script
    assert "$modelPaths = @(Get-ModelPaths)" in script
    assert "$scanned = @($modelInfo | Where-Object { $_.Exists -and $_.SizeScanned })" in script
    assert "$scannedMissingSize = @($scanned | Where-Object { $null -eq $_.SizeBytes })" in script
    assert "$gpus = @(Get-CimInstance Win32_VideoController |" in script
    assert "$videoControllers = @($gpu.VideoControllers)" in script
    assert '$events = @(Get-WinEvent -FilterHashtable @{ LogName="Application"; StartTime=$since }' in script
    assert "Event Log collection skipped:" in script
    assert "$processSnapshot = @()" in script
    assert "StartTime = $(try { $processItem.StartTime } catch { $null })" in script
    assert "Process    = $processSnapshot" in script
    assert "EventLog   = $events" in script
    assert "Checks = $script:Checks.ToArray()" in script
    assert "Checks = @($script:Checks)" not in script
    assert "Select-Object Name,Id,Path,StartTime" not in script
