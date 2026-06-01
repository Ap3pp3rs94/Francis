[CmdletBinding()]
param(
  [ValidateSet('Status', 'PreSleep', 'PostResume')]
  [string]$Mode = 'Status',

  [string]$OutputDir = '',

  [string]$PreSleepEvidencePath = '',

  [string]$ContinuityRecordId = '',

  [string]$SourceNodeId = 'stage16-local-workstation',

  [string]$PairedNodeId = 'stage16-local-loopback-node',

  [string]$TraceId = '',

  [string]$AuthoritySnapshotId = '',

  [string]$RedactionSummary = 'metadata_only_no_private_payload',

  [switch]$OperatorConfirmedSleepResume,

  [switch]$CommitEvidence
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Get-UnixTimeSeconds {
  return [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
}

function New-Stage16Id {
  param([string]$Prefix)
  return ('{0}-{1}' -f $Prefix, [guid]::NewGuid().ToString('N'))
}

function ConvertTo-SafeFileStem {
  param([string]$Value)
  $Text = ([string]$Value).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return [guid]::NewGuid().ToString('N')
  }
  return [regex]::Replace($Text, '[^A-Za-z0-9_.-]', '_')
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

function Write-Stage16Failure {
  param(
    [string]$ErrorCode,
    [string]$EvidenceRoot
  )
  [ordered]@{
    ok = $false
    kind = 'francis.stage16.federation.sleep_continuity_evidence'
    status = 'blocked'
    mode = $Mode.ToLowerInvariant()
    repo_root = $RepoRoot
    evidence_root = $EvidenceRoot
    error = $ErrorCode
    evidence_written = $false
    commit_evidence = [bool]$CommitEvidence
    operator_confirmation_required = $true
    writes_runtime_readback = $false
    marks_stage16_closed = $false
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  } | ConvertTo-Json -Depth 8
}

function New-GovernancePayload {
  [ordered]@{
    operator_supplied_evidence = $true
    explicit_operator_confirmation_required = $true
    does_not_infer_sleep_from_delay = $true
    metadata_only = $true
    contains_raw_private_data = $false
    contains_raw_prompt_body = $false
    contains_raw_model_response = $false
    writes_runtime_readback = $false
    marks_stage16_closed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    subdelegation_allowed = $false
    committed_pre_sleep_path_must_stay_under_project_evidence_root = $true
    committed_pre_sleep_path_traversal_blocked = $true
  }
}

function Write-JsonFile {
  param(
    [string]$Path,
    [object]$Payload
  )
  $Utf8NoBom = [System.Text.UTF8Encoding]::new($false)
  [System.IO.File]::WriteAllText($Path, (($Payload | ConvertTo-Json -Depth 8) + [Environment]::NewLine), $Utf8NoBom)
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

$ProjectEvidenceRoot = [System.IO.Path]::GetFullPath((Join-Path $RepoRoot 'data\test_runs\federation-stage16-sleep-continuity-evidence'))
if ($CommitEvidence) {
  $Profile = ([string]$env:FRANCIS_ENV_PROFILE).Trim().ToLowerInvariant()
  if ([string]::IsNullOrWhiteSpace($Profile)) {
    $Profile = 'dev'
  }
  if (@('production', 'prod', 'regulated') -contains $Profile) {
    Write-Stage16Failure -ErrorCode 'commit_evidence_blocked_in_env_profile' -EvidenceRoot $ProjectEvidenceRoot
    exit 1
  }
  $EvidenceRoot = $ProjectEvidenceRoot
} elseif ([string]::IsNullOrWhiteSpace($OutputDir)) {
  $EvidenceRoot = [System.IO.Path]::GetFullPath((Join-Path ([System.IO.Path]::GetTempPath()) ('francis-stage16-sleep-continuity-evidence\' + [guid]::NewGuid().ToString('N'))))
} else {
  $EvidenceRoot = [System.IO.Path]::GetFullPath($OutputDir)
}

if ($Mode -eq 'Status') {
  [ordered]@{
    ok = $true
    kind = 'francis.stage16.federation.sleep_continuity_evidence'
    status = 'ready_for_operator_evidence'
    mode = 'status'
    repo_root = $RepoRoot
    evidence_root = $EvidenceRoot
    evidence_written = $false
    commit_evidence = [bool]$CommitEvidence
    required_sequence = @('PreSleep', 'operator sleep/resume', 'PostResume', 'runtime proof with CommitReceipts')
    pre_sleep_command = 'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PreSleep -CommitEvidence'
    post_resume_command = 'scripts/federation-stage16-sleep-continuity-evidence.ps1 -Mode PostResume -CommitEvidence -PreSleepEvidencePath <pre_sleep.json> -OperatorConfirmedSleepResume'
    proof_command = 'scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts -PreSleepEvidencePath <pre_sleep.json> -PostResumeEvidencePath <post_resume.json>'
    governance = New-GovernancePayload
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  } | ConvertTo-Json -Depth 8
  exit 0
}

New-Item -ItemType Directory -Force -Path $EvidenceRoot | Out-Null
$Now = Get-UnixTimeSeconds

if ($Mode -eq 'PreSleep') {
  if ([string]::IsNullOrWhiteSpace($ContinuityRecordId)) {
    $ContinuityRecordId = New-Stage16Id -Prefix 'stage16-sleep-continuity'
  }
  if ([string]::IsNullOrWhiteSpace($TraceId)) {
    $TraceId = New-Stage16Id -Prefix 'trace-stage16-sleep-continuity'
  }
  if ([string]::IsNullOrWhiteSpace($AuthoritySnapshotId)) {
    $AuthoritySnapshotId = New-Stage16Id -Prefix 'authsnap-stage16-sleep'
  }

  $FileStem = ConvertTo-SafeFileStem -Value $ContinuityRecordId
  $EvidencePath = Join-Path $EvidenceRoot ('pre_sleep_{0}.json' -f $FileStem)
  $Payload = [ordered]@{
    evidence_kind = 'stage16_sleep_continuity_pre_sleep'
    continuity_record_id = $ContinuityRecordId
    source_node_id = $SourceNodeId
    paired_node_id = $PairedNodeId
    trace_id = $TraceId
    authority_snapshot_id = $AuthoritySnapshotId
    source_recorded_ts = $Now
    freshness_state = 'fresh'
    capture_mode = 'explicit_operator_pre_sleep_marker'
    governance = New-GovernancePayload
  }
  Write-JsonFile -Path $EvidencePath -Payload $Payload

  [ordered]@{
    ok = $true
    kind = 'francis.stage16.federation.sleep_continuity_evidence'
    status = 'pre_sleep_evidence_written'
    mode = 'presleep'
    repo_root = $RepoRoot
    evidence_root = $EvidenceRoot
    evidence_path = $EvidencePath
    evidence_written = $true
    commit_evidence = [bool]$CommitEvidence
    continuity_record_id = $ContinuityRecordId
    source_node_id = $SourceNodeId
    paired_node_id = $PairedNodeId
    trace_id = $TraceId
    authority_snapshot_id = $AuthoritySnapshotId
    operator_next_step = 'sleep_or_suspend_workstation_then_run_postresume_with_operator_confirmation'
    governance = New-GovernancePayload
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  } | ConvertTo-Json -Depth 8
  exit 0
}

if ($Mode -eq 'PostResume') {
  if (-not $OperatorConfirmedSleepResume) {
    Write-Stage16Failure -ErrorCode 'operator_sleep_resume_confirmation_required' -EvidenceRoot $EvidenceRoot
    exit 1
  }
  if ([string]::IsNullOrWhiteSpace($PreSleepEvidencePath)) {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_path_required' -EvidenceRoot $EvidenceRoot
    exit 1
  }
  $PrePath = [System.IO.Path]::GetFullPath($PreSleepEvidencePath)
  if (-not (Test-Path -LiteralPath $PrePath -PathType Leaf)) {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_file_missing' -EvidenceRoot $EvidenceRoot
    exit 1
  }
  if ($CommitEvidence -and -not (Test-PathInsideRoot -Path $PrePath -Root $ProjectEvidenceRoot)) {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_path_outside_commit_root' -EvidenceRoot $EvidenceRoot
    exit 1
  }

  $Pre = Get-Content -Raw -LiteralPath $PrePath | ConvertFrom-Json
  if ([string](Get-JsonProperty -Payload $Pre -Name 'evidence_kind' -Default '') -ne 'stage16_sleep_continuity_pre_sleep') {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_kind_invalid' -EvidenceRoot $EvidenceRoot
    exit 1
  }
  if ([string](Get-JsonProperty -Payload $Pre -Name 'freshness_state' -Default '') -ne 'fresh') {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_not_fresh' -EvidenceRoot $EvidenceRoot
    exit 1
  }

  $ContinuityRecordId = [string](Get-JsonProperty -Payload $Pre -Name 'continuity_record_id' -Default '')
  $SourceNodeId = [string](Get-JsonProperty -Payload $Pre -Name 'source_node_id' -Default '')
  $PairedNodeId = [string](Get-JsonProperty -Payload $Pre -Name 'paired_node_id' -Default '')
  $TraceId = [string](Get-JsonProperty -Payload $Pre -Name 'trace_id' -Default '')
  $AuthoritySnapshotId = [string](Get-JsonProperty -Payload $Pre -Name 'authority_snapshot_id' -Default '')
  $PreTs = [int64](Get-JsonProperty -Payload $Pre -Name 'source_recorded_ts' -Default 0)
  if (
    [string]::IsNullOrWhiteSpace($ContinuityRecordId) -or
    [string]::IsNullOrWhiteSpace($SourceNodeId) -or
    [string]::IsNullOrWhiteSpace($PairedNodeId) -or
    [string]::IsNullOrWhiteSpace($TraceId) -or
    [string]::IsNullOrWhiteSpace($AuthoritySnapshotId) -or
    $PreTs -le 0
  ) {
    Write-Stage16Failure -ErrorCode 'pre_sleep_evidence_missing_required_fields' -EvidenceRoot $EvidenceRoot
    exit 1
  }
  if ($Now -le $PreTs) {
    $Now = $PreTs + 1
  }

  $FileStem = ConvertTo-SafeFileStem -Value $ContinuityRecordId
  $EvidencePath = Join-Path $EvidenceRoot ('post_resume_{0}.json' -f $FileStem)
  $Payload = [ordered]@{
    evidence_kind = 'stage16_sleep_continuity_post_resume'
    continuity_record_id = $ContinuityRecordId
    source_node_id = $SourceNodeId
    paired_node_id = $PairedNodeId
    trace_id = $TraceId
    authority_snapshot_id = $AuthoritySnapshotId
    received_ts = $Now
    freshness_state = 'fresh'
    redaction_summary = $RedactionSummary
    sleep_observed = $true
    resume_observed = $true
    continuity_available_after_resume = $true
    revoked_links_present_current_state = $false
    stale_state_implies_current_authority = $false
    capture_mode = 'explicit_operator_post_resume_confirmation'
    pre_sleep_evidence_path = $PrePath
    governance = New-GovernancePayload
  }
  Write-JsonFile -Path $EvidencePath -Payload $Payload

  [ordered]@{
    ok = $true
    kind = 'francis.stage16.federation.sleep_continuity_evidence'
    status = 'post_resume_evidence_written'
    mode = 'postresume'
    repo_root = $RepoRoot
    evidence_root = $EvidenceRoot
    evidence_path = $EvidencePath
    pre_sleep_evidence_path = $PrePath
    evidence_written = $true
    commit_evidence = [bool]$CommitEvidence
    continuity_record_id = $ContinuityRecordId
    source_node_id = $SourceNodeId
    paired_node_id = $PairedNodeId
    trace_id = $TraceId
    authority_snapshot_id = $AuthoritySnapshotId
    operator_confirmed_sleep_resume = $true
    proof_command = ('scripts/federation-stage16-sleep-continuity-runtime-proof.ps1 -Mode Status -CommitReceipts -PreSleepEvidencePath "{0}" -PostResumeEvidencePath "{1}"' -f $PrePath, $EvidencePath)
    governance = New-GovernancePayload
    next_smallest_truthful_gap = 'stage16_sleep_continuity_runtime_readback'
  } | ConvertTo-Json -Depth 8
  exit 0
}
