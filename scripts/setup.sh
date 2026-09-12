#!/usr/bin/env bash
# ============================================================================
# Companion one-shot setup (macOS / Linux)
#
#   bash scripts/setup.sh
#
# Does everything the manual quick-start does:
#   1. Builds the CLI from source if Go >= 1.18 is available, otherwise
#      downloads the matching prebuilt binary from the v0.1.0-alpha release
#   2. Installs it into <IDE>/bin/companion — a location the IDE
#      auto-detects (no PATH changes needed)
#   3. Runs `companion config init` and downloads the board package index
#   4. Installs IDE dependencies with npm
#
# Safe to re-run; it only overwrites the CLI binary and node_modules.
# ============================================================================
set -euo pipefail

BOLD=$'\033[1m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; OFF=$'\033[0m'
say()  { printf '%s\n' "${BOLD}==>${OFF} $*"; }
ok()   { printf '%s\n' "${GREEN} ok${OFF}  $*"; }
warn() { printf '%s\n' "${YELLOW} !!${OFF}  $*"; }
die()  { printf '%s\n' "${RED} xx${OFF}  $*" >&2; exit 1; }
have() { command -v "$1" >/dev/null 2>&1; }

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── OS / arch detection ──────────────────────────────────────────────────────
case "$(uname -s | tr '[:upper:]' '[:lower:]')" in
  linux*)  GOOS=linux ;;
  darwin*) GOOS=darwin ;;
  *) die "Unsupported OS. On Windows use: powershell -ExecutionPolicy Bypass -File scripts\\setup.ps1" ;;
esac
case "$(uname -m)" in
  x86_64|amd64)  GOARCH=amd64 ;;
  aarch64|arm64) GOARCH=arm64 ;;
  *) die "Unsupported architecture: $(uname -m)" ;;
esac

# ── Layout detection: full workspace vs IDE-only vs CLI-only checkout ───────
if [ -d "$ROOT/companion-ide" ]; then IDE_DIR="$ROOT/companion-ide"; else IDE_DIR="$ROOT"; fi
CLI_DIR="$ROOT/companion-cli"; [ -d "$CLI_DIR" ] || CLI_DIR=""
# CLI-at-root checkouts (e.g. the 'cli' branch / Companion_cli repo)
if [ -z "$CLI_DIR" ] && [ -f "$ROOT/go.mod" ]; then CLI_DIR="$ROOT"; fi
BIN="$IDE_DIR/bin/companion"
mkdir -p "$IDE_DIR/bin"

# ── 1. CLI binary (build or download) ────────────────────────────────────────
BUILT=0
if [ -n "$CLI_DIR" ] && have go; then
  say "Building CLI from source ($(go version | awk '{print $3}'))"
  if (cd "$CLI_DIR" && GOOS="$GOOS" GOARCH="$GOARCH" go build -trimpath -ldflags "-s -w" -o "$BIN" .); then
    BUILT=1; ok "CLI built -> $BIN"
  else
    warn "go build failed; falling back to the prebuilt release download"
  fi
fi
if [ "$BUILT" -eq 0 ]; then
  REL="https://github.com/Aryan-Rajyaguru-1/Companion/releases/download/v0.1.0-alpha/companion-${GOOS}-${GOARCH}"
  have curl || die "curl is required to download the CLI (or install Go 1.18+ and re-run)"
  say "Downloading prebuilt CLI: $REL"
  curl -fsSL --retry 2 -o "$BIN" "$REL" || die "Download failed. Install Go 1.18+ and re-run, or build manually: cd companion-cli && go build -o companion ."
  chmod +x "$BIN"
  ok "CLI installed -> $BIN"
fi

# ── 2. First-run CLI configuration ───────────────────────────────────────────
say "Initializing CLI configuration"
"$BIN" config init >/dev/null && ok "config ready (~/.companion-cli/config.yaml)" || warn "config init failed (run '$BIN config init' manually)"
say "Downloading board package index (one-time, may take a moment)"
"$BIN" board update-index >/dev/null 2>&1 && ok "board index cached" || warn "board index download failed (run '$BIN board update-index' later)"
# Pre-install the default AVR platform so a fresh clone compiles the Uno
# example immediately (first-run wall reported by testers).
if "$BIN" board list 2>/dev/null | grep -q "arduino:avr"; then
  ok "arduino:avr platform already installed"
else
  say "Installing default platform arduino:avr (one-time download)"
  "$BIN" board install arduino:avr >/dev/null 2>&1 && ok "arduino:avr installed" || warn "arduino:avr install failed (run '$BIN board install arduino:avr' later)"
fi

# ── 3. IDE dependencies (skipped when no IDE checkout is present) ────────────
if [ -f "$IDE_DIR/package.json" ]; then
  have node || die "Node.js 18+ is required for the IDE -> https://nodejs.org  (then re-run this script)"
  NODE_MAJOR="$(node -p 'process.versions.node' | cut -d. -f1)"
  [ "$NODE_MAJOR" -ge 18 ] || warn "Node $(node -v) is older than 18; the IDE may misbehave"
  say "Installing IDE dependencies (npm)"
  (cd "$IDE_DIR" && npm install --no-audit --no-fund --loglevel=error) || die "npm install failed — check your network and re-run"
  ok "IDE dependencies installed"
  NEXT_STEPS="1. Flash the bridge firmware to your ESP32:
       $IDE_DIR/esp32-bridge-firmware/esp32_bridge
  2. Start the IDE:
       cd $IDE_DIR && npm run dev
  3. Connect to the bridge WiFi (SSID: ESP32-OTA, password: flashme!)
     and hit Upload. Edit WiFi credentials in
       $IDE_DIR/esp32-bridge-firmware/esp32_bridge/config.local.h"
else
  ok "No IDE checkout found — CLI-only setup complete"
  NEXT_STEPS="The IDE (Electron app) was not found next to this script.
  Clone the full workspace or the 'ide' branch, then re-run this script.
  Meanwhile the CLI works standalone — try:
       $BIN compile --help
       $BIN upload --help
       $BIN ota --help"
fi

# ── Done ─────────────────────────────────────────────────────────────────────
cat <<EOF

${GREEN}Companion is ready.${OFF}
Next steps:
  $NEXT_STEPS

CLI binary: $BIN  (auto-detected by the IDE — nothing to add to PATH)
EOF
