[CmdletBinding()]
param(
  [ValidateSet('Create')]
  [string]$Mode = 'Create',

  [Parameter(Mandatory = $true)]
  [string]$OutputPath,

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
$ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
$Status = 'created_pending_measurement_record'
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]

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

if ($ExitCode -eq 0) {
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
  output_exists = (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf)
  wrote_file = $WroteFile
  read_only_contract = $false
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
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
