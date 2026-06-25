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

  [string]$FinalDecisionPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FinalPhysicalGateScript = Join-Path $PSScriptRoot 'fr017-final-physical-gate.ps1'
$ExpectedFinalPhysicalStatus = 'ready_for_stage17_final_physical_completion_decision'
$ExpectedNextDecisionInput = 'complete_human_final_stage17_completion_decision_record_at_FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json'

function Resolve-GatePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Resolve-LinkedPath {
  param(
    [string]$BasePath,
    [string]$Path
  )

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  $BaseRoot = Split-Path -Parent $BasePath
  return [System.IO.Path]::GetFullPath((Join-Path $BaseRoot $Path))
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

function Get-IdentityFingerprint {
  param([object]$Value)

  if ($null -eq $Value) {
    return ''
  }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  $Sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $Hash = $Sha256.ComputeHash($Bytes)
    $Hex = -join ($Hash | ForEach-Object { $_.ToString('x2', [System.Globalization.CultureInfo]::InvariantCulture) })
    return $Hex.Substring(0, 12)
  } finally {
    $Sha256.Dispose()
  }
}

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
}

function Add-IfMissingText {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Target.Add($Field) | Out-Null
  }
}

function Add-EvidenceDateCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Text,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  if (-not $ParseOk -or $ParsedDate.Date -gt [datetime]::Today) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Add-ExactTextCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [string]$Expected
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  if (-not [string]::Equals(([string]$Value).Trim(), $Expected, [System.StringComparison]::Ordinal)) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Add-RequiredBooleanTrueCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [string]$Field,
    [object]$Value
  )

  if ($null -eq $Value -or (Test-MissingOrPendingText -Value $Value)) {
    $Missing.Add($Field) | Out-Null
    return
  }
  if ($Value -isnot [bool] -or -not [bool]$Value) {
    $Invalid.Add($Field) | Out-Null
    $Violations.Add($Field) | Out-Null
  }
}

function Add-RequiredBooleanFalseCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [string]$Field,
    [object]$Value
  )

  if ($null -eq $Value -or (Test-MissingOrPendingText -Value $Value)) {
    $Missing.Add($Field) | Out-Null
    return
  }
  if ($Value -isnot [bool] -or [bool]$Value) {
    $Invalid.Add($Field) | Out-Null
    $Violations.Add($Field) | Out-Null
  }
}

$FinalArgs = New-Object System.Collections.Generic.List[string]
$FinalArgs.Add('-Mode') | Out-Null
$FinalArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $FinalArgs -Name '-ManifestPath' -Value $ManifestPath
Add-OptionalArg -Target $FinalArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $FinalArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $FinalArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $FinalArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $FinalArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $FinalArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $FinalArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath

$FinalPhysicalGate = Invoke-JsonGate -ScriptPath $FinalPhysicalGateScript -Arguments $FinalArgs.ToArray()
$FinalPhysicalGateStatus = if ([bool]$FinalPhysicalGate.parse_ok) { [string](Get-PropertyValue -Payload $FinalPhysicalGate.payload -Name 'status' -Default '') } else { 'failed_gate_parse' }
$FinalPhysicalGateReady = [bool]$FinalPhysicalGate.parse_ok -and [int]$FinalPhysicalGate.exit_code -eq 0 -and $FinalPhysicalGateStatus -eq $ExpectedFinalPhysicalStatus
$FinalPhysicalGateFailed = (-not [bool]$FinalPhysicalGate.parse_ok) -or [int]$FinalPhysicalGate.exit_code -ne 0 -or $FinalPhysicalGateStatus.StartsWith('failed_') -or $FinalPhysicalGateStatus.StartsWith('missing_') -or $FinalPhysicalGateStatus.StartsWith('invalid_')
$FinalPhysicalGateReferencePilotFingerprint = if ([bool]$FinalPhysicalGate.parse_ok) { [string](Get-PropertyValue -Payload $FinalPhysicalGate.payload -Name 'pilot_identity_continuity_reference_fingerprint' -Default '') } else { '' }

$ResolvedFinalDecisionPath = if ([string]::IsNullOrWhiteSpace($FinalDecisionPath)) { '' } else { Resolve-GatePath -Path $FinalDecisionPath }
$DecisionRecord = $null
$DecisionRecordParseOk = $false
$DecisionRecordExists = -not [string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath) -and (Test-Path -LiteralPath $ResolvedFinalDecisionPath -PathType Leaf)
$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$DecisionLockViolations = New-Object System.Collections.Generic.List[string]
$CompletionDecisionViolations = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$FailedReasons = New-Object System.Collections.Generic.List[string]
$SavedFinalGateRecordPath = ''
$SavedFinalGateRecordExists = $false
$SavedFinalGateRecordParseOk = $false
$SavedFinalGateStatus = ''
$FinalDecisionPilotFingerprint = ''

if ($FinalPhysicalGateReady -and [string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath)) {
  $MissingFields.Add('final_decision_path') | Out-Null
}

if ($FinalPhysicalGateReady -and -not [string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath)) {
  if ($DecisionRecordExists) {
    try {
      $DecisionRecord = Get-Content -LiteralPath $ResolvedFinalDecisionPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $DecisionRecordParseOk = $true
    } catch {
      $DecisionRecordParseOk = $false
      $FailedReasons.Add('final_decision_record_parse_failed') | Out-Null
    }
  } else {
    $MissingFields.Add('final_decision_path') | Out-Null
    $FailedReasons.Add('final_decision_record_missing') | Out-Null
  }
}

if ($FinalPhysicalGateReady -and $DecisionRecordParseOk) {
  Add-ExactTextCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'kind' -Value (Get-PropertyValue -Payload $DecisionRecord -Name 'kind') -Expected 'francis.fr017.final_physical_decision.v1'
  Add-ExactTextCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'component' -Value (Get-PropertyValue -Payload $DecisionRecord -Name 'component') -Expected 'FR-017 Forearm Cuffs'

  $Evidence = Get-PropertyValue -Payload $DecisionRecord -Name 'evidence'
  Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
  Add-IfMissingText -Target $MissingFields -Field 'evidence.decision_reviewer' -Value (Get-PropertyValue -Payload $Evidence -Name 'decision_reviewer')
  Add-IfMissingText -Target $MissingFields -Field 'evidence.reviewer_role' -Value (Get-PropertyValue -Payload $Evidence -Name 'reviewer_role')
  $PilotIdValue = Get-PropertyValue -Payload $Evidence -Name 'pilot_id'
  Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value $PilotIdValue
  if (-not (Test-MissingOrPendingText -Value $PilotIdValue)) {
    $FinalDecisionPilotFingerprint = Get-IdentityFingerprint -Value $PilotIdValue
    if (Test-MissingOrPendingText -Value $FinalPhysicalGateReferencePilotFingerprint) {
      $InvalidFields.Add('evidence.pilot_id.final_physical_gate_reference_missing') | Out-Null
    } elseif ($FinalDecisionPilotFingerprint -ne $FinalPhysicalGateReferencePilotFingerprint) {
      $InvalidFields.Add('evidence.pilot_id') | Out-Null
      $DecisionLockViolations.Add('evidence.pilot_id_must_match_final_physical_gate_reference') | Out-Null
    }
  }
  Add-ExactTextCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.final_physical_gate_status' -Value (Get-PropertyValue -Payload $Evidence -Name 'final_physical_gate_status') -Expected $ExpectedFinalPhysicalStatus
  $FinalGateRecordPathValue = Get-PropertyValue -Payload $Evidence -Name 'final_physical_gate_record_path'
  Add-IfMissingText -Target $MissingFields -Field 'evidence.final_physical_gate_record_path' -Value $FinalGateRecordPathValue

  if (-not (Test-MissingOrPendingText -Value $FinalGateRecordPathValue)) {
    $SavedFinalGateRecordPath = Resolve-LinkedPath -BasePath $ResolvedFinalDecisionPath -Path ([string]$FinalGateRecordPathValue).Trim()
    $SavedFinalGateRecordExists = Test-Path -LiteralPath $SavedFinalGateRecordPath -PathType Leaf
    if ($SavedFinalGateRecordExists) {
      try {
        $SavedFinalGateRecord = Get-Content -LiteralPath $SavedFinalGateRecordPath -Raw | ConvertFrom-Json -ErrorAction Stop
        $SavedFinalGateRecordParseOk = $true
        $SavedFinalGateStatus = [string](Get-PropertyValue -Payload $SavedFinalGateRecord -Name 'status' -Default '')
        if ($SavedFinalGateStatus -ne $ExpectedFinalPhysicalStatus) {
          $InvalidFields.Add('evidence.final_physical_gate_record_path.status') | Out-Null
        }
        if ([bool](Get-PropertyValue -Payload $SavedFinalGateRecord -Name 'physical_validation_complete' -Default $false)) {
          $InvalidFields.Add('evidence.final_physical_gate_record_path.physical_validation_complete') | Out-Null
        }
        if ([bool](Get-PropertyValue -Payload $SavedFinalGateRecord -Name 'stage17_completion_claim_allowed' -Default $false)) {
          $InvalidFields.Add('evidence.final_physical_gate_record_path.stage17_completion_claim_allowed') | Out-Null
        }
        if ([bool](Get-PropertyValue -Payload $SavedFinalGateRecord -Name 'fr018_implementation_cleared' -Default $false)) {
          $InvalidFields.Add('evidence.final_physical_gate_record_path.fr018_implementation_cleared') | Out-Null
        }
      } catch {
        $InvalidFields.Add('evidence.final_physical_gate_record_path') | Out-Null
      }
    } else {
      $InvalidFields.Add('evidence.final_physical_gate_record_path') | Out-Null
    }
  }

  $DecisionLocks = Get-PropertyValue -Payload $DecisionRecord -Name 'decision_locks'
  foreach ($Field in @(
      'real_records_reviewed',
      'all_stop_conditions_reviewed',
      'no_unresolved_safety_fail_conditions',
      'no_powered_testing_cleared',
      'no_frame_coupled_testing_cleared',
      'no_load_bearing_use_approved',
      'fr018_implementation_not_cleared'
    )) {
    Add-RequiredBooleanTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $DecisionLockViolations -Field ('decision_locks.{0}' -f $Field) -Value (Get-PropertyValue -Payload $DecisionLocks -Name $Field)
  }

  $CompletionDecision = Get-PropertyValue -Payload $DecisionRecord -Name 'completion_decision'
  foreach ($Field in @(
      'stage17_completion_claim_requested',
      'physical_validation_accepted_by_human_reviewer',
      'completion_ledger_update_required'
    )) {
    Add-RequiredBooleanTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $CompletionDecisionViolations -Field ('completion_decision.{0}' -f $Field) -Value (Get-PropertyValue -Payload $CompletionDecision -Name $Field)
  }
  $DecisionNotes = Get-PropertyValue -Payload $CompletionDecision -Name 'completion_decision_notes'
  Add-IfMissingText -Target $MissingFields -Field 'completion_decision.completion_decision_notes' -Value $DecisionNotes
  if (-not (Test-MissingOrPendingText -Value $DecisionNotes)) {
    $NotesText = ([string]$DecisionNotes).Trim()
    $NotesLower = $NotesText.ToLowerInvariant()
    if (-not ($NotesLower.Contains('remaining') -or $NotesLower.Contains('limitation'))) {
      $InvalidFields.Add('completion_decision.completion_decision_notes') | Out-Null
    }
    foreach ($Phrase in @(
        'fr-018 cleared',
        'fr018 cleared',
        'powered testing cleared',
        'frame-coupled testing cleared',
        'load-bearing approved',
        'load bearing approved'
      )) {
      if ($NotesLower.Contains($Phrase)) {
        $ProhibitedClearanceFlags.Add(('completion_decision_notes.{0}' -f $Phrase.Replace(' ', '_'))) | Out-Null
      }
    }
  }

  $NoFakeValidationLock = Get-PropertyValue -Payload $DecisionRecord -Name 'no_fake_validation_lock'
  Add-RequiredBooleanTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $DecisionLockViolations -Field 'no_fake_validation_lock.template_is_not_physical_validation' -Value (Get-PropertyValue -Payload $NoFakeValidationLock -Name 'template_is_not_physical_validation')
  Add-RequiredBooleanTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $DecisionLockViolations -Field 'no_fake_validation_lock.requires_real_records' -Value (Get-PropertyValue -Payload $NoFakeValidationLock -Name 'requires_real_records')
  Add-RequiredBooleanFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $ProhibitedClearanceFlags -Field 'no_fake_validation_lock.fr018_implementation_cleared' -Value (Get-PropertyValue -Payload $NoFakeValidationLock -Name 'fr018_implementation_cleared')
  Add-RequiredBooleanFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Violations $ProhibitedClearanceFlags -Field 'no_fake_validation_lock.powered_or_frame_coupled_testing_cleared' -Value (Get-PropertyValue -Payload $NoFakeValidationLock -Name 'powered_or_frame_coupled_testing_cleared')
}

if (-not $FinalPhysicalGateReady) {
  $Status = if ($FinalPhysicalGateFailed) { 'failed_final_physical_gate' } else { 'pending_final_physical_gate' }
  $ExitCode = if ($FinalPhysicalGateFailed) { 1 } else { 0 }
} elseif ([string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath) -or ($MissingFields.Count -gt 0 -and -not $DecisionRecordParseOk)) {
  $Status = 'pending_final_decision_record'
  $ExitCode = 0
} elseif ($MissingFields.Count -gt 0) {
  $Status = 'pending_final_decision_record'
  $ExitCode = 0
} elseif ($InvalidFields.Count -gt 0 -or $DecisionLockViolations.Count -gt 0 -or $CompletionDecisionViolations.Count -gt 0 -or $ProhibitedClearanceFlags.Count -gt 0 -or -not $DecisionRecordParseOk) {
  $Status = 'failed_final_decision_record'
  $ExitCode = 1
} else {
  $Status = 'ready_for_completion_ledger_review'
  $ExitCode = 0
}

$Output = [ordered]@{
  kind = 'francis.fr017.final_decision_record_gate'
  mode = $Mode
  status = $Status
  final_physical_gate_status = $FinalPhysicalGateStatus
  final_physical_gate_exit_code = [int]$FinalPhysicalGate.exit_code
  final_physical_gate_parse_ok = [bool]$FinalPhysicalGate.parse_ok
  final_physical_gate_ready = $FinalPhysicalGateReady
  final_physical_gate_failed = $FinalPhysicalGateFailed
  final_physical_gate_next_required_input = if ([bool]$FinalPhysicalGate.parse_ok) { [string](Get-PropertyValue -Payload $FinalPhysicalGate.payload -Name 'next_required_final_physical_input' -Default '') } else { '' }
  final_decision_record_path = $ResolvedFinalDecisionPath
  final_decision_record_exists = $DecisionRecordExists
  final_decision_record_parse_ok = $DecisionRecordParseOk
  final_decision_record_ready = ($Status -eq 'ready_for_completion_ledger_review')
  final_decision_record_contract = 'This gate validates a populated human final decision record after the final physical gate is decision-ready. It is a ledger-review handoff, not certification, physical validation completion, powered/frame/load clearance, or FR-018 clearance.'
  final_decision_pilot_identity_contract = 'Final decision evidence.pilot_id must match the final physical gate pilot identity continuity reference by redacted SHA-256-derived fingerprint; raw pilot ID is not emitted.'
  final_physical_gate_reference_pilot_fingerprint = $FinalPhysicalGateReferencePilotFingerprint
  final_decision_pilot_fingerprint = $FinalDecisionPilotFingerprint
  saved_final_physical_gate_record_path = $SavedFinalGateRecordPath
  saved_final_physical_gate_record_exists = $SavedFinalGateRecordExists
  saved_final_physical_gate_record_parse_ok = $SavedFinalGateRecordParseOk
  saved_final_physical_gate_record_status = $SavedFinalGateStatus
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  decision_lock_violations = @($DecisionLockViolations.ToArray())
  completion_decision_violations = @($CompletionDecisionViolations.ToArray())
  prohibited_clearance_flags = @($ProhibitedClearanceFlags.ToArray())
  failed_reasons = @($FailedReasons.ToArray())
  ledger_completion_review_ready = ($Status -eq 'ready_for_completion_ledger_review')
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  next_required_final_decision_input = if ($Status -eq 'ready_for_completion_ledger_review') {
    'update_completion_ledger_only_after_operator_review_and_preserve_FR-018_block'
  } else {
    $ExpectedNextDecisionInput
  }
  no_fake_validation_lock = 'This final decision record gate can make the human decision record ready for ledger review, but it does not mark physical_validation_complete, allow a Stage 17 completion claim, or clear FR-018 by itself.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
