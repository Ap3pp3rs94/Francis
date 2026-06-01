[CmdletBinding()]
param(
  [ValidateSet('Status', 'Run')]
  [string]$Mode = 'Status',

  [string]$OutputDir = '',

  [string]$DataDir = '',

  [string]$PreSleepEvidencePath = '',

  [switch]$OperatorConfirmedSleepResume,

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
$StatusPostResumeCommand = "scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath $PreSleepArg -OperatorConfirmedSleepResume"
$StatusSequenceCommand = "scripts/federation-stage16-sleep-continuity-post-resume-sequence.ps1 -Mode Run -CommitEvidence -CommitReceipts -PreSleepEvidencePath $PreSleepArg -OperatorConfirmedSleepResume"

if ($Mode -eq 'Status') {
  Write-SequencePayload -Payload ([ordered]@{
    ok = $true
    kind = 'francis.stage16.federation.sleep_continuity_post_resume_sequence'
    status = 'ready_for_operator_confirmed_post_resume_sequence'
    mode = 'status'
    repo_root = $RepoRoot
    pre_sleep_evidence_path = $PreSleepEvidencePath
    operator_confirmed_sleep_resume = $false
    run_available_after_operator_confirmation = -not [string]::IsNullOrWhiteSpace($PreSleepEvidencePath)
    required_sequence = @('operator-confirmed sleep/resume', 'PostResume evidence', 'runtime proof receipt')
    post_resume_command = $StatusPostResumeCommand
    sequence_command = $StatusSequenceCommand
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
