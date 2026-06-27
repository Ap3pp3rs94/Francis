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

function ConvertTo-HtmlText {
    param([object]$Value)

    return [System.Net.WebUtility]::HtmlEncode([string]$Value)
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
    $VisualPath = Join-Path $OutputRoot "francis-presentation-demo-$Stamp.html"
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
            visual_html = $VisualPath
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
        "- Visual HTML: $VisualPath",
        "- Orb raw JSON: $OrbRawPath",
        "",
        "## Raw MCP Smoke Output",
        "",
        '```text',
        $McpSummary.raw_output,
        '```'
    )
    $Report | Set-Content -LiteralPath $ReportPath -Encoding utf8

    $PlaneCards = New-Object System.Collections.Generic.List[string]
    $PlaneProvenCount = 0
    $PlaneActiveCount = 0
    $PlaneEarlyCount = 0
    foreach ($Plane in @($CompletionSummary.plane_readiness_snapshot)) {
        $StatusText = [string]$Plane.status
        $StatusClass = "status-active"
        $CategoryLabel = "Active build"
        if ($StatusText -match "materially real|strongest") {
            $StatusClass = "status-ready"
            $CategoryLabel = "Proven strength"
            $PlaneProvenCount += 1
        }
        elseif ($StatusText -match "early|roadmap") {
            $StatusClass = "status-early"
            $CategoryLabel = if ($StatusText -match "roadmap") { "Roadmap" } else { "Early capability" }
            $PlaneEarlyCount += 1
        }
        else {
            $PlaneActiveCount += 1
        }
        $PlaneCards.Add("<li><span>$(ConvertTo-HtmlText $Plane.plane)</span><strong class=""$StatusClass"">$(ConvertTo-HtmlText $CategoryLabel)</strong><small>ledger: $(ConvertTo-HtmlText $StatusText)</small></li>")
    }
    if ($PlaneCards.Count -eq 0) {
        $PlaneCards.Add("<li><span>Unavailable</span><strong class=""status-blocked"">no readback</strong></li>")
    }

    $ReceiptCards = New-Object System.Collections.Generic.List[string]
    $ReceiptIndex = 0
    foreach ($ReceiptPath in @($OrbSummary.receipt_paths)) {
        $ReceiptIndex += 1
        $ReceiptName = [System.IO.Path]::GetFileNameWithoutExtension([string]$ReceiptPath)
        $ReceiptCards.Add("<li><span>Receipt $ReceiptIndex</span><strong>$(ConvertTo-HtmlText $ReceiptName)</strong><code>$(ConvertTo-HtmlText $ReceiptPath)</code></li>")
    }
    if ($ReceiptCards.Count -eq 0) {
        $ReceiptCards.Add("<li><span>Receipts</span><strong>unavailable or skipped</strong><code>No receipt path was returned.</code></li>")
    }

    $ResultStatus = if ($Summary.ok) { "READY" } else { "BLOCKED" }
    $LiveInputText = if ($OrbSummary.live_input_performed) { "TRUE" } else { "FALSE" }
    $RawInputText = if ($OrbSummary.raw_input) { "TRUE" } else { "FALSE" }
    $ExecutionAttemptText = if ($OrbSummary.input_execution_attempted) { "TRUE" } else { "FALSE" }
    $McpOkText = if ($McpSummary.ok) { "TRUE" } else { "FALSE" }
    $OrbOkText = if ($OrbSummary.ok) { "TRUE" } else { "FALSE" }
    $CompletionOkText = if ($CompletionSummary.ok) { "TRUE" } else { "FALSE" }
    $GuardrailClass = if ($Summary.ok) { "good" } else { "bad" }
    $PlaneCardsHtml = [string]::Join("`n", [string[]]$PlaneCards.ToArray())
    $PlaneStory = "Phase 2 is expected to show many active-build planes. The visual groups raw ledger statuses into presentation categories while preserving the ledger wording on each plane."
    $ReceiptCardsHtml = [string]::Join("`n", [string[]]$ReceiptCards.ToArray())
    $LatestGap = ConvertTo-HtmlText $CompletionSummary.latest_remaining_gap

    $VisualHtml = @'
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Francis Presentation Demo</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #0b0d10;
      --panel: #15191f;
      --panel-2: #1d232b;
      --text: #eff5f7;
      --muted: #a7b2bd;
      --line: #2a333d;
      --cyan: #56d7e8;
      --green: #7bd88f;
      --amber: #f5c451;
      --red: #f06f6f;
      --blue: #8db8ff;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      background:
        radial-gradient(circle at 72% 10%, rgba(86, 215, 232, 0.14), transparent 30%),
        linear-gradient(180deg, #0b0d10 0%, #10141a 45%, #0b0d10 100%);
      color: var(--text);
      font-family: Inter, Segoe UI, Arial, sans-serif;
      line-height: 1.45;
    }

    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 32px 0 44px;
    }

    .hero {
      min-height: 76vh;
      display: grid;
      grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
      gap: 28px;
      align-items: center;
      border-bottom: 1px solid var(--line);
    }

    .eyebrow {
      color: var(--cyan);
      font-size: 13px;
      font-weight: 700;
      letter-spacing: 0;
      text-transform: uppercase;
    }

    h1 {
      margin: 12px 0 18px;
      max-width: 760px;
      font-size: clamp(44px, 6vw, 76px);
      line-height: 0.98;
      letter-spacing: 0;
    }

    .lead {
      max-width: 700px;
      margin: 0;
      color: #d9e3e8;
      font-size: 20px;
    }

    .hero-meta {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 24px;
    }

    .pill {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 11px;
      color: var(--muted);
      background: rgba(21, 25, 31, 0.72);
      font-size: 13px;
    }

    .orb-stage {
      position: relative;
      display: grid;
      place-items: center;
      min-height: 520px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background:
        linear-gradient(135deg, rgba(29, 35, 43, 0.94), rgba(12, 16, 20, 0.94)),
        repeating-linear-gradient(90deg, rgba(255,255,255,0.03) 0 1px, transparent 1px 72px);
    }

    .orb {
      position: relative;
      width: 220px;
      height: 220px;
      border-radius: 50%;
      background:
        radial-gradient(circle at 50% 50%, #fff 0 8%, #9cecf6 9% 19%, rgba(86, 215, 232, 0.34) 20% 39%, transparent 40%),
        radial-gradient(circle, rgba(86, 215, 232, 0.18), transparent 66%);
      box-shadow: 0 0 34px rgba(86, 215, 232, 0.34), inset 0 0 42px rgba(255, 255, 255, 0.16);
    }

    .orb::before,
    .orb::after {
      content: "";
      position: absolute;
      inset: -16px;
      border: 1px solid rgba(86, 215, 232, 0.62);
      border-radius: 50%;
      transform: rotateX(64deg) rotateZ(18deg);
    }

    .orb::after {
      inset: -42px;
      border-color: rgba(245, 196, 81, 0.42);
      transform: rotateX(72deg) rotateZ(-28deg);
    }

    .orbit {
      position: absolute;
      width: 320px;
      height: 112px;
      border: 1px solid rgba(141, 184, 255, 0.3);
      border-radius: 50%;
      transform: rotate(-18deg);
    }

    .operator-path {
      position: absolute;
      right: 28px;
      bottom: 28px;
      left: 28px;
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
    }

    .step {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: rgba(11, 13, 16, 0.74);
    }

    .step span {
      display: block;
      color: var(--muted);
      font-size: 12px;
    }

    .step strong {
      display: block;
      margin-top: 3px;
      font-size: 15px;
    }

    section {
      padding: 30px 0;
      border-bottom: 1px solid var(--line);
    }

    .grid {
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 14px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 18px;
      background: rgba(21, 25, 31, 0.86);
    }

    .panel h2,
    .panel h3 {
      margin: 0 0 12px;
      letter-spacing: 0;
    }

    .metric {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 0;
      border-top: 1px solid var(--line);
    }

    .metric:first-of-type { border-top: 0; }
    .metric span { color: var(--muted); }
    .metric strong { font-size: 18px; }

    .good { color: var(--green); }
    .warn { color: var(--amber); }
    .bad { color: var(--red); }
    .blue { color: var(--blue); }

    .planes,
    .receipts {
      display: grid;
      gap: 8px;
      padding: 0;
      margin: 0;
      list-style: none;
    }

    .planes {
      grid-template-columns: repeat(2, 1fr);
    }

    .planes li,
    .receipts li {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 11px 12px;
      background: rgba(29, 35, 43, 0.72);
    }

    .planes span,
    .receipts span {
      color: var(--muted);
      font-size: 13px;
    }

    .planes li {
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      align-items: center;
    }

    .status-ready { color: var(--green); }
    .status-active { color: var(--amber); }
    .status-early { color: var(--blue); }
    .status-blocked { color: var(--red); }

    .planes small {
      grid-column: 1 / -1;
      color: var(--muted);
      font-size: 12px;
    }

    .receipts li {
      display: grid;
      grid-template-columns: 92px minmax(160px, 0.55fr) minmax(220px, 1fr);
      align-items: center;
    }

    code {
      overflow-wrap: anywhere;
      color: #c8d2dc;
      font-family: Consolas, Menlo, monospace;
      font-size: 12px;
    }

    .claim-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
    }

    .claim-grid ul {
      margin: 0;
      padding-left: 20px;
      color: #d8e0e6;
    }

    .footer {
      color: var(--muted);
      font-size: 13px;
    }

    @media (max-width: 900px) {
      main { width: min(100% - 20px, 1180px); padding-top: 18px; }
      .hero { grid-template-columns: 1fr; min-height: auto; padding-bottom: 28px; }
      .orb-stage { min-height: 440px; }
      .operator-path { grid-template-columns: repeat(2, 1fr); }
      .grid, .claim-grid { grid-template-columns: 1fr; }
      .planes { grid-template-columns: 1fr; }
      .receipts li { grid-template-columns: 1fr; }
      h1 { font-size: 44px; }
    }
  </style>
</head>
<body>
  <main>
    <header class="hero">
      <div>
        <div class="eyebrow">Francis presentation demo / evidence-backed visual</div>
        <h1>Governed operator substrate, not chatbot theater.</h1>
        <p class="lead">This visual is generated from the live presentation run: completion-model readback, MCP governance smoke, and Orb operator dry-run receipts. It proves the current governed path without claiming live desktop autonomy.</p>
        <div class="hero-meta">
          <span class="pill">Status: <strong class="__GUARDRAIL_CLASS__">__RESULT_STATUS__</strong></span>
          <span class="pill">Phase: __CURRENT_PHASE__</span>
          <span class="pill">Commit: __COMMIT__</span>
          <span class="pill">Working tree: __WORKING_TREE__</span>
        </div>
      </div>
      <div class="orb-stage" aria-label="Visual representation of the Orb as governed operator presence">
        <div class="orbit"></div>
        <div class="orb"></div>
        <div class="operator-path">
          <div class="step"><span>Intent</span><strong>Orb move/click/type</strong></div>
          <div class="step"><span>Gate</span><strong>Dry-run only</strong></div>
          <div class="step"><span>Receipt</span><strong>3 records written</strong></div>
          <div class="step"><span>Live input</span><strong class="good">False</strong></div>
        </div>
      </div>
    </header>

    <section class="grid" aria-label="Demo status cards">
      <article class="panel">
        <h2>Build Readback</h2>
        <div class="metric"><span>Completion model</span><strong class="__COMPLETION_CLASS__">__COMPLETION_OK__</strong></div>
        <div class="metric"><span>Latest ledger entry</span><strong>__LATEST_LEDGER__</strong></div>
        <div class="metric"><span>Stage 17</span><strong class="warn">__STAGE17_STATUS__</strong></div>
      </article>
      <article class="panel">
        <h2>MCP Governance Smoke</h2>
        <div class="metric"><span>Smoke ok</span><strong class="__MCP_CLASS__">__MCP_OK__</strong></div>
        <div class="metric"><span>Tools surfaced</span><strong>__TOOL_COUNT__</strong></div>
        <div class="metric"><span>Unapproved takeover refused</span><strong class="good">__TAKEOVER_REFUSED__</strong></div>
        <div class="metric"><span>Unapproved input refused</span><strong class="good">__INPUT_REFUSED__</strong></div>
      </article>
      <article class="panel">
        <h2>Orb Operator Dry-Run</h2>
        <div class="metric"><span>Dry-run ok</span><strong class="__ORB_CLASS__">__ORB_OK__</strong></div>
        <div class="metric"><span>Sequence count</span><strong>__SEQUENCE_COUNT__</strong></div>
        <div class="metric"><span>Live input performed</span><strong class="good">__LIVE_INPUT__</strong></div>
        <div class="metric"><span>Raw input exposed</span><strong class="good">__RAW_INPUT__</strong></div>
        <div class="metric"><span>Input execution attempted</span><strong class="good">__EXECUTION_ATTEMPT__</strong></div>
      </article>
    </section>

    <section>
      <div class="panel">
        <h2>ORB Plane Readiness</h2>
        <p>__PLANE_STORY__</p>
        <div class="metric"><span>Proven strength</span><strong class="good">__PLANE_PROVEN_COUNT__</strong></div>
        <div class="metric"><span>Active build</span><strong class="warn">__PLANE_ACTIVE_COUNT__</strong></div>
        <div class="metric"><span>Early or roadmap</span><strong class="blue">__PLANE_EARLY_COUNT__</strong></div>
        <ul class="planes">
          __PLANE_CARDS__
        </ul>
      </div>
    </section>

    <section>
      <div class="panel">
        <h2>Orb Operator Receipts</h2>
        <ul class="receipts">
          __RECEIPT_CARDS__
        </ul>
      </div>
    </section>

    <section class="claim-grid">
      <div class="panel">
        <h3>Allowed Claims</h3>
        <ul>
          <li>Francis has a real ledger-backed build posture.</li>
          <li>Francis separates proposal, governance, execution, receipts, and memory.</li>
          <li>The Orb can produce dry-run move, click, and type operator receipts.</li>
          <li>Unapproved takeover and input paths are refused by the smoke check.</li>
        </ul>
      </div>
      <div class="panel">
        <h3>Claims Not Allowed</h3>
        <ul>
          <li>No finished autonomous desktop operation claim.</li>
          <li>No physical cursor movement claim from this demo.</li>
          <li>No live keyboard typing claim from this demo.</li>
          <li>No Stage 6, Stage 17, ORB Core, or full readiness closure claim.</li>
        </ul>
      </div>
    </section>

    <section>
      <div class="panel">
        <h2>Current Remaining Gap</h2>
        <p>__LATEST_GAP__</p>
      </div>
    </section>

    <p class="footer">Generated: __GENERATED_AT__ / Summary JSON: __SUMMARY_PATH__ / Markdown report: __REPORT_PATH__</p>
  </main>
</body>
</html>
'@

    $VisualHtml = $VisualHtml.Replace("__GUARDRAIL_CLASS__", $GuardrailClass)
    $VisualHtml = $VisualHtml.Replace("__RESULT_STATUS__", (ConvertTo-HtmlText $ResultStatus))
    $VisualHtml = $VisualHtml.Replace("__CURRENT_PHASE__", (ConvertTo-HtmlText $CompletionSummary.current_phase))
    $VisualHtml = $VisualHtml.Replace("__COMMIT__", (ConvertTo-HtmlText $Commit))
    $VisualHtml = $VisualHtml.Replace("__WORKING_TREE__", (ConvertTo-HtmlText $WorkingTreeStatus))
    $VisualHtml = $VisualHtml.Replace("__COMPLETION_CLASS__", $(if ($CompletionSummary.ok) { "good" } else { "bad" }))
    $VisualHtml = $VisualHtml.Replace("__COMPLETION_OK__", (ConvertTo-HtmlText $CompletionOkText))
    $VisualHtml = $VisualHtml.Replace("__LATEST_LEDGER__", (ConvertTo-HtmlText $CompletionSummary.latest_ledger_entry))
    $VisualHtml = $VisualHtml.Replace("__STAGE17_STATUS__", (ConvertTo-HtmlText $CompletionSummary.stage17_status))
    $VisualHtml = $VisualHtml.Replace("__MCP_CLASS__", $(if ($McpSummary.ok) { "good" } else { "bad" }))
    $VisualHtml = $VisualHtml.Replace("__MCP_OK__", (ConvertTo-HtmlText $McpOkText))
    $VisualHtml = $VisualHtml.Replace("__TOOL_COUNT__", (ConvertTo-HtmlText $McpSummary.tool_count))
    $VisualHtml = $VisualHtml.Replace("__TAKEOVER_REFUSED__", (ConvertTo-HtmlText $McpSummary.unapproved_takeover_refused))
    $VisualHtml = $VisualHtml.Replace("__INPUT_REFUSED__", (ConvertTo-HtmlText $McpSummary.unapproved_input_refused))
    $VisualHtml = $VisualHtml.Replace("__ORB_CLASS__", $(if ($OrbSummary.ok) { "good" } else { "bad" }))
    $VisualHtml = $VisualHtml.Replace("__ORB_OK__", (ConvertTo-HtmlText $OrbOkText))
    $VisualHtml = $VisualHtml.Replace("__SEQUENCE_COUNT__", (ConvertTo-HtmlText $OrbSummary.sequence_count))
    $VisualHtml = $VisualHtml.Replace("__LIVE_INPUT__", (ConvertTo-HtmlText $LiveInputText))
    $VisualHtml = $VisualHtml.Replace("__RAW_INPUT__", (ConvertTo-HtmlText $RawInputText))
    $VisualHtml = $VisualHtml.Replace("__EXECUTION_ATTEMPT__", (ConvertTo-HtmlText $ExecutionAttemptText))
    $VisualHtml = $VisualHtml.Replace("__PLANE_STORY__", (ConvertTo-HtmlText $PlaneStory))
    $VisualHtml = $VisualHtml.Replace("__PLANE_PROVEN_COUNT__", (ConvertTo-HtmlText $PlaneProvenCount))
    $VisualHtml = $VisualHtml.Replace("__PLANE_ACTIVE_COUNT__", (ConvertTo-HtmlText $PlaneActiveCount))
    $VisualHtml = $VisualHtml.Replace("__PLANE_EARLY_COUNT__", (ConvertTo-HtmlText $PlaneEarlyCount))
    $VisualHtml = $VisualHtml.Replace("__PLANE_CARDS__", $PlaneCardsHtml)
    $VisualHtml = $VisualHtml.Replace("__RECEIPT_CARDS__", $ReceiptCardsHtml)
    $VisualHtml = $VisualHtml.Replace("__LATEST_GAP__", $LatestGap)
    $VisualHtml = $VisualHtml.Replace("__GENERATED_AT__", (ConvertTo-HtmlText $GeneratedAt))
    $VisualHtml = $VisualHtml.Replace("__SUMMARY_PATH__", (ConvertTo-HtmlText $SummaryPath))
    $VisualHtml = $VisualHtml.Replace("__REPORT_PATH__", (ConvertTo-HtmlText $ReportPath))
    $VisualHtml | Set-Content -LiteralPath $VisualPath -Encoding utf8

    $Summary | ConvertTo-Json -Depth 10
    if ($Failures.Count -gt 0) {
        exit 1
    }
}
finally {
    Pop-Location
}
