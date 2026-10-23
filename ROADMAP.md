# Companion IDE + CLI — Roadmap from Arduino User-Pain Analysis

Method: (1) inventory of real, recurring user issues from `arduino/arduino-ide` and
`arduino/arduino-cli` (top-reacted issues, Sep 2026), (2) audit of which of those pains
Companion already solves — **verified in code, not assumed** — (3) prioritized phases for
what remains. No Arduino source was copied; reference trees stay in `Arduino for refs/`
(legal: purge before any release artifact).

---

## Part 1 — What Arduino IDE/CLI users actually complain about

Grouped from top-reacted issues:

| # | Pain (Arduino issue) | Category |
|---|----------------------|----------|
| 1 | Build/indexing performance — slow language-server indexing, full rebuilds (#2438, #714) | Build perf |
| 2 | No object-level build cache in CLI flows; every verify recompiles the world | Build perf |
| 3 | `compile_commands.json` export missing → no clangd/LSP integration (#849, top open CLI request) | Tooling |
| 4 | Platform-extra-flags story confusing for users and platform devs (#846) | Build config |
| 5 | `#pragma message` shown as error in IDE (#2695) | Diagnostics |
| 6 | Profiles can't use custom/local libraries (#2133); no sketch-bundled libraries (#1255) | Profiles |
| 7 | `board listall` quietly depends on installed cores; poor discoverability (#550, #1127) | Board mgmt |
| 8 | No default-board-per-sketch; board resets every session (#2438 IDE) | Board mgmt |
| 9 | STM32: "could not find upload tool" (#80) — external toolchain fragility | Upload |
| 10 | Serial monitor can't tear off into its own window (#289); plotter limited (#58) | Serial UX |
| 11 | No external tools/plugins in IDE (#58, "of high impact") | Extensibility |
| 12 | No portable mode / XDG compliance (#122, #1514-declined) | Packaging |
| 13 | Electron EOL drift (#2424); brew "no bottle available" (#1127) | Distribution |
| 14 | Zero first-party wireless/OTA upload story | **The gap Companion exists to fill** |

---

## Part 2 — Gap audit: does Companion already fill these?

### ✅ Filled (verified)

| Pain | Companion evidence |
|------|--------------------|
| #14 Wireless upload | Bridge protocol Go client (`internal/bridge/`), UART bootloaders for ESP32/AVR/STM32 (`internal/uploader/uploader.go`), AP+STA firmware v1.1 |
| #9 STM32 upload tool | Built-in AN3155 UART bootloader — no external STM32 tool needed (`uploader.go:340–500`) |
| #8 Default board per sketch | `sketch.yaml` profiles + `default_profile`, applied by compile and upload (`cmd/compile.go:198`, `cmd/upload.go:70`) |
| #6 Profile libraries | `companion profile lib add/remove` incl. local dirs (`profileLibDirs`, `cmd/compile.go:20`) |
| #5 Diagnostics quality | Structured `--json` diagnostics from compile (`cmd/compile.go:27+`) routed to Monaco via `error-parser.js`; `#pragma message` parses as `note:`, not error |
| #7 Board discoverability | 428-board `board listall` (Arduino-IDE-style grouping), `board search`, `board packages`, plus IDE `BoardAutoDetect` |
| #10 Plotter | `SerialPlotter.jsx` with multi-series + CSV export |
| IDE responsiveness | Daemon RPC with token auth, streaming compile, working cancel (`cmd/daemon.go`, `electron/companion-cli.js` BUG A fix) |
| Size-report honesty | SysV section parsing excludes ESP-IDF dummy placeholders (fixed today, `compiler.go:1045+`) |
| #1/#2 Build perf | Content-addressed `BuildCache` wired through CLI, daemon and upload (`Compiler.SetCache`, `internal/compiler/cache.go`); object and core archives are keyed by source/flags |
| Download integrity | `verifyArchiveChecksum` (boards) and `verifyFileChecksum` (libraries) compare the index's SHA-256 before extraction; a missing published checksum is refused unless `COMPANION_ALLOW_UNVERIFIED_INDEX=1` explicitly allows a controlled mirror |
| #3 compile_commands.json / LSP | `compile --export-compile-commands` emits clangd-compatible entries; `companion lsp` compiles then launches clangd |
| #10 Tear-off monitor | `monitor:tear-off` opens a second window with the same serial stream (`electron/main.js`, `src/main.jsx`) |
| #12 Portable mode | `--portable` / `COMPANION_PORTABLE=1` moves config, data, sketchbook and downloads beside the executable (`internal/config/config.go`) |
| OTA | `companion ota discover|upload|status|enable|disable`, `upload --ota`, bridge ArduinoOTA server and the IDE toggle are implemented |

### ⚠️ Partial — architecture exists, not active

| Pain | Status | Evidence |
|------|--------|----------|
| #11 Extensibility | Plugin system is loaded from builtins plus `<data>/plugins` and listed by `companion plugins list`; third-party plugin authoring still needs an external SDK story | `internal/plugins/`, `cmd/plugins.go` |

### ❌ Genuine gaps (nothing in codebase)

None from this audit as of 2026-10-19. Keep this section for the next audit
rather than leaving resolved items here as if they were still open.

---

## Part 3 — Roadmap (ordered by impact ÷ effort)

> **STATUS — ALL PHASES COMPLETE (2026-09-09; status corrected 2026-10-19).**
> Every item below is implemented. Exact test counts drift as suites change, so
> they are not repeated here: run `go test ./...`, `go vet ./...` and the IDE's
> `npm test` for the current result. New CLI surface:
> `companion ota discover|upload|status|enable|disable`, `companion plugins list`,
> `companion lsp`, `companion --portable`, `upload --ota`,
> `compile --export-compile-commands`.

### Phase 4a — Build cache activation + correctness ✅
1. ✅ `BuildCache` wired end-to-end: `Compiler.SetCache`, daemon + CLI + upload + OTA
   paths attach a cache honoring `cache.enabled`. Per-file `unitKey` (source SHA-256 +
   normalized flags + toolchain/compiler identity + schema version) serves/stores
   every .o; `.S`/`.s` handled by the same per-file path. `cacheOrDefault()` gives
   CLI users caching for free.
2. ✅ Core `coreCacheKey` = SHA-256 of every core source + variant + platform.txt/
   boards.txt/programmers.txt mtime + platform meta. The 24-hour ModTime heuristic
   and its stale-libcore-a flash hazard are GONE.
3. ✅ Daemon passes its cache; CLI/upload/OTA/`lsp` construct from config.
4. ✅ Config unknown-key help lists all 14 keys (`cache.*`, `daemon.*`, `library.*`).

**Proof:** second identical verify: `27.2s → 2.6s`, `[cache] hit sketch.ino.cpp`,
`Core: using cached libcore.a (content-verified)`; object count grows in cache.stats.

### Phase 4b — Trust & toolchain integration ✅
5. ✅ `verifyArchiveChecksum` in the boards/tool install path: SHA-256 compared
   (constant-time) before extract, hard-fail on mismatch or a missing checksum;
   `COMPANION_ALLOW_UNVERIFIED_INDEX=1` is the explicit escape hatch for a
   controlled mirror. Libraries use the same policy.
6. ✅ `compile --export-compile-commands` writes clangd-compatible
   `compile_commands.json` (60 TUs captured on a real ESP32-S3 sketch — **proven**
   complete even on warm-core builds via per-core TU snapshot+merge).

### Phase 4c — OTA (the differentiator) ✅
> **Warm-build validation note (2026-09-09):** the final warm-build proof was blocked by a
> real bug chain, now fixed and regression-tested:
> ① `unitKey` normalized flags with prefix-only volatile dirs, leaving the random per-run
> temp-dir suffix in the key (`companion_build_<hash>_<pid>_<rand>`); ② `coreCacheKey`
> hashed the preprocessor flags with the same prefix-only normalization — same suffix leak,
> so the core key changed every invocation (3 `libcore.a` entries minted in 10 min).
> Both fixed by adding the actual build dir to the volatile list (`buildDirFromArgs` for
> unit keys, `bf.buildDir` for the core key). Final evidence: build9 compiled the
> ESP32-S3 bridge firmware in **4.7s with zero compiles**, `.a` count stable across runs,
> full `go test ./...` suite and `go vet ./...` were green at that time.
> ③ `hashGeneratedHeader` (new, cache.go): sdkconfig.h now folded into the core key by
> sorted `CONFIG_*` macro CONTENT (comments/volatile path ignored), so a regenerated-but-
> identical sdkconfig no longer mints a new archive; generator change still invalidates.
> ④ `TestCoreCacheKeyStableAcrossBuildDirs`, `TestNormalizeFlagsCollapsesNestedDirs` added.
> **`companion lsp` smoke-verified (2026-09-09):** `--fqbn` flag added (explicit flag wins
> over profile/sketch.yaml — the daemon-generated sketch.yaml carries no `fqbn:` key);
> generated a 2.7 MB compile_commands.json with all **60 TUs** for the bridge sketch;
> clean "clangd not found" fallback with per-OS install hints. Cross-platform hardening:
> `buildDirVolatileDirs` now derives from `os.TempDir()` (was hardcoded `/tmp/...` —
> would have broken all warm caching on Windows `%TEMP%` / macOS `/var/folders`).
7. ✅ `companion ota discover|upload|status|enable|disable` + `companion upload --ota`
   (mDNS auto-discovery + explicit-IP fallback, progress bars, password via
   `--auth`/`sha256:` pre-hash).
8. ✅ Bridge firmware v1.2: ArduinoOTA server mode (`OTA_HOSTNAME`/`OTA_PASSWORD`
   config, `.local` mDNS, port 3232), CMD_QUERY reports `ota=on(mdns=…,port=3232)`.
   The bridge itself is now re-flashable over WiFi (`companion ota upload <ip>`).
9. ✅ IDE: BridgeSettings "Wireless OTA" section (toggle + password, auto-loads
   state on open from `ota status`), persisted per-sketch in sketch.yaml `ota: true`
   via `ota toggle` IPC; the upload path routes through `otaUpload` for ESP boards.

### Phase 5 — Activate the dormant architecture ✅
10. ✅ Plugin system live: `plugins.LoadAll` (builtins + `.so` from `<data>/plugins`),
    type-switch registration, `companion plugins list`. First-party plugins ship:
    `companion.uploader.ota` (ArduinoOTA uploader, routed through `UploaderFor(fqbn)`
    in `upload --ota`) and `companion.tools.meta-export` (writes `companion-meta.json`
    per build). Unit tests cover loading/listing/diagnostics.
11. ✅ Tear-off serial monitor: `monitor:tear-off` IPC opens a second BrowserWindow
    loading the same SerialMonitor component standalone; bridge data fans out to
    both windows; embedded panel closes on tear-off. (Electron + preload + main.jsx
    + component; the IDE suite is green.)
12. ✅ Portable mode: `COMPANION_PORTABLE=1` env + `companion --portable` global flag
    move ALL state (data dir, config, sketchbook, downloads) next to the executable.
    Verified: `config get directories.data` resolves to the exe dir.

### Phase 6 — Polish / distribution ✅

13. ✅ `companion lsp [dir]` — compiles (warm-cache, `--export-compile-commands`),
    then execs clangd with `--compile-commands-dir` so any LSP editor gets real
    IntelliSense (closes Arduino-cli #849 end-to-end).
14. ✅ `docs/RELEASING.md` — Electron upgrade cadence (≤2 majors, pinned versions),
    macOS/Windows signing, brew tap mirroring the Makefile's 4-binary `build-all`
    matrix. `make -C companion-cli publish` builds a publish bundle.
15. ✅ Legal hygiene: `Arduino for refs/` + analysis .md files are now in `.gitignore`
    (never committed), and the `publish` target excludes them — MIT claim stays valid.
16. ✅ `companion fleet list|register|remove|push` — durable device registry
    (`devices.yaml` in the data dir, keyed by name/MAC-hostname with mcu + tags),
    selector engine (`@tag` / substring AND), and **batch OTA push with a
    mandatory confirm step showing the exact resolved target list**, bounded
    concurrency worker pool (semaphore, never full-parallel), one automatic
    retry pass per failing device, a per-device result table, a single shared
    compile for the whole batch, and prompt Ctrl-C abort. Unit-tested
    (`internal/fleet`: select/tag/match, persistence round-trip, retry,
    concurrency cap, cancellation) and e2e-smoke-tested against the real
    binary incl. both confirm paths.
    **Anti-wrong-board hardening:** `fleet push` runs an mDNS **identity
    preflight** before the confirm prompt — each target's live advertisement is
    matched against the registry (MAC-suffix mismatch → hard abort, missing
    advertisement / name drift → warn, address or name reuse across entries →
    fail) so a swapped board can't silently receive another device's firmware
    (`--no-verify` opts out explicitly). `fleet discover [--register]` mDNS-browses
    the network and can auto-seed/refresh the registry with the advertised
    `companion-XXXXXX` identity.

---

## Explicitly NOT roadmap items
- Copying arduino-cli's command surface 1:1 — Companion's value is the wireless pipeline +
  honest diagnostics, not CLI parity for its own sake.
- gRPC: the JSON daemon API is simpler for the Electron side and already working; revisit
  only if a third-party client ecosystem demands it.


