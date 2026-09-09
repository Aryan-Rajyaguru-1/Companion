# Companion Workspace

Complete wireless Arduino programming environment — MIT-licensed.

```
companion-workspace/
├── companion-cli/     ← Original Go CLI  (MIT)
└── companion-ide/     ← Electron + React IDE  (MIT)
```

## Quick Setup

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
