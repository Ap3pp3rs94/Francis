[CmdletBinding()]
param(
  [ValidateSet('Status', 'Create')]
  [string]$Mode = 'Status',

  [string]$OutputPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = '',

  [string]$FinalDecisionPath = '',

  [string]$TemplatePath = '',

  [string]$HandoffDate = '',

  [string]$ValidationCommandOrRecord = '',

  [switch]$ConfirmOperatorReviewedFinalDecision,
  [switch]$ConfirmCandidateOnly,
  [switch]$ConfirmDoesNotWriteCompletionLedger,
  [switch]$ConfirmPhysicalValidationCompleteFalse,
  [switch]$ConfirmStage17CompletionClaimAllowedFalse,
  [switch]$ConfirmFr018ImplementationClearedFalse,
  [switch]$ConfirmPoweredTestingNotCleared,
  [switch]$ConfirmFrameCoupledTestingNotCleared,
  [switch]$ConfirmLoadBearingUseNotApproved,
  [switch]$ConfirmFr018Blocked,

  [switch]$Fr018Cleared,
  [switch]$PoweredTestingCleared,
  [switch]$FrameCoupledTestingCleared,
  [switch]$LoadBearingApproved,
  [switch]$PhysicalValidationCompleteTrue,
  [switch]$Stage17CompletionClaimAllowedTrue
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$FinalDecisionGateScript = Join-Path $PSScriptRoot 'fr017-final-decision-record-gate.ps1'
$ExpectedFinalDecisionStatus = 'ready_for_completion_ledger_review'

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

function Invoke-FinalDecisionGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath,
    [string]$ResolvedMovementPath,
    [string]$ResolvedReleaseCablePath,
    [string]$ResolvedEngineeringReviewPath,
    [string]$ResolvedFinalDecisionPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $FinalDecisionGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath -StaticFitPath $ResolvedStaticFitPath -MovementPath $ResolvedMovementPath -ReleaseCablePath $ResolvedReleaseCablePath -EngineeringReviewPath $ResolvedEngineeringReviewPath -FinalDecisionPath $ResolvedFinalDecisionPath
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

function Add-InvalidIfFalse {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [bool]$Condition,
    [string]$Field
  )

  if (-not $Condition) {
    $Target.Add($Field) | Out-Null
  }
}

function Add-ProhibitedIfTrue {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [bool]$Condition,
    [string]$Field
  )

  if ($Condition) {
    $Target.Add($Field) | Out-Null
  }
}

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-COMPLETION-LEDGER-HANDOFF-TEMPLATE.md'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) { '' } else { Resolve-Fr017Path -Path $OutputPath }
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { '' } else { Resolve-Fr017Path -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { '' } else { Resolve-Fr017Path -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { '' } else { Resolve-Fr017Path -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { '' } else { Resolve-Fr017Path -Path $StaticFitPath }
$ResolvedMovementPath = if ([string]::IsNullOrWhiteSpace($MovementPath)) { '' } else { Resolve-Fr017Path -Path $MovementPath }
$ResolvedReleaseCablePath = if ([string]::IsNullOrWhiteSpace($ReleaseCablePath)) { '' } else { Resolve-Fr017Path -Path $ReleaseCablePath }
$ResolvedEngineeringReviewPath = if ([string]::IsNullOrWhiteSpace($EngineeringReviewPath)) { '' } else { Resolve-Fr017Path -Path $EngineeringReviewPath }
$ResolvedFinalDecisionPath = if ([string]::IsNullOrWhiteSpace($FinalDecisionPath)) { '' } else { Resolve-Fr017Path -Path $FinalDecisionPath }
$CreateCommandTemplate = '.\scripts\fr017-new-completion-ledger-handoff.ps1 -Mode Create -OutputPath <completion-ledger-handoff.md> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json> -HandoffDate YYYY-MM-DD -ValidationCommandOrRecord "<validation command or record>" -ConfirmOperatorReviewedFinalDecision -ConfirmCandidateOnly -ConfirmDoesNotWriteCompletionLedger -ConfirmPhysicalValidationCompleteFalse -ConfirmStage17CompletionClaimAllowedFalse -ConfirmFr018ImplementationClearedFalse -ConfirmPoweredTestingNotCleared -ConfirmFrameCoupledTestingNotCleared -ConfirmLoadBearingUseNotApproved -ConfirmFr018Blocked'
$CompletionLedgerGateStatusCommandTemplate = '.\scripts\fr017-completion-ledger-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json> -StaticFitPath <pilot-static-fit-record.json> -MovementPath <pilot-movement-record.json> -ReleaseCablePath <release-cable-record.json> -EngineeringReviewPath <engineering-review-record.json> -FinalDecisionPath <final-decision-record.json> -LedgerEntryPath <completion-ledger-handoff.md>'
$Status = if ($Mode -eq 'Status') { 'completion_ledger_handoff_initializer_status' } else { 'created_completion_ledger_handoff' }
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$TemplateParseOk = $false
$OutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedOutputPath)
$MeasurementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)
$MockupPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMockupPath)
$MannequinPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMannequinPath)
$StaticFitPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath)
$MovementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMovementPath)
$ReleaseCablePathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedReleaseCablePath)
$EngineeringReviewPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedEngineeringReviewPath)
$FinalDecisionPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath)
$OutputPathTargetsTemplate = $false
$OutputFileExists = $false
$OutputParentExists = $false
$CandidateOutputPathReady = $false
$MeasurementPathTargetsTemplate = $false
$MockupPathTargetsTemplate = $false
$MannequinPathTargetsTemplate = $false
$StaticFitPathTargetsTemplate = $false
$MovementPathTargetsTemplate = $false
$ReleaseCablePathTargetsTemplate = $false
$EngineeringReviewPathTargetsTemplate = $false
$FinalDecisionPathTargetsTemplate = $false
$MeasurementFileExists = $false
$MockupFileExists = $false
$MannequinFileExists = $false
$StaticFitFileExists = $false
$MovementFileExists = $false
$ReleaseCableFileExists = $false
$EngineeringReviewFileExists = $false
$FinalDecisionFileExists = $false
$UpstreamFinalDecisionStatus = ''
$UpstreamFinalDecisionReady = $false
$UpstreamFinalDecisionExitCode = 0
$UpstreamFinalDecisionParseOk = $false

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
  foreach ($RequiredPath in @(
      @{ name = 'measurement'; field = 'measurement_file'; missing_path_status = 'missing_measurement_path'; path = $ResolvedMeasurementPath },
      @{ name = 'mockup'; field = 'mockup_file'; missing_path_status = 'missing_mockup_path'; path = $ResolvedMockupPath },
      @{ name = 'mannequin'; field = 'mannequin_file'; missing_path_status = 'missing_mannequin_path'; path = $ResolvedMannequinPath },
      @{ name = 'static_fit'; field = 'static_fit_file'; missing_path_status = 'missing_static_fit_path'; path = $ResolvedStaticFitPath },
      @{ name = 'movement'; field = 'movement_file'; missing_path_status = 'missing_movement_path'; path = $ResolvedMovementPath },
      @{ name = 'release_cable'; field = 'release_cable_file'; missing_path_status = 'missing_release_cable_path'; path = $ResolvedReleaseCablePath },
      @{ name = 'engineering_review'; field = 'engineering_review_file'; missing_path_status = 'missing_engineering_review_path'; path = $ResolvedEngineeringReviewPath },
      @{ name = 'final_decision'; field = 'final_decision_file'; missing_path_status = 'missing_final_decision_path'; path = $ResolvedFinalDecisionPath }
    )) {
    $PathValue = [string]$RequiredPath.path
    if ([string]::IsNullOrWhiteSpace($PathValue)) {
      if ($Mode -eq 'Create') {
        $Status = [string]$RequiredPath.missing_path_status
        $ExitCode = 1
        break
      }
      continue
    }

    $TargetsTemplate = [string]::Equals($PathValue, $ResolvedTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $Exists = Test-Path -LiteralPath $PathValue -PathType Leaf
    switch ([string]$RequiredPath.name) {
      'measurement' {
        $MeasurementPathTargetsTemplate = $TargetsTemplate
        $MeasurementFileExists = $Exists
      }
      'mockup' {
        $MockupPathTargetsTemplate = $TargetsTemplate
        $MockupFileExists = $Exists
      }
      'mannequin' {
        $MannequinPathTargetsTemplate = $TargetsTemplate
        $MannequinFileExists = $Exists
      }
      'static_fit' {
        $StaticFitPathTargetsTemplate = $TargetsTemplate
        $StaticFitFileExists = $Exists
      }
      'movement' {
        $MovementPathTargetsTemplate = $TargetsTemplate
        $MovementFileExists = $Exists
      }
      'release_cable' {
        $ReleaseCablePathTargetsTemplate = $TargetsTemplate
        $ReleaseCableFileExists = $Exists
      }
      'engineering_review' {
        $EngineeringReviewPathTargetsTemplate = $TargetsTemplate
        $EngineeringReviewFileExists = $Exists
      }
      'final_decision' {
        $FinalDecisionPathTargetsTemplate = $TargetsTemplate
        $FinalDecisionFileExists = $Exists
      }
    }

    if ($TargetsTemplate) {
      $Status = '{0}_path_targets_completion_ledger_handoff_template' -f [string]$RequiredPath.name
      $ExitCode = 1
      break
    } elseif (-not $Exists) {
      $Status = 'missing_{0}' -f [string]$RequiredPath.field
      $ExitCode = 1
      break
    }
  }
}

if ($ExitCode -eq 0 -and
  -not [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedMockupPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedMannequinPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedStaticFitPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedMovementPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedReleaseCablePath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedEngineeringReviewPath) -and
  -not [string]::IsNullOrWhiteSpace($ResolvedFinalDecisionPath)) {
  $FinalDecisionGate = Invoke-FinalDecisionGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath -ResolvedReleaseCablePath $ResolvedReleaseCablePath -ResolvedEngineeringReviewPath $ResolvedEngineeringReviewPath -ResolvedFinalDecisionPath $ResolvedFinalDecisionPath
  $UpstreamFinalDecisionExitCode = [int]$FinalDecisionGate.exit_code
  $UpstreamFinalDecisionParseOk = [bool]$FinalDecisionGate.parse_ok
  $UpstreamFinalDecisionStatus = if ([bool]$FinalDecisionGate.parse_ok) { [string]$FinalDecisionGate.payload.status } else { 'failed_final_decision_gate_parse' }
  $UpstreamFinalDecisionReady = [bool]$FinalDecisionGate.parse_ok -and [int]$FinalDecisionGate.exit_code -eq 0 -and $UpstreamFinalDecisionStatus -eq $ExpectedFinalDecisionStatus
  if (-not $UpstreamFinalDecisionReady) {
    $Status = 'upstream_final_decision_not_ready'
    $ExitCode = 1
  }
}

$TemplateText = ''
if ((Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf) -and ($ExitCode -eq 0 -or $Mode -eq 'Status')) {
  try {
    $TemplateText = Get-Content -LiteralPath $ResolvedTemplatePath -Raw
    $TemplateParseOk = $TemplateText.Contains('PENDING_DATE') -and $TemplateText.Contains('PENDING_FINAL_DECISION_RECORD_PATH') -and $TemplateText.Contains('PENDING_VALIDATION_COMMAND_OR_RECORD')
    if (-not $TemplateParseOk) {
      $Status = 'invalid_completion_ledger_handoff_template'
      $ExitCode = 1
    }
  } catch {
    $Status = 'template_read_failed'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  if (Test-MissingOrPendingText -Value $HandoffDate) {
    $InvalidFields.Add('handoff_date') | Out-Null
  } elseif (-not (Test-IsoDateNotFuture -Value $HandoffDate.Trim())) {
    $InvalidFields.Add('handoff_date') | Out-Null
  }
  if (Test-MissingOrPendingText -Value $ValidationCommandOrRecord) {
    $InvalidFields.Add('validation_command_or_record') | Out-Null
  }

  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmOperatorReviewedFinalDecision.IsPresent -Field 'confirm_operator_reviewed_final_decision'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmCandidateOnly.IsPresent -Field 'confirm_candidate_only'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmDoesNotWriteCompletionLedger.IsPresent -Field 'confirm_does_not_write_completion_ledger'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmPhysicalValidationCompleteFalse.IsPresent -Field 'confirm_physical_validation_complete_false'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmStage17CompletionClaimAllowedFalse.IsPresent -Field 'confirm_stage17_completion_claim_allowed_false'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmFr018ImplementationClearedFalse.IsPresent -Field 'confirm_fr018_implementation_cleared_false'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmPoweredTestingNotCleared.IsPresent -Field 'confirm_powered_testing_not_cleared'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmFrameCoupledTestingNotCleared.IsPresent -Field 'confirm_frame_coupled_testing_not_cleared'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmLoadBearingUseNotApproved.IsPresent -Field 'confirm_load_bearing_use_not_approved'
  Add-InvalidIfFalse -Target $InvalidFields -Condition $ConfirmFr018Blocked.IsPresent -Field 'confirm_fr018_blocked'

  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $Fr018Cleared.IsPresent -Field 'fr018_cleared'
  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $PoweredTestingCleared.IsPresent -Field 'powered_testing_cleared'
  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $FrameCoupledTestingCleared.IsPresent -Field 'frame_coupled_testing_cleared'
  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $LoadBearingApproved.IsPresent -Field 'load_bearing_approved'
  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $PhysicalValidationCompleteTrue.IsPresent -Field 'physical_validation_complete_true'
  Add-ProhibitedIfTrue -Target $ProhibitedClearanceFlags -Condition $Stage17CompletionClaimAllowedTrue.IsPresent -Field 'stage17_completion_claim_allowed_true'

  if ($ProhibitedClearanceFlags.Count -gt 0) {
    $Status = 'completion_ledger_prohibited_clearance_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_completion_ledger_handoff_input'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  $CandidateText = $TemplateText
  $CandidateText = $CandidateText.Replace('PENDING_DATE', $HandoffDate.Trim())
  $CandidateText = $CandidateText.Replace('PENDING_FINAL_DECISION_RECORD_PATH', $ResolvedFinalDecisionPath)
  $CandidateText = $CandidateText.Replace('PENDING_VALIDATION_COMMAND_OR_RECORD', $ValidationCommandOrRecord.Trim())
  $CandidateLines = $CandidateText -split '\r?\n'
  $CandidateText = ($CandidateLines | Where-Object {
      ([string]$_).IndexOf('PENDING', [System.StringComparison]::OrdinalIgnoreCase) -lt 0
    }) -join [Environment]::NewLine

  $GenerationBlock = @"

## Candidate Generation Record

- generated_by: scripts/fr017-new-completion-ledger-handoff.ps1
- template_path: $ResolvedTemplatePath
- final_decision_record_path: $ResolvedFinalDecisionPath
- output_path: $ResolvedOutputPath
- candidate_only: true
- completion_ledger_update_written: false
- physical_validation_complete: false
- stage17_completion_claim_allowed: false
- fr018_implementation_cleared: false
- powered_or_frame_coupled_testing_cleared: false
"@
  $CandidateText = $CandidateText.TrimEnd() + $GenerationBlock + [Environment]::NewLine

  $UpdatedFields.Add('PENDING_DATE') | Out-Null
  $UpdatedFields.Add('PENDING_FINAL_DECISION_RECORD_PATH') | Out-Null
  $UpdatedFields.Add('PENDING_VALIDATION_COMMAND_OR_RECORD') | Out-Null

  Set-Content -LiteralPath $ResolvedOutputPath -Value $CandidateText -Encoding UTF8
  $WroteFile = $true
}

$Output = [ordered]@{
  kind = 'francis.fr017.completion_ledger_handoff_initializer'
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
  final_decision_path = $ResolvedFinalDecisionPath
  output_path = $ResolvedOutputPath
  template_exists = (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)
  template_parse_ok = $TemplateParseOk
  output_path_required_for_create = $OutputPathRequiredForCreate
  measurement_path_required_for_create = $MeasurementPathRequiredForCreate
  mockup_path_required_for_create = $MockupPathRequiredForCreate
  mannequin_path_required_for_create = $MannequinPathRequiredForCreate
  static_fit_path_required_for_create = $StaticFitPathRequiredForCreate
  movement_path_required_for_create = $MovementPathRequiredForCreate
  release_cable_path_required_for_create = $ReleaseCablePathRequiredForCreate
  engineering_review_path_required_for_create = $EngineeringReviewPathRequiredForCreate
  final_decision_path_required_for_create = $FinalDecisionPathRequiredForCreate
  output_path_targets_template = $OutputPathTargetsTemplate
  output_parent_exists = $OutputParentExists
  candidate_output_path_ready = $CandidateOutputPathReady
  measurement_path_targets_completion_ledger_handoff_template = $MeasurementPathTargetsTemplate
  mockup_path_targets_completion_ledger_handoff_template = $MockupPathTargetsTemplate
  mannequin_path_targets_completion_ledger_handoff_template = $MannequinPathTargetsTemplate
  static_fit_path_targets_completion_ledger_handoff_template = $StaticFitPathTargetsTemplate
  movement_path_targets_completion_ledger_handoff_template = $MovementPathTargetsTemplate
  release_cable_path_targets_completion_ledger_handoff_template = $ReleaseCablePathTargetsTemplate
  engineering_review_path_targets_completion_ledger_handoff_template = $EngineeringReviewPathTargetsTemplate
  final_decision_path_targets_completion_ledger_handoff_template = $FinalDecisionPathTargetsTemplate
  measurement_file_exists = $MeasurementFileExists
  mockup_file_exists = $MockupFileExists
  mannequin_file_exists = $MannequinFileExists
  static_fit_file_exists = $StaticFitFileExists
  movement_file_exists = $MovementFileExists
  release_cable_file_exists = $ReleaseCableFileExists
  engineering_review_file_exists = $EngineeringReviewFileExists
  final_decision_file_exists = $FinalDecisionFileExists
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf) }
  wrote_file = $WroteFile
  read_only_contract = ($Mode -eq 'Status')
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  writes_completion_ledger = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_final_decision_status = $UpstreamFinalDecisionStatus
  upstream_final_decision_ready = $UpstreamFinalDecisionReady
  upstream_final_decision_exit_code = $UpstreamFinalDecisionExitCode
  upstream_final_decision_parse_ok = $UpstreamFinalDecisionParseOk
  operator_supplied_completion_ledger_handoff_recorded = $WroteFile
  candidate_ledger_handoff_ready_for_review = $WroteFile
  completion_ledger_update_written = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  prohibited_clearance_flags_recorded = @($ProhibitedClearanceFlags.ToArray())
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  no_fake_validation_lock = 'This initializer creates a candidate FR-017 completion-ledger handoff file only after final decision readiness. It does not write docs/operations/COMPLETION_LEDGER.md, does not mark physical_validation_complete, does not permit a Stage 17 completion claim by itself, and does not clear FR-018, powered testing, frame-coupled testing, or load-bearing use.'
  create_command_template = $CreateCommandTemplate
  completion_ledger_gate_status_command_template = $CompletionLedgerGateStatusCommandTemplate
  next_command = if ($Mode -eq 'Status') { $CreateCommandTemplate } elseif ($WroteFile) { '.\scripts\fr017-completion-ledger-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}" -FinalDecisionPath "{7}" -LedgerEntryPath "{8}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedStaticFitPath, $ResolvedMovementPath, $ResolvedReleaseCablePath, $ResolvedEngineeringReviewPath, $ResolvedFinalDecisionPath, $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
