# 🛰️ Companion

**Upload & program Arduino/ESP32 boards over WiFi — no USB cable, no cloud, no accounts.**

![Release](https://img.shields.io/github/v/release/Aryan-Rajyaguru-1/Companion?include_prereleases&label=release)
![License](https://img.shields.io/github/license/Aryan-Rajyaguru-1/Companion)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)
![Stars](https://img.shields.io/github/stars/Aryan-Rajyaguru-1/Companion?style=social)

**Companion** pairs a from-scratch **Go CLI** with an **Electron IDE** that compile Arduino sketches locally and flash them *over the air* through a $5 ESP32 bridge — with serial monitor, serial plotter, and live GCC error squiggles in the editor.

## ✨ Why Companion?

- 📡 **Truly wireless upload** — flash Uno/Mega/Nano/ESP32 through an ESP32 bridge on your WiFi; leave the USB cable in the drawer
- 🔒 **100% local toolchain** — compiles on your machine, no cloud accounts, no telemetry
- ⚡ **Content-addressed build cache** — warm builds finish in seconds, not minutes
- 🖥️ **CLI-first + full IDE** — scriptable `companion` binary *and* a GUI with tabs, plotter, error markers
- ⚖️ **MIT-licensed** — no GPL obligations anywhere in the tree

## 📥 Download prebuilt binaries

Grab the release for your OS — CLI binaries for Windows/Linux/macOS, plus a Linux `.deb` and `.AppImage` for the IDE:

**→ [Latest release (v0.1.0-alpha)](https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest)**

Then run the one-command setup below — it builds the CLI from source if you have Go, or fetches the right prebuilt binary automatically.

## ⚡ One-command setup

```bash
bash scripts/setup.sh          # macOS / Linux
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # Windows
```

## Manual setup

```bash
# 1. Build CLI
cd companion-cli && go mod tidy && go build -o companion .

# 2. Init
./companion config init && ./companion board update-index

# 3. Flash esp32_bridge.ino to your ESP32 WROOM

# 4. Run IDE
cd ../companion-ide && npm install && npm run dev

# 5. Connect to WiFi SSID=ESP32-OTA Password=flashme!, then Upload
```

## New in this version
- Multi-file tabs (open multiple .ino/.cpp/.h files)
- Explorer sidebar with recent files (Ctrl+B)
- GCC error markers — red squiggles in editor + auto jump to error
- Serial Plotter — real-time canvas graph (Ctrl+Shift+L)
- Upload progress overlay with stage indicators
- Format document (Ctrl+Shift+F), Find & Replace (Ctrl+H)
- Compile result badges on toolbar (✓ / ✗N errors / ⚠N warnings)
- CLI Setup wizard on first run if binary not found

## License: MIT — no GPL, no AGPL, fully yours.
