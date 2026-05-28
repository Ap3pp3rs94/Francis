param(
    [ValidateSet("Status")]
    [string]$Mode = "Status",
    [string]$StatusPath = "",
    [string]$ExecutionReadinessPath = "",
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [int]$TimeoutSeconds = 5
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptRoot

function ConvertTo-StringArray {
    param([object]$Value)

    if ($null -eq $Value) {
        return @()
    }

    if ($Value -is [System.Array]) {
        return @($Value | ForEach-Object { [string]$_ })
    }

    return @([string]$Value)
}

function Get-PropertyValue {
    param(
        [object]$Object,
        [string]$Name,
        [object]$Default = $null
    )

    if ($null -eq $Object) {
        return $Default
    }

    $Property = $Object.PSObject.Properties[$Name]
    if ($null -eq $Property) {
        return $Default
    }

    return $Property.Value
}

function Get-ScriptCommand {
    $Command = Get-Command pwsh -ErrorAction SilentlyContinue
    if ($null -ne $Command) {
        return $Command.Source
    }

    return (Get-Command powershell -ErrorAction Stop).Source
}

function Read-PythonJsonReadback {
    param([string]$Route)

    $Python = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $Python) {
        return [pscustomobject]@{
            ok = $false
            source = "python"
            evidence = "python"
            payload = $null
            error = "python_unavailable"
        }
    }

    $Source = ""
    $Evidence = ""
    if ($Route -eq "/lens/os-binding/execution/readiness?limit=5") {
        $Source = @'
import json
from francis.lens.os_binding_authority import lens_os_binding_execution_readiness_audit
print(json.dumps(lens_os_binding_execution_readiness_audit(limit=5)))
'@
        $Evidence = "francis.lens.os_binding_authority.lens_os_binding_execution_readiness_audit"
    } else {
        return [pscustomobject]@{
            ok = $false
            source = "python"
            evidence = "unsupported_route"
            payload = $null
            error = "python_readback_route_unsupported"
        }
    }

    $Output = & $Python.Source -c $Source 2>$null
    $ExitCode = $LASTEXITCODE
    $Text = [string]::Join("`n", @($Output))
    if ($ExitCode -ne 0 -or [string]::IsNullOrWhiteSpace($Text)) {
        return [pscustomobject]@{
            ok = $false
            source = "python"
            evidence = $Evidence
            payload = $null
            error = "python_readback_failed"
        }
    }

    try {
        $Payload = $Text | ConvertFrom-Json -ErrorAction Stop
        return [pscustomobject]@{
            ok = $true
            source = "python"
            evidence = $Evidence
            payload = $Payload
            error = ""
        }
    } catch {
        return [pscustomobject]@{
            ok = $false
            source = "python"
            evidence = $Evidence
            payload = $null
            error = [string]$_.Exception.Message
        }
    }
}

function Invoke-JsonScript {
    param(
        [string]$Path,
        [string[]]$Arguments
    )

    $PowerShell = Get-ScriptCommand
    $Raw = & $PowerShell -NoProfile -ExecutionPolicy Bypass -File $Path @Arguments
    $ExitCode = $LASTEXITCODE
    $Text = [string]::Join("`n", @($Raw))
    $Json = $null

    if (-not [string]::IsNullOrWhiteSpace($Text)) {
        try {
            $Json = $Text | ConvertFrom-Json
        } catch {
            $Json = $null
        }
    }

    return [pscustomobject]@{
        exit_code = $ExitCode
        raw = $Text
        json = $Json
    }
}

function Read-JsonReadback {
    param(
        [string]$Path,
        [string]$ApiBaseUrl,
        [string]$Route,
        [int]$TimeoutSeconds
    )

    if (-not [string]::IsNullOrWhiteSpace($Path)) {
        try {
            $ResolvedPath = (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path
            $Payload = Get-Content -LiteralPath $ResolvedPath -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
            return [pscustomobject]@{
                ok = $true
                source = "path"
                evidence = $ResolvedPath
                payload = $Payload
                error = ""
            }
        } catch {
            return [pscustomobject]@{
                ok = $false
                source = "path"
                evidence = $Path
                payload = $null
                error = [string]$_.Exception.Message
            }
        }
    }

    $Base = $ApiBaseUrl.TrimEnd("/")
    $Url = "$Base$Route"
    try {
        $Payload = Invoke-RestMethod -Method Get -Uri $Url -TimeoutSec ([Math]::Max(1, $TimeoutSeconds))
        return [pscustomobject]@{
            ok = $true
            source = "api"
            evidence = $Url
            payload = $Payload
            error = ""
        }
    } catch {
        $ApiError = [string]$_.Exception.Message
        $Fallback = Read-PythonJsonReadback -Route $Route
        if ($Fallback.ok) {
            return $Fallback
        }
        return [pscustomobject]@{
            ok = $false
            source = "api"
            evidence = $Url
            payload = $null
            error = $ApiError
        }
    }
}

function Test-ContainsAll {
    param(
        [string[]]$Actual,
        [string[]]$Expected
    )

    foreach ($Item in $Expected) {
        if ($Actual -notcontains $Item) {
            return $false
        }
    }

    return $true
}

function Select-Blockers {
    param(
        [string[]]$Blockers,
        [string[]]$Names
    )

    return @($Names | Where-Object { $Blockers -contains $_ })
}

function Merge-Unique {
    param([string[][]]$Groups)

    $Seen = @{}
    $Merged = New-Object System.Collections.Generic.List[string]
    foreach ($Group in $Groups) {
        foreach ($Item in $Group) {
            if (-not $Seen.ContainsKey($Item)) {
                $Seen[$Item] = $true
                $Merged.Add($Item)
            }
        }
    }

    return @($Merged)
}

function New-Check {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Status,
        [string[]]$Evidence,
        [string[]]$Missing = @()
    )

    return [pscustomobject]@{
        name = $Name
        passed = $Passed
        status = $Status
        evidence = $Evidence
        missing = $Missing
    }
}

$CommandPaletteArgs = @("-Mode", "Status")
if (-not [string]::IsNullOrWhiteSpace($StatusPath)) {
    $CommandPaletteArgs += @("-StatusPath", $StatusPath)
} else {
    $CommandPaletteArgs += @("-ApiBaseUrl", $ApiBaseUrl, "-TimeoutSeconds", [string]$TimeoutSeconds)
}

$CommandPalette = Invoke-JsonScript -Path (Join-Path $ScriptRoot "lens-command-palette.ps1") -Arguments $CommandPaletteArgs
$SummonPreflight = Invoke-JsonScript -Path (Join-Path $ScriptRoot "lens-summon-preflight.ps1") -Arguments @("-Mode", "Status")
$TrayPreflight = Invoke-JsonScript -Path (Join-Path $ScriptRoot "lens-tray-preflight.ps1") -Arguments @("-Mode", "Status")
$OverlayPreflight = Invoke-JsonScript -Path (Join-Path $ScriptRoot "lens-overlay-preflight.ps1") -Arguments @("-Mode", "Status")
$ExecutionReadinessRequired = (-not [string]::IsNullOrWhiteSpace($ExecutionReadinessPath)) -or [string]::IsNullOrWhiteSpace($StatusPath)
$ExecutionReadiness = $null
if ($ExecutionReadinessRequired) {
    $ExecutionReadiness = Read-JsonReadback `
        -Path $ExecutionReadinessPath `
        -ApiBaseUrl $ApiBaseUrl `
        -Route "/lens/os-binding/execution/readiness?limit=5" `
        -TimeoutSeconds $TimeoutSeconds
}

$PaletteJson = $CommandPalette.json
$SummonJson = $SummonPreflight.json
$TrayJson = $TrayPreflight.json
$OverlayJson = $OverlayPreflight.json
$ExecutionReadinessJson = if ($null -ne $ExecutionReadiness) { $ExecutionReadiness.payload } else { $null }

$PaletteGovernance = Get-PropertyValue -Object $PaletteJson -Name "governance"
$SummonGovernance = Get-PropertyValue -Object $SummonJson -Name "governance"
$TrayGovernance = Get-PropertyValue -Object $TrayJson -Name "governance"
$OverlayGovernance = Get-PropertyValue -Object $OverlayJson -Name "governance"
$ExecutionReadinessGovernance = Get-PropertyValue -Object $ExecutionReadinessJson -Name "governance"

$PaletteBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $PaletteJson -Name "blockers" -Default @())
$SummonBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $SummonJson -Name "blockers" -Default @())
$TrayBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $TrayJson -Name "blockers" -Default @())
$OverlayBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $OverlayJson -Name "blockers" -Default @())
$ExecutionReadinessBlockers = ConvertTo-StringArray (
    Get-PropertyValue -Object $ExecutionReadinessJson -Name "blockers" -Default @()
)
$ExecutionReadinessBlockedRequirements = ConvertTo-StringArray (
    Get-PropertyValue -Object $ExecutionReadinessJson -Name "blocked_requirements" -Default @()
)

$PaletteBindingBlockers = Select-Blockers -Blockers $PaletteBlockers -Names @(
    "os_level_command_palette_missing",
    "summon_anywhere_missing",
    "global_hotkey_binding_missing"
)
$GlobalHotkeyBlockers = Select-Blockers -Blockers $SummonBlockers -Names @(
    "global_hotkey_binding_disabled",
    "global_hotkey_registration_disabled",
    "hotkey_registration_authority_not_granted"
)
$SummonBindingBlockers = Select-Blockers -Blockers $SummonBlockers -Names @(
    "lens_summon_binding_disabled_pending_authority",
    "summon_authority_not_granted"
)
$TrayPresenceBlockers = Select-Blockers -Blockers $TrayBlockers -Names @(
    "tray_host_disabled",
    "tray_icon_disabled",
    "tray_registration_authority_not_granted"
)
$OverlayWindowBlockers = Select-Blockers -Blockers $OverlayBlockers -Names @(
    "overlay_window_disabled",
    "always_on_top_disabled",
    "overlay_control_authority_not_granted"
)
$AuthorityBlockers = Merge-Unique -Groups @(
    (Select-Blockers -Blockers $SummonBlockers -Names @(
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "local_process_launch_authority_not_granted"
    )),
    (Select-Blockers -Blockers $TrayBlockers -Names @(
        "tray_registration_authority_not_granted",
        "local_process_launch_authority_not_granted"
    )),
    (Select-Blockers -Blockers $OverlayBlockers -Names @(
        "overlay_control_authority_not_granted",
        "local_process_launch_authority_not_granted"
    ))
)

$PaletteBridgeObserved = (
    $CommandPalette.exit_code -eq 0 -and
    (Get-PropertyValue -Object $PaletteJson -Name "kind") -eq "lens.command_palette.shell_bridge" -and
    (Get-PropertyValue -Object $PaletteJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $PaletteJson -Name "readback_ready") -eq $true -and
    @("chat_ui_only", "os_runtime") -contains (Get-PropertyValue -Object $PaletteJson -Name "availability") -and
    (Get-PropertyValue -Object $PaletteJson -Name "os_level_command_palette") -eq $false -and
    [int](Get-PropertyValue -Object $PaletteJson -Name "command_total" -Default 0) -gt 0 -and
    (Get-PropertyValue -Object $PaletteJson -Name "next_smallest_truthful_gap") -eq "os_level_command_palette_binding" -and
    $PaletteBlockers -contains "os_level_command_palette_missing"
)
$SummonPreflightObserved = (
    $SummonPreflight.exit_code -eq 0 -and
    (Get-PropertyValue -Object $SummonJson -Name "kind") -eq "lens.summon.preflight" -and
    (Get-PropertyValue -Object $SummonJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $SummonJson -Name "ready") -eq $false -and
    (Test-ContainsAll -Actual $SummonBlockers -Expected @(
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted"
    ))
)
$TrayPreflightObserved = (
    $TrayPreflight.exit_code -eq 0 -and
    (Get-PropertyValue -Object $TrayJson -Name "kind") -eq "lens.tray.preflight" -and
    (Get-PropertyValue -Object $TrayJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $TrayJson -Name "ready") -eq $false -and
    (Test-ContainsAll -Actual $TrayBlockers -Expected @(
        "tray_host_disabled",
        "tray_icon_disabled",
        "tray_registration_authority_not_granted"
    ))
)
$OverlayPreflightObserved = (
    $OverlayPreflight.exit_code -eq 0 -and
    (Get-PropertyValue -Object $OverlayJson -Name "kind") -eq "lens.overlay.preflight" -and
    (Get-PropertyValue -Object $OverlayJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $OverlayJson -Name "ready") -eq $false -and
    (Test-ContainsAll -Actual $OverlayBlockers -Expected @(
        "overlay_window_disabled",
        "always_on_top_disabled",
        "overlay_control_authority_not_granted"
    ))
)

$SideEffectsDenied = (
    (Get-PropertyValue -Object $PaletteGovernance -Name "opens_palette") -eq $false -and
    (Get-PropertyValue -Object $PaletteGovernance -Name "hotkey_registration_authority") -eq $false -and
    (Get-PropertyValue -Object $PaletteGovernance -Name "tray_registration_authority") -eq $false -and
    (Get-PropertyValue -Object $PaletteGovernance -Name "local_process_launch_authority") -eq $false -and
    (Get-PropertyValue -Object $SummonGovernance -Name "summon_authority") -eq $false -and
    (Get-PropertyValue -Object $SummonGovernance -Name "hotkey_registration_authority") -eq $false -and
    (Get-PropertyValue -Object $TrayGovernance -Name "tray_registration_authority") -eq $false -and
    (Get-PropertyValue -Object $OverlayGovernance -Name "overlay_control_authority") -eq $false
)

$OsBindingCandidateRequiredAuthority = @(
    "lens.os_binding.command_palette_binding_authority",
    "hotkey_registration_authority",
    "summon_authority",
    "local_process_launch_authority"
)
$OsBindingCandidateAuthorityBlockers = Select-Blockers -Blockers $AuthorityBlockers -Names @(
    "summon_authority_not_granted",
    "hotkey_registration_authority_not_granted",
    "local_process_launch_authority_not_granted"
)
$OsBindingCandidateBlockedBy = Merge-Unique -Groups @(
    $PaletteBindingBlockers,
    $GlobalHotkeyBlockers,
    $SummonBindingBlockers,
    $OsBindingCandidateAuthorityBlockers
)
$OsBindingCandidateObserved = (
    $PaletteBridgeObserved -and
    $SummonPreflightObserved -and
    $SideEffectsDenied -and
    -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Object $SummonJson -Name "global_hotkey" -Default "")) -and
    -not [string]::IsNullOrWhiteSpace([string](Get-PropertyValue -Object $SummonJson -Name "binding_scope" -Default "")) -and
    (Test-ContainsAll -Actual $OsBindingCandidateBlockedBy -Expected @(
        "os_level_command_palette_missing",
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "lens_summon_binding_disabled_pending_authority",
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "local_process_launch_authority_not_granted"
    ))
)
$ExecutionReadinessCommonObserved = (
    $ExecutionReadinessRequired -and
    $null -ne $ExecutionReadiness -and
    $ExecutionReadiness.ok -eq $true -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "kind") -eq "lens.os_binding.command_palette_binding.execution_readiness" -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "route") -eq "/lens/os-binding/execution/readiness" -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "execute_route") -eq "/lens/os-binding/execute" -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "denials_route") -eq "/lens/os-binding/denials" -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "ready") -eq $false -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "execution_ready") -eq $false -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "summon_anywhere" -Default $false) -eq $false -and
    $ExecutionReadinessBlockers -contains "os_binding_execution_boundary_not_implemented" -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "read_only_contract") -eq $true -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "execution_authority") -eq $false -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "approval_decision_authority") -eq $false -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "memory_write") -eq $false
)
$ExecutionReadinessPreAuthorityObserved = (
    $ExecutionReadinessCommonObserved -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "os_level_command_palette" -Default $false) -eq $false -and
    $ExecutionReadinessBlockedRequirements -contains "global_hotkey_binding" -and
    $ExecutionReadinessBlockedRequirements -contains "summon_binding"
)
$ExecutionReadinessPostAuthorityObserved = (
    $ExecutionReadinessCommonObserved -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "os_level_command_palette" -Default $false) -eq $true -and
    $ExecutionReadinessBlockedRequirements -contains "system_write_permission" -and
    $ExecutionReadinessBlockedRequirements -contains "summon_binding" -and
    $ExecutionReadinessBlockedRequirements -contains "resident_host" -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "authority_granted" -Default $false) -eq $true -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "os_level_command_palette_binding_authority" -Default $false) -eq $true
)
$ExecutionReadinessRuntimePrerequisitesObserved = (
    $ExecutionReadinessCommonObserved -and
    (Get-PropertyValue -Object $ExecutionReadinessJson -Name "os_level_command_palette" -Default $false) -eq $true -and
    $ExecutionReadinessBlockedRequirements -contains "system_write_permission" -and
    $ExecutionReadinessBlockedRequirements -contains "os_binding_authority_grant" -and
    $ExecutionReadinessBlockedRequirements -contains "summon_binding" -and
    $ExecutionReadinessBlockedRequirements -contains "resident_host" -and
    $ExecutionReadinessBlockedRequirements -contains "tray_presence" -and
    $ExecutionReadinessBlockedRequirements -contains "overlay_window" -and
    $ExecutionReadinessBlockers -contains "os_level_command_palette_binding_authority_not_granted" -and
    $ExecutionReadinessBlockers -contains "lens_host_persistent_supervision_prerequisites_pending" -and
    $ExecutionReadinessBlockers -contains "overlay_window_missing" -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "authority_granted" -Default $false) -eq $false -and
    (Get-PropertyValue -Object $ExecutionReadinessGovernance -Name "os_level_command_palette_binding_authority" -Default $false) -eq $false
)
$ExecutionReadinessObserved = (
    $ExecutionReadinessPreAuthorityObserved -or
    $ExecutionReadinessPostAuthorityObserved -or
    $ExecutionReadinessRuntimePrerequisitesObserved
)
$ExecutionReadinessSatisfied = if ($ExecutionReadinessRequired) { $ExecutionReadinessObserved } else { $true }

$Checks = @(
    (New-Check -Name "command_palette_shell_bridge" -Passed $PaletteBridgeObserved -Status "blocked_readback_ready" -Evidence $PaletteBindingBlockers),
    (New-Check -Name "summon_preflight" -Passed $SummonPreflightObserved -Status "blocked_readback_ready" -Evidence (Merge-Unique -Groups @($GlobalHotkeyBlockers, $SummonBindingBlockers))),
    (New-Check -Name "tray_preflight" -Passed $TrayPreflightObserved -Status "blocked_readback_ready" -Evidence $TrayPresenceBlockers),
    (New-Check -Name "overlay_preflight" -Passed $OverlayPreflightObserved -Status "blocked_readback_ready" -Evidence $OverlayWindowBlockers),
    (New-Check -Name "os_binding_candidate_boundary" -Passed $OsBindingCandidateObserved -Status "candidate_blocked_readback_ready" -Evidence $OsBindingCandidateBlockedBy),
    (New-Check -Name "os_binding_execution_readiness" -Passed $ExecutionReadinessSatisfied -Status $(if ($ExecutionReadinessObserved) { "blocked_readback_ready" } elseif ($ExecutionReadinessRequired) { "missing_or_unexpected" } else { "not_requested" }) -Evidence $ExecutionReadinessBlockers),
    (New-Check -Name "os_binding_side_effects_denied" -Passed $SideEffectsDenied -Status "diagnostic_bounded" -Evidence $AuthorityBlockers)
)

$FailedChecks = @($Checks | Where-Object { -not $_.passed })
$ProofPassed = $FailedChecks.Count -eq 0
$BlockedFamilies = @(
    "palette_binding",
    "global_hotkey_binding",
    "summon_binding",
    "tray_presence",
    "overlay_window",
    "authority"
)

$Payload = [ordered]@{
    kind = "lens.command_palette.os_binding_blockers.proof"
    status = if ($ProofPassed) { "proof_passed" } else { "proof_failed" }
    ok = $ProofPassed
    stage = "Stage 6 / Lens MVP"
    stage_state = "active"
    acceptance_criterion = "summon_anywhere"
    os_level_command_palette_binding_observed = $PaletteBridgeObserved
    summon_preflight_observed = $SummonPreflightObserved
    tray_preflight_observed = $TrayPreflightObserved
    overlay_preflight_observed = $OverlayPreflightObserved
    os_binding_candidate_observed = $OsBindingCandidateObserved
    os_binding_execution_readiness_observed = $ExecutionReadinessObserved
    side_effects_denied = $SideEffectsDenied
    blocked_families = $BlockedFamilies
    first_blocker_family = "palette_binding"
    next_smallest_truthful_gap = "os_level_command_palette_binding"
    blocker_groups = [ordered]@{
        palette_binding = [string[]]@($PaletteBindingBlockers)
        global_hotkey_binding = [string[]]@($GlobalHotkeyBlockers)
        summon_binding = [string[]]@($SummonBindingBlockers)
        tray_presence = [string[]]@($TrayPresenceBlockers)
        overlay_window = [string[]]@($OverlayWindowBlockers)
        authority = [string[]]@($AuthorityBlockers)
    }
    os_binding_candidate = [ordered]@{
        kind = "lens.command_palette.os_binding_candidate"
        status = "blocked"
        candidate = "global_hotkey_to_lens_command_palette_bridge"
        trigger = Get-PropertyValue -Object $SummonJson -Name "global_hotkey"
        binding_scope = Get-PropertyValue -Object $SummonJson -Name "binding_scope"
        route = Get-PropertyValue -Object $PaletteJson -Name "route"
        local_surface = Get-PropertyValue -Object $PaletteJson -Name "local_surface"
        bridge_script = "scripts/lens-command-palette.ps1"
        proof_script = "scripts/lens-command-palette-os-binding-proof.ps1"
        requires_approval_kind = "lens.os_binding.command_palette_binding_authority"
        required_authority = $OsBindingCandidateRequiredAuthority
        required_preflight_families = [string[]]@("palette_binding", "global_hotkey_binding", "summon_binding", "authority")
        blocked_by = $OsBindingCandidateBlockedBy
        current_authorized_effect = "readback_only_status"
        candidate_effect_if_authorized = "open_lens_command_palette_from_governed_os_binding"
        open_mode_authorized = $false
        open_mode_refusal = "lens_command_palette_open_not_authorized"
        would_register_hotkey_now = $false
        would_open_palette_now = $false
        would_summon_anywhere_now = $false
        would_launch_process_now = $false
        would_write_memory_now = $false
        next_smallest_truthful_gap = "os_level_command_palette_binding"
    }
    execution_readiness = [ordered]@{
        status = [string](Get-PropertyValue -Object $ExecutionReadinessJson -Name "status" -Default $(if ($ExecutionReadinessRequired) { "missing" } else { "not_requested" }))
        source = if ($null -ne $ExecutionReadiness) { [string]$ExecutionReadiness.source } else { "not_requested" }
        evidence = if ($null -ne $ExecutionReadiness) { [string]$ExecutionReadiness.evidence } else { "" }
        error = if ($null -ne $ExecutionReadiness) { [string]$ExecutionReadiness.error } else { "" }
        route = [string](Get-PropertyValue -Object $ExecutionReadinessJson -Name "route" -Default "")
        execute_route = [string](Get-PropertyValue -Object $ExecutionReadinessJson -Name "execute_route" -Default "")
        denials_route = [string](Get-PropertyValue -Object $ExecutionReadinessJson -Name "denials_route" -Default "")
        ready = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "ready" -Default $false)
        execution_ready = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "execution_ready" -Default $false)
        os_level_command_palette = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "os_level_command_palette" -Default $false)
        summon_anywhere = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "summon_anywhere" -Default $false)
        denial_boundary_observed = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "denial_boundary_observed" -Default $false)
        denial_receipt_readback_ready = [bool](Get-PropertyValue -Object $ExecutionReadinessJson -Name "denial_receipt_readback_ready" -Default $false)
        blocked_requirements = $ExecutionReadinessBlockedRequirements
        blockers = $ExecutionReadinessBlockers
        next_smallest_truthful_gap = [string](Get-PropertyValue -Object $ExecutionReadinessJson -Name "next_smallest_truthful_gap" -Default "")
    }
    command_palette = [ordered]@{
        status = Get-PropertyValue -Object $PaletteJson -Name "status"
        availability = Get-PropertyValue -Object $PaletteJson -Name "availability"
        os_level_command_palette = Get-PropertyValue -Object $PaletteJson -Name "os_level_command_palette"
        summon_anywhere = Get-PropertyValue -Object $PaletteJson -Name "summon_anywhere"
        url_entrypoint_ready = Get-PropertyValue -Object $PaletteJson -Name "url_entrypoint_ready"
        url_entrypoint = Get-PropertyValue -Object $PaletteJson -Name "url_entrypoint"
        command_total = Get-PropertyValue -Object $PaletteJson -Name "command_total"
        route = Get-PropertyValue -Object $PaletteJson -Name "route"
        local_surface = Get-PropertyValue -Object $PaletteJson -Name "local_surface"
        blockers = [string[]]@($PaletteBlockers)
    }
    summon_preflight = [ordered]@{
        status = Get-PropertyValue -Object $SummonJson -Name "status"
        ready = Get-PropertyValue -Object $SummonJson -Name "ready"
        global_hotkey = Get-PropertyValue -Object $SummonJson -Name "global_hotkey"
        binding_scope = Get-PropertyValue -Object $SummonJson -Name "binding_scope"
        palette_route = Get-PropertyValue -Object $SummonJson -Name "palette_route"
        blockers = $SummonBlockers
    }
    tray_preflight = [ordered]@{
        status = Get-PropertyValue -Object $TrayJson -Name "status"
        ready = Get-PropertyValue -Object $TrayJson -Name "ready"
        blockers = $TrayBlockers
    }
    overlay_preflight = [ordered]@{
        status = Get-PropertyValue -Object $OverlayJson -Name "status"
        ready = Get-PropertyValue -Object $OverlayJson -Name "ready"
        blockers = $OverlayBlockers
    }
    checks = $Checks
    governance = [ordered]@{
        diagnostic_only = $true
        wraps_command_palette_shell_bridge = $true
        wraps_summon_preflight = $true
        wraps_tray_preflight = $true
        wraps_overlay_preflight = $true
        os_binding_candidate_boundary_readback = $OsBindingCandidateObserved
        wraps_os_binding_execution_readiness = $ExecutionReadinessObserved
        read_only_contract = $true
        opens_palette = $false
        execution_authority = $false
        approval_decision_authority = $false
        memory_write = $false
        overlay_control_authority = $false
        window_management_authority = $false
        summon_authority = $false
        hotkey_registration_authority = $false
        tray_registration_authority = $false
        local_process_launch_authority = $false
        service_control_authority = $false
        capture_authority = $false
        new_sensing_authority = $false
        mutation_authority_granted = $false
    }
}

$Payload | ConvertTo-Json -Depth 16

if (-not $ProofPassed) {
    exit 1
}

exit 0
