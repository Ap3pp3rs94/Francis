[CmdletBinding()]
param(
  [ValidateSet('Status', 'Create')]
  [string]$Mode = 'Status',

  [string]$OutputPath = '',

  [string]$FinalPhysicalGateRecordOutputPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = '',

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$DecisionReviewer = '',

  [string]$ReviewerRole = '',

  [string]$PilotId = '',

  [string]$CompletionDecisionNotes = '',

  [switch]$ConfirmHumanDecisionReviewer,
  [switch]$ConfirmRealRecordsReviewed,
  [switch]$ConfirmAllStopConditionsReviewed,
  [switch]$ConfirmNoUnresolvedSafetyFailConditions,
  [switch]$ConfirmNoPoweredTestingCleared,
  [switch]$ConfirmNoFrameCoupledTestingCleared,
  [switch]$ConfirmNoLoadBearingUseApproved,
  [switch]$ConfirmFr018ImplementationNotCleared,
  [switch]$ConfirmStage17CompletionClaimRequested,
  [switch]$ConfirmPhysicalValidationAcceptedByHumanReviewer,
  [switch]$ConfirmCompletionLedgerUpdateRequired,
  [switch]$ConfirmTemplateIsNotPhysicalValidation,
  [switch]$ConfirmRequiresRealRecords,
  [switch]$ConfirmFr018ImplementationNotClearedByLock,
  [switch]$ConfirmPoweredOrFrameCoupledTestingNotClearedByLock,

  [switch]$Fr018ImplementationCleared,
  [switch]$PoweredOrFrameCoupledTestingCleared
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FinalPhysicalGateScript = Join-Path $PSScriptRoot 'fr017-final-physical-gate.ps1'
$ExpectedFinalPhysicalStatus = 'ready_for_stage17_final_physical_completion_decision'

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

function Get-IdentityFingerprint {
  param([object]$Value)

  if ($null -eq $Value) {
    return ''
  }
  $Text = [string]$Value
  if ([string]::IsNullOrWhiteSpace($Text)) {
    return ''
  }

  $Sha256 = [System.Security.Cryptography.SHA256]::Create()
  try {
    $Bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $Hash = $Sha256.ComputeHash($Bytes)
    $Hex = -join ($Hash | ForEach-Object { $_.ToString('x2', [System.Globalization.CultureInfo]::InvariantCulture) })
    return $Hex.Substring(0, 12)
  } finally {
    $Sha256.Dispose()
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
    [System.Collections.Generic.List[string]]$BlockingFlags,
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
    $BlockingFlags.Add($QualifiedField) | Out-Null
  }
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Invoke-FinalPhysicalGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath,
    [string]$ResolvedMovementPath,
    [string]$ResolvedReleaseCablePath,
    [string]$ResolvedEngineeringReviewPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $FinalPhysicalGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath -StaticFitPath $ResolvedStaticFitPath -MovementPath $ResolvedMovementPath -ReleaseCablePath $ResolvedReleaseCablePath -EngineeringReviewPath $ResolvedEngineeringReviewPath
  $GateExitCode = $LASTEXITCODE
  $RawText = $RawOutput | Out-String
  $Payload = $null
  $ParseOk = $false
  try {
    $Payload = $RawText | ConvertFrom-Json -ErrorAction Stop
    $ParseOk = $true
  } catch {
    $Payload = $null
  }

  return [ordered]@{
    exit_code = $GateExitCode
    parse_ok = $ParseOk
    payload = $Payload
    raw_output = $RawText
  }
}

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-FINAL-PHYSICAL-DECISION-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) { '' } else { Resolve-Fr017Path -Path $OutputPath }
$ResolvedFinalPhysicalGateRecordOutputPath = if ([string]::IsNullOrWhiteSpace($FinalPhysicalGateRecordOutputPath)) { '' } else { Resolve-Fr017Path -Path $FinalPhysicalGateRecordOutputPath }
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { '' } else { Resolve-Fr017Path -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { '' } else { Resolve-Fr017Path -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { '' } else { Resolve-Fr017Path -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { '' } else { Resolve-Fr017Path -Path $StaticFitPath }
$ResolvedMovementPath = if ([string]::IsNullOrWhiteSpace($MovementPath)) { '' } else { Resolve-Fr017Path -Path $MovementPath }
$ResolvedReleaseCablePath = if ([string]::IsNullOrWhiteSpace($ReleaseCablePath)) { '' } else { Resolve-Fr017Path -Path $ReleaseCablePath }
$ResolvedEngineeringReviewPath = if ([string]::IsNullOrWhiteSpace($EngineeringReviewPath)) { '' } else { Resolve-Fr017Path -Path $EngineeringReviewPath }
$CreateCommandTemplate = '.\scripts\fr017-new-final-decision-record.ps1 -Mode Create -OutputPath <final-decision-record.json> -FinalPhysicalGateRecordOutputPath <final-physical-gate-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -EvidenceDate YYYY-MM-DD -DecisionReviewer "<human reviewer>" -ReviewerRole "<reviewer role>" -PilotId "<pilot id>" -CompletionDecisionNotes "<remaining limitations notes>" -ConfirmHumanDecisionReviewer -ConfirmRealRecordsReviewed -ConfirmAllStopConditionsReviewed -ConfirmNoUnresolvedSafetyFailConditions -ConfirmNoPoweredTestingCleared -ConfirmNoFrameCoupledTestingCleared -ConfirmNoLoadBearingUseApproved -ConfirmFr018ImplementationNotCleared -ConfirmStage17CompletionClaimRequested -ConfirmPhysicalValidationAcceptedByHumanReviewer -ConfirmCompletionLedgerUpdateRequired -ConfirmTemplateIsNotPhysicalValidation -ConfirmRequiresRealRecords -ConfirmFr018ImplementationNotClearedByLock -ConfirmPoweredOrFrameCoupledTestingNotClearedByLock'
$FinalDecisionStatusCommandTemplate = '.\scripts\fr017-final-decision-record-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json>'
$Status = if ($Mode -eq 'Status') { 'final_decision_record_initializer_status' } else { 'created_final_decision_record' }
$ExitCode = 0
$WroteDecisionFile = $false
$WroteFinalGateRecordFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$DecisionLockViolations = New-Object System.Collections.Generic.List[string]
$CompletionDecisionViolations = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$TemplateParseOk = $false
$OutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedOutputPath)
$FinalPhysicalGateRecordOutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedFinalPhysicalGateRecordOutputPath)
$MeasurementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)
$MockupPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMockupPath)
$MannequinPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMannequinPath)
$StaticFitPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath)
$MovementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMovementPath)
$ReleaseCablePathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedReleaseCablePath)
$EngineeringReviewPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedEngineeringReviewPath)
$OutputPathTargetsTemplate = $false
$FinalPhysicalGateRecordOutputPathTargetsTemplate = $false
$OutputPathConflictsWithFinalPhysicalGateRecordOutput = $false
$OutputFileExists = $false
$FinalPhysicalGateRecordOutputFileExists = $false
$OutputParentExists = $false
$FinalPhysicalGateRecordOutputParentExists = $false
$CandidateOutputPathReady = $false
$CandidateFinalPhysicalGateRecordOutputPathReady = $false
$MeasurementPathTargetsFinalDecisionTemplate = $false
$MockupPathTargetsFinalDecisionTemplate = $false
$MannequinPathTargetsFinalDecisionTemplate = $false
$StaticFitPathTargetsFinalDecisionTemplate = $false
$MovementPathTargetsFinalDecisionTemplate = $false
$ReleaseCablePathTargetsFinalDecisionTemplate = $false
$EngineeringReviewPathTargetsFinalDecisionTemplate = $false
$MeasurementFileExists = $false
$MockupFileExists = $false
$MannequinFileExists = $false
$StaticFitFileExists = $false
$MovementFileExists = $false
$ReleaseCableFileExists = $false
$EngineeringReviewFileExists = $false
$UpstreamFinalPhysicalStatus = ''
$UpstreamFinalPhysicalReady = $false
$UpstreamFinalPhysicalExitCode = 0
$UpstreamFinalPhysicalParseOk = $false
$FinalPhysicalGateReferencePilotFingerprint = ''
$FinalDecisionPilotFingerprint = ''

if (-not (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)) {
  $Status = 'missing_template_file'
  $ExitCode = 1
} else {
  if (-not [string]::IsNullOrWhiteSpace($ResolvedOutputPath)) {
    $OutputPathTargetsTemplate = [string]::Equals($ResolvedTemplatePath, $ResolvedOutputPath, [System.StringComparison]::OrdinalIgnoreCase)
    $OutputFileExists = Test-Path -LiteralPath $ResolvedOutputPath
    $OutputParent = Split-Path -Parent $ResolvedOutputPath
    $OutputParentExists = -not [string]::IsNullOrWhiteSpace($OutputParent) -and (Test-Path -LiteralPath $OutputParent -PathType Container)
  }
  if (-not [string]::IsNullOrWhiteSpace($ResolvedFinalPhysicalGateRecordOutputPath)) {
    $FinalPhysicalGateRecordOutputPathTargetsTemplate = [string]::Equals($ResolvedTemplatePath, $ResolvedFinalPhysicalGateRecordOutputPath, [System.StringComparison]::OrdinalIgnoreCase)
    $FinalPhysicalGateRecordOutputFileExists = Test-Path -LiteralPath $ResolvedFinalPhysicalGateRecordOutputPath
    $FinalPhysicalGateRecordOutputParent = Split-Path -Parent $ResolvedFinalPhysicalGateRecordOutputPath
    $FinalPhysicalGateRecordOutputParentExists = -not [string]::IsNullOrWhiteSpace($FinalPhysicalGateRecordOutputParent) -and (Test-Path -LiteralPath $FinalPhysicalGateRecordOutputParent -PathType Container)
  }
  if (-not [string]::IsNullOrWhiteSpace($ResolvedOutputPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedFinalPhysicalGateRecordOutputPath)) {
    $OutputPathConflictsWithFinalPhysicalGateRecordOutput = [string]::Equals($ResolvedOutputPath, $ResolvedFinalPhysicalGateRecordOutputPath, [System.StringComparison]::OrdinalIgnoreCase)
  }
  $CandidateOutputPathReady = -not [string]::IsNullOrWhiteSpace($ResolvedOutputPath) -and -not $OutputPathTargetsTemplate -and -not $OutputPathConflictsWithFinalPhysicalGateRecordOutput -and -not $OutputFileExists -and $OutputParentExists
  $CandidateFinalPhysicalGateRecordOutputPathReady = -not [string]::IsNullOrWhiteSpace($ResolvedFinalPhysicalGateRecordOutputPath) -and -not $FinalPhysicalGateRecordOutputPathTargetsTemplate -and -not $OutputPathConflictsWithFinalPhysicalGateRecordOutput -and -not $FinalPhysicalGateRecordOutputFileExists -and $FinalPhysicalGateRecordOutputParentExists

  if ($Mode -eq 'Create') {
    if ($OutputPathRequiredForCreate) {
      $Status = 'missing_output_path'
      $ExitCode = 1
    } elseif ($FinalPhysicalGateRecordOutputPathRequiredForCreate) {
      $Status = 'missing_final_physical_gate_record_output_path'
      $ExitCode = 1
    } elseif ($OutputPathTargetsTemplate) {
      $Status = 'output_path_targets_template'
      $ExitCode = 1
    } elseif ($OutputPathConflictsWithFinalPhysicalGateRecordOutput) {
      $Status = 'output_path_conflicts_with_final_physical_gate_record_output'
      $ExitCode = 1
    } elseif ($OutputFileExists) {
      $Status = 'output_file_exists'
      $ExitCode = 1
    } elseif ($FinalPhysicalGateRecordOutputFileExists) {
      $Status = 'final_physical_gate_record_output_file_exists'
      $ExitCode = 1
    } elseif (-not $OutputParentExists -or -not $FinalPhysicalGateRecordOutputParentExists) {
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
    $MeasurementPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedMeasurementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MeasurementFileExists = Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf
    if ($MeasurementPathTargetsFinalDecisionTemplate) {
      $Status = 'measurement_path_targets_final_decision_template'
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
    $MockupPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedMockupPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MockupFileExists = Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf
    if ($MockupPathTargetsFinalDecisionTemplate) {
      $Status = 'mockup_path_targets_final_decision_template'
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
    $MannequinPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedMannequinPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MannequinFileExists = Test-Path -LiteralPath $ResolvedMannequinPath -PathType Leaf
    if ($MannequinPathTargetsFinalDecisionTemplate) {
      $Status = 'mannequin_path_targets_final_decision_template'
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
    $StaticFitPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedStaticFitPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $StaticFitFileExists = Test-Path -LiteralPath $ResolvedStaticFitPath -PathType Leaf
    if ($StaticFitPathTargetsFinalDecisionTemplate) {
      $Status = 'static_fit_path_targets_final_decision_template'
      $ExitCode = 1
    } elseif (-not $StaticFitFileExists) {
      $Status = 'missing_static_fit_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($MovementPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_movement_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedMovementPath)) {
    $MovementPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedMovementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MovementFileExists = Test-Path -LiteralPath $ResolvedMovementPath -PathType Leaf
    if ($MovementPathTargetsFinalDecisionTemplate) {
      $Status = 'movement_path_targets_final_decision_template'
      $ExitCode = 1
    } elseif (-not $MovementFileExists) {
      $Status = 'missing_movement_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($ReleaseCablePathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_release_cable_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedReleaseCablePath)) {
    $ReleaseCablePathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedReleaseCablePath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $ReleaseCableFileExists = Test-Path -LiteralPath $ResolvedReleaseCablePath -PathType Leaf
    if ($ReleaseCablePathTargetsFinalDecisionTemplate) {
      $Status = 'release_cable_path_targets_final_decision_template'
      $ExitCode = 1
    } elseif (-not $ReleaseCableFileExists) {
      $Status = 'missing_release_cable_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0) {
  if ($EngineeringReviewPathRequiredForCreate -and $Mode -eq 'Create') {
    $Status = 'missing_engineering_review_path'
    $ExitCode = 1
  } elseif (-not [string]::IsNullOrWhiteSpace($ResolvedEngineeringReviewPath)) {
    $EngineeringReviewPathTargetsFinalDecisionTemplate = [string]::Equals($ResolvedEngineeringReviewPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $EngineeringReviewFileExists = Test-Path -LiteralPath $ResolvedEngineeringReviewPath -PathType Leaf
    if ($EngineeringReviewPathTargetsFinalDecisionTemplate) {
      $Status = 'engineering_review_path_targets_final_decision_template'
      $ExitCode = 1
    } elseif (-not $EngineeringReviewFileExists) {
      $Status = 'missing_engineering_review_file'
      $ExitCode = 1
    }
  }
}

$FinalPhysicalGate = $null
if ($ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMockupPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMannequinPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMovementPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedReleaseCablePath) -and -not [string]::IsNullOrWhiteSpace($ResolvedEngineeringReviewPath)) {
  $FinalPhysicalGate = Invoke-FinalPhysicalGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath -ResolvedReleaseCablePath $ResolvedReleaseCablePath -ResolvedEngineeringReviewPath $ResolvedEngineeringReviewPath
  $UpstreamFinalPhysicalExitCode = [int]$FinalPhysicalGate.exit_code
  $UpstreamFinalPhysicalParseOk = [bool]$FinalPhysicalGate.parse_ok
  $UpstreamFinalPhysicalStatus = if ([bool]$FinalPhysicalGate.parse_ok) { [string]$FinalPhysicalGate.payload.status } else { 'failed_final_physical_gate_parse' }
  $UpstreamFinalPhysicalReady = [bool]$FinalPhysicalGate.parse_ok -and [int]$FinalPhysicalGate.exit_code -eq 0 -and $UpstreamFinalPhysicalStatus -eq $ExpectedFinalPhysicalStatus
  $FinalPhysicalGateReferencePilotFingerprint = if ([bool]$FinalPhysicalGate.parse_ok) { [string](Get-PropertyValue -Payload $FinalPhysicalGate.payload -Name 'pilot_identity_continuity_reference_fingerprint' -Default '') } else { '' }

  if (-not $UpstreamFinalPhysicalReady) {
    $Status = 'upstream_final_physical_gate_not_ready'
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
  if ([string]$Payload.kind -ne 'francis.fr017.final_physical_decision.v1') {
    $InvalidFields.Add('kind') | Out-Null
  }
  if ([string]$Payload.component -ne 'FR-017 Forearm Cuffs') {
    $InvalidFields.Add('component') | Out-Null
  }

  if (-not $ConfirmHumanDecisionReviewer.IsPresent) {
    $InvalidFields.Add('evidence.decision_reviewer_human_confirmation') | Out-Null
  }

  $ReviewerText = ([string]$DecisionReviewer).Trim().ToLowerInvariant()
  if ($ReviewerText.Contains('codex') -or $ReviewerText.Contains('automated') -or $ReviewerText.Contains('automation')) {
    $InvalidFields.Add('evidence.decision_reviewer_must_be_human') | Out-Null
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
    Set-RequiredText -Target $Evidence -Field 'decision_reviewer' -Value $DecisionReviewer -QualifiedField 'evidence.decision_reviewer' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'reviewer_role' -Value $ReviewerRole -QualifiedField 'evidence.reviewer_role' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'pilot_id' -Value $PilotId -QualifiedField 'evidence.pilot_id' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    $Evidence.final_physical_gate_status = $ExpectedFinalPhysicalStatus
    $Evidence.final_physical_gate_record_path = $ResolvedFinalPhysicalGateRecordOutputPath
    $UpdatedFields.Add('evidence.final_physical_gate_status') | Out-Null
    $UpdatedFields.Add('evidence.final_physical_gate_record_path') | Out-Null

    if (-not (Test-MissingOrPendingText -Value $PilotId)) {
      $FinalDecisionPilotFingerprint = Get-IdentityFingerprint -Value $PilotId
      if (Test-MissingOrPendingText -Value $FinalPhysicalGateReferencePilotFingerprint) {
        $InvalidFields.Add('evidence.pilot_id.final_physical_gate_reference_missing') | Out-Null
      } elseif ($FinalDecisionPilotFingerprint -ne $FinalPhysicalGateReferencePilotFingerprint) {
        $InvalidFields.Add('evidence.pilot_id_must_match_final_physical_gate_reference') | Out-Null
      }
    }
  }

  $DecisionLocks = $Payload.decision_locks
  if ($null -eq $DecisionLocks) {
    $InvalidFields.Add('decision_locks') | Out-Null
  } else {
    $DecisionLockConfirmations = [ordered]@{
      real_records_reviewed = $ConfirmRealRecordsReviewed.IsPresent
      all_stop_conditions_reviewed = $ConfirmAllStopConditionsReviewed.IsPresent
      no_unresolved_safety_fail_conditions = $ConfirmNoUnresolvedSafetyFailConditions.IsPresent
      no_powered_testing_cleared = $ConfirmNoPoweredTestingCleared.IsPresent
      no_frame_coupled_testing_cleared = $ConfirmNoFrameCoupledTestingCleared.IsPresent
      no_load_bearing_use_approved = $ConfirmNoLoadBearingUseApproved.IsPresent
      fr018_implementation_not_cleared = $ConfirmFr018ImplementationNotCleared.IsPresent
    }
    foreach ($Entry in $DecisionLockConfirmations.GetEnumerator()) {
      Set-RequiredTrue -Target $DecisionLocks -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('decision_locks.{0}' -f [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
      if (-not [bool]$Entry.Value) {
        $DecisionLockViolations.Add(('decision_locks.{0}' -f [string]$Entry.Key)) | Out-Null
      }
    }
  }

  $CompletionDecision = $Payload.completion_decision
  if ($null -eq $CompletionDecision) {
    $InvalidFields.Add('completion_decision') | Out-Null
  } else {
    $CompletionConfirmations = [ordered]@{
      stage17_completion_claim_requested = $ConfirmStage17CompletionClaimRequested.IsPresent
      physical_validation_accepted_by_human_reviewer = $ConfirmPhysicalValidationAcceptedByHumanReviewer.IsPresent
      completion_ledger_update_required = $ConfirmCompletionLedgerUpdateRequired.IsPresent
    }
    foreach ($Entry in $CompletionConfirmations.GetEnumerator()) {
      Set-RequiredTrue -Target $CompletionDecision -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('completion_decision.{0}' -f [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
      if (-not [bool]$Entry.Value) {
        $CompletionDecisionViolations.Add(('completion_decision.{0}' -f [string]$Entry.Key)) | Out-Null
      }
    }
    Set-RequiredText -Target $CompletionDecision -Field 'completion_decision_notes' -Value $CompletionDecisionNotes -QualifiedField 'completion_decision.completion_decision_notes' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields

    if (-not (Test-MissingOrPendingText -Value $CompletionDecisionNotes)) {
      $NotesLower = $CompletionDecisionNotes.Trim().ToLowerInvariant()
      if (-not ($NotesLower.Contains('remaining') -or $NotesLower.Contains('limitation'))) {
        $InvalidFields.Add('completion_decision.completion_decision_notes') | Out-Null
      }
      foreach ($Phrase in @(
          'fr-018 cleared',
          'fr018 cleared',
          'powered testing cleared',
          'frame-coupled testing cleared',
          'load-bearing approved',
          'load bearing approved'
        )) {
        if ($NotesLower.Contains($Phrase)) {
          $ProhibitedClearanceFlags.Add(('completion_decision_notes.{0}' -f $Phrase.Replace(' ', '_'))) | Out-Null
        }
      }
    }
  }

  $NoFakeValidationLock = $Payload.no_fake_validation_lock
  if ($null -eq $NoFakeValidationLock) {
    $InvalidFields.Add('no_fake_validation_lock') | Out-Null
  } else {
    Set-RequiredTrue -Target $NoFakeValidationLock -Field 'template_is_not_physical_validation' -Confirmed $ConfirmTemplateIsNotPhysicalValidation.IsPresent -QualifiedField 'no_fake_validation_lock.template_is_not_physical_validation' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $NoFakeValidationLock -Field 'requires_real_records' -Confirmed $ConfirmRequiresRealRecords.IsPresent -QualifiedField 'no_fake_validation_lock.requires_real_records' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $NoFakeValidationLock -Field 'fr018_implementation_cleared' -ConfirmedAbsent $ConfirmFr018ImplementationNotClearedByLock.IsPresent -Observed $Fr018ImplementationCleared.IsPresent -QualifiedField 'no_fake_validation_lock.fr018_implementation_cleared' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $NoFakeValidationLock -Field 'powered_or_frame_coupled_testing_cleared' -ConfirmedAbsent $ConfirmPoweredOrFrameCoupledTestingNotClearedByLock.IsPresent -Observed $PoweredOrFrameCoupledTestingCleared.IsPresent -QualifiedField 'no_fake_validation_lock.powered_or_frame_coupled_testing_cleared' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
  }

  if ($ProhibitedClearanceFlags.Count -gt 0) {
    $Status = 'final_decision_prohibited_clearance_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $DecisionLockViolations.Count -gt 0 -or $CompletionDecisionViolations.Count -gt 0) {
    $Status = 'invalid_final_decision_record_input'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-final-decision-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    mannequin_path = $ResolvedMannequinPath
    static_fit_path = $ResolvedStaticFitPath
    movement_path = $ResolvedMovementPath
    release_cable_path = $ResolvedReleaseCablePath
    engineering_review_path = $ResolvedEngineeringReviewPath
    final_physical_gate_record_output_path = $ResolvedFinalPhysicalGateRecordOutputPath
    output_path = $ResolvedOutputPath
    operator_supplied_final_decision_input_recorded = $true
    final_decision_record_is_ledger_review_input = $true
    final_decision_record_is_stage17_completion_by_itself = $false
    final_physical_gate_record_saved = $true
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    completion_ledger_update_written = $false
    powered_or_frame_coupled_testing_cleared = $false
    fr018_implementation_cleared = $false
    initializer_updated_fields = @($UpdatedFields.ToArray())
  }

  if ($null -eq $Payload.PSObject.Properties['record_generation']) {
    $Payload | Add-Member -NotePropertyName 'record_generation' -NotePropertyValue $Generation
  } else {
    $Payload.PSObject.Properties['record_generation'].Value = $Generation
  }

  $FinalPhysicalGate.raw_output | Set-Content -LiteralPath $ResolvedFinalPhysicalGateRecordOutputPath -Encoding UTF8
  $WroteFinalGateRecordFile = $true
  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedOutputPath -Encoding UTF8
  $WroteDecisionFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.final_decision_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  release_cable_path = $ResolvedReleaseCablePath
  engineering_review_path = $ResolvedEngineeringReviewPath
  output_path = $ResolvedOutputPath
  final_physical_gate_record_output_path = $ResolvedFinalPhysicalGateRecordOutputPath
  template_exists = (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)
  template_parse_ok = $TemplateParseOk
  output_path_required_for_create = $OutputPathRequiredForCreate
  final_physical_gate_record_output_path_required_for_create = $FinalPhysicalGateRecordOutputPathRequiredForCreate
  measurement_path_required_for_create = $MeasurementPathRequiredForCreate
  mockup_path_required_for_create = $MockupPathRequiredForCreate
  mannequin_path_required_for_create = $MannequinPathRequiredForCreate
  static_fit_path_required_for_create = $StaticFitPathRequiredForCreate
  movement_path_required_for_create = $MovementPathRequiredForCreate
  release_cable_path_required_for_create = $ReleaseCablePathRequiredForCreate
  engineering_review_path_required_for_create = $EngineeringReviewPathRequiredForCreate
  output_path_targets_template = $OutputPathTargetsTemplate
  final_physical_gate_record_output_path_targets_template = $FinalPhysicalGateRecordOutputPathTargetsTemplate
  output_path_conflicts_with_final_physical_gate_record_output = $OutputPathConflictsWithFinalPhysicalGateRecordOutput
  output_parent_exists = $OutputParentExists
  final_physical_gate_record_output_parent_exists = $FinalPhysicalGateRecordOutputParentExists
  candidate_output_path_ready = $CandidateOutputPathReady
  candidate_final_physical_gate_record_output_path_ready = $CandidateFinalPhysicalGateRecordOutputPathReady
  measurement_path_targets_final_decision_template = $MeasurementPathTargetsFinalDecisionTemplate
  mockup_path_targets_final_decision_template = $MockupPathTargetsFinalDecisionTemplate
  mannequin_path_targets_final_decision_template = $MannequinPathTargetsFinalDecisionTemplate
  static_fit_path_targets_final_decision_template = $StaticFitPathTargetsFinalDecisionTemplate
  movement_path_targets_final_decision_template = $MovementPathTargetsFinalDecisionTemplate
  release_cable_path_targets_final_decision_template = $ReleaseCablePathTargetsFinalDecisionTemplate
  engineering_review_path_targets_final_decision_template = $EngineeringReviewPathTargetsFinalDecisionTemplate
  measurement_file_exists = $MeasurementFileExists
  mockup_file_exists = $MockupFileExists
  mannequin_file_exists = $MannequinFileExists
  static_fit_file_exists = $StaticFitFileExists
  movement_file_exists = $MovementFileExists
  release_cable_file_exists = $ReleaseCableFileExists
  engineering_review_file_exists = $EngineeringReviewFileExists
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf) }
  final_physical_gate_record_output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedFinalPhysicalGateRecordOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedFinalPhysicalGateRecordOutputPath -PathType Leaf) }
  wrote_file = $WroteDecisionFile
  wrote_final_physical_gate_record = $WroteFinalGateRecordFile
  read_only_contract = ($Mode -eq 'Status')
  writes_repo = (($WroteDecisionFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot)) -or ($WroteFinalGateRecordFile -and (Test-PathUnderRoot -Path $ResolvedFinalPhysicalGateRecordOutputPath -Root $RepoRoot)))
  writes_data = ($WroteDecisionFile -or $WroteFinalGateRecordFile)
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_final_physical_gate_status = $UpstreamFinalPhysicalStatus
  upstream_final_physical_gate_ready = $UpstreamFinalPhysicalReady
  upstream_final_physical_gate_exit_code = $UpstreamFinalPhysicalExitCode
  upstream_final_physical_gate_parse_ok = $UpstreamFinalPhysicalParseOk
  final_physical_gate_reference_pilot_fingerprint = $FinalPhysicalGateReferencePilotFingerprint
  final_decision_pilot_fingerprint = $FinalDecisionPilotFingerprint
  operator_supplied_final_decision_input_recorded = $WroteDecisionFile
  final_decision_record_is_ledger_review_input = $WroteDecisionFile
  final_decision_record_is_stage17_completion_by_itself = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  completion_ledger_update_written = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  decision_lock_violations = @($DecisionLockViolations.ToArray())
  completion_decision_violations = @($CompletionDecisionViolations.ToArray())
  prohibited_clearance_flags_recorded = @($ProhibitedClearanceFlags.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied human FR-017 final decision input only after the final physical gate is decision-ready and saves that gate output as a linked record. It does not write the completion ledger, does not mark physical_validation_complete, does not allow a Stage 17 completion claim by itself, does not clear powered or frame-coupled testing, does not approve load-bearing use, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  create_command_template = $CreateCommandTemplate
  final_decision_status_command_template = $FinalDecisionStatusCommandTemplate
  next_command = if ($WroteDecisionFile) { '.\scripts\fr017-final-decision-record-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -FinalDecisionPath "{7}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedStaticFitPath, $ResolvedMovementPath, $ResolvedReleaseCablePath, $ResolvedEngineeringReviewPath, $ResolvedOutputPath } elseif ($Mode -eq 'Status' -and $ExitCode -eq 0) { $CreateCommandTemplate } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
