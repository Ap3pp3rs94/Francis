param(
    [int]$RefreshSeconds = 25,
    [int]$TailLines = 400,
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$WatcherRoot = "C:\Users\Ap3pp\.codex\automations\francis-thread-builder",
    [string]$SessionsRoot = "C:\Users\Ap3pp\.codex\sessions",
    [string]$ThreadId = "",
    [switch]$NoClear,
    [switch]$Once
)

$ErrorActionPreference = "Stop"
. (Join-Path $PSScriptRoot "francis-observer-lib.ps1")

$statePath = Join-Path $WatcherRoot "watch-state.json"
$pidPath = Join-Path $WatcherRoot "watch.pid"
$logPath = Join-Path $WatcherRoot "watch.log"
$stopPath = Join-Path $WatcherRoot "stop.flag"

while ($true) {
    $state = Read-FrancisJsonFile -Path $statePath
    $processInfo = Get-FrancisWatcherProcessInfo -PidPath $pidPath
    $sessionPath = Resolve-FrancisSessionPath -State $state -ThreadId $ThreadId -SessionsRoot $SessionsRoot
    $resolvedThreadId = if (-not [string]::IsNullOrWhiteSpace($ThreadId)) {
        $ThreadId
    } else {
        Get-FrancisThreadIdFromSessionPath -SessionFilePath $sessionPath
    }
    $session = Get-FrancisSessionSummary -SessionFilePath $sessionPath -TailLines $TailLines
    $git = Get-FrancisGitSummary -RepoRoot $RepoRoot
    $watcherLog = Get-FrancisWatcherLogSummary -LogPath $logPath
    $stopRequested = Test-Path -LiteralPath $stopPath

    $turnState = if ($session.TurnState -ne "missing" -and $session.TurnState -ne "unknown") {
        $session.TurnState
    } elseif ($state -and $state.ContainsKey("turn_state")) {
        [string]$state["turn_state"]
    } else {
        "unknown"
    }

    $lastTaskStarted = if (-not [string]::IsNullOrWhiteSpace($session.LastTaskStarted)) {
        [string]$session.LastTaskStarted
    } elseif ($state -and $state.ContainsKey("last_turn_started_at")) {
        $state["last_turn_started_at"]
    } else {
        ""
    }

    $lastTerminalAt = if (-not [string]::IsNullOrWhiteSpace($session.LastTerminalAt)) {
        [string]$session.LastTerminalAt
    } elseif ($state -and $state.ContainsKey("last_turn_terminal_at")) {
        $state["last_turn_terminal_at"]
    } else {
        ""
    }

    $lastTerminalType = if (-not [string]::IsNullOrWhiteSpace($session.LastTerminalType)) {
        [string]$session.LastTerminalType
    } elseif ($state -and $state.ContainsKey("last_turn_terminal_type")) {
        [string]$state["last_turn_terminal_type"]
    } else {
        ""
    }

    $watcherPidText = if ($processInfo.Pid) { [string]$processInfo.Pid } else { "-" }
    $threadIdText = if ($resolvedThreadId) { $resolvedThreadId } else { "-" }
    $launchCountText = if ($state -and $state.ContainsKey("launched")) { [string]$state["launched"] } else { "-" }
    $lastDecisionText = if ($state -and $state.ContainsKey("last_decision")) { [string]$state["last_decision"] } else { "-" }
    $lastLaunchVerifiedText = if ($state -and $state.ContainsKey("last_launch_verified")) { ([bool]$state["last_launch_verified"]).ToString().ToLowerInvariant() } else { "-" }
    $lastLaunchObservedStateText = if ($state -and $state.ContainsKey("last_launch_observed_state")) { [string]$state["last_launch_observed_state"] } else { "-" }
    $lastLaunchStartedText = Format-FrancisTimestamp -Timestamp $(if ($state -and $state.ContainsKey("last_launch_observed_started_at")) { $state["last_launch_observed_started_at"] } else { "" })
    $lastLaunchTerminalTypeText = if ($state -and $state.ContainsKey("last_launch_observed_terminal_type")) { [string]$state["last_launch_observed_terminal_type"] } else { "-" }
    $lastLaunchTerminalAtText = Format-FrancisTimestamp -Timestamp $(if ($state -and $state.ContainsKey("last_launch_observed_terminal_at")) { $state["last_launch_observed_terminal_at"] } else { "" })
    $lastWatcherLogText = if ($watcherLog.LastLaunchLine) { $watcherLog.LastLaunchLine } else { "-" }
    $lastTerminalTypeText = if ($lastTerminalType) { $lastTerminalType } else { "-" }
    $idleSecondsText = if ($state -and $state.ContainsKey("idle_seconds")) { [string]$state["idle_seconds"] } else { "-" }
    $sessionPathText = if ($sessionPath) { $sessionPath } else { "-" }
    $lastExecCommandText = if ($session.LastExecCommand) { Shorten-FrancisText -Text $session.LastExecCommand -MaxLength 140 } else { "-" }
    $lastExecAtText = Format-FrancisTimestamp -Timestamp ([string]$session.LastExecAt)
    $lastExecExitCodeText = if ($null -ne $session.LastExecExitCode) { [string]$session.LastExecExitCode } else { "-" }
    $lastBuildCommandText = if ($session.LastBuildCommand) { Shorten-FrancisText -Text $session.LastBuildCommand -MaxLength 140 } else { "-" }
    $lastBuildAtText = Format-FrancisTimestamp -Timestamp ([string]$session.LastBuildAt)
    $lastBuildExitCodeText = if ($null -ne $session.LastBuildExitCode) { [string]$session.LastBuildExitCode } else { "-" }
    $branchText = if ($git.Branch) { $git.Branch } else { "-" }
    $latestCommitText = if ($git.LatestCommit) { $git.LatestCommit } else { "-" }

    $lines = New-Object System.Collections.Generic.List[string]
    $lines.Add("Francis Live Observer")
    $lines.Add(("timestamp: {0}" -f (Get-Date).ToString("yyyy-MM-dd HH:mm:ss zzz")))
    $lines.Add(("refresh_seconds: {0}" -f $RefreshSeconds))
    $lines.Add("")
    $lines.Add("WATCHER")
    $lines.Add(("watcher_pid: {0}" -f $watcherPidText))
    $lines.Add(("watcher_alive: {0}" -f $processInfo.Alive.ToString().ToLowerInvariant()))
    $lines.Add(("watcher_stop_requested: {0}" -f $stopRequested.ToString().ToLowerInvariant()))
    $lines.Add(("thread_id: {0}" -f $threadIdText))
    $lines.Add(("launch_count: {0}" -f $launchCountText))
    $lines.Add(("last_launch_decision: {0}" -f $lastDecisionText))
    $lines.Add(("last_launch_verified: {0}" -f $lastLaunchVerifiedText))
    $lines.Add(("last_launch_observed_state: {0}" -f $lastLaunchObservedStateText))
    $lines.Add(("last_launch_started: {0}" -f $lastLaunchStartedText))
    $lines.Add(("last_launch_terminal: {0} @ {1}" -f $lastLaunchTerminalTypeText, $lastLaunchTerminalAtText))
    $lines.Add(("last_watcher_log: {0}" -f $lastWatcherLogText))
    $lines.Add("")
    $lines.Add("TURN")
    $lines.Add(("turn_state: {0}" -f $turnState))
    $lines.Add(("last_task_started: {0}" -f (Format-FrancisTimestamp -Timestamp $lastTaskStarted)))
    $lines.Add(("last_terminal: {0} @ {1}" -f $lastTerminalTypeText, (Format-FrancisTimestamp -Timestamp $lastTerminalAt)))
    $lines.Add(("idle_seconds: {0}" -f $idleSecondsText))
    $lines.Add(("last_session_file: {0}" -f $sessionPathText))
    $lines.Add("")
    $lines.Add("BUILD / TEST")
    $lines.Add(("last_exec_command: {0}" -f $lastExecCommandText))
    $lines.Add(("last_exec_at: {0}" -f $lastExecAtText))
    $lines.Add(("last_exec_exit_code: {0}" -f $lastExecExitCodeText))
    $lines.Add(("latest_build_or_test: {0}" -f $lastBuildCommandText))
    $lines.Add(("latest_build_or_test_at: {0}" -f $lastBuildAtText))
    $lines.Add(("test_status: {0}" -f $session.TestStatus))
    $lines.Add(("latest_build_or_test_exit_code: {0}" -f $lastBuildExitCodeText))
    $lines.Add("")
    $lines.Add("REPO")
    $lines.Add(("branch: {0}" -f $branchText))
    $lines.Add(("latest_commit: {0}" -f $latestCommitText))
    $lines.Add(("git_status: {0}" -f $git.StatusSummary))
    if ($git.StatusLines.Count -gt 0) {
        foreach ($statusLine in ($git.StatusLines | Select-Object -First 12)) {
            $lines.Add(("  {0}" -f $statusLine))
        }
    } else {
        $lines.Add("  clean")
    }
    $lines.Add("")
    $lines.Add("RECENT SESSION EVENTS")
    if ($session.RecentEvents.Count -gt 0) {
        foreach ($event in $session.RecentEvents) {
            $lines.Add(("  {0} | {1} | {2}" -f (Format-FrancisTimestamp -Timestamp ([string]$event.Timestamp)), [string]$event.Type, [string]$event.Summary))
        }
    } else {
        $lines.Add("  no recent task events found in tail window")
    }

    if (-not $NoClear) {
        Invoke-FrancisSafeClear
    }
    Write-Host ($lines -join [Environment]::NewLine)

    if ($Once) {
        break
    }

    Start-Sleep -Seconds $RefreshSeconds
}
