[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MovementGateScript = Join-Path $PSScriptRoot 'fr017-pilot-movement-gate.ps1'

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

function Test-SignalMatchesPrefix {
  param(
    [string]$Signal,
    [string]$Prefix
  )

  if ([string]::Equals($Signal, $Prefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    return $true
  }
  return $Signal.StartsWith($Prefix + '.', [System.StringComparison]::OrdinalIgnoreCase) -or
    $Signal.StartsWith($Prefix + '_', [System.StringComparison]::OrdinalIgnoreCase)
}

function Get-CaptureStepSignals {
  param(
    [string[]]$Signals,
    [string[]]$RequiredFields,
    [string[]]$SignalPrefixes
  )

  $Result = New-Object System.Collections.Generic.List[string]
  foreach ($Signal in (ConvertTo-StringArray -Value $Signals)) {
    foreach ($Field in $RequiredFields) {
      if (Test-SignalMatchesPrefix -Signal $Signal -Prefix $Field) {
        Add-UniqueString -Target $Result -Value $Signal
      }
    }
    foreach ($Prefix in $SignalPrefixes) {
      if (Test-SignalMatchesPrefix -Signal $Signal -Prefix $Prefix) {
        Add-UniqueString -Target $Result -Value $Signal
      }
    }
  }
  return @($Result.ToArray())
}

function New-ReleaseCableCapturePlanStatus {
  param(
    [object[]]$CapturePlan,
    [bool]$UpstreamMovementReady,
    [string[]]$MissingFields,
    [string[]]$InvalidFields,
    [string[]]$BlockingSignals
  )

  $Result = New-Object System.Collections.Generic.List[object]
  foreach ($Step in $CapturePlan) {
    $RequiredFields = @(ConvertTo-StringArray -Value $Step.required_fields)
    $SignalPrefixes = @(ConvertTo-StringArray -Value $Step.blocking_signal_prefixes)
    $StepMissing = @(Get-CaptureStepSignals -Signals $MissingFields -RequiredFields $RequiredFields -SignalPrefixes @())
    $StepInvalid = @(Get-CaptureStepSignals -Signals $InvalidFields -RequiredFields $RequiredFields -SignalPrefixes @())
    $StepBlockingSignals = @(Get-CaptureStepSignals -Signals $BlockingSignals -RequiredFields $RequiredFields -SignalPrefixes $SignalPrefixes)

    $Status = 'ready_for_release_cable_record_review'
    $RequiredAction = [string]$Step.required_action
    if (-not $UpstreamMovementReady) {
      $Status = 'blocked_by_upstream_pilot_movement'
      $RequiredAction = 'complete measurement intake, mockup, mannequin interface, pilot static-fit, and pilot movement gates before release/cable evidence can be captured or reviewed'
    } elseif ($StepBlockingSignals.Count -gt 0) {
      $Status = 'failed_stop_condition_or_blocking_signal'
    } elseif ($StepInvalid.Count -gt 0) {
      $Status = 'invalid_required_fields'
    } elseif ($StepMissing.Count -gt 0) {
      $Status = 'pending_required_fields'
    }

    $Result.Add([ordered]@{
        id = [string]$Step.id
        status = $Status
        validation_state = [string]$Step.validation_state
        ready_for_release_cable_record_review = ($Status -eq 'ready_for_release_cable_record_review')
        missing_fields = @($StepMissing)
        invalid_fields = @($StepInvalid)
        blocking_signals = @($StepBlockingSignals)
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
  $UpstreamBlockedCount = 0
  $FirstBlockingGroupId = ''
  $FirstBlockingGroupStatus = ''
  $FirstBlockingGroupAction = ''

  foreach ($Step in $CapturePlanStatus) {
    $StepStatus = [string]$Step.status
    if ($StepStatus -eq 'ready_for_release_cable_record_review') {
      $ReadyCount += 1
    } elseif ($StepStatus -eq 'pending_required_fields') {
      $PendingCount += 1
    } elseif ($StepStatus -eq 'invalid_required_fields') {
      $InvalidCount += 1
    } elseif ($StepStatus -eq 'failed_stop_condition_or_blocking_signal') {
      $FailedCount += 1
    } elseif ($StepStatus -eq 'blocked_by_upstream_pilot_movement') {
      $UpstreamBlockedCount += 1
    }

    if ([string]::IsNullOrWhiteSpace($FirstBlockingGroupId) -and $StepStatus -ne 'ready_for_release_cable_record_review') {
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
    upstream_blocked_groups = $UpstreamBlockedCount
    first_blocking_group_id = $FirstBlockingGroupId
    first_blocking_group_status = $FirstBlockingGroupStatus
    first_blocking_group_action = $FirstBlockingGroupAction
  }
}

function Add-PilotIdentityLinkageCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [object]$ReleasePilotId,
    [string]$MovementRecordPath
  )

  if (-not (Test-PresentText -Value $ReleasePilotId)) {
    return
  }

  try {
    $MovementPayload = Get-Content -LiteralPath $MovementRecordPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $MovementEvidence = Get-PropertyValue -Payload $MovementPayload -Name 'evidence'
    $MovementPilotId = Get-PropertyValue -Payload $MovementEvidence -Name 'pilot_id' -Default ''
    if (-not (Test-PresentText -Value $MovementPilotId)) {
      $Invalid.Add('evidence.pilot_movement_record_path') | Out-Null
      return
    }
    if (-not [string]::Equals([string]$ReleasePilotId, [string]$MovementPilotId, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add('evidence.pilot_id_must_match_movement_pilot_id') | Out-Null
    }
  } catch {
    $Invalid.Add('evidence.pilot_movement_record_path') | Out-Null
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

function Invoke-MovementGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath,
    [string]$ResolvedMovementPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $MovementGateScript,
    '-Mode',
    'Status',
    '-MeasurementPath',
    $ResolvedMeasurementPath,
    '-MockupPath',
    $ResolvedMockupPath,
    '-MannequinPath',
    $ResolvedMannequinPath,
    '-StaticFitPath',
    $ResolvedStaticFitPath,
    '-MovementPath',
    $ResolvedMovementPath
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
  'pilot_movement_gate_passed',
  'observer_present',
  'emergency_release_briefed',
  'stop_on_symptoms',
  'pilot_can_self_remove_or_abort'
)

$RequiredReleaseChecks = @(
  'bare_cuff_release_visible_tactile_reachable',
  'glove_base_mockup_release_visible_tactile_reachable',
  'wrist_assembly_mockup_release_visible_tactile_reachable',
  'forearm_frame_mockup_release_visible_tactile_reachable',
  'forearm_armor_mockup_release_visible_tactile_reachable',
  'populated_cable_sleeve_release_visible_tactile_reachable',
  'post_movement_release_visible_tactile_reachable',
  'opposite_hand_release_reachable',
  'same_side_reach_recorded',
  'release_loosens_upper_strap',
  'release_loosens_lower_strap',
  'cuff_removable_without_tools',
  'no_painful_wrist_posture_required',
  'glove_and_wrist_paths_not_trapped'
)

$RequiredCableSleeveChecks = @(
  'outer_forearm_route_preserved',
  'no_inner_elbow_crossing',
  'no_wrist_bone_crossing',
  'no_palm_or_grip_crossing',
  'no_release_handle_obstruction',
  'no_snag_during_release',
  'no_snag_after_elbow_wrist_motion',
  'cable_not_trapped_after_release'
)

$FailObservationFields = @(
  'release_hidden',
  'release_not_found_by_touch',
  'release_blocked_by_glove_or_armor',
  'release_fails_to_loosen',
  'cuff_not_removable_without_tools',
  'painful_wrist_posture_required',
  'cable_trapped_after_release',
  'cable_crossed_no_go_zone'
)

$ReleaseCableEvidenceFields = @(
  'evidence.date',
  'evidence.observer',
  'evidence.pilot_id',
  'evidence.prototype_revision',
  'evidence.pilot_movement_record_path',
  'evidence.test_duration_minutes'
)

$ReleaseCablePreconditionFields = @()
foreach ($Field in $RequiredPreconditions) {
  $ReleaseCablePreconditionFields += ('preconditions.{0}' -f $Field)
}

$LeftReleaseCheckFields = @()
$RightReleaseCheckFields = @()
foreach ($Field in $RequiredReleaseChecks) {
  $LeftReleaseCheckFields += ('sides.left.release_checks.{0}' -f $Field)
  $RightReleaseCheckFields += ('sides.right.release_checks.{0}' -f $Field)
}

$LeftCableAndFailFields = @()
$RightCableAndFailFields = @()
foreach ($Field in $RequiredCableSleeveChecks) {
  $LeftCableAndFailFields += ('sides.left.cable_sleeve_checks.{0}' -f $Field)
  $RightCableAndFailFields += ('sides.right.cable_sleeve_checks.{0}' -f $Field)
}
foreach ($Field in $FailObservationFields) {
  $LeftCableAndFailFields += ('sides.left.fail_observations.{0}' -f $Field)
  $RightCableAndFailFields += ('sides.right.fail_observations.{0}' -f $Field)
}

$ReleaseCableCapturePlan = @(
  [ordered]@{
    id = 'release_cable_evidence_and_linkage'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST_RECORD'
    required_fields = $ReleaseCableEvidenceFields
    blocking_signal_prefixes = @(
      'evidence.pilot_movement_record_path_must_match_movement_path',
      'evidence.pilot_id_must_match_movement_pilot_id',
      'evidence.date_before_movement.evidence.date'
    )
    required_action = 'record ISO date, observer, matching pilot id, prototype revision, linked movement record path, and an unquoted positive quick-release/cable-snag test duration'
  },
  [ordered]@{
    id = 'release_cable_safety_preconditions'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST'
    required_fields = $ReleaseCablePreconditionFields
    blocking_signal_prefixes = @('preconditions')
    required_action = 'confirm non-powered-only setup, no frame or power coupling, movement gate passed, observer presence, emergency-release briefing, stop-on-symptoms rule, and pilot self-removal or abort authority'
  },
  [ordered]@{
    id = 'left_quick_release_access'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST'
    required_fields = $LeftReleaseCheckFields
    blocking_signal_prefixes = @('sides.left.release_checks')
    required_action = 'record left release visibility, tactile reach, same-side and opposite-hand reach, strap loosening, tool-free cuff removal, wrist posture, and glove/wrist path clearance across bare cuff and future mock interfaces'
  },
  [ordered]@{
    id = 'right_quick_release_access'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST'
    required_fields = $RightReleaseCheckFields
    blocking_signal_prefixes = @('sides.right.release_checks')
    required_action = 'record right release visibility, tactile reach, same-side and opposite-hand reach, strap loosening, tool-free cuff removal, wrist posture, and glove/wrist path clearance across bare cuff and future mock interfaces'
  },
  [ordered]@{
    id = 'left_cable_route_and_fail_observations'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST'
    required_fields = $LeftCableAndFailFields
    blocking_signal_prefixes = @('sides.left.cable_sleeve_checks', 'sides.left.fail_observations')
    required_action = 'record left outer-forearm cable route preservation, no-go-zone avoidance, release-handle clearance, no snag before/after release and motion, and every left release/cable fail observation as absent before advancing'
  },
  [ordered]@{
    id = 'right_cable_route_and_fail_observations'
    validation_state = 'REQUIRES_QUICK_RELEASE_CABLE_SNAG_TEST'
    required_fields = $RightCableAndFailFields
    blocking_signal_prefixes = @('sides.right.cable_sleeve_checks', 'sides.right.fail_observations')
    required_action = 'record right outer-forearm cable route preservation, no-go-zone avoidance, release-handle clearance, no snag before/after release and motion, and every right release/cable fail observation as absent before advancing'
  }
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$DefaultMannequinPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$DefaultStaticFitPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json'
$DefaultMovementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json'
$DefaultReleaseCablePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-GatePath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-GatePath -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { $DefaultMannequinPath } else { Resolve-GatePath -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { $DefaultStaticFitPath } else { Resolve-GatePath -Path $StaticFitPath }
$ResolvedMovementPath = if ([string]::IsNullOrWhiteSpace($MovementPath)) { $DefaultMovementPath } else { Resolve-GatePath -Path $MovementPath }
$ResolvedReleaseCablePath = if ([string]::IsNullOrWhiteSpace($ReleaseCablePath)) { $DefaultReleaseCablePath } else { Resolve-GatePath -Path $ReleaseCablePath }
$UsingReleaseCableTemplate = [string]::IsNullOrWhiteSpace($ReleaseCablePath)

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$RecordLinkageViolations = New-Object System.Collections.Generic.List[string]
$RecordChronologyViolations = New-Object System.Collections.Generic.List[string]
$ReleaseCableRedesignTriggers = New-Object System.Collections.Generic.List[string]
$FailObservations = New-Object System.Collections.Generic.List[string]
$ReleaseCableParseOk = $false
$ReleaseCableStatus = 'pending_quick_release_cable_snag_test'
$Status = 'pending_pilot_movement_gate'
$ExitCode = 0

$Upstream = Invoke-MovementGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath
$UpstreamStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_upstream_pilot_movement_gate' }
$UpstreamReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStatus -eq 'ready_for_quick_release_and_cable_snag_test_planning'

if (-not [bool]$Upstream.parse_ok -or [int]$Upstream.exit_code -ne 0 -or $UpstreamStatus.StartsWith('failed_')) {
  $Status = 'failed_upstream_pilot_movement_gate'
  $ExitCode = 1
} elseif (-not $UpstreamReady) {
  $Status = 'pending_pilot_movement_gate'
} else {
  if (-not (Test-Path -LiteralPath $ResolvedReleaseCablePath -PathType Leaf)) {
    $ReleaseCableStatus = 'failed_release_cable_record'
    $InvalidFields.Add('release_cable_file') | Out-Null
  } else {
    try {
      $ReleaseCablePayload = Get-Content -LiteralPath $ResolvedReleaseCablePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $ReleaseCableParseOk = $true
    } catch {
      $ReleaseCableStatus = 'failed_release_cable_record'
      $InvalidFields.Add('release_cable_json_parse') | Out-Null
    }
  }

  if ($ReleaseCableParseOk) {
    if ([string](Get-PropertyValue -Payload $ReleaseCablePayload -Name 'kind' -Default '') -ne 'francis.fr017.quick_release_cable_snag.v1') {
      $InvalidFields.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $ReleaseCablePayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $InvalidFields.Add('component') | Out-Null
    }

    $Evidence = Get-PropertyValue -Payload $ReleaseCablePayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
    $ReleasePilotId = Get-PropertyValue -Payload $Evidence -Name 'pilot_id'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value $ReleasePilotId
    Add-IfMissingText -Target $MissingFields -Field 'evidence.prototype_revision' -Value (Get-PropertyValue -Payload $Evidence -Name 'prototype_revision')
    $ReleaseMovementRecordPath = Get-PropertyValue -Payload $Evidence -Name 'pilot_movement_record_path'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_movement_record_path' -Value $ReleaseMovementRecordPath
    if (Test-PresentText -Value $ReleaseMovementRecordPath) {
      try {
        $ResolvedReleaseMovementRecordPath = Resolve-GatePath -Path ([string]$ReleaseMovementRecordPath)
        if (-not [string]::Equals($ResolvedReleaseMovementRecordPath, $ResolvedMovementPath, [System.StringComparison]::OrdinalIgnoreCase)) {
          $RecordLinkageViolations.Add('evidence.pilot_movement_record_path_must_match_movement_path') | Out-Null
        }
      } catch {
        $InvalidFields.Add('evidence.pilot_movement_record_path') | Out-Null
      }
    }
    Add-PilotIdentityLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -ReleasePilotId $ReleasePilotId -MovementRecordPath $ResolvedMovementPath
    Add-RequiredPositiveJsonNumber -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.test_duration_minutes' -Value (Get-PropertyValue -Payload $Evidence -Name 'test_duration_minutes')

    try {
      $MovementPayloadForChronology = Get-Content -LiteralPath $ResolvedMovementPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $MovementEvidenceDate = Get-EvidenceDateOrNull -Payload $MovementPayloadForChronology
      $ReleaseCableEvidenceDate = Get-EvidenceDateOrNull -Payload $ReleaseCablePayload
      if ($null -ne $MovementEvidenceDate -and $null -ne $ReleaseCableEvidenceDate -and $ReleaseCableEvidenceDate -lt $MovementEvidenceDate) {
        $RecordChronologyViolations.Add('evidence.date_before_movement.evidence.date') | Out-Null
      }
    } catch {
      $InvalidFields.Add('movement_json_parse_for_chronology') | Out-Null
    }

    $Preconditions = Get-PropertyValue -Payload $ReleaseCablePayload -Name 'preconditions'
    foreach ($Field in $RequiredPreconditions) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReleaseCableRedesignTriggers -Field ('preconditions.{0}' -f $Field) -Value (Get-PropertyValue -Payload $Preconditions -Name $Field)
    }

    $Sides = Get-PropertyValue -Payload $ReleaseCablePayload -Name 'sides'
    foreach ($Side in @('left', 'right')) {
      $SidePayload = Get-PropertyValue -Payload $Sides -Name $Side
      $ReleaseChecks = Get-PropertyValue -Payload $SidePayload -Name 'release_checks'
      foreach ($Field in $RequiredReleaseChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReleaseCableRedesignTriggers -Field ('sides.{0}.release_checks.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $ReleaseChecks -Name $Field)
      }

      $CableSleeveChecks = Get-PropertyValue -Payload $SidePayload -Name 'cable_sleeve_checks'
      foreach ($Field in $RequiredCableSleeveChecks) {
        Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReleaseCableRedesignTriggers -Field ('sides.{0}.cable_sleeve_checks.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $CableSleeveChecks -Name $Field)
      }

      $FailObservationPayload = Get-PropertyValue -Payload $SidePayload -Name 'fail_observations'
      foreach ($Field in $FailObservationFields) {
        Add-RequiredFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Fail $FailObservations -Field ('sides.{0}.fail_observations.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $FailObservationPayload -Name $Field)
      }
    }

    if ($InvalidFields.Count -gt 0 -or $RecordLinkageViolations.Count -gt 0 -or $RecordChronologyViolations.Count -gt 0) {
      $ReleaseCableStatus = 'failed_release_cable_record'
      $Status = $ReleaseCableStatus
      $ExitCode = 1
    } elseif ($ReleaseCableRedesignTriggers.Count -gt 0 -or $FailObservations.Count -gt 0) {
      $ReleaseCableStatus = 'failed_requires_release_cable_redesign_or_medical_review'
      $Status = $ReleaseCableStatus
      $ExitCode = 1
    } elseif ($MissingFields.Count -gt 0 -or $UsingReleaseCableTemplate) {
      $ReleaseCableStatus = 'pending_quick_release_cable_snag_test'
      $Status = $ReleaseCableStatus
    } else {
      $ReleaseCableStatus = 'ready_for_engineering_review_or_final_physical_gate_audit'
      $Status = $ReleaseCableStatus
    }
  } else {
    $Status = $ReleaseCableStatus
    if ($ReleaseCableStatus.StartsWith('failed_')) {
      $ExitCode = 1
    }
  }
}

$AllReleaseCableBlockingSignals = New-Object System.Collections.Generic.List[string]
foreach ($Signal in @($RecordLinkageViolations.ToArray())) {
  Add-UniqueString -Target $AllReleaseCableBlockingSignals -Value $Signal
}
foreach ($Signal in @($RecordChronologyViolations.ToArray())) {
  Add-UniqueString -Target $AllReleaseCableBlockingSignals -Value $Signal
}
foreach ($Signal in @($ReleaseCableRedesignTriggers.ToArray())) {
  Add-UniqueString -Target $AllReleaseCableBlockingSignals -Value $Signal
}
foreach ($Signal in @($FailObservations.ToArray())) {
  Add-UniqueString -Target $AllReleaseCableBlockingSignals -Value $Signal
}
$ReleaseCableCapturePlanStatus = @(New-ReleaseCableCapturePlanStatus -CapturePlan $ReleaseCableCapturePlan -UpstreamMovementReady $UpstreamReady -MissingFields $MissingFields.ToArray() -InvalidFields $InvalidFields.ToArray() -BlockingSignals $AllReleaseCableBlockingSignals.ToArray())
$ReleaseCableCapturePlanSummary = New-CapturePlanSummary -CapturePlanStatus $ReleaseCableCapturePlanStatus

$Output = [ordered]@{
  kind = 'francis.fr017.quick_release_cable_snag_gate'
  mode = $Mode
  status = $Status
  upstream_pilot_movement_status = $UpstreamStatus
  upstream_pilot_movement_gate_exit_code = [int]$Upstream.exit_code
  upstream_pilot_movement_gate_parse_ok = [bool]$Upstream.parse_ok
  upstream_pilot_movement_gate_ready = $UpstreamReady
  upstream_static_fit_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_static_fit_status' -Default '') } else { '' }
  upstream_static_fit_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_static_fit_gate_ready' -Default $false) } else { $false }
  upstream_mannequin_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_status' -Default '') } else { '' }
  upstream_mannequin_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_gate_ready' -Default $false) } else { $false }
  upstream_mockup_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mockup_status' -Default '') } else { '' }
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
  upstream_mannequin_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_record_linkage_violations')
  upstream_mannequin_interface_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_interface_redesign_triggers')
  upstream_static_fit_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_record_linkage_violations')
  upstream_static_fit_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_redesign_triggers')
  upstream_static_fit_symptom_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_symptom_blockers')
  upstream_movement_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'record_linkage_violations')
  upstream_movement_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'movement_redesign_triggers')
  upstream_movement_symptom_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'symptom_blockers')
  release_cable_status = $ReleaseCableStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  release_cable_path = $ResolvedReleaseCablePath
  using_release_cable_template = $UsingReleaseCableTemplate
  release_cable_parse_ok = $ReleaseCableParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  quick_release_and_cable_snag_test_complete = ($Status -eq 'ready_for_engineering_review_or_final_physical_gate_audit')
  engineering_review_or_final_physical_gate_audit_ready = ($Status -eq 'ready_for_engineering_review_or_final_physical_gate_audit')
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_preconditions = $RequiredPreconditions
  required_release_checks = $RequiredReleaseChecks
  required_cable_sleeve_checks = $RequiredCableSleeveChecks
  fail_observation_fields = $FailObservationFields
  release_cable_capture_plan_contract = 'The release_cable_capture_plan is read-only operator guidance for capturing FR-017 non-powered quick-release and cable-snag evidence. It is not physical validation evidence by itself, does not prove pilot safety, and cannot clear engineering review, powered, frame-coupled, or FR-018 work.'
  release_cable_capture_plan_status_contract = 'The release_cable_capture_plan_status reports quick-release/cable-snag capture readiness only. A ready group means the supplied record fields passed this script contract; it is not professional certification, medical clearance, or Stage 17 completion.'
  release_cable_capture_summary_contract = 'The release_cable_capture_* summary identifies the next blocking quick-release/cable-snag evidence group. It is not physical validation evidence and cannot mark Stage 17 complete.'
  release_cable_capture_plan_not_completion_evidence = $true
  next_required_release_cable_input = 'complete_non_powered_quick_release_cable_snag_record_at_FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json'
  release_cable_capture_plan = @($ReleaseCableCapturePlan)
  release_cable_capture_plan_status = @($ReleaseCableCapturePlanStatus)
  release_cable_capture_total_groups = [int]$ReleaseCableCapturePlanSummary.total_groups
  release_cable_capture_ready_groups = [int]$ReleaseCableCapturePlanSummary.ready_groups
  release_cable_capture_pending_groups = [int]$ReleaseCableCapturePlanSummary.pending_groups
  release_cable_capture_invalid_groups = [int]$ReleaseCableCapturePlanSummary.invalid_groups
  release_cable_capture_failed_groups = [int]$ReleaseCableCapturePlanSummary.failed_groups
  release_cable_capture_upstream_blocked_groups = [int]$ReleaseCableCapturePlanSummary.upstream_blocked_groups
  release_cable_capture_first_blocking_group_id = [string]$ReleaseCableCapturePlanSummary.first_blocking_group_id
  release_cable_capture_first_blocking_group_status = [string]$ReleaseCableCapturePlanSummary.first_blocking_group_status
  release_cable_capture_first_blocking_group_action = [string]$ReleaseCableCapturePlanSummary.first_blocking_group_action
  record_linkage_contract = 'The quick-release/cable-snag evidence.pilot_movement_record_path must resolve to the same movement record path passed into this gate. A release/cable record cannot advance from stale, copied, or unrelated movement evidence.'
  pilot_identity_linkage_contract = 'The quick-release/cable-snag evidence.pilot_id must match evidence.pilot_id in the linked movement record. A release/cable record cannot advance if it names a different pilot than the completed movement evidence.'
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated quick-release/cable-snag evidence is invalid because it cannot be completed evidence.'
  evidence_chronology_contract = 'Quick-release/cable-snag evidence.date must be the same as or later than the linked pilot movement evidence.date. A release/cable record cannot advance from movement evidence that was not yet recorded.'
  test_duration_value_contract = 'Use an unquoted JSON number greater than 0 for evidence.test_duration_minutes. Quoted numeric strings are invalid. PENDING is treated as missing evidence.'
  boolean_value_contract = 'Use unquoted JSON boolean true only when the release or cable condition is directly verified. Use false for verified failure or for absent fail observations as appropriate. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  record_linkage_violations = @($RecordLinkageViolations.ToArray())
  record_chronology_violations = @($RecordChronologyViolations.ToArray())
  release_cable_redesign_triggers = @($ReleaseCableRedesignTriggers.ToArray())
  fail_observations = @($FailObservations.ToArray())
  next_actions = if ($Status -eq 'ready_for_engineering_review_or_final_physical_gate_audit') {
    @(
      'prepare_engineering_review_packet_without_powered_or_frame_coupled_testing',
      'run_final_FR-017_physical_gate_audit_against_all_evidence',
      'keep_FR-018_implementation_blocked_until_final_FR-017_physical_gate_closes'
    )
  } elseif ($Status -eq 'pending_quick_release_cable_snag_test') {
    @(
      'run_non_powered_quick_release_and_cable_snag_test_with_observer',
      'complete_FR-017_release_cable_record',
      'rerun_quick_release_cable_snag_gate'
    )
  } elseif ($Status -eq 'pending_pilot_movement_gate') {
    @(
      'complete_measurement_mockup_mannequin_static_and_movement_gates',
      'rerun_quick_release_cable_snag_gate_after_upstream_ready'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_upstream_release_or_cable_condition',
      'rerun_gate_before_any_engineering_review_or_final_audit'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
