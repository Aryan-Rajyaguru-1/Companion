# Project ideas / internal backlog

Maintainer planning notes — intentionally **not** GitHub issues. The issue
tracker is reserved for real reports from testers and users.

- [x] cli: `companion version` subcommand (CLI version, Go version, commit via `debug.ReadBuildInfo`) — needed by the bug report template (DONE: `companion version` prints version/Go/OS-arch; release builds now stamp the tag via ldflags)
- [x] docs: wiring diagram for ESP32 bridge → Uno (bridge TX/RX ↔ target RX/TX, common GND); embed in README (DONE: ASCII diagram + level-shifter note in README "Bridge → target wiring")
- [x] cli: friendlier error when bridge unreachable (DONE: `bridge.Client.Connect` now suggests `companion fleet discover`, the AP-mode address, and the Windows Firewall port)
- [ ] ide: show detected CLI version in Preferences / CLI Setup wizard — `electron/companion-cli.js`
- [ ] docs: translate README quick-start to more languages (`docs/README.<lang>.md`, linked from main README)
- [ ] deploy: `install-relay-hub.ps1` / PowerShell parity for the Linux-only hub helpers (Windows testers cannot run systemd scripts)
