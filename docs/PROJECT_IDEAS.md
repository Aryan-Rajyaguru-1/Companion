# Project ideas / internal backlog

Maintainer planning notes — intentionally **not** GitHub issues. The issue
tracker is reserved for real reports from testers and users.

- [ ] docs: wiring diagram for ESP32 bridge → Uno (bridge TX/RX ↔ target RX/TX, common GND); embed in README
- [ ] cli: friendlier error when bridge unreachable on port 3333 (suggest `companion ota discover`, check WiFi, check bridge firmware) — `internal/ota/ota.go`
- [ ] ide: show detected CLI version in Preferences / CLI Setup wizard — `electron/companion-cli.js`
- [ ] cli: `companion version` subcommand (CLI version, Go version, commit via `debug.ReadBuildInfo`) — needed by the bug report template
- [ ] docs: translate README quick-start to more languages (`docs/README.<lang>.md`, linked from main README)
