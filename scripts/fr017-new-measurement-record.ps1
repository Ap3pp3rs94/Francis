[CmdletBinding()]
param(
  [ValidateSet('Status', 'Summary', 'Create')]
  [string]$Mode = 'Status',

  [string]$OutputPath = '',

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Observer = '',

  [string]$PilotId = '',

  [string]$MeasurementTool = '',

  [string]$Method = '',

  [string]$Posture = '',

  [switch]$ConfirmNoTissueCompressionUsed,

  [switch]$ConfirmNoWristBoneCompressionUsed,

  [switch]$ConfirmMetricToolUsed,

  [switch]$ConfirmArmRelaxedPalmNeutralOrExceptionRecorded,

  [switch]$ConfirmStopConditionsBriefed,

  [string]$ConditionNotes = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-Fr017Path {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function Get-DefaultMeasurementOutputPath {
  $DateStamp = Get-Date -Format 'yyyy-MM-dd'
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot ('FR-017_Stage17_Package\FR-017-MEASUREMENTS-{0}-PILOT-RECORD.json' -f $DateStamp)))
}

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-IsoDateNotFuture {
  param([string]$Value)

  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Value,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  return $ParseOk -and $ParsedDate.Date -le [datetime]::Today
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

function Set-OptionalEvidenceText {
  param(
    [object]$Evidence,
    [string]$Name,
    [string]$Value,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$UpdatedFields,
    [string]$FieldPrefix = 'evidence'
  )

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return
  }

  if (Test-MissingOrPendingText -Value $Value) {
    $InvalidFields.Add(('{0}.{1}' -f $FieldPrefix, $Name)) | Out-Null
    return
  }

  $Property = $Evidence.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    $InvalidFields.Add(('{0}.{1}' -f $FieldPrefix, $Name)) | Out-Null
    return
  }

  $Property.Value = $Value.Trim()
  if ($null -ne $UpdatedFields) {
    $UpdatedFields.Add(('{0}.{1}' -f $FieldPrefix, $Name)) | Out-Null
  }
}

function Set-ConfirmedCondition {
  param(
    [object]$MeasurementConditions,
    [string]$Name,
    [bool]$Confirmed,
    [System.Collections.Generic.List[string]]$InvalidFields,
    [System.Collections.Generic.List[string]]$UpdatedFields
  )

  if (-not $Confirmed) {
    return
  }

  $Property = $MeasurementConditions.PSObject.Properties[$Name]
  if ($null -eq $Property) {
    $InvalidFields.Add(('measurement_conditions.{0}' -f $Name)) | Out-Null
    return
  }

  $Property.Value = $true
  $UpdatedFields.Add(('measurement_conditions.{0}' -f $Name)) | Out-Null
}

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ReadOnlyMode = $Mode -in @('Status', 'Summary')
$SuggestedOutputPath = Get-DefaultMeasurementOutputPath
if ([string]::IsNullOrWhiteSpace($OutputPath)) {
  $ResolvedOutputPath = if ($ReadOnlyMode) { $SuggestedOutputPath } else { '' }
  $OutputPathSource = if ($ReadOnlyMode) { 'suggested_default' } else { 'missing' }
} else {
  $ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
  $OutputPathSource = 'operator_supplied'
}
$CreateCommandOutputArg = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { '<measurement-record.json>' } else { '"{0}"' -f $ResolvedOutputPath }
$MeasurementPathStatusArg = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { '<measurement-record.json>' } else { '"{0}"' -f $ResolvedOutputPath }
$CreateCommandTemplate = '.\scripts\fr017-new-measurement-record.ps1 -Mode Create -OutputPath {0} -EvidenceDate YYYY-MM-DD -Observer "<observer>" -PilotId "<pilot-reference>" -MeasurementTool "flexible metric tape" -Method "flexible tape, no tissue compression" -Posture "arm relaxed, palm neutral unless otherwise noted" -ConfirmNoTissueCompressionUsed -ConfirmNoWristBoneCompressionUsed -ConfirmMetricToolUsed -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded -ConfirmStopConditionsBriefed -ConditionNotes "<no tissue/no wrist-bone compression, metric tool, and stop briefing notes>"' -f $CreateCommandOutputArg
$MeasurementIntakeStatusCommandTemplate = '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath {0}' -f $MeasurementPathStatusArg
$EffectiveMode = if ($ReadOnlyMode) { 'Status' } else { $Mode }
$Status = if ($EffectiveMode -eq 'Status') { 'measurement_record_initializer_status' } else { 'created_pending_measurement_record' }
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$TemplateParseOk = $false
$OutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedOutputPath)
$OutputPathTargetsTemplate = $false
$OutputFileExists = $false
$OutputParentExists = $false
$CandidateOutputPathReady = $false

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

  if ($EffectiveMode -eq 'Create') {
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

$Payload = $null
if ((Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf) -and ($ExitCode -eq 0 -or $ReadOnlyMode)) {
  try {
    $Payload = Get-Content -LiteralPath $ResolvedTemplatePath -Raw | ConvertFrom-Json -ErrorAction Stop
    $TemplateParseOk = $true
  } catch {
    $Status = 'invalid_template_json'
    $ExitCode = 1
  }
}

if ($EffectiveMode -eq 'Create' -and $ExitCode -eq 0) {
  $Evidence = $Payload.evidence
  if ($null -eq $Evidence) {
    $InvalidFields.Add('evidence') | Out-Null
  } else {
    if (-not [string]::IsNullOrWhiteSpace($EvidenceDate)) {
      if (-not (Test-IsoDateNotFuture -Value $EvidenceDate.Trim())) {
        $InvalidFields.Add('evidence.date') | Out-Null
      } else {
        $Evidence.date = $EvidenceDate.Trim()
        $UpdatedFields.Add('evidence.date') | Out-Null
      }
    }
    Set-OptionalEvidenceText -Evidence $Evidence -Name 'observer' -Value $Observer -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-OptionalEvidenceText -Evidence $Evidence -Name 'pilot_id' -Value $PilotId -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-OptionalEvidenceText -Evidence $Evidence -Name 'measurement_tool' -Value $MeasurementTool -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-OptionalEvidenceText -Evidence $Evidence -Name 'method' -Value $Method -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-OptionalEvidenceText -Evidence $Evidence -Name 'posture' -Value $Posture -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  $MeasurementConditions = $Payload.measurement_conditions
  if ($null -eq $MeasurementConditions) {
    $InvalidFields.Add('measurement_conditions') | Out-Null
  } else {
    Set-ConfirmedCondition -MeasurementConditions $MeasurementConditions -Name 'no_tissue_compression_used' -Confirmed $ConfirmNoTissueCompressionUsed.IsPresent -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-ConfirmedCondition -MeasurementConditions $MeasurementConditions -Name 'no_wrist_bone_compression_used' -Confirmed $ConfirmNoWristBoneCompressionUsed.IsPresent -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-ConfirmedCondition -MeasurementConditions $MeasurementConditions -Name 'metric_tool_used' -Confirmed $ConfirmMetricToolUsed.IsPresent -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-ConfirmedCondition -MeasurementConditions $MeasurementConditions -Name 'arm_relaxed_palm_neutral_or_exception_recorded' -Confirmed $ConfirmArmRelaxedPalmNeutralOrExceptionRecorded.IsPresent -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-ConfirmedCondition -MeasurementConditions $MeasurementConditions -Name 'stop_conditions_briefed' -Confirmed $ConfirmStopConditionsBriefed.IsPresent -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-OptionalEvidenceText -Evidence $MeasurementConditions -Name 'condition_notes' -Value $ConditionNotes -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields -FieldPrefix 'measurement_conditions'
  }

  if ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_initializer_input'
    $ExitCode = 1
  }
}

if ($EffectiveMode -eq 'Create' -and $ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-measurement-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    output_path = $ResolvedOutputPath
    record_is_measurement_evidence = $false
    setup_brief_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
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
  kind = 'francis.fr017.measurement_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  output_path = $ResolvedOutputPath
  suggested_output_path = $SuggestedOutputPath
  output_path_source = $OutputPathSource
  template_exists = (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)
  template_parse_ok = $TemplateParseOk
  output_path_required_for_create = $OutputPathRequiredForCreate
  output_path_targets_template = $OutputPathTargetsTemplate
  output_parent_exists = $OutputParentExists
  candidate_output_path_ready = $CandidateOutputPathReady
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf) }
  wrote_file = $WroteFile
  read_only_contract = $ReadOnlyMode
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  record_is_measurement_evidence = $false
  setup_brief_is_physical_validation_evidence = $false
  no_fake_validation_lock = 'This initializer creates a pending FR-017 measurement working record and may record explicitly supplied setup/safety-brief fields only. It does not record physical measurements, mark physical validation complete, permit a Stage 17 completion claim, or clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  create_command_template = $CreateCommandTemplate
  measurement_intake_status_command_template = $MeasurementIntakeStatusCommandTemplate
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedOutputPath } elseif ($ReadOnlyMode) { $CreateCommandTemplate } else { '' }
}

if ($Mode -eq 'Summary') {
  $NextCreateCommand = if ($CandidateOutputPathReady) { '.\scripts\fr017-new-measurement-record.ps1 -Mode Create -OutputPath "{0}"' -f $ResolvedOutputPath } else { $CreateCommandTemplate }
  $NextAction = if (-not $Output.template_exists) {
    'repair_or_provide_template_path'
  } elseif (-not $TemplateParseOk) {
    'repair_template_json'
  } elseif ($OutputPathRequiredForCreate) {
    'provide_candidate_output_path'
  } elseif ($OutputPathTargetsTemplate) {
    'choose_non_template_output_path'
  } elseif ($OutputFileExists) {
    'choose_unused_output_path'
  } elseif (-not $OutputParentExists) {
    'choose_existing_output_parent'
  } elseif ($CandidateOutputPathReady) {
    'run_create_or_capture_setup_brief'
  } else {
    'review_initializer_status'
  }

  $Summary = [ordered]@{
    kind = 'francis.fr017.measurement_record_initializer_summary'
    mode = 'Summary'
    source_kind = $Output.kind
    source_mode = 'Status'
    status = $Output.status
    template_path = $Output.template_path
    output_path = $Output.output_path
    suggested_output_path = $Output.suggested_output_path
    output_path_source = $Output.output_path_source
    template_exists = $Output.template_exists
    template_parse_ok = $Output.template_parse_ok
    output_path_required_for_create = $Output.output_path_required_for_create
    output_path_targets_template = $Output.output_path_targets_template
    output_parent_exists = $Output.output_parent_exists
    candidate_output_path_ready = $Output.candidate_output_path_ready
    output_exists = $Output.output_exists
    next_action = $NextAction
    next_create_command = $NextCreateCommand
    create_command_template = $CreateCommandTemplate
    measurement_intake_status_command_template = $MeasurementIntakeStatusCommandTemplate
    setup_brief_fields_supported = @(
      'evidence.date',
      'evidence.observer',
      'evidence.pilot_id',
      'evidence.measurement_tool',
      'evidence.method',
      'evidence.posture',
      'measurement_conditions.no_tissue_compression_used',
      'measurement_conditions.no_wrist_bone_compression_used',
      'measurement_conditions.metric_tool_used',
      'measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded',
      'measurement_conditions.stop_conditions_briefed',
      'measurement_conditions.condition_notes'
    )
    setup_brief_can_only_clear_first_group = $true
    wrote_file = $false
    read_only_contract = $true
    writes_repo = $false
    writes_data = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    powered_or_frame_coupled_testing_cleared = $false
    fr018_implementation_cleared = $false
    record_is_measurement_evidence = $false
    setup_brief_is_physical_validation_evidence = $false
    no_fake_validation_lock = $Output.no_fake_validation_lock
    omitted_full_status_fields = @('updated_fields', 'invalid_fields')
  }

  $Summary | ConvertTo-Json -Depth 8
  exit $ExitCode
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
