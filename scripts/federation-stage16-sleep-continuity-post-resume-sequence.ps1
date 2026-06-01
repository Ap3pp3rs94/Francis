[CmdletBinding()]
param(
  [ValidateSet('Status', 'Run')]
  [string]$Mode = 'Status',

  [string]$OutputDir = '',

  [string]$DataDir = '',

  [string]$PreSleepEvidencePath = '',

  [switch]$OperatorConfirmedSleepResume,

  [switch]$RequireConfirmationReceipt,

  [string]$ConfirmationReceiptId = '',

  [switch]$CommitEvidence,

  [switch]$CommitReceipts
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Write-SequencePayload {
  param([object]$Payload)
  $Payload | ConvertTo-Json -Depth 10
}

function New-GovernancePayload {
  [ordered]@{
    explicit_operator_confirmation_required = $true
    run_requires_operator_confirmed_sleep_resume = $true
    confirmation_receipt_supported = $true
    confirmation_receipt_required = [bool]$RequireConfirmationReceipt
    confirmation_receipt_id_required_when_enabled = $true
    confirmation_receipt_must_match_pre_sleep_evidence_path = $true
    does_not_infer_sleep_from_delay = $true
    uses_bounded_child_scripts = $true
    child_scripts_are_invoked_with_argument_lists = $true
    status_projection_only = $Mode -eq 'Status'
    status_runs_shell = $false
    status_writes_evidence = $false
    status_writes_receipts = $false
    run_writes_evidence = $Mode -eq 'Run'
    run_writes_runtime_readback_receipt = $Mode -eq 'Run'
    marks_stage16_closed = $false
    writes_memory = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    production_commit_blocked = $true
  }
}

function Write-SequenceFailure {
  param(
    [string]$ErrorCode,
    [AllowNull()]
    [object]$EvidenceResult = $null,
    [AllowNull()]
    [object]$ProofResult = $null
  )
  Write-SequencePayload -Payload ([ordered]@{
    ok = $false
    kind = 'francis.stage16.federation.sleep_continuity_post_resume_sequence'
    status = 'blocked'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    error = $ErrorCode
    pre_sleep_evidence_path = $PreSleepEvidencePath
    operator_confirmed_sleep_resume = [bool]$OperatorConfirmedSleepResume
    require_confirmation_receipt = [bool]$RequireConfirmationReceipt
    confirmation_receipt_id = $ConfirmationReceiptId
    confirmation_receipt = $null
    post_resume_evidence_path = ''
    runtime_proof_receipt_id = ''
    evidence_result = $EvidenceResult
    runtime_proof_result = $ProofResult
    governance = New-GovernancePayload
    writes_evidence = $false
    writes_receipts = $false
    marks_stage16_closed = $false
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  })
}

function Get-JsonProperty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name,
    [AllowNull()]
    [object]$Default = $null
  )
  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    return $Default
  }
  return $Property.Value
}

function Test-PathInsideRoot {
  param(
    [string]$Path,
    [string]$Root
  )
  $FullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
  $FullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd('\', '/')
  return (
    $FullPath.Equals($FullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $FullPath.StartsWith(($FullRoot + [System.IO.Path]::DirectorySeparatorChar), [System.StringComparison]::OrdinalIgnoreCase)
  )
}

function Get-DataRoot {
  if ([string]::IsNullOrWhiteSpace($DataDir)) {
    return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'data'))
  }
  return [System.IO.Path]::GetFullPath($DataDir)
}

function Read-ConfirmationReceipt {
  param(
    [string]$ReceiptId,
    [string]$ExpectedPreSleepPath
  )
  $Root = Get-DataRoot
  $ReceiptLogPath = [System.IO.Path]::GetFullPath((Join-Path $Root 'logs\federation\stage16_sleep_resume_operator_confirmations.jsonl'))
  if (-not (Test-PathInsideRoot -Path $ReceiptLogPath -Root $Root)) {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_path_outside_data_root'
      receipt = $null
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }
  if (-not (Test-Path -LiteralPath $ReceiptLogPath -PathType Leaf)) {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_log_missing'
      receipt = $null
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }
  $MatchedReceipt = $null
  foreach ($Line in [System.IO.File]::ReadLines($ReceiptLogPath)) {
    if ([string]::IsNullOrWhiteSpace($Line)) {
      continue
    }
    try {
      $Candidate = $Line | ConvertFrom-Json
    } catch {
      continue
    }
    if ([string](Get-JsonProperty -Payload $Candidate -Name 'receipt_id' -Default '') -eq $ReceiptId) {
      $MatchedReceipt = $Candidate
    }
  }
  if ($null -eq $MatchedReceipt) {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_not_found'
      receipt = $null
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }

  $ReceiptKind = [string](Get-JsonProperty -Payload $MatchedReceipt -Name 'kind' -Default '')
  $ReceiptDecision = [string](Get-JsonProperty -Payload $MatchedReceipt -Name 'decision' -Default '')
  $ReceiptPreSleepPath = [string](Get-JsonProperty -Payload $MatchedReceipt -Name 'pre_sleep_evidence_path' -Default '')
  $ReceiptConfirmed = [bool](Get-JsonProperty -Payload $MatchedReceipt -Name 'operator_confirmed_sleep_resume' -Default $false)
  $ExpectedPath = [System.IO.Path]::GetFullPath($ExpectedPreSleepPath)
  $ReceiptPathValue = if ([string]::IsNullOrWhiteSpace($ReceiptPreSleepPath)) { '' } else { [System.IO.Path]::GetFullPath($ReceiptPreSleepPath) }
  if ($ReceiptKind -ne 'francis.stage16.federation.sleep_resume_operator_confirmation_receipt') {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_kind_mismatch'
      receipt = $MatchedReceipt
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }
  if (-not $ReceiptConfirmed -or $ReceiptDecision -ne 'operator_confirmed_sleep_resume') {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_not_operator_confirmed'
      receipt = $MatchedReceipt
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }
  if ($ReceiptPathValue -ne $ExpectedPath) {
    return [ordered]@{
      ok = $false
      error = 'confirmation_receipt_pre_sleep_path_mismatch'
      receipt = $MatchedReceipt
      receipt_path = $ReceiptLogPath
      data_root = $Root
    }
  }
  return [ordered]@{
    ok = $true
    error = ''
    receipt = $MatchedReceipt
    receipt_path = $ReceiptLogPath
    data_root = $Root
  }
}

function Invoke-JsonScript {
  param(
    [string]$ScriptPath,
    [hashtable]$ScriptParams
  )
  $Output = & $ScriptPath @ScriptParams 2>&1
  $ExitCode = if ($null -eq $global:LASTEXITCODE) { 0 } else { [int]$global:LASTEXITCODE }
  $Stdout = ($Output | Out-String).Trim()
  $Payload = $null
  if (-not [string]::IsNullOrWhiteSpace($Stdout)) {
    try {
      $Payload = $Stdout | ConvertFrom-Json
    } catch {
      $Payload = $null
    }
  }
  return [ordered]@{
    exit_code = $ExitCode
    stdout = $Stdout
    payload = $Payload
  }
}

$EvidenceScript = Join-Path $PSScriptRoot 'federation-stage16-sleep-continuity-evidence.ps1'
$RuntimeProofScript = Join-Path $PSScriptRoot 'federation-stage16-sleep-continuity-runtime-proof.ps1'
$PreSleepArg = if ([string]::IsNullOrWhiteSpace($PreSleepEvidencePath)) { '<pre_sleep.json>' } else { ('"{0}"' -f $PreSleepEvidencePath) }
$ReceiptIdArg = if ([string]::IsNullOrWhiteSpace($ConfirmationReceiptId)) { '<confirmation_receipt_id>' } else { $ConfirmationReceiptId }
$StatusPostResumeCommand = "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath $PreSleepArg -OperatorConfirmedSleepResume"
$StatusSequenceCommand = "scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath $PreSleepArg -OperatorConfirmedSleepResume"
$StatusReceiptBackedSequenceCommand = "$StatusSequenceCommand -RequireConfirmationReceipt -ConfirmationReceiptId $ReceiptIdArg"

if ($Mode -eq 'Status') {
  Write-SequencePayload -Payload ([ordered]@{
    ok = $true
    kind = 'francis.stage16.federation.sleep_continuity_post_resume_sequence'
    status = 'ready_for_operator_confirmed_post_resume_sequence'
    mode = 'status'
    repo_root = $RepoRoot
    pre_sleep_evidence_path = $PreSleepEvidencePath
    operator_confirmed_sleep_resume = $false
    require_confirmation_receipt = [bool]$RequireConfirmationReceipt
    confirmation_receipt_id = $ConfirmationReceiptId
    run_available_after_operator_confirmation = -not [string]::IsNullOrWhiteSpace($PreSleepEvidencePath)
    required_sequence = @('operator-confirmed sleep/resume receipt', 'PostResume evidence', 'runtime proof receipt')
    post_resume_command = $StatusPostResumeCommand
    sequence_command = $StatusSequenceCommand
    receipt_backed_sequence_command = $StatusReceiptBackedSequenceCommand
    output_dir = $OutputDir
    data_dir = $DataDir
    governance = New-GovernancePayload
    writes_evidence = $false
    writes_receipts = $false
    marks_stage16_closed = $false
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  })
  exit 0
}

if (-not $OperatorConfirmedSleepResume) {
  Write-SequenceFailure -ErrorCode 'operator_sleep_resume_confirmation_required'
  exit 1
}
if ([string]::IsNullOrWhiteSpace($PreSleepEvidencePath)) {
  Write-SequenceFailure -ErrorCode 'pre_sleep_evidence_path_required'
  exit 1
}
if ($RequireConfirmationReceipt -and [string]::IsNullOrWhiteSpace($ConfirmationReceiptId)) {
  Write-SequenceFailure -ErrorCode 'confirmation_receipt_id_required'
  exit 1
}
if ($RequireConfirmationReceipt) {
  $ConfirmationReceiptResult = Read-ConfirmationReceipt -ReceiptId $ConfirmationReceiptId -ExpectedPreSleepPath $PreSleepEvidencePath
  if (-not [bool]$ConfirmationReceiptResult.ok) {
    Write-SequencePayload -Payload ([ordered]@{
      ok = $false
      kind = 'francis.stage16.federation.sleep_continuity_post_resume_sequence'
      status = 'blocked'
      mode = $Mode.ToLowerInvariant()
      repo_root = $RepoRoot
      error = [string]$ConfirmationReceiptResult.error
      pre_sleep_evidence_path = $PreSleepEvidencePath
      operator_confirmed_sleep_resume = [bool]$OperatorConfirmedSleepResume
      require_confirmation_receipt = [bool]$RequireConfirmationReceipt
      confirmation_receipt_id = $ConfirmationReceiptId
      confirmation_receipt = $ConfirmationReceiptResult.receipt
      confirmation_receipt_path = [string]$ConfirmationReceiptResult.receipt_path
      post_resume_evidence_path = ''
      runtime_proof_receipt_id = ''
      governance = New-GovernancePayload
      writes_evidence = $false
      writes_receipts = $false
      marks_stage16_closed = $false
      next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
    })
    exit 1
  }
} else {
  $ConfirmationReceiptResult = [ordered]@{
    ok = $false
    error = ''
    receipt = $null
    receipt_path = ''
    data_root = ''
  }
}
if ($CommitEvidence -or $CommitReceipts) {
  $Profile = ([string]$env:FRANCIS_ENV_PROFILE).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($Profile)) {
    $Profile = 'dev'
  }
  if (@('production', 'prod', 'regulated') -contains $Profile) {
    Write-SequenceFailure -ErrorCode 'post_resume_sequence_commit_blocked_in_env_profile'
    exit 1
  }
}

$EvidenceParams = @{
  Mode = 'PostResume'
  PreSleepEvidencePath = $PreSleepEvidencePath
  OperatorConfirmedSleepResume = $true
}
if (-not [string]::IsNullOrWhiteSpace($OutputDir)) {
  $EvidenceParams.OutputDir = $OutputDir
}
if ($CommitEvidence) {
  $EvidenceParams.CommitEvidence = $true
}
$EvidenceResult = Invoke-JsonScript -ScriptPath $EvidenceScript -ScriptParams $EvidenceParams
if ([int]$EvidenceResult.exit_code -ne 0 -or $null -eq $EvidenceResult.payload -or -not [bool]$EvidenceResult.payload.ok) {
  Write-SequenceFailure -ErrorCode 'post_resume_evidence_child_failed' -EvidenceResult $EvidenceResult
  exit 1
}

$PostResumeEvidencePath = [string]$EvidenceResult.payload.evidence_path
if ([string]::IsNullOrWhiteSpace($PostResumeEvidencePath)) {
  Write-SequenceFailure -ErrorCode 'post_resume_evidence_path_missing_from_child' -EvidenceResult $EvidenceResult
  exit 1
}

$ProofParams = @{
  Mode = 'Status'
  PreSleepEvidencePath = $PreSleepEvidencePath
  PostResumeEvidencePath = $PostResumeEvidencePath
}
if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
  $ProofParams.DataDir = $DataDir
}
if ($CommitReceipts) {
  $ProofParams.CommitReceipts = $true
}
$ProofResult = Invoke-JsonScript -ScriptPath $RuntimeProofScript -ScriptParams $ProofParams
if ([int]$ProofResult.exit_code -ne 0 -or $null -eq $ProofResult.payload -or -not [bool]$ProofResult.payload.ok) {
  Write-SequenceFailure -ErrorCode 'runtime_proof_child_failed' -EvidenceResult $EvidenceResult -ProofResult $ProofResult
  exit 1
}

Write-SequencePayload -Payload ([ordered]@{
  ok = $true
  kind = 'francis.stage16.federation.sleep_continuity_post_resume_sequence'
  status = 'sequence_passed'
  mode = 'run'
  repo_root = $RepoRoot
  pre_sleep_evidence_path = $PreSleepEvidencePath
  post_resume_evidence_path = $PostResumeEvidencePath
  operator_confirmed_sleep_resume = $true
  require_confirmation_receipt = [bool]$RequireConfirmationReceipt
  confirmation_receipt_id = $ConfirmationReceiptId
  confirmation_receipt = $ConfirmationReceiptResult.receipt
  post_resume_evidence_status = [string]$EvidenceResult.payload.status
  runtime_proof_status = [string]$ProofResult.payload.status
  runtime_proof_receipt_id = [string]$ProofResult.payload.receipt_id
  readback_id = [string]$ProofResult.payload.readback_id
  completion_review_ready = [bool]$ProofResult.payload.completion_review_ready
  ready_to_close = [bool]$ProofResult.payload.ready_to_close
  evidence_result = $EvidenceResult.payload
  runtime_proof_result = $ProofResult.payload
  governance = New-GovernancePayload
  writes_evidence = $true
  writes_receipts = [bool]$CommitReceipts
  marks_stage16_closed = $false
  next_smallest_truthful_gap = [string]$ProofResult.payload.next_smallest_truthful_gap
})
exit 0
