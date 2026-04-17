Set-StrictMode -Version Latest

function Read-FrancisJsonFile {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or -not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    try {
        return Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -AsHashtable
    } catch {
        return $null
    }
}

function Get-FrancisWatcherProcessInfo {
    param([string]$PidPath)

    $pidValue = $null
    if (-not [string]::IsNullOrWhiteSpace($PidPath) -and (Test-Path -LiteralPath $PidPath)) {
        $rawValue = (Get-Content -LiteralPath $PidPath -Raw).Trim()
        if ($rawValue -match '^\d+$') {
            $pidValue = [int]$rawValue
        }
    }

    $process = $null
    if ($pidValue) {
        try {
            $process = Get-Process -Id $pidValue -ErrorAction Stop
        } catch {
            $process = $null
        }
    }

    [pscustomobject]@{
        Pid         = $pidValue
        Alive       = $null -ne $process
        ProcessName = if ($process) { [string]$process.ProcessName } else { "" }
        StartedAt   = if ($process) { $process.StartTime.ToString("o") } else { "" }
    }
}

function Get-FrancisThreadIdFromSessionPath {
    param([string]$SessionFilePath)

    if ([string]::IsNullOrWhiteSpace($SessionFilePath)) {
        return ""
    }

    if ($SessionFilePath -match '([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.jsonl$') {
        return [string]$matches[1]
    }

    return ""
}

function Read-FrancisSessionPin {
    param(
        [string]$SessionPinPath
    )

    if ([string]::IsNullOrWhiteSpace($SessionPinPath) -or -not (Test-Path -LiteralPath $SessionPinPath)) {
        return ""
    }

    try {
        return (Get-Content -LiteralPath $SessionPinPath -Raw).Trim()
    } catch {
        return ""
    }
}

function Resolve-FrancisSessionBinding {
    param(
        [hashtable]$State,
        [string]$SessionFilePath = "",
        [string]$SessionPinPath = ""
    )

    if (-not [string]::IsNullOrWhiteSpace($SessionFilePath)) {
        return [pscustomobject]@{
            Path   = $SessionFilePath
            Source = if (Test-Path -LiteralPath $SessionFilePath) { "explicit_param" } else { "explicit_param_missing" }
            Valid  = (Test-Path -LiteralPath $SessionFilePath)
        }
    }

    $pinnedPath = Read-FrancisSessionPin -SessionPinPath $SessionPinPath
    if (-not [string]::IsNullOrWhiteSpace($pinnedPath)) {
        return [pscustomobject]@{
            Path   = $pinnedPath
            Source = if (Test-Path -LiteralPath $pinnedPath) { "pin_file" } else { "pin_file_missing" }
            Valid  = (Test-Path -LiteralPath $pinnedPath)
        }
    }

    if ($State -and $State.ContainsKey("last_seen_session_file")) {
        $statePath = [string]$State["last_seen_session_file"]
        if (-not [string]::IsNullOrWhiteSpace($statePath)) {
            return [pscustomobject]@{
                Path   = $statePath
                Source = if (Test-Path -LiteralPath $statePath) { "state_last_seen" } else { "state_last_seen_missing" }
                Valid  = (Test-Path -LiteralPath $statePath)
            }
        }
    }

    return [pscustomobject]@{
        Path   = ""
        Source = "unresolved"
        Valid  = $false
    }
}

function Resolve-FrancisSessionPath {
    param(
        [hashtable]$State,
        [string]$SessionFilePath = "",
        [string]$SessionPinPath = ""
    )

    $binding = Resolve-FrancisSessionBinding -State $State -SessionFilePath $SessionFilePath -SessionPinPath $SessionPinPath
    if ($binding.Valid) {
        return [string]$binding.Path
    }

    return ""
}

function ConvertFrom-FrancisJsonLine {
    param([string]$Line)

    if ([string]::IsNullOrWhiteSpace($Line)) {
        return $null
    }

    try {
        return $Line | ConvertFrom-Json -Depth 100
    } catch {
        return $null
    }
}

function Get-FrancisCommandText {
    param($Command)

    if ($null -eq $Command) {
        return ""
    }

    if ($Command -is [string]) {
        return $Command.Trim()
    }

    if ($Command -is [System.Collections.IEnumerable]) {
        $parts = @()
        foreach ($part in $Command) {
            $parts += [string]$part
        }
        return ($parts -join " ").Trim()
    }

    return ([string]$Command).Trim()
}

function Test-FrancisBuildCommand {
    param([string]$CommandText)

    if ([string]::IsNullOrWhiteSpace($CommandText)) {
        return $false
    }

    $patterns = @(
        'pytest',
        'ruff',
        'mypy',
        'npm test',
        'npm run test',
        'npm run build',
        'pnpm test',
        'pnpm run test',
        'pnpm build',
        'pnpm run build',
        'vitest',
        'playwright test',
        'go test',
        'cargo test',
        'dotnet test'
    )

    foreach ($pattern in $patterns) {
        if ($CommandText -match [regex]::Escape($pattern)) {
            return $true
        }
    }

    return $false
}

function Get-FrancisCommandKind {
    param([string]$CommandText)

    if ([string]::IsNullOrWhiteSpace($CommandText)) {
        return ""
    }

    if ($CommandText -match 'build') {
        return "build"
    }
    if ($CommandText -match 'test|pytest|vitest|mypy|ruff|playwright') {
        return "test"
    }

    return "command"
}

function ConvertTo-FrancisDateTimeOffset {
    param($Timestamp)

    if ($null -eq $Timestamp) {
        return $null
    }

    if ($Timestamp -is [DateTimeOffset]) {
        return $Timestamp
    }

    if ($Timestamp -is [DateTime]) {
        return [DateTimeOffset]$Timestamp
    }

    $timestampText = [string]$Timestamp
    if ([string]::IsNullOrWhiteSpace($timestampText)) {
        return $null
    }

    try {
        return [DateTimeOffset]::Parse($timestampText)
    } catch {
        return $null
    }
}

function Format-FrancisTimestamp {
    param($Timestamp)

    $parsed = ConvertTo-FrancisDateTimeOffset -Timestamp $Timestamp
    if ($null -eq $parsed) {
        return "-"
    }

    return $parsed.ToLocalTime().ToString("yyyy-MM-dd HH:mm:ss zzz")
}

function Shorten-FrancisText {
    param(
        [string]$Text,
        [int]$MaxLength = 120
    )

    if ([string]::IsNullOrWhiteSpace($Text)) {
        return ""
    }

    if ($Text.Length -le $MaxLength) {
        return $Text
    }

    return "{0}..." -f $Text.Substring(0, [Math]::Max(0, $MaxLength - 3))
}

function Get-FrancisEventSummary {
    param($Item)

    if ($null -eq $Item -or $null -eq $Item.payload) {
        return ""
    }

    $eventType = [string]$Item.payload.type
    switch ($eventType) {
        "task_started" {
            return "turn started"
        }
        "task_complete" {
            return "turn completed"
        }
        "turn_aborted" {
            return "turn aborted"
        }
        "exec_command_end" {
            $commandText = Get-FrancisCommandText -Command $Item.payload.command
            $exitCode = if ($null -ne $Item.payload.exit_code) { [string]$Item.payload.exit_code } else { "?" }
            return "exit=$exitCode :: $(Shorten-FrancisText -Text $commandText -MaxLength 110)"
        }
        default {
            return $eventType
        }
    }
}

function Get-FrancisSessionSummary {
    param(
        [string]$SessionFilePath,
        [int]$TailLines = 400
    )

    $summary = [ordered]@{
        Exists            = $false
        SessionFilePath   = $SessionFilePath
        LastTaskStarted   = ""
        LastTerminalAt    = ""
        LastTerminalType  = ""
        TurnState         = "missing"
        LastExecAt        = ""
        LastExecCommand   = ""
        LastExecExitCode  = $null
        LastBuildAt       = ""
        LastBuildCommand  = ""
        LastBuildExitCode = $null
        LastBuildKind     = ""
        TestStatus        = "not_run"
        RecentEvents      = @()
    }

    if ([string]::IsNullOrWhiteSpace($SessionFilePath) -or -not (Test-Path -LiteralPath $SessionFilePath)) {
        return [pscustomobject]$summary
    }

    $summary["Exists"] = $true
    $interestingEvents = New-Object System.Collections.Generic.List[object]

    try {
        $lines = @(Get-Content -LiteralPath $SessionFilePath -Tail $TailLines -ErrorAction Stop)
    } catch {
        return [pscustomobject]$summary
    }

    foreach ($line in $lines) {
        $item = ConvertFrom-FrancisJsonLine -Line ([string]$line)
        if ($null -eq $item -or [string]$item.type -ne "event_msg" -or $null -eq $item.payload) {
            continue
        }

        $timestamp = [string]$item.timestamp
        $eventType = [string]$item.payload.type
        if ([string]::IsNullOrWhiteSpace($eventType)) {
            continue
        }

        switch ($eventType) {
            "task_started" {
                $summary["LastTaskStarted"] = $timestamp
            }
            "task_complete" {
                $summary["LastTerminalAt"] = $timestamp
                $summary["LastTerminalType"] = $eventType
            }
            "turn_aborted" {
                $summary["LastTerminalAt"] = $timestamp
                $summary["LastTerminalType"] = $eventType
            }
            "exec_command_end" {
                $commandText = Get-FrancisCommandText -Command $item.payload.command
                $exitCode = $null
                if ($null -ne $item.payload.exit_code) {
                    try {
                        $exitCode = [int]$item.payload.exit_code
                    } catch {
                        $exitCode = $null
                    }
                }

                $summary["LastExecAt"] = $timestamp
                $summary["LastExecCommand"] = $commandText
                $summary["LastExecExitCode"] = $exitCode

                if (Test-FrancisBuildCommand -CommandText $commandText) {
                    $summary["LastBuildAt"] = $timestamp
                    $summary["LastBuildCommand"] = $commandText
                    $summary["LastBuildExitCode"] = $exitCode
                    $summary["LastBuildKind"] = Get-FrancisCommandKind -CommandText $commandText
                    if ($null -eq $exitCode) {
                        $summary["TestStatus"] = "unknown"
                    } elseif ($exitCode -eq 0) {
                        $summary["TestStatus"] = "passed"
                    } else {
                        $summary["TestStatus"] = "failed"
                    }
                }
            }
        }

        if ($eventType -in @("task_started", "task_complete", "turn_aborted", "exec_command_end")) {
            $interestingEvents.Add([pscustomobject]@{
                Timestamp = $timestamp
                Type      = $eventType
                Summary   = Get-FrancisEventSummary -Item $item
            })
        }
    }

    $startedAt = ConvertTo-FrancisDateTimeOffset -Timestamp ([string]$summary["LastTaskStarted"])
    $terminalAt = ConvertTo-FrancisDateTimeOffset -Timestamp ([string]$summary["LastTerminalAt"])

    if ($null -ne $startedAt -and ($null -eq $terminalAt -or $startedAt -gt $terminalAt)) {
        $summary["TurnState"] = "active"
    } elseif ($null -ne $terminalAt) {
        $summary["TurnState"] = "idle"
    } else {
        $summary["TurnState"] = "unknown"
    }

    $summary["RecentEvents"] = @($interestingEvents | Select-Object -Last 10)
    return [pscustomobject]$summary
}

function Get-FrancisWatcherLogSummary {
    param(
        [string]$LogPath,
        [int]$TailLines = 120
    )

    if ([string]::IsNullOrWhiteSpace($LogPath) -or -not (Test-Path -LiteralPath $LogPath)) {
        return [pscustomobject]@{
            LastLaunchLine = ""
            LastLine       = ""
        }
    }

    $lines = @(Get-Content -LiteralPath $LogPath -Tail $TailLines -ErrorAction SilentlyContinue)
    $launchLines = @($lines | Where-Object { $_ -match 'launch_|stop\.flag|watcher_' })

    [pscustomobject]@{
        LastLaunchLine = if ($launchLines.Count -gt 0) { [string]$launchLines[-1] } else { "" }
        LastLine       = if ($lines.Count -gt 0) { [string]$lines[-1] } else { "" }
    }
}

function Get-FrancisGitSummary {
    param([string]$RepoRoot)

    $branch = ((& git -C $RepoRoot branch --show-current 2>$null) | Out-String).Trim()
    $commit = ((& git -C $RepoRoot log -1 --oneline 2>$null) | Out-String).Trim()
    $statusLines = @(& git -C $RepoRoot status --short 2>$null)

    [pscustomobject]@{
        Branch        = $branch
        LatestCommit  = $commit
        Dirty         = $statusLines.Count -gt 0
        StatusSummary = if ($statusLines.Count -gt 0) { "dirty ($($statusLines.Count) file entries)" } else { "clean" }
        StatusLines   = $statusLines
    }
}

function Invoke-FrancisSafeClear {
    try {
        Clear-Host
    } catch {
        # Non-interactive shells can reject cursor resets; the observer should keep running.
    }
}
