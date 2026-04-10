param(
    [switch]$Apply,
    [switch]$Yes
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..")

Push-Location $repoRoot
try {
    $python = "python"
    $args = @("tools/restore_tree.py")
    if ($Apply) {
        $args += "--apply"
    }
    if ($Yes) {
        $args += "--yes"
    }
    & $python @args
} finally {
    Pop-Location
}
