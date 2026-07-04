[CmdletBinding()]
param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status',

  [string]$LedgerPath = '',

  [string]$LedgerArchiveDirPath = '',

  [string]$BuildManifestPath = '',

  [string]$ArtifactReconstructionReceiptRootPath = ''
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Resolve-CompletionModelPath {
  param(
    [string]$Override,
    [string]$DefaultRelativePath
  )

  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return [System.IO.Path]::GetFullPath($Override)
  }
  return Join-Path $RepoRoot $DefaultRelativePath
}

function Read-CompletionModelText {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return ''
  }
  return [System.IO.File]::ReadAllText($Path)
}

function Get-CompletionLedgerArchivePaths {
  param([string]$ArchiveDirPath)

  if ([string]::IsNullOrWhiteSpace($ArchiveDirPath) -or -not (Test-Path -LiteralPath $ArchiveDirPath -PathType Container)) {
    return @()
  }
  return @(Get-ChildItem -LiteralPath $ArchiveDirPath -File -Filter 'COMPLETION_LEDGER*.md' | Sort-Object Name | ForEach-Object { [string]$_.FullName })
}

function Get-CompletionModelRelativePath {
  param([string]$Path)

  $FullPath = [System.IO.Path]::GetFullPath($Path)
  $RootPath = [System.IO.Path]::GetFullPath($RepoRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  if ($FullPath.StartsWith($RootPath + [System.IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    return $FullPath.Substring($RootPath.Length + 1).Replace('\', '/')
  }
  return $FullPath.Replace('\', '/')
}

function Limit-CompletionModelText {
  param(
    [string]$Text,
    [int]$MaxLength = 500
  )

  $Collapsed = (([string]$Text) -replace '\s+', ' ').Trim()
  if ($Collapsed.Length -le $MaxLength) {
    return $Collapsed
  }
  return $Collapsed.Substring(0, $MaxLength).Trim() + '...'
}

function Get-FirstRegexGroup {
  param(
    [string]$Text,
    [string]$Pattern,
    [string]$GroupName
  )

  $Match = [regex]::Match($Text, $Pattern, [System.Text.RegularExpressions.RegexOptions]::IgnoreCase)
  if (-not $Match.Success) {
    return ''
  }
  return ([string]$Match.Groups[$GroupName].Value).Trim()
}

function Get-LabeledParagraph {
  param(
    [string]$Text,
    [string]$Label
  )

  $Prefix = ($Label + ':').ToLowerInvariant()
  $Lines = [regex]::Split([string]$Text, '\r?\n')
  for ($Index = 0; $Index -lt $Lines.Count; $Index += 1) {
    $Line = ([string]$Lines[$Index]).Trim()
    if (-not $Line.ToLowerInvariant().StartsWith($Prefix)) {
      continue
    }

    $Parts = New-Object System.Collections.ArrayList
    $First = $Line.Substring($Prefix.Length).Trim()
    if (-not [string]::IsNullOrWhiteSpace($First)) {
      [void]$Parts.Add($First)
    }
    for ($Next = $Index + 1; $Next -lt $Lines.Count; $Next += 1) {
      $Continuation = ([string]$Lines[$Next]).Trim()
      if ([string]::IsNullOrWhiteSpace($Continuation)) {
        break
      }
      [void]$Parts.Add($Continuation)
    }
    return Limit-CompletionModelText -Text ([string]::Join(' ', [string[]]$Parts.ToArray([string]))) -MaxLength 700
  }
  return ''
}

function Get-LatestLedgerEntry {
  param([string]$LedgerText)

  $Body = [string]$LedgerText
  $UpdateRuleIndex = $Body.IndexOf("`n## 6. Update rule", [StringComparison]::Ordinal)
  if ($UpdateRuleIndex -ge 0) {
    $Body = $Body.Substring(0, $UpdateRuleIndex)
  }

  $Matches = [regex]::Matches($Body, '(?m)^### (?<title>.+)$')
  if ($Matches.Count -eq 0) {
    return [ordered]@{
      found = $false
      title = ''
      roadmap_area = ''
      remaining_truthful_gap = ''
      has_remaining_truthful_gap = $false
    }
  }

  $Latest = $Matches[$Matches.Count - 1]
  $EntryText = $Body.Substring($Latest.Index).Trim()
  $Title = ([string]$Latest.Groups['title'].Value).Trim()
  $RoadmapArea = Get-LabeledParagraph -Text $EntryText -Label 'Roadmap area'
  $RemainingGap = Get-FirstRegexGroup -Text $EntryText -Pattern '(?s)Remaining truthful gap:\s*(?<gap>.+)$' -GroupName 'gap'

  return [ordered]@{
    found = $true
    title = $Title
    roadmap_area = $RoadmapArea
    remaining_truthful_gap = Limit-CompletionModelText -Text $RemainingGap -MaxLength 700
    has_remaining_truthful_gap = -not [string]::IsNullOrWhiteSpace($RemainingGap)
  }
}

function Test-Stage17LedgerEntry {
  param(
    [string]$Title,
    [string]$RoadmapArea
  )

  $TitleKey = ([string]$Title).ToLowerInvariant()
  $RoadmapKey = ([string]$RoadmapArea).ToLowerInvariant()
  $TitleIsStage17Slice = ($TitleKey.StartsWith('stage 17 ') -or $TitleKey.Contains(' - stage 17 '))
  return ($TitleIsStage17Slice -or $RoadmapKey.StartsWith('stage 17 /'))
}

function Test-Stage17OpenText {
  param([string]$Text)

  $Key = ([string]$Text).ToLowerInvariant()
  return ($Key.Contains('stage 17 remains open') -or $Key.Contains('stage 17 still needs'))
}

function Get-Stage17Status {
  param([string]$LedgerText)

  $Body = [string]$LedgerText
  $UpdateRuleIndex = $Body.IndexOf("`n## 6. Update rule", [StringComparison]::Ordinal)
  if ($UpdateRuleIndex -ge 0) {
    $Body = $Body.Substring(0, $UpdateRuleIndex)
  }

  $Matches = [regex]::Matches($Body, '(?m)^### (?<title>.+)$')
  $LatestStage17Entry = $null
  for ($Index = 0; $Index -lt $Matches.Count; $Index += 1) {
    $Match = $Matches[$Index]
    $NextStart = if (($Index + 1) -lt $Matches.Count) { $Matches[$Index + 1].Index } else { $Body.Length }
    $EntryText = $Body.Substring($Match.Index, $NextStart - $Match.Index).Trim()
    $Title = ([string]$Match.Groups['title'].Value).Trim()
    $RoadmapArea = Get-LabeledParagraph -Text $EntryText -Label 'Roadmap area'
    if (-not (Test-Stage17LedgerEntry -Title $Title -RoadmapArea $RoadmapArea)) {
      continue
    }
    $RemainingGap = Get-FirstRegexGroup -Text $EntryText -Pattern '(?s)Remaining truthful gap:\s*(?<gap>.+)$' -GroupName 'gap'
    $LatestStage17Entry = [ordered]@{
      found = $true
      title = $Title
      roadmap_area = $RoadmapArea
      remaining_truthful_gap = Limit-CompletionModelText -Text $RemainingGap -MaxLength 700
      has_remaining_truthful_gap = -not [string]::IsNullOrWhiteSpace($RemainingGap)
    }
  }

  if ($null -eq $LatestStage17Entry) {
    return [ordered]@{
      found = $false
      status = 'unknown'
      readback_scope = 'latest_stage17_ledger_entry'
      read_only_contract = $true
      writes_repo = $false
      writes_data = $false
      grants_execution_authority = $false
      grants_mutation_authority = $false
      latest_ledger_entry = [ordered]@{
        found = $false
        title = ''
        roadmap_area = ''
        remaining_truthful_gap = ''
        has_remaining_truthful_gap = $false
      }
      next_smallest_truthful_gap = 'name_stage17_remaining_truthful_gap_in_ledger'
    }
  }

  return [ordered]@{
    found = $true
    status = if (Test-Stage17OpenText -Text ([string]$LatestStage17Entry.remaining_truthful_gap)) { 'open' } else { 'review' }
    readback_scope = 'latest_stage17_ledger_entry'
    read_only_contract = $true
    writes_repo = $false
    writes_data = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    latest_ledger_entry = $LatestStage17Entry
    next_smallest_truthful_gap = if ([bool]$LatestStage17Entry.has_remaining_truthful_gap) { 'select_from_latest_stage17_remaining_truthful_gap' } else { 'name_stage17_remaining_truthful_gap_in_ledger' }
  }
}

function Get-Stage17StatusWithArchiveFallback {
  param(
    [string]$LedgerText,
    [string[]]$ArchivePaths
  )

  $Status = Get-Stage17Status -LedgerText $LedgerText
  $Status['archive_fallback_used'] = $false
  $Status['archive_source_documents'] = @()
  if ([bool]$Status.found) {
    return $Status
  }

  $ArchiveTextParts = New-Object System.Collections.Generic.List[string]
  $ArchiveSourceDocuments = @()
  foreach ($ArchivePath in @($ArchivePaths)) {
    if ([string]::IsNullOrWhiteSpace($ArchivePath)) {
      continue
    }
    [void]$ArchiveTextParts.Add((Read-CompletionModelText -Path $ArchivePath))
    $ArchiveSourceDocuments += (Get-CompletionModelRelativePath -Path $ArchivePath)
  }

  $ArchiveStatus = Get-Stage17Status -LedgerText ([string]::Join("`n`n", [string[]]$ArchiveTextParts.ToArray()))
  $ArchiveStatus['archive_fallback_used'] = [bool]$ArchiveStatus.found
  $ArchiveStatus['archive_source_documents'] = @($ArchiveSourceDocuments)
  return $ArchiveStatus
}

function Get-PlaneReadiness {
  param([string]$BuildManifestText)

  $Planes = @()
  foreach ($Match in [regex]::Matches($BuildManifestText, '(?m)^- `(?<plane>P\d+_[A-Z_]+)`:\s*(?<status>[^\r\n]+)$')) {
    $Planes += [ordered]@{
      plane = ([string]$Match.Groups['plane'].Value).Trim()
      status = ([string]$Match.Groups['status'].Value).Trim()
    }
  }
  return @($Planes)
}

function ConvertTo-CompletionModelBool {
  param([object]$Value)

  return ($null -ne $Value -and [bool]$Value)
}

function Get-Stage17ArtifactReconstructionEvidence {
  param([string]$ReceiptRootPath)

  $Evidence = [ordered]@{
    found = $false
    status = 'missing'
    read_only_contract = $true
    writes_repo = $false
    writes_data = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    receipt_root = $ReceiptRootPath
    receipt_count = 0
    malformed_receipt_count = 0
    clean_json = $false
    latest_receipt_path = ''
    receipt_id = ''
    contract = ''
    durable_receipt_contract_verified = $false
    queue_count_contract = ''
    queue_count_contract_verified = $false
    kind = ''
    route = ''
    actor = ''
    receipt_status = ''
    selection_strategy = ''
    projection_scope = ''
    global_counts_included = $false
    before_global_remediation_queue_count = $null
    after_global_remediation_queue_count = $null
    before_remediation_queue_count = $null
    after_remediation_queue_count = $null
    before_validation_receipt_reconstruction_required_count = $null
    after_validation_receipt_reconstruction_required_count = $null
    before_proposal_lineage_reconstruction_required_count = $null
    after_proposal_lineage_reconstruction_required_count = $null
    candidate_reduction_count = $null
    validation_receipt_write_count = $null
    proposal_lineage_write_count = $null
    recorded_pack_count = $null
    recorded_capability_count = $null
    dry_run_fingerprint_matched = $false
    writes_batch_reconstruction_receipt = $false
    approval_authority = $false
    promotion_authority = $false
    execution_authority = $false
    memory_write = $false
    selected_reconstruction_pack_ids = @()
  }

  if ([string]::IsNullOrWhiteSpace($ReceiptRootPath) -or -not (Test-Path -LiteralPath $ReceiptRootPath -PathType Container)) {
    return $Evidence
  }

  $Files = @(Get-ChildItem -LiteralPath $ReceiptRootPath -File -Filter '*_receipt.json' | Sort-Object LastWriteTime -Descending)
  $Evidence.receipt_count = $Files.Count
  foreach ($File in $Files) {
    try {
      $Receipt = Get-Content -LiteralPath $File.FullName -Raw | ConvertFrom-Json
    } catch {
      $Evidence.malformed_receipt_count += 1
      continue
    }

    if ([string]$Receipt.contract -ne 'stage17_capability_pack_artifact_reconstruction_receipt_v1') {
      continue
    }

    $Evidence.found = $true
    $Evidence.status = 'ready'
    $Evidence.clean_json = $true
    $Evidence.latest_receipt_path = [string]$File.FullName
    $Evidence.receipt_id = [string]$Receipt.receipt_id
    $Evidence.contract = [string]$Receipt.contract
    $Evidence.durable_receipt_contract_verified = $true
    $Evidence.queue_count_contract = [string]$Receipt.queue_count_contract
    $Evidence.queue_count_contract_verified = ([string]$Receipt.queue_count_contract -eq 'stage17_capability_pack_artifact_reconstruction_batch_queue_evidence_v1')
    $Evidence.kind = [string]$Receipt.kind
    $Evidence.route = [string]$Receipt.route
    $Evidence.actor = [string]$Receipt.actor
    $Evidence.receipt_status = [string]$Receipt.status
    $Evidence.selection_strategy = [string]$Receipt.selection_strategy
    $Evidence.projection_scope = [string]$Receipt.projection_scope
    $Evidence.global_counts_included = ConvertTo-CompletionModelBool -Value $Receipt.global_counts_included
    $Evidence.before_global_remediation_queue_count = $Receipt.before_global_remediation_queue_count
    $Evidence.after_global_remediation_queue_count = $Receipt.after_global_remediation_queue_count
    $Evidence.before_remediation_queue_count = $Receipt.before_remediation_queue_count
    $Evidence.after_remediation_queue_count = $Receipt.after_remediation_queue_count
    $Evidence.before_validation_receipt_reconstruction_required_count = $Receipt.before_validation_receipt_reconstruction_required_count
    $Evidence.after_validation_receipt_reconstruction_required_count = $Receipt.after_validation_receipt_reconstruction_required_count
    $Evidence.before_proposal_lineage_reconstruction_required_count = $Receipt.before_proposal_lineage_reconstruction_required_count
    $Evidence.after_proposal_lineage_reconstruction_required_count = $Receipt.after_proposal_lineage_reconstruction_required_count
    $Evidence.candidate_reduction_count = $Receipt.candidate_reduction_count
    $Evidence.validation_receipt_write_count = $Receipt.validation_receipt_write_count
    $Evidence.proposal_lineage_write_count = $Receipt.proposal_lineage_write_count
    $Evidence.recorded_pack_count = $Receipt.recorded_pack_count
    $Evidence.recorded_capability_count = $Receipt.recorded_capability_count
    $Evidence.dry_run_fingerprint_matched = ConvertTo-CompletionModelBool -Value $Receipt.dry_run_confirmation.fingerprint_matched
    $Evidence.writes_batch_reconstruction_receipt = ConvertTo-CompletionModelBool -Value $Receipt.governance.writes_batch_reconstruction_receipt
    $Evidence.approval_authority = ConvertTo-CompletionModelBool -Value $Receipt.governance.approval_authority
    $Evidence.promotion_authority = ConvertTo-CompletionModelBool -Value $Receipt.governance.promotion_authority
    $Evidence.execution_authority = ConvertTo-CompletionModelBool -Value $Receipt.governance.execution_authority
    $Evidence.memory_write = ConvertTo-CompletionModelBool -Value $Receipt.governance.memory_write
    $Evidence.selected_reconstruction_pack_ids = @($Receipt.selected_reconstruction_pack_ids)
    return $Evidence
  }

  return $Evidence
}

function New-CompletionLoopGuard {
  param(
    [bool]$LedgerExists,
    [bool]$BuildManifestExists,
    [object]$LatestLedgerEntry,
    [object]$Stage17Status
  )

  $Stage17Entry = if ($null -ne $Stage17Status) { $Stage17Status.latest_ledger_entry } else { $null }
  $Stage17GapPreserved = (
    $null -ne $Stage17Status -and
    [bool]$Stage17Status.found -and
    ([string]$Stage17Status.status) -eq 'open' -and
    $null -ne $Stage17Entry -and
    [bool]$Stage17Entry.has_remaining_truthful_gap
  )
  $Stage17GapEvidence = if ($Stage17GapPreserved) {
    [string]$Stage17Entry.title
  } else {
    'no open Stage 17 gap selected'
  }

  $Checklist = @(
    [ordered]@{
      id = 'ledger_read'
      status = if ($LedgerExists) { 'ready' } else { 'blocked' }
      required_before_continue = $true
      evidence = 'docs/operations/COMPLETION_LEDGER.md'
    },
    [ordered]@{
      id = 'build_manifest_read'
      status = if ($BuildManifestExists) { 'ready' } else { 'blocked' }
      required_before_continue = $true
      evidence = 'docs/canonical/BUILD_MANIFEST.md'
    },
    [ordered]@{
      id = 'latest_validated_slice_identified'
      status = if ([bool]$LatestLedgerEntry.found) { 'ready' } else { 'blocked' }
      required_before_continue = $true
      evidence = [string]$LatestLedgerEntry.title
    },
    [ordered]@{
      id = 'remaining_gap_named'
      status = if ([bool]$LatestLedgerEntry.has_remaining_truthful_gap) { 'ready' } else { 'needs_review' }
      required_before_continue = $true
      evidence = [string]$LatestLedgerEntry.remaining_truthful_gap
    },
    [ordered]@{
      id = 'stage17_lane_gap_preserved'
      status = if ($Stage17GapPreserved) { 'ready' } else { 'not_applicable' }
      required_before_continue = $true
      evidence = $Stage17GapEvidence
    },
    [ordered]@{
      id = 'dirty_worktree_preservation_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'inspect git status before editing and preserve unrelated dirty work'
    },
    [ordered]@{
      id = 'percentage_movement_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'percentages require baseline, validated gate movement, and remaining blockers'
    },
    [ordered]@{
      id = 'single_bounded_slice_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'continue should pick one roadmap-aligned slice, validate it, then ledger it'
    },
    [ordered]@{
      id = 'material_ledger_update_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'update the ledger only for material repo truth backed by validation'
    },
    [ordered]@{
      id = 'stage17_readback_apply_boundary_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Stage 17 readbacks stay authority-denying; apply routes must remain governed, dry-run confirmed, scoped, and tested'
    },
    [ordered]@{
      id = 'stage17_queue_count_evidence_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not queue-count evidence; queue movement claims require route readback or apply response with projection_scope, global_counts_included, before/after counts, and focused validation'
    },
    [ordered]@{
      id = 'stage17_projection_timing_evidence_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not projection timing evidence; broad readback or projection hardening claims require route readback or apply response with generated_at or receipt timestamp, projection_scope, bounded plugin scope or full-library declaration, global_counts_included, and focused validation'
    },
    [ordered]@{
      id = 'stage17_proposal_evidence_reference_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not proposal-evidence references; proposal evidence claims require proposal artifact, proposal-review receipt, validation or quality-evidence reference, bounded plugin scope, and focused validation'
    },
    [ordered]@{
      id = 'stage17_publication_evidence_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not publication evidence; publication claims require a PM-owned publication marker with matching prompt hash, GitHub push or explicit no-change/blocked receipt, and focused validation'
    },
    [ordered]@{
      id = 'stage17_worker_readback_evidence_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not worker lane readbacks; worker packet claims require a lane readback path, matching prompt hash, files changed, validation, blockers or risks, proposed commit scope, and next recommended prompt'
    },
    [ordered]@{
      id = 'stage17_worker_publication_handoff_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not worker/publication handoff evidence; handoff claims require a lane readback plus a PM-owned publication marker with matching prompt hash, GitHub push or explicit no-change/blocked receipt, files changed, validation, blockers or risks, proposed commit scope, and next recommended prompt'
    },
    [ordered]@{
      id = 'stage17_worker_execution_liveness_guard'
      status = 'enforced'
      required_before_continue = $true
      evidence = 'Selected Stage 17 gaps are not worker execution or session-liveness evidence; worker execution claims require a worker session path, matching prompt hash, process liveness or exit code, completed or blocked status, lane readback or last message, files changed or no-change scope, and validation or blocker evidence'
    }
  )

  $Blocked = @($Checklist | Where-Object { $_.status -eq 'blocked' })
  return [ordered]@{
    status = if ($Blocked.Count -eq 0) { 'ready' } else { 'blocked' }
    blocked_count = $Blocked.Count
    checklist = $Checklist
  }
}

function New-SelectedGapContract {
  param(
    [string]$SelectedSource,
    [bool]$Stage17GapPreferred
  )

  $Selected = ($SelectedSource -eq 'stage17_latest_ledger_entry' -or $SelectedSource -eq 'latest_ledger_entry')
  if ($Stage17GapPreferred) {
    $SelectionBasis = 'latest_open_stage17_remaining_gap'
  } elseif ($SelectedSource -eq 'latest_ledger_entry') {
    $SelectionBasis = 'latest_ledger_remaining_gap'
  } elseif ($SelectedSource -eq 'completion_model_sources') {
    $SelectionBasis = 'restore_completion_model_sources'
  } else {
    $SelectionBasis = 'no_gap_selected'
  }

  return [ordered]@{
    kind = 'francis.completion_model.selected_gap_contract'
    status = if ($Selected) { 'selected' } else { 'blocked' }
    selected_gap_source = $SelectedSource
    selection_basis = $SelectionBasis
    selected_gap_is_stage17 = $Stage17GapPreferred
    read_only_selection = $true
    writes_repo = $false
    writes_data = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    apply_authority_granted = $false
    proposal_evidence_apply_authority = $false
    proposal_review_authority = $false
    promotion_authority = $false
    capability_execution_authority = $false
    selected_gap_is_proposal_evidence_reference = $false
    proposal_evidence_refs_verified = $false
    proposal_review_receipts_verified = $false
    validation_receipts_verified = $false
    proposal_evidence_reference_authority_granted = $false
    selected_gap_is_queue_count_evidence = $false
    global_queue_count_recomputed = $false
    queue_count_authority_granted = $false
    selected_gap_is_projection_timing_evidence = $false
    projection_generated_at_verified = $false
    projection_is_fresh = $false
    projection_timing_authority_granted = $false
    selected_gap_is_publication_evidence = $false
    github_publication_verified = $false
    publication_marker_verified = $false
    publication_authority_granted = $false
    selected_gap_is_worker_readback_evidence = $false
    worker_lane_readback_verified = $false
    worker_packet_verified = $false
    worker_readback_authority_granted = $false
    selected_gap_is_worker_publication_handoff_evidence = $false
    worker_publication_handoff_verified = $false
    worker_publication_handoff_authority_granted = $false
    selected_gap_is_worker_execution_liveness_evidence = $false
    worker_session_liveness_verified = $false
    worker_process_completion_verified = $false
    worker_execution_readback_authority_granted = $false
    stage17_readback_authority_denied = $true
    future_stage17_apply_requires = @(
      'existing_governed_route',
      'dry_run_confirmation',
      'bounded_scope',
      'focused_validation'
    )
    future_stage17_queue_count_claim_requires = @(
      'route_readback_or_apply_response',
      'projection_scope',
      'global_counts_included_flag',
      'before_after_counts',
      'focused_validation'
    )
    future_stage17_projection_timing_claim_requires = @(
      'route_readback_or_apply_response',
      'projection_generated_at_or_receipt_timestamp',
      'projection_scope',
      'bounded_plugin_id_scope_or_full_library_declaration',
      'global_counts_included_flag',
      'focused_validation'
    )
    future_stage17_proposal_evidence_claim_requires = @(
      'existing_governed_route',
      'proposal_artifact_ref',
      'proposal_review_receipt_ref',
      'validation_receipt_or_quality_evidence_ref',
      'bounded_plugin_id_scope',
      'focused_validation'
    )
    future_stage17_publication_claim_requires = @(
      'pm_owned_publication_marker',
      'matching_prompt_sha256',
      'github_push_or_explicit_no_change_or_blocked_receipt',
      'focused_validation'
    )
    future_stage17_worker_readback_claim_requires = @(
      'worker_lane_readback_path',
      'matching_prompt_sha256',
      'files_changed',
      'validation_run',
      'blockers_and_risks',
      'proposed_commit_scope',
      'next_recommended_prompt'
    )
    future_stage17_worker_publication_handoff_claim_requires = @(
      'worker_lane_readback_path',
      'pm_owned_publication_marker',
      'matching_prompt_sha256',
      'github_push_or_explicit_no_change_or_blocked_receipt',
      'files_changed',
      'validation_run',
      'blockers_and_risks',
      'proposed_commit_scope',
      'next_recommended_prompt'
    )
    future_stage17_worker_execution_liveness_claim_requires = @(
      'worker_session_path',
      'matching_prompt_sha256',
      'process_alive_or_exit_code',
      'worker_execution_completed_or_blocked_status',
      'lane_readback_path_or_last_message',
      'files_changed_or_no_change_scope',
      'validation_or_blocker_evidence'
    )
  }
}

function New-NextContinueDecision {
  param(
    [object]$LoopGuard,
    [object]$LatestLedgerEntry,
    [object]$Stage17Status
  )

  $SelectedSource = 'none'
  $SelectedTitle = ''
  $SelectedRoadmapArea = ''
  $Stage17GapPreferred = $false
  $NextGap = 'name_remaining_truthful_gap_in_ledger'

  if ($LoopGuard.status -ne 'ready') {
    $SelectedSource = 'completion_model_sources'
    $NextGap = 'restore_completion_model_sources'
  } else {
    $Stage17Entry = $Stage17Status.latest_ledger_entry
    if (
      [bool]$Stage17Status.found -and
      ([string]$Stage17Status.status) -eq 'open' -and
      $null -ne $Stage17Entry -and
      [bool]$Stage17Entry.has_remaining_truthful_gap
    ) {
      $SelectedSource = 'stage17_latest_ledger_entry'
      $SelectedTitle = [string]$Stage17Entry.title
      $SelectedRoadmapArea = [string]$Stage17Entry.roadmap_area
      $Stage17GapPreferred = $true
      $NextGap = [string]$Stage17Entry.remaining_truthful_gap
    } elseif ([bool]$LatestLedgerEntry.has_remaining_truthful_gap) {
      $SelectedSource = 'latest_ledger_entry'
      $SelectedTitle = [string]$LatestLedgerEntry.title
      $SelectedRoadmapArea = [string]$LatestLedgerEntry.roadmap_area
      $NextGap = [string]$LatestLedgerEntry.remaining_truthful_gap
    }
  }

  return [ordered]@{
    status = if ($LoopGuard.status -eq 'ready') { 'bounded_slice_required' } else { 'blocked_until_model_sources_exist' }
    rule = 'On continue, preserve dirty work, choose one remaining truthful gap, state plan, implement the smallest coherent change, validate, then update the ledger.'
    selected_gap_source = $SelectedSource
    selected_ledger_title = $SelectedTitle
    selected_roadmap_area = $SelectedRoadmapArea
    stage17_gap_preferred = $Stage17GapPreferred
    next_smallest_truthful_gap = $NextGap
    selected_gap_contract = New-SelectedGapContract -SelectedSource $SelectedSource -Stage17GapPreferred $Stage17GapPreferred
  }
}

$ResolvedLedgerPath = Resolve-CompletionModelPath -Override $LedgerPath -DefaultRelativePath 'docs/operations/COMPLETION_LEDGER.md'
$ResolvedLedgerArchiveDirPath = Resolve-CompletionModelPath -Override $LedgerArchiveDirPath -DefaultRelativePath 'docs/operations/archive'
$ResolvedBuildManifestPath = Resolve-CompletionModelPath -Override $BuildManifestPath -DefaultRelativePath 'docs/canonical/BUILD_MANIFEST.md'
$ResolvedArtifactReconstructionReceiptRootPath = Resolve-CompletionModelPath -Override $ArtifactReconstructionReceiptRootPath -DefaultRelativePath 'data/artifacts/plugins/capability_packs/artifact_reconstructions'
$LedgerExists = Test-Path -LiteralPath $ResolvedLedgerPath -PathType Leaf
$BuildManifestExists = Test-Path -LiteralPath $ResolvedBuildManifestPath -PathType Leaf
$LedgerText = Read-CompletionModelText -Path $ResolvedLedgerPath
$BuildManifestText = Read-CompletionModelText -Path $ResolvedBuildManifestPath
$UseLedgerArchiveFallback = ([string]::IsNullOrWhiteSpace($LedgerPath) -or -not [string]::IsNullOrWhiteSpace($LedgerArchiveDirPath))
$LedgerArchivePaths = if ($UseLedgerArchiveFallback) { @(Get-CompletionLedgerArchivePaths -ArchiveDirPath $ResolvedLedgerArchiveDirPath) } else { @() }
$LedgerArchiveSourceDocuments = @($LedgerArchivePaths | ForEach-Object { Get-CompletionModelRelativePath -Path $_ })
$CurrentPhase = Get-FirstRegexGroup -Text $LedgerText -Pattern 'Francis is in `(?<phase>Phase \d+)`' -GroupName 'phase'
if ([string]::IsNullOrWhiteSpace($CurrentPhase)) {
  $CurrentPhase = Get-FirstRegexGroup -Text $BuildManifestText -Pattern '\((?<phase>Phase \d+)\)' -GroupName 'phase'
}
$LatestLedgerEntry = Get-LatestLedgerEntry -LedgerText $LedgerText
$Stage17Status = Get-Stage17StatusWithArchiveFallback -LedgerText $LedgerText -ArchivePaths $LedgerArchivePaths
$Planes = Get-PlaneReadiness -BuildManifestText $BuildManifestText
$LoopGuard = New-CompletionLoopGuard -LedgerExists $LedgerExists -BuildManifestExists $BuildManifestExists -LatestLedgerEntry $LatestLedgerEntry -Stage17Status $Stage17Status
$NextContinueDecision = New-NextContinueDecision -LoopGuard $LoopGuard -LatestLedgerEntry $LatestLedgerEntry -Stage17Status $Stage17Status
$Stage17ArtifactReconstructionEvidence = Get-Stage17ArtifactReconstructionEvidence -ReceiptRootPath $ResolvedArtifactReconstructionReceiptRootPath

$Payload = [ordered]@{
  ok = ($LedgerExists -and $BuildManifestExists)
  kind = 'francis.completion_model.status'
  mode = $Mode
  status = if ($LedgerExists -and $BuildManifestExists) { 'ready' } else { 'blocked' }
  generated_at = [DateTimeOffset]::UtcNow.ToString('o')
  read_only_contract = $true
  writes_repo = $false
  writes_data = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  source_documents = [ordered]@{
    completion_ledger = 'docs/operations/COMPLETION_LEDGER.md'
    completion_ledger_archive = 'docs/operations/archive'
    completion_ledger_archive_files = @($LedgerArchiveSourceDocuments)
    build_manifest = 'docs/canonical/BUILD_MANIFEST.md'
  }
  current_phase = $CurrentPhase
  plane_readiness_snapshot = $Planes
  latest_ledger_entry = $LatestLedgerEntry
  stage17_status = $Stage17Status
  stage17_artifact_reconstruction_evidence = $Stage17ArtifactReconstructionEvidence
  completion_percentage_model = [ordered]@{
    status = 'evidence_gated'
    numeric_baseline_declared_here = $false
    overall_project_percent = $null
    current_build_phase_percent = $null
    current_task_percent = $null
    movement_allowed_by_this_readback = $false
    required_to_move = @(
      'known_baseline_source',
      'validated_repo_evidence',
      'ledger_backed_gate_or_milestone_change',
      'explicit_remaining_blockers'
    )
    rule = 'Do not move overall Francis or build-phase percentages from effort, elapsed time, runtime-only success, or documentation-only changes.'
  }
  continue_loop_guard = $LoopGuard
  next_continue_decision = $NextContinueDecision
}

$Payload | ConvertTo-Json -Depth 8
