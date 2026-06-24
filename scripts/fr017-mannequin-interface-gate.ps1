[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MockupGateScript = Join-Path $PSScriptRoot 'fr017-mockup-readiness-gate.ps1'

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

function Add-MannequinSubjectCheck {
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
  foreach ($ForbiddenFragment in @('pilot', 'human', 'wearer')) {
    if ($Text.IndexOf($ForbiddenFragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      $Invalid.Add($Field) | Out-Null
      return
    }
  }

  foreach ($RequiredFragment in @('mannequin', 'arm-form', 'arm form')) {
    if ($Text.IndexOf($RequiredFragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return
    }
  }

  $Invalid.Add($Field) | Out-Null
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

function Invoke-MockupReadinessGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $MockupGateScript,
    '-Mode',
    'Status',
    '-MeasurementPath',
    $ResolvedMeasurementPath,
    '-MockupPath',
    $ResolvedMockupPath
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

$RequiredInterfaceIds = @(
  'fr032_left_forearm_frame',
  'fr033_right_forearm_frame',
  'fr043_left_elbow_joint',
  'fr044_right_elbow_joint',
  'fr045_left_wrist_joint',
  'fr046_right_wrist_joint',
  'fr066_left_glove_base',
  'fr067_right_glove_base',
  'fr068_palm_interface_ring',
  'fr184_forearm_armor'
)

$RequiredCableSensorChecks = @(
  'fr163_outer_route_only',
  'fr069_no_pressure_or_palm_crossing',
  'fr070_no_powered_anchoring',
  'fr145_no_raised_hard_spot',
  'fr149_no_pressure_zone_placement'
)

$RequiredReleaseChecks = @(
  'left_release_visible_and_reachable',
  'right_release_visible_and_reachable',
  'armor_does_not_hide_release',
  'glove_and_wrist_removal_paths_open'
)

$RequiredFailObservationFields = @(
  'snag_detected',
  'compression_detected',
  'release_hidden',
  'wrist_path_blocked',
  'glove_path_blocked',
  'cable_inner_elbow_crossing',
  'cable_wrist_bone_crossing',
  'cable_palm_or_grip_crossing'
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$DefaultMannequinPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-GatePath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-GatePath -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { $DefaultMannequinPath } else { Resolve-GatePath -Path $MannequinPath }
$UsingMannequinTemplate = [string]::IsNullOrWhiteSpace($MannequinPath)

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$RecordLinkageViolations = New-Object System.Collections.Generic.List[string]
$RecordChronologyViolations = New-Object System.Collections.Generic.List[string]
$InterfaceRedesignTriggers = New-Object System.Collections.Generic.List[string]
$FailObservations = New-Object System.Collections.Generic.List[string]
$MannequinParseOk = $false
$MannequinStatus = 'pending_mannequin_interface_test'
$Status = 'pending_mockup_readiness'
$ExitCode = 0

$Upstream = Invoke-MockupReadinessGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath
$UpstreamStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_upstream_mockup_gate' }
$UpstreamReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStatus -eq 'ready_for_mannequin_interface_test'

if (-not [bool]$Upstream.parse_ok -or [int]$Upstream.exit_code -ne 0 -or $UpstreamStatus.StartsWith('failed_')) {
  $Status = 'failed_upstream_mockup_gate'
  $ExitCode = 1
} elseif (-not $UpstreamReady) {
  $Status = 'pending_mockup_readiness'
} else {
  if (-not (Test-Path -LiteralPath $ResolvedMannequinPath -PathType Leaf)) {
    $MannequinStatus = 'failed_mannequin_record'
    $InvalidFields.Add('mannequin_file') | Out-Null
  } else {
    try {
      $MannequinPayload = Get-Content -LiteralPath $ResolvedMannequinPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MannequinParseOk = $true
    } catch {
      $MannequinStatus = 'failed_mannequin_record'
      $InvalidFields.Add('mannequin_json_parse') | Out-Null
    }
  }

  if ($MannequinParseOk) {
    if ([string](Get-PropertyValue -Payload $MannequinPayload -Name 'kind' -Default '') -ne 'francis.fr017.mannequin_interface_test.v1') {
      $InvalidFields.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $MannequinPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $InvalidFields.Add('component') | Out-Null
    }

    $Evidence = Get-PropertyValue -Payload $MannequinPayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
    $MannequinMockupRecordPath = Get-PropertyValue -Payload $Evidence -Name 'mockup_readiness_record_path'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.mockup_readiness_record_path' -Value $MannequinMockupRecordPath
    if (Test-PresentText -Value $MannequinMockupRecordPath) {
      try {
        $ResolvedMannequinMockupRecordPath = Resolve-GatePath -Path ([string]$MannequinMockupRecordPath)
        if (-not [string]::Equals($ResolvedMannequinMockupRecordPath, $ResolvedMockupPath, [System.StringComparison]::OrdinalIgnoreCase)) {
          $RecordLinkageViolations.Add('evidence.mockup_readiness_record_path_must_match_mockup_path') | Out-Null
        }
      } catch {
        $InvalidFields.Add('evidence.mockup_readiness_record_path') | Out-Null
      }
    }

    $MockupPayloadForChronology = $null
    try {
      $MockupPayloadForChronology = Get-Content -LiteralPath $ResolvedMockupPath -Raw | ConvertFrom-Json -ErrorAction Stop
    } catch {
      $InvalidFields.Add('mockup_json_parse_for_chronology') | Out-Null
    }
    if ($null -ne $MockupPayloadForChronology) {
      $MockupEvidenceDate = Get-EvidenceDateOrNull -Payload $MockupPayloadForChronology
      $MannequinEvidenceDate = Get-EvidenceDateOrNull -Payload $MannequinPayload
      if ($null -ne $MockupEvidenceDate -and $null -ne $MannequinEvidenceDate -and $MannequinEvidenceDate -lt $MockupEvidenceDate) {
        $RecordChronologyViolations.Add('evidence.date_before_mockup.evidence.date') | Out-Null
      }
    }

    Add-MannequinSubjectCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.mannequin_or_arm_form_id' -Value (Get-PropertyValue -Payload $Evidence -Name 'mannequin_or_arm_form_id')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.future_interface_mock_geometry_revision' -Value (Get-PropertyValue -Payload $Evidence -Name 'future_interface_mock_geometry_revision')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.cable_sleeve_mock_id' -Value (Get-PropertyValue -Payload $Evidence -Name 'cable_sleeve_mock_id')

    $TestArticle = Get-PropertyValue -Payload $MannequinPayload -Name 'test_article'
    Add-IfMissingText -Target $MissingFields -Field 'test_article.left_cuff_revision' -Value (Get-PropertyValue -Payload $TestArticle -Name 'left_cuff_revision')
    Add-IfMissingText -Target $MissingFields -Field 'test_article.right_cuff_revision' -Value (Get-PropertyValue -Payload $TestArticle -Name 'right_cuff_revision')
    Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $InterfaceRedesignTriggers -Field 'test_article.non_powered_only' -Value (Get-PropertyValue -Payload $TestArticle -Name 'non_powered_only')

    $Interfaces = Get-PropertyValue -Payload $MannequinPayload -Name 'interfaces'
    foreach ($InterfaceId in $RequiredInterfaceIds) {
      $Interface = Get-PropertyValue -Payload $Interfaces -Name $InterfaceId
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $InterfaceRedesignTriggers -Field ('interfaces.{0}.mock_installed' -f $InterfaceId) -Value (Get-PropertyValue -Payload $Interface -Name 'mock_installed')
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $InterfaceRedesignTriggers -Field ('interfaces.{0}.clearance_passed' -f $InterfaceId) -Value (Get-PropertyValue -Payload $Interface -Name 'clearance_passed')
      Add-IfMissingText -Target $MissingFields -Field ('interfaces.{0}.notes' -f $InterfaceId) -Value (Get-PropertyValue -Payload $Interface -Name 'notes')
    }

    $CableSensorChecks = Get-PropertyValue -Payload $MannequinPayload -Name 'cable_sensor_checks'
    foreach ($Field in $RequiredCableSensorChecks) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $InterfaceRedesignTriggers -Field ('cable_sensor_checks.{0}' -f $Field) -Value (Get-PropertyValue -Payload $CableSensorChecks -Name $Field)
    }

    $ReleaseChecks = Get-PropertyValue -Payload $MannequinPayload -Name 'release_checks'
    foreach ($Field in $RequiredReleaseChecks) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $InterfaceRedesignTriggers -Field ('release_checks.{0}' -f $Field) -Value (Get-PropertyValue -Payload $ReleaseChecks -Name $Field)
    }

    $FailObservationPayload = Get-PropertyValue -Payload $MannequinPayload -Name 'fail_observations'
    foreach ($Field in $RequiredFailObservationFields) {
      Add-RequiredFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Fail $FailObservations -Field ('fail_observations.{0}' -f $Field) -Value (Get-PropertyValue -Payload $FailObservationPayload -Name $Field)
    }

    if ($InvalidFields.Count -gt 0 -or $RecordLinkageViolations.Count -gt 0 -or $RecordChronologyViolations.Count -gt 0) {
      $MannequinStatus = 'failed_mannequin_record'
      $Status = $MannequinStatus
      $ExitCode = 1
    } elseif ($MissingFields.Count -gt 0 -or $UsingMannequinTemplate) {
      $MannequinStatus = 'pending_mannequin_interface_test'
      $Status = $MannequinStatus
    } elseif ($InterfaceRedesignTriggers.Count -gt 0 -or $FailObservations.Count -gt 0) {
      $MannequinStatus = 'failed_requires_interface_redesign'
      $Status = $MannequinStatus
      $ExitCode = 1
    } else {
      $MannequinStatus = 'ready_for_pilot_static_fit_planning'
      $Status = $MannequinStatus
    }
  } else {
    $Status = $MannequinStatus
    if ($MannequinStatus.StartsWith('failed_')) {
      $ExitCode = 1
    }
  }
}

$Output = [ordered]@{
  kind = 'francis.fr017.mannequin_interface_gate'
  mode = $Mode
  status = $Status
  upstream_mockup_status = $UpstreamStatus
  upstream_mockup_gate_exit_code = [int]$Upstream.exit_code
  upstream_mockup_gate_parse_ok = [bool]$Upstream.parse_ok
  upstream_mockup_gate_ready = $UpstreamReady
  upstream_measurement_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_status' -Default '') } else { '' }
  upstream_measurement_intake_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_intake_status' -Default '') } else { '' }
  upstream_next_required_physical_input = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'next_required_physical_input' -Default '') } else { '' }
  upstream_measurement_capture_plan_status_contract = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_plan_status_contract' -Default '') } else { '' }
  upstream_measurement_capture_summary_contract = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_summary_contract' -Default '') } else { '' }
  upstream_measurement_capture_plan_not_completion_evidence = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_plan_not_completion_evidence' -Default $false) } else { $false }
  upstream_measurement_capture_plan_status = @(Get-UpstreamObjectArrayProperty -Payload $Upstream.payload -Name 'measurement_capture_plan_status')
  upstream_measurement_capture_total_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_total_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_ready_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_ready_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_pending_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_pending_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_invalid_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_invalid_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_failed_groups = if ([bool]$Upstream.parse_ok) { [int](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_failed_groups' -Default 0) } else { 0 }
  upstream_measurement_capture_first_blocking_group_id = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_first_blocking_group_id' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_first_blocking_group_status' -Default '') } else { '' }
  upstream_measurement_capture_first_blocking_group_action = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'measurement_capture_first_blocking_group_action' -Default '') } else { '' }
  upstream_measurement_invalid_fields = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'measurement_invalid_fields')
  upstream_measurement_consistency_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'measurement_consistency_violations')
  upstream_marked_zone_specificity_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'marked_zone_specificity_violations')
  upstream_repeatability_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'repeatability_blockers')
  upstream_left_right_independence_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'left_right_independence_blockers')
  upstream_measurement_condition_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'measurement_condition_blockers')
  upstream_landmark_confirmation_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'landmark_confirmation_blockers')
  upstream_measurement_note_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'measurement_note_blockers')
  upstream_safety_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'safety_blockers')
  upstream_mockup_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'mockup_linkage_violations')
  upstream_mockup_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'mockup_redesign_triggers')
  mannequin_status = $MannequinStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  using_mannequin_template = $UsingMannequinTemplate
  mannequin_parse_ok = $MannequinParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  mannequin_interface_test_complete = ($Status -eq 'ready_for_pilot_static_fit_planning')
  pilot_static_fit_planning_ready = ($Status -eq 'ready_for_pilot_static_fit_planning')
  pilot_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_interface_ids = $RequiredInterfaceIds
  required_cable_sensor_checks = $RequiredCableSensorChecks
  required_release_checks = $RequiredReleaseChecks
  required_fail_observation_fields = $RequiredFailObservationFields
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated mannequin interface evidence is invalid because it cannot be completed evidence.'
  test_subject_contract = 'Mannequin interface evidence.mannequin_or_arm_form_id must identify a non-human mannequin or arm-form test subject. Any text that identifies a pilot, human, or wearer is invalid because this gate is not a pilot test.'
  record_linkage_contract = 'The mannequin interface evidence.mockup_readiness_record_path must resolve to the same mockup record path passed into this gate. A mannequin test cannot advance from stale, copied, or unrelated mockup evidence.'
  evidence_chronology_contract = 'Mannequin interface evidence.date must be the same as or later than the linked mockup evidence.date. A mannequin test cannot advance from mockup evidence that was not yet recorded.'
  boolean_value_contract = 'Use unquoted JSON boolean true only when the mannequin/interface condition is directly verified. Use false for verified failure or for absent fail observations as appropriate. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  record_linkage_violations = @($RecordLinkageViolations.ToArray())
  record_chronology_violations = @($RecordChronologyViolations.ToArray())
  interface_redesign_triggers = @($InterfaceRedesignTriggers.ToArray())
  fail_observations = @($FailObservations.ToArray())
  next_actions = if ($Status -eq 'ready_for_pilot_static_fit_planning') {
    @(
      'prepare_pilot_static_fit_plan_without_powered_or_frame_coupled_testing',
      'verify_quick_release_access_before_any_wearable_test',
      'keep_FR-018_implementation_blocked_until_FR-017_physical_gate_closes'
    )
  } elseif ($Status -eq 'pending_mannequin_interface_test') {
    @(
      'run_non_powered_mannequin_interface_test',
      'complete_FR-017_mannequin_interface_record',
      'rerun_mannequin_interface_gate'
    )
  } elseif ($Status -eq 'pending_mockup_readiness') {
    @(
      'complete_measurement_intake',
      'complete_non_powered_mockup_build_record',
      'rerun_mockup_readiness_gate_before_mannequin_test'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_upstream_or_mannequin_interface_condition',
      'rerun_gate_before_any_pilot_static_fit'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
