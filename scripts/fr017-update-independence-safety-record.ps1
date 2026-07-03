[CmdletBinding()]
param(
  [ValidateSet('UpdateIndependenceSafety')]
  [string]$Mode = 'UpdateIndependenceSafety',

  [string]$MeasurementPath = '',

  [switch]$ConfirmLeftArmMeasuredSeparately,

  [switch]$ConfirmRightArmMeasuredSeparately,

  [switch]$ConfirmSideLabelsVerified,

  [switch]$ConfirmValuesNotCopiedBetweenSides,

  [string]$LeftMeasurementReference = '',

  [string]$RightMeasurementReference = '',

  [string]$IndependenceNotes = '',

  [switch]$ConfirmNoPain,

  [switch]$ConfirmNoTingling,

  [switch]$ConfirmNoNumbness,

  [switch]$ConfirmNoColdFingers,

  [switch]$ConfirmNoDiscoloration,

  [switch]$ConfirmNoHandWeakness,

  [switch]$ConfirmNoWristPain,

  [switch]$ConfirmNoSharpPressure,

  [switch]$ConfirmNoReducedFingerMotion,

  [switch]$ConfirmNoLossOfGripStrength,

  [switch]$PainObserved,

  [switch]$TinglingObserved,

  [switch]$NumbnessObserved,

  [switch]$ColdFingersObserved,

  [switch]$DiscolorationObserved,

  [switch]$HandWeaknessObserved,

  [switch]$WristPainObserved,

  [switch]$SharpPressureObserved,

  [switch]$ReducedFingerMotionObserved,

  [switch]$LossOfGripStrengthObserved,

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

function Set-RequiredTrue {
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

function Set-SafetyScreenValue {
  param(
    [object]$Target,
    [string]$Field,
    [bool]$ConfirmAbsent,
    [bool]$Observed,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$SafetyBlockers,
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

  if ($ConfirmAbsent -and $Observed) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }
  if (-not $ConfirmAbsent -and -not $Observed) {
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

  $Property.Value = [bool]$Observed
  if ($Observed) {
    $SafetyBlockers.Add($Field) | Out-Null
  }
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

$Status = 'updated_measurement_independence_safety'
$ExitCode = 0
$WroteFile = $false
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$SafetyBlockers = New-Object System.Collections.Generic.List[string]
$OverwriteBlockedFields = New-Object System.Collections.Generic.List[string]
$OverwrittenFields = New-Object System.Collections.Generic.List[string]
$ResolvedMeasurementPath = ''
$Payload = $null

if ([string]::IsNullOrWhiteSpace($MeasurementPath)) {
  $InvalidFields.Add('measurement_path') | Out-Null
  $Status = 'invalid_independence_safety_update_input'
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

  $LeftRightIndependence = $Payload.left_right_independence
  $SafetyScreen = $Payload.safety_screen
  if ($null -eq $LeftRightIndependence) {
    $InvalidFields.Add('left_right_independence') | Out-Null
  }
  if ($null -eq $SafetyScreen) {
    $InvalidFields.Add('safety_screen') | Out-Null
  }

  if ($InvalidFields.Count -eq 0) {
    Set-RequiredTrue -Target $LeftRightIndependence -Field 'left_arm_measured_separately' -Confirmed $ConfirmLeftArmMeasuredSeparately.IsPresent -QualifiedField 'left_right_independence.left_arm_measured_separately' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RequiredTrue -Target $LeftRightIndependence -Field 'right_arm_measured_separately' -Confirmed $ConfirmRightArmMeasuredSeparately.IsPresent -QualifiedField 'left_right_independence.right_arm_measured_separately' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RequiredTrue -Target $LeftRightIndependence -Field 'side_labels_verified' -Confirmed $ConfirmSideLabelsVerified.IsPresent -QualifiedField 'left_right_independence.side_labels_verified' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RequiredTrue -Target $LeftRightIndependence -Field 'values_not_copied_between_sides' -Confirmed $ConfirmValuesNotCopiedBetweenSides.IsPresent -QualifiedField 'left_right_independence.values_not_copied_between_sides' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent

    Set-RequiredText -Target $LeftRightIndependence -Field 'left_measurement_reference' -Value $LeftMeasurementReference -QualifiedField 'left_right_independence.left_measurement_reference' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RequiredText -Target $LeftRightIndependence -Field 'right_measurement_reference' -Value $RightMeasurementReference -QualifiedField 'left_right_independence.right_measurement_reference' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-RequiredText -Target $LeftRightIndependence -Field 'independence_notes' -Value $IndependenceNotes -QualifiedField 'left_right_independence.independence_notes' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent

    if (-not (Test-MissingOrPendingText -Value $LeftMeasurementReference) -and -not (Test-MissingOrPendingText -Value $RightMeasurementReference) -and [string]::Equals($LeftMeasurementReference.Trim(), $RightMeasurementReference.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
      $InvalidFields.Add('left_right_independence.measurement_reference') | Out-Null
    }

    Set-SafetyScreenValue -Target $SafetyScreen -Field 'pain' -ConfirmAbsent $ConfirmNoPain.IsPresent -Observed $PainObserved.IsPresent -QualifiedField 'safety_screen.pain' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'tingling' -ConfirmAbsent $ConfirmNoTingling.IsPresent -Observed $TinglingObserved.IsPresent -QualifiedField 'safety_screen.tingling' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'numbness' -ConfirmAbsent $ConfirmNoNumbness.IsPresent -Observed $NumbnessObserved.IsPresent -QualifiedField 'safety_screen.numbness' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'cold_fingers' -ConfirmAbsent $ConfirmNoColdFingers.IsPresent -Observed $ColdFingersObserved.IsPresent -QualifiedField 'safety_screen.cold_fingers' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'discoloration' -ConfirmAbsent $ConfirmNoDiscoloration.IsPresent -Observed $DiscolorationObserved.IsPresent -QualifiedField 'safety_screen.discoloration' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'hand_weakness' -ConfirmAbsent $ConfirmNoHandWeakness.IsPresent -Observed $HandWeaknessObserved.IsPresent -QualifiedField 'safety_screen.hand_weakness' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'wrist_pain' -ConfirmAbsent $ConfirmNoWristPain.IsPresent -Observed $WristPainObserved.IsPresent -QualifiedField 'safety_screen.wrist_pain' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'sharp_pressure' -ConfirmAbsent $ConfirmNoSharpPressure.IsPresent -Observed $SharpPressureObserved.IsPresent -QualifiedField 'safety_screen.sharp_pressure' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'reduced_finger_motion' -ConfirmAbsent $ConfirmNoReducedFingerMotion.IsPresent -Observed $ReducedFingerMotionObserved.IsPresent -QualifiedField 'safety_screen.reduced_finger_motion' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
    Set-SafetyScreenValue -Target $SafetyScreen -Field 'loss_of_grip_strength' -ConfirmAbsent $ConfirmNoLossOfGripStrength.IsPresent -Observed $LossOfGripStrengthObserved.IsPresent -QualifiedField 'safety_screen.loss_of_grip_strength' -InvalidFields $InvalidFields -SafetyBlockers $SafetyBlockers -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  }

  if ($SafetyBlockers.Count -gt 0) {
    $Status = 'safety_symptom_recorded_requires_review'
    $ExitCode = 1
  } elseif ($OverwriteBlockedFields.Count -gt 0) {
    $Status = 'independence_safety_fields_already_populated'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_independence_safety_update_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $UpdateEvent = [ordered]@{
    generated_by = 'scripts/fr017-update-independence-safety-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode
    updated_fields = @($UpdatedFields.ToArray())
    overwritten_fields = @($OverwrittenFields.ToArray())
    independence_safety_update_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    fr018_implementation_cleared = $false
  }

  if ($null -eq $Payload.PSObject.Properties['independence_safety_update_events']) {
    $Payload | Add-Member -NotePropertyName 'independence_safety_update_events' -NotePropertyValue @($UpdateEvent)
  } else {
    $Payload.PSObject.Properties['independence_safety_update_events'].Value = @(@($Payload.independence_safety_update_events) + $UpdateEvent)
  }

  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedMeasurementPath -Encoding UTF8
  $WroteFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.independence_safety_record_update'
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
  operator_supplied_independence_safety_input_recorded = $WroteFile
  independence_safety_update_is_physical_validation_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  safety_symptoms_recorded = @($SafetyBlockers.ToArray())
  no_fake_validation_lock = 'This updater records operator-supplied left/right independence confirmations and safety-screen values in an existing FR-017 working record only. It does not mark physical validation complete, does not permit a Stage 17 completion claim, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  overwrite_blocked_fields = @($OverwriteBlockedFields.ToArray())
  overwritten_fields = @($OverwrittenFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedMeasurementPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
