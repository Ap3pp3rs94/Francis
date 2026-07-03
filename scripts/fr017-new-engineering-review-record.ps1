[CmdletBinding()]
param(
  [ValidateSet('Create')]
  [string]$Mode = 'Create',

  [Parameter(Mandatory = $true)]
  [string]$OutputPath,

  [Parameter(Mandatory = $true)]
  [string]$MeasurementPath,

  [Parameter(Mandatory = $true)]
  [string]$MockupPath,

  [Parameter(Mandatory = $true)]
  [string]$MannequinPath,

  [Parameter(Mandatory = $true)]
  [string]$StaticFitPath,

  [Parameter(Mandatory = $true)]
  [string]$MovementPath,

  [Parameter(Mandatory = $true)]
  [string]$ReleaseCablePath,

  [string]$TemplatePath = '',

  [string]$EvidenceDate = '',

  [string]$Reviewer = '',

  [string]$ReviewerRole = '',

  [string]$ReviewerCredentialReference = '',

  [string]$PilotId = '',

  [string]$EngineeringReviewNotes = '',

  [switch]$ConfirmDocumentationPackageReviewed,
  [switch]$ConfirmMeasurementRecordReviewed,
  [switch]$ConfirmMockupRecordReviewed,
  [switch]$ConfirmMannequinRecordReviewed,
  [switch]$ConfirmPilotStaticRecordReviewed,
  [switch]$ConfirmPilotMovementRecordReviewed,
  [switch]$ConfirmQuickReleaseCableRecordReviewed,
  [switch]$ConfirmNoLoadBearingClaimApproved,
  [switch]$ConfirmNoPoweredTestingCleared,
  [switch]$ConfirmNoFrameCoupledTestingCleared,
  [switch]$ConfirmFr018ImplementationNotCleared,
  [switch]$ConfirmRedesignItemsClosedOrBlocked,

  [switch]$ConfirmCirculationNerveRiskReviewed,
  [switch]$ConfirmQuickReleaseAccessReviewed,
  [switch]$ConfirmGloveWristRemovalReviewed,
  [switch]$ConfirmCableRouteReviewed,
  [switch]$ConfirmSymptomFailConditionsReviewed,
  [switch]$ConfirmStopConditionsPreserved,

  [switch]$ConfirmNonPoweredFr017PhysicalValidationAccepted,
  [switch]$ConfirmNoRedesignRequired,
  [switch]$ConfirmNoLoadBearingUseApproved,
  [switch]$ConfirmNoPoweredTestingApproved,
  [switch]$ConfirmNoFrameCoupledTestingApproved,
  [switch]$ConfirmFr018ImplementationNotClearedByDecision,

  [switch]$RequiresRedesign,
  [switch]$LoadBearingUseApproved,
  [switch]$PoweredTestingApproved,
  [switch]$FrameCoupledTestingApproved,
  [switch]$Fr018ImplementationCleared
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$ReleaseCableGateScript = Join-Path $PSScriptRoot 'fr017-quick-release-cable-snag-gate.ps1'
$ExpectedReviewScope = 'non-powered FR-017 forearm cuff physical-validation evidence review only'

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
  $RawOutput = & $PowerShellExe -NoProfile -ExecutionPolicy Bypass -File $ReleaseCableGateScript -Mode Status -MeasurementPath $ResolvedMeasurementPath -MockupPath $ResolvedMockupPath -MannequinPath $ResolvedMannequinPath -StaticFitPath $ResolvedStaticFitPath -MovementPath $ResolvedMovementPath -ReleaseCablePath $ResolvedReleaseCablePath
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

$DefaultTemplatePath = Join-Path $RepoRoot 'FR-017_Stage17_Package\FR-017-ENGINEERING-REVIEW-INPUT-TEMPLATE.json'
$ResolvedTemplatePath = if ([string]::IsNullOrWhiteSpace($TemplatePath)) { $DefaultTemplatePath } else { Resolve-Fr017Path -Path $TemplatePath }
$ResolvedOutputPath = Resolve-Fr017Path -Path $OutputPath
$ResolvedMeasurementPath = Resolve-Fr017Path -Path $MeasurementPath
$ResolvedMockupPath = Resolve-Fr017Path -Path $MockupPath
$ResolvedMannequinPath = Resolve-Fr017Path -Path $MannequinPath
$ResolvedStaticFitPath = Resolve-Fr017Path -Path $StaticFitPath
$ResolvedMovementPath = Resolve-Fr017Path -Path $MovementPath
$ResolvedReleaseCablePath = Resolve-Fr017Path -Path $ReleaseCablePath
$Status = 'created_engineering_review_record'
$ExitCode = 0
$WroteFile = $false
$InvalidFields = New-Object System.Collections.Generic.List[string]
$UpdatedFields = New-Object System.Collections.Generic.List[string]
$ProhibitedClearanceFlags = New-Object System.Collections.Generic.List[string]
$ChronologyViolations = New-Object System.Collections.Generic.List[string]
$UpstreamReleaseCableStatus = ''
$UpstreamReleaseCableReady = $false
$UpstreamReleaseCableExitCode = 1
$UpstreamReleaseCableParseOk = $false

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
  if (-not (Test-Path -LiteralPath $ResolvedMeasurementPath -PathType Leaf)) {
    $Status = 'missing_measurement_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMockupPath -PathType Leaf)) {
    $Status = 'missing_mockup_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMannequinPath -PathType Leaf)) {
    $Status = 'missing_mannequin_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedStaticFitPath -PathType Leaf)) {
    $Status = 'missing_static_fit_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedMovementPath -PathType Leaf)) {
    $Status = 'missing_movement_file'
    $ExitCode = 1
  } elseif (-not (Test-Path -LiteralPath $ResolvedReleaseCablePath -PathType Leaf)) {
    $Status = 'missing_release_cable_file'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $Upstream = Invoke-ReleaseCableGate -ResolvedMeasurementPath $ResolvedMeasurementPath -ResolvedMockupPath $ResolvedMockupPath -ResolvedMannequinPath $ResolvedMannequinPath -ResolvedStaticFitPath $ResolvedStaticFitPath -ResolvedMovementPath $ResolvedMovementPath -ResolvedReleaseCablePath $ResolvedReleaseCablePath
  $UpstreamReleaseCableExitCode = [int]$Upstream.exit_code
  $UpstreamReleaseCableParseOk = [bool]$Upstream.parse_ok
  $UpstreamReleaseCableStatus = if ([bool]$Upstream.parse_ok) { [string]$Upstream.payload.status } else { 'failed_quick_release_cable_snag_gate_parse' }
  $UpstreamReleaseCableReady = [bool]$Upstream.parse_ok -and [int]$Upstream.exit_code -eq 0 -and $UpstreamReleaseCableStatus -eq 'ready_for_engineering_review_or_final_physical_gate_audit'

  if (-not $UpstreamReleaseCableReady) {
    $Status = 'upstream_quick_release_cable_snag_not_ready'
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
  if ([string]$Payload.kind -ne 'francis.fr017.engineering_review.v1') {
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
    Set-RequiredText -Target $Evidence -Field 'reviewer' -Value $Reviewer -QualifiedField 'evidence.reviewer' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'reviewer_role' -Value $ReviewerRole -QualifiedField 'evidence.reviewer_role' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'reviewer_credential_reference' -Value $ReviewerCredentialReference -QualifiedField 'evidence.reviewer_credential_reference' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $Evidence -Field 'pilot_id' -Value $PilotId -QualifiedField 'evidence.pilot_id' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    $Evidence.quick_release_cable_snag_record_path = $ResolvedReleaseCablePath
    $Evidence.review_scope = $ExpectedReviewScope
    $UpdatedFields.Add('evidence.quick_release_cable_snag_record_path') | Out-Null
    $UpdatedFields.Add('evidence.review_scope') | Out-Null

    $ReleaseCablePilotId = Get-EvidencePilotId -Path $ResolvedReleaseCablePath
    if (-not (Test-MissingOrPendingText -Value $PilotId) -and -not [string]::Equals($PilotId.Trim(), $ReleaseCablePilotId.Trim(), [System.StringComparison]::OrdinalIgnoreCase)) {
      $InvalidFields.Add('evidence.pilot_id_must_match_release_cable_pilot_id') | Out-Null
    }

    $EngineeringReviewEvidenceDate = Get-IsoDateOrNull -Value $EvidenceDate
    $ReleaseCableEvidenceDate = Get-EvidenceDateOrNull -Path $ResolvedReleaseCablePath
    if ($null -ne $EngineeringReviewEvidenceDate -and $null -ne $ReleaseCableEvidenceDate -and $EngineeringReviewEvidenceDate -lt $ReleaseCableEvidenceDate) {
      $ChronologyViolations.Add('evidence.date_before_release_cable.evidence.date') | Out-Null
    }
  }

  $ReviewConstraints = $Payload.review_constraints
  if ($null -eq $ReviewConstraints) {
    $InvalidFields.Add('review_constraints') | Out-Null
  } else {
    $ReviewConstraintConfirmations = [ordered]@{
      documentation_package_reviewed = $ConfirmDocumentationPackageReviewed.IsPresent
      measurement_record_reviewed = $ConfirmMeasurementRecordReviewed.IsPresent
      mockup_record_reviewed = $ConfirmMockupRecordReviewed.IsPresent
      mannequin_record_reviewed = $ConfirmMannequinRecordReviewed.IsPresent
      pilot_static_record_reviewed = $ConfirmPilotStaticRecordReviewed.IsPresent
      pilot_movement_record_reviewed = $ConfirmPilotMovementRecordReviewed.IsPresent
      quick_release_cable_record_reviewed = $ConfirmQuickReleaseCableRecordReviewed.IsPresent
      no_load_bearing_claim_approved = $ConfirmNoLoadBearingClaimApproved.IsPresent
      no_powered_testing_cleared = $ConfirmNoPoweredTestingCleared.IsPresent
      no_frame_coupled_testing_cleared = $ConfirmNoFrameCoupledTestingCleared.IsPresent
      fr018_implementation_not_cleared = $ConfirmFr018ImplementationNotCleared.IsPresent
      redesign_items_closed_or_blocked = $ConfirmRedesignItemsClosedOrBlocked.IsPresent
    }
    foreach ($Entry in $ReviewConstraintConfirmations.GetEnumerator()) {
      Set-RequiredTrue -Target $ReviewConstraints -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('review_constraints.{0}' -f [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    }
  }

  $SafetyReview = $Payload.safety_review
  if ($null -eq $SafetyReview) {
    $InvalidFields.Add('safety_review') | Out-Null
  } else {
    $SafetyReviewConfirmations = [ordered]@{
      circulation_nerve_risk_reviewed = $ConfirmCirculationNerveRiskReviewed.IsPresent
      quick_release_access_reviewed = $ConfirmQuickReleaseAccessReviewed.IsPresent
      glove_wrist_removal_reviewed = $ConfirmGloveWristRemovalReviewed.IsPresent
      cable_route_reviewed = $ConfirmCableRouteReviewed.IsPresent
      symptom_fail_conditions_reviewed = $ConfirmSymptomFailConditionsReviewed.IsPresent
      stop_conditions_preserved = $ConfirmStopConditionsPreserved.IsPresent
    }
    foreach ($Entry in $SafetyReviewConfirmations.GetEnumerator()) {
      Set-RequiredTrue -Target $SafetyReview -Field ([string]$Entry.Key) -Confirmed ([bool]$Entry.Value) -QualifiedField ('safety_review.{0}' -f [string]$Entry.Key) -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    }
  }

  $ReviewDecision = $Payload.review_decision
  if ($null -eq $ReviewDecision) {
    $InvalidFields.Add('review_decision') | Out-Null
  } else {
    Set-RequiredTrue -Target $ReviewDecision -Field 'non_powered_fr017_physical_validation_accepted' -Confirmed $ConfirmNonPoweredFr017PhysicalValidationAccepted.IsPresent -QualifiedField 'review_decision.non_powered_fr017_physical_validation_accepted' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $ReviewDecision -Field 'requires_redesign' -ConfirmedAbsent $ConfirmNoRedesignRequired.IsPresent -Observed $RequiresRedesign.IsPresent -QualifiedField 'review_decision.requires_redesign' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $ReviewDecision -Field 'load_bearing_use_approved' -ConfirmedAbsent $ConfirmNoLoadBearingUseApproved.IsPresent -Observed $LoadBearingUseApproved.IsPresent -QualifiedField 'review_decision.load_bearing_use_approved' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $ReviewDecision -Field 'powered_testing_approved' -ConfirmedAbsent $ConfirmNoPoweredTestingApproved.IsPresent -Observed $PoweredTestingApproved.IsPresent -QualifiedField 'review_decision.powered_testing_approved' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $ReviewDecision -Field 'frame_coupled_testing_approved' -ConfirmedAbsent $ConfirmNoFrameCoupledTestingApproved.IsPresent -Observed $FrameCoupledTestingApproved.IsPresent -QualifiedField 'review_decision.frame_coupled_testing_approved' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredFalse -Target $ReviewDecision -Field 'fr018_implementation_cleared' -ConfirmedAbsent $ConfirmFr018ImplementationNotClearedByDecision.IsPresent -Observed $Fr018ImplementationCleared.IsPresent -QualifiedField 'review_decision.fr018_implementation_cleared' -InvalidFields $InvalidFields -BlockingFlags $ProhibitedClearanceFlags -UpdatedFields $UpdatedFields
    Set-RequiredText -Target $ReviewDecision -Field 'engineering_review_notes' -Value $EngineeringReviewNotes -QualifiedField 'review_decision.engineering_review_notes' -InvalidFields $InvalidFields -UpdatedFields $UpdatedFields
  }

  if ($ProhibitedClearanceFlags.Count -gt 0) {
    $Status = 'engineering_review_prohibited_clearance_recorded_requires_review'
    $ExitCode = 1
  } elseif ($InvalidFields.Count -gt 0 -or $ChronologyViolations.Count -gt 0) {
    $Status = 'invalid_engineering_review_record_input'
    $ExitCode = 1
  }
}

if ($ExitCode -eq 0) {
  $Generation = [ordered]@{
    generated_by = 'scripts/fr017-new-engineering-review-record.ps1'
    generated_at_utc = (Get-Date).ToUniversalTime().ToString('o')
    template_path = $ResolvedTemplatePath
    measurement_path = $ResolvedMeasurementPath
    mockup_path = $ResolvedMockupPath
    mannequin_path = $ResolvedMannequinPath
    static_fit_path = $ResolvedStaticFitPath
    movement_path = $ResolvedMovementPath
    release_cable_path = $ResolvedReleaseCablePath
    output_path = $ResolvedOutputPath
    operator_supplied_engineering_review_input_recorded = $true
    engineering_review_record_is_stage17_completion_evidence = $false
    physical_validation_complete = $false
    stage17_completion_claim_allowed = $false
    final_physical_gate_audit_ready = $false
    load_bearing_use_approved = $false
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
  kind = 'francis.fr017.engineering_review_record_initializer'
  mode = $Mode
  status = $Status
  template_path = $ResolvedTemplatePath
  measurement_path = $ResolvedMeasurementPath
  mockup_path = $ResolvedMockupPath
  mannequin_path = $ResolvedMannequinPath
  static_fit_path = $ResolvedStaticFitPath
  movement_path = $ResolvedMovementPath
  release_cable_path = $ResolvedReleaseCablePath
  output_path = $ResolvedOutputPath
  output_exists = (Test-Path -LiteralPath $ResolvedOutputPath -PathType Leaf)
  wrote_file = $WroteFile
  read_only_contract = $false
  writes_repo = ($WroteFile -and (Test-PathUnderRoot -Path $ResolvedOutputPath -Root $RepoRoot))
  writes_data = $WroteFile
  grants_execution_authority = $false
  grants_mutation_authority = $false
  upstream_quick_release_cable_snag_status = $UpstreamReleaseCableStatus
  upstream_quick_release_cable_snag_ready = $UpstreamReleaseCableReady
  upstream_quick_release_cable_snag_exit_code = $UpstreamReleaseCableExitCode
  upstream_quick_release_cable_snag_parse_ok = $UpstreamReleaseCableParseOk
  operator_supplied_engineering_review_input_recorded = $WroteFile
  engineering_review_record_is_stage17_completion_evidence = $false
  physical_validation_complete = $false
  stage17_completion_claim_allowed = $false
  final_physical_gate_audit_ready = $false
  load_bearing_use_approved = $false
  powered_or_frame_coupled_testing_cleared = $false
  fr018_implementation_cleared = $false
  prohibited_clearance_flags_recorded = @($ProhibitedClearanceFlags.ToArray())
  record_chronology_violations = @($ChronologyViolations.ToArray())
  no_fake_validation_lock = 'This initializer records operator-supplied professional FR-017 engineering review input only after quick-release/cable-snag readiness is ready. It does not certify pilot safety by itself, does not mark physical validation complete, does not permit a Stage 17 completion claim, does not approve load-bearing use, does not clear powered or frame-coupled testing, and does not clear FR-018.'
  updated_fields = @($UpdatedFields.ToArray())
  invalid_fields = @($InvalidFields.ToArray())
  next_command = if ($WroteFile) { '.\scripts\fr017-engineering-review-gate.ps1 -Mode Status -MeasurementPath "{0}" -MockupPath "{1}" -MannequinPath "{2}" -StaticFitPath "{3}" -MovementPath "{4}" -ReleaseCablePath "{5}" -EngineeringReviewPath "{6}"' -f $ResolvedMeasurementPath, $ResolvedMockupPath, $ResolvedMannequinPath, $ResolvedStaticFitPath, $ResolvedMovementPath, $ResolvedReleaseCablePath, $ResolvedOutputPath } else { '' }
}

$Output | ConvertTo-Json -Depth 8
exit $ExitCode
