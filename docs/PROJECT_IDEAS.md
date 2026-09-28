# Project ideas / internal backlog

Maintainer planning notes — intentionally **not** GitHub issues. The issue
tracker is reserved for real reports from testers and users.

- [x] cli: `companion version` subcommand (CLI version, Go version, commit via `debug.ReadBuildInfo`) — needed by the bug report template (DONE: `companion version` prints version/Go/OS-arch; release builds now stamp the tag via ldflags)
- [x] docs: wiring diagram for ESP32 bridge → Uno (bridge TX/RX ↔ target RX/TX, common GND); embed in README (DONE: ASCII diagram + level-shifter note in README "Bridge → target wiring")
- [x] cli: friendlier error when bridge unreachable (DONE: `bridge.Client.Connect` now suggests `companion fleet discover`, the AP-mode address, and the Windows Firewall port)
- [ ] ide: show detected CLI version in Preferences / CLI Setup wizard — `electron/companion-cli.js`
- [ ] docs: translate README quick-start to more languages (`docs/README.<lang>.md`, linked from main README)
- [x] deploy: `install-relay-hub.ps1` / PowerShell parity for the Linux-only hub helpers (DONE: `-RunNow` / `-InstallStartupTask` (logon task = the systemd equivalent, user-scope env) / `-Uninstall`, .NET-RNG token generation so openssl isn't needed, `/health` verify)
- [x] ota: one local|remote transport choice across category 2 and 3 (DONE: `pipe_req` + `companion relay bridge` expose a remote *bridge* as a local TCP socket, so esptool/avrdude/`companion upload` work unchanged; `upload --ota-mode remote` drives it one-shot; the bridge firmware dials out via `RELAY_MODE_REMOTE`; the dial/hello/heartbeat/reconnect block lives once in `shared/relay_link.h`, included by both sketches)
