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

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Observer = '',

  [string]$PilotId = '',

  [string]$PrototypeRevision = '',

  [double]$TestDurationMinutes = 0,

  [switch]$ConfirmNonPoweredOnly,

  [switch]$ConfirmNoFrameOrPowerCoupling,

  [switch]$ConfirmObserverPresent,

  [switch]$ConfirmEmergencyReleaseBriefed,

  [switch]$ConfirmStopOnSymptoms,

  [switch]$ConfirmPilotCanSelfRemoveOrAbort,

  [switch]$ConfirmLeftFingersWarmBeforeDonning,

  [switch]$ConfirmLeftNormalColorBeforeDonning,

  [switch]$ConfirmLeftBaselineGripPresent,

  [switch]$ConfirmRightFingersWarmBeforeDonning,

  [switch]$ConfirmRightNormalColorBeforeDonning,

  [switch]$ConfirmRightBaselineGripPresent,

  [switch]$ConfirmLeftCuffBelowElbowCrease,

  [switch]$ConfirmLeftLowerCuffAboveWristBones,

  [switch]$ConfirmLeftUpperStrapBroadNonCompressive,

  [switch]$ConfirmLeftLowerStrapBroadNonCompressive,

  [switch]$ConfirmLeftInnerForearmClear,

  [switch]$ConfirmLeftBoneReliefPresent,

  [switch]$ConfirmLeftQuickReleaseVisibleTactileReachable,

  [switch]$ConfirmLeftCuffStableWithoutMigration,

  [switch]$ConfirmLeftGloveRemovalPathOpen,

  [switch]$ConfirmLeftWristAssemblyRemovalPathOpen,

  [switch]$ConfirmLeftCableRouteStaticNoSnag,

  [switch]$ConfirmRightCuffBelowElbowCrease,

  [switch]$ConfirmRightLowerCuffAboveWristBones,

  [switch]$ConfirmRightUpperStrapBroadNonCompressive,

  [switch]$ConfirmRightLowerStrapBroadNonCompressive,

  [switch]$ConfirmRightInnerForearmClear,

  [switch]$ConfirmRightBoneReliefPresent,

  [switch]$ConfirmRightQuickReleaseVisibleTactileReachable,

  [switch]$ConfirmRightCuffStableWithoutMigration,

  [switch]$ConfirmRightGloveRemovalPathOpen,

  [switch]$ConfirmRightWristAssemblyRemovalPathOpen,

  [switch]$ConfirmRightCableRouteStaticNoSnag,

  [switch]$ConfirmLeftFingersWarmAfterDoffing,

  [switch]$ConfirmLeftNormalColorAfterDoffing,

  [switch]$ConfirmLeftGripStrengthUnchanged,

  [switch]$ConfirmRightFingersWarmAfterDoffing,

  [switch]$ConfirmRightNormalColorAfterDoffing,

  [switch]$ConfirmRightGripStrengthUnchanged,

  [switch]$ConfirmNoLeftPain,

  [switch]$ConfirmNoLeftTingling,

  [switch]$ConfirmNoLeftNumbness,

  [switch]$ConfirmNoLeftColdFingers,

  [switch]$ConfirmNoLeftDiscoloration,

  [switch]$ConfirmNoLeftHandWeakness,

  [switch]$ConfirmNoLeftWristPain,

  [switch]$ConfirmNoLeftSharpPressure,

  [switch]$ConfirmNoLeftReducedFingerMotion,

  [switch]$ConfirmNoLeftLossOfGripStrength,

  [switch]$ConfirmNoRightPain,

  [switch]$ConfirmNoRightTingling,

  [switch]$ConfirmNoRightNumbness,

  [switch]$ConfirmNoRightColdFingers,

  [switch]$ConfirmNoRightDiscoloration,

  [switch]$ConfirmNoRightHandWeakness,

  [switch]$ConfirmNoRightWristPain,

  [switch]$ConfirmNoRightSharpPressure,

  [switch]$ConfirmNoRightReducedFingerMotion,

  [switch]$ConfirmNoRightLossOfGripStrength,

  [switch]$LeftPainObserved,

  [switch]$LeftTinglingObserved,

  [switch]$LeftNumbnessObserved,

  [switch]$LeftColdFingersObserved,

  [switch]$LeftDiscolorationObserved,

  [switch]$LeftHandWeaknessObserved,

  [switch]$LeftWristPainObserved,

  [switch]$LeftSharpPressureObserved,

  [switch]$LeftReducedFingerMotionObserved,

  [switch]$LeftLossOfGripStrengthObserved,

  [switch]$RightPainObserved,

  [switch]$RightTinglingObserved,

  [switch]$RightNumbnessObserved,

  [switch]$RightColdFingersObserved,

  [switch]$RightDiscolorationObserved,

  [switch]$RightHandWeaknessObserved,

  [switch]$RightWristPainObserved,

  [switch]$RightSharpPressureObserved,

  [switch]$RightReducedFingerMotionObserved,

  [switch]$RightLossOfGripStrengthObserved
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MannequinGateScript = Join-Path $PSScriptRoot 'fr017-mannequin-interface-gate.ps1'

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
    [System.Collections.Generic.List[string]]$SymptomObservations,
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
    $SymptomObservations.Add($QualifiedField) | Out-Null
  }
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Invoke-MannequinInterfaceGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $MannequinGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath
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

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
$ResolvedMeasurementPath = Resolve-Fr017Path -Path $MeasurementPath
$ResolvedMockupPath = Resolve-Fr017Path -Path $MockupPath
$ResolvedMannequinPath = Resolve-Fr017Path -Path $MannequinPath
$Status = 'created_pilot_static_fit_record'
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$SymptomObservations = New-Object System.Collections.Generic.List[string]
$ChronologyViolations = New-Object System.Collections.Generic.List[string]
$UpstreamMannequinStatus = ''
$UpstreamMannequinReady = $false
$UpstreamMannequinExitCode = 1
$UpstreamMannequinParseOk = $false

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
  }
}

if ($ExitCode -eq 0) {
  $Upstream = Invoke-MannequinInterfaceGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath
  $UpstreamMannequinExitCode = [int]$Upstream.exit_code
  $UpstreamMannequinParseOk = [bool]$Upstream.parse_ok
  $UpstreamMannequinStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_mannequin_interface_gate_parse' }
  $UpstreamMannequinReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamMannequinStatus -eq 'ready_for_pilot_static_fit_planning'

  if (-not $UpstreamMannequinReady) {
    $Status = 'upstream_mannequin_interface_not_ready'
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
  if ([string]$Payload.kind -ne 'francis.fr017.pilot_static_fit.v1') {
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
    $Evidence.measurement_record_path = $ResolvedMeasurementPath
    $Evidence.mockup_build_record_path = $ResolvedMockupPath
    $Evidence.mannequin_interface_record_path = $ResolvedMannequinPath
    $UpdatedFields.Add('evidence.measurement_record_path') | Out-Null
    $UpdatedFields.Add('evidence.mockup_build_record_path') | Out-Null
    $UpdatedFields.Add('evidence.mannequin_interface_record_path') | Out-Null
    if ($TestDurationMinutes -le 0) {
      $InvalidFields.Add('evidence.test_duration_minutes') | Out-Null
    } else {
      $Evidence.test_duration_minutes = $TestDurationMinutes
      $UpdatedFields.Add('evidence.test_duration_minutes') | Out-Null
    }

    $MeasurementPilotId = Get-EvidencePilotId -Path $ResolvedMeasurementPath
    if (-not (Test-MissingOrPendingText -Value $PilotId) -and -not [string]::Equals($PilotId.Trim(), $MeasurementPilotId.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
      $InvalidFields.Add('evidence.pilot_id_must_match_measurement_pilot_id') | Out-Null
    }

    $StaticEvidenceDate = Get-IsoDateOrNull -Value $EvidenceDate
    foreach ($UpstreamEvidence in @(
        @{ Path = $ResolvedMeasurementPath; Id = 'measurement' },
        @{ Path = $ResolvedMockupPath; Id = 'mockup' },
        @{ Path = $ResolvedMannequinPath; Id = 'mannequin' }
      )) {
      $UpstreamEvidenceDate = Get-EvidenceDateOrNull -Path ([string]$UpstreamEvidence.Path)
      if ($null -ne $StaticEvidenceDate -and $null -ne $UpstreamEvidenceDate -and $StaticEvidenceDate -lt $UpstreamEvidenceDate) {
        $ChronologyViolations.Add(('evidence.date_before_{0}.evidence.date' -f [string]$UpstreamEvidence.Id)) | Out-Null
      }
    }
  }

  $Preconditions = $Payload.preconditions
  if ($null -eq $Preconditions) {
    $InvalidFields.Add('preconditions') | Out-Null
  } else {
    $PreconditionConfirmations = [ordered]@{
      non_powered_only = $ConfirmNonPoweredOnly.IsPresent
      no_frame_or_power_coupling = $ConfirmNoFrameOrPowerCoupling.IsPresent
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
      baseline = [ordered]@{
        fingers_warm_before_donning = $ConfirmLeftFingersWarmBeforeDonning.IsPresent
        normal_color_before_donning = $ConfirmLeftNormalColorBeforeDonning.IsPresent
        baseline_grip_present = $ConfirmLeftBaselineGripPresent.IsPresent
      }
      static_checks = [ordered]@{
        cuff_below_elbow_crease = $ConfirmLeftCuffBelowElbowCrease.IsPresent
        lower_cuff_above_wrist_bones = $ConfirmLeftLowerCuffAboveWristBones.IsPresent
        upper_strap_broad_non_compressive = $ConfirmLeftUpperStrapBroadNonCompressive.IsPresent
        lower_strap_broad_non_compressive = $ConfirmLeftLowerStrapBroadNonCompressive.IsPresent
        inner_forearm_clear = $ConfirmLeftInnerForearmClear.IsPresent
        bone_relief_present = $ConfirmLeftBoneReliefPresent.IsPresent
        quick_release_visible_tactile_reachable = $ConfirmLeftQuickReleaseVisibleTactileReachable.IsPresent
        cuff_stable_without_migration = $ConfirmLeftCuffStableWithoutMigration.IsPresent
        glove_removal_path_open = $ConfirmLeftGloveRemovalPathOpen.IsPresent
        wrist_assembly_removal_path_open = $ConfirmLeftWristAssemblyRemovalPathOpen.IsPresent
        cable_route_static_no_snag = $ConfirmLeftCableRouteStaticNoSnag.IsPresent
      }
      post_doff = [ordered]@{
        fingers_warm_after_doffing = $ConfirmLeftFingersWarmAfterDoffing.IsPresent
        normal_color_after_doffing = $ConfirmLeftNormalColorAfterDoffing.IsPresent
        grip_strength_unchanged = $ConfirmLeftGripStrengthUnchanged.IsPresent
      }
      symptoms_absent = [ordered]@{
        pain = $ConfirmNoLeftPain.IsPresent
        tingling = $ConfirmNoLeftTingling.IsPresent
        numbness = $ConfirmNoLeftNumbness.IsPresent
        cold_fingers = $ConfirmNoLeftColdFingers.IsPresent
        discoloration = $ConfirmNoLeftDiscoloration.IsPresent
        hand_weakness = $ConfirmNoLeftHandWeakness.IsPresent
        wrist_pain = $ConfirmNoLeftWristPain.IsPresent
        sharp_pressure = $ConfirmNoLeftSharpPressure.IsPresent
        reduced_finger_motion = $ConfirmNoLeftReducedFingerMotion.IsPresent
        loss_of_grip_strength = $ConfirmNoLeftLossOfGripStrength.IsPresent
      }
      symptoms_observed = [ordered]@{
        pain = $LeftPainObserved.IsPresent
        tingling = $LeftTinglingObserved.IsPresent
        numbness = $LeftNumbnessObserved.IsPresent
        cold_fingers = $LeftColdFingersObserved.IsPresent
        discoloration = $LeftDiscolorationObserved.IsPresent
        hand_weakness = $LeftHandWeaknessObserved.IsPresent
        wrist_pain = $LeftWristPainObserved.IsPresent
        sharp_pressure = $LeftSharpPressureObserved.IsPresent
        reduced_finger_motion = $LeftReducedFingerMotionObserved.IsPresent
        loss_of_grip_strength = $LeftLossOfGripStrengthObserved.IsPresent
      }
    }
    right = [ordered]@{
      baseline = [ordered]@{
        fingers_warm_before_donning = $ConfirmRightFingersWarmBeforeDonning.IsPresent
        normal_color_before_donning = $ConfirmRightNormalColorBeforeDonning.IsPresent
        baseline_grip_present = $ConfirmRightBaselineGripPresent.IsPresent
      }
      static_checks = [ordered]@{
        cuff_below_elbow_crease = $ConfirmRightCuffBelowElbowCrease.IsPresent
        lower_cuff_above_wrist_bones = $ConfirmRightLowerCuffAboveWristBones.IsPresent
        upper_strap_broad_non_compressive = $ConfirmRightUpperStrapBroadNonCompressive.IsPresent
        lower_strap_broad_non_compressive = $ConfirmRightLowerStrapBroadNonCompressive.IsPresent
        inner_forearm_clear = $ConfirmRightInnerForearmClear.IsPresent
        bone_relief_present = $ConfirmRightBoneReliefPresent.IsPresent
        quick_release_visible_tactile_reachable = $ConfirmRightQuickReleaseVisibleTactileReachable.IsPresent
        cuff_stable_without_migration = $ConfirmRightCuffStableWithoutMigration.IsPresent
        glove_removal_path_open = $ConfirmRightGloveRemovalPathOpen.IsPresent
        wrist_assembly_removal_path_open = $ConfirmRightWristAssemblyRemovalPathOpen.IsPresent
        cable_route_static_no_snag = $ConfirmRightCableRouteStaticNoSnag.IsPresent
      }
      post_doff = [ordered]@{
        fingers_warm_after_doffing = $ConfirmRightFingersWarmAfterDoffing.IsPresent
        normal_color_after_doffing = $ConfirmRightNormalColorAfterDoffing.IsPresent
        grip_strength_unchanged = $ConfirmRightGripStrengthUnchanged.IsPresent
      }
      symptoms_absent = [ordered]@{
        pain = $ConfirmNoRightPain.IsPresent
        tingling = $ConfirmNoRightTingling.IsPresent
        numbness = $ConfirmNoRightNumbness.IsPresent
        cold_fingers = $ConfirmNoRightColdFingers.IsPresent
        discoloration = $ConfirmNoRightDiscoloration.IsPresent
        hand_weakness = $ConfirmNoRightHandWeakness.IsPresent
        wrist_pain = $ConfirmNoRightWristPain.IsPresent
        sharp_pressure = $ConfirmNoRightSharpPressure.IsPresent
        reduced_finger_motion = $ConfirmNoRightReducedFingerMotion.IsPresent
        loss_of_grip_strength = $ConfirmNoRightLossOfGripStrength.IsPresent
      }
      symptoms_observed = [ordered]@{
        pain = $RightPainObserved.IsPresent
        tingling = $RightTinglingObserved.IsPresent
        numbness = $RightNumbnessObserved.IsPresent
        cold_fingers = $RightColdFingersObserved.IsPresent
        discoloration = $RightDiscolorationObserved.IsPresent
        hand_weakness = $RightHandWeaknessObserved.IsPresent
        wrist_pain = $RightWristPainObserved.IsPresent
        sharp_pressure = $RightSharpPressureObserved.IsPresent
        reduced_finger_motion = $RightReducedFingerMotionObserved.IsPresent
        loss_of_grip_strength = $RightLossOfGripStrengthObserved.IsPresent
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
      foreach ($GroupName in @('baseline', 'static_checks', 'post_doff')) {
        $GroupPayload = Get-PropertyValue -Payload $SidePayload -Name $GroupName
        if ($null -eq $GroupPayload) {
          $InvalidFields.Add(('sides.{0}.{1}' -f $SideName, $GroupName)) | Out-Null
          continue
        }
        foreach ($Entry in $SideEntry.Value[$GroupName].GetEnumerator()) {
          Set-RequiredTrue -Target $GroupPayload -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('sides.{0}.{1}.{2}' -f $SideName, $GroupName, [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        }
      }

      $SymptomsPayload = Get-PropertyValue -Payload $SidePayload -Name 'symptoms'
      if ($null -eq $SymptomsPayload) {
        $InvalidFields.Add(('sides.{0}.symptoms' -f $SideName)) | Out-Null
      } else {
        foreach ($Entry in $SideEntry.Value.symptoms_absent.GetEnumerator()) {
          $SymptomField = [string]$Entry.Key
          $Observed = [bool]$SideEntry.Value.symptoms_observed[$SymptomField]
          Set-RequiredFalse -Target $SymptomsPayload -Field $SymptomField -ConfirmedAbsent ([bool]$Entry.Value) -Observed $Observed -QualifiedField ('sides.{0}.symptoms.{1}' -f $SideName, $SymptomField) -InvalidFields $InvalidFields -SymptomObservations $SymptomObservations -UpdatedFields $UpdatedFields
        }
      }
    }
  }

  if ($SymptomObservations.Count -gt 0) {
    $Status = 'static_fit_symptom_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $ChronologyViolations.Count -gt 0) {
    $Status = 'invalid_pilot_static_fit_record_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-pilot-static-fit-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    mannequin_path = $ResolvedMannequinPath
    output_path = $ResolvedOutputPath
    operator_supplied_pilot_static_fit_input_recorded = $true
    pilot_static_fit_record_is_stage17_completion_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    pilot_movement_testing_cleared = $false
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
  kind = 'francis.fr017.pilot_static_fit_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  output_path = $ResolvedOutputPath
  output_exists = (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf)
  wrote_file = $WroteFile
  read_only_contract = $false
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_mannequin_status = $UpstreamMannequinStatus
  upstream_mannequin_ready = $UpstreamMannequinReady
  upstream_mannequin_exit_code = $UpstreamMannequinExitCode
  upstream_mannequin_parse_ok = $UpstreamMannequinParseOk
  operator_supplied_pilot_static_fit_input_recorded = $WroteFile
  pilot_static_fit_record_is_stage17_completion_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  pilot_movement_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  symptom_observations_recorded = @($SymptomObservations.ToArray())
  record_chronology_violations = @($ChronologyViolations.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied non-powered FR-017 pilot static-fit input only after mannequin interface readiness is ready. It does not certify fit or pilot safety, does not mark physical validation complete, does not permit a Stage 17 completion claim, does not clear pilot movement testing, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-pilot-static-fit-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
