param(
  [ValidateSet('Start', 'Run', 'Status', 'Stop')]
  [string]$Mode = 'Status',

  [ValidateRange(5, 3600)]
  [int]$PollSeconds = 45,

  [ValidateRange(0, 1000000)]
  [int]$MaxIterations = 0,

  [string]$Model = '',

  [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
  [string]$Sandbox = 'workspace-write',

  [ValidateSet('Visible', 'Minimized', 'Background', 'Exec')]
  [string]$WorkerLaunchMode = 'Exec',

  [string]$StateRoot = '',

  [switch]$NoLaunch,

  [switch]$ForcePromptAll
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

if ([string]::IsNullOrWhiteSpace($StateRoot)) {
  $StateRoot = Join-Path $RepoRoot '.francis\worker-terminal-coordinator'
}
$StateRoot = [System.IO.Path]::GetFullPath($StateRoot)
$StatusPath = Join-Path $StateRoot 'status.json'
$ReceiptPath = Join-Path $StateRoot 'receipts.jsonl'
$StopFlagPath = Join-Path $StateRoot 'stop.flag'
$PidPath = Join-Path $StateRoot 'coordinator.pid'
$DispatchRoot = Join-Path $StateRoot 'dispatches'
$ReadbackRoot = Join-Path $StateRoot 'readbacks'
$PublicationRoot = Join-Path $StateRoot 'publications'
$Launcher = Join-Path $PSScriptRoot 'start-francis-worker-terminals.ps1'
$CompletionModelScript = Join-Path $PSScriptRoot 'francis-completion-model.ps1'
$PromptRoot = Join-Path $RepoRoot 'docs\operations\worker_prompts'
$Workers = @(
  'worker-1-orb-voice-proof',
  'worker-2-lens-overlay-spatial',
  'worker-3-voice-receipts',
  'worker-4-stage17-completion'
)

function Initialize-CoordinatorStateRoot {
  New-Item -ItemType Directory -Force -Path $StateRoot | Out-Null
}

function Write-CoordinatorJson {
  param(
    [string]$Path,
    [object]$Payload
  )

  Initialize-CoordinatorStateRoot
  $Payload | ConvertTo-Json -Depth 16 | Set-Content -LiteralPath $Path -Encoding UTF8
}

function Add-CoordinatorReceipt {
  param([object]$Payload)

  Initialize-CoordinatorStateRoot
  $Payload | ConvertTo-Json -Depth 16 -Compress | Add-Content -LiteralPath $ReceiptPath -Encoding UTF8
}

function Read-CoordinatorStatusFile {
  if (-not (Test-Path -LiteralPath $StatusPath -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $StatusPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Read-CoordinatorJsonFile {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
}

function Get-UtcNowText {
  return [DateTimeOffset]::UtcNow.ToString('o')
}

function Get-CoordinatorBoundedText {
  param(
    [string]$Text,
    [int]$MaxLength = 6000
  )

  if ([string]::IsNullOrEmpty($Text)) {
    return ''
  }
  if ($Text.Length -le $MaxLength) {
    return $Text
  }
  return ($Text.Substring(0, $MaxLength) + "`n[truncated]")
}

function Get-CoordinatorBuildSnapshot {
  $Completion = ''
  if (Test-Path -LiteralPath $CompletionModelScript -PathType Leaf) {
    try {
      $Completion = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $CompletionModelScript -Mode Status | Out-String
    } catch {
      $Completion = 'completion_model_read_failed: {0}' -f $_.Exception.Message
    }
  } else {
    $Completion = 'completion_model_script_missing'
  }

  $GitStatus = ''
  try {
    $GitStatus = git -C $RepoRoot status --short | Out-String
  } catch {
    $GitStatus = 'git_status_read_failed: {0}' -f $_.Exception.Message
  }

  return [ordered]@{
    completion_model = Get-CoordinatorBoundedText -Text $Completion -MaxLength 9000
    git_status_short = Get-CoordinatorBoundedText -Text $GitStatus -MaxLength 6000
  }
}

function Get-LaneProjectManagerInstruction {
  param([string]$WorkerId)

  switch ($WorkerId) {
    'worker-1-orb-voice-proof' {
      return 'Project-manager direction: advance the next smallest Orb voice proof slice. Prioritize truthful manual-acoustic proof diagnostics, monitor evidence, receipt completeness, and visual-lock preservation. Do not fake microphone evidence.'
    }
    'worker-2-lens-overlay-spatial' {
      return 'Project-manager direction: advance the next smallest lens-to-overlay spatial contract slice. Prioritize requested/mapped/actual region truth, coordinate boundaries, confidence, limitations, and tests. Do not claim unsupported perception.'
    }
    'worker-3-voice-receipts' {
      return 'Project-manager direction: advance the next smallest voice receipt or provider-boundary slice. Prioritize ElevenLabs/ChatGPT voice receipts, redaction, unavailable/live/replay distinctions, and preventing voice from bypassing substrate governance.'
    }
    'worker-4-stage17-completion' {
      return 'Project-manager direction: advance the next smallest Stage 17 or completion-model truth slice. Prioritize bounded readback/apply boundaries, proposal evidence references, completion-loop guards, and focused validation. Do not claim Stage 17 closure without proof.'
    }
    default {
      return 'Project-manager direction: inspect repo truth, choose one bounded roadmap-aligned slice, validate it, and leave a precise handoff.'
    }
  }
}

function Get-LaneReadbackPath {
  param([string]$WorkerId)

  return (Join-Path $ReadbackRoot ('{0}.md' -f $WorkerId))
}

function Get-LanePublicationPath {
  param([string]$WorkerId)

  return (Join-Path $PublicationRoot ('{0}.json' -f $WorkerId))
}

function Select-CoordinatorWorker {
  param(
    [object]$WorkersPayload,
    [string]$WorkerId
  )

  $Matches = @($WorkersPayload | Where-Object { [string]$_.worker_id -eq $WorkerId })
  if ($Matches.Count -eq 0) {
    return $null
  }
  return $Matches[0]
}

function Test-LaneRePromptPublicationGate {
  param(
    [string]$WorkerId,
    [object]$Worker
  )

  if ($Worker -is [array]) {
    if ($Worker.Count -eq 0) {
      $Worker = $null
    } else {
      $Worker = $Worker[0]
    }
  }

  New-Item -ItemType Directory -Force -Path $ReadbackRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $PublicationRoot | Out-Null

  $ReadbackPath = Get-LaneReadbackPath -WorkerId $WorkerId
  $PublicationPath = Get-LanePublicationPath -WorkerId $WorkerId
  $PromptSha256 = if ($null -ne $Worker -and $Worker.PSObject.Properties['prompt_sha256']) {
    [string]$Worker.prompt_sha256
  } else {
    ''
  }
  $SessionExists = if ($null -ne $Worker -and $Worker.PSObject.Properties['session_exists']) {
    [bool]$Worker.session_exists
  } else {
    $false
  }
  if (-not $SessionExists) {
    return [ordered]@{
      allowed = $true
      status = 'first_prompt_allowed'
      prompt_sha256 = $PromptSha256
      readback_path = $ReadbackPath
      readback_exists = $false
      publication_path = $PublicationPath
      publication_exists = $false
      publication_status = ''
    }
  }

  $ReadbackExists = Test-Path -LiteralPath $ReadbackPath -PathType Leaf
  $Publication = Read-CoordinatorJsonFile -Path $PublicationPath
  $PublicationExists = $null -ne $Publication
  $PublicationPromptSha256 = if ($PublicationExists -and $Publication.PSObject.Properties['prompt_sha256']) {
    [string]$Publication.prompt_sha256
  } else {
    ''
  }
  $PublicationStatus = if ($PublicationExists -and $Publication.PSObject.Properties['status']) {
    [string]$Publication.status
  } else {
    ''
  }
  $AllowedStatuses = @('github_pushed', 'no_changes', 'blocked_with_receipt')
  $PublicationMatchesPrompt = (
    $PublicationExists -and
    -not [string]::IsNullOrWhiteSpace($PromptSha256) -and
    $PublicationPromptSha256 -eq $PromptSha256 -and
    $AllowedStatuses -contains $PublicationStatus
  )

  $Allowed = $ReadbackExists -and $PublicationMatchesPrompt
  $Status = if ($Allowed) {
    'publication_gate_satisfied'
  } elseif (-not $ReadbackExists) {
    'awaiting_lane_readback'
  } elseif (-not $PublicationExists) {
    'awaiting_publication_marker'
  } elseif (-not ($AllowedStatuses -contains $PublicationStatus)) {
    'publication_marker_status_not_allowed'
  } else {
    'publication_marker_prompt_mismatch'
  }

  return [ordered]@{
    allowed = [bool]$Allowed
    status = $Status
    prompt_sha256 = $PromptSha256
    readback_path = $ReadbackPath
    readback_exists = [bool]$ReadbackExists
    publication_path = $PublicationPath
    publication_exists = [bool]$PublicationExists
    publication_status = $PublicationStatus
    publication_prompt_sha256 = $PublicationPromptSha256
  }
}

function New-ProjectManagerDispatchPrompt {
  param(
    [string]$WorkerId,
    [int]$Iteration,
    [string]$Reason,
    [object]$PreviousWorker,
    [object]$BuildSnapshot
  )

  New-Item -ItemType Directory -Force -Path $DispatchRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $ReadbackRoot | Out-Null
  New-Item -ItemType Directory -Force -Path $PublicationRoot | Out-Null
  $BasePromptPath = Join-Path $PromptRoot ('{0}.md' -f $WorkerId)
  $BasePrompt = Get-Content -LiteralPath $BasePromptPath -Raw -Encoding UTF8
  $DispatchPath = Join-Path $DispatchRoot ('{0}-iteration-{1}.md' -f $WorkerId, $Iteration)
  $ReadbackPath = Get-LaneReadbackPath -WorkerId $WorkerId
  $PublicationPath = Get-LanePublicationPath -WorkerId $WorkerId
  $PreviousWorkerJson = if ($null -ne $PreviousWorker) {
    $PreviousWorker | ConvertTo-Json -Depth 8
  } else {
    '{}'
  }
  $Prompt = @"
# Francis Project Manager Dispatch

Worker: `$WorkerId`
Coordinator iteration: `$Iteration`
Dispatch reason: `$Reason`
Generated at: $(Get-UtcNowText)

You are being individually re-prompted by the Francis coordinator. Stay in your assigned lane, inspect current repo truth before editing, and make one bounded, validated advancement. Do not wait for the other lanes unless your work would conflict with them.

$(Get-LaneProjectManagerInstruction -WorkerId $WorkerId)

## Current Build Snapshot

### Completion Model

```json
$($BuildSnapshot.completion_model)
```

### Dirty Worktree

```text
$($BuildSnapshot.git_status_short)
```

### Previous Worker Readback

```json
$PreviousWorkerJson
```

## Project Manager Acceptance Criteria For This Pass

- Focus on wiring and completion blockers before cosmetic or broad cleanup.
- Identify the exact substrate surfaces you are connecting before editing.
- Preserve Orb visuals.
- Preserve existing Francis substrate contracts.
- Use existing mission/governance/receipt surfaces instead of creating a parallel substrate.
- Keep the edit bounded to your lane.
- Validate the touched path.
- Update durable state only when repo truth materially changed.
- Write a concise lane readback to `$ReadbackPath` before ending. Include files touched, validation, blockers, proposed Git commit scope, and the next highest-value prompt for this lane.
- The next prompt for this lane is gated on that readback plus a PM-owned publication marker at `$PublicationPath`. The marker must reference this pass prompt hash and represent a GitHub push, an explicit no-change receipt, or a blocked-with-evidence receipt.
- Final answer must include exact files changed, validation, and remaining risks.
- Do not commit, push, restart Continuum, or spawn new workers. The project-manager session owns GitHub publication after lane review and validation.

---

$BasePrompt
"@
  Set-Content -LiteralPath $DispatchPath -Value $Prompt -Encoding UTF8
  return $DispatchPath
}

function Get-LauncherStatus {
  $Output = powershell.exe -NoProfile -ExecutionPolicy Bypass -File $Launcher -Mode Status
  return ($Output | ConvertFrom-Json -ErrorAction Stop)
}

function Start-WorkerLane {
  param(
    [string]$WorkerId,
    [int]$Iteration,
    [string]$Reason,
    [object]$PreviousWorker,
    [object]$BuildSnapshot
  )

  $DispatchPromptPath = New-ProjectManagerDispatchPrompt -WorkerId $WorkerId -Iteration $Iteration -Reason $Reason -PreviousWorker $PreviousWorker -BuildSnapshot $BuildSnapshot
  if ($NoLaunch) {
    return [ordered]@{
      skipped = $true
      reason = 'no_launch_requested'
      worker_id = $WorkerId
      dispatch_prompt_path = $DispatchPromptPath
    }
  }
  $Args = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $Launcher,
    '-Mode',
    'Start',
    '-WorkerId',
    $WorkerId,
    '-PromptPath',
    $DispatchPromptPath,
    '-Sandbox',
    $Sandbox,
    '-LaunchMode',
    $WorkerLaunchMode
  )
  if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $Args += @('-Model', $Model)
  }
  $Output = powershell.exe @Args
  $Launch = ($Output | ConvertFrom-Json -ErrorAction Stop)
  return [ordered]@{
    launch = $Launch
    dispatch_prompt_path = $DispatchPromptPath
  }
}

function Stop-StaleWorkerRunner {
  param([object]$Worker)

  $PidValue = [int]$Worker.pid
  if ($PidValue -le 0 -or -not [bool]$Worker.process_alive) {
    return [ordered]@{ stopped = $false; reason = 'process_not_alive'; pid = $PidValue }
  }
  if ([bool]$Worker.codex_child_alive) {
    return [ordered]@{ stopped = $false; reason = 'codex_child_still_alive'; pid = $PidValue }
  }
  try {
    Stop-Process -Id $PidValue -Force -ErrorAction Stop
    return [ordered]@{ stopped = $true; reason = 'stale_runner_without_codex_child'; pid = $PidValue }
  } catch {
    return [ordered]@{ stopped = $false; reason = 'stop_failed'; pid = $PidValue; error = [string]$_.Exception.Message }
  }
}

function Test-WorkerNeedsPrompt {
  param([object]$Worker)

  if (-not [bool]$Worker.process_alive) {
    return $true
  }
  if (-not [bool]$Worker.codex_child_alive) {
    return $true
  }
  return $false
}

function Invoke-CoordinatorIteration {
  param([int]$Iteration)

  $Before = Get-LauncherStatus
  $BuildSnapshot = Get-CoordinatorBuildSnapshot
  $Actions = @()
  foreach ($WorkerId in $Workers) {
    $Worker = Select-CoordinatorWorker -WorkersPayload $Before.workers -WorkerId $WorkerId
    if ($null -eq $Worker) {
      $NeedsPrompt = $true
      $Reason = 'missing_worker_status'
    } elseif ($ForcePromptAll) {
      $NeedsPrompt = $true
      $Reason = 'project_manager_force_prompt'
    } elseif (Test-WorkerNeedsPrompt -Worker $Worker) {
      $NeedsPrompt = $true
      $Reason = if (-not [bool]$Worker.process_alive) { 'worker_process_missing' } else { 'worker_codex_child_missing' }
    } else {
      $NeedsPrompt = $false
      $Reason = 'worker_active'
    }

    $Action = [ordered]@{
      worker_id = $WorkerId
      needs_prompt = [bool]$NeedsPrompt
      reason = $Reason
      previous_pid = if ($null -ne $Worker) { [int]$Worker.pid } else { 0 }
      previous_codex_child_alive = if ($null -ne $Worker) { [bool]$Worker.codex_child_alive } else { $false }
      stale_stop = $null
      launch = $null
      publication_gate = $null
      launch_blocked = $false
    }

    if ($NeedsPrompt) {
      $PublicationGate = if ($NoLaunch) {
        [ordered]@{
          allowed = $true
          status = 'no_launch_preview_allowed'
          prompt_sha256 = if ($null -ne $Worker -and $Worker.PSObject.Properties['prompt_sha256']) { [string]$Worker.prompt_sha256 } else { '' }
          readback_path = Get-LaneReadbackPath -WorkerId $WorkerId
          readback_exists = Test-Path -LiteralPath (Get-LaneReadbackPath -WorkerId $WorkerId) -PathType Leaf
          publication_path = Get-LanePublicationPath -WorkerId $WorkerId
          publication_exists = Test-Path -LiteralPath (Get-LanePublicationPath -WorkerId $WorkerId) -PathType Leaf
          publication_status = ''
        }
      } else {
        Test-LaneRePromptPublicationGate -WorkerId $WorkerId -Worker $Worker
      }
      $Action.publication_gate = $PublicationGate
      if (-not [bool]$PublicationGate.allowed) {
        $Action.launch_blocked = $true
        $Action.reason = [string]$PublicationGate.status
        $Actions += $Action
        continue
      }
      if ($null -ne $Worker -and [bool]$Worker.process_alive -and -not [bool]$Worker.codex_child_alive) {
        $Action.stale_stop = Stop-StaleWorkerRunner -Worker $Worker
      }
      $Action.launch = Start-WorkerLane -WorkerId $WorkerId -Iteration $Iteration -Reason $Reason -PreviousWorker $Worker -BuildSnapshot $BuildSnapshot
    }
    $Actions += $Action
  }
  $After = Get-LauncherStatus
  $Receipt = [ordered]@{
    kind = 'francis.worker_terminal.coordinator.iteration'
    iteration = $Iteration
    at = Get-UtcNowText
    repo_root = $RepoRoot
    mode = 'Run'
    poll_seconds = $PollSeconds
    max_iterations = $MaxIterations
    no_launch = [bool]$NoLaunch
    force_prompt_all = [bool]$ForcePromptAll
    sandbox = $Sandbox
    model = $Model
    worker_launch_mode = $WorkerLaunchMode
    worker_count = $Workers.Count
    actions = $Actions
    project_manager_dispatch = $true
    dispatch_root = $DispatchRoot
    readback_root = $ReadbackRoot
    publication_root = $PublicationRoot
    re_prompt_publication_gate_required = $true
    build_snapshot = $BuildSnapshot
    workers = $After.workers
    stop_flag_path = $StopFlagPath
    uncontrolled_recursion_allowed = $false
    one_codex_child_per_lane = $true
  }
  Add-CoordinatorReceipt -Payload $Receipt
  Write-CoordinatorJson -Path $StatusPath -Payload ([ordered]@{
      kind = 'francis.worker_terminal.coordinator.status'
      ok = $true
      state = 'running'
      updated_at = Get-UtcNowText
      pid = $PID
      iteration = $Iteration
      poll_seconds = $PollSeconds
      max_iterations = $MaxIterations
      no_launch = [bool]$NoLaunch
      force_prompt_all = [bool]$ForcePromptAll
      worker_launch_mode = $WorkerLaunchMode
      stop_flag_path = $StopFlagPath
      receipt_path = $ReceiptPath
      workers = $After.workers
      last_actions = $Actions
      project_manager_dispatch = $true
      dispatch_root = $DispatchRoot
      readback_root = $ReadbackRoot
      publication_root = $PublicationRoot
      re_prompt_publication_gate_required = $true
      uncontrolled_recursion_allowed = $false
      one_codex_child_per_lane = $true
    })
  return $Receipt
}

if ($Mode -eq 'Status') {
  Initialize-CoordinatorStateRoot
  $Status = Read-CoordinatorStatusFile
  $CoordinatorPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $CoordinatorPid = [int](Get-Content -LiteralPath $PidPath -Raw -Encoding UTF8)
    } catch {
      $CoordinatorPid = 0
    }
  }
  $CoordinatorAlive = $false
  if ($CoordinatorPid -gt 0) {
    $CoordinatorAlive = $null -ne (Get-Process -Id $CoordinatorPid -ErrorAction SilentlyContinue)
  }
  [ordered]@{
    kind = 'francis.worker_terminal.coordinator.status_readback'
    ok = $true
    repo_root = $RepoRoot
    state_root = $StateRoot
    status_exists = $null -ne $Status
    coordinator_pid = $CoordinatorPid
    coordinator_alive = [bool]$CoordinatorAlive
    stop_requested = Test-Path -LiteralPath $StopFlagPath -PathType Leaf
    status = $Status
    worker_status = (Get-LauncherStatus).workers
  } | ConvertTo-Json -Depth 16
  exit 0
}

if ($Mode -eq 'Stop') {
  Initialize-CoordinatorStateRoot
  Set-Content -LiteralPath $StopFlagPath -Value (Get-UtcNowText) -Encoding UTF8
  Add-CoordinatorReceipt -Payload ([ordered]@{
      kind = 'francis.worker_terminal.coordinator.stop_requested'
      at = Get-UtcNowText
      stop_flag_path = $StopFlagPath
    })
  [ordered]@{
    kind = 'francis.worker_terminal.coordinator.stop'
    ok = $true
    stop_requested = $true
    stop_flag_path = $StopFlagPath
  } | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Start') {
  Initialize-CoordinatorStateRoot
  Remove-Item -LiteralPath $StopFlagPath -Force -ErrorAction SilentlyContinue
  $Pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
  if ([string]::IsNullOrWhiteSpace($Pwsh)) {
    $Pwsh = (Get-Command powershell.exe -ErrorAction Stop).Source
  }
  $Args = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $PSCommandPath,
    '-Mode',
    'Run',
    '-PollSeconds',
    ([string]$PollSeconds),
    '-MaxIterations',
    ([string]$MaxIterations),
    '-Sandbox',
    $Sandbox,
    '-WorkerLaunchMode',
    $WorkerLaunchMode,
    '-StateRoot',
    $StateRoot
  )
  if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $Args += @('-Model', $Model)
  }
  if ($NoLaunch) {
    $Args += '-NoLaunch'
  }
  if ($ForcePromptAll) {
    $Args += '-ForcePromptAll'
  }
  $Process = Start-Process -FilePath $Pwsh -ArgumentList $Args -WindowStyle Hidden -PassThru
  Set-Content -LiteralPath $PidPath -Value ([string]$Process.Id) -Encoding UTF8
  Add-CoordinatorReceipt -Payload ([ordered]@{
      kind = 'francis.worker_terminal.coordinator.started'
      at = Get-UtcNowText
      pid = $Process.Id
      poll_seconds = $PollSeconds
      max_iterations = $MaxIterations
      sandbox = $Sandbox
      model = $Model
      worker_launch_mode = $WorkerLaunchMode
      no_launch = [bool]$NoLaunch
      force_prompt_all = [bool]$ForcePromptAll
    })
  [ordered]@{
    kind = 'francis.worker_terminal.coordinator.start'
    ok = $true
    pid = $Process.Id
    state_root = $StateRoot
    stop_flag_path = $StopFlagPath
    receipt_path = $ReceiptPath
    readback_root = $ReadbackRoot
    publication_root = $PublicationRoot
    poll_seconds = $PollSeconds
    max_iterations = $MaxIterations
    no_launch = [bool]$NoLaunch
    force_prompt_all = [bool]$ForcePromptAll
  } | ConvertTo-Json -Depth 8
  exit 0
}

Initialize-CoordinatorStateRoot
Remove-Item -LiteralPath $StopFlagPath -Force -ErrorAction SilentlyContinue
Set-Content -LiteralPath $PidPath -Value ([string]$PID) -Encoding UTF8
Add-CoordinatorReceipt -Payload ([ordered]@{
    kind = 'francis.worker_terminal.coordinator.run_started'
    at = Get-UtcNowText
    pid = $PID
    poll_seconds = $PollSeconds
    max_iterations = $MaxIterations
    sandbox = $Sandbox
    model = $Model
    worker_launch_mode = $WorkerLaunchMode
    no_launch = [bool]$NoLaunch
    force_prompt_all = [bool]$ForcePromptAll
  })

$Iteration = 0
while ($true) {
  if (Test-Path -LiteralPath $StopFlagPath -PathType Leaf) {
    break
  }
  $Iteration += 1
  [void](Invoke-CoordinatorIteration -Iteration $Iteration)
  if ($MaxIterations -gt 0 -and $Iteration -ge $MaxIterations) {
    break
  }
  Start-Sleep -Seconds $PollSeconds
}

$FinalState = if (Test-Path -LiteralPath $StopFlagPath -PathType Leaf) { 'stopped' } else { 'completed_max_iterations' }
Add-CoordinatorReceipt -Payload ([ordered]@{
    kind = 'francis.worker_terminal.coordinator.run_completed'
    at = Get-UtcNowText
    pid = $PID
    state = $FinalState
    iterations = $Iteration
  })
Write-CoordinatorJson -Path $StatusPath -Payload ([ordered]@{
    kind = 'francis.worker_terminal.coordinator.status'
    ok = $true
    state = $FinalState
    updated_at = Get-UtcNowText
    pid = $PID
    iteration = $Iteration
    poll_seconds = $PollSeconds
    max_iterations = $MaxIterations
    no_launch = [bool]$NoLaunch
    worker_launch_mode = $WorkerLaunchMode
    stop_flag_path = $StopFlagPath
    receipt_path = $ReceiptPath
    workers = (Get-LauncherStatus).workers
    project_manager_dispatch = $true
    dispatch_root = $DispatchRoot
    readback_root = $ReadbackRoot
    publication_root = $PublicationRoot
    re_prompt_publication_gate_required = $true
    uncontrolled_recursion_allowed = $false
    one_codex_child_per_lane = $true
  })
exit 0
