[CmdletBinding()]
param(
  [ValidateSet('Status', 'UpdateSetup')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

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

  [string]$ConditionNotes = '',

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
    [bool]$AllowOverwrite,
    [bool]$AllowMatchingExisting = $false
  )

  $Property = $Target.PSObject.Properties[$Field]
  if ($null -eq $Property) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (Test-MissingOrPendingValue -Value $Value) {
    $InvalidFields.Add($QualifiedField) | Out-Null
    return
  }

  if (
    $AllowMatchingExisting -and
    -not (Test-MissingOrPendingValue -Value $Property.Value) -and
    [string]::Equals(([string]$Property.Value).Trim(), $Value.Trim(), [System.StringComparison]::OrdinalIgnoreCase)
  ) {
    $Property.Value = $Value.Trim()
    $UpdatedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not $AllowOverwrite -and -not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwriteBlockedFields.Add($QualifiedField) | Out-Null
    return
  }

  if (-not (Test-MissingOrPendingValue -Value $Property.Value)) {
    $OverwrittenFields.Add($QualifiedField) | Out-Null
  }

  $Property.Value = $Value.Trim()
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Set-RequiredDate {
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

  if ((Test-MissingOrPendingValue -Value $Value) -or -not (Test-IsoDateNotFuture -Value $Value.Trim())) {
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

$SetupRequiredFields = @(
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

function Add-SetupFieldReadback {
  param(
    [object]$Target,
    [string]$Field,
    [string]$QualifiedField,
    [System.Collections.Generic.List[string]]$MissingFields,
    [System.Collections.Generic.List[string]]$ExistingFields
  )

  if ($null -eq $Target) {
    $MissingFields.Add($QualifiedField) | Out-Null
    return
  }

  $Property = $Target.PSObject.Properties[$Field]
  if ($null -eq $Property -or (Test-MissingOrPendingValue -Value $Property.Value)) {
    $MissingFields.Add($QualifiedField) | Out-Null
    return
  }

  $ExistingFields.Add($QualifiedField) | Out-Null
}

$Status = if ($Mode -eq 'Status') { 'measurement_setup_update_status' } else { 'updated_measurement_setup_brief' }
$ExitCode = 0
$WroteFile = $false
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$OverwriteBlockedFields = New-Object System.Collections.Generic.List[string]
$OverwrittenFields = New-Object System.Collections.Generic.List[string]
$SetupMissingFields = New-Object System.Collections.Generic.List[string]
$SetupExistingFields = New-Object System.Collections.Generic.List[string]
$ResolvedMeasurementPath = ''
$Payload = $null

if ([string]::IsNullOrWhiteSpace($MeasurementPath)) {
  $InvalidFields.Add('measurement_path') | Out-Null
  $Status = 'invalid_measurement_setup_update_input'
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

  $Evidence = $Payload.evidence
  $MeasurementConditions = $Payload.measurement_conditions
  if ($null -eq $Evidence) {
    $InvalidFields.Add('evidence') | Out-Null
  }
  if ($null -eq $MeasurementConditions) {
    $InvalidFields.Add('measurement_conditions') | Out-Null
  }

  if ($InvalidFields.Count -eq 0) {
    Add-SetupFieldReadback -Target $Evidence -Field 'date' -QualifiedField 'evidence.date' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $Evidence -Field 'observer' -QualifiedField 'evidence.observer' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $Evidence -Field 'pilot_id' -QualifiedField 'evidence.pilot_id' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $Evidence -Field 'measurement_tool' -QualifiedField 'evidence.measurement_tool' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $Evidence -Field 'method' -QualifiedField 'evidence.method' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $Evidence -Field 'posture' -QualifiedField 'evidence.posture' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'no_tissue_compression_used' -QualifiedField 'measurement_conditions.no_tissue_compression_used' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'no_wrist_bone_compression_used' -QualifiedField 'measurement_conditions.no_wrist_bone_compression_used' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'metric_tool_used' -QualifiedField 'measurement_conditions.metric_tool_used' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'arm_relaxed_palm_neutral_or_exception_recorded' -QualifiedField 'measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'stop_conditions_briefed' -QualifiedField 'measurement_conditions.stop_conditions_briefed' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
    Add-SetupFieldReadback -Target $MeasurementConditions -Field 'condition_notes' -QualifiedField 'measurement_conditions.condition_notes' -MissingFields $SetupMissingFields -ExistingFields $SetupExistingFields
  }

  if ($InvalidFields.Count -gt 0) {
    $Status = if ($Mode -eq 'Status') { 'invalid_measurement_setup_status_target' } else { 'invalid_measurement_setup_update_input' }
    $ExitCode = 1
  }
}

if ($Mode -eq 'UpdateSetup' -and $ExitCode -eq 0) {
  $Evidence = $Payload.evidence
  $MeasurementConditions = $Payload.measurement_conditions
  Set-RequiredDate -Target $Evidence -Field 'date' -Value $EvidenceDate -QualifiedField 'evidence.date' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredText -Target $Evidence -Field 'observer' -Value $Observer -QualifiedField 'evidence.observer' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredText -Target $Evidence -Field 'pilot_id' -Value $PilotId -QualifiedField 'evidence.pilot_id' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredText -Target $Evidence -Field 'measurement_tool' -Value $MeasurementTool -QualifiedField 'evidence.measurement_tool' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredText -Target $Evidence -Field 'method' -Value $Method -QualifiedField 'evidence.method' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent -AllowMatchingExisting $true
  Set-RequiredText -Target $Evidence -Field 'posture' -Value $Posture -QualifiedField 'evidence.posture' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent -AllowMatchingExisting $true
  Set-RequiredConfirmation -Target $MeasurementConditions -Field 'no_tissue_compression_used' -Confirmed $ConfirmNoTissueCompressionUsed.IsPresent -QualifiedField 'measurement_conditions.no_tissue_compression_used' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredConfirmation -Target $MeasurementConditions -Field 'no_wrist_bone_compression_used' -Confirmed $ConfirmNoWristBoneCompressionUsed.IsPresent -QualifiedField 'measurement_conditions.no_wrist_bone_compression_used' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredConfirmation -Target $MeasurementConditions -Field 'metric_tool_used' -Confirmed $ConfirmMetricToolUsed.IsPresent -QualifiedField 'measurement_conditions.metric_tool_used' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredConfirmation -Target $MeasurementConditions -Field 'arm_relaxed_palm_neutral_or_exception_recorded' -Confirmed $ConfirmArmRelaxedPalmNeutralOrExceptionRecorded.IsPresent -QualifiedField 'measurement_conditions.arm_relaxed_palm_neutral_or_exception_recorded' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredConfirmation -Target $MeasurementConditions -Field 'stop_conditions_briefed' -Confirmed $ConfirmStopConditionsBriefed.IsPresent -QualifiedField 'measurement_conditions.stop_conditions_briefed' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent
  Set-RequiredText -Target $MeasurementConditions -Field 'condition_notes' -Value $ConditionNotes -QualifiedField 'measurement_conditions.condition_notes' -InvalidFields $InvalidFields -OverwriteBlockedFields $OverwriteBlockedFields -OverwrittenFields $OverwrittenFields -UpdatedFields $UpdatedFields -AllowOverwrite $AllowOverwrite.IsPresent

  if ($OverwriteBlockedFields.Count -gt 0) {
    $Status = 'measurement_setup_fields_already_populated'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_measurement_setup_update_input'
    $ExitCode = 1
  }
}

if ($Mode -eq 'UpdateSetup' -and $ExitCode -eq 0) {
  $UpdateEvent = [ordered]@{
    generated_by = 'scripts/fr017-update-measurement-setup-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    mode = $Mode
    updated_fields = @($UpdatedFields.ToArray())
    overwritten_fields = @($OverwrittenFields.ToArray())
    setup_update_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    fr018_implementation_cleared = $false
  }

  if ($null -eq $Payload.PSObject.Properties['measurement_setup_update_events']) {
    $Payload | Add-Member -NotePropertyName 'measurement_setup_update_events' -NotePropertyValue @($UpdateEvent)
  } else {
    $Payload.PSObject.Properties['measurement_setup_update_events'].Value = @(@($Payload.measurement_setup_update_events) + $UpdateEvent)
  }

  $Payload | ConvertTo-Json -Depth 20 | Set-Content -LiteralPath $ResolvedMeasurementPath -Encoding UTF8
  $WroteFile = $true
}

$UpdateCommandTemplate = '.\scripts\fr017-update-measurement-setup-record.ps1 -Mode UpdateSetup -MeasurementPath "{0}" -EvidenceDate YYYY-MM-DD -Observer "<observer>" -PilotId "<pilot-reference>" -MeasurementTool "flexible metric tape" -Method "flexible tape, no tissue compression" -Posture "arm relaxed, palm neutral unless otherwise noted" -ConfirmNoTissueCompressionUsed -ConfirmNoWristBoneCompressionUsed -ConfirmMetricToolUsed -ConfirmArmRelaxedPalmNeutralOrExceptionRecorded -ConfirmStopConditionsBriefed -ConditionNotes "<no tissue/no wrist-bone compression, metric tool, and stop briefing notes>"' -f $ResolvedMeasurementPath

$Output = [ordered]@{
  kind = 'francis.fr017.measurement_setup_record_update'
  mode = $Mode
  status = $Status
  measurement_path = $ResolvedMeasurementPath
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)) { $false } else { Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf }
  wrote_file = $WroteFile
  read_only_contract = ($Mode -eq 'Status')
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedMeasurementPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  operator_supplied_setup_input_recorded = $WroteFile
  setup_update_is_physical_validation_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  no_fake_validation_lock = 'This updater records operator-supplied setup and measurement-condition inputs in an existing FR-017 working record only. It does not record left/right measurements, mark physical validation complete, permit a Stage 17 completion claim, or clear FR-018.'
  setup_status_contract = 'Status mode is a read-only preflight for the setup/safety updater. It checks the target working record and reports which setup fields are still missing without writing evidence, recording measurements, marking physical validation complete, or clearing FR-018.'
  setup_required_fields = @($SetupRequiredFields)
  setup_missing_fields = @($SetupMissingFields.ToArray())
  setup_existing_fields = @($SetupExistingFields.ToArray())
  setup_missing_field_count = [int]$SetupMissingFields.Count
  setup_existing_field_count = [int]$SetupExistingFields.Count
  setup_capture_group_complete = ($ExitCode -eq 0 -and $SetupMissingFields.Count -eq 0)
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  overwrite_blocked_fields = @($OverwriteBlockedFields.ToArray())
  overwritten_fields = @($OverwrittenFields.ToArray())
  update_command_template = $UpdateCommandTemplate
  next_command = if ($WroteFile) { '.\scripts\fr017-measurement-intake.ps1 -Mode Status -MeasurementPath "{0}"' -f $ResolvedMeasurementPath } elseif ($Mode -eq 'Status' -and $ExitCode -eq 0) { $UpdateCommandTemplate } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
