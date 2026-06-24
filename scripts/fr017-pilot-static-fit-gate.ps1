[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MannequinGateScript = Join-Path $PSScriptRoot 'fr017-mannequin-interface-gate.ps1'

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

function Add-RecordLinkageCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [string]$Field,
    [object]$Value,
    [string]$ExpectedPath,
    [string]$ViolationId
  )

  if (-not (Test-PresentText -Value $Value)) {
    return
  }

  try {
    $ResolvedValue = Resolve-GatePath -Path ([string]$Value)
    if (-not [string]::Equals($ResolvedValue, $ExpectedPath, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add($ViolationId) | Out-Null
    }
  } catch {
    $Invalid.Add($Field) | Out-Null
  }
}

function Add-PilotIdentityLinkageCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [object]$StaticPilotId,
    [string]$MeasurementRecordPath
  )

  if (-not (Test-PresentText -Value $StaticPilotId)) {
    return
  }

  try {
    $MeasurementPayload = Get-Content -LiteralPath $MeasurementRecordPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $MeasurementEvidence = Get-PropertyValue -Payload $MeasurementPayload -Name 'evidence'
    $MeasurementPilotId = Get-PropertyValue -Payload $MeasurementEvidence -Name 'pilot_id' -Default ''
    if (-not (Test-PresentText -Value $MeasurementPilotId)) {
      $Invalid.Add('evidence.measurement_record_path') | Out-Null
      return
    }
    if (-not [string]::Equals([string]$StaticPilotId, [string]$MeasurementPilotId, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add('evidence.pilot_id_must_match_measurement_pilot_id') | Out-Null
    }
  } catch {
    $Invalid.Add('evidence.measurement_record_path') | Out-Null
  }
}

function Get-UpstreamArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  return @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Payload -Name $Name))
}

function Get-UpstreamObjectArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  $Value = Get-PropertyValue -Payload $Payload -Name $Name
  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value)
  }
  return @($Value)
}

function Invoke-MannequinInterfaceGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $MannequinGateScript,
    '-Mode',
    'Status',
    '-MeasurementPath',
    $ResolvedMeasurementPath,
    '-MockupPath',
    $ResolvedMockupPath,
    '-MannequinPath',
    $ResolvedMannequinPath
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
  'observer_present',
  'emergency_release_briefed',
  'stop_on_symptoms',
  'pilot_can_self_remove_or_abort'
)

$RequiredBaselineChecks = @(
  'fingers_warm_before_donning',
  'normal_color_before_donning',
  'baseline_grip_present'
)

$RequiredStaticChecks = @(
  'cuff_below_elbow_crease',
  'lower_cuff_above_wrist_bones',
  'upper_strap_broad_non_compressive',
  'lower_strap_broad_non_compressive',
  'inner_forearm_clear',
  'bone_relief_present',
  'quick_release_visible_tactile_reachable',
  'cuff_stable_without_migration',
  'glove_removal_path_open',
  'wrist_assembly_removal_path_open',
  'cable_route_static_no_snag'
)

$RequiredPostDoffChecks = @(
  'fingers_warm_after_doffing',
  'normal_color_after_doffing',
  'grip_strength_unchanged'
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
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-GatePath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-GatePath -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { $DefaultMannequinPath } else { Resolve-GatePath -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { $DefaultStaticFitPath } else { Resolve-GatePath -Path $StaticFitPath }
$UsingStaticFitTemplate = [string]::IsNullOrWhiteSpace($StaticFitPath)

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$RecordLinkageViolations = New-Object System.Collections.Generic.List[string]
$RecordChronologyViolations = New-Object System.Collections.Generic.List[string]
$FitRedesignTriggers = New-Object System.Collections.Generic.List[string]
$SymptomBlockers = New-Object System.Collections.Generic.List[string]
$StaticFitParseOk = $false
$StaticFitStatus = 'pending_pilot_static_fit_test'
$Status = 'pending_mannequin_interface_gate'
$ExitCode = 0

$Upstream = Invoke-MannequinInterfaceGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath
$UpstreamStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_upstream_mannequin_gate' }
$UpstreamReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStatus -eq 'ready_for_pilot_static_fit_planning'

if (-not [bool]$Upstream.parse_ok -or [int]$Upstream.exit_code -ne 0 -or $UpstreamStatus.StartsWith('failed_')) {
  $Status = 'failed_upstream_mannequin_gate'
  $ExitCode = 1
} elseif (-not $UpstreamReady) {
  $Status = 'pending_mannequin_interface_gate'
} else {
  if (-not (Test-Path -LiteralPath $ResolvedStaticFitPath -PathType Leaf)) {
    $StaticFitStatus = 'failed_static_fit_record'
    $InvalidFields.Add('static_fit_file') | Out-Null
  } else {
    try {
      $StaticFitPayload = Get-Content -LiteralPath $ResolvedStaticFitPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $StaticFitParseOk = $true
    } catch {
      $StaticFitStatus = 'failed_static_fit_record'
      $InvalidFields.Add('static_fit_json_parse') | Out-Null
    }
  }

  if ($StaticFitParseOk) {
    if ([string](Get-PropertyValue -Payload $StaticFitPayload -Name 'kind' -Default '') -ne 'francis.fr017.pilot_static_fit.v1') {
      $InvalidFields.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $StaticFitPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $InvalidFields.Add('component') | Out-Null
    }

    $Evidence = Get-PropertyValue -Payload $StaticFitPayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
    $StaticPilotId = Get-PropertyValue -Payload $Evidence -Name 'pilot_id'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value $StaticPilotId
    Add-IfMissingText -Target $MissingFields -Field 'evidence.prototype_revision' -Value (Get-PropertyValue -Payload $Evidence -Name 'prototype_revision')
    $StaticMeasurementRecordPath = Get-PropertyValue -Payload $Evidence -Name 'measurement_record_path'
    $StaticMockupRecordPath = Get-PropertyValue -Payload $Evidence -Name 'mockup_build_record_path'
    $StaticMannequinRecordPath = Get-PropertyValue -Payload $Evidence -Name 'mannequin_interface_record_path'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.measurement_record_path' -Value $StaticMeasurementRecordPath
    Add-IfMissingText -Target $MissingFields -Field 'evidence.mockup_build_record_path' -Value $StaticMockupRecordPath
    Add-IfMissingText -Target $MissingFields -Field 'evidence.mannequin_interface_record_path' -Value $StaticMannequinRecordPath
    Add-RecordLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -Field 'evidence.measurement_record_path' -Value $StaticMeasurementRecordPath -ExpectedPath $ResolvedMeasurementPath -ViolationId 'evidence.measurement_record_path_must_match_measurement_path'
    Add-RecordLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -Field 'evidence.mockup_build_record_path' -Value $StaticMockupRecordPath -ExpectedPath $ResolvedMockupPath -ViolationId 'evidence.mockup_build_record_path_must_match_mockup_path'
    Add-RecordLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -Field 'evidence.mannequin_interface_record_path' -Value $StaticMannequinRecordPath -ExpectedPath $ResolvedMannequinPath -ViolationId 'evidence.mannequin_interface_record_path_must_match_mannequin_path'
    Add-PilotIdentityLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -StaticPilotId $StaticPilotId -MeasurementRecordPath $ResolvedMeasurementPath
    Add-RequiredPositiveJsonNumber -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.test_duration_minutes' -Value (Get-PropertyValue -Payload $Evidence -Name 'test_duration_minutes')

    $StaticEvidenceDate = Get-EvidenceDateOrNull -Payload $StaticFitPayload
    foreach ($UpstreamEvidence in @(
        @{ Path = $ResolvedMeasurementPath; Id = 'measurement' },
        @{ Path = $ResolvedMockupPath; Id = 'mockup' },
        @{ Path = $ResolvedMannequinPath; Id = 'mannequin' }
      )) {
      try {
        $UpstreamPayloadForChronology = Get-Content -LiteralPath ([string]$UpstreamEvidence.Path) -Raw | ConvertFrom-Json -ErrorAction Stop
        $UpstreamEvidenceDate = Get-EvidenceDateOrNull -Payload $UpstreamPayloadForChronology
        if ($null -ne $StaticEvidenceDate -and $null -ne $UpstreamEvidenceDate -and $StaticEvidenceDate -lt $UpstreamEvidenceDate) {
          $RecordChronologyViolations.Add(('evidence.date_before_{0}.evidence.date' -f [string]$UpstreamEvidence.Id)) | Out-Null
        }
      } catch {
        $InvalidFields.Add(('{0}_json_parse_for_chronology' -f [string]$UpstreamEvidence.Id)) | Out-Null
      }
    }

    $Preconditions = Get-PropertyValue -Payload $StaticFitPayload -Name 'preconditions'
    foreach ($Field in $RequiredPreconditions) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $FitRedesignTriggers -Field ('preconditions.{0}' -f $Field) -Value (Get-PropertyValue -Payload $Preconditions -Name $Field)
    }

    $Sides = Get-PropertyValue -Payload $StaticFitPayload -Name 'sides'
    foreach ($Side in @('left', 'right')) {
      $SidePayload = Get-PropertyValue -Payload $Sides -Name $Side
      $Baseline = Get-PropertyValue -Payload $SidePayload -Name 'baseline'
      foreach ($Field in $RequiredBaselineChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $FitRedesignTriggers -Field ('sides.{0}.baseline.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $Baseline -Name $Field)
      }

      $StaticChecks = Get-PropertyValue -Payload $SidePayload -Name 'static_checks'
      foreach ($Field in $RequiredStaticChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $FitRedesignTriggers -Field ('sides.{0}.static_checks.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $StaticChecks -Name $Field)
      }

      $PostDoff = Get-PropertyValue -Payload $SidePayload -Name 'post_doff'
      foreach ($Field in $RequiredPostDoffChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $FitRedesignTriggers -Field ('sides.{0}.post_doff.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $PostDoff -Name $Field)
      }

      $Symptoms = Get-PropertyValue -Payload $SidePayload -Name 'symptoms'
      foreach ($Field in $SymptomFields) {
        Add-RequiredFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Fail $SymptomBlockers -Field ('sides.{0}.symptoms.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $Symptoms -Name $Field)
      }
    }

    if ($InvalidFields.Count -gt 0 -or $RecordLinkageViolations.Count -gt 0 -or $RecordChronologyViolations.Count -gt 0) {
      $StaticFitStatus = 'failed_static_fit_record'
      $Status = $StaticFitStatus
      $ExitCode = 1
    } elseif ($FitRedesignTriggers.Count -gt 0 -or $SymptomBlockers.Count -gt 0) {
      $StaticFitStatus = 'failed_requires_fit_redesign_or_medical_review'
      $Status = $StaticFitStatus
      $ExitCode = 1
    } elseif ($MissingFields.Count -gt 0 -or $UsingStaticFitTemplate) {
      $StaticFitStatus = 'pending_pilot_static_fit_test'
      $Status = $StaticFitStatus
    } else {
      $StaticFitStatus = 'ready_for_pilot_movement_test_planning'
      $Status = $StaticFitStatus
    }
  } else {
    $Status = $StaticFitStatus
    if ($StaticFitStatus.StartsWith('failed_')) {
      $ExitCode = 1
    }
  }
}

$Output = [ordered]@{
  kind = 'francis.fr017.pilot_static_fit_gate'
  mode = $Mode
  status = $Status
  upstream_mannequin_status = $UpstreamStatus
  upstream_mannequin_gate_exit_code = [int]$Upstream.exit_code
  upstream_mannequin_gate_parse_ok = [bool]$Upstream.parse_ok
  upstream_mannequin_gate_ready = $UpstreamReady
  upstream_mockup_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mockup_status' -Default '') } else { '' }
  upstream_mockup_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mockup_gate_ready' -Default $false) } else { $false }
  upstream_measurement_intake_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_intake_status' -Default '') } else { '' }
  upstream_next_required_physical_input = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_next_required_physical_input' -Default '') } else { '' }
  upstream_measurement_capture_plan_status_contract = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_status_contract' -Default '') } else { '' }
  upstream_measurement_capture_summary_contract = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_summary_contract' -Default '') } else { '' }
  upstream_measurement_capture_plan_not_completion_evidence = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_not_completion_evidence' -Default $false) } else { $false }
  upstream_measurement_capture_plan_status = @(Get-UpstreamObjectArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_status')
  upstream_measurement_capture_total_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_total_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_ready_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_ready_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_pending_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_pending_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_invalid_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_invalid_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_failed_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_failed_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_first_blocking_group_id = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_first_blocking_group_id' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_first_blocking_group_status' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_action = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_first_blocking_group_action' -Default '') } else { '' }
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
  upstream_mannequin_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'record_linkage_violations')
  upstream_mannequin_interface_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'interface_redesign_triggers')
  upstream_mannequin_fail_observations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'fail_observations')
  static_fit_status = $StaticFitStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  using_static_fit_template = $UsingStaticFitTemplate
  static_fit_parse_ok = $StaticFitParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  pilot_static_fit_test_complete = ($Status -eq 'ready_for_pilot_movement_test_planning')
  pilot_movement_test_planning_ready = ($Status -eq 'ready_for_pilot_movement_test_planning')
  pilot_movement_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_preconditions = $RequiredPreconditions
  required_baseline_checks = $RequiredBaselineChecks
  required_static_checks = $RequiredStaticChecks
  required_post_doff_checks = $RequiredPostDoffChecks
  symptom_fields = $SymptomFields
  record_linkage_contract = 'The pilot static-fit evidence paths for measurement_record_path, mockup_build_record_path, and mannequin_interface_record_path must resolve to the same records passed into this gate. A static-fit record cannot advance from stale, copied, or unrelated upstream evidence.'
  pilot_identity_linkage_contract = 'The pilot static-fit evidence.pilot_id must match evidence.pilot_id in the linked measurement record. A static-fit record cannot advance if it names a different pilot than the measurements used for cuff sizing.'
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated pilot static-fit evidence is invalid because it cannot be completed evidence.'
  evidence_chronology_contract = 'Pilot static-fit evidence.date must be the same as or later than the linked measurement, mockup, and mannequin evidence dates. A static-fit record cannot advance from upstream evidence that was not yet recorded.'
  test_duration_value_contract = 'Use an unquoted JSON number greater than 0 for evidence.test_duration_minutes. Quoted numeric strings are invalid. PENDING is treated as missing evidence.'
  boolean_value_contract = 'Use unquoted JSON boolean true only when the static-fit condition is directly verified. Use false for verified failure or for absent symptoms as appropriate. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  record_linkage_violations = @($RecordLinkageViolations.ToArray())
  record_chronology_violations = @($RecordChronologyViolations.ToArray())
  fit_redesign_triggers = @($FitRedesignTriggers.ToArray())
  symptom_blockers = @($SymptomBlockers.ToArray())
  next_actions = if ($Status -eq 'ready_for_pilot_movement_test_planning') {
    @(
      'prepare_pilot_movement_test_plan_without_powered_or_frame_coupled_testing',
      'verify_quick_release_access_before_movement',
      'keep_FR-018_implementation_blocked_until_full_FR-017_physical_gate_closes'
    )
  } elseif ($Status -eq 'pending_pilot_static_fit_test') {
    @(
      'run_non_powered_pilot_static_fit_test_with_observer',
      'complete_FR-017_pilot_static_fit_record',
      'rerun_pilot_static_fit_gate'
    )
  } elseif ($Status -eq 'pending_mannequin_interface_gate') {
    @(
      'complete_measurement_mockup_and_mannequin_interface_gates',
      'rerun_pilot_static_fit_gate_after_upstream_ready'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_upstream_or_static_fit_condition',
      'rerun_gate_before_any_pilot_movement_test'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
