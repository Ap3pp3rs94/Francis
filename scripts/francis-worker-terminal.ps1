param(
  [Parameter(Mandatory = $true)]
  [ValidateSet('worker-1-orb-voice-proof', 'worker-2-lens-overlay-spatial', 'worker-3-voice-receipts', 'worker-4-stage17-completion')]
  [string]$WorkerId,

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

if ([string]::IsNullOrWhiteSpace($PromptPath)) {
  $PromptPath = Join-Path $RepoRoot ("docs/operations/worker_prompts/{0}.md" -f $WorkerId)
}
$ResolvedPromptPath = (Resolve-Path -LiteralPath $PromptPath).Path
$Prompt = Get-Content -LiteralPath $ResolvedPromptPath -Raw -Encoding UTF8
$PromptHash = Get-WorkerFileSha256 -Path $ResolvedPromptPath

$SessionRoot = Join-Path $RepoRoot '.francis\worker-terminal-sessions'
New-Item -ItemType Directory -Force -Path $SessionRoot | Out-Null
$SessionPath = Join-Path $SessionRoot ('{0}.json' -f $WorkerId)
$SessionPayload = [ordered]@{
  kind = 'francis.worker_terminal.session'
  worker_id = $WorkerId
  prompt_path = $ResolvedPromptPath
  prompt_sha256 = $PromptHash
  prompt_char_count = $Prompt.Length
  repo_root = $RepoRoot
  pid = $PID
  started_at = [DateTimeOffset]::UtcNow.ToString('o')
  sandbox = $Sandbox
  model = $Model
  launch_mode = $LaunchMode
  codex_cli = 'codex'
  visible_terminal_requested = ($LaunchMode -eq 'Visible')
  continuum_started = $false
  uncontrolled_recursion_allowed = $false
}
$SessionPayload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SessionPath -Encoding UTF8

$Host.UI.RawUI.WindowTitle = "Francis $WorkerId"
Set-Location -LiteralPath $RepoRoot

$CodexArgs = @(
  '--cd', $RepoRoot,
  '--sandbox', $Sandbox,
  '--ask-for-approval', 'never',
  '--no-alt-screen'
)
if (-not [string]::IsNullOrWhiteSpace($Model)) {
  $CodexArgs += @('--model', $Model)
}
$CodexArgs += $Prompt

try {
  & codex @CodexArgs
  $ExitCode = $LASTEXITCODE
} catch {
  Write-Host ("Francis worker {0} failed to start Codex: {1}" -f $WorkerId, $_.Exception.Message)
  $ExitCode = 1
}

$SessionPayload.completed_at = [DateTimeOffset]::UtcNow.ToString('o')
$SessionPayload.exit_code = $ExitCode
$SessionPayload | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $SessionPath -Encoding UTF8

if ($LaunchMode -eq 'Visible') {
  Write-Host ""
  Write-Host ("Francis worker {0} exited with code {1}." -f $WorkerId, $ExitCode)
  Read-Host "Press Enter to close this worker terminal"
} else {
  Write-Output ("Francis worker {0} exited with code {1}." -f $WorkerId, $ExitCode)
}
exit $ExitCode
