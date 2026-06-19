param(
  [ValidateSet('Start', 'Status', 'ListPrompts')]
  [string]$Mode = 'Start',

  [ValidateSet('All', 'worker-1-orb-voice-proof', 'worker-2-lens-overlay-spatial', 'worker-3-voice-receipts', 'worker-4-stage17-completion')]
  [string]$WorkerId = 'All',

  [string]$PromptPath = '',

  [string]$Model = '',

  [ValidateSet('read-only', 'workspace-write', 'danger-full-access')]
  [string]$Sandbox = 'workspace-write',

  [ValidateSet('Visible', 'Background')]
  [string]$LaunchMode = 'Visible'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

$Workers = @(
  [ordered]@{ id = 'worker-1-orb-voice-proof'; title = 'Francis W1 Orb Voice Proof' },
  [ordered]@{ id = 'worker-2-lens-overlay-spatial'; title = 'Francis W2 Lens Overlay Spatial' },
  [ordered]@{ id = 'worker-3-voice-receipts'; title = 'Francis W3 Voice Receipts' },
  [ordered]@{ id = 'worker-4-stage17-completion'; title = 'Francis W4 Stage17 Completion' }
)

$PromptRoot = Join-Path $RepoRoot 'docs\operations\worker_prompts'
$SessionRoot = Join-Path $RepoRoot '.francis\worker-terminal-sessions'
New-Item -ItemType Directory -Force -Path $SessionRoot | Out-Null

function Get-WorkerFileSha256 {
  param([string]$Path)

  $Stream = [System.IO.File]::OpenRead($Path)
  try {
    $Sha = [System.Security.Cryptography.SHA256]::Create()
    try {
      $Bytes = $Sha.ComputeHash($Stream)
      return ([System.BitConverter]::ToString($Bytes) -replace '-', '').ToLowerInvariant()
    } finally {
      $Sha.Dispose()
    }
  } finally {
    $Stream.Dispose()
  }
}

function Get-WorkerPromptRows {
  $Rows = @()
  foreach ($Worker in $Workers) {
    $PromptPath = Join-Path $PromptRoot ('{0}.md' -f $Worker.id)
    $Rows += [ordered]@{
      worker_id = $Worker.id
      title = $Worker.title
      prompt_path = $PromptPath
      prompt_exists = Test-Path -LiteralPath $PromptPath -PathType Leaf
    }
  }
  return $Rows
}

function Get-WorkerStatusRows {
  $Rows = @()
  foreach ($Worker in $Workers) {
    $SessionPath = Join-Path $SessionRoot ('{0}.json' -f $Worker.id)
    $Session = $null
    if (Test-Path -LiteralPath $SessionPath -PathType Leaf) {
      try {
        $Session = Get-Content -LiteralPath $SessionPath -Raw -Encoding UTF8 | ConvertFrom-Json -ErrorAction Stop
      } catch {
        $Session = $null
      }
    }
    $PidValue = if ($null -ne $Session) { [int]$Session.pid } else { 0 }
    $ProcessAlive = $false
    $Process = $null
    if ($PidValue -gt 0) {
      $Process = Get-Process -Id $PidValue -ErrorAction SilentlyContinue
      $ProcessAlive = $null -ne $Process
    }
    $ChildProcesses = @()
    if ($PidValue -gt 0) {
      try {
        $ChildProcesses = @(Get-CimInstance Win32_Process -Filter ("ParentProcessId = {0}" -f $PidValue) -ErrorAction Stop)
      } catch {
        $ChildProcesses = @()
      }
    }
    $CodexChildren = @($ChildProcesses | Where-Object {
        [string]$_.Name -in @('node.exe', 'codex.exe') -and [string]$_.CommandLine -like '*codex*'
      })
    $ConsoleChildren = @($ChildProcesses | Where-Object { [string]$_.Name -eq 'conhost.exe' })
    $MainWindowHandle = if ($null -ne $Process) { [int64]$Process.MainWindowHandle } else { 0 }
    $PhysicalConsoleObserved = ($MainWindowHandle -ne 0 -or @($ConsoleChildren).Count -gt 0)
    $VisibleTerminalEvidence = if ($MainWindowHandle -ne 0) {
      'main_window_handle_observed'
    } elseif (@($ConsoleChildren).Count -gt 0) {
      'console_host_child_observed'
    } else {
      'no_visible_window_evidence'
    }
    $StartedAt = if ($null -ne $Session -and $Session.PSObject.Properties['started_at']) { [string]$Session.started_at } else { '' }
    $CompletedAt = if ($null -ne $Session -and $Session.PSObject.Properties['completed_at']) { [string]$Session.completed_at } else { '' }
    $ExitCode = if ($null -ne $Session -and $Session.PSObject.Properties['exit_code']) { [int]$Session.exit_code } else { $null }
    $StatusPromptPath = if ($null -ne $Session -and $Session.PSObject.Properties['prompt_path']) {
      [string]$Session.prompt_path
    } else {
      Join-Path $PromptRoot ('{0}.md' -f $Worker.id)
    }
    $LaunchModeText = if ($null -ne $Session -and $Session.PSObject.Properties['launch_mode']) {
      [string]$Session.launch_mode
    } else {
      'Visible'
    }
    $VisibleTerminalRequested = if ($null -ne $Session -and $Session.PSObject.Properties['visible_terminal_requested']) {
      [bool]$Session.visible_terminal_requested
    } else {
      $true
    }
    $PromptSha256 = if ($null -ne $Session -and $Session.PSObject.Properties['prompt_sha256']) {
      [string]$Session.prompt_sha256
    } elseif (Test-Path -LiteralPath $StatusPromptPath -PathType Leaf) {
      Get-WorkerFileSha256 -Path $StatusPromptPath
    } else {
      ''
    }
    $Rows += [ordered]@{
      worker_id = $Worker.id
      title = $Worker.title
      session_path = $SessionPath
      session_exists = Test-Path -LiteralPath $SessionPath -PathType Leaf
      pid = $PidValue
      process_alive = [bool]$ProcessAlive
      main_window_handle = $MainWindowHandle
      physical_console_observed = [bool]$PhysicalConsoleObserved
      visible_terminal_evidence = $VisibleTerminalEvidence
      codex_child_alive = @($CodexChildren).Count -gt 0
      codex_child_process_ids = @($CodexChildren | ForEach-Object { [int]$_.ProcessId })
      console_host_child_alive = @($ConsoleChildren).Count -gt 0
      console_host_process_ids = @($ConsoleChildren | ForEach-Object { [int]$_.ProcessId })
      prompt_path = $StatusPromptPath
      prompt_sha256 = $PromptSha256
      launch_mode = $LaunchModeText
      visible_terminal_requested = $VisibleTerminalRequested
      started_at = $StartedAt
      completed_at = $CompletedAt
      exit_code = $ExitCode
    }
  }
  return $Rows
}

if ($Mode -eq 'ListPrompts') {
  [ordered]@{
    kind = 'francis.worker_terminal.prompts'
    ok = $true
    repo_root = $RepoRoot
    workers = @(Get-WorkerPromptRows)
  } | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'Status') {
  [ordered]@{
    kind = 'francis.worker_terminal.status'
    ok = $true
    repo_root = $RepoRoot
    workers = @(Get-WorkerStatusRows)
  } | ConvertTo-Json -Depth 8
  exit 0
}

$Pwsh = (Get-Command pwsh.exe -ErrorAction SilentlyContinue).Source
if ([string]::IsNullOrWhiteSpace($Pwsh)) {
  $Pwsh = (Get-Command powershell.exe -ErrorAction Stop).Source
}
$Runner = Join-Path $PSScriptRoot 'francis-worker-terminal.ps1'

$Launches = @()
foreach ($Worker in @($Workers | Where-Object { $WorkerId -eq 'All' -or [string]$_.id -eq $WorkerId })) {
  $EffectivePromptPath = if ([string]::IsNullOrWhiteSpace($PromptPath)) {
    Join-Path $PromptRoot ('{0}.md' -f $Worker.id)
  } else {
    [System.IO.Path]::GetFullPath($PromptPath)
  }
  if (-not (Test-Path -LiteralPath $EffectivePromptPath -PathType Leaf)) {
    throw "Missing worker prompt: $EffectivePromptPath"
  }
  $ArgumentList = @(
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $Runner,
    '-WorkerId',
    $Worker.id,
    '-PromptPath',
    $EffectivePromptPath,
    '-Sandbox',
    $Sandbox,
    '-LaunchMode',
    $LaunchMode
  )
  if ($LaunchMode -eq 'Visible') {
    $ArgumentList = @('-NoExit') + $ArgumentList
  }
  if (-not [string]::IsNullOrWhiteSpace($Model)) {
    $ArgumentList += @('-Model', $Model)
  }
  $StartProcessArgs = @{
    FilePath = $Pwsh
    ArgumentList = $ArgumentList
    PassThru = $true
  }
  if ($LaunchMode -eq 'Background') {
    $StartProcessArgs.WindowStyle = 'Hidden'
  }
  $Process = Start-Process @StartProcessArgs
  $Launches += [ordered]@{
    worker_id = $Worker.id
    title = $Worker.title
    prompt_path = $EffectivePromptPath
    prompt_sha256 = Get-WorkerFileSha256 -Path $EffectivePromptPath
    launcher_process_id = $Process.Id
    launch_mode = $LaunchMode
    visible_terminal_requested = ($LaunchMode -eq 'Visible')
  }
}

Start-Sleep -Seconds 2

[ordered]@{
  kind = 'francis.worker_terminal.launch'
  ok = $true
  repo_root = $RepoRoot
  sandbox = $Sandbox
  model = $Model
  launch_mode = $LaunchMode
  visible_terminal_requested = ($LaunchMode -eq 'Visible')
  worker_count = $Launches.Count
  worker_filter = $WorkerId
  launches = $Launches
  status = @(Get-WorkerStatusRows)
} | ConvertTo-Json -Depth 8
