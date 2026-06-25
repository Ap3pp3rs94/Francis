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

  [string]$EngineeringReviewPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$Stage17PackageGateScript = Join-Path $PSScriptRoot 'fr017-stage17-validation-gate.ps1'
$EngineeringReviewGateScript = Join-Path $PSScriptRoot 'fr017-engineering-review-gate.ps1'

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
  }
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

function ConvertTo-StringArray {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function Add-UniqueString {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [object]$Value
  )

  if ($null -eq $Value) {
    return
  }
  $Text = ([string]$Value).Trim()
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return
  }
  if (-not $Target.Contains($Text)) {
    $Target.Add($Text) | Out-Null
  }
}

function New-FinalPhysicalDecisionPlanStatus {
  param(
    [object[]]$DecisionPlan,
    [bool]$PackageGateReady,
    [bool]$EngineeringGateReady,
    [bool]$EngineeringGateFailed,
    [string[]]$PackageSignals,
    [string[]]$EngineeringSignals,
    [string[]]$EngineeringMissingFields,
    [string[]]$EngineeringInvalidFields,
    [string[]]$ChronologySignals,
    [string[]]$PilotIdentitySignals
  )

  $Result = New-Object System.Collections.Generic.List[object]
  foreach ($Step in $DecisionPlan) {
    $StepId = [string]$Step.id
    $Status = 'ready_for_final_physical_decision_review'
    $RequiredAction = [string]$Step.required_action
    $Missing = @()
    $Invalid = @()
    $BlockingSignals = @()

    if ($StepId -eq 'stage17_package_and_manifest_lock') {
      if (-not $PackageGateReady) {
        $Status = 'failed_stop_condition_or_blocking_signal'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PackageSignals)
      }
    } elseif ($StepId -eq 'engineering_review_gate_lock') {
      if (-not $PackageGateReady) {
        $Status = 'blocked_by_stage17_package_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PackageSignals)
      } elseif ($EngineeringGateFailed) {
        $Status = 'failed_stop_condition_or_blocking_signal'
        $BlockingSignals = @(ConvertTo-StringArray -Value $EngineeringSignals)
      } elseif (-not $EngineeringGateReady) {
        $Status = 'pending_required_engineering_review_gate'
        $Missing = @(ConvertTo-StringArray -Value $EngineeringMissingFields)
        $Invalid = @(ConvertTo-StringArray -Value $EngineeringInvalidFields)
        $BlockingSignals = @(ConvertTo-StringArray -Value $EngineeringSignals)
      }
    } elseif ($StepId -eq 'evidence_chronology_audit') {
      if (-not $PackageGateReady) {
        $Status = 'blocked_by_stage17_package_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PackageSignals)
      } elseif (-not $EngineeringGateReady) {
        $Status = 'blocked_by_engineering_review_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $EngineeringSignals)
      } elseif (@($ChronologySignals).Count -gt 0) {
        $Status = 'failed_stop_condition_or_blocking_signal'
        $BlockingSignals = @(ConvertTo-StringArray -Value $ChronologySignals)
      }
    } elseif ($StepId -eq 'pilot_identity_continuity_audit') {
      if (-not $PackageGateReady) {
        $Status = 'blocked_by_stage17_package_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PackageSignals)
      } elseif (-not $EngineeringGateReady) {
        $Status = 'blocked_by_engineering_review_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $EngineeringSignals)
      } elseif (@($PilotIdentitySignals).Count -gt 0) {
        $Status = 'failed_stop_condition_or_blocking_signal'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PilotIdentitySignals)
      }
    } elseif ($StepId -eq 'human_final_decision_and_no_clearance_locks') {
      if (-not $PackageGateReady) {
        $Status = 'blocked_by_stage17_package_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $PackageSignals)
      } elseif (-not $EngineeringGateReady) {
        $Status = 'blocked_by_engineering_review_gate'
        $BlockingSignals = @(ConvertTo-StringArray -Value $EngineeringSignals)
      } elseif (@($ChronologySignals).Count -gt 0 -or @($PilotIdentitySignals).Count -gt 0) {
        $Status = 'blocked_by_evidence_audit_failure'
        $CombinedSignals = New-Object System.Collections.Generic.List[string]
        foreach ($Signal in @(ConvertTo-StringArray -Value $ChronologySignals)) {
          Add-UniqueString -Target $CombinedSignals -Value $Signal
        }
        foreach ($Signal in @(ConvertTo-StringArray -Value $PilotIdentitySignals)) {
          Add-UniqueString -Target $CombinedSignals -Value $Signal
        }
        $BlockingSignals = @($CombinedSignals.ToArray())
      }
    }

    $Result.Add([ordered]@{
        id = $StepId
        status = $Status
        validation_state = [string]$Step.validation_state
        ready_for_final_physical_decision_review = ($Status -eq 'ready_for_final_physical_decision_review')
        missing_fields = @($Missing)
        invalid_fields = @($Invalid)
        blocking_signals = @($BlockingSignals)
        required_action = $RequiredAction
      }) | Out-Null
  }
  return @($Result.ToArray())
}

function New-CapturePlanSummary {
  param([object[]]$CapturePlanStatus)

  $ReadyCount = 0
  $PendingCount = 0
  $InvalidCount = 0
  $FailedCount = 0
  $BlockedCount = 0
  $FirstBlockingGroupId = ''
  $FirstBlockingGroupStatus = ''
  $FirstBlockingGroupAction = ''

  foreach ($Step in $CapturePlanStatus) {
    $StepStatus = [string]$Step.status
    if ($StepStatus -eq 'ready_for_final_physical_decision_review') {
      $ReadyCount += 1
    } elseif ($StepStatus.StartsWith('pending_')) {
      $PendingCount += 1
    } elseif ($StepStatus.StartsWith('invalid_')) {
      $InvalidCount += 1
    } elseif ($StepStatus.StartsWith('failed_')) {
      $FailedCount += 1
    } elseif ($StepStatus.StartsWith('blocked_')) {
      $BlockedCount += 1
    }

    if ([string]::IsNullOrWhiteSpace($FirstBlockingGroupId) -and $StepStatus -ne 'ready_for_final_physical_decision_review') {
      $FirstBlockingGroupId = [string]$Step.id
      $FirstBlockingGroupStatus = $StepStatus
      $FirstBlockingGroupAction = [string]$Step.required_action
    }
  }

  return [ordered]@{
    total_groups = @($CapturePlanStatus).Count
    ready_groups = $ReadyCount
    pending_groups = $PendingCount
    invalid_groups = $InvalidCount
    failed_groups = $FailedCount
    blocked_groups = $BlockedCount
    first_blocking_group_id = $FirstBlockingGroupId
    first_blocking_group_status = $FirstBlockingGroupStatus
    first_blocking_group_action = $FirstBlockingGroupAction
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

function Get-GateProperty {
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

function Get-GateArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  return @(ConvertTo-StringArray -Value (Get-GateProperty -Payload $Payload -Name $Name))
}

function Get-GateObjectArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  $Value = Get-GateProperty -Payload $Payload -Name $Name
  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value)
  }
  return @($Value)
}

function Read-EvidenceDateRecord {
  param(
    [string]$Id,
    [string]$Path
  )

  $Result = [ordered]@{
    id = $Id
    path = $Path
    parse_ok = $false
    date_text = ''
    date = $null
    issue = ''
  }

  if ([string]::IsNullOrWhiteSpace($Path)) {
    $Result.issue = 'missing_path'
    return $Result
  }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    $Result.issue = 'missing_file'
    return $Result
  }

  try {
    $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Result.issue = 'json_parse_failed'
    return $Result
  }

  $Evidence = Get-GateProperty -Payload $Payload -Name 'evidence'
  $DateText = [string](Get-GateProperty -Payload $Evidence -Name 'date' -Default '')
  $Result.date_text = $DateText
  if (Test-MissingOrPendingText -Value $DateText) {
    $Result.issue = 'missing_date'
    return $Result
  }
  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $DateText,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  if (-not $ParseOk) {
    $Result.issue = 'date_parse_failed'
    return $Result
  }

  $Result.parse_ok = $true
  $Result.date = $ParsedDate.Date
  return $Result
}

function Get-EvidenceChronologyAudit {
  param(
    [object[]]$Records
  )

  $Violations = New-Object System.Collections.Generic.List[string]
  $PublicRecords = New-Object System.Collections.Generic.List[object]

  foreach ($Record in $Records) {
    $PublicRecords.Add([ordered]@{
        id = [string]$Record.id
        path = [string]$Record.path
        parse_ok = [bool]$Record.parse_ok
        date = [string]$Record.date_text
        issue = [string]$Record.issue
      }) | Out-Null
    if (-not [bool]$Record.parse_ok) {
      $Violations.Add(('{0}.evidence.date_{1}' -f [string]$Record.id, [string]$Record.issue)) | Out-Null
    }
  }

  for ($Index = 1; $Index -lt $Records.Count; $Index += 1) {
    $Previous = $Records[$Index - 1]
    $Current = $Records[$Index]
    if ([bool]$Previous.parse_ok -and [bool]$Current.parse_ok -and $Current.date -lt $Previous.date) {
      $Violations.Add(('{0}.evidence.date_before_{1}' -f [string]$Current.id, [string]$Previous.id)) | Out-Null
    }
  }

  return [ordered]@{
    records = @($PublicRecords.ToArray())
    violations = @($Violations.ToArray())
  }
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

function Read-PilotIdentityRecord {
  param(
    [string]$Id,
    [string]$Path,
    [bool]$Required = $true
  )

  $Result = [ordered]@{
    id = $Id
    path = $Path
    required = $Required
    parse_ok = $false
    pilot_id_present = $false
    pilot_id_fingerprint = ''
    pilot_id = ''
    issue = ''
  }

  if ([string]::IsNullOrWhiteSpace($Path)) {
    $Result.issue = 'missing_path'
    return $Result
  }
  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    $Result.issue = 'missing_file'
    return $Result
  }

  try {
    $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Result.issue = 'json_parse_failed'
    return $Result
  }

  $Evidence = Get-GateProperty -Payload $Payload -Name 'evidence'
  $PilotId = [string](Get-GateProperty -Payload $Evidence -Name 'pilot_id' -Default '')
  $Result.parse_ok = $true
  if (Test-MissingOrPendingText -Value $PilotId) {
    if ($Required) {
      $Result.issue = 'missing_pilot_id'
    } else {
      $Result.issue = 'pilot_id_not_present_optional'
    }
    return $Result
  }

  $Result.pilot_id_present = $true
  $Result.pilot_id = $PilotId
  $Result.pilot_id_fingerprint = Get-IdentityFingerprint -Value $PilotId
  return $Result
}

function Get-PilotIdentityContinuityAudit {
  param(
    [object[]]$Records
  )

  $Violations = New-Object System.Collections.Generic.List[string]
  $PublicRecords = New-Object System.Collections.Generic.List[object]
  $ReferencePilotId = ''
  $ReferenceRecordId = ''

  foreach ($Record in $Records) {
    $PublicRecords.Add([ordered]@{
        id = [string]$Record.id
        path = [string]$Record.path
        required = [bool]$Record.required
        parse_ok = [bool]$Record.parse_ok
        pilot_id_present = [bool]$Record.pilot_id_present
        pilot_id_fingerprint = [string]$Record.pilot_id_fingerprint
        issue = [string]$Record.issue
      }) | Out-Null

    if (-not [bool]$Record.parse_ok) {
      $Violations.Add(('{0}.evidence.pilot_id_{1}' -f [string]$Record.id, [string]$Record.issue)) | Out-Null
      continue
    }

    if (-not [bool]$Record.pilot_id_present) {
      if ([bool]$Record.required) {
        $Violations.Add(('{0}.evidence.pilot_id_missing' -f [string]$Record.id)) | Out-Null
      }
      continue
    }

    if ([string]::IsNullOrWhiteSpace($ReferencePilotId)) {
      $ReferencePilotId = [string]$Record.pilot_id
      $ReferenceRecordId = [string]$Record.id
      continue
    }

    if (-not [string]::Equals([string]$Record.pilot_id, $ReferencePilotId, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add(('{0}.evidence.pilot_id_must_match_{1}' -f [string]$Record.id, $ReferenceRecordId)) | Out-Null
    }
  }

  return [ordered]@{
    records = @($PublicRecords.ToArray())
    violations = @($Violations.ToArray())
    reference_record = $ReferenceRecordId
    reference_pilot_id_fingerprint = Get-IdentityFingerprint -Value $ReferencePilotId
  }
}

$PackageGateArgs = New-Object System.Collections.Generic.List[string]
$PackageGateArgs.Add('-Mode') | Out-Null
$PackageGateArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $PackageGateArgs -Name '-ManifestPath' -Value $ManifestPath

$EngineeringGateArgs = New-Object System.Collections.Generic.List[string]
$EngineeringGateArgs.Add('-Mode') | Out-Null
$EngineeringGateArgs.Add('Status') | Out-Null
Add-OptionalArg -Target $EngineeringGateArgs -Name '-MeasurementPath' -Value $MeasurementPath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-MockupPath' -Value $MockupPath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-MannequinPath' -Value $MannequinPath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-StaticFitPath' -Value $StaticFitPath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-MovementPath' -Value $MovementPath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-ReleaseCablePath' -Value $ReleaseCablePath
Add-OptionalArg -Target $EngineeringGateArgs -Name '-EngineeringReviewPath' -Value $EngineeringReviewPath

$PackageGate = Invoke-JsonGate -ScriptPath $Stage17PackageGateScript -Arguments $PackageGateArgs.ToArray()
$EngineeringGate = Invoke-JsonGate -ScriptPath $EngineeringReviewGateScript -Arguments $EngineeringGateArgs.ToArray()

$PackageGateStatus = if ([bool]$PackageGate.parse_ok) { [string]$PackageGate.payload.status } else { 'failed_package_gate_parse' }
$EngineeringGateStatus = if ([bool]$EngineeringGate.parse_ok) { [string]$EngineeringGate.payload.status } else { 'failed_engineering_gate_parse' }
$PackageGateReady = [bool]$PackageGate.parse_ok -and [int]$PackageGate.exit_code -eq 0 -and $PackageGateStatus -eq 'blocked_physical_validation'
$EngineeringRecordLinkageViolations = @(if ([bool]$EngineeringGate.parse_ok) { ConvertTo-StringArray -Value $EngineeringGate.payload.record_linkage_violations })
$EngineeringRecordLinkageContract = if ([bool]$EngineeringGate.parse_ok) { [string]$EngineeringGate.payload.record_linkage_contract } else { '' }
$EngineeringRecordLinkageContractPresent = -not [string]::IsNullOrWhiteSpace($EngineeringRecordLinkageContract)
$EngineeringGateReady = (
  [bool]$EngineeringGate.parse_ok -and
  [int]$EngineeringGate.exit_code -eq 0 -and
  $EngineeringGateStatus -eq 'ready_for_final_stage17_physical_gate_audit' -and
  $EngineeringRecordLinkageContractPresent -and
  $EngineeringRecordLinkageViolations.Count -eq 0
)

$EvidenceChronologyContract = 'Final FR-017 evidence dates must be valid ISO YYYY-MM-DD dates and must not move backward across the linked gate order: measurement, mockup, mannequin, pilot static-fit, pilot movement, quick-release/cable-snag, engineering review. Equal dates are allowed when same-day evidence is documented.'
$EvidenceChronologyAudit = [ordered]@{
  records = @()
  violations = @()
}
if ($EngineeringGateReady) {
  $EvidenceChronologyAudit = Get-EvidenceChronologyAudit -Records @(
    (Read-EvidenceDateRecord -Id 'measurement' -Path $MeasurementPath),
    (Read-EvidenceDateRecord -Id 'mockup' -Path $MockupPath),
    (Read-EvidenceDateRecord -Id 'mannequin' -Path $MannequinPath),
    (Read-EvidenceDateRecord -Id 'pilot_static_fit' -Path $StaticFitPath),
    (Read-EvidenceDateRecord -Id 'pilot_movement' -Path $MovementPath),
    (Read-EvidenceDateRecord -Id 'quick_release_cable_snag' -Path $ReleaseCablePath),
    (Read-EvidenceDateRecord -Id 'engineering_review' -Path $EngineeringReviewPath)
  )
}
$EvidenceChronologyViolations = @(ConvertTo-StringArray -Value $EvidenceChronologyAudit.violations)

$PilotIdentityContinuityContract = 'Final FR-017 pilot-linked evidence must preserve one pilot identity across measurement, any pilot-id-bearing mockup record, pilot static-fit, pilot movement, quick-release/cable-snag, and engineering review. The final gate exposes redacted identity fingerprints only and fails closed on missing required pilot IDs or mismatched identities.'
$PilotIdentityContinuityAudit = [ordered]@{
  records = @()
  violations = @()
  reference_record = ''
  reference_pilot_id_fingerprint = ''
}
if ($EngineeringGateReady) {
  $PilotIdentityContinuityAudit = Get-PilotIdentityContinuityAudit -Records @(
    (Read-PilotIdentityRecord -Id 'measurement' -Path $MeasurementPath -Required $true),
    (Read-PilotIdentityRecord -Id 'mockup' -Path $MockupPath -Required $false),
    (Read-PilotIdentityRecord -Id 'pilot_static_fit' -Path $StaticFitPath -Required $true),
    (Read-PilotIdentityRecord -Id 'pilot_movement' -Path $MovementPath -Required $true),
    (Read-PilotIdentityRecord -Id 'quick_release_cable_snag' -Path $ReleaseCablePath -Required $true),
    (Read-PilotIdentityRecord -Id 'engineering_review' -Path $EngineeringReviewPath -Required $true)
  )
}
$PilotIdentityContinuityViolations = @(ConvertTo-StringArray -Value $PilotIdentityContinuityAudit.violations)

$FailedReasons = New-Object System.Collections.Generic.List[string]
if (-not $PackageGateReady) {
  $FailedReasons.Add('stage17_package_gate_not_clean') | Out-Null
}
if (-not [bool]$EngineeringGate.parse_ok) {
  $FailedReasons.Add('engineering_review_gate_parse_failed') | Out-Null
} elseif ([int]$EngineeringGate.exit_code -ne 0 -or $EngineeringGateStatus.StartsWith('failed_')) {
  $FailedReasons.Add('engineering_review_gate_failed') | Out-Null
} elseif (-not $EngineeringRecordLinkageContractPresent) {
  $FailedReasons.Add('engineering_review_record_linkage_contract_missing') | Out-Null
} elseif ($EngineeringRecordLinkageViolations.Count -gt 0) {
  $FailedReasons.Add('engineering_review_record_linkage_violation') | Out-Null
} elseif ($EvidenceChronologyViolations.Count -gt 0) {
  $FailedReasons.Add('evidence_chronology_violation') | Out-Null
} elseif ($PilotIdentityContinuityViolations.Count -gt 0) {
  $FailedReasons.Add('pilot_identity_continuity_violation') | Out-Null
}

$Status = 'pending_engineering_review_gate'
$ExitCode = 0
if (-not $PackageGateReady) {
  $Status = 'failed_stage17_package_gate'
  $ExitCode = 1
} elseif ([int]$EngineeringGate.exit_code -ne 0 -or -not [bool]$EngineeringGate.parse_ok -or $EngineeringGateStatus.StartsWith('failed_')) {
  $Status = 'failed_engineering_review_gate'
  $ExitCode = 1
} elseif (-not $EngineeringRecordLinkageContractPresent -or $EngineeringRecordLinkageViolations.Count -gt 0) {
  $Status = 'failed_engineering_review_gate'
  $ExitCode = 1
} elseif ($EvidenceChronologyViolations.Count -gt 0) {
  $Status = 'failed_evidence_chronology'
  $ExitCode = 1
} elseif ($PilotIdentityContinuityViolations.Count -gt 0) {
  $Status = 'failed_pilot_identity_continuity'
  $ExitCode = 1
} elseif ($EngineeringGateReady) {
  $Status = 'ready_for_stage17_final_physical_completion_decision'
}

$BlockedInputs = if ([bool]$PackageGate.parse_ok) { ConvertTo-StringArray -Value $PackageGate.payload.blocked_inputs } else { @() }
$EngineeringNextActions = if ([bool]$EngineeringGate.parse_ok) { ConvertTo-StringArray -Value $EngineeringGate.payload.next_actions } else { @('rerun_engineering_review_gate_after_parse_failure') }
$EngineeringMissingFields = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'missing_fields')
$EngineeringInvalidFields = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'invalid_fields')
$EngineeringReviewRedesignTriggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'review_redesign_triggers')
$EngineeringReviewProhibitedClearanceFlags = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'prohibited_clearance_flags')
$EngineeringGateFailed = (-not [bool]$EngineeringGate.parse_ok) -or [int]$EngineeringGate.exit_code -ne 0 -or $EngineeringGateStatus.StartsWith('failed_')

$PackageDecisionSignals = New-Object System.Collections.Generic.List[string]
if (-not $PackageGateReady) {
  Add-UniqueString -Target $PackageDecisionSignals -Value ('stage17_package_gate_status.{0}' -f $PackageGateStatus)
  foreach ($Signal in @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'failed_checks')) {
    Add-UniqueString -Target $PackageDecisionSignals -Value ('stage17_package.failed_checks.{0}' -f $Signal)
  }
}

$EngineeringDecisionSignals = New-Object System.Collections.Generic.List[string]
if (-not [bool]$EngineeringGate.parse_ok) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value 'engineering_review_gate_parse_failed'
} elseif (-not $EngineeringGateReady) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value ('engineering_review_gate_status.{0}' -f $EngineeringGateStatus)
}
foreach ($Signal in @($EngineeringRecordLinkageViolations)) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value $Signal
}
foreach ($Signal in @($EngineeringMissingFields)) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value $Signal
}
foreach ($Signal in @($EngineeringInvalidFields)) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value $Signal
}
foreach ($Signal in @($EngineeringReviewRedesignTriggers)) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value $Signal
}
foreach ($Signal in @($EngineeringReviewProhibitedClearanceFlags)) {
  Add-UniqueString -Target $EngineeringDecisionSignals -Value $Signal
}

$FinalPhysicalDecisionPlan = @(
  [ordered]@{
    id = 'stage17_package_and_manifest_lock'
    validation_state = 'DOCUMENTED_CONTAINER_GATE_REQUIRED'
    required_conditions = @(
      'stage17 package gate parses',
      'stage17 package gate status remains blocked_physical_validation',
      'documentation and evidence containers are complete without claiming physical validation'
    )
    required_action = 'keep the FR-017 package, manifest, templates, and pending evidence containers intact before evaluating final physical decision readiness'
  },
  [ordered]@{
    id = 'engineering_review_gate_lock'
    validation_state = 'REQUIRES_PROFESSIONAL_ENGINEERING_REVIEW_GATE_READY'
    required_conditions = @(
      'engineering review gate parses',
      'engineering review gate status is ready_for_final_stage17_physical_gate_audit',
      'engineering review record linkage contract is present',
      'engineering review record linkage violations are empty'
    )
    required_action = 'complete and link the professional engineering review record without powered, frame-coupled, load-bearing, or FR-018 clearance'
  },
  [ordered]@{
    id = 'evidence_chronology_audit'
    validation_state = 'REQUIRES_FINAL_EVIDENCE_CHRONOLOGY_AUDIT'
    required_conditions = @(
      'measurement through engineering review evidence dates parse as ISO YYYY-MM-DD',
      'linked evidence dates do not move backward across the FR-017 gate order'
    )
    required_action = 'audit linked evidence chronology from measurement through engineering review and correct any backdated, missing, or unparsable record'
  },
  [ordered]@{
    id = 'pilot_identity_continuity_audit'
    validation_state = 'REQUIRES_FINAL_PILOT_IDENTITY_CONTINUITY_AUDIT'
    required_conditions = @(
      'required pilot IDs exist for measurement, pilot static-fit, pilot movement, quick-release/cable-snag, and engineering review',
      'pilot identity fingerprints remain consistent across required pilot-linked records'
    )
    required_action = 'audit redacted pilot identity continuity across all required FR-017 pilot-linked evidence records'
  },
  [ordered]@{
    id = 'human_final_decision_and_no_clearance_locks'
    validation_state = 'REQUIRES_HUMAN_FINAL_STAGE17_COMPLETION_DECISION'
    required_conditions = @(
      'physical_validation_complete remains false in this read-only gate',
      'stage17_completion_claim_allowed remains false in this read-only gate',
      'powered_or_frame_coupled_testing_cleared remains false',
      'fr018_implementation_cleared remains false'
    )
    required_action = 'complete a separate human final Stage 17 completion decision record using FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json against real accepted records before any ledger-backed completion claim; keep FR-018 blocked'
  }
)
$FinalPhysicalDecisionPlanStatus = @(New-FinalPhysicalDecisionPlanStatus -DecisionPlan $FinalPhysicalDecisionPlan -PackageGateReady $PackageGateReady -EngineeringGateReady $EngineeringGateReady -EngineeringGateFailed $EngineeringGateFailed -PackageSignals $PackageDecisionSignals.ToArray() -EngineeringSignals $EngineeringDecisionSignals.ToArray() -EngineeringMissingFields $EngineeringMissingFields -EngineeringInvalidFields $EngineeringInvalidFields -ChronologySignals $EvidenceChronologyViolations -PilotIdentitySignals $PilotIdentityContinuityViolations)
$FinalPhysicalDecisionPlanSummary = New-CapturePlanSummary -CapturePlanStatus $FinalPhysicalDecisionPlanStatus

$Output = [ordered]@{
  kind = 'francis.fr017.final_physical_gate'
  mode = $Mode
  status = $Status
  stage17_package_gate_status = $PackageGateStatus
  stage17_package_gate_exit_code = [int]$PackageGate.exit_code
  stage17_package_gate_parse_ok = [bool]$PackageGate.parse_ok
  stage17_package_failed_checks = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'failed_checks')
  stage17_package_missing_measurement_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_measurement_template_contracts')
  stage17_package_missing_measurement_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_measurement_template_fields')
  stage17_package_missing_mockup_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_mockup_template_contracts')
  stage17_package_missing_mockup_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_mockup_template_fields')
  stage17_package_missing_mannequin_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_mannequin_template_contracts')
  stage17_package_missing_mannequin_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_mannequin_template_fields')
  stage17_package_missing_static_fit_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_static_fit_template_contracts')
  stage17_package_missing_static_fit_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_static_fit_template_fields')
  stage17_package_missing_movement_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_movement_template_contracts')
  stage17_package_missing_movement_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_movement_template_fields')
  stage17_package_missing_release_cable_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_release_cable_template_contracts')
  stage17_package_missing_release_cable_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_release_cable_template_fields')
  stage17_package_missing_engineering_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_engineering_template_contracts')
  stage17_package_missing_engineering_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_engineering_template_fields')
  stage17_package_missing_final_decision_template_contracts = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_final_decision_template_contracts')
  stage17_package_missing_final_decision_template_fields = @(Get-GateArrayProperty -Payload $PackageGate.payload -Name 'missing_final_decision_template_fields')
  engineering_review_gate_status = $EngineeringGateStatus
  engineering_review_gate_exit_code = [int]$EngineeringGate.exit_code
  engineering_review_gate_parse_ok = [bool]$EngineeringGate.parse_ok
  engineering_review_gate_ready = $EngineeringGateReady
  upstream_quick_release_cable_snag_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_quick_release_cable_snag_status' -Default '') } else { '' }
  upstream_quick_release_cable_snag_gate_ready = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_quick_release_cable_snag_gate_ready' -Default $false) } else { $false }
  upstream_pilot_movement_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_pilot_movement_status' -Default '') } else { '' }
  upstream_pilot_movement_gate_ready = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_pilot_movement_gate_ready' -Default $false) } else { $false }
  upstream_static_fit_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_static_fit_status' -Default '') } else { '' }
  upstream_static_fit_gate_ready = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_static_fit_gate_ready' -Default $false) } else { $false }
  upstream_mannequin_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_mannequin_status' -Default '') } else { '' }
  upstream_mannequin_gate_ready = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_mannequin_gate_ready' -Default $false) } else { $false }
  upstream_mockup_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_mockup_status' -Default '') } else { '' }
  upstream_measurement_intake_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_intake_status' -Default '') } else { '' }
  upstream_next_required_physical_input = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_next_required_physical_input' -Default '') } else { '' }
  upstream_measurement_capture_plan_status_contract = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_plan_status_contract' -Default '') } else { '' }
  upstream_measurement_capture_summary_contract = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_summary_contract' -Default '') } else { '' }
  upstream_measurement_capture_plan_not_completion_evidence = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_plan_not_completion_evidence' -Default $false) } else { $false }
  upstream_measurement_capture_plan_status = @(Get-GateObjectArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_plan_status')
  upstream_measurement_capture_total_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_total_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_ready_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_ready_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_pending_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_pending_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_invalid_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_invalid_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_failed_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_failed_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_first_blocking_group_id = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_first_blocking_group_id' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_first_blocking_group_status' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_action = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_capture_first_blocking_group_action' -Default '') } else { '' }
  engineering_review_capture_plan_contract = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_plan_contract' -Default '') } else { '' }
  engineering_review_capture_plan_status_contract = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_plan_status_contract' -Default '') } else { '' }
  engineering_review_capture_summary_contract = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_summary_contract' -Default '') } else { '' }
  engineering_review_capture_plan_not_completion_evidence = if ([bool]$EngineeringGate.parse_ok) { [bool](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_plan_not_completion_evidence' -Default $false) } else { $false }
  next_required_engineering_review_input = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'next_required_engineering_review_input' -Default '') } else { '' }
  engineering_review_capture_plan = @(Get-GateObjectArrayProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_plan')
  engineering_review_capture_plan_status = @(Get-GateObjectArrayProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_plan_status')
  engineering_review_capture_total_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_total_groups' -Default 0) } else { 0 }
  engineering_review_capture_ready_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_ready_groups' -Default 0) } else { 0 }
  engineering_review_capture_pending_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_pending_groups' -Default 0) } else { 0 }
  engineering_review_capture_invalid_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_invalid_groups' -Default 0) } else { 0 }
  engineering_review_capture_failed_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_failed_groups' -Default 0) } else { 0 }
  engineering_review_capture_upstream_blocked_groups = if ([bool]$EngineeringGate.parse_ok) { [int](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_upstream_blocked_groups' -Default 0) } else { 0 }
  engineering_review_capture_first_blocking_group_id = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_first_blocking_group_id' -Default '') } else { '' }
  engineering_review_capture_first_blocking_group_status = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_first_blocking_group_status' -Default '') } else { '' }
  engineering_review_capture_first_blocking_group_action = if ([bool]$EngineeringGate.parse_ok) { [string](Get-GateProperty -Payload $EngineeringGate.payload -Name 'engineering_review_capture_first_blocking_group_action' -Default '') } else { '' }
  upstream_measurement_invalid_fields = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_invalid_fields')
  upstream_measurement_consistency_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_consistency_violations')
  upstream_marked_zone_specificity_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_marked_zone_specificity_violations')
  upstream_repeatability_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_repeatability_blockers')
  upstream_left_right_independence_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_left_right_independence_blockers')
  upstream_measurement_condition_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_condition_blockers')
  upstream_landmark_confirmation_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_landmark_confirmation_blockers')
  upstream_measurement_note_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_measurement_note_blockers')
  upstream_safety_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_safety_blockers')
  upstream_mockup_linkage_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_mockup_linkage_violations')
  upstream_mockup_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_mockup_redesign_triggers')
  upstream_mannequin_record_linkage_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_mannequin_record_linkage_violations')
  upstream_mannequin_interface_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_mannequin_interface_redesign_triggers')
  upstream_static_fit_record_linkage_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_static_fit_record_linkage_violations')
  upstream_static_fit_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_static_fit_redesign_triggers')
  upstream_static_fit_symptom_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_static_fit_symptom_blockers')
  upstream_movement_record_linkage_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_movement_record_linkage_violations')
  upstream_movement_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_movement_redesign_triggers')
  upstream_movement_symptom_blockers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_movement_symptom_blockers')
  upstream_release_cable_record_linkage_violations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_release_cable_record_linkage_violations')
  upstream_release_cable_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_release_cable_redesign_triggers')
  upstream_release_cable_fail_observations = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'upstream_release_cable_fail_observations')
  evidence_chronology_contract = $EvidenceChronologyContract
  evidence_chronology_records = @($EvidenceChronologyAudit.records)
  evidence_chronology_violations = @($EvidenceChronologyViolations)
  pilot_identity_continuity_contract = $PilotIdentityContinuityContract
  pilot_identity_continuity_records = @($PilotIdentityContinuityAudit.records)
  pilot_identity_continuity_violations = @($PilotIdentityContinuityViolations)
  pilot_identity_continuity_reference_record = [string]$PilotIdentityContinuityAudit.reference_record
  pilot_identity_continuity_reference_fingerprint = [string]$PilotIdentityContinuityAudit.reference_pilot_id_fingerprint
  engineering_review_missing_fields = @($EngineeringMissingFields)
  engineering_review_invalid_fields = @($EngineeringInvalidFields)
  engineering_review_redesign_triggers = @($EngineeringReviewRedesignTriggers)
  engineering_review_prohibited_clearance_flags = @($EngineeringReviewProhibitedClearanceFlags)
  documentation_complete = $PackageGateReady
  evidence_containers_complete = $PackageGateReady
  physical_validation_evidence_chain_complete = ($PackageGateReady -and $EngineeringGateReady -and $EvidenceChronologyViolations.Count -eq 0 -and $PilotIdentityContinuityViolations.Count -eq 0)
  final_physical_decision_plan_contract = 'The final_physical_decision_plan is read-only operator guidance for checking FR-017 final physical decision readiness. It is not physical validation evidence by itself, does not accept or certify the cuffs, and cannot clear powered, frame-coupled, load-bearing, or FR-018 work.'
  final_physical_decision_plan_status_contract = 'The final_physical_decision_plan_status reports final physical decision readiness only. A ready group means the evidence-chain readback passed this script contract; it is not a completion claim, certification, or FR-018 clearance.'
  final_physical_decision_summary_contract = 'The final_physical_decision_* summary identifies the next blocking final-decision evidence group. It is not physical validation evidence and cannot mark Stage 17 complete.'
  final_physical_decision_plan_not_completion_evidence = $true
  next_required_final_physical_input = 'complete_human_final_stage17_completion_decision_record_at_FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json'
  final_physical_decision_plan = @($FinalPhysicalDecisionPlan)
  final_physical_decision_plan_status = @($FinalPhysicalDecisionPlanStatus)
  final_physical_decision_total_groups = [int]$FinalPhysicalDecisionPlanSummary.total_groups
  final_physical_decision_ready_groups = [int]$FinalPhysicalDecisionPlanSummary.ready_groups
  final_physical_decision_pending_groups = [int]$FinalPhysicalDecisionPlanSummary.pending_groups
  final_physical_decision_invalid_groups = [int]$FinalPhysicalDecisionPlanSummary.invalid_groups
  final_physical_decision_failed_groups = [int]$FinalPhysicalDecisionPlanSummary.failed_groups
  final_physical_decision_blocked_groups = [int]$FinalPhysicalDecisionPlanSummary.blocked_groups
  final_physical_decision_first_blocking_group_id = [string]$FinalPhysicalDecisionPlanSummary.first_blocking_group_id
  final_physical_decision_first_blocking_group_status = [string]$FinalPhysicalDecisionPlanSummary.first_blocking_group_status
  final_physical_decision_first_blocking_group_action = [string]$FinalPhysicalDecisionPlanSummary.first_blocking_group_action
  physical_validation_complete = $false
  stage17_physical_completion_decision_ready = ($Status -eq 'ready_for_stage17_final_physical_completion_decision')
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  engineering_review_record_linkage_contract_present = $EngineeringRecordLinkageContractPresent
  engineering_review_record_linkage_violations = @($EngineeringRecordLinkageViolations)
  blocked_inputs_from_manifest = $BlockedInputs
  failed_reasons = @($FailedReasons.ToArray())
  next_actions = if ($Status -eq 'ready_for_stage17_final_physical_completion_decision') {
    @(
      'complete_human_final_stage17_completion_decision_record_at_FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json',
      'update_manifest_and_completion_ledger_only_if_real_physical_evidence_is_accepted',
      'keep_FR-018_implementation_blocked_until_FR-017_completion_claim_is_ledger_backed'
    )
  } elseif ($Status -eq 'pending_engineering_review_gate') {
    $EngineeringNextActions
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_package_or_engineering_gate',
      'rerun_final_physical_gate_before_any_completion_or_FR-018_claim'
    )
  }
  no_fake_validation_lock = 'This final gate can make the evidence chain decision-ready, but it does not mark physical_validation_complete or clear FR-018 by itself.'
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
