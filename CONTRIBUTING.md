# Contributing to Companion

Thanks for helping! Companion is young, so every contribution counts.

## Project layout
```
companion-cli/   Go toolchain (compile, cache, OTA upload, board registry)
companion-ide/   Electron + React IDE
esp32_bridge/    ESP32 bridge firmware (Arduino)
```

## Dev setup
```bash
bash scripts/setup.sh          # or scripts\setup.ps1 on Windows
cd companion-cli && go test ./...
cd ../companion-ide && npm test
```

## Ground rules
- **MIT only** — no GPL/AGPL dependencies anywhere in the tree
- Go code follows `gofmt` + `go vet` clean; JS follows existing prettier style
- Never commit credentials, tokens, or `config.local.h` with real WiFi values
- One feature/fix per PR, with a short "how was it tested" note

## Good first issues
Issues labeled `good first issue` are scoped for newcomers. Claim one by
commenting, and ask questions in the issue or Discussions — happy to help.

## Reporting bugs
Use the bug template and include `companion version`, OS, and board.
Wireless-upload problems: also note your bridge firmware version and WiFi band (2.4/5 GHz).
