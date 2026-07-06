[CmdletBinding()]
param(
  [ValidateSet('UpdateLandmarks')]
  [string]$Mode = 'UpdateLandmarks',

  [string]$MeasurementPath = '',

  [string]$LeftInnerElbowCreaseBoundary = '',

  [string]$LeftWristBoneBoundary = '',

  [string]$LeftRadiusRidgeRelief = '',

  [string]$LeftUlnaRidgeRelief = '',

  [string]$LeftOuterForearmCableRoute = '',

  [string]$LeftQuickReleaseReachZone = '',

  [string]$LeftGloveRemovalPath = '',

  [string]$RightInnerElbowCreaseBoundary = '',

  [string]$RightWristBoneBoundary = '',

  [string]$RightRadiusRidgeRelief = '',

  [string]$RightUlnaRidgeRelief = '',

  [string]$RightOuterForearmCableRoute = '',

  [string]$RightQuickReleaseReachZone = '',

  [string]$RightGloveRemovalPath = '',

  [switch]$ConfirmInnerElbowCreaseBoundary,

  [switch]$ConfirmWristBoneBoundary,

  [switch]$ConfirmRadiusUlnaReliefPaths,

  [switch]$ConfirmOuterForearmCableRoute,

  [switch]$ConfirmQuickReleaseReachZone,

  [switch]$ConfirmGloveRemovalPath,

  [switch]$ConfirmSkinSafeMarkingUsed,

  [string]$LandmarkNotes = '',

  [switch]$AllowOverwrite
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'

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

function Set-RequiredText {
  param(
    [object]$Target,
    [string]$Field,
    [string]$Value,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$OverwriteBlockedFields,
    [System.Collections.Generic.List[string]]$OverwrittenFields,
    [System.Collections.Generic.List[string]]$UpdatedFields,
    [bool]$AllowOverwrite
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

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingText -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingText -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $Value.Trim()
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RequiredConfirmation {
  param(
    [object]$Target,
    [string]$Field,
    [bool]$Confirmed,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$OverwriteBlockedFields,
    [System.Collections.Generic.List[string]]$OverwrittenFields,
    [System.Collections.Generic.List[string]]$UpdatedFields,
    [bool]$AllowOverwrite
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

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingText -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingText -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $true
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Add-CopiedReferenceCheck {
  param(
    [System.Collections.Generic.List[string]]$ReferenceBlockers,
    [string]$Field,
    [string]$LeftValue,
    [string]$RightValue
  )

  if ((Test-MissingOrPendingText -Value $LeftValue) -or (Test-MissingOrPendingText -Value $RightValue)) {
    return
  }

  if ([string]::Equals($LeftValue.Trim(), $RightValue.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
    $ReferenceBlockers.Add(('marked_zones.{0}_left_right_references_must_be_distinct' -f $Field)) | Out-Null
  }
}

$Status = 'updated_measurement_landmarks'
$ExitCode = 0
$WroteFile = $false
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$OverwriteBlockedFields = New-Object System.Collections.Generic.List[string]
$OverwrittenFields = New-Object System.Collections.Generic.List[string]
$ReferenceBlockers = New-Object System.Collections.Generic.List[string]
$ResolvedMeasurementPath = ''
$Payload = $null

if ([string]::IsNullOrWhiteSpace($MeasurementPath)) {
  $InvalidFields.Add('measurement_path') | Out-Null
  $Status = 'invalid_landmark_update_input'
  $ExitCode = 1
} else {
  $ResolvedMeasurementPath = Resolve-Fr017Path -Path $MeasurementPath
}

if ($ExitCode -eq 0) {
  if ([string]::Equals($ResolvedMeasurementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)) {
    $Status = 'measurement_path_targets_template'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf)) {
    $Status = 'missing_measurement_file'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  try {
    $Payload = Get-Content -LiteralPath $ResolvedMeasurementPath -Raw | ConvertFrom-Json -ErrorAction Stop
  } catch {
    $Status = 'invalid_measurement_json'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  if ([string]$Payload.kind -ne 'francis.fr017.measurements.v1') {
    $InvalidFields.Add('kind') | Out-Null
  }
  if ([string]$Payload.component -ne 'FR-017 Forearm Cuffs') {
    $InvalidFields.Add('component') | Out-Null
  }
  if ([string]$Payload.units -ne 'mm') {
    $InvalidFields.Add('units') | Out-Null
  }

  $MarkedZones = $Payload.marked_zones
  $LandmarkConfirmation = $Payload.landmark_confirmation
  $LeftZonesProperty = if ($null -eq $MarkedZones) { $null } else { $MarkedZones.PSObject.Properties['left'] }
  $RightZonesProperty = if ($null -eq $MarkedZones) { $null } else { $MarkedZones.PSObject.Properties['right'] }
  $LeftZones = if ($null -eq $LeftZonesProperty) { $null } else { $LeftZonesProperty.Value }
  $RightZones = if ($null -eq $RightZonesProperty) { $null } else { $RightZonesProperty.Value }

  if ($null -eq $LeftZones) {
    $InvalidFields.Add('marked_zones.left') | Out-Null
  }
  if ($null -eq $RightZones) {
    $InvalidFields.Add('marked_zones.right') | Out-Null
  }
  if ($null -eq $LandmarkConfirmation) {
    $InvalidFields.Add('landmark_confirmation') | Out-Null
  }

  if ($InvalidFields.Count -eq 0) {
    $ZoneInputs = [ordered]@{
      inner_elbow_crease_boundary = [ordered]@{ left = $LeftInnerElbowCreaseBoundary; right = $RightInnerElbowCreaseBoundary }
      wrist_bone_boundary = [ordered]@{ left = $LeftWristBoneBoundary; right = $RightWristBoneBoundary }
      radius_ridge_relief = [ordered]@{ left = $LeftRadiusRidgeRelief; right = $RightRadiusRidgeRelief }
      ulna_ridge_relief = [ordered]@{ left = $LeftUlnaRidgeRelief; right = $RightUlnaRidgeRelief }
      outer_forearm_cable_route = [ordered]@{ left = $LeftOuterForearmCableRoute; right = $RightOuterForearmCableRoute }
      quick_release_reach_zone = [ordered]@{ left = $LeftQuickReleaseReachZone; right = $RightQuickReleaseReachZone }
      glove_removal_path = [ordered]@{ left = $LeftGloveRemovalPath; right = $RightGloveRemovalPath }
    }

    foreach ($Entry in $ZoneInputs.GetEnumerator()) {
      $Field = [string]$Entry.Key
      $LeftValue = [string]$Entry.Value.left
      $RightValue = [string]$Entry.Value.right
      Add-CopiedReferenceCheck -ReferenceBlockers $ReferenceBlockers -Field $Field -LeftValue $LeftValue -RightValue $RightValue
      Set-RequiredText -Target $LeftZones -Field $Field -Value $LeftValue -QualifiedField ('marked_zones.left.{0}' -f $Field) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
      Set-RequiredText -Target $RightZones -Field $Field -Value $RightValue -QualifiedField ('marked_zones.right.{0}' -f $Field) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    }

    $Confirmations = [ordered]@{
      inner_elbow_crease_boundary_confirmed = $ConfirmInnerElbowCreaseBoundary.IsPresent
      wrist_bone_boundary_confirmed = $ConfirmWristBoneBoundary.IsPresent
      radius_ulna_relief_paths_confirmed = $ConfirmRadiusUlnaReliefPaths.IsPresent
      outer_forearm_cable_route_confirmed = $ConfirmOuterForearmCableRoute.IsPresent
      quick_release_reach_zone_confirmed = $ConfirmQuickReleaseReachZone.IsPresent
      glove_removal_path_confirmed = $ConfirmGloveRemovalPath.IsPresent
      skin_safe_marking_used = $ConfirmSkinSafeMarkingUsed.IsPresent
    }

    foreach ($Entry in $Confirmations.GetEnumerator()) {
      Set-RequiredConfirmation -Target $LandmarkConfirmation -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('landmark_confirmation.{0}' -f $Entry.Key) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    }

    Set-RequiredText -Target $LandmarkConfirmation -Field 'landmark_notes' -Value $LandmarkNotes -QualifiedField 'landmark_confirmation.landmark_notes' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  }

  if ($ReferenceBlockers.Count -gt 0) {
    $Status = 'copied_left_right_landmark_reference'
    $ExitCode = 1
  } elseif ($OverwriteBlockedFields.Count -gt 0) {
    $Status = 'landmark_fields_already_populated'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_landmark_update_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $UpdateEvent = [ordered]@{
    generated_by = 'scripts/fr017-update-landmark-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode
    updated_fields = @($UpdatedFields.ToArray())
    overwritten_fields = @($OverwrittenFields.ToArray())
    landmark_update_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    fr018_implementation_cleared = $false
  }

  if ($null -eq $Payload.PSObject.Properties['landmark_update_events']) {
    $Payload | Add-Member -NotePropertyName 'landmark_update_events' -NotePropertyValue @($UpdateEvent)
  } else {
    $Payload.PSObject.Properties['landmark_update_events'].Value = @(@($Payload.landmark_update_events) + $UpdateEvent)
  }

  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedMeasurementPath -Encoding UTF8
  $WroteFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.landmark_record_update'
  mode = $Mode
  status = $Status
  measurement_path = $ResolvedMeasurementPath
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)) { $false } else { Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf }
  wrote_file = $WroteFile
  read_only_contract = $false
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedMeasurementPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  operator_supplied_landmark_input_recorded = $WroteFile
  landmark_update_is_physical_validation_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  no_fake_validation_lock = 'This updater records operator-supplied marked-zone references and landmark confirmations in an existing FR-017 working record only. It does not mark the measurement intake gate ready by itself, does not mark physical validation complete, does not permit a Stage 17 completion claim, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  reference_blockers = @($ReferenceBlockers.ToArray())
  overwrite_blocked_fields = @($OverwriteBlockedFields.ToArray())
  overwritten_fields = @($OverwrittenFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedMeasurementPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
