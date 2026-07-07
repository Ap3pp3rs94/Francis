[CmdletBinding()]
param(
  [ValidateSet('Status', 'Create')]
  [string]$Mode = 'Status',

  [string]$OutputPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Observer = '',

  [string]$PilotId = '',

  [string]$PrototypeRevision = '',

  [double]$TestDurationMinutes = 0,

  [switch]$ConfirmNonPoweredOnly,

  [switch]$ConfirmNoFrameOrPowerCoupling,

  [switch]$ConfirmPilotStaticFitGatePassed,

  [switch]$ConfirmObserverPresent,

  [switch]$ConfirmEmergencyReleaseBriefed,

  [switch]$ConfirmStopOnSymptoms,

  [switch]$ConfirmPilotCanSelfRemoveOrAbort,

  [switch]$ConfirmLeftElbowFlexionNoCreaseCompression,

  [switch]$ConfirmLeftElbowExtensionNoCuffMigration,

  [switch]$ConfirmLeftWristFlexionNoDistalEdgePressure,

  [switch]$ConfirmLeftWristExtensionNoDistalEdgePressure,

  [switch]$ConfirmLeftWristLateralNoStrapOrCableInterference,

  [switch]$ConfirmLeftHandOpeningFull,

  [switch]$ConfirmLeftGripFormationClear,

  [switch]$ConfirmLeftGloveRemovalNotTrapped,

  [switch]$ConfirmLeftWristAssemblyRemovalNotBlocked,

  [switch]$ConfirmLeftOuterCableRouteNoSnag,

  [switch]$ConfirmLeftQuickReleaseReachableDuringMotion,

  [switch]$ConfirmLeftCuffReturnsToSafePositionAfterMotion,

  [switch]$ConfirmRightElbowFlexionNoCreaseCompression,

  [switch]$ConfirmRightElbowExtensionNoCuffMigration,

  [switch]$ConfirmRightWristFlexionNoDistalEdgePressure,

  [switch]$ConfirmRightWristExtensionNoDistalEdgePressure,

  [switch]$ConfirmRightWristLateralNoStrapOrCableInterference,

  [switch]$ConfirmRightHandOpeningFull,

  [switch]$ConfirmRightGripFormationClear,

  [switch]$ConfirmRightGloveRemovalNotTrapped,

  [switch]$ConfirmRightWristAssemblyRemovalNotBlocked,

  [switch]$ConfirmRightOuterCableRouteNoSnag,

  [switch]$ConfirmRightQuickReleaseReachableDuringMotion,

  [switch]$ConfirmRightCuffReturnsToSafePositionAfterMotion,

  [switch]$ConfirmLeftFingersWarmAfterMotion,

  [switch]$ConfirmLeftNormalColorAfterMotion,

  [switch]$ConfirmLeftGripStrengthUnchanged,

  [switch]$ConfirmLeftNoNewPressureMarks,

  [switch]$ConfirmRightFingersWarmAfterMotion,

  [switch]$ConfirmRightNormalColorAfterMotion,

  [switch]$ConfirmRightGripStrengthUnchanged,

  [switch]$ConfirmRightNoNewPressureMarks,

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
$StaticFitGateScript = Join-Path $PSScriptRoot 'fr017-pilot-static-fit-gate.ps1'

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

function Invoke-StaticFitGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $StaticFitGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath -StaticFitPath $ResolvedStaticFitPath
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

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) { '' } else { Resolve-Fr017Path -Path $OutputPath }
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { '' } else { Resolve-Fr017Path -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { '' } else { Resolve-Fr017Path -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { '' } else { Resolve-Fr017Path -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { '' } else { Resolve-Fr017Path -Path $StaticFitPath }
$CreateCommandTemplate = '.\scripts\fr017-new-pilot-movement-record.ps1 -Mode Create -OutputPath <pilot-movement-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -EvidenceDate YYYY-MM-DD -Observer "<observer>" -PilotId "<pilot id>" -PrototypeRevision "<prototype revision>" -TestDurationMinutes <minutes> -ConfirmNonPoweredOnly -ConfirmNoFrameOrPowerCoupling -ConfirmPilotStaticFitGatePassed -ConfirmObserverPresent -ConfirmEmergencyReleaseBriefed -ConfirmStopOnSymptoms -ConfirmPilotCanSelfRemoveOrAbort -ConfirmLeftElbowFlexionNoCreaseCompression -ConfirmLeftElbowExtensionNoCuffMigration -ConfirmLeftWristFlexionNoDistalEdgePressure -ConfirmLeftWristExtensionNoDistalEdgePressure -ConfirmLeftWristLateralNoStrapOrCableInterference -ConfirmLeftHandOpeningFull -ConfirmLeftGripFormationClear -ConfirmLeftGloveRemovalNotTrapped -ConfirmLeftWristAssemblyRemovalNotBlocked -ConfirmLeftOuterCableRouteNoSnag -ConfirmLeftQuickReleaseReachableDuringMotion -ConfirmLeftCuffReturnsToSafePositionAfterMotion -ConfirmRightElbowFlexionNoCreaseCompression -ConfirmRightElbowExtensionNoCuffMigration -ConfirmRightWristFlexionNoDistalEdgePressure -ConfirmRightWristExtensionNoDistalEdgePressure -ConfirmRightWristLateralNoStrapOrCableInterference -ConfirmRightHandOpeningFull -ConfirmRightGripFormationClear -ConfirmRightGloveRemovalNotTrapped -ConfirmRightWristAssemblyRemovalNotBlocked -ConfirmRightOuterCableRouteNoSnag -ConfirmRightQuickReleaseReachableDuringMotion -ConfirmRightCuffReturnsToSafePositionAfterMotion -ConfirmLeftFingersWarmAfterMotion -ConfirmLeftNormalColorAfterMotion -ConfirmLeftGripStrengthUnchanged -ConfirmLeftNoNewPressureMarks -ConfirmRightFingersWarmAfterMotion -ConfirmRightNormalColorAfterMotion -ConfirmRightGripStrengthUnchanged -ConfirmRightNoNewPressureMarks -ConfirmNoLeftPain -ConfirmNoLeftTingling -ConfirmNoLeftNumbness -ConfirmNoLeftColdFingers -ConfirmNoLeftDiscoloration -ConfirmNoLeftHandWeakness -ConfirmNoLeftWristPain -ConfirmNoLeftSharpPressure -ConfirmNoLeftReducedFingerMotion -ConfirmNoLeftLossOfGripStrength -ConfirmNoRightPain -ConfirmNoRightTingling -ConfirmNoRightNumbness -ConfirmNoRightColdFingers -ConfirmNoRightDiscoloration -ConfirmNoRightHandWeakness -ConfirmNoRightWristPain -ConfirmNoRightSharpPressure -ConfirmNoRightReducedFingerMotion -ConfirmNoRightLossOfGripStrength'
$PilotMovementStatusCommandTemplate = '.\scripts\fr017-pilot-movement-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json>'
$Status = if ($Mode -eq 'Status') { 'pilot_movement_record_initializer_status' } else { 'created_pilot_movement_record' }
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$SymptomObservations = New-Object System.Collections.Generic.List[string]
$ChronologyViolations = New-Object System.Collections.Generic.List[string]
$TemplateParseOk = $false
$OutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedOutputPath)
$MeasurementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)
$MockupPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMockupPath)
$MannequinPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMannequinPath)
$StaticFitPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath)
$OutputPathTargetsTemplate = $false
$OutputFileExists = $false
$OutputParentExists = $false
$CandidateOutputPathReady = $false
$MeasurementPathTargetsMovementTemplate = $false
$MockupPathTargetsMovementTemplate = $false
$MannequinPathTargetsMovementTemplate = $false
$StaticFitPathTargetsMovementTemplate = $false
$MeasurementFileExists = $false
$MockupFileExists = $false
$MannequinFileExists = $false
$StaticFitFileExists = $false
$UpstreamStaticFitStatus = ''
$UpstreamStaticFitReady = $false
$UpstreamStaticFitExitCode = 0
$UpstreamStaticFitParseOk = $false

if (-not (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)) {
  $Status = 'missing_template_file'
  $ExitCode = 1
} else {
  if (-not [string]::IsNullOrWhiteSpace($ResolvedOutputPath)) {
    $OutputPathTargetsTemplate = [string]::Equals($ResolvedTemplatePath, $ResolvedOutputPath, [System.StringComparison]::OrdinalIgnoreCase)
    $OutputFileExists = Test-Path -LiteralPath $ResolvedOutputPath
    $OutputParent = Split-Path -Parent $ResolvedOutputPath
    $OutputParentExists = -not [string]::IsNullOrWhiteSpace($OutputParent) -and (Test-Path -LiteralPath $OutputParent -PathType Container)
    $CandidateOutputPathReady = -not $OutputPathTargetsTemplate -and -not $OutputFileExists -and $OutputParentExists
  }

  if ($Mode -eq 'Create') {
    if ($OutputPathRequiredForCreate) {
      $Status = 'missing_output_path'
      $ExitCode = 1
    } elseif ($OutputPathTargetsTemplate) {
      $Status = 'output_path_targets_template'
      $ExitCode = 1
    } elseif ($OutputFileExists) {
      $Status = 'output_file_exists'
      $ExitCode = 1
    } elseif (-not $OutputParentExists) {
      $Status = 'missing_output_parent'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($MeasurementPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_measurement_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)) {
    $MeasurementPathTargetsMovementTemplate = [string]::Equals($ResolvedMeasurementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MeasurementFileExists = Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf
    if ($MeasurementPathTargetsMovementTemplate) {
      $Status = 'measurement_path_targets_movement_template'
      $ExitCode = 1
    } elseif (-not $MeasurementFileExists) {
      $Status = 'missing_measurement_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($MockupPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_mockup_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedMockupPath)) {
    $MockupPathTargetsMovementTemplate = [string]::Equals($ResolvedMockupPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MockupFileExists = Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf
    if ($MockupPathTargetsMovementTemplate) {
      $Status = 'mockup_path_targets_movement_template'
      $ExitCode = 1
    } elseif (-not $MockupFileExists) {
      $Status = 'missing_mockup_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($MannequinPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_mannequin_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedMannequinPath)) {
    $MannequinPathTargetsMovementTemplate = [string]::Equals($ResolvedMannequinPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MannequinFileExists = Test-Path -LiteralPath $ResolvedMannequinPath -PathType Leaf
    if ($MannequinPathTargetsMovementTemplate) {
      $Status = 'mannequin_path_targets_movement_template'
      $ExitCode = 1
    } elseif (-not $MannequinFileExists) {
      $Status = 'missing_mannequin_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($StaticFitPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_static_fit_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath)) {
    $StaticFitPathTargetsMovementTemplate = [string]::Equals($ResolvedStaticFitPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $StaticFitFileExists = Test-Path -LiteralPath $ResolvedStaticFitPath -PathType Leaf
    if ($StaticFitPathTargetsMovementTemplate) {
      $Status = 'static_fit_path_targets_movement_template'
      $ExitCode = 1
    } elseif (-not $StaticFitFileExists) {
      $Status = 'missing_static_fit_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMockupPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMannequinPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath)) {
  $Upstream = Invoke-StaticFitGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath
  $UpstreamStaticFitExitCode = [int]$Upstream.exit_code
  $UpstreamStaticFitParseOk = [bool]$Upstream.parse_ok
  $UpstreamStaticFitStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_static_fit_gate_parse' }
  $UpstreamStaticFitReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStaticFitStatus -eq 'ready_for_pilot_movement_test_planning'

  if (-not $UpstreamStaticFitReady) {
    $Status = 'upstream_pilot_static_fit_not_ready'
    $ExitCode = 1
  }
}

$Payload = $null
if ((Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf) -and ($ExitCode -eq 0 -or $Mode -eq 'Status')) {
  try {
    $Payload = Get-Content -LiteralPath $ResolvedTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
    $TemplateParseOk = $true
  } catch {
    $Status = 'invalid_template_json'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  if ([string]$Payload.kind -ne 'francis.fr017.pilot_movement_fit.v1') {
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
    $Evidence.pilot_static_fit_record_path = $ResolvedStaticFitPath
    $UpdatedFields.Add('evidence.pilot_static_fit_record_path') | Out-Null
    if ($TestDurationMinutes -le 0) {
      $InvalidFields.Add('evidence.test_duration_minutes') | Out-Null
    } else {
      $Evidence.test_duration_minutes = $TestDurationMinutes
      $UpdatedFields.Add('evidence.test_duration_minutes') | Out-Null
    }

    $StaticFitPilotId = Get-EvidencePilotId -Path $ResolvedStaticFitPath
    if (-not (Test-MissingOrPendingText -Value $PilotId) -and -not [string]::Equals($PilotId.Trim(), $StaticFitPilotId.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
      $InvalidFields.Add('evidence.pilot_id_must_match_static_fit_pilot_id') | Out-Null
    }

    $MovementEvidenceDate = Get-IsoDateOrNull -Value $EvidenceDate
    $StaticFitEvidenceDate = Get-EvidenceDateOrNull -Path $ResolvedStaticFitPath
    if ($null -ne $MovementEvidenceDate -and $null -ne $StaticFitEvidenceDate -and $MovementEvidenceDate -lt $StaticFitEvidenceDate) {
      $ChronologyViolations.Add('evidence.date_before_static_fit.evidence.date') | Out-Null
    }
  }

  $Preconditions = $Payload.preconditions
  if ($null -eq $Preconditions) {
    $InvalidFields.Add('preconditions') | Out-Null
  } else {
    $PreconditionConfirmations = [ordered]@{
      non_powered_only = $ConfirmNonPoweredOnly.IsPresent
      no_frame_or_power_coupling = $ConfirmNoFrameOrPowerCoupling.IsPresent
      pilot_static_fit_gate_passed = $ConfirmPilotStaticFitGatePassed.IsPresent
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
      movement_checks = [ordered]@{
        elbow_flexion_no_crease_compression = $ConfirmLeftElbowFlexionNoCreaseCompression.IsPresent
        elbow_extension_no_cuff_migration = $ConfirmLeftElbowExtensionNoCuffMigration.IsPresent
        wrist_flexion_no_distal_edge_pressure = $ConfirmLeftWristFlexionNoDistalEdgePressure.IsPresent
        wrist_extension_no_distal_edge_pressure = $ConfirmLeftWristExtensionNoDistalEdgePressure.IsPresent
        wrist_lateral_no_strap_or_cable_interference = $ConfirmLeftWristLateralNoStrapOrCableInterference.IsPresent
        hand_opening_full = $ConfirmLeftHandOpeningFull.IsPresent
        grip_formation_clear = $ConfirmLeftGripFormationClear.IsPresent
        glove_removal_not_trapped = $ConfirmLeftGloveRemovalNotTrapped.IsPresent
        wrist_assembly_removal_not_blocked = $ConfirmLeftWristAssemblyRemovalNotBlocked.IsPresent
        outer_cable_route_no_snag = $ConfirmLeftOuterCableRouteNoSnag.IsPresent
        quick_release_reachable_during_motion = $ConfirmLeftQuickReleaseReachableDuringMotion.IsPresent
        cuff_returns_to_safe_position_after_motion = $ConfirmLeftCuffReturnsToSafePositionAfterMotion.IsPresent
      }
      post_movement = [ordered]@{
        fingers_warm_after_motion = $ConfirmLeftFingersWarmAfterMotion.IsPresent
        normal_color_after_motion = $ConfirmLeftNormalColorAfterMotion.IsPresent
        grip_strength_unchanged = $ConfirmLeftGripStrengthUnchanged.IsPresent
        no_new_pressure_marks = $ConfirmLeftNoNewPressureMarks.IsPresent
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
      movement_checks = [ordered]@{
        elbow_flexion_no_crease_compression = $ConfirmRightElbowFlexionNoCreaseCompression.IsPresent
        elbow_extension_no_cuff_migration = $ConfirmRightElbowExtensionNoCuffMigration.IsPresent
        wrist_flexion_no_distal_edge_pressure = $ConfirmRightWristFlexionNoDistalEdgePressure.IsPresent
        wrist_extension_no_distal_edge_pressure = $ConfirmRightWristExtensionNoDistalEdgePressure.IsPresent
        wrist_lateral_no_strap_or_cable_interference = $ConfirmRightWristLateralNoStrapOrCableInterference.IsPresent
        hand_opening_full = $ConfirmRightHandOpeningFull.IsPresent
        grip_formation_clear = $ConfirmRightGripFormationClear.IsPresent
        glove_removal_not_trapped = $ConfirmRightGloveRemovalNotTrapped.IsPresent
        wrist_assembly_removal_not_blocked = $ConfirmRightWristAssemblyRemovalNotBlocked.IsPresent
        outer_cable_route_no_snag = $ConfirmRightOuterCableRouteNoSnag.IsPresent
        quick_release_reachable_during_motion = $ConfirmRightQuickReleaseReachableDuringMotion.IsPresent
        cuff_returns_to_safe_position_after_motion = $ConfirmRightCuffReturnsToSafePositionAfterMotion.IsPresent
      }
      post_movement = [ordered]@{
        fingers_warm_after_motion = $ConfirmRightFingersWarmAfterMotion.IsPresent
        normal_color_after_motion = $ConfirmRightNormalColorAfterMotion.IsPresent
        grip_strength_unchanged = $ConfirmRightGripStrengthUnchanged.IsPresent
        no_new_pressure_marks = $ConfirmRightNoNewPressureMarks.IsPresent
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
      foreach ($GroupName in @('movement_checks', 'post_movement')) {
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
    $Status = 'movement_symptom_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $ChronologyViolations.Count -gt 0) {
    $Status = 'invalid_pilot_movement_record_input'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-pilot-movement-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    mannequin_path = $ResolvedMannequinPath
    static_fit_path = $ResolvedStaticFitPath
    output_path = $ResolvedOutputPath
    operator_supplied_pilot_movement_input_recorded = $true
    pilot_movement_record_is_stage17_completion_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    quick_release_and_cable_snag_testing_cleared = $false
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
  kind = 'francis.fr017.pilot_movement_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  output_path = $ResolvedOutputPath
  template_exists = (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)
  template_parse_ok = $TemplateParseOk
  output_path_required_for_create = $OutputPathRequiredForCreate
  measurement_path_required_for_create = $MeasurementPathRequiredForCreate
  mockup_path_required_for_create = $MockupPathRequiredForCreate
  mannequin_path_required_for_create = $MannequinPathRequiredForCreate
  static_fit_path_required_for_create = $StaticFitPathRequiredForCreate
  output_path_targets_template = $OutputPathTargetsTemplate
  output_parent_exists = $OutputParentExists
  candidate_output_path_ready = $CandidateOutputPathReady
  measurement_path_targets_movement_template = $MeasurementPathTargetsMovementTemplate
  mockup_path_targets_movement_template = $MockupPathTargetsMovementTemplate
  mannequin_path_targets_movement_template = $MannequinPathTargetsMovementTemplate
  static_fit_path_targets_movement_template = $StaticFitPathTargetsMovementTemplate
  measurement_file_exists = $MeasurementFileExists
  mockup_file_exists = $MockupFileExists
  mannequin_file_exists = $MannequinFileExists
  static_fit_file_exists = $StaticFitFileExists
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf) }
  wrote_file = $WroteFile
  read_only_contract = ($Mode -eq 'Status')
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_static_fit_status = $UpstreamStaticFitStatus
  upstream_static_fit_ready = $UpstreamStaticFitReady
  upstream_static_fit_exit_code = $UpstreamStaticFitExitCode
  upstream_static_fit_parse_ok = $UpstreamStaticFitParseOk
  operator_supplied_pilot_movement_input_recorded = $WroteFile
  pilot_movement_record_is_stage17_completion_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  quick_release_and_cable_snag_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  symptom_observations_recorded = @($SymptomObservations.ToArray())
  record_chronology_violations = @($ChronologyViolations.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied non-powered FR-017 pilot movement input only after pilot static-fit readiness is ready. It does not certify fit or pilot safety, does not mark physical validation complete, does not permit a Stage 17 completion claim, does not clear quick-release/cable-snag testing, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  create_command_template = $CreateCommandTemplate
  pilot_movement_status_command_template = $PilotMovementStatusCommandTemplate
  next_command = if ($WroteFile) { '.\scripts\fr017-pilot-movement-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedStaticFitPath, $ResolvedOutputPath } elseif ($Mode -eq 'Status' -and $ExitCode -eq 0) { $CreateCommandTemplate } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
