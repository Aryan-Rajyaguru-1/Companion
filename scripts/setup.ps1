# ============================================================================
# Companion one-shot setup (Windows)
#
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
#
#   1. Builds the CLI from source if Go >= 1.18 is available, otherwise
#      downloads the matching prebuilt binary from the v0.1.0-alpha release
#   2. Installs it into <IDE>\bin\companion.exe - a location the IDE
#      auto-detects (no PATH changes needed)
#   3. Runs `companion config init` and downloads the board package index
#   4. Installs IDE dependencies with npm
#
# Safe to re-run; it only overwrites the CLI binary and node_modules.
# ============================================================================
#Requires -Version 5.1
$ErrorActionPreference = 'Stop'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Say($m) { Write-Host "==> $m" }
function Ok($m)  { Write-Host " ok  $m" -ForegroundColor Green }
function Warn($m){ Write-Host " !!  $m" -ForegroundColor Yellow }

$Root = Split-Path -Parent $PSScriptRoot

# Layout detection: full workspace vs IDE-only vs CLI-only checkout
$IdeDir = if (Test-Path "$Root\companion-ide") { "$Root\companion-ide" } else { $Root }
$CliDir = "$Root\companion-cli"
if (-not (Test-Path $CliDir) -and (Test-Path "$Root\go.mod")) { $CliDir = $Root }
$BinDir = "$IdeDir\bin"
New-Item -ItemType Directory -Force -Path $BinDir | Out-Null
$Bin    = "$BinDir\companion.exe"

# ── 1. CLI binary (build or download) ────────────────────────────────────────
$Arch = if ($env:PROCESSOR_ARCHITECTURE -match 'ARM64') { 'arm64' } else { 'amd64' }
$Built = $false
if ((Test-Path $CliDir) -and (Get-Command go -ErrorAction SilentlyContinue)) {
    Say "Building CLI from source ($(go version))"
    Push-Location $CliDir
    try {
        $env:GOOS = 'windows'; $env:GOARCH = $Arch
        go build -trimpath -ldflags "-s -w" -o $Bin .
        if ($LASTEXITCODE -eq 0) { $Built = $true; Ok "CLI built -> $Bin" }
        else                     { Warn "go build failed; falling back to the prebuilt release download" }
    } finally { Pop-Location }
}
if (-not $Built) {
    $Url = "https://github.com/Aryan-Rajyaguru-1/Companion/releases/download/v0.1.0-alpha/companion-windows-$Arch.exe"
    Say "Downloading prebuilt CLI: $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Bin -UseBasicParsing
    Ok "CLI installed -> $Bin"
}

# ── 2. First-run CLI configuration ───────────────────────────────────────────
Say "Initializing CLI configuration"
& $Bin config init
if ($LASTEXITCODE -eq 0) { Ok "config ready (~\.companion-cli\config.yaml)" }
else { Warn "config init failed (run '$Bin config init' manually)" }

Say "Downloading board package index (one-time, may take a moment)"
& $Bin board update-index
if ($LASTEXITCODE -eq 0) { Ok "board index cached" }
else { Warn "board index download failed (run '$Bin board update-index' later)" }

# ── 3. IDE dependencies (skipped when no IDE checkout is present) ────────────
$HasIde = Test-Path "$IdeDir\package.json"
if ($HasIde) {
    if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
        throw "Node.js 18+ is required for the IDE -> https://nodejs.org  (then re-run this script)"
    }
    Say "Installing IDE dependencies (npm)"
    Push-Location $IdeDir
    try { npm install --no-audit --no-fund --loglevel=error } finally { Pop-Location }
    if ($LASTEXITCODE -ne 0) { throw "npm install failed - check your network and re-run" }
    Ok "IDE dependencies installed"
} else {
    Ok "No IDE checkout found - CLI-only setup complete"
}

# ── Done ─────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Companion is ready." -ForegroundColor Green
Write-Host "Next steps:"
if ($HasIde) {
    Write-Host "  1. Flash the bridge firmware to your ESP32:"
    Write-Host "       $IdeDir\esp32-bridge-firmware\esp32_bridge"
    Write-Host "  2. Start the IDE:"
    Write-Host "       cd $IdeDir; npm run dev"
    Write-Host "  3. Connect to the bridge WiFi (SSID: ESP32-OTA, password: flashme!)"
    Write-Host "     and hit Upload. Edit WiFi credentials in"
    Write-Host "       $IdeDir\esp32-bridge-firmware\esp32_bridge\config.local.h"
} else {
    Write-Host "  The IDE (Electron app) was not found next to this script."
    Write-Host "  Clone the full workspace or the 'ide' branch, then re-run."
    Write-Host "  Meanwhile the CLI works standalone - try:"
    Write-Host "       $Bin compile --help"
    Write-Host "       $Bin upload --help"
    Write-Host "       $Bin ota --help"
}
Write-Host ""
Write-Host "CLI binary: $Bin  (auto-detected by the IDE - nothing to add to PATH)"
