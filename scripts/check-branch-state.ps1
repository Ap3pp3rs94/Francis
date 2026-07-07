param(
    [string]$Root = "",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

if (-not $Root) {
    $Root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
}

function Invoke-Git {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Args)
    $output = & git @Args 2>&1
    if ($LASTEXITCODE -ne 0) {
        $message = ($output | Out-String).Trim()
        throw "git $($Args -join ' ') failed`n$message"
    }
    return ($output | Out-String).Trim()
}

function Get-RevListCounts {
    param([string]$RevisionRange)

    $counts = Invoke-Git rev-list --left-right --count $RevisionRange
    $parts = @($counts -split "\s+" | Where-Object { $_ -ne "" })
    if ($parts.Count -lt 2) {
        throw "Could not parse git rev-list counts for '$RevisionRange': '$counts'."
    }
    return [ordered]@{
        Ahead = [int]$parts[0]
        Behind = [int]$parts[1]
    }
}

function New-BranchStatePayload {
    param(
        [bool]$Ok,
        [string]$Status,
        [string]$Reason,
        [string]$Branch,
        [string]$Upstream,
        [string]$Head,
        [string]$OriginMain,
        [string]$MergeBase,
        [object]$OriginMainCounts,
        [object]$UpstreamCounts
    )

    return [ordered]@{
        ok = $Ok
        status = $Status
        reason = $Reason
        read_only_contract = $true
        writes_repo = $false
        writes_data = $false
        grants_mutation_authority = $false
        branch = $Branch
        upstream = $Upstream
        head = $Head
        origin_main = $OriginMain
        merge_base = $MergeBase
        head_origin_main = [ordered]@{
            ahead = [int]$OriginMainCounts.Ahead
            behind = [int]$OriginMainCounts.Behind
        }
        head_upstream = [ordered]@{
            ahead = [int]$UpstreamCounts.Ahead
            behind = [int]$UpstreamCounts.Behind
        }
    }
}

function Write-BranchStateJson {
    param([object]$Payload)

    $Payload | ConvertTo-Json -Depth 6
}

function Format-BranchStateBlocker {
    param([object]$Payload)

    return @"
Branch '$($Payload.branch)' is behind or diverged from 'origin/main'. Rebase or merge origin/main before continuing.
  branch: $($Payload.branch)
  upstream: $($Payload.upstream)
  HEAD: $($Payload.head)
  origin/main: $($Payload.origin_main)
  merge-base: $($Payload.merge_base)
  HEAD...origin/main: ahead $($Payload.head_origin_main.ahead), behind $($Payload.head_origin_main.behind)
  HEAD...upstream: ahead $($Payload.head_upstream.ahead), behind $($Payload.head_upstream.behind)
"@.Trim()
}

Push-Location $Root
try {
    $insideWorkTree = Invoke-Git rev-parse --is-inside-work-tree
    if ($insideWorkTree -ne "true") {
        throw "Not inside a git work tree."
    }

    $branch = Invoke-Git branch --show-current
    if (-not $branch) {
        throw "Detached HEAD is not allowed for normal repo work."
    }

    $allowedPrefixes = @("codex/", "backup/", "release/", "hotfix/")
    $allowedBranch = $branch -eq "main"
    if (-not $allowedBranch) {
        foreach ($prefix in $allowedPrefixes) {
            if ($branch.StartsWith($prefix, [System.StringComparison]::Ordinal)) {
                $allowedBranch = $true
                break
            }
        }
    }
    if (-not $allowedBranch) {
        throw "Branch '$branch' does not match the repo workflow. Use 'main' or an approved prefix: $($allowedPrefixes -join ', ')."
    }

    $upstream = ""
    try {
        $upstream = Invoke-Git rev-parse --abbrev-ref --symbolic-full-name "@{u}"
    }
    catch {
        throw "Branch '$branch' does not have an upstream tracking branch."
    }

    if ($branch -eq "main" -and $upstream -ne "origin/main") {
        throw "Local 'main' must track 'origin/main'. Current upstream: '$upstream'."
    }

    $originMain = ""
    try {
        $originMain = Invoke-Git rev-parse origin/main
    }
    catch {
        throw "Missing 'origin/main'. Fetch from origin before running repo checks."
    }

    if ($branch -ne "main") {
        $mergeBase = Invoke-Git merge-base HEAD origin/main
        if ($mergeBase -ne $originMain) {
            $head = Invoke-Git rev-parse HEAD
            $originMainCounts = Get-RevListCounts "HEAD...origin/main"
            $upstreamCounts = Get-RevListCounts "HEAD...@{u}"
            $payload = New-BranchStatePayload `
                -Ok $false `
                -Status "blocked" `
                -Reason "branch_behind_or_diverged_from_origin_main" `
                -Branch $branch `
                -Upstream $upstream `
                -Head $head `
                -OriginMain $originMain `
                -MergeBase $mergeBase `
                -OriginMainCounts $originMainCounts `
                -UpstreamCounts $upstreamCounts
            if ($Json) {
                Write-BranchStateJson $payload
                exit 1
            }
            throw (Format-BranchStateBlocker $payload)
        }
    }

    if ($Json) {
        $head = Invoke-Git rev-parse HEAD
        $mergeBase = Invoke-Git merge-base HEAD origin/main
        $originMainCounts = Get-RevListCounts "HEAD...origin/main"
        $upstreamCounts = Get-RevListCounts "HEAD...@{u}"
        $payload = New-BranchStatePayload `
            -Ok $true `
            -Status "ok" `
            -Reason "branch_state_ok" `
            -Branch $branch `
            -Upstream $upstream `
            -Head $head `
            -OriginMain $originMain `
            -MergeBase $mergeBase `
            -OriginMainCounts $originMainCounts `
            -UpstreamCounts $upstreamCounts
        Write-BranchStateJson $payload
        exit 0
    }

    Write-Host "Branch state OK"
    Write-Host "  branch:   $branch"
    Write-Host "  upstream: $upstream"
    Write-Host "  origin/main: $originMain"
}
finally {
    Pop-Location
}
