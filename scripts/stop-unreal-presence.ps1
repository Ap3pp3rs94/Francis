[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$receiptPath = Join-Path $repoRoot "data\runtime\unreal-presence\launch.json"
if (-not (Test-Path -LiteralPath $receiptPath -PathType Leaf)) {
    [pscustomobject]@{ Status = "not_running"; ReceiptPath = $receiptPath }
    return
}

$receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
$targets = @(
    [pscustomobject]@{ Id = [int]$receipt.host_process_id; Kind = "host" },
    [pscustomobject]@{ Id = [int]$receipt.unreal_process_id; Kind = "unreal" }
)
$stopped = @()
foreach ($target in $targets) {
    $process = Get-CimInstance Win32_Process -Filter "ProcessId = $($target.Id)" -ErrorAction SilentlyContinue
    if (-not $process) {
        continue
    }
    $matches = if ($target.Kind -eq "host") {
        $process.CommandLine -match "francis\.unreal_presence_host"
    } else {
        $process.Name -eq "UnrealEditor.exe" -and $process.CommandLine -match "FrancisPresence\.uproject"
    }
    if (-not $matches) {
        throw "Refusing to stop PID $($target.Id): command line no longer matches the recorded $($target.Kind) process."
    }
    Stop-Process -Id $target.Id
    Wait-Process -Id $target.Id -Timeout 15 -ErrorAction SilentlyContinue
    $stopped += $target.Id
}

[pscustomobject]@{
    Status = "stopped"
    StoppedProcessIds = $stopped
    ReceiptPath = $receiptPath
}
