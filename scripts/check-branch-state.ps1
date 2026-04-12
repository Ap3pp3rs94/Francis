param(
    [string]$Root = ""
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
            throw "Branch '$branch' is behind or diverged from 'origin/main'. Rebase or merge origin/main before continuing."
        }
    }

    Write-Host "Branch state OK"
    Write-Host "  branch:   $branch"
    Write-Host "  upstream: $upstream"
    Write-Host "  origin/main: $originMain"
}
finally {
    Pop-Location
}
