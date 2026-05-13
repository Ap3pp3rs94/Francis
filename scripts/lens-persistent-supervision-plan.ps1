param(
  [ValidateSet('Status')]
  [string]$Mode = 'Status'
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
& (Join-Path $PSScriptRoot 'assert-runtime-root.ps1') -Root $RepoRoot

function Read-JsonFile {
  param([string]$Path)

  if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
    return $null
  }
  try {
    return Get-Content -LiteralPath $Path -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
  } catch {
    return $null
  }
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
  if ($Payload -is [System.Collections.IDictionary] -and $Payload.Contains($Name)) {
    $Value = $Payload[$Name]
    if ($null -ne $Value) {
      return $Value
    }
    return $Default
  }
  $Property = $Payload.PSObject.Properties[$Name]
  if ($null -eq $Property -or $null -eq $Property.Value) {
    return $Default
  }
  return $Property.Value
}

function ConvertTo-StringArray {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return @()
  }
  if ($Value -is [System.Array]) {
    return @($Value | ForEach-Object { [string]$_ })
  }
  return @([string]$Value)
}

function ConvertTo-Number {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value -or $Value -is [bool]) {
    return 0
  }
  try {
    return [double]$Value
  } catch {
    return 0
  }
}

function Get-DataRoot {
  $Override = [string]$env:FRANCIS_DATA_DIR
  if (-not [string]::IsNullOrWhiteSpace($Override)) {
    return $Override
  }
  return (Join-Path $RepoRoot 'data')
}

function Get-LatestActiveHostSupervisionAuthorityGrant {
  param([string]$DataRoot)

  $GrantRoot = Join-Path $DataRoot 'lens/host_supervision_authority_grants'
  if (-not (Test-Path -LiteralPath $GrantRoot -PathType Container)) {
    return $null
  }

  $Now = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()
  $Candidates = @()
  foreach ($Path in @(Get-ChildItem -LiteralPath $GrantRoot -Filter '*.json' -File -ErrorAction SilentlyContinue)) {
    $Item = Read-JsonFile -Path $Path.FullName
    if ($null -eq $Item) {
      continue
    }
    $Lease = Get-PropertyValue -Payload $Item -Name 'lease' -Default $null
    $Boundary = Get-PropertyValue -Payload $Item -Name 'authority_boundary' -Default $null
    $ExpiresTs = ConvertTo-Number -Value (Get-PropertyValue -Payload $Lease -Name 'expires_ts' -Default (Get-PropertyValue -Payload $Item -Name 'expires_ts' -Default 0))
    if (
      [string](Get-PropertyValue -Payload $Item -Name 'kind' -Default '') -ne 'lens.host.supervision_authority.grant.receipt' -or
      [string](Get-PropertyValue -Payload $Item -Name 'status' -Default '') -ne 'authority_granted' -or
      -not [bool](Get-PropertyValue -Payload $Lease -Name 'active' -Default $false) -or
      -not [bool](Get-PropertyValue -Payload $Boundary -Name 'authority_granted' -Default $false) -or
      $ExpiresTs -le $Now
    ) {
      continue
    }
    $Candidates += $Item
  }

  if ($Candidates.Count -eq 0) {
    return $null
  }
  return @($Candidates | Sort-Object `
    @{Expression = { ConvertTo-Number -Value (Get-PropertyValue -Payload $_ -Name 'created_ts' -Default 0) }; Descending = $true}, `
    @{Expression = { [string](Get-PropertyValue -Payload $_ -Name 'receipt_id' -Default '') }; Descending = $true} `
  )[0]
}

function New-Requirement {
  param(
    [string]$Id,
    [string]$Label,
    [bool]$Ready,
    [string]$Reason,
    [string]$AuthorityRequired = '',
    [bool]$AuthorityGranted = $false
  )

  return [ordered]@{
    id = $Id
    label = $Label
    ready = $Ready
    status = if ($Ready) { 'ready' } else { 'blocked' }
    reason = $Reason
    authority_required = $AuthorityRequired
    authority_granted = $AuthorityGranted
  }
}

function Quote-CommandPart {
  param([string]$Value)

  if ([string]::IsNullOrWhiteSpace($Value)) {
    return '""'
  }
  if ($Value -match '\s' -or $Value.Contains('"')) {
    return '"' + ($Value -replace '"', '\"') + '"'
  }
  return $Value
}

function Test-TruthyProperty {
  param(
    [AllowNull()]
    [object]$Payload,
    [string]$Name
  )

  return [bool](Get-PropertyValue -Payload $Payload -Name $Name -Default $false)
}

function ConvertTo-EpochSeconds {
  param([AllowNull()][object]$Value)

  if ($null -eq $Value) {
    return 0.0
  }
  try {
    return [double]$Value
  } catch {
  }
  try {
    return [double]([System.DateTimeOffset]::Parse([string]$Value)).ToUnixTimeSeconds()
  } catch {
    return 0.0
  }
}

function Get-LatestHostSupervisionExecutionReceipt {
  param([string]$DataRoot)

  $ReceiptRoot = Join-Path $DataRoot 'lens/host_supervision_executions'
  if (-not (Test-Path -LiteralPath $ReceiptRoot -PathType Container)) {
    return $null
  }

  $Latest = $null
  $LatestTs = 0.0
  foreach ($File in Get-ChildItem -LiteralPath $ReceiptRoot -Filter '*.json' -File -ErrorAction SilentlyContinue) {
    $Receipt = Read-JsonFile -Path $File.FullName
    if ($null -eq $Receipt) {
      continue
    }
    if ([string](Get-PropertyValue -Payload $Receipt -Name 'kind' -Default '') -ne 'lens.host.supervision.execution.receipt') {
      continue
    }
    $Ts = ConvertTo-EpochSeconds -Value (Get-PropertyValue -Payload $Receipt -Name 'created_ts' -Default 0)
    if ($null -eq $Latest -or $Ts -ge $LatestTs) {
      $Latest = $Receipt
      $LatestTs = $Ts
    }
  }
  return $Latest
}

function Get-ResidentCandidateReadback {
  param([string]$DataRoot)

  $SupervisorStatusPath = Join-Path $DataRoot 'runtime/lens-host-supervisor/status.json'
  $SupervisorStatus = Read-JsonFile -Path $SupervisorStatusPath
  $SupervisorKind = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'kind' -Default '')
  $SupervisorState = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'status' -Default '')
  $SupervisorMode = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'mode' -Default '')
  $SupervisorHostMode = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'host_mode' -Default '')
  $SupervisorObservedPid = [int](Get-PropertyValue -Payload $SupervisorStatus -Name 'observed_pid' -Default 0)
  $SupervisorUpdatedAt = [string](Get-PropertyValue -Payload $SupervisorStatus -Name 'updated_at' -Default '')
  $UpdatedTs = ConvertTo-EpochSeconds -Value $SupervisorUpdatedAt
  $FreshWindowSeconds = 900
  $NowTs = [double]([System.DateTimeOffset]::UtcNow.ToUnixTimeSeconds())
  $FreshSupervisorCandidate = (
    $SupervisorKind -eq 'lens.host.supervisor_state' -and
    $SupervisorState -eq 'supervised_session_completed' -and
    $SupervisorMode -eq 'supervise_resident_once' -and
    $SupervisorHostMode -eq 'resident' -and
    $UpdatedTs -gt 0 -and
    (($NowTs - $UpdatedTs) -le $FreshWindowSeconds)
  )
  $ResidentSupervisedRuntime = (
    $SupervisorKind -eq 'lens.host.supervisor_state' -and
    $SupervisorState -eq 'resident_supervising' -and
    $SupervisorMode -eq 'supervise_resident' -and
    $SupervisorHostMode -eq 'resident' -and
    (Test-TruthyProperty -Payload $SupervisorStatus -Name 'resident_supervised_runtime') -and
    $UpdatedTs -gt 0 -and
    (($NowTs - $UpdatedTs) -le $FreshWindowSeconds)
  )

  $Receipt = Get-LatestHostSupervisionExecutionReceipt -DataRoot $DataRoot
  $ReceiptExecution = Get-PropertyValue -Payload $Receipt -Name 'execution' -Default $null
  $ReceiptStatus = [string](Get-PropertyValue -Payload $Receipt -Name 'status' -Default '')
  $ReceiptCandidate = (
    $null -ne $Receipt -and
    $ReceiptStatus -eq 'resident_candidate_supervised_not_persistent' -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'bounded_supervised_session') -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'temporary_host_process_observed') -and
    (Test-TruthyProperty -Payload $ReceiptExecution -Name 'resident_runtime_candidate_supervised') -and
    -not (Test-TruthyProperty -Payload $ReceiptExecution -Name 'resident_supervised_runtime')
  )

  return [ordered]@{
    resident_runtime_candidate_supervised = [bool]($FreshSupervisorCandidate -or $ReceiptCandidate)
    resident_supervised_runtime = [bool]$ResidentSupervisedRuntime
    supervision_observed_pid = $SupervisorObservedPid
    fresh_resident_runtime_candidate_supervised = [bool]$FreshSupervisorCandidate
    supervision_execution_receipt_observed = [bool]$ReceiptCandidate
    supervision_execution_receipt_id = [string](Get-PropertyValue -Payload $Receipt -Name 'receipt_id' -Default '')
    supervision_execution_readback_status = if ($ReceiptCandidate) { 'receipt_observed' } else { 'empty' }
    supervision_execution_next_smallest_truthful_gap = if ($ReceiptCandidate) {
      [string](Get-PropertyValue -Payload $ReceiptExecution -Name 'next_smallest_truthful_gap' -Default 'resident_supervision_not_persistent')
    } else {
      ''
    }
    supervisor_freshness_status = if ($FreshSupervisorCandidate -or $ResidentSupervisedRuntime) { 'fresh' } elseif ($null -ne $SupervisorStatus) { 'stale_or_not_candidate' } else { 'missing' }
    supervisor_state_age_seconds = if ($UpdatedTs -gt 0) { [int]([Math]::Max(0, $NowTs - $UpdatedTs)) } else { $null }
  }
}

function Get-HostProcessReadback {
  param([string]$DataRoot)

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-host'
  $PidPath = Join-Path $RuntimeRoot 'lens-host.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = [string](Get-PropertyValue -Payload $Status -Name 'kind' -Default '')
  $StatusValue = [string](Get-PropertyValue -Payload $Status -Name 'status' -Default '')
  $StatusPid = [int](Get-PropertyValue -Payload $Status -Name 'pid' -Default 0)
  $HostPid = 0
  if (Test-Path -LiteralPath $PidPath -PathType Leaf) {
    try {
      $HostPid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $HostPid = 0
    }
  }

  $StatusClaimsRunningHost = (
    $StatusKind -eq 'lens.host.runtime_state' -and
    @('foreground_running', 'resident_running') -contains $StatusValue -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $HostPid
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningHost -and $HostPid -gt 0) {
    try {
      $ProcessAlive = $null -ne (Get-Process -Id $HostPid -ErrorAction Stop)
    } catch {
      $ProcessAlive = $false
    }
  }

  $CandidateReadback = Get-ResidentCandidateReadback -DataRoot $DataRoot
  $CandidateObserved = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'resident_runtime_candidate_supervised' -Default $false)
  $ResidentSupervisedRuntime = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'resident_supervised_runtime' -Default $false)
  $SupervisorObservedPid = [int](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_observed_pid' -Default 0)
  $SupervisedResidentProcess = (
    $ProcessAlive -and
    $ResidentSupervisedRuntime -and
    $HostPid -gt 0 -and
    ($SupervisorObservedPid -eq 0 -or $SupervisorObservedPid -eq $HostPid)
  )
  $BlockedReason = if ($SupervisedResidentProcess) {
    ''
  } elseif ($ProcessAlive) {
    'resident_host_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_supervision_not_persistent'
  } else {
    'resident_host_process_missing'
  }
  $Blocker = if ($SupervisedResidentProcess) {
    ''
  } elseif ($ProcessAlive) {
    'resident_host_process_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_supervision_not_persistent'
  } else {
    'resident_host_process_missing'
  }
  $RequirementState = if ($SupervisedResidentProcess) {
    'ready'
  } elseif ($ProcessAlive) {
    'foreground_observed_not_supervised'
  } elseif ($CandidateObserved) {
    'resident_candidate_observed_not_persistent'
  } else {
    'missing'
  }
  $NextGap = if ($SupervisedResidentProcess) {
    ''
  } elseif ($CandidateObserved) {
    'resident_supervision_not_persistent'
  } else {
    'resident_host_process_not_supervised'
  }

  return [ordered]@{
    process_alive = $ProcessAlive
    pid = $HostPid
    status_path = $StatusPath
    pid_path = $PidPath
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    blocked_reason = $BlockedReason
    blocker = $Blocker
    requirement_state = $RequirementState
    next_smallest_truthful_gap = $NextGap
    resident_supervised_runtime = [bool]$SupervisedResidentProcess
    supervision_observed_pid = $SupervisorObservedPid
    resident_runtime_candidate_supervised = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'resident_runtime_candidate_supervised' -Default $false)
    fresh_resident_runtime_candidate_supervised = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'fresh_resident_runtime_candidate_supervised' -Default $false)
    supervision_execution_receipt_observed = [bool](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_receipt_observed' -Default $false)
    supervision_execution_receipt_id = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_receipt_id' -Default '')
    supervision_execution_readback_status = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_readback_status' -Default '')
    supervision_execution_next_smallest_truthful_gap = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervision_execution_next_smallest_truthful_gap' -Default '')
    supervisor_freshness_status = [string](Get-PropertyValue -Payload $CandidateReadback -Name 'supervisor_freshness_status' -Default '')
    supervisor_state_age_seconds = Get-PropertyValue -Payload $CandidateReadback -Name 'supervisor_state_age_seconds' -Default $null
  }
}

function Get-ProcessAlive {
  param([int]$ProcessId)

  if ($ProcessId -le 0) {
    return $false
  }
  try {
    return $null -ne (Get-Process -Id $ProcessId -ErrorAction Stop)
  } catch {
    return $false
  }
}

function Get-TrayRuntimeReadback {
  param([string]$DataRoot)

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-tray'
  $PidPath = Join-Path $RuntimeRoot 'lens-tray.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = [string](Get-PropertyValue -Payload $Status -Name 'kind' -Default '')
  $StatusValue = [string](Get-PropertyValue -Payload $Status -Name 'status' -Default '')
  $StatusPid = [int](Get-PropertyValue -Payload $Status -Name 'pid' -Default 0)
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsRunningTray = (
    $StatusKind -eq 'lens.tray.runtime_state' -and
    $StatusValue -eq 'tray_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningTray) {
    $ProcessAlive = Get-ProcessAlive -ProcessId $RuntimePid
  }
  $TrayIconVisible = $ProcessAlive -and (Test-TruthyProperty -Payload $Status -Name 'tray_icon_visible')
  $RequirementState = if ($TrayIconVisible) {
    'ready'
  } elseif ($ProcessAlive) {
    'process_running_no_icon_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($TrayIconVisible) {
    ''
  } elseif ($ProcessAlive) {
    'tray_icon_not_observed'
  } else {
    'tray_presence_runtime_missing'
  }

  return [ordered]@{
    ready = $TrayIconVisible
    process_alive = $ProcessAlive
    tray_icon_visible = $TrayIconVisible
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = 'data/runtime/lens-tray/status.json'
    pid_path = 'data/runtime/lens-tray/lens-tray.pid'
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function Get-HotkeyRuntimeReadback {
  param(
    [string]$DataRoot,
    [AllowNull()]
    [object]$SummonConfig
  )

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-hotkey'
  $PidPath = Join-Path $RuntimeRoot 'lens-hotkey.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = [string](Get-PropertyValue -Payload $Status -Name 'kind' -Default '')
  $StatusValue = [string](Get-PropertyValue -Payload $Status -Name 'status' -Default '')
  $StatusPid = [int](Get-PropertyValue -Payload $Status -Name 'pid' -Default 0)
  $ExpectedGlobalHotkey = [string](Get-PropertyValue -Payload $SummonConfig -Name 'global_hotkey' -Default 'Ctrl+Alt+Space')
  $ExpectedBindingScope = [string](Get-PropertyValue -Payload $SummonConfig -Name 'binding_scope' -Default 'global')
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsBoundHotkey = (
    $StatusKind -eq 'lens.hotkey.runtime_state' -and
    $StatusValue -eq 'hotkey_bound' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    (Test-TruthyProperty -Payload $Status -Name 'hotkey_bound') -and
    [string](Get-PropertyValue -Payload $Status -Name 'global_hotkey' -Default '') -eq $ExpectedGlobalHotkey -and
    [string](Get-PropertyValue -Payload $Status -Name 'binding_scope' -Default '') -eq $ExpectedBindingScope
  )
  $ProcessAlive = $false
  if ($StatusClaimsBoundHotkey) {
    $ProcessAlive = Get-ProcessAlive -ProcessId $RuntimePid
  }
  $HotkeyBound = $ProcessAlive -and $StatusClaimsBoundHotkey
  $RequirementState = if ($HotkeyBound) {
    'ready'
  } elseif ($ProcessAlive) {
    'process_running_no_bound_hotkey_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($HotkeyBound) {
    ''
  } elseif ($ProcessAlive) {
    'global_hotkey_binding_not_observed'
  } else {
    'global_hotkey_binding_runtime_missing'
  }

  return [ordered]@{
    ready = $HotkeyBound
    process_alive = $ProcessAlive
    hotkey_bound = $HotkeyBound
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = 'data/runtime/lens-hotkey/status.json'
    pid_path = 'data/runtime/lens-hotkey/lens-hotkey.pid'
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    global_hotkey = [string](Get-PropertyValue -Payload $Status -Name 'global_hotkey' -Default '')
    expected_global_hotkey = $ExpectedGlobalHotkey
    binding_scope = [string](Get-PropertyValue -Payload $Status -Name 'binding_scope' -Default '')
    expected_binding_scope = $ExpectedBindingScope
    launch_on_hotkey = (Test-TruthyProperty -Payload $Status -Name 'launch_on_hotkey')
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function Get-OverlayRuntimeReadback {
  param(
    [string]$DataRoot,
    [AllowNull()]
    [object]$OverlayConfig
  )

  $RuntimeRoot = Join-Path $DataRoot 'runtime/lens-overlay'
  $PidPath = Join-Path $RuntimeRoot 'lens-overlay.pid'
  $StatusPath = Join-Path $RuntimeRoot 'status.json'
  $Status = Read-JsonFile -Path $StatusPath
  $StatusKind = [string](Get-PropertyValue -Payload $Status -Name 'kind' -Default '')
  $StatusValue = [string](Get-PropertyValue -Payload $Status -Name 'status' -Default '')
  $StatusPid = [int](Get-PropertyValue -Payload $Status -Name 'pid' -Default 0)
  $ExpectedOverlayName = [string](Get-PropertyValue -Payload $OverlayConfig -Name 'overlay_name' -Default 'Francis Lens Overlay')
  $ExpectedOverlayScope = [string](Get-PropertyValue -Payload $OverlayConfig -Name 'overlay_scope' -Default 'user_session')
  $RuntimeStateExists = Test-Path -LiteralPath $StatusPath -PathType Leaf
  $PidPresent = Test-Path -LiteralPath $PidPath -PathType Leaf
  $RuntimePid = 0
  if ($PidPresent) {
    try {
      $RuntimePid = [int]((Get-Content -LiteralPath $PidPath -Raw -ErrorAction Stop).Trim())
    } catch {
      $RuntimePid = 0
    }
  }

  $StatusClaimsRunningOverlay = (
    $StatusKind -eq 'lens.overlay.runtime_state' -and
    $StatusValue -eq 'overlay_running' -and
    $StatusPid -gt 0 -and
    $StatusPid -eq $RuntimePid -and
    [string](Get-PropertyValue -Payload $Status -Name 'overlay_name' -Default '') -eq $ExpectedOverlayName -and
    [string](Get-PropertyValue -Payload $Status -Name 'overlay_scope' -Default '') -eq $ExpectedOverlayScope
  )
  $ProcessAlive = $false
  if ($StatusClaimsRunningOverlay) {
    $ProcessAlive = Get-ProcessAlive -ProcessId $RuntimePid
  }
  $OverlayWindowVisible = $ProcessAlive -and (Test-TruthyProperty -Payload $Status -Name 'overlay_window_visible')
  $AlwaysOnTop = $OverlayWindowVisible -and (Test-TruthyProperty -Payload $Status -Name 'always_on_top')
  $OverlayReady = $OverlayWindowVisible -and $AlwaysOnTop
  $RequirementState = if ($OverlayReady) {
    'ready'
  } elseif ($ProcessAlive) {
    'process_running_no_visible_overlay_claim'
  } elseif ($RuntimeStateExists -or $PidPresent) {
    'stale_or_unverified'
  } else {
    'missing'
  }
  $Blocker = if ($OverlayReady) {
    ''
  } elseif ($ProcessAlive) {
    'overlay_window_not_observed'
  } else {
    'overlay_window_runtime_missing'
  }

  return [ordered]@{
    ready = $OverlayReady
    process_alive = $ProcessAlive
    overlay_window_visible = $OverlayWindowVisible
    always_on_top = $AlwaysOnTop
    pid = $RuntimePid
    pid_present = $PidPresent
    status_path = 'data/runtime/lens-overlay/status.json'
    pid_path = 'data/runtime/lens-overlay/lens-overlay.pid'
    runtime_state_exists = $RuntimeStateExists
    runtime_status = $StatusValue
    runtime_status_kind = $StatusKind
    runtime_status_pid = $StatusPid
    runtime_status_pid_matches_pid_file = ($StatusPid -gt 0 -and $StatusPid -eq $RuntimePid)
    overlay_name = [string](Get-PropertyValue -Payload $Status -Name 'overlay_name' -Default '')
    expected_overlay_name = $ExpectedOverlayName
    overlay_scope = [string](Get-PropertyValue -Payload $Status -Name 'overlay_scope' -Default '')
    expected_overlay_scope = $ExpectedOverlayScope
    requirement_state = $RequirementState
    blocker = $Blocker
  }
}

function New-EnablementDependency {
  param(
    [string]$Id,
    [string]$Family,
    [string]$Route,
    [string]$ReadinessRoute,
    [bool]$Ready,
    [string]$Blocker,
    [string]$RequirementState,
    [string]$BlockedReason,
    [string]$ProofScript = '',
    [string]$PreflightScript = '',
    [AllowNull()]
    [object]$Extra = $null
  )

  $Dependency = [ordered]@{
    id = $Id
    family = $Family
    route = $Route
    readiness_route = $ReadinessRoute
    proof_script = $ProofScript
    preflight_script = $PreflightScript
    ready = $Ready
    status = if ($Ready) { 'ready' } else { 'blocked' }
    blocker = if ($Ready) { '' } else { $Blocker }
    requirement_state = if ($Ready) { 'ready' } else { $RequirementState }
    blocked_reason = if ($Ready) { '' } else { $BlockedReason }
    read_only_contract = $true
    diagnostic_only = $true
    would_execute = $false
    would_mutate = $false
  }

  if ($null -ne $Extra) {
    foreach ($Property in $Extra.PSObject.Properties) {
      $Dependency[$Property.Name] = $Property.Value
    }
  }
  return $Dependency
}

$ConfigRelativePath = 'config/runtime/services/lens-host.json'
$ConfigPath = Join-Path $RepoRoot $ConfigRelativePath
$HostRelativePath = 'scripts/lens-host.ps1'
$HostPath = Join-Path $RepoRoot $HostRelativePath
$ManagerRelativePath = 'scripts/service-install.ps1'
$ManagerPath = Join-Path $RepoRoot $ManagerRelativePath
$TrayConfigRelativePath = 'config/runtime/lens/tray.json'
$SummonConfigRelativePath = 'config/runtime/lens/summon.json'
$OverlayConfigRelativePath = 'config/runtime/lens/overlay.json'
$Config = Read-JsonFile -Path $ConfigPath
$TrayConfig = Read-JsonFile -Path (Join-Path $RepoRoot $TrayConfigRelativePath)
$SummonConfig = Read-JsonFile -Path (Join-Path $RepoRoot $SummonConfigRelativePath)
$OverlayConfig = Read-JsonFile -Path (Join-Path $RepoRoot $OverlayConfigRelativePath)
$DataRoot = Get-DataRoot
$ActiveAuthorityGrant = Get-LatestActiveHostSupervisionAuthorityGrant -DataRoot $DataRoot
$GrantAuthorities = Get-PropertyValue -Payload $ActiveAuthorityGrant -Name 'authorities' -Default $null
$AuthorityGrantActive = $null -ne $ActiveAuthorityGrant

$ConfigPresent = $null -ne $Config
$HostPresent = Test-Path -LiteralPath $HostPath -PathType Leaf
$ManagerPresent = Test-Path -LiteralPath $ManagerPath -PathType Leaf

$ServiceName = [string](Get-PropertyValue -Payload $Config -Name 'service_name' -Default 'Francis-LensHost')
$Executable = [string](Get-PropertyValue -Payload $Config -Name 'service_executable' -Default '')
$Arguments = ConvertTo-StringArray -Value (Get-PropertyValue -Payload $Config -Name 'service_arguments' -Default @())
$PlannedCommandParts = @()
if (-not [string]::IsNullOrWhiteSpace($Executable)) {
  $PlannedCommandParts += Quote-CommandPart -Value $Executable
}
$PlannedCommandParts += @($Arguments | ForEach-Object { Quote-CommandPart -Value $_ })

$ProcessSupervisionEnabled = [bool](Get-PropertyValue -Payload $Config -Name 'process_supervision_enabled' -Default $false)
$PersistentSupervisionEnabled = [bool](Get-PropertyValue -Payload $Config -Name 'persistent_supervision_enabled' -Default $false)
$ProcessRestartAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'process_restart_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'process_restart_authority' -Default $false)
)
$InstallAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'install_authority' -Default $false) -or
  (Get-PropertyValue -Payload $Config -Name 'service_install_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'service_install_authority' -Default $false)
)
$ServiceControlAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'service_control_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'service_control_authority' -Default $false)
)
$ReceiptWriteAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'receipt_write_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'receipt_write_authority' -Default $false)
)
$ResidentClaimAuthority = [bool](
  (Get-PropertyValue -Payload $Config -Name 'resident_claim_authority' -Default $false) -or
  (Get-PropertyValue -Payload $GrantAuthorities -Name 'resident_claim_authority' -Default $false)
)

$Requirements = @(
  (New-Requirement -Id 'service_config' -Label 'Lens host service config' -Ready $ConfigPresent -Reason $(if ($ConfigPresent) { '' } else { 'service_config_missing' })),
  (New-Requirement -Id 'host_entrypoint' -Label 'Lens host entrypoint' -Ready $HostPresent -Reason $(if ($HostPresent) { '' } else { 'host_entrypoint_missing' })),
  (New-Requirement -Id 'service_manager' -Label 'Service manager script' -Ready $ManagerPresent -Reason $(if ($ManagerPresent) { '' } else { 'service_manager_missing' })),
  (New-Requirement -Id 'process_supervision_enabled' -Label 'Process supervision enabled' -Ready $ProcessSupervisionEnabled -Reason $(if ($ProcessSupervisionEnabled) { '' } else { 'process_supervision_disabled' }) -AuthorityRequired 'process_supervision'),
  (New-Requirement -Id 'persistent_supervision_enabled' -Label 'Persistent supervision enabled' -Ready $PersistentSupervisionEnabled -Reason $(if ($PersistentSupervisionEnabled) { '' } else { 'persistent_supervision_disabled' }) -AuthorityRequired 'persistent_supervision'),
  (New-Requirement -Id 'process_restart_authority' -Label 'Process restart authority' -Ready $ProcessRestartAuthority -Reason $(if ($ProcessRestartAuthority) { '' } else { 'process_restart_authority_not_granted' }) -AuthorityRequired 'process_restart' -AuthorityGranted $ProcessRestartAuthority),
  (New-Requirement -Id 'service_install_authority' -Label 'Service install authority' -Ready $InstallAuthority -Reason $(if ($InstallAuthority) { '' } else { 'service_install_authority_not_granted' }) -AuthorityRequired 'service_install' -AuthorityGranted $InstallAuthority),
  (New-Requirement -Id 'service_control_authority' -Label 'Service control authority' -Ready $ServiceControlAuthority -Reason $(if ($ServiceControlAuthority) { '' } else { 'service_control_authority_not_granted' }) -AuthorityRequired 'service_control' -AuthorityGranted $ServiceControlAuthority),
  (New-Requirement -Id 'receipt_write_authority' -Label 'Persistent supervision receipt authority' -Ready $ReceiptWriteAuthority -Reason $(if ($ReceiptWriteAuthority) { '' } else { 'receipt_write_authority_not_granted' }) -AuthorityRequired 'receipt_write' -AuthorityGranted $ReceiptWriteAuthority),
  (New-Requirement -Id 'resident_claim_authority' -Label 'Resident claim authority' -Ready $ResidentClaimAuthority -Reason $(if ($ResidentClaimAuthority) { '' } else { 'resident_claim_authority_not_granted' }) -AuthorityRequired 'resident_claim' -AuthorityGranted $ResidentClaimAuthority)
)

$HostProcessReadback = Get-HostProcessReadback -DataRoot $DataRoot
$TrayRuntimeReadback = Get-TrayRuntimeReadback -DataRoot $DataRoot
$HotkeyRuntimeReadback = Get-HotkeyRuntimeReadback -DataRoot $DataRoot -SummonConfig $SummonConfig
$OverlayRuntimeReadback = Get-OverlayRuntimeReadback -DataRoot $DataRoot -OverlayConfig $OverlayConfig
$HostProcessProofScript = if ([bool]$HostProcessReadback.resident_supervised_runtime) {
  ''
} elseif ([string]$HostProcessReadback.blocker -eq 'resident_supervision_not_persistent') {
  'scripts/lens-resident-supervision-persistence-boundary-proof.ps1 -Mode Status'
} else {
  'scripts/lens-resident-host-runtime-boundary-proof.ps1 -Mode Status'
}
$ResidentHostProcessReady = [bool]$HostProcessReadback.resident_supervised_runtime
$TrayConfigReady = (
  (Test-TruthyProperty -Payload $TrayConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_host_enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_enabled') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'startup_register') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_registration_authority') -and
  (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_authority')
)
$TrayRuntimeReady = [bool]$TrayRuntimeReadback.ready
$TrayReady = $TrayConfigReady -or $TrayRuntimeReady
$TrayRequirementState = if ($TrayRuntimeReady) {
  'ready'
} elseif ([string]$TrayRuntimeReadback.requirement_state -ne 'missing') {
  [string]$TrayRuntimeReadback.requirement_state
} else {
  'tray_host_disabled'
}
$TrayBlocker = if ($TrayRuntimeReady) {
  ''
} elseif ([string]$TrayRuntimeReadback.blocker -and [string]$TrayRuntimeReadback.requirement_state -ne 'missing') {
  [string]$TrayRuntimeReadback.blocker
} else {
  'tray_host_missing'
}
$GlobalHotkeyConfigReady = (
  (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'register_hotkey') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'startup_register') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'hotkey_registration_authority')
)
$HotkeyRuntimeReady = [bool]$HotkeyRuntimeReadback.ready
$GlobalHotkeyReady = $GlobalHotkeyConfigReady -or $HotkeyRuntimeReady
$GlobalHotkeyRequirementState = if ($HotkeyRuntimeReady) {
  'ready'
} elseif ([string]$HotkeyRuntimeReadback.requirement_state -ne 'missing') {
  [string]$HotkeyRuntimeReadback.requirement_state
} else {
  'binding_disabled'
}
$GlobalHotkeyBlocker = if ($HotkeyRuntimeReady) {
  ''
} elseif ([string]$HotkeyRuntimeReadback.blocker -and [string]$HotkeyRuntimeReadback.requirement_state -ne 'missing') {
  [string]$HotkeyRuntimeReadback.blocker
} else {
  'global_hotkey_binding_missing'
}
$OverlayConfigReady = (
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_enabled') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'overlay_control_authority') -and
  (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_management_authority')
)
$OverlayRuntimeReady = [bool]$OverlayRuntimeReadback.ready
$OverlayReady = $OverlayConfigReady -or $OverlayRuntimeReady
$OverlayRequirementState = if ($OverlayRuntimeReady) {
  'ready'
} elseif ([string]$OverlayRuntimeReadback.requirement_state -ne 'missing') {
  [string]$OverlayRuntimeReadback.requirement_state
} else {
  'window_disabled'
}
$OverlayBlocker = if ($OverlayRuntimeReady) {
  ''
} elseif ([string]$OverlayRuntimeReadback.blocker -and [string]$OverlayRuntimeReadback.requirement_state -ne 'missing') {
  [string]$OverlayRuntimeReadback.blocker
} else {
  'overlay_window_missing'
}
$SummonReady = (
  (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'summon_authority') -and
  (Test-TruthyProperty -Payload $SummonConfig -Name 'local_process_launch_authority') -and
  $TrayReady -and
  $OverlayReady
)
$RequiredBeforeEnable = @(
  'resident_host_process',
  'tray_presence',
  'global_hotkey_binding',
  'overlay_window',
  'summon_binding'
)
$EnablementDependencyReadback = @(
  (New-EnablementDependency -Id 'resident_host_process' -Family 'resident_host' -Route '/lens/host' -ReadinessRoute '/lens/host/runtime-loop/readiness' -Ready $ResidentHostProcessReady -Blocker ([string]$HostProcessReadback.blocker) -RequirementState ([string]$HostProcessReadback.requirement_state) -BlockedReason ([string]$HostProcessReadback.blocked_reason) -ProofScript $HostProcessProofScript -Extra ([pscustomobject]@{
        process_alive = [bool]$HostProcessReadback.process_alive
        pid = [int]$HostProcessReadback.pid
        runtime_status = [string]$HostProcessReadback.runtime_status
        next_smallest_truthful_gap = [string]$HostProcessReadback.next_smallest_truthful_gap
        resident_supervised_runtime = [bool]$HostProcessReadback.resident_supervised_runtime
        supervision_observed_pid = [int]$HostProcessReadback.supervision_observed_pid
        resident_runtime_candidate_supervised = [bool]$HostProcessReadback.resident_runtime_candidate_supervised
        fresh_resident_runtime_candidate_supervised = [bool]$HostProcessReadback.fresh_resident_runtime_candidate_supervised
        supervision_execution_receipt_observed = [bool]$HostProcessReadback.supervision_execution_receipt_observed
        supervision_execution_receipt_id = [string]$HostProcessReadback.supervision_execution_receipt_id
        supervision_execution_readback_status = [string]$HostProcessReadback.supervision_execution_readback_status
        supervision_execution_next_smallest_truthful_gap = [string]$HostProcessReadback.supervision_execution_next_smallest_truthful_gap
        supervisor_freshness_status = [string]$HostProcessReadback.supervisor_freshness_status
        supervisor_state_age_seconds = $HostProcessReadback.supervisor_state_age_seconds
      })),
  (New-EnablementDependency -Id 'tray_presence' -Family 'tray_presence' -Route '/lens/tray' -ReadinessRoute '/lens/tray/readiness' -Ready $TrayReady -Blocker $TrayBlocker -RequirementState $TrayRequirementState -BlockedReason ([string](Get-PropertyValue -Payload $TrayConfig -Name 'blocked_reason' -Default 'lens_tray_presence_disabled_pending_authority')) -PreflightScript 'scripts/lens-tray-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $TrayConfigRelativePath
        config_exists = $null -ne $TrayConfig
        tray_host_enabled = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_host_enabled')
        tray_icon_enabled = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_enabled')
        tray_registration_authority = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_registration_authority')
        tray_icon_authority = (Test-TruthyProperty -Payload $TrayConfig -Name 'tray_icon_authority')
        tray_config_ready = $TrayConfigReady
        tray_runtime_ready = $TrayRuntimeReady
        tray_presence_source = if ($TrayRuntimeReady) { 'live_runtime_readback' } elseif ($TrayConfigReady) { 'enabled_config' } else { 'blocked_config' }
        tray_runtime_requirement_state = [string]$TrayRuntimeReadback.requirement_state
        tray_runtime_blocker = [string]$TrayRuntimeReadback.blocker
        tray_runtime_process_alive = [bool]$TrayRuntimeReadback.process_alive
        tray_runtime_icon_visible = [bool]$TrayRuntimeReadback.tray_icon_visible
        tray_runtime_pid = [int]$TrayRuntimeReadback.pid
        tray_runtime_status = [string]$TrayRuntimeReadback.runtime_status
        tray_runtime_status_kind = [string]$TrayRuntimeReadback.runtime_status_kind
        tray_runtime_state_exists = [bool]$TrayRuntimeReadback.runtime_state_exists
        tray_runtime_status_pid_matches_pid_file = [bool]$TrayRuntimeReadback.runtime_status_pid_matches_pid_file
      })),
  (New-EnablementDependency -Id 'global_hotkey_binding' -Family 'global_hotkey_binding' -Route '/lens/summon' -ReadinessRoute '/lens/summon/readiness' -Ready $GlobalHotkeyReady -Blocker $GlobalHotkeyBlocker -RequirementState $GlobalHotkeyRequirementState -BlockedReason 'global_hotkey_binding_disabled' -ProofScript 'scripts/lens-summon-global-hotkey-binding-blocker-proof.ps1 -Mode Status' -PreflightScript 'scripts/lens-summon-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $SummonConfigRelativePath
        config_exists = $null -ne $SummonConfig
        global_hotkey = [string](Get-PropertyValue -Payload $SummonConfig -Name 'global_hotkey' -Default '')
        binding_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled')
        register_hotkey = (Test-TruthyProperty -Payload $SummonConfig -Name 'register_hotkey')
        hotkey_registration_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'hotkey_registration_authority')
        hotkey_config_ready = $GlobalHotkeyConfigReady
        hotkey_runtime_ready = $HotkeyRuntimeReady
        global_hotkey_source = if ($HotkeyRuntimeReady) { 'live_runtime_readback' } elseif ($GlobalHotkeyConfigReady) { 'enabled_config' } else { 'blocked_config' }
        hotkey_runtime_requirement_state = [string]$HotkeyRuntimeReadback.requirement_state
        hotkey_runtime_blocker = [string]$HotkeyRuntimeReadback.blocker
        hotkey_runtime_process_alive = [bool]$HotkeyRuntimeReadback.process_alive
        hotkey_runtime_bound = [bool]$HotkeyRuntimeReadback.hotkey_bound
        hotkey_runtime_pid = [int]$HotkeyRuntimeReadback.pid
        hotkey_runtime_status = [string]$HotkeyRuntimeReadback.runtime_status
        hotkey_runtime_status_kind = [string]$HotkeyRuntimeReadback.runtime_status_kind
        hotkey_runtime_state_exists = [bool]$HotkeyRuntimeReadback.runtime_state_exists
        hotkey_runtime_status_pid_matches_pid_file = [bool]$HotkeyRuntimeReadback.runtime_status_pid_matches_pid_file
        os_binding_readiness_route = '/lens/os-binding/readiness'
        os_binding_plan_route = '/lens/os-binding/plan'
        os_binding_authority_route = '/lens/os-binding/authority'
        os_binding_authority_request_route = '/lens/os-binding/authority/request'
        os_binding_authority_requests_route = '/lens/os-binding/authority/requests'
        os_binding_authority_grants_route = '/lens/os-binding/authority/grants'
        os_binding_execution_readiness_route = '/lens/os-binding/execution/readiness'
        os_binding_execution_denials_route = '/lens/os-binding/denials'
        approval_action = 'lens.os_binding.command_palette_binding_authority'
        authority_scope = 'system.write'
      })),
  (New-EnablementDependency -Id 'overlay_window' -Family 'overlay_window' -Route '/lens/overlay' -ReadinessRoute '/lens/overlay/readiness' -Ready $OverlayReady -Blocker $OverlayBlocker -RequirementState $OverlayRequirementState -BlockedReason ([string](Get-PropertyValue -Payload $OverlayConfig -Name 'blocked_reason' -Default 'lens_overlay_window_not_implemented')) -PreflightScript 'scripts/lens-overlay-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $OverlayConfigRelativePath
        config_exists = $null -ne $OverlayConfig
        window_enabled = (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_enabled')
        overlay_control_authority = (Test-TruthyProperty -Payload $OverlayConfig -Name 'overlay_control_authority')
        window_management_authority = (Test-TruthyProperty -Payload $OverlayConfig -Name 'window_management_authority')
        overlay_config_ready = $OverlayConfigReady
        overlay_runtime_ready = $OverlayRuntimeReady
        overlay_window_source = if ($OverlayRuntimeReady) { 'live_runtime_readback' } elseif ($OverlayConfigReady) { 'enabled_config' } else { 'blocked_config' }
        overlay_runtime_requirement_state = [string]$OverlayRuntimeReadback.requirement_state
        overlay_runtime_blocker = [string]$OverlayRuntimeReadback.blocker
        overlay_runtime_process_alive = [bool]$OverlayRuntimeReadback.process_alive
        overlay_runtime_window_visible = [bool]$OverlayRuntimeReadback.overlay_window_visible
        overlay_runtime_always_on_top = [bool]$OverlayRuntimeReadback.always_on_top
        overlay_runtime_pid = [int]$OverlayRuntimeReadback.pid
        overlay_runtime_status = [string]$OverlayRuntimeReadback.runtime_status
        overlay_runtime_status_kind = [string]$OverlayRuntimeReadback.runtime_status_kind
        overlay_runtime_state_exists = [bool]$OverlayRuntimeReadback.runtime_state_exists
        overlay_runtime_status_pid_matches_pid_file = [bool]$OverlayRuntimeReadback.runtime_status_pid_matches_pid_file
      })),
  (New-EnablementDependency -Id 'summon_binding' -Family 'summon_binding' -Route '/lens/summon' -ReadinessRoute '/lens/summon/readiness' -Ready $SummonReady -Blocker 'summon_binding_missing' -RequirementState 'disabled_pending_authority' -BlockedReason ([string](Get-PropertyValue -Payload $SummonConfig -Name 'blocked_reason' -Default 'lens_summon_binding_disabled_pending_authority')) -PreflightScript 'scripts/lens-summon-preflight.ps1 -Mode Status' -Extra ([pscustomobject]@{
        config_path = $SummonConfigRelativePath
        config_exists = $null -ne $SummonConfig
        summon_runner = [string](Get-PropertyValue -Payload $SummonConfig -Name 'summon_runner' -Default 'scripts/lens-summon.ps1')
        local_palette_launcher = [string](Get-PropertyValue -Payload $SummonConfig -Name 'local_palette_launcher' -Default 'scripts/lens-command-palette.ps1 -Mode LocalOpen')
        summon_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'enabled')
        binding_enabled = (Test-TruthyProperty -Payload $SummonConfig -Name 'binding_enabled')
        summon_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'summon_authority')
        local_process_launch_authority = (Test-TruthyProperty -Payload $SummonConfig -Name 'local_process_launch_authority')
      }))
)
$MissingRequiredBeforeEnable = [string[]]@($EnablementDependencyReadback | Where-Object { -not [bool]$_.ready } | ForEach-Object { [string]$_.id })
$FirstMissingRequirementHandoff = $EnablementDependencyReadback | Where-Object { -not [bool]$_.ready } | Select-Object -First 1
$RequiredBeforeEnableReady = $MissingRequiredBeforeEnable.Count -eq 0
$RequiredBeforeEnableGuardNextGap = if ($RequiredBeforeEnableReady) {
  'persistent_supervision_enablement_readiness'
} else {
  'persistent_supervision_required_prerequisites_missing'
}

$BlockedRequirements = @($Requirements | Where-Object { -not [bool]$_.ready })
$BlockedRequirementIds = @($BlockedRequirements | ForEach-Object { [string]$_.id })
$Blockers = @(
  $BlockedRequirements | ForEach-Object {
    $Reason = [string]$_.reason
    if (-not [string]::IsNullOrWhiteSpace($Reason)) {
      $Reason
    }
  }
) | Sort-Object -Unique
if (-not $RequiredBeforeEnableReady) {
  $Blockers = @($Blockers + @('persistent_supervision_required_prerequisites_missing') | Sort-Object -Unique)
}

$Ready = $BlockedRequirements.Count -eq 0 -and $RequiredBeforeEnableReady
$AuthorityRequirementIds = @(
  'process_restart_authority',
  'service_install_authority',
  'service_control_authority',
  'receipt_write_authority',
  'resident_claim_authority'
)
$AuthorityBlocked = @($BlockedRequirementIds | Where-Object { $AuthorityRequirementIds -contains $_ }).Count -gt 0
$NextSmallestTruthfulGap = if ($Ready) {
  'persistent_supervision_execution_boundary'
} elseif (-not $RequiredBeforeEnableReady) {
  'persistent_supervision_required_prerequisites_missing'
} elseif (-not $AuthorityBlocked) {
  'persistent_supervision_execution_boundary'
} else {
  'persistent_supervision_authority_not_granted'
}
$Payload = [ordered]@{
  ok = $true
  kind = 'lens.host.persistent_supervision_plan'
  status = if ($Ready) { 'ready' } else { 'blocked' }
  mode = $Mode.ToLowerInvariant()
  plan_available = $true
  persistent_supervision_ready = $Ready
  resident_claim_allowed = $false
  config_path = $ConfigRelativePath
  config_present = $ConfigPresent
  host_entrypoint = $HostRelativePath
  host_entrypoint_present = $HostPresent
  service_manager = $ManagerRelativePath
  service_manager_present = $ManagerPresent
  service_name = $ServiceName
  planned_command = ($PlannedCommandParts -join ' ')
  data_root = $DataRoot
  authority_grant_active = $AuthorityGrantActive
  authority_grant_route = '/lens/host/supervision/authority'
  authority_grants_route = '/lens/host/supervision/authority/grants'
  authority_grant_receipt_id = [string](Get-PropertyValue -Payload $ActiveAuthorityGrant -Name 'receipt_id' -Default '')
  requirements_total = $Requirements.Count
  requirements_ready_total = ($Requirements.Count - $BlockedRequirements.Count)
  requirements_blocked_total = $BlockedRequirements.Count
  requirements = $Requirements
  blocked_requirements = [string[]]$BlockedRequirementIds
  required_before_enable_ready = $RequiredBeforeEnableReady
  required_before_enable = [string[]]$RequiredBeforeEnable
  missing_required_before_enable = [string[]]$MissingRequiredBeforeEnable
  first_missing_required_before_enable = [string](Get-PropertyValue -Payload $FirstMissingRequirementHandoff -Name 'id' -Default '')
  first_missing_requirement_handoff = $FirstMissingRequirementHandoff
  enablement_dependency_readback = @($EnablementDependencyReadback)
  required_before_enable_guard_next_smallest_truthful_gap = $RequiredBeforeEnableGuardNextGap
  blockers = [string[]]$Blockers
  plan = [ordered]@{
    mode = 'persistent_supervised_resident_host'
    service_name = $ServiceName
    command = ($PlannedCommandParts -join ' ')
    would_install_service = $false
    would_update_service = $false
    would_start_service = $false
    would_restart_process = $false
    would_supervise_process = $false
    would_write_receipt = $false
    would_write_memory = $false
    would_claim_resident = $false
  }
  next_smallest_truthful_gap = $NextSmallestTruthfulGap
  governance = [ordered]@{
    diagnostic_only = $true
    read_only_contract = $true
    execution_authority = $false
    approval_decision_authority = $false
    memory_write = $false
    local_process_launch_authority = $false
    process_supervision_authority = $false
    process_restart_authority = $false
    service_install_authority = $false
    service_control_authority = $false
    receipt_write_authority = $false
    resident_claim_authority = $false
    mutation_authority_granted = $false
  }
  message = 'Persistent Lens host supervision is planned but blocked; this proof does not install, start, supervise, restart, write receipts, write memory, or claim a resident host.'
}

$Payload | ConvertTo-Json -Depth 8
exit 0
