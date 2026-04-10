<#
C:\Francis\scripts\web-learn.ps1

Purpose
  Crawl one or more websites (politely) and generate a local “learning corpus”:
    - cleaned text per page
    - per-page metadata JSON
    - run index CSV
    - optional JSONL suitable for RAG/embeddings
  Also writes an operations transcript log under:
    <Root>\data\logs\operations\

Defaults / Layout
  Root:      C:\Francis
  Data dir:  <Root>\data\learn\web\run_<timestamp>\
    pages\   -> <sha1>.txt + <sha1>.meta.json
    raw\     -> (optional) <sha1>.html
    index.csv
    documents.jsonl (optional)

Examples
  # Crawl a site (max 100 pages, depth 2)
  pwsh -File C:\Francis\scripts\web-learn.ps1 -Urls "https://example.com" -MaxPages 100 -MaxDepth 2

  # Crawl multiple start URLs
  pwsh -File .\web-learn.ps1 -Urls "https://example.com","https://docs.example.com" -IncludeSubdomains

  # From file (one URL per line; # comments allowed)
  pwsh -File .\web-learn.ps1 -UrlsFile "C:\Francis\data\config\web-seeds.txt"

  # Include sitemap discovery + raw HTML + JSONL
  pwsh -File .\web-learn.ps1 -Urls "https://example.com" -UseSitemap -SaveRawHtml -WriteJsonl

  # Respect robots (default). Override only if you are authorized.
  pwsh -File .\web-learn.ps1 -Urls "https://example.com" -IgnoreRobots

Notes
  - Defaults are conservative (MaxPages/Depth/Delay).
  - Respects robots.txt by default.
  - Only “text-like” content is processed (HTML and text/*). Other types are logged as skipped.
#>

[CmdletBinding(SupportsShouldProcess=$true, ConfirmImpact='Medium')]
param(
  [string]$Root = 'C:\Francis',

  [string[]]$Urls = @(),
  [string]  $UrlsFile = '',

  # Crawl behavior
  [int]   $MaxPages = 150,
  [int]   $MaxDepth = 2,
  [int]   $DelayMs  = 350,
  [int]   $TimeoutSec = 20,

  # Domain rules
  [switch]$SameDomainOnly = $true,
  [switch]$IncludeSubdomains,

  # Discovery
  [switch]$UseSitemap,
  [int]   $MaxSitemapUrls = 3000,

  # Robots
  [switch]$IgnoreRobots,
  [string]$UserAgent = 'FrancisWebLearn/1.0 (+local script)',

  # Output
  [switch]$SaveRawHtml,
  [switch]$WriteJsonl,
  [int]   $MaxTextChars = 200000,

  # If set, don’t write transcript log
  [switch]$NoTranscript
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

# -----------------------------
# Francis logging + output dirs
# -----------------------------
$Now       = Get-Date -Format "yyyyMMdd_HHmmss"
$OpLogDir  = Join-Path $Root "data\logs\operations"
$DataRoot  = Join-Path $Root "data\learn\web"
$RunDir    = Join-Path $DataRoot ("run_{0}" -f $Now)
$PagesDir  = Join-Path $RunDir "pages"
$RawDir    = Join-Path $RunDir "raw"

New-Item -ItemType Directory -Force -Path $OpLogDir | Out-Null
New-Item -ItemType Directory -Force -Path $PagesDir | Out-Null
if($SaveRawHtml){ New-Item -ItemType Directory -Force -Path $RawDir | Out-Null }

$LogPath   = Join-Path $OpLogDir ("web_learn_{0}.log" -f $Now)
$IndexCsv  = Join-Path $RunDir  "index.csv"
$ReportJson= Join-Path $RunDir  "report.json"
$JsonlPath = Join-Path $RunDir  "documents.jsonl"

if(-not $NoTranscript){
  try { Start-Transcript -Path $LogPath -Force | Out-Null } catch {}
}

function Write-Section([string]$Title){
  Write-Host ""
  Write-Host ("="*72)
  Write-Host $Title
  Write-Host ("="*72)
}

function Resolve-FullPath([string]$Path){
  try { return (Resolve-Path -LiteralPath $Path -ErrorAction Stop).Path }
  catch {
    try { return [System.IO.Path]::GetFullPath($Path) } catch { return $Path }
  }
}

$script:Errors = New-Object System.Collections.Generic.List[string]
function Add-Err([string]$Context, [string]$Message){
  $script:Errors.Add(("{0}: {1}" -f $Context, $Message)) | Out-Null
}

function Normalize-Url([string]$u){
  if([string]::IsNullOrWhiteSpace($u)){ return $null }
  $t = $u.Trim()
  if($t.StartsWith("#")){ return $null }
  if($t -notmatch '^[a-zA-Z][a-zA-Z0-9+\-.]*://'){
    # assume https if scheme missing
    $t = "https://$t"
  }
  try { return [Uri]$t } catch { return $null }
}

function Read-UrlFile([string]$Path){
  if(-not (Test-Path -LiteralPath $Path)){ throw "UrlsFile not found: $Path" }
  $lines = Get-Content -LiteralPath $Path -ErrorAction Stop
  $out = @()
  foreach($l in $lines){
    $u = Normalize-Url $l
    if($u){ $out += $u.AbsoluteUri }
  }
  return $out
}

function Get-Sha1Hex([string]$Text){
  $sha1 = [System.Security.Cryptography.SHA1]::Create()
  try{
    $bytes = [System.Text.Encoding]::UTF8.GetBytes($Text)
    $hash  = $sha1.ComputeHash($bytes)
    return -join ($hash | ForEach-Object { $_.ToString('x2') })
  } finally {
    $sha1.Dispose()
  }
}

function Get-BaseRoot([Uri]$u){
  # scheme://host[:port]
  $builder = New-Object System.UriBuilder($u)
  $builder.Path  = '/'
  $builder.Query = ''
  $builder.Fragment = ''
  return $builder.Uri
}

function Test-HostAllowed {
  param(
    [Uri]$Uri,
    [string[]]$AllowedHosts,
    [switch]$IncludeSubdomains
  )
  if(-not $Uri -or -not $Uri.Host){ return $false }

  foreach($h in $AllowedHosts){
    if([string]::IsNullOrWhiteSpace($h)){ continue }
    if($IncludeSubdomains){
      if($Uri.Host -ieq $h){ return $true }
      if($Uri.Host.ToLowerInvariant().EndsWith("." + $h.ToLowerInvariant())){ return $true }
    } else {
      if($Uri.Host -ieq $h){ return $true }
    }
  }
  return $false
}

function Convert-HtmlToText([string]$Html){
  if([string]::IsNullOrWhiteSpace($Html)){ return "" }

  # Remove script/style/noscript blocks (best-effort)
  $s = $Html
  $s = [regex]::Replace($s, '(?is)<(script|style|noscript)\b.*?>.*?</\1>', ' ')
  # Replace some block tags with newlines
  $s = [regex]::Replace($s, '(?is)<\s*(br|p|div|li|tr|h1|h2|h3|h4|h5|h6)\b[^>]*>', "`n")
  # Remove all remaining tags
  $s = [regex]::Replace($s, '(?is)<[^>]+>', ' ')
  # Decode HTML entities
  try { $s = [System.Net.WebUtility]::HtmlDecode($s) } catch {}
  # Normalize whitespace
  $s = $s -replace '\r',''
  $s = [regex]::Replace($s, '[ \t]+', ' ')
  $s = [regex]::Replace($s, '\n\s*\n+', "`n`n")
  return $s.Trim()
}

function Get-TitleFromHtml([string]$Html){
  if([string]::IsNullOrWhiteSpace($Html)){ return $null }
  $m = [regex]::Match($Html, '(?is)<title\b[^>]*>(.*?)</title>')
  if($m.Success){
    $t = $m.Groups[1].Value
    try { $t = [System.Net.WebUtility]::HtmlDecode($t) } catch {}
    return ($t -replace '\s+',' ').Trim()
  }
  return $null
}

function Invoke-WebGet {
  param(
    [Parameter(Mandatory=$true)][Uri]$Uri,
    [string]$UserAgent,
    [int]$TimeoutSec
  )

  $iwr = Get-Command Invoke-WebRequest -ErrorAction Stop

  $params = @{
    Uri         = $Uri.AbsoluteUri
    Method      = 'GET'
    Headers     = @{ 'User-Agent' = $UserAgent }
    TimeoutSec  = $TimeoutSec
    ErrorAction = 'Stop'
  }

  # Compatibility: Windows PowerShell 5.1 has -UseBasicParsing; PowerShell 7+ removed it.
  if($iwr.Parameters.ContainsKey('UseBasicParsing')){
    $params['UseBasicParsing'] = $true
  }

  # PowerShell 7+: -SkipHttpErrorCheck exists to avoid exceptions for 4xx/5xx
  if($iwr.Parameters.ContainsKey('SkipHttpErrorCheck')){
    $params['SkipHttpErrorCheck'] = $true
  }

  return Invoke-WebRequest @params
}

# -----------------------------
# robots.txt (minimal parser)
# -----------------------------
function Get-Robots {
  param(
    [Parameter(Mandatory=$true)][Uri]$BaseRoot,
    [string]$UserAgent,
    [int]$TimeoutSec
  )

  $robotsUrl = [Uri]::new($BaseRoot, "/robots.txt")
  $result = [ordered]@{
    url = $robotsUrl.AbsoluteUri
    fetched = $false
    statusCode = $null
    disallow = @()
    sitemap = @()
    raw = $null
    note = ""
  }

  try {
    $resp = Invoke-WebGet -Uri $robotsUrl -UserAgent $UserAgent -TimeoutSec $TimeoutSec
    $result.fetched = $true
    try { $result.statusCode = [int]$resp.StatusCode } catch {}

    $raw = [string]$resp.Content
    $result.raw = $raw

    # Parse groups: choose UA-specific group if present, else '*' group
    $lines = $raw -split "`r?`n" | ForEach-Object {
      $t = ($_ -as [string]).Trim()
      if(-not $t){ return $null }
      if($t.StartsWith("#")){ return $null }
      # strip trailing comment
      $t = ($t -split '#',2)[0].Trim()
      if($t){ $t } else { $null }
    } | Where-Object { $_ }

    $groups = New-Object System.Collections.Generic.List[object]
    $cur = [ordered]@{ userAgents = @(); disallow=@(); sitemap=@() }

    foreach($ln in $lines){
      if($ln -match '^(?i)\s*user-agent\s*:\s*(.+)$'){
        $ua = $Matches[1].Trim()
        # Start a new group if we already have UA entries and see another UA (common pattern)
        if($cur.userAgents.Count -gt 0 -and ($cur.disallow.Count -gt 0 -or $cur.sitemap.Count -gt 0)){
          $groups.Add([pscustomobject]$cur) | Out-Null
          $cur = [ordered]@{ userAgents = @(); disallow=@(); sitemap=@() }
        }
        $cur.userAgents += $ua
        continue
      }

      if($ln -match '^(?i)\s*disallow\s*:\s*(.*)$'){
        $p = $Matches[1].Trim()
        if($p){ $cur.disallow += $p }
        continue
      }

      if($ln -match '^(?i)\s*sitemap\s*:\s*(.+)$'){
        $s = $Matches[1].Trim()
        if($s){ $cur.sitemap += $s }
        continue
      }
    }

    if($cur.userAgents.Count -gt 0 -or $cur.disallow.Count -gt 0 -or $cur.sitemap.Count -gt 0){
      $groups.Add([pscustomobject]$cur) | Out-Null
    }

    $uaLower = ($UserAgent ?? "").ToLowerInvariant()
    $matchUa = $null
    $matchStar = $null

    foreach($g in $groups){
      foreach($ua in @($g.userAgents)){
        $u = ($ua -as [string]).Trim().ToLowerInvariant()
        if($u -eq '*'){ $matchStar = $g }
        if($u -and $uaLower -and $uaLower -like "$u*"){ $matchUa = $g }
      }
    }

    $chosen = $matchUa
    if(-not $chosen){ $chosen = $matchStar }

    if($chosen){
      $result.disallow = @($chosen.disallow | Where-Object { $_ })
      $result.sitemap  = @($chosen.sitemap  | Where-Object { $_ })
    } else {
      # still honor any sitemap lines found anywhere
      $allSitemaps = @()
      foreach($g in $groups){ $allSitemaps += @($g.sitemap) }
      $result.sitemap = @($allSitemaps | Where-Object { $_ } | Select-Object -Unique)
      $result.note = "No matching UA group; disallow not applied."
    }
  } catch {
    $result.note = "robots fetch failed: $($_.Exception.Message)"
  }

  return [pscustomobject]$result
}

function Test-RobotsAllowed {
  param(
    [pscustomobject]$Robots,
    [Uri]$Uri
  )
  if(-not $Robots -or -not $Uri){ return $true }
  if(-not $Robots.disallow -or $Robots.disallow.Count -eq 0){ return $true }

  $path = $Uri.AbsolutePath
  foreach($rule in @($Robots.disallow)){
    $r = ($rule -as [string]).Trim()
    if(-not $r){ continue }
    if($r -eq '/'){ return $false }

    # Minimal wildcard support: '*' -> '.*'
    $pattern = [regex]::Escape($r) -replace '\\\*','.*'
    # rules in robots are usually path-prefix matches
    if($path -match ("(?i)^" + $pattern)){
      return $false
    }
  }
  return $true
}

# -----------------------------
# sitemap.xml discovery (optional)
# -----------------------------
function Get-SitemapUrls {
  param(
    [Uri]$BaseRoot,
    [string[]]$SitemapHints,
    [string]$UserAgent,
    [int]$TimeoutSec,
    [int]$MaxUrls = 3000
  )

  $queue = New-Object System.Collections.Generic.Queue[string]
  $seen  = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)
  $urls  = New-Object System.Collections.Generic.List[string]

  $hints = @()
  if($SitemapHints){ $hints += $SitemapHints }
  if($hints.Count -eq 0){
    $hints += ([Uri]::new($BaseRoot, "/sitemap.xml").AbsoluteUri)
  }

  foreach($h in $hints){
    if($seen.Add($h)){ $queue.Enqueue($h) }
  }

  $rounds = 0
  while($queue.Count -gt 0 -and $urls.Count -lt $MaxUrls -and $rounds -lt 50){
    $rounds++
    $smUrl = $queue.Dequeue()
    try {
      $resp = Invoke-WebGet -Uri ([Uri]$smUrl) -UserAgent $UserAgent -TimeoutSec $TimeoutSec
      $xmlText = [string]$resp.Content
      if([string]::IsNullOrWhiteSpace($xmlText)){ continue }

      $xml = $null
      try { $xml = [xml]$xmlText } catch { continue }

      # Find all <loc> elements regardless of namespace
      $locs = $xml.SelectNodes("//*[local-name()='loc']")
      if(-not $locs){ continue }

      # Heuristic: if root looks like sitemapindex, enqueue locs as more sitemaps
      $rootName = $xml.DocumentElement.LocalName
      if($rootName -ieq 'sitemapindex'){
        foreach($n in $locs){
          $v = ($n.InnerText -as [string]).Trim()
          if($v -and $seen.Add($v)){ $queue.Enqueue($v) }
        }
      } else {
        foreach($n in $locs){
          $v = ($n.InnerText -as [string]).Trim()
          if($v -and $urls.Count -lt $MaxUrls){
            $urls.Add($v) | Out-Null
          }
        }
      }
    } catch {
      # ignore sitemap fetch errors
    }
  }

  return @($urls | Select-Object -Unique)
}

# -----------------------------
# Start URLs + Allowed Hosts
# -----------------------------
Write-Section "Web Learn"
Write-Host ("Root     : {0}" -f (Resolve-FullPath $Root))
Write-Host ("RunDir   : {0}" -f (Resolve-FullPath $RunDir))
if(-not $NoTranscript){ Write-Host ("Log      : {0}" -f $LogPath) }
Write-Host ("IndexCSV : {0}" -f $IndexCsv)
Write-Host ("Report   : {0}" -f $ReportJson)
if($WriteJsonl){ Write-Host ("JSONL    : {0}" -f $JsonlPath) }

$seedList = @()
if($UrlsFile){
  $seedList = Read-UrlFile -Path $UrlsFile
} elseif($Urls.Count -gt 0){
  foreach($u in $Urls){
    $nu = Normalize-Url $u
    if($nu){ $seedList += $nu.AbsoluteUri }
  }
}

if(-not $seedList -or $seedList.Count -eq 0){
  throw "No URLs provided. Use -Urls or -UrlsFile."
}

# Normalize/unique while preserving order
$seenSeed = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)
$seeds = @()
foreach($s in $seedList){
  if($seenSeed.Add($s)){ $seeds += $s }
}

Write-Host ""
Write-Host "Seeds:"
$seeds | ForEach-Object { Write-Host ("  - {0}" -f $_) }

$allowedHosts = @()
foreach($s in $seeds){
  try {
    $u = [Uri]$s
    if($u.Host){ $allowedHosts += $u.Host }
  } catch {}
}
$allowedHosts = @($allowedHosts | Select-Object -Unique)

Write-Host ""
Write-Host "Allowed hosts:"
$allowedHosts | ForEach-Object { Write-Host ("  - {0}" -f $_) }
Write-Host ("SameDomainOnly   : {0}" -f $SameDomainOnly)
Write-Host ("IncludeSubdomains: {0}" -f $IncludeSubdomains)

# -----------------------------
# robots + sitemap per host
# -----------------------------
$robotsByHost = @{}
$sitemapUrlsAll = @()

foreach($h in $allowedHosts){
  try {
    $base = Normalize-Url ("https://{0}/" -f $h)
    if(-not $base){ continue }
    $baseRoot = Get-BaseRoot $base

    $robots = $null
    if(-not $IgnoreRobots){
      $robots = Get-Robots -BaseRoot $baseRoot -UserAgent $UserAgent -TimeoutSec $TimeoutSec
      $robotsByHost[$h.ToLowerInvariant()] = $robots
      Write-Host ""
      Write-Host ("robots: {0} (fetched={1}, status={2})" -f $robots.url,$robots.fetched,$robots.statusCode)
      if($robots.note){ Write-Host ("  note: {0}" -f $robots.note) }
      if($robots.disallow -and $robots.disallow.Count -gt 0){
        Write-Host ("  disallow rules: {0}" -f $robots.disallow.Count)
      }
      if($robots.sitemap -and $robots.sitemap.Count -gt 0){
        Write-Host ("  sitemap hints:  {0}" -f $robots.sitemap.Count)
      }
    }

    if($UseSitemap){
      $hints = @()
      if($robots -and $robots.sitemap -and $robots.sitemap.Count -gt 0){
        $hints += $robots.sitemap
      }

      $sm = Get-SitemapUrls -BaseRoot $baseRoot -SitemapHints $hints -UserAgent $UserAgent -TimeoutSec $TimeoutSec -MaxUrls $MaxSitemapUrls
      if($sm -and $sm.Count -gt 0){
        Write-Host ("sitemap urls discovered for {0}: {1}" -f $h,$sm.Count)
        $sitemapUrlsAll += $sm
      } else {
        Write-Host ("sitemap urls discovered for {0}: 0" -f $h)
      }
    }
  } catch {
    Add-Err "Init:$h" $_.Exception.Message
  }
}

# -----------------------------
# Crawl queue (BFS)
# -----------------------------
$queue = New-Object System.Collections.Generic.Queue[object]
$visited = New-Object System.Collections.Generic.HashSet[string] ([StringComparer]::OrdinalIgnoreCase)

foreach($s in $seeds){
  $queue.Enqueue([pscustomobject]@{ url=$s; depth=0; via="seed" })
}

# If sitemap is enabled, enqueue sitemap URLs too (but still respect MaxPages and domain rules)
if($UseSitemap -and $sitemapUrlsAll -and $sitemapUrlsAll.Count -gt 0){
  $uniqSm = $sitemapUrlsAll | Select-Object -Unique
  foreach($u in $uniqSm){
    $nu = Normalize-Url $u
    if($nu){
      $queue.Enqueue([pscustomobject]@{ url=$nu.AbsoluteUri; depth=0; via="sitemap" })
    }
  }
}

$results = New-Object System.Collections.Generic.List[object]

function Extract-Links {
  param(
    $WebResponse,
    [Uri]$BaseUri
  )
  $out = New-Object System.Collections.Generic.List[string]

  # Try built-in .Links (works for HTML responses in many PS builds)
  try {
    if($WebResponse -and $WebResponse.Links){
      foreach($lnk in $WebResponse.Links){
        $href = $null
        try { $href = [string]$lnk.href } catch {}
        if(-not $href){ continue }
        $href = $href.Trim()
        if(-not $href){ continue }
        if($href.StartsWith("#")){ continue }
        if($href -match '^(?i)javascript:'){ continue }
        if($href -match '^(?i)mailto:'){ continue }

        try {
          $abs = $null
          if($href -match '^[a-zA-Z][a-zA-Z0-9+\-.]*://'){
            $abs = [Uri]$href
          } else {
            $abs = [Uri]::new($BaseUri, $href)
          }
          if($abs.Scheme -in @('http','https')){
            $out.Add($abs.AbsoluteUri) | Out-Null
          }
        } catch {}
      }
      return @($out)
    }
  } catch {}

  # Fallback: regex href scan from Content
  try {
    $html = [string]$WebResponse.Content
    if($html){
      $ms = [regex]::Matches($html, '(?is)href\s*=\s*["'']([^"''#]+)["'']')
      foreach($m in $ms){
        $href = ($m.Groups[1].Value -as [string]).Trim()
        if(-not $href){ continue }
        if($href -match '^(?i)javascript:'){ continue }
        if($href -match '^(?i)mailto:'){ continue }
        try {
          $abs = $null
          if($href -match '^[a-zA-Z][a-zA-Z0-9+\-.]*://'){
            $abs = [Uri]$href
          } else {
            $abs = [Uri]::new($BaseUri, $href)
          }
          if($abs.Scheme -in @('http','https')){
            $out.Add($abs.AbsoluteUri) | Out-Null
          }
        } catch {}
      }
    }
  } catch {}

  return @($out)
}

Write-Section "Crawl"
Write-Host ("MaxPages: {0} | MaxDepth: {1} | DelayMs: {2} | TimeoutSec: {3}" -f $MaxPages,$MaxDepth,$DelayMs,$TimeoutSec)
Write-Host ("IgnoreRobots: {0} | UseSitemap: {1}" -f $IgnoreRobots,$UseSitemap)
Write-Host ("SaveRawHtml: {0} | WriteJsonl: {1}" -f $SaveRawHtml,$WriteJsonl)

$startTime = Get-Date

while($queue.Count -gt 0 -and $visited.Count -lt $MaxPages){
  $item = $queue.Dequeue()
  $uStr = [string]$item.url
  $depth= [int]$item.depth
  $via  = [string]$item.via

  $uri = $null
  try { $uri = [Uri]$uStr } catch { continue }
  if(-not $uri -or -not $uri.Host){ continue }

  # Enforce domain rule
  if($SameDomainOnly){
    if(-not (Test-HostAllowed -Uri $uri -AllowedHosts $allowedHosts -IncludeSubdomains:$IncludeSubdomains)){
      continue
    }
  }

  # De-dupe by normalized absolute URI (strip fragment)
  $normBuilder = New-Object System.UriBuilder($uri)
  $normBuilder.Fragment = ''
  $norm = $normBuilder.Uri.AbsoluteUri

  if(-not $visited.Add($norm)){ continue }

  # robots (per-host) unless ignored
  if(-not $IgnoreRobots){
    $k = $uri.Host.ToLowerInvariant()
    $rob = $null
    if($robotsByHost.ContainsKey($k)){ $rob = $robotsByHost[$k] }
    if($rob){
      if(-not (Test-RobotsAllowed -Robots $rob -Uri $uri)){
        $results.Add([pscustomobject]@{
          Url         = $norm
          Depth       = $depth
          Via         = $via
          Status      = "SKIPPED_ROBOTS"
          StatusCode  = $null
          ContentType = $null
          Bytes       = 0
          Title       = $null
          TextChars   = 0
          SavedText   = $null
          SavedMeta   = $null
          SavedRaw    = $null
          FetchedAt   = (Get-Date).ToString("o")
          Why         = "Disallowed by robots.txt"
        }) | Out-Null
        continue
      }
    }
  }

  Write-Host ""
  Write-Host ("[{0}/{1}] GET (d={2}) {3}" -f $visited.Count,$MaxPages,$depth,$norm)

  $resp = $null
  $statusCode = $null
  $ctype = $null
  $bytes = 0
  $title = $null
  $text  = $null
  $why   = ""

  try {
    if($PSCmdlet.ShouldProcess($norm, "Fetch")){
      $resp = Invoke-WebGet -Uri $uri -UserAgent $UserAgent -TimeoutSec $TimeoutSec
    } else {
      $why = "ShouldProcess declined"
      $results.Add([pscustomobject]@{
        Url=$norm; Depth=$depth; Via=$via; Status="WHATIF"
        StatusCode=$null; ContentType=$null; Bytes=0; Title=$null; TextChars=0
        SavedText=$null; SavedMeta=$null; SavedRaw=$null; FetchedAt=(Get-Date).ToString("o"); Why=$why
      }) | Out-Null
      continue
    }

    try { $statusCode = [int]$resp.StatusCode } catch { $statusCode = $null }
    try { $ctype = [string]$resp.Headers['Content-Type'] } catch { $ctype = $null }
    if(-not $ctype){
      try { $ctype = [string]$resp.ContentType } catch {}
    }

    $content = [string]$resp.Content
    if($content){
      $bytes = ([System.Text.Encoding]::UTF8.GetByteCount($content))
    }

    # Only process html/text
    $isHtml = $false
    $isText = $false
    if($ctype){
      if($ctype -match '(?i)text/html'){ $isHtml = $true }
      elseif($ctype -match '(?i)^text/'){ $isText = $true }
      elseif($ctype -match '(?i)application/xhtml\+xml'){ $isHtml = $true }
    } else {
      # heuristic: if it looks like html
      if($content -match '(?is)<html\b'){ $isHtml = $true } else { $isText = $true }
    }

    if(-not ($isHtml -or $isText)){
      $why = "Non-text content type"
      $results.Add([pscustomobject]@{
        Url=$norm; Depth=$depth; Via=$via; Status="SKIPPED_TYPE"
        StatusCode=$statusCode; ContentType=$ctype; Bytes=$bytes; Title=$null; TextChars=0
        SavedText=$null; SavedMeta=$null; SavedRaw=$null; FetchedAt=(Get-Date).ToString("o"); Why=$why
      }) | Out-Null
      continue
    }

    if($isHtml){
      $title = Get-TitleFromHtml $content
      $text  = Convert-HtmlToText $content
    } else {
      $title = $null
      $text  = ($content -replace '\r','').Trim()
    }

    if($MaxTextChars -gt 0 -and $text.Length -gt $MaxTextChars){
      $text = $text.Substring(0, $MaxTextChars)
    }

    $id = Get-Sha1Hex $norm
    $txtPath  = Join-Path $PagesDir ("{0}.txt" -f $id)
    $metaPath = Join-Path $PagesDir ("{0}.meta.json" -f $id)
    $rawPath  = if($SaveRawHtml) { Join-Path $RawDir ("{0}.html" -f $id) } else { $null }

    # Save files
    if($PSCmdlet.ShouldProcess($txtPath, "Write page text")){
      $text | Out-File -LiteralPath $txtPath -Encoding UTF8 -Force
    }
    if($SaveRawHtml -and $rawPath){
      if($PSCmdlet.ShouldProcess($rawPath, "Write raw HTML")){
        $content | Out-File -LiteralPath $rawPath -Encoding UTF8 -Force
      }
    }

    # Extract links (for BFS)
    $links = @()
    if($depth -lt $MaxDepth){
      $links = @(Extract-Links -WebResponse $resp -BaseUri $uri)
    }

    $meta = [ordered]@{
      id          = $id
      url         = $norm
      host        = $uri.Host
      depth       = $depth
      via         = $via
      fetched_at  = (Get-Date).ToString("o")
      status_code = $statusCode
      content_type= $ctype
      bytes       = $bytes
      title       = $title
      text_chars  = $text.Length
      link_count  = ($links.Count)
      tool        = "web-learn.ps1"
      user_agent  = $UserAgent
    }

    if($PSCmdlet.ShouldProcess($metaPath, "Write metadata JSON")){
      ($meta | ConvertTo-Json -Depth 6) | Out-File -LiteralPath $metaPath -Encoding UTF8 -Force
    }

    # Enqueue new links
    if($depth -lt $MaxDepth -and $links -and $links.Count -gt 0){
      foreach($lk in $links){
        $lkUri = Normalize-Url $lk
        if(-not $lkUri){ continue }

        if($SameDomainOnly){
          if(-not (Test-HostAllowed -Uri $lkUri -AllowedHosts $allowedHosts -IncludeSubdomains:$IncludeSubdomains)){
            continue
          }
        }

        # Normalize (strip fragment)
        $b = New-Object System.UriBuilder($lkUri)
        $b.Fragment = ''
        $n2 = $b.Uri.AbsoluteUri

        if(-not $visited.Contains($n2)){
          $queue.Enqueue([pscustomobject]@{ url=$n2; depth=($depth+1); via=$norm })
        }
      }
    }

    # Record index row
    $results.Add([pscustomobject]@{
      Url         = $norm
      Depth       = $depth
      Via         = $via
      Status      = "OK"
      StatusCode  = $statusCode
      ContentType = $ctype
      Bytes       = $bytes
      Title       = $title
      TextChars   = $text.Length
      SavedText   = $txtPath
      SavedMeta   = $metaPath
      SavedRaw    = $rawPath
      FetchedAt   = (Get-Date).ToString("o")
      Why         = ""
    }) | Out-Null

    Write-Host ("OK   {0} chars | {1} links" -f $text.Length, ($links.Count))
  }
  catch {
    $why = $_.Exception.Message
    Add-Err "Fetch:$norm" $why
    Write-Warning ("FAIL {0}" -f $why)

    $results.Add([pscustomobject]@{
      Url=$norm; Depth=$depth; Via=$via; Status="FAILED"
      StatusCode=$statusCode; ContentType=$ctype; Bytes=$bytes; Title=$title; TextChars=0
      SavedText=$null; SavedMeta=$null; SavedRaw=$null; FetchedAt=(Get-Date).ToString("o"); Why=$why
    }) | Out-Null
  }

  if($DelayMs -gt 0){
    Start-Sleep -Milliseconds $DelayMs
  }
}

# -----------------------------
# Write outputs (CSV / report / optional JSONL)
# -----------------------------
Write-Section "Write Outputs"

try {
  $results | Export-Csv -NoTypeInformation -Encoding UTF8 -LiteralPath $IndexCsv
  Write-Host ("Saved index CSV : {0}" -f $IndexCsv)
} catch {
  Add-Err "ExportCSV" $_.Exception.Message
}

# JSONL (docs)
if($WriteJsonl){
  try {
    if(Test-Path -LiteralPath $JsonlPath){ Remove-Item -LiteralPath $JsonlPath -Force -ErrorAction SilentlyContinue }
    foreach($r in $results){
      if($r.Status -ne 'OK'){ continue }
      if(-not (Test-Path -LiteralPath $r.SavedText)){ continue }
      $docText = Get-Content -LiteralPath $r.SavedText -Raw -ErrorAction SilentlyContinue
      if([string]::IsNullOrWhiteSpace($docText)){ continue }

      $id = Get-Sha1Hex $r.Url
      $obj = [ordered]@{
        id         = $id
        url        = $r.Url
        title      = $r.Title
        text       = $docText
        fetched_at = $r.FetchedAt
        source     = "web-learn"
        content_type = $r.ContentType
      }
      ($obj | ConvertTo-Json -Depth 6 -Compress) | Out-File -LiteralPath $JsonlPath -Encoding UTF8 -Append
    }
    Write-Host ("Saved JSONL     : {0}" -f $JsonlPath)
  } catch {
    Add-Err "WriteJSONL" $_.Exception.Message
  }
}

# Report JSON
$endTime = Get-Date
$report = [ordered]@{
  timestamp   = $Now
  started_at  = $startTime.ToString("o")
  ended_at    = $endTime.ToString("o")
  duration_s  = [math]::Round(($endTime - $startTime).TotalSeconds,2)
  root        = (Resolve-FullPath $Root)
  run_dir     = (Resolve-FullPath $RunDir)
  seeds       = $seeds
  allowed_hosts = $allowedHosts
  settings    = [ordered]@{
    MaxPages = $MaxPages
    MaxDepth = $MaxDepth
    DelayMs  = $DelayMs
    TimeoutSec = $TimeoutSec
    SameDomainOnly = [bool]$SameDomainOnly
    IncludeSubdomains = [bool]$IncludeSubdomains
    UseSitemap = [bool]$UseSitemap
    MaxSitemapUrls = $MaxSitemapUrls
    IgnoreRobots = [bool]$IgnoreRobots
    UserAgent = $UserAgent
    SaveRawHtml = [bool]$SaveRawHtml
    WriteJsonl  = [bool]$WriteJsonl
    MaxTextChars= $MaxTextChars
  }
  counts = [ordered]@{
    visited = $visited.Count
    queued_remaining = $queue.Count
    ok      = @($results | Where-Object { $_.Status -eq 'OK' }).Count
    failed  = @($results | Where-Object { $_.Status -eq 'FAILED' }).Count
    skipped_type   = @($results | Where-Object { $_.Status -eq 'SKIPPED_TYPE' }).Count
    skipped_robots = @($results | Where-Object { $_.Status -eq 'SKIPPED_ROBOTS' }).Count
    whatif  = @($results | Where-Object { $_.Status -eq 'WHATIF' }).Count
  }
  outputs = [ordered]@{
    index_csv = (Resolve-FullPath $IndexCsv)
    report_json = (Resolve-FullPath $ReportJson)
    jsonl = (if($WriteJsonl){ Resolve-FullPath $JsonlPath } else { $null })
    pages_dir = (Resolve-FullPath $PagesDir)
    raw_dir   = (if($SaveRawHtml){ Resolve-FullPath $RawDir } else { $null })
    log = (if(-not $NoTranscript){ $LogPath } else { $null })
  }
  errors = @($script:Errors)
}

try {
  ($report | ConvertTo-Json -Depth 10) | Out-File -LiteralPath $ReportJson -Encoding UTF8 -Force
  Write-Host ("Saved report JSON: {0}" -f $ReportJson)
} catch {
  Add-Err "ExportReportJSON" $_.Exception.Message
}

Write-Section "Summary"
$results | Group-Object Status | Sort-Object Count -Descending | Format-Table Count,Name -AutoSize

Write-Host ""
Write-Host ("RunDir   : {0}" -f $RunDir)
Write-Host ("IndexCSV : {0}" -f $IndexCsv)
Write-Host ("Report   : {0}" -f $ReportJson)
if($WriteJsonl){ Write-Host ("JSONL    : {0}" -f $JsonlPath) }
if(-not $NoTranscript){ Write-Host ("Log      : {0}" -f $LogPath) }

if($script:Errors.Count -gt 0){
  Write-Host ""
  Write-Warning ("Non-fatal errors captured: {0} (see report.json)" -f $script:Errors.Count)
}

if(-not $NoTranscript){
  try { Stop-Transcript | Out-Null } catch {}
}
