[CmdletBinding()]
param(
  [ValidateSet('UpdateSide')]
  [string]$Mode = 'UpdateSide',

  [string]$MeasurementPath = '',

  [string]$Side = '',

  [double]$ForearmCircumference25mmBelowElbowCrease = [double]::NaN,

  [double]$ForearmCircumferenceMidForearm = [double]::NaN,

  [double]$ForearmCircumference40mmAboveWristCrease = [double]::NaN,

  [double]$ForearmLengthElbowCreaseToWristCrease = [double]::NaN,

  [double]$OuterForearmUsablePanelLength = [double]::NaN,

  [double]$UpperStrapAllowedBandWidth = [double]::NaN,

  [double]$LowerStrapAllowedBandWidth = [double]::NaN,

  [double]$BoneRidgeReliefLength = [double]::NaN,

  [double]$InnerForearmNoPressureZoneWidth = [double]::NaN,

  [double]$WristClearanceGap = [double]::NaN,

  [switch]$ConfirmSecondPassCompleted,

  [double]$MaxDeltaMm = [double]::NaN,

  [switch]$ConfirmAllRequiredMeasurementsWithin5mm,

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

function Test-MissingOrPendingValue {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  if ($Value -is [string]) {
    $Text = ([string]$Value).Trim()
    return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
  }
  return $false
}

function Test-FinitePositiveNumber {
  param([double]$Value)

  return -not [double]::IsNaN($Value) -and -not [double]::IsInfinity($Value) -and $Value -gt 0
}

function Set-MeasurementNumber {
  param(
    [object]$Target,
    [string]$Field,
    [double]$Value,
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

  if (-not (Test-FinitePositiveNumber -Value $Value)) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $Value
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RepeatabilityBoolean {
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

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $true
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RepeatabilityDelta {
  param(
    [object]$Target,
    [double]$Value,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$OverwriteBlockedFields,
    [System.Collections.Generic.List[string]]$OverwrittenFields,
    [System.Collections.Generic.List[string]]$UpdatedFields,
    [bool]$AllowOverwrite
  )

  $Property = $Target.PSObject.Properties['max_delta_mm']
  if ($null -eq $Property) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if ([double]::IsNaN($Value) -or [double]::IsInfinity($Value) -or $Value -lt 0 -or $Value -gt 5) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $Value
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

$Status = 'updated_measurement_side_pass'
$ExitCode = 0
$WroteFile = $false
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$OverwriteBlockedFields = New-Object System.Collections.Generic.List[string]
$OverwrittenFields = New-Object System.Collections.Generic.List[string]
$ResolvedMeasurementPath = ''
$Payload = $null

if ([string]::IsNullOrWhiteSpace($MeasurementPath)) {
  $InvalidFields.Add('measurement_path') | Out-Null
  $Status = 'invalid_measurement_update_input'
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
  if (-not [string]::Equals($Side, 'left', [System.StringComparison]::OrdinalIgnoreCase) -and -not [string]::Equals($Side, 'right', [System.StringComparison]::OrdinalIgnoreCase)) {
    $InvalidFields.Add('side') | Out-Null
    $Status = 'invalid_measurement_update_input'
    $ExitCode = 1
  } else {
    $Side = $Side.ToLowerInvariant()
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

  $Sides = $Payload.sides
  $Repeatability = $Payload.repeatability
  $SideMeasurements = if ($null -eq $Sides) { $null } else { $Sides.PSObject.Properties[$Side].Value }
  $SideRepeatability = if ($null -eq $Repeatability) { $null } else { $Repeatability.PSObject.Properties[$Side].Value }
  if ($null -eq $SideMeasurements) {
    $InvalidFields.Add(('sides.{0}' -f $Side)) | Out-Null
  }
  if ($null -eq $SideRepeatability) {
    $InvalidFields.Add(('repeatability.{0}' -f $Side)) | Out-Null
  }

  if ($InvalidFields.Count -eq 0) {
    $Inputs = [ordered]@{
      forearm_circumference_25mm_below_elbow_crease = $ForearmCircumference25mmBelowElbowCrease
      forearm_circumference_mid_forearm = $ForearmCircumferenceMidForearm
      forearm_circumference_40mm_above_wrist_crease = $ForearmCircumference40mmAboveWristCrease
      forearm_length_elbow_crease_to_wrist_crease = $ForearmLengthElbowCreaseToWristCrease
      outer_forearm_usable_panel_length = $OuterForearmUsablePanelLength
      upper_strap_allowed_band_width = $UpperStrapAllowedBandWidth
      lower_strap_allowed_band_width = $LowerStrapAllowedBandWidth
      bone_ridge_relief_length = $BoneRidgeReliefLength
      inner_forearm_no_pressure_zone_width = $InnerForearmNoPressureZoneWidth
      wrist_clearance_gap = $WristClearanceGap
    }

    foreach ($Entry in $Inputs.GetEnumerator()) {
      Set-MeasurementNumber -Target $SideMeasurements -Field $Entry.Key -Value ([double]$Entry.Value) -QualifiedField ('sides.{0}.{1}' -f $Side, $Entry.Key) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    }

    Set-RepeatabilityBoolean -Target $SideRepeatability -Field 'second_pass_completed' -Confirmed $ConfirmSecondPassCompleted.IsPresent -QualifiedField ('repeatability.{0}.second_pass_completed' -f $Side) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RepeatabilityDelta -Target $SideRepeatability -Value $MaxDeltaMm -QualifiedField ('repeatability.{0}.max_delta_mm' -f $Side) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RepeatabilityBoolean -Target $SideRepeatability -Field 'all_required_measurements_within_5mm' -Confirmed $ConfirmAllRequiredMeasurementsWithin5mm.IsPresent -QualifiedField ('repeatability.{0}.all_required_measurements_within_5mm' -f $Side) -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  }

  if ($OverwriteBlockedFields.Count -gt 0) {
    $Status = 'measurement_fields_already_populated'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_measurement_update_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $UpdateEvent = [ordered]@{
    generated_by = 'scripts/fr017-update-measurement-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode
    side = $Side
    updated_fields = @($UpdatedFields.ToArray())
    overwritten_fields = @($OverwrittenFields.ToArray())
    side_update_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    fr018_implementation_cleared = $false
  }

  if ($null -eq $Payload.PSObject.Properties['measurement_update_events']) {
    $Payload | Add-Member -NotePropertyName 'measurement_update_events' -NotePropertyValue @($UpdateEvent)
  } else {
    $Payload.PSObject.Properties['measurement_update_events'].Value = @(@($Payload.measurement_update_events) + $UpdateEvent)
  }

  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedMeasurementPath -Encoding UTF8
  $WroteFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.measurement_record_update'
  mode = $Mode
  status = $Status
  measurement_path = $ResolvedMeasurementPath
  side = $Side
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)) { $false } else { Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf }
  wrote_file = $WroteFile
  read_only_contract = $false
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedMeasurementPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  operator_supplied_measurement_input_recorded = $WroteFile
  side_update_is_physical_validation_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  no_fake_validation_lock = 'This updater records operator-supplied side-specific numeric measurement inputs in an existing FR-017 working record only. It does not mark the measurement intake gate ready by itself, does not mark physical validation complete, does not permit a Stage 17 completion claim, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  overwrite_blocked_fields = @($OverwriteBlockedFields.ToArray())
  overwritten_fields = @($OverwrittenFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedMeasurementPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
