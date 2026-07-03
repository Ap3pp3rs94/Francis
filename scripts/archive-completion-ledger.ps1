<#
D:\Francis\scripts\archive-completion-ledger.ps1

Purpose
  Archive old dated entries ("### YYYY-MM-DD ...") out of
  docs/operations/COMPLETION_LEDGER.md into per-month archive files under
  docs/operations/archive/, keeping the ledger small enough for bounded
  readers (developer bridge readback caps at ~256KB; the ledger is ~5.6MB).

  Keeps intact:
    - All "## " section headers and undated prose (sections 1-3, 5b-5i, 6)
    - All dated entries newer than the cutoff (default: keep last 14 days)

  Moves:
    - Dated "### YYYY-MM-DD..." entry blocks older than the cutoff, in
      original order, into docs/operations/archive/COMPLETION_LEDGER_<YYYY-MM>.md

Safety
  - Dry run by default. Nothing is written without -Apply.
  - Refuses to run if git reports the ledger dirty (another agent mid-write)
    unless -Force is given. Run this while Codex is idle.
  - Writes COMPLETION_LEDGER.md.bak (gitignored) before rewriting.
  - Never deletes content: every removed line lands in an archive file.

Examples
  # See what would be archived
  pwsh -File D:\Francis\scripts\archive-completion-ledger.ps1

  # Archive entries older than 14 days
  pwsh -File D:\Francis\scripts\archive-completion-ledger.ps1 -Apply

  # Keep the last 30 days instead
  pwsh -File D:\Francis\scripts\archive-completion-ledger.ps1 -KeepDays 30 -Apply
#>

[CmdletBinding()]
param(
  [string]$Root = 'D:\Francis',
  [int]$KeepDays = 14,
  [switch]$Apply,
  [switch]$Force
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$LedgerRel  = 'docs/operations/COMPLETION_LEDGER.md'
$LedgerPath = Join-Path $Root 'docs\operations\COMPLETION_LEDGER.md'
$ArchiveDir = Join-Path $Root 'docs\operations\archive'
$Cutoff     = (Get-Date).Date.AddDays(-$KeepDays)

if (-not (Test-Path $LedgerPath)) { throw "Ledger not found: $LedgerPath" }

# --- Guard: do not rewrite while another agent has the ledger dirty ---------
$dirty = $null
try { $dirty = (& git -C $Root status --porcelain -- $LedgerRel 2>$null) } catch { $dirty = $null }
if ($dirty -and -not $Force) {
  throw "Ledger has uncommitted changes (another agent may be mid-write). Re-run when idle, or use -Force."
}

$utf8   = New-Object System.Text.UTF8Encoding($false)
$lines  = [System.IO.File]::ReadAllLines($LedgerPath, [System.Text.Encoding]::UTF8)
$entryRx = '^###\s+(\d{4}-\d{2}-\d{2})'

$keep     = New-Object System.Collections.Generic.List[string]
$archives = @{}   # 'YYYY-MM' -> List[string]
$stats    = @{}   # 'YYYY-MM' -> entry count

$i = 0
$total = $lines.Count
$archivedEntries = 0
$archivedLines   = 0

while ($i -lt $total) {
  $line = $lines[$i]
  $m = [regex]::Match($line, $entryRx)
  if ($m.Success) {
    $date = [datetime]::ParseExact($m.Groups[1].Value, 'yyyy-MM-dd', $null)
    # Collect the whole entry block: until next '### ' or '## ' header
    $j = $i + 1
    while ($j -lt $total -and $lines[$j] -notmatch '^###?\s' ) { $j++ }
    if ($date -lt $Cutoff) {
      $key = $date.ToString('yyyy-MM')
      if (-not $archives.ContainsKey($key)) {
        $archives[$key] = New-Object System.Collections.Generic.List[string]
        $stats[$key] = 0
      }
      for ($k = $i; $k -lt $j; $k++) { $archives[$key].Add($lines[$k]) }
      $stats[$key]++
      $archivedEntries++
      $archivedLines += ($j - $i)
    } else {
      for ($k = $i; $k -lt $j; $k++) { $keep.Add($lines[$k]) }
    }
    $i = $j
  } else {
    $keep.Add($line)
    $i++
  }
}

$keptBytes = ($keep -join "`n").Length

Write-Host "Ledger lines           : $total"
Write-Host "Cutoff (keep >= )      : $($Cutoff.ToString('yyyy-MM-dd'))  (KeepDays=$KeepDays)"
Write-Host "Entries to archive     : $archivedEntries  ($archivedLines lines)"
Write-Host "Ledger lines after     : $($keep.Count)  (~$([math]::Round($keptBytes/1KB)) KB)"
foreach ($key in ($stats.Keys | Sort-Object)) {
  Write-Host ("  {0}: {1} entries -> archive/COMPLETION_LEDGER_{0}.md" -f $key, $stats[$key])
}

if (-not $Apply) {
  Write-Host "`nDry run only. Re-run with -Apply to write." -ForegroundColor Yellow
  return
}

if ($archivedEntries -eq 0) { Write-Host 'Nothing to archive.'; return }

# --- Write --------------------------------------------------------------------
New-Item -ItemType Directory -Force -Path $ArchiveDir | Out-Null
Copy-Item $LedgerPath "$LedgerPath.bak" -Force

foreach ($key in ($archives.Keys | Sort-Object)) {
  $dest = Join-Path $ArchiveDir "COMPLETION_LEDGER_$key.md"
  $block = $archives[$key]
  if (-not (Test-Path $dest)) {
    $header = @(
      "# FRANCIS - COMPLETION_LEDGER archive ($key)",
      '',
      "Entries moved verbatim from docs/operations/COMPLETION_LEDGER.md.",
      "Archived on $(Get-Date -Format 'yyyy-MM-dd') by scripts/archive-completion-ledger.ps1.",
      ''
    )
    [System.IO.File]::WriteAllLines($dest, ($header + $block), $utf8)
  } else {
    [System.IO.File]::AppendAllLines($dest, $block, $utf8)
  }
  Write-Host "Wrote $dest"
}

# Pointer note so readers know where old evidence lives (inserted once).
$note = '> Older dated entries are archived under docs/operations/archive/ (see scripts/archive-completion-ledger.ps1).'
if (-not ($keep -contains $note)) {
  $out = New-Object System.Collections.Generic.List[string]
  $inserted = $false
  foreach ($l in $keep) {
    $out.Add($l)
    if (-not $inserted -and $l -match '^## 4\.') { $out.Add(''); $out.Add($note); $inserted = $true }
  }
  if (-not $inserted) { $out.Insert(0, $note); $out.Insert(1, '') }
  $keep = $out
}

[System.IO.File]::WriteAllLines($LedgerPath, $keep, $utf8)
Write-Host "Rewrote $LedgerPath ($($keep.Count) lines). Backup at $LedgerPath.bak"
