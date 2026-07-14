param(
    [switch]$Run,
    [switch]$Launch,
    [int]$RunSeconds = 600,
    [int]$Size = 270,
    [int]$X = -1,
    [int]$Y = -1,
    [string]$Snapshot = "schemas\native_orb_state_snapshot.fixture.json",
    [string]$RuntimeDir = ""
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourcePath = Join-Path $PSScriptRoot "native_orb_renderer.cpp"
$buildDir = Join-Path $PSScriptRoot "build"
$exePath = Join-Path $buildDir "native_orb_renderer.exe"
$runtimeDir = if ([string]::IsNullOrWhiteSpace($RuntimeDir)) { Join-Path $repoRoot "data\runtime\native-orb-renderer" } else { [System.IO.Path]::GetFullPath($RuntimeDir) }
$pidPath = Join-Path $runtimeDir "native-orb-renderer.pid"
$statusPath = Join-Path $runtimeDir "status.json"

$programFilesX86 = ${env:ProgramFiles(x86)}
if ([string]::IsNullOrWhiteSpace($programFilesX86)) {
    throw "ProgramFiles(x86) is not available; Visual Studio Build Tools cannot be located."
}

$vsWhere = Join-Path $programFilesX86 "Microsoft Visual Studio\Installer\vswhere.exe"
if (-not (Test-Path -LiteralPath $vsWhere)) {
    throw "vswhere.exe was not found. Install Visual Studio Build Tools with MSVC C++ tools."
}

$vsInstall = (& $vsWhere -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath)
if ([string]::IsNullOrWhiteSpace($vsInstall)) {
    throw "MSVC C++ Build Tools were not found."
}

$vsDevCmd = Join-Path $vsInstall "Common7\Tools\VsDevCmd.bat"
if (-not (Test-Path -LiteralPath $vsDevCmd)) {
    throw "VsDevCmd.bat was not found in the selected Visual Studio installation."
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null

$objectPath = Join-Path $buildDir "native_orb_renderer.obj"
$compileCommand = "call `"$vsDevCmd`" -arch=x64 >nul && cl.exe /nologo /std:c++17 /EHsc /W4 /permissive- /I`"$PSScriptRoot`" `"$sourcePath`" /Fo:`"$objectPath`" /Fe:`"$exePath`" /link /SUBSYSTEM:WINDOWS gdiplus.lib user32.lib gdi32.lib shell32.lib"
& $env:ComSpec /d /s /c $compileCommand
if ($LASTEXITCODE -ne 0) {
    throw "native Orb renderer build failed with exit code $LASTEXITCODE."
}

$runOutput = $null
$processId = $null
$launched = $false
if ($Run -and $Launch) {
    throw "Use either -Run or -Launch, not both."
}

if ($Run) {
    Push-Location $repoRoot
    try {
        & $exePath --snapshot $Snapshot --run-seconds $RunSeconds --size $Size
        if ($LASTEXITCODE -ne 0) {
            throw "native Orb renderer run failed with exit code $LASTEXITCODE."
        }
        $runOutput = "completed"
    }
    finally {
        Pop-Location
    }
}

if ($Launch) {
    $arguments = @("--snapshot", $Snapshot, "--run-seconds", [string]$RunSeconds, "--size", [string]$Size, "--runtime-dir", $runtimeDir)
    if ($X -ge 0) {
        $arguments += @("--x", [string]$X)
    }
    if ($Y -ge 0) {
        $arguments += @("--y", [string]$Y)
    }
    $process = Start-Process -FilePath $exePath -ArgumentList $arguments -WorkingDirectory $repoRoot -PassThru
    $processId = $process.Id
    $launched = $true

    $launchedAtUtc = [DateTime]::UtcNow
    $expiresAtUtc = $launchedAtUtc.AddSeconds($RunSeconds)
    New-Item -ItemType Directory -Force -Path $runtimeDir | Out-Null
    Set-Content -LiteralPath $pidPath -Value ([string]$processId) -Encoding ascii
    [pscustomobject]@{
        kind = "francis.native_orb_renderer.runtime_status"
        schema_version = "francis.native_orb_renderer.runtime_status.v1"
        status = "running"
        active_renderer = $true
        renderer = "native_cpp_orb_renderer"
        body_renderer_only = $true
        render_only = $true
        authority_granted = $false
        accepts_mutation_events = $false
        controls_user_os_cursor = $false
        can_click = $false
        can_drag = $false
        can_type = $false
        process_id = $processId
        executable = $exePath
        snapshot = $Snapshot
        size = $Size
        x = $X
        y = $Y
        run_seconds = $RunSeconds
        runtime_dir = $runtimeDir
        right_click_request_path = Join-Path $runtimeDir "right-click-request.json"
        native_right_click_request_supported = $true
        can_open_backend_surface_directly = $false
        right_click_opens_local_ui_panel = $true
        native_local_ui_panel_supported = $true
        native_local_ui_panel_open_mode = "native_cpp_panel"
        launched_at_utc = $launchedAtUtc.ToString("o")
        expires_at_utc = $expiresAtUtc.ToString("o")
        liveness_truth = "launcher_pid_observation_only"
    } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $statusPath -Encoding utf8
}

[pscustomobject]@{
    status = "built"
    executable = $exePath
    source = $sourcePath
    snapshot = $Snapshot
    run_seconds = $RunSeconds
    size = $Size
    ran = [bool]$Run
    launched = $launched
    process_id = $processId
    runtime_status_path = $statusPath
    pid_path = $pidPath
    output = $runOutput
} | ConvertTo-Json -Depth 3
