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

  [string]$LedgerEntryPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FinalDecisionGateScript = Join-Path $PSScriptRoot 'fr017-final-decision-record-gate.ps1'
$ExpectedFinalDecisionStatus = 'ready_for_completion_ledger_review'
$ExpectedNextLedgerInput = 'create_candidate_completion_ledger_handoff_with_fr017-new-completion-ledger-handoff.ps1_then_rerun_completion_ledger_gate'
$CompletionLedgerHandoffInitializerPath = Join-Path $RepoRoot 'scripts\fr017-new-completion-ledger-handoff.ps1'
$CompletionLedgerHandoffTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md'

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

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
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
    $Target.Add(('ledger_entry.{0}' -f $Phrase.Replace(' ', '_'))) | Out-Null
  }
}

$FinalDecisionArgs = New-Object System.Collections.Generic.List[string]
$FinalDecisionArgs.Add('-Mode') | Out-Null
$FinalDecisionArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $FinalDecisionArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath
Add-OptionalArg -Target $FinalDecisionArgs -Name '-FinalDecisionPath' -Value $FinalDecisionPath

$FinalDecisionGate = Invoke-JsonGate -ScriptPath $FinalDecisionGateScript -Arguments $FinalDecisionArgs.ToArray()
$FinalDecisionGateStatus = if ([bool]$FinalDecisionGate.parse_ok) { [string](Get-PropertyValue -Payload $FinalDecisionGate.payload -Name 'status' -Default '') } else { 'failed_gate_parse' }
$FinalDecisionGateReady = [bool]$FinalDecisionGate.parse_ok -and [int]$FinalDecisionGate.exit_code -eq 0 -and $FinalDecisionGateStatus -eq $ExpectedFinalDecisionStatus
$FinalDecisionGateFailed = (-not [bool]$FinalDecisionGate.parse_ok) -or [int]$FinalDecisionGate.exit_code -ne 0 -or $FinalDecisionGateStatus.StartsWith('failed_') -or $FinalDecisionGateStatus.StartsWith('missing_') -or $FinalDecisionGateStatus.StartsWith('invalid_')
$ResolvedFinalDecisionPath = if ([string]::IsNullOrWhiteSpace($FinalDecisionPath)) { '' } else { Resolve-GatePath -Path $FinalDecisionPath }
$ResolvedLedgerEntryPath = if ([string]::IsNullOrWhiteSpace($LedgerEntryPath)) { '' } else { Resolve-GatePath -Path $LedgerEntryPath }
$LedgerEntryExists = -not [string]::IsNullOrWhiteSpace($ResolvedLedgerEntryPath) -and (Test-Path -LiteralPath $ResolvedLedgerEntryPath -PathType Leaf)
$LedgerEntryText = ''
$LedgerEntryReadOk = $false
$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$FailedReasons = New-Object System.Collections.Generic.List[string]

if ($FinalDecisionGateReady) {
  if ([string]::IsNullOrWhiteSpace($ResolvedLedgerEntryPath)) {
    $MissingFields.Add('ledger_entry_path') | Out-Null
  } elseif (-not $LedgerEntryExists) {
    $MissingFields.Add('ledger_entry_path') | Out-Null
    $FailedReasons.Add('ledger_entry_missing') | Out-Null
  } else {
    try {
      $LedgerEntryText = Get-Content -LiteralPath $ResolvedLedgerEntryPath -Raw
      $LedgerEntryReadOk = $true
    } catch {
      $InvalidFields.Add('ledger_entry_path') | Out-Null
      $FailedReasons.Add('ledger_entry_read_failed') | Out-Null
    }
  }
}

if ($FinalDecisionGateReady -and $LedgerEntryReadOk) {
  if ($LedgerEntryText.IndexOf('PENDING', [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
    $MissingFields.Add('ledger_entry.template_placeholders') | Out-Null
  }
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.stage17_scope' -Text $LedgerEntryText -RequiredTerms @('Stage 17', 'FR-017', 'Forearm Cuffs')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.final_decision_status' -Text $LedgerEntryText -RequiredTerms @($ExpectedFinalDecisionStatus)
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.final_decision_record_path' -Text $LedgerEntryText -RequiredTerms @($ResolvedFinalDecisionPath)
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.physical_validation_complete_false' -Text $LedgerEntryText -RequiredTerms @('physical_validation_complete', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.stage17_completion_claim_allowed_false' -Text $LedgerEntryText -RequiredTerms @('stage17_completion_claim_allowed', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.fr018_implementation_cleared_false' -Text $LedgerEntryText -RequiredTerms @('fr018_implementation_cleared', 'false')
  Add-RequiredLedgerText -Missing $MissingFields -Field 'ledger_entry.fr018_scope' -Text $LedgerEntryText -RequiredTerms @('FR-018')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'ledger_entry.fr018_blocked_or_not_cleared' -Text $LedgerEntryText -AnyTerms @('blocked', 'not cleared', 'not_cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'ledger_entry.powered_testing_not_cleared' -Text $LedgerEntryText -AnyTerms @('powered testing: not cleared', 'powered testing remains blocked', 'powered testing not cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'ledger_entry.frame_coupled_testing_not_cleared' -Text $LedgerEntryText -AnyTerms @('frame-coupled testing: not cleared', 'frame-coupled testing remains blocked', 'frame-coupled testing not cleared')
  Add-RequiredLedgerAnyText -Missing $MissingFields -Field 'ledger_entry.load_bearing_not_approved' -Text $LedgerEntryText -AnyTerms @('load-bearing use: not approved', 'load-bearing use remains blocked', 'load-bearing use not approved')

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
    Add-ProhibitedLedgerPhrase -Target $ProhibitedClearanceFlags -Text $LedgerEntryText -Phrase $Phrase
  }
}

if (-not $FinalDecisionGateReady) {
  $Status = if ($FinalDecisionGateFailed) { 'failed_final_decision_record' } else { 'pending_final_decision_record' }
  $ExitCode = if ($FinalDecisionGateFailed) { 1 } else { 0 }
} elseif ([string]::IsNullOrWhiteSpace($ResolvedLedgerEntryPath)) {
  $Status = 'pending_completion_ledger_entry'
  $ExitCode = 0
} elseif (-not $LedgerEntryExists -or -not $LedgerEntryReadOk -or $InvalidFields.Count -gt 0 -or $ProhibitedClearanceFlags.Count -gt 0) {
  $Status = 'failed_completion_ledger_entry'
  $ExitCode = 1
} elseif ($MissingFields.Count -gt 0) {
  $Status = 'pending_completion_ledger_entry'
  $ExitCode = 0
} else {
  $Status = 'ready_for_operator_completion_ledger_update'
  $ExitCode = 0
}

$Output = [ordered]@{
  kind = 'francis.fr017.completion_ledger_gate'
  mode = $Mode
  status = $Status
  final_decision_gate_status = $FinalDecisionGateStatus
  final_decision_gate_exit_code = [int]$FinalDecisionGate.exit_code
  final_decision_gate_parse_ok = [bool]$FinalDecisionGate.parse_ok
  final_decision_record_ready = $FinalDecisionGateReady
  final_decision_record_failed = $FinalDecisionGateFailed
  final_decision_record_path = $ResolvedFinalDecisionPath
  ledger_entry_path = $ResolvedLedgerEntryPath
  ledger_entry_exists = $LedgerEntryExists
  ledger_entry_read_ok = $LedgerEntryReadOk
  ledger_entry_review_ready = ($Status -eq 'ready_for_operator_completion_ledger_update')
  ledger_entry_contract = 'This gate validates a candidate FR-017 completion-ledger handoff after final decision readiness. It is read-only and does not write the ledger, certify physical validation, clear powered/frame/load use, or clear FR-018.'
  completion_ledger_handoff_runbook_contract = 'Use scripts/fr017-new-completion-ledger-handoff.ps1 only to create a candidate completion-ledger handoff file from FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md after final decision readiness. The initializer and this gate do not write docs/operations/COMPLETION_LEDGER.md, mark Stage 17 complete, or clear FR-018.'
  completion_ledger_handoff_template_path = $CompletionLedgerHandoffTemplatePath
  completion_ledger_handoff_initializer_path = $CompletionLedgerHandoffInitializerPath
  completion_ledger_handoff_working_record_name_pattern = 'FR-017-COMPLETION-LEDGER-HANDOFF-YYYY-MM-DD-PILOT.md'
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
  next_required_ledger_input = if ($Status -eq 'ready_for_operator_completion_ledger_update') {
    'operator_may_review_candidate_entry_and_update_completion_ledger_manually_without_FR-018_clearance'
  } else {
    $ExpectedNextLedgerInput
  }
  no_fake_validation_lock = 'A ready ledger handoff means the candidate entry preserves final-decision evidence references and blocked-clearance language. The script still does not mark Stage 17 complete or clear FR-018.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
