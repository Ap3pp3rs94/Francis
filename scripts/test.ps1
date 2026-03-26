param(
    [ValidateSet("fast", "full", "full-first-failure", "full-stepwise", "integration", "redteam", "evals")]
    [string]$Lane = "fast",
    [string[]]$Target = @(),
    [switch]$NoQuiet,
    [Nullable[int]]$MaxFailures = $null
)

$ErrorActionPreference = "Stop"

$args = @("-m", "pytest")

if (-not $NoQuiet) {
    $args += "-q"
}

if ($Lane -eq "full-stepwise") {
    $args += "--stepwise"
}

if ($null -ne $MaxFailures) {
    if ($MaxFailures -gt 0) {
        $args += "--maxfail=$MaxFailures"
    }
} elseif ($Lane -in @("fast", "full-first-failure", "full-stepwise")) {
    $args += "--maxfail=1"
}

switch ($Lane) {
    "fast" {
        $args += @("-m", "not slow and not redteam and not evals")
    }
    "integration" {
        $args += @("-m", "integration and not slow")
    }
    "redteam" {
        $args += @("-m", "redteam")
    }
    "evals" {
        $args += @("-m", "evals")
    }
    "full" {
    }
    "full-first-failure" {
    }
    "full-stepwise" {
    }
}

if ($Target.Count -gt 0) {
    $args += $Target
}

Write-Host ("Running: python " + ($args -join " "))
& python @args
exit $LASTEXITCODE
