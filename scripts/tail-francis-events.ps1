param(
    [ValidateSet("watcher-log", "state", "session", "all")]
    [string]$Mode = "all",
    [int]$Lines = 40,
    [int]$RefreshSeconds = 5,
    [string]$WatcherRoot = "C:\Users\Ap3pp\.codex\automations\francis-thread-builder",
    [string]$SessionsRoot = "C:\Users\Ap3pp\.codex\sessions",
    [string]$ThreadId = "",
    [switch]$Follow,
    [switch]$RawSession,
    [switch]$NoClear
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "francis-observer-lib.ps1")

$statePath = Join-Path $WatcherRoot "watch-state.json"
$logPath = Join-Path $WatcherRoot "watch.log"

function Show-FrancisStateSnapshot {
    param([string]$Path)

    Write-Host "WATCHER STATE JSON"
    Write-Host "------------------"
    if (Test-Path -LiteralPath $Path) {
        Write-Host (Get-Content -LiteralPath $Path -Raw)
    } else {
        Write-Host "<missing>"
    }
}

function Show-FrancisSessionSnapshot {
    param(
        [hashtable]$State,
        [string]$ThreadId,
        [string]$SessionsRoot,
        [int]$Lines,
        [switch]$RawSession
    )

    $sessionPath = Resolve-FrancisSessionPath -State $State -ThreadId $ThreadId -SessionsRoot $SessionsRoot
    Write-Host "PINNED SESSION EVENTS"
    Write-Host "---------------------"
    Write-Host ("session_file: {0}" -f $(if ($sessionPath) { $sessionPath } else { "<missing>" }))

    if ([string]::IsNullOrWhiteSpace($sessionPath) -or -not (Test-Path -LiteralPath $sessionPath)) {
        Write-Host "<session unavailable>"
        return
    }

    if ($RawSession) {
        Get-Content -LiteralPath $sessionPath -Tail $Lines
        return
    }

    $summary = Get-FrancisSessionSummary -SessionFilePath $sessionPath -TailLines ([Math]::Max($Lines * 6, 120))
    if ($summary.RecentEvents.Count -eq 0) {
        Write-Host "<no recent task events found>"
        return
    }

    foreach ($event in ($summary.RecentEvents | Select-Object -Last $Lines)) {
        Write-Host ("{0} | {1} | {2}" -f (Format-FrancisTimestamp -Timestamp ([string]$event.Timestamp)), [string]$event.Type, [string]$event.Summary)
    }
}

if ($Mode -eq "watcher-log") {
    if ($Follow) {
        Get-Content -LiteralPath $logPath -Tail $Lines -Wait
    } else {
        Get-Content -LiteralPath $logPath -Tail $Lines
    }
    exit 0
}

while ($true) {
    $state = Read-FrancisJsonFile -Path $statePath

    if (-not $NoClear) {
        Invoke-FrancisSafeClear
    }

    switch ($Mode) {
        "state" {
            Show-FrancisStateSnapshot -Path $statePath
        }
        "session" {
            Show-FrancisSessionSnapshot -State $state -ThreadId $ThreadId -SessionsRoot $SessionsRoot -Lines $Lines -RawSession:$RawSession
        }
        "all" {
            Write-Host "WATCHER LOG"
            Write-Host "-----------"
            if (Test-Path -LiteralPath $logPath) {
                Get-Content -LiteralPath $logPath -Tail $Lines
            } else {
                Write-Host "<missing>"
            }
            Write-Host ""
            Show-FrancisStateSnapshot -Path $statePath
            Write-Host ""
            Show-FrancisSessionSnapshot -State $state -ThreadId $ThreadId -SessionsRoot $SessionsRoot -Lines $Lines -RawSession:$RawSession
        }
    }

    if (-not $Follow) {
        break
    }

    Start-Sleep -Seconds $RefreshSeconds
}
