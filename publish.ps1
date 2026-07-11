[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidatePattern('^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$')]
    [string]$Tag
)

$ErrorActionPreference = "Stop"
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Assert-LastExitCode {
    param([string]$Action)

    if ($LASTEXITCODE -ne 0) {
        throw "$Action failed (exit code $LASTEXITCODE)."
    }
}

function Assert-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Required command '$Name' was not found in PATH."
    }
}

Push-Location $ProjectDir
try {
    Assert-Command "git"
    Assert-Command "gh"

    git rev-parse --is-inside-work-tree *> $null
    Assert-LastExitCode "Git repository check"

    if (-not $Tag) {
        $tagsAtHead = @(git tag --points-at HEAD --list "v*")
        Assert-LastExitCode "Reading tags at HEAD"

        if ($tagsAtHead.Count -eq 0) {
            throw "No v* tag points at HEAD. Create one first, for example: git tag -a v1.0.0 -m 'Release v1.0.0'"
        }
        if ($tagsAtHead.Count -gt 1) {
            throw "Multiple v* tags point at HEAD: $($tagsAtHead -join ', '). Pass the intended tag explicitly: .\publish.ps1 v1.0.0"
        }

        $Tag = $tagsAtHead[0]
    }

    if ($Tag -notmatch '^v\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$') {
        throw "Tag '$Tag' is not a supported semantic version such as v1.0.0 or v1.0.0-beta.1."
    }

    git rev-parse --verify "refs/tags/$Tag" *> $null
    Assert-LastExitCode "Checking local tag '$Tag'"

    $headCommit = (git rev-parse HEAD).Trim()
    Assert-LastExitCode "Reading HEAD"
    $tagCommit = (git rev-list -n 1 $Tag).Trim()
    Assert-LastExitCode "Reading tag '$Tag'"
    if ($headCommit -ne $tagCommit) {
        throw "Tag '$Tag' does not point at HEAD. Check out the tagged commit or create the tag on the current commit."
    }

    $workingTreeChanges = git status --porcelain
    Assert-LastExitCode "Checking working tree"
    if ($workingTreeChanges) {
        throw "The working tree has uncommitted changes. Commit or stash them before publishing."
    }

    gh auth status
    Assert-LastExitCode "GitHub CLI authentication check"

    # A missing release is expected here. Temporarily prevent PowerShell from
    # promoting gh's stderr/exit code to a terminating NativeCommandError.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "SilentlyContinue"
    try {
        gh release view $Tag *> $null
        $releaseViewExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    if ($releaseViewExitCode -eq 0) {
        throw "GitHub Release '$Tag' already exists."
    }

    Write-Host "Building $Tag..."
    & "$ProjectDir\build.ps1"

    $exePath = Join-Path $ProjectDir "dist\GBFRTextureFixer.exe"
    if (-not (Test-Path -LiteralPath $exePath -PathType Leaf)) {
        throw "Build output was not found: $exePath"
    }

    $archivePath = Join-Path $ProjectDir "dist\GBFRTextureFixer-$Tag-win-x64.zip"
    $archiveFiles = @(
        $exePath,
        (Join-Path $ProjectDir "README.md"),
        (Join-Path $ProjectDir "README_zh-CN.md"),
        (Join-Path $ProjectDir "LICENSE")
    )

    Write-Host "Creating $archivePath..."
    Compress-Archive -LiteralPath $archiveFiles -DestinationPath $archivePath -CompressionLevel Optimal -Force

    $branch = (git branch --show-current).Trim()
    Assert-LastExitCode "Reading current branch"
    if (-not $branch) {
        throw "HEAD is detached. Check out the release branch before publishing."
    }

    Write-Host "Pushing branch '$branch' and tag '$Tag'..."
    git push origin $branch
    Assert-LastExitCode "Pushing branch '$branch'"
    git push origin "refs/tags/$Tag"
    Assert-LastExitCode "Pushing tag '$Tag'"

    Write-Host "Creating GitHub Release '$Tag'..."
    gh release create $Tag $archivePath --verify-tag --generate-notes --title "GBFRTextureFixer $Tag"
    Assert-LastExitCode "Creating GitHub Release '$Tag'"

    Write-Host ""
    Write-Host "Published successfully: $archivePath" -ForegroundColor Green
}
finally {
    Pop-Location
}
