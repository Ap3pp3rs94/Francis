[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$MeasurementPath = '',

  [string]$MockupPath = '',

  [string]$MannequinPath = '',

  [string]$StaticFitPath = '',

  [string]$MovementPath = '',

  [string]$ReleaseCablePath = '',

  [string]$EngineeringReviewPath = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ReleaseCableGateScript = Join-Path $PSScriptRoot 'fr017-quick-release-cable-snag-gate.ps1'

function Resolve-GatePath {
  param([string]$Path)

  if ([System.IO.Path]::IsPathRooted($Path)) {
    return [System.IO.Path]::GetFullPath($Path)
  }
  return [System.IO.Path]::GetFullPath((Join-Path $RepoRoot $Path))
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

function Test-MissingOrPendingText {
  param([object]$Value)

  if ($null -eq $Value) {
    return $true
  }
  $Text = ([string]$Value).Trim()
  return [string]::IsNullOrWhiteSpace($Text) -or [string]::Equals($Text, 'PENDING', [System.StringComparison]::OrdinalIgnoreCase)
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

function Get-EvidenceDateOrNull {
  param([object]$Payload)

  $Evidence = Get-PropertyValue -Payload $Payload -Name 'evidence'
  $Value = Get-PropertyValue -Payload $Evidence -Name 'date'
  if (Test-MissingOrPendingText -Value $Value) {
    return $null
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
    return $null
  }

  return $ParsedDate.Date
}

function Add-ExactTextCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [string]$Field,
    [object]$Value,
    [string]$Expected
  )

  if (Test-MissingOrPendingText -Value $Value) {
    $Missing.Add($Field) | Out-Null
    return
  }

  if (-not [string]::Equals(([string]$Value).Trim(), $Expected, [System.StringComparison]::Ordinal)) {
    $Invalid.Add($Field) | Out-Null
  }
}

function Test-PresentText {
  param([object]$Value)

  return -not (Test-MissingOrPendingText -Value $Value)
}

function Add-PilotIdentityLinkageCheck {
  param(
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Violations,
    [object]$ReviewPilotId,
    [string]$ReleaseCableRecordPath
  )

  if (-not (Test-PresentText -Value $ReviewPilotId)) {
    return
  }

  try {
    $ReleaseCablePayload = Get-Content -LiteralPath $ReleaseCableRecordPath -Raw | ConvertFrom-Json -ErrorAction Stop
    $ReleaseCableEvidence = Get-PropertyValue -Payload $ReleaseCablePayload -Name 'evidence'
    $ReleaseCablePilotId = Get-PropertyValue -Payload $ReleaseCableEvidence -Name 'pilot_id' -Default ''
    if (-not (Test-PresentText -Value $ReleaseCablePilotId)) {
      $Invalid.Add('evidence.quick_release_cable_snag_record_path') | Out-Null
      return
    }
    if (-not [string]::Equals([string]$ReviewPilotId, [string]$ReleaseCablePilotId, [System.StringComparison]::OrdinalIgnoreCase)) {
      $Violations.Add('evidence.pilot_id_must_match_release_cable_pilot_id') | Out-Null
    }
  } catch {
    $Invalid.Add('evidence.quick_release_cable_snag_record_path') | Out-Null
  }
}

function Get-UpstreamArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  return @(ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Payload -Name $Name))
}

function Get-UpstreamObjectArrayProperty {
  param(
    [object]$Payload,
    [string]$Name
  )

  $Value = Get-PropertyValue -Payload $Payload -Name $Name
  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value)
  }
  return @($Value)
}

function Get-BoolState {
  param([object]$Value)

  if ($null -eq $Value) {
    return 'missing'
  }
  if ($Value -is [bool]) {
    if ($Value) {
      return 'true'
    }
    return 'false'
  }

  if (Test-MissingOrPendingText -Value $Value) {
    return 'missing'
  }
  return 'invalid'
}

function Add-RequiredTrueCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Redesign,
    [string]$Field,
    [object]$Value
  )

  $State = Get-BoolState -Value $Value
  if ($State -eq 'missing') {
    $Missing.Add($Field) | Out-Null
  } elseif ($State -eq 'invalid') {
    $Invalid.Add($Field) | Out-Null
  } elseif ($State -eq 'false') {
    $Redesign.Add($Field) | Out-Null
  }
}

function Add-RequiredFalseCheck {
  param(
    [System.Collections.Generic.List[string]]$Missing,
    [System.Collections.Generic.List[string]]$Invalid,
    [System.Collections.Generic.List[string]]$Fail,
    [string]$Field,
    [object]$Value
  )

  $State = Get-BoolState -Value $Value
  if ($State -eq 'missing') {
    $Missing.Add($Field) | Out-Null
  } elseif ($State -eq 'invalid') {
    $Invalid.Add($Field) | Out-Null
  } elseif ($State -eq 'true') {
    $Fail.Add($Field) | Out-Null
  }
}

function Invoke-ReleaseCableGate {
  param(
    [string]$ResolvedMeasurementPath,
    [string]$ResolvedMockupPath,
    [string]$ResolvedMannequinPath,
    [string]$ResolvedStaticFitPath,
    [string]$ResolvedMovementPath,
    [string]$ResolvedReleaseCablePath
  )

  $PowerShellExe = (Get-Process -Id $PID).Path
  $GateArgs = @(
    '-NoProfile',
    '-ExecutionPolicy',
    'Bypass',
    '-File',
    $ReleaseCableGateScript,
    '-Mode',
    'Status',
    '-MeasurementPath',
    $ResolvedMeasurementPath,
    '-MockupPath',
    $ResolvedMockupPath,
    '-MannequinPath',
    $ResolvedMannequinPath,
    '-StaticFitPath',
    $ResolvedStaticFitPath,
    '-MovementPath',
    $ResolvedMovementPath,
    '-ReleaseCablePath',
    $ResolvedReleaseCablePath
  )

  $RawOutput = & $PowerShellExe @GateArgs
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

$RequiredReviewConstraints = @(
  'documentation_package_reviewed',
  'measurement_record_reviewed',
  'mockup_record_reviewed',
  'mannequin_record_reviewed',
  'pilot_static_record_reviewed',
  'pilot_movement_record_reviewed',
  'quick_release_cable_record_reviewed',
  'no_load_bearing_claim_approved',
  'no_powered_testing_cleared',
  'no_frame_coupled_testing_cleared',
  'fr018_implementation_not_cleared',
  'redesign_items_closed_or_blocked'
)

$RequiredSafetyReview = @(
  'circulation_nerve_risk_reviewed',
  'quick_release_access_reviewed',
  'glove_wrist_removal_reviewed',
  'cable_route_reviewed',
  'symptom_fail_conditions_reviewed',
  'stop_conditions_preserved'
)

$RequiredFalseReviewDecision = @(
  'requires_redesign',
  'load_bearing_use_approved',
  'powered_testing_approved',
  'frame_coupled_testing_approved',
  'fr018_implementation_cleared'
)

$DefaultMeasurementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MEASUREMENTS-INPUT-TEMPLATE.json'
$DefaultMockupPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MOCKUP-BUILD-INPUT-TEMPLATE.json'
$DefaultMannequinPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-MANNEQUIN-INTERFACE-INPUT-TEMPLATE.json'
$DefaultStaticFitPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-STATIC-FIT-INPUT-TEMPLATE.json'
$DefaultMovementPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-PILOT-MOVEMENT-INPUT-TEMPLATE.json'
$DefaultReleaseCablePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-QUICK-RELEASE-CABLE-SNAG-INPUT-TEMPLATE.json'
$DefaultEngineeringReviewPath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json'
$ResolvedMeasurementPath = if ([string]::IsNullOrWhiteSpace($MeasurementPath)) { $DefaultMeasurementPath } else { Resolve-GatePath -Path $MeasurementPath }
$ResolvedMockupPath = if ([string]::IsNullOrWhiteSpace($MockupPath)) { $DefaultMockupPath } else { Resolve-GatePath -Path $MockupPath }
$ResolvedMannequinPath = if ([string]::IsNullOrWhiteSpace($MannequinPath)) { $DefaultMannequinPath } else { Resolve-GatePath -Path $MannequinPath }
$ResolvedStaticFitPath = if ([string]::IsNullOrWhiteSpace($StaticFitPath)) { $DefaultStaticFitPath } else { Resolve-GatePath -Path $StaticFitPath }
$ResolvedMovementPath = if ([string]::IsNullOrWhiteSpace($MovementPath)) { $DefaultMovementPath } else { Resolve-GatePath -Path $MovementPath }
$ResolvedReleaseCablePath = if ([string]::IsNullOrWhiteSpace($ReleaseCablePath)) { $DefaultReleaseCablePath } else { Resolve-GatePath -Path $ReleaseCablePath }
$ResolvedEngineeringReviewPath = if ([string]::IsNullOrWhiteSpace($EngineeringReviewPath)) { $DefaultEngineeringReviewPath } else { Resolve-GatePath -Path $EngineeringReviewPath }
$UsingEngineeringReviewTemplate = [string]::IsNullOrWhiteSpace($EngineeringReviewPath)

$MissingFields = New-Object System.Collections.Generic.List[string]
$InvalidFields = New-Object System.Collections.Generic.List[string]
$ReviewRedesignTriggers = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$RecordLinkageViolations = New-Object System.Collections.Generic.List[string]
$RecordChronologyViolations = New-Object System.Collections.Generic.List[string]
$EngineeringReviewParseOk = $false
$EngineeringReviewStatus = 'pending_engineering_review'
$Status = 'pending_quick_release_cable_snag_gate'
$ExitCode = 0

$Upstream = Invoke-ReleaseCableGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath -ResolvedReleaseCablePath $ResolvedReleaseCablePath
$UpstreamStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_upstream_quick_release_cable_snag_gate' }
$UpstreamReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamStatus -eq 'ready_for_engineering_review_or_final_physical_gate_audit'
$ExpectedReviewScope = 'non-powered FR-017 forearm cuff physical-validation evidence review only'

if (-not [bool]$Upstream.parse_ok -or [int]$Upstream.exit_code -ne 0 -or $UpstreamStatus.StartsWith('failed_')) {
  $Status = 'failed_upstream_quick_release_cable_snag_gate'
  $ExitCode = 1
} elseif (-not $UpstreamReady) {
  $Status = 'pending_quick_release_cable_snag_gate'
} else {
  if (-not (Test-Path -LiteralPath $ResolvedEngineeringReviewPath -PathType Leaf)) {
    $EngineeringReviewStatus = 'failed_engineering_review_record'
    $InvalidFields.Add('engineering_review_file') | Out-Null
  } else {
    try {
      $EngineeringReviewPayload = Get-Content -LiteralPath $ResolvedEngineeringReviewPath -Raw | ConvertFrom-Json -ErrorAction Stop
      $EngineeringReviewParseOk = $true
    } catch {
      $EngineeringReviewStatus = 'failed_engineering_review_record'
      $InvalidFields.Add('engineering_review_json_parse') | Out-Null
    }
  }

  if ($EngineeringReviewParseOk) {
    if ([string](Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'kind' -Default '') -ne 'francis.fr017.engineering_review.v1') {
      $InvalidFields.Add('kind') | Out-Null
    }
    if ([string](Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'component' -Default '') -ne 'FR-017 Forearm Cuffs') {
      $InvalidFields.Add('component') | Out-Null
    }

    $Evidence = Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'evidence'
    Add-EvidenceDateCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.date' -Value (Get-PropertyValue -Payload $Evidence -Name 'date')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.reviewer' -Value (Get-PropertyValue -Payload $Evidence -Name 'reviewer')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.reviewer_role' -Value (Get-PropertyValue -Payload $Evidence -Name 'reviewer_role')
    Add-IfMissingText -Target $MissingFields -Field 'evidence.reviewer_credential_reference' -Value (Get-PropertyValue -Payload $Evidence -Name 'reviewer_credential_reference')
    $ReviewPilotId = Get-PropertyValue -Payload $Evidence -Name 'pilot_id'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.pilot_id' -Value $ReviewPilotId
    $ReleaseCableEvidencePath = Get-PropertyValue -Payload $Evidence -Name 'quick_release_cable_snag_record_path'
    Add-IfMissingText -Target $MissingFields -Field 'evidence.quick_release_cable_snag_record_path' -Value $ReleaseCableEvidencePath
    Add-ExactTextCheck -Missing $MissingFields -Invalid $InvalidFields -Field 'evidence.review_scope' -Value (Get-PropertyValue -Payload $Evidence -Name 'review_scope') -Expected $ExpectedReviewScope

    if (Test-PresentText -Value $ReleaseCableEvidencePath) {
      try {
        $ResolvedReleaseCableEvidencePath = Resolve-GatePath -Path ([string]$ReleaseCableEvidencePath)
        if (-not [string]::Equals($ResolvedReleaseCableEvidencePath, $ResolvedReleaseCablePath, [System.StringComparison]::OrdinalIgnoreCase)) {
          $RecordLinkageViolations.Add('evidence.quick_release_cable_snag_record_path_must_match_release_cable_path') | Out-Null
        }
      } catch {
        $InvalidFields.Add('evidence.quick_release_cable_snag_record_path') | Out-Null
      }
    }
    Add-PilotIdentityLinkageCheck -Invalid $InvalidFields -Violations $RecordLinkageViolations -ReviewPilotId $ReviewPilotId -ReleaseCableRecordPath $ResolvedReleaseCablePath

    try {
      $ReleaseCablePayloadForChronology = Get-Content -LiteralPath $ResolvedReleaseCablePath -Raw | ConvertFrom-Json -ErrorAction Stop
      $ReleaseCableEvidenceDate = Get-EvidenceDateOrNull -Payload $ReleaseCablePayloadForChronology
      $EngineeringReviewEvidenceDate = Get-EvidenceDateOrNull -Payload $EngineeringReviewPayload
      if ($null -ne $ReleaseCableEvidenceDate -and $null -ne $EngineeringReviewEvidenceDate -and $EngineeringReviewEvidenceDate -lt $ReleaseCableEvidenceDate) {
        $RecordChronologyViolations.Add('evidence.date_before_release_cable.evidence.date') | Out-Null
      }
    } catch {
      $InvalidFields.Add('release_cable_json_parse_for_chronology') | Out-Null
    }

    $ReviewConstraints = Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'review_constraints'
    foreach ($Field in $RequiredReviewConstraints) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReviewRedesignTriggers -Field ('review_constraints.{0}' -f $Field) -Value (Get-PropertyValue -Payload $ReviewConstraints -Name $Field)
    }

    $SafetyReview = Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'safety_review'
    foreach ($Field in $RequiredSafetyReview) {
      Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReviewRedesignTriggers -Field ('safety_review.{0}' -f $Field) -Value (Get-PropertyValue -Payload $SafetyReview -Name $Field)
    }

    $ReviewDecision = Get-PropertyValue -Payload $EngineeringReviewPayload -Name 'review_decision'
    Add-RequiredTrueCheck -Missing $MissingFields -Invalid $InvalidFields -Redesign $ReviewRedesignTriggers -Field 'review_decision.non_powered_fr017_physical_validation_accepted' -Value (Get-PropertyValue -Payload $ReviewDecision -Name 'non_powered_fr017_physical_validation_accepted')
    foreach ($Field in $RequiredFalseReviewDecision) {
      Add-RequiredFalseCheck -Missing $MissingFields -Invalid $InvalidFields -Fail $ProhibitedClearanceFlags -Field ('review_decision.{0}' -f $Field) -Value (Get-PropertyValue -Payload $ReviewDecision -Name $Field)
    }
    Add-IfMissingText -Target $MissingFields -Field 'review_decision.engineering_review_notes' -Value (Get-PropertyValue -Payload $ReviewDecision -Name 'engineering_review_notes')

    if ($InvalidFields.Count -gt 0 -or $RecordLinkageViolations.Count -gt 0 -or $RecordChronologyViolations.Count -gt 0) {
      $EngineeringReviewStatus = 'failed_engineering_review_record'
      $Status = $EngineeringReviewStatus
      $ExitCode = 1
    } elseif ($ReviewRedesignTriggers.Count -gt 0 -or $ProhibitedClearanceFlags.Count -gt 0) {
      $EngineeringReviewStatus = 'failed_requires_stage17_redesign_or_review_rejection'
      $Status = $EngineeringReviewStatus
      $ExitCode = 1
    } elseif ($MissingFields.Count -gt 0 -or $UsingEngineeringReviewTemplate) {
      $EngineeringReviewStatus = 'pending_engineering_review'
      $Status = $EngineeringReviewStatus
    } else {
      $EngineeringReviewStatus = 'ready_for_final_stage17_physical_gate_audit'
      $Status = $EngineeringReviewStatus
    }
  } else {
    $Status = $EngineeringReviewStatus
    if ($EngineeringReviewStatus.StartsWith('failed_')) {
      $ExitCode = 1
    }
  }
}

$Output = [ordered]@{
  kind = 'francis.fr017.engineering_review_gate'
  mode = $Mode
  status = $Status
  upstream_quick_release_cable_snag_status = $UpstreamStatus
  upstream_quick_release_cable_snag_gate_exit_code = [int]$Upstream.exit_code
  upstream_quick_release_cable_snag_gate_parse_ok = [bool]$Upstream.parse_ok
  upstream_quick_release_cable_snag_gate_ready = $UpstreamReady
  upstream_pilot_movement_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_pilot_movement_status' -Default '') } else { '' }
  upstream_pilot_movement_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_pilot_movement_gate_ready' -Default $false) } else { $false }
  upstream_static_fit_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_static_fit_status' -Default '') } else { '' }
  upstream_static_fit_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_static_fit_gate_ready' -Default $false) } else { $false }
  upstream_mannequin_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_status' -Default '') } else { '' }
  upstream_mannequin_gate_ready = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mannequin_gate_ready' -Default $false) } else { $false }
  upstream_mockup_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_mockup_status' -Default '') } else { '' }
  upstream_measurement_intake_status = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_intake_status' -Default '') } else { '' }
  upstream_next_required_physical_input = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_next_required_physical_input' -Default '') } else { '' }
  upstream_measurement_capture_plan_status_contract = if ([bool]$Upstream.parse_ok) { [string](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_status_contract' -Default '') } else { '' }
  upstream_measurement_capture_plan_not_completion_evidence = if ([bool]$Upstream.parse_ok) { [bool](Get-PropertyValue -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_not_completion_evidence' -Default $false) } else { $false }
  upstream_measurement_capture_plan_status = @(Get-UpstreamObjectArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_capture_plan_status')
  upstream_measurement_invalid_fields = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_invalid_fields')
  upstream_measurement_consistency_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_consistency_violations')
  upstream_marked_zone_specificity_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_marked_zone_specificity_violations')
  upstream_repeatability_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_repeatability_blockers')
  upstream_left_right_independence_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_left_right_independence_blockers')
  upstream_measurement_condition_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_condition_blockers')
  upstream_landmark_confirmation_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_landmark_confirmation_blockers')
  upstream_measurement_note_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_measurement_note_blockers')
  upstream_safety_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_safety_blockers')
  upstream_mockup_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mockup_linkage_violations')
  upstream_mockup_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mockup_redesign_triggers')
  upstream_mannequin_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_record_linkage_violations')
  upstream_mannequin_interface_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_mannequin_interface_redesign_triggers')
  upstream_static_fit_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_record_linkage_violations')
  upstream_static_fit_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_redesign_triggers')
  upstream_static_fit_symptom_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_static_fit_symptom_blockers')
  upstream_movement_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_movement_record_linkage_violations')
  upstream_movement_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_movement_redesign_triggers')
  upstream_movement_symptom_blockers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'upstream_movement_symptom_blockers')
  upstream_release_cable_record_linkage_violations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'record_linkage_violations')
  upstream_release_cable_redesign_triggers = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'release_cable_redesign_triggers')
  upstream_release_cable_fail_observations = @(Get-UpstreamArrayProperty -Payload $Upstream.payload -Name 'fail_observations')
  engineering_review_status = $EngineeringReviewStatus
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  release_cable_path = $ResolvedReleaseCablePath
  engineering_review_path = $ResolvedEngineeringReviewPath
  using_engineering_review_template = $UsingEngineeringReviewTemplate
  engineering_review_parse_ok = $EngineeringReviewParseOk
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  physical_validation_complete = $false
  engineering_review_complete = ($Status -eq 'ready_for_final_stage17_physical_gate_audit')
  final_physical_gate_audit_ready = ($Status -eq 'ready_for_final_stage17_physical_gate_audit')
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  required_review_constraints = $RequiredReviewConstraints
  required_safety_review = $RequiredSafetyReview
  required_false_review_decision = $RequiredFalseReviewDecision
  boolean_value_contract = 'Use unquoted JSON booleans only. Strings such as yes/no/1/0/"true"/"false" are invalid. Review acceptance requires true for required reviewed items and false for prohibited clearances or redesign conditions.'
  record_linkage_contract = 'The engineering review evidence.quick_release_cable_snag_record_path must resolve to the same quick-release/cable-snag record path passed into this gate. An engineering review record cannot advance from stale, copied, or unrelated release/cable evidence.'
  pilot_identity_linkage_contract = 'The engineering review evidence.pilot_id must match evidence.pilot_id in the linked quick-release/cable-snag record. An engineering review record cannot advance if it names a different pilot than the completed release/cable evidence.'
  evidence_date_contract = 'Use an ISO 8601 calendar date in YYYY-MM-DD format for evidence.date. Future-dated engineering-review evidence is invalid because it cannot be completed evidence.'
  evidence_chronology_contract = 'Engineering-review evidence.date must be the same as or later than the linked quick-release/cable-snag evidence.date. An engineering-review record cannot advance from release/cable evidence that was not yet recorded.'
  review_scope_contract = 'The engineering review evidence.review_scope must remain exactly "non-powered FR-017 forearm cuff physical-validation evidence review only". Broader powered, load-bearing, frame-coupled, FR-018, or general exosystem review scope is invalid for this gate.'
  missing_fields = @($MissingFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  record_linkage_violations = @($RecordLinkageViolations.ToArray())
  record_chronology_violations = @($RecordChronologyViolations.ToArray())
  review_redesign_triggers = @($ReviewRedesignTriggers.ToArray())
  prohibited_clearance_flags = @($ProhibitedClearanceFlags.ToArray())
  next_actions = if ($Status -eq 'ready_for_final_stage17_physical_gate_audit') {
    @(
      'run_final_FR-017_physical_gate_audit_without_powered_or_frame_coupled_testing',
      'keep_FR-018_implementation_blocked_until_final_FR-017_physical_gate_closes',
      'preserve_all_evidence_records_with_reviewer_limitations'
    )
  } elseif ($Status -eq 'pending_engineering_review') {
    @(
      'obtain_professional_engineering_review_of_completed_non_powered_FR-017_evidence',
      'complete_FR-017_engineering_review_record',
      'rerun_engineering_review_gate'
    )
  } elseif ($Status -eq 'pending_quick_release_cable_snag_gate') {
    @(
      'complete_measurement_mockup_mannequin_static_movement_and_release_cable_gates',
      'rerun_engineering_review_gate_after_release_cable_gate_is_ready'
    )
  } else {
    @(
      'stop_FR-017_progression',
      'correct_failed_evidence_or_review_condition',
      'rerun_gate_before_any_final_physical_completion_claim'
    )
  }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
