[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DestinationPath,

    [string]$RemoteUrl = "https://github.com/MustafaHameed/NSCT_HEC.git",

    [string]$InitialCommitMessage = "Initial standalone NSCT_HEC repository",

    [switch]$SetRemote,

    [switch]$Push,

    [switch]$Force
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

function Write-Step {
    param([string]$Message)
    Write-Host "[NSCT_HEC Export] $Message" -ForegroundColor Cyan
}

function Get-StandaloneSourceRoot {
    $scriptRoot = Split-Path -Parent $PSCommandPath
    return (Resolve-Path (Join-Path $scriptRoot '..')).Path
}

function Remove-PathIfExists {
    param([string]$PathToRemove)
    if (Test-Path $PathToRemove) {
        Remove-Item -Recurse -Force $PathToRemove
    }
}

function Test-GitAvailable {
    $gitCommand = Get-Command git -ErrorAction SilentlyContinue
    if (-not $gitCommand) {
        throw 'Git is not installed or not available on PATH.'
    }
}

function Invoke-Git {
    param(
        [string]$WorkingDirectory,
        [string[]]$Arguments
    )

    Push-Location $WorkingDirectory
    try {
        & git @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "Git command failed: git $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

$sourceRoot = Get-StandaloneSourceRoot
$destinationResolved = [System.IO.Path]::GetFullPath($DestinationPath)

if ($sourceRoot -eq $destinationResolved) {
    throw 'DestinationPath must be different from the current NSCT_HEC source folder.'
}

if ((Test-Path $destinationResolved) -and -not $Force) {
    throw "Destination already exists: $destinationResolved. Use -Force to overwrite it."
}

Test-GitAvailable

Write-Step "Preparing export from $sourceRoot"
if (Test-Path $destinationResolved) {
    Write-Step "Removing existing destination because -Force was provided"
    Remove-PathIfExists -PathToRemove $destinationResolved
}

Write-Step "Copying standalone repository files"
Copy-Item -Path $sourceRoot -Destination $destinationResolved -Recurse -Force

Write-Step "Cleaning local-only artifacts"
$cleanupTargets = @(
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.ruff_cache',
    '.git'
)
foreach ($target in $cleanupTargets) {
    Get-ChildItem -Path $destinationResolved -Recurse -Force -Directory -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -eq $target } |
        ForEach-Object { Remove-Item -Recurse -Force $_.FullName }
}
Get-ChildItem -Path $destinationResolved -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { $_.Extension -eq '.pyc' } |
    ForEach-Object { Remove-Item -Force $_.FullName }

Write-Step 'Initializing git repository'
Invoke-Git -WorkingDirectory $destinationResolved -Arguments @('init')
Invoke-Git -WorkingDirectory $destinationResolved -Arguments @('add', '.')
Invoke-Git -WorkingDirectory $destinationResolved -Arguments @('commit', '-m', $InitialCommitMessage)
Invoke-Git -WorkingDirectory $destinationResolved -Arguments @('branch', '-M', 'main')

if ($SetRemote -or $Push) {
    Write-Step "Configuring remote origin -> $RemoteUrl"
    & git -C $destinationResolved remote remove origin 2>$null
    & git -C $destinationResolved remote add origin $RemoteUrl
    if ($LASTEXITCODE -ne 0) {
        throw 'Failed to configure git remote origin.'
    }
}

if ($Push) {
    Write-Step 'Pushing repository to remote origin/main'
    Invoke-Git -WorkingDirectory $destinationResolved -Arguments @('push', '-u', 'origin', 'main')
}

Write-Step "Standalone repository exported successfully to: $destinationResolved"
Write-Host ''
Write-Host 'Next commands:' -ForegroundColor Green
Write-Host ('  cd "{0}"' -f $destinationResolved)
if (-not ($SetRemote -or $Push)) {
    Write-Host ('  git remote add origin "{0}"' -f $RemoteUrl)
    Write-Host '  git push -u origin main'
}
elseif (-not $Push) {
    Write-Host '  git push -u origin main'
}
