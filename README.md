# 🛰️ Companion

**Upload & program Arduino/ESP32 boards over WiFi — no USB cable, no cloud, no accounts.**

![Release](https://img.shields.io/github/v/release/Aryan-Rajyaguru-1/Companion?include_prereleases&label=release)
![License](https://img.shields.io/github/license/Aryan-Rajyaguru-1/Companion)
![Platforms](https://img.shields.io/badge/platform-Windows%20%7C%20Linux%20%7C%20macOS-blue)
![Stars](https://img.shields.io/github/stars/Aryan-Rajyaguru-1/Companion?style=social)

**Companion** pairs a from-scratch **Go CLI** with an **Electron IDE** that compile Arduino sketches locally and flash them *over the air* through a $5 ESP32 bridge — with serial monitor, serial plotter, and live GCC error squiggles in the editor.

## ✨ Why Companion?

- 📡 **Truly wireless upload** — flash Uno/Mega/Nano/ESP32 through an ESP32 bridge on your WiFi; leave the USB cable in the drawer
- 🚀 **Fleet OTA** — register boards once (name/MAC/tags), then `companion fleet push` flashes many at once with a confirm step, bounded concurrency, and a per-device result table
- 🔒 **100% local toolchain** — compiles on your machine, no cloud accounts, no telemetry
- ⚡ **Content-addressed build cache** — warm builds finish in seconds, not minutes
- 🖥️ **CLI-first + full IDE** — scriptable `companion` binary *and* a GUI with tabs, plotter, error markers
- ⚖️ **MIT-licensed** — no GPL obligations anywhere in the tree

## 🗂️ Repository layout

This repository is the workspace and source of truth. It contains two projects:

- `companion-cli/` — the Go CLI
- `companion-ide/` — the Electron IDE and bridge firmware

They are also published as the standalone repositories
[`Companion_cli`](https://github.com/Aryan-Rajyaguru-1/Companion_cli) and
[`Companion_IDE`](https://github.com/Aryan-Rajyaguru-1/Companion_IDE). A
manifest-driven workflow keeps those mirrors and the workspace `cli`/`ide`
branches synchronized when enabled. Split-only files such as each repository's
README and the sanitized firmware template are preserved. See
[docs/SPLIT_REPOS.md](docs/SPLIT_REPOS.md) for the manifest, setup, and safety
rules.

## 📥 Download prebuilt binaries

Grab the release for your OS — CLI binaries for Windows/Linux/macOS, plus a Linux `.deb` and `.AppImage` for the IDE:

**→ [Latest release](https://github.com/Aryan-Rajyaguru-1/Companion/releases/latest)**

Then run the one-command setup below — it builds the CLI from source if you have Go, or fetches the right prebuilt binary automatically.

## ⚡ One-command setup

**Step 1 — get the code** (if you already cloned it earlier, just run `git pull` inside the folder instead):

```bash
git clone https://github.com/Aryan-Rajyaguru-1/Companion.git
cd Companion

# later, to update an existing copy to the latest:
git pull
```

**Step 2 — run the setup:**

```bash
bash scripts/setup.sh          # macOS / Linux
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup.ps1   # Windows
```

> **On Windows?** Read **[docs/WINDOWS.md](docs/WINDOWS.md)** first — it covers the
> walls that trip up testers: SmartScreen on the unsigned binaries, serial
> drivers (CP210x/CH340), the 2.4 GHz-only bridge radio, Windows Firewall on
> port 3333, and the `py -m pip install esptool` step.

**Step 3 — check your environment before the first upload:**

```bash
companion doctor                 # toolchain, esptool/avrdude/Python, config perms
companion doctor --hub wss://<your-host>   # …and your relay, if you self-host one
```

It prints what is missing and the exact fix for your OS, and exits non-zero
when something required is absent — so a failure is explained here rather than
halfway through an upload.

## 🔄 Updating

The CLI can update itself from the project's GitHub releases:

```bash
companion --update                       # check and install the newest CLI
companion self-update                    # same command, discoverable in --help
companion self-update --check            # report only, no download
companion self-update --check --json     # machine-readable status (used by the IDE)
```

The updater selects the asset for your OS and architecture, verifies its
SHA-256 against the release's `SHA256SUMS.txt`, and replaces the binary
atomically. It is fail-closed: a release without the matching asset or checksum
entry is not installed. Use `--target <path>` when the running binary is in a
read-only location such as an AppImage or macOS app bundle, and `--force` to
reinstall the selected release.

In the IDE, choose **Help → Check for Updates…**. The panel reports both the
CLI and IDE versions. A CLI update installs to `~/.companion-cli/bin/`, which
the IDE prefers over its bundled copy on the next launch. An IDE update opens
the published installer for this platform, or the release page when no
compatible installer exists. The IDE does not silently replace its own
installation — that requires signed installer/updater metadata.

> Companion currently publishes alpha tags. The updater therefore considers the
> newest published release, including prereleases. Every release includes the
> six CLI binaries and `SHA256SUMS.txt`; IDE installers are optional for
> platforms that are not built (Linux arm64 and macOS x64 currently fall back to
> the release page).

## 🚀 Fleet OTA (batch flash)

Register your boards once, then update many over WiFi in one command:

```bash
companion fleet register 192.x.x.x kitchen-uno --mcu avr --tags kitchen,uno
companion fleet register 192.x.x.y office-esp32 --mcu esp32 --tags office
companion fleet list
companion fleet push firmware.bin @office            # flash the office boards only
```

Replace `192.x.x.x` / `192.x.x.y` with each board's address on your own network.

Or let mDNS find your boards for you:

```bash
companion fleet discover --register                  # scan + auto-add companion-XXXXXX boards
```

Names are positional (`register <host> [name]`), tags select groups (`@office`), and any selector also matches id/MAC/host/MCU substrings.

`fleet push` shows the exact target list and **asks for confirmation before
flashing anything** — then runs with bounded concurrency, one automatic retry
per failing device, and prints a per-device result table. Before the prompt it
runs an mDNS **identity preflight**: if a registered host now advertises a
different MAC (wrong/swapped board), the push hard-aborts; missing or drifted
advertisements are surfaced as warnings (`--no-verify` to skip).

Boards on the internet rather than your LAN? That's an opt-in extra — none of
the above needs it. Self-host a relay with the scripts in `deploy/`
(`install-relay-hub.sh`, plus `setup-tunnel.sh` if you want a public TLS
endpoint), flash the `RelayDevice` firmware with your endpoint, then
`companion ota upload <device-id> --ota-mode remote --relay-hub wss://<your-host>`.

The same relay also gives a no-radio target (Uno, Nano, STM32) the same choice:
flash `esp32_bridge` with `RELAY_MODE_REMOTE 1`, then either
`companion relay bridge --hub wss://<your-host> --device <bridge-id>` to expose
it as a local socket for any `socket://`/`net:` tool, or
`companion upload --ota-mode remote --relay-hub wss://<your-host> --relay-device <bridge-id>`.
Full walkthrough, security notes, and uninstall steps: `deploy/README.md`.

## 🤖 Drive it from any AI agent (MCP)

`companion mcp` turns the CLI into a **Model Context Protocol** server, so Claude
Desktop, Cursor, an IDE assistant or your own agent can check the environment,
compile, flash a target, and push firmware to a board on the other side of the
internet:

```bash
companion mcp --hub wss://ota.example.com --allow-upload
```

Tools that flash hardware are opt-in, and relay secrets come from the
environment rather than through the agent. Setup, client config and the safety
model: **[docs/MCP.md](docs/MCP.md)**.

## Manual setup

```bash
# 1. Build CLI
cd companion-cli && go mod tidy && go build -o companion .

# 2. Init
./companion config init && ./companion board update-index

# 3. Flash esp32_bridge.ino to your ESP32 WROOM
#    Add AP_SSID/AP_PASS and a unique BRIDGE_KEY to config.local.h first.

# 4. Run IDE
cd ../companion-ide && npm install && npm run dev

# 5. Set AP_SSID/AP_PASS and BRIDGE_KEY in config.local.h and flash. Join that
#    AP (or use STA mode), set the same bridge key in the CLI, then Upload.
#    There is no default AP password: the sketch refuses an open or placeholder AP.
```

### Bridge → target wiring (step 3)

```
        ESP32 bridge                              target MCU
  ┌───────────────────────┐                ┌──────────────────────┐
  │  GPIO17 (TX2)  ───────┼────────────────► RX                   │
  │  GPIO16 (RX2)  ◄──────┼───────────────── TX                   │
  │  GPIO4         ───────┼────────────────► EN / RST / NRST      │
  │  GPIO5         ───────┼────────────────► BOOT / GPIO0 / BOOT0 │
  │  GND           ───────┼───────────────── GND   ← REQUIRED     │
  └───────────────────────┘                └──────────────────────┘
```

- Classic 5 V targets (Uno / Nano / Mega) need a **bidirectional level shifter**
  on all four signal lines — the ESP32 is 3.3 V only. Never feed 5 V in.
- STM32 targets use the built-in UART bootloader only (BOOT0 + NRST
  sequencing); SWD is not supported.
- Full notes: the header comment of
  `companion-ide/esp32-bridge-firmware/esp32_bridge/esp32_bridge.ino`.

### Bridge security (LAN authentication)

The LAN bridge requires a **per-device shared key**. Before it accepts a
control command or forwards a single UART byte, the firmware sends a fresh
32-byte nonce and requires `HMAC-SHA256(BRIDGE_KEY, nonce)`. A missing, short,
or placeholder key disables the LAN TCP server entirely (fail closed).

Set it up once:

1. Generate a key and keep it out of git:

   ```bash
   openssl rand -hex 32
   ```

2. Put the **same** value in `config.local.h`, then reflash the bridge:

   ```c
   #define BRIDGE_KEY "paste-the-generated-value"
   ```

3. Configure the laptop. Store it in the owner-only CLI config without
   putting it in argv or shell history:

   ```bash
   read -rsp 'Bridge key: ' BRIDGE_KEY; echo
   printf '%s' "$BRIDGE_KEY" | companion config set bridge.key --stdin
   unset BRIDGE_KEY
   ```

   `--stdin` also keeps the key out of the process list. The IDE uses the same
   path. To inject it without writing a file instead:

   ```bash
   export COMPANION_BRIDGE_KEY='paste-the-generated-value'
   ```

4. Reconnect from the IDE. **Bridge Settings** shows only `<set>` / `<unset>`;
   the renderer never receives the secret. The Electron main process reads it
   from the CLI when it opens a LAN connection.

`companion config get bridge.key` and `companion config dump` print `<set>` or
`<unset>`, never the value. `companion config get bridge.key --reveal` is the
deliberate machine-readable disclosure path and prints the raw key without
color codes. The key lives in `~/.companion-cli/config.yaml` (mode `0600`).

**Upgrading an existing bridge:** a firmware build without `BRIDGE_KEY` now
refuses its LAN TCP server. This is not a brick — when `OTA_PASSWORD` is set,
the LAN OTA/mDNS recovery service still starts, so you can flash a corrected
firmware with `companion ota upload <bridge-ip>` (or by USB). Add the key,
reflash, and configure the laptop before the next LAN upload.

**Why a local proxy?** `esptool` (`socket://`) and `avrdude` (`net:`) cannot
perform the HMAC handshake themselves. For ESP/AVR uploads the CLI starts a
temporary proxy bound to `127.0.0.1`, authenticates each upstream connection,
and then pipes bytes unchanged. The relay path is different: `RELAY_MODE_REMOTE`
does not start the LAN server and does not use `BRIDGE_KEY`; the hub's
`DEVICE_TOKEN` and per-device secret authenticate that transport.

**Daemon API compatibility:** `/api/v1/upload` and `/api/v1/serial` treat an
omitted `bridgeMode` as `local`. Relay-aware clients must send `remote`
explicitly. A loopback host is not inferred to be a relay — that would bypass
authentication for an SSH-forwarded LAN bridge.

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
