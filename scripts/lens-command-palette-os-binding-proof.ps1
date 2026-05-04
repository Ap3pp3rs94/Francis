param(
    [ValidateSet("Status")]
    [string]$Mode = "Status",
    [string]$StatusPath = "",
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

$PaletteJson = $CommandPalette.json
$SummonJson = $SummonPreflight.json
$TrayJson = $TrayPreflight.json
$OverlayJson = $OverlayPreflight.json

$PaletteGovernance = Get-PropertyValue -Object $PaletteJson -Name "governance"
$SummonGovernance = Get-PropertyValue -Object $SummonJson -Name "governance"
$TrayGovernance = Get-PropertyValue -Object $TrayJson -Name "governance"
$OverlayGovernance = Get-PropertyValue -Object $OverlayJson -Name "governance"

$PaletteBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $PaletteJson -Name "blockers" -Default @())
$SummonBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $SummonJson -Name "blockers" -Default @())
$TrayBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $TrayJson -Name "blockers" -Default @())
$OverlayBlockers = ConvertTo-StringArray (Get-PropertyValue -Object $OverlayJson -Name "blockers" -Default @())

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
    "lens_summon_binding_not_implemented",
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
    (Get-PropertyValue -Object $PaletteJson -Name "availability") -eq "chat_ui_only" -and
    (Get-PropertyValue -Object $PaletteJson -Name "os_level_command_palette") -eq $false -and
    (Get-PropertyValue -Object $PaletteJson -Name "summon_anywhere") -eq $false -and
    (Test-ContainsAll -Actual $PaletteBlockers -Expected @(
        "os_level_command_palette_missing",
        "summon_anywhere_missing",
        "global_hotkey_binding_missing"
    ))
)
$SummonPreflightObserved = (
    $SummonPreflight.exit_code -eq 0 -and
    (Get-PropertyValue -Object $SummonJson -Name "kind") -eq "lens.summon.preflight" -and
    (Get-PropertyValue -Object $SummonJson -Name "status") -eq "blocked" -and
    (Get-PropertyValue -Object $SummonJson -Name "ready") -eq $false -and
    (Test-ContainsAll -Actual $SummonBlockers -Expected @(
        "global_hotkey_binding_disabled",
        "global_hotkey_registration_disabled",
        "lens_summon_binding_not_implemented",
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
        "lens_summon_binding_not_implemented",
        "summon_authority_not_granted",
        "hotkey_registration_authority_not_granted",
        "local_process_launch_authority_not_granted"
    ))
)

$Checks = @(
    (New-Check -Name "command_palette_shell_bridge" -Passed $PaletteBridgeObserved -Status "blocked_readback_ready" -Evidence $PaletteBindingBlockers),
    (New-Check -Name "summon_preflight" -Passed $SummonPreflightObserved -Status "blocked_readback_ready" -Evidence (Merge-Unique -Groups @($GlobalHotkeyBlockers, $SummonBindingBlockers))),
    (New-Check -Name "tray_preflight" -Passed $TrayPreflightObserved -Status "blocked_readback_ready" -Evidence $TrayPresenceBlockers),
    (New-Check -Name "overlay_preflight" -Passed $OverlayPreflightObserved -Status "blocked_readback_ready" -Evidence $OverlayWindowBlockers),
    (New-Check -Name "os_binding_candidate_boundary" -Passed $OsBindingCandidateObserved -Status "candidate_blocked_readback_ready" -Evidence $OsBindingCandidateBlockedBy),
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
    side_effects_denied = $SideEffectsDenied
    blocked_families = $BlockedFamilies
    first_blocker_family = "palette_binding"
    next_smallest_truthful_gap = "os_level_command_palette_binding"
    blocker_groups = [ordered]@{
        palette_binding = $PaletteBindingBlockers
        global_hotkey_binding = $GlobalHotkeyBlockers
        summon_binding = $SummonBindingBlockers
        tray_presence = $TrayPresenceBlockers
        overlay_window = $OverlayWindowBlockers
        authority = $AuthorityBlockers
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
    command_palette = [ordered]@{
        status = Get-PropertyValue -Object $PaletteJson -Name "status"
        availability = Get-PropertyValue -Object $PaletteJson -Name "availability"
        os_level_command_palette = Get-PropertyValue -Object $PaletteJson -Name "os_level_command_palette"
        summon_anywhere = Get-PropertyValue -Object $PaletteJson -Name "summon_anywhere"
        command_total = Get-PropertyValue -Object $PaletteJson -Name "command_total"
        route = Get-PropertyValue -Object $PaletteJson -Name "route"
        local_surface = Get-PropertyValue -Object $PaletteJson -Name "local_surface"
        blockers = $PaletteBlockers
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
