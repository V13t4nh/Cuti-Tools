[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$OutputPath,

    [Parameter(Mandatory = $false)]
    [string]$DependencyBundlePath,

    [Parameter(Mandatory = $false)]
    [string]$DependencyManifestPath,

    [Parameter(Mandatory = $false)]
    [string]$ConfigPath,

    [switch]$AllowDirty,
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

function Fail([string]$Message) {
    throw "Notion sandbox export failed: $Message"
}

function Invoke-Git([string[]]$Arguments) {
    $result = @(& git -C $script:RepoRoot @Arguments 2>&1)
    if ($LASTEXITCODE -ne 0) {
        Fail ("git " + ($Arguments -join ' ') + " failed: " + ($result -join "`n"))
    }
    return $result
}

function Get-ConfigValue($Object, [string]$Name, $DefaultValue) {
    $property = $Object.PSObject.Properties[$Name]
    if ($null -eq $property -or $null -eq $property.Value) { return $DefaultValue }
    return $property.Value
}

function Convert-ToZipName([string]$Path) {
    return ($Path -replace '\\', '/')
}

function Test-ForbiddenPath([string]$Path) {
    $normalized = Convert-ToZipName $Path
    $parts = @($normalized -split '/')
    foreach ($part in $parts) {
        if ($part -in @('.git', '.zip', 'node_modules', '.next', 'dist', 'out', 'build', 'coverage', 'test-results', 'playwright-report', 'blob-report', 'runtime', 'cache', '.cache', '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.venv', 'venv', 'var', 'tmp', 'temp')) {
            return $true
        }
    }
    if ($normalized -match '(^|/)\.env($|/)' -or $normalized -match '(^|/)\.env\.[^/]+($|/)') {
        if ($normalized -notmatch '(^|/)\.env\.example$') { return $true }
    }
    if ($normalized -match '\.(db|sqlite|sqlite3|log)$') { return $true }
    return $false
}

function Test-SecretText([string]$Text) {
    $patterns = @(
        '(?i)-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----',
        '(?i)\bAKIA[0-9A-Z]{16}\b',
        '(?i)\b(?:ghp|gho|github_pat|sk_live|sk_test|xoxb|xoxp)-[A-Za-z0-9_-]{16,}\b',
        '(?i)\b(?:api[_-]?key|access[_-]?token|secret|password|private[_-]?key)\s*[:=]\s*["'']?[A-Za-z0-9_+/=-]{20,}',
        '(?i)\bpostgres(?:ql)?://[^\s"'']+:[^\s"'']+@[^\s"'']+'
    )
    foreach ($pattern in $patterns) {
        if ($Text -match $pattern) { return $true }
    }
    return $false
}

function Add-ZipText([string]$ZipPath, [string]$EntryName, [string]$Text) {
    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $entry = $zip.CreateEntry($EntryName, [System.IO.Compression.CompressionLevel]::Optimal)
        $writer = New-Object System.IO.StreamWriter($entry.Open(), (New-Object System.Text.UTF8Encoding($false)))
        try { $writer.Write($Text) } finally { $writer.Dispose() }
    } finally { $zip.Dispose() }
}

function Add-ZipDirectory([string]$ZipPath, [string]$Directory, [string]$Prefix) {
    $zip = [System.IO.Compression.ZipFile]::Open($ZipPath, [System.IO.Compression.ZipArchiveMode]::Update)
    try {
        $base = (Resolve-Path -LiteralPath $Directory).Path
        foreach ($file in @(Get-ChildItem -LiteralPath $base -File -Recurse -Force)) {
            $relative = $file.FullName.Substring($base.Length).TrimStart('\', '/')
            $zipName = Convert-ToZipName ($Prefix + $relative)
            if (Test-ForbiddenPath $relative) { Fail "dependency bundle contains forbidden path '$relative'" }
            if ($zipName -match '(^|/)\.env($|/)' -and $zipName -notmatch '(^|/)\.env\.example$') { Fail "dependency bundle contains an environment secret file '$relative'" }
            $entry = $zip.CreateEntry($zipName, [System.IO.Compression.CompressionLevel]::Optimal)
            $input = [System.IO.File]::OpenRead($file.FullName)
            $output = $entry.Open()
            try { $input.CopyTo($output) } finally { $output.Dispose(); $input.Dispose() }
        }
    } finally { $zip.Dispose() }
}

function Assert-ZipSafe([string]$ZipPath) {
    $zip = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
    $entryCount = 0
    $uncompressedBytes = [int64]0
    try {
        foreach ($entry in $zip.Entries) {
            $entryCount++
            $name = Convert-ToZipName $entry.FullName
            if ([string]::IsNullOrWhiteSpace($name) -or $name -match '(^|/)\.\.?(/|$)') { Fail "archive contains unsafe path '$name'" }
            if (Test-ForbiddenPath $name) { Fail "archive contains forbidden path '$name'" }
            if ($name -match '(^|/)\.env\.example$') { continue }
            if ($name -match '(^|/)\.env($|/)') { Fail "archive contains environment secret file '$name'" }
            $uncompressedBytes += [int64]$entry.Length
        }
    } finally { $zip.Dispose() }
    if ($entryCount -lt 1) { Fail 'archive is empty' }
    return [pscustomobject]@{ Entries = $entryCount; UncompressedBytes = $uncompressedBytes }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:RepoRoot = (Resolve-Path (Join-Path $scriptDir '..')).Path
$repoName = Split-Path -Leaf $script:RepoRoot

if (-not (Test-Path -LiteralPath (Join-Path $script:RepoRoot '.git'))) { Fail "repository root '$script:RepoRoot' has no .git directory" }
$configFile = if ($ConfigPath) { $ConfigPath } else { Join-Path $script:RepoRoot 'sandbox\notion-sandbox.json' }
if (-not (Test-Path -LiteralPath $configFile)) { Fail "config not found: $configFile" }
$config = Get-Content -LiteralPath $configFile -Raw | ConvertFrom-Json

$status = @(Invoke-Git @('status', '--porcelain', '--untracked-files=all'))
if (-not $AllowDirty -and $status.Count -gt 0) { Fail "worktree is not clean; commit or stash changes first (or pass -AllowDirty explicitly)" }
$commit = (Invoke-Git @('rev-parse', 'HEAD') | Select-Object -First 1).Trim()
$branch = (Invoke-Git @('symbolic-ref', '--short', '-q', 'HEAD') | Select-Object -First 1).Trim()
if ([string]::IsNullOrWhiteSpace($branch)) { $branch = 'DETACHED' }
$tracked = @(Invoke-Git @('ls-files')) | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ }
foreach ($path in $tracked) {
    $normalizedPath = Convert-ToZipName $path
    if ($normalizedPath -match '(^|/)\.git(/|$)') { Fail "tracked .git path is not allowed: $path" }
    if ($normalizedPath -match '(^|/)\.env($|/)' -or ($normalizedPath -match '(^|/)\.env\.[^/]+($|/)' -and $normalizedPath -notmatch '(^|/)\.env\.example$')) { Fail "tracked environment secret file is not allowed: $path" }
    if (Test-ForbiddenPath $normalizedPath) { Fail "tracked output/dependency/runtime path is not allowed: $path" }
    if ($normalizedPath -notmatch '(^|/)\.env\.example$') {
        $full = Join-Path $script:RepoRoot $path
        if (Test-Path -LiteralPath $full -PathType Leaf) {
            $item = Get-Item -LiteralPath $full
            if ($item.Length -le 2097152) {
                $text = Get-Content -LiteralPath $full -Raw -ErrorAction SilentlyContinue
                if ($text -and (Test-SecretText $text)) { Fail "high-confidence secret-like value found in tracked file '$path'" }
            }
        }
    }
}

if (-not $OutputPath) { $OutputPath = Join-Path (Split-Path -Parent $script:RepoRoot) ("{0}-notion-sandbox-{1}.zip" -f $repoName, $commit.Substring(0, 12)) }
$outputFull = [System.IO.Path]::GetFullPath($OutputPath)
$rootWithSlash = $script:RepoRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
$repoZipDirectory = [System.IO.Path]::GetFullPath((Join-Path $script:RepoRoot '.zip')).TrimEnd('\', '/')
$outputParentFull = [System.IO.Path]::GetFullPath((Split-Path -Parent $outputFull)).TrimEnd('\', '/')
if ($outputFull.StartsWith($rootWithSlash, [System.StringComparison]::OrdinalIgnoreCase)) {
    $isDirectLocalZip = $outputParentFull.Equals($repoZipDirectory, [System.StringComparison]::OrdinalIgnoreCase) -and
        [System.IO.Path]::GetExtension($outputFull).Equals('.zip', [System.StringComparison]::OrdinalIgnoreCase)
    if (-not $isDirectLocalZip) { Fail 'OutputPath inside the repository must be a direct .zip file under the ignored .zip directory' }
}
if ((Test-Path -LiteralPath $outputFull) -and -not $Force) { Fail "output already exists; pass -Force to replace it: $outputFull" }
$outputParent = Split-Path -Parent $outputFull
New-Item -ItemType Directory -Path $outputParent -Force | Out-Null

$bundle = $null
$bundleManifest = $null
if ($DependencyBundlePath) {
    if (-not (Test-Path -LiteralPath $DependencyBundlePath -PathType Container)) { Fail "DependencyBundlePath must be an existing directory" }
    $bundle = (Resolve-Path -LiteralPath $DependencyBundlePath).Path
    $manifestFile = if ($DependencyManifestPath) { $DependencyManifestPath } else { Join-Path $bundle 'dependency-manifest.json' }
    if (-not (Test-Path -LiteralPath $manifestFile -PathType Leaf)) { Fail "dependency manifest not found: $manifestFile" }
    try { $bundleManifest = Get-Content -LiteralPath $manifestFile -Raw | ConvertFrom-Json } catch { Fail "dependency manifest is not valid JSON: $manifestFile" }
    $platform = [string](Get-ConfigValue $bundleManifest 'platform' '')
    $arch = [string](Get-ConfigValue $bundleManifest 'arch' (Get-ConfigValue $bundleManifest 'architecture' ''))
    $runtime = [string](Get-ConfigValue $bundleManifest 'runtime' '')
    $nodeMajor = Get-ConfigValue $bundleManifest 'nodeMajor' $null
    if (-not $nodeMajor) {
        $nodeVersion = [string](Get-ConfigValue $bundleManifest 'nodeVersion' '')
        if ($nodeVersion -match '^24(?:\.|$)') { $nodeMajor = 24 }
    }
    $glibc = [string](Get-ConfigValue $bundleManifest 'glibc' '')
    $al2023 = [bool](Get-ConfigValue $bundleManifest 'al2023Compatible' $false)
    if ($platform -ne 'linux' -or $arch -ne 'x64') { Fail 'dependency manifest must declare platform=linux and arch=x64' }
    if ($runtime -eq 'node' -and $nodeMajor -ne 24) { Fail 'Node dependency manifest must declare Node 24' }
    if ($runtime -ne 'node' -and $runtime -ne 'python') { Fail 'dependency manifest runtime must be node or python' }
    if ($glibc -notmatch '(?i)glibc|al2023') { Fail 'dependency manifest must declare glibc compatibility' }
    if (-not $al2023 -and $glibc -notmatch '(?i)al2023') { Fail 'dependency manifest must declare AL2023 compatibility' }
}

$tempArchive = Join-Path ([System.IO.Path]::GetTempPath()) ("notion-sandbox-{0}.zip" -f [guid]::NewGuid().ToString('N'))
try {
& git -C $script:RepoRoot archive --format=zip --output=$tempArchive HEAD
    if ($LASTEXITCODE -ne 0) { Fail 'git archive failed' }
    # Validate the source archive before adding generated hand-off metadata.
    # This also rejects a tracked .zip/ directory if it ever bypasses .gitignore.
    Assert-ZipSafe $tempArchive | Out-Null
    $sourceArchiveHash = (Get-FileHash -LiteralPath $tempArchive -Algorithm SHA256).Hash
    if ($bundle) { Add-ZipDirectory -ZipPath $tempArchive -Directory $bundle -Prefix 'dependencies/' }
    $testCommand = [string](Get-ConfigValue $config.verification 'command' 'not specified')
    $baselineStatus = [string](Get-ConfigValue $config.verification 'status' 'not-run')
    $blockingReason = [string](Get-ConfigValue $config.verification 'blockingReason' '')
    $testReady = $null -ne $bundle
    $provenance = [ordered]@{
        schemaVersion = 1
        packageType = 'notion-sandbox'
        repository = $repoName
        repositoryPath = $script:RepoRoot
        branch = $branch
        commit = $commit
        sourceArchiveSha256 = $sourceArchiveHash
        generatedAtUtc = [DateTime]::UtcNow.ToString('o')
        sourceOnly = (-not $testReady)
        testReady = $testReady
        testCommand = $testCommand
        baselineStatus = $baselineStatus
        blockingReason = if ($blockingReason) { $blockingReason } else { $null }
        dependencyManifest = if ($bundleManifest) { $bundleManifest } else { $null }
        network = 'disabled'
        docker = 'unsupported'
        database = 'unsupported'
        patchCommand = [string](Get-ConfigValue $config.packaging 'patchCommand' 'git diff --binary > changes.patch')
        warning = if ($blockingReason) { $blockingReason } elseif ($testReady) { 'Dependency bundle metadata passed; still use only the declared offline Linux environment.' } else { 'Source-only package; install no dependencies in the sandbox. testReady=false.' }
    }
    $generatedDoc = @"
# Notion sandbox hand-off

Repository: $repoName
Branch: $branch
Commit: $commit
Source archive SHA-256: $sourceArchiveHash
Test-ready: $testReady
Verification command: $testCommand
Baseline status: $baselineStatus
$blockingReason

This package is offline. Do not install dependencies, make network calls, use Docker, run database migrations, or start database-backed services.

Create a Git baseline after extraction, make the requested business-logic edits, then run these commands:

    git init
    git add -A
    git commit -m "Notion sandbox baseline"
    git diff --binary > changes.patch

The source-only package intentionally has testReady=false. A dependency-enabled package is test-ready only when the caller supplied an explicitly declared Linux x64 bundle whose manifest passed the exporter checks.
"@
    Add-ZipText -ZipPath $tempArchive -EntryName 'NOTION_SANDBOX/PROVENANCE.json' -Text (($provenance | ConvertTo-Json -Depth 10) + "`n")
    Add-ZipText -ZipPath $tempArchive -EntryName 'NOTION_SANDBOX/README.md' -Text $generatedDoc
    $validation = Assert-ZipSafe $tempArchive
    if ((Test-Path -LiteralPath $outputFull) -and $Force) { Remove-Item -LiteralPath $outputFull -Force }
    Move-Item -LiteralPath $tempArchive -Destination $outputFull
    $finalHash = (Get-FileHash -LiteralPath $outputFull -Algorithm SHA256).Hash
    $size = (Get-Item -LiteralPath $outputFull).Length
    Write-Output ("Created {0} ({1} bytes, {2} entries, SHA-256 {3}, uncompressed {4} bytes, testReady={5})" -f $outputFull, $size, $validation.Entries, $finalHash, $validation.UncompressedBytes, $testReady)
} finally {
    if (Test-Path -LiteralPath $tempArchive) { Remove-Item -LiteralPath $tempArchive -Force -ErrorAction SilentlyContinue }
}
