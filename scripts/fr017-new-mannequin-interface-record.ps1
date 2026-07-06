[CmdletBinding()]
param(
  [ValidateSet('Status', 'Create')]
  [string]$Mode = 'Status',

  [string]$OutputPath = '',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Observer = '',

  [string]$MannequinOrArmFormId = '',

  [string]$FutureInterfaceMockGeometryRevision = '',

  [string]$CableSleeveMockId = '',

  [string]$LeftCuffRevision = '',

  [string]$RightCuffRevision = '',

  [switch]$ConfirmNonPoweredOnly,

  [switch]$ConfirmAllInterfaceMocksInstalled,

  [switch]$ConfirmAllInterfaceClearancesPassed,

  [string]$InterfaceNotes = '',

  [switch]$ConfirmFr163OuterRouteOnly,

  [switch]$ConfirmFr069NoPressureOrPalmCrossing,

  [switch]$ConfirmFr070NoPoweredAnchoring,

  [switch]$ConfirmFr145NoRaisedHardSpot,

  [switch]$ConfirmFr149NoPressureZonePlacement,

  [switch]$ConfirmLeftReleaseVisibleAndReachable,

  [switch]$ConfirmRightReleaseVisibleAndReachable,

  [switch]$ConfirmArmorDoesNotHideRelease,

  [switch]$ConfirmGloveAndWristRemovalPathsOpen,

  [switch]$ConfirmNoSnagDetected,

  [switch]$ConfirmNoCompressionDetected,

  [switch]$ConfirmNoReleaseHidden,

  [switch]$ConfirmNoWristPathBlocked,

  [switch]$ConfirmNoGlovePathBlocked,

  [switch]$ConfirmNoCableInnerElbowCrossing,

  [switch]$ConfirmNoCableWristBoneCrossing,

  [switch]$ConfirmNoCablePalmOrGripCrossing,

  [switch]$SnagDetected,

  [switch]$CompressionDetected,

  [switch]$ReleaseHidden,

  [switch]$WristPathBlocked,

  [switch]$GlovePathBlocked,

  [switch]$CableInnerElbowCrossing,

  [switch]$CableWristBoneCrossing,

  [switch]$CablePalmOrGripCrossing
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MockupGateScript = Join-Path $PSScriptRoot 'fr017-mockup-readiness-gate.ps1'

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

function Test-MannequinSubject {
  param([string]$Value)

  if (Test-MissingOrPendingText -Value $Value) {
    return $false
  }

  $Text = $Value.Trim()
  foreach ($ForbiddenFragment in @('pilot', 'human', 'wearer')) {
    if ($Text.IndexOf($ForbiddenFragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return $false
    }
  }

  foreach ($RequiredFragment in @('mannequin', 'arm-form', 'arm form')) {
    if ($Text.IndexOf($RequiredFragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
      return $true
    }
  }
  return $false
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
    [System.Collections.Generic.List[string]]$FailObservations,
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
    $FailObservations.Add($QualifiedField) | Out-Null
  }
  $UpdatedFields.Add($QualifiedField) | Out-Null
}

function Invoke-MockupReadinessGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $MockupGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath
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

$InterfaceIds = @(
  'fr032_left_forearm_frame',
  'fr033_right_forearm_frame',
  'fr043_left_elbow_joint',
  'fr044_right_elbow_joint',
  'fr045_left_wrist_joint',
  'fr046_right_wrist_joint',
  'fr066_left_glove_base',
  'fr067_right_glove_base',
  'fr068_palm_interface_ring',
  'fr184_forearm_armor'
)

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = if ([string]::IsNullOrWhiteSpace($OutputPath)) { '' } else { Resolve-Fr017Path -Path $OutputPath }
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { '' } else { Resolve-Fr017Path -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { '' } else { Resolve-Fr017Path -Path $MockupPath }
$CreateCommandTemplate = '.\scripts\fr017-new-mannequin-interface-record.ps1 -Mode Create -OutputPath <mannequin-interface-record.json> -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -EvidenceDate YYYY-MM-DD -Observer "<observer>" -MannequinOrArmFormId "<mannequin or arm form id>" -FutureInterfaceMockGeometryRevision "<future interface mock revision>" -CableSleeveMockId "<outer cable sleeve mock id>" -LeftCuffRevision "<left cuff revision>" -RightCuffRevision "<right cuff revision>" -ConfirmNonPoweredOnly -ConfirmAllInterfaceMocksInstalled -ConfirmAllInterfaceClearancesPassed -InterfaceNotes "<clearance notes>" -ConfirmFr163OuterRouteOnly -ConfirmFr069NoPressureOrPalmCrossing -ConfirmFr070NoPoweredAnchoring -ConfirmFr145NoRaisedHardSpot -ConfirmFr149NoPressureZonePlacement -ConfirmLeftReleaseVisibleAndReachable -ConfirmRightReleaseVisibleAndReachable -ConfirmArmorDoesNotHideRelease -ConfirmGloveAndWristRemovalPathsOpen -ConfirmNoSnagDetected -ConfirmNoCompressionDetected -ConfirmNoReleaseHidden -ConfirmNoWristPathBlocked -ConfirmNoGlovePathBlocked -ConfirmNoCableInnerElbowCrossing -ConfirmNoCableWristBoneCrossing -ConfirmNoCablePalmOrGripCrossing'
$MannequinInterfaceStatusCommandTemplate = '.\scripts\fr017-mannequin-interface-gate.ps1 -Mode Status -MeasurementPath <measurement-record.json> -MockupPath <mockup-record.json> -MannequinPath <mannequin-interface-record.json>'
$Status = if ($Mode -eq 'Status') { 'mannequin_interface_record_initializer_status' } else { 'created_mannequin_interface_record' }
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$FailObservations = New-Object System.Collections.Generic.List[string]
$TemplateParseOk = $false
$OutputPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedOutputPath)
$MeasurementPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath)
$MockupPathRequiredForCreate = [string]::IsNullOrWhiteSpace($ResolvedMockupPath)
$OutputPathTargetsTemplate = $false
$OutputFileExists = $false
$OutputParentExists = $false
$CandidateOutputPathReady = $false
$MeasurementPathTargetsMannequinTemplate = $false
$MockupPathTargetsMannequinTemplate = $false
$MeasurementFileExists = $false
$MockupFileExists = $false
$UpstreamMockupStatus = ''
$UpstreamMockupReady = $false
$UpstreamMockupExitCode = 0
$UpstreamMockupParseOk = $false

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
    $MeasurementPathTargetsMannequinTemplate = [string]::Equals($ResolvedMeasurementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MeasurementFileExists = Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf
    if ($MeasurementPathTargetsMannequinTemplate) {
      $Status = 'measurement_path_targets_mannequin_template'
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
    $MockupPathTargetsMannequinTemplate = [string]::Equals($ResolvedMockupPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)
    $MockupFileExists = Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf
    if ($MockupPathTargetsMannequinTemplate) {
      $Status = 'mockup_path_targets_mannequin_template'
      $ExitCode = 1
    } elseif (-not $MockupFileExists) {
      $Status = 'missing_mockup_file'
      $ExitCode = 1
    }
  }
}

if ($ExitCode -eq 0 -and -not [string]::IsNullOrWhiteSpace($ResolvedMeasurementPath) -and -not [string]::IsNullOrWhiteSpace($ResolvedMockupPath)) {
  $Upstream = Invoke-MockupReadinessGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath
  $UpstreamMockupExitCode = [int]$Upstream.exit_code
  $UpstreamMockupParseOk = [bool]$Upstream.parse_ok
  $UpstreamMockupStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_mockup_readiness_gate_parse' }
  $UpstreamMockupReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamMockupStatus -eq 'ready_for_mannequin_interface_test'

  if (-not $UpstreamMockupReady) {
    $Status = 'upstream_mockup_readiness_not_ready'
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
  if ([string]$Payload.kind -ne 'francis.fr017.mannequin_interface_test.v1') {
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
    $Evidence.mockup_readiness_record_path = $ResolvedMockupPath
    $UpdatedFields.Add('evidence.mockup_readiness_record_path') | Out-Null
    if (-not (Test-MannequinSubject -Value $MannequinOrArmFormId)) {
      $InvalidFields.Add('evidence.mannequin_or_arm_form_id') | Out-Null
    } else {
      $Evidence.mannequin_or_arm_form_id = $MannequinOrArmFormId.Trim()
      $UpdatedFields.Add('evidence.mannequin_or_arm_form_id') | Out-Null
    }
    Set-RequiredText -Target $Evidence -Field 'future_interface_mock_geometry_revision' -Value $FutureInterfaceMockGeometryRevision -QualifiedField 'evidence.future_interface_mock_geometry_revision' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'cable_sleeve_mock_id' -Value $CableSleeveMockId -QualifiedField 'evidence.cable_sleeve_mock_id' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  $TestArticle = $Payload.test_article
  if ($null -eq $TestArticle) {
    $InvalidFields.Add('test_article') | Out-Null
  } else {
    Set-RequiredText -Target $TestArticle -Field 'left_cuff_revision' -Value $LeftCuffRevision -QualifiedField 'test_article.left_cuff_revision' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $TestArticle -Field 'right_cuff_revision' -Value $RightCuffRevision -QualifiedField 'test_article.right_cuff_revision' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $TestArticle -Field 'non_powered_only' -Confirmed $ConfirmNonPoweredOnly.IsPresent -QualifiedField 'test_article.non_powered_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  $Interfaces = $Payload.interfaces
  if ($null -eq $Interfaces) {
    $InvalidFields.Add('interfaces') | Out-Null
  } else {
    foreach ($InterfaceId in $InterfaceIds) {
      $Interface = $Interfaces.PSObject.Properties[$InterfaceId]
      if ($null -eq $Interface) {
        $InvalidFields.Add('interfaces.' + $InterfaceId) | Out-Null
      } else {
        Set-RequiredTrue -Target $Interface.Value -Field 'mock_installed' -Confirmed $ConfirmAllInterfaceMocksInstalled.IsPresent -QualifiedField ('interfaces.{0}.mock_installed' -f $InterfaceId) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Interface.Value -Field 'clearance_passed' -Confirmed $ConfirmAllInterfaceClearancesPassed.IsPresent -QualifiedField ('interfaces.{0}.clearance_passed' -f $InterfaceId) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Interface.Value -Field 'notes' -Value $InterfaceNotes -QualifiedField ('interfaces.{0}.notes' -f $InterfaceId) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
      }
    }
  }

  $CableSensorChecks = $Payload.cable_sensor_checks
  if ($null -eq $CableSensorChecks) {
    $InvalidFields.Add('cable_sensor_checks') | Out-Null
  } else {
    Set-RequiredTrue -Target $CableSensorChecks -Field 'fr163_outer_route_only' -Confirmed $ConfirmFr163OuterRouteOnly.IsPresent -QualifiedField 'cable_sensor_checks.fr163_outer_route_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $CableSensorChecks -Field 'fr069_no_pressure_or_palm_crossing' -Confirmed $ConfirmFr069NoPressureOrPalmCrossing.IsPresent -QualifiedField 'cable_sensor_checks.fr069_no_pressure_or_palm_crossing' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $CableSensorChecks -Field 'fr070_no_powered_anchoring' -Confirmed $ConfirmFr070NoPoweredAnchoring.IsPresent -QualifiedField 'cable_sensor_checks.fr070_no_powered_anchoring' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $CableSensorChecks -Field 'fr145_no_raised_hard_spot' -Confirmed $ConfirmFr145NoRaisedHardSpot.IsPresent -QualifiedField 'cable_sensor_checks.fr145_no_raised_hard_spot' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $CableSensorChecks -Field 'fr149_no_pressure_zone_placement' -Confirmed $ConfirmFr149NoPressureZonePlacement.IsPresent -QualifiedField 'cable_sensor_checks.fr149_no_pressure_zone_placement' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  $ReleaseChecks = $Payload.release_checks
  if ($null -eq $ReleaseChecks) {
    $InvalidFields.Add('release_checks') | Out-Null
  } else {
    Set-RequiredTrue -Target $ReleaseChecks -Field 'left_release_visible_and_reachable' -Confirmed $ConfirmLeftReleaseVisibleAndReachable.IsPresent -QualifiedField 'release_checks.left_release_visible_and_reachable' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $ReleaseChecks -Field 'right_release_visible_and_reachable' -Confirmed $ConfirmRightReleaseVisibleAndReachable.IsPresent -QualifiedField 'release_checks.right_release_visible_and_reachable' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $ReleaseChecks -Field 'armor_does_not_hide_release' -Confirmed $ConfirmArmorDoesNotHideRelease.IsPresent -QualifiedField 'release_checks.armor_does_not_hide_release' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredTrue -Target $ReleaseChecks -Field 'glove_and_wrist_removal_paths_open' -Confirmed $ConfirmGloveAndWristRemovalPathsOpen.IsPresent -QualifiedField 'release_checks.glove_and_wrist_removal_paths_open' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  $FailObservationPayload = $Payload.fail_observations
  if ($null -eq $FailObservationPayload) {
    $InvalidFields.Add('fail_observations') | Out-Null
  } else {
    Set-RequiredFalse -Target $FailObservationPayload -Field 'snag_detected' -ConfirmedAbsent $ConfirmNoSnagDetected.IsPresent -Observed $SnagDetected.IsPresent -QualifiedField 'fail_observations.snag_detected' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'compression_detected' -ConfirmedAbsent $ConfirmNoCompressionDetected.IsPresent -Observed $CompressionDetected.IsPresent -QualifiedField 'fail_observations.compression_detected' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'release_hidden' -ConfirmedAbsent $ConfirmNoReleaseHidden.IsPresent -Observed $ReleaseHidden.IsPresent -QualifiedField 'fail_observations.release_hidden' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'wrist_path_blocked' -ConfirmedAbsent $ConfirmNoWristPathBlocked.IsPresent -Observed $WristPathBlocked.IsPresent -QualifiedField 'fail_observations.wrist_path_blocked' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'glove_path_blocked' -ConfirmedAbsent $ConfirmNoGlovePathBlocked.IsPresent -Observed $GlovePathBlocked.IsPresent -QualifiedField 'fail_observations.glove_path_blocked' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'cable_inner_elbow_crossing' -ConfirmedAbsent $ConfirmNoCableInnerElbowCrossing.IsPresent -Observed $CableInnerElbowCrossing.IsPresent -QualifiedField 'fail_observations.cable_inner_elbow_crossing' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'cable_wrist_bone_crossing' -ConfirmedAbsent $ConfirmNoCableWristBoneCrossing.IsPresent -Observed $CableWristBoneCrossing.IsPresent -QualifiedField 'fail_observations.cable_wrist_bone_crossing' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $FailObservationPayload -Field 'cable_palm_or_grip_crossing' -ConfirmedAbsent $ConfirmNoCablePalmOrGripCrossing.IsPresent -Observed $CablePalmOrGripCrossing.IsPresent -QualifiedField 'fail_observations.cable_palm_or_grip_crossing' -InvalidFields $InvalidFields -FailObservations $FailObservations -UpdatedFields $UpdatedFields
  }

  if ($FailObservations.Count -gt 0) {
    $Status = 'mannequin_fail_observation_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0) {
    $Status = 'invalid_mannequin_interface_record_input'
    $ExitCode = 1
  }
}

if ($Mode -eq 'Create' -and $ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-mannequin-interface-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    output_path = $ResolvedOutputPath
    mannequin_interface_record_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    pilot_testing_cleared = $false
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
  kind = 'francis.fr017.mannequin_interface_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  output_path = $ResolvedOutputPath
  template_exists = (Test-Path -LiteralPath $ResolvedTemplatePath -PathType Leaf)
  template_parse_ok = $TemplateParseOk
  output_path_required_for_create = $OutputPathRequiredForCreate
  measurement_path_required_for_create = $MeasurementPathRequiredForCreate
  mockup_path_required_for_create = $MockupPathRequiredForCreate
  output_path_targets_template = $OutputPathTargetsTemplate
  output_parent_exists = $OutputParentExists
  candidate_output_path_ready = $CandidateOutputPathReady
  measurement_path_targets_mannequin_template = $MeasurementPathTargetsMannequinTemplate
  mockup_path_targets_mannequin_template = $MockupPathTargetsMannequinTemplate
  measurement_file_exists = $MeasurementFileExists
  mockup_file_exists = $MockupFileExists
  output_exists = if ([string]::IsNullOrWhiteSpace($ResolvedOutputPath)) { $false } else { (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf) }
  wrote_file = $WroteFile
  read_only_contract = ($Mode -eq 'Status')
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_mockup_status = $UpstreamMockupStatus
  upstream_mockup_ready = $UpstreamMockupReady
  upstream_mockup_exit_code = $UpstreamMockupExitCode
  upstream_mockup_parse_ok = $UpstreamMockupParseOk
  operator_supplied_mannequin_interface_input_recorded = $WroteFile
  mannequin_interface_record_is_physical_validation_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  pilot_testing_cleared = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  fail_observations_recorded = @($FailObservations.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied non-powered FR-017 mannequin or arm-form interface input only after mockup readiness is ready. It does not mark physical validation complete, does not permit a Stage 17 completion claim, does not clear pilot testing, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  create_command_template = $CreateCommandTemplate
  mannequin_interface_status_command_template = $MannequinInterfaceStatusCommandTemplate
  next_command = if ($WroteFile) { '.\scripts\fr017-mannequin-interface-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedOutputPath } elseif ($Mode -eq 'Status' -and $ExitCode -eq 0) { $CreateCommandTemplate } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
