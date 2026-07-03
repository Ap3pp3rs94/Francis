[CmdletBinding()]
param(
  [ValidateSet('Create')]
  [string]$Mode = 'Create',

  [Parameter(Mandatory = $true)]
  [string]$OutputPath,

  [Parameter(Mandatory = $true)]
  [string]$MeasurementPath,

  [Parameter(Mandatory = $true)]
  [string]$MockupPath,

  [Parameter(Mandatory = $true)]
  [string]$MannequinPath,

  [Parameter(Mandatory = $true)]
  [string]$StaticFitPath,

  [Parameter(Mandatory = $true)]
  [string]$MovementPath,

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Observer = '',

  [string]$PilotId = '',

  [string]$PrototypeRevision = '',

  [double]$TestDurationMinutes = 0,

  [switch]$ConfirmNonPoweredOnly,

  [switch]$ConfirmNoFrameOrPowerCoupling,

  [switch]$ConfirmPilotMovementGatePassed,

  [switch]$ConfirmObserverPresent,

  [switch]$ConfirmEmergencyReleaseBriefed,

  [switch]$ConfirmStopOnSymptoms,

  [switch]$ConfirmPilotCanSelfRemoveOrAbort,

  [switch]$ConfirmLeftBareCuffReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftGloveBaseMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftWristAssemblyMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftForearmFrameMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftForearmArmorMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftPopulatedCableSleeveReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftPostMovementReleaseVisibleTactileReachable,
  [switch]$ConfirmLeftOppositeHandReleaseReachable,
  [switch]$ConfirmLeftSameSideReachRecorded,
  [switch]$ConfirmLeftReleaseLoosensUpperStrap,
  [switch]$ConfirmLeftReleaseLoosensLowerStrap,
  [switch]$ConfirmLeftCuffRemovableWithoutTools,
  [switch]$ConfirmLeftNoPainfulWristPostureRequired,
  [switch]$ConfirmLeftGloveAndWristPathsNotTrapped,

  [switch]$ConfirmRightBareCuffReleaseVisibleTactileReachable,
  [switch]$ConfirmRightGloveBaseMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmRightWristAssemblyMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmRightForearmFrameMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmRightForearmArmorMockupReleaseVisibleTactileReachable,
  [switch]$ConfirmRightPopulatedCableSleeveReleaseVisibleTactileReachable,
  [switch]$ConfirmRightPostMovementReleaseVisibleTactileReachable,
  [switch]$ConfirmRightOppositeHandReleaseReachable,
  [switch]$ConfirmRightSameSideReachRecorded,
  [switch]$ConfirmRightReleaseLoosensUpperStrap,
  [switch]$ConfirmRightReleaseLoosensLowerStrap,
  [switch]$ConfirmRightCuffRemovableWithoutTools,
  [switch]$ConfirmRightNoPainfulWristPostureRequired,
  [switch]$ConfirmRightGloveAndWristPathsNotTrapped,

  [switch]$ConfirmLeftOuterForearmRoutePreserved,
  [switch]$ConfirmLeftNoInnerElbowCrossing,
  [switch]$ConfirmLeftNoWristBoneCrossing,
  [switch]$ConfirmLeftNoPalmOrGripCrossing,
  [switch]$ConfirmLeftNoReleaseHandleObstruction,
  [switch]$ConfirmLeftNoSnagDuringRelease,
  [switch]$ConfirmLeftNoSnagAfterElbowWristMotion,
  [switch]$ConfirmLeftCableNotTrappedAfterRelease,

  [switch]$ConfirmRightOuterForearmRoutePreserved,
  [switch]$ConfirmRightNoInnerElbowCrossing,
  [switch]$ConfirmRightNoWristBoneCrossing,
  [switch]$ConfirmRightNoPalmOrGripCrossing,
  [switch]$ConfirmRightNoReleaseHandleObstruction,
  [switch]$ConfirmRightNoSnagDuringRelease,
  [switch]$ConfirmRightNoSnagAfterElbowWristMotion,
  [switch]$ConfirmRightCableNotTrappedAfterRelease,

  [switch]$ConfirmNoLeftReleaseHidden,
  [switch]$ConfirmNoLeftReleaseNotFoundByTouch,
  [switch]$ConfirmNoLeftReleaseBlockedByGloveOrArmor,
  [switch]$ConfirmNoLeftReleaseFailsToLoosen,
  [switch]$ConfirmNoLeftCuffNotRemovableWithoutTools,
  [switch]$ConfirmNoLeftPainfulWristPostureRequired,
  [switch]$ConfirmNoLeftCableTrappedAfterRelease,
  [switch]$ConfirmNoLeftCableCrossedNoGoZone,

  [switch]$ConfirmNoRightReleaseHidden,
  [switch]$ConfirmNoRightReleaseNotFoundByTouch,
  [switch]$ConfirmNoRightReleaseBlockedByGloveOrArmor,
  [switch]$ConfirmNoRightReleaseFailsToLoosen,
  [switch]$ConfirmNoRightCuffNotRemovableWithoutTools,
  [switch]$ConfirmNoRightPainfulWristPostureRequired,
  [switch]$ConfirmNoRightCableTrappedAfterRelease,
  [switch]$ConfirmNoRightCableCrossedNoGoZone,

  [switch]$LeftReleaseHiddenObserved,
  [switch]$LeftReleaseNotFoundByTouchObserved,
  [switch]$LeftReleaseBlockedByGloveOrArmorObserved,
  [switch]$LeftReleaseFailsToLoosenObserved,
  [switch]$LeftCuffNotRemovableWithoutToolsObserved,
  [switch]$LeftPainfulWristPostureRequiredObserved,
  [switch]$LeftCableTrappedAfterReleaseObserved,
  [switch]$LeftCableCrossedNoGoZoneObserved,

  [switch]$RightReleaseHiddenObserved,
  [switch]$RightReleaseNotFoundByTouchObserved,
  [switch]$RightReleaseBlockedByGloveOrArmorObserved,
  [switch]$RightReleaseFailsToLoosenObserved,
  [switch]$RightCuffNotRemovableWithoutToolsObserved,
  [switch]$RightPainfulWristPostureRequiredObserved,
  [switch]$RightCableTrappedAfterReleaseObserved,
  [switch]$RightCableCrossedNoGoZoneObserved
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MovementGateScript = Join-Path $PSScriptRoot 'fr017-pilot-movement-gate.ps1'

function Resolve-Fr017Path {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Test-PathUnderRoot {
  param(
    [string]$Path,
    [string]$Root
  )

  $Separators = [char[]]@([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $FullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd($Separators)
  $FullRoot = [System.IO.Path]::GetFullPath($Root).TrimEnd($Separators)
  return [string]::Equals($FullPath, $FullRoot, [System.StringComparison]::OrdinalIgnoreCase) -or
    $FullPath.StartsWith($FullRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
    $FullPath.StartsWith($FullRoot + [System.IO.Path]::AltDirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
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

function Get-IsoDateOrNull {
  param([string]$Value)

  if (Test-MissingOrPendingText -Value $Value) {
    return $null
  }

  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Value.Trim(),
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

function Test-IsoDateNotFuture {
  param([string]$Value)

  $ParsedDate = Get-IsoDateOrNull -Value $Value
  return $null -ne $ParsedDate -and $ParsedDate -le [datetime]::Today
}

function Get-EvidencePilotId {
  param([string]$Path)

  try {
    $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -ErrorAction Stop
    $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
    return [string](Get-PropertyValue -Payload $Evidence -Name 'pilot_id' -Default '')
  } catch {
    return ''
  }
}

function Get-EvidenceDateOrNull {
  param([string]$Path)

  try {
    $Payload = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json -ErrorAction Stop
    $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
    $DateText = [string](Get-PropertyValue -Payload $Evidence -Name 'date' -Default '')
    return Get-IsoDateOrNull -Value $DateText
  } catch {
    return $null
  }
}

function Set-RequiredText {
  param(
    [object]$Target,
    [string]$Field,
    [string]$Value,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$UpdatedFields
  )

  $Property = $Target.PSObject.Properties[$Field]
  if ($null -eq $Property) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (Test-MissingOrPendingText -Value $Value) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  $Property.Value = $Value.Trim()
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RequiredTrue {
  param(
    [object]$Target,
    [string]$Field,
    [bool]$Confirmed,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$UpdatedFields
  )

  $Property = $Target.PSObject.Properties[$Field]
  if ($null -eq $Property) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not $Confirmed) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  $Property.Value = $true
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RequiredFalse {
  param(
    [object]$Target,
    [string]$Field,
    [bool]$ConfirmedAbsent,
    [bool]$Observed,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$FailObservations,
    [System.Collections.Generic.List[string]]$UpdatedFields
  )

  $Property = $Target.PSObject.Properties[$Field]
  if ($null -eq $Property) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if ($ConfirmedAbsent -and $Observed) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }
  if (-not $ConfirmedAbsent -and -not $Observed) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  $Property.Value = [bool]$Observed
  if ($Observed) {
    $FailObservations.Add($QualifiedField) | Out-Null
  }
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Invoke-PilotMovementGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath,
    [string]$ResolvedMovementPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $MovementGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath -StaticFitPath $ResolvedStaticFitPath -MovementPath $ResolvedMovementPath
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

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
$ResolvedMeasurementPath = Resolve-Fr017Path -Path $MeasurementPath
$ResolvedMockupPath = Resolve-Fr017Path -Path $MockupPath
$ResolvedMannequinPath = Resolve-Fr017Path -Path $MannequinPath
$ResolvedStaticFitPath = Resolve-Fr017Path -Path $StaticFitPath
$ResolvedMovementPath = Resolve-Fr017Path -Path $MovementPath
$Status = 'created_quick_release_cable_snag_record'
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$FailObservations = New-Object System.Collections.Generic.List[string]
$ChronologyViolations = New-Object System.Collections.Generic.List[string]
$UpstreamMovementStatus = ''
$UpstreamMovementReady = $false
$UpstreamMovementExitCode = 1
$UpstreamMovementParseOk = $false

if (-not (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)) {
  $Status = 'missing_template_file'
  $ExitCode = 1
} elseif ([string]::Equals($ResolvedTemplatePath, $ResolvedOutputPath, [System.StringComparison]::OrdinalIgnoreCase)) {
  $Status = 'output_path_targets_template'
  $ExitCode = 1
} elseif (Test-Path -LiteralPath $ResolvedOutputPath) {
  $Status = 'output_file_exists'
  $ExitCode = 1
} else {
  $OutputParent = Split-Path -Parent $ResolvedOutputPath
  if ([string]::IsNullOrWhiteSpace($OutputParent) -or -not (Test-Path -LiteralPath $OutputParent -PathType Container)) {
    $Status = 'missing_output_parent'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  if (-not (Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf)) {
    $Status = 'missing_measurement_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf)) {
    $Status = 'missing_mockup_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMannequinPath -PathType Leaf)) {
    $Status = 'missing_mannequin_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedStaticFitPath -PathType Leaf)) {
    $Status = 'missing_static_fit_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMovementPath -PathType Leaf)) {
    $Status = 'missing_movement_file'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $Upstream = Invoke-PilotMovementGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath
  $UpstreamMovementExitCode = [int]$Upstream.exit_code
  $UpstreamMovementParseOk = [bool]$Upstream.parse_ok
  $UpstreamMovementStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_pilot_movement_gate_parse' }
  $UpstreamMovementReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamMovementStatus -eq 'ready_for_quick_release_and_cable_snag_test_planning'

  if (-not $UpstreamMovementReady) {
    $Status = 'upstream_pilot_movement_not_ready'
    $ExitCode = 1
  }
}

$Payload = $null
if ($ExitCode -eq 0) {
  try {
    $Payload = Get-Content -LiteralPath $ResolvedTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Status = 'invalid_template_json'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  if ([string]$Payload.kind -ne 'francis.fr017.quick_release_cable_snag.v1') {
    $InvalidFields.Add('kind') | Out-Null
  }
  if ([string]$Payload.component -ne 'FR-017 Forearm Cuffs') {
    $InvalidFields.Add('component') | Out-Null
  }

  $Evidence = $Payload.evidence
  if ($null -eq $Evidence) {
    $InvalidFields.Add('evidence') | Out-Null
  } else {
    if (Test-MissingOrPendingText -Value $EvidenceDate) {
      $InvalidFields.Add('evidence.date') | Out-Null
    } elseif (-not (Test-IsoDateNotFuture -Value $EvidenceDate.Trim())) {
      $InvalidFields.Add('evidence.date') | Out-Null
    } else {
      $Evidence.date = $EvidenceDate.Trim()
      $UpdatedFields.Add('evidence.date') | Out-Null
    }
    Set-RequiredText -Target $Evidence -Field 'observer' -Value $Observer -QualifiedField 'evidence.observer' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'pilot_id' -Value $PilotId -QualifiedField 'evidence.pilot_id' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'prototype_revision' -Value $PrototypeRevision -QualifiedField 'evidence.prototype_revision' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    $Evidence.pilot_movement_record_path = $ResolvedMovementPath
    $UpdatedFields.Add('evidence.pilot_movement_record_path') | Out-Null
    if ($TestDurationMinutes -le 0) {
      $InvalidFields.Add('evidence.test_duration_minutes') | Out-Null
    } else {
      $Evidence.test_duration_minutes = $TestDurationMinutes
      $UpdatedFields.Add('evidence.test_duration_minutes') | Out-Null
    }

    $MovementPilotId = Get-EvidencePilotId -Path $ResolvedMovementPath
    if (-not (Test-MissingOrPendingText -Value $PilotId) -and -not [string]::Equals($PilotId.Trim(), $MovementPilotId.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
      $InvalidFields.Add('evidence.pilot_id_must_match_movement_pilot_id') | Out-Null
    }

    $ReleaseEvidenceDate = Get-IsoDateOrNull -Value $EvidenceDate
    $MovementEvidenceDate = Get-EvidenceDateOrNull -Path $ResolvedMovementPath
    if ($null -ne $ReleaseEvidenceDate -and $null -ne $MovementEvidenceDate -and $ReleaseEvidenceDate -lt $MovementEvidenceDate) {
      $ChronologyViolations.Add('evidence.date_before_movement.evidence.date') | Out-Null
    }
  }

  $Preconditions = $Payload.preconditions
  if ($null -eq $Preconditions) {
    $InvalidFields.Add('preconditions') | Out-Null
  } else {
    $PreconditionConfirmations = [ordered]@{
      non_powered_only = $ConfirmNonPoweredOnly.IsPresent
      no_frame_or_power_coupling = $ConfirmNoFrameOrPowerCoupling.IsPresent
      pilot_movement_gate_passed = $ConfirmPilotMovementGatePassed.IsPresent
      observer_present = $ConfirmObserverPresent.IsPresent
      emergency_release_briefed = $ConfirmEmergencyReleaseBriefed.IsPresent
      stop_on_symptoms = $ConfirmStopOnSymptoms.IsPresent
      pilot_can_self_remove_or_abort = $ConfirmPilotCanSelfRemoveOrAbort.IsPresent
    }
    foreach ($Entry in $PreconditionConfirmations.GetEnumerator()) {
      Set-RequiredTrue -Target $Preconditions -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('preconditions.{0}' -f [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    }
  }

  $SideConfirmations = [ordered]@{
    left = [ordered]@{
      release_checks = [ordered]@{
        bare_cuff_release_visible_tactile_reachable = $ConfirmLeftBareCuffReleaseVisibleTactileReachable.IsPresent
        glove_base_mockup_release_visible_tactile_reachable = $ConfirmLeftGloveBaseMockupReleaseVisibleTactileReachable.IsPresent
        wrist_assembly_mockup_release_visible_tactile_reachable = $ConfirmLeftWristAssemblyMockupReleaseVisibleTactileReachable.IsPresent
        forearm_frame_mockup_release_visible_tactile_reachable = $ConfirmLeftForearmFrameMockupReleaseVisibleTactileReachable.IsPresent
        forearm_armor_mockup_release_visible_tactile_reachable = $ConfirmLeftForearmArmorMockupReleaseVisibleTactileReachable.IsPresent
        populated_cable_sleeve_release_visible_tactile_reachable = $ConfirmLeftPopulatedCableSleeveReleaseVisibleTactileReachable.IsPresent
        post_movement_release_visible_tactile_reachable = $ConfirmLeftPostMovementReleaseVisibleTactileReachable.IsPresent
        opposite_hand_release_reachable = $ConfirmLeftOppositeHandReleaseReachable.IsPresent
        same_side_reach_recorded = $ConfirmLeftSameSideReachRecorded.IsPresent
        release_loosens_upper_strap = $ConfirmLeftReleaseLoosensUpperStrap.IsPresent
        release_loosens_lower_strap = $ConfirmLeftReleaseLoosensLowerStrap.IsPresent
        cuff_removable_without_tools = $ConfirmLeftCuffRemovableWithoutTools.IsPresent
        no_painful_wrist_posture_required = $ConfirmLeftNoPainfulWristPostureRequired.IsPresent
        glove_and_wrist_paths_not_trapped = $ConfirmLeftGloveAndWristPathsNotTrapped.IsPresent
      }
      cable_sleeve_checks = [ordered]@{
        outer_forearm_route_preserved = $ConfirmLeftOuterForearmRoutePreserved.IsPresent
        no_inner_elbow_crossing = $ConfirmLeftNoInnerElbowCrossing.IsPresent
        no_wrist_bone_crossing = $ConfirmLeftNoWristBoneCrossing.IsPresent
        no_palm_or_grip_crossing = $ConfirmLeftNoPalmOrGripCrossing.IsPresent
        no_release_handle_obstruction = $ConfirmLeftNoReleaseHandleObstruction.IsPresent
        no_snag_during_release = $ConfirmLeftNoSnagDuringRelease.IsPresent
        no_snag_after_elbow_wrist_motion = $ConfirmLeftNoSnagAfterElbowWristMotion.IsPresent
        cable_not_trapped_after_release = $ConfirmLeftCableNotTrappedAfterRelease.IsPresent
      }
      fail_absent = [ordered]@{
        release_hidden = $ConfirmNoLeftReleaseHidden.IsPresent
        release_not_found_by_touch = $ConfirmNoLeftReleaseNotFoundByTouch.IsPresent
        release_blocked_by_glove_or_armor = $ConfirmNoLeftReleaseBlockedByGloveOrArmor.IsPresent
        release_fails_to_loosen = $ConfirmNoLeftReleaseFailsToLoosen.IsPresent
        cuff_not_removable_without_tools = $ConfirmNoLeftCuffNotRemovableWithoutTools.IsPresent
        painful_wrist_posture_required = $ConfirmNoLeftPainfulWristPostureRequired.IsPresent
        cable_trapped_after_release = $ConfirmNoLeftCableTrappedAfterRelease.IsPresent
        cable_crossed_no_go_zone = $ConfirmNoLeftCableCrossedNoGoZone.IsPresent
      }
      fail_observed = [ordered]@{
        release_hidden = $LeftReleaseHiddenObserved.IsPresent
        release_not_found_by_touch = $LeftReleaseNotFoundByTouchObserved.IsPresent
        release_blocked_by_glove_or_armor = $LeftReleaseBlockedByGloveOrArmorObserved.IsPresent
        release_fails_to_loosen = $LeftReleaseFailsToLoosenObserved.IsPresent
        cuff_not_removable_without_tools = $LeftCuffNotRemovableWithoutToolsObserved.IsPresent
        painful_wrist_posture_required = $LeftPainfulWristPostureRequiredObserved.IsPresent
        cable_trapped_after_release = $LeftCableTrappedAfterReleaseObserved.IsPresent
        cable_crossed_no_go_zone = $LeftCableCrossedNoGoZoneObserved.IsPresent
      }
    }
    right = [ordered]@{
      release_checks = [ordered]@{
        bare_cuff_release_visible_tactile_reachable = $ConfirmRightBareCuffReleaseVisibleTactileReachable.IsPresent
        glove_base_mockup_release_visible_tactile_reachable = $ConfirmRightGloveBaseMockupReleaseVisibleTactileReachable.IsPresent
        wrist_assembly_mockup_release_visible_tactile_reachable = $ConfirmRightWristAssemblyMockupReleaseVisibleTactileReachable.IsPresent
        forearm_frame_mockup_release_visible_tactile_reachable = $ConfirmRightForearmFrameMockupReleaseVisibleTactileReachable.IsPresent
        forearm_armor_mockup_release_visible_tactile_reachable = $ConfirmRightForearmArmorMockupReleaseVisibleTactileReachable.IsPresent
        populated_cable_sleeve_release_visible_tactile_reachable = $ConfirmRightPopulatedCableSleeveReleaseVisibleTactileReachable.IsPresent
        post_movement_release_visible_tactile_reachable = $ConfirmRightPostMovementReleaseVisibleTactileReachable.IsPresent
        opposite_hand_release_reachable = $ConfirmRightOppositeHandReleaseReachable.IsPresent
        same_side_reach_recorded = $ConfirmRightSameSideReachRecorded.IsPresent
        release_loosens_upper_strap = $ConfirmRightReleaseLoosensUpperStrap.IsPresent
        release_loosens_lower_strap = $ConfirmRightReleaseLoosensLowerStrap.IsPresent
        cuff_removable_without_tools = $ConfirmRightCuffRemovableWithoutTools.IsPresent
        no_painful_wrist_posture_required = $ConfirmRightNoPainfulWristPostureRequired.IsPresent
        glove_and_wrist_paths_not_trapped = $ConfirmRightGloveAndWristPathsNotTrapped.IsPresent
      }
      cable_sleeve_checks = [ordered]@{
        outer_forearm_route_preserved = $ConfirmRightOuterForearmRoutePreserved.IsPresent
        no_inner_elbow_crossing = $ConfirmRightNoInnerElbowCrossing.IsPresent
        no_wrist_bone_crossing = $ConfirmRightNoWristBoneCrossing.IsPresent
        no_palm_or_grip_crossing = $ConfirmRightNoPalmOrGripCrossing.IsPresent
        no_release_handle_obstruction = $ConfirmRightNoReleaseHandleObstruction.IsPresent
        no_snag_during_release = $ConfirmRightNoSnagDuringRelease.IsPresent
        no_snag_after_elbow_wrist_motion = $ConfirmRightNoSnagAfterElbowWristMotion.IsPresent
        cable_not_trapped_after_release = $ConfirmRightCableNotTrappedAfterRelease.IsPresent
      }
      fail_absent = [ordered]@{
        release_hidden = $ConfirmNoRightReleaseHidden.IsPresent
        release_not_found_by_touch = $ConfirmNoRightReleaseNotFoundByTouch.IsPresent
        release_blocked_by_glove_or_armor = $ConfirmNoRightReleaseBlockedByGloveOrArmor.IsPresent
        release_fails_to_loosen = $ConfirmNoRightReleaseFailsToLoosen.IsPresent
        cuff_not_removable_without_tools = $ConfirmNoRightCuffNotRemovableWithoutTools.IsPresent
        painful_wrist_posture_required = $ConfirmNoRightPainfulWristPostureRequired.IsPresent
        cable_trapped_after_release = $ConfirmNoRightCableTrappedAfterRelease.IsPresent
        cable_crossed_no_go_zone = $ConfirmNoRightCableCrossedNoGoZone.IsPresent
      }
      fail_observed = [ordered]@{
        release_hidden = $RightReleaseHiddenObserved.IsPresent
        release_not_found_by_touch = $RightReleaseNotFoundByTouchObserved.IsPresent
        release_blocked_by_glove_or_armor = $RightReleaseBlockedByGloveOrArmorObserved.IsPresent
        release_fails_to_loosen = $RightReleaseFailsToLoosenObserved.IsPresent
        cuff_not_removable_without_tools = $RightCuffNotRemovableWithoutToolsObserved.IsPresent
        painful_wrist_posture_required = $RightPainfulWristPostureRequiredObserved.IsPresent
        cable_trapped_after_release = $RightCableTrappedAfterReleaseObserved.IsPresent
        cable_crossed_no_go_zone = $RightCableCrossedNoGoZoneObserved.IsPresent
      }
    }
  }

  $Sides = $Payload.sides
  if ($null -eq $Sides) {
    $InvalidFields.Add('sides') | Out-Null
  } else {
    foreach ($SideEntry in $SideConfirmations.GetEnumerator()) {
      $SideName = [string]$SideEntry.Key
      $SidePayloadProperty = $Sides.PSObject.Properties[$SideName]
      if ($null -eq $SidePayloadProperty) {
        $InvalidFields.Add('sides.' + $SideName) | Out-Null
        continue
      }

      $SidePayload = $SidePayloadProperty.Value
      foreach ($GroupName in @('release_checks', 'cable_sleeve_checks')) {
        $GroupPayload = Get-PropertyValue -Payload $SidePayload -Name $GroupName
        if ($null -eq $GroupPayload) {
          $InvalidFields.Add(('sides.{0}.{1}' -f $SideName, $GroupName)) | Out-Null
          continue
        }
        foreach ($Entry in $SideEntry.Value[$GroupName].GetEnumerator()) {
          Set-RequiredTrue -Target $GroupPayload -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('sides.{0}.{1}.{2}' -f $SideName, $GroupName, [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        }
      }

      $FailPayload = Get-PropertyValue -Payload $SidePayload -Name 'fail_observations'
      if ($null -eq $FailPayload) {
        $InvalidFields.Add(('sides.{0}.fail_observations' -f $SideName)) | Out-Null
      } else {
        foreach ($Entry in $SideEntry.Value.fail_absent.GetEnumerator()) {
          $FailField = [string]$Entry.Key
          $Observed = [bool]$SideEntry.Value.fail_observed[$FailField]
          Set-RequiredFalse -Target $FailPayload -Field $FailField -ConfirmedAbsent ([bool]$Entry.Value) -Observed $Observed -QualifiedField ('sides.{0}.fail_observations.{1}' -f $SideName, $FailField) -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
        }
      }
    }
  }

  if ($FailObservations.Count -gt 0) {
    $Status = 'release_cable_fail_observation_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $ChronologyViolations.Count -gt 0) {
    $Status = 'invalid_release_cable_record_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-release-cable-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    mannequin_path = $ResolvedMannequinPath
    static_fit_path = $ResolvedStaticFitPath
    movement_path = $ResolvedMovementPath
    output_path = $ResolvedOutputPath
    operator_supplied_release_cable_input_recorded = $true
    release_cable_record_is_stage17_completion_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    professional_engineering_review_cleared = $false
    powered_or_frame_coupled_testing_cleared = $false
    fr018_implementation_cleared = $false
    initializer_updated_fields = @($UpdatedFields.ToArray())
  }

  if ($null -eq $Payload.PSObject.Properties['record_generation']) {
    $Payload | Add-Member -NotePropertyName 'record_generation' -NotePropertyValue $Generation
  } else {
    $Payload.PSObject.Properties['record_generation'].Value = $Generation
  }

  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedOutputPath -Encoding UTF8
  $WroteFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.release_cable_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  output_path = $ResolvedOutputPath
  output_exists = (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf)
  wrote_file = $WroteFile
  read_only_contract = $false
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_pilot_movement_status = $UpstreamMovementStatus
  upstream_pilot_movement_ready = $UpstreamMovementReady
  upstream_pilot_movement_exit_code = $UpstreamMovementExitCode
  upstream_pilot_movement_parse_ok = $UpstreamMovementParseOk
  operator_supplied_release_cable_input_recorded = $WroteFile
  release_cable_record_is_stage17_completion_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  professional_engineering_review_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  fail_observations_recorded = @($FailObservations.ToArray())
  record_chronology_violations = @($ChronologyViolations.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied non-powered FR-017 quick-release/cable-snag input only after pilot movement readiness is ready. It does not certify emergency release safety, cable safety, fit, or pilot safety, does not mark physical validation complete, does not permit a Stage 17 completion claim, does not clear professional engineering review, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-quick-release-cable-snag-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedStaticFitPath, $ResolvedMovementPath, $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
