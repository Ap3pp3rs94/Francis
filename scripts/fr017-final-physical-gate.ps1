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
  engineering_review_missing_fields = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'missing_fields')
  engineering_review_invalid_fields = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'invalid_fields')
  engineering_review_redesign_triggers = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'review_redesign_triggers')
  engineering_review_prohibited_clearance_flags = @(Get-GateArrayProperty -Payload $EngineeringGate.payload -Name 'prohibited_clearance_flags')
  documentation_complete = $PackageGateReady
  evidence_containers_complete = $PackageGateReady
  physical_validation_evidence_chain_complete = ($PackageGateReady -and $EngineeringGateReady -and $EvidenceChronologyViolations.Count -eq 0 -and $PilotIdentityContinuityViolations.Count -eq 0)
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
      'perform_human_final_stage17_completion_decision_against_real_records',
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
