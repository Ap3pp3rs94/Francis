<#
==============================================================================
 FRANClS — backup.ps1
 Policy-aware snapshot backups (repo + optional data) with manifests, retention,
 optional compression/encryption, and verification.

 Location:
   C:\Francis\scripts\backup.ps1

 Design stance:
   - Default-safe: excludes secrets unless explicitly included.
   - Deterministic artifacts: manifest + hashes (optional) for integrity.
   - Restore-friendly: produces a snapshot folder; optionally archives it.
   - Fail-closed: if risky flags are used (IncludeSecrets / remote UNC / Encrypt),
     require either -Force or an ApprovalId reference (project governance style).

 Notes:
   - Optimized for Windows + PowerShell 7+ (robocopy preferred).
   - Works on PowerShell 5.1+ with reduced functionality (no $IsWindows vars).
   - Respects -WhatIf via an internal Dry-Run toggle (external tools can't).
==============================================================================
#>

#requires -Version 7.0

[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    # Repo root (defaults to parent of scripts/).
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path,

    # Destination root where backups are written.
    # Example: D:\Backups  or  \\NAS01\backups
    [Parameter(Mandatory = $true)]
    [ValidateNotNullOrEmpty()]
    [string]$DestinationRoot,

    # Backup mode:
    #   full        = fresh snapshot copy
    #   incremental = hardlink-clone previous snapshot then update changed files
    [Parameter()]
    [ValidateSet('full', 'incremental')]
    [string]$Mode = 'full',

    # Include repo's data/ directory
    [Parameter()]
    [bool]$IncludeData = $true,

    # Include data/logs in the data/ backup (can be large)
    [Parameter()]
    [bool]$IncludeLogs = $true,

    # Include caches (data/cache, node_modules, etc.) — OFF by default
    [Parameter()]
    [bool]$IncludeCaches = $false,

    # Include secrets (config/secrets.yaml, data/credentials/vault.db, etc.) — OFF by default
    [Parameter()]
    [bool]$IncludeSecrets = $false,

    # Manifest + hashing
    [Parameter()]
    [bool]$ComputeHashes = $true,

    [Parameter()]
    [ValidateSet('SHA256', 'SHA1', 'MD5')]
    [string]$HashAlgorithm = 'SHA256',

    # Verify manifest after write (checks file count + hashes when enabled)
    [Parameter()]
    [bool]$Verify = $true,

    # Archiving:
    #   none = keep snapshot folder
    #   zip  = Compress-Archive snapshot into .zip
    #   7z   = Use 7-Zip if available (better compression + supports password)
    [Parameter()]
    [ValidateSet('none', 'zip', '7z')]
    [string]$Archive = 'none',

    # Encrypt archive (7z preferred; otherwise AES wraps the zip)
    [Parameter()]
    [bool]$Encrypt = $false,

    # Env var containing encryption password (never pass plaintext on CLI)
    [Parameter()]
    [ValidateNotNullOrEmpty()]
    [string]$EncryptPasswordEnvVar = 'FRANCIS_BACKUP_PASSWORD',

    # If archiving, delete the snapshot folder after creating/verifying archive
    [Parameter()]
    [bool]$DeleteSnapshotAfterArchive = $true,

    # Keep last N backups (snapshots + archives). 0 disables pruning.
    [Parameter()]
    [ValidateRange(0, 3650)]
    [int]$Retention = 30,

    # Optional governance approval reference.
    # If set, we will look for a matching approval artifact under data/approvals.
    [Parameter()]
    [string]$ApprovalId = '',

    # Bypass high-risk confirmations (IncludeSecrets, Encrypt, UNC destinations).
    [Parameter()]
    [switch]$Force,

    # Extra explicit dry-run switch (also enabled by -WhatIf).
    [Parameter()]
    [switch]$DryRun
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

function Get-NowStamp {
    return (Get-Date).ToString('yyyyMMdd_HHmmss')
}

function Get-NowUtcIso {
    return (Get-Date).ToUniversalTime().ToString('o')
}

function Write-Info([string]$Message) {
    Write-Host "[INFO ] $Message"
}

function Write-Warn([string]$Message) {
    Write-Warning $Message
}

function Write-Err([string]$Message) {
    Write-Error $Message
}

function Ensure-Directory([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path)) {
        New-Item -ItemType Directory -Path $Path -Force | Out-Null
    }
}

function Is-UncPath([string]$Path) {
    return ($Path -like '\\*')
}

function Get-DriveRoot([string]$Path) {
    # Best-effort drive root for local paths
    try {
        $resolved = Resolve-Path -LiteralPath $Path -ErrorAction Stop
        $p = $resolved.Path
        if ($p -match '^[A-Za-z]:\\') {
            return ($p.Substring(0, 3)) # e.g. C:\
        }
    } catch {
        # If path doesn't exist yet, infer from string
        if ($Path -match '^[A-Za-z]:\\') {
            return ($Path.Substring(0, 3))
        }
    }
    return $null
}

function Test-IsSameVolume([string]$PathA, [string]$PathB) {
    $a = Get-DriveRoot $PathA
    $b = Get-DriveRoot $PathB
    if (-not $a -or -not $b) { return $false }
    return ($a.ToLowerInvariant() -eq $b.ToLowerInvariant())
}

function Get-7ZipPath {
    $candidates = @()

    # PATH
    $cmd = Get-Command '7z' -ErrorAction SilentlyContinue
    if ($cmd) { $candidates += $cmd.Source }

    # Common install paths
    $candidates += @(
        "$env:ProgramFiles\7-Zip\7z.exe",
        "${env:ProgramFiles(x86)}\7-Zip\7z.exe"
    ) | Where-Object { $_ -and ($_ -ne '\7-Zip\7z.exe') }

    foreach ($c in $candidates) {
        if ($c -and (Test-Path -LiteralPath $c)) {
            return $c
        }
    }
    return $null
}

function Get-GitHead([string]$Root) {
    try {
        $git = Get-Command 'git' -ErrorAction SilentlyContinue
        if (-not $git) { return $null }
        $head = & $git.Source -C $Root rev-parse HEAD 2>$null
        if ($LASTEXITCODE -eq 0 -and $head) { return ($head.Trim()) }
    } catch { }
    return $null
}

function Find-ApprovalArtifact([string]$RepoRoot, [string]$ApprovalId) {
    if ([string]::IsNullOrWhiteSpace($ApprovalId)) { return $null }

    $approvalsRoot = Join-Path $RepoRoot 'data\approvals'
    if (-not (Test-Path -LiteralPath $approvalsRoot)) { return $null }

    $paths = @(
        (Join-Path $approvalsRoot 'approved'),
        (Join-Path $approvalsRoot 'emergency')
    ) | Where-Object { Test-Path -LiteralPath $_ }

    foreach ($p in $paths) {
        $match = Get-ChildItem -LiteralPath $p -Recurse -File -ErrorAction SilentlyContinue |
            Where-Object { $_.Name -like "*$ApprovalId*" -or $_.FullName -like "*$ApprovalId*" } |
            Select-Object -First 1
        if ($match) { return $match.FullName }
    }

    return $null
}

function Assert-RiskyOperationApproved {
    param(
        [string]$Reason,
        [string]$RepoRoot,
        [string]$ApprovalId,
        [switch]$Force
    )

    if ($Force) {
        Write-Warn "High-risk flag accepted via -Force. Reason: $Reason"
        return
    }

    $artifact = Find-ApprovalArtifact -RepoRoot $RepoRoot -ApprovalId $ApprovalId
    if ($artifact) {
        Write-Info "Approval artifact found for risky operation: $artifact"
        return
    }

    throw "High-risk operation blocked: $Reason. Provide -Force or -ApprovalId referencing an approval artifact under data/approvals."
}

function Get-RelativePathSafe([string]$Base, [string]$Full) {
    $baseNorm = [IO.Path]::GetFullPath($Base).TrimEnd('\','/')
    $fullNorm = [IO.Path]::GetFullPath($Full)

    if ($fullNorm.StartsWith($baseNorm, [StringComparison]::OrdinalIgnoreCase)) {
        $rel = $fullNorm.Substring($baseNorm.Length).TrimStart('\','/')
        return $rel
    }
    return $fullNorm
}

# ---------------------------------------------------------------------------
# Copy engines
# ---------------------------------------------------------------------------

function Invoke-RoboCopy {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter()][string[]]$ExcludeDirs = @(),
        [Parameter()][string[]]$ExcludeFiles = @(),
        [Parameter()][switch]$Mirror,
        [Parameter()][switch]$IncludeEmptyDirs
    )

    Ensure-Directory -Path $Destination

    $args = @()
    $args += @("`"$Source`"", "`"$Destination`"")

    if ($Mirror) { $args += '/MIR' } else { $args += '/E' }

    if ($IncludeEmptyDirs) {
        # /E already includes empty dirs, but keep explicit intent for readability.
    }

    # Copy semantics: Data, Attributes, Timestamps; include dirs timestamps.
    $args += @('/COPY:DAT', '/DCOPY:DAT')

    # Reliability / noise
    $args += @('/R:2', '/W:2', '/NP', '/NFL', '/NDL')

    # Excludes
    if ($ExcludeDirs.Count -gt 0) {
        $args += '/XD'
        foreach ($d in $ExcludeDirs) { $args += "`"$d`"" }
    }

    if ($ExcludeFiles.Count -gt 0) {
        $args += '/XF'
        foreach ($f in $ExcludeFiles) { $args += "`"$f`"" }
    }

    $cmd = 'robocopy'
    $dry = ($DryRun -or $WhatIfPreference)

    if ($dry) {
        Write-Info "[DRY-RUN] $cmd $($args -join ' ')"
        return
    }

    Write-Info "Robocopy: $Source -> $Destination"
    & $cmd @args | Out-Null

    # Robocopy uses bitmask exit codes; 0-7 are typically success states.
    if ($LASTEXITCODE -gt 7) {
        throw "Robocopy failed with exit code $LASTEXITCODE for: $Source -> $Destination"
    }
}

function Copy-TreeFallback {
    param(
        [Parameter(Mandatory=$true)][string]$Source,
        [Parameter(Mandatory=$true)][string]$Destination,
        [Parameter()][string[]]$ExcludeDirNames = @(),
        [Parameter()][string[]]$ExcludeFileNames = @()
    )

    Ensure-Directory -Path $Destination

    $dry = ($DryRun -or $WhatIfPreference)
    if ($dry) {
        Write-Info "[DRY-RUN] Copy fallback: $Source -> $Destination"
        return
    }

    # Very conservative fallback copy. Slower than robocopy.
    $items = Get-ChildItem -LiteralPath $Source -Force -Recurse -ErrorAction Stop

    foreach ($item in $items) {
        $rel = Get-RelativePathSafe -Base $Source -Full $item.FullName

        if ($item.PSIsContainer) {
            if ($ExcludeDirNames -contains $item.Name) { continue }
            Ensure-Directory -Path (Join-Path $Destination $rel)
            continue
        }

        if ($ExcludeFileNames -contains $item.Name) { continue }

        $destPath = Join-Path $Destination $rel
        Ensure-Directory -Path (Split-Path -Path $destPath -Parent)

        Copy-Item -LiteralPath $item.FullName -Destination $destPath -Force
    }
}

function New-HardlinkClone {
    <#
        Creates a new snapshot by hardlinking files from a previous snapshot.
        Requirements:
          - Windows + NTFS
          - Same destination volume
        Directories are recreated; files are hardlinked.
    #>
    param(
        [Parameter(Mandatory=$true)][string]$PrevSnapshot,
        [Parameter(Mandatory=$true)][string]$NewSnapshot
    )

    $dry = ($DryRun -or $WhatIfPreference)

    Ensure-Directory -Path $NewSnapshot

    # Create directories first (including empties)
    $dirs = Get-ChildItem -LiteralPath $PrevSnapshot -Recurse -Force -Directory -ErrorAction Stop
    foreach ($d in $dirs) {
        $rel = Get-RelativePathSafe -Base $PrevSnapshot -Full $d.FullName
        $targetDir = Join-Path $NewSnapshot $rel
        if ($dry) {
            Write-Info "[DRY-RUN] mkdir $targetDir"
        } else {
            Ensure-Directory -Path $targetDir
        }
    }

    # Hardlink files
    $files = Get-ChildItem -LiteralPath $PrevSnapshot -Recurse -Force -File -ErrorAction Stop
    foreach ($f in $files) {
        $rel = Get-RelativePathSafe -Base $PrevSnapshot -Full $f.FullName
        $target = Join-Path $NewSnapshot $rel
        $targetParent = Split-Path -Path $target -Parent

        if ($dry) {
            Write-Info "[DRY-RUN] hardlink $target -> $($f.FullName)"
            continue
        }

        Ensure-Directory -Path $targetParent

        # If already exists, skip (shouldn't happen), but be safe.
        if (-not (Test-Path -LiteralPath $target)) {
            New-Item -ItemType HardLink -Path $target -Target $f.FullName -Force | Out-Null
        }
    }
}

# ---------------------------------------------------------------------------
# Manifest + verification
# ---------------------------------------------------------------------------

function Get-FileInventory {
    param(
        [Parameter(Mandatory=$true)][string]$RootPath,
        [Parameter(Mandatory=$true)][bool]$ComputeHashes,
        [Parameter(Mandatory=$true)][string]$HashAlgorithm
    )

    $files = Get-ChildItem -LiteralPath $RootPath -Recurse -Force -File -ErrorAction Stop

    $inventory = New-Object System.Collections.Generic.List[object]
    foreach ($f in $files) {
        $rel = Get-RelativePathSafe -Base $RootPath -Full $f.FullName
        $obj = [ordered]@{
            path = $rel
            bytes = [int64]$f.Length
            last_write_utc = $f.LastWriteTimeUtc.ToString('o')
        }

        if ($ComputeHashes) {
            try {
                $h = Get-FileHash -LiteralPath $f.FullName -Algorithm $HashAlgorithm -ErrorAction Stop
                $obj.hash = $h.Hash.ToLowerInvariant()
                $obj.hash_alg = $HashAlgorithm
            } catch {
                $obj.hash = $null
                $obj.hash_alg = $HashAlgorithm
                $obj.hash_error = $_.Exception.Message
            }
        }

        $inventory.Add([pscustomobject]$obj)
    }

    return $inventory
}

function Write-Manifest {
    param(
        [Parameter(Mandatory=$true)][string]$SnapshotRoot,
        [Parameter(Mandatory=$true)][hashtable]$Header,
        [Parameter(Mandatory=$true)][System.Collections.Generic.List[object]]$Inventory
    )

    $manifest = [ordered]@{
        header = $Header
        file_count = $Inventory.Count
        total_bytes = ($Inventory | Measure-Object -Property bytes -Sum).Sum
        files = $Inventory
    }

    $manifestPath = Join-Path $SnapshotRoot 'manifest.json'
    $manifest | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath $manifestPath -Encoding UTF8

    # Also emit a JSONL for streaming/grep-friendly use
    $jsonlPath = Join-Path $SnapshotRoot 'manifest.files.jsonl'
    $dry = ($DryRun -or $WhatIfPreference)
    if ($dry) {
        Write-Info "[DRY-RUN] Write manifest: $manifestPath + $jsonlPath"
        return
    }

    $Inventory | ForEach-Object {
        ($_ | ConvertTo-Json -Compress -Depth 6)
    } | Set-Content -LiteralPath $jsonlPath -Encoding UTF8

    Write-Info "Manifest written: $manifestPath"
}

function Verify-SnapshotAgainstManifest {
    param(
        [Parameter(Mandatory=$true)][string]$SnapshotRoot
    )

    $manifestPath = Join-Path $SnapshotRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath)) {
        throw "Cannot verify: manifest.json not found at $manifestPath"
    }

    $manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
    $expectedCount = [int]$manifest.file_count

    $currentFiles = Get-ChildItem -LiteralPath $SnapshotRoot -Recurse -Force -File -ErrorAction Stop |
        Where-Object { $_.Name -notin @('manifest.json', 'manifest.files.jsonl') }

    if ($currentFiles.Count -lt $expectedCount) {
        throw "Verify failed: snapshot has fewer files than manifest. Snapshot=$($currentFiles.Count), Manifest=$expectedCount"
    }

    $hashing = $false
    if ($manifest.header.compute_hashes -eq $true) { $hashing = $true }

    if ($hashing) {
        Write-Info "Verifying hashes (this can take time)..."
        $root = [IO.Path]::GetFullPath($SnapshotRoot)

        $map = @{}
        foreach ($f in $manifest.files) {
            if ($null -ne $f.hash -and $f.hash -ne '') {
                $map[$f.path] = $f.hash
            }
        }

        foreach ($entry in $map.GetEnumerator()) {
            $rel = $entry.Key
            $expected = $entry.Value

            $abs = Join-Path $root $rel
            if (-not (Test-Path -LiteralPath $abs)) {
                throw "Verify failed: missing file listed in manifest: $rel"
            }

            $actual = (Get-FileHash -LiteralPath $abs -Algorithm $manifest.header.hash_algorithm).Hash.ToLowerInvariant()
            if ($actual -ne $expected) {
                throw "Verify failed: hash mismatch: $rel expected=$expected actual=$actual"
            }
        }
    }

    Write-Info "Verification OK."
}

# ---------------------------------------------------------------------------
# Archive + encryption
# ---------------------------------------------------------------------------

function Get-EncryptPassword {
    param([string]$EnvVarName)

    $pw = [Environment]::GetEnvironmentVariable($EnvVarName)
    if ([string]::IsNullOrWhiteSpace($pw)) {
        throw "Encryption requested but env var '$EnvVarName' is not set."
    }
    return $pw
}

function New-ZipArchive {
    param(
        [Parameter(Mandatory=$true)][string]$SnapshotRoot,
        [Parameter(Mandatory=$true)][string]$ArchivePath
    )

    $dry = ($DryRun -or $WhatIfPreference)
    if ($dry) {
        Write-Info "[DRY-RUN] Compress-Archive $SnapshotRoot -> $ArchivePath"
        return
    }

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force
    }

    # Compress-Archive includes folder content; we want deterministic top-level.
    Compress-Archive -Path (Join-Path $SnapshotRoot '*') -DestinationPath $ArchivePath -CompressionLevel Optimal
}

function New-7zArchive {
    param(
        [Parameter(Mandatory=$true)][string]$SevenZipPath,
        [Parameter(Mandatory=$true)][string]$SnapshotRoot,
        [Parameter(Mandatory=$true)][string]$ArchivePath,
        [Parameter()][string]$Password = $null
    )

    $dry = ($DryRun -or $WhatIfPreference)
    $args = @('a', '-t7z', '-mx=9', '-mmt=on')

    if ($Password) {
        $args += @("-p$Password", '-mhe=on') # encrypt headers too
    }

    $args += @("`"$ArchivePath`"", "`"$SnapshotRoot\*`"")

    if ($dry) {
        Write-Info "[DRY-RUN] `"$SevenZipPath`" $($args -join ' ')"
        return
    }

    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force
    }

    & $SevenZipPath @args | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "7-Zip failed with exit code $LASTEXITCODE"
    }
}

function Protect-FileAesGcm {
    <#
      Wraps a file with AES-GCM encryption (for when 7z isn't available).
      Output format:
        - 4 bytes "FGCM"
        - 4 bytes version (uint32 LE)
        - 12 bytes nonce
        - 16 bytes tag
        - ciphertext bytes
      Key derivation:
        - PBKDF2 (Rfc2898DeriveBytes) SHA256, 200k iterations, random 16-byte salt
      Header extends to include salt too:
        "FGCM" + ver + salt(16) + nonce(12) + tag(16) + ciphertext
    #>
    param(
        [Parameter(Mandatory=$true)][string]$InputPath,
        [Parameter(Mandatory=$true)][string]$OutputPath,
        [Parameter(Mandatory=$true)][string]$Password
    )

    $dry = ($DryRun -or $WhatIfPreference)
    if ($dry) {
        Write-Info "[DRY-RUN] AES-GCM encrypt $InputPath -> $OutputPath"
        return
    }

    Add-Type -AssemblyName System.Security.Cryptography

    $salt = New-Object byte[] 16
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($salt)

    $kdf = New-Object System.Security.Cryptography.Rfc2898DeriveBytes($Password, $salt, 200000, [System.Security.Cryptography.HashAlgorithmName]::SHA256)
    $key = $kdf.GetBytes(32) # AES-256

    $nonce = New-Object byte[] 12
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($nonce)

    $plain = [IO.File]::ReadAllBytes($InputPath)
    $cipher = New-Object byte[] $plain.Length
    $tag = New-Object byte[] 16

    $aes = New-Object System.Security.Cryptography.AesGcm($key)
    $aes.Encrypt($nonce, $plain, $cipher, $tag, $null)

    $magic = [Text.Encoding]::ASCII.GetBytes('FGCM')
    $ver = [BitConverter]::GetBytes([uint32]1)

    $out = New-Object System.Collections.Generic.List[byte]
    $out.AddRange($magic)
    $out.AddRange($ver)
    $out.AddRange($salt)
    $out.AddRange($nonce)
    $out.AddRange($tag)
    $out.AddRange($cipher)

    [IO.File]::WriteAllBytes($OutputPath, $out.ToArray())
}

# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------

function Prune-Backups {
    param(
        [Parameter(Mandatory=$true)][string]$BackupRoot,
        [Parameter(Mandatory=$true)][int]$Retention
    )

    if ($Retention -le 0) {
        Write-Info "Retention disabled (Retention=$Retention)."
        return
    }

    if (-not (Test-Path -LiteralPath $BackupRoot)) { return }

    $items = Get-ChildItem -LiteralPath $BackupRoot -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.PSIsContainer -or $_.Extension -in @('.zip', '.7z', '.aes') } |
        Sort-Object -Property LastWriteTimeUtc -Descending

    if ($items.Count -le $Retention) {
        Write-Info "Retention OK: $($items.Count) items <= $Retention"
        return
    }

    $toDelete = $items | Select-Object -Skip $Retention
    foreach ($item in $toDelete) {
        $dry = ($DryRun -or $WhatIfPreference)
        if ($dry) {
            Write-Info "[DRY-RUN] Prune: $($item.FullName)"
            continue
        }

        Write-Warn "Pruning old backup: $($item.FullName)"
        Remove-Item -LiteralPath $item.FullName -Recurse -Force -ErrorAction Stop
    }
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

# Normalize and guard
$RepoRoot = (Resolve-Path -LiteralPath $RepoRoot).Path

# Ensure DestinationRoot exists (create if needed)
if (-not (Test-Path -LiteralPath $DestinationRoot)) {
    if ($DryRun -or $WhatIfPreference) {
        Write-Info "[DRY-RUN] Would create destination root: $DestinationRoot"
    } else {
        Ensure-Directory -Path $DestinationRoot
    }
}

# Prevent destination inside repo root (recursive backup)
try {
    $destResolved = Resolve-Path -LiteralPath $DestinationRoot -ErrorAction Stop
    $destPath = $destResolved.Path
    $repoPath = [IO.Path]::GetFullPath($RepoRoot)
    $destFull = [IO.Path]::GetFullPath($destPath)
    if ($destFull.StartsWith($repoPath, [StringComparison]::OrdinalIgnoreCase)) {
        throw "DestinationRoot must not be inside RepoRoot (to avoid recursive backups). RepoRoot=$RepoRoot DestinationRoot=$destPath"
    }
} catch {
    # If DestinationRoot isn't resolvable yet (new path), skip this check.
}

$backupStamp = Get-NowStamp
$backupName = "francis_$backupStamp"
$backupRoot = Join-Path $DestinationRoot 'francis_backups'
$snapshotRoot = Join-Path $backupRoot $backupName
$repoSnapshot = Join-Path $snapshotRoot 'repo'
$dataSnapshot = Join-Path $snapshotRoot 'data'

# High-risk gates
$unc = Is-UncPath $DestinationRoot
if ($unc) {
    Assert-RiskyOperationApproved -Reason "DestinationRoot is a UNC path ($DestinationRoot) which increases exfiltration risk." -RepoRoot $RepoRoot -ApprovalId $ApprovalId -Force:$Force
}
if ($IncludeSecrets) {
    Assert-RiskyOperationApproved -Reason "IncludeSecrets=true will back up secret-bearing files (config/secrets.yaml, vault.db)." -RepoRoot $RepoRoot -ApprovalId $ApprovalId -Force:$Force
}
if ($Encrypt) {
    Assert-RiskyOperationApproved -Reason "Encrypt=true will create encrypted artifacts; ensure key management is approved." -RepoRoot $RepoRoot -ApprovalId $ApprovalId -Force:$Force
}

# Determine copy engine
$hasRoboCopy = $false
try {
    $rc = Get-Command 'robocopy' -ErrorAction SilentlyContinue
    if ($rc) { $hasRoboCopy = $true }
} catch { }

$dry = ($DryRun -or $WhatIfPreference)

Write-Info "RepoRoot:        $RepoRoot"
Write-Info "DestinationRoot: $DestinationRoot"
Write-Info "BackupRoot:      $backupRoot"
Write-Info "SnapshotRoot:    $snapshotRoot"
Write-Info "Mode:            $Mode"
Write-Info "IncludeData:     $IncludeData"
Write-Info "IncludeLogs:     $IncludeLogs"
Write-Info "IncludeCaches:   $IncludeCaches"
Write-Info "IncludeSecrets:  $IncludeSecrets"
Write-Info "Archive:         $Archive"
Write-Info "Encrypt:         $Encrypt"
Write-Info "ComputeHashes:   $ComputeHashes ($HashAlgorithm)"
Write-Info "Verify:          $Verify"
Write-Info "Retention:       $Retention"
if (-not [string]::IsNullOrWhiteSpace($ApprovalId)) { Write-Info "ApprovalId:      $ApprovalId" }
if ($dry) { Write-Warn "DRY-RUN ENABLED (no changes will be written)" }

# Prepare folders
if (-not $dry) {
    Ensure-Directory -Path $backupRoot
    Ensure-Directory -Path $snapshotRoot
}

# Exclusion strategy
$commonExcludeDirs = @(
    '.git',
    '.venv',
    '.mypy_cache',
    '.pytest_cache',
    '.ruff_cache',
    '__pycache__',
    'node_modules'
)

$commonExcludeFiles = @(
    '*.pyc',
    '*.pyo',
    '*.tmp',
    '*.log'
)

# Repo excludes (always exclude data here; handled separately)
$repoExcludeDirs = @($commonExcludeDirs + @('data'))
$repoExcludeFiles = @($commonExcludeFiles)

# Data excludes (safety + size)
$dataExcludeDirs = @($commonExcludeDirs)

# Always exclude volatile caches unless IncludeCaches
if (-not $IncludeCaches) {
    $dataExcludeDirs += @(
        'cache',
        'vectors',
        'web_knowledge\cache',
        'uploads\processed',
        'uploads\rejected',
        'uploads\redacted'
    )
}

# Exclude logs unless IncludeLogs
if (-not $IncludeLogs) {
    $dataExcludeDirs += @(
        'logs'
    )
}

# Exclude secrets unless IncludeSecrets
$dataExcludeFiles = @($commonExcludeFiles)
$repoExcludeFilesSecrets = @()
if (-not $IncludeSecrets) {
    $repoExcludeFilesSecrets += @('secrets.yaml')
    $dataExcludeFiles += @('vault.db')
}

# Also exclude config/secrets.yaml specifically (repo side), unless IncludeSecrets
if (-not $IncludeSecrets) {
    $repoExcludeFiles += @('secrets.yaml')
}

# Mode=incremental: attempt hardlink clone previous snapshot if possible
$prevSnapshot = $null
if ($Mode -eq 'incremental') {
    $candidates = Get-ChildItem -LiteralPath $backupRoot -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -like 'francis_*' } |
        Sort-Object -Property LastWriteTimeUtc -Descending

    if ($candidates -and $candidates.Count -gt 0) {
        $prevSnapshot = $candidates[0].FullName
        Write-Info "Previous snapshot detected for incremental mode: $prevSnapshot"
    } else {
        Write-Warn "Incremental requested, but no previous snapshot found. Falling back to full."
        $Mode = 'full'
    }
}

# For incremental hardlinking, the snapshot folder must be on same volume as prev snapshot
if ($Mode -eq 'incremental' -and $prevSnapshot) {
    if (-not (Test-IsSameVolume -PathA $prevSnapshot -PathB $snapshotRoot)) {
        Write-Warn "Incremental hardlinking requires same destination volume. Falling back to full."
        $Mode = 'full'
    }
}

# If incremental and still allowed, hardlink-clone previous then update
if ($Mode -eq 'incremental' -and $prevSnapshot) {
    Write-Info "Incremental strategy: hardlink-clone previous snapshot, then update changed files."

    # Clone entire previous snapshot first
    if ($hasRoboCopy) {
        # We clone via hardlinks using our function (more deterministic), then robocopy updates.
        New-HardlinkClone -PrevSnapshot $prevSnapshot -NewSnapshot $snapshotRoot
    } else {
        Write-Warn "Robocopy not available; incremental will behave like full (fallback copy)."
    }
}

# Copy repo (excluding data)
Write-Info "Copying repository snapshot..."
if ($hasRoboCopy) {
    Invoke-RoboCopy -Source $RepoRoot -Destination $repoSnapshot -ExcludeDirs $repoExcludeDirs -ExcludeFiles $repoExcludeFiles -Mirror:($Mode -ne 'full') -IncludeEmptyDirs
} else {
    Copy-TreeFallback -Source $RepoRoot -Destination $repoSnapshot -ExcludeDirNames $repoExcludeDirs -ExcludeFileNames $repoExcludeFiles
}

# Copy data (optional)
if ($IncludeData) {
    $dataSource = Join-Path $RepoRoot 'data'
    if (Test-Path -LiteralPath $dataSource) {
        Write-Info "Copying data snapshot..."
        if ($hasRoboCopy) {
            Invoke-RoboCopy -Source $dataSource -Destination $dataSnapshot -ExcludeDirs $dataExcludeDirs -ExcludeFiles $dataExcludeFiles -Mirror:($Mode -ne 'full') -IncludeEmptyDirs
        } else {
            Copy-TreeFallback -Source $dataSource -Destination $dataSnapshot -ExcludeDirNames $dataExcludeDirs -ExcludeFileNames $dataExcludeFiles
        }
    } else {
        Write-Warn "IncludeData=true but data/ not found at: $dataSource"
    }
} else {
    Write-Info "IncludeData=false (skipping data/)."
}

# Manifest
Write-Info "Generating manifest..."
$gitHead = Get-GitHead -Root $RepoRoot

$header = [ordered]@{
    backup_id = $backupName
    created_utc = Get-NowUtcIso
    machine = $env:COMPUTERNAME
    user = $env:USERNAME
    repo_root = $RepoRoot
    mode = $Mode
    include_data = $IncludeData
    include_logs = $IncludeLogs
    include_caches = $IncludeCaches
    include_secrets = $IncludeSecrets
    compute_hashes = $ComputeHashes
    hash_algorithm = $HashAlgorithm
    git_head = $gitHead
}

# Inventory snapshot excluding manifest files (written after)
# We inventory snapshotRoot after copy but before manifest is written, so OK.
$inventory = Get-FileInventory -RootPath $snapshotRoot -ComputeHashes $ComputeHashes -HashAlgorithm $HashAlgorithm
Write-Manifest -SnapshotRoot $snapshotRoot -Header $header -Inventory $inventory

# Verify
if ($Verify) {
    if ($dry) {
        Write-Info "[DRY-RUN] Would verify snapshot against manifest."
    } else {
        Verify-SnapshotAgainstManifest -SnapshotRoot $snapshotRoot
    }
}

# Archive (optional)
$archivePath = $null
if ($Archive -ne 'none') {
    Write-Info "Archiving snapshot ($Archive)..."

    if ($Archive -eq 'zip') {
        $archivePath = Join-Path $backupRoot ("$backupName.zip")
        New-ZipArchive -SnapshotRoot $snapshotRoot -ArchivePath $archivePath

        if ($Encrypt) {
            $pw = Get-EncryptPassword -EnvVarName $EncryptPasswordEnvVar
            $encryptedPath = "$archivePath.aes"
            Protect-FileAesGcm -InputPath $archivePath -OutputPath $encryptedPath -Password $pw

            if (-not $dry) {
                Remove-Item -LiteralPath $archivePath -Force
            }
            $archivePath = $encryptedPath
        }
    }

    if ($Archive -eq '7z') {
        $sevenZip = Get-7ZipPath
        if (-not $sevenZip) {
            throw "Archive=7z requested but 7-Zip was not found. Install 7-Zip or use Archive=zip."
        }

        $archivePath = Join-Path $backupRoot ("$backupName.7z")
        $pw = $null
        if ($Encrypt) {
            $pw = Get-EncryptPassword -EnvVarName $EncryptPasswordEnvVar
        }

        New-7zArchive -SevenZipPath $sevenZip -SnapshotRoot $snapshotRoot -ArchivePath $archivePath -Password $pw
    }

    # Optionally delete snapshot after archive
    if ($DeleteSnapshotAfterArchive) {
        if ($dry) {
            Write-Info "[DRY-RUN] Would delete snapshot folder after archive: $snapshotRoot"
        } else {
            Write-Info "Deleting snapshot folder (archived): $snapshotRoot"
            Remove-Item -LiteralPath $snapshotRoot -Recurse -Force -ErrorAction Stop
        }
    }
}

# Retention pruning
Write-Info "Applying retention..."
Prune-Backups -BackupRoot $backupRoot -Retention $Retention

# Summary
Write-Info "Backup complete."
Write-Info "Snapshot folder: $snapshotRoot"
if ($archivePath) {
    Write-Info "Archive:         $archivePath"
}
Write-Info "Manifest:        $(Join-Path $snapshotRoot 'manifest.json') (if snapshot retained)"
