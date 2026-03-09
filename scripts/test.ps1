param(
    [ValidateSet("fast", "full", "integration", "redteam", "evals")]
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

if ($null -ne $MaxFailures) {
    if ($MaxFailures -gt 0) {
        $args += "--maxfail=$MaxFailures"
    }
} elseif ($Lane -eq "fast") {
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
}

if ($Target.Count -gt 0) {
    $args += $Target
}

Write-Host ("Running: python " + ($args -join " "))
& python @args
exit $LASTEXITCODE
