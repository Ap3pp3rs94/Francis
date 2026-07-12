[CmdletBinding()]
param(
    [int]$ExitAfterSeconds = 0,
    [switch]$AutoIntent,
    [string]$ScreenshotPath = "",
    [string]$SessionId = "francis_unreal_stage1_v1"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$projectPath = Join-Path $repoRoot "apps\unreal_presence\FrancisPresence.uproject"
$selectionPath = Join-Path $repoRoot "apps\unreal_presence\Config\francis_presence_selection.json"
$engineRoot = "C:\Program Files\Epic Games\UE_5.8"
$editorPath = Join-Path $engineRoot "Engine\Binaries\Win64\UnrealEditor.exe"
$runtimeRoot = Join-Path $repoRoot "data\runtime\unreal-presence"
$launchReceiptPath = Join-Path $runtimeRoot "launch.json"
$rendererStatusPath = Join-Path $repoRoot "apps\unreal_presence\Saved\FrancisPresence\runtime_status.json"
$rendererDedupRoot = Join-Path $repoRoot "apps\unreal_presence\Saved\FrancisPresence\dedup"
$rendererDedupPath = Join-Path $rendererDedupRoot "$SessionId.json"
$hostStatusPath = Join-Path $repoRoot "data\runtime\unreal-presence-host\status.json"
$temporaryReceipt = "$launchReceiptPath.$PID.tmp"

function Resolve-BoundedScreenshotPath {
    param(
        [string]$Path,
        [string]$RuntimeRoot,
        [string]$RepoRoot
    )

    if (-not $Path) {
        return ""
    }

    $candidate = if ([System.IO.Path]::IsPathRooted($Path)) {
        $Path
    } elseif (-not (Split-Path -Parent $Path)) {
        Join-Path $RuntimeRoot $Path
    } else {
        Join-Path $RepoRoot $Path
    }
    $resolved = [System.IO.Path]::GetFullPath($candidate)
    $resolvedRuntimeRoot = [System.IO.Path]::GetFullPath($RuntimeRoot)
    $resolvedParent = [System.IO.Path]::GetDirectoryName($resolved)
    if (-not [string]::Equals($resolvedParent, $resolvedRuntimeRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "ScreenshotPath must name a file directly under $resolvedRuntimeRoot."
    }
    if (-not [string]::Equals([System.IO.Path]::GetExtension($resolved), ".png", [StringComparison]::OrdinalIgnoreCase)) {
        throw "ScreenshotPath must use the .png extension."
    }
    return $resolved
}

function Get-ProcessEnvironmentSnapshot {
    param([string[]]$Names)

    $snapshot = @{}
    foreach ($name in $Names) {
        $item = Get-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
        $snapshot[$name] = [pscustomobject]@{
            Exists = $null -ne $item
            Value = if ($null -ne $item) { [string]$item.Value } else { "" }
        }
    }
    return $snapshot
}

function Restore-ProcessEnvironment {
    param([hashtable]$Snapshot)

    foreach ($entry in $Snapshot.GetEnumerator()) {
        if ($entry.Value.Exists) {
            [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value.Value, "Process")
        } else {
            Remove-Item -LiteralPath "Env:$($entry.Key)" -ErrorAction SilentlyContinue
        }
    }
}

function Stop-OwnedProcess {
    param([System.Diagnostics.Process]$Process)

    if ($null -eq $Process) {
        return
    }
    try {
        $Process.Refresh()
        if (-not $Process.HasExited) {
            Stop-Process -Id $Process.Id -Force -ErrorAction SilentlyContinue
            Wait-Process -Id $Process.Id -Timeout 15 -ErrorAction SilentlyContinue
        }
    } catch {
        # The process may have exited between refresh and cleanup.
    }
}

foreach ($requiredPath in @($projectPath, $selectionPath, $editorPath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Unreal presence path is missing: $requiredPath"
    }
}
if ($ExitAfterSeconds -lt 0 -or $ExitAfterSeconds -gt 86400) {
    throw "ExitAfterSeconds must be between 0 and 86400."
}
if (-not $SessionId -or $SessionId.Length -gt 160 -or $SessionId -notmatch '^[A-Za-z0-9_.-]+$') {
    throw "SessionId must be a non-empty contract identifier of at most 160 characters."
}
$resolvedScreenshotPath = Resolve-BoundedScreenshotPath `
    -Path $ScreenshotPath `
    -RuntimeRoot $runtimeRoot `
    -RepoRoot $repoRoot
if (Test-Path -LiteralPath $launchReceiptPath -PathType Leaf) {
    $previousLaunch = Get-Content -LiteralPath $launchReceiptPath -Raw | ConvertFrom-Json
    foreach ($previousProcessId in @($previousLaunch.host_process_id, $previousLaunch.unreal_process_id)) {
        if (-not $previousProcessId) {
            continue
        }
        $previousProcess = Get-CimInstance Win32_Process -Filter "ProcessId = $previousProcessId" -ErrorAction SilentlyContinue
        if ($previousProcess -and (
                $previousProcess.CommandLine -match 'francis\.unreal_presence_host' -or
                $previousProcess.CommandLine -match [regex]::Escape($projectPath)
            )) {
            throw "Francis Unreal presence is already running as process $previousProcessId."
        }
    }
}

$environmentNames = @(
    "FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID",
    "FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64",
    "FRANCIS_UNREAL_PRESENCE_ADAPTER_ID",
    "FRANCIS_UNREAL_PRESENCE_SESSION_ID",
    "FRANCIS_UNREAL_PRESENCE_SELECTION_PATH",
    "FRANCIS_UNREAL_PRESENCE_STATUS_PATH",
    "FRANCIS_UNREAL_PRESENCE_DEDUP_PATH",
    "FRANCIS_UNREAL_PRESENCE_HOST_STATUS_PATH",
    "FRANCIS_UNREAL_PRESENCE_AUTO_INTENT",
    "FRANCIS_UNREAL_PRESENCE_HOST_EXIT_AFTER_SECONDS",
    "FRANCIS_UNREAL_PRESENCE_EXIT_AFTER_SECONDS",
    "FRANCIS_UNREAL_PRESENCE_SCREENSHOT_PATH"
)
$environmentSnapshot = Get-ProcessEnvironmentSnapshot -Names $environmentNames
$hostProcess = $null
$unrealProcess = $null
$launchCommitted = $false

try {
    New-Item -ItemType Directory -Path $runtimeRoot -Force | Out-Null
    foreach ($stalePath in @($rendererStatusPath, $hostStatusPath)) {
        Remove-Item -LiteralPath $stalePath -Force -ErrorAction SilentlyContinue
    }
    if ($resolvedScreenshotPath) {
        Remove-Item -LiteralPath $resolvedScreenshotPath -Force -ErrorAction SilentlyContinue
    }

    $secret = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($secret)
    $env:FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID = "francis_presence_local_v1"
    $env:FRANCIS_UNREAL_PRESENCE_IPC_KEY_B64 = [Convert]::ToBase64String($secret)
    [Array]::Clear($secret, 0, $secret.Length)
    $env:FRANCIS_UNREAL_PRESENCE_ADAPTER_ID = "unreal_presence_1"
    $env:FRANCIS_UNREAL_PRESENCE_SESSION_ID = $SessionId
    $env:FRANCIS_UNREAL_PRESENCE_SELECTION_PATH = $selectionPath
    $env:FRANCIS_UNREAL_PRESENCE_STATUS_PATH = $rendererStatusPath
    $env:FRANCIS_UNREAL_PRESENCE_DEDUP_PATH = $rendererDedupPath
    $env:FRANCIS_UNREAL_PRESENCE_HOST_STATUS_PATH = $hostStatusPath
    $env:FRANCIS_UNREAL_PRESENCE_AUTO_INTENT = if ($AutoIntent) { "1" } else { "0" }
    $env:FRANCIS_UNREAL_PRESENCE_HOST_EXIT_AFTER_SECONDS = [string]$ExitAfterSeconds
    $env:FRANCIS_UNREAL_PRESENCE_EXIT_AFTER_SECONDS = [string]$ExitAfterSeconds
    if ($resolvedScreenshotPath) {
        $env:FRANCIS_UNREAL_PRESENCE_SCREENSHOT_PATH = $resolvedScreenshotPath
    } else {
        Remove-Item -LiteralPath "Env:FRANCIS_UNREAL_PRESENCE_SCREENSHOT_PATH" -ErrorAction SilentlyContinue
    }

    $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
    $python = if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        $venvPython
    } else {
        (Get-Command python -CommandType Application -ErrorAction Stop).Source
    }
    $hostProcess = Start-Process `
        -FilePath $python `
        -ArgumentList @("-m", "francis.unreal_presence_host") `
        -WorkingDirectory $repoRoot `
        -WindowStyle Hidden `
        -PassThru
    Start-Sleep -Milliseconds 750
    if ($hostProcess.HasExited) {
        throw "Francis Unreal presence host exited during startup with code $($hostProcess.ExitCode)."
    }

    $editorArguments = @(
        $projectPath,
        "-game",
        "-windowed",
        "-ResX=1440",
        "-ResY=900",
        "-NoSplash",
        "-NoLoadingScreen",
        "-Unattended"
    )
    $unrealProcess = Start-Process `
        -FilePath $editorPath `
        -ArgumentList $editorArguments `
        -WorkingDirectory (Split-Path -Parent $projectPath) `
        -PassThru
    Start-Sleep -Milliseconds 750
    if ($unrealProcess.HasExited) {
        throw "Unreal presence exited during startup with code $($unrealProcess.ExitCode)."
    }

    $receipt = [ordered]@{
        kind = "francis.grounded_presence.unreal_launch"
        schema_version = "francis.grounded_presence.unreal_launch.v1"
        launched_at = [DateTimeOffset]::UtcNow.ToString("o")
        project_path = $projectPath
        selection_path = $selectionPath
        engine_root = $engineRoot
        host_process_id = $hostProcess.Id
        unreal_process_id = $unrealProcess.Id
        adapter_id = $env:FRANCIS_UNREAL_PRESENCE_ADAPTER_ID
        session_id = $env:FRANCIS_UNREAL_PRESENCE_SESSION_ID
        authentication_key_id = $env:FRANCIS_UNREAL_PRESENCE_IPC_KEY_ID
        secret_persisted = $false
        renderer_status_path = $rendererStatusPath
        renderer_dedup_path = $rendererDedupPath
        host_status_path = $hostStatusPath
        screenshot_path = $resolvedScreenshotPath
        auto_intent = [bool]$AutoIntent
        bounded_test_runtime = $ExitAfterSeconds -gt 0
        authority = [ordered]@{
            francis_core_authoritative = $true
            grants_execution_authority = $false
            grants_desktop_authority = $false
            grants_network_authority = $false
            grants_memory_write_authority = $false
            grants_approval_authority = $false
        }
    }
    $receipt | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $temporaryReceipt -Encoding utf8NoBOM
    Move-Item -LiteralPath $temporaryReceipt -Destination $launchReceiptPath -Force
    $launchCommitted = $true

    [pscustomobject]@{
        Status = "started"
        HostProcessId = $hostProcess.Id
        UnrealProcessId = $unrealProcess.Id
        ProjectPath = $projectPath
        RendererStatusPath = $rendererStatusPath
        HostStatusPath = $hostStatusPath
        LaunchReceiptPath = $launchReceiptPath
        SecretPersisted = $false
    }
} catch {
    if (-not $launchCommitted) {
        Stop-OwnedProcess -Process $unrealProcess
        Stop-OwnedProcess -Process $hostProcess
        Remove-Item -LiteralPath $temporaryReceipt -Force -ErrorAction SilentlyContinue
    }
    throw
} finally {
    Restore-ProcessEnvironment -Snapshot $environmentSnapshot
}
