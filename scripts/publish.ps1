<#>
.SYNOPSIS
    One-click release: build, tag, push, create GitHub Release, optionally publish to PyPI.

.DESCRIPTION
    This script performs a complete release cycle for blender-mcp-plus:
      1. Reads version from pyproject.toml
      2. Cleans and rebuilds dist/ (wheel, sdist, .mcpb)
      3. Creates/updates GitHub repo (if -CreateRepo)
      4. Commits changes, creates tag v<version>, pushes
      5. Creates GitHub Release with all artifacts
      6. Optionally publishes to PyPI via `uv publish`

.REQUIREMENTS
    - gh (GitHub CLI) authenticated: `gh auth login`
    - uv installed
    - UV_PUBLISH_TOKEN env var set for PyPI (or use Trusted Publishing)

.PARAMETER CreateRepo
    If the GitHub repo doesn't exist, create it (requires gh auth).

.PARAMETER PyPI
    Also publish to PyPI after creating the release.

.PARAMETER SkipBuild
    Skip the clean build step (assumes dist/ already contains correct artifacts).

.PARAMETER DryRun
    Print what would be done without executing.

.EXAMPLE
    # Full release (create repo, tag, release, PyPI)
    $env:UV_PUBLISH_TOKEN = "pypi-..."
    powershell -ExecutionPolicy Bypass -File publish.ps1 -CreateRepo -PyPI

.EXAMPLE
    # Just tag and create GitHub Release
    powershell -ExecutionPolicy Bypass -File publish.ps1

.EXAMPLE
    # Dry run to see what would happen
    powershell -ExecutionPolicy Bypass -File publish.ps1 -DryRun
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [switch]$CreateRepo,

    [Parameter(Mandatory=$false)]
    [switch]$PyPI,

    [Parameter(Mandatory=$false)]
    [switch]$SkipBuild,

    [Parameter(Mandatory=$false)]
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# ── Helpers ────────────────────────────────────────────────────────────────
function Write-Log {
    param([string]$Msg, [string]$Color = "White")
    Write-Host "[$(Get-Date -Format 'HH:mm:ss')] $Msg" -ForegroundColor $Color
}

function Invoke-Cmd {
    param([string]$Cmd, [switch]$AllowFail)
    Write-Log ">> $Cmd" "Cyan"
    if ($DryRun) { return @{ExitCode = 0; Output = "(dry run)"} }
    $result = Invoke-Expression $Cmd
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0 -and -not $AllowFail) {
        Write-Log "Command failed (exit $exitCode): $Cmd" "Red"
        exit $exitCode
    }
    return @{ExitCode = $exitCode; Output = $result}
}

# ── Read version from pyproject.toml ──────────────────────────────────────
$root = Split-Path -Parent $MyInvocation.MyCommand.Definition | Split-Path -Parent
$toml = Get-Content "$root\pyproject.toml" -Raw
if ($toml -match 'version\s*=\s*"([^"]+)"') {
    $version = $matches[1]
} else {
    Write-Error "Could not parse version from pyproject.toml"
    exit 1
}
Write-Log "Version: $version" "Green"
$tag = "v$version"

# ── Paths ──────────────────────────────────────────────────────────────────
$distDir = "$root\dist"
$repoUrl = "https://github.com/lusilong/blender-mcp-plus.git"

# ── 1. Build ───────────────────────────────────────────────────────────────
if (-not $SkipBuild) {
    Write-Log "=== Building wheel, sdist, and .mcpb ===" "Green"
    if (-not $DryRun) {
        if (Test-Path $distDir) { Remove-Item $distDir -Recurse -Force }
        Invoke-Cmd "uv build --wheel --sdist"
        Invoke-Cmd "python scripts/build_mcpb.py --output-dir dist"
    }
} else {
    Write-Log "=== Skipping build (--SkipBuild) ===" "Yellow"
}

# ── 2. List artifacts ──────────────────────────────────────────────────────
$artifacts = @()
if (Test-Path $distDir) {
    $artifacts = Get-ChildItem $distDir -File | Where-Object { $_.Extension -in '.whl','.tar.gz','.mcpb' }
    Write-Log "Artifacts:" "Green"
    foreach ($a in $artifacts) { Write-Log "  $($a.Name) ($([math]::Round($a.Length/1KB,1)) KB)" }
}
if ($artifacts.Count -eq 0) {
    Write-Error "No artifacts found in $distDir"
    exit 1
}

# ── 3. Git operations ──────────────────────────────────────────────────────
Write-Log "=== Git operations ===" "Green"

# Check if we're in a git repo
$inRepo = (Invoke-Cmd "git rev-parse --is-inside-work-tree" -AllowFail).ExitCode -eq 0

if (-not $inRepo) {
    Write-Log "Initializing git repository..." "Yellow"
    Invoke-Cmd "git init"
    Invoke-Cmd "git remote add origin $repoUrl" -AllowFail
    Invoke-Cmd "git checkout -b main" -AllowFail
}

# Check for uncommitted changes
$status = Invoke-Cmd "git status --porcelain"
if ($status.Output -and -not $DryRun) {
    Write-Log "Committing changes..." "Yellow"
    Invoke-Cmd "git add -A"
    Invoke-Cmd "git commit -m 'Release $version'"
} elseif (-not $DryRun) {
    Write-Log "No changes to commit" "Yellow"
}

# Tag
$existingTag = (Invoke-Cmd "git tag -l '$tag'" -AllowFail).Output.Trim()
if ($existingTag) {
    Write-Log "Tag $tag already exists locally" "Yellow"
    $tagExistsRemote = (Invoke-Cmd "git ls-remote --tags origin '$tag'" -AllowFail).Output.Trim()
    if ($tagExistsRemote) {
        Write-Log "Tag $tag also exists on remote" "Yellow"
    }
} else {
    Write-Log "Creating tag $tag..." "Yellow"
    Invoke-Cmd "git tag -a $tag -m 'Release $version'"
}

# Push
Write-Log "Pushing to origin..." "Yellow"
Invoke-Cmd "git push origin main"
Invoke-Cmd "git push origin $tag"

# ── 4. GitHub Repo (create if needed) ──────────────────────────────────────
if ($CreateRepo) {
    Write-Log "=== Ensuring GitHub repo exists ===" "Green"
    $repoInfo = Invoke-Cmd "gh repo view lusilong/blender-mcp-plus --json name,url" -AllowFail
    if ($repoInfo.ExitCode -ne 0) {
        Write-Log "Creating GitHub repository..." "Yellow"
        Invoke-Cmd "gh repo create lusilong/blender-mcp-plus --public --description 'MCP server for Blender: official Blender Lab tools + Poly Haven asset library' --source=. --remote=origin --push"
    } else {
        Write-Log "Repo already exists: $($repoInfo.Output | ConvertFrom-Json).url" "Green"
    }
}

# ── 5. GitHub Release ──────────────────────────────────────────────────────
Write-Log "=== Creating GitHub Release ===" "Green"

$releaseNotes = @"
## Blender MCP Plus $version

MCP server for Blender: official Blender Lab tools + Poly Haven asset library.

### Assets
| File | Description |
|------|-------------|
"@

foreach ($a in $artifacts) {
    $releaseNotes += "| `$($a.Name)` | $([math]::Round($a.Length/1KB,1)) KB |`n"
}

$releaseNotes += @"

### Installation

```powershell
# Via uvx (recommended)
uvx blender-mcp-plus@$version

# Or direct from GitHub
uvx --from git+https://github.com/lusilong/blender-mcp-plus@$version blender-mcp-plus
```

### Prerequisites

- Blender 5.1+ with the official **MCP** add-on installed (see [installation guide](https://github.com/lusilong/blender-mcp-plus#installation))
- Blender running and listening on `localhost:9876`
- MCP client configured to use `uvx blender-mcp-plus@$version`

### Changelog

See [CHANGELOG.md](https://github.com/lusilong/blender-mcp-plus/blob/main/CHANGELOG.md).
"@

$notesFile = "$env:TEMP\release_notes_$version.md"
if (-not $DryRun) {
    Set-Content -Path $notesFile -Value $releaseNotes -Encoding UTF8
    Invoke-Cmd "gh release create $tag --title 'Blender MCP Plus $version' --notes-file '$notesFile' $($artifacts.Name | ForEach-Object { "$distDir\$_" })"
} else {
    Write-Log "Would create release $tag with $($artifacts.Count) artifacts" "Cyan"
    Write-Log "Artifacts: $($artifacts.Name -join ', ')"
}

# ── 6. PyPI ────────────────────────────────────────────────────────────────
if ($PyPI) {
    Write-Log "=== Publishing to PyPI ===" "Green"
    if (-not $env:UV_PUBLISH_TOKEN) {
        Write-Error "UV_PUBLISH_TOKEN environment variable not set. Set it to your PyPI token."
        exit 1
    }
    if (-not $DryRun) {
        Invoke-Cmd "uv publish --token $env:UV_PUBLISH_TOKEN $distDir\*"
    } else {
        Write-Log "Would run: uv publish $distDir\*" "Cyan"
    }
}

Write-Log "=== Release $version complete ===" "Green"