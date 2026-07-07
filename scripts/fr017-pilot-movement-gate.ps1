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

function New-MovementCapturePlanStatus {
  param(
    [object[]]$CapturePlan,
    [bool]$UpstreamStaticFitReady,
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

    $Status = 'ready_for_movement_record_review'
    $RequiredAction = [string]$Step.required_action
    if (-not $UpstreamStaticFitReady) {
      $Status = 'blocked_by_upstream_static_fit'
      $RequiredAction = 'complete measurement intake, mockup, mannequin interface, and pilot static-fit gates before pilot movement evidence can be captured or reviewed'
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
        ready_for_movement_record_review = ($Status -eq 'ready_for_movement_record_review')
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
  $FirstBlockingGroupMissingFields = @()
  $FirstBlockingGroupInvalidFields = @()
  $FirstBlockingGroupBlockingSignals = @()

  foreach ($Step in $CapturePlanStatus) {
    $StepStatus = [string]$Step.status
    if ($StepStatus -eq 'ready_for_movement_record_review') {
      $ReadyCount += 1
    } elseif ($StepStatus -eq 'pending_required_fields') {
      $PendingCount += 1
    } elseif ($StepStatus -eq 'invalid_required_fields') {
      $InvalidCount += 1
    } elseif ($StepStatus -eq 'failed_stop_condition_or_blocking_signal') {
      $FailedCount += 1
    } elseif ($StepStatus -eq 'blocked_by_upstream_static_fit') {
      $UpstreamBlockedCount += 1
    }

    if ([string]::IsNullOrWhiteSpace($FirstBlockingGroupId) -and $StepStatus -ne 'ready_for_movement_record_review') {
      $FirstBlockingGroupId = [string]$Step.id
      $FirstBlockingGroupStatus = $StepStatus
      $FirstBlockingGroupAction = [string]$Step.required_action
      $FirstBlockingGroupMissingFields = @(ConvertTo-StringArray -Value $Step.missing_fields)
      $FirstBlockingGroupInvalidFields = @(ConvertTo-StringArray -Value $Step.invalid_fields)
      $FirstBlockingGroupBlockingSignals = @(ConvertTo-StringArray -Value $Step.blocking_signals)
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
    first_blocking_group_missing_fields = @($FirstBlockingGroupMissingFields)
    first_blocking_group_invalid_fields = @($FirstBlockingGroupInvalidFields)
    first_blocking_group_blocking_signals = @($FirstBlockingGroupBlockingSignals)
  }
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

$MovementEvidenceFields = @(
  'evidence.date',
  'evidence.observer',
  'evidence.pilot_id',
  'evidence.prototype_revision',
  'evidence.pilot_static_fit_record_path',
  'evidence.test_duration_minutes'
)

$MovementPreconditionFields = @()
foreach ($Field in $RequiredPreconditions) {
  $MovementPreconditionFields += ('preconditions.{0}' -f $Field)
}

$LeftMovementCheckFields = @()
$RightMovementCheckFields = @()
foreach ($Field in $RequiredMovementChecks) {
  $LeftMovementCheckFields += ('sides.left.movement_checks.{0}' -f $Field)
  $RightMovementCheckFields += ('sides.right.movement_checks.{0}' -f $Field)
}

$LeftPostMovementSymptomFields = @()
$RightPostMovementSymptomFields = @()
foreach ($Field in $RequiredPostMovementChecks) {
  $LeftPostMovementSymptomFields += ('sides.left.post_movement.{0}' -f $Field)
  $RightPostMovementSymptomFields += ('sides.right.post_movement.{0}' -f $Field)
}
foreach ($Field in $SymptomFields) {
  $LeftPostMovementSymptomFields += ('sides.left.symptoms.{0}' -f $Field)
  $RightPostMovementSymptomFields += ('sides.right.symptoms.{0}' -f $Field)
}

$MovementCapturePlan = @(
  [ordered]@{
    id = 'movement_evidence_and_linkage'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST_RECORD'
    required_fields = $MovementEvidenceFields
    blocking_signal_prefixes = @(
      'evidence.pilot_static_fit_record_path_must_match_static_fit_path',
      'evidence.pilot_id_must_match_static_fit_pilot_id',
      'evidence.date_before_static_fit.evidence.date'
    )
    required_action = 'record ISO date, observer, matching pilot id, prototype revision, linked static-fit record path, and an unquoted positive movement-test duration'
  },
  [ordered]@{
    id = 'movement_safety_preconditions'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST'
    required_fields = $MovementPreconditionFields
    blocking_signal_prefixes = @('preconditions')
    required_action = 'confirm non-powered-only setup, no frame or power coupling, static-fit gate passed, observer presence, emergency-release briefing, stop-on-symptoms rule, and pilot self-removal or abort authority'
  },
  [ordered]@{
    id = 'left_movement_clearance'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST'
    required_fields = $LeftMovementCheckFields
    blocking_signal_prefixes = @('sides.left.movement_checks')
    required_action = 'record left elbow, wrist, hand opening, grip, glove removal, wrist assembly removal, outer cable route, quick-release reach, and cuff return checks during non-powered movement'
  },
  [ordered]@{
    id = 'right_movement_clearance'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST'
    required_fields = $RightMovementCheckFields
    blocking_signal_prefixes = @('sides.right.movement_checks')
    required_action = 'record right elbow, wrist, hand opening, grip, glove removal, wrist assembly removal, outer cable route, quick-release reach, and cuff return checks during non-powered movement'
  },
  [ordered]@{
    id = 'left_post_movement_and_symptoms'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST'
    required_fields = $LeftPostMovementSymptomFields
    blocking_signal_prefixes = @('sides.left.post_movement', 'sides.left.symptoms')
    required_action = 'record left post-motion warmth, color, grip, pressure marks, and every left-side pain, tingling, numbness, temperature, color, weakness, wrist, pressure, finger-motion, and grip-strength symptom as absent before advancing'
  },
  [ordered]@{
    id = 'right_post_movement_and_symptoms'
    validation_state = 'REQUIRES_PILOT_MOVEMENT_TEST'
    required_fields = $RightPostMovementSymptomFields
    blocking_signal_prefixes = @('sides.right.post_movement', 'sides.right.symptoms')
    required_action = 'record right post-motion warmth, color, grip, pressure marks, and every right-side pain, tingling, numbness, temperature, color, weakness, wrist, pressure, finger-motion, and grip-strength symptom as absent before advancing'
  }
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$DefaultMannequinPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$DefaultStaticFitPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json'
$DefaultMovementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json'
$MovementRecordInitializerPath = Join-Path $RepoRoot 'scripts\fr017-new-pilot-movement-record.ps1'
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

$AllMovementBlockingSignals = New-Object System.Collections.Generic.List[string]
foreach ($Signal in @($RecordLinkageViolations.ToArray())) {
  Add-UniqueString -Target $AllMovementBlockingSignals -Value $Signal
}
foreach ($Signal in @($RecordChronologyViolations.ToArray())) {
  Add-UniqueString -Target $AllMovementBlockingSignals -Value $Signal
}
foreach ($Signal in @($MovementRedesignTriggers.ToArray())) {
  Add-UniqueString -Target $AllMovementBlockingSignals -Value $Signal
}
foreach ($Signal in @($SymptomBlockers.ToArray())) {
  Add-UniqueString -Target $AllMovementBlockingSignals -Value $Signal
}
$MovementCapturePlanStatus = @(New-MovementCapturePlanStatus -CapturePlan $MovementCapturePlan -UpstreamStaticFitReady $UpstreamReady -MissingFields $MissingFields.ToArray() -InvalidFields $InvalidFields.ToArray() -BlockingSignals $AllMovementBlockingSignals.ToArray())
$MovementCapturePlanSummary = New-CapturePlanSummary -CapturePlanStatus $MovementCapturePlanStatus

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
  stage17_completion_claim_allowed = $false
  pilot_movement_test_complete = ($Status -eq 'ready_for_quick_release_and_cable_snag_test_planning')
  quick_release_and_cable_snag_test_planning_ready = ($Status -eq 'ready_for_quick_release_and_cable_snag_test_planning')
  quick_release_and_cable_snag_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_preconditions = $RequiredPreconditions
  required_movement_checks = $RequiredMovementChecks
  required_post_movement_checks = $RequiredPostMovementChecks
  symptom_fields = $SymptomFields
  movement_capture_plan_contract = 'The movement_capture_plan is read-only operator guidance for capturing FR-017 non-powered pilot movement evidence. It is not physical validation evidence by itself, does not prove pilot safety, and cannot clear release/cable testing, powered, frame-coupled, or FR-018 work.'
  movement_capture_plan_status_contract = 'The movement_capture_plan_status reports pilot movement capture readiness only. A ready group means the supplied record fields passed this script contract; it is not professional certification, medical clearance, or quick-release/cable-snag clearance.'
  movement_capture_summary_contract = 'The movement_capture_* summary identifies the next blocking pilot movement evidence group. It is not physical validation evidence and cannot mark Stage 17 complete.'
  movement_capture_runbook_contract = 'Use FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json with completed measurement, mockup, mannequin, and static-fit records. Use scripts/fr017-new-pilot-movement-record.ps1 only to create a real operator-supplied non-powered pilot movement working record after pilot static-fit readiness is ready. The template, initializer, and gate are operator input tooling only; they are not physical validation completion, quick-release/cable-snag clearance, powered testing clearance, frame-coupled testing clearance, professional engineering approval, or FR-018 clearance.'
  movement_capture_plan_not_completion_evidence = $true
  next_required_movement_input = 'create_non_powered_pilot_movement_record_with_fr017-new-pilot-movement-record.ps1_then_rerun_pilot_movement_gate'
  movement_input_template_path = $DefaultMovementPath
  movement_record_initializer_path = $MovementRecordInitializerPath
  movement_working_record_name_pattern = 'FR-017-PILOT-MOVEMENT-YYYY-MM-DD-PILOT-RECORD.json'
  movement_capture_plan = @($MovementCapturePlan)
  movement_capture_plan_status = @($MovementCapturePlanStatus)
  movement_capture_total_groups = [int]$MovementCapturePlanSummary.total_groups
  movement_capture_ready_groups = [int]$MovementCapturePlanSummary.ready_groups
  movement_capture_pending_groups = [int]$MovementCapturePlanSummary.pending_groups
  movement_capture_invalid_groups = [int]$MovementCapturePlanSummary.invalid_groups
  movement_capture_failed_groups = [int]$MovementCapturePlanSummary.failed_groups
  movement_capture_upstream_blocked_groups = [int]$MovementCapturePlanSummary.upstream_blocked_groups
  movement_capture_first_blocking_group_id = [string]$MovementCapturePlanSummary.first_blocking_group_id
  movement_capture_first_blocking_group_status = [string]$MovementCapturePlanSummary.first_blocking_group_status
  movement_capture_first_blocking_group_action = [string]$MovementCapturePlanSummary.first_blocking_group_action
  movement_capture_first_blocking_group_missing_fields = @($MovementCapturePlanSummary.first_blocking_group_missing_fields)
  movement_capture_first_blocking_group_invalid_fields = @($MovementCapturePlanSummary.first_blocking_group_invalid_fields)
  movement_capture_first_blocking_group_blocking_signals = @($MovementCapturePlanSummary.first_blocking_group_blocking_signals)
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
      'create_non_powered_pilot_movement_record_with_fr017-new-pilot-movement-record.ps1',
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
