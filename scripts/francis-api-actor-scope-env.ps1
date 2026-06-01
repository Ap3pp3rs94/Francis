param(
  [ValidateSet('Status', 'Apply')]
  [string]$Mode = 'Status',

  [string]$Root = '',

  [string]$Actor = 'codex.builder',

  [string]$Scope = 'federation.stage16.sleep_resume.confirmation.write',

  [string]$Reason = 'stage16_sleep_resume_confirmation_actor_scope_remediation',

  [string]$EnvProfile = ''
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'

function Resolve-RepoRoot {
  param([string]$RequestedRoot)

  if (-not [string]::IsNullOrWhiteSpace($RequestedRoot)) {
    return (Resolve-Path -LiteralPath $RequestedRoot).Path
  }
  return (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
}

function Test-SafeToken {
  param([string]$Value)
  return -not [string]::IsNullOrWhiteSpace($Value) -and $Value -match '^[a-zA-Z0-9][a-zA-Z0-9._:-]{1,127}$'
}

function Test-PathWithinRoot {
  param(
    [string]$RootPath,
    [string]$CandidatePath
  )

  $rootFull = [System.IO.Path]::GetFullPath($RootPath).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar)
  $candidateFull = [System.IO.Path]::GetFullPath($CandidatePath)
  return $candidateFull.Equals($rootFull, [System.StringComparison]::OrdinalIgnoreCase) -or
    $candidateFull.StartsWith($rootFull + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase) -or
    $candidateFull.StartsWith($rootFull + [System.IO.Path]::AltDirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)
}

function ConvertTo-ActorScopePolicy {
  param([string]$RawPolicy)

  $policy = @{}
  $text = ([string]$RawPolicy).Trim()
  if ([string]::IsNullOrWhiteSpace($text)) {
    return $policy
  }
  if (($text.StartsWith("'") -and $text.EndsWith("'")) -or ($text.StartsWith('"') -and $text.EndsWith('"'))) {
    $text = $text.Substring(1, $text.Length - 2)
  }

  try {
    $parsed = $text | ConvertFrom-Json -ErrorAction Stop
  } catch {
    throw 'invalid_existing_actor_scope_json'
  }
  if ($null -eq $parsed -or $null -eq $parsed.PSObject -or $null -eq $parsed.PSObject.Properties) {
    throw 'invalid_existing_actor_scope_json'
  }

  foreach ($property in $parsed.PSObject.Properties) {
    $actorId = [string]$property.Name
    if (-not (Test-SafeToken -Value $actorId)) {
      throw 'invalid_existing_actor_scope_actor'
    }
    if ($property.Value -is [string] -or $null -eq $property.Value) {
      throw 'invalid_existing_actor_scope_list'
    }
    $scopes = @()
    foreach ($rawScope in @($property.Value)) {
      $scopeId = [string]$rawScope
      if (-not (Test-SafeToken -Value $scopeId)) {
        throw 'invalid_existing_actor_scope_value'
      }
      if ($scopes -notcontains $scopeId) {
        $scopes += $scopeId
      }
    }
    $policy[$actorId] = $scopes
  }

  return $policy
}

function ConvertFrom-ActorScopePolicy {
  param([hashtable]$Policy)

  $ordered = [ordered]@{}
  foreach ($actorId in @($Policy.Keys | Sort-Object)) {
    $ordered[$actorId] = @($Policy[$actorId])
  }
  return ($ordered | ConvertTo-Json -Compress -Depth 10)
}

function New-ReceiptId {
  return ('apiscopeenv_{0}_{1}' -f ([DateTimeOffset]::UtcNow.ToUnixTimeSeconds()), ([Guid]::NewGuid().ToString('N').Substring(0, 8)))
}

$repoRoot = Resolve-RepoRoot -RequestedRoot $Root
$envPath = Join-Path $repoRoot '.env'
$receiptRoot = Join-Path $repoRoot 'data\approvals\actor_scope_env_receipts'

if (-not (Test-PathWithinRoot -RootPath $repoRoot -CandidatePath $envPath) -or -not (Test-PathWithinRoot -RootPath $repoRoot -CandidatePath $receiptRoot)) {
  throw 'resolved_actor_scope_paths_outside_repo_root'
}

$profile = if ([string]::IsNullOrWhiteSpace($EnvProfile)) { [string]$env:FRANCIS_ENV_PROFILE } else { $EnvProfile }
$profile = $profile.Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($profile)) {
  $profile = 'dev'
}
$profileAllowed = @('dev', 'workstation') -contains $profile
$safeActor = [string]$Actor
$safeScope = [string]$Scope
$safeReason = if ([string]::IsNullOrWhiteSpace($Reason)) { 'actor_scope_env_update' } else { [string]$Reason }
$safeReason = ($safeReason -replace '[\r\n]+', ' ').Trim()

$status = 'ready'
$ok = $true
$errorCode = ''
if (-not $profileAllowed) {
  $status = 'blocked_env_profile'
  $ok = $false
  $errorCode = 'env_profile_not_allowed'
} elseif (-not (Test-SafeToken -Value $safeActor)) {
  $status = 'blocked_invalid_actor'
  $ok = $false
  $errorCode = 'invalid_actor'
} elseif (-not (Test-SafeToken -Value $safeScope)) {
  $status = 'blocked_invalid_scope'
  $ok = $false
  $errorCode = 'invalid_scope'
}

$lines = @()
if (Test-Path -LiteralPath $envPath -PathType Leaf) {
  $lines = @(Get-Content -LiteralPath $envPath)
}

$scopeLineIndexes = @()
for ($index = 0; $index -lt $lines.Count; $index++) {
  $line = [string]$lines[$index]
  if ($line.TrimStart().StartsWith('FRANCIS_API_ACTOR_SCOPES=')) {
    $scopeLineIndexes += $index
  }
}
if ($scopeLineIndexes.Count -gt 1) {
  $status = 'blocked_duplicate_actor_scope_lines'
  $ok = $false
  $errorCode = 'duplicate_actor_scope_lines'
}

$policy = @{}
if ($ok -and $scopeLineIndexes.Count -eq 1) {
  $existingLine = [string]$lines[$scopeLineIndexes[0]]
  $existingValue = $existingLine.Substring($existingLine.IndexOf('=') + 1)
  try {
    $policy = ConvertTo-ActorScopePolicy -RawPolicy $existingValue
  } catch {
    $status = 'blocked_invalid_existing_policy'
    $ok = $false
    $errorCode = [string]$_.Exception.Message
  }
}

$existingScopes = if ($policy.ContainsKey($safeActor)) { @($policy[$safeActor]) } else { @() }
$scopeAlreadyPresent = $existingScopes -contains $safeScope
$changed = $false
if ($ok -and -not $scopeAlreadyPresent) {
  $policy[$safeActor] = @($existingScopes + $safeScope | Select-Object -Unique)
  $changed = $true
}

$receiptPath = ''
$receipt = $null
if ($ok -and $Mode -eq 'Apply') {
  $policyJson = ConvertFrom-ActorScopePolicy -Policy $policy
  $scopeLine = "FRANCIS_API_ACTOR_SCOPES=$policyJson"
  $nextLines = @($lines)
  if ($scopeLineIndexes.Count -eq 1) {
    $nextLines[$scopeLineIndexes[0]] = $scopeLine
  } else {
    $nextLines += $scopeLine
  }

  if ($changed -or -not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
    [System.IO.File]::WriteAllLines($envPath, [string[]]$nextLines, [System.Text.UTF8Encoding]::new($false))
  }

  $receiptId = New-ReceiptId
  $receiptPath = Join-Path $receiptRoot "$receiptId.json"
  New-Item -ItemType Directory -Path $receiptRoot -Force | Out-Null
  $receipt = [ordered]@{
    kind = 'francis.api.actor_scope_env.receipt'
    receipt_id = $receiptId
    actor = $safeActor
    scope = $safeScope
    reason = $safeReason
    decision = $(if ($changed) { 'scope_added_to_repo_env' } else { 'scope_already_present_in_repo_env' })
    env_profile = $profile
    env_file = '.env'
    recorded_ts = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
    writes_env_file = $true
    writes_receipt = $true
    writes_confirmation_receipt = $false
    writes_evidence = $false
    marks_stage16_closed = $false
    grants_execution_authority = $false
    grants_mutation_authority = $false
    governance = [ordered]@{
      local_repo_env_only = $true
      dev_or_workstation_only = $true
      production_allowed = $false
      regulated_profile_allowed = $false
      subdelegation_allowed = $false
      preserves_existing_actor_scopes = $true
      does_not_write_confirmation_receipt = $true
      does_not_capture_sleep_resume_evidence = $true
      does_not_mark_stage16_closed = $true
    }
  }
  $receipt | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $receiptPath -Encoding UTF8
  $status = if ($changed) { 'applied' } else { 'already_present' }
}

$payload = [ordered]@{
  ok = $ok
  kind = 'francis.api.actor_scope_env'
  status = $status
  error = $errorCode
  mode = $Mode
  actor = $safeActor
  scope = $safeScope
  env_profile = $profile
  env_file = '.env'
  env_var = 'FRANCIS_API_ACTOR_SCOPES'
  scope_already_present = $scopeAlreadyPresent
  changed = $changed
  actor_scope_policy_actor_count = @($policy.Keys).Count
  receipt_path = $receiptPath
  receipt = $receipt
  writes_env_file = ($Mode -eq 'Apply' -and $ok)
  writes_receipt = ($Mode -eq 'Apply' -and $ok)
  writes_confirmation_receipt = $false
  writes_evidence = $false
  marks_stage16_closed = $false
  grants_execution_authority = $false
  grants_mutation_authority = $false
  next_smallest_truthful_gap = $(if ($ok) { 'restart_api_and_recheck_stage16_sleep_resume_confirmation_actor_readiness' } else { 'repair_actor_scope_env_configuration' })
  governance = [ordered]@{
    local_repo_env_only = $true
    dev_or_workstation_only = $true
    production_allowed = $false
    regulated_profile_allowed = $false
    validates_actor_and_scope = $true
    rejects_duplicate_env_lines = $true
    preserves_existing_actor_scopes = $true
    does_not_write_confirmation_receipt = $true
    does_not_capture_sleep_resume_evidence = $true
    does_not_mark_stage16_closed = $true
  }
}

$payload | ConvertTo-Json -Depth 8
if ($ok) {
  exit 0
}
exit 1
