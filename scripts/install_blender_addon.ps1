<#>
.SYNOPSIS
    Download and install the official Blender Lab MCP addon.

.DESCRIPTION
    Fetches mcp-1.0.3.zip from Blender Lab's official releases and installs it via
    Blender's extension CLI. Optionally enables it in user preferences.

.PARAMETER BlenderExe
    Full path to blender.exe. If omitted, tries to discover from common locations.

.PARAMETER AddonVersion
    The addon version to install (default: 1.0.3).

.PARAMETER ForceReinstall
    If $true, uninstalls any existing 'mcp' extension first.

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install_blender_addon.ps1 -BlenderExe "E:\Blender 5.2\blender.exe"

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File install_blender_addon.ps1 -ForceReinstall
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory=$false)]
    [ValidateScript({Test-Path $_ -PathType Leaf})]
    [string]$BlenderExe,

    [Parameter(Mandatory=$false)]
    [string]$AddonVersion = "1.0.3",

    [Parameter(Mandatory=$false)]
    [switch]$ForceReinstall
)

$ErrorActionPreference = "Stop"

# ── Find Blender ────────────────────────────────────────────────────────────
if (-not $BlenderExe) {
    $candidates = @(
        "E:\Blender 5.2\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 5.1\blender.exe",
        "${env:ProgramFiles}\Blender Foundation\Blender 4.5\blender.exe",
        (Get-Command blender -ErrorAction SilentlyContinue).Source
    )
    foreach ($c in $candidates) {
        if ($c -and (Test-Path $c)) { $BlenderExe = $c; break }
    }
    if (-not $BlenderExe) {
        Write-Error "Blender executable not found. Pass -BlenderExe explicitly."
        exit 1
    }
}
Write-Host "Using Blender: $BlenderExe" -ForegroundColor Cyan

# ── Download addon zip ──────────────────────────────────────────────────────
$url = "https://projects.blender.org/lab/blender_mcp/releases/download/v$AddonVersion/mcp-$AddonVersion.zip"
$zipPath = Join-Path $env:TEMP "mcp-addon-$AddonVersion.zip"
Write-Host "Downloading $url ..." -ForegroundColor Cyan
try {
    Invoke-WebRequest -Uri $url -OutFile $zipPath -UseBasicParsing -ErrorAction Stop
} catch {
    Write-Error "Failed to download addon: $($_.Exception.Message)"
    exit 1
}
Write-Host "Saved to $zipPath" -ForegroundColor Green

# ── Install via Blender extension CLI ──────────────────────────────────────
if ($ForceReinstall) {
    Write-Host "Uninstalling existing 'mcp' extension..." -ForegroundColor Yellow
    & $BlenderExe --command extension remove mcp -r user_default 2>$null
}

Write-Host "Installing extension..." -ForegroundColor Cyan
& $BlenderExe --command extension install-file -r user_default -e $zipPath
if ($LASTEXITCODE -ne 0) {
    Write-Error "Extension install failed (exit $LASTEXITCODE)"
    exit 1
}
Write-Host "Extension installed and enabled." -ForegroundColor Green

# ── Verify ─────────────────────────────────────────────────────────────────
$check = & $BlenderExe -b --python-expr "import addon_utils; print('ENABLED', addon_utils.check('bl_ext.user_default.mcp'))" 2>&1
Write-Host "Verification: $check" -ForegroundColor Cyan

# ── Cleanup ────────────────────────────────────────────────────────────────
Remove-Item $zipPath -Force -ErrorAction SilentlyContinue
Write-Host "Done." -ForegroundColor Green