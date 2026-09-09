# Companion vs Arduino — Architecture & User-Facing Gap Report

> Grounded in: first-party architecture docs (`docs/development.md`) and source
> checkouts in `Arduino for refs/`, plus live top-voted GitHub issues from
> `arduino/arduino-ide` (596 open) and `arduino/arduino-cli` (220 open).

---

## 1. Architectural Difference: Arduino CLI vs Arduino IDE

The key thing to understand is that **Arduino splits the "compiler backend" and the
"user-facing app" into two separate projects with a hard machine boundary between
them**, and Companion collapses both into one repo with no such boundary.

### Arduino CLI (`arduino-cli`) — the backend engine

- **Language/internals**: Go, compiled to a single static binary.
- **Interface**: a **gRPC service API**, defined in Protocol Buffers
  (`rpc/cc/arduino/cli/commands/v1/*.proto` — `compile.proto`, `upload.proto`,
  `board.proto`, `lib.proto`, `monitor.proto`, `debug.proto`, `settings.proto`, …).
- **Every CLI command is a thin cobra wrapper over a gRPC service method**:
  `commands/service_board_*.go`, `service_compile.go`, `service_library_*.go`,
  `service_upload.go`, `service_monitor.go`, etc.
- **Streaming by design**: long operations (`Compile`, `Upload`, `Monitor`) are
  *bidirectional/server-streaming* gRPC calls, so progress and cancellation are
  first-class (`utility_grpc_streaming.go`).
- **Persistent build cache**: `internal/buildcache` — incremental, content-keyed,
  survives across processes.
- **Pluggable discovery/monitor/programmer** subprocesses (stdio protocol).
- **Instance/profile model**: `commands/instances.go` + `service_profile_*.go` —
  multiple isolated board/env configurations coexist.
- **i18n built in**: `internal/i18n`, `internal/locales`.

**Arduino CLI is deliberately headless** — it has no GUI, no editor. Its entire
surface is the gRPC API + the CLI.

### Arduino IDE 2.x (`arduino-ide`) — the app

Confirmed from `docs/development.md` (verbatim) it is **strictly three tiers**:

1. **Electron main** — app lifecycle, window management. Spawns the backend.
2. **Backend (Node.js/Theia)** — filesystem access, terminal, Git, **communicates
   with arduino-cli via gRPC**, hosts an HTTP server, runs VS Code extensions.
   Spawns subprocesses (filesystem watcher, Git, language server).
3. **Frontend (renderer)** — talks to the backend over **JSON-RPC over WebSocket**;
   all frontend "services" are thin proxies to backend implementations.

Plus two out-of-repo components pulled in at build time:
- `vscode-arduino-tools` (Language Server Protocol + debugger adapter)
- `arduino-language-server` (parses Arduino `.ino` → LSP diagnostics)

Communication chain, end to end:

```
React/UI  ⇄(JSON-RPC/WS)⇄  Theia backend  ⇄(gRPC)⇄  arduino-cli (Go)  → GCC/avr-gcc
```

The IDE is a **version-pinned gRPC client** of the CLI; mismatched IDE/CLI
versions are unsupported (documented).

### Companion — where it diverges

| Layer | Arduino | Companion |
|---|---|---|
| Backend engine | Separate Go binary, gRPC API, protobuf-typed | Go CLI in-repo, cobra + custom JSON-RPC/HTTP daemon (`cmd/daemon.go`, `openapi.yaml`) |
| IDE↔backend transport | gRPC (typed stream) | subprocess spawn + HTTP daemon (`daemon-manager.js`) |
| Editor frontend | Theia + React + Monaco, full LSP | React + Vite + Monaco, **no LSP** (regex parsers) |
| Three-tier split | main / backend / frontend (3 processes) | main / renderer (2 processes; CLI is child) |
| Build cache | persistent incremental (`internal/buildcache`) | core-only (`coreIsCached`) |
| Config | YAML + JSON Schema | YAML, no schema |
| Errors/diagnostics | structured codes + LSP | string + regex |
| Board model | full FQBN + variants/menus + profiles | partial FQBN |
| Plugins | discovery/monitor/programmer/protocol | none |
| Upload | USB/UART/JTAG/DFU | **+ wireless WiFi bridge (ESP32)** ← uniqueness |

**Net architectural difference**: Arduino's CLI/IDE are a **service-oriented,
typed-contract system** (protobuf + gRPC + LSP) where the backend is a network
service competitive enough to be reused by VSCode/CI/other tools. Companion's
CLI/IDE are a **monolith with a thin daemon** — the compiler and the UI share a
repo, communicate via subprocess + untyped HTTP, and the "service" surface is
only barely formalized (`openapi.yaml` exists but upload/compile stream through
ad-hoc JSON).

---

## 2. User-Facing Issues & Gaps (from real Arduino trackers)

### A. Arduino IDE 2.x — top community pain points (top-reaction open issues)

| Theme | Representative issue | Why users care |
|---|---|---|
| **No portable/U盘 mode** | #122 "Add a portable mode" | can't run off a USB stick / preserve config per-machine |
| **No plugin/extension system** | #58 "Missing support for external tools / plugins" (criticality high) | can't add custom uploaders, linters, board packs |
| **Serial Plotter limits** | #803 "Allow more data points in Plotter" | long logging sessions truncate/clip |
| **Serial Monitor is a fixed panel** | #289 "Tear off serial monitor window" | can't detach/move monitor while editing |
| **Serial Monitor missing basics** | #549 "save output to file", #812 "Missing Select All" | no export, no proper text handling |
| **Can't persist board per sketch** | #2438, #2573 "Use configuration from sketch project file" | re-selecting board/port every reopen |
| **Crash on launch (Linux)** | #2759 "Segmentation fault when launching IDE" | startup stability (Electron/GPU) |
| **Stale Electron** | #2424 "Electron 27 is EOL" | security + perf debt users feel as slowness |

### B. Arduino CLI — top community asks (top-reaction open issues)

| Theme | Representative issue | Why users care |
|---|---|---|
| **No `compile_commands.json`** | #849 | can't drive clangd/IDEs/CI tooling |
| **`sketch.yaml` can't declare custom libraries** | #2133 | project deps not self-contained |
| **Can't bundle libraries with a sketch** | #1255 | sharing a sketch = sharing its deps by hand |
| **`#pragma message` misclassified as error** | #2695 | noisy false errors confuse users |
| **"board listall" silently depends on installed cores** | #550 | "where is my board?" confusion |
| **No user-level `-D` cppflags / extra flags set** | #159, #846 | advanced users can't pass build defines cleanly |
| **Index download is very slow** | #2347 | first-run experience feels broken |
| **No CMake support** | #1973 | can't integrate into modern build systems |
| **No lib subfolder storage** | #1257 | library organization constraints |

### C. The underlying gaps (what the two issues lists share)

These are the **root-cause categories** behind most complaints:

1. **Build-system ergonomics** — no `compile_commands.json`, no CMake, no clean
   way to add cppflags/extra flags, slow index download, no sketch-local deps.
2. **Self-containedness** — no portable mode, no sketch-local config, no bundled
   deps (library include paths / subfolders).
3. **Extensibility** — no plugin system in either side; users can't add boards,
   uploaders, monitors, or linters without forking.
4. **Diagnostics quality** — misclassified messages (`#pragma message`), string
   parsing fragility, no true LSP (IDE side).
5. **Serial tooling** — monitor/plotter are the most-requested UX fixes (detach,
   save-to-file, select-all, more points).
6. **Stability/staleness** — Electron EOL, Linux segfaults, slow cold starts.

---

## 3. How Companion maps onto those gaps (opportunity)

- **Wins already**: Companion uniquely solves the cable problem (wireless ESP32
  bridge), is far lighter than Theia, and already has a serial plotter + monitor.
- **Gaps it shares with Arduino** (and should fix): no plugin system (#58/#1255
  equivalent), no portable/sketch-local config (#122/#2573), no
  `compile_commands.json` (#849), no incremental cache beyond core (#findings),
  no LSP (regex parsers), serial monitor lacks detach/save/select-all (#289/#549/#812).
- **Gaps Arduino has that Companion *doesn't* yet feel** (because it's newer):
  stale framework, segfaults, slow index — Companion should guard these early.