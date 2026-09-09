param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationRoot,

    [switch]$IncludeLocalResults
)

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$backupDir = Join-Path $DestinationRoot "Bondik-TV-Ultimate-$timestamp"

New-Item -ItemType Directory -Path $backupDir -Force | Out-Null

$insideRepo = git -C $repoRoot rev-parse --is-inside-work-tree
if ($insideRepo -ne "true") {
    throw "Bondik TV repository was not detected at $repoRoot"
}

$bundlePath = Join-Path $backupDir "Bondik-TV-Ultimate.bundle"
git -C $repoRoot bundle create $bundlePath --all

$head = git -C $repoRoot rev-parse HEAD
$branch = git -C $repoRoot branch --show-current
$status = git -C $repoRoot status --short
$remotes = git -C $repoRoot remote -v

$manifest = @(
    "Bondik TV Ultimate recovery backup"
    "Created: $(Get-Date -Format o)"
    "Repository: $repoRoot"
    "Branch: $branch"
    "HEAD: $head"
    ""
    "Remotes:"
    $remotes
    ""
    "Working tree:"
    $(if ($status) { $status } else { "clean" })
)

$manifest | Set-Content -Path (Join-Path $backupDir "manifest.txt") -Encoding UTF8

if ($IncludeLocalResults) {
    $resultsPath = Join-Path $repoRoot "hunt-results"
    if (Test-Path $resultsPath) {
        Copy-Item -Path $resultsPath -Destination (Join-Path $backupDir "hunt-results") -Recurse -Force
    }
}

Get-FileHash -Path $bundlePath -Algorithm SHA256 |
    Format-List |
    Out-String |
    Set-Content -Path (Join-Path $backupDir "Bondik-TV-Ultimate.bundle.sha256.txt") -Encoding UTF8

Write-Host ""
Write-Host "Bondik TV recovery backup created:"
Write-Host $backupDir
Write-Host ""
Write-Host "Keep this copy on storage independent of Black Tower."
