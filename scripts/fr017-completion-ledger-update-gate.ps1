[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$ManifestPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = '',

  [string]$FinalDecisionPath = '',

  [string]$LedgerEntryPath = '',

  [string]$CompletionLedgerPath = 'docs\operations\COMPLETION_LEDGER.md'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$CompletionLedgerGateScript = Join-Path $PSScriptRoot 'fr017-completion-ledger-gate.ps1'
$ExpectedCompletionLedgerGateStatus = 'ready_for_operator_completion_ledger_update'
$ExpectedStatus = 'ready_for_operator_stage17_completion_ledger_update_review'
$ExpectedNextCompletionLedgerInput = 'operator_updates_or_provides_completion_ledger_file_containing_reviewed_FR-017_handoff_entry_then_reruns_completion_ledger_update_gate'

function Resolve-GatePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Add-OptionalArg {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Name,
    [string]$Value
  )

  if (-not [string]::IsNullOrWhiteSpace($Value)) {
    $Target.Add($Name) | Out-Null
    $Target.Add($Value) | Out-Null
  }
}

function Invoke-JsonGate {
  param(
    [string]$ScriptPath,
    [string[]]$Arguments
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ScriptPath
  ) + $Arguments

  $RawOutput = & $PowerShellExe @GateArgs
  $GateExitCode = $LASTEXITCODE
  $Payload = $null
  $ParseOk = $false
  try {
    $Payload = ($RawOutput | Out-String) | ConvertFrom-Json -ErrorAction Stop
    $ParseOk = $true
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $GateExitCode
    parse_ok = $ParseOk
    payload = $Payload
    raw_output = ($RawOutput | Out-String)
  }
}

function Get-PropertyValue {
  param(
    [object]$Payload,
    [string]$Name,
    [object]$Default = $null
  )

  if ($null -eq $Payload) {
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function Add-RequiredLedgerText {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [string]$Field,
    [string]$Text,
    [string[]]$RequiredTerms
  )

  foreach ($Term in $RequiredTerms) {
    if ([string]::IsNullOrWhiteSpace($Term)) {
      continue
    }
    if ($Text.IndexOf($Term, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      $Missing.Add($Field) | Out-Null
      return
    }
  }
}

function Add-RequiredLedgerAnyText {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [string]$Field,
    [string]$Text,
    [string[]]$AnyTerms
  )

  foreach ($Term in $AnyTerms) {
    if (-not [string]::IsNullOrWhiteSpace($Term) -and $Text.IndexOf($Term, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return
    }
  }
  $Missing.Add($Field) | Out-Null
}

function Add-ProhibitedLedgerPhrase {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Text,
    [string]$Phrase
  )

  if ($Text.IndexOf($Phrase, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
    $Target.Add(('completion_ledger_update.{0}' -f $Phrase.Replace(' ', '_'))) | Out-Null
  }
}

function Get-FirstLedgerHeading {
  param([string]$Text)

  $Lines = $Text -split "\r?\n"
  foreach ($Line in $Lines) {
    $Trimmed = $Line.Trim()
    if ($Trimmed.StartsWith('### ', [System.StringComparison]::Ordinal)) {
      return $Trimmed
    }
  }
  return ''
}

function Get-LedgerSectionByHeading {
  param(
    [string]$Text,
    [string]$Heading
  )

  if ([string]::IsNullOrWhiteSpace($Heading)) {
    return ''
  }

  $Lines = $Text -split "\r?\n"
  $Found = $false
  $SectionLines = New-Object System.Collections.Generic.List[string]
  foreach ($Line in $Lines) {
    $Trimmed = $Line.Trim()
    if (-not $Found) {
      if ([string]::Equals($Trimmed, $Heading, [System.StringComparison]::OrdinalIgnoreCase)) {
        $Found = $true
        $SectionLines.Add($Line) | Out-Null
      }
      continue
    }

    if ($Trimmed.StartsWith('### ', [System.StringComparison]::Ordinal)) {
      break
    }
    $SectionLines.Add($Line) | Out-Null
  }

  if (-not $Found) {
    return ''
  }
  return ($SectionLines.ToArray() -join [Environment]::NewLine)
}

$CompletionLedgerArgs = New-Object System.Collections.Generic.List[string]
$CompletionLedgerArgs.Add('-Mode') | Out-Null
$CompletionLedgerArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath
Add-OptionalArg -Target $CompletionLedgerArgs -Name '-LedgerEntryPath' -Value $LedgerEntryPath

$CompletionLedgerGate = Invoke-JsonGate -ScriptPath $CompletionLedgerGateScript -Arguments $CompletionLedgerArgs.ToArray()
$CompletionLedgerGateStatus = if ([bool]$CompletionLedgerGate.parse_ok) { [string](Get-PropertyValue -Payload $CompletionLedgerGate.payload -Name 'status' -Default '') } else { 'failed_gate_parse' }
$CompletionLedgerGateReady = [bool]$CompletionLedgerGate.parse_ok -and [int]$CompletionLedgerGate.exit_code -eq 0 -and $CompletionLedgerGateStatus -eq $ExpectedCompletionLedgerGateStatus
$CompletionLedgerGateFailed = (-not [bool]$CompletionLedgerGate.parse_ok) -or [int]$CompletionLedgerGate.exit_code -ne 0 -or $CompletionLedgerGateStatus.StartsWith('failed_') -or $CompletionLedgerGateStatus.StartsWith('missing_') -or $CompletionLedgerGateStatus.StartsWith('invalid_')
$ResolvedFinalDecisionPath = if ([string]::IsNullOrWhiteSpace($FinalDecisionPath)) { '' } else { Resolve-GatePath -Path $FinalDecisionPath }
$ResolvedLedgerEntryPath = if ([string]::IsNullOrWhiteSpace($LedgerEntryPath)) { '' } else { Resolve-GatePath -Path $LedgerEntryPath }
$ResolvedCompletionLedgerPath = if ([string]::IsNullOrWhiteSpace($CompletionLedgerPath)) { '' } else { Resolve-GatePath -Path $CompletionLedgerPath }

$LedgerEntryText = ''
$CandidateLedgerHeading = ''
$CompletionLedgerText = ''
$CompletionLedgerSection = ''
$CompletionLedgerExists = -not [string]::IsNullOrWhiteSpace($ResolvedCompletionLedgerPath) -and (Test-Path -LiteralPath $ResolvedCompletionLedgerPath -PathType Leaf)
$CompletionLedgerReadOk = $false
$LedgerUpdateSectionFound = $false
$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$FailedReasons = New-Object System.Collections.Generic.List[string]

if ($CompletionLedgerGateReady) {
  try {
    $LedgerEntryText = Get-Content -LiteralPath $ResolvedLedgerEntryPath -Raw
    $CandidateLedgerHeading = Get-FirstLedgerHeading -Text $LedgerEntryText
  } catch {
    $InvalidFields.Add('candidate_ledger_entry_path') | Out-Null
    $FailedReasons.Add('candidate_ledger_entry_read_failed') | Out-Null
  }

  if ([string]::IsNullOrWhiteSpace($CandidateLedgerHeading)) {
    $InvalidFields.Add('candidate_ledger_heading') | Out-Null
    $FailedReasons.Add('candidate_ledger_heading_missing') | Out-Null
  }

  if ([string]::IsNullOrWhiteSpace($ResolvedCompletionLedgerPath)) {
    $MissingFields.Add('completion_ledger_path') | Out-Null
  } elseif (-not $CompletionLedgerExists) {
    $MissingFields.Add('completion_ledger_path') | Out-Null
  } else {
    try {
      $CompletionLedgerText = Get-Content -LiteralPath $ResolvedCompletionLedgerPath -Raw
      $CompletionLedgerReadOk = $true
    } catch {
      $InvalidFields.Add('completion_ledger_path') | Out-Null
      $FailedReasons.Add('completion_ledger_read_failed') | Out-Null
    }
  }

  if ($CompletionLedgerReadOk -and -not [string]::IsNullOrWhiteSpace($CandidateLedgerHeading)) {
    $CompletionLedgerSection = Get-LedgerSectionByHeading -Text $CompletionLedgerText -Heading $CandidateLedgerHeading
    $LedgerUpdateSectionFound = -not [string]::IsNullOrWhiteSpace($CompletionLedgerSection)
    if (-not $LedgerUpdateSectionFound) {
      $MissingFields.Add('completion_ledger_update.candidate_heading') | Out-Null
    }
  }
}

if ($CompletionLedgerGateReady -and $LedgerUpdateSectionFound) {
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.stage17_scope' -Text $CompletionLedgerSection -RequiredTerms @('Stage 17', 'FR-017', 'Forearm Cuffs')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.final_decision_status' -Text $CompletionLedgerSection -RequiredTerms @('ready_for_completion_ledger_review')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.final_decision_record_path' -Text $CompletionLedgerSection -RequiredTerms @($ResolvedFinalDecisionPath)
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.physical_validation_complete_false' -Text $CompletionLedgerSection -RequiredTerms @('physical_validation_complete', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.stage17_completion_claim_allowed_false' -Text $CompletionLedgerSection -RequiredTerms @('stage17_completion_claim_allowed', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.fr018_implementation_cleared_false' -Text $CompletionLedgerSection -RequiredTerms @('fr018_implementation_cleared', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'completion_ledger_update.fr018_scope' -Text $CompletionLedgerSection -RequiredTerms @('FR-018')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'completion_ledger_update.fr018_blocked_or_not_cleared' -Text $CompletionLedgerSection -AnyTerms @('blocked', 'not cleared', 'not_cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'completion_ledger_update.powered_testing_not_cleared' -Text $CompletionLedgerSection -AnyTerms @('powered testing: not cleared', 'powered testing remains blocked', 'powered testing not cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'completion_ledger_update.frame_coupled_testing_not_cleared' -Text $CompletionLedgerSection -AnyTerms @('frame-coupled testing: not cleared', 'frame-coupled testing remains blocked', 'frame-coupled testing not cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'completion_ledger_update.load_bearing_not_approved' -Text $CompletionLedgerSection -AnyTerms @('load-bearing use: not approved', 'load-bearing use remains blocked', 'load-bearing use not approved')

  foreach ($Phrase in @(
      'FR-018 cleared',
      'FR018 cleared',
      'powered testing cleared',
      'frame-coupled testing cleared',
      'load-bearing approved',
      'load bearing approved',
      'physical_validation_complete: true',
      'physical_validation_complete = true',
      'stage17_completion_claim_allowed: true',
      'stage17_completion_claim_allowed = true',
      'fr018_implementation_cleared: true',
      'fr018_implementation_cleared = true'
    )) {
    Add-ProhibitedLedgerPhrase -Target $ProhibitedClearanceFlags -Text $CompletionLedgerSection -Phrase $Phrase
  }
}

if (-not $CompletionLedgerGateReady) {
  $Status = if ($CompletionLedgerGateFailed) { 'failed_completion_ledger_handoff' } else { 'pending_completion_ledger_handoff' }
  $ExitCode = if ($CompletionLedgerGateFailed) { 1 } else { 0 }
} elseif ($InvalidFields.Count -gt 0 -or $ProhibitedClearanceFlags.Count -gt 0) {
  $Status = 'failed_completion_ledger_update'
  $ExitCode = 1
} elseif ($MissingFields.Count -gt 0) {
  $Status = 'pending_completion_ledger_update'
  $ExitCode = 0
} else {
  $Status = $ExpectedStatus
  $ExitCode = 0
}

$Output = [ordered]@{
  kind = 'francis.fr017.completion_ledger_update_gate'
  mode = $Mode
  status = $Status
  completion_ledger_gate_status = $CompletionLedgerGateStatus
  completion_ledger_gate_exit_code = [int]$CompletionLedgerGate.exit_code
  completion_ledger_gate_parse_ok = [bool]$CompletionLedgerGate.parse_ok
  completion_ledger_handoff_ready = $CompletionLedgerGateReady
  completion_ledger_handoff_failed = $CompletionLedgerGateFailed
  final_decision_record_path = $ResolvedFinalDecisionPath
  candidate_ledger_entry_path = $ResolvedLedgerEntryPath
  candidate_ledger_heading = $CandidateLedgerHeading
  completion_ledger_path = $ResolvedCompletionLedgerPath
  completion_ledger_exists = $CompletionLedgerExists
  completion_ledger_read_ok = $CompletionLedgerReadOk
  ledger_update_section_found = $LedgerUpdateSectionFound
  ledger_update_review_ready = ($Status -eq $ExpectedStatus)
  completion_ledger_update_guard_contract = 'This gate validates that the actual or proposed completion ledger contains the reviewed FR-017 handoff section and preserves no-clearance language. It is read-only and does not write the ledger, certify physical validation, clear powered/frame/load use, or clear FR-018.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  prohibited_clearance_flags = @($ProhibitedClearanceFlags.ToArray())
  failed_reasons = @($FailedReasons.ToArray())
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  next_required_completion_ledger_update_input = if ($Status -eq $ExpectedStatus) {
    'operator_may_review_completion_ledger_update_evidence_without_FR-018_clearance'
  } else {
    $ExpectedNextCompletionLedgerInput
  }
  no_fake_validation_lock = 'A ready completion-ledger update review means the ledger section preserves FR-017 evidence references and blocked-clearance language. The script still does not mark Stage 17 complete or clear FR-018.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
