param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CliArgs
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    throw "npx is required to run Playwright CLI."
}

& npx --yes --package @playwright/cli playwright-cli @CliArgs
exit $LASTEXITCODE
