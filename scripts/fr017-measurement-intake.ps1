[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path

function Resolve-IntakePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
}

function ConvertTo-StringArray {
  param([object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [string]) {
    if ([string]::IsNullOrWhiteSpace($Value)) {
      return @()
    }
    return @($Value)
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object {
        $Item = [string]$_
        if (-not [string]::IsNullOrWhiteSpace($Item)) {
          $Item
        }
      })
  }
  $SingleValue = [string]$Value
  if ([string]::IsNullOrWhiteSpace($SingleValue)) {
    return @()
  }
  return @($SingleValue)
}

function Get-UniqueStringArray {
  param([object]$Value)

  $Result = New-Object System.Collections.Generic.List[string]
  foreach ($Item in (ConvertTo-StringArray -Value $Value)) {
    if (-not $Result.Contains([string]$Item)) {
      $Result.Add([string]$Item) | Out-Null
    }
  }
  return @($Result.ToArray())
}

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-PositiveNumber {
  param([object]$Value)

  if ($null -eq $Value) {
    return $false
  }
  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number)) {
    return $false
  }
  return $Number -gt 0
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

function Add-IfMissingText {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Target.Add($Field) | Out-Null
  }
}

function Add-EvidenceDateCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  $ParsedDate = [datetime]::MinValue
  $ParseOk = [datetime]::TryParseExact(
    $Text,
    'yyyy-MM-dd',
    [System.Globalization.CultureInfo]::InvariantCulture,
    [System.Globalization.DateTimeStyles]::None,
    [ref]$ParsedDate
  )
  if (-not $ParseOk) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($ParsedDate.Date -gt [datetime]::Today) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Add-RequiredTextFragmentsCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [string[]]$RequiredFragments
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  foreach ($Fragment in $RequiredFragments) {
    if ($Text.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      $Invalid.Add($Field) | Out-Null
      return
    }
  }
}

function Add-TextExclusionCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [string[]]$ExcludedPatterns
  )

  if (Test-MissingOrPendingText -Value $Value) {
    return
  }

  $Text = ([string]$Value).Trim()
  foreach ($Pattern in $ExcludedPatterns) {
    if ([System.Text.RegularExpressions.Regex]::IsMatch($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)) {
      if (-not $Invalid.Contains($Field)) {
        $Invalid.Add($Field) | Out-Null
      }
      return
    }
  }
}

function ConvertTo-BlockerToken {
  param([string]$Value)

  $Token = ([string]$Value).Trim().ToLowerInvariant()
  $Token = [System.Text.RegularExpressions.Regex]::Replace($Token, '[^a-z0-9]+', '_')
  $Token = $Token.Trim('_')
  if ([string]::IsNullOrWhiteSpace($Token)) {
    return 'required_detail'
  }
  return $Token
}

function Add-RequiredNoteFragmentsCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Blockers,
    [string]$Field,
    [object]$Value,
    [string[]]$RequiredFragments
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  foreach ($Fragment in $RequiredFragments) {
    if ($Text.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
      $Blockers.Add(('{0}_must_reference_{1}' -f $Field, (ConvertTo-BlockerToken -Value $Fragment))) | Out-Null
    }
  }
}

function Add-AnyTextFragmentCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [string[]]$AllowedFragments
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  foreach ($Fragment in $AllowedFragments) {
    if ($Text.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return
    }
  }

  $Invalid.Add($Field) | Out-Null
}

function Add-MetricMeasurementToolCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  $Text = ([string]$Value).Trim()
  $MetricEvidencePresent = $Text.IndexOf('metric', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
    $Text.IndexOf('millimeter', [System.StringComparison]::OrdinalIgnoreCase) -ge 0 -or
    [System.Text.RegularExpressions.Regex]::IsMatch($Text, '(^|[^a-z0-9])mm([^a-z0-9]|$)', [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  $ImperialOrNegatedMetricPresent = [System.Text.RegularExpressions.Regex]::IsMatch(
    $Text,
    'non[\s-]?metric|imperial|inch|inches',
    [System.Text.RegularExpressions.RegexOptions]::IgnoreCase
  )

  if (-not $MetricEvidencePresent -or $ImperialOrNegatedMetricPresent) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Add-IfMissingPositiveNumber {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value
  )

  if (-not (Test-PositiveNumber -Value $Value)) {
    $Target.Add($Field) | Out-Null
  }
}

function Add-MeasurementBoundsCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [double]$Minimum,
    [double]$Maximum
  )

  if ($null -eq $Value -or ($Value -is [string] -and (Test-MissingOrPendingText -Value $Value))) {
    $Missing.Add($Field) | Out-Null
    return
  }

  if (-not (Test-JsonNumber -Value $Value)) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number)) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($Number -le 0) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($Number -lt $Minimum -or $Number -gt $Maximum) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Test-JsonNumber {
  param([object]$Value)

  if ($null -eq $Value -or $Value -is [string] -or $Value -is [bool]) {
    return $false
  }

  return $Value -is [byte] -or
    $Value -is [sbyte] -or
    $Value -is [int16] -or
    $Value -is [uint16] -or
    $Value -is [int] -or
    $Value -is [uint32] -or
    $Value -is [long] -or
    $Value -is [uint64] -or
    $Value -is [single] -or
    $Value -is [double] -or
    $Value -is [decimal]
}

function Get-PositiveNumberOrNull {
  param([object]$Value)

  if ($null -eq $Value) {
    return $null
  }
  if (-not (Test-JsonNumber -Value $Value)) {
    return $null
  }

  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number) -or $Number -le 0) {
    return $null
  }
  return $Number
}

function Add-MustBeLessThanCheck {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$Value,
    [string]$ParentField,
    [object]$ParentValue
  )

  $Number = Get-PositiveNumberOrNull -Value $Value
  $ParentNumber = Get-PositiveNumberOrNull -Value $ParentValue
  if ($null -eq $Number -or $null -eq $ParentNumber) {
    return
  }

  if ($Number -ge $ParentNumber) {
    $Target.Add(('{0}_must_be_less_than_{1}' -f $Field, $ParentField)) | Out-Null
  }
}

function ConvertTo-SafetyBoolean {
  param([object]$Value)

  if ($null -eq $Value) {
    return [ordered]@{
      present = $false
      valid = $false
      value = $false
    }
  }

  if ($Value -is [bool]) {
    return [ordered]@{
      present = $true
      valid = $true
      value = [bool]$Value
    }
  }

  if (Test-MissingOrPendingText -Value $Value) {
    return [ordered]@{
      present = $false
      valid = $false
      value = $false
    }
  }

  return [ordered]@{
    present = $true
    valid = $false
    value = $false
  }
}

function Add-RequiredTrueBooleanCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Blockers,
    [string]$Field,
    [object]$Value
  )

  $BooleanValue = ConvertTo-SafetyBoolean -Value $Value
  if (-not [bool]$BooleanValue.present) {
    $Missing.Add($Field) | Out-Null
    return
  }
  if (-not [bool]$BooleanValue.valid) {
    $Invalid.Add($Field) | Out-Null
    return
  }
  if (-not [bool]$BooleanValue.value) {
    $Blockers.Add($Field + '_must_be_true') | Out-Null
  }
}

function Add-RepeatabilityMaxDeltaCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Blockers,
    [string]$Field,
    [object]$Value,
    [double]$Maximum
  )

  if ($null -eq $Value -or ($Value -is [string] -and (Test-MissingOrPendingText -Value $Value))) {
    $Missing.Add($Field) | Out-Null
    return
  }

  if (-not (Test-JsonNumber -Value $Value)) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  $Number = 0.0
  if (-not [double]::TryParse([string]$Value, [ref]$Number) -or $Number -lt 0) {
    $Invalid.Add($Field) | Out-Null
    return
  }

  if ($Number -gt $Maximum) {
    $Blockers.Add(('{0}_exceeds_{1}mm_limit' -f $Field, $Maximum)) | Out-Null
  }
}

function Test-PresentText {
  param([object]$Value)

  return -not (Test-MissingOrPendingText -Value $Value)
}

function Add-MarkedZoneSpecificityCheck {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$LeftValue,
    [object]$RightValue
  )

  if (-not (Test-PresentText -Value $LeftValue) -or -not (Test-PresentText -Value $RightValue)) {
    return
  }

  $LeftText = ([string]$LeftValue).Trim()
  $RightText = ([string]$RightValue).Trim()
  if ([string]::Equals($LeftText, $RightText, [System.StringComparison]::OrdinalIgnoreCase)) {
    $Target.Add(('marked_zones.{0}_left_right_references_must_be_distinct' -f $Field)) | Out-Null
  }
}

function Add-DistinctEvidenceReferenceCheck {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [string]$Field,
    [object]$LeftValue,
    [object]$RightValue
  )

  if (-not (Test-PresentText -Value $LeftValue) -or -not (Test-PresentText -Value $RightValue)) {
    return
  }

  $LeftText = ([string]$LeftValue).Trim()
  $RightText = ([string]$RightValue).Trim()
  if ([string]::Equals($LeftText, $RightText, [System.StringComparison]::OrdinalIgnoreCase)) {
    $Target.Add(('{0}_left_right_references_must_be_distinct' -f $Field)) | Out-Null
  }
}

function Add-IdenticalLeftRightMeasurementProfileCheck {
  param(
    [System.Collections.Generic.List[string]]$Target,
    [object]$LeftMeasurements,
    [object]$RightMeasurements,
    [string[]]$Fields
  )

  $ComparedCount = 0
  $IdenticalCount = 0
  foreach ($Field in $Fields) {
    $LeftNumber = Get-PositiveNumberOrNull -Value (Get-PropertyValue -Payload $LeftMeasurements -Name $Field)
    $RightNumber = Get-PositiveNumberOrNull -Value (Get-PropertyValue -Payload $RightMeasurements -Name $Field)
    if ($null -eq $LeftNumber -or $null -eq $RightNumber) {
      return
    }
    $ComparedCount += 1
    if ([double]$LeftNumber -eq [double]$RightNumber) {
      $IdenticalCount += 1
    }
  }

  if ($ComparedCount -eq $Fields.Count -and $IdenticalCount -eq $Fields.Count) {
    $Target.Add('left_right_independence.all_required_numeric_measurements_identical_requires_recheck') | Out-Null
  }
}

$RequiredMeasurementFields = @(
  'forearm_circumference_25mm_below_elbow_crease',
  'forearm_circumference_mid_forearm',
  'forearm_circumference_40mm_above_wrist_crease',
  'forearm_length_elbow_crease_to_wrist_crease',
  'outer_forearm_usable_panel_length',
  'upper_strap_allowed_band_width',
  'lower_strap_allowed_band_width',
  'bone_ridge_relief_length',
  'inner_forearm_no_pressure_zone_width',
  'wrist_clearance_gap'
)

$MeasurementBoundsMm = [ordered]@{
  forearm_circumference_25mm_below_elbow_crease = [ordered]@{ min = 100; max = 450 }
  forearm_circumference_mid_forearm = [ordered]@{ min = 90; max = 420 }
  forearm_circumference_40mm_above_wrist_crease = [ordered]@{ min = 80; max = 360 }
  forearm_length_elbow_crease_to_wrist_crease = [ordered]@{ min = 150; max = 420 }
  outer_forearm_usable_panel_length = [ordered]@{ min = 75; max = 350 }
  upper_strap_allowed_band_width = [ordered]@{ min = 20; max = 90 }
  lower_strap_allowed_band_width = [ordered]@{ min = 20; max = 80 }
  bone_ridge_relief_length = [ordered]@{ min = 75; max = 350 }
  inner_forearm_no_pressure_zone_width = [ordered]@{ min = 20; max = 140 }
  wrist_clearance_gap = [ordered]@{ min = 10; max = 120 }
}

$RequiredMarkedZoneFields = @(
  'inner_elbow_crease_boundary',
  'wrist_bone_boundary',
  'radius_ridge_relief',
  'ulna_ridge_relief',
  'outer_forearm_cable_route',
  'quick_release_reach_zone',
  'glove_removal_path'
)

$SafetyScreenFields = @(
  'pain',
  'tingling',
  'numbness',
  'cold_fingers',
  'discoloration',
  'hand_weakness',
  'wrist_pain',
  'sharp_pressure',
  'reduced_finger_motion',
  'loss_of_grip_strength'
)

$RepeatabilityMaxDeltaMm = 5.0
$RequiredRepeatabilityFields = @(
  'second_pass_completed',
  'max_delta_mm',
  'all_required_measurements_within_5mm'
)

$RequiredLeftRightIndependenceTrueFields = @(
  'left_arm_measured_separately',
  'right_arm_measured_separately',
  'side_labels_verified',
  'values_not_copied_between_sides'
)

$RequiredLeftRightIndependenceReferenceFields = @(
  'left_measurement_reference',
  'right_measurement_reference',
  'independence_notes'
)
$RequiredLeftRightIndependenceNoteFragments = @(
  'left',
  'right',
  'separate',
  'side label'
)

$RequiredMeasurementConditionTrueFields = @(
  'no_tissue_compression_used',
  'no_wrist_bone_compression_used',
  'metric_tool_used',
  'arm_relaxed_palm_neutral_or_exception_recorded',
  'stop_conditions_briefed'
)

$RequiredMeasurementConditionReferenceFields = @(
  'condition_notes'
)
$RequiredMeasurementConditionNoteFragments = @(
  'no tissue',
  'wrist',
  'metric',
  'stop'
)

$RequiredLandmarkConfirmationTrueFields = @(
  'inner_elbow_crease_boundary_confirmed',
  'wrist_bone_boundary_confirmed',
  'radius_ulna_relief_paths_confirmed',
  'outer_forearm_cable_route_confirmed',
  'quick_release_reach_zone_confirmed',
  'glove_removal_path_confirmed',
  'skin_safe_marking_used'
)

$RequiredLandmarkConfirmationReferenceFields = @(
  'landmark_notes'
)
$RequiredLandmarkConfirmationNoteFragments = @(
  'inner elbow',
  'wrist',
  'radius',
  'ulna',
  'cable',
  'quick',
  'release',
  'glove',
  'skin',
  'safe'
)

$ExcludedMeasurementMethodPatterns = @(
  '\bcalipers?\b',
  'hard\s+calipers?',
  'rigid\s+calipers?',
  'with\s+(?:tissue\s+)?compression',
  'under\s+(?:tissue\s+)?compression',
  '\bcompressive\b'
)

$ExcludedMeasurementPosturePatterns = @(
  'under\s+load',
  '\bloaded\b',
  '\bweighted\b',
  '\bforced\b',
  '\bclench(?:ed|ing)?\b',
  '\bgripping\b'
)

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultTemplatePath } else { Resolve-IntakePath -Path $MeasurementPath }
$UsingTemplate = [string]::IsNullOrWhiteSpace($MeasurementPath)
$Exists = Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$MeasurementConsistencyViolations = New-Object System.Collections.Generic.List[string]
$MarkedZoneSpecificityViolations = New-Object System.Collections.Generic.List[string]
$RepeatabilityBlockers = New-Object System.Collections.Generic.List[string]
$LeftRightIndependenceBlockers = New-Object System.Collections.Generic.List[string]
$MeasurementConditionBlockers = New-Object System.Collections.Generic.List[string]
$LandmarkConfirmationBlockers = New-Object System.Collections.Generic.List[string]
$MeasurementNoteBlockers = New-Object System.Collections.Generic.List[string]
$SafetyBlockers = New-Object System.Collections.Generic.List[string]
$Payload = $null
$ParseOk = $false
$ExitCode = 0
$Status = 'pending_measurements'

if (-not $Exists) {
  $Status = 'missing_measurement_file'
  $ExitCode = 1
} else {
  try {
    $Payload = Get-Content -LiteralPath $ResolvedMeasurementPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $ParseOk = $true
  } catch {
    $Status = 'invalid_measurement_json'
    $ExitCode = 1
    $InvalidFields.Add('json_parse') | Out-Null
  }
}

if ($ParseOk) {
  if ([string](Get-PropertyValue -Payload $Payload -Name 'kind' -Default '') -ne 'francis.fr017.measurements.v1') {
    $InvalidFields.Add('kind') | Out-Null
  }
  if ([string](Get-PropertyValue -Payload $Payload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
    $InvalidFields.Add('component') | Out-Null
  }
  if ([string](Get-PropertyValue -Payload $Payload -Name 'units' -Default '') -ne 'mm') {
    $InvalidFields.Add('units') | Out-Null
  }

  $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
  Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
  Add-IfMissingText -Target $MissingFields -Field 'evidence.observer' -Value (Get-PropertyValue -Payload $Evidence -Name 'observer')
  Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value (Get-PropertyValue -Payload $Evidence -Name 'pilot_id')
  Add-MetricMeasurementToolCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.measurement_tool' -Value (Get-PropertyValue -Payload $Evidence -Name 'measurement_tool')
  Add-RequiredTextFragmentsCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.method' -Value (Get-PropertyValue -Payload $Evidence -Name 'method') -RequiredFragments @('flexible', 'no tissue compression')
  Add-TextExclusionCheck -Invalid $InvalidFields -Field 'evidence.method' -Value (Get-PropertyValue -Payload $Evidence -Name 'method') -ExcludedPatterns $ExcludedMeasurementMethodPatterns
  Add-RequiredTextFragmentsCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.posture' -Value (Get-PropertyValue -Payload $Evidence -Name 'posture') -RequiredFragments @('arm relaxed', 'palm neutral')
  Add-TextExclusionCheck -Invalid $InvalidFields -Field 'evidence.posture' -Value (Get-PropertyValue -Payload $Evidence -Name 'posture') -ExcludedPatterns $ExcludedMeasurementPosturePatterns

  $Sides = Get-PropertyValue -Payload $Payload -Name 'sides'
  $LeftMeasurements = Get-PropertyValue -Payload $Sides -Name 'left'
  $RightMeasurements = Get-PropertyValue -Payload $Sides -Name 'right'
  $MarkedZones = Get-PropertyValue -Payload $Payload -Name 'marked_zones'
  $Repeatability = Get-PropertyValue -Payload $Payload -Name 'repeatability'
  foreach ($Side in @('left', 'right')) {
    $SideMeasurements = Get-PropertyValue -Payload $Sides -Name $Side
    $InvalidCountBeforeSideMeasurements = $InvalidFields.Count
    foreach ($Field in $RequiredMeasurementFields) {
      $Bounds = $MeasurementBoundsMm[$Field]
      Add-MeasurementBoundsCheck -Missing $MissingFields -Invalid $InvalidFields -Field ('sides.{0}.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $SideMeasurements -Name $Field) -Minimum ([double]$Bounds.min) -Maximum ([double]$Bounds.max)
    }

    if ($InvalidFields.Count -eq $InvalidCountBeforeSideMeasurements) {
      $ForearmLength = Get-PropertyValue -Payload $SideMeasurements -Name 'forearm_length_elbow_crease_to_wrist_crease'
      $MidForearmCircumference = Get-PropertyValue -Payload $SideMeasurements -Name 'forearm_circumference_mid_forearm'
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.outer_forearm_usable_panel_length' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'outer_forearm_usable_panel_length') -ParentField ('sides.{0}.forearm_length_elbow_crease_to_wrist_crease' -f $Side) -ParentValue $ForearmLength
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.bone_ridge_relief_length' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'bone_ridge_relief_length') -ParentField ('sides.{0}.forearm_length_elbow_crease_to_wrist_crease' -f $Side) -ParentValue $ForearmLength
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.upper_strap_allowed_band_width' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'upper_strap_allowed_band_width') -ParentField ('sides.{0}.forearm_length_elbow_crease_to_wrist_crease' -f $Side) -ParentValue $ForearmLength
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.lower_strap_allowed_band_width' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'lower_strap_allowed_band_width') -ParentField ('sides.{0}.forearm_length_elbow_crease_to_wrist_crease' -f $Side) -ParentValue $ForearmLength
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.wrist_clearance_gap' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'wrist_clearance_gap') -ParentField ('sides.{0}.forearm_length_elbow_crease_to_wrist_crease' -f $Side) -ParentValue $ForearmLength
      Add-MustBeLessThanCheck -Target $MeasurementConsistencyViolations -Field ('sides.{0}.inner_forearm_no_pressure_zone_width' -f $Side) -Value (Get-PropertyValue -Payload $SideMeasurements -Name 'inner_forearm_no_pressure_zone_width') -ParentField ('sides.{0}.forearm_circumference_mid_forearm' -f $Side) -ParentValue $MidForearmCircumference
    }

    $SideZones = Get-PropertyValue -Payload $MarkedZones -Name $Side
    foreach ($Field in $RequiredMarkedZoneFields) {
      Add-IfMissingText -Target $MissingFields -Field ('marked_zones.{0}.{1}' -f $Side, $Field) -Value (Get-PropertyValue -Payload $SideZones -Name $Field)
    }

    $SideRepeatability = Get-PropertyValue -Payload $Repeatability -Name $Side
    Add-RequiredTrueBooleanCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $RepeatabilityBlockers -Field ('repeatability.{0}.second_pass_completed' -f $Side) -Value (Get-PropertyValue -Payload $SideRepeatability -Name 'second_pass_completed')
    Add-RepeatabilityMaxDeltaCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $RepeatabilityBlockers -Field ('repeatability.{0}.max_delta_mm' -f $Side) -Value (Get-PropertyValue -Payload $SideRepeatability -Name 'max_delta_mm') -Maximum $RepeatabilityMaxDeltaMm
    Add-RequiredTrueBooleanCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $RepeatabilityBlockers -Field ('repeatability.{0}.all_required_measurements_within_5mm' -f $Side) -Value (Get-PropertyValue -Payload $SideRepeatability -Name 'all_required_measurements_within_5mm')
  }

  $LeftMarkedZones = Get-PropertyValue -Payload $MarkedZones -Name 'left'
  $RightMarkedZones = Get-PropertyValue -Payload $MarkedZones -Name 'right'
  foreach ($Field in $RequiredMarkedZoneFields) {
    Add-MarkedZoneSpecificityCheck -Target $MarkedZoneSpecificityViolations -Field $Field -LeftValue (Get-PropertyValue -Payload $LeftMarkedZones -Name $Field) -RightValue (Get-PropertyValue -Payload $RightMarkedZones -Name $Field)
  }

  Add-IdenticalLeftRightMeasurementProfileCheck -Target $LeftRightIndependenceBlockers -LeftMeasurements $LeftMeasurements -RightMeasurements $RightMeasurements -Fields $RequiredMeasurementFields

  $LeftRightIndependence = Get-PropertyValue -Payload $Payload -Name 'left_right_independence'
  foreach ($Field in $RequiredLeftRightIndependenceTrueFields) {
    Add-RequiredTrueBooleanCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $LeftRightIndependenceBlockers -Field ('left_right_independence.{0}' -f $Field) -Value (Get-PropertyValue -Payload $LeftRightIndependence -Name $Field)
  }
  foreach ($Field in $RequiredLeftRightIndependenceReferenceFields) {
    Add-IfMissingText -Target $MissingFields -Field ('left_right_independence.{0}' -f $Field) -Value (Get-PropertyValue -Payload $LeftRightIndependence -Name $Field)
  }
  Add-DistinctEvidenceReferenceCheck -Target $LeftRightIndependenceBlockers -Field 'left_right_independence.measurement_reference' -LeftValue (Get-PropertyValue -Payload $LeftRightIndependence -Name 'left_measurement_reference') -RightValue (Get-PropertyValue -Payload $LeftRightIndependence -Name 'right_measurement_reference')
  Add-RequiredNoteFragmentsCheck -Missing $MissingFields -Blockers $MeasurementNoteBlockers -Field 'left_right_independence.independence_notes' -Value (Get-PropertyValue -Payload $LeftRightIndependence -Name 'independence_notes') -RequiredFragments $RequiredLeftRightIndependenceNoteFragments

  $MeasurementConditions = Get-PropertyValue -Payload $Payload -Name 'measurement_conditions'
  foreach ($Field in $RequiredMeasurementConditionTrueFields) {
    Add-RequiredTrueBooleanCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $MeasurementConditionBlockers -Field ('measurement_conditions.{0}' -f $Field) -Value (Get-PropertyValue -Payload $MeasurementConditions -Name $Field)
  }
  foreach ($Field in $RequiredMeasurementConditionReferenceFields) {
    Add-IfMissingText -Target $MissingFields -Field ('measurement_conditions.{0}' -f $Field) -Value (Get-PropertyValue -Payload $MeasurementConditions -Name $Field)
  }
  Add-RequiredNoteFragmentsCheck -Missing $MissingFields -Blockers $MeasurementNoteBlockers -Field 'measurement_conditions.condition_notes' -Value (Get-PropertyValue -Payload $MeasurementConditions -Name 'condition_notes') -RequiredFragments $RequiredMeasurementConditionNoteFragments

  $LandmarkConfirmation = Get-PropertyValue -Payload $Payload -Name 'landmark_confirmation'
  foreach ($Field in $RequiredLandmarkConfirmationTrueFields) {
    Add-RequiredTrueBooleanCheck -Missing $MissingFields -Invalid $InvalidFields -Blockers $LandmarkConfirmationBlockers -Field ('landmark_confirmation.{0}' -f $Field) -Value (Get-PropertyValue -Payload $LandmarkConfirmation -Name $Field)
  }
  foreach ($Field in $RequiredLandmarkConfirmationReferenceFields) {
    Add-IfMissingText -Target $MissingFields -Field ('landmark_confirmation.{0}' -f $Field) -Value (Get-PropertyValue -Payload $LandmarkConfirmation -Name $Field)
  }
  Add-RequiredNoteFragmentsCheck -Missing $MissingFields -Blockers $MeasurementNoteBlockers -Field 'landmark_confirmation.landmark_notes' -Value (Get-PropertyValue -Payload $LandmarkConfirmation -Name 'landmark_notes') -RequiredFragments $RequiredLandmarkConfirmationNoteFragments

  $SafetyScreen = Get-PropertyValue -Payload $Payload -Name 'safety_screen'
  foreach ($Field in $SafetyScreenFields) {
    $Value = Get-PropertyValue -Payload $SafetyScreen -Name $Field
    $SafetyValue = ConvertTo-SafetyBoolean -Value $Value
    if (-not [bool]$SafetyValue.present) {
      $MissingFields.Add('safety_screen.' + $Field) | Out-Null
      continue
    }
    if (-not [bool]$SafetyValue.valid) {
      $InvalidFields.Add('safety_screen.' + $Field) | Out-Null
      continue
    }
    if ([bool]$SafetyValue.value) {
      $SafetyBlockers.Add($Field) | Out-Null
    }
  }

  if ($SafetyBlockers.Count -gt 0) {
    $Status = 'failed_requires_redesign_or_medical_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $MeasurementConsistencyViolations.Count -gt 0 -or $MarkedZoneSpecificityViolations.Count -gt 0 -or $RepeatabilityBlockers.Count -gt 0 -or $LeftRightIndependenceBlockers.Count -gt 0 -or $MeasurementConditionBlockers.Count -gt 0 -or $LandmarkConfirmationBlockers.Count -gt 0 -or $MeasurementNoteBlockers.Count -gt 0) {
    $Status = 'invalid_measurement_record'
    $ExitCode = 1
  } elseif ($MissingFields.Count -gt 0 -or $UsingTemplate) {
    $Status = 'pending_measurements'
  } else {
    $Status = 'ready_for_non_powered_mockup_patterning'
  }
}

$Output = [ordered]@{
  kind = 'francis.fr017.measurement_intake'
  mode = $Mode
  status = $Status
  measurement_path = $ResolvedMeasurementPath
  using_template = $UsingTemplate
  parse_ok = $ParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  fr018_implementation_cleared = $false
  units_required = 'mm'
  units_value_contract = 'Top-level units must be exactly "mm". Inch, centimeter, mixed-unit, or omitted unit records are invalid because all FR-017 measurement values feed millimeter-only downstream gates.'
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated measurement evidence is invalid because it cannot be completed evidence.'
  measurement_tool_contract = 'Measurement evidence.measurement_tool must identify a metric or millimeter-capable measuring tool and must not claim inch, imperial, non-metric, or mixed-unit collection. Tool text that omits metric/mm/millimeter capability or includes imperial/negated metric wording is invalid because FR-017 measurement units are millimeters.'
  measurement_method_contract = 'Measurement evidence.method must preserve flexible measuring-tool language and explicitly state no tissue compression. Method text that omits flexible collection or no tissue compression is invalid.'
  measurement_method_exclusions_contract = 'Measurement evidence.method must not include caliper, hard/rigid measuring tool, compressive, with-compression, or under-compression collection language. These conditions make FR-017 measurement evidence unsafe or unreliable even if flexible/no-compression wording is also present.'
  measurement_posture_contract = 'Measurement evidence.posture must preserve arm relaxed and palm neutral language. Posture exceptions must be recorded without removing relaxed/neutral baseline wording.'
  measurement_posture_exclusions_contract = 'Measurement evidence.posture must not include loaded, weighted, forced, clenched, gripping, or under-load collection language. These conditions make FR-017 measurement evidence unsafe or unreliable even if the relaxed/neutral baseline words are also present.'
  placeholder_value_contract = 'Placeholder text such as PENDING is treated as missing evidence case-insensitively and after trimming. Lowercase, padded, or whitespace-only placeholders cannot satisfy required FR-017 measurement fields.'
  measurement_number_value_contract = 'Use unquoted JSON numbers for all measurement fields. Quoted numeric strings are invalid. PENDING is allowed only in templates and is treated as missing evidence.'
  measurement_bounds_contract = 'Measurement bounds are broad human-scale sanity checks only. Passing them does not approve fit, fabrication, load-bearing use, or powered testing.'
  measurement_consistency_contract = 'Derived measurement consistency checks reject contradictory dimensions, such as a usable panel length greater than the measured forearm length. Passing these checks is still not fit approval.'
  marked_zone_specificity_contract = 'Left and right marked-zone evidence references must be distinct for each required zone. Shared photo sets are allowed only when the left and right side labels or anchors are separately identifiable.'
  left_right_independence_contract = 'Left and right arms must be measured independently with side labels verified. The intake gate rejects records that state values were copied between sides, reuse the same measurement evidence reference for both arms, or report an exactly identical complete numeric profile across all required left/right measurements.'
  measurement_condition_contract = 'Measurement collection must explicitly confirm no tissue compression, no wrist-bone compression, metric tool use, neutral posture or a recorded posture exception, and stop-condition briefing. Any false condition blocks FR-017 progression because the measurement evidence is unsafe or unreliable.'
  landmark_confirmation_contract = 'Safety-critical forearm landmarks must be visibly confirmed before FR-017 measurement evidence can advance: inner elbow crease boundary, wrist-bone boundary, radius/ulna relief paths, outer cable route, quick-release reach zone, glove-removal path, and skin-safe marking method.'
  measurement_note_contract = 'Measurement evidence notes must be specific enough to audit the safety-critical context. Independence notes must mention separate left/right collection and side labels; condition notes must mention no-tissue/no-wrist-bone compression, metric tooling, and stop briefing; landmark notes must mention inner elbow, wrist, radius/ulna, cable route, quick release, glove path, and skin-safe marking.'
  measurement_bounds_mm = $MeasurementBoundsMm
  repeatability_value_contract = 'Use unquoted JSON boolean true for second-pass confirmation fields and an unquoted JSON number for max_delta_mm. max_delta_mm must be 0 through 5 mm inclusive. PENDING is allowed only in templates and is treated as missing evidence.'
  repeatability_max_delta_mm = $RepeatabilityMaxDeltaMm
  safety_screen_value_contract = 'Use unquoted JSON boolean false for absent symptoms. Use true only when the symptom is observed; any true symptom blocks FR-017 progression. Any string value such as yes/no/1/0/"true"/"false" is invalid.'
  required_measurement_fields = $RequiredMeasurementFields
  required_marked_zone_fields = $RequiredMarkedZoneFields
  required_repeatability_fields = $RequiredRepeatabilityFields
  required_left_right_independence_true_fields = $RequiredLeftRightIndependenceTrueFields
  required_left_right_independence_reference_fields = $RequiredLeftRightIndependenceReferenceFields
  required_left_right_independence_note_fragments = $RequiredLeftRightIndependenceNoteFragments
  required_measurement_condition_true_fields = $RequiredMeasurementConditionTrueFields
  required_measurement_condition_reference_fields = $RequiredMeasurementConditionReferenceFields
  required_measurement_condition_note_fragments = $RequiredMeasurementConditionNoteFragments
  required_landmark_confirmation_true_fields = $RequiredLandmarkConfirmationTrueFields
  required_landmark_confirmation_reference_fields = $RequiredLandmarkConfirmationReferenceFields
  required_landmark_confirmation_note_fragments = $RequiredLandmarkConfirmationNoteFragments
  excluded_measurement_method_patterns = $ExcludedMeasurementMethodPatterns
  excluded_measurement_posture_patterns = $ExcludedMeasurementPosturePatterns
  safety_screen_fields = $SafetyScreenFields
  missing_fields = @(Get-UniqueStringArray -Value $MissingFields.ToArray())
  invalid_fields = @(Get-UniqueStringArray -Value $InvalidFields.ToArray())
  measurement_consistency_violations = @(Get-UniqueStringArray -Value $MeasurementConsistencyViolations.ToArray())
  marked_zone_specificity_violations = @(Get-UniqueStringArray -Value $MarkedZoneSpecificityViolations.ToArray())
  repeatability_blockers = @(Get-UniqueStringArray -Value $RepeatabilityBlockers.ToArray())
  left_right_independence_blockers = @(Get-UniqueStringArray -Value $LeftRightIndependenceBlockers.ToArray())
  measurement_condition_blockers = @(Get-UniqueStringArray -Value $MeasurementConditionBlockers.ToArray())
  landmark_confirmation_blockers = @(Get-UniqueStringArray -Value $LandmarkConfirmationBlockers.ToArray())
  measurement_note_blockers = @(Get-UniqueStringArray -Value $MeasurementNoteBlockers.ToArray())
  safety_blockers = @(Get-UniqueStringArray -Value $SafetyBlockers.ToArray())
  next_actions = if ($Status -eq 'ready_for_non_powered_mockup_patterning') {
    @(
      'copy_measurements_into_FR-017_measurement_record',
      'build_non_powered_soft_cuff_mockup',
      'run_mannequin_interface_test_before_pilot_motion'
    )
  } else {
    @(
      'collect_left_right_measurements_separately',
      'mark_left_right_zone_boundaries',
      'confirm_safety_critical_landmarks_before_measurement_use',
      'complete_safety_screen_without_symptoms',
      'rerun_measurement_intake'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
