param(
    [switch]$Run
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$sourcePath = Join-Path $PSScriptRoot "native_orb_state_probe.cpp"
$buildDir = Join-Path $PSScriptRoot "build"
$exePath = Join-Path $buildDir "native_orb_state_probe.exe"
$fixturePath = "schemas\native_orb_state_snapshot.fixture.json"

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

$objectPath = Join-Path $buildDir "native_orb_state_probe.obj"
$compileCommand = "call `"$vsDevCmd`" -arch=x64 >nul && cl.exe /nologo /std:c++17 /EHsc /W4 /permissive- /I`"$PSScriptRoot`" `"$sourcePath`" /Fo:`"$objectPath`" /Fe:`"$exePath`""
& $env:ComSpec /d /s /c $compileCommand
if ($LASTEXITCODE -ne 0) {
    throw "native Orb state probe build failed with exit code $LASTEXITCODE."
}

$runOutput = $null
if ($Run) {
    Push-Location $repoRoot
    try {
        $runOutput = (& $exePath $fixturePath) -join "`n"
        if ($LASTEXITCODE -ne 0) {
            throw "native Orb state probe run failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

[pscustomobject]@{
    status = "built"
    executable = $exePath
    source = $sourcePath
    fixture = $fixturePath
    ran = [bool]$Run
    output = $runOutput
} | ConvertTo-Json -Depth 3
