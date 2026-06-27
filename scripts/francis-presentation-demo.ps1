param(
    [int]$X = 320,
    [int]$Y = 240,
    [string]$DemoText = "Francis presentation dry-run",
    [string]$OutDir = ".francis\presentation\demos",
    [switch]$SkipMcpSmoke,
    [switch]$SkipOrbDryRun
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

function Resolve-FrancisPath {
    param([string]$Path)

    if ([System.IO.Path]::IsPathRooted($Path)) {
        return $Path
    }

    return Join-Path $RepoRoot $Path
}

function ConvertFrom-JsonOrNull {
    param([string]$Text)

    try {
        return $Text | ConvertFrom-Json -ErrorAction Stop
    }
    catch {
        return $null
    }
}

function Get-SmokeValue {
    param(
        [string]$Text,
        [string]$Name
    )

    $Pattern = "(?m)^\s*$([regex]::Escape($Name)):\s*(.+?)\s*$"
    $Match = [regex]::Match($Text, $Pattern)
    if (-not $Match.Success) {
        return $null
    }

    return $Match.Groups[1].Value.Trim()
}

function ConvertTo-DemoBool {
    param([object]$Value)

    if ($null -eq $Value) {
        return $false
    }

    if ($Value -is [bool]) {
        return [bool]$Value
    }

    return @("true", "True", "1", "yes", "Yes") -contains ([string]$Value)
}

function Invoke-ExternalCommand {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    $global:LASTEXITCODE = 0
    try {
        $Output = & $Command 2>&1
        $ExitCode = if ($null -ne $global:LASTEXITCODE) { [int]$global:LASTEXITCODE } else { 0 }
        return [ordered]@{
            name = $Name
            exit_code = $ExitCode
            text = (($Output | Out-String).Trim())
            error = $null
        }
    }
    catch {
        return [ordered]@{
            name = $Name
            exit_code = 1
            text = ""
            error = $_.Exception.Message
        }
    }
}

Push-Location $RepoRoot
try {
    $GeneratedAt = (Get-Date).ToUniversalTime().ToString("o")
    $Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMdd-HHmmss")
    $OutputRoot = Resolve-FrancisPath -Path $OutDir
    New-Item -ItemType Directory -Path $OutputRoot -Force | Out-Null

    $Commit = (& git rev-parse --short HEAD 2>$null | Out-String).Trim()
    if (-not $Commit) {
        $Commit = "unavailable"
    }

    $Branch = (& git branch --show-current 2>$null | Out-String).Trim()
    if (-not $Branch) {
        $Branch = "unavailable"
    }

    $GitStatusLines = @(& git status --short 2>$null)
    $WorkingTreeStatus = if ($GitStatusLines.Count -eq 0) { "clean" } else { "dirty" }

    $Failures = New-Object System.Collections.Generic.List[string]

    $CompletionCommand = Invoke-ExternalCommand -Name "completion_model" -Command {
        & (Join-Path $RepoRoot "scripts\francis-completion-model.ps1") -Mode Status
    }
    $Completion = ConvertFrom-JsonOrNull -Text $CompletionCommand.text
    $CompletionSummary = [ordered]@{
        command = "scripts/francis-completion-model.ps1 -Mode Status"
        exit_code = $CompletionCommand.exit_code
        ok = $false
        status = "unavailable"
        current_phase = ""
        latest_ledger_entry = ""
        latest_remaining_gap = ""
        stage17_status = ""
        read_only_contract = $false
        writes_repo = $true
        writes_data = $true
        grants_execution_authority = $true
        plane_readiness_snapshot = @()
        error = $CompletionCommand.error
    }
    if ($null -ne $Completion) {
        $CompletionSummary.ok = ConvertTo-DemoBool -Value $Completion.ok
        $CompletionSummary.status = [string]$Completion.status
        $CompletionSummary.current_phase = [string]$Completion.current_phase
        $CompletionSummary.latest_ledger_entry = [string]$Completion.latest_ledger_entry.title
        $CompletionSummary.latest_remaining_gap = [string]$Completion.latest_ledger_entry.remaining_truthful_gap
        $CompletionSummary.stage17_status = [string]$Completion.stage17_status.status
        $CompletionSummary.read_only_contract = ConvertTo-DemoBool -Value $Completion.read_only_contract
        $CompletionSummary.writes_repo = ConvertTo-DemoBool -Value $Completion.writes_repo
        $CompletionSummary.writes_data = ConvertTo-DemoBool -Value $Completion.writes_data
        $CompletionSummary.grants_execution_authority = ConvertTo-DemoBool -Value $Completion.grants_execution_authority
        $CompletionSummary.plane_readiness_snapshot = @($Completion.plane_readiness_snapshot)
    }
    if ($CompletionCommand.exit_code -ne 0 -or -not $CompletionSummary.ok) {
        $Failures.Add("completion_model_readback_failed")
    }

    $McpSummary = [ordered]@{
        skipped = [bool]$SkipMcpSmoke
        command = "python -m francis.mcp_gateway.smoke"
        exit_code = $null
        ok = $null
        tool_count = $null
        health_status = $null
        screen_status = $null
        takeover_status = $null
        input_status = $null
        unapproved_takeover_refused = $null
        unapproved_input_refused = $null
        raw_output = ""
        error = $null
    }
    if (-not $SkipMcpSmoke) {
        $McpCommand = Invoke-ExternalCommand -Name "mcp_gateway_smoke" -Command {
            & $Python -m francis.mcp_gateway.smoke
        }
        $McpSummary.exit_code = $McpCommand.exit_code
        $McpSummary.raw_output = $McpCommand.text
        $McpSummary.error = $McpCommand.error
        $McpSummary.ok = ConvertTo-DemoBool -Value (Get-SmokeValue -Text $McpCommand.text -Name "ok")
        $McpSummary.tool_count = [int](Get-SmokeValue -Text $McpCommand.text -Name "tool_count")
        $McpSummary.health_status = Get-SmokeValue -Text $McpCommand.text -Name "health_status"
        $McpSummary.screen_status = Get-SmokeValue -Text $McpCommand.text -Name "screen_status"
        $McpSummary.takeover_status = Get-SmokeValue -Text $McpCommand.text -Name "takeover_status"
        $McpSummary.input_status = Get-SmokeValue -Text $McpCommand.text -Name "input_status"
        $McpSummary.unapproved_takeover_refused = ConvertTo-DemoBool -Value (Get-SmokeValue -Text $McpCommand.text -Name "unapproved_takeover_refused")
        $McpSummary.unapproved_input_refused = ConvertTo-DemoBool -Value (Get-SmokeValue -Text $McpCommand.text -Name "unapproved_input_refused")
        if ($McpCommand.exit_code -ne 0 -or -not $McpSummary.ok -or -not $McpSummary.unapproved_takeover_refused -or -not $McpSummary.unapproved_input_refused) {
            $Failures.Add("mcp_gateway_smoke_failed")
        }
    }

    $OrbSummary = [ordered]@{
        skipped = [bool]$SkipOrbDryRun
        command = "scripts/orb-operator-dry-run.ps1 -X $X -Y $Y -Text <redacted>"
        exit_code = $null
        ok = $null
        status = $null
        mode = $null
        sequence_count = $null
        receipt_paths = @()
        live_input_performed = $null
        raw_input = $null
        input_execution_attempted = $null
        text_length = $DemoText.Length
        raw_output_path = ""
        error = $null
    }
    $OrbRawPath = Join-Path $OutputRoot "francis-presentation-demo-$Stamp-orb.json"
    if (-not $SkipOrbDryRun) {
        $OrbCommand = Invoke-ExternalCommand -Name "orb_operator_dry_run" -Command {
            & (Join-Path $RepoRoot "scripts\orb-operator-dry-run.ps1") -X $X -Y $Y -Text $DemoText
        }
        $OrbSummary.exit_code = $OrbCommand.exit_code
        $OrbSummary.error = $OrbCommand.error
        $OrbCommand.text | Set-Content -LiteralPath $OrbRawPath -Encoding utf8
        $OrbSummary.raw_output_path = $OrbRawPath
        $Orb = ConvertFrom-JsonOrNull -Text $OrbCommand.text
        if ($null -ne $Orb) {
            $OrbSummary.ok = ConvertTo-DemoBool -Value $Orb.ok
            $OrbSummary.status = [string]$Orb.status
            $OrbSummary.mode = [string]$Orb.mode
            $OrbSummary.sequence_count = [int]$Orb.governance.sequence_count
            $OrbSummary.receipt_paths = @($Orb.receipt_paths)
            $OrbLiveValues = @($Orb.results | ForEach-Object { ConvertTo-DemoBool -Value $_.governance.live_input_performed })
            $OrbRawValues = @($Orb.results | ForEach-Object { ConvertTo-DemoBool -Value $_.governance.raw_input })
            $OrbAttemptValues = @($Orb.results | ForEach-Object { ConvertTo-DemoBool -Value $_.governance.input_execution_attempted })
            $OrbSummary.live_input_performed = ($OrbLiveValues -contains $true)
            $OrbSummary.raw_input = ($OrbRawValues -contains $true)
            $OrbSummary.input_execution_attempted = ($OrbAttemptValues -contains $true)
        }
        if (
            $OrbCommand.exit_code -ne 0 -or
            -not $OrbSummary.ok -or
            $OrbSummary.live_input_performed -or
            $OrbSummary.raw_input -or
            $OrbSummary.input_execution_attempted
        ) {
            $Failures.Add("orb_dry_run_failed_or_attempted_live_input")
        }
    }

    $SummaryPath = Join-Path $OutputRoot "francis-presentation-demo-$Stamp.json"
    $ReportPath = Join-Path $OutputRoot "francis-presentation-demo-$Stamp.md"
    $Summary = [ordered]@{
        ok = ($Failures.Count -eq 0)
        generated_at = $GeneratedAt
        repo = [ordered]@{
            root = [string]$RepoRoot
            branch = $Branch
            commit = $Commit
            working_tree = $WorkingTreeStatus
        }
        scope = [ordered]@{
            demo_kind = "readback_and_dry_run"
            starts_servers = $false
            live_input = $false
            writes_repo = $false
            writes_runtime_artifacts = $true
            output_root = $OutputRoot
        }
        completion_model = $CompletionSummary
        mcp_gateway_smoke = $McpSummary
        orb_operator_dry_run = $OrbSummary
        guardrails = @(
            "This demo does not claim finished autonomy.",
            "This demo does not move the physical cursor or type into a live app.",
            "This demo does not grant proposal, promotion, execution, or memory-write authority.",
            "Receipt paths are evidence of attempted governed dry-run actions."
        )
        failures = @($Failures)
        artifacts = [ordered]@{
            summary_json = $SummaryPath
            report_markdown = $ReportPath
            orb_raw_json = $OrbRawPath
        }
    }

    $Summary | ConvertTo-Json -Depth 10 | Set-Content -LiteralPath $SummaryPath -Encoding utf8

    $PlaneLines = @()
    foreach ($Plane in @($CompletionSummary.plane_readiness_snapshot)) {
        $PlaneLines += "- $($Plane.plane): $($Plane.status)"
    }
    if ($PlaneLines.Count -eq 0) {
        $PlaneLines = @("- unavailable")
    }

    $ReceiptLines = @()
    foreach ($ReceiptPath in @($OrbSummary.receipt_paths)) {
        $ReceiptLines += "- $ReceiptPath"
    }
    if ($ReceiptLines.Count -eq 0) {
        $ReceiptLines = @("- unavailable or skipped")
    }

    $Report = @(
        "# Francis Presentation Demo Evidence",
        "",
        "Generated: $GeneratedAt",
        "Repository: $RepoRoot",
        "Branch: $Branch",
        "Commit: $Commit",
        "Working tree: $WorkingTreeStatus",
        "",
        "## Demo Scope",
        "",
        "This presentation run is readback plus dry-run only. It does not start servers, move the physical cursor, type into a live app, grant execution authority, approve proposals, promote capabilities, or write repo files.",
        "",
        "## 30 Second Story",
        "",
        "Francis is a local-first governed operator layer. The demo shows the current posture readback, the MCP governance smoke path, and Orb-as-operator-body dry-run receipts. The point is not that Francis is finished. The point is that the project already treats action as something that must be proposed, gated, traced, and receipted.",
        "",
        "## Evidence Summary",
        "",
        "- Overall demo status: $($Summary.ok)",
        "- Completion model status: $($CompletionSummary.status)",
        "- Current phase: $($CompletionSummary.current_phase)",
        "- Latest ledger entry: $($CompletionSummary.latest_ledger_entry)",
        "- Stage 17 status: $($CompletionSummary.stage17_status)",
        "- MCP smoke ok: $($McpSummary.ok)",
        "- MCP tool count: $($McpSummary.tool_count)",
        "- Unapproved takeover refused: $($McpSummary.unapproved_takeover_refused)",
        "- Unapproved input refused: $($McpSummary.unapproved_input_refused)",
        "- Orb dry-run ok: $($OrbSummary.ok)",
        "- Orb dry-run sequence count: $($OrbSummary.sequence_count)",
        "- Orb live input performed: $($OrbSummary.live_input_performed)",
        "- Orb raw input exposed: $($OrbSummary.raw_input)",
        "- Orb input execution attempted: $($OrbSummary.input_execution_attempted)",
        "",
        "## Plane Readiness Readback",
        "",
        $PlaneLines,
        "",
        "## Orb Operator Receipt Paths",
        "",
        $ReceiptLines,
        "",
        "## Allowed Claims",
        "",
        "- Francis has a real repository, runtime, tests, docs, and ledger-backed build posture.",
        "- Francis separates proposal, governance, identity, execution, observability, and memory.",
        "- Francis can produce receipt-backed Orb operator dry-runs for move, click, and type intents.",
        "- The MCP smoke path proves unapproved takeover and input attempts are refused in this environment.",
        "",
        "## Claims Not Allowed",
        "",
        "- Do not claim finished autonomous desktop operation.",
        "- Do not claim the Orb moved the live cursor in this demo.",
        "- Do not claim keyboard text was typed into a live app.",
        "- Do not claim Stage 6, Stage 17, ORB Core, or full Francis product readiness is closed.",
        "",
        "## Artifacts",
        "",
        "- Summary JSON: $SummaryPath",
        "- Report Markdown: $ReportPath",
        "- Orb raw JSON: $OrbRawPath",
        "",
        "## Raw MCP Smoke Output",
        "",
        '```text',
        $McpSummary.raw_output,
        '```'
    )
    $Report | Set-Content -LiteralPath $ReportPath -Encoding utf8

    $Summary | ConvertTo-Json -Depth 10
    if ($Failures.Count -gt 0) {
        exit 1
    }
}
finally {
    Pop-Location
}
