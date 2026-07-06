[CmdletBinding()]
param(
    [ValidateSet('Create')]
    [string]$Mode = 'Create',

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [Parameter(Mandatory = $true)]
    [string]$MeasurementPath,

    [string]$TemplatePath = '',

    [string]$EvidenceDate = '',

    [string]$Observer = '',

    [string]$BuildMethod = '',

    [string]$PaddingLayer = '',

    [string]$SemiRigidOuterLayer = '',

    [string]$UpperForearmStrap = '',

    [string]$LowerForearmStrap = '',

    [string]$QuickRelease = '',

    [string]$OuterForearmCableSleeve = '',

    [string]$NonLoadBearingAlignmentTabs = '',

    [string]$SensorPlaceholderBlanks = '',

    [switch]$ConfirmNonPoweredOnly,

    [switch]$ConfirmNoLoadBearingClaim,

    [switch]$ConfirmNoHardInnerForearmBuckles,

    [switch]$ConfirmNoInnerElbowCrossing,

    [switch]$ConfirmNoWristBonePressure,

    [switch]$ConfirmReleasesVisibleAndReachable,

    [switch]$ConfirmGloveRemovalPathPreserved,

    [switch]$ConfirmOuterForearmCableRouteOnly,

    [switch]$ConfirmStopOnSymptoms,

    [switch]$ConfirmLeftUpperStrapWidthMatchesMeasurement,

    [switch]$ConfirmLeftLowerStrapWidthMatchesMeasurement,

    [switch]$ConfirmLeftBoneReliefChannelPresent,

    [switch]$ConfirmLeftInnerForearmNoPressureZoneMarked,

    [switch]$ConfirmLeftWristClearanceKept,

    [switch]$ConfirmLeftQuickReleaseInstalledOuterOrLateral,

    [switch]$ConfirmLeftAlignmentTabsNonLoadBearing,

    [switch]$ConfirmLeftCableSleeveOuterRouteOnly,

    [switch]$ConfirmRightUpperStrapWidthMatchesMeasurement,

    [switch]$ConfirmRightLowerStrapWidthMatchesMeasurement,

    [switch]$ConfirmRightBoneReliefChannelPresent,

    [switch]$ConfirmRightInnerForearmNoPressureZoneMarked,

    [switch]$ConfirmRightWristClearanceKept,

    [switch]$ConfirmRightQuickReleaseInstalledOuterOrLateral,

    [switch]$ConfirmRightAlignmentTabsNonLoadBearing,

    [switch]$ConfirmRightCableSleeveOuterRouteOnly
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$MeasurementIntakeGateScript = Join-Path $PSScriptRoot 'fr017-measurement-intake.ps1'

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

function Test-MockupBuildMethod {
    param([string]$Value)

    if (Test-MissingOrPendingText -Value $Value) {
        return $false
    }

    $Text = $Value.Trim()
    if ($Text.IndexOf('non-powered', [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
        return $false
    }

    foreach ($Fragment in @('soft', 'semi-rigid', 'semi rigid')) {
        if ($Text.IndexOf($Fragment, [System.StringComparison]::OrdinalIgnoreCase) -ge 0) {
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

function Invoke-MeasurementIntakeGate {
    param([string]$ResolvedMeasurementPath)

    $PowerShellExe = (Get-Process -Id $PID).Path
    $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $MeasurementIntakeGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath
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

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
$ResolvedMeasurementPath = Resolve-Fr017Path -Path $MeasurementPath
$Status = 'created_mockup_build_record'
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$UpstreamMeasurementIntakeStatus = ''
$UpstreamMeasurementIntakeReady = $false
$UpstreamMeasurementIntakeExitCode = 1
$UpstreamMeasurementIntakeParseOk = $false

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

if ($ExitCode -eq 0) {
    if ([string]::Equals($ResolvedMeasurementPath, $DefaultTemplatePath, [System.StringComparison]::OrdinalIgnoreCase)) {
        $Status = 'measurement_path_targets_mockup_template'
        $ExitCode = 1
    } elseif (-not (Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf)) {
        $Status = 'missing_measurement_file'
        $ExitCode = 1
    }
}

if ($ExitCode -eq 0) {
    $MeasurementIntake = Invoke-MeasurementIntakeGate -ResolvedMeasurementPath $ResolvedMeasurementPath
    $UpstreamMeasurementIntakeExitCode = [int]$MeasurementIntake.exit_code
    $UpstreamMeasurementIntakeParseOk = [bool]$MeasurementIntake.parse_ok
    $UpstreamMeasurementIntakeStatus = if ([bool]$MeasurementIntake.parse_ok) { [string]$MeasurementIntake.payload.status } else { 'failed_measurement_intake_gate_parse' }
    $UpstreamMeasurementIntakeReady = [bool]$MeasurementIntake.parse_ok -and [int]$MeasurementIntake.exit_code -eq 0 -and $UpstreamMeasurementIntakeStatus -eq 'ready_for_non_powered_mockup_patterning'

    if (-not $UpstreamMeasurementIntakeReady) {
        $Status = 'upstream_measurement_intake_not_ready'
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
    if ([string]$Payload.kind -ne 'francis.fr017.mockup_build.v1') {
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
        if (-not (Test-MockupBuildMethod -Value $BuildMethod)) {
            $InvalidFields.Add('evidence.build_method') | Out-Null
        } else {
            $Evidence.build_method = $BuildMethod.Trim()
            $UpdatedFields.Add('evidence.build_method') | Out-Null
        }
        $Evidence.measurement_record_path = $ResolvedMeasurementPath
        $UpdatedFields.Add('evidence.measurement_record_path') | Out-Null
    }

    $Materials = $Payload.materials
    if ($null -eq $Materials) {
        $InvalidFields.Add('materials') | Out-Null
    } else {
        Set-RequiredText -Target $Materials -Field 'padding_layer' -Value $PaddingLayer -QualifiedField 'materials.padding_layer' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'semi_rigid_outer_layer' -Value $SemiRigidOuterLayer -QualifiedField 'materials.semi_rigid_outer_layer' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'upper_forearm_strap' -Value $UpperForearmStrap -QualifiedField 'materials.upper_forearm_strap' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'lower_forearm_strap' -Value $LowerForearmStrap -QualifiedField 'materials.lower_forearm_strap' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'quick_release' -Value $QuickRelease -QualifiedField 'materials.quick_release' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'outer_forearm_cable_sleeve' -Value $OuterForearmCableSleeve -QualifiedField 'materials.outer_forearm_cable_sleeve' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'non_load_bearing_alignment_tabs' -Value $NonLoadBearingAlignmentTabs -QualifiedField 'materials.non_load_bearing_alignment_tabs' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredText -Target $Materials -Field 'sensor_placeholder_blanks' -Value $SensorPlaceholderBlanks -QualifiedField 'materials.sensor_placeholder_blanks' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    }

    $Constraints = $Payload.constraints
    if ($null -eq $Constraints) {
        $InvalidFields.Add('constraints') | Out-Null
    } else {
        Set-RequiredTrue -Target $Constraints -Field 'non_powered_only' -Confirmed $ConfirmNonPoweredOnly.IsPresent -QualifiedField 'constraints.non_powered_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'no_load_bearing_claim' -Confirmed $ConfirmNoLoadBearingClaim.IsPresent -QualifiedField 'constraints.no_load_bearing_claim' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'no_hard_inner_forearm_buckles' -Confirmed $ConfirmNoHardInnerForearmBuckles.IsPresent -QualifiedField 'constraints.no_hard_inner_forearm_buckles' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'no_inner_elbow_crossing' -Confirmed $ConfirmNoInnerElbowCrossing.IsPresent -QualifiedField 'constraints.no_inner_elbow_crossing' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'no_wrist_bone_pressure' -Confirmed $ConfirmNoWristBonePressure.IsPresent -QualifiedField 'constraints.no_wrist_bone_pressure' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'releases_visible_and_reachable' -Confirmed $ConfirmReleasesVisibleAndReachable.IsPresent -QualifiedField 'constraints.releases_visible_and_reachable' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'glove_removal_path_preserved' -Confirmed $ConfirmGloveRemovalPathPreserved.IsPresent -QualifiedField 'constraints.glove_removal_path_preserved' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'outer_forearm_cable_route_only' -Confirmed $ConfirmOuterForearmCableRouteOnly.IsPresent -QualifiedField 'constraints.outer_forearm_cable_route_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        Set-RequiredTrue -Target $Constraints -Field 'stop_on_symptoms' -Confirmed $ConfirmStopOnSymptoms.IsPresent -QualifiedField 'constraints.stop_on_symptoms' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    }

    $Sides = $Payload.sides
    if ($null -eq $Sides) {
        $InvalidFields.Add('sides') | Out-Null
    } else {
        $Left = $Sides.left
        $Right = $Sides.right
        if ($null -eq $Left) {
            $InvalidFields.Add('sides.left') | Out-Null
        } else {
            Set-RequiredTrue -Target $Left -Field 'upper_strap_width_matches_measurement' -Confirmed $ConfirmLeftUpperStrapWidthMatchesMeasurement.IsPresent -QualifiedField 'sides.left.upper_strap_width_matches_measurement' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'lower_strap_width_matches_measurement' -Confirmed $ConfirmLeftLowerStrapWidthMatchesMeasurement.IsPresent -QualifiedField 'sides.left.lower_strap_width_matches_measurement' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'bone_relief_channel_present' -Confirmed $ConfirmLeftBoneReliefChannelPresent.IsPresent -QualifiedField 'sides.left.bone_relief_channel_present' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'inner_forearm_no_pressure_zone_marked' -Confirmed $ConfirmLeftInnerForearmNoPressureZoneMarked.IsPresent -QualifiedField 'sides.left.inner_forearm_no_pressure_zone_marked' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'wrist_clearance_kept' -Confirmed $ConfirmLeftWristClearanceKept.IsPresent -QualifiedField 'sides.left.wrist_clearance_kept' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'quick_release_installed_outer_or_lateral' -Confirmed $ConfirmLeftQuickReleaseInstalledOuterOrLateral.IsPresent -QualifiedField 'sides.left.quick_release_installed_outer_or_lateral' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'alignment_tabs_non_load_bearing' -Confirmed $ConfirmLeftAlignmentTabsNonLoadBearing.IsPresent -QualifiedField 'sides.left.alignment_tabs_non_load_bearing' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Left -Field 'cable_sleeve_outer_route_only' -Confirmed $ConfirmLeftCableSleeveOuterRouteOnly.IsPresent -QualifiedField 'sides.left.cable_sleeve_outer_route_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        }
        if ($null -eq $Right) {
            $InvalidFields.Add('sides.right') | Out-Null
        } else {
            Set-RequiredTrue -Target $Right -Field 'upper_strap_width_matches_measurement' -Confirmed $ConfirmRightUpperStrapWidthMatchesMeasurement.IsPresent -QualifiedField 'sides.right.upper_strap_width_matches_measurement' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'lower_strap_width_matches_measurement' -Confirmed $ConfirmRightLowerStrapWidthMatchesMeasurement.IsPresent -QualifiedField 'sides.right.lower_strap_width_matches_measurement' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'bone_relief_channel_present' -Confirmed $ConfirmRightBoneReliefChannelPresent.IsPresent -QualifiedField 'sides.right.bone_relief_channel_present' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'inner_forearm_no_pressure_zone_marked' -Confirmed $ConfirmRightInnerForearmNoPressureZoneMarked.IsPresent -QualifiedField 'sides.right.inner_forearm_no_pressure_zone_marked' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'wrist_clearance_kept' -Confirmed $ConfirmRightWristClearanceKept.IsPresent -QualifiedField 'sides.right.wrist_clearance_kept' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'quick_release_installed_outer_or_lateral' -Confirmed $ConfirmRightQuickReleaseInstalledOuterOrLateral.IsPresent -QualifiedField 'sides.right.quick_release_installed_outer_or_lateral' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'alignment_tabs_non_load_bearing' -Confirmed $ConfirmRightAlignmentTabsNonLoadBearing.IsPresent -QualifiedField 'sides.right.alignment_tabs_non_load_bearing' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
            Set-RequiredTrue -Target $Right -Field 'cable_sleeve_outer_route_only' -Confirmed $ConfirmRightCableSleeveOuterRouteOnly.IsPresent -QualifiedField 'sides.right.cable_sleeve_outer_route_only' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
        }
    }

    if ($InvalidFields.Count -gt 0) {
        $Status = 'invalid_mockup_record_input'
        $ExitCode = 1
    }
}

if ($ExitCode -eq 0) {
    $Generation = [ordered]@{
        generated_by = 'scripts/fr017-new-mockup-record.ps1'
        generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
        template_path = $ResolvedTemplatePath
        measurement_path = $ResolvedMeasurementPath
        output_path = $ResolvedOutputPath
        mockup_record_is_physical_validation_evidence = $false
        physical_validation_complete = $false
        stage17_completion_claim_allowed = $false
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
    kind = 'francis.fr017.mockup_record_initializer'
    mode = $Mode
    status = $Status
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    output_path = $ResolvedOutputPath
    output_exists = (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf)
    wrote_file = $WroteFile
    read_only_contract = $false
    writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
    writes_data = $WroteFile
    grants_execution_authority = $false
    grants_mutation_authority = $false
    upstream_measurement_intake_status = $UpstreamMeasurementIntakeStatus
    upstream_measurement_intake_ready = $UpstreamMeasurementIntakeReady
    upstream_measurement_intake_exit_code = $UpstreamMeasurementIntakeExitCode
    upstream_measurement_intake_parse_ok = $UpstreamMeasurementIntakeParseOk
    operator_supplied_mockup_input_recorded = $WroteFile
    mockup_record_is_physical_validation_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    mannequin_interface_test_complete = $false
    pilot_testing_cleared = $false
    powered_or_frame_coupled_testing_cleared = $false
    fr018_implementation_cleared = $false
    no_fake_validation_lock = 'This initializer records operator-supplied non-powered FR-017 mockup-build input only after measurement intake is ready. It does not mark physical validation complete, does not permit a Stage 17 completion claim, does not complete mannequin or pilot testing, does not clear powered or frame-coupled testing, and does not clear FR-018.'
    updated_fields = @($UpdatedFields.ToArray())
    invalid_fields = @($InvalidFields.ToArray())
    next_command = if ($WroteFile) { '.\scripts\fr017-mockup-readiness-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}"' -f $ResolvedMeasurementPath, $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
