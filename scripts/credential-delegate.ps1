<#
  File Sanity / Syntax Audit (drop-in replacement)
  - Recursively scans a root folder and validates common text formats:
    JSON, JSONL, YAML/YML (if parser available), PS1/PSM1 syntax, PY syntax (if python present)
  - Everything else: basic “text readability” check (binary-ish files fail via NULL-byte heuristic)
  - Writes a timestamped CSV report to: <Root>\data\logs\operations
  - Compatible with Windows PowerShell 5.1 + PowerShell 7+ (no ?? operator)

  Defaults:
    Root: D:\francis
    Output: D:\francis\data\logs\operations\file_sanity_<timestamp>.csv

  Run:
    powershell -ExecutionPolicy Bypass -File D:\francis\scripts\credential-delegate.ps1
#>

[CmdletBinding()]
param(
  [string]$Root = "D:\francis",

  # Where the report goes (default stays under $Root)
  [string]$OutDir = "",

  # Additional paths to skip (directories or prefixes)
  [string[]]$ExcludePaths = @(),

  # Safety: skip full-file parsing for huge JSON/YAML (ConvertFrom-Json needs full string)
  [int64]$MaxStructuredParseBytes = 50MB,

  # For "text readability" checks, only sample up to this many bytes
  [int64]$MaxTextSampleBytes = 1MB
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# --- Resolve + prep output paths ---
try {
  $RootResolved = (Resolve-Path -LiteralPath $Root).ProviderPath
} catch {
  throw "Root path not found or not accessible: $Root"
}

if ([string]::IsNullOrWhiteSpace($OutDir)) {
  $OutDir = Join-Path $RootResolved "data\logs\operations"
}

# Ensure output directory exists
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

$Now = Get-Date -Format "yyyyMMdd_HHmmss"
$Csv = Join-Path $OutDir ("file_sanity_{0}.csv" -f $Now)

# Build default excludes (always exclude the output dir so reports don't scan reports)
function Normalize-DirPath([string]$p) {
  if ([string]::IsNullOrWhiteSpace($p)) { return $null }
  try { $rp = (Resolve-Path -LiteralPath $p -ErrorAction Stop).ProviderPath } catch { $rp = $p }
  $rp = $rp.TrimEnd('\')
  return ($rp + '\')
}

$Exclude = New-Object System.Collections.Generic.List[string]
$Exclude.Add((Normalize-DirPath $OutDir)) | Out-Null
foreach ($p in $ExcludePaths) {
  $np = Normalize-DirPath $p
  if ($np) { $Exclude.Add($np) | Out-Null }
}

function Is-ExcludedPath([string]$path) {
  foreach ($ex in $Exclude) {
    if ($ex -and $path.StartsWith($ex, [System.StringComparison]::OrdinalIgnoreCase)) { return $true }
  }
  return $false
}

# --- Tool detection ---
$Py = $null
try { $Py = (Get-Command python -ErrorAction SilentlyContinue).Source } catch { $Py = $null }

$HasCfy = $false
try {
  if (Get-Command ConvertFrom-Yaml -ErrorAction SilentlyContinue) { $HasCfy = $true }
} catch { $HasCfy = $false }

$HasPyYaml = $false
if ($Py) {
  try {
    & $Py -c "import yaml" 2>$null
    $HasPyYaml = ($LASTEXITCODE -eq 0)
  } catch { $HasPyYaml = $false }
}

# --- Helpers ---
function Test-TextReadable {
  param(
    [Parameter(Mandatory=$true)][string]$Path,
    [int64]$SampleBytes = 1MB
  )
  # Returns $true/$false only (caller sets reason)
  try {
    $fi = Get-Item -LiteralPath $Path -Force -ErrorAction Stop
    if ($fi.Length -le 0) { return $true }

    $toRead = [Math]::Min([int64]$fi.Length, [int64]$SampleBytes)
    $buf = New-Object byte[] $toRead

    $fs = [System.IO.File]::Open($Path,
      [System.IO.FileMode]::Open,
      [System.IO.FileAccess]::Read,
      ([System.IO.FileShare]::ReadWrite -bor [System.IO.FileShare]::Delete)
    )

    try {
      $read = $fs.Read($buf, 0, [int]$toRead)

      # NULL byte heuristic (very common indicator of binary)
      for ($i=0; $i -lt $read; $i++) {
        if ($buf[$i] -eq 0) { return $false }
      }

      # Attempt decode (UTF-8 strict, then system default)
      try {
        $utf8Strict = New-Object System.Text.UTF8Encoding($false, $true)
        $null = $utf8Strict.GetString($buf, 0, $read) | Out-Null
        return $true
      } catch {
        try {
          $enc = [System.Text.Encoding]::Default
          $null = $enc.GetString($buf, 0, $read) | Out-Null
          return $true
        } catch {
          return $false
        }
      }
    } finally {
      $fs.Dispose()
    }
  } catch {
    return $false
  }
}

function Test-YamlFile {
  param([Parameter(Mandatory=$true)][string]$Path)

  # returns $null on success, otherwise returns an error string
  try {
    if ($HasCfy) {
      $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
      $null = $raw | ConvertFrom-Yaml -ErrorAction Stop
      return $null
    }
    elseif ($Py -and $HasPyYaml) {
      $out = & $Py -c "import sys,yaml; p=sys.argv[1]; s=open(p,'rb').read().decode('utf-8-sig'); yaml.safe_load(s)" $Path 2>&1
      if ($LASTEXITCODE -ne 0) { return (($out | Select-Object -First 1) -as [string]) }
      return $null
    }
    else {
      # No parser available -> minimal sanity (TABs are a common YAML gotcha)
      $raw = Get-Content -LiteralPath $Path -Raw -ErrorAction Stop
      if ($raw -match "`t") { return "YAML contains TAB characters (often invalid). Install PowerShell 7+ YAML support or PyYAML to fully parse." }
      return $null
    }
  } catch {
    return $_.Exception.Message
  }
}

function Get-FilesSafe {
  param([Parameter(Mandatory=$true)][string]$StartDir)

  # Custom recursion so we can skip reparse-point directories (symlink/junction loops)
  $stack = New-Object System.Collections.Generic.Stack[string]
  $stack.Push($StartDir)

  while ($stack.Count -gt 0) {
    $dir = $stack.Pop()

    if (Is-ExcludedPath ($dir.TrimEnd('\') + '\')) { continue }

    # Enumerate files in this directory
    try {
      Get-ChildItem -LiteralPath $dir -Force -File -ErrorAction SilentlyContinue | ForEach-Object {
        if (-not (Is-ExcludedPath (($_.FullName).TrimEnd('\') + '\'))) {
          $_
        }
      }
    } catch { }

    # Recurse into subdirectories (skip reparse points)
    try {
      Get-ChildItem -LiteralPath $dir -Force -Directory -ErrorAction SilentlyContinue | ForEach-Object {
        try {
          if ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) { return }
          $full = $_.FullName
          if (-not (Is-ExcludedPath ($full.TrimEnd('\') + '\'))) {
            $stack.Push($full)
          }
        } catch { }
      }
    } catch { }
  }
}

# --- Main scan ---
$sw = [System.Diagnostics.Stopwatch]::StartNew()

$Results = New-Object System.Collections.Generic.List[object]

Get-FilesSafe -StartDir $RootResolved | ForEach-Object {
  $f = $_
  $path = $f.FullName

  # Extension (PS5.1 safe)
  $ext = $f.Extension
  if ([string]::IsNullOrWhiteSpace($ext)) { $ext = "" }
  $ext = $ext.ToLowerInvariant()

  $size = [int64]$f.Length

  $status = "PASSED"
  $why    = ""

  if ($size -eq 0) {
    $status = "EMPTY"
    $why    = "0 bytes"
  }
  else {
    try {
      switch ($ext) {
        ".json" {
          if ($size -gt $MaxStructuredParseBytes) {
            $status = "SKIPPED"
            $why = "JSON too large to fully parse safely ($([Math]::Round($size/1MB,2)) MB > $([Math]::Round($MaxStructuredParseBytes/1MB,2)) MB)"
            break
          }
          $raw = Get-Content -LiteralPath $path -Raw -ErrorAction Stop
          $null = $raw | ConvertFrom-Json -ErrorAction Stop
        }

        ".jsonl" {
          $bad = 0; $lineNo = 0; $first = ""
          Get-Content -LiteralPath $path -ErrorAction Stop | ForEach-Object {
            $lineNo++
            $line = $_
            if ([string]::IsNullOrWhiteSpace($line)) { return }
            try { $null = $line | ConvertFrom-Json -ErrorAction Stop }
            catch {
              $bad++
              if (-not $first) { $first = "line $lineNo: $($_.Exception.Message)" }
            }
          }
          if ($bad -gt 0) { throw "$bad bad JSON line(s); $first" }
        }

        ".yaml" { 
          if ($size -gt $MaxStructuredParseBytes -and (-not $HasCfy) -and (-not ($Py -and $HasPyYaml))) {
            # fallback mode reads full raw anyway; avoid huge reads
            $status = "SKIPPED"
            $why = "YAML too large to minimally check without a real parser ($([Math]::Round($size/1MB,2)) MB). Install YAML parser (ConvertFrom-Yaml or PyYAML)."
            break
          }
          $e = Test-YamlFile $path; if ($e) { throw $e }
        }

        ".yml"  { 
          if ($size -gt $MaxStructuredParseBytes -and (-not $HasCfy) -and (-not ($Py -and $HasPyYaml))) {
            $status = "SKIPPED"
            $why = "YML too large to minimally check without a real parser ($([Math]::Round($size/1MB,2)) MB). Install YAML parser (ConvertFrom-Yaml or PyYAML)."
            break
          }
          $e = Test-YamlFile $path; if ($e) { throw $e }
        }

        ".ps1" {
          $t = $null; $e = $null
          [void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$t, [ref]$e)
          if ($e -and $e.Count -gt 0) { throw $e[0].Message }
        }

        ".psm1" {
          $t = $null; $e = $null
          [void][System.Management.Automation.Language.Parser]::ParseFile($path, [ref]$t, [ref]$e)
          if ($e -and $e.Count -gt 0) { throw $e[0].Message }
        }

        ".py" {
          if ($Py) {
            $out = & $Py -c "import sys,ast,tokenize; p=sys.argv[1]; ast.parse(tokenize.open(p).read(), filename=p)" $path 2>&1
            if ($LASTEXITCODE -ne 0) { throw (($out | Select-Object -First 1) -as [string]) }
          }
          else {
            if (-not (Test-TextReadable -Path $path -SampleBytes $MaxTextSampleBytes)) {
              throw "Unreadable text file (no python installed to syntax-check)"
            }
          }
        }

        default {
          if (-not (Test-TextReadable -Path $path -SampleBytes $MaxTextSampleBytes)) {
            throw "Unreadable or binary (NULL byte / decode failure / access denied)"
          }
        }
      }
    }
    catch {
      if ($status -ne "SKIPPED") {
        $status = "FAILED"
        $why = $_.Exception.Message
      }
    }
  }

  $Results.Add([pscustomobject]@{
    Path     = $path
    Ext      = (if ([string]::IsNullOrWhiteSpace($ext)) { "(none)" } else { $ext })
    SizeKB   = [math]::Round(($size/1KB), 2)
    Modified = $f.LastWriteTime
    Why      = $why
    Status   = $status
  }) | Out-Null
}

$sw.Stop()

# --- Output ---
$Results | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $Csv

$Results |
  Sort-Object Status, Path |
  Select-Object Path, Ext, SizeKB, Modified, Why, Status |
  Format-Table -AutoSize

"`nSaved report: $Csv"
"Elapsed: $([Math]::Round($sw.Elapsed.TotalSeconds,2))s"
"`nStatus counts:"
$Results | Group-Object Status | Sort-Object Count -Descending | Format-Table Count, Name -AutoSize
