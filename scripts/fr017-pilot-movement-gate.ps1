[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$StaticFitGateScript = Join-Path $PSScriptRoot 'fr017-pilot-static-fit-gate.ps1'

function Resolve-GatePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
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
  if ($null -eq $Property) {
    return $Default
  }
  if ($null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
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
  if (-not $ParseOk) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($ParsedDate.Date -gt [datetime]::Today) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Get-EvidenceDateOrNull {
  param([object]$Payload)

  $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
  $Value = Get-PropertyValue -Payload $Evidence -Name 'date'
  if (Test-MissingOrPendingText -Value $Value) {
    return $null
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
  if (-not $ParseOk) {
    return $null
  }

  return $ParsedDate.Date
}

function Test-JsonNumber {
  param([object]$Value)

  if ($null -eq $Value -or $Value -is [string] -or $Value -is [bool]) {
    return $false
  }

  return $Value -is [byte] -or
    $Value -is [sbyte] -or
    $Value -is [int16] -or
    $Value -is [uint16] -or
    $Value -is [int] -or
    $Value -is [uint32] -or
    $Value -is [long] -or
    $Value -is [uint64] -or
    $Value -is [single] -or
    $Value -is [double] -or
    $Value -is [decimal]
}

function Add-RequiredPositiveJsonNumber {
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
  if (-not (Test-JsonNumber -Value $Value)) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number) -or $Number -le 0) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Get-BoolState {
  param([object]$Value)

  if ($null -eq $Value) {
    return 'missing'
  }
  if ($Value -is [bool]) {
    if ($Value) {
      return 'true'
    }
    return 'false'
  }

  if (Test-MissingOrPendingText -Value $Value) {
    return 'missing'
  }
  return 'invalid'
}

function Add-RequiredTrueCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Redesign,
    [string]$Field,
    [object]$Value
  )

  $State = Get-BoolState -Value $Value
  if ($State -eq 'missing') {
    $Missing.Add($Field) | Out-Null
  } elseif ($State -eq 'invalid') {
    $Invalid.Add($Field) | Out-Null
  } elseif ($State -eq 'false') {
    $Redesign.Add($Field) | Out-Null
  }
}

function Add-RequiredFalseCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Fail,
    [string]$Field,
    [object]$Value
  )

  $State = Get-BoolState -Value $Value
  if ($State -eq 'missing') {
    $Missing.Add($Field) | Out-Null
  } elseif ($State -eq 'invalid') {
    $Invalid.Add($Field) | Out-Null
  } elseif ($State -eq 'true') {
    $Fail.Add($Field) | Out-Null
  }
}

function Test-PresentText {
  param([object]$Value)

  return -not (Test-MissingOrPendingText -Value $Value)
}

function Add-PilotIdentityLinkageCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [object]$MovementPilotId,
    [string]$StaticFitRecordPath
  )

  if (-not (Test-PresentText -Value $MovementPilotId)) {
    return
  }

  try {
    $StaticFitPayload = Get-Content -LiteralPath $StaticFitRecordPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $StaticFitEvidence = Get-PropertyValue -Payload $StaticFitPayload -Name 'evidence'
    $StaticFitPilotId = Get-PropertyValue -Payload $StaticFitEvidence -Name 'pilot_id' -Default ''
    if (-not (Test-PresentText -Value $StaticFitPilotId)) {
      $Invalid.Add('evidence.pilot_static_fit_record_path') | Out-Null
      return
    }
    if (-not [string]::Equals([string]$MovementPilotId, [string]$StaticFitPilotId, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add('evidence.pilot_id_must_match_static_fit_pilot_id') | Out-Null
    }
  } catch {
    $Invalid.Add('evidence.pilot_static_fit_record_path') | Out-Null
  }
}

function Get-UpstreamArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  return @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Payload -Name $Name))
}

function Invoke-StaticFitGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $StaticFitGateScript,
    '-Mode',
    'Status',
    '-MeasurementPath',
    $ResolvedMeasurementPath,
    '-MockupPath',
    $ResolvedMockupPath,
    '-MannequinPath',
    $ResolvedMannequinPath,
    '-StaticFitPath',
    $ResolvedStaticFitPath
  )

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

$RequiredPreconditions = @(
  'non_powered_only',
  'no_frame_or_power_coupling',
  'pilot_static_fit_gate_passed',
  'observer_present',
  'emergency_release_briefed',
  'stop_on_symptoms',
  'pilot_can_self_remove_or_abort'
)

$RequiredMovementChecks = @(
  'elbow_flexion_no_crease_compression',
  'elbow_extension_no_cuff_migration',
  'wrist_flexion_no_distal_edge_pressure',
  'wrist_extension_no_distal_edge_pressure',
  'wrist_lateral_no_strap_or_cable_interference',
  'hand_opening_full',
  'grip_formation_clear',
  'glove_removal_not_trapped',
  'wrist_assembly_removal_not_blocked',
  'outer_cable_route_no_snag',
  'quick_release_reachable_during_motion',
  'cuff_returns_to_safe_position_after_motion'
)

$RequiredPostMovementChecks = @(
  'fingers_warm_after_motion',
  'normal_color_after_motion',
  'grip_strength_unchanged',
  'no_new_pressure_marks'
)

$SymptomFields = @(
  'pain',
  'tingling',
  'numbness',
  'cold_fingers',
  'discoloration',
  'hand_weakness',
  'wrist_pain',
  'sharp_pressure',
  'reduced_finger_motion',
  'loss_of_grip_strength'
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$DefaultMannequinPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$DefaultStaticFitPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json'
$DefaultMovementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-GatePath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-GatePath -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { $DefaultMannequinPath } else { Resolve-GatePath -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { $DefaultStaticFitPath } else { Resolve-GatePath -Path $StaticFitPath }
$ResolvedMovementPath = if ([string]::IsNullOrWhiteSpace($MovementPath)) { $DefaultMovementPath } else { Resolve-GatePath -Path $MovementPath }
$UsingMovementTemplate = [string]::IsNullOrWhiteSpace($MovementPath)

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$RecordLinkageViolations = New-Object System.Collections.Generic.List[string]
$RecordChronologyViolations = New-Object System.Collections.Generic.List[string]
$MovementRedesignTriggers = New-Object System.Collections.Generic.List[string]
$SymptomBlockers = New-Object System.Collections.Generic.List[string]
$MovementParseOk = $false
$MovementStatus = 'pending_pilot_movement_test'
$Status = 'pending_pilot_static_fit_gate'
$ExitCode = 0

$Upstream = Invoke-StaticFitGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath
$UpstreamStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_upstream_static_fit_gate' }
$UpstreamReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStatus -eq 'ready_for_pilot_movement_test_planning'

if (-not [bool]$Upstream.parse_ok -or [int]$Upstream.exit_code -ne 0 -or $UpstreamStatus.StartsWith('failed_')) {
  $Status = 'failed_upstream_static_fit_gate'
  $ExitCode = 1
} elseif (-not $UpstreamReady) {
  $Status = 'pending_pilot_static_fit_gate'
} else {
  if (-not (Test-Path -LiteralPath $ResolvedMovementPath -PathType Leaf)) {
    $MovementStatus = 'failed_movement_record'
    $InvalidFields.Add('movement_file') | Out-Null
  } else {
    try {
      $MovementPayload = Get-Content -LiteralPath $ResolvedMovementPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MovementParseOk = $true
    } catch {
      $MovementStatus = 'failed_movement_record'
      $InvalidFields.Add('movement_json_parse') | Out-Null
    }
  }

  if ($MovementParseOk) {
    if ([string](Get-PropertyValue -Payload $MovementPayload -Name 'kind' -Default '') -ne 'francis.fr017.pilot_movement_fit.v1') {
      $InvalidFields.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $MovementPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $InvalidFields.Add('component') | Out-Null
    }

    $Evidence = Get-PropertyValue -Payload $MovementPayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
    $MovementPilotId = Get-PropertyValue -Payload $Evidence -Name 'pilot_id'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value $MovementPilotId
    Add-IfMissingText -Target $MissingFields -Field 'evidence.prototype_revision' -Value (Get-PropertyValue -Payload $Evidence -Name 'prototype_revision')
    $MovementStaticFitRecordPath = Get-PropertyValue -Payload $Evidence -Name 'pilot_static_fit_record_path'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_static_fit_record_path' -Value $MovementStaticFitRecordPath
    if (Test-PresentText -Value $MovementStaticFitRecordPath) {
      try {
        $ResolvedMovementStaticFitRecordPath = Resolve-GatePath -Path ([string]$MovementStaticFitRecordPath)
        if (-not [string]::Equals($ResolvedMovementStaticFitRecordPath, $ResolvedStaticFitPath, [System.StringComparison]::OrdinalIgnoreCase)) {
          $RecordLinkageViolations.Add('evidence.pilot_static_fit_record_path_must_match_static_fit_path') | Out-Null
        }
      } catch {
        $InvalidFields.Add('evidence.pilot_static_fit_record_path') | Out-Null
      }
    }
    Add-PilotIdentityLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -MovementPilotId $MovementPilotId -StaticFitRecordPath $ResolvedStaticFitPath
    Add-RequiredPositiveJsonNumber -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.test_duration_minutes' -Value (Get-PropertyValue -Payload $Evidence -Name 'test_duration_minutes')

    try {
      $StaticFitPayloadForChronology = Get-Content -LiteralPath $ResolvedStaticFitPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $StaticFitEvidenceDate = Get-EvidenceDateOrNull -Payload $StaticFitPayloadForChronology
      $MovementEvidenceDate = Get-EvidenceDateOrNull -Payload $MovementPayload
      if ($null -ne $StaticFitEvidenceDate -and $null -ne $MovementEvidenceDate -and $MovementEvidenceDate -lt $StaticFitEvidenceDate) {
        $RecordChronologyViolations.Add('evidence.date_before_static_fit.evidence.date') | Out-Null
      }
    } catch {
      $InvalidFields.Add('static_fit_json_parse_for_chronology') | Out-Null
    }

    $Preconditions = Get-PropertyValue -Payload $MovementPayload -Name 'preconditions'
    foreach ($Field in $RequiredPreconditions) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $MovementRedesignTriggers -Field ('preconditions.{0}' -f $Field) -Value (Get-PropertyValue -Payload $Preconditions -Name $Field)
    }

    $Sides = Get-PropertyValue -Payload $MovementPayload -Name 'sides'
    foreach ($Side in @('left', 'right')) {
      $SidePayload = Get-PropertyValue -Payload $Sides -Name $Side
      $MovementChecks = Get-PropertyValue -Payload $SidePayload -Name 'movement_checks'
      foreach ($Field in $RequiredMovementChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $MovementRedesignTriggers -Field ('sides.{0}.movement_checks.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $MovementChecks -Name $Field)
      }

      $PostMovement = Get-PropertyValue -Payload $SidePayload -Name 'post_movement'
      foreach ($Field in $RequiredPostMovementChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $MovementRedesignTriggers -Field ('sides.{0}.post_movement.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $PostMovement -Name $Field)
      }

      $Symptoms = Get-PropertyValue -Payload $SidePayload -Name 'symptoms'
      foreach ($Field in $SymptomFields) {
        Add-RequiredFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Fail $SymptomBlockers -Field ('sides.{0}.symptoms.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $Symptoms -Name $Field)
      }
    }

    if ($InvalidFields.Count -gt 0 -or $RecordLinkageViolations.Count -gt 0 -or $RecordChronologyViolations.Count -gt 0) {
      $MovementStatus = 'failed_movement_record'
      $Status = $MovementStatus
      $ExitCode = 1
    } elseif ($MovementRedesignTriggers.Count -gt 0 -or $SymptomBlockers.Count -gt 0) {
      $MovementStatus = 'failed_requires_movement_redesign_or_medical_review'
      $Status = $MovementStatus
      $ExitCode = 1
    } elseif ($MissingFields.Count -gt 0 -or $UsingMovementTemplate) {
      $MovementStatus = 'pending_pilot_movement_test'
      $Status = $MovementStatus
    } else {
      $MovementStatus = 'ready_for_quick_release_and_cable_snag_test_planning'
      $Status = $MovementStatus
    }
  } else {
    $Status = $MovementStatus
    if ($MovementStatus.StartsWith('failed_')) {
      $ExitCode = 1
    }
  }
}

$Output = [ordered]@{
  kind = 'francis.fr017.pilot_movement_gate'
  mode = $Mode
  status = $Status
  upstream_static_fit_status = $UpstreamStatus
  upstream_static_fit_gate_exit_code = [int]$Upstream.exit_code
  upstream_static_fit_gate_parse_ok = [bool]$Upstream.parse_ok
  upstream_static_fit_gate_ready = $UpstreamReady
  upstream_mannequin_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_status' -Default '') } else { '' }
  upstream_mannequin_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_gate_ready' -Default $false) } else { $false }
  upstream_mockup_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mockup_status' -Default '') } else { '' }
  upstream_measurement_intake_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_intake_status' -Default '') } else { '' }
  upstream_measurement_invalid_fields = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_invalid_fields')
  upstream_measurement_consistency_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_consistency_violations')
  upstream_marked_zone_specificity_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_marked_zone_specificity_violations')
  upstream_repeatability_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_repeatability_blockers')
  upstream_left_right_independence_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_left_right_independence_blockers')
  upstream_measurement_condition_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_condition_blockers')
  upstream_landmark_confirmation_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_landmark_confirmation_blockers')
  upstream_measurement_note_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_note_blockers')
  upstream_safety_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_safety_blockers')
  upstream_mockup_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mockup_linkage_violations')
  upstream_mockup_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mockup_redesign_triggers')
  upstream_mannequin_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_record_linkage_violations')
  upstream_mannequin_interface_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_interface_redesign_triggers')
  upstream_static_fit_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'record_linkage_violations')
  upstream_static_fit_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'fit_redesign_triggers')
  upstream_static_fit_symptom_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'symptom_blockers')
  movement_status = $MovementStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  using_movement_template = $UsingMovementTemplate
  movement_parse_ok = $MovementParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  pilot_movement_test_complete = ($Status -eq 'ready_for_quick_release_and_cable_snag_test_planning')
  quick_release_and_cable_snag_test_planning_ready = ($Status -eq 'ready_for_quick_release_and_cable_snag_test_planning')
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_preconditions = $RequiredPreconditions
  required_movement_checks = $RequiredMovementChecks
  required_post_movement_checks = $RequiredPostMovementChecks
  symptom_fields = $SymptomFields
  record_linkage_contract = 'The pilot movement evidence.pilot_static_fit_record_path must resolve to the same static-fit record path passed into this gate. A movement record cannot advance from stale, copied, or unrelated static-fit evidence.'
  pilot_identity_linkage_contract = 'The pilot movement evidence.pilot_id must match evidence.pilot_id in the linked static-fit record. A movement record cannot advance if it names a different pilot than the completed static-fit evidence.'
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated pilot movement evidence is invalid because it cannot be completed evidence.'
  evidence_chronology_contract = 'Pilot movement evidence.date must be the same as or later than the linked static-fit evidence.date. A movement record cannot advance from static-fit evidence that was not yet recorded.'
  test_duration_value_contract = 'Use an unquoted JSON number greater than 0 for evidence.test_duration_minutes. Quoted numeric strings are invalid. PENDING is treated as missing evidence.'
  boolean_value_contract = 'Use unquoted JSON boolean true only when the movement condition is directly verified. Use false for verified failure or for absent symptoms as appropriate. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  record_linkage_violations = @($RecordLinkageViolations.ToArray())
  record_chronology_violations = @($RecordChronologyViolations.ToArray())
  movement_redesign_triggers = @($MovementRedesignTriggers.ToArray())
  symptom_blockers = @($SymptomBlockers.ToArray())
  next_actions = if ($Status -eq 'ready_for_quick_release_and_cable_snag_test_planning') {
    @(
      'prepare_quick_release_and_cable_snag_test_plan_without_powered_or_frame_coupled_testing',
      'verify_release_access_and_removal_under_representative_static_and_motion_conditions',
      'keep_FR-018_implementation_blocked_until_full_FR-017_physical_gate_closes'
    )
  } elseif ($Status -eq 'pending_pilot_movement_test') {
    @(
      'run_non_powered_pilot_movement_test_with_observer',
      'complete_FR-017_pilot_movement_record',
      'rerun_pilot_movement_gate'
    )
  } elseif ($Status -eq 'pending_pilot_static_fit_gate') {
    @(
      'complete_measurement_mockup_mannequin_and_static_fit_gates',
      'rerun_pilot_movement_gate_after_upstream_ready'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_upstream_or_movement_condition',
      'rerun_gate_before_any_release_or_cable_snag_test'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
